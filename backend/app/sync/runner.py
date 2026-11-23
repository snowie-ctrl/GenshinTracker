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

from app.config import GAPS_DEBOUNCE_SECONDS, MANUAL_SYNC_MIN_SECONDS
from app.db.models import GapRun, SyncRun
from app.planner.requests import build_inputs, gap_requests, has_work, snapshot
from app.settings.store import get_setting, set_setting
from app.sync.backup import backup_db
from app.sync.chronicle import character_ids, to_json
from app.sync.hoyolab import AuthExpired, HoyolabSource
from app.sync.persist import (load_talent_ids, save_challenge_runs, save_details, save_gap_failure, save_gaps,
                              save_notes, save_roster, save_snapshot, save_talent_ids, unknown_character_ids)
from app.timeutil import utcnow

log = logging.getLogger(__name__)
CHRONICLE_PARTS = ("calendar", "profile", "challenges")
PARTS = ("roster", "details", "notes", "gaps", *CHRONICLE_PARTS)
FRESH_MINUTES = 60
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
    """Last finished run whose roster part succeeded. A part that keeps failing for an
    account-setting reason (e.g. Real-Time Notes disabled) must not shorten the interval."""
    runs = session.scalars(
        select(SyncRun).where(SyncRun.finished_at.is_not(None), SyncRun.trigger != "gaps")
        .order_by(SyncRun.id.desc()).limit(20)
    )
    for run in runs:
        if (run.parts or {}).get("roster", {}).get("ok"):
            return run
    return None


def last_part_success(session: Session, part: str) -> datetime | None:
    runs = session.scalars(select(SyncRun).where(SyncRun.finished_at.is_not(None), SyncRun.trigger != "gaps")
                           .order_by(SyncRun.id.desc()).limit(50))
    for run in runs:
        p = (run.parts or {}).get(part) or {}
        if p.get("ok") and "skipped" not in p:
            return run.started_at
    return None


def _failure(e: Exception) -> dict:
    return {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}


class SyncManager:
    def __init__(self, session_factory: sessionmaker, db_file: Path, backups_dir: Path,
                 source_factory: Callable[[], HoyolabSource | None],
                 on_unknown_ids: Callable[[set[int]], Awaitable[None]],
                 clock: Callable[[], datetime] = utcnow, gaps_delay: float = GAPS_DEBOUNCE_SECONDS):
        self._sf = session_factory
        self._db_file = db_file
        self._backups_dir = backups_dir
        self._source_factory = source_factory
        self._on_unknown_ids = on_unknown_ids
        self._clock = clock
        self._task: asyncio.Task | None = None
        self._run_id: int | None = None
        self._run_trigger: str | None = None
        self._auth_generation = 0
        self._gaps_delay = gaps_delay
        self._gaps_timer: asyncio.Task | None = None
        self._gaps_queued = False

    def invalidate_auth(self) -> None:
        """Called when new cookies are saved: an in-flight run with the old cookie must not
        mark the account expired afterwards."""
        self._auth_generation += 1

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    @property
    def gaps_pending(self) -> bool:
        timer = self._gaps_timer is not None and not self._gaps_timer.done()
        return timer or self._gaps_queued

    @property
    def gaps_running(self) -> bool:
        """A gaps-only recalculation is in progress (a full sync's gaps part does not count)."""
        return self.running and self._run_trigger == "gaps"

    async def wait(self) -> None:
        while True:
            if self._gaps_timer is not None and not self._gaps_timer.done():
                # asyncio.wait does not raise if schedule_gaps() cancels the timer meanwhile
                await asyncio.wait({self._gaps_timer})
                continue
            if self._task is not None and not self._task.done():
                await self._task
                await asyncio.sleep(0)  # let the done callback start a queued gaps run
                continue
            return

    def schedule_gaps(self) -> None:
        """Recalculate gaps a few seconds after the last edit; later edits restart the timer.

        Must be called from inside the running event loop (e.g. from an async def handler)."""
        if self._gaps_timer is not None and not self._gaps_timer.done():
            self._gaps_timer.cancel()
        self._gaps_timer = asyncio.create_task(self._gaps_after_delay())

    async def _gaps_after_delay(self) -> None:
        await asyncio.sleep(self._gaps_delay)
        self.start_gaps()

    def start_gaps(self) -> SyncRequestResult:
        if self.running:
            self._gaps_queued = True
            return SyncRequestResult(self._run_id, False, "queued")
        source = self._source_factory()
        if source is None:
            return SyncRequestResult(None, False, "not_connected")
        with self._sf.begin() as s:
            run = SyncRun(started_at=self._clock(), trigger="gaps", parts={})
            s.add(run)
            s.flush()
            run_id = run.id
        self._run_id = run_id
        self._run_trigger = "gaps"
        self._task = asyncio.create_task(self._run_gaps_only(run_id, source, self._auth_generation))
        self._task.add_done_callback(self._on_task_done)
        return SyncRequestResult(run_id, True, "started")

    def _on_task_done(self, _task: asyncio.Task) -> None:
        if self._gaps_queued:
            self._gaps_queued = False
            self.start_gaps()

    async def _gaps_part(self, source: HoyolabSource) -> tuple[dict, set[int]]:
        """Raises AuthExpired; any other failure is recorded and returned as a failed part."""
        try:
            with self._sf() as s:
                inputs, skipped = build_inputs(s)
                snap = snapshot(s)
                cache = load_talent_ids(s)
            work = [i for i in inputs if has_work(i)]
            missing = [i for i in work if i.character_id not in cache]
            for i in missing:
                cache[i.character_id] = await source.get_talent_ids(i.avatar_id, i.element_attr_id)
            if missing:
                with self._sf.begin() as s:
                    save_talent_ids(s, cache)
            result = await source.compute_gaps(gap_requests(work, cache)) if work else None
            with self._sf.begin() as s:
                unknown = save_gaps(s, result, snap, skipped, self._clock())
            part: dict = {"ok": True, "count": len(work)}
            if skipped:
                part["skipped"] = skipped
            return part, unknown
        except AuthExpired:
            raise
        except Exception as e:  # isolated like every other part
            log.warning("Sync part gaps failed: %s", type(e).__name__)
            failure = _failure(e)
            with self._sf.begin() as s:
                save_gap_failure(s, failure["error"], self._clock())
            return failure, set()

    async def _chronicle_part(self, part: str, source: HoyolabSource) -> tuple[dict, set[int]]:
        now = self._clock()
        if part == "calendar":
            cal = await source.get_calendar()
            with self._sf.begin() as s:
                save_snapshot(s, "calendar", to_json(cal), now)
                return {"ok": True, "count": len(cal.events)}, unknown_character_ids(s, character_ids(cal))
        if part == "profile":
            profile = await source.get_profile()
            with self._sf.begin() as s:
                save_snapshot(s, "profile", to_json(profile), now)
            return {"ok": True}, set()
        runs = await source.get_challenges()
        with self._sf.begin() as s:
            count = save_challenge_runs(s, runs, now)
            return {"ok": True, "count": count}, unknown_character_ids(s, character_ids(runs))

    async def _run_gaps_only(self, run_id: int, source: HoyolabSource, generation: int) -> None:
        parts: dict[str, dict] = {}
        unknown: set[int] = set()
        try:
            try:
                parts["gaps"], unknown = await self._gaps_part(source)
            except AuthExpired:
                parts["gaps"] = {"ok": False, "error": EXPIRED_MSG}
                if generation == self._auth_generation:
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

    @staticmethod
    def _gaps_outdated(session: Session) -> bool:
        """Build goals differ from the last successful calculation (or were never calculated)."""
        run = session.get(GapRun, 1)
        stored = run.snapshot if run is not None else None
        return (stored or []) != snapshot(session)

    async def request(self, trigger: str) -> SyncRequestResult:
        while self.running and self._run_trigger == "gaps":
            # a gaps-only run has no roster/details/notes: let it finish, then sync for real
            await asyncio.wait({self._task})
        if self.running:
            return SyncRequestResult(self._run_id, False, "joined")
        now = self._clock()
        skip: SyncRequestResult | None = None
        gaps_outdated = False
        with self._sf() as s:
            last = s.scalars(select(SyncRun).where(SyncRun.trigger != "gaps")
                             .order_by(SyncRun.id.desc()).limit(1)).first()
            elapsed = (now - last.started_at).total_seconds() if last else None
            if trigger == "manual" and elapsed is not None and elapsed < MANUAL_SYNC_MIN_SECONDS:
                raise SyncTooSoon(int(MANUAL_SYNC_MIN_SECONDS - elapsed))
            if trigger == "auto":
                ok = last_successful(s)
                interval = timedelta(minutes=int(get_setting(s, "sync_interval_minutes")))
                if ok is not None and now - ok.finished_at < interval:
                    skip = SyncRequestResult(ok.id, False, "fresh")
                elif elapsed is not None and elapsed < MANUAL_SYNC_MIN_SECONDS:
                    skip = SyncRequestResult(last.id, False, "recent")
                if skip is not None:
                    gap_run = s.get(GapRun, 1)
                    # after a failed calculation only an edit or the interval sync retries: not every page load
                    gaps_outdated = (gap_run is None or gap_run.ok is not False) and self._gaps_outdated(s)
        if skip is not None:
            if gaps_outdated and not self.gaps_pending:
                self.start_gaps()  # e.g. goals edited before a restart, or Build goals from before the upgrade
            return skip
        source = self._source_factory()
        if source is None:
            return SyncRequestResult(None, False, "not_connected")
        with self._sf.begin() as s:
            run = SyncRun(started_at=now, trigger=trigger, parts={})
            s.add(run)
            s.flush()
            run_id = run.id
        self._run_id = run_id
        self._run_trigger = trigger
        self._task = asyncio.create_task(self._run(run_id, source, self._auth_generation))
        self._task.add_done_callback(self._on_task_done)
        return SyncRequestResult(run_id, True, "started")

    async def _run(self, run_id: int, source: HoyolabSource, generation: int) -> None:
        trigger = self._run_trigger
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

            if not expired:
                if roster is None:
                    parts["gaps"] = {"ok": False, "error": "skipped: roster failed"}
                else:
                    try:
                        parts["gaps"], gap_unknown = await self._gaps_part(source)
                        unknown |= gap_unknown
                    except AuthExpired:
                        expired = True

            for part in CHRONICLE_PARTS:
                if expired:
                    break
                if trigger not in ("manual", "connect"):
                    with self._sf() as s:
                        last = last_part_success(s, part)
                    if last is not None and self._clock() - last < timedelta(minutes=FRESH_MINUTES):
                        parts[part] = {"ok": True, "skipped": "fresh"}
                        continue
                try:
                    parts[part], found = await self._chronicle_part(part, source)
                    unknown |= found
                except AuthExpired:
                    expired = True
                except Exception as e:
                    log.warning("Sync part %s failed: %s", part, type(e).__name__)
                    parts[part] = _failure(e)

            if expired:
                for part in PARTS:
                    parts.setdefault(part, {"ok": False, "error": EXPIRED_MSG})
                if generation == self._auth_generation:  # cookie not replaced meanwhile
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
