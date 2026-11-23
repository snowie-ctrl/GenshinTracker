from sqlalchemy import inspect, text

from app.db.engine import make_engine
from test_migration_0007 import NOW, downgrade, upgrade


def goal(conn, cid, kind):
    conn.execute(text("INSERT INTO character_goal (character_id, goal, target_level, updated_at) "
                      "VALUES (:c, :g, 90, :t)"), dict(c=cid, g=kind, t=NOW))


def test_upgrade_numbers_existing_build_rows_by_id(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0007")
    with engine.begin() as conn:
        goal(conn, 10000089, "build")
        goal(conn, 10000032, "build")
        goal(conn, 10000047, "want")
    upgrade(engine, "0008")
    with engine.begin() as conn:
        rows = dict(conn.execute(text("SELECT character_id, priority FROM character_goal")).all())
    assert rows == {10000032: 1, 10000089: 2, 10000047: None}
    cols = {c["name"] for c in inspect(engine).get_columns("live_notes")}
    assert {"commission_bonus_claimed", "realm_currency_full_at", "transformer_ready_at",
            "expeditions_max"} <= cols
    engine.dispose()


def test_downgrade_drops_columns(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0008")
    downgrade(engine, "0007")
    insp = inspect(engine)
    assert "priority" not in {c["name"] for c in insp.get_columns("character_goal")}
    assert "expeditions_max" not in {c["name"] for c in insp.get_columns("live_notes")}
    engine.dispose()
