from app.db.models import GameMeta, OwnedArtifact, OwnedCharacter, TravelerElement
from app.settings.store import get_setting
from app.sync.persist import save_challenge_runs, save_details, save_roster
from app.sync.chronicle import ChallengeRunInfo
from app.gamedata.traveler import TRAVELER_PENDING
from app.timeutil import utcnow
from app.traveler.store import get_or_create, owned_elements, refresh_owned, resolve
from fakes import make_detail, make_roster
from helpers import seed_game

CRYO, ANEMO, GEO = 1000000507, 1000000502, 1000000503


def sync_cryo(sf, level=80, talents=(4, 9, 10)):
    with sf.begin() as s:
        save_roster(s, [make_roster(10000032, name="Bennett"),
                        make_roster(CRYO, level=level, raw_id=10000007, name="Traveler", element="Cryo")], utcnow())
        save_details(s, [make_detail(10000032), make_detail(CRYO, talents=talents)])


def test_current_element_recorded(session_factory):
    seed_game(session_factory)
    sync_cryo(session_factory)
    with session_factory() as s:
        assert get_setting(s, "traveler_current_element") == "Cryo"
        assert get_setting(s, "traveler_body") == "girl"
        te = s.get(TravelerElement, CRYO)
        assert (te.seen, te.talent_normal, te.talent_skill, te.talent_burst, te.constellation, te.source) == (
            True, 4, 9, 10, 2, "sync")
        assert owned_elements(s) == [CRYO]


def test_unlocked_element_gets_shared_fields_and_its_own_talents(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        te = get_or_create(s, ANEMO)
        te.unlocked, te.talent_normal, te.talent_skill, te.talent_burst, te.constellation = True, 2, 3, 4, 6
    sync_cryo(session_factory, level=90)
    with session_factory() as s:
        a = s.get(OwnedCharacter, ANEMO)
        c = s.get(OwnedCharacter, CRYO)
        assert (a.name, a.element, a.level, a.weapon_name) == ("Anemo Traveler", "Anemo", 90, c.weapon_name)
        assert (a.talent_normal, a.talent_skill, a.talent_burst, a.constellation) == (2, 3, 4, 6)
        assert a.stats == c.stats
        assert [x.set_name for x in s.query(OwnedArtifact).filter_by(character_id=ANEMO)] == ["Noblesse Oblige"]
        assert s.get(OwnedCharacter, 10000032) is not None


def test_switching_element_overwrites_manual_values(session_factory):
    seed_game(session_factory)
    sync_cryo(session_factory)
    with session_factory.begin() as s:
        te = get_or_create(s, GEO)
        te.unlocked, te.talent_normal, te.source = True, 7, "manual"
    with session_factory.begin() as s:
        save_roster(s, [make_roster(GEO, raw_id=10000007, name="Traveler", element="Geo")], utcnow())
        save_details(s, [make_detail(GEO, talents=(1, 2, 3))])
    with session_factory() as s:
        te = s.get(TravelerElement, GEO)
        assert (te.talent_normal, te.talent_skill, te.talent_burst, te.source, te.seen) == (1, 2, 3, "sync", True)
        assert get_setting(s, "traveler_current_element") == "Geo"
        cryo = s.get(OwnedCharacter, CRYO)                     # previous element stays owned with its talents
        assert (cryo.talent_normal, cryo.talent_skill, cryo.talent_burst) == (4, 9, 10)


def test_unknown_element_keeps_previous_rows(session_factory, caplog):
    seed_game(session_factory)
    sync_cryo(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032, name="Bennett"),
                        make_roster(TRAVELER_PENDING, raw_id=10000007, name="Traveler", element="Lunar")], utcnow())
    with session_factory() as s:
        assert s.get(OwnedCharacter, CRYO) is not None
        assert s.get(OwnedCharacter, TRAVELER_PENDING) is None
        assert get_setting(s, "traveler_current_element") == "Cryo"
    assert "Lunar" in caplog.text


def test_body_change_updates_icons_and_clears_talent_cache(session_factory):
    seed_game(session_factory)
    sync_cryo(session_factory)
    with session_factory.begin() as s:
        s.merge(GameMeta(key="talent_ids", value={str(CRYO): [1, 2, 3], "10000032": [4, 5, 6]}))
    with session_factory.begin() as s:
        save_roster(s, [make_roster(CRYO, raw_id=10000005, name="Traveler", element="Cryo")], utcnow())
    with session_factory() as s:
        assert get_setting(s, "traveler_body") == "boy"
        assert s.get(OwnedCharacter, CRYO).icon == "UI_AvatarIcon_PlayerBoy"
        from app.db.models import GameCharacter
        assert s.get(GameCharacter, ANEMO).icon == "UI_AvatarIcon_PlayerBoy"
        assert s.get(GameMeta, "talent_ids").value == {"10000032": [4, 5, 6]}


def test_untick_never_seen_element_removes_owned_row(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        get_or_create(s, ANEMO).unlocked = True
    sync_cryo(session_factory)
    with session_factory.begin() as s:
        s.get(TravelerElement, ANEMO).unlocked = False
        refresh_owned(s, utcnow())
    with session_factory() as s:
        assert s.get(OwnedCharacter, ANEMO) is None
        assert s.query(OwnedArtifact).filter_by(character_id=ANEMO).count() == 0


def test_challenge_teams_resolve_pending_and_drop_none(session_factory):
    seed_game(session_factory)
    sync_cryo(session_factory)
    with session_factory.begin() as s:
        assert resolve(s, TRAVELER_PENDING) == CRYO and resolve(s, 10000032) == 10000032
        save_challenge_runs(s, [ChallengeRunInfo("abyss", "9", None, None, {}, [[TRAVELER_PENDING, 10000032]])],
                            utcnow())
        from app.db.models import ChallengeRun
        assert s.get(ChallengeRun, ("abyss", "9")).teams == [[CRYO, 10000032]]
