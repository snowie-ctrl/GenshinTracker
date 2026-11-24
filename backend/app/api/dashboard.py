from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.events import events_payload
from app.api.planner import gaps_for, planner_view, region
from app.api.wishes import pity_lines
from app.context import AppContext, get_ctx
from app.dashboard.artifacts import artifact_domains_view
from app.dashboard.view import banners_with_pity, build_progress, event_list, timers
from app.db.models import LiveNotes, WeeklyBossDone
from app.events.view import ending_within
from app.planner.order import build_order, set_order
from app.planner.priority import build_sections
from app.planner.today import farm_today, weekly_bosses
from app.servertime import offset_hours, server_weekday, week_start
from app.settings.envfile import connection_status, read_env
from app.settings.store import get_setting
from app.timeutil import iso, utcnow
from app.wishes.pity import summarize

router = APIRouter()


def _opt_iso(value):
    return iso(value) if value is not None else None


def notes_payload(n: LiveNotes) -> dict:
    return {
        "resin": n.resin, "resin_max": n.resin_max, "resin_full_at": iso(n.resin_full_at),
        "commissions_done": n.commissions_done, "commissions_max": n.commissions_max,
        "commission_bonus_claimed": n.commission_bonus_claimed,
        "realm_currency": n.realm_currency, "realm_currency_max": n.realm_currency_max,
        "realm_currency_full_at": _opt_iso(n.realm_currency_full_at),
        "expeditions": n.expeditions, "expeditions_max": n.expeditions_max, "fetched_at": iso(n.fetched_at),
    }


def _builds(s) -> tuple[dict, dict[int, int], object, dict]:
    data, index = planner_view(s)
    order = [cid for cid in build_order(s) if cid in data.characters]
    rank = {cid: i for i, cid in enumerate(order)}
    return build_sections(data, order, index, build_progress(s)), rank, data, index


@router.get("/dashboard")
def dashboard(ctx: AppContext = Depends(get_ctx)) -> dict:
    now, reg = utcnow(), region(ctx)
    with ctx.session_factory() as s:
        notes = s.get(LiveNotes, 1)
        results = summarize(s, now, offset_hours(reg))
        ev = events_payload(ctx, s, results)
        sections, rank, data, index = _builds(s)
        done = set(s.scalars(select(WeeklyBossDone.boss).where(WeeklyBossDone.week_start == week_start(now, reg))))
        return {
            "connection": connection_status(read_env(ctx.paths.env_file), get_setting(s, "hoyolab_status")),
            "display_name": str(get_setting(s, "display_name") or ""),
            "notes": notes_payload(notes) if notes is not None else None,
            "timers": timers(notes) if notes is not None else [],
            "ending_soon": ending_within(ev["events"], now),
            "server_weekday": server_weekday(now, reg),
            "domains_by_day": {str(d): farm_today(data, d, index, rank) for d in range(7)},
            "weekly_bosses": {
                "discounts_left": notes.weekly_discounts_left if notes is not None else None,
                "discounts_max": notes.weekly_discounts_max if notes is not None else None,
                "bosses": weekly_bosses(data, done, index, rank),
            },
            "artifact_domains": artifact_domains_view(s),
            **sections,
            "live_banners": banners_with_pity(ev["banners"]["current"], pity_lines(results)),
            "events": event_list(ev["events"], ev["resets"]),
            "calendar_fetched_at": ev["fetched_at"],
            "gaps": gaps_for(ctx, s),
        }


class PriorityIn(BaseModel):
    order: list[int]


@router.put("/priority")
def put_priority(body: PriorityIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory.begin() as s:
        try:
            set_order(s, body.order)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        sections, _rank, _data, _index = _builds(s)
        return sections
