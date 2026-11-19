"""Background sync: one run at a time; each part independent; never touches user data."""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import MANUAL_SYNC_MIN_SECONDS
from app.db.models import SyncRun
from app.settings.store import get_setting, set_setting
from app.sync.backup import backup_db
from app.sync.hoyolab import AuthExpired, HoyolabSource
from app.sync.persist import save_details, save_notes, save_roster
from app.timeutil import utcnow

log = logging.getLogger(__name__)
PARTS = ("roster", "details", "notes")
EXPIRED_MSG = "skipped: HoYoLAB login expired"


class SyncTooSoon(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"retry after {retry_after}s")
        self.retry_after = retry_after


@dataclass(frozen=True)
class SyncRequestResult:
    run_id: int | None
    started: bool
    reason: str


def last_successful(session: Session) -> SyncRun | None:
    runs = session.scalars(
        select(SyncRun).where(SyncRun.finished_at.is_not(None)).order_by(SyncRun.id.desc()).limit(20)
    )
    for run in runs:
        if run.parts and all(p.get("ok") for p in run.parts.values()):
            return run
    return None


def _failure(e: Exception) -> dict:
    return {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}


class SyncManager:
    def __init__(self, session_factory: sessionmaker, db_file: Path, backups_dir: Path,
                 source_factory: Callable[[], HoyolabSource | None],
                 on_unknown_ids: Callable[[set[int]], Awaitable[None]],
                 clock: Callable[[], datetime] = utcnow):
        self._sf = session_factory
        self._db_file = db_file
        self._backups_dir = backups_dir
        self._source_factory = source_factory
        self._on_unknown_ids = on_unknown_ids
        self._clock = clock
        self._task: asyncio.Task | None = None
        self._run_id: int | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def wait(self) -> None:
        if self._task is not None:
            await self._task

    async def request(self, trigger: str) -> SyncRequestResult:
        if self.running:
            return SyncRequestResult(self._run_id, False, "joined")
        now = self._clock()
        with self._sf() as s:
            last = s.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(1)).first()
            elapsed = (now - last.started_at).total_seconds() if last else None
            if trigger == "manual" and elapsed is not None and elapsed < MANUAL_SYNC_MIN_SECONDS:
                raise SyncTooSoon(int(MANUAL_SYNC_MIN_SECONDS - elapsed))
            if trigger == "auto":
                ok = last_successful(s)
                interval = timedelta(minutes=int(get_setting(s, "sync_interval_minutes")))
                if ok is not None and now - ok.finished_at < interval:
                    return SyncRequestResult(ok.id, False, "fresh")
                if elapsed is not None and elapsed < MANUAL_SYNC_MIN_SECONDS:
                    return SyncRequestResult(last.id, False, "recent")
        source = self._source_factory()
        if source is None:
            return SyncRequestResult(None, False, "not_connected")
        with self._sf.begin() as s:
            run = SyncRun(started_at=now, trigger=trigger, parts={})
            s.add(run)
            s.flush()
            run_id = run.id
        self._run_id = run_id
        self._task = asyncio.create_task(self._run(run_id, source))
        return SyncRequestResult(run_id, True, "started")

    async def _run(self, run_id: int, source: HoyolabSource) -> None:
        parts: dict[str, dict] = {}
        unknown: set[int] = set()
        try:
            try:
                backup_db(self._db_file, self._backups_dir, self._clock())
            except (OSError, sqlite3.Error) as e:
                log.warning("Database backup failed: %s", e)

            expired = False
            roster = None
            try:
                roster = await source.get_roster()
                with self._sf.begin() as s:
                    unknown = save_roster(s, roster, self._clock())
                parts["roster"] = {"ok": True, "count": len(roster)}
            except AuthExpired:
                expired = True
            except Exception as e:  # each part is isolated by design
                log.warning("Sync part roster failed: %s", type(e).__name__)
                parts["roster"] = _failure(e)

            if not expired:
                if roster is None:
                    parts["details"] = {"ok": False, "error": "skipped: roster failed"}
                else:
                    try:
                        details = await source.get_details([r.raw_id for r in roster])
                        with self._sf.begin() as s:
                            save_details(s, details)
                        parts["details"] = {"ok": True, "count": len(details)}
                    except AuthExpired:
                        expired = True
                    except Exception as e:
                        log.warning("Sync part details failed: %s", type(e).__name__)
                        parts["details"] = _failure(e)

            if not expired:
                try:
                    notes = await source.get_notes()
                    with self._sf.begin() as s:
                        save_notes(s, notes, self._clock())
                    parts["notes"] = {"ok": True}
                except AuthExpired:
                    expired = True
                except Exception as e:
                    log.warning("Sync part notes failed: %s", type(e).__name__)
                    parts["notes"] = _failure(e)

            if expired:
                for part in PARTS:
                    parts.setdefault(part, {"ok": False, "error": EXPIRED_MSG})
                with self._sf.begin() as s:
                    set_setting(s, "hoyolab_status", "expired")
        finally:
            with self._sf.begin() as s:
                run = s.get(SyncRun, run_id)
                run.finished_at = self._clock()
                run.parts = parts
        if unknown:
            try:
                await self._on_unknown_ids(unknown)
            except Exception as e:
                log.warning("Game data refresh after unknown ids failed: %s", type(e).__name__)
