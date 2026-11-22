"""Does each map site allow being shown in an iframe? One unauthenticated request per site per day."""
from __future__ import annotations

import asyncio
from collections.abc import Mapping
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import sessionmaker

from app.db.models import GameMeta
from app.timeutil import iso

MAPS: dict[str, tuple[str, str]] = {
    "hoyolab": ("HoYoLAB Interactive Map", "https://act.hoyolab.com/ys/app/interactive-map/index.html"),
    "appsample": ("AppSample", "https://genshin-impact-map.appsample.com/"),
}
CACHE = timedelta(hours=24)
TIMEOUT = 8.0


def frame_allowed(headers: Mapping[str, str], origin: str) -> bool:
    lower = {k.lower(): v for k, v in headers.items()}
    xfo = lower.get("x-frame-options", "").strip().lower()
    if xfo in ("deny", "sameorigin"):
        return False
    for directive in lower.get("content-security-policy", "").split(";"):
        parts = directive.split()
        if parts and parts[0].lower() == "frame-ancestors":
            sources = [p.strip() for p in parts[1:]]
            return "*" in sources or origin in sources
    return True


async def check(url: str, origin: str = "http://127.0.0.1",
                transport: httpx.AsyncBaseTransport | None = None) -> bool | None:
    # Throwaway client: no shared cookie jar, nothing but the public URL is requested. `transport` is for tests.
    try:
        async with httpx.AsyncClient(transport=transport) as http:
            response = await http.get(url, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError:
        return None
    return frame_allowed(response.headers, origin)


async def map_status(session_factory: sessionmaker, now: datetime, offline: bool, origin: str,
                     transport: httpx.AsyncBaseTransport | None = None) -> list[dict]:
    cached: dict[str, dict | None] = {}
    with session_factory() as s:
        for key in MAPS:
            row = s.get(GameMeta, f"map_embed_{key}")
            cached[key] = row.value if row is not None else None
    stale = [key for key in MAPS if not offline and not (
        cached[key] is not None
        and now - datetime.fromisoformat(cached[key]["checked_at"].rstrip("Z")) < CACHE)]
    checked = dict(zip(stale, await asyncio.gather(*(check(MAPS[k][1], origin, transport) for k in stale))))
    if checked:
        with session_factory.begin() as s:
            for key, allowed in checked.items():
                s.merge(GameMeta(key=f"map_embed_{key}", value={"allowed": allowed, "checked_at": iso(now)}))
    return [{"key": key, "name": name, "url": url,
             "allowed": checked[key] if key in checked else (cached[key]["allowed"] if cached[key] else None)}
            for key, (name, url) in MAPS.items()]
