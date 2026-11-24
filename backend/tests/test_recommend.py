import asyncio
from types import SimpleNamespace as NS

import genshin

from app.sync import hoyolab
from app.sync.recommend import PROPERTY_KEYS, StatRecommendation, parse_recommendation, recommendations_by_raw_id


def entry(props, cid=10000032):
    return {"base": {"id": cid}, "recommend_relic_property": {
        "recommend_properties": props, "custom_properties": {"sand_main_property_list": [28]},
        "has_set_recommend_prop": False}}


FULL = {"sand_main_property_list": [23, 3], "goblet_main_property_list": [40, 3],
        "circlet_main_property_list": [26, 3], "sub_property_list": [23, 3, 2, 20]}


def test_property_keys_pinned():
    assert PROPERTY_KEYS == {2: "hp", 3: "hp%", 5: "atk", 6: "atk%", 8: "def", 9: "def%", 20: "crit_rate",
                             22: "crit_dmg", 23: "er", 26: "heal", 28: "em", 30: "phys", 40: "pyro",
                             41: "electro", 42: "hydro", 43: "dendro", 44: "anemo", 45: "geo", 46: "cryo"}


def test_parse_full_block():
    r = parse_recommendation(entry(FULL))
    assert r == StatRecommendation(main={"sands": ["er", "hp%"], "goblet": ["pyro", "hp%"], "circlet": ["heal", "hp%"]},
                                   subs=["er", "hp%", "hp", "crit_rate"])
    assert r.to_json() == {"main": {"sands": ["er", "hp%"], "goblet": ["pyro", "hp%"], "circlet": ["heal", "hp%"]},
                           "subs": ["er", "hp%", "hp", "crit_rate"]}


def test_parse_ignores_custom_properties():
    r = parse_recommendation(entry({"sand_main_property_list": [6]}))
    assert r.main["sands"] == ["atk%"]                 # custom 28 (em) never used


def test_parse_missing_or_odd_block_is_none():
    assert parse_recommendation({}) is None
    assert parse_recommendation({"recommend_relic_property": None}) is None
    assert parse_recommendation({"recommend_relic_property": []}) is None
    assert parse_recommendation({"recommend_relic_property": {"recommend_properties": "x"}}) is None
    assert parse_recommendation("nope") is None


def test_parse_drops_unknown_invalid_and_duplicates():
    r = parse_recommendation(entry({
        "sand_main_property_list": [23, 999, 40, 23],   # 999 unknown, pyro not a sands stat, duplicate er
        "goblet_main_property_list": "x",               # not a list -> empty
        "circlet_main_property_list": ["22", None],     # string id accepted, None dropped
        "sub_property_list": [40, 20, 20, 22],          # pyro is not a substat
    }))
    assert r.main == {"sands": ["er"], "goblet": [], "circlet": ["crit_dmg"]}
    assert r.subs == ["crit_rate", "crit_dmg"]


def test_parse_all_empty_is_none():
    assert parse_recommendation(entry({"sand_main_property_list": [999], "sub_property_list": []})) is None


def test_recommendations_by_raw_id():
    raw = {"list": [entry(FULL, 10000032), {"base": {"id": 10000089}}, "junk", {"id": 10000023, **entry(FULL, 0)}]}
    got = recommendations_by_raw_id(raw)
    assert set(got) == {10000032}                      # entry without block skipped; base id 0 ignored
    assert recommendations_by_raw_id(None) == {}
    assert recommendations_by_raw_id({"list": "x"}) == {}


def test_get_details_attaches_recommendation(monkeypatch):
    raw = {"list": [entry(FULL, 10000032)]}
    seen = {}

    class Client:
        async def get_genshin_detailed_characters(self, uid, *, characters, return_raw_data):
            assert return_raw_data is True and list(characters) == [10000032]
            return raw

    def fake_model(**data):
        seen["data"] = data
        weapon = NS(id=1, icon="https://act-webstatic.hoyoverse.com/w.png", name="W", rarity=4, level=90,
                    refinement=1)
        return NS(characters=[NS(id=10000032, weapon=weapon, artifacts=[], skills=[], base_properties=[],
                                 extra_properties=[])])

    monkeypatch.setattr(genshin.models, "GenshinDetailCharacters", fake_model)
    src = object.__new__(hoyolab.GenshinPySource)
    src._client, src._uid, src._delays = Client(), 800000001, ()
    out = asyncio.run(src.get_details([10000032]))
    assert out[0].id == 10000032 and out[0].recommendation.main["sands"] == ["er", "hp%"]
    assert seen["data"] is not raw and seen["data"]["list"] is not raw["list"]   # model got a copy


def test_detail_entry_without_recommendation_defaults_to_none():
    weapon = NS(id=1, icon="i", name="W", rarity=4, level=90, refinement=1)
    c = NS(id=10000032, weapon=weapon, artifacts=[], skills=[], base_properties=[], extra_properties=[])
    assert hoyolab.to_detail_entry(c).recommendation is None
