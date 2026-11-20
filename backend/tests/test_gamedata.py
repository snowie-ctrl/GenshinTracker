from datetime import datetime, timedelta

import httpx
from sqlalchemy import select

from app.db.models import GameCharacter, GameDomain, GameMaterial, GameWeapon
from app.gamedata.service import (claim_unknown_ids_refresh, gamedata_status, needs_refresh, refresh,
                                  refresh_all, refresh_materials)
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
        assert status == {"fetched_at": "2026-11-19T12:00:00Z", "last_error": None, "count": 6,
                      "materials": {"fetched_at": None, "last_error": None, "count": 0}}


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


async def test_refresh_materials_stores_catalogue_chains_and_domains(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh_materials(session_factory, http) is True
    with session_factory() as s:
        mats = {m.id: m for m in s.scalars(select(GameMaterial))}
        assert mats[104302].craft_from == 104301 and mats[104303].craft_from == 104302
        assert mats[104301].family == mats[104302].family == mats[104303].family == 104301
        assert mats[113003].sources[0] == {"kind": "weekly_boss", "name": "Stormterror", "days": []}
        assert mats[100055].sources == [{"kind": "region", "name": "Mondstadt", "days": []}]
        assert all(m.detail_fetched for m in mats.values())
        order = sorted(mats.values(), key=lambda m: m.sort_order)
        cats = [m.category for m in order]
        assert cats == sorted(cats, key=["exp", "ascension", "specialty", "talent", "weapon",
                                         "enemy", "weekly", "special"].index)
        assert [m.id for m in order if m.category == "talent"] == [104301, 104302, 104303]
        assert {d.id for d in s.scalars(select(GameDomain))} == {4213, 4313}
        assert s.get(GameWeapon, 11401).weapon_type == "Sword"
        assert gamedata_status(s)["materials"]["count"] == len(mats)


async def test_refresh_materials_is_skipped_when_fresh(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_materials(session_factory, http)
        assert await refresh_materials(session_factory, http) is False


async def test_failed_detail_is_retried_next_time_and_reported(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport(fail_details=frozenset({104302}))) as http:
        assert await refresh_materials(session_factory, http) is True
    with session_factory() as s:
        assert s.get(GameMaterial, 104302).detail_fetched is False
        assert "1 material detail" in gamedata_status(s)["materials"]["last_error"]
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh_materials(session_factory, http) is True   # unfetched detail forces a refresh
    with session_factory() as s:
        assert s.get(GameMaterial, 104302).craft_from == 104301
        assert gamedata_status(s)["materials"]["last_error"] is None


async def test_refresh_materials_failure_keeps_cache(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_materials(session_factory, http)
    async with httpx.AsyncClient(transport=yatta_transport(status=500)) as http:
        assert await refresh_materials(session_factory, http, force=True) is False
    with session_factory() as s:
        assert s.get(GameMaterial, 104302) is not None
        assert gamedata_status(s)["materials"]["last_error"].startswith("HTTPStatusError")


async def test_refresh_all_runs_both(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh_all(session_factory, http) is True
    with session_factory() as s:
        status = gamedata_status(s)
        assert status["count"] > 0 and status["materials"]["count"] > 0


def test_unknown_ids_refresh_is_throttled_per_id_set(session_factory):
    def claim(ids, at):
        with session_factory.begin() as s:
            return claim_unknown_ids_refresh(s, ids, at)

    assert claim({5, 7}, NOW) is True
    assert claim({7, 5}, NOW + timedelta(minutes=30)) is False     # same ids within the hour
    assert claim({5, 7, 9}, NOW + timedelta(minutes=31)) is True   # a different set
    assert claim({5, 7, 9}, NOW + timedelta(minutes=50)) is False
    assert claim({5, 7, 9}, NOW + timedelta(minutes=92)) is True   # an hour later: try again
