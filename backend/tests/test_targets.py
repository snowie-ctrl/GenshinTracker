from datetime import datetime

from app.db.models import CharacterGoal, OwnedCharacter, TravelerElement
from app.domain import Current, Targets
from app.sync.persist import save_details, save_roster
from app.targets import current_for, defaults_for, stored_targets, write_targets
from fakes import make_detail, make_roster
from helpers import seed_game

NOW = datetime(2026, 11, 23)


def test_current_for_owned(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000089, level=90, name="Furina")], NOW)
        save_details(s, [make_detail(10000089, talents=(6, 8, 10))])
    with session_factory() as s:
        assert current_for(s, 10000089) == Current(90, 6, 8, 10, constellation=2, weapon_level=90, refinement=5)
        assert current_for(s, 10000023) is None                      # not owned


def test_current_for_traveler_other_element_uses_shared_level(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(1000000503, raw_id=10000007, name="Traveler", element="Geo", level=80)], NOW)
        s.add(TravelerElement(element_id=1000000502, seen=False, unlocked=True, talent_normal=3, talent_skill=4,
                              talent_burst=5, constellation=1, source="manual", updated_at=NOW))
    with session_factory() as s:
        cur = current_for(s, 1000000502)
        assert (cur.level, cur.normal, cur.skill, cur.burst, cur.constellation) == (80, 3, 4, 5, 1)
        assert current_for(s, 1000000507) is None                    # never seen, not unlocked


def test_defaults_for_unowned(session_factory):
    seed_game(session_factory)
    with session_factory() as s:
        assert defaults_for(s, 10000023) == Targets(90, 6, 9, 9, 90, constellation=0, refinement=1)


def test_write_targets_keeps_stored_wish_targets_when_none(session_factory):
    with session_factory.begin() as s:
        row = CharacterGoal(character_id=1, goal="build", updated_at=NOW)
        s.add(row)
        write_targets(row, Targets(90, 6, 9, 9, 90, constellation=6, refinement=5))
        write_targets(row, Targets(80, 6, 9, 9, 90))                 # no wish targets given
        assert stored_targets(row) == Targets(80, 6, 9, 9, 90, constellation=6, refinement=5)
    assert stored_targets(None) is None
