from sqlalchemy import inspect, text

from app.db.engine import make_engine
from test_migration_0007 import downgrade, upgrade


def test_0012_adds_columns_and_table(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0011")
    with engine.begin() as c:
        c.execute(text("INSERT INTO character_goal (character_id, goal, updated_at) "
                       "VALUES (10000032, 'build', '2026-11-24 00:00:00')"))
    upgrade(engine, "0012")
    cols = {c["name"] for c in inspect(engine).get_columns("character_goal")}
    assert {"artifact_target", "artifacts_done"} <= cols
    with engine.connect() as c:
        assert c.execute(text("SELECT artifacts_done, artifact_target FROM character_goal")).one() == (0, None)
    dom = {c["name"] for c in inspect(engine).get_columns("game_artifact_domain")}
    assert dom == {"id", "name", "entrance", "region", "elements", "set_ids"}
    engine.dispose()


def test_0012_downgrade(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0012")
    downgrade(engine, "0011")
    cols = {c["name"] for c in inspect(engine).get_columns("character_goal")}
    assert "artifact_target" not in cols and "artifacts_done" not in cols
    assert "game_artifact_domain" not in inspect(engine).get_table_names()
    engine.dispose()
