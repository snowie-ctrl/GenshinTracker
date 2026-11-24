# backend/tests/test_profile_showcase.py
from datetime import datetime

from app.db.models import OwnedArtifact, OwnedCharacter
from app.profile.showcase import crit_value, owned_options, set_summary, showcase_view, validate_ids
from app.settings.store import set_setting
from helpers import seed_game

T = datetime(2026, 11, 1)


def own(s, cid, name, level=90, cons=0, element=None, stats=()):
    s.add(OwnedCharacter(character_id=cid, name=name, element=element, icon=None, level=level, constellation=cons,
                         friendship=10, talent_normal=6, talent_skill=10, talent_burst=None,
                         weapon_name="Favonius Sword", weapon_icon="https://x.test/w.png", weapon_rarity=4,
                         weapon_level=90, weapon_refinement=3, stats=list(stats), synced_at=T))


def art(cid, slot, set_name, subs):
    return OwnedArtifact(character_id=cid, slot=slot, set_name=set_name, rarity=5, level=20, main_stat="HP 4780",
                         substats=list(subs), icon="https://x.test/a.png")


def test_default_order_level_cons_rarity_name(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        own(s, 10000089, "Furina", cons=2)
        own(s, 10000073, "Nahida")
        own(s, 10000032, "Bennett", cons=6)
        own(s, 10000023, "Xiangling", level=80)
        own(s, 1000000507, "Cryo Traveler", element="Cryo")
    with session_factory() as s:
        v = showcase_view(s)
    assert v["mode"] == "auto"
    assert [e["id"] for e in v["entries"]] == [10000032, 10000089, 1000000507, 10000073, 10000023]
    traveler = v["entries"][2]
    assert traveler["slug"] == "cryo-traveler" and traveler["element"] == "Cryo"
    assert traveler["icon"] == "UI_AvatarIcon_PlayerGirl"                 # owned icon empty → game icon


def test_default_order_caps_at_eight(session_factory):
    with session_factory.begin() as s:
        for i in range(1, 10):
            own(s, 500 + i, f"C{i}", level=80 + i)
    with session_factory() as s:
        assert len(showcase_view(s)["entries"]) == 8


def test_showcase_skips_unowned(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        own(s, 10000073, "Nahida")
        own(s, 10000089, "Furina")
        set_setting(s, "profile_showcase", [999, 10000073])
    with session_factory() as s:
        v = showcase_view(s)
    assert v["mode"] == "custom" and [e["id"] for e in v["entries"]] == [10000073]


def test_entry_stats_artifacts_sets_and_crit(session_factory):
    seed_game(session_factory)
    stats = [{"name": "Max HP", "value": "38412"}, {"name": "Max Stamina", "value": "240"},
             {"name": "CRIT Rate", "value": "72.4%"}, {"name": "Healing Bonus", "value": "0.0%"}]
    with session_factory.begin() as s:
        own(s, 10000089, "Furina", stats=stats)
        for slot in (1, 2, 3, 4):
            s.add(art(10000089, slot, "Golden Troupe", ["CRIT Rate 3.5%", "ATK 14"]))
        s.add(art(10000089, 5, "Noblesse Oblige", ["CRIT DMG 7.8%", "HP 5.8%"]))
    with session_factory() as s:
        e = showcase_view(s)["entries"][0]
    assert e["stats"] == [{"name": "Max HP", "value": "38412"}, {"name": "CRIT Rate", "value": "72.4%"}]
    assert [a["slot"] for a in e["artifacts"]] == [1, 2, 3, 4, 5]
    assert e["sets"] == "Golden Troupe 4" and e["crit_value"] == 35.8              # 4 × 2 × 3.5 + 7.8
    assert e["talents"] == {"normal": 6, "skill": 10, "burst": None}
    assert e["weapon"] == {"name": "Favonius Sword", "icon": "https://x.test/w.png", "level": 90, "refinement": 3,
                           "rarity": 4}


def test_set_summary_and_crit_value_edge_cases():
    two_two = [art(1, 1, "B Set", []), art(1, 2, "A Set", []), art(1, 3, "B Set", []), art(1, 4, "A Set", []),
               art(1, 5, "C Set", [])]
    assert set_summary(two_two) == "A Set 2 · B Set 2"
    assert set_summary([art(1, 1, "A Set", [])]) == ""
    assert crit_value([art(1, 1, "A", ["CRIT Rate 3.9%", "CRIT DMG 21.0%", "CRIT Rate 3"])]) == 28.8   # flat ignored


def test_validate_ids_and_owned_options(session_factory):
    with session_factory.begin() as s:
        own(s, 10000089, "Furina")
        own(s, 10000032, "Bennett")
    with session_factory() as s:
        assert validate_ids(s, [10000089, 10000032]) is None
        assert validate_ids(s, []) is None
        assert validate_ids(s, list(range(9))) == "Pick at most 8 characters."
        assert validate_ids(s, [10000089, 10000089]) == "Each character can be shown once."
        assert validate_ids(s, [123]) == "Only characters you own can be shown."
        assert [o["name"] for o in owned_options(s)] == ["Bennett", "Furina"]


def test_default_has_one_traveler_current_element_wins(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        own(s, 10000089, "Furina", level=80)
        own(s, 1000000507, "Cryo Traveler", element="Cryo")
        own(s, 1000000502, "Anemo Traveler", element="Anemo")
        set_setting(s, "traveler_current_element", "Cryo")
    with session_factory() as s:
        ids = [e["id"] for e in showcase_view(s)["entries"]]
        assert len(owned_options(s)) == 3
    assert ids == [1000000507, 10000089]


def test_custom_showcase_may_pick_any_traveler_element(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        own(s, 1000000507, "Cryo Traveler", element="Cryo")
        own(s, 1000000502, "Anemo Traveler", element="Anemo")
        set_setting(s, "profile_showcase", [1000000502])
    with session_factory() as s:
        v = showcase_view(s)
    assert v["mode"] == "custom" and [e["id"] for e in v["entries"]] == [1000000502]


def test_custom_list_with_no_owned_ids_falls_back_to_auto(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        own(s, 10000073, "Nahida")
        set_setting(s, "profile_showcase", [999])
    with session_factory() as s:
        v = showcase_view(s)
    assert v["mode"] == "auto" and [e["id"] for e in v["entries"]] == [10000073]
