"""Wish analysis per banner filter (Ad Astra sub-project 7).
Pure functions over pity results, Wish rows and an item lookup; only load_items queries."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, GameWeapon
from app.gamedata.kinds import ELEMENTS, WEAPON_TYPES
from app.wishes.pity import PullView
from app.wishes.types import PITY, PityRule

AVERAGE_BAND = 3.0                       # ±3 pulls around the expected value counts as "average"
RATES = {"weapon": (0.007, 0.07)}        # (base 5★ rate, rise per pull from soft pity) — community model
DEFAULT_RATES = (0.006, 0.06)


@dataclass(frozen=True)
class ItemInfo:
    name: str
    icon: str
    rarity: int
    element: str | None          # characters only
    weapon_type: str


def load_items(session: Session) -> dict[int, ItemInfo]:
    items = {w.id: ItemInfo(w.name, w.icon, w.rarity, None, w.weapon_type) for w in session.scalars(select(GameWeapon))}
    items.update({c.id: ItemInfo(c.name, c.icon, c.rarity, c.element, c.weapon_type)
                  for c in session.scalars(select(GameCharacter))})
    return items


def expected_for(rule: PityRule, base: float, step: float) -> float:
    """Expected pull number of the first 5★: Σ n · P(first 5★ at n)."""
    none, total = 1.0, 0.0
    for n in range(1, rule.hard + 1):
        if n == rule.hard:
            rate = 1.0
        elif rule.soft is None or n < rule.soft:
            rate = base
        else:
            rate = min(1.0, base + step * (n - rule.soft + 1))
        total += n * none * rate
        none *= 1 - rate
    return round(total, 1)


def expected_pity(pool: str) -> float:
    base, step = RATES.get(pool, DEFAULT_RATES)
    return expected_for(PITY[pool], base, step)


def luck(fives: list[PullView], judged: list[PullView], expected: float, label: str | None) -> dict:
    avg = round(sum(p.pity for p in fives) / len(fives), 1) if fives else None
    verdict = None
    if avg is not None:
        verdict = ("luckier" if avg < expected - AVERAGE_BAND
                   else "unluckier" if avg > expected + AVERAGE_BAND else "average")
    out = {"avg_pity": avg, "expected": expected, "verdict": verdict,
           "won": None, "lost": None, "rate": None, "judged_label": label}
    if label is not None:
        won = sum(1 for p in judged if p.outcome == "won")
        lost = sum(1 for p in judged if p.outcome == "lost")
        out.update(won=won, lost=lost, rate=round(won / (won + lost), 3) if won + lost else None)
    return out


def spiders(pulls: list[PullView], items: dict[int, ItemInfo]) -> tuple[dict, dict, int]:
    elements = {"five": dict.fromkeys(ELEMENTS, 0), "four": dict.fromkeys(ELEMENTS, 0)}
    weapons = {"five": dict.fromkeys(WEAPON_TYPES, 0), "four": dict.fromkeys(WEAPON_TYPES, 0)}
    unknown = 0
    for p in pulls:
        if p.rarity not in (4, 5):
            continue
        info = items.get(p.item_id) if p.item_id is not None else None
        if info is None:
            unknown += 1
            continue
        tier = "five" if p.rarity == 5 else "four"
        if info.element in elements[tier]:
            elements[tier][info.element] += 1
        if info.weapon_type in weapons[tier]:
            weapons[tier][info.weapon_type] += 1
    return elements, weapons, unknown
