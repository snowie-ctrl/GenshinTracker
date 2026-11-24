from datetime import datetime, timedelta

import httpx
import pytest

from app.db.models import GameArtifactDomain, GameArtifactSet, GameMeta
from app.gamedata.genshindb import base_name, parse_artifact_domains
from app.gamedata.service import META_SETS_FETCHED, gamedata_status, refresh_all, refresh_artifact_domains, refresh_artifact_sets
from helpers import load_fixture, yatta_transport

NOW = datetime(2026, 11, 24, 12, 0)
BY_NAME = {"Gladiator's Finale": 15001, "Noblesse Oblige": 15007, "Bloodstained Chivalry": 15008}


def test_base_name_strips_tier():
    assert base_name("Domain of Blessing: Stone Chamber III") == "Domain of Blessing: Stone Chamber"
    assert base_name("Domain of Blessing: Dance of Steel V") == "Domain of Blessing: Dance of Steel"


def test_parse_groups_tiers_and_maps_top_tier_sets():
    domains, unmatched = parse_artifact_domains(load_fixture("genshindb_domains.json"), BY_NAME)
    assert [d.name for d in domains] == ["Domain of Blessing: Stone Chamber"]
    d = domains[0]
    assert d.id == 5101                                    # lowest tier id
    assert d.entrance == "Clear Pool and Mountain Cavern" and d.region == "Liyue"
    assert d.elements == ["Hydro", "Pyro"]                 # from the highest tier
    assert d.set_ids == [15008, 15007]                     # 5* names, de-duplicated, in reward order
    assert unmatched == ["Thundering Fury", "Thundersoother"]   # Fires of Purification dropped


def test_parse_keeps_domain_with_one_matched_set():
    domains, unmatched = parse_artifact_domains(load_fixture("genshindb_domains.json"),
                                                {"Noblesse Oblige": 15007})
    assert domains[0].set_ids == [15007]
    assert "Bloodstained Chivalry" in unmatched


def test_parse_rejects_non_list():
    with pytest.raises(ValueError):
        parse_artifact_domains({"error": "nope"}, BY_NAME)


async def test_refresh_domains_stores_rows_and_status(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_artifact_sets(session_factory, http, now=NOW)
        assert await refresh_artifact_domains(session_factory, http, now=NOW) is True
        assert await refresh_artifact_domains(session_factory, http, now=NOW + timedelta(days=1)) is False
    with session_factory() as s:
        row = s.get(GameArtifactDomain, 5101)
        assert row.set_ids == [15007] and row.entrance == "Clear Pool and Mountain Cavern"
        status = gamedata_status(s)["artifact_domains"]
        assert status["count"] == 1 and status["last_error"] is None
        assert status["unmatched"] == ["Bloodstained Chivalry", "Thundering Fury", "Thundersoother"]


async def test_refresh_domains_waits_for_sets(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh_artifact_domains(session_factory, http, now=NOW) is False
    with session_factory() as s:
        assert gamedata_status(s)["artifact_domains"] == {
            "fetched_at": None, "last_error": None, "count": 0, "unmatched": []}


async def test_refresh_domains_failure_keeps_rows(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_artifact_sets(session_factory, http, now=NOW)
        await refresh_artifact_domains(session_factory, http, now=NOW)
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>oops</html>")
    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as http:
        assert await refresh_artifact_domains(session_factory, http, now=NOW, force=True) is False
    with session_factory() as s:
        status = gamedata_status(s)["artifact_domains"]
        assert status["count"] == 1 and status["last_error"]


async def test_refresh_all_refreshes_domains_after_sets(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_all(session_factory, http, now=NOW)
    with session_factory() as s:
        assert s.get(GameArtifactSet, 15007) is not None
        assert s.get(GameArtifactDomain, 5101) is not None


async def test_refresh_domains_empty_result_keeps_rows(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_artifact_sets(session_factory, http, now=NOW)
        await refresh_artifact_domains(session_factory, http, now=NOW)
    with session_factory() as s:
        before = gamedata_status(s)["artifact_domains"]["fetched_at"]
    empty = httpx.MockTransport(lambda request: httpx.Response(200, json=[]))
    async with httpx.AsyncClient(transport=empty) as http:
        assert await refresh_artifact_domains(session_factory, http, now=NOW + timedelta(days=1), force=True) is False
    with session_factory() as s:
        status = gamedata_status(s)["artifact_domains"]
        assert status["count"] == 1 and status["last_error"]
        assert status["fetched_at"] == before


async def test_refresh_all_forces_domains_when_sets_refresh(session_factory):
    later = NOW + timedelta(days=1)
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_all(session_factory, http, now=NOW)
        with session_factory.begin() as s:   # make only the sets stale
            s.merge(GameMeta(key=META_SETS_FETCHED, value="2026-01-01T00:00:00Z"))
        assert await refresh_all(session_factory, http, now=later) is True
    with session_factory() as s:
        assert gamedata_status(s)["artifact_domains"]["fetched_at"] == "2026-11-25T12:00:00Z"
