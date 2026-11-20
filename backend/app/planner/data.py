"""One read of everything the planner needs. All other planner modules are pure functions over this."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import LACK_INCLUDES_CRAFTING
from app.db.models import (
    CharacterGoal, GameCharacter, GameDomain, GameMaterial, GapRun, MaterialGap, MaterialTotal, OwnedCharacter,
)
from app.gamedata.materials import CATEGORIES
from app.planner.requests import snapshot

CATEGORY_ORDER: tuple[str, ...] = (*CATEGORIES, "other")
OTHER_ORDER = 10**6


@dataclass(frozen=True)
class Material:
    id: int
    name: str
    icon: str
    rarity: int
    category: str
    craft_from: int | None
    sources: list = field(default_factory=list)
    sort_order: int = 0


@dataclass(frozen=True)
class Total:
    need: int
    short: int
    spare: int


@dataclass(frozen=True)
class CharRef:
    id: int
    name: str
    slug: str
    icon: str | None

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "slug": self.slug, "icon": self.icon}


@dataclass(frozen=True)
class Domain:
    id: int
    name: str
    kind: str
    city: int | None
    weekdays: list
    material_ids: list


@dataclass
class PlannerData:
    materials: dict[int, Material]
    totals: dict[int, Total]
    gaps: dict[int, dict[int, tuple[int, int]]]
    characters: dict[int, CharRef]
    domains: list[Domain]
    lack_includes_crafting: bool = False
    # Build characters whose goal is unchanged since the last successful calculation. Having no
    # gap rows means "fully built" only for these; the others are simply not calculated yet.
    calculated: frozenset[int] = frozenset()


def calculated_ids(stored: list | None, current: list) -> frozenset[int]:
    """Ids whose current snapshot row equals the row in the last successful gap run's snapshot."""
    before = {row[0]: list(row) for row in stored or []}
    return frozenset(row[0] for row in current if before.get(row[0]) == list(row))


def load(session: Session) -> PlannerData:
    materials = {m.id: Material(m.id, m.name, m.icon, m.rarity, m.category, m.craft_from, list(m.sources or []),
                                m.sort_order) for m in session.scalars(select(GameMaterial))}
    totals: dict[int, Total] = {}
    for t in session.scalars(select(MaterialTotal)):
        totals[t.material_id] = Total(t.need, t.short, t.spare)
        if t.material_id not in materials:
            materials[t.material_id] = Material(t.material_id, t.name or f"Material {t.material_id}", t.icon,
                                                t.rarity, "other", None, [], OTHER_ORDER + t.material_id)
    gaps: dict[int, dict[int, tuple[int, int]]] = {}
    for g in session.scalars(select(MaterialGap)):
        gaps.setdefault(g.character_id, {})[g.material_id] = (g.need, g.short)
        if g.material_id not in materials:
            materials[g.material_id] = Material(g.material_id, f"Material {g.material_id}", "", 0, "other", None,
                                                [], OTHER_ORDER + g.material_id)
    characters: dict[int, CharRef] = {}
    for row in session.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")):
        g = session.get(GameCharacter, row.character_id)
        o = session.get(OwnedCharacter, row.character_id)
        if g is None and o is None:
            continue
        icon = (o.icon if o is not None and o.icon else None) or (g.icon if g is not None else None)
        characters[row.character_id] = CharRef(row.character_id, g.name if g is not None else o.name,
                                               g.slug if g is not None else f"id-{row.character_id}", icon)
    domains = [Domain(d.id, d.name, d.kind, d.city, list(d.weekdays), list(d.material_ids))
               for d in session.scalars(select(GameDomain).order_by(GameDomain.id))]
    run = session.get(GapRun, 1)
    calculated = calculated_ids(run.snapshot if run is not None else None, snapshot(session))
    return PlannerData(materials, totals, gaps, characters, domains, LACK_INCLUDES_CRAFTING, calculated)
