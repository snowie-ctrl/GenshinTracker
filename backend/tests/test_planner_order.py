import pytest

from app.db.models import CharacterGoal
from app.planner.order import apply_goal, build_order, set_order
from app.teams.goals import raise_to_build
from app.domain import Targets
from app.timeutil import utcnow
from helpers import make_client, seed_game


def add(s, cid, goal="none", priority=None):
    row = CharacterGoal(character_id=cid, goal=goal, priority=priority, updated_at=utcnow())
    s.add(row)
    return row


def test_entering_build_appends_and_leaving_clears(session_factory):
    with session_factory.begin() as s:
        a, b, c = add(s, 1), add(s, 2), add(s, 3)
        s.flush()
        apply_goal(s, a, "build")
        apply_goal(s, b, "build")
        assert (a.priority, b.priority) == (1, 2)
        apply_goal(s, a, "want")
        assert a.priority is None
        apply_goal(s, c, "build")
        apply_goal(s, a, "build")
        assert build_order(s) == [2, 3, 1]
        apply_goal(s, b, "build")            # unchanged goal keeps its place
        assert build_order(s) == [2, 3, 1]


def test_rows_without_priority_sort_last_by_id(session_factory):
    with session_factory.begin() as s:
        add(s, 30, "build", None)
        add(s, 20, "build", None)
        add(s, 99, "build", 1)
        add(s, 5, "want", None)
        s.flush()
        assert build_order(s) == [99, 20, 30]


def test_set_order_renumbers_appends_unlisted_and_validates(session_factory):
    with session_factory.begin() as s:
        for cid, p in [(1, 1), (2, 2), (3, 3)]:
            add(s, cid, "build", p)
        add(s, 4, "want")
        s.flush()
        set_order(s, [3, 1])
        assert build_order(s) == [3, 1, 2]
        with pytest.raises(ValueError, match="not set to Build"):
            set_order(s, [4, 1])
        with pytest.raises(ValueError, match="more than once"):
            set_order(s, [1, 1])
        assert build_order(s) == [3, 1, 2]   # failed calls change nothing


def test_teams_raise_appends_priority(session_factory):
    with session_factory.begin() as s:
        add(s, 1, "build", 1)
        s.flush()
        raise_to_build(s, [7, 1], Targets(90, 8, 8, 8, 90))
        assert build_order(s) == [1, 7]


def test_goal_endpoint_sets_and_clears_priority(paths):
    from test_api_characters import setup_data
    from test_api_planner import sf_for
    setup_data(paths)               # Bennett and Nahida are Build rows written directly (priority NULL); Furina owned
    sf = sf_for(paths)

    def furina():
        with sf() as s:
            return s.get(CharacterGoal, 10000089).priority

    with make_client(paths) as client:
        client.put("/api/characters/10000089/goal", json={"goal": "build"})
        assert furina() == 1                                    # NULL rows do not count towards the max
        client.put("/api/characters/10000089/goal", json={"goal": "want"})
        assert furina() is None
        client.put("/api/characters/10000089/goal", json={"goal": "build"})
        assert furina() == 1
        client.put("/api/characters/10000089/goal", json={"targets": {"level": 80, "normal": 6, "skill": 6,
                                                                       "burst": 6, "weapon_level": 80}})
        assert furina() == 1                                    # editing targets keeps the place
    with sf() as s:
        assert build_order(s) == [10000089, 10000032, 10000073]
