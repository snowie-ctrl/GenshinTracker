from dataclasses import replace
from datetime import datetime, timedelta

from app.db.models import (
    CharacterStatRecommendation, GameMaterial, GapRun, LiveNotes, MaterialGap, MaterialTotal, OwnedArtifact,
    OwnedCharacter,
)
from app.sync.backup import backup_db
from app.sync.hoyolab import GapResult, MaterialAmount, NotesInfo, TalentIds
from app.sync.persist import (
    load_talent_ids, save_details, save_gap_failure, save_gaps, save_notes, save_roster, save_talent_ids,
)
from app.sync.recommend import StatRecommendation
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
        save_roster(s, [make_roster(1000000503, raw_id=10000007, name="Traveler", element="Geo")], NOW)
    with session_factory() as s:
        row = s.get(OwnedCharacter, 1000000503)
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


def _catalogue(sf, ids):
    with sf.begin() as s:
        for mid in ids:
            s.add(GameMaterial(id=mid, name=f"M{mid}", icon=f"UI_ItemIcon_{mid}", rarity=3, yatta_type="x",
                               category="talent", sources=[], sort_order=0, detail_fetched=True))


def _result():
    a = MaterialAmount(104302, "Guide to Freedom", "https://act-webstatic.hoyoverse.com/g.png", 3, 9, 4)
    new = MaterialAmount(999001, "Brand New", "https://act-webstatic.hoyoverse.com/n.png", 4, 3, 3)
    spare = MaterialAmount(104301, "Teachings of Freedom", "", 2, 10, 0)
    return GapResult(per_character={10000032: [a], 10000089: [a, new]},
                     total=[MaterialAmount(104302, "Guide to Freedom", "", 3, 18, 7), new], spare=[spare])


def test_save_gaps_replaces_rows_and_reports_unknown_ids(session_factory):
    _catalogue(session_factory, [104301, 104302])
    with session_factory.begin() as s:
        unknown = save_gaps(s, _result(), [[10000032]], ["Traveler"], datetime(2026, 11, 19, 12))
    assert unknown == {999001}
    with session_factory() as s:
        assert s.get(MaterialGap, (10000089, 999001)).short == 3
        total = s.get(MaterialTotal, 104302)
        assert (total.need, total.short, total.spare) == (18, 7, 0)
        assert s.get(MaterialTotal, 104301).spare == 10        # spare-only material kept
        run = s.get(GapRun, 1)
        assert run.ok and run.snapshot == [[10000032]] and run.skipped == ["Traveler"]
    with session_factory.begin() as s:
        save_gaps(s, None, [], [], datetime(2026, 11, 19, 13))
    with session_factory() as s:
        assert s.query(MaterialGap).count() == 0 and s.query(MaterialTotal).count() == 0


def test_save_gap_failure_keeps_last_rows_and_snapshot(session_factory):
    with session_factory.begin() as s:
        save_gaps(s, _result(), [[1]], [], datetime(2026, 11, 19, 12))
    with session_factory.begin() as s:
        save_gap_failure(s, "NoInventoryData: no data", datetime(2026, 11, 19, 13))
    with session_factory() as s:
        run = s.get(GapRun, 1)
        assert run.ok is False and run.error == "NoInventoryData: no data"
        assert run.snapshot == [[1]] and run.computed_at == datetime(2026, 11, 19, 12)
        assert s.query(MaterialTotal).count() > 0


def test_roster_stores_weapon_id_and_notes_store_discounts(session_factory):
    seed_game(session_factory)
    now = datetime(2026, 11, 19, 12)
    notes = NotesInfo(10, 200, 0, 4, 4, 0, 2400, [], weekly_discounts_left=2, weekly_discounts_max=3)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], now)
        save_notes(s, notes, now)
    with session_factory() as s:
        assert s.get(OwnedCharacter, 10000032).weapon_id == 1
        assert s.get(LiveNotes, 1).weekly_discounts_left == 2


def test_talent_id_cache_round_trip(session_factory):
    with session_factory.begin() as s:
        save_talent_ids(s, {10000032: TalentIds(1, 2, 9)})
    with session_factory() as s:
        assert load_talent_ids(s) == {10000032: TalentIds(1, 2, 9)}


def test_save_notes_new_fields(session_factory):
    now = datetime(2026, 11, 22, 12, 0, 0)
    with session_factory.begin() as s:
        save_notes(s, NotesInfo(1, 200, 60, 4, 4, 10, 2400, [], None, None, True, 7200, 0, 5), now)
        row = s.get(LiveNotes, 1)
        assert row.commission_bonus_claimed is True and row.expeditions_max == 5
        assert row.realm_currency_full_at == now + timedelta(hours=2)
        assert row.transformer_ready_at == now
        save_notes(s, NotesInfo(1, 200, 60, 4, 4, 10, 2400, []), now)
        assert row.transformer_ready_at is None and row.realm_currency_full_at is None


REC = StatRecommendation(main={"sands": ["er"], "goblet": ["pyro"], "circlet": ["crit_rate"]}, subs=["er", "crit_rate"])


def test_save_details_stores_recommendation(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], NOW)
        save_details(s, [replace(make_detail(10000032), recommendation=REC)], NOW)
    with session_factory() as s:
        row = s.get(CharacterStatRecommendation, 10000032)
        assert row.data == REC.to_json() and row.synced_at == NOW


def test_save_details_updates_recommendation(session_factory):
    seed_game(session_factory)
    newer = StatRecommendation(main={"sands": ["hp%"], "goblet": [], "circlet": []}, subs=[])
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], NOW)
        save_details(s, [replace(make_detail(10000032), recommendation=REC)], NOW)
        save_details(s, [replace(make_detail(10000032), recommendation=newer)], NOW + timedelta(days=1))
    with session_factory() as s:
        row = s.get(CharacterStatRecommendation, 10000032)
        assert row.data["main"]["sands"] == ["hp%"] and row.synced_at == NOW + timedelta(days=1)


def test_save_details_none_keeps_row(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], NOW)
        save_details(s, [replace(make_detail(10000032), recommendation=REC)], NOW)
        save_details(s, [make_detail(10000032)], NOW + timedelta(days=1))      # field missing this time
    with session_factory() as s:
        row = s.get(CharacterStatRecommendation, 10000032)
        assert row.data == REC.to_json() and row.synced_at == NOW


def test_recommendation_survives_losing_the_character(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032), make_roster(10000089)], NOW)
        save_details(s, [replace(make_detail(10000032), recommendation=REC)], NOW)
        save_roster(s, [make_roster(10000089)], NOW)                            # 10000032 gone
    with session_factory() as s:
        assert s.get(CharacterStatRecommendation, 10000032) is not None
