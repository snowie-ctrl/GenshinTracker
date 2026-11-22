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
