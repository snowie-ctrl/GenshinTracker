"""Wish analysis per banner filter (Ad Astra sub-project 7).
Pure functions over pity results, Wish rows and an item lookup; only load_items queries."""
from __future__ import annotations

from bisect import bisect_right
from collections import Counter
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, GameWeapon, Wish
from app.gamedata.kinds import ELEMENTS, WEAPON_TYPES
from app.wishes.pity import BannerWindow, PoolResult, PullView
from app.wishes.stats import PRIMOGEMS_PER_PULL, monthly, pity_histogram
from app.wishes.types import PITY, POOLS, PityRule

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


FILTER_POOLS = ("character", "weapon", "chronicled", "standard")
JUDGED = {"character": "50/50", "weapon": "75/25"}


@dataclass(frozen=True)
class Phase:
    label: str          # e.g. "7.1 ph2"
    version: str
    start: str          # server-local "YYYY-MM-DD HH:MM:SS" (already shifted by banner_windows)


def load_phases(windows: list[BannerWindow]) -> list[Phase]:
    """Banner phases from the character windows: one per (version, start day), earliest start wins."""
    starts: dict[tuple[str, str], str] = {}
    for w in windows:
        if w.pool != "character" or not w.version:
            continue
        key = (w.version, w.start[:10])
        starts[key] = min(starts.get(key, w.start), w.start)
    count: Counter = Counter()
    out = []
    for (version, _day), start in sorted(starts.items(), key=lambda kv: kv[1]):
        count[version] += 1
        out.append(Phase(f"{version} ph{count[version]}", version, start))
    return out


def _icon(items: dict[int, ItemInfo], item_id: int | None) -> str | None:
    info = items.get(item_id) if item_id is not None else None
    return info.icon if info else None


def rotations(rows: list[Wish], phases: list[Phase], items: dict[int, ItemInfo]) -> list[dict]:
    """Pulls per phase. A pull belongs to the last phase that started at or before it; earlier pulls are left out."""
    starts = [p.start for p in phases]
    out: dict[int, dict] = {}
    for w in rows:
        i = bisect_right(starts, w.time) - 1
        if i < 0:
            continue
        e = out.setdefault(i, {"label": phases[i].label, "version": phases[i].version, "start": phases[i].start,
                               "pool_counts": Counter(), "pulls": 0, "fives": []})
        e["pool_counts"][w.pool] += 1
        e["pulls"] += 1
        if w.rarity == 5:
            e["fives"].append({"name": w.name, "icon": _icon(items, w.item_id)})
    return [{**e, "pool_counts": dict(e["pool_counts"])} for _i, e in sorted(out.items())]


def primogem_series(rows: list[Wish], items: dict[int, ItemInfo]) -> dict:
    points: list[dict] = []
    fives: list[dict] = []
    total = 0
    for w in rows:
        total += PRIMOGEMS_PER_PULL
        day = w.time[:10]
        if points and points[-1]["date"] == day:
            points[-1]["total"] = total
        else:
            points.append({"date": day, "total": total})
        if w.rarity == 5:
            fives.append({"date": day, "name": w.name, "icon": _icon(items, w.item_id), "total": total})
    return {"points": points, "fives": fives}


def _pull(p: PullView, pool: str, items: dict[int, ItemInfo]) -> dict:
    return {"name": p.name, "item_id": p.item_id, "icon": _icon(items, p.item_id), "item_type": p.item_type,
            "rarity": p.rarity, "time": p.time, "pity": p.pity, "outcome": p.outcome, "banner": p.banner,
            "pool": pool}


def _expected(pools: list[str], results: dict[str, PoolResult]) -> float:
    if len(pools) == 1:
        return expected_pity(pools[0])
    weights = {p: results[p].total for p in pools if results[p].total}
    total = sum(weights.values())
    return round(sum(expected_pity(p) * n for p, n in weights.items()) / total, 1) if total else expected_pity("character")


def _block(pools: list[str], results: dict[str, PoolResult], rows: list[Wish], phases: list[Phase],
           items: dict[int, ItemInfo]) -> dict:
    sub = [w for w in rows if w.pool in pools]
    fives = sorted(((p, pool) for pool in pools for p in results[pool].fives), key=lambda t: t[0].time, reverse=True)
    fours = sorted(((p, pool) for pool in pools for p in results[pool].fours), key=lambda t: t[0].time, reverse=True)
    judged = [p for pool in pools if pool in JUDGED for p in results[pool].fives]
    label = " + ".join(JUDGED[p] for p in ("character", "weapon") if p in pools) or None
    elements, weapon_types, unknown = spiders([p for p, _ in fives + fours], items)
    lk = luck([p for p, _ in fives], judged, _expected(pools, results), label)
    return {
        "months": monthly(sub),
        "rotations": rotations(sub, phases, items),
        "elements": elements, "weapon_types": weapon_types, "unknown_items": unknown,
        "pity_hist": {"buckets": pity_histogram({p: results[p] for p in pools}),
                      "soft": PITY[pools[0]].soft if len(pools) == 1 else None, "avg": lk["avg_pity"]},
        "primogems": primogem_series(sub, items),
        "luck": lk,
        "fives": [_pull(p, pool, items) for p, pool in fives],
        "fours": [_pull(p, pool, items) for p, pool in fours],
    }


def analyze(results: dict[str, PoolResult], rows: list[Wish], phases: list[Phase],
            items: dict[int, ItemInfo]) -> dict[str, dict]:
    rows = sorted(rows, key=lambda w: (w.time, w.seq, w.pk))
    present = [p for p in POOLS if p in results and results[p].total]
    if not present:
        return {}
    filters: dict[str, list[str]] = {"all": present}
    filters.update({p: [p] for p in FILTER_POOLS if p in present})
    return {f: _block(pools, results, rows, phases, items) for f, pools in filters.items()}
