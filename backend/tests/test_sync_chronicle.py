from app.db.models import ChallengeRun, HoyolabSnapshot, SyncRun
from app.sync.chronicle import CalendarInfo, ChallengeRunInfo, EventInfo, Reward
from app.sync.hoyolab import HoyolabError
from fakes import Clock, FakeSource
from helpers import seed_game
from test_sync_runner import START, last_run, manager

CAL = CalendarInfo([], [EventInfo(9001, "Fest", "", "2026-11-19T04:00:00Z", "2026-12-01T04:00:00Z",
                                  [Reward(201, "Primogem", "", 420, 5)])], [])
RUN = ChallengeRunInfo("abyss", "101", "2026-11-16T04:00:00Z", "2026-12-16T04:00:00Z",
                       {"stars": 36, "max_floor": "12-3", "wins": 12, "battles": 12}, [[10000089, 10000032]])


async def test_parts_store_snapshots_and_runs(paths, session_factory):
    seed_game(session_factory)
    m = manager(paths, session_factory, FakeSource(calendar=CAL, challenges=[RUN]))
    await m.request("manual")
    await m.wait()
    parts = last_run(session_factory).parts
    assert parts["calendar"] == {"ok": True, "count": 1}
    assert parts["profile"] == {"ok": True}
    assert parts["challenges"] == {"ok": True, "count": 1}
    with session_factory() as s:
        assert s.get(HoyolabSnapshot, "calendar").data["events"][0]["id"] == 9001
        assert s.get(HoyolabSnapshot, "profile").data["stats"]["ar"] == 60
        assert s.get(ChallengeRun, ("abyss", "101")).summary["stars"] == 36


async def test_throttle_skips_fresh_parts_on_auto_but_not_manual(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    source = FakeSource(calendar=CAL)
    m = manager(paths, session_factory, source, clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(minutes=30)                     # the auto sync is due (interval 10 min)
    await m.request("auto")
    await m.wait()
    parts = last_run(session_factory).parts
    assert parts["calendar"] == {"ok": True, "skipped": "fresh"}
    assert parts["profile"] == {"ok": True, "skipped": "fresh"}
    clock.advance(minutes=2)
    await m.request("manual")
    await m.wait()
    assert last_run(session_factory).parts["calendar"] == {"ok": True, "count": 1}
    clock.advance(minutes=61)
    await m.request("auto")
    await m.wait()
    assert last_run(session_factory).parts["calendar"] == {"ok": True, "count": 1}
    assert source.calls.count("calendar") == 3


async def test_failure_keeps_previous_snapshot_and_isolates(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(calendar=CAL), clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(minutes=2)
    m2 = manager(paths, session_factory, FakeSource(fail={"calendar": HoyolabError("down")}), clock=clock)
    await m2.request("manual")
    await m2.wait()
    parts = last_run(session_factory).parts
    assert parts["calendar"]["ok"] is False and parts["profile"]["ok"] and parts["challenges"]["ok"]
    with session_factory() as s:
        assert s.get(HoyolabSnapshot, "calendar").data["events"][0]["id"] == 9001


async def test_challenge_runs_upsert_never_delete(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(challenges=[RUN]), clock=clock)
    await m.request("manual")
    await m.wait()
    better = ChallengeRunInfo("abyss", "101", RUN.start, RUN.end, {**RUN.summary, "stars": 33}, [])
    clock.advance(minutes=2)
    m2 = manager(paths, session_factory, FakeSource(challenges=[better]), clock=clock)
    await m2.request("manual")
    await m2.wait()
    clock.advance(minutes=2)
    m3 = manager(paths, session_factory, FakeSource(challenges=[]), clock=clock)
    await m3.request("manual")
    await m3.wait()
    with session_factory() as s:
        row = s.get(ChallengeRun, ("abyss", "101"))
        assert row.summary["stars"] == 33 and row.seen_at == START


async def test_gaps_only_run_never_runs_chronicle_parts(paths, session_factory):
    seed_game(session_factory)
    source = FakeSource()
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    before = source.calls.count("calendar")
    m.start_gaps()
    await m.wait()
    assert source.calls.count("calendar") == before
