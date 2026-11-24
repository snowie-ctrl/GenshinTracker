import asyncio
from datetime import datetime

import pytest

from app.db.models import CharacterGoal, GapRun, LiveNotes, MaterialTotal, OwnedCharacter, SyncRun
from app.settings.store import get_setting, set_setting
from app.sync.hoyolab import AuthExpired, HoyolabError, NoInventoryData, RateLimited
from app.sync.runner import SyncManager, SyncTooSoon
from fakes import Clock, FakeSource, make_roster
from app.timeutil import utcnow
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
                         "notes": {"ok": True}, "gaps": {"ok": True, "count": 0},
                         "calendar": {"ok": True, "count": 0}, "profile": {"ok": True},
                         "challenges": {"ok": True, "count": 0}}
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
    assert parts["gaps"] == {"ok": False, "error": "skipped: roster failed"}
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
    m = manager(paths, session_factory, FakeSource(fail={"roster": HoyolabError("x")}), clock=clock)
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


async def test_interval_counts_runs_whose_roster_succeeded(paths, session_factory):
    """A part that always fails (e.g. Real-Time Notes disabled) must not make auto-sync run every page load."""
    seed_game(session_factory)
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(fail={"notes": HoyolabError("DataNotPublic")}), clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(minutes=5)
    assert (await m.request("auto")).reason == "fresh"


async def test_reconnect_during_run_is_not_overwritten_by_old_expiry(paths, session_factory):
    gate = asyncio.Event()
    m = manager(paths, session_factory, FakeSource(fail={"roster": AuthExpired("old cookie")}, gate=gate))
    await m.request("manual")
    m.invalidate_auth()  # user reconnects with a fresh cookie while the old run is in flight
    with session_factory.begin() as s:
        set_setting(s, "hoyolab_status", "connected")
    gate.set()
    await m.wait()
    with session_factory() as s:
        assert get_setting(s, "hoyolab_status") == "connected"


def build_goal(session_factory, cid, skill=8):
    with session_factory.begin() as s:
        s.merge(CharacterGoal(character_id=cid, goal="build", target_level=90, target_normal=8,
                              target_skill=skill, target_burst=8, target_weapon_level=90, updated_at=utcnow()))


async def test_full_sync_runs_gaps_part(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    source = FakeSource()
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    assert last_run(session_factory).parts["gaps"] == {"ok": True, "count": 1}
    assert ("talents", 10000032) in source.calls and ("gaps", (10000032,)) in source.calls
    with session_factory() as s:
        assert s.get(MaterialTotal, 104302).short == 4
        assert s.get(GapRun, 1).ok is True


async def test_gaps_failure_is_isolated_and_recorded(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    m = manager(paths, session_factory, FakeSource(fail={"gaps": NoInventoryData("HoYoLAB returned no inventory data.")}))
    await m.request("manual")
    await m.wait()
    parts = last_run(session_factory).parts
    assert parts["gaps"]["ok"] is False and "no inventory data" in parts["gaps"]["error"]
    assert parts["roster"]["ok"] and parts["notes"]["ok"]
    with session_factory() as s:
        assert s.get(GapRun, 1).ok is False


async def test_traveler_is_calculated_with_element(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    build_goal(session_factory, 1000000507)
    source = FakeSource(roster=[make_roster(10000032, name="Bennett"),
                                make_roster(1000000507, raw_id=10000007, name="Traveler", element="Cryo")])
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    assert last_run(session_factory).parts["gaps"] == {"ok": True, "count": 2}
    assert ("talents", 10000007, 7) in source.calls
    assert ("gaps", (10000032, 1000000507)) in source.calls


async def test_no_work_skips_calculator_call(paths, session_factory):
    seed_game(session_factory)
    source = FakeSource()
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    assert last_run(session_factory).parts["gaps"] == {"ok": True, "count": 0}
    assert not any(isinstance(c, tuple) and c[0] == "gaps" for c in source.calls)


async def test_talent_ids_are_cached(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    clock = Clock(START)
    source = FakeSource()
    m = manager(paths, session_factory, source, clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(minutes=2)
    await m.request("manual")
    await m.wait()
    assert source.calls.count(("talents", 10000032)) == 1


async def test_schedule_gaps_debounces_edits(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    source = FakeSource()
    m = SyncManager(session_factory, paths.db_file, paths.backups, lambda: source,
                    lambda ids: asyncio.sleep(0), clock=Clock(START), gaps_delay=0.05)
    m.schedule_gaps()
    m.schedule_gaps()
    m.schedule_gaps()
    assert m.gaps_pending
    await m.wait()
    gap_calls = [c for c in source.calls if isinstance(c, tuple) and c[0] == "gaps"]
    assert len(gap_calls) == 1
    run = last_run(session_factory)
    assert run.trigger == "gaps" and set(run.parts) == {"gaps"}
    assert "roster" not in source.calls                   # gaps-only run touches nothing else
    assert not m.gaps_pending


async def test_gaps_request_during_full_sync_is_queued_once(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    gate = asyncio.Event()
    source = FakeSource(gate=gate)
    m = manager(paths, session_factory, source)
    await m.request("manual")
    assert m.start_gaps().reason == "queued"
    assert m.start_gaps().reason == "queued"
    gate.set()
    await m.wait()
    gap_calls = [c for c in source.calls if isinstance(c, tuple) and c[0] == "gaps"]
    assert len(gap_calls) == 2                            # one inside the full sync, one queued run
    assert last_run(session_factory).trigger == "gaps"


async def test_gaps_runs_do_not_count_for_manual_limit(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(), clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(seconds=61)
    m.start_gaps()
    await m.wait()
    result = await m.request("manual")                    # last non-gaps run is 61 s old
    assert result.started


async def test_start_gaps_not_connected(paths, session_factory):
    m = manager(paths, session_factory, None)
    assert m.start_gaps().reason == "not_connected"


async def test_wait_survives_timer_replaced_by_new_edit(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    source = FakeSource()
    m = SyncManager(session_factory, paths.db_file, paths.backups, lambda: source,
                    lambda ids: asyncio.sleep(0), clock=Clock(START), gaps_delay=0.05)
    m.schedule_gaps()
    waiter = asyncio.create_task(m.wait())
    await asyncio.sleep(0)
    m.schedule_gaps()                                     # cancels the timer the waiter is on
    await waiter                                          # must not raise CancelledError
    assert len([c for c in source.calls if isinstance(c, tuple) and c[0] == "gaps"]) == 1


async def test_request_during_gaps_only_run_waits_then_runs_full_sync(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    gate = asyncio.Event()
    source = FakeSource(gaps_gate=gate)
    m = manager(paths, session_factory, source)
    assert m.start_gaps().started
    req = asyncio.create_task(m.request("manual"))
    await asyncio.sleep(0.01)
    assert not req.done()
    gate.set()
    result = await req
    await m.wait()
    assert result.started and result.reason == "started"
    run = last_run(session_factory)
    assert run.trigger == "manual" and {"roster", "details", "notes"} <= set(run.parts)
    with session_factory() as s:
        assert s.query(SyncRun).filter_by(trigger="gaps").count() == 1


def gaps_runs(session_factory) -> int:
    with session_factory() as s:
        return s.query(SyncRun).filter_by(trigger="gaps").count()


async def test_auto_fresh_recalculates_when_goals_changed_since_last_calculation(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    source = FakeSource()
    m = manager(paths, session_factory, source, clock=clock)
    await m.request("manual")
    await m.wait()
    build_goal(session_factory, 10000032)                 # edited without a debounce timer (e.g. app restarted)
    clock.advance(minutes=5)
    assert (await m.request("auto")).reason == "fresh"
    await m.wait()
    assert gaps_runs(session_factory) == 1
    with session_factory() as s:
        assert s.get(GapRun, 1).snapshot == [[10000032, 90, 8, 8, 8, 90, None]]
    assert (await m.request("auto")).reason == "fresh"    # now up to date: nothing more
    await m.wait()
    assert gaps_runs(session_factory) == 1


async def test_auto_recent_after_upgrade_calculates_existing_build_goals(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    with session_factory.begin() as s:                    # a phase 1 sync: no gap_run row yet
        s.add(SyncRun(started_at=START, finished_at=START, trigger="manual", parts={"roster": {"ok": False}}))
    clock = Clock(START)
    clock.advance(seconds=30)
    m = manager(paths, session_factory, FakeSource(), clock=clock)
    assert (await m.request("auto")).reason == "recent"
    await m.wait()
    assert gaps_runs(session_factory) == 1
    with session_factory() as s:
        assert s.get(GapRun, 1).ok is True


def gap_calls(source) -> list:
    return [c for c in source.calls if isinstance(c, tuple) and c[0] == "gaps"]


async def failed_gaps_then_goal_edit(paths, session_factory, clock):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    source = FakeSource(fail={"gaps": NoInventoryData("HoYoLAB returned no inventory data.")})
    m = SyncManager(session_factory, paths.db_file, paths.backups, lambda: source,
                    lambda ids: asyncio.sleep(0), clock=clock, gaps_delay=0.01)
    await m.request("manual")
    await m.wait()
    with session_factory() as s:
        assert s.get(GapRun, 1).ok is False
    build_goal(session_factory, 10000032, skill=9)        # goals now differ from the stored snapshot
    return m, source


@pytest.mark.parametrize("seconds,reason", [(300, "fresh"), (30, "recent")])
async def test_auto_skip_does_not_retry_gaps_after_a_failed_calculation(paths, session_factory, seconds, reason):
    clock = Clock(START)
    m, source = await failed_gaps_then_goal_edit(paths, session_factory, clock)
    if reason == "recent":                                # last full sync failed, so only the 60 s rule skips
        with session_factory.begin() as s:
            run = s.query(SyncRun).filter_by(trigger="manual").one()
            run.parts = {**run.parts, "roster": {"ok": False}}
    calls, runs = len(gap_calls(source)), gaps_runs(session_factory)
    clock.advance(seconds=seconds)
    for _ in range(3):                                    # repeated page navigations
        assert (await m.request("auto")).reason == reason
        await m.wait()
    assert len(gap_calls(source)) == calls
    assert gaps_runs(session_factory) == runs


async def test_goal_edit_still_retries_gaps_after_a_failed_calculation(paths, session_factory):
    m, source = await failed_gaps_then_goal_edit(paths, session_factory, Clock(START))
    calls = len(gap_calls(source))
    m.schedule_gaps()
    await m.wait()
    assert len(gap_calls(source)) == calls + 1


async def test_auto_fresh_without_build_goals_starts_nothing(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(), clock=clock)
    await m.request("manual")
    await m.wait()
    with session_factory.begin() as s:
        s.delete(s.get(GapRun, 1))
    clock.advance(minutes=5)
    assert (await m.request("auto")).reason == "fresh"
    await m.wait()
    assert gaps_runs(session_factory) == 0


async def test_gaps_running_only_during_gaps_only_run(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    gate = asyncio.Event()
    m = manager(paths, session_factory, FakeSource(gaps_gate=gate))
    assert not m.gaps_running
    m.start_gaps()
    await asyncio.sleep(0.01)
    assert m.gaps_running
    gate.set()
    await m.wait()
    assert not m.gaps_running


def test_last_successful_ignores_gaps_runs(session_factory):
    from app.sync.runner import last_successful
    with session_factory.begin() as s:
        s.add(SyncRun(started_at=START, finished_at=START, trigger="manual", parts={"roster": {"ok": True}}))
        s.add(SyncRun(started_at=START, finished_at=START, trigger="gaps", parts={"roster": {"ok": True}}))
    with session_factory() as s:
        assert last_successful(s).trigger == "manual"


async def test_calculator_rejecting_one_character_skips_it(paths, session_factory):
    """HoYoLAB fails the whole batch for one character it rejects (seen with brand-new characters):
    find it one by one, then calculate everyone else in one batch."""
    from app.db.models import MaterialGap
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    build_goal(session_factory, 10000089)
    source = FakeSource(reject={10000089})
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    part = last_run(session_factory).parts["gaps"]
    assert part == {"ok": True, "count": 1, "skipped": ["Furina (HoYoLAB calculator error)"]}
    gap_calls = [c for c in source.calls if isinstance(c, tuple) and c[0] == "gaps"]
    assert gap_calls == [("gaps", (10000032, 10000089)), ("gaps", (10000032,)), ("gaps", (10000089,)),
                         ("gaps", (10000032,))]
    with session_factory() as s:
        assert {g.character_id for g in s.query(MaterialGap)} == {10000032}
        run = s.get(GapRun, 1)
        assert run.ok is True and run.skipped == ["Furina (HoYoLAB calculator error)"]


async def test_calculator_rejecting_everyone_keeps_the_error(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    m = manager(paths, session_factory, FakeSource(reject={10000032}))
    await m.request("manual")
    await m.wait()
    part = last_run(session_factory).parts["gaps"]
    assert part["ok"] is False and "-500001" in part["error"]
    with session_factory() as s:
        assert s.get(GapRun, 1).ok is False


@pytest.mark.parametrize("error", [RateLimited("slow down"), NoInventoryData("HoYoLAB returned no inventory data.")])
async def test_calculator_errors_that_are_not_per_character_do_not_retry_one_by_one(paths, session_factory, error):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    build_goal(session_factory, 10000089)
    source = FakeSource(fail={"gaps": error})
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    assert last_run(session_factory).parts["gaps"]["ok"] is False
    assert [c for c in source.calls if isinstance(c, tuple) and c[0] == "gaps"] == [("gaps", (10000032, 10000089))]
