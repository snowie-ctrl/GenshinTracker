# backend/tests/test_planner.py
from datetime import datetime

from app.db.models import CharacterGoal, GameMaterial, GapRun, MaterialGap, MaterialTotal
from app.planner.crafting import chains, rollup
from app.planner.data import CharRef, Material, PlannerData, Total, load
from app.planner.inventory import inventory, material_index
from app.planner.status import gap_status
from app.timeutil import utcnow
from helpers import seed_game


def mat(mid, category="talent", rarity=3, craft_from=None, sources=(), order=0, name=None):
    return Material(mid, name or f"M{mid}", f"UI_ItemIcon_{mid}", rarity, category, craft_from, list(sources), order)


BOOKS = {1: mat(1, rarity=2, order=1), 2: mat(2, rarity=3, craft_from=1, order=2),
         3: mat(3, rarity=4, craft_from=2, order=3)}


def data(totals, gaps=None, materials=BOOKS, netted=False):
    chars = {10: CharRef(10, "Bennett", "bennett", "UI_AvatarIcon_Bennett"),
             20: CharRef(20, "Furina", "furina", "UI_AvatarIcon_Furina")}
    return PlannerData(materials=dict(materials), totals=totals, gaps=gaps or {}, characters=chars,
                       domains=[], lack_includes_crafting=netted)


def test_chains_follow_craft_from():
    assert chains(BOOKS) == [[1, 2, 3]]


def test_rollup_crafts_from_spare_lower_tiers():
    d = data({1: Total(0, 0, 40), 2: Total(10, 5, 0), 3: Total(6, 2, 0)})
    r = rollup(d)
    assert (r[2].craftable, r[2].to_farm) == (5, 0)     # 40 green -> 13 blue
    assert (r[3].craftable, r[3].to_farm) == (2, 0)     # (13 - 5) // 3 = 2 gold


def test_rollup_partial_and_nothing_spare():
    r = rollup(data({1: Total(0, 0, 7), 2: Total(10, 5, 0), 3: Total(6, 2, 0)}))
    assert (r[2].craftable, r[2].to_farm) == (2, 3)
    assert (r[3].craftable, r[3].to_farm) == (0, 2)
    r = rollup(data({2: Total(10, 5, 0)}))
    assert (r[2].craftable, r[2].to_farm) == (0, 5)


def test_rollup_netted_mode_does_not_subtract_again():
    r = rollup(data({1: Total(0, 0, 40), 2: Total(10, 5, 0)}, netted=True))
    assert (r[2].craftable, r[2].to_farm) == (0, 5)


def test_material_states_and_have():
    idx = material_index(data({2: Total(10, 4, 0), 3: Total(6, 0, 0)},
                              gaps={10: {2: (6, 4)}, 20: {2: (4, 4), 3: (6, 0)}}))
    assert idx[1]["state"] == "unneeded" and idx[1]["have"] is None
    assert idx[2]["state"] == "short" and idx[2]["have"] == 6 and idx[2]["to_farm"] == 4
    assert [c["name"] for c in idx[2]["characters"]] == ["Bennett", "Furina"]
    assert idx[3]["state"] == "met" and idx[3]["need"] == 6


def test_inventory_groups_in_category_order_and_adds_other():
    mats = {**BOOKS, 9: mat(9, category="exp", order=0),
            999: Material(999, "Brand New", "https://x/n.png", 4, "other", None, [], 10**6)}
    d = data({999: Total(3, 3, 0)}, materials=mats)
    cats = inventory(d, material_index(d))
    assert [c["key"] for c in cats] == ["exp", "talent", "other"]
    assert cats[-1]["label"] == "Other" and cats[-1]["materials"][0]["name"] == "Brand New"


def test_load_reads_tables_and_creates_other_for_unknown(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        s.add(GameMaterial(id=2, name="Guide", icon="UI_ItemIcon_2", rarity=3, yatta_type="t", category="talent",
                           craft_from=None, sources=[], sort_order=0, detail_fetched=True))
        s.add(MaterialTotal(material_id=2, name="Guide", icon="", rarity=3, need=9, short=4, spare=0))
        s.add(MaterialTotal(material_id=999, name="Brand New", icon="https://act-webstatic.hoyoverse.com/n.png",
                            rarity=4, need=3, short=3, spare=0))
        s.add(MaterialGap(character_id=10000032, material_id=2, need=9, short=4))
        s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, updated_at=utcnow()))
    with session_factory() as s:
        d = load(s)
    assert d.materials[999].category == "other" and d.materials[999].name == "Brand New"
    assert d.totals[2] == Total(9, 4, 0)
    assert d.gaps == {10000032: {2: (9, 4)}}
    assert d.characters[10000032].slug == "bennett"


def test_gap_status_stale_pending_failed_and_disconnected(session_factory):
    seed_game(session_factory)
    with session_factory() as s:
        assert gap_status(s, pending=False, connected=True)["stale"] is False   # nothing to build
    with session_factory.begin() as s:
        s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, updated_at=utcnow()))
    with session_factory() as s:
        assert gap_status(s, pending=False, connected=True)["stale"] is True    # never calculated
        assert gap_status(s, pending=False, connected=False)["stale"] is False  # cannot calculate
    with session_factory.begin() as s:
        s.add(GapRun(id=1, computed_at=datetime(2026, 11, 19, 12), ok=True, error=None, skipped=[],
                     snapshot=[[10000032, 90, 8, 8, 8, 90, None]]))
    with session_factory() as s:
        st = gap_status(s, pending=False, connected=True)
        assert st["stale"] is False and st["computed_at"] == "2026-11-19T12:00:00Z"
        assert gap_status(s, pending=True, connected=True)["stale"] is True
    with session_factory.begin() as s:
        s.get(GapRun, 1).ok = False
        s.get(GapRun, 1).error = "HoyolabError: down"
    with session_factory() as s:
        st = gap_status(s, pending=False, connected=True)
        assert st["ok"] is False and st["error"] == "HoyolabError: down"
