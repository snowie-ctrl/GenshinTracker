from fastapi import APIRouter, Depends

from app.api.events import last_error
from app.api.planner import is_connected
from app.context import AppContext, get_ctx
from app.db.models import HoyolabSnapshot
from app.profile.view import challenge_views, profile_view, roster_view
from app.settings.store import get_setting
from app.timeutil import iso, utcnow

router = APIRouter()


@router.get("/profile")
def get_profile(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        snap = s.get(HoyolabSnapshot, "profile")
        return {"connected": is_connected(ctx, s), "fetched_at": iso(snap.fetched_at) if snap else None,
                "error": last_error(s, "profile") or last_error(s, "challenges"),
                "profile": profile_view(snap.data if snap else None, str(get_setting(s, "display_name") or "")),
                "roster": roster_view(s),
                "challenges": challenge_views(s, utcnow())}
