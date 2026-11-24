"""HoYoLAB's recommended artifact stats (character detail `recommend_relic_property`) in our stat keys (sub-project 9).
Only `recommend_properties` is read; the player's own `custom_properties` is ignored and never stored."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.artifacts.stats import MAIN_SLOTS, SLOT_OPTIONS, SUB_KEYS

# Game fight-property ids as HoYoLAB reports them.
PROPERTY_KEYS: dict[int, str] = {
    2: "hp", 3: "hp%", 5: "atk", 6: "atk%", 8: "def", 9: "def%", 20: "crit_rate", 22: "crit_dmg", 23: "er",
    26: "heal", 28: "em", 30: "phys", 40: "pyro", 41: "electro", 42: "hydro", 43: "dendro", 44: "anemo",
    45: "geo", 46: "cryo",
}
_LISTS = {"sands": "sand_main_property_list", "goblet": "goblet_main_property_list",
          "circlet": "circlet_main_property_list"}


@dataclass(frozen=True)
class StatRecommendation:
    main: dict[str, list[str]]
    subs: list[str]

    def to_json(self) -> dict:
        return {"main": {k: list(v) for k, v in self.main.items()}, "subs": list(self.subs)}


def _keys(values: Any, allowed: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    if not isinstance(values, list):
        return out
    for v in values:
        try:
            key = PROPERTY_KEYS.get(int(v))
        except (TypeError, ValueError):
            continue
        if key in allowed and key not in out:
            out.append(key)
    return out


def parse_recommendation(raw_entry: Any) -> StatRecommendation | None:
    """Never raises. None when the block is missing, malformed or maps to nothing."""
    if not isinstance(raw_entry, dict):
        return None
    block = raw_entry.get("recommend_relic_property")
    props = block.get("recommend_properties") if isinstance(block, dict) else None
    if not isinstance(props, dict):
        return None
    main = {slot: _keys(props.get(_LISTS[slot]), SLOT_OPTIONS[slot]) for slot in MAIN_SLOTS}
    subs = _keys(props.get("sub_property_list"), SUB_KEYS)
    if not subs and not any(main.values()):
        return None
    return StatRecommendation(main=main, subs=subs)


def recommendations_by_raw_id(raw: Any) -> dict[int, StatRecommendation]:
    """HoYoLAB character id -> recommendation, from a raw character/detail response."""
    out: dict[int, StatRecommendation] = {}
    entries = raw.get("list") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return out
    for e in entries:
        if not isinstance(e, dict):
            continue
        base = e.get("base") if isinstance(e.get("base"), dict) else {}
        try:
            cid = int(base.get("id") or 0)
        except (TypeError, ValueError):
            continue
        rec = parse_recommendation(e)
        if cid and rec is not None:
            out[cid] = rec
    return out
