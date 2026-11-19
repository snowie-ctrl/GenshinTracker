from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.characters import goal_targets
from app.context import AppContext, get_ctx
from app.db.models import CharacterGoal, LiveNotes, OwnedCharacter
from app.domain import Current, progress
from app.settings.envfile import connection_status, read_env
from app.settings.store import get_setting
from app.timeutil import iso

router = APIRouter()


def notes_payload(n: LiveNotes) -> dict:
    return {
        "resin": n.resin, "resin_max": n.resin_max, "resin_full_at": iso(n.resin_full_at),
        "commissions_done": n.commissions_done, "commissions_max": n.commissions_max,
        "realm_currency": n.realm_currency, "realm_currency_max": n.realm_currency_max,
        "expeditions": n.expeditions, "fetched_at": iso(n.fetched_at),
    }


@router.get("/dashboard")
def dashboard(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        owned = {o.character_id: o for o in s.scalars(select(OwnedCharacter))}
        values = []
        for row in s.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")):
            o, t = owned.get(row.character_id), goal_targets(row)
            if o is not None and t is not None:
                values.append(progress(Current(o.level, o.talent_normal, o.talent_skill, o.talent_burst), t))
        notes = s.get(LiveNotes, 1)
        return {
            "connection": connection_status(read_env(ctx.paths.env_file), get_setting(s, "hoyolab_status")),
            "notes": notes_payload(notes) if notes is not None else None,
            "building": {
                "count": len(values),
                "average_progress": round(sum(values) / len(values), 4) if values else None,
            },
        }
