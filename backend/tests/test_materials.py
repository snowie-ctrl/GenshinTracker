# backend/tests/test_materials.py
from app.gamedata.materials import (
    CATEGORIES, CATEGORY_LABELS, categorize, parse_daily_dungeon, parse_material_detail, parse_material_list, parse_weapon_list,
)
from helpers import load_fixture


def test_categorize_rules():
    assert categorize("commonCurrency", 3, 202) == "exp"            # Mora
    assert categorize("characterEXPMaterial", 4, 104003) == "exp"
    assert categorize("weaponEnhancementMaterial", 3, 104013) == "exp"
    assert categorize("characterAscensionMaterial", 2, 104111) == "ascension"
    assert categorize("characterLevelUpMaterial", 4, 113001) == "ascension"   # normal boss drop
    assert categorize("characterLevelUpMaterial", 5, 113003) == "weekly"
    assert categorize("characterLevelUpMaterial", 4, 113021) == "special"     # Dream Solvent
    assert categorize("characterTalentMaterial", 5, 104319) == "special"      # Crown
    assert categorize("characterTalentMaterial", 3, 104302) == "talent"
    assert categorize("localSpecialtyMondstadt", 1, 100055) == "specialty"
    assert categorize("weaponAscensionMaterial", 2, 114001) == "weapon"
    assert categorize("characterandWeaponEnhancementMaterial", 1, 112002) == "enemy"
    assert categorize("cookingIngredient", 1, 100001) is None
    assert categorize("questItem", 4, 100100) is None


def test_parse_material_list_keeps_upgrade_materials_only():
    mats = {m.id: m for m in parse_material_list(load_fixture("yatta_material.json"))}
    assert 100001 not in mats and 100100 not in mats
    assert mats[104302].category == "talent" and mats[104302].rarity == 3
    assert mats[100055].region == "Mondstadt"
    assert mats[104302].region is None


def test_parse_material_detail_craft_chain_and_sources():
    details = load_fixture("yatta_material_details.json")
    frag = parse_material_detail(details["104112"], rarity=3)
    assert frag.craft_from == 104111                      # 3 slivers -> 1 fragment; conversions ignored
    assert frag.sources == [{"kind": "text", "name": "Check the Enemies Tab in the Adventurer Handbook", "days": []}]
    guide = parse_material_detail(details["104302"], rarity=3)
    assert guide.craft_from == 104301
    assert guide.sources == [{"kind": "domain", "name": "Domain of Mastery: Forsaken Rift", "days": [0, 3, 6]}]
    plume = parse_material_detail(details["113003"], rarity=5)
    assert plume.craft_from is None                       # Dream Solvent conversion is not a 3:1 craft
    assert plume.sources[0] == {"kind": "weekly_boss", "name": "Stormterror", "days": []}


def test_parse_daily_dungeon_merges_weekdays_and_filters_rewards():
    domains = parse_daily_dungeon(load_fixture("yatta_daily_dungeon.json"), {104301, 104302, 104303, 114001})
    by_id = {d.id: d for d in domains}
    assert set(by_id) == {4213, 4313}                     # trounce domain dropped
    assert by_id[4213].kind == "talent" and by_id[4213].weekdays == [0, 3, 6]
    assert by_id[4213].material_ids == [104303, 104302, 104301]   # 102/202/105 filtered out
    assert by_id[4313].kind == "weapon" and by_id[4313].weekdays == [0, 6]


def test_parse_weapon_list_maps_types():
    weapons = parse_weapon_list(load_fixture("yatta_weapon.json"))
    assert [w.name for w in weapons] == ["Mistsplitter Reforged", "Favonius Lance", "Favonius Sword"]
    assert {w.weapon_type for w in weapons} == {"Sword", "Polearm"}


def test_categorize_teapot_range():
    assert categorize("material", 1, 101299) is None
    assert categorize("material", 1, 101300) == "teapot"
    assert categorize("material", 1, 101301) == "teapot"      # Birch Wood
    assert categorize("material", 1, 101404) == "teapot"      # Blue Dye
    assert categorize("material", 1, 101499) == "teapot"
    assert categorize("material", 1, 101500) is None
    assert categorize("material", 1, 100618) is None          # Strange Tooth: type material, outside range
    assert categorize("cookingIngredient", 1, 101301) is None  # inside range, wrong type


def test_teapot_category_is_last_and_labelled():
    assert CATEGORIES[-1] == "teapot"
    assert CATEGORY_LABELS["teapot"] == "Serenitea Pot: wood, fabric & dyes"
    assert set(CATEGORIES) <= set(CATEGORY_LABELS)


def test_parse_material_list_keeps_teapot_materials():
    mats = {m.id: m for m in parse_material_list(load_fixture("yatta_material.json"))}
    assert mats[101301].category == "teapot" and mats[101301].name == "Birch Wood"
    assert mats[101401].category == "teapot" and mats[101401].region is None
    assert 100618 not in mats
