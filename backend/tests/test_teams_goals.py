from datetime import datetime

from app.db.models import CharacterGoal, Team, TeamMember, TeamTag
from app.domain import Targets
from app.teams.artifacts import set_line
from app.teams.goals import lower_from_build, raise_to_build

DEFAULTS = Targets(90, 8, 8, 8, 90)
NOW = datetime(2026, 11, 21)


def add_goal(s, cid, goal, targets=None):
    t = targets or (None, None, None, None, None)
    s.add(CharacterGoal(character_id=cid, goal=goal, target_level=t[0], target_normal=t[1], target_skill=t[2],
                        target_burst=t[3], target_weapon_level=t[4], updated_at=NOW))


def test_raise_none_want_and_missing_rows(session_factory):
    with session_factory.begin() as s:
        add_goal(s, 1, "none")
        add_goal(s, 2, "want")
        add_goal(s, 3, "build", (80, 6, 6, 6, 80))
    with session_factory.begin() as s:
        raised = raise_to_build(s, [1, 2, 3, 4, 1], DEFAULTS)
    assert raised == [1, 2, 4]
    with session_factory() as s:
        assert {cid: s.get(CharacterGoal, cid).goal for cid in (1, 2, 3, 4)} == dict.fromkeys((1, 2, 3, 4), "build")
        three = s.get(CharacterGoal, 3)
        assert (three.target_level, three.target_normal) == (80, 6)          # untouched
        four = s.get(CharacterGoal, 4)
        assert (four.target_level, four.target_skill, four.target_weapon_level) == (90, 8, 90)


def test_raise_restores_stored_targets(session_factory):
    with session_factory.begin() as s:
        add_goal(s, 1, "want", (70, 9, 9, 9, 70))
    with session_factory.begin() as s:
        assert raise_to_build(s, [1], DEFAULTS) == [1]
    with session_factory() as s:
        row = s.get(CharacterGoal, 1)
        assert (row.goal, row.target_level, row.target_burst) == ("build", 70, 9)


def test_raise_nothing():
    assert raise_to_build(None, [], DEFAULTS) == []


def test_set_line():
    assert set_line(["A", "A", "A", "A", "B"]) == "4pc A"
    assert set_line(["A"] * 5) == "4pc A"
    assert set_line(["A", "A", "B", "B"]) == "2pc A + 2pc B"
    assert set_line(["B", "B", "A", "A", "C"]) == "2pc A + 2pc B"
    assert set_line(["B", "B", "B", "A", "A"]) == "2pc B + 2pc A"
    assert set_line(["A", "B", "C", "D", "E"]) == ""
    assert set_line([]) == ""


def team_with(s, tid, members, build):
    s.add(Team(id=tid, name=f"T{tid}", notes="", sort_order=tid, created_at=NOW, updated_at=NOW))
    s.flush()
    for slot, cid in enumerate(members):
        s.add(TeamMember(team_id=tid, slot=slot, character_id=cid, role=""))
    if build:
        s.add(TeamTag(team_id=tid, tag_id=1))


def test_lower_build_to_none_and_clears_priority(session_factory):
    with session_factory.begin() as s:
        add_goal(s, 1, "build", (80, 6, 6, 6, 80))
        s.get(CharacterGoal, 1).priority = 3
        add_goal(s, 2, "want")
    with session_factory.begin() as s:
        assert lower_from_build(s, [1, 2, 3], None) == [1]
    with session_factory() as s:
        row = s.get(CharacterGoal, 1)
        assert (row.goal, row.priority, row.target_level) == ("none", None, 80)   # targets kept
        assert s.get(CharacterGoal, 2).goal == "want" and s.get(CharacterGoal, 3) is None


def test_lower_keeps_member_of_other_build_team(session_factory):
    with session_factory.begin() as s:
        for cid in (1, 2):
            add_goal(s, cid, "build")
        team_with(s, 10, [1, 2], build=False)     # the team being switched off
        team_with(s, 11, [1], build=True)         # another Build team still has 1
        team_with(s, 12, [2], build=False)        # a non-Build team does not protect 2
    with session_factory.begin() as s:
        assert lower_from_build(s, [1, 2], exclude_team_id=10) == [2]


def test_lower_then_raise_restores_targets(session_factory):
    with session_factory.begin() as s:
        add_goal(s, 1, "build", (70, 9, 9, 9, 70))
    with session_factory.begin() as s:
        lower_from_build(s, [1], None)
    with session_factory.begin() as s:
        assert raise_to_build(s, [1], DEFAULTS) == [1]
    with session_factory() as s:
        assert s.get(CharacterGoal, 1).target_level == 70
