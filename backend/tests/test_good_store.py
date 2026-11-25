import json
import logging
from datetime import datetime

from sqlalchemy import func, select

from app.db.models import (GameArtifactSet, GameMaterial, GameMeta, GameWeapon, GoodArtifactRow, GoodImport,
                           GoodMaterial, GoodWeaponRow)
from app.gamedata.service import META_MAT_KEYS
from app.good.keys import KeyIndex
from app.good.parse import parse_good
from app.good.store import (delete_snapshot, good_active, match_file, owned_weapons, replace_snapshot,
                            scan_counts)
from app.settings.store import set_setting
from helpers import FIXTURES, seed_game

NOW = datetime(2026, 11, 22, 12, 0)
SAMPLE = (FIXTURES / "good_sample.json").read_bytes()


def seed_catalogue(sf):
    seed_game(sf)
    with sf.begin() as s:
        for order, (mid, name) in enumerate([(202, "Mora"), (104301, "Teachings of Freedom"),
                                             (104302, "Guide to Freedom"), (113003, "Dvalin's Plume")]):
            s.add(GameMaterial(id=mid, name=name, icon=f"UI_ItemIcon_{mid}", rarity=3, yatta_type="x",
                               category="talent", family=mid, craft_from=None, sources=[], sort_order=order,
                               detail_fetched=True))
        s.add(GameWeapon(id=11401, name="Favonius Sword", icon="UI_EquipIcon_Sword_Zephyrus", rarity=4,
                         weapon_type="Sword"))
        s.add(GameWeapon(id=11509, name="Mistsplitter Reforged", icon="UI_EquipIcon_Sword_Narukami", rarity=5,
                         weapon_type="Sword"))
        s.add(GameArtifactSet(id=15001, name="Gladiator's Finale", icon="UI_RelicIcon_15001_4", sort_order=1))
        s.add(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=2))
        s.merge(GameMeta(key=META_MAT_KEYS, value=["Fowl", "GuideToFreedom", "Mora", "SweetMadame"]))


def index(sf) -> KeyIndex:
    with sf() as s:
        return KeyIndex.build(s)


def test_match_counts_and_unmatched(session_factory):
    seed_catalogue(session_factory)
    m = match_file(parse_good(SAMPLE), index(session_factory))
    assert m.materials == {202: 1234567, 104301: 40, 104302: 12, 113003: 3}
    assert m.counts == {"materials": {"matched": 4, "ignored": 1, "unmatched": 1},
                        "weapons": {"matched": 3, "unmatched": 1},
                        "artifacts": {"matched": 3, "unmatched": 0}}
    assert m.unmatched == ["character:SomeNewCharacter", "material:NotARealItem", "weapon:UnknownBlade"]


def test_food_is_ignored_not_unmatched(session_factory):
    seed_catalogue(session_factory)
    body = {"format": "GOOD", "version": 2, "materials": {"Fowl": 3, "SweetMadame": 2, "Mora": 5}}
    m = match_file(parse_good(json.dumps(body).encode()), index(session_factory))
    assert m.counts["materials"] == {"matched": 1, "ignored": 2, "unmatched": 0}
    assert m.unmatched == []


def test_holders_traveler_and_unknown(session_factory):
    seed_catalogue(session_factory)
    m = match_file(parse_good(SAMPLE), index(session_factory))
    bennett = next(w for w in m.weapons if w["location"] == "Bennett")
    assert bennett["character_id"] == 10000032
    free = [w for w in m.weapons if w["location"] is None]
    assert len(free) == 2 and all(w["character_id"] is None for w in free)
    traveler = next(a for a in m.artifacts if a["location"] == "TravelerAnemo")
    assert traveler["character_id"] == 1000000502
    unknown = next(a for a in m.artifacts if a["location"] == "SomeNewCharacter")
    assert unknown["character_id"] is None            # equipped by someone we can't name, not "unequipped"


def test_index_maps_manekina_and_collisions_keep_first(session_factory, caplog):
    seed_catalogue(session_factory)
    with session_factory.begin() as s:
        s.add(GameWeapon(id=99999, name="Favonius-Sword", icon="x", rarity=4, weapon_type="Sword"))
    caplog.set_level(logging.INFO)
    idx = index(session_factory)
    assert idx.weapons["FavoniusSword"] == 11401
    assert idx.character("Manekina") is None and idx.character("Manekin") is None
    assert idx.character("") is None
    assert "FavoniusSword" in caplog.text


def test_replace_snapshot_writes_everything(session_factory):
    seed_catalogue(session_factory)
    with session_factory.begin() as s:
        summary = replace_snapshot(s, parse_good(SAMPLE), KeyIndex.build(s), NOW)
    assert summary.imported_at == "2026-11-22T12:00:00Z" and summary.source == "Test_Scanner"
    with session_factory() as s:
        assert s.get(GoodImport, 1).counts["weapons"]["matched"] == 3
        assert s.scalar(select(func.count()).select_from(GoodWeaponRow)) == 3
        assert s.scalar(select(func.count()).select_from(GoodArtifactRow)) == 3
        assert s.get(GoodMaterial, 104302).count == 12
        art = s.scalars(select(GoodArtifactRow).where(GoodArtifactRow.slot == "flower")).one()
        assert art.substats == [{"key": "critRate_", "value": 3.9}, {"key": "atk_", "value": 5.8}]


def test_reimport_replaces_everything(session_factory):
    seed_catalogue(session_factory)
    with session_factory.begin() as s:
        replace_snapshot(s, parse_good(SAMPLE), KeyIndex.build(s), NOW)
    small = {"format": "GOOD", "version": 1, "materials": {"Mora": 7}}
    with session_factory.begin() as s:
        replace_snapshot(s, parse_good(json.dumps(small).encode()), KeyIndex.build(s), NOW)
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(GoodWeaponRow)) == 0
        assert s.scalar(select(func.count()).select_from(GoodArtifactRow)) == 0
        assert {r.material_id: r.count for r in s.scalars(select(GoodMaterial))} == {202: 7}
        assert s.get(GoodImport, 1).source is None


def test_delete_and_active_and_aggregates(session_factory):
    seed_catalogue(session_factory)
    with session_factory.begin() as s:
        replace_snapshot(s, parse_good(SAMPLE), KeyIndex.build(s), NOW)
    with session_factory() as s:
        assert good_active(s) is None                     # toggle is off by default
    with session_factory.begin() as s:
        set_setting(s, "good_import_enabled", True)
    with session_factory() as s:
        assert good_active(s).id == 1
        assert scan_counts(s)[202] == 1234567
        assert owned_weapons(s)[11401] == {"count": 2, "best_level": 90, "best_refinement": 3}
    with session_factory.begin() as s:
        delete_snapshot(s)
    with session_factory() as s:
        assert good_active(s) is None and scan_counts(s) == {}
        assert s.scalar(select(func.count()).select_from(GoodArtifactRow)) == 0


def test_unmatched_is_capped_at_200(session_factory):
    seed_catalogue(session_factory)
    body = {"format": "GOOD", "version": 2, "materials": {f"Nope{i:04d}": 1 for i in range(300)}}
    m = match_file(parse_good(json.dumps(body).encode()), index(session_factory))
    assert len(m.unmatched) == 200 and m.counts["materials"]["unmatched"] == 300


def test_check_cli_prints_only_the_summary(session_factory, paths, capsys):
    from app.good.check import main
    seed_catalogue(session_factory)
    assert main(["--db", str(paths.db_file), str(FIXTURES / "good_sample.json")]) == 0
    out = capsys.readouterr().out
    assert "materials: 4 matched, 1 ignored, 1 unmatched" in out
    assert "weapon:UnknownBlade" in out
    assert "1234567" not in out and "Test_Scanner" not in out


def test_teapot_materials_match_by_name(session_factory):
    seed_catalogue(session_factory)
    with session_factory.begin() as s:
        for order, (mid, name) in enumerate([(101301, "Birch Wood"), (101401, "Fabric")], start=10):
            s.add(GameMaterial(id=mid, name=name, icon=f"UI_ItemIcon_{mid}", rarity=1, yatta_type="material",
                               category="teapot", family=mid, craft_from=None, sources=[], sort_order=order,
                               detail_fetched=True))
    body = {"format": "GOOD", "version": 2, "materials": {"BirchWood": 250, "Fabric": 40, "Fowl": 3}}
    m = match_file(parse_good(json.dumps(body).encode()), index(session_factory))
    assert m.materials == {101301: 250, 101401: 40}
    assert m.counts["materials"] == {"matched": 2, "ignored": 1, "unmatched": 0}
