"""Turn Build goals plus synced account data into calculator requests."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CharacterGoal, GameCharacter, OwnedCharacter
from app.domain import Targets
from app.gamedata.yatta import MANEKIN_ID, TRAVELER_ID
from app.sync.hoyolab import GapCharacter, TalentIds

UNSUPPORTED = {TRAVELER_ID: "Traveler", MANEKIN_ID: "Manekin"}


@dataclass(frozen=True)
class PlanInput:
    character_id: int
    name: str
    level: int
    talents: tuple[int, int, int]
    targets: Targets
    weapon: tuple[int, int] | None


def _build_rows(session: Session) -> list[CharacterGoal]:
    rows = session.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")
                           .order_by(CharacterGoal.character_id))
    return [r for r in rows if r.target_level is not None]


def build_inputs(session: Session) -> tuple[list[PlanInput], list[str]]:
    inputs: list[PlanInput] = []
    skipped: list[str] = []
    for row in _build_rows(session):
        cid = row.character_id
        g = session.get(GameCharacter, cid)
        o = session.get(OwnedCharacter, cid)
        if g is None and o is None:
            continue
        if cid in UNSUPPORTED:
            skipped.append(UNSUPPORTED[cid])
            continue
        targets = Targets(row.target_level, row.target_normal, row.target_skill, row.target_burst,
                          row.target_weapon_level)
        level = o.level if o is not None else 1
        talents = ((o.talent_normal or 1, o.talent_skill or 1, o.talent_burst or 1) if o is not None else (1, 1, 1))
        weapon: tuple[int, int] | None = None
        equipped = o.weapon_id if o is not None else None
        if row.planned_weapon_id is not None and row.planned_weapon_id != equipped:
            weapon = (row.planned_weapon_id, 1)
        elif equipped:
            weapon = (equipped, o.weapon_level)
        inputs.append(PlanInput(cid, g.name if g is not None else o.name, level, talents, targets, weapon))
    return inputs, skipped


def has_work(i: PlanInput) -> bool:
    t = i.targets
    talents_up = any(tgt > cur for cur, tgt in zip(i.talents, (t.normal, t.skill, t.burst)))
    weapon_up = i.weapon is not None and t.weapon_level > i.weapon[1]
    return t.level > i.level or talents_up or weapon_up


def snapshot(session: Session) -> list[list]:
    return [[r.character_id, r.target_level, r.target_normal, r.target_skill, r.target_burst,
             r.target_weapon_level, r.planned_weapon_id] for r in _build_rows(session)]


def gap_requests(inputs: list[PlanInput], talent_ids: dict[int, TalentIds]) -> list[GapCharacter]:
    out: list[GapCharacter] = []
    for i in inputs:
        if not has_work(i):
            continue
        t = i.targets
        talents: tuple[tuple[int, int, int], ...] = ()
        if any(tgt > cur for cur, tgt in zip(i.talents, (t.normal, t.skill, t.burst))):
            ids = talent_ids[i.character_id]
            talents = tuple((gid, cur, tgt) for gid, cur, tgt in
                            zip((ids.normal, ids.skill, ids.burst), i.talents, (t.normal, t.skill, t.burst))
                            if tgt > cur)
        weapon = None
        if i.weapon is not None and t.weapon_level > i.weapon[1]:
            weapon = (i.weapon[0], i.weapon[1], t.weapon_level)
        out.append(GapCharacter(i.character_id, i.level, max(i.level, t.level), talents, weapon))
    return out
