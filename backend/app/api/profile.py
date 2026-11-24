from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.events import last_error
from app.api.planner import is_connected
from app.context import AppContext, get_ctx
from app.db.models import HoyolabSnapshot
from app.profile.view import challenge_views, profile_view, roster_view
from app.profile.showcase import owned_options, showcase_view, validate_ids
from app.settings.store import get_setting, set_setting
from app.timeutil import iso, utcnow

router = APIRouter()


@router.get("/profile")
def get_profile(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        snap = s.get(HoyolabSnapshot, "profile")
        show = showcase_view(s)
        return {"connected": is_connected(ctx, s), "fetched_at": iso(snap.fetched_at) if snap else None,
                "error": last_error(s, "profile") or last_error(s, "challenges"),
                "profile": profile_view(snap.data if snap else None, str(get_setting(s, "display_name") or "")),
                "roster": roster_view(s),
                "showcase": show["entries"], "showcase_mode": show["mode"], "owned": owned_options(s),
                "challenges": challenge_views(s, utcnow())}


class ShowcaseIn(BaseModel):
    ids: list[int]


@router.put("/profile/showcase")
def put_showcase(body: ShowcaseIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory.begin() as s:
        message = validate_ids(s, body.ids)
        if message is not None:
            raise HTTPException(400, message)
        set_setting(s, "profile_showcase", list(body.ids))
        show = showcase_view(s)
    return {"showcase": show["entries"], "showcase_mode": show["mode"]}
