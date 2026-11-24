from app.wishes.analysis import ItemInfo, expected_for, expected_pity, luck, spiders
from app.wishes.pity import PullView
from app.wishes.types import PityRule

FURINA, NAHIDA, MIST, FAV = 10000089, 10000073, 11509, 11401
ITEMS = {FURINA: ItemInfo("Furina", "UI_AvatarIcon_Furina", 5, "Hydro", "Sword"),
         NAHIDA: ItemInfo("Nahida", "UI_AvatarIcon_Nahida", 5, "Dendro", "Catalyst"),
         MIST: ItemInfo("Mistsplitter Reforged", "UI_EquipIcon_Sword_Narukami", 5, None, "Sword"),
         FAV: ItemInfo("Favonius Sword", "UI_EquipIcon_Sword_Zephyrus", 4, None, "Sword")}


def pv(pity, outcome=None, item_id=FURINA, rarity=5, time="2024-01-15 10:00:00", pk=1):
    return PullView(pk, "x", item_id, "character", rarity, time, pity, outcome, None, None)


def test_expected_for_small_rule_and_real_pools():
    assert expected_for(PityRule(2, None, 10), 0.5, 0.0) == 1.5
    assert expected_pity("character") == 62.3
    assert expected_pity("standard") == 62.3
    assert expected_pity("weapon") == 53.3


def test_luck_verdicts_and_record():
    judged = [pv(80, "lost"), pv(10, "guaranteed"), pv(60, "won"), pv(70, "unknown")]
    out = luck(judged, judged, 62.3, "50/50")
    assert out == {"avg_pity": 55.0, "expected": 62.3, "verdict": "luckier", "won": 1, "lost": 1, "rate": 0.5,
                   "judged_label": "50/50"}
    assert luck([pv(62)], [], 62.3, None)["verdict"] == "average"
    assert luck([pv(65)], [], 62.0, None)["verdict"] == "average"            # exactly +3 is still average
    assert luck([pv(66)], [], 62.3, None)["verdict"] == "unluckier"
    assert luck([pv(59)], [], 62.0, None)["verdict"] == "average"            # exactly −3 is still average
    std = luck([pv(66)], [], 62.3, None)
    assert (std["won"], std["lost"], std["rate"], std["judged_label"]) == (None, None, None, None)


def test_luck_without_fives():
    out = luck([], [], 53.3, "75/25")
    assert out == {"avg_pity": None, "expected": 53.3, "verdict": None, "won": 0, "lost": 0, "rate": None,
                   "judged_label": "75/25"}


def test_spiders_counts_zero_fill_and_unknown():
    pulls = [pv(70, item_id=FURINA), pv(50, item_id=NAHIDA), pv(40, item_id=MIST), pv(9, item_id=FAV, rarity=4),
             pv(9, item_id=999999, rarity=4), pv(1, item_id=None, rarity=3)]
    elements, weapons, unknown = spiders(pulls, ITEMS)
    assert elements["five"] == {"Pyro": 0, "Hydro": 1, "Anemo": 0, "Electro": 0, "Dendro": 1, "Cryo": 0, "Geo": 0}
    assert sum(elements["four"].values()) == 0                        # weapons have no element
    assert weapons["five"] == {"Sword": 2, "Claymore": 0, "Polearm": 0, "Bow": 0, "Catalyst": 1}
    assert weapons["four"]["Sword"] == 1
    assert unknown == 1                                                # 3★ never counted, unknown 4★ is
