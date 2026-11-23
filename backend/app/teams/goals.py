"""The only place teams change goals. Goals are only ever raised to build, never lowered."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.db.models import CharacterGoal
from app.domain import Targets, resolve_targets
from app.planner.order import apply_goal
from app.timeutil import utcnow


def _stored(row: CharacterGoal) -> Targets | None:
    if row.target_level is None:
        return None
    return Targets(row.target_level, row.target_normal, row.target_skill, row.target_burst,
                   row.target_weapon_level)


def raise_to_build(session: Session, character_ids: Iterable[int], defaults: Targets) -> list[int]:
    """Set goal build for every id whose goal is none/want (no row = none). Returns the ids changed."""
    raised: list[int] = []
    for cid in dict.fromkeys(character_ids):
        row = session.get(CharacterGoal, cid)
        if row is None:
            row = CharacterGoal(character_id=cid, goal="none", updated_at=utcnow())
            session.add(row)
        if row.goal == "build":
            continue
        targets = resolve_targets("build", _stored(row), defaults)
        apply_goal(session, row, "build")
        row.target_level, row.target_normal = targets.level, targets.normal
        row.target_skill, row.target_burst = targets.skill, targets.burst
        row.target_weapon_level = targets.weapon_level
        row.updated_at = utcnow()
        raised.append(cid)
    if raised:
        session.flush()
    return raised
