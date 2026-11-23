import pytest
from pydantic import ValidationError

from app.domain import Current, Targets, build_defaults, derive_status, progress, resolve_targets
from app.schemas import TargetsIn

DEFAULTS = Targets(level=90, normal=8, skill=8, burst=8, weapon_level=90)


@pytest.mark.parametrize(
    ("owned", "goal", "expected"),
    [
        (False, "none", ("unobtained", False)),
        (False, "want", ("wanted", False)),
        (False, "build", ("wanted", True)),
        (True, "none", ("obtained", False)),
        (True, "want", ("obtained", False)),
        (True, "build", ("building", False)),
    ],
)
def test_derive_status_all_six(owned, goal, expected):
    assert derive_status(owned, goal) == expected


def test_derive_status_rejects_unknown_goal():
    with pytest.raises(ValueError):
        derive_status(True, "maybe")


def test_progress_averages_level_and_talents():
    cur = Current(level=45, normal=4, skill=8, burst=8)
    assert progress(cur, DEFAULTS) == pytest.approx((0.5 + 0.5 + 1 + 1) / 4)


def test_progress_target_at_or_below_current_counts_full():
    cur = Current(level=90, normal=10, skill=9, burst=8)
    assert progress(cur, DEFAULTS) == 1.0


def test_progress_unknown_talents_count_as_one():
    cur = Current(level=90, normal=None, skill=None, burst=None)
    assert progress(cur, DEFAULTS) == pytest.approx((1 + 3 * (1 / 8)) / 4, abs=1e-4)


def test_resolve_targets_build_without_stored_uses_defaults():
    assert resolve_targets("build", None, DEFAULTS) == DEFAULTS


def test_resolve_targets_keeps_stored_when_leaving_build():
    stored = Targets(80, 6, 6, 6, 80)
    assert resolve_targets("want", stored, DEFAULTS) == stored
    assert resolve_targets("build", stored, DEFAULTS) == stored


def test_resolve_targets_none_without_stored():
    assert resolve_targets("none", None, DEFAULTS) is None


def test_targets_dict_round_trip():
    assert Targets.from_dict(DEFAULTS.to_dict()) == DEFAULTS


def test_targets_in_validates_ranges():
    TargetsIn(level=90, normal=10, skill=1, burst=8, weapon_level=90)
    with pytest.raises(ValidationError):
        TargetsIn(level=90, normal=11, skill=1, burst=8, weapon_level=90)
    with pytest.raises(ValidationError):
        TargetsIn(level=0, normal=1, skill=1, burst=1, weapon_level=1)


def test_build_defaults_baseline_for_unowned():
    assert build_defaults(None) == Targets(90, 6, 9, 9, 90, constellation=0, refinement=1)


def test_build_defaults_never_below_current():
    cur = Current(level=90, normal=10, skill=8, burst=10, constellation=2, weapon_level=80, refinement=5)
    assert build_defaults(cur) == Targets(90, 10, 9, 10, 90, constellation=2, refinement=5)


def test_build_defaults_missing_current_values():
    cur = Current(level=40, normal=None, skill=None, burst=None)
    assert build_defaults(cur) == Targets(90, 6, 9, 9, 90, constellation=0, refinement=1)


def test_targets_from_dict_without_new_fields():
    t = Targets.from_dict({"level": 80, "normal": 6, "skill": 6, "burst": 6, "weapon_level": 80})
    assert (t.constellation, t.refinement) == (None, None)
    assert t.to_dict()["constellation"] is None
