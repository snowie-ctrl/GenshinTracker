from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.context import AppContext, get_ctx
from app.db.models import GameWeapon, WeeklyBossDone
from app.planner.data import PlannerData, load
from app.planner.inventory import inventory, material_index
from app.planner.status import gap_status
from app.servertime import week_start
from app.settings.envfile import connection_status, read_env
from app.settings.store import get_setting
from app.timeutil import utcnow

router = APIRouter()
KEEP_WEEKS = 8


class BossDoneIn(BaseModel):
    done: bool


def region(ctx: AppContext) -> str | None:
    return read_env(ctx.paths.env_file).get("GENSHIN_REGION")


def is_connected(ctx: AppContext, session: Session) -> bool:
    status = connection_status(read_env(ctx.paths.env_file), get_setting(session, "hoyolab_status"))
    return status["status"] == "connected"


def planner_view(session: Session) -> tuple[PlannerData, dict[int, dict]]:
    data = load(session)
    return data, material_index(data)


def gaps_for(ctx: AppContext, session: Session) -> dict:
    pending = ctx.sync.gaps_pending or ctx.sync.gaps_running
    return gap_status(session, pending=pending, connected=is_connected(ctx, session))


@router.get("/inventory")
def get_inventory(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        data, index = planner_view(s)
        return {"gaps": gaps_for(ctx, s), "categories": inventory(data, index)}


@router.get("/weapons")
def list_weapons(type: str | None = None, ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        q = select(GameWeapon).order_by(GameWeapon.rarity.desc(), GameWeapon.name)
        if type:
            q = q.where(GameWeapon.weapon_type == type)
        return [{"id": w.id, "name": w.name, "icon": w.icon, "rarity": w.rarity, "weapon_type": w.weapon_type}
                for w in s.scalars(q)]


@router.put("/weekly-bosses/{boss}")
def set_boss_done(boss: str, body: BossDoneIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    if not boss or len(boss) > 100:
        raise HTTPException(422, "Bad boss name")
    ws = week_start(utcnow(), region(ctx))
    with ctx.session_factory.begin() as s:
        row = s.get(WeeklyBossDone, (boss, ws))
        if body.done and row is None:
            s.add(WeeklyBossDone(boss=boss, week_start=ws))
        elif not body.done and row is not None:
            s.delete(row)
        s.execute(delete(WeeklyBossDone).where(WeeklyBossDone.week_start < ws - timedelta(weeks=KEEP_WEEKS)))
    return {"name": boss, "done": body.done}
