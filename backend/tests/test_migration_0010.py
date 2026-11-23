from sqlalchemy import inspect, text

from app.db.engine import make_engine
from test_migration_0007 import downgrade, upgrade


def test_0010_adds_columns_kit_table_and_drops_setting(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0009")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO setting (key, value) VALUES ('default_targets', '{\"level\": 90}')"))
        conn.execute(text("INSERT INTO setting (key, value) VALUES ('display_name', '\"x\"')"))
    upgrade(engine, "0010")
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("character_goal")}
    assert {"target_constellation", "target_refinement"} <= cols
    assert {c["name"] for c in insp.get_columns("game_character_kit")} == {"character_id", "data", "fetched_at"}
    with engine.begin() as conn:
        keys = {k for (k,) in conn.execute(text("SELECT key FROM setting"))}
    assert "default_targets" not in keys and "display_name" in keys
    engine.dispose()


def test_0010_downgrade(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0010")
    downgrade(engine, "0009")
    insp = inspect(engine)
    assert "game_character_kit" not in insp.get_table_names()
    assert "target_constellation" not in {c["name"] for c in insp.get_columns("character_goal")}
    engine.dispose()
