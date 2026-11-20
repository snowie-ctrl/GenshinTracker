import time
from datetime import datetime

from app.db.engine import make_engine, make_session_factory, migrate
from app.db.models import (
    CharacterGoal, GameDomain, GameMaterial, GameWeapon, MaterialGap, MaterialTotal, WeeklyBossDone,
)
from app.sync.persist import save_details, save_notes, save_roster
from app.timeutil import utcnow
from fakes import NOTES, FakeSource, make_detail, make_roster
from helpers import make_client, seed_game, wait_for_sync


def sf_for(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    return make_session_factory(engine)


def setup(paths, catalogue=True):
    sf = sf_for(paths)
    seed_game(sf)
    now = utcnow()
    with sf.begin() as s:
        save_roster(s, [make_roster(10000032, level=80, name="Bennett")], now)
        save_details(s, [make_detail(10000032, talents=(6, 8, 8))])
        save_notes(s, NOTES, now)
        s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, updated_at=now))
        if catalogue:
            for mid, name, cat, rarity, craft, sources in [
                (104301, "Teachings of Freedom", "talent", 2, None, []),
                (104302, "Guide to Freedom", "talent", 3, 104301, []),
                (113003, "Dvalin's Plume", "weekly", 5, None, [{"kind": "weekly_boss", "name": "Stormterror", "days": []}]),
            ]:
                s.add(GameMaterial(id=mid, name=name, icon=f"UI_ItemIcon_{mid}", rarity=rarity, yatta_type="x",
                                   category=cat, family=104301 if cat == "talent" else mid, craft_from=craft,
                                   sources=sources, sort_order=mid, detail_fetched=True))
            s.add(GameDomain(id=4213, name="Domain of Mastery: Forsaken Rift", kind="talent", city=1,
                             weekdays=[0, 1, 2, 3, 4, 5, 6], material_ids=[104302, 104301]))
            s.add(GameWeapon(id=11401, name="Favonius Sword", icon="UI_EquipIcon_Sword_Zephyrus", rarity=4,
                             weapon_type="Sword"))
            s.add(GameWeapon(id=13407, name="Favonius Lance", icon="UI_EquipIcon_Pole_Zephyrus", rarity=4,
                             weapon_type="Polearm"))
        s.add(MaterialTotal(material_id=104302, name="Guide to Freedom", icon="", rarity=3, need=9, short=4, spare=0))
        s.add(MaterialTotal(material_id=113003, name="Dvalin's Plume", icon="", rarity=5, need=2, short=2, spare=0))
        s.add(MaterialGap(character_id=10000032, material_id=104302, need=9, short=4))
        s.add(MaterialGap(character_id=10000032, material_id=113003, need=2, short=2))
    return sf


def test_inventory_endpoint(paths):
    setup(paths)
    with make_client(paths) as client:
        body = client.get("/api/inventory").json()
    cats = {c["key"]: c for c in body["categories"]}
    guide = next(m for m in cats["talent"]["materials"] if m["id"] == 104302)
    assert guide["state"] == "short" and guide["have"] == 5 and guide["to_farm"] == 4
    assert guide["characters"][0]["name"] == "Bennett"
    assert body["gaps"]["stale"] is False            # not connected in tests -> never stale


def test_inventory_without_catalogue_shows_other(paths):
    setup(paths, catalogue=False)
    with make_client(paths) as client:
        body = client.get("/api/inventory").json()
    assert [c["key"] for c in body["categories"]] == ["other"]
    with make_client(paths) as client:
        dash = client.get("/api/dashboard")
    assert dash.status_code == 200


def test_dashboard_planner_sections(paths):
    setup(paths)
    with make_client(paths) as client:
        body = client.get("/api/dashboard").json()
    assert body["farm_today"]["domains"][0]["name"] == "Domain of Mastery: Forsaken Rift"
    boss = body["weekly_bosses"]["bosses"][0]
    assert boss["name"] == "Stormterror" and boss["done"] is False
    card = body["building_cards"][0]
    assert card["character"]["name"] == "Bennett" and {m["id"] for m in card["materials"]} == {104302, 113003}
    assert "gaps" in body


def test_weekly_boss_toggle_round_trip(paths):
    sf = setup(paths)
    with make_client(paths) as client:
        assert client.put("/api/weekly-bosses/Stormterror", json={"done": True}).json() == {"name": "Stormterror", "done": True}
        assert client.get("/api/dashboard").json()["weekly_bosses"]["bosses"][0]["done"] is True
        client.put("/api/weekly-bosses/Stormterror", json={"done": False})
        assert client.get("/api/dashboard").json()["weekly_bosses"]["bosses"][0]["done"] is False
        assert client.put("/api/weekly-bosses/Dvalin%27s%20Lair", json={"done": True}).json()["name"] == "Dvalin's Lair"
    with sf() as s:
        assert s.query(WeeklyBossDone).count() == 1


def test_old_weekly_rows_are_pruned(paths):
    sf = setup(paths)
    with sf.begin() as s:
        s.add(WeeklyBossDone(boss="Stormterror", week_start=datetime(2020, 1, 6, 20)))
    with make_client(paths) as client:
        client.put("/api/weekly-bosses/Childe", json={"done": True})
    with sf() as s:
        assert [r.boss for r in s.query(WeeklyBossDone)] == ["Childe"]


def test_weapons_filtered_by_type(paths):
    setup(paths)
    with make_client(paths) as client:
        assert [w["name"] for w in client.get("/api/weapons?type=Sword").json()] == ["Favonius Sword"]


def test_character_detail_shortfall_and_planned_weapon(paths):
    setup(paths)
    with make_client(paths) as client:
        body = client.get("/api/characters/bennett").json()
        assert {m["id"] for m in body["shortfall"]["materials"]} == {104302, 113003}
        assert body["planned_weapon"]["equipped"] is True and body["planned_weapon_id"] is None
        r = client.put("/api/characters/10000032/goal", json={"planned_weapon_id": 11401})
        assert r.status_code == 200 and r.json()["planned_weapon_id"] == 11401
        body = client.get("/api/characters/bennett").json()
        assert body["planned_weapon"]["name"] == "Favonius Sword" and body["planned_weapon"]["equipped"] is False
        assert client.put("/api/characters/10000032/goal", json={"planned_weapon_id": 13407}).status_code == 400
        assert client.put("/api/characters/10000032/goal", json={"planned_weapon_id": 1}).status_code == 400
        assert client.put("/api/characters/10000032/goal", json={"planned_weapon_id": None}).json()["planned_weapon_id"] is None
        assert client.get("/api/characters/furina").json()["shortfall"] is None   # not Build


def test_goal_change_schedules_gaps_run(paths):
    setup(paths)
    source = FakeSource()
    with make_client(paths, source=source) as client:
        client.app.state.ctx.sync._gaps_delay = 0.01
        client.put("/api/characters/10000032/goal", json={"targets": {"level": 90, "normal": 9, "skill": 8,
                                                                       "burst": 8, "weapon_level": 90}})
        deadline = time.monotonic() + 5
        while not any(isinstance(c, tuple) and c[0] == "gaps" for c in source.calls):
            assert time.monotonic() < deadline, "gaps run never started"
            time.sleep(0.05)
        wait_for_sync(client)
    assert any(isinstance(c, tuple) and c[0] == "gaps" for c in source.calls)
