import asyncio
from datetime import datetime

import pytest

from app.db.models import LiveNotes, OwnedCharacter, SyncRun
from app.settings.store import get_setting, set_setting
from app.sync.hoyolab import AuthExpired, HoyolabError
from app.sync.runner import SyncManager, SyncTooSoon
from fakes import Clock, FakeSource, make_roster
from helpers import seed_game

START = datetime(2026, 11, 19, 12, 0, 0)


def manager(paths, session_factory, source, clock=None, unknown_sink=None):
    async def on_unknown(ids):
        if unknown_sink is not None:
            unknown_sink.append(ids)

    return SyncManager(session_factory, paths.db_file, paths.backups,
                       lambda: source, on_unknown, clock=clock or Clock(START))


def last_run(session_factory) -> SyncRun:
    with session_factory() as s:
        return s.query(SyncRun).order_by(SyncRun.id.desc()).first()


async def test_full_sync_saves_everything(paths, session_factory):
    seed_game(session_factory)
    m = manager(paths, session_factory, FakeSource())
    result = await m.request("manual")
    await m.wait()
    assert result.started and result.reason == "started"
    run = last_run(session_factory)
    assert run.finished_at is not None
    assert run.parts == {"roster": {"ok": True, "count": 2}, "details": {"ok": True, "count": 2},
                         "notes": {"ok": True}}
    with session_factory() as s:
        assert s.get(OwnedCharacter, 10000032).talent_burst == 8
        assert s.get(LiveNotes, 1).resin == 153
    assert len(list(paths.backups.glob("tracker-*.db"))) == 1


async def test_details_failure_does_not_block_notes(paths, session_factory):
    seed_game(session_factory)
    m = manager(paths, session_factory, FakeSource(fail={"details": HoyolabError("boom")}))
    await m.request("manual")
    await m.wait()
    parts = last_run(session_factory).parts
    assert parts["details"] == {"ok": False, "error": "HoyolabError: boom"}
    assert parts["roster"]["ok"] and parts["notes"]["ok"]


async def test_roster_failure_skips_details_but_runs_notes(paths, session_factory):
    source = FakeSource(fail={"roster": HoyolabError("down")})
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    parts = last_run(session_factory).parts
    assert parts["roster"]["ok"] is False
    assert parts["details"] == {"ok": False, "error": "skipped: roster failed"}
    assert parts["notes"]["ok"] is True
    assert not any(isinstance(c, tuple) for c in source.calls)


async def test_expired_cookie_marks_status_and_stops(paths, session_factory):
    source = FakeSource(fail={"roster": AuthExpired("not logged in")})
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    parts = last_run(session_factory).parts
    assert all(p == {"ok": False, "error": "skipped: HoYoLAB login expired"} for p in parts.values())
    assert source.calls == ["roster"]
    with session_factory() as s:
        assert get_setting(s, "hoyolab_status") == "expired"


async def test_auto_respects_interval(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    source = FakeSource()
    m = manager(paths, session_factory, source, clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(minutes=5)
    assert (await m.request("auto")).reason == "fresh"
    clock.advance(minutes=6)
    assert (await m.request("auto")).reason == "started"
    await m.wait()


async def test_auto_skips_right_after_a_failed_run(paths, session_factory):
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(fail={"notes": HoyolabError("x")}), clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(seconds=30)
    assert (await m.request("auto")).reason == "recent"


async def test_manual_limited_to_once_per_minute(paths, session_factory):
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(), clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(seconds=20)
    with pytest.raises(SyncTooSoon) as exc:
        await m.request("manual")
    assert exc.value.retry_after == 40
    clock.advance(seconds=41)
    assert (await m.request("manual")).started
    await m.wait()


async def test_second_request_joins_running_sync(paths, session_factory):
    gate = asyncio.Event()
    m = manager(paths, session_factory, FakeSource(gate=gate))
    first = await m.request("manual")
    second = await m.request("manual")
    assert m.running
    assert (second.run_id, second.started, second.reason) == (first.run_id, False, "joined")
    gate.set()
    await m.wait()
    assert not m.running


async def test_not_connected(paths, session_factory):
    m = manager(paths, session_factory, None)
    assert (await m.request("auto")).reason == "not_connected"


async def test_unknown_ids_trigger_callback(paths, session_factory):
    seed_game(session_factory)
    sink: list = []
    source = FakeSource(roster=[make_roster(10000032), make_roster(10000999)])
    m = manager(paths, session_factory, source, unknown_sink=sink)
    await m.request("manual")
    await m.wait()
    assert sink == [{10000999}]


async def test_sync_never_touches_goals_or_other_settings(paths, session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        set_setting(s, "sync_interval_minutes", 42)
    m = manager(paths, session_factory, FakeSource())
    await m.request("manual")
    await m.wait()
    with session_factory() as s:
        assert get_setting(s, "sync_interval_minutes") == 42
