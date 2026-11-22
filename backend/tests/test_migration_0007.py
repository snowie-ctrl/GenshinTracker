import json
from datetime import datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db.engine import BACKEND_DIR, make_engine

NOW = "2026-11-22 12:00:00"


def upgrade(engine, rev: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, rev)


def downgrade(engine, rev: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, rev)


def owned(conn, cid, element, icon, talents=(4, 9, 10), cons=2):
    conn.execute(text(
        "INSERT INTO owned_character (character_id, name, element, icon, level, constellation, friendship, "
        "talent_normal, talent_skill, talent_burst, weapon_name, weapon_icon, weapon_rarity, weapon_level, "
        "weapon_refinement, weapon_id, stats, synced_at) VALUES (:c, 'X', :e, :i, 80, :k, 10, :n, :s, :b, "
        "'W', 'w', 4, 90, 1, NULL, '[]', :t)"),
        dict(c=cid, e=element, i=icon, k=cons, n=talents[0], s=talents[1], b=talents[2], t=NOW))


def goal(conn, cid):
    conn.execute(text("INSERT INTO character_goal (character_id, goal, target_level, updated_at) "
                      "VALUES (:c, 'build', 90, :t)"), dict(c=cid, t=NOW))


def team(conn, tid, members):
    conn.execute(text("INSERT INTO team (id, name, notes, sort_order, created_at, updated_at) "
                      "VALUES (:i, 'T', '', 0, :t, :t)"), dict(i=tid, t=NOW))
    for slot, cid in enumerate(members):
        conn.execute(text("INSERT INTO team_member (team_id, slot, character_id, role) VALUES (:t, :s, :c, '')"),
                     dict(t=tid, s=slot, c=cid))


def seeded(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0006")
    with engine.begin() as conn:
        owned(conn, 10000005, "Cryo", "UI_AvatarIcon_PlayerGirl")
        owned(conn, 10000117, "Cryo", "UI_AvatarIcon_MannequinGirl")
        owned(conn, 10000032, "Pyro", "UI_AvatarIcon_Bennett")
        goal(conn, 10000005)
        goal(conn, 10000117)
        team(conn, 1, [10000032, 10000117, 10000005])
        team(conn, 2, [10000117])
        conn.execute(text("INSERT INTO good_weapon (weapon_id, level, ascension, refinement, location, character_id, lock) "
                          "VALUES (11401, 90, 6, 1, 'Manekina', 10000117, 0), (11401, 90, 6, 1, 'Traveler', 10000005, 0)"))
        conn.execute(text("INSERT INTO challenge_run (kind, season, start, \"end\", summary, teams, seen_at, updated_at) "
                          "VALUES ('abyss', '77', NULL, NULL, '{}', :teams, :t, :t)"),
                     dict(teams=json.dumps([[10000005, 10000117, 10000032]]), t=NOW))
        conn.execute(text("INSERT INTO game_meta (key, value) VALUES ('talent_ids', :v)"),
                     dict(v=json.dumps({"10000005": [1, 2, 3], "10000032": [4, 5, 6]})))
    return engine


def test_upgrade_moves_traveler_to_current_element_and_drops_manekin(paths):
    engine = seeded(paths)
    upgrade(engine, "head")
    cryo = 1000000507
    with engine.connect() as conn:
        q = lambda sql: conn.execute(text(sql)).all()  # noqa: E731
        assert q("SELECT character_id FROM character_goal") == [(cryo,)]
        assert q("SELECT team_id, slot, character_id FROM team_member ORDER BY team_id, slot") == [
            (1, 0, 10000032), (1, 1, cryo)]                       # slots closed up
        assert q("SELECT id FROM team") == [(1,)]                  # a Manekin-only team is deleted
        assert q("SELECT location, character_id FROM good_weapon ORDER BY location") == [
            ("Manekina", None), ("Traveler", cryo)]
        assert json.loads(q("SELECT teams FROM challenge_run")[0][0]) == [[cryo, 10000032]]
        assert q("SELECT character_id FROM owned_character") == [(10000032,)]
        row = q("SELECT element_id, seen, unlocked, talent_normal, talent_skill, talent_burst, constellation, source "
                "FROM traveler_element")
        assert row == [(cryo, 1, 0, 4, 9, 10, 2, "sync")]
        settings = dict(q("SELECT key, value FROM setting"))
        assert json.loads(settings["traveler_current_element"]) == "Cryo"
        assert json.loads(settings["traveler_body"]) == "girl"
        assert json.loads(q("SELECT value FROM game_meta WHERE key='talent_ids'")[0][0]) == {"10000032": [4, 5, 6]}
    engine.dispose()


def test_fresh_database_gets_no_invented_traveler(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0006")
    with engine.begin() as conn:
        goal(conn, 10000005)        # a goal without any synced Traveler
    upgrade(engine, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT character_id FROM character_goal")).all() == [(1000000502,)]
        assert conn.execute(text("SELECT count(*) FROM traveler_element")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM setting WHERE key LIKE 'traveler_%'")).scalar() == 0
    engine.dispose()


def test_downgrade_folds_elements_back(paths):
    engine = seeded(paths)
    upgrade(engine, "head")
    with engine.begin() as conn:
        goal(conn, 1000000502)      # a second element goal; the current element's (Cryo) one wins
        team(conn, 3, [1000000502, 10000032, 1000000507])
    downgrade(engine, "0006")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT character_id FROM team_member WHERE team_id=3 ORDER BY slot")).all() == [
            (10000005,), (10000032,)]
        assert conn.execute(text("SELECT character_id FROM character_goal")).all() == [(10000005,)]
        assert conn.execute(text("SELECT character_id FROM team_member WHERE team_id=1 ORDER BY slot")).all() == [
            (10000032,), (10000005,)]
    engine.dispose()
