import pytest

from app.good.keys import good_key


@pytest.mark.parametrize("name, key", [
    ("Shivada Jade Gemstone", "ShivadaJadeGemstone"),
    ("Wolf's Gravestone", "WolfsGravestone"),
    ("Dvalin's Plume", "DvalinsPlume"),
    ("Thrilling Tales of Dragon Slayers", "ThrillingTalesOfDragonSlayers"),
    ("Key of Khaj-Nisut", "KeyOfKhajNisut"),
    ('Philosophies of "Freedom"', "PhilosophiesOfFreedom"),
    ("Mora", "Mora"),
    ("Déjà vu", "DejaVu"),
    ("Kagotsurube Isshin", "KagotsurubeIsshin"),
    ("Amos' Bow", "AmosBow"),
    ("  The  Catch ", "TheCatch"),
    ("", ""),
])
def test_good_key(name, key):
    assert good_key(name) == key


def test_traveler_keys_per_element_and_bare_traveler_uses_current(session_factory):
    from app.good.keys import KeyIndex
    from app.settings.store import set_setting
    with session_factory.begin() as s:
        set_setting(s, "traveler_current_element", "Cryo")
    with session_factory() as s:
        idx = KeyIndex.build(s)
    assert idx.character("TravelerGeo") == 1000000503
    assert idx.character("TravelerCryo") == 1000000507
    assert idx.character("Traveler") == 1000000507
    assert idx.character("TravelerLunar") is None
