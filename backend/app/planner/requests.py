"""Turn Build goals plus synced account data into calculator requests."""
from __future__ import annotations

from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CharacterGoal, GameCharacter, OwnedCharacter
from app.domain import Targets
from app.gamedata.traveler import BODY_IDS, TRAVELER_IDS, calc_element, is_traveler
from app.settings.store import get_setting
from app.sync.hoyolab import GapCharacter, TalentIds
from app.traveler.store import current_element_id


@dataclass(frozen=True)
class PlanInput:
    character_id: int
    name: str
    level: int
    talents: tuple[int, int, int]
    targets: Targets
    weapon: tuple[int, int] | None
    avatar_id: int = 0
    element_attr_id: int | None = None
    weapon_planned: bool = False

    def __post_init__(self):
        if not self.avatar_id:
            object.__setattr__(self, "avatar_id", self.character_id)


def _build_rows(session: Session) -> list[CharacterGoal]:
    rows = session.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")
                           .order_by(CharacterGoal.character_id))
    return [r for r in rows if r.target_level is not None]


def shared_traveler_row(session: Session) -> OwnedCharacter | None:
    """Level and weapon are shared: an element without its own owned row borrows them from one that has."""
    cur = current_element_id(session)
    for cid in ([cur] if cur else []) + sorted(TRAVELER_IDS):
        o = session.get(OwnedCharacter, cid)
        if o is not None:
            return o
    return None


def build_inputs(session: Session) -> tuple[list[PlanInput], list[str]]:
    inputs: list[PlanInput] = []
    body_id = BODY_IDS.get(str(get_setting(session, "traveler_body")), BODY_IDS["girl"])
    for row in _build_rows(session):
        cid = row.character_id
        g = session.get(GameCharacter, cid)
        o = session.get(OwnedCharacter, cid)
        if g is None and o is None:
            continue
        traveler = is_traveler(cid)
        shared = (o or shared_traveler_row(session)) if traveler else o
        targets = Targets(row.target_level, row.target_normal, row.target_skill, row.target_burst,
                          row.target_weapon_level)
        level = shared.level if shared is not None else 1
        talents = ((o.talent_normal or 1, o.talent_skill or 1, o.talent_burst or 1) if o is not None else (1, 1, 1))
        weapon: tuple[int, int] | None = None
        equipped = shared.weapon_id if shared is not None else None
        planned = row.planned_weapon_id is not None and row.planned_weapon_id != equipped
        if planned:
            weapon = (row.planned_weapon_id, 1)
        elif equipped:
            weapon = (equipped, shared.weapon_level)
        inputs.append(PlanInput(cid, g.name if g is not None else o.name, level, talents, targets, weapon,
                                avatar_id=body_id if traveler else cid,
                                element_attr_id=calc_element(cid) if traveler else None,
                                weapon_planned=planned))
    return share_traveler(inputs, current_element_id(session)), []


def share_traveler(inputs: list[PlanInput], current: int | None) -> list[PlanInput]:
    """Level and weapon are shared by all Traveler elements: send them once, with one carrier element."""
    group = [i for i in inputs if is_traveler(i.character_id) and has_work(i)]
    if not group:
        return inputs
    ids = {i.character_id for i in group}
    carrier_id = current if current in ids else min(ids)
    level = max(i.targets.level for i in group)
    weapon_level = max(i.targets.weapon_level for i in group)
    ordered = sorted(group, key=lambda i: (i.character_id != carrier_id, i.character_id))
    weapon = next((i.weapon for i in ordered if i.weapon_planned), None) or next(
        (i.weapon for i in ordered if i.weapon is not None), None)
    out: list[PlanInput] = []
    for i in inputs:
        if i.character_id not in ids:
            out.append(i)
        elif i.character_id == carrier_id:
            out.append(replace(i, targets=replace(i.targets, level=level, weapon_level=weapon_level), weapon=weapon))
        else:
            out.append(replace(i, targets=replace(i.targets, level=i.level), weapon=None))
    return out


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
        out.append(GapCharacter(i.character_id, i.level, max(i.level, t.level), talents, weapon,
                                avatar_id=i.avatar_id if i.avatar_id != i.character_id else None,
                                element_attr_id=i.element_attr_id))
    return out
