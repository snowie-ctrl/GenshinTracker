from sqlalchemy import inspect

from app.db.engine import make_engine
from test_migration_0007 import downgrade, upgrade


def test_0011_creates_event_log(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0011")
    cols = {c["name"] for c in inspect(engine).get_columns("event_log")}
    assert cols == {"key", "kind", "name", "start", "end", "image", "description", "calendar_id",
                    "first_seen", "last_seen"}
    engine.dispose()


def test_0011_downgrade(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0011")
    downgrade(engine, "0010")
    assert "event_log" not in inspect(engine).get_table_names()
    engine.dispose()
