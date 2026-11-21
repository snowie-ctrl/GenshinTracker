"""What is still left to farm to finish one team, using the whole bag for it ("team goes first")."""
from __future__ import annotations

from dataclasses import replace

from app.gamedata.materials import CATEGORY_LABELS
from app.planner.crafting import Crafted, rollup
from app.planner.data import CATEGORY_ORDER, PlannerData, Total

EMPTY = Total(0, 0, 0)


def team_totals(data: PlannerData, build_ids: list[int]) -> dict[int, Total]:
    """Per material (team need, team short, team spare). `have` is exact when short overall, else a lower bound."""
    need: dict[int, int] = {}
    for cid in build_ids:
        for mid, (n, _short) in data.gaps.get(cid, {}).items():
            need[mid] = need.get(mid, 0) + n
    out: dict[int, Total] = {}
    for mid in set(data.totals) | set(need):
        t = data.totals.get(mid, EMPTY)
        have = t.need - t.short + t.spare
        team_need = need.get(mid, 0)
        out[mid] = Total(team_need, max(0, team_need - have), max(0, have - team_need))
    return out


def team_shortfall(data: PlannerData, build_ids: list[int], index: dict[int, dict]) -> list[dict]:
    totals = team_totals(data, build_ids)
    crafted = rollup(replace(data, totals=totals))
    members = set(build_ids)
    rows = []
    for mid, t in totals.items():
        m = index.get(mid)
        if t.need <= 0 or m is None:
            continue
        c = crafted.get(mid, Crafted(0, t.short))
        shared = any(cid not in members and mats.get(mid, (0, 0))[0] > 0 for cid, mats in data.gaps.items())
        rows.append({"id": mid, "name": m["name"], "icon": m["icon"], "rarity": m["rarity"],
                     "category": m["category"], "category_label": CATEGORY_LABELS[m["category"]],
                     "need": t.need, "short": t.short, "craftable": c.craftable, "to_farm": c.to_farm,
                     "shared": shared,
                     "_order": (CATEGORY_ORDER.index(m["category"]), m["sort_order"], mid)})
    rows.sort(key=lambda r: r["_order"])
    for r in rows:
        del r["_order"]
    return rows


def team_progress(values: list[float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return round(sum(known) / len(known), 4) if known else None
