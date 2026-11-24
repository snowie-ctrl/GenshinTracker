from app.db.models import CharacterGoal, GameArtifactDomain, GameArtifactSet
from app.sync.persist import save_details, save_roster
from app.timeutil import utcnow
from fakes import make_detail, make_roster
from helpers import make_client, seed_game
from test_api_characters import sf_for

TARGET = {"sets": [{"set_id": 15007, "pieces": 4}],
          "main": {"sands": ["er"], "goblet": ["pyro"], "circlet": ["crit_rate", "crit_dmg"]},
          "subs": ["crit_rate", "crit_dmg", "er"]}


def setup(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with sf.begin() as s:
        now = utcnow()
        save_roster(s, [make_roster(10000032, name="Bennett"),
                        make_roster(1000000503, raw_id=10000007, name="Traveler", element="Geo")], now)
        save_details(s, [make_detail(10000032), make_detail(1000000503)])   # one Noblesse flower each
        s.add(GameArtifactSet(id=15001, name="Gladiator's Finale", icon="UI_RelicIcon_15001_4", sort_order=1))
        s.add(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=2))
        s.add(GameArtifactDomain(id=5101, name="Domain of Blessing: Stone Chamber",
                                 entrance="Clear Pool and Mountain Cavern", region="Liyue",
                                 elements=["Hydro"], set_ids=[15007]))
        s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, priority=1, updated_at=now))
    return sf


def test_goal_stores_target_and_returns_check(paths):
    setup(paths)
    with make_client(paths) as client:
        r = client.put("/api/characters/10000032/goal", json={"artifact_target": TARGET})
        assert r.status_code == 200 and r.json()["artifact_target"] == TARGET
        d = client.get("/api/characters/bennett").json()
    assert d["artifact_target"] == TARGET and d["artifacts_done"] is False
    assert d["artifact_check"]["status"] == "missing"
    assert d["artifact_check"]["sets"][0]["equipped"] == 1
    assert d["artifact_check"]["missing"][0] == "4pc Noblesse Oblige (1/4)"


def test_omit_keeps_and_null_clears(paths):
    setup(paths)
    with make_client(paths) as client:
        client.put("/api/characters/10000032/goal", json={"artifact_target": TARGET})
        client.put("/api/characters/10000032/goal", json={"artifacts_done": True})
        d = client.get("/api/characters/bennett").json()
        assert d["artifact_target"] == TARGET and d["artifacts_done"] is True
        client.put("/api/characters/10000032/goal", json={"artifact_target": None})
        d = client.get("/api/characters/bennett").json()
    assert d["artifact_target"] is None and d["artifact_check"]["status"] == "none"


def test_no_target_check_is_none(paths):
    setup(paths)
    with make_client(paths) as client:
        d = client.get("/api/characters/bennett").json()
    assert d["artifact_target"] is None and d["artifact_check"]["status"] == "none"
    assert d["artifact_check"]["slots"][0]["slot"] == "flower"


def test_invalid_targets_are_422(paths):
    setup(paths)
    bad = [
        {"sets": [{"set_id": 15007, "pieces": 3}]},
        {"sets": [{"set_id": 15007, "pieces": 4}, {"set_id": 15001, "pieces": 2}]},
        {"sets": [{"set_id": 15007, "pieces": 2}, {"set_id": 15007, "pieces": 2}]},
        {"sets": [{"set_id": 15007, "pieces": 2}, {"set_id": 15001, "pieces": 2}, {"set_id": 15001, "pieces": 2}]},
        {"main": {"sands": ["crit_rate"]}},
        {"main": {"goblet": ["shiny"]}},
        {"subs": ["er", "er"]},
        {"subs": ["heal"]},
        {"sets": [{"set_id": 99999, "pieces": 4}]},
        {"extra": 1},
    ]
    with make_client(paths) as client:
        for body in bad:
            assert client.put("/api/characters/10000032/goal", json={"artifact_target": body}).status_code == 422, body


def test_single_two_piece_is_allowed(paths):
    setup(paths)
    with make_client(paths) as client:
        r = client.put("/api/characters/10000032/goal",
                       json={"artifact_target": {"sets": [{"set_id": 15007, "pieces": 2}]}})
    assert r.status_code == 200
    assert r.json()["artifact_target"] == {"sets": [{"set_id": 15007, "pieces": 2}],
                                           "main": {"sands": [], "goblet": [], "circlet": []}, "subs": []}


def test_leaving_build_clears_done_keeps_target(paths):
    setup(paths)
    with make_client(paths) as client:
        client.put("/api/characters/10000032/goal", json={"artifact_target": TARGET, "artifacts_done": True})
        client.put("/api/characters/10000032/goal", json={"goal": "none"})
        d = client.get("/api/characters/bennett").json()
    assert d["artifacts_done"] is False and d["artifact_target"] == TARGET


def test_traveler_element_uses_synced_gear(paths):
    setup(paths)
    with make_client(paths) as client:
        client.put("/api/characters/1000000502/goal",
                   json={"goal": "build", "artifact_target": {"sets": [{"set_id": 15007, "pieces": 4}]}})
        d = client.get("/api/characters/anemo-traveler").json()
    assert d["artifact_check"]["sets"][0]["equipped"] == 1           # the synced Geo element's flower
    assert d["artifact_check"]["missing"] != ["No artifacts equipped"]


def test_artifact_sets_lists_domains(paths):
    setup(paths)
    with make_client(paths) as client:
        rows = client.get("/api/artifact-sets").json()
    assert [r["name"] for r in rows] == ["Gladiator's Finale", "Noblesse Oblige"]
    assert rows[0]["domain"] is None
    assert rows[1]["domain"] == {"id": 5101, "name": "Domain of Blessing: Stone Chamber",
                                 "entrance": "Clear Pool and Mountain Cavern", "region": "Liyue"}


def test_traveler_current_element_gear_beats_stale_own_rows(paths):
    from app.db.models import OwnedArtifact
    from app.settings.store import set_setting
    sf = setup(paths)
    with sf.begin() as s:
        set_setting(s, "traveler_current_element", "Geo")      # Geo is current; Anemo is owned but stale
        s.add(OwnedArtifact(character_id=1000000502, slot=2, set_name="Gladiator's Finale", rarity=5, level=20,
                            main_stat="atk", substats=[], icon="UI_RelicIcon_15001_2"))
    with make_client(paths) as client:
        client.put("/api/characters/1000000502/goal",
                   json={"goal": "build", "artifact_target": {"sets": [{"set_id": 15007, "pieces": 4}]}})
        d = client.get("/api/characters/anemo-traveler").json()
    assert d["artifact_check"]["sets"][0]["equipped"] == 1           # Geo's Noblesse flower, not Anemo's stale row


def test_artifact_sets_unknown_source_without_domains(paths):
    sf = setup(paths)
    with sf.begin() as s:
        s.query(GameArtifactDomain).delete()
    with make_client(paths) as client:
        rows = client.get("/api/artifact-sets").json()
    assert [r["source"] for r in rows] == ["unknown", "unknown"] and all(r["domain"] is None for r in rows)


def test_artifact_sets_source_with_domains(paths):
    setup(paths)
    with make_client(paths) as client:
        rows = client.get("/api/artifact-sets").json()
    assert [r["source"] for r in rows] == ["none", "domain"]


def test_dashboard_sources_known_flag(paths):
    sf = setup(paths)
    with make_client(paths) as client:
        assert client.get("/api/dashboard").json()["artifact_domains"]["sources_known"] is True
    with sf.begin() as s:
        s.query(GameArtifactDomain).delete()
    with make_client(paths) as client:
        assert client.get("/api/dashboard").json()["artifact_domains"]["sources_known"] is False
