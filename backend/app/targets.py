"""The one place a character's current values and stored build targets are read and written (sub-project 5)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import CharacterGoal, CharacterStatRecommendation, OwnedCharacter, TravelerElement
from app.domain import Current, Targets, build_defaults
from app.gamedata.traveler import is_traveler
from app.planner.requests import shared_traveler_row
from app.timeutil import iso


def current_for(s: Session, cid: int) -> Current | None:
    o = s.get(OwnedCharacter, cid)
    if o is not None:
        return Current(o.level, o.talent_normal, o.talent_skill, o.talent_burst, constellation=o.constellation or 0,
                       weapon_level=o.weapon_level, refinement=o.weapon_refinement)
    if not is_traveler(cid):
        return None
    te = s.get(TravelerElement, cid)
    shared = shared_traveler_row(s)
    if te is None or not (te.seen or te.unlocked) or shared is None:
        return None
    return Current(shared.level, te.talent_normal, te.talent_skill, te.talent_burst, constellation=te.constellation,
                   weapon_level=shared.weapon_level, refinement=shared.weapon_refinement)


def defaults_for(s: Session, cid: int) -> Targets:
    return build_defaults(current_for(s, cid))


def stored_targets(row: CharacterGoal | None) -> Targets | None:
    if row is None or row.target_level is None:
        return None
    return Targets(row.target_level, row.target_normal, row.target_skill, row.target_burst, row.target_weapon_level,
                   constellation=row.target_constellation, refinement=row.target_refinement)


def write_targets(row: CharacterGoal, t: Targets) -> None:
    """Write targets; a None constellation/refinement keeps what is stored (old clients omit them)."""
    row.target_level, row.target_normal = t.level, t.normal
    row.target_skill, row.target_burst = t.skill, t.burst
    row.target_weapon_level = t.weapon_level
    if t.constellation is not None:
        row.target_constellation = t.constellation
    if t.refinement is not None:
        row.target_refinement = t.refinement


def prefill_artifact_target(s: Session, row: CharacterGoal) -> None:
    """A Build character with no artifact target starts from HoYoLAB's recommendation, when one is stored."""
    if row.goal != "build" or row.artifact_target is not None:
        return
    rec = s.get(CharacterStatRecommendation, row.character_id)
    if rec is None:
        return
    row.artifact_target = {"sets": [], "main": dict(rec.data["main"]), "subs": list(rec.data["subs"])}


def recommendation_payload(s: Session, cid: int) -> dict | None:
    rec = s.get(CharacterStatRecommendation, cid)
    if rec is None:
        return None
    return {"main": rec.data["main"], "subs": rec.data["subs"], "synced_at": iso(rec.synced_at)}
