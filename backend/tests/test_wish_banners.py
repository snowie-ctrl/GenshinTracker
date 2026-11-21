import json

import pytest

from app.db.models import GameBanner, GameMeta, GameWeapon
from app.gamedata.service import gamedata_status, refresh_banners
from app.wishes.banners import (BannerParseError, build_banners, js_to_json, name_slug, parse_banners,
                                slug_index)
from helpers import FIXTURES, seed_game, yatta_transport
import httpx

JS = (FIXTURES / "paimon_banners.js").read_text(encoding="utf-8")
WEAPONS = [(11401, "Favonius Sword", 4), (11509, "Mistsplitter Reforged", 5),
           (14504, "A Thousand Floating Dreams", 5)]


def seed_weapons(sf):
    with sf.begin() as s:
        for wid, name, rarity in WEAPONS:
            s.merge(GameWeapon(id=wid, name=name, icon="x", rarity=rarity, weapon_type="Sword"))


def test_js_to_json_handles_comments_quotes_and_trailing_commas():
    data = json.loads(js_to_json("export const banners = { a: [ { b: \"It's\", c: 'x', d: true, }, ], // c\n };"))
    assert data == {"a": [{"b": "It's", "c": "x", "d": True}]}


def test_js_to_json_rejects_unexpected_syntax():
    with pytest.raises(BannerParseError):
        js_to_json("export const banners = { a: someVariable };")
    with pytest.raises(BannerParseError):
        js_to_json("export const banners = { a: 'unterminated };")


def test_parse_fixture_keys():
    parsed = parse_banners(JS)
    assert set(parsed) == {"beginners", "standard", "characters", "weapons", "chronicled"}
    assert len(parsed["characters"]) == 3                      # the commented-out banner is ignored


def test_name_slug():
    assert name_slug("Wolf's Gravestone") == "wolfs_gravestone"
    assert name_slug("Amos' Bow") == "amos_bow"
    assert name_slug("Raiden Shogun") == "raiden_shogun"


def test_build_banners_maps_slugs_orders_parallel_and_reports_unmapped(session_factory):
    seed_game(session_factory)
    seed_weapons(session_factory)
    with session_factory() as s:
        slugs = slug_index(s)
    banners, unmapped = build_banners(parse_banners(JS), slugs)
    by_name = {(b.pool, b.name, b.order, b.start): b for b in banners}
    furina = by_name[("character", "Tide of Furina", 0, "2024-01-10 06:00:00")]
    nahida = by_name[("character", "Bloom of Nahida", 1, "2024-01-10 06:00:00")]
    assert furina.featured_5 == [10000089] and nahida.featured_5 == [10000073]
    assert furina.featured_4 == [10000032, 10000023] and furina.timezone_dependent
    assert not furina.timezone_dependent_end and nahida.timezone_dependent_end
    later = by_name[("character", "Tide of Furina", 0, "2024-01-30 18:00:00")]
    assert not later.timezone_dependent
    weapon = next(b for b in banners if b.pool == "weapon")
    assert weapon.featured_5 == [11509, 14504] and weapon.featured_4 == [11401]
    assert unmapped == {"xingqiu", "the_flute"}
    assert {b.pool for b in banners} == {"beginner", "standard", "character", "weapon", "chronicled"}
    assert len({b.key for b in banners}) == len(banners)


def test_overrides_map_odd_slugs(session_factory):
    seed_game(session_factory)
    with session_factory() as s:
        slugs = slug_index(s)
    parsed = {"characters": [{"name": "X", "shortName": "X", "start": "2024-01-01 00:00:00",
                              "end": "2024-01-02 00:00:00", "featured": ["hydro_archon"], "featuredRare": []}]}
    banners, unmapped = build_banners(parsed, slugs, overrides={"hydro_archon": "furina"})
    assert banners[0].featured_5 == [10000089] and unmapped == set()


async def test_refresh_banners_stores_rows_and_status(session_factory):
    seed_game(session_factory)
    seed_weapons(session_factory)
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh_banners(session_factory, http, force=True) is True
    with session_factory() as s:
        assert s.query(GameBanner).count() == 7
        status = gamedata_status(s)["banners"]
    assert status["count"] == 7 and status["last_error"] is None
    assert status["unmapped"] == ["the_flute", "xingqiu"]


async def test_refresh_banners_failure_keeps_cache(session_factory):
    seed_game(session_factory)
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_banners(session_factory, http, force=True)

    def broken(request):
        return httpx.Response(200, text="export const banners = { a: nope };")
    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as http:
        assert await refresh_banners(session_factory, http, force=True) is False
    with session_factory() as s:
        assert s.query(GameBanner).count() == 7
        assert gamedata_status(s)["banners"]["last_error"].startswith("BannerParseError")


async def test_refresh_banners_malformed_entry_keeps_cache(session_factory):
    seed_game(session_factory)
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_banners(session_factory, http, force=True)

    def malformed(request):
        return httpx.Response(200, text="export const banners = { characters: [ { name: 'X' } ] };")
    async with httpx.AsyncClient(transport=httpx.MockTransport(malformed)) as http:
        assert await refresh_banners(session_factory, http, force=True) is False
    with session_factory() as s:
        assert s.query(GameBanner).count() == 7
        assert gamedata_status(s)["banners"]["last_error"].startswith("BannerParseError")


async def test_refresh_banners_non_string_slug_keeps_cache(session_factory):
    seed_game(session_factory)
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_banners(session_factory, http, force=True)

    def mixed(request):
        return httpx.Response(200, text="export const banners = { characters: [ { name: 'X', "
                                        "start: 'a', end: 'b', featured: ['nope', 5] } ] };")
    async with httpx.AsyncClient(transport=httpx.MockTransport(mixed)) as http:
        assert await refresh_banners(session_factory, http, force=True) is False
    with session_factory() as s:
        assert s.query(GameBanner).count() == 7
        assert gamedata_status(s)["banners"]["last_error"].startswith("BannerParseError")


def test_partly_mapped_featured_5_list_is_stored_empty():
    parsed = {"weapons": [{"name": "Mix", "shortName": "Mix", "start": "2024-01-01 00:00:00",
                           "end": "2024-01-02 00:00:00", "featured": ["mistsplitter_reforged", "no_such_weapon"],
                           "featuredRare": ["favonius_sword", "no_such_rare"]}]}
    slugs = {"mistsplitter_reforged": 11509, "favonius_sword": 11401}
    banners, unmapped = build_banners(parsed, slugs)
    assert banners[0].featured_5 == []                          # never half a featured list
    assert banners[0].featured_4 == [11401]                     # 4★ lists are not used for outcomes
    assert unmapped == {"no_such_weapon", "no_such_rare"}
