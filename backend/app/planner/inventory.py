"""Material rows for the Inventory grid and every other planner view."""
from __future__ import annotations

from app.gamedata.materials import CATEGORY_LABELS
from app.planner.crafting import Crafted, rollup
from app.planner.data import CATEGORY_ORDER, PlannerData, Total


def needers(data: PlannerData, material_id: int) -> list[dict]:
    out = []
    for cid, mats in data.gaps.items():
        need = mats.get(material_id, (0, 0))[0]
        ref = data.characters.get(cid)
        if need > 0 and ref is not None:
            out.append({**ref.to_dict(), "need": need})
    return sorted(out, key=lambda c: c["name"])


def material_index(data: PlannerData) -> dict[int, dict]:
    crafted = rollup(data)
    empty = Total(0, 0, 0)
    index: dict[int, dict] = {}
    for mid, m in data.materials.items():
        t = data.totals.get(mid, empty)
        c = crafted.get(mid, Crafted(0, t.short))
        state = "short" if t.short > 0 else "met" if t.need > 0 else "unneeded"
        index[mid] = {
            "id": mid, "name": m.name, "icon": m.icon, "rarity": m.rarity, "category": m.category,
            "sort_order": m.sort_order, "state": state, "need": t.need, "short": t.short,
            "have": t.need - t.short if t.short > 0 else None,
            "craftable": c.craftable, "to_farm": c.to_farm, "sources": m.sources,
            "characters": needers(data, mid) if t.need > 0 else [],
        }
    return index


def inventory(data: PlannerData, index: dict[int, dict]) -> list[dict]:
    out = []
    for key in CATEGORY_ORDER:
        rows = sorted((r for r in index.values() if r["category"] == key), key=lambda r: (r["sort_order"], r["id"]))
        if rows:
            out.append({"key": key, "label": CATEGORY_LABELS[key], "materials": rows})
    return out
