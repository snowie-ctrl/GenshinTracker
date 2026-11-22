from dataclasses import replace

from app.planner.data import CharRef, Material, PlannerData, Total
from app.planner.inventory import material_index
from app.teams.shortfall import team_progress, team_shortfall, team_totals

BEN, FUR = 10000032, 10000089
TEACH, GUIDE, PHIL, PLUME = 104301, 104302, 104303, 113003


def data(lack_includes_crafting=False) -> PlannerData:
    materials = {
        TEACH: Material(TEACH, "Teachings", "", 2, "talent", None, [], 1),
        GUIDE: Material(GUIDE, "Guide", "", 3, "talent", TEACH, [], 2),
        PHIL: Material(PHIL, "Philosophies", "", 4, "talent", GUIDE, [], 3),
        PLUME: Material(PLUME, "Plume", "", 5, "weekly", None, [], 4),
    }
    totals = {
        TEACH: Total(0, 0, 9),     # 9 spare Teachings -> 3 Guides
        GUIDE: Total(15, 7, 0),    # have 8
        PHIL: Total(6, 0, 0),      # have >= 6
        PLUME: Total(2, 2, 0),     # have 0
    }
    gaps = {
        BEN: {GUIDE: (9, 4), PHIL: (6, 0), PLUME: (2, 2)},
        FUR: {GUIDE: (6, 4)},
    }
    chars = {BEN: CharRef(BEN, "Bennett", "bennett", None), FUR: CharRef(FUR, "Furina", "furina", None)}
    return PlannerData(materials, totals, gaps, chars, [], lack_includes_crafting, frozenset({BEN, FUR}))


def rows_by_id(d, ids):
    return {r["id"]: r for r in team_shortfall(d, ids, material_index(d))}


def test_team_totals_team_goes_first():
    t = team_totals(data(), [BEN])
    assert t[GUIDE] == Total(9, 1, 0)        # need 9, have 8
    assert t[PHIL] == Total(6, 0, 0)
    assert t[PLUME] == Total(2, 2, 0)
    assert t[TEACH] == Total(0, 0, 9)


def test_shared_material_and_crafting():
    rows = rows_by_id(data(), [BEN])
    guide = rows[GUIDE]
    assert (guide["need"], guide["short"], guide["craftable"], guide["to_farm"]) == (9, 1, 1, 0)
    assert guide["shared"] is True                     # Furina, outside the team, needs it too
    assert rows[PLUME]["shared"] is False and rows[PLUME]["to_farm"] == 2
    assert rows[PHIL]["short"] == 0
    assert TEACH not in rows                           # the team does not need it
    assert [r["id"] for r in team_shortfall(data(), [BEN], material_index(data()))] == [GUIDE, PHIL, PLUME]
    assert rows[PLUME]["category_label"] == "Weekly boss drops"


def test_shared_ignores_characters_no_longer_set_to_build():
    # Furina's gap rows are left over from an earlier calculation, but she is no longer Build.
    d = replace(data(), characters={BEN: data().characters[BEN]})
    assert rows_by_id(d, [BEN])[GUIDE]["shared"] is False


def test_whole_roster_team_matches_combined_short():
    rows = rows_by_id(data(), [BEN, FUR])
    assert rows[GUIDE]["short"] == 7 and rows[GUIDE]["shared"] is False


def test_netted_mode_keeps_hint_but_farms_short():
    rows = rows_by_id(data(lack_includes_crafting=True), [BEN])
    assert (rows[GUIDE]["craftable"], rows[GUIDE]["to_farm"]) == (1, 1)


def test_not_calculated_members_contribute_nothing():
    # The caller passes only calculated Build members; an empty list gives an empty shortfall.
    assert team_shortfall(data(), [], material_index(data())) == []
    d = replace(data(), gaps={BEN: data().gaps[BEN]})
    assert rows_by_id(d, [BEN, FUR])[GUIDE]["need"] == 9    # Furina has no gap rows: adds nothing


def test_team_progress():
    assert team_progress([0.5, None, 1.0]) == 0.75
    assert team_progress([None]) is None
    assert team_progress([]) is None
