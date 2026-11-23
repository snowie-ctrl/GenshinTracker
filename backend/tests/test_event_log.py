from datetime import datetime, timedelta

from app.db.models import EventLog, GameBanner
from app.events.log import match_banner, match_calendar, normalise, record, wish_pool
from app.sync.announcements import Announcement

NOW = datetime(2026, 11, 23, 12, 0, 0)


def ann(ann_id, name, kind="event", start="2026-11-20T15:00:00Z", end="2026-11-30T08:59:00Z", title=None):
    return Announcement(ann_id, kind, name, title or name, start, end, None, None,
                        "https://sdk.hoyoverse.com/upload/ann/test/x.png", "Text.")


def cal_event(id, name, start="2026-11-20T15:00:00Z", end="2026-11-30T08:59:59Z"):
    return {"id": id, "name": name, "description": "", "start": start, "end": end, "rewards": []}


def banner(pool, start, key=None):
    return GameBanner(key=key or f"{pool}|{start}|0", pool=pool, name="B", short_name="B", start=start, end=start,
                      timezone_dependent=True, timezone_dependent_end=False, order=0, featured_5=[], featured_4=[],
                      version="9.9")


def test_normalise():
    assert normalise('"Stress Block" Smashing: Project!') == "stress block smashing project"


def test_match_calendar_containment_both_ways_and_closest_end():
    events = [cal_event(1, "Stygian Onslaught", end="2026-12-15T08:59:59Z"),
              cal_event(2, "Digging", end="2026-11-30T08:59:59Z"),
              cal_event(3, "Digging", end="2027-01-30T08:59:59Z")]
    assert match_calendar(ann(9, "Stygian Onslaught Event: Ley Line"), events)["id"] == 1
    assert match_calendar(ann(9, "Digging Days"), events)["id"] == 2
    assert match_calendar(ann(9, "Unrelated"), events) is None
    assert match_calendar(ann(9, "Digging Days", kind="wish"), events) is None


def test_wish_pool():
    assert wish_pool('Event Wish "X" - Epitome Invocation') == "weapon"
    assert wish_pool('Event Wish "Y" - Chronicled Wish Now Available') == "chronicled"
    assert wish_pool('Event Wish "Z" - Boosted Drop Rate') == "character"


def test_both_character_wishes_match_one_row():
    rows = [banner("character", "2026-11-25 02:00:00"), banner("weapon", "2026-11-25 02:00:00"),
            banner("character", "2026-11-04 06:00:00")]
    first = match_banner("character", "2026-11-24T23:00:00Z", rows)
    second = match_banner("character", "2026-11-24T23:00:00Z", rows)
    assert first is rows[0] and second is rows[0]
    assert match_banner("character", "2026-12-20T00:00:00Z", rows) is None
    assert match_banner("character", None, rows) is None


def test_record_upserts_adds_cal_rows_replaces_them_and_prunes(session_factory):
    calendar = {"banners": [], "challenges": [], "events": [
        cal_event(1, "Digging"), cal_event(2, "Calendar Only"), cal_event(3, "No Dates", start=None, end=None)]}
    with session_factory.begin() as s:
        s.add(EventLog(key="ann:1", kind="event", name="Ancient", start=None, end="2026-08-01T00:00:00Z",
                       image=None, description="", calendar_id=None, first_seen=NOW, last_seen=NOW))
        record(s, [ann(10, "Digging Days")], calendar, NOW)
    with session_factory() as s:
        keys = {r.key: r for r in s.query(EventLog)}
    assert set(keys) == {"ann:10", "cal:2"}                    # ancient pruned, no-dates calendar row skipped
    assert keys["ann:10"].calendar_id == 1
    later = NOW + timedelta(hours=1)
    with session_factory.begin() as s:
        record(s, [ann(10, "Digging Days", end="2026-12-01T00:00:00Z"), ann(11, "Calendar Only")], calendar, later)
    with session_factory() as s:
        keys = {r.key: r for r in s.query(EventLog)}
    assert set(keys) == {"ann:10", "ann:11"}                   # cal:2 replaced by the announcement
    assert keys["ann:10"].end == "2026-12-01T00:00:00Z" and keys["ann:10"].first_seen == NOW
    assert keys["ann:10"].last_seen == later


def test_record_stores_wish_pool(session_factory):
    with session_factory.begin() as s:
        record(s, [ann(30, "Test Invocation", kind="wish", title='Event Wish "Test Invocation" - Epitome Invocation')],
               {"events": []}, NOW)
    with session_factory() as s:
        assert s.get(EventLog, "ann:30").kind == "wish:weapon"


def test_record_keeps_rows_missing_from_feed_and_fills_times(session_factory):
    calendar = {"banners": [], "challenges": [], "events": [cal_event(1, "Grand Test")]}
    with session_factory.begin() as s:
        record(s, [ann(20, "Grand Test", start=None, end=None), ann(21, "Window Only", start=None, end=None)],
               calendar, NOW)
    with session_factory.begin() as s:
        record(s, [], calendar, NOW + timedelta(hours=1))
    with session_factory() as s:
        rows = {r.key: r for r in s.query(EventLog)}
    assert rows["ann:20"].start == "2026-11-20T15:00:00Z"      # from the matched calendar event
    assert "ann:21" not in rows                                 # no times and no fallback window: skipped
