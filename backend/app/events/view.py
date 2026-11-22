"""Events page and Dashboard cards: pure functions over the calendar snapshot, Done ticks and banner data."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import EventDone, GameBanner, GameCharacter, GameWeapon, HoyolabSnapshot
from app.servertime import RESET_HOUR, offset_hours, server_day, week_start
from app.timeutil import iso
from app.wishes.pity import BannerWindow, PoolResult
from app.wishes.types import server_local_now

PRIMOGEM_ID = 201
ENDING_SOON = timedelta(hours=24)
PAGE_SIZE = 50
KEEP_DONE = timedelta(days=60)
FALLBACK_DAY = {"abyss": 16, "theater": 1}
LABELS = {"daily": "Daily reset", "weekly": "Weekly reset", "abyss": "Spiral Abyss",
          "theater": "Imaginarium Theater", "stygian": "Stygian Onslaught"}


def parse_iso(s: str | None) -> datetime | None:
    return None if not s else datetime.fromisoformat(s.rstrip("Z"))


def primogems(rewards: list[dict]) -> int:
    return sum(int(r["count"]) for r in rewards if r["id"] == PRIMOGEM_ID or r["name"] == "Primogem")


def event_rows(calendar: dict, done: set[int], now: datetime) -> list[dict]:
    rows = []
    for e in calendar.get("events", []):
        end = parse_iso(e.get("end"))
        if end is not None and end <= now:
            continue
        rows.append({**e, "primogems": primogems(e["rewards"]), "done": e["id"] in done,
                     "ending_soon": end is not None and end - now <= ENDING_SOON})
    far = datetime.max
    rows.sort(key=lambda r: (r["done"], parse_iso(r.get("end")) or far, r["id"]))
    return rows


def events_left(rows: list[dict]) -> dict:
    left = [r for r in rows if not r["done"]]
    return {"count": len(left), "primogems": sum(r["primogems"] for r in left)}


def pulls_by_banner(results: dict[str, PoolResult]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for result in results.values():
        for window in result.banner_at.values():
            if window is not None:
                out.setdefault(window.key, {"pulls": 0, "fives": [], "fours": []})["pulls"] += 1
        for view, bucket in [(v, "fives") for v in result.fives] + [(v, "fours") for v in result.fours]:
            if view.banner_key is not None:
                out.setdefault(view.banner_key, {"pulls": 0, "fives": [], "fours": []})[bucket].append(view.name)
    return out


def _window_for(banner: dict, windows: dict[str, list[BannerWindow]], offset: int) -> BannerWindow | None:
    start = parse_iso(banner.get("start"))
    if start is None:
        return None
    local = server_local_now(start + timedelta(minutes=1), offset)
    fives = {i["id"] for i in banner["items"] if i["rarity"] == 5}
    return next((w for w in windows.get(banner["pool"], [])
                 if w.start <= local <= w.end and (not fives or fives & set(w.featured_5))), None)


def live_banners(calendar: dict, now: datetime, windows: dict[str, list[BannerWindow]],
                 pulls: dict[str, dict], offset: int) -> dict:
    current, upcoming = [], []
    for b in calendar.get("banners", []):
        start, end = parse_iso(b.get("start")), parse_iso(b.get("end"))
        if end is not None and end <= now:
            continue
        window = _window_for(b, windows, offset)
        row = {**b, "pulls": pulls.get(window.key) if window is not None else None}
        (upcoming if start is not None and start > now else current).append(row)
    order = {"character": 0, "weapon": 1, "chronicled": 2}
    current.sort(key=lambda r: (order.get(r["pool"], 9), r["start"] or ""))
    upcoming.sort(key=lambda r: r["start"] or "")
    return {"current": current, "upcoming": upcoming}


def _next_month_day(now: datetime, day: int, offset: int) -> datetime:
    local = now + timedelta(hours=offset)
    year, month = local.year, local.month
    for _ in range(2):
        candidate = datetime(year, month, day, RESET_HOUR)
        if candidate > local:
            return candidate - timedelta(hours=offset)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    raise AssertionError("unreachable")


def resets(calendar: dict | None, now: datetime, region: str | None,
           periods: dict[str, str | None] | None = None) -> list[dict]:
    """`periods` maps a challenge kind to a stored period end (ISO) used when the calendar has no future end."""
    offset = offset_hours(region)
    day = server_day(now, region)
    today_reset = datetime(day.year, day.month, day.day) + timedelta(hours=RESET_HOUR - offset)
    at = {"daily": today_reset + timedelta(days=1), "weekly": week_start(now, region) + timedelta(days=7)}
    calendar_ends = {c["kind"]: parse_iso(c.get("end")) for c in (calendar or {}).get("challenges", [])}
    stored_ends = {k: parse_iso(v) for k, v in (periods or {}).items()}
    for kind in ("abyss", "theater", "stygian"):
        end = calendar_ends.get(kind)
        stored = stored_ends.get(kind)
        if end is not None and end > now:
            at[kind] = end
        elif stored is not None and stored > now:
            at[kind] = stored
        elif kind in FALLBACK_DAY:
            at[kind] = _next_month_day(now, FALLBACK_DAY[kind], offset)
    return [{"key": k, "label": LABELS[k], "at": iso(at[k])} for k in LABELS if k in at]


def _items(session: Session) -> dict[int, dict]:
    out = {w.id: {"id": w.id, "name": w.name, "icon": w.icon, "rarity": w.rarity}
           for w in session.scalars(select(GameWeapon))}
    out.update({c.id: {"id": c.id, "name": c.name, "icon": c.icon, "rarity": c.rarity}
                for c in session.scalars(select(GameCharacter))})
    return out


def banner_history(session: Session, pool: str, q: str, page: int, pulls: dict[str, dict]) -> dict:
    items = _items(session)
    query = select(GameBanner).where(GameBanner.pool == pool)
    text = q.strip().lower()
    if text:
        ids = [i for i, it in items.items() if text in it["name"].lower()]
        matching = [b.key for b in session.scalars(select(GameBanner).where(GameBanner.pool == pool))
                    if set(b.featured_5 or []) & set(ids) or set(b.featured_4 or []) & set(ids)]
        query = query.where(or_(func.lower(GameBanner.name).contains(text, autoescape=True),
                                func.lower(GameBanner.short_name).contains(text, autoescape=True),
                                GameBanner.key.in_(matching)))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    page = max(1, page)
    rows = session.scalars(query.order_by(GameBanner.start.desc(), GameBanner.order)
                           .offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))

    def item(i: int) -> dict:
        return items.get(i, {"id": i, "name": f"Item {i}", "icon": None, "rarity": 0})

    return {"total": total, "page": page, "page_size": PAGE_SIZE, "rows": [
        {"key": b.key, "name": b.name, "short_name": b.short_name, "start": b.start, "end": b.end,
         "featured_5": [item(i) for i in b.featured_5 or []], "featured_4": [item(i) for i in b.featured_4 or []],
         "pulls": pulls.get(b.key)} for b in rows]}


def cleanup_event_done(session: Session, now: datetime) -> int:
    snap = session.get(HoyolabSnapshot, "calendar")
    if snap is None:
        return 0
    current = {e["id"] for e in snap.data.get("events", [])}
    stale = [r.event_id for r in session.scalars(select(EventDone).where(EventDone.done_at < now - KEEP_DONE))
             if r.event_id not in current]
    if stale:
        session.execute(delete(EventDone).where(EventDone.event_id.in_(stale)))
    return len(stale)
