from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.db.engine import make_engine, migrate
from app.db.models import Base, Setting

TABLES = {
    "game_character", "game_meta", "owned_character", "owned_artifact",
    "live_notes", "sync_run", "character_goal", "setting",
    "game_material", "game_domain", "game_weapon", "material_gap", "material_total",
    "gap_run", "weekly_boss_done",
}


def test_migrate_creates_all_tables(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    assert TABLES <= set(inspect(engine).get_table_names())
    engine.dispose()


def test_phase2_columns_exist(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    cols = {t: {c["name"] for c in inspect(engine).get_columns(t)}
            for t in ("owned_character", "live_notes", "character_goal")}
    assert "weapon_id" in cols["owned_character"]
    assert {"weekly_discounts_left", "weekly_discounts_max"} <= cols["live_notes"]
    assert "planned_weapon_id" in cols["character_goal"]
    engine.dispose()


def test_migrate_is_idempotent(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    migrate(engine)
    engine.dispose()


def test_models_match_migrations(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    with engine.connect() as conn:
        diff = compare_metadata(MigrationContext.configure(conn), Base.metadata)
    engine.dispose()
    assert diff == []


def test_json_round_trip(session_factory):
    with session_factory.begin() as s:
        s.add(Setting(key="default_targets", value={"level": 90}))
    with session_factory() as s:
        assert s.get(Setting, "default_targets").value == {"level": 90}
