"""Per-character shortfall (own numbers, with a shared mark) and Dashboard Building cards."""
from __future__ import annotations

from app.gamedata.materials import CATEGORY_LABELS
from app.planner.data import CATEGORY_ORDER, PlannerData, Total


def character_shortfall(data: PlannerData, character_id: int, index: dict[int, dict]) -> list[dict]:
    rows = []
    for mid, (need, short) in data.gaps.get(character_id, {}).items():
        m = index.get(mid)
        if m is None:
            continue
        # Only characters still set to Build count: gap rows can outlive a goal change until the next calculation.
        others = any(cid != character_id and cid in data.characters and mats.get(mid, (0, 0))[0] > 0
                     for cid, mats in data.gaps.items())
        combined = data.totals.get(mid, Total(0, 0, 0)).short
        rows.append({"id": mid, "name": m["name"], "icon": m["icon"], "rarity": m["rarity"],
                     "category": m["category"], "category_label": CATEGORY_LABELS[m["category"]],
                     "need": need, "short": short,
                     "shared": others and combined > short,
                     "_order": (CATEGORY_ORDER.index(m["category"]), m["sort_order"], mid)})
    rows.sort(key=lambda r: r["_order"])
    for r in rows:
        del r["_order"]
    return rows


def building_cards(data: PlannerData, progress: dict[int, float | None], index: dict[int, dict]) -> list[dict]:
    cards = []
    for cid, ref in data.characters.items():
        materials = [r for r in character_shortfall(data, cid, index) if r["short"] > 0]
        cards.append({"character": ref.to_dict(), "progress": progress.get(cid),
                      "materials": materials, "skipped": False,
                      "calculated": cid in data.calculated})
    return sorted(cards, key=lambda c: (c["progress"] if c["progress"] is not None else -1, c["character"]["name"]))
