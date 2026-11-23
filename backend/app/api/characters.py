from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.context import AppContext, get_ctx
from app.api.planner import gaps_for, planner_view
from app.api.traveler import traveler_payload
from app.db.models import (CharacterGoal, GameCharacter, GameWeapon, OwnedArtifact, OwnedCharacter,
                           TravelerElement)
from app.domain import Current, Targets, derive_status, progress, resolve_targets
from app.gamedata.traveler import is_traveler
from app.gamedata.yatta import splash_for
from app.planner.characters import character_shortfall
from app.planner.order import apply_goal
from app.schemas import TargetsIn
from app.settings.store import default_targets
from app.teams.store import memberships
from app.timeutil import utcnow
from app.traveler.store import current_element_id

router = APIRouter()


class GoalIn(BaseModel):
    goal: Literal["none", "want", "build"] | None = None
    targets: TargetsIn | None = None
    planned_weapon_id: int | None = None


def goal_targets(row: CharacterGoal | None) -> Targets | None:
    if row is None or row.target_level is None:
        return None
    return Targets(row.target_level, row.target_normal, row.target_skill, row.target_burst,
                   row.target_weapon_level)


def character_payload(g: GameCharacter | None, o: OwnedCharacter | None, goal_row: CharacterGoal | None) -> dict:
    goal = goal_row.goal if goal_row else "none"
    status, prefarming = derive_status(o is not None, goal)
    targets = goal_targets(goal_row)
    cid = g.id if g is not None else o.character_id
    icon = (o.icon if o is not None and o.icon else None) or (g.icon if g is not None else None)
    talents = None
    if o is not None and o.talent_normal is not None:
        talents = {"normal": o.talent_normal, "skill": o.talent_skill, "burst": o.talent_burst}
    prog = None
    if status == "building" and targets is not None:
        prog = progress(Current(o.level, o.talent_normal, o.talent_skill, o.talent_burst), targets)
    return {
        "id": cid,
        "slug": g.slug if g is not None else f"id-{cid}",
        "name": g.name if g is not None else o.name,
        "rarity": g.rarity if g is not None else 0,
        "element": (o.element if o is not None and o.element else None) or (g.element if g is not None else None),
        "weapon_type": g.weapon_type if g is not None else None,
        "release_at": g.release_at.date().isoformat() if g is not None and g.release_at else None,
        "icon": icon,
        "splash": splash_for(icon) if icon else None,
        "owned": o is not None,
        "level": o.level if o else None,
        "constellation": o.constellation if o else None,
        "friendship": o.friendship if o else None,
        "talents": talents,
        "weapon": None if o is None else {
            "name": o.weapon_name, "icon": o.weapon_icon, "rarity": o.weapon_rarity,
            "level": o.weapon_level, "refinement": o.weapon_refinement,
        },
        "goal": goal,
        "targets": targets.to_dict() if targets else None,
        "status": status,
        "prefarming": prefarming,
        "progress": prog,
        "planned_weapon_id": goal_row.planned_weapon_id if goal_row else None,
    }


def planned_weapon(s: Session, row: CharacterGoal | None, o: OwnedCharacter | None) -> dict | None:
    if row is not None and row.planned_weapon_id is not None:
        w = s.get(GameWeapon, row.planned_weapon_id)
        if w is not None:
            return {"id": w.id, "name": w.name, "icon": w.icon, "rarity": w.rarity,
                    "equipped": o is not None and o.weapon_id == w.id}
    if o is not None and o.weapon_id:
        return {"id": o.weapon_id, "name": o.weapon_name, "icon": o.weapon_icon, "rarity": o.weapon_rarity,
                "equipped": True}
    return None


def _all(s: Session) -> list[tuple[GameCharacter | None, OwnedCharacter | None, CharacterGoal | None]]:
    games = {g.id: g for g in s.scalars(select(GameCharacter))}
    owned = {o.character_id: o for o in s.scalars(select(OwnedCharacter))}
    goals = {r.character_id: r for r in s.scalars(select(CharacterGoal))}
    now = utcnow()
    ids = [gid for gid, g in games.items() if g.release_at <= now or gid in owned]
    ids += [oid for oid in owned if oid not in games]
    return [(games.get(i), owned.get(i), goals.get(i)) for i in ids]


@router.get("/characters")
def list_characters(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        teams = memberships(s)
        rows = []
        for g, o, r in _all(s):
            p = character_payload(g, o, r)
            p["team_tags"] = [[t["id"] for t in m["tags"]] for m in teams.get(p["id"], [])]
            rows.append(p)
        return rows


@router.get("/characters/{slug}")
def get_character(slug: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        for g, o, r in _all(s):
            payload = character_payload(g, o, r)
            if payload["slug"] != slug:
                continue
            artifacts = [] if o is None else s.scalars(
                select(OwnedArtifact).where(OwnedArtifact.character_id == o.character_id)
                .order_by(OwnedArtifact.slot)).all()
            payload["artifacts"] = [
                {"slot": a.slot, "set_name": a.set_name, "rarity": a.rarity, "level": a.level,
                 "main_stat": a.main_stat, "substats": a.substats, "icon": a.icon}
                for a in artifacts
            ]
            payload["stats"] = o.stats if o is not None else []
            payload["planned_weapon"] = planned_weapon(s, r, o)
            payload["teams"] = memberships(s).get(payload["id"], [])
            if is_traveler(payload["id"]):
                payload["traveler"] = traveler_payload(s.get(TravelerElement, payload["id"]), payload["id"],
                                                       current_element_id(s))
            else:
                payload["traveler"] = None
            if payload["goal"] == "build":
                data, index = planner_view(s)
                payload["shortfall"] = {"gaps": gaps_for(ctx, s),
                                        "materials": character_shortfall(data, payload["id"], index),
                                        "calculated": payload["id"] in data.calculated}
            else:
                payload["shortfall"] = None
            return payload
    raise HTTPException(404, "Unknown character")


@router.put("/characters/{character_id}/goal")
async def set_goal(character_id: int, body: GoalIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory.begin() as s:
        g = s.get(GameCharacter, character_id)
        o = s.get(OwnedCharacter, character_id)
        if g is None and o is None:
            raise HTTPException(404, "Unknown character")
        row = s.get(CharacterGoal, character_id)
        if row is None:
            row = CharacterGoal(character_id=character_id, goal="none", updated_at=utcnow())
            s.add(row)

        def state() -> tuple:
            return (row.goal, row.target_level, row.target_normal, row.target_skill, row.target_burst,
                    row.target_weapon_level, row.planned_weapon_id)

        before = state()
        new_goal = body.goal or row.goal
        if body.targets is not None:
            targets = Targets(**body.targets.model_dump())
        else:
            targets = resolve_targets(new_goal, goal_targets(row), default_targets(s))
        apply_goal(s, row, new_goal)
        if targets is not None:
            row.target_level, row.target_normal = targets.level, targets.normal
            row.target_skill, row.target_burst = targets.skill, targets.burst
            row.target_weapon_level = targets.weapon_level
        if "planned_weapon_id" in body.model_fields_set:
            wid = body.planned_weapon_id
            if wid is not None:
                w = s.get(GameWeapon, wid)
                if w is None or (g is not None and w.weapon_type != g.weapon_type):
                    raise HTTPException(400, "That weapon does not fit this character.")
            row.planned_weapon_id = wid
        changed = state() != before
        row.updated_at = utcnow()
        s.flush()
        payload = character_payload(g, o, row)
    if changed:
        ctx.sync.schedule_gaps()
    return payload
