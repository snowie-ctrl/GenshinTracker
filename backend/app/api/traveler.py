from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.context import AppContext, get_ctx
from app.db.models import TravelerElement
from app.gamedata.traveler import is_traveler
from app.timeutil import utcnow
from app.traveler.store import current_element_id, get_or_create, refresh_owned

router = APIRouter()


class TalentsIn(BaseModel):
    normal: int = Field(ge=1, le=10)
    skill: int = Field(ge=1, le=10)
    burst: int = Field(ge=1, le=10)


class TravelerIn(BaseModel):
    unlocked: bool | None = None
    talents: TalentsIn | None = None
    constellation: int | None = Field(default=None, ge=0, le=6)


def traveler_payload(row: TravelerElement | None, element_id: int, current: int | None) -> dict:
    return {
        "element_id": element_id,
        "current": element_id == current,
        "seen": bool(row and row.seen),
        "unlocked": bool(row and row.unlocked),
        "talents": {"normal": row.talent_normal if row else 1, "skill": row.talent_skill if row else 1,
                    "burst": row.talent_burst if row else 1},
        "constellation": row.constellation if row else 0,
        "source": row.source if row else "manual",
    }


@router.put("/traveler/{element_id}")
async def set_traveler(element_id: int, body: TravelerIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    if not is_traveler(element_id):
        raise HTTPException(404, "Not a Traveler element")
    with ctx.session_factory.begin() as s:
        current = current_element_id(s)
        row = get_or_create(s, element_id)
        if (body.talents is not None or body.constellation is not None) and element_id == current:
            raise HTTPException(409, "Set by HoYoLAB: this is your current element")
        if body.unlocked is False and row.seen:
            raise HTTPException(409, "Seen in sync: always unlocked")
        if body.unlocked is not None:
            row.unlocked = body.unlocked
        if body.talents is not None:
            row.talent_normal, row.talent_skill, row.talent_burst = (
                body.talents.normal, body.talents.skill, body.talents.burst)
            row.source = "manual"
        if body.constellation is not None:
            row.constellation, row.source = body.constellation, "manual"
        row.updated_at = utcnow()
        s.flush()
        refresh_owned(s, utcnow())
        payload = traveler_payload(row, element_id, current)
    ctx.sync.schedule_gaps()
    return payload
