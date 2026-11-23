from sqlalchemy import text

from app.db.engine import make_engine
from test_migration_0007 import NOW, downgrade, upgrade

DEFAULTS = {"abyss": "navy", "theater": "purple", "nuke": "red", "aoe": "yellow", "boss": "gold",
            "exploration": "green", "main": "teal", "fun": "pink"}


def tags(conn):
    return {k: (n, c) for k, n, c in conn.execute(text("SELECT name_key, name, color FROM tag"))}


def test_0009_adds_defaults(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0009")
    with engine.begin() as conn:
        rows = tags(conn)
    assert rows["build"] == ("Build", "orange")
    assert {k: c for k, (_n, c) in rows.items() if k != "build"} == DEFAULTS
    assert rows["aoe"][0] == "AoE" and rows["exploration"][0] == "Exploration"
    engine.dispose()


def test_0009_skips_existing_names(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0008")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO tag (name, name_key, color, builtin) VALUES ('FUN', 'fun', 'blue', 0)"))
    upgrade(engine, "0009")
    with engine.begin() as conn:
        rows = tags(conn)
        count = conn.execute(text("SELECT count(*) FROM tag WHERE name_key = 'fun'")).scalar()
    assert rows["fun"] == ("FUN", "blue") and count == 1
    engine.dispose()


def test_0009_downgrade_keeps_tags_in_use(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0009")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO team (id, name, notes, sort_order, created_at, updated_at) "
                          "VALUES (1, 'T', '', 0, :t, :t)"), {"t": NOW})
        abyss = conn.execute(text("SELECT id FROM tag WHERE name_key = 'abyss'")).scalar()
        conn.execute(text("INSERT INTO team_tag (team_id, tag_id) VALUES (1, :a)"), {"a": abyss})
    downgrade(engine, "0008")
    with engine.begin() as conn:
        assert set(tags(conn)) == {"build", "abyss"}
    engine.dispose()
