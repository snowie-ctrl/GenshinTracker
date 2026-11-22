from fastapi import APIRouter, Depends

from app.context import AppContext, get_ctx
from app.mapcheck import map_status
from app.settings.store import get_setting
from app.timeutil import utcnow

router = APIRouter()


@router.get("/map")
async def get_maps(ctx: AppContext = Depends(get_ctx)) -> dict:
    maps = await map_status(ctx.session_factory, ctx.http, utcnow(), ctx.offline, "http://127.0.0.1")
    with ctx.session_factory() as s:
        return {"maps": maps, "default_map": get_setting(s, "default_map")}
