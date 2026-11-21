"""One wish import at a time: (link) → backup → read → merge in one transaction → UIGF snapshot."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from app.config import APP_VERSION, WISH_BACKUPS_KEPT, Paths
from app.db.models import Wish, WishImport
from app.servertime import offset_hours
from app.settings.envfile import read_env
from app.settings.store import get_setting
from app.sync.backup import backup_db
from app.timeutil import iso, utcnow
from app.wishes.authkey import WishLink, link_status
from app.wishes.fetch import (LINK_EXPIRED, FetchFailed, PageFn, WishLinkExpired, fetch_new, record_uid,
                              to_incoming)
from app.wishes.merge import merge
from app.wishes.paimon_xlsx import parse_paimon_xlsx
from app.wishes.types import NEEDS_UID, UID_MISMATCH, ImportFailed, IncomingWish
from app.wishes.uigf import NOT_UIGF, build_uigf, parse_uigf

log = logging.getLogger(__name__)
FETCH_FAILED = "Couldn't read the wish history ({kind}). Try again in a minute."
INTERRUPTED = "Interrupted: the app was closed during the import."


class ImportBusy(Exception):
    pass


def import_dict(row: WishImport) -> dict:
    return {"id": row.id, "source": row.source, "started_at": iso(row.started_at),
            "finished_at": iso(row.finished_at), "ok": row.ok, "added": row.added,
            "upgraded": row.upgraded, "skipped": row.skipped, "error": row.error}


class WishImporter:
    def __init__(self, session_factory: sessionmaker, paths: Paths,
                 link_reader: Callable[[str], WishLink], page_factory: Callable[[WishLink], PageFn],
                 on_unknown: Callable[[set[str]], Awaitable[None]], clock=utcnow, sleep=asyncio.sleep):
        self._sf = session_factory
        self._paths = paths
        self._link_reader = link_reader
        self._page_factory = page_factory
        self._on_unknown = on_unknown
        self._clock = clock
        self._sleep = sleep
        self._busy = False
        self._source: str | None = None
        self._current_id: int | None = None
        self._task: asyncio.Task | None = None
        with session_factory.begin() as s:
            s.execute(update(WishImport).where(WishImport.ok.is_(None))
                      .values(ok=False, error=INTERRUPTED, finished_at=clock()))

    @property
    def running(self) -> bool:
        return self._busy

    async def start_game(self) -> int:
        if self._busy:
            if self._source == "game" and self._current_id is not None:
                return self._current_id
            raise ImportBusy()
        import_id = self._begin("game")
        self._task = asyncio.create_task(self._run(import_id, "game", self._prepare_game, self._read_game))
        return import_id

    async def import_file(self, filename: str, content: bytes) -> dict:
        if self._busy:
            raise ImportBusy()
        source = "paimon" if filename.lower().endswith(".xlsx") else "uigf"
        import_id = self._begin(source)

        async def prepare():
            return None

        async def read(_ctx, uid: int, offset: int) -> list[IncomingWish]:
            return await asyncio.to_thread(self._parse_file, source, content, uid, offset)

        await self._run(import_id, source, prepare, read)
        return self.status()

    async def wait(self) -> None:
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)

    def status(self) -> dict:
        with self._sf() as s:
            row = s.scalars(select(WishImport).order_by(WishImport.id.desc()).limit(1)).first()
            return {"running": self._busy, "last": None if row is None else import_dict(row)}

    def cache_status(self) -> dict:
        with self._sf() as s:
            game_path = get_setting(s, "game_install_path")
        return link_status(lambda: self._link_reader(game_path))

    # --- internals -------------------------------------------------------
    def _begin(self, source: str) -> int:
        self._busy, self._source = True, source
        try:
            with self._sf.begin() as s:
                row = WishImport(started_at=self._clock(), source=source, ok=None, added=0, upgraded=0, skipped=0)
                s.add(row)
                s.flush()
                self._current_id = row.id
        except Exception:
            self._busy = False
            raise
        return self._current_id

    def _account(self) -> tuple[int, int]:
        env = read_env(self._paths.env_file)
        if not env.get("GENSHIN_UID"):
            raise ImportFailed(NEEDS_UID)
        return int(env["GENSHIN_UID"]), offset_hours(env.get("GENSHIN_REGION"))

    async def _prepare_game(self) -> WishLink:
        with self._sf() as s:
            game_path = get_setting(s, "game_install_path")
        return await asyncio.to_thread(self._link_reader, game_path)

    async def _read_game(self, link: WishLink, uid: int, offset: int) -> list[IncomingWish]:
        with self._sf() as s:
            known = set(s.scalars(select(Wish.id).where(Wish.id.is_not(None))))
        try:
            raw = await fetch_new(self._page_factory(link), known, sleep=self._sleep)
        except WishLinkExpired:
            raise ImportFailed(LINK_EXPIRED) from None
        except FetchFailed as e:
            raise ImportFailed(FETCH_FAILED.format(kind=e.kind)) from None
        found = record_uid(raw)
        if found is not None and found != uid:
            raise ImportFailed(UID_MISMATCH)
        try:
            return [to_incoming(r) for r in raw]
        except (KeyError, ValueError, TypeError) as e:
            raise ImportFailed(f"Unexpected wish data from the server ({type(e).__name__}).") from None

    def _parse_file(self, source: str, content: bytes, uid: int, offset: int) -> list[IncomingWish]:
        if source == "paimon":
            return parse_paimon_xlsx(content)
        try:
            data = json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ImportFailed(NOT_UIGF) from None
        return parse_uigf(data, uid, offset)

    def _write_snapshot(self, uid: int, offset: int) -> str:
        now = self._clock()
        with self._sf() as s:
            rows = list(s.scalars(select(Wish)))
        data = build_uigf(rows, uid, offset, now, APP_VERSION)
        path = self._paths.wish_backups / f"uigf-{now:%Y%m%d-%H%M%S-%f}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        for old in sorted(self._paths.wish_backups.glob("uigf-*.json"))[:-WISH_BACKUPS_KEPT]:
            old.unlink()
        return path.name

    def _finish(self, import_id: int, *, ok: bool, result=None, error: str | None = None,
                backup: str | None = None, snapshot: str | None = None) -> None:
        with self._sf.begin() as s:
            row = s.get(WishImport, import_id)
            row.ok, row.error, row.finished_at = ok, error, self._clock()
            row.backup_file, row.snapshot_file = backup, snapshot
            if result is not None:
                row.added, row.upgraded, row.skipped = result.added, result.upgraded, result.skipped

    async def _run(self, import_id: int, source: str, prepare, read) -> None:
        backup_name = None
        try:
            uid, offset = self._account()
            ctx = await prepare()
            backup = await asyncio.to_thread(backup_db, self._paths.db_file, self._paths.wish_backups,
                                             self._clock(), WISH_BACKUPS_KEPT)
            backup_name = backup.name if backup is not None else None
            incoming = await read(ctx, uid, offset)
            with self._sf.begin() as s:
                result = merge(s, incoming, source, self._clock())
            snapshot = None
            try:
                snapshot = await asyncio.to_thread(self._write_snapshot, uid, offset)
            except OSError as e:
                log.warning("Wish snapshot failed: %s", type(e).__name__)
            self._finish(import_id, ok=True, result=result, backup=backup_name, snapshot=snapshot)
            if result.unknown_names:
                try:
                    await self._on_unknown(result.unknown_names)
                except Exception as e:  # noqa: BLE001
                    log.warning("Game-data refresh after a wish import failed: %s", type(e).__name__)
        except ImportFailed as e:
            self._finish(import_id, ok=False, error=e.message, backup=backup_name)
        except Exception as e:  # noqa: BLE001 - never str(e): network errors can carry the wish URL
            log.warning("Wish import failed: %s", type(e).__name__)
            self._finish(import_id, ok=False, error=f"Import failed ({type(e).__name__}).", backup=backup_name)
        finally:
            self._busy = False
