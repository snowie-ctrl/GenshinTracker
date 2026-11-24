from datetime import timedelta

from app.db.models import CharacterGoal, HoyolabSnapshot, MaterialGap, MaterialTotal
from app.timeutil import iso, utcnow
from helpers import make_client
from test_api_planner import mark_calculated, setup, sf_for

KEYS = {"connection", "display_name", "notes", "timers", "ending_soon", "server_weekday", "domains_by_day",
        "weekly_bosses", "artifact_domains", "builds", "completed", "live_banners", "events", "calendar_fetched_at", "gaps"}


def test_dashboard_empty_account(paths):
    sf_for(paths)
    with make_client(paths) as client:
        body = client.get("/api/dashboard").json()
    assert set(body) == KEYS
    assert body["notes"] is None and body["timers"] == [] and body["builds"] == [] and body["completed"] == []
    assert body["ending_soon"] == [] and body["live_banners"] == [] and body["display_name"] == ""
    assert sorted(body["domains_by_day"]) == [str(d) for d in range(7)]
    assert all(e["kind"] == "reset" for e in body["events"])


def test_dashboard_shape_and_allocation(paths):
    sf = setup(paths)
    with sf.begin() as s:
        s.get(CharacterGoal, 10000032).priority = 1
    mark_calculated(sf)               # only calculated characters list materials
    with make_client(paths) as client:
        body = client.get("/api/dashboard").json()
    assert set(body) == KEYS
    assert body["notes"]["expeditions_max"] is None and "commission_bonus_claimed" in body["notes"]
    assert body["domains_by_day"]["0"]["domains"][0]["name"] == "Domain of Mastery: Forsaken Rift"
    card = body["builds"][0]
    assert card["character"]["name"] == "Bennett" and card["priority"] == 1
    guide = next(m for m in card["materials"] if m["id"] == 104302)
    assert (guide["need"], guide["have"], guide["craft"]) == (9, 5, 0)
    assert body["timers"][0]["kind"] in {"resin", "expedition"}


def test_put_priority_reorders_and_recomputes(paths):
    sf = setup(paths)
    with sf.begin() as s:
        s.add(CharacterGoal(character_id=10000089, goal="build", target_level=90, target_normal=8, target_skill=8,
                            target_burst=8, target_weapon_level=90, priority=2, updated_at=utcnow()))
        s.get(CharacterGoal, 10000032).priority = 1
        s.add(MaterialGap(character_id=10000089, material_id=104302, need=6, short=6))
        total = s.get(MaterialTotal, 104302)
        total.need, total.short = 15, 10                     # 5 held
    mark_calculated(sf)
    with make_client(paths) as client:
        before = client.get("/api/dashboard").json()["builds"]
        assert [b["character"]["id"] for b in before] == [10000032, 10000089]
        res = client.put("/api/priority", json={"order": [10000089, 10000032]})
        assert res.status_code == 200
        builds = {b["character"]["id"]: b for b in res.json()["builds"]}
        assert next(m for m in builds[10000089]["materials"] if m["id"] == 104302)["have"] == 5
        assert next(m for m in builds[10000032]["materials"] if m["id"] == 104302)["have"] == 0
        assert [b["priority"] for b in res.json()["builds"]] == [1, 2]
        assert set(res.json()) == {"builds", "completed"}


def test_put_priority_appends_unlisted_and_rejects_stale(paths):
    sf = setup(paths)
    with sf.begin() as s:
        s.add(CharacterGoal(character_id=10000089, goal="build", target_level=90, target_normal=8, target_skill=8,
                            target_burst=8, target_weapon_level=90, updated_at=utcnow()))
    with make_client(paths) as client:
        assert client.put("/api/priority", json={"order": [10000089]}).status_code == 200
        res = client.put("/api/priority", json={"order": [10000047]})
        assert res.status_code == 400 and "not set to Build" in res.json()["detail"]
        assert client.put("/api/priority", json={"order": [10000089, 10000089]}).status_code == 400
    with sf() as s:
        assert (s.get(CharacterGoal, 10000089).priority, s.get(CharacterGoal, 10000032).priority) == (1, 2)


def test_dashboard_events_ending_soon_and_finished(paths):
    sf = sf_for(paths)
    now = utcnow()
    cal = {"banners": [], "challenges": [], "events": [
        {"id": 1, "name": "Soon", "description": "", "start": None, "end": iso(now + timedelta(days=2)),
         "rewards": []},
        {"id": 2, "name": "Finished", "description": "", "start": None, "end": iso(now + timedelta(days=1)),
         "rewards": [], "finished": True},
        {"id": 3, "name": "Later", "description": "", "start": None, "end": iso(now + timedelta(days=9)),
         "rewards": []}]}
    with sf.begin() as s:
        s.add(HoyolabSnapshot(part="calendar", data=cal, fetched_at=now))
    with make_client(paths) as client:
        body = client.get("/api/dashboard").json()
    assert [e["id"] for e in body["ending_soon"]] == [1]
    finished = next(e for e in body["events"] if e.get("id") == 2)
    assert finished["done"] is True and finished["finished"] is True


def test_dashboard_artifact_domains(paths):
    sf = setup(paths)
    from app.db.models import GameArtifactDomain, GameArtifactSet
    with sf.begin() as s:
        s.merge(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=2))
        s.add(GameArtifactDomain(id=5101, name="Domain of Blessing: Stone Chamber", entrance="Clear Pool and Mountain Cavern",
                                 region="Liyue", elements=["Hydro"], set_ids=[15007]))
        s.get(CharacterGoal, 10000032).artifact_target = {"sets": [{"set_id": 15007, "pieces": 4}], "main": {}, "subs": []}
    with make_client(paths) as client:
        block = client.get("/api/dashboard").json()["artifact_domains"]
    assert block["domains"][0]["entrance"] == "Clear Pool and Mountain Cavern"
    assert block["domains"][0]["sets"][0]["characters"][0]["id"] == 10000032
