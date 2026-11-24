from datetime import datetime, timedelta

from app.db.models import EventDone, EventLog, GameBanner, HoyolabSnapshot
from app.events.view import (
    banner_history, cleanup_event_done, ending_soon_list, ending_within, event_rows, events_left, history_items,
    live_banners, primogems, resets, timeline_rows,
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


def gb(pool, start, version, name="B", f5=(), f4=(), order=0):
    return GameBanner(key=f"{pool}|{start}|{order}", pool=pool, name=name, short_name=name, start=start,
                      end=start, timezone_dependent=True, timezone_dependent_end=False, order=order,
                      featured_5=list(f5), featured_4=list(f4), version=version)


def test_banner_history_versions_phases_search_and_paging(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        s.add(gb("character", "2026-11-04 06:00:00", "9.9", "Tide of Furina", [10000089], [10000032]))
        s.add(gb("weapon", "2026-11-04 06:00:00", "9.9", "Epitome Invocation"))
        s.add(gb("chronicled", "2026-11-04 06:00:00", "9.9", "Chronicle"))
        s.add(gb("character", "2026-10-14 18:00:00", "9.8", "Older"))
        s.add(gb("standard", "2000-01-01 00:00:00", None, "Wanderlust"))
        s.add(gb("standard", "2000-01-02 00:00:00", "9.9", "Wanderlust 9.9"))   # standard pool never shown
        for i in range(8):
            s.add(gb("character", f"2020-{i + 1:02d}-01 06:00:00", f"1.{i}", f"Old {i}"))
    with session_factory() as s:
        page1 = banner_history(s, "", 1, {"character|2026-11-04 06:00:00|0": {"pulls": 7, "fives": ["Furina"], "fours": []}})
        page2 = banner_history(s, "", 2, {})
        found = banner_history(s, "furina", 1, {})
    assert page1["total_versions"] == 10 and page1["page_size"] == 6
    assert [v["version"] for v in page1["versions"]] == ["9.9", "9.8", "1.7", "1.6", "1.5", "1.4"]
    assert len(page2["versions"]) == 4
    top = page1["versions"][0]["phases"][0]
    assert [b["pool"] for b in top["banners"]] == ["character", "weapon", "chronicled"]
    assert top["banners"][0]["featured_5"][0]["name"] == "Furina" and top["banners"][0]["pulls"]["pulls"] == 7
    assert top["upcoming"] is False
    assert [v["version"] for v in found["versions"]] == ["9.9"]
    assert [b["name"] for b in found["versions"][0]["phases"][0]["banners"]] == ["Tide of Furina"]


def test_banner_history_upcoming_phase_from_log(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        s.add(gb("character", "2026-11-04 06:00:00", "9.9", "Tide of Furina"))
        s.add(EventLog(key="ann:5", kind="wish:character", name="Next Wish", start="2026-11-24T10:00:00Z",
                       end="2026-12-15T06:59:00Z", image="https://sdk.hoyoverse.com/upload/ann/test/n.png",
                       description="", calendar_id=None, first_seen=NOW, last_seen=NOW))
        s.add(EventLog(key="ann:6", kind="wish:character", name="Matched Wish", start="2026-11-03T22:00:00Z",
                       end="2026-11-24T06:59:00Z", image=None, description="", calendar_id=None,
                       first_seen=NOW, last_seen=NOW))
    with session_factory() as s:
        out = banner_history(s, "", 1, {})
    phases = out["versions"][0]["phases"]
    assert [p["upcoming"] for p in phases] == [False, True]
    assert phases[1]["image"].endswith("n.png") and phases[1]["banners"][0]["name"] == "Next Wish"
    assert phases[1]["banners"][0]["featured_5"] == []


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


def log(key, name, start, end, kind="event", calendar_id=None, image=None):
    return EventLog(key=key, kind=kind, name=name, start=start, end=end, image=image, description="Text",
                    calendar_id=calendar_id, first_seen=NOW, last_seen=NOW)


def test_timeline_window_calendar_override_and_done():
    rows = [log("ann:1", "Long", "2026-11-01T00:00:00Z", "2026-12-30T00:00:00Z", calendar_id=1),
            log("ann:2", "Old", "2026-10-01T00:00:00Z", "2026-10-20T00:00:00Z"),          # ended > 21 days ago
            log("ann:3", "Recent", "2026-11-01T00:00:00Z", "2026-11-10T00:00:00Z"),       # ended 11 days ago
            log("ann:4", "Ticked", "2026-11-10T00:00:00Z", "2026-11-21T20:00:00Z", calendar_id=2)]
    out = timeline_rows(rows, CAL, {2}, [], {}, {}, NOW)
    by = {r["key"]: r for r in out}
    assert set(by) == {"ann:1", "ann:3", "ann:4"}
    assert by["ann:1"]["end"] == "2026-11-30T04:00:00Z"                 # calendar's end wins
    assert by["ann:1"]["primogems"] == 420 and by["ann:1"]["done"] is False
    assert by["ann:4"]["done"] is True and by["ann:4"]["ending_soon"] is False   # done rows never warn
    assert by["ann:3"]["rewards"] == [] and by["ann:3"]["calendar_id"] is None
    # starts after the calendar override: ann:3 Nov 1; ann:4 and ann:1 both Nov 10 (calendar), ann:4 ends first
    assert [r["key"] for r in out] == ["ann:3", "ann:4", "ann:1"]


def test_timeline_wish_items_and_pulls(session_factory):
    seed_game(session_factory)
    b = GameBanner(key="character|2026-11-21 18:00:00|0", pool="character", name="B", short_name="B",
                   start="2026-11-21 18:00:00", end="2026-12-12 14:59:00", timezone_dependent=True,
                   timezone_dependent_end=False, order=0, featured_5=[10000089], featured_4=[10000032], version="9.9")
    with session_factory() as s:
        items = history_items(s)
    rows = [log("ann:7", "Wish A", "2026-11-21T10:00:00Z", "2026-12-12T06:59:00Z", kind="wish:character"),
            log("ann:8", "Wish B", "2026-12-20T10:00:00Z", "2027-01-12T06:59:00Z", kind="wish:character")]
    out = {r["key"]: r for r in timeline_rows(rows, CAL, set(), [b], items, {b.key: {"pulls": 3, "fives": [], "fours": []}}, NOW)}
    assert out["ann:7"]["kind"] == "wish" and out["ann:7"]["pool"] == "character"
    assert out["ann:7"]["items"]["featured_5"][0]["name"] == "Furina"
    assert out["ann:7"]["pulls"]["pulls"] == 3 and out["ann:7"]["done"] is False
    assert out["ann:8"]["items"] is None and out["ann:8"]["pulls"] is None


def test_ending_soon_list():
    rows = [{"key": "a", "kind": "event", "name": "A", "end": "2026-11-22T00:00:00Z", "done": False},
            {"key": "b", "kind": "event", "name": "B", "end": "2026-11-22T00:00:00Z", "done": True},
            {"key": "c", "kind": "wish", "name": "C", "end": "2026-11-21T18:00:00Z", "done": False},
            {"key": "d", "kind": "event", "name": "D", "end": "2026-11-29T00:00:00Z", "done": False},
            {"key": "e", "kind": "event", "name": "E", "end": "2026-11-20T00:00:00Z", "done": False}]
    assert [r["key"] for r in ending_soon_list(rows, NOW)] == ["c", "a"]
    assert set(ending_soon_list(rows, NOW)[0]) == {"key", "kind", "name", "end"}
