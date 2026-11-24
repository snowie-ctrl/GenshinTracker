"""Temporary field census of raw HoYoLAB responses (key names and types only)."""
import asyncio
import json
from types import SimpleNamespace as NS

import genshin

from app.db.models import HoyolabSnapshot
from app.sync import hoyolab
from app.sync.census import field_census
from fakes import FakeSource
from helpers import load_fixture, seed_game
from test_sync_runner import manager

SECRET = "Lumine-Secret-Name"


def test_records_paths_and_types_only():
    raw = {"list": [{"base": {"id": 10000032, "name": SECRET, "rarity": 4.0}, "weapon": None,
                     "flags": [True]}],
           "avatar_wiki": {"10000032": "https://wiki.hoyolab.com/x"}}
    c = field_census(raw)
    assert c["types"]["list[].base.id"] == ["int"]
    assert c["types"]["list[].base.name"] == ["str"]
    assert c["types"]["list[].base.rarity"] == ["float"]
    assert c["types"]["list[].weapon"] == ["null"]
    assert c["types"]["list[].flags[]"] == ["bool"]
    assert c["types"]["avatar_wiki.<n>"] == ["str"]            # numeric keys collapse
    dumped = json.dumps(c)
    assert SECRET not in dumped and "wiki.hoyolab.com" not in dumped and "10000032" not in dumped


def test_merges_types_across_list_items_and_calls():
    c = field_census({"list": [{"a": 1}, {"a": "x"}]})
    field_census({"list": [{"a": None}]}, c)
    assert c["types"]["list[].a"] == ["int", "str", "null"]


def test_keeps_set_flag_counts_and_lineup_host_only():
    raw = {"list": [{"recommend_relic_property": {"has_set_recommend_prop": True}},
                    {"recommend_relic_property": {"has_set_recommend_prop": False}},
                    {"recommend_relic_property": {"has_set_recommend_prop": True}}],
           "lineup_recommend": "https://act.hoyolab.com/lineup?id=123&uid=800000001"}
    c = field_census(raw)
    assert c["kept"]["list[].recommend_relic_property.has_set_recommend_prop"] == {"true": 2, "false": 1}
    assert c["kept"]["lineup_recommend"] == ["str host=act.hoyolab.com"]
    assert "800000001" not in json.dumps(c) and "id=123" not in json.dumps(c)


def test_lineup_non_link_keeps_type_and_length():
    c = field_census({"a": {"lineup_recommend": "abc"}, "b": {"lineup_recommend": {"x": 1}}})
    assert c["kept"]["a.lineup_recommend"] == ["str len=3"]
    assert c["kept"]["b.lineup_recommend"] == ["dict"]


def _source(client):
    src = object.__new__(hoyolab.GenshinPySource)
    src._client, src._uid, src._delays, src._region = client, 800000001, (), "os_euro"
    src.census = {}
    return src


def test_get_details_fills_detail_census(monkeypatch):
    raw = {"list": [{"base": {"id": 10000032},
                     "recommend_relic_property": {"recommend_properties": {}, "has_set_recommend_prop": False}}]}

    class Client:
        async def get_genshin_detailed_characters(self, uid, *, characters, return_raw_data):
            return raw

    weapon = NS(id=1, icon="i", name="W", rarity=4, level=90, refinement=1)
    monkeypatch.setattr(genshin.models, "GenshinDetailCharacters", lambda **d: NS(characters=[
        NS(id=10000032, weapon=weapon, artifacts=[], skills=[], base_properties=[], extra_properties=[])]))
    src = _source(Client())
    asyncio.run(src.get_details([10000032]))
    assert src.census["detail"]["kept"]["list[].recommend_relic_property.has_set_recommend_prop"] == \
        {"true": 0, "false": 1}


def test_compute_gaps_fills_calculator_census():
    raw = load_fixture("calculator_batch.json")

    class Client:
        async def request_calculator(self, path, *, data, api_version):
            return raw

    src = _source(Client())
    try:
        asyncio.run(src.compute_gaps([]))
    except Exception:
        pass                                  # mapping is not under test; the census runs first
    assert src.census["calculator"]["types"]


def test_census_failure_never_breaks_details(monkeypatch):
    monkeypatch.setattr(hoyolab, "field_census", lambda *a, **k: 1 / 0)
    weapon = NS(id=1, icon="i", name="W", rarity=4, level=90, refinement=1)
    monkeypatch.setattr(genshin.models, "GenshinDetailCharacters", lambda **d: NS(characters=[
        NS(id=10000032, weapon=weapon, artifacts=[], skills=[], base_properties=[], extra_properties=[])]))

    class Client:
        async def get_genshin_detailed_characters(self, uid, *, characters, return_raw_data):
            return {"list": []}

    out = asyncio.run(_source(Client()).get_details([10000032]))
    assert out[0].id == 10000032


async def test_runner_saves_census_snapshots(paths, session_factory):
    seed_game(session_factory)
    source = FakeSource()
    source.census = {"detail": {"types": {"list[].x": ["int"]}, "kept": {}}}
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    with session_factory() as s:
        row = s.get(HoyolabSnapshot, "field_census:detail")
        assert row.data == {"types": {"list[].x": ["int"]}, "kept": {}}
        assert s.get(HoyolabSnapshot, "field_census:calculator") is None    # nothing recorded, nothing saved


async def test_runner_without_census_attribute_saves_nothing(paths, session_factory):
    seed_game(session_factory)
    m = manager(paths, session_factory, FakeSource())
    await m.request("manual")
    await m.wait()
    with session_factory() as s:
        assert s.get(HoyolabSnapshot, "field_census:detail") is None
