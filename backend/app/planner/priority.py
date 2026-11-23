"""Allocate held materials to Build characters in priority order (spec sub-project 3, section 5)."""
from __future__ import annotations

from dataclasses import dataclass

from app.gamedata.materials import CATEGORY_LABELS
from app.planner.crafting import chains
from app.planner.data import CATEGORY_ORDER, PlannerData


@dataclass(frozen=True)
class Allocation:
    need: int
    have: int
    craft: int


def held_counts(data: PlannerData) -> dict[int, int]:
    """What the bag holds (need - short + spare), as far as the calculator reports it."""
    return {mid: max(0, t.need - t.short + t.spare) for mid, t in data.totals.items()}


def _lower_tiers(data: PlannerData) -> dict[int, list[int]]:
    """Material id -> the tiers below it in its crafting chain, lowest first."""
    out: dict[int, list[int]] = {}
    for chain in chains(data.materials):
        for i, mid in enumerate(chain):
            out[mid] = chain[:i]
    return out


def _craft_raw(remaining: dict[int, int], lower: list[int], n: int) -> int:
    """Make up to n of the tier above `lower[-1]` from `remaining`, 3 -> 1, recursing down the chain."""
    if not lower or n <= 0:
        return 0
    below = lower[-1]
    want = 3 * n
    direct = min(want, remaining.get(below, 0))
    remaining[below] = remaining.get(below, 0) - direct
    total = direct + _craft_raw(remaining, lower[:-1], want - direct)
    made = total // 3
    remaining[below] += total - made * 3          # unused units (held or just crafted) stay in the bag
    return made


def _craft(remaining: dict[int, int], lower: list[int], n: int) -> int:
    """Transactional craft: dry-run on a copy to learn how many whole units can be made, then consume exactly that."""
    made = _craft_raw(dict(remaining), lower, n)
    return _craft_raw(remaining, lower, made) if made > 0 else 0


def allocate(data: PlannerData, order: list[int]) -> dict[int, dict[int, Allocation]]:
    order = list(dict.fromkeys(order))
    remaining = held_counts(data)
    rows: dict[int, dict[int, list[int]]] = {}
    for cid in order:                               # exact pass
        row: dict[int, list[int]] = {}
        for mid, (need, _short) in data.gaps.get(cid, {}).items():
            if need <= 0:
                continue
            got = min(need, remaining.get(mid, 0))
            remaining[mid] = remaining.get(mid, 0) - got
            row[mid] = [need, got, 0]
        rows[cid] = row
    if not data.lack_includes_crafting:             # craft pass
        lower = _lower_tiers(data)
        for cid in order:
            for mid in sorted(rows[cid], key=lambda m: (data.materials[m].rarity if m in data.materials else 0, m)):
                need, have, _ = rows[cid][mid]
                if have < need and lower.get(mid):
                    rows[cid][mid][2] = _craft(remaining, lower[mid], need - have)
    return {cid: {mid: Allocation(*v) for mid, v in row.items()} for cid, row in rows.items()}


def _material_rows(alloc: dict[int, Allocation], index: dict[int, dict]) -> list[dict]:
    out = []
    for mid, a in alloc.items():
        m = index.get(mid)
        if m is None:
            continue
        out.append({"id": mid, "name": m["name"], "icon": m["icon"], "rarity": m["rarity"],
                    "category": m["category"], "category_label": CATEGORY_LABELS[m["category"]],
                    "need": a.need, "have": a.have, "craft": a.craft,
                    "_order": (CATEGORY_ORDER.index(m["category"]), m["sort_order"], mid)})
    out.sort(key=lambda r: r["_order"])
    for r in out:
        del r["_order"]
    return out


def build_sections(data: PlannerData, order: list[int], index: dict[int, dict],
                   progress: dict[int, float | None]) -> dict:
    order = [cid for cid in dict.fromkeys(order) if cid in data.characters]
    alloc = allocate(data, order)
    builds, completed = [], []
    for cid in order:
        ref = data.characters[cid]
        calculated = cid in data.calculated
        if calculated and not data.gaps.get(cid):
            completed.append(ref.to_dict())
            continue
        materials = _material_rows(alloc[cid], index) if calculated else []
        builds.append({"character": ref.to_dict(), "priority": len(builds) + 1, "progress": progress.get(cid),
                       "calculated": calculated,
                       "ready": calculated and all(a.have + a.craft >= a.need for a in alloc[cid].values()),
                       "materials": materials})
    return {"builds": builds, "completed": completed}
