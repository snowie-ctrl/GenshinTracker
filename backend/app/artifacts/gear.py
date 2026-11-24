"""Database lookups for the artifact check: equipped gear (Traveler elements share it) and set names."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.artifacts.check import check
from app.db.models import GameArtifactSet, OwnedArtifact
from app.gamedata.traveler import TRAVELER_IDS, is_traveler
from app.traveler.store import current_element_id


def equipped_for(s: Session, cid: int) -> list[OwnedArtifact]:
    """A character's equipped pieces. Sync stores gear only for the synced Traveler element, and all
    elements share it in game, so other elements borrow it."""
    ids = [cid]
    if is_traveler(cid):
        cur = current_element_id(s)
        ids += ([cur] if cur else []) + sorted(TRAVELER_IDS)
    for i in dict.fromkeys(ids):
        rows = s.scalars(select(OwnedArtifact).where(OwnedArtifact.character_id == i)
                         .order_by(OwnedArtifact.slot)).all()
        if rows:
            return list(rows)
    return []


def sets_by_id(s: Session) -> dict[int, tuple[str, str | None]]:
    return {a.id: (a.name, a.icon) for a in s.scalars(select(GameArtifactSet))}


def check_for(s: Session, cid: int, target: dict | None) -> dict:
    return check(target, equipped_for(s, cid), sets_by_id(s))
