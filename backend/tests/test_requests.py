import pytest
from app.db.models import CharacterGoal
from app.planner.requests import build_inputs, gap_requests, has_work, snapshot
from app.sync.hoyolab import TalentIds
from app.sync.persist import save_details, save_roster
from app.timeutil import utcnow
from fakes import make_detail, make_roster
from helpers import seed_game


def goal(cid, level=90, talents=(8, 8, 8), weapon_level=90, planned=None):
    return CharacterGoal(character_id=cid, goal="build", target_level=level, target_normal=talents[0],
                         target_skill=talents[1], target_burst=talents[2], target_weapon_level=weapon_level,
                         planned_weapon_id=planned, updated_at=utcnow())


def setup(session_factory, goals):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032, level=80, name="Bennett"),
                        make_roster(1000000507, raw_id=10000007, name="Traveler", element="Cryo")], utcnow())
        save_details(s, [make_detail(10000032, talents=(6, 8, 8))])
        for g in goals:
            s.add(g)


def test_owned_prefarm_and_traveler(session_factory):
    setup(session_factory, [goal(10000032), goal(10000073), goal(1000000507)])
    with session_factory() as s:
        inputs, skipped = build_inputs(s)
    by_id = {i.character_id: i for i in inputs}
    assert skipped == []
    assert set(by_id) == {10000032, 10000073, 1000000507}
    assert by_id[1000000507].element_attr_id == 7 and by_id[1000000507].avatar_id == 10000007
    bennett, nahida = by_id[10000032], by_id[10000073]
    assert (bennett.level, bennett.talents) == (80, (6, 8, 8))
    assert bennett.weapon == (1, 90)             # equipped weapon id from the fake roster (WEAPON.id == 1)
    assert (nahida.level, nahida.talents, nahida.weapon) == (1, (1, 1, 1), None)


def test_planned_weapon_starts_at_level_1(session_factory):
    setup(session_factory, [goal(10000032, planned=11509), goal(10000073, planned=13407)])
    with session_factory() as s:
        by_id = {i.character_id: i for i in build_inputs(s)[0]}
    assert by_id[10000032].weapon == (11509, 1)
    assert by_id[10000073].weapon == (13407, 1)


def test_planned_weapon_equal_to_equipped_keeps_current_level(session_factory):
    setup(session_factory, [goal(10000032, planned=1)])
    with session_factory() as s:
        assert build_inputs(s)[0][0].weapon == (1, 90)


def test_fully_built_character_has_no_work_and_no_request(session_factory):
    setup(session_factory, [goal(10000032, level=80, talents=(6, 8, 8), weapon_level=90)])
    with session_factory() as s:
        inputs, _ = build_inputs(s)
    assert has_work(inputs[0]) is False
    assert gap_requests([i for i in inputs if has_work(i)], {}) == []


def test_gap_requests_only_raise_parts_below_target(session_factory):
    setup(session_factory, [goal(10000032, level=90, talents=(9, 8, 10), weapon_level=90)])
    with session_factory() as s:
        inputs, _ = build_inputs(s)
    (req,) = gap_requests(inputs, {10000032: TalentIds(3201, 3202, 3209)})
    assert (req.level_current, req.level_target) == (80, 90)
    assert req.talents == ((3201, 6, 9), (3209, 8, 10))
    assert req.weapon is None                     # weapon already at target


def test_snapshot_changes_with_targets(session_factory):
    setup(session_factory, [goal(10000032)])
    with session_factory() as s:
        before = snapshot(s)
    with session_factory.begin() as s:
        s.get(CharacterGoal, 10000032).target_skill = 10
    with session_factory() as s:
        assert snapshot(s) != before
