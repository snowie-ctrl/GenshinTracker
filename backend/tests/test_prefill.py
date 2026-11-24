from datetime import datetime

from app.db.models import CharacterGoal, CharacterStatRecommendation
from app.sync.persist import save_details, save_roster
from app.teams.goals import raise_to_build
from fakes import make_detail, make_roster
from helpers import make_client, seed_game
from test_api_characters import sf_for

NOW = datetime(2026, 11, 24)
REC = {"main": {"sands": ["er"], "goblet": ["pyro"], "circlet": ["crit_rate", "crit_dmg"]},
       "subs": ["er", "crit_rate", "crit_dmg"]}
SETS_ONLY = {"sets": [{"set_id": 15007, "pieces": 4}], "main": {"sands": [], "goblet": [], "circlet": []}, "subs": []}


def setup(paths, rec=True, goal_row=None):
    sf = sf_for(paths)
    seed_game(sf)
    with sf.begin() as s:
        save_roster(s, [make_roster(10000032, name="Bennett")], NOW)
        save_details(s, [make_detail(10000032)], NOW)
        if rec:
            s.add(CharacterStatRecommendation(character_id=10000032, data=REC, synced_at=NOW))
        if goal_row is not None:
            s.add(goal_row)
    return sf


def test_goal_switch_prefills_empty_target(paths):
    setup(paths)
    with make_client(paths) as client:
        body = client.put("/api/characters/10000032/goal", json={"goal": "build"}).json()
    assert body["artifact_target"] == {"sets": [], **REC}


def test_prefill_keeps_existing_target(paths):
    from app.db.models import GameArtifactSet
    sf = setup(paths, goal_row=CharacterGoal(character_id=10000032, goal="want", artifact_target=SETS_ONLY,
                                             updated_at=NOW))
    with sf.begin() as s:
        s.add(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=1))
    with make_client(paths) as client:
        body = client.put("/api/characters/10000032/goal", json={"goal": "build"}).json()
    assert body["artifact_target"] == SETS_ONLY


def test_no_recommendation_leaves_target_empty(paths):
    setup(paths, rec=False)
    with make_client(paths) as client:
        body = client.put("/api/characters/10000032/goal", json={"goal": "build"}).json()
    assert body["artifact_target"] is None


def test_explicit_target_wins_over_prefill(paths):
    setup(paths)
    explicit = {"sets": [], "main": {"sands": ["atk%"], "goblet": [], "circlet": []}, "subs": []}
    with make_client(paths) as client:
        body = client.put("/api/characters/10000032/goal", json={"goal": "build", "artifact_target": explicit}).json()
    assert body["artifact_target"] == explicit


def test_leaving_and_reentering_build_keeps_stored_target(paths):
    setup(paths)
    edited = {"sets": [], "main": {"sands": ["hp%"], "goblet": [], "circlet": []}, "subs": []}
    with make_client(paths) as client:
        client.put("/api/characters/10000032/goal", json={"goal": "build"})
        client.put("/api/characters/10000032/goal", json={"artifact_target": edited})
        client.put("/api/characters/10000032/goal", json={"goal": "none"})
        body = client.put("/api/characters/10000032/goal", json={"goal": "build"}).json()
    assert body["artifact_target"] == edited


def test_already_build_is_not_changed_retroactively(paths):
    setup(paths, goal_row=CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=6,
                                        target_skill=9, target_burst=9, target_weapon_level=90, priority=1,
                                        updated_at=NOW))
    with make_client(paths) as client:
        body = client.put("/api/characters/10000032/goal", json={"goal": "build"}).json()
    assert body["artifact_target"] is None


def test_teams_raise_prefills(paths):
    sf = setup(paths)
    with sf.begin() as s:
        assert raise_to_build(s, [10000032]) == [10000032]
    with sf() as s:
        assert s.get(CharacterGoal, 10000032).artifact_target == {"sets": [], **REC}


def test_character_payload_has_recommendation(paths):
    setup(paths)
    with make_client(paths) as client:
        d = client.get("/api/characters/bennett").json()
    assert d["stat_recommendation"] == {**REC, "synced_at": "2026-11-24T00:00:00Z"}


def test_character_payload_with_malformed_recommendation_row(paths):
    sf = setup(paths, rec=False)
    with sf.begin() as s:
        s.add(CharacterStatRecommendation(character_id=10000032, data={}, synced_at=NOW))
    with make_client(paths) as client:
        r = client.get("/api/characters/bennett")
    assert r.status_code == 200
    assert r.json()["stat_recommendation"] == {"main": {"sands": [], "goblet": [], "circlet": []}, "subs": [],
                                               "synced_at": "2026-11-24T00:00:00Z"}


def test_character_payload_without_recommendation(paths):
    setup(paths, rec=False)
    with make_client(paths) as client:
        assert client.get("/api/characters/bennett").json()["stat_recommendation"] is None
