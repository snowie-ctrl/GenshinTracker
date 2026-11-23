from app.planner.data import CharRef, Material, PlannerData, Total
from app.planner.inventory import material_index
from app.planner.priority import Allocation, allocate, build_sections, held_counts


def mat(mid, rarity=3, craft_from=None, category="talent"):
    return Material(mid, f"M{mid}", f"UI_ItemIcon_{mid}", rarity, category, craft_from, [], mid)


BOOKS = {1: mat(1, 2), 2: mat(2, 3, craft_from=1), 3: mat(3, 4, craft_from=2)}
CHARS = {10: CharRef(10, "Bennett", "bennett", None), 20: CharRef(20, "Furina", "furina", None),
         1000000507: CharRef(1000000507, "Cryo Traveler", "cryo-traveler", None),
         1000000502: CharRef(1000000502, "Anemo Traveler", "anemo-traveler", None)}


def data(totals, gaps, netted=False, calculated=frozenset({10, 20, 1000000507, 1000000502})):
    return PlannerData(materials=dict(BOOKS), totals=totals, gaps=gaps, characters=dict(CHARS), domains=[],
                       lack_includes_crafting=netted, calculated=calculated)


def test_held_counts_need_minus_short_plus_spare():
    assert held_counts(data({2: Total(50, 36, 0), 1: Total(0, 0, 9)}, {})) == {2: 14, 1: 9}


def test_user_examples_14_and_32_held():
    gaps = {10: {2: (20, 6)}, 20: {2: (30, 16)}}
    d = data({2: Total(50, 36, 0)}, gaps)                  # 14 held
    a = allocate(d, [10, 20])
    assert a[10][2] == Allocation(20, 14, 0) and a[20][2] == Allocation(30, 0, 0)
    d = data({2: Total(50, 18, 0)}, gaps)                  # 32 held
    a = allocate(d, [10, 20])
    assert a[10][2] == Allocation(20, 20, 0) and a[20][2] == Allocation(30, 12, 0)


def test_leftover_lower_tiers_craft_for_p1_before_p2():
    gaps = {10: {2: (9, 4)}, 20: {2: (6, 4)}}
    d = data({2: Total(15, 7, 0), 1: Total(0, 0, 9)}, gaps)   # 8 blue, 9 green held
    a = allocate(d, [10, 20])
    assert a[10][2] == Allocation(9, 8, 1)                  # 3 green -> 1 blue
    assert a[20][2] == Allocation(6, 0, 2)                  # 6 green left -> 2 blue
    a = allocate(d, [20, 10])
    assert a[20][2] == Allocation(6, 6, 0) and a[10][2] == Allocation(9, 2, 3)


def test_crafting_goes_through_two_tiers():
    d = data({3: Total(1, 1, 0), 1: Total(0, 0, 9)}, {10: {3: (1, 1)}})  # 9 green -> 3 blue -> 1 gold
    assert allocate(d, [10])[10][3] == Allocation(1, 0, 1)


def test_netted_mode_never_crafts():
    d = data({2: Total(15, 7, 0), 1: Total(0, 0, 9)}, {10: {2: (9, 4)}}, netted=True)
    assert allocate(d, [10])[10][2] == Allocation(9, 8, 0)


def test_allocate_zero_held_and_disjoint_materials():
    gaps = {10: {2: (5, 5)}, 20: {3: (2, 0)}}
    d = data({2: Total(5, 5, 0), 3: Total(2, 0, 0)}, gaps)
    a = allocate(d, [10, 20])
    assert a[10] == {2: Allocation(5, 0, 0)} and a[20] == {3: Allocation(2, 2, 0)}


def test_traveler_elements_are_separate_entries():
    gaps = {1000000507: {2: (6, 6)}, 1000000502: {2: (6, 6)}, 10: {2: (6, 6)}}
    d = data({2: Total(18, 10, 0)}, gaps)                  # 8 held
    a = allocate(d, [1000000502, 10, 1000000507])
    assert [a[c][2].have for c in (1000000502, 10, 1000000507)] == [6, 2, 0]


def test_build_sections_ready_completed_and_not_calculated():
    gaps = {10: {2: (9, 4)}, 20: {2: (6, 4)}}
    d = data({2: Total(15, 7, 0), 1: Total(0, 0, 9)}, gaps,
             calculated=frozenset({10, 20, 1000000507}))
    out = build_sections(d, [20, 10, 1000000507, 1000000502], material_index(d), {10: 0.5})
    builds = {b["character"]["id"]: b for b in out["builds"]}
    assert [b["character"]["id"] for b in out["builds"]] == [20, 10, 1000000502]
    assert [b["priority"] for b in out["builds"]] == [1, 2, 3]
    assert builds[20]["ready"] is True and builds[10]["ready"] is False  # Bennett: 2 held + 3 craft < 9
    m = builds[10]["materials"][0]
    assert (m["need"], m["have"], m["craft"], m["category_label"]) == (9, 2, 3, "Talent books")
    assert builds[10]["progress"] == 0.5 and builds[20]["progress"] is None
    nc = builds[1000000502]
    assert (nc["calculated"], nc["ready"], nc["materials"]) == (False, False, [])
    assert [c["id"] for c in out["completed"]] == [1000000507]          # calculated, no gap rows


def test_failed_higher_tier_craft_does_not_drain_pool():
    gaps = {10: {3: (1, 1)}, 20: {2: (2, 2)}}
    d = data({1: Total(0, 0, 6), 3: Total(1, 1, 0), 2: Total(2, 2, 0)}, gaps)   # 6 green held only
    a = allocate(d, [10, 20])
    assert a[10][3] == Allocation(1, 0, 0) and a[20][2] == Allocation(2, 0, 2)


def test_partial_multi_tier_craft_leaves_rest_for_later_gap():
    gaps = {10: {3: (2, 2)}, 20: {2: (1, 1)}}
    d = data({1: Total(0, 0, 12), 3: Total(2, 2, 0), 2: Total(1, 1, 0)}, gaps)  # 12 green held
    a = allocate(d, [10, 20])
    assert a[10][3] == Allocation(2, 0, 1) and a[20][2] == Allocation(1, 0, 1)


def test_duplicate_ids_in_order_are_ignored():
    gaps = {10: {2: (5, 5)}}
    d = data({2: Total(5, 3, 0)}, gaps)                    # 2 held
    assert allocate(d, [10, 10])[10][2] == Allocation(5, 2, 0)
    assert len(build_sections(d, [10, 10], material_index(d), {})["builds"]) == 1
