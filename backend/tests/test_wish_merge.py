from datetime import datetime

from sqlalchemy import select

from app.db.models import GameWeapon, Wish
from app.wishes.merge import backfill_item_ids, merge
from helpers import seed_game
from wishdata import inc

NOW = datetime(2024, 2, 1)
T = "2024-01-10 10:00:00"


def run(sf, rows, source):
    with sf.begin() as s:
        return merge(s, rows, source, NOW)


def stored(sf, pool=None):
    with sf() as s:
        q = select(Wish).order_by(Wish.pool, Wish.time, Wish.seq)
        if pool:
            q = q.where(Wish.pool == pool)
        return list(s.scalars(q))


def test_game_import_then_reimport_adds_nothing(session_factory):
    rows = [inc("1704880800000000002", "weapon", T, "Slingshot", gacha_type="302"),
            inc("1704880800000000001", "weapon", T, "Favonius Sword", 4, "302")]
    r = run(session_factory, rows, "game")
    assert (r.added, r.upgraded, r.skipped) == (2, 0, 0)
    assert [w.name for w in stored(session_factory)] == ["Favonius Sword", "Slingshot"]   # seq by id
    r = run(session_factory, rows, "game")
    assert (r.added, r.upgraded, r.skipped) == (0, 0, 2)


def test_paimon_ten_pull_multiset_counting(session_factory):
    run(session_factory, [inc(None, "weapon", T, "Slingshot", gacha_type="302")], "paimon")
    r = run(session_factory, [inc(None, "weapon", T, "Slingshot", gacha_type="302"),
                              inc(None, "weapon", T, "Slingshot", gacha_type="302")], "paimon")
    assert (r.added, r.skipped) == (1, 1)
    assert len(stored(session_factory)) == 2


def test_paimon_twice_adds_nothing_and_keeps_file_order(session_factory):
    rows = [inc(None, "character", T, "Furina", 5, item_type="character"),
            inc(None, "character", T, "Slingshot"),
            inc(None, "character", T, "Bennett", 4, item_type="character")]
    assert run(session_factory, rows, "paimon").added == 3
    assert run(session_factory, rows, "paimon").added == 0
    assert [w.name for w in stored(session_factory)] == ["Furina", "Slingshot", "Bennett"]


def test_game_upgrades_idless_rows(session_factory):
    run(session_factory, [inc(None, "character", T, "Furina", 5, item_type="character")], "paimon")
    r = run(session_factory, [inc("1704880800000000009", "character", T, "Furina", 5, "301", "character")], "game")
    assert (r.added, r.upgraded) == (0, 1)
    (w,) = stored(session_factory)
    assert (w.id, w.source, w.gacha_type) == ("1704880800000000009", "game", "301")


def test_game_replaces_ids_invented_by_other_trackers(session_factory):
    run(session_factory, [inc("1111111111000000001", "weapon", T, "Slingshot", gacha_type="302")], "uigf")
    r = run(session_factory, [inc("1704880800000000003", "weapon", T, "Slingshot", gacha_type="302")], "game")
    assert (r.added, r.upgraded) == (0, 1)
    assert stored(session_factory)[0].id == "1704880800000000003"


def test_file_with_other_ids_does_not_duplicate_game_rows(session_factory):
    run(session_factory, [inc("1704880800000000003", "weapon", T, "Slingshot", gacha_type="302")], "game")
    r = run(session_factory, [inc("1111111111000000001", "weapon", T, "Slingshot", gacha_type="302")], "uigf")
    assert (r.added, r.skipped) == (0, 1)
    assert stored(session_factory)[0].id == "1704880800000000003"


def test_two_game_pulls_same_key_second_is_inserted(session_factory):
    a = inc("1704880800000000001", "weapon", T, "Slingshot", gacha_type="302")
    b = inc("1704880800000000002", "weapon", T, "Slingshot", gacha_type="302")
    run(session_factory, [a], "game")
    r = run(session_factory, [a, b], "game")
    assert (r.added, r.skipped) == (1, 1)
    assert len(stored(session_factory)) == 2


def test_resolves_item_ids_and_reports_unknown_names(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        s.add(GameWeapon(id=11401, name="Favonius Sword", icon="x", rarity=4, weapon_type="Sword"))
    r = run(session_factory, [inc(None, "weapon", T, "Favonius Sword", 4, "302"),
                              inc(None, "weapon", T, "Brand New Bow", 4, "302")], "paimon")
    assert r.unknown_names == {"Brand New Bow"}
    assert {w.name: w.item_id for w in stored(session_factory)} == {"Favonius Sword": 11401, "Brand New Bow": None}


def test_pools_are_separate(session_factory):
    run(session_factory, [inc(None, "weapon", T, "Slingshot", gacha_type="302")], "paimon")
    r = run(session_factory, [inc(None, "standard", T, "Slingshot", gacha_type="200")], "paimon")
    assert r.added == 1


def test_mixed_input_same_key_empty_db_stores_both(session_factory):
    rows = [inc("1704880800000000001", "weapon", T, "Slingshot", gacha_type="302"),
            inc(None, "weapon", T, "Slingshot", gacha_type="302")]
    r = run(session_factory, rows, "uigf")
    assert (r.added, r.skipped) == (2, 0)
    assert len(stored(session_factory)) == 2


def test_mixed_input_same_key_with_id_row_stored_adds_idless(session_factory):
    run(session_factory, [inc("1704880800000000001", "weapon", T, "Slingshot", gacha_type="302")], "game")
    rows = [inc("1704880800000000001", "weapon", T, "Slingshot", gacha_type="302"),
            inc(None, "weapon", T, "Slingshot", gacha_type="302")]
    r = run(session_factory, rows, "game")
    assert (r.added, r.skipped) == (1, 1)
    assert len(stored(session_factory)) == 2


def test_remerging_mixed_export_adds_nothing(session_factory):
    rows = [inc("1704880800000000001", "weapon", T, "Slingshot", gacha_type="302"),
            inc(None, "weapon", T, "Slingshot", gacha_type="302")]
    assert run(session_factory, rows, "uigf").added == 2
    r = run(session_factory, rows, "uigf")
    assert (r.added, r.upgraded) == (0, 0)
    assert len(stored(session_factory)) == 2


def test_id_stored_in_other_pool_is_skipped_not_inserted(session_factory):
    run(session_factory, [inc("1704880800000000005", "standard", T, "Slingshot", gacha_type="200")], "game")
    r = run(session_factory, [inc("1704880800000000005", "weapon", T, "Slingshot", gacha_type="302")], "game")
    assert (r.added, r.skipped) == (0, 1)
    rows = stored(session_factory)
    assert [(w.pool, w.id) for w in rows] == [("standard", "1704880800000000005")]


def test_non_numeric_id_does_not_break_renumbering(session_factory):
    rows = [inc("abc", "weapon", T, "Slingshot", gacha_type="302"),
            inc("1704880800000000001", "weapon", T, "Favonius Sword", 4, "302")]
    r = run(session_factory, rows, "uigf")
    assert r.added == 2
    assert {w.id for w in stored(session_factory)} == {"abc", "1704880800000000001"}


def test_backfill_item_ids_after_game_data_arrives(session_factory):
    seed_game(session_factory)
    run(session_factory, [inc(None, "weapon", T, "Brand New Bow", 4, "302")], "paimon")
    assert stored(session_factory)[0].item_id is None
    with session_factory.begin() as s:
        s.add(GameWeapon(id=15401, name="Brand New Bow", icon="x", rarity=4, weapon_type="Bow"))
        assert backfill_item_ids(s) == 1
    assert stored(session_factory)[0].item_id == 15401
    with session_factory.begin() as s:
        assert backfill_item_ids(s) == 0


def test_upgrade_of_unresolved_row_reports_unknown_name(session_factory):
    seed_game(session_factory)
    run(session_factory, [inc(None, "weapon", T, "Brand New Bow", 4, "302")], "paimon")
    r = run(session_factory, [inc("1704880800000000009", "weapon", T, "Brand New Bow", 4, "302")], "game")
    assert r.upgraded == 1 and r.unknown_names == {"Brand New Bow"}
