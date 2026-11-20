from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.characters import goal_targets
from app.api.planner import gaps_for, planner_view, region
from app.context import AppContext, get_ctx
from app.db.models import CharacterGoal, LiveNotes, OwnedCharacter, WeeklyBossDone
from app.domain import Current, progress
from app.planner.characters import building_cards
from app.planner.today import farm_today, weekly_bosses
from app.servertime import server_weekday, week_start
from app.settings.envfile import connection_status, read_env
from app.settings.store import get_setting
from app.timeutil import iso, utcnow

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
    now, reg = utcnow(), region(ctx)
    with ctx.session_factory() as s:
        owned = {o.character_id: o for o in s.scalars(select(OwnedCharacter))}
        progress_by_id: dict[int, float | None] = {}
        for row in s.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")):
            o, t = owned.get(row.character_id), goal_targets(row)
            progress_by_id[row.character_id] = (
                progress(Current(o.level, o.talent_normal, o.talent_skill, o.talent_burst), t)
                if o is not None and t is not None else None)
        values = [v for v in progress_by_id.values() if v is not None]
        notes = s.get(LiveNotes, 1)
        data, index = planner_view(s)
        done = set(s.scalars(select(WeeklyBossDone.boss).where(WeeklyBossDone.week_start == week_start(now, reg))))
        return {
            "connection": connection_status(read_env(ctx.paths.env_file), get_setting(s, "hoyolab_status")),
            "notes": notes_payload(notes) if notes is not None else None,
            "building": {
                "count": len(values),
                "average_progress": round(sum(values) / len(values), 4) if values else None,
            },
            "farm_today": farm_today(data, server_weekday(now, reg), index),
            "weekly_bosses": {
                "discounts_left": notes.weekly_discounts_left if notes is not None else None,
                "discounts_max": notes.weekly_discounts_max if notes is not None else None,
                "bosses": weekly_bosses(data, done, index),
            },
            "building_cards": building_cards(data, progress_by_id, index),
            "gaps": gaps_for(ctx, s),
        }
