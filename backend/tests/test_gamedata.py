from datetime import datetime, timedelta

import httpx

from app.db.models import GameCharacter
from app.gamedata.service import gamedata_status, needs_refresh, refresh
from app.gamedata.yatta import canonical_id, parse_avatar_list, splash_for
from helpers import load_fixture, yatta_transport

NOW = datetime(2026, 11, 19, 12, 0, 0)


def test_canonical_id():
    assert canonical_id("10000005-anemo") == 10000005
    assert canonical_id(10000007) == 10000005
    assert canonical_id(10000118) == 10000117
    assert canonical_id(10000032) == 10000032


def test_parse_collapses_variants_and_maps_names():
    chars = {c.id: c for c in parse_avatar_list(load_fixture("yatta_avatar.json"))}
    assert set(chars) == {10000032, 10000089, 10000052, 10000005, 10000117, 10000999}
    trav = chars[10000005]
    assert (trav.name, trav.slug, trav.element, trav.icon) == ("Traveler", "traveler", None, "UI_AvatarIcon_PlayerBoy")
    assert trav.release_at == datetime(2020, 9, 27, 22, 0)  # earliest variant
    assert chars[10000117].name == "Manekin"
    raiden = chars[10000052]
    assert (raiden.element, raiden.weapon_type, raiden.slug) == ("Electro", "Polearm", "raiden-shogun")
    assert raiden.splash == "UI_Gacha_AvatarImg_Shougun"


def test_splash_for():
    assert splash_for("UI_AvatarIcon_Bennett") == "UI_Gacha_AvatarImg_Bennett"


async def test_refresh_stores_rows_and_meta(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh(session_factory, http, now=NOW) is True
    with session_factory() as s:
        assert s.get(GameCharacter, 10000032).element == "Pyro"
        status = gamedata_status(s)
        assert status == {"fetched_at": "2026-11-19T12:00:00Z", "last_error": None, "count": 6}


async def test_refresh_skipped_when_fresh_and_forced_when_asked(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh(session_factory, http, now=NOW)
        assert await refresh(session_factory, http, now=NOW + timedelta(days=1)) is False
        assert await refresh(session_factory, http, now=NOW + timedelta(days=1), force=True) is True


def test_needs_refresh_after_seven_days(session_factory):
    with session_factory() as s:
        assert needs_refresh(s, NOW) is True


async def test_refresh_failure_keeps_old_rows_and_records_error(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh(session_factory, http, now=NOW)
    async with httpx.AsyncClient(transport=yatta_transport(status=503)) as http:
        assert await refresh(session_factory, http, now=NOW, force=True) is False
    with session_factory() as s:
        status = gamedata_status(s)
        assert status["count"] == 6
        assert "503" in status["last_error"]
        assert status["fetched_at"] == "2026-11-19T12:00:00Z"
