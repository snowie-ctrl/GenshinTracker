# backend/tests/test_artifact_check.py
from dataclasses import dataclass

import pytest

from app.artifacts.check import check
from app.artifacts.stats import SLOT_OPTIONS, main_key


@dataclass
class Gear:
    slot: int
    set_name: str
    main_stat: str
    icon: str = "UI_RelicIcon_x"


SETS = {15007: ("Noblesse Oblige", "UI_RelicIcon_15007_4"), 15001: ("Gladiator's Finale", "UI_RelicIcon_15001_4")}
NO = "Noblesse Oblige"
GL = "Gladiator's Finale"


@pytest.mark.parametrize("text,key", [
    ("HP 4780", "hp"), ("ATK 311", "atk"), ("HP 46.6%", "hp%"), ("ATK 46.6%", "atk%"), ("DEF 58.3%", "def%"),
    ("Elemental Mastery 187", "em"), ("Energy Recharge 51.8%", "er"), ("CRIT Rate 31.1%", "crit_rate"),
    ("CRIT DMG 62.2%", "crit_dmg"), ("Healing Bonus 35.9%", "heal"), ("Pyro DMG Bonus 46.6%", "pyro"),
    ("Dendro DMG Bonus 46.6%", "dendro"), ("Physical DMG Bonus 58.3%", "phys"),
])
def test_main_key(text, key):
    assert main_key(text) == key


def test_main_key_aliases():
    assert main_key("HP% 46.6%") == "hp%"
    assert main_key("ER 51.8%") == "er"
    assert main_key("Mystery Stat 12") is None
    assert main_key("") is None
    assert main_key("Shiny DMG Bonus 46.6%") is None


def test_slot_options():
    assert "er" in SLOT_OPTIONS["sands"] and "crit_rate" not in SLOT_OPTIONS["sands"]
    assert "pyro" in SLOT_OPTIONS["goblet"] and "phys" in SLOT_OPTIONS["goblet"]
    assert "heal" in SLOT_OPTIONS["circlet"] and "er" not in SLOT_OPTIONS["circlet"]


FULL_NO = [Gear(1, NO, "HP 4780"), Gear(2, NO, "ATK 311"), Gear(3, NO, "Energy Recharge 51.8%"),
           Gear(4, NO, "Pyro DMG Bonus 46.6%"), Gear(5, GL, "CRIT Rate 31.1%")]


def test_no_target_is_none():
    r = check(None, FULL_NO, SETS)
    assert r["status"] == "none" and r["missing"] == [] and len(r["slots"]) == 5
    assert check({"sets": [], "main": {"sands": []}, "subs": ["er"]}, FULL_NO, SETS)["status"] == "none"


def test_four_piece_and_mains_met():
    t = {"sets": [{"set_id": 15007, "pieces": 4}],
         "main": {"sands": ["er", "atk%"], "goblet": ["pyro"], "circlet": ["crit_rate", "crit_dmg"]}, "subs": []}
    r = check(t, FULL_NO, SETS)
    assert r["status"] == "met"
    assert r["sets"] == [{"set_id": 15007, "name": NO, "icon": "UI_RelicIcon_15007_4", "pieces": 4, "equipped": 4}]
    assert [s["ok"] for s in r["slots"]] == [None, None, True, True, True]


def test_two_plus_two():
    gear = [Gear(1, NO, "HP 4780"), Gear(2, NO, "ATK 311"), Gear(3, GL, "ATK 46.6%"), Gear(4, GL, "ATK 46.6%")]
    t = {"sets": [{"set_id": 15007, "pieces": 2}, {"set_id": 15001, "pieces": 2}], "main": {}, "subs": []}
    assert check(t, gear, SETS)["status"] == "met"


def test_partial_set_and_wrong_main():
    gear = [Gear(1, NO, "HP 4780"), Gear(2, NO, "ATK 311"), Gear(3, GL, "ATK 46.6%"), Gear(4, GL, "HP 46.6%")]
    t = {"sets": [{"set_id": 15007, "pieces": 4}], "main": {"goblet": ["pyro"]}, "subs": []}
    r = check(t, gear, SETS)
    assert r["status"] == "missing"
    assert r["missing"] == ["4pc Noblesse Oblige (2/4)", "Goblet"]
    assert [s["ok"] for s in r["slots"]] == [None, None, None, False]   # sands has no preference


def test_missing_slot_counts():
    gear = [Gear(1, NO, "HP 4780"), Gear(2, NO, "ATK 311"), Gear(4, NO, "Pyro DMG Bonus 46.6%"), Gear(5, NO, "CRIT DMG 62.2%")]
    t = {"sets": [{"set_id": 15007, "pieces": 4}], "main": {"sands": ["er"]}, "subs": []}
    assert check(t, gear, SETS)["missing"] == ["Sands"]


def test_no_gear():
    t = {"sets": [{"set_id": 15007, "pieces": 4}], "main": {}, "subs": []}
    r = check(t, [], SETS)
    assert r["status"] == "missing" and r["missing"] == ["No artifacts equipped"]
    assert r["sets"][0]["equipped"] == 0


def test_check_unparseable_main():
    gear = [Gear(3, NO, "Mystery Stat 12")]
    r = check({"sets": [], "main": {"sands": ["er"]}, "subs": []}, gear, SETS)
    assert r["slots"][0] == {"slot": "sands", "set_name": NO, "icon": "UI_RelicIcon_x",
                             "main_stat": "Mystery Stat 12", "key": None, "ok": False}
    assert r["status"] == "missing" and r["missing"] == ["Sands"]


def test_unknown_set_id_gets_a_placeholder_name():
    r = check({"sets": [{"set_id": 99999, "pieces": 4}], "main": {}, "subs": []}, FULL_NO, SETS)
    assert r["sets"][0]["name"] == "Set 99999" and r["sets"][0]["icon"] is None
