import pytest
from app.db.engine import make_engine, make_session_factory, migrate
from app.db.models import CharacterGoal, GameArtifactSet, GameMaterial, GameMeta, GameWeapon
from app.gamedata.service import META_MAT_KEYS
from app.planner.requests import snapshot
from app.sync.hoyolab import GapResult, MaterialAmount
from app.sync.persist import save_gaps
from app.timeutil import utcnow
from helpers import FIXTURES, make_client, seed_game

SAMPLE = (FIXTURES / "good_sample.json").read_bytes()


def setup(paths, catalogue=True, gaps=True):
    engine = make_engine(paths.db_file)
    migrate(engine)
    sf = make_session_factory(engine)
    seed_game(sf)
    now = utcnow()
    with sf.begin() as s:
        if catalogue:
            for order, (mid, name, cat) in enumerate([(202, "Mora", "exp"), (104301, "Teachings of Freedom", "talent"),
                                                      (104302, "Guide to Freedom", "talent"),
                                                      (113003, "Dvalin's Plume", "weekly"),
                                                      (100055, "Small Lamp Grass", "specialty")]):
                s.add(GameMaterial(id=mid, name=name, icon=f"UI_ItemIcon_{mid}", rarity=3, yatta_type="x",
                                   category=cat, family=mid, craft_from=None, sources=[], sort_order=order,
                                   detail_fetched=True))
            s.add(GameWeapon(id=11401, name="Favonius Sword", icon="UI_EquipIcon_Sword_Zephyrus", rarity=4,
                             weapon_type="Sword"))
            s.add(GameWeapon(id=11509, name="Mistsplitter Reforged", icon="UI_EquipIcon_Sword_Narukami",
                             rarity=5, weapon_type="Sword"))
            s.add(GameWeapon(id=11301, name="Cool Steel", icon="UI_EquipIcon_Sword_Steel", rarity=3,
                             weapon_type="Sword"))
            s.add(GameArtifactSet(id=15001, name="Gladiator's Finale", icon="UI_RelicIcon_15001_4", sort_order=1))
            s.add(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=2))
            s.merge(GameMeta(key=META_MAT_KEYS, value=["Fowl"]))
        if catalogue and gaps:
            s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                                target_skill=8, target_burst=8, target_weapon_level=90, updated_at=now))
            s.flush()
            amt = lambda mid, need, short: MaterialAmount(mid, "x", "", 3, need, short)  # noqa: E731
            save_gaps(s, GapResult(per_character={10000032: [amt(104302, 15, 7), amt(104301, 10, 0),
                                                             amt(113003, 2, 0)]},
                                   total=[amt(104302, 15, 7), amt(104301, 10, 0), amt(113003, 2, 0)], spare=[]),
                      snapshot(s), [], now)
    engine.dispose()


def enable(client, on=True):
    assert client.put("/api/settings", json={"good_import_enabled": on}).status_code == 200


def upload(client, content=SAMPLE, name="good.json"):
    return client.post("/api/good/import", files={"file": (name, content, "application/json")})


def mats(client) -> dict[int, dict]:
    body = client.get("/api/inventory").json()
    return {m["id"]: m for c in body["categories"] for m in c["materials"]}


def test_import_requires_the_toggle(paths):
    setup(paths)
    with make_client(paths) as client:
        r = upload(client)
        assert r.status_code == 409 and "Settings" in r.json()["detail"]
        assert client.get("/api/good/status").json() == {"enabled": False, "imported_at": None, "source": None,
                                                        "counts": None, "unmatched": []}


def test_import_and_status(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        r = upload(client)
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "Test_Scanner"
        assert body["counts"]["materials"] == {"matched": 4, "ignored": 1, "unmatched": 1}
        assert "weapon:UnknownBlade" in body["unmatched"]
        status = client.get("/api/good/status").json()
        assert status["enabled"] is True and status["imported_at"] == body["imported_at"]


def test_bad_files_change_nothing(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        upload(client)
        before = client.get("/api/good/status").json()
        r = upload(client, b'{"format": "GOOD", "version": 9}')
        assert r.status_code == 400 and r.json()["detail"] == "Unsupported GOOD version 9"
        assert upload(client, b"not json").status_code == 400
        assert client.get("/api/good/status").json() == before


def test_size_limit(paths, monkeypatch):
    import app.api.good as good_api
    monkeypatch.setattr(good_api, "GOOD_UPLOAD_MAX_BYTES", 100)
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        assert upload(client, b" " * 101).status_code == 413


def test_empty_catalogue_is_409(paths):
    setup(paths, catalogue=False)
    with make_client(paths) as client:
        enable(client)
        r = upload(client)
        assert r.status_code == 409 and r.json()["detail"] == "Refresh game data first"


def test_inventory_scan_fields(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        before = mats(client)
        assert before[104302]["scan"] is None and client.get("/api/inventory").json()["good"] is None
        upload(client)
        body = client.get("/api/inventory").json()
        assert body["good"]["source"] == "Test_Scanner"
        after = mats(client)
        assert after[104302]["scan"] == 12 and after[100055]["scan"] == 0   # absent from the file = 0
        assert after[202]["scan"] == 1234567


def test_inventory_to_farm_unchanged_by_import(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        before = mats(client)
        upload(client)
        after = mats(client)
        for mid, m in before.items():
            for k in ("state", "need", "short", "have", "craftable", "to_farm"):
                assert after[mid][k] == m[k], (mid, k)


def test_weapons_and_artifacts_lists(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        assert client.get("/api/good/weapons").status_code == 404
        upload(client)
        ws = client.get("/api/good/weapons").json()
        assert [w["name"] for w in ws] == ["Mistsplitter Reforged", "Favonius Sword", "Favonius Sword"]
        assert ws[1]["level"] == 90 and ws[1]["holder"]["slug"] == "bennett"
        assert ws[0]["holder"] is None and ws[0]["location"] is None
        arts = client.get("/api/good/artifacts").json()
        assert [(a["set_name"], a["slot"]) for a in arts] == [
            ("Gladiator's Finale", "flower"), ("Noblesse Oblige", "goblet"), ("Noblesse Oblige", "sands")]
        assert arts[0]["icon"] == "UI_RelicIcon_15001_4" and arts[1]["icon"] == "UI_RelicIcon_15007_1"
        assert arts[0]["holder"]["slug"] == "anemo-traveler"
        assert arts[2]["holder"] is None and arts[2]["location"] == "SomeNewCharacter"


def test_weapon_picker_marks_owned_first(paths):
    setup(paths)
    with make_client(paths) as client:
        assert all(w["owned"] is None for w in client.get("/api/weapons?type=Sword").json())
        enable(client)
        upload(client)
        ws = client.get("/api/weapons?type=Sword").json()
        assert [w["name"] for w in ws] == ["Mistsplitter Reforged", "Favonius Sword", "Cool Steel"]
        assert ws[1]["owned"] == {"count": 2, "best_level": 90, "best_refinement": 3}
        assert ws[2]["owned"] is None


def test_toggle_off_hides_and_on_restores(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        upload(client)
        enable(client, False)
        assert mats(client)[104302]["scan"] is None
        assert client.get("/api/inventory").json()["good"] is None
        assert client.get("/api/good/weapons").status_code == 404
        assert client.get("/api/good/artifacts").status_code == 404
        assert all(w["owned"] is None for w in client.get("/api/weapons?type=Sword").json())
        assert client.get("/api/good/status").json()["imported_at"] is not None   # kept for Settings
        assert client.get("/api/settings").json()["good_import_enabled"] is False
        enable(client)
        assert mats(client)[104302]["scan"] == 12


def test_delete(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        upload(client)
        enable(client, False)
        assert client.delete("/api/good").status_code == 204     # allowed while disabled
        enable(client)
        assert client.get("/api/good/status").json()["imported_at"] is None
        assert mats(client)[104302]["scan"] is None


def test_file_contents_never_logged(paths, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        upload(client)
    assert "1234567" not in caplog.text and "Test_Scanner" not in caplog.text
