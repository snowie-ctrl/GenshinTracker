from datetime import datetime

import pytest

from app.db.models import GameWeapon
from app.wishes.types import (PITY, POOL_BY_GACHA_TYPE, ItemResolver, item_type_of, normalize_time,
                              server_local_now, shift_time, to_utc_seconds)
from helpers import seed_game


def test_pools_and_pity_table():
    assert POOL_BY_GACHA_TYPE == {"100": "beginner", "200": "standard", "301": "character",
                                  "400": "character", "302": "weapon", "500": "chronicled"}
    assert (PITY["character"].hard, PITY["character"].soft, PITY["character"].four) == (90, 74, 10)
    assert (PITY["weapon"].hard, PITY["weapon"].soft) == (80, 63)
    assert PITY["beginner"].hard == 50 and PITY["beginner"].soft is None


def test_normalize_time_accepts_strings_and_datetimes():
    assert normalize_time("2024-03-01 18:02:11") == "2024-03-01 18:02:11"
    assert normalize_time("2024-03-01T18:02:11") == "2024-03-01 18:02:11"
    assert normalize_time(datetime(2024, 3, 1, 18, 2, 11)) == "2024-03-01 18:02:11"
    with pytest.raises(ValueError):
        normalize_time("yesterday")


def test_shift_and_utc_seconds():
    assert shift_time("2024-03-01 02:00:00", 8, -5) == "2024-02-29 13:00:00"
    assert to_utc_seconds("2024-01-01 08:00:00", 8) == 1704067200
    assert server_local_now(datetime(2024, 1, 1, 0, 0, 0), 1) == "2024-01-01 01:00:00"


def test_bad_rows_message_caps_at_50():
    from app.wishes.types import bad_rows_message
    msg = bad_rows_message([f"row {i}: bad time" for i in range(60)])
    assert msg.startswith("Nothing was imported: 60 row(s)")
    assert "row 49: bad time" in msg and "row 50: bad time" not in msg and "(and 10 more)" in msg


def test_item_type_of():
    assert item_type_of("Character") == "character"
    assert item_type_of("weapon") == "weapon"
    with pytest.raises(ValueError):
        item_type_of("角色")


def test_resolver_maps_character_and_weapon_names(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        s.add(GameWeapon(id=11401, name="Favonius Sword", icon="x", rarity=4, weapon_type="Sword"))
    with session_factory() as s:
        r = ItemResolver.from_session(s)
    assert r.resolve("Furina") == 10000089
    assert r.resolve("Favonius Sword") == 11401
    assert r.resolve("Nobody") is None
