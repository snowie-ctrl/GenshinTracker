"""3 of tier k-1 craft into 1 of tier k. Spare lower tiers reduce what is left to farm."""
from __future__ import annotations

from dataclasses import dataclass

from app.planner.data import Material, PlannerData, Total


@dataclass(frozen=True)
class Crafted:
    craftable: int
    to_farm: int


def chains(materials: dict[int, Material]) -> list[list[int]]:
    up = {m.craft_from: m.id for m in materials.values() if m.craft_from is not None and m.craft_from in materials}
    roots = sorted(mid for mid in up if materials[mid].craft_from not in materials)
    out = []
    for root in roots:
        chain = [root]
        while chain[-1] in up and len(chain) < 10:
            chain.append(up[chain[-1]])
        out.append(chain)
    return out


def rollup(data: PlannerData) -> dict[int, Crafted]:
    """In netted mode HoYoLAB's short already accounts for crafting: keep the hint, farm = short."""
    result = {mid: Crafted(0, t.short) for mid, t in data.totals.items()}
    empty = Total(0, 0, 0)
    for chain in chains(data.materials):
        carry = 0  # spare lower-tier items, already converted to this tier's units
        for mid in chain:
            t = data.totals.get(mid, empty)
            craftable = min(t.short, carry)
            if mid in data.totals:
                to_farm = t.short if data.lack_includes_crafting else t.short - craftable
                result[mid] = Crafted(craftable, to_farm)
            carry = (t.spare + carry - craftable) // 3
    return result
