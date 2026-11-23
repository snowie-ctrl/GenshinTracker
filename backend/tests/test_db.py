from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.db.engine import make_engine, migrate
from app.db.models import Base, Setting

TABLES = {
    "game_character", "game_meta", "owned_character", "owned_artifact",
    "live_notes", "sync_run", "character_goal", "setting",
    "game_material", "game_domain", "game_weapon", "material_gap", "material_total",
    "gap_run", "weekly_boss_done", "traveler_element",
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
        s.add(Setting(key="display_name", value={"x": 1}))
    with session_factory() as s:
        assert s.get(Setting, "display_name").value == {"x": 1}


def test_phase3_tables_exist(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    insp = inspect(engine)
    assert {"wish", "wish_import", "wish_chart", "game_banner"} <= set(insp.get_table_names())
    cols = {c["name"] for c in insp.get_columns("wish")}
    assert cols == {"pk", "id", "pool", "gacha_type", "time", "seq", "name", "item_id", "item_type",
                    "rarity", "source", "imported_at"}
    engine.dispose()


def test_wish_id_unique_but_nullable(session_factory):
    from datetime import datetime
    import pytest
    from sqlalchemy.exc import IntegrityError
    from app.db.models import Wish

    def row(id_):
        return Wish(id=id_, pool="standard", gacha_type="200", time="2024-01-01 10:00:00", seq=0,
                    name="Slingshot", item_id=None, item_type="weapon", rarity=3, source="paimon",
                    imported_at=datetime(2024, 1, 1))
    with session_factory.begin() as s:
        s.add_all([row(None), row(None)])          # many id-less rows are fine
    with pytest.raises(IntegrityError):
        with session_factory.begin() as s:
            s.add_all([row("1704067200000000001"), row("1704067200000000001")])


def test_paths_create_wish_backups(paths):
    assert paths.wish_backups == paths.backups / "wishes"
    assert paths.wish_backups.is_dir()


def test_phase4_tables_and_build_tag(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    insp = inspect(engine)
    assert {"team", "team_member", "tag", "team_tag"} <= set(insp.get_table_names())
    with engine.connect() as conn:
        row = conn.exec_driver_sql("SELECT id, name, name_key, color, builtin FROM tag WHERE builtin = 1").one()
    engine.dispose()
    assert tuple(row) == (1, "Build", "build", "orange", 1)


def test_team_delete_cascades(session_factory):
    from datetime import datetime

    from sqlalchemy import delete, func, select

    from app.db.models import Team, TeamMember, TeamTag

    now = datetime(2026, 11, 21)
    with session_factory.begin() as s:
        s.add(Team(id=5, name="T", notes="", sort_order=0, created_at=now, updated_at=now))
        s.flush()
        s.add(TeamMember(team_id=5, slot=0, character_id=10000032, role=""))
        s.add(TeamTag(team_id=5, tag_id=1))
    with session_factory.begin() as s:
        s.execute(delete(Team).where(Team.id == 5))
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(TeamMember)) == 0
        assert s.scalar(select(func.count()).select_from(TeamTag)) == 0


def test_phase5_tables_exist(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert {"hoyolab_snapshot", "challenge_run", "event_done"} <= names


def test_default_map_setting(session_factory):
    from app.settings.store import get_setting, set_setting
    with session_factory.begin() as s:
        assert get_setting(s, "default_map") == "hoyolab"
        set_setting(s, "default_map", "appsample")
    with session_factory() as s:
        assert get_setting(s, "default_map") == "appsample"


def test_phase6_tables_exist(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    names = set(inspect(engine).get_table_names())
    assert {"game_artifact_set", "good_import", "good_material", "good_weapon", "good_artifact"} <= names
