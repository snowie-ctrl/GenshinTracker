from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.planner import is_connected, region
from app.context import AppContext, get_ctx
from app.db.models import ChallengeRun, EventDone, GameBanner, HoyolabSnapshot, SyncRun
from app.events.view import banner_history, event_rows, events_left, live_banners, pulls_by_banner, resets
from app.servertime import offset_hours
from app.timeutil import iso, utcnow
from app.wishes.pity import banner_windows, summarize

router = APIRouter()


class DoneIn(BaseModel):
    done: bool


def last_error(session: Session, part: str) -> str | None:
    run = session.scalars(select(SyncRun).where(SyncRun.finished_at.is_not(None), SyncRun.trigger != "gaps")
                          .order_by(SyncRun.id.desc()).limit(1)).first()
    p = ((run.parts or {}) if run is not None else {}).get(part) or {}
    return None if p.get("ok", True) else p.get("error")


def challenge_periods(session: Session) -> dict[str, str | None]:
    """Per challenge kind, the latest stored period end."""
    out: dict[str, str | None] = {}
    for kind in ("abyss", "theater", "stygian"):
        end = session.scalars(select(ChallengeRun.end).where(ChallengeRun.kind == kind, ChallengeRun.end.is_not(None))
                              .order_by(ChallengeRun.end.desc()).limit(1)).first()
        if end is not None:
            out[kind] = end
    return out


def events_payload(ctx: AppContext, s: Session) -> dict:
    now, reg = utcnow(), region(ctx)
    snap = s.get(HoyolabSnapshot, "calendar")
    calendar = snap.data if snap is not None else {"banners": [], "events": [], "challenges": []}
    offset = offset_hours(reg)
    pulls = pulls_by_banner(summarize(s, now, offset))
    windows = banner_windows(list(s.scalars(select(GameBanner))), offset)
    done = set(s.scalars(select(EventDone.event_id)))
    rows = event_rows(calendar, done, now)
    return {"connected": is_connected(ctx, s), "fetched_at": iso(snap.fetched_at) if snap else None,
            "error": last_error(s, "calendar"),
            "banners": live_banners(calendar, now, windows, pulls, offset),
            "events": rows, "events_left": events_left(rows),
            "resets": resets(snap.data if snap is not None else None, now, reg, challenge_periods(s))}


@router.get("/events")
def get_events(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        return events_payload(ctx, s)


@router.put("/events/{event_id}/done")
def set_done(event_id: int, body: DoneIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory.begin() as s:
        row = s.get(EventDone, event_id)
        if body.done and row is None:
            s.add(EventDone(event_id=event_id, done_at=utcnow()))
        elif not body.done and row is not None:
            s.delete(row)
    return {"id": event_id, "done": body.done}


@router.get("/banners/history")
def get_banner_history(pool: Literal["character", "weapon", "chronicled"] = "character",
                       q: str = Query("", max_length=100), page: int = Query(1, ge=1),
                       ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        pulls = pulls_by_banner(summarize(s, utcnow(), offset_hours(region(ctx))))
        return banner_history(s, pool, q, page, pulls)
