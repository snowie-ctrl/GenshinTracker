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
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert await check(http, MAPS["hoyolab"][1]) is False
        assert await check(http, MAPS["appsample"][1]) is True

    def boom(request):
        raise httpx.ConnectError("down")
    async with httpx.AsyncClient(transport=httpx.MockTransport(boom)) as http:
        assert await check(http, MAPS["appsample"][1]) is None


async def test_map_status_offline_and_failure(session_factory):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        raise httpx.ConnectError("down")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        offline = await map_status(session_factory, http, NOW, True, ORIGIN)
        assert [m["allowed"] for m in offline] == [None, None] and calls == []
        first = await map_status(session_factory, http, NOW, False, ORIGIN)
        assert [m["allowed"] for m in first] == [None, None] and len(calls) == 2
        await map_status(session_factory, http, NOW + timedelta(hours=1), False, ORIGIN)
        assert len(calls) == 2                       # cached for 24 h, even after a failure
        await map_status(session_factory, http, NOW + timedelta(hours=25), False, ORIGIN)
        assert len(calls) == 4


async def test_cached_value_used_offline(session_factory):
    with session_factory.begin() as s:
        s.add(GameMeta(key="map_embed_hoyolab", value={"allowed": False, "checked_at": "2026-11-21T11:00:00Z"}))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as http:
        got = {m["key"]: m["allowed"] for m in await map_status(session_factory, http, NOW, True, ORIGIN)}
    assert got == {"hoyolab": False, "appsample": None}
