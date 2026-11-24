"""Keeps every announced event and wish in event_log, matched to HoYoLAB calendar events by name."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import EventLog, GameBanner
from app.sync.announcements import Announcement

KEEP = timedelta(days=90)
WISH_MATCH = timedelta(days=1)
_PUNCT = re.compile(r"[^\w\s]")


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.rstrip("Z").replace(" ", "T"))


def normalise(name: str) -> str:
    return " ".join(_PUNCT.sub(" ", name.lower()).split())


def match_calendar(ann: Announcement, events: list[dict]) -> dict | None:
    if ann.kind != "event":
        return None
    a = normalise(ann.name)
    hits = [e for e in events if (c := normalise(e.get("name") or "")) and (c in a or a in c)]
    if not hits:
        return None
    end = _dt(ann.end) or _dt(ann.window_end)
    if end is None:
        return hits[0]
    far = timedelta(days=36500)
    return min(hits, key=lambda e: abs((_dt(e.get("end")) or end + far) - end))


def wish_pool(title: str) -> str:
    t = title.lower()
    if "epitome invocation" in t:
        return "weapon"
    if "chronicled" in t:
        return "chronicled"
    return "character"


def match_banner(pool: str, start: str | None, banners: list[GameBanner]) -> GameBanner | None:
    at = _dt(start)
    if at is None:
        return None
    hits = [b for b in banners if b.pool == pool and abs(_dt(b.start) - at) <= WISH_MATCH]
    return min(hits, key=lambda b: abs(_dt(b.start) - at)) if hits else None


def _upsert(session: Session, key: str, now: datetime, **values) -> None:
    row = session.get(EventLog, key)
    if row is None:
        session.add(EventLog(key=key, first_seen=now, last_seen=now, **values))
    else:
        for k, v in values.items():
            setattr(row, k, v)
        row.last_seen = now


def record(session: Session, anns: list[Announcement], calendar: dict, now: datetime) -> int:
    events = [e for e in calendar.get("events", []) if isinstance(e, dict)]
    matched: set[int] = set()
    written = 0
    for a in anns:
        cal = match_calendar(a, events)
        old = session.get(EventLog, f"ann:{a.ann_id}")
        # Times from the announcement's own tags or a current calendar match win; otherwise keep what is stored,
        # and only then fall back to the display window.
        start = a.start or (cal or {}).get("start") or (old.start if old else None) or a.window_start
        end = a.end or (cal or {}).get("end") or (old.end if old else None) or a.window_end
        if start is None and end is None:
            continue
        if cal is not None:
            matched.add(cal["id"])
            session.execute(delete(EventLog).where(EventLog.key == f"cal:{cal['id']}"))
        kind = f"wish:{wish_pool(a.title)}" if a.kind == "wish" else "event"
        calendar_id = cal["id"] if cal else (old.calendar_id if old else None)
        _upsert(session, f"ann:{a.ann_id}", now, kind=kind, name=a.name, start=start, end=end, image=a.image,
                description=a.description, calendar_id=calendar_id)
        written += 1
    known = {r for (r,) in session.execute(select(EventLog.calendar_id).where(EventLog.calendar_id.is_not(None)))}
    for e in events:
        if e["id"] in matched or e["id"] in known or not e.get("start") or not e.get("end"):
            continue
        _upsert(session, f"cal:{e['id']}", now, kind="event", name=e["name"], start=e["start"], end=e["end"],
                image=None, description=e.get("description") or "", calendar_id=e["id"])
        written += 1
    session.flush()
    cutoff = now - KEEP
    stale = [r.key for r in session.scalars(select(EventLog)) if (end := _dt(r.end)) is not None and end < cutoff]
    if stale:
        session.execute(delete(EventLog).where(EventLog.key.in_(stale)))
    return written
