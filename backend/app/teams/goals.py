"""The only place teams change goals: raise to build, or lower build -> none when no Build team still needs it."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CharacterGoal, TeamMember, TeamTag
from app.domain import resolve_targets
from app.planner.order import apply_goal
from app.targets import defaults_for, stored_targets, write_targets
from app.timeutil import utcnow

BUILD_TAG_ID = 1


def raise_to_build(session: Session, character_ids: Iterable[int]) -> list[int]:
    """Set goal build for every id whose goal is none/want (no row = none). Returns the ids changed."""
    raised: list[int] = []
    for cid in dict.fromkeys(character_ids):
        row = session.get(CharacterGoal, cid)
        if row is None:
            row = CharacterGoal(character_id=cid, goal="none", updated_at=utcnow())
            session.add(row)
        if row.goal == "build":
            continue
        targets = resolve_targets("build", stored_targets(row), defaults_for(session, cid))
        apply_goal(session, row, "build")
        write_targets(row, targets)
        row.updated_at = utcnow()
        raised.append(cid)
    if raised:
        session.flush()
    return raised


def _in_other_build_team(session: Session, exclude_team_id: int | None) -> set[int]:
    q = (select(TeamMember.character_id)
         .join(TeamTag, TeamTag.team_id == TeamMember.team_id)
         .where(TeamTag.tag_id == BUILD_TAG_ID))
    if exclude_team_id is not None:
        q = q.where(TeamMember.team_id != exclude_team_id)
    return set(session.scalars(q))


def lower_from_build(session: Session, character_ids: Iterable[int], exclude_team_id: int | None) -> list[int]:
    """Build -> none for ids no other Build team still lists. Targets are kept. Returns the ids changed."""
    ids = list(dict.fromkeys(character_ids))
    if not ids:
        return []
    covered = _in_other_build_team(session, exclude_team_id)
    lowered: list[int] = []
    for cid in ids:
        row = session.get(CharacterGoal, cid)
        if row is None or row.goal != "build" or cid in covered:
            continue
        apply_goal(session, row, "none")
        row.updated_at = utcnow()
        lowered.append(cid)
    if lowered:
        session.flush()
    return lowered
