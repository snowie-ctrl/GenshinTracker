import asyncio
from datetime import timedelta

import httpx

from app.db.models import GameCharacterKit
from app.gamedata.kit import KIT_VERSION, load_kit
from app.timeutil import utcnow
from helpers import kit_transport, make_client, seed_game
from test_api_characters import sf_for


def test_kit_fetches_once_then_serves_cache(paths):
    sf = sf_for(paths)
    seed_game(sf)
    calls: list = []
    with make_client(paths, transport=kit_transport(calls=calls), offline=False) as client:
        first = client.get("/api/characters/furina/kit").json()
        second = client.get("/api/characters/furina/kit").json()
    assert first["state"] == "fresh" and first["kit"]["talents"][1]["name"] == "Salon Solitaire"
    assert second == first and calls == ["10000089"]


def test_kit_stale_cache_is_refetched_and_failure_serves_stale(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with sf.begin() as s:
        s.add(GameCharacterKit(character_id=10000089, data={"talents": [], "passives": [], "constellations": []},
                               fetched_at=utcnow() - timedelta(days=30)))
    with make_client(paths, transport=kit_transport(fail=True), offline=False) as client:
        body = client.get("/api/characters/furina/kit").json()
    assert body == {"state": "stale", "kit": {"talents": [], "passives": [], "constellations": []}}
    with make_client(paths, transport=kit_transport(), offline=False) as client:
        assert client.get("/api/characters/furina/kit").json()["state"] == "fresh"


def test_kit_unavailable_without_cache(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with make_client(paths, transport=kit_transport(fail=True), offline=False) as client:
        assert client.get("/api/characters/furina/kit").json() == {"state": "unavailable", "kit": None}
        assert client.get("/api/characters/nobody/kit").status_code == 404


def test_kit_offline_never_fetches(paths):
    sf = sf_for(paths)
    seed_game(sf)
    calls: list = []
    with make_client(paths, transport=kit_transport(calls=calls)) as client:   # offline=True
        assert client.get("/api/characters/furina/kit").json() == {"state": "unavailable", "kit": None}
    assert calls == []


def test_traveler_kit_uses_body_and_element_key(paths):
    sf = sf_for(paths)
    seed_game(sf)
    calls: list = []
    with make_client(paths, transport=kit_transport(calls=calls), offline=False) as client:
        assert client.get("/api/characters/anemo-traveler/kit").json()["state"] == "fresh"
    assert calls == ["10000007-anemo"]


def test_concurrent_loads_fetch_once(session_factory):
    import httpx
    seed_game(session_factory)
    calls: list = []

    async def run():
        http = httpx.AsyncClient(transport=kit_transport(calls=calls))
        lock = asyncio.Lock()
        a, b = await asyncio.gather(*[load_kit(session_factory, http, 10000089, "10000089", False, lock, utcnow())
                                      for _ in range(2)])
        await http.aclose()
        return a, b

    a, b = asyncio.run(run())
    assert a["state"] == b["state"] == "fresh" and len(calls) == 1


def test_wrong_version_cache_is_refetched(paths):
    sf = sf_for(paths)
    seed_game(sf)
    old = {"talents": [{"name": "Old"}], "passives": [], "constellations": []}
    with sf.begin() as s:
        s.add(GameCharacterKit(character_id=10000089, data=old, fetched_at=utcnow()))     # fresh by date, but no "v"
    calls: list = []
    with make_client(paths, transport=kit_transport(calls=calls), offline=False) as client:
        body = client.get("/api/characters/furina/kit").json()
    assert calls == ["10000089"] and body["state"] == "fresh" and body["kit"]["v"] == KIT_VERSION
    assert body["kit"]["talents"][1]["name"] == "Salon Solitaire"


def test_wrong_version_cache_served_stale_when_fetch_fails(paths):
    sf = sf_for(paths)
    seed_game(sf)
    old = {"talents": [{"name": "Old"}], "passives": [], "constellations": []}
    with sf.begin() as s:
        s.add(GameCharacterKit(character_id=10000089, data=old, fetched_at=utcnow()))
    with make_client(paths, transport=kit_transport(fail=True), offline=False) as client:
        assert client.get("/api/characters/furina/kit").json() == {"state": "stale", "kit": old}


def test_empty_kit_from_yatta_does_not_overwrite_stored(paths):
    sf = sf_for(paths)
    seed_game(sf)
    good = {"v": KIT_VERSION, "talents": [{"name": "Keep"}], "passives": [], "constellations": []}
    with sf.begin() as s:
        s.add(GameCharacterKit(character_id=10000089, data=good, fetched_at=utcnow() - timedelta(days=30)))
    empty = httpx.MockTransport(lambda r: httpx.Response(200, json={"data": {}}))
    with make_client(paths, transport=empty, offline=False) as client:
        assert client.get("/api/characters/furina/kit").json() == {"state": "stale", "kit": good}
    with sf() as s:
        assert s.get(GameCharacterKit, 10000089).data == good


def test_fetch_failure_is_logged_without_secrets(session_factory, caplog):
    seed_game(session_factory)

    async def run():
        http = httpx.AsyncClient(transport=kit_transport(fail=True))
        try:
            return await load_kit(session_factory, http, 10000089, "10000089", False, asyncio.Lock(), utcnow())
        finally:
            await http.aclose()

    with caplog.at_level("WARNING", logger="app.gamedata.kit"):
        assert asyncio.run(run())["state"] == "unavailable"
    assert "HTTPStatusError" in caplog.text and "10000089" in caplog.text
