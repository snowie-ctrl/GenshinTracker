import pytest

from app.gamedata.traveler import (TRAVELER_IDS, TRAVELER_PENDING, body_icon, body_of, calc_element, element_of,
                                   is_traveler, traveler_id, traveler_name)
from app.gamedata.yatta import canonical_id


def test_ids_are_base_times_100_plus_calculator_number():
    assert traveler_id("Pyro") == 1000000501
    assert traveler_id("Anemo") == 1000000502
    assert traveler_id("Cryo") == 1000000507
    assert sorted(TRAVELER_IDS) == list(range(1000000501, 1000000508))
    assert element_of(1000000503) == "Geo" and calc_element(1000000503) == 3
    assert is_traveler(1000000505) and not is_traveler(10000005) and not is_traveler(10000032)


def test_body_helpers():
    assert body_of(10000005) == "boy" and body_of(10000007) == "girl" and body_of(10000032) is None
    assert body_icon("boy") == "UI_AvatarIcon_PlayerBoy" and body_icon("girl") == "UI_AvatarIcon_PlayerGirl"
    assert traveler_name("Hydro") == "Hydro Traveler"


def test_unknown_element_raises():
    with pytest.raises(KeyError):
        traveler_id("Lunar")


def test_canonical_id():
    assert canonical_id(10000007, "Geo") == 1000000503
    assert canonical_id("10000005-anemo", "Anemo") == 1000000502
    assert canonical_id(10000005) == TRAVELER_PENDING          # element not known: resolved later
    assert canonical_id(10000007, "Lunar") == TRAVELER_PENDING  # element Ad Astra doesn't know
    assert canonical_id(10000117) is None and canonical_id(10000118, "Cryo") is None
    assert canonical_id(10000032) == 10000032 and canonical_id(10000032, "Pyro") == 10000032
