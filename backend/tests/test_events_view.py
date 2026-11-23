from datetime import datetime, timedelta

from app.db.models import EventDone, GameBanner, HoyolabSnapshot
from app.events.view import (
    banner_history, cleanup_event_done, ending_within, event_rows, events_left, live_banners, primogems, resets,
)
from app.wishes.pity import BannerWindow
from helpers import seed_game

NOW = datetime(2026, 11, 21, 12, 0, 0)       # Saturday


def ev(id, end, rewards=(), start="2026-11-10T04:00:00Z"):
    return {"id": id, "name": f"E{id}", "description": "", "start": start, "end": end,
            "rewards": [{"id": r[0], "name": r[1], "icon": "", "count": r[2], "rarity": 5} for r in rewards]}


CAL = {"banners": [], "challenges": [], "events": [
    ev(1, "2026-11-30T04:00:00Z", [(201, "Primogem", 420), (104003, "Hero's Wit", 4)]),
    ev(2, "2026-11-22T04:00:00Z", [(201, "Primogem", 60)]),
    ev(3, "2026-12-05T04:00:00Z"),
    ev(4, "2026-11-20T04:00:00Z", [(201, "Primogem", 999)]),        # already ended
]}


def test_primogems_by_id_or_name():
    assert primogems([{"id": 201, "name": "x", "count": 3}, {"id": 9, "name": "Primogem", "count": 2},
                      {"id": 9, "name": "Mora", "count": 50}]) == 5


def test_event_rows_order_done_and_ending_soon():
    rows = event_rows(CAL, {3}, NOW)
    assert [r["id"] for r in rows] == [2, 1, 3]
    assert rows[0]["ending_soon"] is True and rows[1]["ending_soon"] is False
    assert rows[2]["done"] is True
    assert events_left(rows) == {"count": 2, "primogems": 480}


def test_resets_from_calendar_and_fallback_when_calendar_has_no_challenges():
    cal = {"banners": [], "events": [], "challenges": [
        {"kind": "abyss", "name": "A", "start": None, "end": "2026-12-16T04:00:00Z"},
        {"kind": "stygian", "name": "S", "start": None, "end": "2026-12-01T04:00:00Z"}]}
    got = {r["key"]: r["at"] for r in resets(cal, NOW, "os_euro")}
    assert got["daily"] == "2026-11-22T03:00:00Z"          # 04:00 UTC+1
    assert got["weekly"] == "2026-11-23T03:00:00Z"         # Monday 04:00 UTC+1
    assert got["abyss"] == "2026-12-16T04:00:00Z" and got["stygian"] == "2026-12-01T04:00:00Z"
    assert got["theater"] == "2026-12-01T03:00:00Z"        # fallback: the 1st 04:00 server time


def test_resets_fallback_when_calendar_has_no_challenges():
    got = {r["key"]: r["at"] for r in resets({"banners": [], "events": [], "challenges": []}, NOW, "os_usa")}
    assert got["abyss"] == "2026-12-16T09:00:00Z"          # 16th 04:00 UTC-5
    assert got["theater"] == "2026-12-01T09:00:00Z"
    assert "stygian" not in got
    assert [r["key"] for r in resets(None, NOW, "os_asia")] == ["daily", "weekly", "abyss", "theater"]
    past = {"kind": "abyss", "name": "A", "start": None, "end": "2026-11-16T04:00:00Z"}   # already over
    got = {r["key"]: r["at"] for r in resets({"banners": [], "events": [], "challenges": [past]}, NOW, "os_asia")}
    assert got["abyss"] == "2026-12-15T20:00:00Z"          # fallback 16th 04:00 UTC+8


def test_fallback_on_the_reset_day_itself():
    on_16th = datetime(2026, 11, 16, 1, 0, 0)               # 09:00 UTC+8: the 04:00 reset already passed
    got = {r["key"]: r["at"] for r in resets(None, on_16th, "os_asia")}
    assert got["abyss"] == "2026-12-15T20:00:00Z"


def test_resets_use_stored_period_when_calendar_lacks_the_challenge():
    empty = {"banners": [], "events": [], "challenges": []}
    got = {r["key"]: r["at"] for r in resets(empty, NOW, "os_asia", {"stygian": "2026-12-03T04:00:00Z"})}
    assert got["stygian"] == "2026-12-03T04:00:00Z"
    got = {r["key"]: r["at"] for r in resets(empty, NOW, "os_asia", {"abyss": "2026-12-10T04:00:00Z"})}
    assert got["abyss"] == "2026-12-10T04:00:00Z"
    got = {r["key"]: r["at"] for r in resets(empty, NOW, "os_asia", {"stygian": "2026-11-01T04:00:00Z", "abyss": None})}
    assert "stygian" not in got and got["abyss"] == "2026-12-15T20:00:00Z"        # stale / missing: fallback
    cal = {"banners": [], "events": [], "challenges": [
        {"kind": "stygian", "name": "S", "start": None, "end": "2026-12-01T04:00:00Z"}]}
    got = {r["key"]: r["at"] for r in resets(cal, NOW, "os_asia", {"stygian": "2026-12-03T04:00:00Z"})}
    assert got["stygian"] == "2026-12-01T04:00:00Z"                               # the calendar wins


def test_live_banners_with_pulls():
    cal = {"events": [], "challenges": [], "banners": [
        {"id": 1, "pool": "character", "name": "Tide", "version": "6.2", "start": "2026-11-18T03:00:00Z",
         "end": "2026-12-09T03:00:00Z", "items": [{"id": 10000089, "name": "Furina", "icon": "", "rarity": 5,
                                                    "kind": "character"}]},
        {"id": 2, "pool": "weapon", "name": "Next", "version": "6.3", "start": "2026-12-10T03:00:00Z",
         "end": "2026-12-30T03:00:00Z", "items": []}]}
    window = BannerWindow("character|2026-11-18 11:00:00|0", "character", "Tide", "Furina",
                          "2026-11-18 11:00:00", "2026-12-09 10:59:59", 0, (10000089,), ())
    pulls = {window.key: {"pulls": 30, "fives": ["Furina"], "fours": []}}
    out = live_banners(cal, NOW, {"character": [window]}, pulls, 8)
    assert [b["id"] for b in out["current"]] == [1] and [b["id"] for b in out["upcoming"]] == [2]
    assert out["current"][0]["pulls"] == {"pulls": 30, "fives": ["Furina"], "fours": []}
    assert out["upcoming"][0]["pulls"] is None


def test_banner_history_filter_search_page(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        for i in range(55):
            s.add(GameBanner(key=f"character|2020-01-{i:02d}|0", pool="character", name=f"Banner {i}",
                             short_name="Furina" if i == 3 else f"B{i}", start=f"2020-{1 + i // 28:02d}-{1 + i % 28:02d} 10:00:00",
                             end="2020-12-31 10:00:00", timezone_dependent=False, timezone_dependent_end=False,
                             order=0, featured_5=[10000089] if i == 3 else [], featured_4=[10000032], version="1.0"))
        s.add(GameBanner(key="weapon|x|0", pool="weapon", name="W", short_name="W", start="2020-01-01 10:00:00",
                         end="2020-01-20 10:00:00", timezone_dependent=False, timezone_dependent_end=False, order=0,
                         featured_5=[], featured_4=[], version="1.0"))
    with session_factory() as s:
        page1 = banner_history(s, "character", "", 1, {})
        page2 = banner_history(s, "character", "", 2, {})
        found = banner_history(s, "character", "furina", 1, {"character|2020-01-03|0": {"pulls": 7, "fives": [], "fours": []}})
    assert page1["total"] == 55 and len(page1["rows"]) == 50 and len(page2["rows"]) == 5
    assert page1["rows"][0]["start"] >= page1["rows"][1]["start"]          # newest first
    assert [r["key"] for r in found["rows"]] == ["character|2020-01-03|0"]
    assert found["rows"][0]["featured_5"][0]["name"] == "Furina" and found["rows"][0]["pulls"]["pulls"] == 7


def test_cleanup_event_done(session_factory):
    with session_factory.begin() as s:
        s.add(HoyolabSnapshot(part="calendar", data={"banners": [], "challenges": [], "events": [ev(1, None)]},
                              fetched_at=NOW))
        s.add(EventDone(event_id=1, done_at=NOW - timedelta(days=90)))     # still in calendar: kept
        s.add(EventDone(event_id=2, done_at=NOW - timedelta(days=90)))     # gone and old: deleted
        s.add(EventDone(event_id=3, done_at=NOW - timedelta(days=10)))     # gone but recent: kept
    with session_factory.begin() as s:
        assert cleanup_event_done(s, NOW) == 1
    with session_factory() as s:
        assert {r.event_id for r in s.query(EventDone)} == {1, 3}


def test_cleanup_event_done_tolerates_event_without_id(session_factory):
    with session_factory.begin() as s:
        s.add(HoyolabSnapshot(part="calendar", data={"banners": [], "challenges": [], "events": [{"name": "No id"}]},
                              fetched_at=NOW))
        s.add(EventDone(event_id=2, done_at=NOW - timedelta(days=90)))
    with session_factory.begin() as s:
        assert cleanup_event_done(s, NOW) == 1


def test_event_rows_finished_counts_as_done():
    cal = {"banners": [], "challenges": [], "events": [
        {**ev(1, "2026-11-30T04:00:00Z"), "finished": True},
        ev(2, "2026-11-30T04:00:00Z"),                         # old snapshot: no "finished" key
        {**ev(3, "2026-11-30T04:00:00Z"), "finished": True},
    ]}
    rows = {r["id"]: r for r in event_rows(cal, {3}, NOW)}
    assert (rows[1]["done"], rows[1]["finished"]) == (True, True)
    assert (rows[2]["done"], rows[2]["finished"]) == (False, False)
    assert (rows[3]["done"], rows[3]["finished"]) == (True, True)       # ticked and finished: done once


def test_ending_within_three_days_skips_done_and_far():
    rows = event_rows(CAL, {2}, NOW)          # 2 ends in 16h but is done; 1 ends in 8d16h; 3 in 13d
    assert ending_within(rows, NOW) == []
    rows = event_rows(CAL, set(), NOW)
    assert [r["id"] for r in ending_within(rows, NOW)] == [2]
