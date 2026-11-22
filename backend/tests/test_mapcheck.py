from datetime import datetime, timedelta

import httpx

from app.db.models import GameMeta
from app.mapcheck import MAPS, check, frame_allowed, map_status

ORIGIN = "http://127.0.0.1:8765"
NOW = datetime(2026, 11, 21, 12, 0, 0)


def test_frame_allowed_headers():
    assert frame_allowed({}, ORIGIN) is True
    assert frame_allowed({"X-Frame-Options": "DENY"}, ORIGIN) is False
    assert frame_allowed({"x-frame-options": "sameorigin"}, ORIGIN) is False
    assert frame_allowed({"Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'"}, ORIGIN) is False
    assert frame_allowed({"Content-Security-Policy": "frame-ancestors 'self' https://a.com"}, ORIGIN) is False
    assert frame_allowed({"Content-Security-Policy": "frame-ancestors *"}, ORIGIN) is True
    assert frame_allowed({"Content-Security-Policy": f"frame-ancestors {ORIGIN}"}, ORIGIN) is True
    assert frame_allowed({"Content-Security-Policy": "default-src 'self'"}, ORIGIN) is True


async def test_check_and_failure():
    def handler(request):
        if "hoyolab" in str(request.url):
            return httpx.Response(200, headers={"X-Frame-Options": "SAMEORIGIN"})
        return httpx.Response(200)
    transport = httpx.MockTransport(handler)
    assert await check(MAPS["hoyolab"][1], transport=transport) is False
    assert await check(MAPS["appsample"][1], transport=transport) is True

    def boom(request):
        raise httpx.ConnectError("down")
    assert await check(MAPS["appsample"][1], transport=httpx.MockTransport(boom)) is None


async def test_map_status_offline_and_failure(session_factory):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        raise httpx.ConnectError("down")
    http = httpx.MockTransport(handler)
    offline = await map_status(session_factory, NOW, True, ORIGIN, http)
    assert [m["allowed"] for m in offline] == [None, None] and calls == []
    first = await map_status(session_factory, NOW, False, ORIGIN, http)
    assert [m["allowed"] for m in first] == [None, None] and len(calls) == 2
    await map_status(session_factory, NOW + timedelta(hours=1), False, ORIGIN, http)
    assert len(calls) == 2                       # cached for 24 h, even after a failure
    await map_status(session_factory, NOW + timedelta(hours=25), False, ORIGIN, http)
    assert len(calls) == 4


async def test_cached_value_used_offline(session_factory):
    with session_factory.begin() as s:
        s.add(GameMeta(key="map_embed_hoyolab", value={"allowed": False, "checked_at": "2026-11-21T11:00:00Z"}))
    http = httpx.MockTransport(lambda r: httpx.Response(200))
    got = {m["key"]: m["allowed"] for m in await map_status(session_factory, NOW, True, ORIGIN, http)}
    assert got == {"hoyolab": False, "appsample": None}


async def test_malformed_cached_checked_at_is_stale(session_factory):
    with session_factory.begin() as s:
        s.add(GameMeta(key="map_embed_hoyolab", value={"allowed": False, "checked_at": "not-a-date"}))
        s.add(GameMeta(key="map_embed_appsample", value={"allowed": False}))
    calls = []

    def handler(request):
        calls.append(str(request.url))
        return httpx.Response(200)
    got = {m["key"]: m["allowed"]
           for m in await map_status(session_factory, NOW, False, ORIGIN, httpx.MockTransport(handler))}
    assert got == {"hoyolab": True, "appsample": True} and len(calls) == 2
