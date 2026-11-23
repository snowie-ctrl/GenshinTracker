from datetime import timedelta

from app.db.models import ChallengeRun, EventDone, EventLog, GameBanner, HoyolabSnapshot, SyncRun
from app.events.view import cleanup_event_done
from app.timeutil import iso, utcnow
from helpers import make_client
from test_api_planner import sf_for


def seed_calendar(sf):
    now = utcnow()
    soon, later = iso(now + timedelta(hours=5)), iso(now + timedelta(days=9))
    data = {"banners": [], "challenges": [{"kind": "abyss", "name": "A", "start": None, "end": later}],
            "events": [{"id": 9001, "name": "Fest", "description": "", "start": None, "end": later,
                        "rewards": [{"id": 201, "name": "Primogem", "icon": "", "count": 420, "rarity": 5}]},
                       {"id": 9002, "name": "Quick", "description": "", "start": None, "end": soon,
                        "rewards": [{"id": 201, "name": "Primogem", "icon": "", "count": 60, "rarity": 5}]}]}
    with sf.begin() as s:
        s.add(HoyolabSnapshot(part="calendar", data=data, fetched_at=now))


def test_events_endpoint_and_done(paths):
    sf = sf_for(paths)
    seed_calendar(sf)
    with make_client(paths) as client:
        body = client.get("/api/events").json()
        assert [e["id"] for e in body["events"]] == [9002, 9001]
        assert body["events_left"] == {"count": 2, "primogems": 480}
        assert {r["key"] for r in body["resets"]} == {"daily", "weekly", "abyss", "theater"}
        assert client.put("/api/events/9002/done", json={"done": True}).json() == {"id": 9002, "done": True}
        body = client.get("/api/events").json()
        assert [e["id"] for e in body["events"]] == [9001, 9002] and body["events_left"]["primogems"] == 420
        dash = client.get("/api/dashboard").json()
        assert next(e for e in dash["events"] if e.get("id") == 9002)["done"] is True
        client.put("/api/events/9002/done", json={"done": False})
        assert client.get("/api/events").json()["events_left"]["count"] == 2


def test_done_echo_is_true_for_finished_event(paths):
    sf = sf_for(paths)
    seed_calendar(sf)
    with sf.begin() as s:
        snap = s.get(HoyolabSnapshot, "calendar")
        snap.data = {**snap.data, "events": [{**snap.data["events"][0], "finished": True}, snap.data["events"][1]]}
    with make_client(paths) as client:
        assert client.put("/api/events/9001/done", json={"done": False}).json() == {"id": 9001, "done": True}
        assert client.put("/api/events/9002/done", json={"done": False}).json() == {"id": 9002, "done": False}


def test_events_without_snapshot_and_error(paths):
    sf = sf_for(paths)
    with sf.begin() as s:
        s.add(SyncRun(started_at=utcnow(), finished_at=utcnow(), trigger="manual",
                      parts={"calendar": {"ok": False, "error": "HoyolabError: down"}}))
    with make_client(paths) as client:
        body = client.get("/api/events").json()
        assert body["fetched_at"] is None and body["events"] == [] and body["error"] == "HoyolabError: down"
        assert client.get("/api/dashboard").json()["live_banners"] == []


def test_banner_history_endpoint(paths):
    sf_for(paths)
    with make_client(paths) as client:
        body = client.get("/api/banners/history?pool=character&q=&page=1").json()
        assert body == {"total": 0, "page": 1, "page_size": 50, "rows": []}
        assert client.get("/api/banners/history?pool=nope").status_code == 422


def test_banner_history_wildcards_are_literal(paths):
    sf = sf_for(paths)
    with sf.begin() as s:
        s.add(GameBanner(key="character|2024-01-01 00:00:00|0", pool="character", name="Plain Banner",
                         short_name="Plain", start="2024-01-01 00:00:00", end="2024-01-20 00:00:00",
                         timezone_dependent=False, timezone_dependent_end=False, order=0,
                         featured_5=[], featured_4=[], version="1.0"))
    with make_client(paths) as client:
        assert client.get("/api/banners/history?pool=character&q=%25").json()["total"] == 0
        assert client.get("/api/banners/history?pool=character&q=_").json()["total"] == 0
        assert client.get("/api/banners/history?pool=character&q=plain").json()["total"] == 1


def test_done_validation(paths):
    sf_for(paths)
    with make_client(paths) as client:
        assert client.put("/api/events/abc/done", json={"done": True}).status_code == 422
        assert client.put("/api/events/1/done", json={}).status_code == 422


def test_stygian_reset_from_challenge_run(paths):
    sf = sf_for(paths)
    now = utcnow()
    end = iso(now + timedelta(days=6))
    with sf.begin() as s:
        s.add(HoyolabSnapshot(part="calendar", data={"banners": [], "events": [], "challenges": []},
                              fetched_at=now))
        s.add(ChallengeRun(kind="stygian", season="7", start=None, end=end, summary={}, teams=[],
                           seen_at=now, updated_at=now))
    with make_client(paths) as client:
        resets = {r["key"]: r["at"] for r in client.get("/api/events").json()["resets"]}
    assert resets["stygian"] == end


def test_cleanup_keeps_done_rows_without_snapshot(paths):
    sf = sf_for(paths)
    now = utcnow()
    with sf.begin() as s:
        s.add(EventDone(event_id=1, done_at=now - timedelta(days=200)))
    with sf.begin() as s:
        assert cleanup_event_done(s, now) == 0
    with sf() as s:
        assert s.get(EventDone, 1) is not None


def test_events_payload_has_timeline_and_feed_error(paths):
    sf = sf_for(paths)
    now = utcnow()
    with sf.begin() as s:
        s.add(HoyolabSnapshot(part="calendar", data={"banners": [], "events": [], "challenges": []}, fetched_at=now))
        s.add(EventLog(key="ann:1", kind="event", name="Fest", start=iso(now - timedelta(days=1)),
                       end=iso(now + timedelta(hours=10)), image=None, description="", calendar_id=None,
                       first_seen=now, last_seen=now))
        s.add(SyncRun(trigger="manual", started_at=now, finished_at=now,
                      parts={"calendar": {"ok": True, "count": 0, "announcements_error": "AnnouncementError: x"}}))
    with make_client(paths) as client:
        body = client.get("/api/events").json()
    assert [r["key"] for r in body["timeline"]] == ["ann:1"]
    assert body["ending_soon"] == [{"key": "ann:1", "kind": "event", "name": "Fest", "end": body["timeline"][0]["end"]}]
    assert body["announcements_error"] == "AnnouncementError: x"
    assert "banners" in body and "events" in body                 # Dashboard fields kept
