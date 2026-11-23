import pytest
from sqlalchemy import func, select

from app.db.models import CharacterGoal, Tag, Team, TeamMember
from app.teams import store
from app.teams.store import BUILD_TAG_ID, MemberIn, TeamError
from helpers import drop_default_tags, seed_game

BEN, FUR, XL, NAH = 10000032, 10000089, 10000023, 10000073


@pytest.fixture
def sf(session_factory):
    seed_game(session_factory)
    drop_default_tags(session_factory)
    return session_factory


def save(sf, team_id=None, members=(BEN,), tags=(), new_tags=(), name="Team", notes="", roles=None):
    roles = roles or {}
    with sf.begin() as s:
        team, raised = store.save_team(s, team_id, name, notes,
                                       [MemberIn(c, roles.get(c, "")) for c in members], list(tags), list(new_tags))
        return team.id, raised


def goals(sf, *ids):
    with sf() as s:
        return [(s.get(CharacterGoal, i).goal if s.get(CharacterGoal, i) else "none") for i in ids]


def set_goal(sf, cid, goal):
    from datetime import datetime
    with sf.begin() as s:
        row = s.get(CharacterGoal, cid) or CharacterGoal(character_id=cid, goal=goal, updated_at=datetime(2026, 1, 1))
        row.goal = goal
        s.add(row)


def members_of(sf, team_id):
    with sf() as s:
        return [(m.slot, m.character_id, m.role) for m in
                s.scalars(select(TeamMember).where(TeamMember.team_id == team_id).order_by(TeamMember.slot))]


def test_create_without_build_changes_no_goals(sf):
    tid, raised = save(sf, members=(BEN, FUR), roles={FUR: "driver"})
    assert raised == []
    assert goals(sf, BEN, FUR) == ["none", "none"]
    assert members_of(sf, tid) == [(0, BEN, ""), (1, FUR, "driver")]


def test_adding_build_raises_all_members(sf):
    set_goal(sf, FUR, "build")
    tid, _ = save(sf, members=(BEN, FUR))
    _, raised = save(sf, tid, members=(BEN, FUR), tags=(BUILD_TAG_ID,))
    assert raised == [BEN]
    assert goals(sf, BEN, FUR) == ["build", "build"]


def test_build_team_gaining_member_raises_only_that_member(sf):
    tid, raised = save(sf, members=(BEN, FUR), tags=(BUILD_TAG_ID,))
    assert raised == [BEN, FUR]
    set_goal(sf, FUR, "want")                                   # the user lowers Furina elsewhere
    _, raised = save(sf, tid, members=(BEN, FUR), tags=(BUILD_TAG_ID,))
    assert raised == [] and goals(sf, FUR) == ["want"]          # unchanged re-save keeps the drift
    _, raised = save(sf, tid, members=(BEN, FUR, XL), tags=(BUILD_TAG_ID,))
    assert raised == [XL] and goals(sf, FUR, XL) == ["want", "build"]


def test_removals_change_no_goals(sf):
    tid, _ = save(sf, members=(BEN, FUR), tags=(BUILD_TAG_ID,))
    save(sf, tid, members=(BEN,), tags=())                      # remove the tag and a member
    with sf.begin() as s:
        store.delete_team(s, tid)
    assert goals(sf, BEN, FUR) == ["build", "build"]


def test_validation(sf):
    cases = [
        dict(members=()), dict(members=(BEN, FUR, XL, NAH, 1000000507)), dict(members=(BEN, BEN)),
        dict(members=(424242,)), dict(name="   "), dict(name="x" * 61), dict(notes="x" * 2001),
        dict(roles={BEN: "x" * 41}), dict(tags=(999,)),
    ]
    for case in cases:
        with pytest.raises(TeamError) as e:
            save(sf, **case)
        assert e.value.status == 422, case
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(Team)) == 0
    with pytest.raises(TeamError) as e:
        save(sf, team_id=77)
    assert e.value.status == 404 and e.value.message == "Team not found"


def test_traveler_element_ids_saved_and_raw_or_manekin_ids_rejected(sf):
    tid, _ = save(sf, members=(1000000507,))
    assert members_of(sf, tid) == [(0, 1000000507, "")]
    for bad in (10000007, 10000005, 10000117):
        with pytest.raises(TeamError) as e:
            save(sf, members=(bad,))
        assert e.value.status == 422 and "Unknown character" in e.value.message


def test_new_tag_reuses_existing_case_insensitively(sf):
    with sf.begin() as s:
        abyss = store.create_tag(s, "abyss").id
    tid, _ = save(sf, new_tags=("Abyss", "fun", "FUN"))
    with sf() as s:
        names = [t.name for t in s.scalars(select(Tag).order_by(Tag.id))]
        tag_ids = [t.id for t in store.team_rows(s)[0][2]]
    assert names == ["Build", "abyss", "fun"]
    assert abyss in tag_ids and len(tag_ids) == 2


def test_slots_are_contiguous_after_removal(sf):
    tid, _ = save(sf, members=(BEN, FUR, XL))
    save(sf, tid, members=(BEN, XL))
    assert members_of(sf, tid) == [(0, BEN, ""), (1, XL, "")]


def test_new_teams_go_first_and_reorder(sf):
    a, _ = save(sf, name="A")
    b, _ = save(sf, name="B")
    with sf() as s:
        assert [t.name for t, _m, _t in store.team_rows(s)] == ["B", "A"]
    with sf.begin() as s:
        store.reorder(s, [a, b])
    with sf() as s:
        assert [t.name for t, _m, _t in store.team_rows(s)] == ["A", "B"]


def test_reorder_requires_every_team_once(sf):
    a, _ = save(sf, name="A")
    b, _ = save(sf, name="B")
    for ids in ([a], [a, b, 99], [a, a]):
        with pytest.raises(TeamError) as e:
            with sf.begin() as s:
                store.reorder(s, ids)
        assert e.value.status == 422 and e.value.message == "The order must list every team once"


def test_tags(sf):
    with sf.begin() as s:
        fun = store.create_tag(s, " fun ")
        assert fun.name == "fun"
    with pytest.raises(TeamError) as e:
        with sf.begin() as s:
            store.create_tag(s, "FUN")
    assert (e.value.status, e.value.message) == (409, "A tag with that name exists")
    with pytest.raises(TeamError) as e:
        with sf.begin() as s:
            store.create_tag(s, "x", color="black")
    assert e.value.status == 422
    for call in (lambda s: store.update_tag(s, BUILD_TAG_ID, "Farm", None), lambda s: store.delete_tag(s, BUILD_TAG_ID)):
        with pytest.raises(TeamError) as e:
            with sf.begin() as s:
                call(s)
        assert (e.value.status, e.value.message) == (409, "Build is a built-in tag")
    with sf.begin() as s:
        assert store.update_tag(s, BUILD_TAG_ID, None, "blue").color == "blue"
        assert store.update_tag(s, BUILD_TAG_ID, "Build", None).name == "Build"   # same name is not a rename
    tid, _ = save(sf, tags=(fun.id,))
    with sf() as s:
        listed = store.list_tags(s)
    assert [(t["name"], t["team_count"]) for t in listed] == [("Build", 0), ("fun", 1)]
    with sf.begin() as s:
        store.delete_tag(s, fun.id)
    with sf() as s:
        assert store.team_rows(s)[0][2] == []
    with pytest.raises(TeamError) as e:
        with sf.begin() as s:
            store.delete_tag(s, 12345)
    assert (e.value.status, e.value.message) == (404, "Tag not found")


def test_new_tag_colours_cycle(sf):
    with sf.begin() as s:
        colours = [store.create_tag(s, f"t{i}").color for i in range(3)]
    # Build is tag #1, so the next three tags take palette positions 1, 2, 3.
    assert colours == list(store.TAG_COLORS[1:4])


def test_memberships(sf):
    tid, _ = save(sf, name="Abyss", members=(BEN, FUR), tags=(BUILD_TAG_ID,))
    with sf() as s:
        m = store.memberships(s)
    assert m[BEN] == [{"id": tid, "name": "Abyss",
                       "tags": [{"id": 1, "name": "Build", "color": "orange", "builtin": True}]}]
    assert XL not in m


def test_failed_write_rolls_back_everything(sf, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("boom")
    monkeypatch.setattr(store, "raise_to_build", boom)
    with pytest.raises(RuntimeError):
        save(sf, members=(BEN,), tags=(BUILD_TAG_ID,), new_tags=("fresh",))
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(Team)) == 0
        assert s.scalar(select(Tag).where(Tag.name_key == "fresh")) is None
    assert goals(sf, BEN) == ["none"]


def test_palette_accepts_navy_and_gold(sf):
    with sf.begin() as s:
        t = store.create_tag(s, "night", color="navy")
        assert store.update_tag(s, t.id, None, "gold").color == "gold"
