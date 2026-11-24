from sqlalchemy import inspect

from app.db.engine import make_engine
from test_migration_0007 import downgrade, upgrade


def test_0013_creates_table(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0013")
    cols = {c["name"] for c in inspect(engine).get_columns("stat_recommendation")}
    assert cols == {"character_id", "data", "synced_at"}
    engine.dispose()


def test_0013_downgrade(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0013")
    downgrade(engine, "0012")
    assert "stat_recommendation" not in inspect(engine).get_table_names()
    engine.dispose()
