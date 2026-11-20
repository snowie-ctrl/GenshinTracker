from datetime import timedelta
from types import SimpleNamespace as NS

import genshin
import pytest

from app.sync.hoyolab import (
    AuthExpired, GapCharacter, HoyolabError, NoInventoryData, RateLimited, build_batch_body, call_api,
    to_detail_entry, to_gap_result, to_notes, to_roster_entry, to_talent_ids,
)
from helpers import load_fixture

WEAPON = NS(id=1, icon="https://act-webstatic.hoyoverse.com/w.png", name="The Flute", rarity=4, level=90, refinement=5)


def prop(name, value):
    return NS(info=NS(name=name), value=value, final=value)


def test_roster_entry_maps_traveler_variant():
    c = NS(id=10000007, name="Traveler", element="Geo", rarity=5, icon="x", level=90,
           friendship=10, constellation=6, weapon=WEAPON)
    e = to_roster_entry(c)
    assert (e.id, e.raw_id, e.element, e.level) == (10000005, 10000007, "Geo", 90)
    assert e.weapon.name == "The Flute" and e.weapon.refinement == 5


def test_detail_entry_talents_skip_passives_and_sprint():
    skills = [
        NS(skill_type=1, level=6),   # normal attack
        NS(skill_type=1, level=9),   # elemental skill
        NS(skill_type=1, level=1),   # alternate sprint (Ayaka/Mona) — ignored
        NS(skill_type=1, level=10),  # burst (always last active skill)
        NS(skill_type=2, level=1),   # passive
    ]
    artifact = NS(pos=1, icon="https://act-webstatic.hoyoverse.com/a.png", rarity=5, level=20,
                  set=NS(name="Noblesse Oblige"), main_stat=prop("HP", "4780"),
                  sub_stats=[prop("CRIT Rate", "3.9%"), prop("ATK", "19")])
    c = NS(id=10000032, weapon=WEAPON, artifacts=[artifact], skills=skills,
           base_properties=[prop("HP", "20000")], extra_properties=[prop("Energy Recharge", "200%")])
    d = to_detail_entry(c)
    assert (d.normal, d.skill, d.burst) == (6, 9, 10)
    assert d.artifacts[0].main_stat == "HP 4780"
    assert d.artifacts[0].substats == ["CRIT Rate 3.9%", "ATK 19"]
    assert d.stats == [{"name": "HP", "value": "20000"}, {"name": "Energy Recharge", "value": "200%"}]


def test_detail_entry_with_too_few_skills_defaults_to_one():
    c = NS(id=1, weapon=WEAPON, artifacts=[], skills=[NS(skill_type=1, level=4)],
           base_properties=[], extra_properties=[])
    d = to_detail_entry(c)
    assert (d.normal, d.skill, d.burst) == (4, 1, 1)


def test_notes_mapping():
    n = NS(current_resin=153, max_resin=200, remaining_resin_recovery_time=timedelta(minutes=376),
           completed_commissions=4, max_commissions=4, current_realm_currency=1460,
           max_realm_currency=2400,
           expeditions=[NS(character_icon="https://act-webstatic.hoyoverse.com/e.png",
                           status="Finished", remaining_time=timedelta(0))])
    notes = to_notes(n)
    assert notes.resin_recovery_seconds == 376 * 60
    assert notes.expeditions[0].finished is True


async def test_call_api_retries_rate_limit_then_succeeds():
    attempts = []

    async def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise genshin.errors.TooManyRequests({"retcode": 10101, "message": "slow down"})
        return "ok"

    assert await call_api(flaky, delays=(0, 0, 0)) == "ok"
    assert len(attempts) == 3


async def test_call_api_gives_up_with_rate_limited():
    async def always():
        raise genshin.errors.VisitsTooFrequently({"retcode": -110, "message": "busy"})

    with pytest.raises(RateLimited):
        await call_api(always, delays=(0, 0))


@pytest.mark.parametrize("error", [__import__("aiohttp").ClientConnectionError("dns"), TimeoutError()])
async def test_call_api_maps_network_errors(error):
    async def offline():
        raise error

    with pytest.raises(HoyolabError, match="Could not reach HoYoLAB"):
        await call_api(offline, delays=())


async def test_call_api_maps_invalid_cookies_and_other_errors():
    async def bad_cookie():
        raise genshin.errors.InvalidCookies({"retcode": -100, "message": "not logged in"})

    async def other():
        raise genshin.errors.GenshinException({"retcode": -1, "message": "boom"})

    with pytest.raises(AuthExpired):
        await call_api(bad_cookie, delays=())
    with pytest.raises(HoyolabError):
        await call_api(other, delays=())


def test_roster_entry_keeps_weapon_id():
    c = NS(id=10000032, name="Bennett", element="Pyro", rarity=4, icon="x", level=80,
           friendship=10, constellation=6, weapon=WEAPON)
    assert to_roster_entry(c).weapon.id == 1


def test_notes_weekly_discounts_optional():
    base = dict(current_resin=10, max_resin=200, remaining_resin_recovery_time=timedelta(minutes=1),
                completed_commissions=4, max_commissions=4, current_realm_currency=0,
                max_realm_currency=2400, expeditions=[])
    assert to_notes(NS(**base)).weekly_discounts_left is None
    notes = to_notes(NS(**base, remaining_resin_discounts=1, max_resin_discounts=3))
    assert (notes.weekly_discounts_left, notes.weekly_discounts_max) == (1, 3)


def test_to_talent_ids_picks_normal_skill_burst():
    items = [
        {"id": 10321, "group_id": 3201, "max_level": 10},   # normal
        {"id": 10322, "group_id": 3202, "max_level": 10},   # skill
        {"id": 10323, "group_id": 3203, "max_level": 10},   # alternate sprint (order 3) - dropped
        {"id": 10329, "group_id": 3209, "max_level": 10},   # burst
        {"id": 3221, "group_id": 3221, "max_level": 1},     # passive
    ]
    ids = to_talent_ids(items)
    assert (ids.normal, ids.skill, ids.burst) == (3201, 3202, 3209)


def test_to_talent_ids_rejects_short_lists():
    with pytest.raises(HoyolabError):
        to_talent_ids([{"id": 1, "group_id": 1, "max_level": 10}])


def test_build_batch_body_includes_uid_region_and_only_given_parts():
    chars = [GapCharacter(10000032, 80, 90, ((3201, 6, 8),), (11401, 90, 90)),
             GapCharacter(10000089, 1, 90, (), None)]
    body = build_batch_body(chars, uid=700000001, region="os_euro")
    assert body["uid"] == 700000001 and body["region"] == "os_euro"
    first, second = body["items"]
    assert first == {"avatar_id": 10000032, "avatar_level_current": 80, "avatar_level_target": 90,
                     "skill_list": [{"id": 3201, "level_current": 6, "level_target": 8}],
                     "weapon": {"id": 11401, "level_current": 90, "level_target": 90}}
    assert "weapon" not in second and second["skill_list"] == []


def test_to_gap_result_maps_per_character_total_and_spare():
    result = to_gap_result(load_fixture("calculator_batch.json"), [10000032, 10000089])
    assert [m.id for m in result.per_character[10000089]] == [104302, 104303, 999001]
    guide = next(m for m in result.total if m.id == 104302)
    assert (guide.need, guide.short, guide.rarity) == (18, 7, 3)
    assert result.spare[0].id == 104301 and result.spare[0].need == 10


def test_to_gap_result_without_user_info_fails():
    raw = load_fixture("calculator_batch.json") | {"has_user_info": False}
    with pytest.raises(NoInventoryData):
        to_gap_result(raw, [10000032, 10000089])


def test_to_gap_result_single_character_without_single_results():
    raw = load_fixture("calculator_batch.json") | {"single_role_result": []}
    result = to_gap_result(raw, [10000032])
    assert result.per_character[10000032] == result.total


def test_to_gap_result_count_mismatch_fails():
    with pytest.raises(HoyolabError):
        to_gap_result(load_fixture("calculator_batch.json"), [1, 2, 3])
