from app.gamedata.kit import KIT_VERSION, fill, parse_kit, segments, yatta_key
from helpers import load_fixture


def kit(name):
    return parse_kit(load_fixture(f"yatta_kit_{name}.json"))


def test_furina_roles_and_scaling():
    k = kit("furina")
    roles = [(t["role"], t["name"]) for t in k["talents"]]
    assert roles == [("normal", "Soloist's Solicitation"), ("skill", "Salon Solitaire"),
                     ("burst", "Let the People Rejoice")]
    skill = k["talents"][1]
    assert skill["icon"] == "Skill_S_Furina_01" and skill["cooldown"] == 20.0 and skill["cost"] is None
    assert k["talents"][2]["cost"] == 60
    row = next(r for r in skill["scaling"] if r["label"] == "Ousia Bubble DMG")
    assert len(row["values"]) == 15 and row["values"][0].endswith("% Max HP")
    assert [p["name"] for p in k["passives"]][:2] == ["Endless Waltz", "Unheard Confession"]


def test_furina_constellations_raise_by_link():
    k = kit("furina")
    assert [c["index"] for c in k["constellations"]] == [1, 2, 3, 4, 5, 6]
    raises = {c["index"]: c["raises"] for c in k["constellations"]}
    assert raises == {1: None, 2: None, 3: "burst", 4: None, 5: "skill", 6: None}


def test_mona_sprint_is_other_and_raises_by_text():
    k = kit("mona")
    assert [t["role"] for t in k["talents"]] == ["normal", "skill", "other", "burst"]
    raises = {c["index"]: c["raises"] for c in k["constellations"]}
    assert raises[3] == "burst" and raises[5] == "skill"
    assert len(k["passives"]) == 4


def test_traveler_link_markup_keeps_text():
    k = kit("traveler_anemo")
    text = "".join(s["text"] for line in k["talents"][0]["description"] for s in line)
    assert "{LINK" not in text and "<color" not in text


def test_segments_colour_italic_and_lines():
    out = segments("Deal <color=#80C0FFFF>Hydro DMG</color>.\\nThen <i>rest</i>{LINK#N1}buffs{/LINK}")
    assert out == [
        [{"text": "Deal ", "color": None, "italic": False}, {"text": "Hydro DMG", "color": "#80C0FF", "italic": False},
         {"text": ".", "color": None, "italic": False}],
        [{"text": "Then ", "color": None, "italic": False}, {"text": "rest", "color": None, "italic": True},
         {"text": "buffs", "color": None, "italic": False}],
    ]


def test_fill_formats():
    p = [0.114064, 18, 0.01, 300, 0.0007, 1.5]
    assert fill("{param1:F1P} Max HP", p) == "11.4% Max HP"
    assert fill("{param2:F1}s", p) == "18.0s"
    assert fill("{param4:I}", p) == "300"
    assert fill("{param5:F2P}", p) == "0.07%"
    assert fill("{param3:P}/{param6:F2}", p) == "1%/1.50"
    assert fill("{param9:F1P}", p) == "?"                   # missing param
    assert fill("{param1:ZZ}", p) == "0.114064"             # unknown format prints the raw number


def test_skips_malformed_entries():
    payload = load_fixture("yatta_kit_furina.json")
    payload["data"]["talent"]["99"] = {"type": 2}            # no name
    payload["data"]["constellation"]["9"] = None
    k = parse_kit(payload)
    assert len(k["passives"]) == 3 and len(k["constellations"]) == 6


def test_parse_kit_carries_shape_version():
    assert kit("furina")["v"] == KIT_VERSION


def test_yatta_key():
    assert yatta_key(10000089, "girl") == "10000089"
    assert yatta_key(1000000502, "girl") == "10000007-anemo"
    assert yatta_key(1000000503, "boy") == "10000005-geo"


def test_segments_real_newline_also_splits():
    assert segments("a\nb") == [[{"text": "a", "color": None, "italic": False}],
                                [{"text": "b", "color": None, "italic": False}]]


def test_furina_has_no_literal_backslash_n():
    k = kit("furina")
    descs = [t["description"] for t in k["talents"]] + [p["description"] for p in k["passives"]] \
        + [c["description"] for c in k["constellations"]]
    assert all("\\n" not in s["text"] for d in descs for line in d for s in line)
    assert len(k["talents"][0]["description"]) > 1   # multi-line description actually split
