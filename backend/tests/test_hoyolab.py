from datetime import timedelta
from types import SimpleNamespace as NS

import genshin
import pytest

from app.sync.hoyolab import (
    AuthExpired, HoyolabError, RateLimited, call_api,
    to_detail_entry, to_notes, to_roster_entry,
)

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


async def test_call_api_maps_invalid_cookies_and_other_errors():
    async def bad_cookie():
        raise genshin.errors.InvalidCookies({"retcode": -100, "message": "not logged in"})

    async def other():
        raise genshin.errors.GenshinException({"retcode": -1, "message": "boom"})

    with pytest.raises(AuthExpired):
        await call_api(bad_cookie, delays=())
    with pytest.raises(HoyolabError):
        await call_api(other, delays=())
