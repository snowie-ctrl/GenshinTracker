"""Build priority: the order the Dashboard allocates materials in (1 = first)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CharacterGoal

BUILD = "build"


def build_order(session: Session) -> list[int]:
    rows = session.scalars(select(CharacterGoal).where(CharacterGoal.goal == BUILD))
    ordered = sorted(rows, key=lambda r: (r.priority is None, r.priority or 0, r.character_id))
    return [r.character_id for r in ordered]


def _next_priority(session: Session) -> int:
    top = session.scalar(select(func.max(CharacterGoal.priority)).where(CharacterGoal.goal == BUILD))
    return (top or 0) + 1


def apply_goal(session: Session, row: CharacterGoal, new_goal: str) -> None:
    """Change a goal. Entering Build goes to the end of the order; leaving Build forgets the place.
    Leaving Build also clears the Artifacts done tick (sub-project 8)."""
    if new_goal == row.goal:
        return
    priority = _next_priority(session) if new_goal == BUILD else None
    row.goal = new_goal
    row.priority = priority
    if new_goal != BUILD:
        row.artifacts_done = False


def set_order(session: Session, order: list[int]) -> None:
    """Number `order` 1..n; Build characters it leaves out follow in their current order."""
    if len(set(order)) != len(order):
        raise ValueError("A character is listed more than once.")
    rows = {r.character_id: r for r in session.scalars(select(CharacterGoal).where(CharacterGoal.goal == BUILD))}
    stale = [cid for cid in order if cid not in rows]
    if stale:
        raise ValueError(f"Characters not set to Build: {', '.join(str(c) for c in stale)}. Reload the Dashboard.")
    listed = set(order)
    rest = [cid for cid in build_order(session) if cid not in listed]
    for n, cid in enumerate([*order, *rest], start=1):
        rows[cid].priority = n
    session.flush()
