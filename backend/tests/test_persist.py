from datetime import datetime, timedelta

from app.db.models import LiveNotes, OwnedArtifact, OwnedCharacter
from app.sync.backup import backup_db
from app.sync.hoyolab import NotesInfo
from app.sync.persist import save_details, save_notes, save_roster
from fakes import NOTES, make_detail, make_roster
from helpers import seed_game

NOW = datetime(2026, 11, 19, 12, 0, 0)


def test_save_roster_upserts_and_reports_unknown(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        unknown = save_roster(s, [make_roster(10000032), make_roster(10000999, name="New")], NOW)
    assert unknown == {10000999}
    with session_factory() as s:
        row = s.get(OwnedCharacter, 10000032)
        assert (row.level, row.weapon_name, row.synced_at) == (80, "The Flute", NOW)
        assert s.get(OwnedCharacter, 10000999).name == "New"


def test_save_roster_removes_characters_no_longer_reported(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032), make_roster(10000089)], NOW)
        save_details(s, [make_detail(10000089)])
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], NOW)
    with session_factory() as s:
        assert s.get(OwnedCharacter, 10000089) is None
        assert s.query(OwnedArtifact).filter_by(character_id=10000089).count() == 0


def test_save_roster_keeps_variant_icon(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000005, raw_id=10000007, name="Traveler", element="Geo")], NOW)
    with session_factory() as s:
        row = s.get(OwnedCharacter, 10000005)
        assert (row.icon, row.element) == ("UI_AvatarIcon_PlayerGirl", "Geo")


def test_save_details_sets_talents_and_replaces_artifacts(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], NOW)
        save_details(s, [make_detail(10000032, talents=(6, 9, 10))])
        save_details(s, [make_detail(10000032, talents=(7, 9, 10))])
        save_details(s, [make_detail(12345678)])  # not owned: ignored
    with session_factory() as s:
        row = s.get(OwnedCharacter, 10000032)
        assert (row.talent_normal, row.talent_skill, row.talent_burst) == (7, 9, 10)
        assert row.stats == [{"name": "HP", "value": "20000"}]
        assert s.query(OwnedArtifact).filter_by(character_id=10000032).count() == 1


def test_save_notes_computes_times(session_factory):
    with session_factory.begin() as s:
        save_notes(s, NOTES, NOW)
    with session_factory() as s:
        n = s.get(LiveNotes, 1)
        assert n.resin_full_at == NOW + timedelta(seconds=3600)
        assert n.expeditions == [{"icon": "https://act-webstatic.hoyoverse.com/e.png",
                                  "finished": False, "return_at": "2026-11-19T14:00:00Z"}]


def test_save_notes_full_resin(session_factory):
    full = NotesInfo(200, 200, 0, 4, 4, 0, 2400, [])
    with session_factory.begin() as s:
        save_notes(s, full, NOW)
    with session_factory() as s:
        assert s.get(LiveNotes, 1).resin_full_at == NOW


def test_backup_rotation_keeps_five(paths, session_factory):
    for i in range(7):
        backup_db(paths.db_file, paths.backups, NOW + timedelta(seconds=i))
    files = sorted(p.name for p in paths.backups.glob("tracker-*.db"))
    assert len(files) == 5
    assert files[-1].startswith("tracker-20261119-120006")


def test_backup_without_database_is_noop(tmp_path):
    assert backup_db(tmp_path / "missing.db", tmp_path / "b", NOW) is None
