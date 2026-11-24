"""Stat keys for artifact targets and the parser for HoYoLAB main-stat strings ("ATK 46.6%")."""
from __future__ import annotations

ELEMENTS = ("pyro", "hydro", "electro", "cryo", "anemo", "geo", "dendro")
MAIN_SLOTS = ("sands", "goblet", "circlet")
SLOT_NAMES = {1: "flower", 2: "plume", 3: "sands", 4: "goblet", 5: "circlet"}
SLOT_OPTIONS: dict[str, tuple[str, ...]] = {
    "sands": ("hp%", "atk%", "def%", "em", "er"),
    "goblet": ("hp%", "atk%", "def%", "em", *ELEMENTS, "phys"),
    "circlet": ("hp%", "atk%", "def%", "em", "crit_rate", "crit_dmg", "heal"),
}
SUB_KEYS = ("hp", "atk", "def", "hp%", "atk%", "def%", "em", "er", "crit_rate", "crit_dmg")

_NAMES = {"Elemental Mastery": "em", "Energy Recharge": "er", "ER": "er", "CRIT Rate": "crit_rate",
          "CRIT DMG": "crit_dmg", "Healing Bonus": "heal", "Physical DMG Bonus": "phys"}


def main_key(text: str) -> str | None:
    """'Pyro DMG Bonus 46.6%' -> 'pyro'; 'ATK 311' -> 'atk'; anything unknown -> None."""
    name, _, value = (text or "").strip().rpartition(" ")
    if not name:
        return None
    pct = value.endswith("%")
    if name.endswith("%"):
        name, pct = name[:-1], True
    if name in ("HP", "ATK", "DEF"):
        return name.lower() + ("%" if pct else "")
    if name in _NAMES:
        return _NAMES[name]
    if name.endswith(" DMG Bonus"):
        element = name[: -len(" DMG Bonus")].lower()
        if element in ELEMENTS:
            return element
    return None
