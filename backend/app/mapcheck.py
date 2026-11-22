"""Does each map site allow being shown in an iframe? One unauthenticated request per site per day."""
from __future__ import annotations

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


async def check(http: httpx.AsyncClient, url: str, origin: str = "http://127.0.0.1") -> bool | None:
    try:
        response = await http.get(url, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError:
        return None
    return frame_allowed(response.headers, origin)


async def map_status(session_factory: sessionmaker, http: httpx.AsyncClient, now: datetime, offline: bool,
                     origin: str) -> list[dict]:
    out = []
    for key, (name, url) in MAPS.items():
        meta_key = f"map_embed_{key}"
        with session_factory() as s:
            row = s.get(GameMeta, meta_key)
            cached = row.value if row is not None else None
        fresh = cached is not None and now - datetime.fromisoformat(cached["checked_at"].rstrip("Z")) < CACHE
        if fresh or offline:
            allowed = cached["allowed"] if cached is not None else None
        else:
            allowed = await check(http, url, origin)
            with session_factory.begin() as s:
                s.merge(GameMeta(key=meta_key, value={"allowed": allowed, "checked_at": iso(now)}))
        out.append({"key": key, "name": name, "url": url, "allowed": allowed})
    return out
