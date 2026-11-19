# Phase 1 — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A locally run web app that syncs the user's Genshin roster from HoYoLAB with no manual entry, shows it grouped by status (building / obtained / wanted / unobtained), lets the user set goals and build targets, and shows live resin/commission data.

**Architecture:** FastAPI backend (`backend/app`) owns all data: SQLite via SQLAlchemy + Alembic, a game-data cache from Yatta, an image cache, and a background sync manager that is the only code calling HoYoLAB (through `genshin.py`). A SvelteKit SPA (`frontend/`, static build) talks only to `/api/*` on the same origin; `run.py` serves both on `127.0.0.1`.

**Tech Stack:** Python 3.12, FastAPI, uvicorn, SQLAlchemy 2, Alembic, httpx, python-dotenv, genshin.py 1.7.32, pytest + pytest-asyncio; SvelteKit 2 + Svelte 5 (runes) + TypeScript, Vite 6, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-19-phase1-foundation-design.md` (parent: `docs/superpowers/specs/2026-11-19-genshintracker-overview-design.md`)

## Global Constraints

- Backend binds to `127.0.0.1` only; default port `8765`, overridable by `PORT` in the environment or `.env`.
- `genshin` is pinned to exactly `1.7.32` (its internal `__version__` prints `1.0.0`; do not "fix" the pin to 1.0.0).
- Cookie values live only in `.env`; they are never returned by any API, logged, or committed. The API exposes only `{status: connected|expired|missing, uid}`.
- `.env`, `.env.*` (except `.env.example`), `data/`, `.e2e-data/`, and build/test output are git-ignored. No game art is committed; tests use fake identifiers only (UID `800000001`, nickname `TestTraveler`).
- Sync never writes `character_goal` or `setting` rows except `setting.hoyolab_status`.
- Status rules: `none`+not owned → unobtained; `none`/`want`+owned → obtained; `want`+not owned → wanted; `build`+not owned → wanted with `prefarming=true`; `build`+owned → building.
- Default targets: level 90, talents 8/8/8, weapon level 90. Default sync interval: 10 minutes. Manual sync at most once per 60 s. Keep 5 database backups. Game data refreshes when older than 7 days.
- Level-cap dropdown values: `[20, 40, 50, 60, 70, 80, 90]` (single constant `LEVEL_CAPS`); API validation accepts levels 1–100, talents 1–10, weapon level 1–90.
- Canonical ids: Traveler `10000005`/`10000007` → `10000005`; Manekin `10000117`/`10000118` → `10000117`.
- Timestamps are stored as naive UTC `datetime`s and serialized as ISO 8601 with a trailing `Z`.
- All backend commands run from `backend/` with the repo-root venv activated (`..\.venv\Scripts\Activate.ps1` in PowerShell). All frontend commands run from `frontend/`.

## Review Focus

1. **Female Traveler / Manekina** (HoYoLAB raw id `10000007`/`10000118`): the single canonical card must show the reported variant's icon and splash, not the male default. → tests in Task 8 (`test_save_roster_keeps_variant_icon`) and Task 11 (`test_traveler_uses_variant_icon_and_element`).
2. **Cookie values pasted with junk** (surrounding spaces, quotes, a `ltoken_v2=` prefix, a trailing `;`): must be cleaned, not rejected or stored dirty. → Task 10 (`test_connect_cleans_pasted_values`).
3. **Owned character missing from game data** (new patch before Yatta updates, or first sync before game data downloads): must render as a placeholder card, not crash or vanish. → Task 11 (`test_owned_character_without_game_data_is_placeholder`).
4. **Existing `.env` content** (comments, `PORT=...`, old cookie keys): connecting must preserve unrelated lines and clear stale optional cookie keys. → Task 4 (`test_update_env_preserves_other_lines`) and Task 10 (`test_connect_clears_stale_optional_keys`).
5. **Resin already full** (recovery time 0): dashboard must show it as full now, not a time in the past or a crash. → Task 8 (`test_save_notes_full_resin`) and Task 18 (`formatDuration(0)` → `'now'`).

---

## File Structure

```
run.py                                  start backend (+ build frontend if missing)
.env.example                            template, empty values
README.md                               setup / run / connect / disclaimer
backend/
  pyproject.toml                        deps, pytest config
  alembic.ini
  migrations/env.py, script.py.mako, versions/0001_initial.py
  app/
    __init__.py
    config.py                           Paths, constants
    timeutil.py                         utcnow(), iso()
    domain.py                           Targets, Current, derive_status, progress, resolve_targets
    schemas.py                          shared pydantic models (TargetsIn)
    context.py                          AppContext, get_ctx, make_source_factory
    main.py                             create_app(), frontend mount
    smoke.py                            live manual check
    devseed.py                          fake data for e2e / demos
    db/__init__.py, models.py, engine.py
    settings/__init__.py, store.py, envfile.py, connect.py
    gamedata/__init__.py, yatta.py, service.py, images.py
    sync/__init__.py, hoyolab.py, persist.py, backup.py, runner.py
    api/__init__.py, settings.py, sync.py, characters.py, dashboard.py, img.py
  tests/
    conftest.py, helpers.py, fakes.py
    fixtures/yatta_avatar.json
    test_*.py
frontend/
  package.json, svelte.config.js, vite.config.ts, tsconfig.json, playwright.config.ts
  e2e/characters.spec.ts
  src/app.html, app.d.ts, app.css
  src/lib/types.ts, api.ts, img.ts, status.ts, syncLabel.ts, time.ts, collapse.ts, sync.svelte.ts
  src/lib/CharacterCard.svelte, GoalSwitch.svelte, TargetsEditor.svelte
  src/lib/*.test.ts
  src/routes/+layout.ts, +layout.svelte, +page.svelte
  src/routes/characters/+page.svelte, characters/[slug]/+page.svelte
  src/routes/settings/+page.svelte
```

---

### Task 1: Backend skeleton and dev environment

**Files:**
- Create: `backend/pyproject.toml`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/timeutil.py`, `backend/app/main.py`, `backend/tests/conftest.py`, `backend/tests/test_health.py`, `.env.example`
- Modify: `.gitignore`

**Interfaces:**
- Produces: `app.config.Paths(root)` with properties `data`, `db_file`, `backups`, `img_cache`, `env_file` and method `ensure()`; `app.config.FRONTEND_BUILD: Path`; `default_paths() -> Paths` (honours env `GT_ROOT`); `offline() -> bool` (env `GT_OFFLINE == "1"`); constants `DEFAULT_PORT=8765`, `LEVEL_CAPS`, `DEFAULT_TARGETS`, `DEFAULT_SYNC_INTERVAL_MINUTES=10`, `MANUAL_SYNC_MIN_SECONDS=60`, `GAMEDATA_MAX_AGE_DAYS=7`, `BACKUPS_KEPT=5`. `app.timeutil.utcnow() -> datetime` (naive UTC), `iso(dt | None) -> str | None`. Pytest fixture `paths`.

- [ ] **Step 1: Create the venv and package files**

`backend/pyproject.toml`:

```toml
[build-system]
requires = ["setuptools>=69"]
build-backend = "setuptools.build_meta"

[project]
name = "genshintracker"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = [
  "fastapi>=0.115,<1",
  "uvicorn[standard]>=0.32",
  "sqlalchemy>=2.0.36,<3",
  "alembic>=1.14,<2",
  "httpx>=0.28,<1",
  "python-dotenv>=1.0",
  "genshin==1.7.32",
]

[project.optional-dependencies]
dev = ["pytest>=8.3", "pytest-asyncio>=0.24"]

[tool.setuptools.packages.find]
include = ["app*"]

[tool.pytest.ini_options]
testpaths = ["tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

`backend/app/__init__.py`: empty file.

Run from the repo root (PowerShell):

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e "backend[dev]"
```

Expected: install finishes; `python -c "import genshin, fastapi"` exits 0.

- [ ] **Step 2: Write the failing test**

`backend/tests/conftest.py`:

```python
import pytest

from app.config import Paths


@pytest.fixture
def paths(tmp_path) -> Paths:
    p = Paths(tmp_path)
    p.ensure()
    return p
```

`backend/tests/test_health.py`:

```python
from fastapi.testclient import TestClient

from app.config import Paths, default_paths
from app.main import create_app
from app.timeutil import iso, utcnow


def test_health():
    client = TestClient(create_app())
    assert client.get("/api/health").json() == {"ok": True}


def test_paths_layout(tmp_path):
    p = Paths(tmp_path)
    p.ensure()
    assert p.db_file == tmp_path / "data" / "tracker.db"
    assert p.env_file == tmp_path / ".env"
    assert p.backups.is_dir() and p.img_cache.is_dir()


def test_default_paths_honours_gt_root(monkeypatch, tmp_path):
    monkeypatch.setenv("GT_ROOT", str(tmp_path))
    assert default_paths().root == tmp_path


def test_iso_is_utc_with_z():
    now = utcnow()
    assert now.tzinfo is None
    assert iso(now).endswith("Z")
    assert iso(None) is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`

- [ ] **Step 4: Write minimal implementation**

`backend/app/config.py`:

```python
"""Filesystem locations and app-wide constants. User data lives under data/ and .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_BUILD = REPO_ROOT / "frontend" / "build"

DEFAULT_PORT = 8765
LEVEL_CAPS = [20, 40, 50, 60, 70, 80, 90]
DEFAULT_TARGETS = {"level": 90, "normal": 8, "skill": 8, "burst": 8, "weapon_level": 90}
DEFAULT_SYNC_INTERVAL_MINUTES = 10
MANUAL_SYNC_MIN_SECONDS = 60
GAMEDATA_MAX_AGE_DAYS = 7
BACKUPS_KEPT = 5


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def db_file(self) -> Path:
        return self.data / "tracker.db"

    @property
    def backups(self) -> Path:
        return self.data / "backups"

    @property
    def img_cache(self) -> Path:
        return self.data / "cache" / "img"

    @property
    def env_file(self) -> Path:
        return self.root / ".env"

    def ensure(self) -> None:
        for d in (self.data, self.backups, self.img_cache):
            d.mkdir(parents=True, exist_ok=True)


def default_paths() -> Paths:
    return Paths(Path(os.environ.get("GT_ROOT", str(REPO_ROOT))))


def offline() -> bool:
    return os.environ.get("GT_OFFLINE") == "1"
```

`backend/app/timeutil.py`:

```python
from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC now — the only form stored in SQLite."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: datetime | None) -> str | None:
    return None if dt is None else dt.replace(microsecond=0).isoformat() + "Z"
```

`backend/app/main.py` (replaced fully in Task 10):

```python
from fastapi import FastAPI


def create_app() -> FastAPI:
    app = FastAPI(title="GenshinTracker")

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    return app
```

`.env.example` (repo root):

```dotenv
# Copy to .env (never commit .env). Easiest: leave cookie fields empty and connect from the
# app's Settings page, which fills them in for you after testing them.
LTUID_V2=
LTOKEN_V2=
LTMID_V2=
ACCOUNT_ID_V2=
ACCOUNT_MID_V2=
COOKIE_TOKEN_V2=
GENSHIN_UID=
GENSHIN_REGION=
# Optional: port for http://127.0.0.1:<PORT> (default 8765)
PORT=
```

Append to `.gitignore`:

```gitignore

# End-to-end test data and frontend test output
.e2e-data/
frontend/test-results/
frontend/playwright-report/
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_health.py -v`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add backend .env.example .gitignore
git commit -m "feat: backend skeleton with config, time helpers, health endpoint"
```

---

### Task 2: Database models and migrations

**Files:**
- Create: `backend/app/db/__init__.py`, `backend/app/db/models.py`, `backend/app/db/engine.py`, `backend/alembic.ini`, `backend/migrations/env.py`, `backend/migrations/script.py.mako`, `backend/migrations/versions/0001_initial.py`, `backend/tests/test_db.py`
- Modify: `backend/tests/conftest.py`

**Interfaces:**
- Consumes: `Paths` (Task 1).
- Produces: models `GameCharacter`, `GameMeta`, `OwnedCharacter`, `OwnedArtifact`, `LiveNotes`, `SyncRun`, `CharacterGoal`, `Setting` (columns exactly as below); `make_engine(db_file: Path) -> Engine`; `migrate(engine) -> None`; `make_session_factory(engine) -> sessionmaker`. Pytest fixture `session_factory`.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/conftest.py`:

```python
from app.db.engine import make_engine, make_session_factory, migrate


@pytest.fixture
def session_factory(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    yield make_session_factory(engine)
    engine.dispose()
```

`backend/tests/test_db.py`:

```python
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect

from app.db.engine import make_engine, migrate
from app.db.models import Base, Setting

TABLES = {
    "game_character", "game_meta", "owned_character", "owned_artifact",
    "live_notes", "sync_run", "character_goal", "setting",
}


def test_migrate_creates_all_tables(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    assert TABLES <= set(inspect(engine).get_table_names())
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.db'`

- [ ] **Step 3: Write the models**

`backend/app/db/__init__.py`: empty file.

`backend/app/db/models.py`:

```python
"""SQLite tables. Three categories: game data, account data (overwritten by sync), user data."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# --- game data -------------------------------------------------------------
class GameCharacter(Base):
    __tablename__ = "game_character"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True)
    rarity: Mapped[int] = mapped_column(Integer)
    element: Mapped[str | None] = mapped_column(String, nullable=True)
    weapon_type: Mapped[str] = mapped_column(String)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    icon: Mapped[str] = mapped_column(String)
    splash: Mapped[str] = mapped_column(String)
    release_at: Mapped[datetime] = mapped_column(DateTime)


class GameMeta(Base):
    __tablename__ = "game_meta"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[object | None] = mapped_column(JSON, nullable=True)


# --- account data (sync overwrites) ----------------------------------------
class OwnedCharacter(Base):
    __tablename__ = "owned_character"
    character_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    element: Mapped[str | None] = mapped_column(String, nullable=True)
    icon: Mapped[str | None] = mapped_column(String, nullable=True)
    level: Mapped[int] = mapped_column(Integer)
    constellation: Mapped[int] = mapped_column(Integer)
    friendship: Mapped[int] = mapped_column(Integer)
    talent_normal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    talent_skill: Mapped[int | None] = mapped_column(Integer, nullable=True)
    talent_burst: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weapon_name: Mapped[str] = mapped_column(String)
    weapon_icon: Mapped[str] = mapped_column(String)
    weapon_rarity: Mapped[int] = mapped_column(Integer)
    weapon_level: Mapped[int] = mapped_column(Integer)
    weapon_refinement: Mapped[int] = mapped_column(Integer)
    stats: Mapped[list] = mapped_column(JSON)
    synced_at: Mapped[datetime] = mapped_column(DateTime)


class OwnedArtifact(Base):
    __tablename__ = "owned_artifact"
    character_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    set_name: Mapped[str] = mapped_column(String)
    rarity: Mapped[int] = mapped_column(Integer)
    level: Mapped[int] = mapped_column(Integer)
    main_stat: Mapped[str] = mapped_column(String)
    substats: Mapped[list] = mapped_column(JSON)
    icon: Mapped[str] = mapped_column(String)


class LiveNotes(Base):
    __tablename__ = "live_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resin: Mapped[int] = mapped_column(Integer)
    resin_max: Mapped[int] = mapped_column(Integer)
    resin_full_at: Mapped[datetime] = mapped_column(DateTime)
    commissions_done: Mapped[int] = mapped_column(Integer)
    commissions_max: Mapped[int] = mapped_column(Integer)
    realm_currency: Mapped[int] = mapped_column(Integer)
    realm_currency_max: Mapped[int] = mapped_column(Integer)
    expeditions: Mapped[list] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)


class SyncRun(Base):
    __tablename__ = "sync_run"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trigger: Mapped[str] = mapped_column(String)
    parts: Mapped[dict] = mapped_column(JSON)


# --- user data (sync never writes, except setting.hoyolab_status) ----------
class CharacterGoal(Base):
    __tablename__ = "character_goal"
    character_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal: Mapped[str] = mapped_column(String)
    target_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_normal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_skill: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_burst: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_weapon_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class Setting(Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[object | None] = mapped_column(JSON, nullable=True)
```

- [ ] **Step 4: Write the engine and Alembic files**

`backend/app/db/engine.py`:

```python
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import Engine, create_engine, event
from sqlalchemy.orm import sessionmaker

BACKEND_DIR = Path(__file__).resolve().parents[2]


def make_engine(db_file: Path) -> Engine:
    db_file.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}", connect_args={"check_same_thread": False}
    )

    @event.listens_for(engine, "connect")
    def _pragmas(dbapi_conn, _record):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    return engine


def migrate(engine: Engine) -> None:
    """Bring the database to the latest schema. Safe to call on every startup."""
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, "head")


def make_session_factory(engine: Engine) -> sessionmaker:
    return sessionmaker(engine, expire_on_commit=False)
```

`backend/alembic.ini`:

```ini
[alembic]
script_location = migrations
sqlalchemy.url = sqlite:///../data/tracker.db
```

`backend/migrations/env.py`:

```python
from alembic import context
from sqlalchemy import create_engine

from app.db.models import Base

config = context.config
target_metadata = Base.metadata


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:  # plain `alembic` CLI use (e.g. `alembic revision --autogenerate`)
    with create_engine(config.get_main_option("sqlalchemy.url")).connect() as conn:
        _run(conn)
```

`backend/migrations/script.py.mako`:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}
"""
from alembic import op
import sqlalchemy as sa
${imports if imports else ""}

revision = ${repr(up_revision)}
down_revision = ${repr(down_revision)}
branch_labels = ${repr(branch_labels)}
depends_on = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

`backend/migrations/versions/0001_initial.py`:

```python
"""initial schema

Revision ID: 0001
Revises:
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_character",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("slug", sa.String(), nullable=False, unique=True),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("element", sa.String(), nullable=True),
        sa.Column("weapon_type", sa.String(), nullable=False),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("splash", sa.String(), nullable=False),
        sa.Column("release_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "game_meta",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=True),
    )
    op.create_table(
        "owned_character",
        sa.Column("character_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("element", sa.String(), nullable=True),
        sa.Column("icon", sa.String(), nullable=True),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("constellation", sa.Integer(), nullable=False),
        sa.Column("friendship", sa.Integer(), nullable=False),
        sa.Column("talent_normal", sa.Integer(), nullable=True),
        sa.Column("talent_skill", sa.Integer(), nullable=True),
        sa.Column("talent_burst", sa.Integer(), nullable=True),
        sa.Column("weapon_name", sa.String(), nullable=False),
        sa.Column("weapon_icon", sa.String(), nullable=False),
        sa.Column("weapon_rarity", sa.Integer(), nullable=False),
        sa.Column("weapon_level", sa.Integer(), nullable=False),
        sa.Column("weapon_refinement", sa.Integer(), nullable=False),
        sa.Column("stats", sa.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "owned_artifact",
        sa.Column("character_id", sa.Integer(), primary_key=True),
        sa.Column("slot", sa.Integer(), primary_key=True),
        sa.Column("set_name", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("main_stat", sa.String(), nullable=False),
        sa.Column("substats", sa.JSON(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
    )
    op.create_table(
        "live_notes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("resin", sa.Integer(), nullable=False),
        sa.Column("resin_max", sa.Integer(), nullable=False),
        sa.Column("resin_full_at", sa.DateTime(), nullable=False),
        sa.Column("commissions_done", sa.Integer(), nullable=False),
        sa.Column("commissions_max", sa.Integer(), nullable=False),
        sa.Column("realm_currency", sa.Integer(), nullable=False),
        sa.Column("realm_currency_max", sa.Integer(), nullable=False),
        sa.Column("expeditions", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "sync_run",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("trigger", sa.String(), nullable=False),
        sa.Column("parts", sa.JSON(), nullable=False),
    )
    op.create_table(
        "character_goal",
        sa.Column("character_id", sa.Integer(), primary_key=True),
        sa.Column("goal", sa.String(), nullable=False),
        sa.Column("target_level", sa.Integer(), nullable=True),
        sa.Column("target_normal", sa.Integer(), nullable=True),
        sa.Column("target_skill", sa.Integer(), nullable=True),
        sa.Column("target_burst", sa.Integer(), nullable=True),
        sa.Column("target_weapon_level", sa.Integer(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "setting",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("value", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    for table in (
        "setting", "character_goal", "sync_run", "live_notes",
        "owned_artifact", "owned_character", "game_meta", "game_character",
    ):
        op.drop_table(table)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_db.py -v`
Expected: 4 passed. If `test_models_match_migrations` reports a difference, fix whichever of `models.py` / `0001_initial.py` disagrees with the column list in the spec §4 — they must match exactly.

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: SQLite models and initial Alembic migration"
```

---

### Task 3: Domain rules (status, progress, targets)

**Files:**
- Create: `backend/app/domain.py`, `backend/app/schemas.py`, `backend/tests/test_domain.py`

**Interfaces:**
- Produces:
  - `GOALS = ("none", "want", "build")`
  - `@dataclass(frozen=True) Targets(level, normal, skill, burst, weapon_level)` with `from_dict(d) -> Targets`, `to_dict() -> dict`
  - `@dataclass(frozen=True) Current(level: int, normal: int | None, skill: int | None, burst: int | None)`
  - `derive_status(owned: bool, goal: str) -> tuple[str, bool]` → `(status, prefarming)`
  - `progress(current: Current, targets: Targets) -> float` (0–1, 4 decimals)
  - `resolve_targets(goal: str, stored: Targets | None, defaults: Targets) -> Targets | None`
  - `app.schemas.TargetsIn` pydantic model (level 1–100, talents 1–10, weapon_level 1–90)

- [ ] **Step 1: Write the failing test**

`backend/tests/test_domain.py`:

```python
import pytest
from pydantic import ValidationError

from app.domain import Current, Targets, derive_status, progress, resolve_targets
from app.schemas import TargetsIn

DEFAULTS = Targets(level=90, normal=8, skill=8, burst=8, weapon_level=90)


@pytest.mark.parametrize(
    ("owned", "goal", "expected"),
    [
        (False, "none", ("unobtained", False)),
        (False, "want", ("wanted", False)),
        (False, "build", ("wanted", True)),
        (True, "none", ("obtained", False)),
        (True, "want", ("obtained", False)),
        (True, "build", ("building", False)),
    ],
)
def test_derive_status_all_six(owned, goal, expected):
    assert derive_status(owned, goal) == expected


def test_derive_status_rejects_unknown_goal():
    with pytest.raises(ValueError):
        derive_status(True, "maybe")


def test_progress_averages_level_and_talents():
    cur = Current(level=45, normal=4, skill=8, burst=8)
    assert progress(cur, DEFAULTS) == pytest.approx((0.5 + 0.5 + 1 + 1) / 4)


def test_progress_target_at_or_below_current_counts_full():
    cur = Current(level=90, normal=10, skill=9, burst=8)
    assert progress(cur, DEFAULTS) == 1.0


def test_progress_unknown_talents_count_as_one():
    cur = Current(level=90, normal=None, skill=None, burst=None)
    assert progress(cur, DEFAULTS) == pytest.approx((1 + 3 * (1 / 8)) / 4)


def test_resolve_targets_build_without_stored_uses_defaults():
    assert resolve_targets("build", None, DEFAULTS) == DEFAULTS


def test_resolve_targets_keeps_stored_when_leaving_build():
    stored = Targets(80, 6, 6, 6, 80)
    assert resolve_targets("want", stored, DEFAULTS) == stored
    assert resolve_targets("build", stored, DEFAULTS) == stored


def test_resolve_targets_none_without_stored():
    assert resolve_targets("none", None, DEFAULTS) is None


def test_targets_dict_round_trip():
    assert Targets.from_dict(DEFAULTS.to_dict()) == DEFAULTS


def test_targets_in_validates_ranges():
    TargetsIn(level=90, normal=10, skill=1, burst=8, weapon_level=90)
    with pytest.raises(ValidationError):
        TargetsIn(level=90, normal=11, skill=1, burst=8, weapon_level=90)
    with pytest.raises(ValidationError):
        TargetsIn(level=0, normal=1, skill=1, burst=1, weapon_level=1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_domain.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.domain'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/domain.py`:

```python
"""Pure rules shared by the API: status derivation, progress, target defaults."""
from __future__ import annotations

from dataclasses import asdict, dataclass

GOALS = ("none", "want", "build")


@dataclass(frozen=True)
class Targets:
    level: int
    normal: int
    skill: int
    burst: int
    weapon_level: int

    @classmethod
    def from_dict(cls, d: dict) -> Targets:
        return cls(
            level=int(d["level"]),
            normal=int(d["normal"]),
            skill=int(d["skill"]),
            burst=int(d["burst"]),
            weapon_level=int(d["weapon_level"]),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Current:
    level: int
    normal: int | None
    skill: int | None
    burst: int | None


def derive_status(owned: bool, goal: str) -> tuple[str, bool]:
    """Return (status, prefarming). Ownership comes from sync; intent from the goal."""
    if goal not in GOALS:
        raise ValueError(f"unknown goal: {goal!r}")
    if owned:
        return ("building", False) if goal == "build" else ("obtained", False)
    if goal == "none":
        return ("unobtained", False)
    return ("wanted", goal == "build")


def progress(current: Current, targets: Targets) -> float:
    """Average of level and three talents, each counted up to its target (weapon excluded)."""
    pairs = [
        (current.level, targets.level),
        (current.normal or 1, targets.normal),
        (current.skill or 1, targets.skill),
        (current.burst or 1, targets.burst),
    ]
    parts = [1.0 if target <= cur else cur / target for cur, target in pairs]
    return round(sum(parts) / len(parts), 4)


def resolve_targets(goal: str, stored: Targets | None, defaults: Targets) -> Targets | None:
    """Targets to keep after a goal change. Choosing build fills defaults once; stored targets survive."""
    if goal == "build" and stored is None:
        return defaults
    return stored
```

`backend/app/schemas.py`:

```python
from pydantic import BaseModel, Field


class TargetsIn(BaseModel):
    level: int = Field(ge=1, le=100)
    normal: int = Field(ge=1, le=10)
    skill: int = Field(ge=1, le=10)
    burst: int = Field(ge=1, le=10)
    weapon_level: int = Field(ge=1, le=90)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_domain.py -v`
Expected: 15 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: status, progress, and target rules"
```

---

### Task 4: Settings store and `.env` handling

**Files:**
- Create: `backend/app/settings/__init__.py`, `backend/app/settings/store.py`, `backend/app/settings/envfile.py`, `backend/tests/test_settings_store.py`

**Interfaces:**
- Consumes: `Setting` model, `session_factory` fixture (Task 2), `Targets` (Task 3), config defaults (Task 1).
- Produces:
  - `store.get_setting(session, key) -> object`, `store.set_setting(session, key, value) -> None` (keys: `sync_interval_minutes`, `default_targets`, `hoyolab_status`; unknown key → `KeyError`), `store.default_targets(session) -> Targets`
  - `envfile.COOKIE_KEYS` tuple; `read_env(path) -> dict[str, str]` (non-empty values only); `update_env(path, values: dict[str, str]) -> None`; `cookies_from_env(env) -> dict[str, str]` (lowercase cookie names); `connection_status(env, stored_status) -> dict` → `{"status": "connected"|"expired"|"missing", "uid": int|None}`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_settings_store.py`:

```python
import pytest

from app.domain import Targets
from app.settings.envfile import (
    connection_status, cookies_from_env, read_env, update_env,
)
from app.settings.store import default_targets, get_setting, set_setting


def test_defaults_when_unset(session_factory):
    with session_factory() as s:
        assert get_setting(s, "sync_interval_minutes") == 10
        assert get_setting(s, "hoyolab_status") is None
        assert default_targets(s) == Targets(90, 8, 8, 8, 90)


def test_set_and_get(session_factory):
    with session_factory.begin() as s:
        set_setting(s, "sync_interval_minutes", 30)
        set_setting(s, "sync_interval_minutes", 15)
    with session_factory() as s:
        assert get_setting(s, "sync_interval_minutes") == 15


def test_unknown_key_rejected(session_factory):
    with session_factory() as s, pytest.raises(KeyError):
        set_setting(s, "nope", 1)


def test_default_value_is_a_copy(session_factory):
    with session_factory() as s:
        get_setting(s, "default_targets")["level"] = 1
        assert get_setting(s, "default_targets")["level"] == 90


def test_update_env_preserves_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# my comment\nPORT=9000\nLTOKEN_V2=old\nCOOKIE_TOKEN_V2=stale\n", encoding="utf-8")
    update_env(env, {"LTOKEN_V2": "new", "LTUID_V2": "123", "COOKIE_TOKEN_V2": ""})
    text = env.read_text(encoding="utf-8")
    assert "# my comment" in text and "PORT=9000" in text
    assert read_env(env) == {"PORT": "9000", "LTOKEN_V2": "new", "LTUID_V2": "123"}


def test_update_env_creates_file(tmp_path):
    env = tmp_path / ".env"
    update_env(env, {"GENSHIN_UID": "800000001"})
    assert read_env(env) == {"GENSHIN_UID": "800000001"}


def test_cookies_from_env():
    env = {"LTUID_V2": "1", "LTOKEN_V2": "t", "PORT": "1"}
    assert cookies_from_env(env) == {"ltuid_v2": "1", "ltoken_v2": "t"}


@pytest.mark.parametrize(
    ("env", "stored", "expected"),
    [
        ({}, None, {"status": "missing", "uid": None}),
        ({"LTUID_V2": "1"}, None, {"status": "missing", "uid": None}),
        ({"LTUID_V2": "1", "LTOKEN_V2": "t", "GENSHIN_UID": "800000001"}, "connected",
         {"status": "connected", "uid": 800000001}),
        ({"LTUID_V2": "1", "LTOKEN_V2": "t", "GENSHIN_UID": "800000001"}, "expired",
         {"status": "expired", "uid": 800000001}),
    ],
)
def test_connection_status(env, stored, expected):
    assert connection_status(env, stored) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_settings_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.settings'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/settings/__init__.py`: empty file.

`backend/app/settings/store.py`:

```python
import copy

from sqlalchemy.orm import Session

from app.config import DEFAULT_SYNC_INTERVAL_MINUTES, DEFAULT_TARGETS
from app.db.models import Setting
from app.domain import Targets

DEFAULTS: dict[str, object] = {
    "sync_interval_minutes": DEFAULT_SYNC_INTERVAL_MINUTES,
    "default_targets": DEFAULT_TARGETS,
    "hoyolab_status": None,  # None | "connected" | "expired"
}


def get_setting(session: Session, key: str) -> object:
    row = session.get(Setting, key)
    return row.value if row is not None else copy.deepcopy(DEFAULTS[key])


def set_setting(session: Session, key: str, value: object) -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    session.flush()


def default_targets(session: Session) -> Targets:
    return Targets.from_dict(get_setting(session, "default_targets"))
```

`backend/app/settings/envfile.py`:

```python
"""Read/write the local .env. Values here are secrets: never log or return them."""
from pathlib import Path

from dotenv import dotenv_values

COOKIE_KEYS = (
    "ltuid_v2", "ltoken_v2", "ltmid_v2", "account_id_v2", "account_mid_v2", "cookie_token_v2",
)


def read_env(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    return {k: v for k, v in dotenv_values(path).items() if v}


def update_env(path: Path, values: dict[str, str]) -> None:
    """Set the given keys, keep every other line (comments, PORT, ...) untouched."""
    lines = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    remaining = dict(values)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        key = stripped.split("=", 1)[0].strip() if "=" in stripped and not stripped.startswith("#") else None
        if key is not None and key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    out.extend(f"{k}={v}" for k, v in remaining.items())
    path.write_text("\n".join(out) + "\n", encoding="utf-8")


def cookies_from_env(env: dict[str, str]) -> dict[str, str]:
    return {k: env[k.upper()] for k in COOKIE_KEYS if env.get(k.upper())}


def connection_status(env: dict[str, str], stored_status: object) -> dict:
    if not (env.get("LTUID_V2") and env.get("LTOKEN_V2")):
        return {"status": "missing", "uid": None}
    uid = int(env["GENSHIN_UID"]) if env.get("GENSHIN_UID") else None
    return {"status": "expired" if stored_status == "expired" else "connected", "uid": uid}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_settings_store.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: settings store and .env read/write"
```

---

### Task 5: Game data from Yatta

**Files:**
- Create: `backend/app/gamedata/__init__.py`, `backend/app/gamedata/yatta.py`, `backend/app/gamedata/service.py`, `backend/tests/fixtures/yatta_avatar.json`, `backend/tests/helpers.py`, `backend/tests/test_gamedata.py`

**Interfaces:**
- Consumes: `GameCharacter`, `GameMeta` (Task 2); `utcnow`, `iso` (Task 1); `GAMEDATA_MAX_AGE_DAYS`.
- Produces:
  - `yatta.TRAVELER_ID = 10000005`, `yatta.MANEKIN_ID = 10000117`, `yatta.VARIANT_ICONS: dict[int, str]` (raw id → icon), `canonical_id(raw: int | str) -> int`, `splash_for(icon: str) -> str`, `slugify(name) -> str`, `@dataclass CharacterData(id, name, slug, rarity, element, weapon_type, region, icon, splash, release_at)`, `parse_avatar_list(payload: dict) -> list[CharacterData]`, `async fetch_avatar_list(http: httpx.AsyncClient) -> list[CharacterData]`, `YATTA_AVATAR_URL`
  - `service.async refresh(session_factory, http, now=None, force=False) -> bool`; `service.needs_refresh(session, now) -> bool`; `service.gamedata_status(session) -> {"fetched_at": str|None, "last_error": str|None, "count": int}`
  - `tests/helpers.py`: `load_fixture(name) -> dict`, `yatta_transport() -> httpx.MockTransport`, `seed_game(session_factory, rows=GAME_ROWS)`

- [ ] **Step 1: Create the fixture and helpers**

`backend/tests/fixtures/yatta_avatar.json` (trimmed public data in Yatta's shape; one future-dated character):

```json
{
  "response": 200,
  "data": {
    "items": {
      "10000032": {"id": 10000032, "rank": 4, "name": "Bennett", "element": "Fire", "weaponType": "WEAPON_SWORD_ONE_HAND", "region": "MONDSTADT", "icon": "UI_AvatarIcon_Bennett", "release": 1601244000},
      "10000089": {"id": 10000089, "rank": 5, "name": "Furina", "element": "Water", "weaponType": "WEAPON_SWORD_ONE_HAND", "region": "FONTAINE", "icon": "UI_AvatarIcon_Furina", "release": 1699398000},
      "10000052": {"id": 10000052, "rank": 5, "name": "Raiden Shogun", "element": "Electric", "weaponType": "WEAPON_POLE", "region": "INAZUMA", "icon": "UI_AvatarIcon_Shougun", "release": 1630447200},
      "10000005-anemo": {"id": "10000005-anemo", "rank": 5, "name": "Traveler", "element": "Wind", "weaponType": "WEAPON_SWORD_ONE_HAND", "region": "", "icon": "UI_AvatarIcon_PlayerBoy", "release": 1601244000},
      "10000005-pyro": {"id": "10000005-pyro", "rank": 5, "name": "Traveler", "element": "Fire", "weaponType": "WEAPON_SWORD_ONE_HAND", "region": "", "icon": "UI_AvatarIcon_PlayerBoy", "release": 1735758000},
      "10000007-geo": {"id": "10000007-geo", "rank": 5, "name": "Traveler", "element": "Rock", "weaponType": "WEAPON_SWORD_ONE_HAND", "region": "", "icon": "UI_AvatarIcon_PlayerGirl", "release": 1601244000},
      "10000117": {"id": 10000117, "rank": 5, "name": "Manekin", "element": null, "weaponType": "WEAPON_SWORD_ONE_HAND", "region": "", "icon": "UI_AvatarIcon_MannequinBoy", "release": 1760994000},
      "10000118": {"id": 10000118, "rank": 5, "name": "Manekina", "element": null, "weaponType": "WEAPON_SWORD_ONE_HAND", "region": "", "icon": "UI_AvatarIcon_MannequinGirl", "release": 1760994000},
      "10000999": {"id": 10000999, "rank": 5, "name": "Futurechar", "element": "Ice", "weaponType": "WEAPON_CATALYST", "region": "SNEZHNAYA", "icon": "UI_AvatarIcon_Futurechar", "release": 4102444800}
    }
  }
}
```

`backend/tests/helpers.py`:

```python
import json
from datetime import datetime
from pathlib import Path

import httpx

from app.db.models import GameCharacter

FIXTURES = Path(__file__).parent / "fixtures"

# (id, name, slug, rarity, element, weapon_type, icon)
GAME_ROWS = [
    (10000032, "Bennett", "bennett", 4, "Pyro", "Sword", "UI_AvatarIcon_Bennett"),
    (10000089, "Furina", "furina", 5, "Hydro", "Sword", "UI_AvatarIcon_Furina"),
    (10000023, "Xiangling", "xiangling", 4, "Pyro", "Polearm", "UI_AvatarIcon_Xiangling"),
    (10000073, "Nahida", "nahida", 5, "Dendro", "Catalyst", "UI_AvatarIcon_Nahida"),
    (10000005, "Traveler", "traveler", 5, None, "Sword", "UI_AvatarIcon_PlayerBoy"),
]


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def yatta_transport(status: int = 200) -> httpx.MockTransport:
    payload = load_fixture("yatta_avatar.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/avatar"):
            return httpx.Response(status, json=payload if status == 200 else {})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def seed_game(session_factory, rows=GAME_ROWS, release: datetime = datetime(2020, 9, 28)) -> None:
    with session_factory.begin() as s:
        for cid, name, slug, rarity, element, weapon, icon in rows:
            s.merge(GameCharacter(
                id=cid, name=name, slug=slug, rarity=rarity, element=element, weapon_type=weapon,
                region=None, icon=icon, splash=icon.replace("UI_AvatarIcon_", "UI_Gacha_AvatarImg_"),
                release_at=release,
            ))
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_gamedata.py`:

```python
from datetime import datetime, timedelta

import httpx

from app.db.models import GameCharacter
from app.gamedata.service import gamedata_status, needs_refresh, refresh
from app.gamedata.yatta import canonical_id, parse_avatar_list, splash_for
from helpers import load_fixture, yatta_transport

NOW = datetime(2026, 11, 19, 12, 0, 0)


def test_canonical_id():
    assert canonical_id("10000005-anemo") == 10000005
    assert canonical_id(10000007) == 10000005
    assert canonical_id(10000118) == 10000117
    assert canonical_id(10000032) == 10000032


def test_parse_collapses_variants_and_maps_names():
    chars = {c.id: c for c in parse_avatar_list(load_fixture("yatta_avatar.json"))}
    assert set(chars) == {10000032, 10000089, 10000052, 10000005, 10000117, 10000999}
    trav = chars[10000005]
    assert (trav.name, trav.slug, trav.element, trav.icon) == ("Traveler", "traveler", None, "UI_AvatarIcon_PlayerBoy")
    assert trav.release_at == datetime(2020, 9, 27, 22, 0)  # earliest variant
    assert chars[10000117].name == "Manekin"
    raiden = chars[10000052]
    assert (raiden.element, raiden.weapon_type, raiden.slug) == ("Electro", "Polearm", "raiden-shogun")
    assert raiden.splash == "UI_Gacha_AvatarImg_Shougun"


def test_splash_for():
    assert splash_for("UI_AvatarIcon_Bennett") == "UI_Gacha_AvatarImg_Bennett"


async def test_refresh_stores_rows_and_meta(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh(session_factory, http, now=NOW) is True
    with session_factory() as s:
        assert s.get(GameCharacter, 10000032).element == "Pyro"
        status = gamedata_status(s)
        assert status == {"fetched_at": "2026-11-19T12:00:00Z", "last_error": None, "count": 6}


async def test_refresh_skipped_when_fresh_and_forced_when_asked(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh(session_factory, http, now=NOW)
        assert await refresh(session_factory, http, now=NOW + timedelta(days=1)) is False
        assert await refresh(session_factory, http, now=NOW + timedelta(days=1), force=True) is True


def test_needs_refresh_after_seven_days(session_factory):
    with session_factory() as s:
        assert needs_refresh(s, NOW) is True


async def test_refresh_failure_keeps_old_rows_and_records_error(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh(session_factory, http, now=NOW)
    async with httpx.AsyncClient(transport=yatta_transport(status=503)) as http:
        assert await refresh(session_factory, http, now=NOW, force=True) is False
    with session_factory() as s:
        status = gamedata_status(s)
        assert status["count"] == 6
        assert "503" in status["last_error"]
        assert status["fetched_at"] == "2026-11-19T12:00:00Z"
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_gamedata.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.gamedata'`

- [ ] **Step 4: Write minimal implementation**

`backend/app/gamedata/__init__.py`: empty file.

`backend/app/gamedata/yatta.py`:

```python
"""Character list from Yatta (gi.yatta.moe), normalised to our ids and display names."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

YATTA_AVATAR_URL = "https://gi.yatta.moe/api/v2/en/avatar"

TRAVELER_ID = 10000005
MANEKIN_ID = 10000117
_ALIASES = {10000005: TRAVELER_ID, 10000007: TRAVELER_ID, 10000117: MANEKIN_ID, 10000118: MANEKIN_ID}
VARIANT_ICONS = {
    10000005: "UI_AvatarIcon_PlayerBoy",
    10000007: "UI_AvatarIcon_PlayerGirl",
    10000117: "UI_AvatarIcon_MannequinBoy",
    10000118: "UI_AvatarIcon_MannequinGirl",
}
_FIXED_NAMES = {TRAVELER_ID: "Traveler", MANEKIN_ID: "Manekin"}

ELEMENTS = {
    "Electric": "Electro", "Fire": "Pyro", "Grass": "Dendro", "Ice": "Cryo",
    "Rock": "Geo", "Water": "Hydro", "Wind": "Anemo",
}
WEAPONS = {
    "WEAPON_SWORD_ONE_HAND": "Sword", "WEAPON_CLAYMORE": "Claymore", "WEAPON_POLE": "Polearm",
    "WEAPON_BOW": "Bow", "WEAPON_CATALYST": "Catalyst",
}


@dataclass(frozen=True)
class CharacterData:
    id: int
    name: str
    slug: str
    rarity: int
    element: str | None
    weapon_type: str
    region: str | None
    icon: str
    splash: str
    release_at: datetime


def canonical_id(raw: int | str) -> int:
    n = int(str(raw).split("-")[0])
    return _ALIASES.get(n, n)


def splash_for(icon: str) -> str:
    return icon.replace("UI_AvatarIcon_", "UI_Gacha_AvatarImg_", 1)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_avatar_list(payload: dict) -> list[CharacterData]:
    by_id: dict[int, CharacterData] = {}
    for key, v in payload["data"]["items"].items():
        cid = canonical_id(key)
        name = _FIXED_NAMES.get(cid, v["name"])
        icon = VARIANT_ICONS.get(cid, v["icon"])
        element = None if cid in _FIXED_NAMES else ELEMENTS.get(v.get("element") or "")
        release = datetime.fromtimestamp(int(v["release"]), tz=timezone.utc).replace(tzinfo=None)
        data = CharacterData(
            id=cid, name=name, slug=slugify(name), rarity=int(v["rank"]), element=element,
            weapon_type=WEAPONS.get(v["weaponType"], v["weaponType"]), region=v.get("region") or None,
            icon=icon, splash=splash_for(icon), release_at=release,
        )
        previous = by_id.get(cid)
        if previous is None or data.release_at < previous.release_at:
            by_id[cid] = data
    return sorted(by_id.values(), key=lambda c: c.id)


async def fetch_avatar_list(http: httpx.AsyncClient) -> list[CharacterData]:
    response = await http.get(YATTA_AVATAR_URL, timeout=30)
    response.raise_for_status()
    return parse_avatar_list(response.json())
```

`backend/app/gamedata/service.py`:

```python
import logging
from datetime import datetime, timedelta

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from app.config import GAMEDATA_MAX_AGE_DAYS
from app.db.models import GameCharacter, GameMeta
from app.gamedata.yatta import CharacterData, fetch_avatar_list
from app.timeutil import iso, utcnow

log = logging.getLogger(__name__)
META_FETCHED = "characters_fetched_at"
META_ERROR = "characters_last_error"


def _get_meta(session: Session, key: str):
    row = session.get(GameMeta, key)
    return row.value if row else None


def _set_meta(session: Session, key: str, value) -> None:
    session.merge(GameMeta(key=key, value=value))


def needs_refresh(session: Session, now: datetime) -> bool:
    fetched = _get_meta(session, META_FETCHED)
    if not fetched or session.scalar(select(func.count()).select_from(GameCharacter)) == 0:
        return True
    return now - datetime.fromisoformat(fetched.rstrip("Z")) > timedelta(days=GAMEDATA_MAX_AGE_DAYS)


def _store(session: Session, chars: list[CharacterData], now: datetime) -> None:
    for c in chars:
        session.merge(GameCharacter(
            id=c.id, name=c.name, slug=c.slug, rarity=c.rarity, element=c.element,
            weapon_type=c.weapon_type, region=c.region, icon=c.icon, splash=c.splash,
            release_at=c.release_at,
        ))
    _set_meta(session, META_FETCHED, iso(now))
    _set_meta(session, META_ERROR, None)


async def refresh(session_factory: sessionmaker, http: httpx.AsyncClient,
                  now: datetime | None = None, force: bool = False) -> bool:
    """Download the character list if stale (or forced). Returns True if data was stored."""
    now = now or utcnow()
    with session_factory() as s:
        if not force and not needs_refresh(s, now):
            return False
    try:
        chars = await fetch_avatar_list(http)
    except (httpx.HTTPError, KeyError, ValueError, TypeError) as e:
        message = f"{type(e).__name__}: {e}"[:300]
        log.warning("Game data refresh failed: %s", message)
        with session_factory.begin() as s:
            _set_meta(s, META_ERROR, message)
        return False
    with session_factory.begin() as s:
        _store(s, chars, now)
    return True


def gamedata_status(session: Session) -> dict:
    return {
        "fetched_at": _get_meta(session, META_FETCHED),
        "last_error": _get_meta(session, META_ERROR),
        "count": session.scalar(select(func.count()).select_from(GameCharacter)) or 0,
    }
```

Note: the failure test expects `"503"` in the error; `raise_for_status()` produces `HTTPStatusError` whose message includes the status code.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_gamedata.py -v`
Expected: 7 passed

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: game data download and cache from Yatta"
```

---

### Task 6: Image cache

**Files:**
- Create: `backend/app/gamedata/images.py`, `backend/tests/test_images.py`

**Interfaces:**
- Produces: `PLACEHOLDER_PNG: bytes`; `@dataclass ImageResult(data: bytes, media_type: str, cached: bool)`; `async get_named(cache_dir: Path, http, name: str, offline: bool = False) -> ImageResult` (raises `ValueError` for names not matching `^UI_[A-Za-z0-9_]+$`); `is_allowed_remote(url) -> bool`; `async get_remote(cache_dir, http, url, offline=False) -> ImageResult` (raises `ValueError` for disallowed hosts).

- [ ] **Step 1: Write the failing test**

`backend/tests/test_images.py`:

```python
import httpx
import pytest

from app.gamedata.images import (
    PLACEHOLDER_PNG, get_named, get_remote, is_allowed_remote,
)

PNG = b"\x89PNG\r\n\x1a\nfake"


def transport(calls: list, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    return httpx.MockTransport(handler)


async def test_named_downloads_once_then_serves_cache(tmp_path):
    calls: list = []
    async with httpx.AsyncClient(transport=transport(calls)) as http:
        first = await get_named(tmp_path, http, "UI_AvatarIcon_Bennett")
        second = await get_named(tmp_path, http, "UI_AvatarIcon_Bennett")
    assert first.data == PNG and first.cached and second.cached
    assert calls == ["https://enka.network/ui/UI_AvatarIcon_Bennett.png"]
    assert (tmp_path / "UI_AvatarIcon_Bennett.png").read_bytes() == PNG


async def test_named_falls_back_then_placeholder_not_cached(tmp_path):
    calls: list = []
    async with httpx.AsyncClient(transport=transport(calls, status=404)) as http:
        result = await get_named(tmp_path, http, "UI_AvatarIcon_Nobody")
    assert result.data == PLACEHOLDER_PNG and not result.cached
    assert len(calls) == 2  # enka then yatta
    assert not (tmp_path / "UI_AvatarIcon_Nobody.png").exists()


async def test_named_rejects_bad_names(tmp_path):
    async with httpx.AsyncClient() as http:
        for bad in ("../secret", "UI_x.png", "foo", "UI_a/b"):
            with pytest.raises(ValueError):
                await get_named(tmp_path, http, bad)


async def test_offline_returns_placeholder_without_network(tmp_path):
    calls: list = []
    async with httpx.AsyncClient(transport=transport(calls)) as http:
        result = await get_named(tmp_path, http, "UI_AvatarIcon_Bennett", offline=True)
    assert result.data == PLACEHOLDER_PNG and calls == []


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("https://act-webstatic.hoyoverse.com/x/a.png", True),
        ("https://upload-os-bbs.mihoyo.com/a.png", True),
        ("https://enka.network/ui/a.png", True),
        ("http://act-webstatic.hoyoverse.com/a.png", False),
        ("https://evil.com/a.png", False),
        ("https://hoyoverse.com.evil.com/a.png", False),
    ],
)
def test_remote_allowlist(url, ok):
    assert is_allowed_remote(url) is ok


async def test_remote_cached_by_hash(tmp_path):
    calls: list = []
    url = "https://act-webstatic.hoyoverse.com/w/UI_EquipIcon_Sword.png"
    async with httpx.AsyncClient(transport=transport(calls)) as http:
        await get_remote(tmp_path, http, url)
        again = await get_remote(tmp_path, http, url)
        with pytest.raises(ValueError):
            await get_remote(tmp_path, http, "https://evil.com/a.png")
    assert again.cached and calls == [url]
    assert len(list((tmp_path / "remote").iterdir())) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_images.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.gamedata.images'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/gamedata/images.py`:

```python
"""Download-once image cache for game art (named) and HoYoLAB icon URLs (remote, allow-listed)."""
from __future__ import annotations

import base64
import hashlib
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

NAME_RE = re.compile(r"^UI_[A-Za-z0-9_]+$")
ALLOWED_HOST_SUFFIXES = ("hoyoverse.com", "mihoyo.com", "hoyolab.com", "enka.network", "yatta.moe")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@dataclass(frozen=True)
class ImageResult:
    data: bytes
    media_type: str
    cached: bool


def _named_sources(name: str) -> list[str]:
    return [f"https://enka.network/ui/{name}.png", f"https://gi.yatta.moe/assets/UI/{name}.png"]


def is_allowed_remote(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(
        host == s or host.endswith("." + s) for s in ALLOWED_HOST_SUFFIXES
    )


async def _fetch(path: Path, urls: list[str], http: httpx.AsyncClient, offline: bool) -> ImageResult:
    media = mimetypes.guess_type(path.name)[0] or "image/png"
    if path.exists():
        return ImageResult(path.read_bytes(), media, True)
    if offline:
        return ImageResult(PLACEHOLDER_PNG, "image/png", False)
    for url in urls:
        try:
            response = await http.get(url, timeout=20)
        except httpx.HTTPError:
            continue
        if response.status_code == 200 and response.headers.get("content-type", "").startswith("image/"):
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(response.content)
            tmp.replace(path)
            return ImageResult(response.content, media, True)
    return ImageResult(PLACEHOLDER_PNG, "image/png", False)


async def get_named(cache_dir: Path, http: httpx.AsyncClient, name: str, offline: bool = False) -> ImageResult:
    if not NAME_RE.fullmatch(name):
        raise ValueError("bad image name")
    return await _fetch(cache_dir / f"{name}.png", _named_sources(name), http, offline)


async def get_remote(cache_dir: Path, http: httpx.AsyncClient, url: str, offline: bool = False) -> ImageResult:
    if not is_allowed_remote(url):
        raise ValueError("image host not allowed")
    ext = Path(urlsplit(url).path).suffix.lower()
    key = hashlib.sha256(url.encode()).hexdigest()[:32]
    path = cache_dir / "remote" / f"{key}{ext if ext in IMAGE_EXTS else '.png'}"
    return await _fetch(path, [url], http, offline)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_images.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: image cache for game art and HoYoLAB icons"
```

---

### Task 7: HoYoLAB wrapper

**Files:**
- Create: `backend/app/sync/__init__.py`, `backend/app/sync/hoyolab.py`, `backend/tests/test_hoyolab.py`

**Interfaces:**
- Consumes: `canonical_id` (Task 5). genshin.py 1.7.32 fields (verified): roster `Character(id, name, element, rarity, icon, level, friendship, constellation, weapon: CharacterWeapon(id, icon, name, rarity, level, refinement))`; detail `GenshinDetailCharacters.characters: [GenshinDetailCharacter(id, weapon, artifacts: [DetailArtifact(pos, icon, rarity, level, set.name, main_stat: ArtifactProperty(value, info.name), sub_stats)], skills: [CharacterSkill(skill_type, level)], base_properties/extra_properties: [PropertyValue(final, info.name)])]`; `Notes(current_resin, max_resin, remaining_resin_recovery_time: timedelta, completed_commissions, max_commissions, current_realm_currency, max_realm_currency, expeditions: [Expedition(character_icon, status, remaining_time)])`; `GenshinAccount(uid, level, nickname, server, game)`. Errors: `genshin.errors.InvalidCookies`, `TooManyRequests` (a `CookieException` subclass — catch it before `InvalidCookies`), `VisitsTooFrequently`, base `GenshinException`.
- Produces: exceptions `HoyolabError`, `AuthExpired(HoyolabError)`, `RateLimited(HoyolabError)`; frozen dataclasses `Account(uid, server, nickname, level)`, `WeaponInfo(name, icon, rarity, level, refinement)`, `RosterEntry(id, raw_id, name, element, level, constellation, friendship, weapon)`, `ArtifactInfo(slot, set_name, rarity, level, main_stat, substats, icon)`, `DetailEntry(id, normal, skill, burst, weapon, artifacts, stats)`, `ExpeditionInfo(icon, finished, remaining_seconds)`, `NotesInfo(resin, resin_max, resin_recovery_seconds, commissions_done, commissions_max, realm_currency, realm_currency_max, expeditions)`; `HoyolabSource` Protocol with `async get_roster() -> list[RosterEntry]`, `async get_details(raw_ids) -> list[DetailEntry]`, `async get_notes() -> NotesInfo`; mappers `to_roster_entry`, `to_detail_entry`, `to_notes`, `to_account`; `async call_api(fn, *args, delays=RETRY_DELAYS, **kwargs)`; `GenshinPySource(cookies, uid, delays=RETRY_DELAYS)`; `async fetch_accounts(cookies) -> list[Account]`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_hoyolab.py`:

```python
from datetime import timedelta
from types import SimpleNamespace as NS

import genshin
import pytest

from app.sync.hoyolab import (
    AuthExpired, HoyolabError, RateLimited, call_api,
    to_detail_entry, to_notes, to_roster_entry,
)

WEAPON = NS(id=1, icon="https://act-webstatic.hoyoverse.com/w.png", name="The Flute", rarity=4, level=90, refinement=5)


def prop(name, value):
    return NS(info=NS(name=name), value=value, final=value)


def test_roster_entry_maps_traveler_variant():
    c = NS(id=10000007, name="Traveler", element="Geo", rarity=5, icon="x", level=90,
           friendship=10, constellation=6, weapon=WEAPON)
    e = to_roster_entry(c)
    assert (e.id, e.raw_id, e.element, e.level) == (10000005, 10000007, "Geo", 90)
    assert e.weapon.name == "The Flute" and e.weapon.refinement == 5


def test_detail_entry_talents_skip_passives_and_sprint():
    skills = [
        NS(skill_type=1, level=6),   # normal attack
        NS(skill_type=1, level=9),   # elemental skill
        NS(skill_type=1, level=1),   # alternate sprint (Ayaka/Mona) — ignored
        NS(skill_type=1, level=10),  # burst (always last active skill)
        NS(skill_type=2, level=1),   # passive
    ]
    artifact = NS(pos=1, icon="https://act-webstatic.hoyoverse.com/a.png", rarity=5, level=20,
                  set=NS(name="Noblesse Oblige"), main_stat=prop("HP", "4780"),
                  sub_stats=[prop("CRIT Rate", "3.9%"), prop("ATK", "19")])
    c = NS(id=10000032, weapon=WEAPON, artifacts=[artifact], skills=skills,
           base_properties=[prop("HP", "20000")], extra_properties=[prop("Energy Recharge", "200%")])
    d = to_detail_entry(c)
    assert (d.normal, d.skill, d.burst) == (6, 9, 10)
    assert d.artifacts[0].main_stat == "HP 4780"
    assert d.artifacts[0].substats == ["CRIT Rate 3.9%", "ATK 19"]
    assert d.stats == [{"name": "HP", "value": "20000"}, {"name": "Energy Recharge", "value": "200%"}]


def test_detail_entry_with_too_few_skills_defaults_to_one():
    c = NS(id=1, weapon=WEAPON, artifacts=[], skills=[NS(skill_type=1, level=4)],
           base_properties=[], extra_properties=[])
    d = to_detail_entry(c)
    assert (d.normal, d.skill, d.burst) == (4, 1, 1)


def test_notes_mapping():
    n = NS(current_resin=153, max_resin=200, remaining_resin_recovery_time=timedelta(minutes=376),
           completed_commissions=4, max_commissions=4, current_realm_currency=1460,
           max_realm_currency=2400,
           expeditions=[NS(character_icon="https://act-webstatic.hoyoverse.com/e.png",
                           status="Finished", remaining_time=timedelta(0))])
    notes = to_notes(n)
    assert notes.resin_recovery_seconds == 376 * 60
    assert notes.expeditions[0].finished is True


async def test_call_api_retries_rate_limit_then_succeeds():
    attempts = []

    async def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise genshin.errors.TooManyRequests({"retcode": 10101, "message": "slow down"})
        return "ok"

    assert await call_api(flaky, delays=(0, 0, 0)) == "ok"
    assert len(attempts) == 3


async def test_call_api_gives_up_with_rate_limited():
    async def always():
        raise genshin.errors.VisitsTooFrequently({"retcode": -110, "message": "busy"})

    with pytest.raises(RateLimited):
        await call_api(always, delays=(0, 0))


async def test_call_api_maps_invalid_cookies_and_other_errors():
    async def bad_cookie():
        raise genshin.errors.InvalidCookies({"retcode": -100, "message": "not logged in"})

    async def other():
        raise genshin.errors.GenshinException({"retcode": -1, "message": "boom"})

    with pytest.raises(AuthExpired):
        await call_api(bad_cookie, delays=())
    with pytest.raises(HoyolabError):
        await call_api(other, delays=())
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_hoyolab.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.sync'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/sync/__init__.py`: empty file.

`backend/app/sync/hoyolab.py`:

```python
"""The ONLY module that talks to HoYoLAB. Converts genshin.py models to our own dataclasses
so a library or endpoint change is contained here."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Protocol, Sequence

import genshin

from app.gamedata.yatta import canonical_id

RETRY_DELAYS: tuple[float, ...] = (2.0, 5.0, 10.0)
DETAIL_BATCH = 20


class HoyolabError(Exception):
    """Any HoYoLAB failure. Messages never contain cookie values."""


class AuthExpired(HoyolabError):
    pass


class RateLimited(HoyolabError):
    pass


@dataclass(frozen=True)
class Account:
    uid: int
    server: str
    nickname: str
    level: int


@dataclass(frozen=True)
class WeaponInfo:
    name: str
    icon: str
    rarity: int
    level: int
    refinement: int


@dataclass(frozen=True)
class RosterEntry:
    id: int        # canonical id
    raw_id: int    # id HoYoLAB uses (needed for detail requests)
    name: str
    element: str | None
    level: int
    constellation: int
    friendship: int
    weapon: WeaponInfo


@dataclass(frozen=True)
class ArtifactInfo:
    slot: int
    set_name: str
    rarity: int
    level: int
    main_stat: str
    substats: list[str]
    icon: str


@dataclass(frozen=True)
class DetailEntry:
    id: int
    normal: int
    skill: int
    burst: int
    weapon: WeaponInfo
    artifacts: list[ArtifactInfo]
    stats: list[dict]


@dataclass(frozen=True)
class ExpeditionInfo:
    icon: str
    finished: bool
    remaining_seconds: int


@dataclass(frozen=True)
class NotesInfo:
    resin: int
    resin_max: int
    resin_recovery_seconds: int
    commissions_done: int
    commissions_max: int
    realm_currency: int
    realm_currency_max: int
    expeditions: list[ExpeditionInfo]


class HoyolabSource(Protocol):
    async def get_roster(self) -> list[RosterEntry]: ...
    async def get_details(self, raw_ids: Sequence[int]) -> list[DetailEntry]: ...
    async def get_notes(self) -> NotesInfo: ...


# --- mappers ---------------------------------------------------------------
def _weapon(w: Any) -> WeaponInfo:
    return WeaponInfo(name=w.name, icon=w.icon, rarity=int(w.rarity), level=int(w.level),
                      refinement=int(w.refinement))


def _prop(p: Any) -> str:
    return f"{p.info.name} {p.value}"


def to_roster_entry(c: Any) -> RosterEntry:
    return RosterEntry(
        id=canonical_id(c.id), raw_id=int(c.id), name=c.name, element=c.element or None,
        level=int(c.level), constellation=int(c.constellation), friendship=int(c.friendship),
        weapon=_weapon(c.weapon),
    )


def to_detail_entry(c: Any) -> DetailEntry:
    # Active skills arrive as: normal, skill, [alternate sprint], burst. Burst is always last.
    levels = [int(s.level) for s in c.skills if s.skill_type == 1]
    normal = levels[0] if levels else 1
    skill = levels[1] if len(levels) > 1 else 1
    burst = levels[-1] if len(levels) >= 3 else 1
    artifacts = [
        ArtifactInfo(slot=int(a.pos), set_name=a.set.name, rarity=int(a.rarity), level=int(a.level),
                     main_stat=_prop(a.main_stat), substats=[_prop(s) for s in a.sub_stats], icon=a.icon)
        for a in c.artifacts
    ]
    stats = [{"name": p.info.name, "value": p.final} for p in [*c.base_properties, *c.extra_properties]]
    return DetailEntry(id=canonical_id(c.id), normal=normal, skill=skill, burst=burst,
                       weapon=_weapon(c.weapon), artifacts=artifacts, stats=stats)


def to_notes(n: Any) -> NotesInfo:
    return NotesInfo(
        resin=int(n.current_resin), resin_max=int(n.max_resin),
        resin_recovery_seconds=int(n.remaining_resin_recovery_time.total_seconds()),
        commissions_done=int(n.completed_commissions), commissions_max=int(n.max_commissions),
        realm_currency=int(n.current_realm_currency), realm_currency_max=int(n.max_realm_currency),
        expeditions=[
            ExpeditionInfo(icon=e.character_icon, finished=e.status == "Finished",
                           remaining_seconds=int(e.remaining_time.total_seconds()))
            for e in n.expeditions
        ],
    )


def to_account(a: Any) -> Account:
    return Account(uid=int(a.uid), server=a.server, nickname=a.nickname, level=int(a.level))


# --- calls -----------------------------------------------------------------
async def call_api(fn: Callable[..., Awaitable[Any]], *args: Any,
                   delays: Sequence[float] = RETRY_DELAYS, **kwargs: Any) -> Any:
    """Call genshin.py, retrying rate limits; map errors to ours (without chaining request info)."""
    for attempt in range(len(delays) + 1):
        try:
            return await fn(*args, **kwargs)
        except (genshin.errors.TooManyRequests, genshin.errors.VisitsTooFrequently) as e:
            if attempt == len(delays):
                raise RateLimited(str(e)) from None
            await asyncio.sleep(delays[attempt])
        except genshin.errors.InvalidCookies as e:
            raise AuthExpired(str(e)) from None
        except genshin.errors.GenshinException as e:
            raise HoyolabError(str(e)) from None
    raise AssertionError("unreachable")


class GenshinPySource:
    def __init__(self, cookies: dict[str, str], uid: int, delays: Sequence[float] = RETRY_DELAYS):
        self._client = genshin.Client(cookies, game=genshin.Game.GENSHIN, uid=uid)
        self._uid = uid
        self._delays = delays

    async def get_roster(self) -> list[RosterEntry]:
        chars = await call_api(self._client.get_genshin_characters, self._uid, delays=self._delays)
        return [to_roster_entry(c) for c in chars]

    async def get_details(self, raw_ids: Sequence[int]) -> list[DetailEntry]:
        out: list[DetailEntry] = []
        ids = list(raw_ids)
        for i in range(0, len(ids), DETAIL_BATCH):
            result = await call_api(self._client.get_genshin_detailed_characters, self._uid,
                                    characters=ids[i:i + DETAIL_BATCH], delays=self._delays)
            out.extend(to_detail_entry(c) for c in result.characters)
        return out

    async def get_notes(self) -> NotesInfo:
        return to_notes(await call_api(self._client.get_genshin_notes, self._uid, delays=self._delays))


async def fetch_accounts(cookies: dict[str, str]) -> list[Account]:
    client = genshin.Client(cookies, game=genshin.Game.GENSHIN)
    accounts = await call_api(client.get_game_accounts)
    return [to_account(a) for a in accounts if a.game == genshin.Game.GENSHIN]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_hoyolab.py -v`
Expected: 7 passed. If constructing `genshin.errors.TooManyRequests({...})` fails, check its constructor with `python -c "import genshin, inspect; print(inspect.signature(genshin.errors.GenshinException.__init__))"` and adapt only the test's construction of the exception.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: HoYoLAB wrapper with retry and error mapping"
```

---

### Task 8: Saving synced data and database backups

**Files:**
- Create: `backend/app/sync/persist.py`, `backend/app/sync/backup.py`, `backend/tests/fakes.py`, `backend/tests/test_persist.py`

**Interfaces:**
- Consumes: models (Task 2), dataclasses from Task 7, `VARIANT_ICONS` (Task 5), `iso` (Task 1), `seed_game` (Task 5 helpers).
- Produces: `save_roster(session, entries, now) -> set[int]` (returns canonical ids missing from game data; deletes owned rows/artifacts not in `entries`); `save_details(session, details) -> None`; `save_notes(session, notes, now) -> None`; `backup_db(db_file, backups_dir, now, keep=BACKUPS_KEPT) -> Path | None`. Test fakes: `WEAPON`, `make_roster(id, level=80, raw_id=None, name="Char", element="Pyro")`, `make_detail(id, talents=(6, 8, 8))`, `NOTES`, `FakeSource`, `Clock`.

- [ ] **Step 1: Write the fakes**

`backend/tests/fakes.py`:

```python
import asyncio
from datetime import datetime, timedelta

from app.sync.hoyolab import (
    ArtifactInfo, DetailEntry, ExpeditionInfo, NotesInfo, RosterEntry, WeaponInfo,
)

WEAPON = WeaponInfo("The Flute", "https://act-webstatic.hoyoverse.com/w.png", 4, 90, 5)
NOTES = NotesInfo(153, 200, 3600, 4, 4, 1460, 2400,
                  [ExpeditionInfo("https://act-webstatic.hoyoverse.com/e.png", False, 7200)])


def make_roster(id: int, level: int = 80, raw_id: int | None = None, name: str = "Char",
                element: str | None = "Pyro") -> RosterEntry:
    return RosterEntry(id=id, raw_id=raw_id or id, name=name, element=element, level=level,
                       constellation=2, friendship=10, weapon=WEAPON)


def make_detail(id: int, talents: tuple[int, int, int] = (6, 8, 8)) -> DetailEntry:
    artifact = ArtifactInfo(1, "Noblesse Oblige", 5, 20, "HP 4780", ["CRIT Rate 3.9%"],
                            "https://act-webstatic.hoyoverse.com/a.png")
    return DetailEntry(id, *talents, WEAPON, [artifact], [{"name": "HP", "value": "20000"}])


class FakeSource:
    """Stand-in for GenshinPySource. `fail` maps part name -> exception to raise."""

    def __init__(self, roster=None, notes=NOTES, fail=None, gate: asyncio.Event | None = None):
        self.roster = roster if roster is not None else [
            make_roster(10000032, name="Bennett"), make_roster(10000089, level=90, name="Furina"),
        ]
        self.notes = notes
        self.fail = fail or {}
        self.gate = gate
        self.calls: list = []

    async def get_roster(self):
        self.calls.append("roster")
        if self.gate is not None:
            await self.gate.wait()
        if "roster" in self.fail:
            raise self.fail["roster"]
        return list(self.roster)

    async def get_details(self, raw_ids):
        self.calls.append(("details", tuple(raw_ids)))
        if "details" in self.fail:
            raise self.fail["details"]
        return [make_detail(r.id) for r in self.roster if r.raw_id in raw_ids]

    async def get_notes(self):
        self.calls.append("notes")
        if "notes" in self.fail:
            raise self.fail["notes"]
        return self.notes


class Clock:
    def __init__(self, now: datetime):
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, **kwargs) -> None:
        self.now += timedelta(**kwargs)
```

- [ ] **Step 2: Write the failing test**

`backend/tests/test_persist.py`:

```python
from datetime import datetime, timedelta

from app.db.models import LiveNotes, OwnedArtifact, OwnedCharacter
from app.sync.backup import backup_db
from app.sync.hoyolab import NotesInfo
from app.sync.persist import save_details, save_notes, save_roster
from fakes import NOTES, make_detail, make_roster
from helpers import seed_game

NOW = datetime(2026, 11, 19, 12, 0, 0)


def test_save_roster_upserts_and_reports_unknown(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        unknown = save_roster(s, [make_roster(10000032), make_roster(10000999, name="New")], NOW)
    assert unknown == {10000999}
    with session_factory() as s:
        row = s.get(OwnedCharacter, 10000032)
        assert (row.level, row.weapon_name, row.synced_at) == (80, "The Flute", NOW)
        assert s.get(OwnedCharacter, 10000999).name == "New"


def test_save_roster_removes_characters_no_longer_reported(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032), make_roster(10000089)], NOW)
        save_details(s, [make_detail(10000089)])
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], NOW)
    with session_factory() as s:
        assert s.get(OwnedCharacter, 10000089) is None
        assert s.query(OwnedArtifact).filter_by(character_id=10000089).count() == 0


def test_save_roster_keeps_variant_icon(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000005, raw_id=10000007, name="Traveler", element="Geo")], NOW)
    with session_factory() as s:
        row = s.get(OwnedCharacter, 10000005)
        assert (row.icon, row.element) == ("UI_AvatarIcon_PlayerGirl", "Geo")


def test_save_details_sets_talents_and_replaces_artifacts(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], NOW)
        save_details(s, [make_detail(10000032, talents=(6, 9, 10))])
        save_details(s, [make_detail(10000032, talents=(7, 9, 10))])
        save_details(s, [make_detail(12345678)])  # not owned: ignored
    with session_factory() as s:
        row = s.get(OwnedCharacter, 10000032)
        assert (row.talent_normal, row.talent_skill, row.talent_burst) == (7, 9, 10)
        assert row.stats == [{"name": "HP", "value": "20000"}]
        assert s.query(OwnedArtifact).filter_by(character_id=10000032).count() == 1


def test_save_notes_computes_times(session_factory):
    with session_factory.begin() as s:
        save_notes(s, NOTES, NOW)
    with session_factory() as s:
        n = s.get(LiveNotes, 1)
        assert n.resin_full_at == NOW + timedelta(seconds=3600)
        assert n.expeditions == [{"icon": "https://act-webstatic.hoyoverse.com/e.png",
                                  "finished": False, "return_at": "2026-11-19T14:00:00Z"}]


def test_save_notes_full_resin(session_factory):
    full = NotesInfo(200, 200, 0, 4, 4, 0, 2400, [])
    with session_factory.begin() as s:
        save_notes(s, full, NOW)
    with session_factory() as s:
        assert s.get(LiveNotes, 1).resin_full_at == NOW


def test_backup_rotation_keeps_five(paths, session_factory):
    for i in range(7):
        backup_db(paths.db_file, paths.backups, NOW + timedelta(seconds=i))
    files = sorted(p.name for p in paths.backups.glob("tracker-*.db"))
    assert len(files) == 5
    assert files[-1].startswith("tracker-20261119-120006")


def test_backup_without_database_is_noop(tmp_path):
    assert backup_db(tmp_path / "missing.db", tmp_path / "b", NOW) is None
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/test_persist.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.sync.persist'`

- [ ] **Step 4: Write minimal implementation**

`backend/app/sync/persist.py`:

```python
"""Write sync results. Only account-data tables are touched here."""
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, LiveNotes, OwnedArtifact, OwnedCharacter
from app.gamedata.yatta import VARIANT_ICONS
from app.sync.hoyolab import DetailEntry, NotesInfo, RosterEntry
from app.timeutil import iso


def save_roster(session: Session, entries: list[RosterEntry], now: datetime) -> set[int]:
    known = set(session.scalars(select(GameCharacter.id)))
    seen: set[int] = set()
    for e in entries:
        seen.add(e.id)
        row = session.get(OwnedCharacter, e.id)
        if row is None:
            row = OwnedCharacter(character_id=e.id, stats=[])
            session.add(row)
        row.name = e.name
        row.element = e.element
        row.icon = VARIANT_ICONS.get(e.raw_id)
        row.level = e.level
        row.constellation = e.constellation
        row.friendship = e.friendship
        row.weapon_name = e.weapon.name
        row.weapon_icon = e.weapon.icon
        row.weapon_rarity = e.weapon.rarity
        row.weapon_level = e.weapon.level
        row.weapon_refinement = e.weapon.refinement
        row.synced_at = now
    session.flush()
    session.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id.not_in(seen)))
    session.execute(delete(OwnedCharacter).where(OwnedCharacter.character_id.not_in(seen)))
    return seen - known


def save_details(session: Session, details: list[DetailEntry]) -> None:
    for d in details:
        row = session.get(OwnedCharacter, d.id)
        if row is None:
            continue
        row.talent_normal, row.talent_skill, row.talent_burst = d.normal, d.skill, d.burst
        row.weapon_name = d.weapon.name
        row.weapon_icon = d.weapon.icon
        row.weapon_rarity = d.weapon.rarity
        row.weapon_level = d.weapon.level
        row.weapon_refinement = d.weapon.refinement
        row.stats = list(d.stats)
        session.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id == d.id))
        for a in d.artifacts:
            session.add(OwnedArtifact(
                character_id=d.id, slot=a.slot, set_name=a.set_name, rarity=a.rarity, level=a.level,
                main_stat=a.main_stat, substats=list(a.substats), icon=a.icon,
            ))
    session.flush()


def save_notes(session: Session, notes: NotesInfo, now: datetime) -> None:
    row = session.get(LiveNotes, 1)
    if row is None:
        row = LiveNotes(id=1)
        session.add(row)
    row.resin = notes.resin
    row.resin_max = notes.resin_max
    row.resin_full_at = now + timedelta(seconds=max(0, notes.resin_recovery_seconds))
    row.commissions_done = notes.commissions_done
    row.commissions_max = notes.commissions_max
    row.realm_currency = notes.realm_currency
    row.realm_currency_max = notes.realm_currency_max
    row.expeditions = [
        {"icon": e.icon, "finished": e.finished,
         "return_at": iso(now + timedelta(seconds=max(0, e.remaining_seconds)))}
        for e in notes.expeditions
    ]
    row.fetched_at = now
    session.flush()
```

`backend/app/sync/backup.py`:

```python
import sqlite3
from datetime import datetime
from pathlib import Path

from app.config import BACKUPS_KEPT


def backup_db(db_file: Path, backups_dir: Path, now: datetime, keep: int = BACKUPS_KEPT) -> Path | None:
    """Consistent copy via SQLite's backup API; keep only the newest `keep` copies."""
    if not db_file.exists():
        return None
    backups_dir.mkdir(parents=True, exist_ok=True)
    dest = backups_dir / f"tracker-{now:%Y%m%d-%H%M%S-%f}.db"
    src = sqlite3.connect(db_file)
    dst = sqlite3.connect(dest)
    try:
        src.backup(dst)
    finally:
        dst.close()
        src.close()
    for old in sorted(backups_dir.glob("tracker-*.db"))[:-keep]:
        old.unlink()
    return dest
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/test_persist.py -v`
Expected: 8 passed

- [ ] **Step 6: Commit**

```bash
git add backend
git commit -m "feat: persist roster/details/notes and rotate database backups"
```

---

### Task 9: Sync manager

**Files:**
- Create: `backend/app/sync/runner.py`, `backend/tests/test_sync_runner.py`

**Interfaces:**
- Consumes: `save_roster`, `save_details`, `save_notes`, `backup_db` (Task 8); `AuthExpired`, `HoyolabSource` (Task 7); `get_setting`, `set_setting` (Task 4); `SyncRun` (Task 2); `MANUAL_SYNC_MIN_SECONDS`; fakes (Task 8).
- Produces: `PARTS = ("roster", "details", "notes")`; `SyncTooSoon(retry_after: int)`; `@dataclass SyncRequestResult(run_id: int | None, started: bool, reason: str)` with reasons `"started" | "joined" | "fresh" | "recent" | "not_connected"`; `last_successful(session) -> SyncRun | None`; `SyncManager(session_factory, db_file, backups_dir, source_factory: Callable[[], HoyolabSource | None], on_unknown_ids: Callable[[set[int]], Awaitable[None]], clock=utcnow)` with `async request(trigger: "auto"|"manual"|"connect") -> SyncRequestResult`, property `running: bool`, `async wait() -> None`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_sync_runner.py`:

```python
import asyncio
from datetime import datetime

import pytest

from app.db.models import LiveNotes, OwnedCharacter, SyncRun
from app.settings.store import get_setting, set_setting
from app.sync.hoyolab import AuthExpired, HoyolabError
from app.sync.runner import SyncManager, SyncTooSoon
from fakes import Clock, FakeSource, make_roster
from helpers import seed_game

START = datetime(2026, 11, 19, 12, 0, 0)


def manager(paths, session_factory, source, clock=None, unknown_sink=None):
    async def on_unknown(ids):
        if unknown_sink is not None:
            unknown_sink.append(ids)

    return SyncManager(session_factory, paths.db_file, paths.backups,
                       lambda: source, on_unknown, clock=clock or Clock(START))


def last_run(session_factory) -> SyncRun:
    with session_factory() as s:
        return s.query(SyncRun).order_by(SyncRun.id.desc()).first()


async def test_full_sync_saves_everything(paths, session_factory):
    seed_game(session_factory)
    m = manager(paths, session_factory, FakeSource())
    result = await m.request("manual")
    await m.wait()
    assert result.started and result.reason == "started"
    run = last_run(session_factory)
    assert run.finished_at is not None
    assert run.parts == {"roster": {"ok": True, "count": 2}, "details": {"ok": True, "count": 2},
                         "notes": {"ok": True}}
    with session_factory() as s:
        assert s.get(OwnedCharacter, 10000032).talent_burst == 8
        assert s.get(LiveNotes, 1).resin == 153
    assert len(list(paths.backups.glob("tracker-*.db"))) == 1


async def test_details_failure_does_not_block_notes(paths, session_factory):
    seed_game(session_factory)
    m = manager(paths, session_factory, FakeSource(fail={"details": HoyolabError("boom")}))
    await m.request("manual")
    await m.wait()
    parts = last_run(session_factory).parts
    assert parts["details"] == {"ok": False, "error": "HoyolabError: boom"}
    assert parts["roster"]["ok"] and parts["notes"]["ok"]


async def test_roster_failure_skips_details_but_runs_notes(paths, session_factory):
    source = FakeSource(fail={"roster": HoyolabError("down")})
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    parts = last_run(session_factory).parts
    assert parts["roster"]["ok"] is False
    assert parts["details"] == {"ok": False, "error": "skipped: roster failed"}
    assert parts["notes"]["ok"] is True
    assert not any(isinstance(c, tuple) for c in source.calls)


async def test_expired_cookie_marks_status_and_stops(paths, session_factory):
    source = FakeSource(fail={"roster": AuthExpired("not logged in")})
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    parts = last_run(session_factory).parts
    assert all(p == {"ok": False, "error": "skipped: HoYoLAB login expired"} for p in parts.values())
    assert source.calls == ["roster"]
    with session_factory() as s:
        assert get_setting(s, "hoyolab_status") == "expired"


async def test_auto_respects_interval(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    source = FakeSource()
    m = manager(paths, session_factory, source, clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(minutes=5)
    assert (await m.request("auto")).reason == "fresh"
    clock.advance(minutes=6)
    assert (await m.request("auto")).reason == "started"
    await m.wait()


async def test_auto_skips_right_after_a_failed_run(paths, session_factory):
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(fail={"notes": HoyolabError("x")}), clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(seconds=30)
    assert (await m.request("auto")).reason == "recent"


async def test_manual_limited_to_once_per_minute(paths, session_factory):
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(), clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(seconds=20)
    with pytest.raises(SyncTooSoon) as exc:
        await m.request("manual")
    assert exc.value.retry_after == 40
    clock.advance(seconds=41)
    assert (await m.request("manual")).started


async def test_second_request_joins_running_sync(paths, session_factory):
    gate = asyncio.Event()
    m = manager(paths, session_factory, FakeSource(gate=gate))
    first = await m.request("manual")
    second = await m.request("manual")
    assert m.running
    assert (second.run_id, second.started, second.reason) == (first.run_id, False, "joined")
    gate.set()
    await m.wait()
    assert not m.running


async def test_not_connected(paths, session_factory):
    m = manager(paths, session_factory, None)
    assert (await m.request("auto")).reason == "not_connected"


async def test_unknown_ids_trigger_callback(paths, session_factory):
    seed_game(session_factory)
    sink: list = []
    source = FakeSource(roster=[make_roster(10000032), make_roster(10000999)])
    m = manager(paths, session_factory, source, unknown_sink=sink)
    await m.request("manual")
    await m.wait()
    assert sink == [{10000999}]


async def test_sync_never_touches_goals_or_other_settings(paths, session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        set_setting(s, "sync_interval_minutes", 42)
    m = manager(paths, session_factory, FakeSource())
    await m.request("manual")
    await m.wait()
    with session_factory() as s:
        assert get_setting(s, "sync_interval_minutes") == 42
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_sync_runner.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.sync.runner'`

- [ ] **Step 3: Write minimal implementation**

`backend/app/sync/runner.py`:

```python
"""Background sync: one run at a time; each part independent; never touches user data."""
from __future__ import annotations

import asyncio
import logging
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.config import MANUAL_SYNC_MIN_SECONDS
from app.db.models import SyncRun
from app.settings.store import get_setting, set_setting
from app.sync.backup import backup_db
from app.sync.hoyolab import AuthExpired, HoyolabSource
from app.sync.persist import save_details, save_notes, save_roster
from app.timeutil import utcnow

log = logging.getLogger(__name__)
PARTS = ("roster", "details", "notes")
EXPIRED_MSG = "skipped: HoYoLAB login expired"


class SyncTooSoon(Exception):
    def __init__(self, retry_after: int):
        super().__init__(f"retry after {retry_after}s")
        self.retry_after = retry_after


@dataclass(frozen=True)
class SyncRequestResult:
    run_id: int | None
    started: bool
    reason: str


def last_successful(session: Session) -> SyncRun | None:
    runs = session.scalars(
        select(SyncRun).where(SyncRun.finished_at.is_not(None)).order_by(SyncRun.id.desc()).limit(20)
    )
    for run in runs:
        if run.parts and all(p.get("ok") for p in run.parts.values()):
            return run
    return None


def _failure(e: Exception) -> dict:
    return {"ok": False, "error": f"{type(e).__name__}: {e}"[:300]}


class SyncManager:
    def __init__(self, session_factory: sessionmaker, db_file: Path, backups_dir: Path,
                 source_factory: Callable[[], HoyolabSource | None],
                 on_unknown_ids: Callable[[set[int]], Awaitable[None]],
                 clock: Callable[[], datetime] = utcnow):
        self._sf = session_factory
        self._db_file = db_file
        self._backups_dir = backups_dir
        self._source_factory = source_factory
        self._on_unknown_ids = on_unknown_ids
        self._clock = clock
        self._task: asyncio.Task | None = None
        self._run_id: int | None = None

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def wait(self) -> None:
        if self._task is not None:
            await self._task

    async def request(self, trigger: str) -> SyncRequestResult:
        if self.running:
            return SyncRequestResult(self._run_id, False, "joined")
        now = self._clock()
        with self._sf() as s:
            last = s.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(1)).first()
            elapsed = (now - last.started_at).total_seconds() if last else None
            if trigger == "manual" and elapsed is not None and elapsed < MANUAL_SYNC_MIN_SECONDS:
                raise SyncTooSoon(int(MANUAL_SYNC_MIN_SECONDS - elapsed))
            if trigger == "auto":
                ok = last_successful(s)
                interval = timedelta(minutes=int(get_setting(s, "sync_interval_minutes")))
                if ok is not None and now - ok.finished_at < interval:
                    return SyncRequestResult(ok.id, False, "fresh")
                if elapsed is not None and elapsed < MANUAL_SYNC_MIN_SECONDS:
                    return SyncRequestResult(last.id, False, "recent")
        source = self._source_factory()
        if source is None:
            return SyncRequestResult(None, False, "not_connected")
        with self._sf.begin() as s:
            run = SyncRun(started_at=now, trigger=trigger, parts={})
            s.add(run)
            s.flush()
            run_id = run.id
        self._run_id = run_id
        self._task = asyncio.create_task(self._run(run_id, source))
        return SyncRequestResult(run_id, True, "started")

    async def _run(self, run_id: int, source: HoyolabSource) -> None:
        parts: dict[str, dict] = {}
        unknown: set[int] = set()
        try:
            try:
                backup_db(self._db_file, self._backups_dir, self._clock())
            except (OSError, sqlite3.Error) as e:
                log.warning("Database backup failed: %s", e)

            expired = False
            roster = None
            try:
                roster = await source.get_roster()
                with self._sf.begin() as s:
                    unknown = save_roster(s, roster, self._clock())
                parts["roster"] = {"ok": True, "count": len(roster)}
            except AuthExpired:
                expired = True
            except Exception as e:  # each part is isolated by design
                log.warning("Sync part roster failed: %s", type(e).__name__)
                parts["roster"] = _failure(e)

            if not expired:
                if roster is None:
                    parts["details"] = {"ok": False, "error": "skipped: roster failed"}
                else:
                    try:
                        details = await source.get_details([r.raw_id for r in roster])
                        with self._sf.begin() as s:
                            save_details(s, details)
                        parts["details"] = {"ok": True, "count": len(details)}
                    except AuthExpired:
                        expired = True
                    except Exception as e:
                        log.warning("Sync part details failed: %s", type(e).__name__)
                        parts["details"] = _failure(e)

            if not expired:
                try:
                    notes = await source.get_notes()
                    with self._sf.begin() as s:
                        save_notes(s, notes, self._clock())
                    parts["notes"] = {"ok": True}
                except AuthExpired:
                    expired = True
                except Exception as e:
                    log.warning("Sync part notes failed: %s", type(e).__name__)
                    parts["notes"] = _failure(e)

            if expired:
                for part in PARTS:
                    parts.setdefault(part, {"ok": False, "error": EXPIRED_MSG})
                with self._sf.begin() as s:
                    set_setting(s, "hoyolab_status", "expired")
        finally:
            with self._sf.begin() as s:
                run = s.get(SyncRun, run_id)
                run.finished_at = self._clock()
                run.parts = parts
        if unknown:
            try:
                await self._on_unknown_ids(unknown)
            except Exception as e:
                log.warning("Game data refresh after unknown ids failed: %s", type(e).__name__)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/test_sync_runner.py -v`
Expected: 11 passed

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: background sync manager with isolated parts and limits"
```

---

### Task 10: App wiring, connect flow, settings and sync API

**Files:**
- Create: `backend/app/context.py`, `backend/app/settings/connect.py`, `backend/app/api/__init__.py`, `backend/app/api/settings.py`, `backend/app/api/sync.py`, `backend/tests/test_api_settings.py`
- Modify: `backend/app/main.py` (replace fully), `backend/tests/test_health.py` (replace `test_health`), `backend/tests/helpers.py` (append `make_client`, `wait_for_sync`)

**Interfaces:**
- Consumes: everything from Tasks 1–9.
- Produces:
  - `context.AppContext(paths, session_factory, http, offline, sync, accounts_fetcher)`; `get_ctx(request) -> AppContext`; `make_source_factory(paths, session_factory) -> Callable[[], HoyolabSource | None]`
  - `connect.ConnectError`; `@dataclass ConnectResult(status: "connected"|"choose", uid: int | None = None, accounts: list[Account] = [])`; `async connect(env_file, session_factory, cookies, chosen_uid, fetch_accounts) -> ConnectResult`
  - `main.create_app(paths=None, *, source_factory=None, accounts_fetcher=None, http_client=None, offline=None) -> FastAPI`
  - `api.ROUTERS: list[APIRouter]`; `api.settings.settings_payload(ctx, session) -> dict`; `api.sync.run_dict(run) -> dict`
  - Endpoints: `GET/PUT /api/settings`, `POST /api/settings/hoyolab`, `POST /api/gamedata/refresh`, `POST /api/sync?trigger=auto|manual`, `GET /api/sync/status`
  - Test helpers: `make_client(paths, source=None, accounts=None, transport=None) -> TestClient` (use as a context manager), `wait_for_sync(client, timeout=5.0) -> dict`

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/helpers.py`:

```python
import time

from fastapi.testclient import TestClient

from app.main import create_app


def make_client(paths, source=None, accounts=None, transport=None) -> TestClient:
    """`accounts`: list[Account] to return, or an Exception to raise, from the account lookup."""
    http = httpx.AsyncClient(transport=transport or httpx.MockTransport(lambda r: httpx.Response(404)))

    async def fetch_accounts(cookies):
        if isinstance(accounts, Exception):
            raise accounts
        return list(accounts or [])

    app = create_app(paths, source_factory=lambda: source, accounts_fetcher=fetch_accounts,
                     http_client=http, offline=True)
    return TestClient(app)


def wait_for_sync(client: TestClient, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        status = client.get("/api/sync/status").json()
        if not status["running"]:
            return status
        if time.monotonic() > deadline:
            raise TimeoutError("sync did not finish")
        time.sleep(0.02)
```

Replace `test_health` in `backend/tests/test_health.py` (keep the other three tests and imports, drop the now-unused `create_app` import):

```python
from helpers import make_client


def test_health(paths):
    with make_client(paths) as client:
        assert client.get("/api/health").json() == {"ok": True}
```

`backend/tests/test_api_settings.py`:

```python
import logging

from app.settings.envfile import read_env
from app.sync.hoyolab import Account, HoyolabError
from fakes import FakeSource
from helpers import make_client, seed_game, wait_for_sync, yatta_transport

ACCOUNT = Account(uid=800000001, server="os_usa", nickname="TestTraveler", level=60)
OTHER = Account(uid=800000002, server="os_euro", nickname="Alt", level=20)
COOKIES = {"ltuid_v2": "SECRET-LTUID-111", "ltoken_v2": "SECRET-LTOKEN-222", "ltmid_v2": "SECRET-LTMID-333"}
SECRETS = list(COOKIES.values())


def test_settings_defaults(paths):
    with make_client(paths) as client:
        body = client.get("/api/settings").json()
    assert body["connection"] == {"status": "missing", "uid": None}
    assert body["sync_interval_minutes"] == 10
    assert body["default_targets"] == {"level": 90, "normal": 8, "skill": 8, "burst": 8, "weapon_level": 90}
    assert body["level_caps"] == [20, 40, 50, 60, 70, 80, 90]
    assert body["gamedata"] == {"fetched_at": None, "last_error": None, "count": 0}


def test_put_settings_validates_and_saves(paths):
    with make_client(paths) as client:
        assert client.put("/api/settings", json={"sync_interval_minutes": 0}).status_code == 422
        bad_targets = {"level": 90, "normal": 11, "skill": 8, "burst": 8, "weapon_level": 90}
        assert client.put("/api/settings", json={"default_targets": bad_targets}).status_code == 422
        good = {"level": 80, "normal": 6, "skill": 6, "burst": 6, "weapon_level": 80}
        body = client.put("/api/settings", json={"sync_interval_minutes": 30, "default_targets": good}).json()
    assert body["sync_interval_minutes"] == 30 and body["default_targets"] == good


def test_connect_single_account_writes_env_and_syncs(paths):
    source = FakeSource()  # roster ids missing from game data are fine here
    with make_client(paths, source=source, accounts=[ACCOUNT]) as client:
        r = client.post("/api/settings/hoyolab", json=COOKIES)
        assert r.status_code == 200
        assert r.json() == {"status": "connected", "uid": 800000001}
        status = wait_for_sync(client)
        settings = client.get("/api/settings").json()
    env = read_env(paths.env_file)
    assert env["LTOKEN_V2"] == "SECRET-LTOKEN-222"
    assert env["GENSHIN_UID"] == "800000001" and env["GENSHIN_REGION"] == "os_usa"
    assert status["runs"][0]["trigger"] == "connect"
    assert settings["connection"] == {"status": "connected", "uid": 800000001}


def test_connect_multiple_accounts_asks_then_accepts_choice(paths):
    with make_client(paths, source=FakeSource(), accounts=[ACCOUNT, OTHER]) as client:
        r = client.post("/api/settings/hoyolab", json=COOKIES)
        assert r.json()["status"] == "choose"
        assert [a["uid"] for a in r.json()["accounts"]] == [800000001, 800000002]
        assert not paths.env_file.exists()
        r = client.post("/api/settings/hoyolab", json={**COOKIES, "uid": 800000002})
        assert r.json() == {"status": "connected", "uid": 800000002}
        wait_for_sync(client)
    assert read_env(paths.env_file)["GENSHIN_REGION"] == "os_euro"


def test_connect_failure_writes_nothing(paths, caplog):
    caplog.set_level(logging.DEBUG)
    with make_client(paths, accounts=HoyolabError("Please login")) as client:
        r = client.post("/api/settings/hoyolab", json=COOKIES)
    assert r.status_code == 400 and "Please login" in r.json()["detail"]
    assert not paths.env_file.exists()
    assert not any(secret in caplog.text for secret in SECRETS)


def test_connect_requires_ltuid_and_ltoken(paths):
    with make_client(paths, accounts=[ACCOUNT]) as client:
        r = client.post("/api/settings/hoyolab", json={"ltuid_v2": "  ", "ltoken_v2": "x"})
    assert r.status_code == 400


def test_connect_cleans_pasted_values(paths):
    messy = {"ltuid_v2": ' "SECRET-LTUID-111" ', "ltoken_v2": "ltoken_v2=SECRET-LTOKEN-222;",
             "ltmid_v2": "'SECRET-LTMID-333'"}
    with make_client(paths, source=FakeSource(), accounts=[ACCOUNT]) as client:
        assert client.post("/api/settings/hoyolab", json=messy).status_code == 200
        wait_for_sync(client)
    env = read_env(paths.env_file)
    assert (env["LTUID_V2"], env["LTOKEN_V2"], env["LTMID_V2"]) == tuple(SECRETS)


def test_connect_clears_stale_optional_keys(paths):
    paths.env_file.write_text("PORT=9000\nCOOKIE_TOKEN_V2=old-token\n", encoding="utf-8")
    with make_client(paths, source=FakeSource(), accounts=[ACCOUNT]) as client:
        client.post("/api/settings/hoyolab", json=COOKIES)
        wait_for_sync(client)
    env = read_env(paths.env_file)
    assert "COOKIE_TOKEN_V2" not in env and env["PORT"] == "9000"


def test_no_endpoint_leaks_cookie_values(paths, caplog):
    caplog.set_level(logging.DEBUG)
    seed_game(_sf_for(paths))
    with make_client(paths, source=FakeSource(), accounts=[ACCOUNT]) as client:
        client.post("/api/settings/hoyolab", json=COOKIES)
        wait_for_sync(client)
        bodies = [client.get(p).text for p in
                  ("/api/settings", "/api/sync/status", "/api/characters", "/api/dashboard")]
    for text in [*bodies, caplog.text]:
        assert not any(secret in text for secret in SECRETS)


def test_manual_sync_rate_limit_and_not_connected(paths):
    with make_client(paths, source=None) as client:
        assert client.post("/api/sync?trigger=manual").json()["reason"] == "not_connected"
    with make_client(paths, source=FakeSource()) as client:
        assert client.post("/api/sync?trigger=manual").json()["started"] is True
        wait_for_sync(client)
        r = client.post("/api/sync?trigger=manual")
        assert r.status_code == 429 and "Retry-After" in r.headers


def test_gamedata_refresh_endpoint(paths):
    with make_client(paths, transport=yatta_transport()) as client:
        body = client.post("/api/gamedata/refresh").json()
    assert body["refreshed"] is True and body["gamedata"]["count"] == 6


def _sf_for(paths):
    from app.db.engine import make_engine, make_session_factory, migrate
    engine = make_engine(paths.db_file)
    migrate(engine)
    return make_session_factory(engine)
```

Note: `test_no_endpoint_leaks_cookie_values` calls `/api/characters` and `/api/dashboard`, which arrive in Task 11; until then those two return 404 pages that also must not leak. The test passes in both states.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api_settings.py tests/test_health.py -v`
Expected: FAIL with `TypeError: create_app() got an unexpected keyword argument` or `ModuleNotFoundError: No module named 'app.context'`

- [ ] **Step 3: Write the context and connect service**

`backend/app/context.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx
from fastapi import Request
from sqlalchemy.orm import sessionmaker

from app.config import Paths
from app.settings.envfile import cookies_from_env, read_env
from app.settings.store import get_setting
from app.sync.hoyolab import Account, GenshinPySource, HoyolabSource
from app.sync.runner import SyncManager


@dataclass
class AppContext:
    paths: Paths
    session_factory: sessionmaker
    http: httpx.AsyncClient
    offline: bool
    sync: SyncManager
    accounts_fetcher: Callable[[dict[str, str]], Awaitable[list[Account]]]


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def make_source_factory(paths: Paths, session_factory: sessionmaker) -> Callable[[], HoyolabSource | None]:
    def factory() -> HoyolabSource | None:
        env = read_env(paths.env_file)
        cookies = cookies_from_env(env)
        if "ltuid_v2" not in cookies or "ltoken_v2" not in cookies or not env.get("GENSHIN_UID"):
            return None
        with session_factory() as s:
            if get_setting(s, "hoyolab_status") == "expired":
                return None
        return GenshinPySource(cookies, int(env["GENSHIN_UID"]))

    return factory
```

`backend/app/settings/connect.py`:

```python
from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from sqlalchemy.orm import sessionmaker

from app.settings.envfile import COOKIE_KEYS, update_env
from app.settings.store import set_setting
from app.sync.hoyolab import Account, HoyolabError


class ConnectError(Exception):
    pass


@dataclass
class ConnectResult:
    status: str  # "connected" | "choose"
    uid: int | None = None
    accounts: list[Account] = field(default_factory=list)


async def connect(env_file: Path, session_factory: sessionmaker, cookies: dict[str, str],
                  chosen_uid: int | None,
                  fetch_accounts: Callable[[dict[str, str]], Awaitable[list[Account]]]) -> ConnectResult:
    """Test cookies first; only write .env after HoYoLAB accepts them."""
    try:
        accounts = await fetch_accounts(cookies)
    except HoyolabError as e:
        raise ConnectError(str(e) or "HoYoLAB rejected these cookies.") from None
    if not accounts:
        raise ConnectError("No Genshin Impact account is linked to this HoYoLAB login.")
    if chosen_uid is not None:
        account = next((a for a in accounts if a.uid == chosen_uid), None)
        if account is None:
            raise ConnectError("That UID is not linked to this HoYoLAB login.")
    elif len(accounts) == 1:
        account = accounts[0]
    else:
        return ConnectResult("choose", accounts=list(accounts))

    values = {k.upper(): cookies.get(k, "") for k in COOKIE_KEYS}  # "" clears stale optional keys
    values.update(GENSHIN_UID=str(account.uid), GENSHIN_REGION=account.server)
    update_env(env_file, values)
    with session_factory.begin() as s:
        set_setting(s, "hoyolab_status", "connected")
    return ConnectResult("connected", uid=account.uid)
```

- [ ] **Step 4: Write the routers**

`backend/app/api/__init__.py`:

```python
from app.api import settings, sync

ROUTERS = [settings.router, sync.router]
```

`backend/app/api/settings.py`:

```python
from dataclasses import asdict

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from sqlalchemy.orm import Session

from app.config import LEVEL_CAPS
from app.context import AppContext, get_ctx
from app.gamedata.service import gamedata_status, refresh
from app.schemas import TargetsIn
from app.settings.connect import ConnectError, connect
from app.settings.envfile import COOKIE_KEYS, connection_status, read_env
from app.settings.store import get_setting, set_setting

router = APIRouter()


class SettingsIn(BaseModel):
    sync_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    default_targets: TargetsIn | None = None


class HoyolabIn(BaseModel):
    ltuid_v2: str = ""
    ltoken_v2: str = ""
    ltmid_v2: str = ""
    account_id_v2: str = ""
    account_mid_v2: str = ""
    cookie_token_v2: str = ""
    uid: int | None = None

    @field_validator(*COOKIE_KEYS, mode="before")
    @classmethod
    def _clean(cls, value, info: ValidationInfo) -> str:
        """Accept values pasted with spaces, quotes, a `name=` prefix, or a trailing `;`."""
        text = "" if value is None else str(value).strip()
        prefix = f"{info.field_name}="
        if text.startswith(prefix):
            text = text[len(prefix):]
        return text.strip().rstrip(";").strip().strip("\"'").strip()

    def cookies(self) -> dict[str, str]:
        return {k: getattr(self, k) for k in COOKIE_KEYS if getattr(self, k)}


def settings_payload(ctx: AppContext, s: Session) -> dict:
    env = read_env(ctx.paths.env_file)
    return {
        "connection": connection_status(env, get_setting(s, "hoyolab_status")),
        "sync_interval_minutes": get_setting(s, "sync_interval_minutes"),
        "default_targets": get_setting(s, "default_targets"),
        "level_caps": LEVEL_CAPS,
        "gamedata": gamedata_status(s),
    }


@router.get("/settings")
def get_settings(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        return settings_payload(ctx, s)


@router.put("/settings")
def put_settings(body: SettingsIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory.begin() as s:
        if body.sync_interval_minutes is not None:
            set_setting(s, "sync_interval_minutes", body.sync_interval_minutes)
        if body.default_targets is not None:
            set_setting(s, "default_targets", body.default_targets.model_dump())
        return settings_payload(ctx, s)


@router.post("/settings/hoyolab")
async def connect_hoyolab(body: HoyolabIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    cookies = body.cookies()
    if "ltuid_v2" not in cookies or "ltoken_v2" not in cookies:
        raise HTTPException(400, "ltuid_v2 and ltoken_v2 are required.")
    try:
        result = await connect(ctx.paths.env_file, ctx.session_factory, cookies, body.uid,
                               ctx.accounts_fetcher)
    except ConnectError as e:
        raise HTTPException(400, str(e)) from None
    if result.status == "choose":
        return {"status": "choose", "accounts": [asdict(a) for a in result.accounts]}
    await ctx.sync.request("connect")
    return {"status": "connected", "uid": result.uid}


@router.post("/gamedata/refresh")
async def refresh_gamedata(ctx: AppContext = Depends(get_ctx)) -> dict:
    refreshed = await refresh(ctx.session_factory, ctx.http, force=True)
    with ctx.session_factory() as s:
        return {"refreshed": refreshed, "gamedata": gamedata_status(s)}
```

`backend/app/api/sync.py`:

```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.context import AppContext, get_ctx
from app.db.models import SyncRun
from app.sync.runner import SyncTooSoon
from app.timeutil import iso

router = APIRouter()


def run_dict(run: SyncRun) -> dict:
    return {
        "id": run.id, "trigger": run.trigger, "started_at": iso(run.started_at),
        "finished_at": iso(run.finished_at), "parts": run.parts,
    }


@router.post("/sync")
async def start_sync(trigger: Literal["auto", "manual"] = "auto", ctx: AppContext = Depends(get_ctx)) -> dict:
    try:
        result = await ctx.sync.request(trigger)
    except SyncTooSoon as e:
        raise HTTPException(429, f"Wait {e.retry_after}s before syncing again.",
                            headers={"Retry-After": str(e.retry_after)}) from None
    return {"run_id": result.run_id, "started": result.started, "reason": result.reason}


@router.get("/sync/status")
def sync_status(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        runs = s.scalars(select(SyncRun).order_by(SyncRun.id.desc()).limit(10)).all()
        return {"running": ctx.sync.running, "runs": [run_dict(r) for r in runs]}
```

- [ ] **Step 5: Replace `main.py`**

`backend/app/main.py`:

```python
"""App factory: database, shared HTTP client, sync manager, API routers, built frontend."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app import config
from app.api import ROUTERS
from app.config import FRONTEND_BUILD, Paths, default_paths
from app.context import AppContext, make_source_factory
from app.db.engine import make_engine, make_session_factory, migrate
from app.gamedata.service import refresh
from app.sync.hoyolab import fetch_accounts
from app.sync.runner import SyncManager

log = logging.getLogger(__name__)
USER_AGENT = "GenshinTracker/0.1 (local personal tool)"


def create_app(paths: Paths | None = None, *, source_factory=None, accounts_fetcher=None,
               http_client: httpx.AsyncClient | None = None, offline: bool | None = None) -> FastAPI:
    paths = paths or default_paths()
    paths.ensure()
    engine = make_engine(paths.db_file)
    migrate(engine)
    session_factory = make_session_factory(engine)
    http = http_client or httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    is_offline = config.offline() if offline is None else offline

    async def on_unknown_ids(_ids: set[int]) -> None:
        if not is_offline:
            await refresh(session_factory, http, force=True)

    sync = SyncManager(session_factory, paths.db_file, paths.backups,
                       source_factory or make_source_factory(paths, session_factory), on_unknown_ids)
    ctx = AppContext(paths=paths, session_factory=session_factory, http=http, offline=is_offline,
                     sync=sync, accounts_fetcher=accounts_fetcher or fetch_accounts)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        task = None if is_offline else asyncio.create_task(refresh(session_factory, http))
        yield
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if http_client is None:
            await http.aclose()
        engine.dispose()

    app = FastAPI(title="GenshinTracker", lifespan=lifespan)
    app.state.ctx = ctx

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    for router in ROUTERS:
        app.include_router(router, prefix="/api")
    _mount_frontend(app, FRONTEND_BUILD)
    return app


def _mount_frontend(app: FastAPI, build_dir: Path) -> None:
    index = build_dir / "index.html"
    if not index.exists():
        @app.get("/", include_in_schema=False)
        def _not_built() -> HTMLResponse:
            return HTMLResponse("<h1>Frontend not built</h1><p>Run <code>python run.py</code> "
                                "or <code>cd frontend; npm install; npm run build</code>.</p>")
        return

    root = build_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def _spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = (build_dir / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: all tests pass (Tasks 1–10).

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat: app wiring, HoYoLAB connect flow, settings and sync API"
```

---

### Task 11: Characters, dashboard, and image API

**Files:**
- Create: `backend/app/api/characters.py`, `backend/app/api/dashboard.py`, `backend/app/api/img.py`, `backend/tests/test_api_characters.py`
- Modify: `backend/app/api/__init__.py`

**Interfaces:**
- Consumes: Tasks 1–10.
- Produces:
  - `characters.goal_targets(row: CharacterGoal | None) -> Targets | None`; `characters.character_payload(game, owned, goal_row) -> dict` with keys `id, slug, name, rarity, element, weapon_type, icon, splash, owned, level, constellation, friendship, talents, weapon, goal, targets, status, prefarming, progress`
  - `GET /api/characters` (list), `GET /api/characters/{slug}` (adds `artifacts` sorted by slot and `stats`), `PUT /api/characters/{id}/goal` body `{goal?: "none"|"want"|"build", targets?: TargetsIn}`
  - `GET /api/dashboard` → `{connection, notes: {resin, resin_max, resin_full_at, commissions_done, commissions_max, realm_currency, realm_currency_max, expeditions, fetched_at} | null, building: {count, average_progress}}`
  - `GET /api/img/remote?url=`, `GET /api/img/{name}`

- [ ] **Step 1: Write the failing test**

`backend/tests/test_api_characters.py`:

```python
from datetime import datetime

import httpx

from app.db.engine import make_engine, make_session_factory, migrate
from app.db.models import CharacterGoal, GameCharacter
from app.sync.persist import save_details, save_notes, save_roster
from app.timeutil import utcnow
from fakes import NOTES, make_detail, make_roster
from helpers import make_client, seed_game


def sf_for(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    return make_session_factory(engine)


def setup_data(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with sf.begin() as s:
        s.add(GameCharacter(id=10000999, name="Futurechar", slug="futurechar", rarity=5, element="Cryo",
                            weapon_type="Catalyst", region=None, icon="UI_AvatarIcon_Futurechar",
                            splash="UI_Gacha_AvatarImg_Futurechar", release_at=datetime(2100, 1, 1)))
        now = utcnow()
        save_roster(s, [make_roster(10000032, level=80, name="Bennett"),
                        make_roster(10000089, level=90, name="Furina"),
                        make_roster(10000005, raw_id=10000007, name="Traveler", element="Geo")], now)
        save_details(s, [make_detail(10000032, talents=(4, 8, 8)), make_detail(10000089)])
        save_notes(s, NOTES, now)
        s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, updated_at=now))
        s.add(CharacterGoal(character_id=10000073, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, updated_at=now))
    return sf


def by_slug(items):
    return {c["slug"]: c for c in items}


def test_list_statuses_and_visibility(paths):
    setup_data(paths)
    with make_client(paths) as client:
        chars = by_slug(client.get("/api/characters").json())
    assert chars["bennett"]["status"] == "building"
    assert chars["bennett"]["progress"] == round((80 / 90 + 4 / 8 + 1 + 1) / 4, 4)
    assert chars["furina"]["status"] == "obtained" and chars["furina"]["progress"] is None
    assert chars["nahida"]["status"] == "wanted" and chars["nahida"]["prefarming"] is True
    assert chars["xiangling"]["status"] == "unobtained" and chars["xiangling"]["targets"] is None
    assert "futurechar" not in chars  # unreleased, not owned


def test_traveler_uses_variant_icon_and_element(paths):
    setup_data(paths)
    with make_client(paths) as client:
        trav = by_slug(client.get("/api/characters").json())["traveler"]
    assert trav["icon"] == "UI_AvatarIcon_PlayerGirl"
    assert trav["splash"] == "UI_Gacha_AvatarImg_PlayerGirl"
    assert trav["element"] == "Geo"


def test_owned_character_without_game_data_is_placeholder(paths):
    sf = sf_for(paths)
    with sf.begin() as s:
        save_roster(s, [make_roster(10000777, name="Brandnew", element="Hydro")], utcnow())
    with make_client(paths) as client:
        chars = by_slug(client.get("/api/characters").json())
        detail = client.get("/api/characters/id-10000777")
    c = chars["id-10000777"]
    assert (c["name"], c["status"], c["element"], c["icon"], c["rarity"]) == \
        ("Brandnew", "obtained", "Hydro", None, 0)
    assert detail.status_code == 200


def test_detail_includes_artifacts_and_stats(paths):
    setup_data(paths)
    with make_client(paths) as client:
        d = client.get("/api/characters/bennett").json()
        missing = client.get("/api/characters/nobody")
    assert d["artifacts"][0]["set_name"] == "Noblesse Oblige"
    assert d["stats"] == [{"name": "HP", "value": "20000"}]
    assert d["talents"] == {"normal": 4, "skill": 8, "burst": 8}
    assert missing.status_code == 404


def test_set_goal_build_fills_defaults_and_leaving_keeps_targets(paths):
    setup_data(paths)
    with make_client(paths) as client:
        c = client.put("/api/characters/10000089/goal", json={"goal": "build"}).json()
        assert c["status"] == "building"
        assert c["targets"] == {"level": 90, "normal": 8, "skill": 8, "burst": 8, "weapon_level": 90}
        custom = {"level": 80, "normal": 6, "skill": 9, "burst": 9, "weapon_level": 80}
        client.put("/api/characters/10000089/goal", json={"targets": custom})
        c = client.put("/api/characters/10000089/goal", json={"goal": "none"}).json()
        assert c["status"] == "obtained" and c["targets"] == custom
        c = client.put("/api/characters/10000089/goal", json={"goal": "build"}).json()
        assert c["targets"] == custom


def test_set_goal_validation_and_404(paths):
    setup_data(paths)
    with make_client(paths) as client:
        assert client.put("/api/characters/10000089/goal", json={"goal": "maybe"}).status_code == 422
        assert client.put("/api/characters/1/goal", json={"goal": "build"}).status_code == 404


def test_dashboard(paths):
    with make_client(paths) as client:
        empty = client.get("/api/dashboard").json()
    assert empty["notes"] is None and empty["building"] == {"count": 0, "average_progress": None}
    setup_data(paths)
    with make_client(paths) as client:
        d = client.get("/api/dashboard").json()
    assert d["notes"]["resin"] == 153 and d["notes"]["resin_full_at"].endswith("Z")
    assert d["building"]["count"] == 1
    assert d["connection"]["status"] == "missing"


def test_img_routes(paths):
    def handler(request):
        return httpx.Response(200, content=b"\x89PNG", headers={"content-type": "image/png"})

    with make_client(paths, transport=httpx.MockTransport(handler)) as client:
        named = client.get("/api/img/UI_AvatarIcon_Bennett")
        bad = client.get("/api/img/..%2Fsecret")
        remote_bad = client.get("/api/img/remote", params={"url": "https://evil.com/a.png"})
    # make_client runs offline=True, so named images come back as the placeholder, uncached
    assert named.status_code == 200 and named.headers["cache-control"] == "no-store"
    assert bad.status_code in (400, 404)
    assert remote_bad.status_code == 400
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_api_characters.py -v`
Expected: FAIL — `/api/characters` returns 404 (assertion errors / `KeyError`)

- [ ] **Step 3: Write minimal implementation**

`backend/app/api/characters.py`:

```python
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.context import AppContext, get_ctx
from app.db.models import CharacterGoal, GameCharacter, OwnedArtifact, OwnedCharacter
from app.domain import Current, Targets, derive_status, progress, resolve_targets
from app.gamedata.yatta import splash_for
from app.schemas import TargetsIn
from app.settings.store import default_targets
from app.timeutil import utcnow

router = APIRouter()


class GoalIn(BaseModel):
    goal: Literal["none", "want", "build"] | None = None
    targets: TargetsIn | None = None


def goal_targets(row: CharacterGoal | None) -> Targets | None:
    if row is None or row.target_level is None:
        return None
    return Targets(row.target_level, row.target_normal, row.target_skill, row.target_burst,
                   row.target_weapon_level)


def character_payload(g: GameCharacter | None, o: OwnedCharacter | None, goal_row: CharacterGoal | None) -> dict:
    goal = goal_row.goal if goal_row else "none"
    status, prefarming = derive_status(o is not None, goal)
    targets = goal_targets(goal_row)
    cid = g.id if g is not None else o.character_id
    icon = (o.icon if o is not None and o.icon else None) or (g.icon if g is not None else None)
    talents = None
    if o is not None and o.talent_normal is not None:
        talents = {"normal": o.talent_normal, "skill": o.talent_skill, "burst": o.talent_burst}
    prog = None
    if status == "building" and targets is not None:
        prog = progress(Current(o.level, o.talent_normal, o.talent_skill, o.talent_burst), targets)
    return {
        "id": cid,
        "slug": g.slug if g is not None else f"id-{cid}",
        "name": g.name if g is not None else o.name,
        "rarity": g.rarity if g is not None else 0,
        "element": (o.element if o is not None and o.element else None) or (g.element if g is not None else None),
        "weapon_type": g.weapon_type if g is not None else None,
        "icon": icon,
        "splash": splash_for(icon) if icon else None,
        "owned": o is not None,
        "level": o.level if o else None,
        "constellation": o.constellation if o else None,
        "friendship": o.friendship if o else None,
        "talents": talents,
        "weapon": None if o is None else {
            "name": o.weapon_name, "icon": o.weapon_icon, "rarity": o.weapon_rarity,
            "level": o.weapon_level, "refinement": o.weapon_refinement,
        },
        "goal": goal,
        "targets": targets.to_dict() if targets else None,
        "status": status,
        "prefarming": prefarming,
        "progress": prog,
    }


def _all(s: Session) -> list[tuple[GameCharacter | None, OwnedCharacter | None, CharacterGoal | None]]:
    games = {g.id: g for g in s.scalars(select(GameCharacter))}
    owned = {o.character_id: o for o in s.scalars(select(OwnedCharacter))}
    goals = {r.character_id: r for r in s.scalars(select(CharacterGoal))}
    now = utcnow()
    ids = [gid for gid, g in games.items() if g.release_at <= now or gid in owned]
    ids += [oid for oid in owned if oid not in games]
    return [(games.get(i), owned.get(i), goals.get(i)) for i in ids]


@router.get("/characters")
def list_characters(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        return [character_payload(g, o, r) for g, o, r in _all(s)]


@router.get("/characters/{slug}")
def get_character(slug: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        for g, o, r in _all(s):
            payload = character_payload(g, o, r)
            if payload["slug"] != slug:
                continue
            artifacts = [] if o is None else s.scalars(
                select(OwnedArtifact).where(OwnedArtifact.character_id == o.character_id)
                .order_by(OwnedArtifact.slot)).all()
            payload["artifacts"] = [
                {"slot": a.slot, "set_name": a.set_name, "rarity": a.rarity, "level": a.level,
                 "main_stat": a.main_stat, "substats": a.substats, "icon": a.icon}
                for a in artifacts
            ]
            payload["stats"] = o.stats if o is not None else []
            return payload
    raise HTTPException(404, "Unknown character")


@router.put("/characters/{character_id}/goal")
def set_goal(character_id: int, body: GoalIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory.begin() as s:
        g = s.get(GameCharacter, character_id)
        o = s.get(OwnedCharacter, character_id)
        if g is None and o is None:
            raise HTTPException(404, "Unknown character")
        row = s.get(CharacterGoal, character_id)
        if row is None:
            row = CharacterGoal(character_id=character_id, goal="none", updated_at=utcnow())
            s.add(row)
        new_goal = body.goal or row.goal
        if body.targets is not None:
            targets = Targets(**body.targets.model_dump())
        else:
            targets = resolve_targets(new_goal, goal_targets(row), default_targets(s))
        row.goal = new_goal
        if targets is not None:
            row.target_level, row.target_normal = targets.level, targets.normal
            row.target_skill, row.target_burst = targets.skill, targets.burst
            row.target_weapon_level = targets.weapon_level
        row.updated_at = utcnow()
        s.flush()
        return character_payload(g, o, row)
```

`backend/app/api/dashboard.py`:

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.characters import goal_targets
from app.context import AppContext, get_ctx
from app.db.models import CharacterGoal, LiveNotes, OwnedCharacter
from app.domain import Current, progress
from app.settings.envfile import connection_status, read_env
from app.settings.store import get_setting
from app.timeutil import iso

router = APIRouter()


def notes_payload(n: LiveNotes) -> dict:
    return {
        "resin": n.resin, "resin_max": n.resin_max, "resin_full_at": iso(n.resin_full_at),
        "commissions_done": n.commissions_done, "commissions_max": n.commissions_max,
        "realm_currency": n.realm_currency, "realm_currency_max": n.realm_currency_max,
        "expeditions": n.expeditions, "fetched_at": iso(n.fetched_at),
    }


@router.get("/dashboard")
def dashboard(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        owned = {o.character_id: o for o in s.scalars(select(OwnedCharacter))}
        values = []
        for row in s.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")):
            o, t = owned.get(row.character_id), goal_targets(row)
            if o is not None and t is not None:
                values.append(progress(Current(o.level, o.talent_normal, o.talent_skill, o.talent_burst), t))
        notes = s.get(LiveNotes, 1)
        return {
            "connection": connection_status(read_env(ctx.paths.env_file), get_setting(s, "hoyolab_status")),
            "notes": notes_payload(notes) if notes is not None else None,
            "building": {
                "count": len(values),
                "average_progress": round(sum(values) / len(values), 4) if values else None,
            },
        }
```

`backend/app/api/img.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.context import AppContext, get_ctx
from app.gamedata.images import ImageResult, get_named, get_remote

router = APIRouter()


def _response(result: ImageResult) -> Response:
    cache = "public, max-age=604800" if result.cached else "no-store"
    return Response(result.data, media_type=result.media_type, headers={"Cache-Control": cache})


@router.get("/img/remote")
async def img_remote(url: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    try:
        return _response(await get_remote(ctx.paths.img_cache, ctx.http, url, offline=ctx.offline))
    except ValueError:
        raise HTTPException(400, "Image host not allowed") from None


@router.get("/img/{name}")
async def img_named(name: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    try:
        return _response(await get_named(ctx.paths.img_cache, ctx.http, name, offline=ctx.offline))
    except ValueError:
        raise HTTPException(400, "Bad image name") from None
```

Replace `backend/app/api/__init__.py`:

```python
from app.api import characters, dashboard, img, settings, sync

ROUTERS = [settings.router, sync.router, characters.router, dashboard.router, img.router]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: all tests pass, including `test_no_endpoint_leaks_cookie_values` now exercising real characters/dashboard responses.

- [ ] **Step 5: Commit**

```bash
git add backend
git commit -m "feat: characters, dashboard, and image endpoints"
```

---

### Task 12: Run script, smoke check, demo seed, README

**Files:**
- Create: `run.py`, `backend/app/smoke.py`, `backend/app/devseed.py`, `backend/tests/test_devseed.py`, `README.md`

**Interfaces:**
- Consumes: `create_app`, `default_paths`, `GenshinPySource`, `read_env`, `cookies_from_env`, models.
- Produces: `python run.py [--no-build]`; `python -m app.smoke`; `python -m app.devseed --root PATH` (creates `PATH/data/tracker.db` with 8 characters: building Bennett & Furina, obtained Xiangling & Nahida, wanted Kazuha, pre-farming Neuvillette, unobtained Raiden Shogun & Xingqiu) — slugs `bennett, furina, xiangling, nahida, kazuha, neuvillette, raiden-shogun, xingqiu`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_devseed.py`:

```python
from app.config import Paths
from app.devseed import seed
from helpers import make_client


def test_devseed_creates_expected_statuses(tmp_path):
    seed(tmp_path)
    seed(tmp_path)  # re-seeding starts fresh
    paths = Paths(tmp_path)
    with make_client(paths) as client:
        chars = {c["slug"]: c for c in client.get("/api/characters").json()}
        dash = client.get("/api/dashboard").json()
    statuses = {slug: (c["status"], c["prefarming"]) for slug, c in chars.items()}
    assert statuses == {
        "bennett": ("building", False), "furina": ("building", False),
        "xiangling": ("obtained", False), "nahida": ("obtained", False),
        "kazuha": ("wanted", False), "neuvillette": ("wanted", True),
        "raiden-shogun": ("unobtained", False), "xingqiu": ("unobtained", False),
    }
    assert dash["notes"]["resin"] == 120
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_devseed.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.devseed'`

- [ ] **Step 3: Write the implementation**

`backend/app/devseed.py`:

```python
"""Fake data for demos and end-to-end tests: python -m app.devseed --root PATH"""
import argparse
from datetime import datetime
from pathlib import Path

from app.config import Paths
from app.db.engine import make_engine, make_session_factory, migrate
from app.db.models import CharacterGoal, GameCharacter, GameMeta
from app.sync.hoyolab import ArtifactInfo, DetailEntry, NotesInfo, RosterEntry, WeaponInfo
from app.sync.persist import save_details, save_notes, save_roster
from app.timeutil import iso, utcnow

# (id, name, slug, rarity, element, weapon, icon)
CHARACTERS = [
    (10000032, "Bennett", "bennett", 4, "Pyro", "Sword", "UI_AvatarIcon_Bennett"),
    (10000089, "Furina", "furina", 5, "Hydro", "Sword", "UI_AvatarIcon_Furina"),
    (10000023, "Xiangling", "xiangling", 4, "Pyro", "Polearm", "UI_AvatarIcon_Xiangling"),
    (10000073, "Nahida", "nahida", 5, "Dendro", "Catalyst", "UI_AvatarIcon_Nahida"),
    (10000047, "Kaedehara Kazuha", "kazuha", 5, "Anemo", "Sword", "UI_AvatarIcon_Kazuha"),
    (10000087, "Neuvillette", "neuvillette", 5, "Hydro", "Catalyst", "UI_AvatarIcon_Neuvillette"),
    (10000052, "Raiden Shogun", "raiden-shogun", 5, "Electro", "Polearm", "UI_AvatarIcon_Shougun"),
    (10000025, "Xingqiu", "xingqiu", 4, "Hydro", "Sword", "UI_AvatarIcon_Xingqiu"),
]
OWNED = {10000032: (80, (6, 8, 8)), 10000089: (90, (9, 9, 9)), 10000023: (80, (6, 6, 6)), 10000073: (90, (8, 8, 8))}
GOALS = {10000032: "build", 10000089: "build", 10000047: "want", 10000087: "build"}
WEAPON = WeaponInfo("Favonius Sword", "https://enka.network/ui/UI_EquipIcon_Sword_Favonius.png", 4, 90, 3)


def seed(root: Path) -> None:
    paths = Paths(root)
    paths.ensure()
    if paths.db_file.exists():
        paths.db_file.unlink()
    engine = make_engine(paths.db_file)
    migrate(engine)
    sf = make_session_factory(engine)
    now = utcnow()
    with sf.begin() as s:
        for cid, name, slug, rarity, element, weapon, icon in CHARACTERS:
            s.add(GameCharacter(id=cid, name=name, slug=slug, rarity=rarity, element=element,
                                weapon_type=weapon, region=None, icon=icon,
                                splash=icon.replace("UI_AvatarIcon_", "UI_Gacha_AvatarImg_"),
                                release_at=datetime(2020, 9, 28)))
        s.merge(GameMeta(key="characters_fetched_at", value=iso(now)))
        s.flush()
        names = {c[0]: c[1] for c in CHARACTERS}
        save_roster(s, [RosterEntry(cid, cid, names[cid], None, lvl, 1, 10, WEAPON)
                        for cid, (lvl, _t) in OWNED.items()], now)
        art = ArtifactInfo(1, "Noblesse Oblige", 5, 20, "HP 4780", ["CRIT Rate 3.9%", "ER 11.0%"],
                           "https://enka.network/ui/UI_RelicIcon_15007_4.png")
        save_details(s, [DetailEntry(cid, *t, WEAPON, [art], [{"name": "Max HP", "value": "20000"}])
                         for cid, (_l, t) in OWNED.items()])
        save_notes(s, NotesInfo(120, 200, 80 * 8 * 60, 3, 4, 900, 2400, []), now)
        for cid, goal in GOALS.items():
            build = goal == "build"
            s.add(CharacterGoal(character_id=cid, goal=goal, target_level=90 if build else None,
                                target_normal=8 if build else None, target_skill=8 if build else None,
                                target_burst=8 if build else None,
                                target_weapon_level=90 if build else None, updated_at=now))
    engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    seed(parser.parse_args().root.resolve())
```

`backend/app/smoke.py`:

```python
"""Live check against your real account (manual, never in CI): python -m app.smoke"""
import asyncio
import sys

from app.config import default_paths
from app.settings.envfile import cookies_from_env, read_env
from app.sync.hoyolab import GenshinPySource


async def main() -> None:
    env = read_env(default_paths().env_file)
    if not env.get("GENSHIN_UID"):
        sys.exit("Connect from the app's Settings page first (GENSHIN_UID missing in .env).")
    source = GenshinPySource(cookies_from_env(env), int(env["GENSHIN_UID"]))
    roster = await source.get_roster()
    print(f"roster: {len(roster)} characters")
    details = await source.get_details([r.raw_id for r in roster[:3]])
    for d in details:
        print(f"  {d.id}: talents {d.normal}/{d.skill}/{d.burst}, artifacts {len(d.artifacts)}, stats {len(d.stats)}")
    notes = await source.get_notes()
    print(f"notes: resin {notes.resin}/{notes.resin_max}, commissions "
          f"{notes.commissions_done}/{notes.commissions_max}, expeditions {len(notes.expeditions)}")


if __name__ == "__main__":
    asyncio.run(main())
```

`run.py` (repo root):

```python
"""Start GenshinTracker on http://127.0.0.1:<port>.  Usage: python run.py [--no-build]"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))


def ensure_frontend_built() -> None:
    if (ROOT / "frontend" / "build" / "index.html").exists():
        return
    npm = shutil.which("npm")
    if npm is None:
        print("Frontend is not built and npm was not found. Install Node.js (LTS), then run:\n"
              "  cd frontend; npm install; npm run build")
        return
    subprocess.run([npm, "install"], cwd=ROOT / "frontend", check=True)
    subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--no-build", action="store_true", help="skip building the frontend")
    args = parser.parse_args()

    from dotenv import dotenv_values

    from app.config import DEFAULT_PORT, default_paths

    env = dotenv_values(default_paths().env_file) if default_paths().env_file.exists() else {}
    port = int(os.environ.get("PORT") or env.get("PORT") or DEFAULT_PORT)
    if not args.no_build:
        ensure_frontend_built()

    import uvicorn

    print(f"GenshinTracker running at http://127.0.0.1:{port}")
    uvicorn.run("app.main:create_app", factory=True, host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
```

`README.md`:

````markdown
# GenshinTracker

A personal, locally run Genshin Impact tracker: your roster syncs from HoYoLAB automatically,
grouped by what you're building, own, want, or don't have yet.

> Fan project. Not affiliated with or endorsed by HoYoverse. Game data comes from community
> sources (Yatta, Enka) and is downloaded at runtime; no game assets are stored in this repo.

## Requirements

- Python 3.12+
- Node.js LTS (to build the web pages)

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e "backend[dev]"
python run.py
```

Open http://127.0.0.1:8765. The first `python run.py` builds the frontend (needs `npm`).

## Connect HoYoLAB

1. Log in at hoyolab.com in your browser.
2. Press F12 → Application (Firefox: Storage) → Cookies → `https://www.hoyolab.com`.
3. In the app, open **Settings → Connect HoYoLAB** and paste `ltuid_v2`, `ltoken_v2`, `ltmid_v2`
   (and the optional ones if present).

The values are tested first, then saved only to your local `.env`, which is git-ignored.
Treat them like a password.

## Development

```powershell
# backend tests (from backend/)
python -m pytest
# live check against your account (from backend/, after connecting)
python -m app.smoke
# frontend (from frontend/)
npm run dev      # http://localhost:5173, proxies /api to the backend on 8765
npm run check
npm test
npm run e2e      # needs the venv active; builds nothing, run `npm run build` first
```

Your data lives in `data/` (database, backups, image cache). Delete `data/` to start fresh.
````

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest -v`
Expected: all pass, including `test_devseed_creates_expected_statuses`.

Also run from the repo root: `python run.py --no-build` → prints `GenshinTracker running at http://127.0.0.1:8765`; `http://127.0.0.1:8765/api/health` returns `{"ok":true}` and `/` shows "Frontend not built". Stop with Ctrl+C.

- [ ] **Step 5: Commit**

```bash
git add run.py README.md backend
git commit -m "feat: run script, live smoke check, demo seed, README"
```

---

### Task 13: Frontend scaffold and pure display logic

**Files:**
- Create: `frontend/package.json`, `frontend/svelte.config.js`, `frontend/vite.config.ts`, `frontend/tsconfig.json`, `frontend/src/app.html`, `frontend/src/app.d.ts`, `frontend/src/app.css`, `frontend/src/routes/+layout.ts`, `frontend/src/routes/+layout.svelte` (minimal; replaced in Task 14), `frontend/src/routes/+page.svelte` (placeholder; replaced in Task 18), `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/img.ts`, `frontend/src/lib/status.ts`, `frontend/src/lib/time.ts`, `frontend/src/lib/syncLabel.ts`, `frontend/src/lib/status.test.ts`, `frontend/src/lib/time.test.ts`

**Interfaces:**
- Consumes: backend API shapes (Tasks 10–11).
- Produces: TS types `Goal, Status, Targets, Talents, Weapon, Character, Artifact, CharacterDetail, Connection, SyncPart, SyncRun, SyncStatus, Expedition, Notes, Dashboard, Settings, Account`; `api` object (methods `characters, character, setGoal, dashboard, settings, saveSettings, connect, refreshGamedata, startSync, syncStatus`), `ApiError`; `imgSrc(icon)`; `status.ts`: `SECTIONS, ELEMENTS, WEAPON_TYPES, deriveStatus, statusLine, progressTooltip, Filters, emptyFilters, matches, groupCharacters`; `time.ts`: `formatDuration(ms), timeAgo(iso, now)`; `syncLabel.ts`: `lastFinished, failedParts, syncLabel`.

- [ ] **Step 1: Create the project files**

`frontend/package.json`:

```json
{
  "name": "genshintracker-frontend",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "scripts": {
    "dev": "vite dev",
    "build": "vite build",
    "preview": "vite preview",
    "check": "svelte-kit sync && svelte-check --tsconfig ./tsconfig.json",
    "test": "vitest run",
    "e2e": "playwright test"
  },
  "devDependencies": {
    "@playwright/test": "^1.51.0",
    "@sveltejs/adapter-static": "^3.0.8",
    "@sveltejs/kit": "^2.20.0",
    "@sveltejs/vite-plugin-svelte": "^5.0.3",
    "svelte": "^5.25.0",
    "svelte-check": "^4.1.5",
    "typescript": "^5.8.2",
    "vite": "^6.2.0",
    "vitest": "^3.0.9"
  }
}
```

`frontend/svelte.config.js`:

```js
import adapter from '@sveltejs/adapter-static';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
export default {
	preprocess: vitePreprocess(),
	kit: { adapter: adapter({ fallback: 'index.html' }) }
};
```

`frontend/vite.config.ts`:

```ts
import { sveltekit } from '@sveltejs/kit/vite';
import { defineConfig } from 'vitest/config';

export default defineConfig({
	plugins: [sveltekit()],
	server: { proxy: { '/api': 'http://127.0.0.1:8765' } },
	test: { include: ['src/**/*.test.ts'] }
});
```

`frontend/tsconfig.json`:

```json
{
	"extends": "./.svelte-kit/tsconfig.json",
	"compilerOptions": {
		"strict": true,
		"moduleResolution": "bundler",
		"skipLibCheck": true,
		"sourceMap": true,
		"esModuleInterop": true,
		"resolveJsonModule": true,
		"allowJs": true,
		"checkJs": true
	}
}
```

`frontend/src/app.html`:

```html
<!doctype html>
<html lang="en">
	<head>
		<meta charset="utf-8" />
		<meta name="viewport" content="width=device-width, initial-scale=1" />
		<title>GenshinTracker</title>
		%sveltekit.head%
	</head>
	<body data-sveltekit-preload-data="hover">
		<div style="display: contents">%sveltekit.body%</div>
	</body>
</html>
```

`frontend/src/app.d.ts`:

```ts
declare global {
	namespace App {}
}
export {};
```

`frontend/src/routes/+layout.ts`:

```ts
// Single-page app: the backend serves index.html for every non-API path.
export const ssr = false;
export const prerender = false;
```

`frontend/src/routes/+layout.svelte` (temporary):

```svelte
<script lang="ts">
	import '../app.css';
	let { children } = $props();
</script>

{@render children()}
```

`frontend/src/routes/+page.svelte` (temporary):

```svelte
<h1>GenshinTracker</h1>
```

`frontend/src/app.css`:

```css
:root {
	--bg: #14141b;
	--panel: #1d1d27;
	--panel-2: #262633;
	--line: #34344a;
	--text: #e6e6ee;
	--muted: #9a9ab0;
	--accent: #4fd1a5;
	--building: #4fd1a5;
	--obtained: #8fa3ff;
	--wanted: #e8c15a;
	--unobtained: #6b6b7d;
	--warn: #f0a04b;
	--error: #ef6b6b;
	--r5: linear-gradient(160deg, #9b6a3c, #d6a253);
	--r4: linear-gradient(160deg, #5c4a8a, #9a78c9);
	--r0: linear-gradient(160deg, #3a3a48, #50505f);
	color-scheme: dark;
}
* { box-sizing: border-box; }
body {
	margin: 0;
	background: var(--bg);
	color: var(--text);
	font: 14px/1.45 system-ui, -apple-system, 'Segoe UI', sans-serif;
}
a { color: var(--accent); }
main { max-width: 1280px; margin: 0 auto; padding: 16px; }
h1 { font-size: 22px; margin: 4px 0 16px; }
h2 { font-size: 15px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
button, input, select {
	font: inherit;
	color: var(--text);
	background: var(--panel-2);
	border: 1px solid var(--line);
	border-radius: 6px;
	padding: 4px 10px;
}
button { cursor: pointer; }
button:disabled { opacity: 0.5; cursor: default; }
button.primary { background: var(--accent); color: #111; border-color: var(--accent); font-weight: 600; }
.panel { background: var(--panel); border: 1px solid var(--line); border-radius: 10px; padding: 14px; }
.muted { color: var(--muted); }
.error { color: var(--error); }
.chip { border-radius: 999px; padding: 2px 10px; font-size: 12px; }
.chip.on { background: var(--accent); color: #111; border-color: var(--accent); }
```

Install:

```powershell
cd frontend
npm install
```

Expected: completes; `node_modules/` created (git-ignored).

- [ ] **Step 2: Write the failing tests**

`frontend/src/lib/status.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import type { Character } from './types';
import { deriveStatus, emptyFilters, groupCharacters, progressTooltip, statusLine } from './status';

function char(over: Partial<Character>): Character {
	return {
		id: 1, slug: 'x', name: 'X', rarity: 4, element: 'Pyro', weapon_type: 'Sword',
		icon: 'UI_AvatarIcon_X', splash: null, owned: true, level: 80, constellation: 2,
		friendship: 10, talents: { normal: 6, skill: 8, burst: 8 }, weapon: null, goal: 'none',
		targets: null, status: 'obtained', prefarming: false, progress: null, ...over
	};
}

describe('deriveStatus', () => {
	it('matches backend rules', () => {
		expect(deriveStatus(false, 'none')).toEqual({ status: 'unobtained', prefarming: false });
		expect(deriveStatus(false, 'want')).toEqual({ status: 'wanted', prefarming: false });
		expect(deriveStatus(false, 'build')).toEqual({ status: 'wanted', prefarming: true });
		expect(deriveStatus(true, 'want')).toEqual({ status: 'obtained', prefarming: false });
		expect(deriveStatus(true, 'build')).toEqual({ status: 'building', prefarming: false });
	});
});

describe('statusLine', () => {
	it('shows level and constellation for obtained', () => {
		expect(statusLine(char({}))).toBe('Lv 80 · C2');
	});
	it('shows wanted / pre-farming', () => {
		expect(statusLine(char({ status: 'wanted', owned: false }))).toBe('Wanted');
		expect(statusLine(char({ status: 'wanted', owned: false, prefarming: true }))).toBe('Pre-farming');
	});
	it('is empty for unobtained', () => {
		expect(statusLine(char({ status: 'unobtained', owned: false }))).toBe('');
	});
});

describe('progressTooltip', () => {
	it('shows current → target', () => {
		const c = char({ status: 'building', targets: { level: 90, normal: 8, skill: 8, burst: 8, weapon_level: 90 } });
		expect(progressTooltip(c)).toBe('Lv 80→90 · 6/8/8 → 8/8/8');
	});
});

describe('groupCharacters', () => {
	const list = [
		char({ id: 1, name: 'Bennett', status: 'building', progress: 0.9 }),
		char({ id: 2, name: 'Furina', status: 'building', progress: 0.4, rarity: 5, element: 'Hydro' }),
		char({ id: 3, name: 'Xiangling', status: 'obtained' }),
		char({ id: 4, name: 'Nahida', status: 'obtained', rarity: 5, element: 'Dendro', weapon_type: 'Catalyst' }),
		char({ id: 5, name: 'Kazuha', status: 'wanted', owned: false, rarity: 5, element: 'Anemo' })
	];

	it('sorts building by progress ascending, others by rarity then element order', () => {
		const g = groupCharacters(list, emptyFilters());
		expect(g.building.map((c) => c.name)).toEqual(['Furina', 'Bennett']);
		expect(g.obtained.map((c) => c.name)).toEqual(['Nahida', 'Xiangling']);
		expect(g.wanted.map((c) => c.name)).toEqual(['Kazuha']);
		expect(g.unobtained).toEqual([]);
	});

	it('applies filters inside every section', () => {
		const g = groupCharacters(list, { ...emptyFilters(), elements: ['Pyro'] });
		expect(g.building.map((c) => c.name)).toEqual(['Bennett']);
		expect(g.obtained.map((c) => c.name)).toEqual(['Xiangling']);
		const s = groupCharacters(list, { ...emptyFilters(), search: 'nah' });
		expect(s.obtained.map((c) => c.name)).toEqual(['Nahida']);
		const w = groupCharacters(list, { ...emptyFilters(), weapons: ['Catalyst'], rarities: [5] });
		expect(w.obtained.map((c) => c.name)).toEqual(['Nahida']);
	});
});
```

`frontend/src/lib/time.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { formatDuration, timeAgo } from './time';
import { syncLabel } from './syncLabel';
import type { SyncStatus } from './types';

describe('formatDuration', () => {
	it('formats minutes and hours', () => {
		expect(formatDuration(0)).toBe('now');
		expect(formatDuration(-5)).toBe('now');
		expect(formatDuration(59_000)).toBe('1m');
		expect(formatDuration(3_600_000 + 5 * 60_000)).toBe('1h 5m');
	});
});

describe('timeAgo', () => {
	const now = Date.parse('2026-11-19T12:00:00Z');
	it('formats relative times', () => {
		expect(timeAgo('2026-11-19T11:59:30Z', now)).toBe('just now');
		expect(timeAgo('2026-11-19T11:57:00Z', now)).toBe('3 min ago');
		expect(timeAgo('2026-11-19T09:00:00Z', now)).toBe('3 h ago');
		expect(timeAgo('2026-11-17T12:00:00Z', now)).toBe('2 d ago');
	});
});

describe('syncLabel', () => {
	const now = Date.parse('2026-11-19T12:00:00Z');
	const run = (parts: SyncStatus['runs'][0]['parts'], finished: string | null = '2026-11-19T11:57:00Z') => ({
		id: 1, trigger: 'auto', started_at: '2026-11-19T11:56:50Z', finished_at: finished, parts
	});
	it('covers each state', () => {
		expect(syncLabel(null, now)).toBe('…');
		expect(syncLabel({ running: true, runs: [] }, now)).toBe('Syncing…');
		expect(syncLabel({ running: false, runs: [] }, now)).toBe('Not synced yet');
		expect(syncLabel({ running: false, runs: [run({ roster: { ok: true } })] }, now)).toBe('Synced 3 min ago');
		expect(
			syncLabel({ running: false, runs: [run({ roster: { ok: true }, notes: { ok: false, error: 'x' } })] }, now)
		).toBe('⚠ 1 part failed');
	});
});
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL — cannot resolve `./status`, `./time`, `./syncLabel`.

- [ ] **Step 4: Write the modules**

`frontend/src/lib/types.ts`:

```ts
export type Goal = 'none' | 'want' | 'build';
export type Status = 'building' | 'obtained' | 'wanted' | 'unobtained';

export interface Targets { level: number; normal: number; skill: number; burst: number; weapon_level: number }
export interface Talents { normal: number; skill: number; burst: number }
export interface Weapon { name: string; icon: string; rarity: number; level: number; refinement: number }

export interface Character {
	id: number;
	slug: string;
	name: string;
	rarity: number;
	element: string | null;
	weapon_type: string | null;
	icon: string | null;
	splash: string | null;
	owned: boolean;
	level: number | null;
	constellation: number | null;
	friendship: number | null;
	talents: Talents | null;
	weapon: Weapon | null;
	goal: Goal;
	targets: Targets | null;
	status: Status;
	prefarming: boolean;
	progress: number | null;
}

export interface Artifact {
	slot: number; set_name: string; rarity: number; level: number;
	main_stat: string; substats: string[]; icon: string;
}
export interface CharacterDetail extends Character {
	artifacts: Artifact[];
	stats: { name: string; value: string }[];
}

export interface Connection { status: 'connected' | 'expired' | 'missing'; uid: number | null }
export interface SyncPart { ok: boolean; error?: string; count?: number }
export interface SyncRun {
	id: number; trigger: string; started_at: string; finished_at: string | null;
	parts: Record<string, SyncPart>;
}
export interface SyncStatus { running: boolean; runs: SyncRun[] }

export interface Expedition { icon: string; finished: boolean; return_at: string }
export interface Notes {
	resin: number; resin_max: number; resin_full_at: string;
	commissions_done: number; commissions_max: number;
	realm_currency: number; realm_currency_max: number;
	expeditions: Expedition[]; fetched_at: string;
}
export interface Dashboard {
	connection: Connection;
	notes: Notes | null;
	building: { count: number; average_progress: number | null };
}
export interface Settings {
	connection: Connection;
	sync_interval_minutes: number;
	default_targets: Targets;
	level_caps: number[];
	gamedata: { fetched_at: string | null; last_error: string | null; count: number };
}
export interface Account { uid: number; server: string; nickname: string; level: number }
export type ConnectResponse = { status: 'connected'; uid: number } | { status: 'choose'; accounts: Account[] };
```

`frontend/src/lib/api.ts`:

```ts
import type {
	Character, CharacterDetail, ConnectResponse, Dashboard, Goal, Settings, SyncStatus, Targets
} from './types';

export class ApiError extends Error {
	constructor(public status: number, message: string) {
		super(message);
	}
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	const res = await fetch(`/api${path}`, {
		method,
		headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
		body: body === undefined ? undefined : JSON.stringify(body)
	});
	if (!res.ok) {
		let message = res.statusText;
		try {
			const j = await res.json();
			message = typeof j.detail === 'string' ? j.detail : JSON.stringify(j.detail);
		} catch {
			/* keep statusText */
		}
		throw new ApiError(res.status, message);
	}
	return (await res.json()) as T;
}

export const api = {
	characters: () => request<Character[]>('GET', '/characters'),
	character: (slug: string) => request<CharacterDetail>('GET', `/characters/${encodeURIComponent(slug)}`),
	setGoal: (id: number, body: { goal?: Goal; targets?: Targets }) =>
		request<Character>('PUT', `/characters/${id}/goal`, body),
	dashboard: () => request<Dashboard>('GET', '/dashboard'),
	settings: () => request<Settings>('GET', '/settings'),
	saveSettings: (body: { sync_interval_minutes?: number; default_targets?: Targets }) =>
		request<Settings>('PUT', '/settings', body),
	connect: (body: Record<string, string | number>) =>
		request<ConnectResponse>('POST', '/settings/hoyolab', body),
	refreshGamedata: () => request<{ refreshed: boolean }>('POST', '/gamedata/refresh'),
	startSync: (trigger: 'auto' | 'manual') =>
		request<{ run_id: number | null; started: boolean; reason: string }>('POST', `/sync?trigger=${trigger}`),
	syncStatus: () => request<SyncStatus>('GET', '/sync/status')
};

export function errorMessage(e: unknown): string {
	return e instanceof Error ? e.message : String(e);
}
```

`frontend/src/lib/img.ts`:

```ts
/** Route every image through the backend cache. Game art arrives as a UI_ name, HoYoLAB icons as URLs. */
export function imgSrc(icon: string | null | undefined): string | null {
	if (!icon) return null;
	if (/^https?:\/\//.test(icon)) return `/api/img/remote?url=${encodeURIComponent(icon)}`;
	return `/api/img/${encodeURIComponent(icon)}`;
}
```

`frontend/src/lib/status.ts`:

```ts
import type { Character, Goal, Status } from './types';

export const SECTIONS: { status: Status; label: string }[] = [
	{ status: 'building', label: 'Actively building' },
	{ status: 'obtained', label: 'Obtained' },
	{ status: 'wanted', label: 'Wanted' },
	{ status: 'unobtained', label: 'Unobtained' }
];
export const ELEMENTS = ['Pyro', 'Hydro', 'Anemo', 'Electro', 'Dendro', 'Cryo', 'Geo'];
export const WEAPON_TYPES = ['Sword', 'Claymore', 'Polearm', 'Bow', 'Catalyst'];

export function deriveStatus(owned: boolean, goal: Goal): { status: Status; prefarming: boolean } {
	if (owned) return { status: goal === 'build' ? 'building' : 'obtained', prefarming: false };
	if (goal === 'none') return { status: 'unobtained', prefarming: false };
	return { status: 'wanted', prefarming: goal === 'build' };
}

export function statusLine(c: Character): string {
	switch (c.status) {
		case 'building':
			return `${Math.round((c.progress ?? 0) * 100)}%`;
		case 'obtained':
			return `Lv ${c.level} · C${c.constellation}`;
		case 'wanted':
			return c.prefarming ? 'Pre-farming' : 'Wanted';
		default:
			return '';
	}
}

export function progressTooltip(c: Character): string {
	if (!c.targets) return '';
	const t = c.talents;
	const now = t ? `${t.normal}/${t.skill}/${t.burst}` : '?/?/?';
	return `Lv ${c.level ?? '?'}→${c.targets.level} · ${now} → ${c.targets.normal}/${c.targets.skill}/${c.targets.burst}`;
}

export interface Filters { elements: string[]; weapons: string[]; rarities: number[]; search: string }

export function emptyFilters(): Filters {
	return { elements: [], weapons: [], rarities: [], search: '' };
}

export function matches(c: Character, f: Filters): boolean {
	if (f.elements.length && !f.elements.includes(c.element ?? '')) return false;
	if (f.weapons.length && !f.weapons.includes(c.weapon_type ?? '')) return false;
	if (f.rarities.length && !f.rarities.includes(c.rarity)) return false;
	const q = f.search.trim().toLowerCase();
	return !q || c.name.toLowerCase().includes(q);
}

function elementRank(e: string | null): number {
	const i = ELEMENTS.indexOf(e ?? '');
	return i === -1 ? ELEMENTS.length : i;
}

export function groupCharacters(chars: Character[], f: Filters): Record<Status, Character[]> {
	const groups: Record<Status, Character[]> = { building: [], obtained: [], wanted: [], unobtained: [] };
	for (const c of chars) if (matches(c, f)) groups[c.status].push(c);
	groups.building.sort((a, b) => (a.progress ?? 0) - (b.progress ?? 0) || a.name.localeCompare(b.name));
	const byRarity = (a: Character, b: Character) =>
		b.rarity - a.rarity || elementRank(a.element) - elementRank(b.element) || a.name.localeCompare(b.name);
	groups.obtained.sort(byRarity);
	groups.wanted.sort(byRarity);
	groups.unobtained.sort(byRarity);
	return groups;
}
```

`frontend/src/lib/time.ts`:

```ts
export function formatDuration(ms: number): string {
	if (ms <= 0) return 'now';
	const totalMinutes = Math.ceil(ms / 60_000);
	const h = Math.floor(totalMinutes / 60);
	const m = totalMinutes % 60;
	return h ? `${h}h ${m}m` : `${m}m`;
}

export function timeAgo(iso: string, now: number): string {
	const ms = now - Date.parse(iso);
	if (ms < 60_000) return 'just now';
	const m = Math.floor(ms / 60_000);
	if (m < 60) return `${m} min ago`;
	const h = Math.floor(m / 60);
	if (h < 24) return `${h} h ago`;
	return `${Math.floor(h / 24)} d ago`;
}
```

`frontend/src/lib/syncLabel.ts`:

```ts
import { timeAgo } from './time';
import type { SyncRun, SyncStatus } from './types';

export function lastFinished(s: SyncStatus | null): SyncRun | null {
	return s?.runs.find((r) => r.finished_at) ?? null;
}

export function failedParts(run: SyncRun): string[] {
	return Object.entries(run.parts).filter(([, p]) => !p.ok).map(([name]) => name);
}

export function syncLabel(s: SyncStatus | null, now: number): string {
	if (!s) return '…';
	if (s.running) return 'Syncing…';
	const last = lastFinished(s);
	if (!last) return 'Not synced yet';
	const failed = failedParts(last);
	if (failed.length) return `⚠ ${failed.length} part${failed.length > 1 ? 's' : ''} failed`;
	return `Synced ${timeAgo(last.finished_at!, now)}`;
}
```

- [ ] **Step 5: Run tests and checks**

Run: `npm test` → Expected: all tests in `status.test.ts` and `time.test.ts` pass.
Run: `npm run check` → Expected: `svelte-check found 0 errors`.
Run: `npm run build` → Expected: `build/index.html` exists.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat: SvelteKit scaffold, API client, and display logic"
```

---

### Task 14: Layout — navigation, sync status, connection banners

**Files:**
- Create: `frontend/src/lib/sync.svelte.ts`
- Modify: `frontend/src/routes/+layout.svelte` (replace fully)

**Interfaces:**
- Consumes: `api`, `errorMessage` (Task 13), `syncLabel`, `failedParts`, `lastFinished`.
- Produces: `sync` store (Svelte 5 runes) with reactive fields `status: SyncStatus | null`, `connection: Connection | null`, `error: string | null`, `version: number` (increments after each finished sync — pages read it to refetch) and methods `start(trigger)`, `poll()`, `loadConnection()`. Layout renders nav with `data-testid="sync-label"` and the **Sync** button.

- [ ] **Step 1: Write the sync store**

`frontend/src/lib/sync.svelte.ts`:

```ts
import { api, errorMessage } from './api';
import type { Connection, SyncStatus } from './types';

class SyncStore {
	status = $state<SyncStatus | null>(null);
	connection = $state<Connection | null>(null);
	error = $state<string | null>(null);
	/** Increments whenever a sync finishes; pages read it inside $effect to refetch. */
	version = $state(0);
	#timer: ReturnType<typeof setTimeout> | null = null;
	#awaitingFinish = false;

	async loadConnection(): Promise<void> {
		try {
			this.connection = (await api.settings()).connection;
		} catch {
			/* nav still works without it */
		}
	}

	async start(trigger: 'auto' | 'manual'): Promise<void> {
		try {
			const r = await api.startSync(trigger);
			this.error = null;
			if (r.started || r.reason === 'joined') this.#awaitingFinish = true;
		} catch (e) {
			this.error = errorMessage(e);
		}
		await this.poll();
	}

	async poll(): Promise<void> {
		if (this.#timer) {
			clearTimeout(this.#timer);
			this.#timer = null;
		}
		const wasRunning = this.status?.running ?? false;
		try {
			this.status = await api.syncStatus();
		} catch (e) {
			this.error = errorMessage(e);
			return;
		}
		if (this.status.running) {
			this.#timer = setTimeout(() => this.poll(), 2000);
		} else if (wasRunning || this.#awaitingFinish) {
			this.#awaitingFinish = false;
			this.version += 1;
			await this.loadConnection();
		}
	}
}

export const sync = new SyncStore();
```

- [ ] **Step 2: Replace the layout**

`frontend/src/routes/+layout.svelte`:

```svelte
<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { afterNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import { sync } from '$lib/sync.svelte';
	import { failedParts, lastFinished, syncLabel } from '$lib/syncLabel';

	let { children } = $props();

	const NAV: { label: string; href?: string; phase?: number }[] = [
		{ label: 'Dashboard', href: '/' },
		{ label: 'Characters', href: '/characters' },
		{ label: 'Teams', phase: 4 },
		{ label: 'Inventory', phase: 2 },
		{ label: 'Events', phase: 5 },
		{ label: 'Map', phase: 5 },
		{ label: 'Wishes', phase: 3 },
		{ label: 'Profile', phase: 5 },
		{ label: 'Settings', href: '/settings' }
	];

	let now = $state(Date.now());
	let showDetails = $state(false);
	const last = $derived(lastFinished(sync.status));
	const failed = $derived(last ? failedParts(last) : []);

	function isActive(href: string): boolean {
		return href === '/' ? page.url.pathname === '/' : page.url.pathname.startsWith(href);
	}

	onMount(() => {
		sync.loadConnection();
		const t = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(t);
	});

	// "Sync on page load": every navigation asks for an auto sync; the backend decides if it's due.
	afterNavigate(() => {
		sync.start('auto');
	});
</script>

<nav class="topnav">
	<span class="brand">GenshinTracker</span>
	{#each NAV as item (item.label)}
		{#if item.href}
			<a href={item.href} class:active={isActive(item.href)}>{item.label}</a>
		{:else}
			<span class="disabled" title="Coming in phase {item.phase}">{item.label}</span>
		{/if}
	{/each}
	<div class="sync">
		<button
			type="button"
			class="label"
			class:warn={failed.length > 0}
			data-testid="sync-label"
			onclick={() => (showDetails = !showDetails)}
		>
			{syncLabel(sync.status, now)}
		</button>
		<button
			type="button"
			onclick={() => sync.start('manual')}
			disabled={sync.status?.running || sync.connection?.status !== 'connected'}
		>
			Sync
		</button>
		{#if showDetails && last}
			<div class="popover panel">
				<div class="muted">Last sync ({last.trigger})</div>
				{#each Object.entries(last.parts) as [name, part] (name)}
					<div>
						<b>{name}</b>:
						{#if part.ok}ok{#if part.count !== undefined} ({part.count}){/if}{:else}<span class="error"
								>{part.error}</span
							>{/if}
					</div>
				{/each}
			</div>
		{/if}
		{#if sync.error}<div class="sync-error error" title={sync.error}>{sync.error}</div>{/if}
	</div>
</nav>

{#if sync.connection?.status === 'expired'}
	<div class="banner warn">Your HoYoLAB login expired. <a href="/settings">Reconnect HoYoLAB</a></div>
{:else if sync.connection?.status === 'missing'}
	<div class="banner">Not connected to HoYoLAB yet. <a href="/settings">Connect HoYoLAB</a></div>
{/if}

<main>{@render children()}</main>

<style>
	.topnav {
		display: flex; align-items: center; gap: 14px; padding: 10px 16px;
		background: #101016; border-bottom: 1px solid var(--line); flex-wrap: wrap;
	}
	.brand { font-weight: 700; margin-right: 8px; }
	.topnav a { color: var(--text); text-decoration: none; padding-bottom: 2px; }
	.topnav a.active { border-bottom: 2px solid var(--accent); }
	.disabled { color: var(--unobtained); cursor: default; }
	.sync { margin-left: auto; display: flex; gap: 8px; align-items: center; position: relative; }
	.label { background: none; border: none; color: var(--muted); font-size: 12px; }
	.label.warn { color: var(--warn); }
	.popover { position: absolute; top: 34px; right: 0; z-index: 10; min-width: 260px; font-size: 12px; }
	.sync-error { position: absolute; top: 34px; right: 0; font-size: 12px; white-space: nowrap; }
	.banner { padding: 8px 16px; background: var(--panel-2); border-bottom: 1px solid var(--line); }
	.banner.warn { background: #3a2a14; }
</style>
```

- [ ] **Step 3: Check and build**

Run: `npm run check` → Expected: 0 errors.
Run: `npm run build` → Expected: success.

Manual check: in one terminal `python -m app.devseed --root ..\.e2e-data` (from `backend/`), then from the repo root with `$env:GT_ROOT = "$PWD\.e2e-data"; $env:GT_OFFLINE = "1"; python run.py --no-build`. Open http://127.0.0.1:8765 → nav shows Dashboard / Characters / greyed later pages / Settings; banner reads "Not connected to HoYoLAB yet"; sync label reads "Not synced yet"; the Sync button is disabled. Stop the server and clear the two env vars (`Remove-Item Env:GT_ROOT, Env:GT_OFFLINE`).

- [ ] **Step 4: Commit**

```bash
git add frontend
git commit -m "feat: top navigation with sync status and connection banners"
```

---

### Task 15: Characters page

**Files:**
- Create: `frontend/src/lib/GoalSwitch.svelte`, `frontend/src/lib/CharacterCard.svelte`, `frontend/src/lib/collapse.ts`, `frontend/src/lib/collapse.test.ts`, `frontend/src/routes/characters/+page.svelte`

**Interfaces:**
- Consumes: `api`, `errorMessage`, `imgSrc`, `status.ts` exports, `sync.version`.
- Produces: `GoalSwitch` props `{ goal: Goal; onchange: (g: Goal) => void; compact?: boolean }` (buttons named `None`, `Want`, `Build`); `CharacterCard` props `{ character: Character; onGoal: (g: Goal) => void }` with `data-testid="card-<slug>"`, a link (accessible name = character name) to `/characters/<slug>`, and `role="progressbar"` when building; section containers `data-testid="section-<status>"`; `collapse.ts`: `loadCollapsed(): Record<Status, boolean>`, `saveCollapsed(v)`.

- [ ] **Step 1: Write the failing test**

`frontend/src/lib/collapse.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadCollapsed, saveCollapsed } from './collapse';

describe('collapse state', () => {
	afterEach(() => vi.unstubAllGlobals());

	it('defaults to unobtained collapsed when storage is unavailable', () => {
		vi.stubGlobal('localStorage', {
			getItem: () => { throw new Error('blocked'); },
			setItem: () => { throw new Error('blocked'); }
		});
		expect(loadCollapsed()).toEqual({ building: false, obtained: false, wanted: false, unobtained: true });
		expect(() => saveCollapsed({ building: true, obtained: false, wanted: false, unobtained: true })).not.toThrow();
	});

	it('round-trips through storage', () => {
		const store = new Map<string, string>();
		vi.stubGlobal('localStorage', {
			getItem: (k: string) => store.get(k) ?? null,
			setItem: (k: string, v: string) => store.set(k, v)
		});
		saveCollapsed({ building: true, obtained: false, wanted: false, unobtained: false });
		expect(loadCollapsed().building).toBe(true);
		expect(loadCollapsed().unobtained).toBe(false);
	});
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test`
Expected: FAIL — cannot resolve `./collapse`.

- [ ] **Step 3: Write the components and page**

`frontend/src/lib/collapse.ts`:

```ts
import type { Status } from './types';

const KEY = 'gt.collapsed';
const DEFAULTS: Record<Status, boolean> = { building: false, obtained: false, wanted: false, unobtained: true };

export function loadCollapsed(): Record<Status, boolean> {
	try {
		const raw = localStorage.getItem(KEY);
		if (raw) return { ...DEFAULTS, ...JSON.parse(raw) };
	} catch {
		/* storage blocked or corrupt: use defaults */
	}
	return { ...DEFAULTS };
}

export function saveCollapsed(value: Record<Status, boolean>): void {
	try {
		localStorage.setItem(KEY, JSON.stringify(value));
	} catch {
		/* ignore */
	}
}
```

`frontend/src/lib/GoalSwitch.svelte`:

```svelte
<script lang="ts">
	import type { Goal } from './types';

	let { goal, onchange, compact = false }: { goal: Goal; onchange: (g: Goal) => void; compact?: boolean } =
		$props();

	const OPTIONS: { value: Goal; label: string }[] = [
		{ value: 'none', label: 'None' },
		{ value: 'want', label: 'Want' },
		{ value: 'build', label: 'Build' }
	];
</script>

<div class="goal-switch" class:compact role="group" aria-label="Goal">
	{#each OPTIONS as o (o.value)}
		<button
			type="button"
			class:active={goal === o.value}
			aria-pressed={goal === o.value}
			onclick={() => {
				if (goal !== o.value) onchange(o.value);
			}}>{o.label}</button
		>
	{/each}
</div>

<style>
	.goal-switch { display: inline-flex; border: 1px solid var(--line); border-radius: 8px; overflow: hidden; }
	.goal-switch button { border: none; border-radius: 0; background: var(--panel-2); padding: 4px 12px; }
	.goal-switch button.active { background: var(--accent); color: #111; font-weight: 600; }
	.compact button { padding: 2px 6px; font-size: 11px; }
</style>
```

`frontend/src/lib/CharacterCard.svelte`:

```svelte
<script lang="ts">
	import GoalSwitch from './GoalSwitch.svelte';
	import { imgSrc } from './img';
	import { progressTooltip, statusLine } from './status';
	import type { Character, Goal } from './types';

	let { character, onGoal }: { character: Character; onGoal: (g: Goal) => void } = $props();

	const src = $derived(imgSrc(character.icon));
	const pct = $derived(Math.round((character.progress ?? 0) * 100));
</script>

<div class="card r{character.rarity} st-{character.status}" data-testid="card-{character.slug}">
	<a href="/characters/{character.slug}" class="body" aria-label={character.name}>
		{#if src}<img {src} alt="" loading="lazy" />{:else}<div class="ph">?</div>{/if}
		<div class="name">{character.name}</div>
		{#if character.status === 'building'}
			<div
				class="bar"
				role="progressbar"
				aria-valuemin={0}
				aria-valuemax={100}
				aria-valuenow={pct}
				title={progressTooltip(character)}
			>
				<i style="width: {pct}%"></i>
			</div>
		{:else}
			<div class="sub">{statusLine(character)}</div>
		{/if}
	</a>
	<div class="switch">
		<GoalSwitch goal={character.goal} onchange={onGoal} compact />
	</div>
</div>

<style>
	.card { position: relative; width: 104px; border-radius: 10px; overflow: hidden; background: var(--panel-2); }
	.body { display: block; color: var(--text); text-decoration: none; }
	img, .ph { width: 104px; height: 104px; display: block; background: var(--r0); }
	.r5 img, .r5 .ph { background: var(--r5); }
	.r4 img, .r4 .ph { background: var(--r4); }
	.ph { display: grid; place-items: center; font-size: 32px; color: var(--muted); }
	.name { font-size: 12px; text-align: center; padding: 4px 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.sub { font-size: 11px; color: var(--muted); text-align: center; min-height: 20px; padding-bottom: 4px; }
	.bar { height: 5px; margin: 6px 8px 9px; background: #444; border-radius: 3px; }
	.bar i { display: block; height: 100%; background: var(--building); border-radius: 3px; }
	.st-building { outline: 2px solid var(--building); outline-offset: -2px; }
	.st-wanted { opacity: 0.85; }
	.st-unobtained img { filter: grayscale(1); opacity: 0.45; }
	.switch {
		position: absolute; top: 4px; left: 0; right: 0; display: flex; justify-content: center;
		opacity: 0; transition: opacity 0.12s;
	}
	.card:hover .switch, .card:focus-within .switch { opacity: 1; }
</style>
```

`frontend/src/routes/characters/+page.svelte`:

```svelte
<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import CharacterCard from '$lib/CharacterCard.svelte';
	import { loadCollapsed, saveCollapsed } from '$lib/collapse';
	import {
		ELEMENTS, SECTIONS, WEAPON_TYPES, deriveStatus, emptyFilters, groupCharacters, type Filters
	} from '$lib/status';
	import { sync } from '$lib/sync.svelte';
	import type { Character, Goal, Status } from '$lib/types';

	let chars = $state<Character[]>([]);
	let loading = $state(true);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let filters = $state<Filters>(emptyFilters());
	let collapsed = $state<Record<Status, boolean>>(loadCollapsed());
	const groups = $derived(groupCharacters(chars, filters));

	$effect(() => {
		void sync.version;
		load();
	});

	async function load() {
		try {
			chars = await api.characters();
			error = null;
		} catch (e) {
			error = errorMessage(e);
		} finally {
			loading = false;
		}
	}

	async function setGoal(c: Character, goal: Goal) {
		const before = chars;
		chars = chars.map((x) => (x.id === c.id ? { ...x, goal, ...deriveStatus(x.owned, goal) } : x));
		try {
			const updated = await api.setGoal(c.id, { goal });
			chars = chars.map((x) => (x.id === updated.id ? updated : x));
		} catch (e) {
			chars = before;
			toast = `Could not save the goal for ${c.name}: ${errorMessage(e)}`;
		}
	}

	function toggle<T>(list: T[], value: T): T[] {
		return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
	}

	function toggleSection(status: Status) {
		collapsed = { ...collapsed, [status]: !collapsed[status] };
		saveCollapsed(collapsed);
	}
</script>

<h1>Characters</h1>

<div class="filters">
	<input placeholder="Search name" bind:value={filters.search} aria-label="Search characters" />
	{#each ELEMENTS as el (el)}
		<button type="button" class="chip" class:on={filters.elements.includes(el)}
			onclick={() => (filters.elements = toggle(filters.elements, el))}>{el}</button>
	{/each}
	{#each WEAPON_TYPES as w (w)}
		<button type="button" class="chip" class:on={filters.weapons.includes(w)}
			onclick={() => (filters.weapons = toggle(filters.weapons, w))}>{w}</button>
	{/each}
	{#each [5, 4] as r (r)}
		<button type="button" class="chip" class:on={filters.rarities.includes(r)}
			onclick={() => (filters.rarities = toggle(filters.rarities, r))}>{r}★</button>
	{/each}
</div>

{#if toast}
	<div class="toast error">{toast} <button type="button" onclick={() => (toast = null)}>Dismiss</button></div>
{/if}

{#if loading}
	<p class="muted">Loading…</p>
{:else if error}
	<p class="error">{error}</p>
{:else}
	{#each SECTIONS as section (section.status)}
		<section data-testid="section-{section.status}">
			<button type="button" class="section-head" onclick={() => toggleSection(section.status)}
				aria-expanded={!collapsed[section.status]}>
				<span class="dot" style="background: var(--{section.status})"></span>
				{section.label} · {groups[section.status].length}
				<span class="muted">{collapsed[section.status] ? '▸' : '▾'}</span>
			</button>
			{#if !collapsed[section.status]}
				<div class="grid">
					{#each groups[section.status] as c (c.id)}
						<CharacterCard character={c} onGoal={(g) => setGoal(c, g)} />
					{:else}
						<p class="muted">None.</p>
					{/each}
				</div>
			{/if}
		</section>
	{/each}
{/if}

<style>
	.filters { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; align-items: center; }
	.filters input { width: 180px; }
	section { margin-bottom: 18px; }
	.section-head {
		background: none; border: none; padding: 4px 0; display: flex; gap: 8px; align-items: center;
		text-transform: uppercase; letter-spacing: 0.06em; font-size: 13px; color: var(--muted);
	}
	.dot { width: 10px; height: 10px; border-radius: 50%; display: inline-block; }
	.grid { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 8px; }
	.toast { margin-bottom: 10px; }
</style>
```

- [ ] **Step 4: Run tests and checks**

Run: `npm test` → Expected: all pass (including `collapse.test.ts`).
Run: `npm run check` → Expected: 0 errors.
Run: `npm run build` → Expected: success.

Manual check with the seeded server (same commands as Task 14 Step 3): `/characters` shows four sections with counts 2/2/2/2, Unobtained collapsed; hovering a card shows None/Want/Build; choosing Build on Xiangling moves it into Actively building with a bar; reloading the page keeps it there.

- [ ] **Step 5: Commit**

```bash
git add frontend
git commit -m "feat: characters page with grouped sections, filters, and goal switch"
```

---

### Task 16: Character detail page

**Files:**
- Create: `frontend/src/lib/TargetsEditor.svelte`, `frontend/src/routes/characters/[slug]/+page.svelte`

**Interfaces:**
- Consumes: `api.character`, `api.settings`, `api.setGoal`, `GoalSwitch`, `imgSrc`, `sync.version`.
- Produces: `TargetsEditor` props `{ targets: Targets; levelCaps: number[]; onchange: (t: Targets) => void }` with selects labelled (aria-label) `Target level`, `Target normal attack`, `Target elemental skill`, `Target elemental burst`, `Target weapon level`. Reused by Settings (Task 17).

- [ ] **Step 1: Write the targets editor**

`frontend/src/lib/TargetsEditor.svelte`:

```svelte
<script lang="ts">
	import type { Targets } from './types';

	let { targets, levelCaps, onchange }: { targets: Targets; levelCaps: number[]; onchange: (t: Targets) => void } =
		$props();

	const TALENTS = [
		{ key: 'normal', label: 'Normal attack' },
		{ key: 'skill', label: 'Elemental skill' },
		{ key: 'burst', label: 'Elemental burst' }
	] as const;
	const TALENT_LEVELS = Array.from({ length: 10 }, (_, i) => i + 1);
	const WEAPON_LEVELS = [20, 40, 50, 60, 70, 80, 90];

	const levelOptions = $derived([...new Set([...levelCaps, targets.level])].sort((a, b) => a - b));
	const weaponOptions = $derived([...new Set([...WEAPON_LEVELS, targets.weapon_level])].sort((a, b) => a - b));

	function set(key: keyof Targets, value: number) {
		onchange({ ...targets, [key]: value });
	}
</script>

<div class="targets">
	<label>
		<span>Level</span>
		<select aria-label="Target level" value={targets.level}
			onchange={(e) => set('level', Number(e.currentTarget.value))}>
			{#each levelOptions as l (l)}<option value={l}>{l}</option>{/each}
		</select>
	</label>
	{#each TALENTS as t (t.key)}
		<label>
			<span>{t.label}</span>
			<select aria-label="Target {t.label.toLowerCase()}" value={targets[t.key]}
				onchange={(e) => set(t.key, Number(e.currentTarget.value))}>
				{#each TALENT_LEVELS as l (l)}<option value={l}>{l}</option>{/each}
			</select>
		</label>
	{/each}
	<label>
		<span>Weapon level</span>
		<select aria-label="Target weapon level" value={targets.weapon_level}
			onchange={(e) => set('weapon_level', Number(e.currentTarget.value))}>
			{#each weaponOptions as l (l)}<option value={l}>{l}</option>{/each}
		</select>
	</label>
</div>

<style>
	.targets { display: flex; flex-wrap: wrap; gap: 12px; }
	label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
</style>
```

- [ ] **Step 2: Write the detail page**

`frontend/src/routes/characters/[slug]/+page.svelte`:

```svelte
<script lang="ts">
	import { page } from '$app/state';
	import { api, errorMessage } from '$lib/api';
	import GoalSwitch from '$lib/GoalSwitch.svelte';
	import { imgSrc } from '$lib/img';
	import { sync } from '$lib/sync.svelte';
	import TargetsEditor from '$lib/TargetsEditor.svelte';
	import type { CharacterDetail, Goal, Targets } from '$lib/types';

	let c = $state<CharacterDetail | null>(null);
	let caps = $state<number[]>([20, 40, 50, 60, 70, 80, 90]);
	let error = $state<string | null>(null);
	let saveError = $state<string | null>(null);

	const SLOTS: Record<number, string> = { 1: 'Flower', 2: 'Plume', 3: 'Sands', 4: 'Goblet', 5: 'Circlet' };

	$effect(() => {
		const slug = page.params.slug ?? '';
		void sync.version;
		load(slug);
	});

	async function load(slug: string) {
		try {
			const [detail, settings] = await Promise.all([api.character(slug), api.settings()]);
			c = detail;
			caps = settings.level_caps;
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	async function update(body: { goal?: Goal; targets?: Targets }) {
		if (!c) return;
		try {
			const updated = await api.setGoal(c.id, body);
			c = { ...c, ...updated };
			saveError = null;
		} catch (e) {
			saveError = errorMessage(e);
		}
	}
</script>

<a href="/characters">← Characters</a>

{#if error}
	<p class="error">{error}</p>
{:else if !c}
	<p class="muted">Loading…</p>
{:else}
	<header class="hero r{c.rarity}">
		{#if imgSrc(c.splash)}<img src={imgSrc(c.splash)} alt="" />{/if}
		<div class="info">
			<h1>{c.name}</h1>
			<div class="muted">
				{'★'.repeat(c.rarity || 0)} · {c.element ?? '—'} · {c.weapon_type ?? '—'}
			</div>
			<div class="goal">
				<GoalSwitch goal={c.goal} onchange={(g) => update({ goal: g })} />
				{#if c.prefarming}<span class="muted">Pre-farming</span>{/if}
			</div>
			{#if saveError}<p class="error">{saveError}</p>{/if}
		</div>
	</header>

	{#if c.goal === 'build' && c.targets}
		<section class="panel">
			<h2>Build targets</h2>
			<TargetsEditor targets={c.targets} levelCaps={caps} onchange={(t) => update({ targets: t })} />
		</section>
	{/if}

	{#if c.owned}
		<section class="panel">
			<h2>Current</h2>
			<p>Lv {c.level} · C{c.constellation} · Friendship {c.friendship}</p>
			{#if c.talents}
				<p>
					Talents {c.talents.normal}/{c.talents.skill}/{c.talents.burst}
					{#if c.targets && c.goal === 'build'}
						→ {c.targets.normal}/{c.targets.skill}/{c.targets.burst}{/if}
				</p>
			{/if}
			{#if c.weapon}
				<div class="weapon">
					{#if imgSrc(c.weapon.icon)}<img src={imgSrc(c.weapon.icon)} alt="" />{/if}
					<div>
						<b>{c.weapon.name}</b>
						<div class="muted">{'★'.repeat(c.weapon.rarity)} · Lv {c.weapon.level} · R{c.weapon.refinement}</div>
					</div>
				</div>
			{/if}
		</section>

		<section class="panel">
			<h2>Artifacts</h2>
			<div class="artifacts">
				{#each c.artifacts as a (a.slot)}
					<div class="artifact">
						<div class="muted">{SLOTS[a.slot] ?? `Slot ${a.slot}`} · +{a.level}</div>
						<b>{a.set_name}</b>
						<div>{a.main_stat}</div>
						<ul>{#each a.substats as s (s)}<li>{s}</li>{/each}</ul>
					</div>
				{:else}
					<p class="muted">No artifact data yet.</p>
				{/each}
			</div>
		</section>

		<section class="panel">
			<h2>Stats</h2>
			<table>
				<tbody>
					{#each c.stats as s (s.name)}<tr><td>{s.name}</td><td>{s.value}</td></tr>{/each}
				</tbody>
			</table>
		</section>
	{/if}

	<section class="panel muted">Material shortfall — arrives in phase 2.</section>
{/if}

<style>
	.hero { display: flex; gap: 20px; align-items: center; margin: 12px 0 16px; }
	.hero img { width: 420px; max-width: 50vw; height: 210px; object-fit: cover; border-radius: 10px; background: var(--r0); }
	.r5 img { background: var(--r5); }
	.r4 img { background: var(--r4); }
	.goal { margin-top: 10px; display: flex; gap: 10px; align-items: center; }
	section { margin-bottom: 12px; }
	.weapon { display: flex; gap: 10px; align-items: center; }
	.weapon img { width: 56px; height: 56px; }
	.artifacts { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 10px; }
	.artifact { background: var(--panel-2); border-radius: 8px; padding: 8px; }
	.artifact ul { margin: 4px 0 0; padding-left: 16px; color: var(--muted); }
	table td { padding: 2px 16px 2px 0; }
</style>
```

- [ ] **Step 3: Check and build**

Run: `npm run check` → Expected: 0 errors.
Run: `npm run build` → Expected: success.

Manual check with the seeded server: `/characters/bennett` shows header, goal switch on Build, five target selects, current talents 6/8/8 → 8/8/8, one artifact, stats. Changing "Target level" to 80 and reloading keeps 80. `/characters/kazuha` shows only game info, goal, and the phase-2 placeholder.

- [ ] **Step 4: Commit**

```bash
git add frontend
git commit -m "feat: character detail page with goal and target editors"
```

---

### Task 17: Settings page

**Files:**
- Create: `frontend/src/routes/settings/+page.svelte`

**Interfaces:**
- Consumes: `api.settings`, `api.saveSettings`, `api.connect`, `api.refreshGamedata`, `api.syncStatus`, `TargetsEditor`, `sync` store, `timeAgo`.
- Produces: the Settings page (connect form with fields `ltuid_v2`, `ltoken_v2`, `ltmid_v2`, `account_id_v2`, `account_mid_v2`, `cookie_token_v2`; account chooser; sync interval; recent runs; default targets; game data).

- [ ] **Step 1: Write the page**

`frontend/src/routes/settings/+page.svelte`:

```svelte
<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import { sync } from '$lib/sync.svelte';
	import TargetsEditor from '$lib/TargetsEditor.svelte';
	import { timeAgo } from '$lib/time';
	import type { Account, Settings, SyncRun, Targets } from '$lib/types';

	const FIELDS = [
		{ key: 'ltuid_v2', required: true },
		{ key: 'ltoken_v2', required: true },
		{ key: 'ltmid_v2', required: false },
		{ key: 'account_id_v2', required: false },
		{ key: 'account_mid_v2', required: false },
		{ key: 'cookie_token_v2', required: false }
	] as const;

	let settings = $state<Settings | null>(null);
	let runs = $state<SyncRun[]>([]);
	let error = $state<string | null>(null);
	let showForm = $state(false);
	let cookie = $state<Record<string, string>>({});
	let accounts = $state<Account[] | null>(null);
	let connecting = $state(false);
	let connectError = $state<string | null>(null);
	let interval = $state(10);
	let savedNote = $state<string | null>(null);
	let refreshing = $state(false);
	const now = Date.now();

	$effect(() => {
		void sync.version;
		load();
	});

	async function load() {
		try {
			const [s, st] = await Promise.all([api.settings(), api.syncStatus()]);
			settings = s;
			runs = st.runs;
			interval = s.sync_interval_minutes;
			showForm = showForm || s.connection.status !== 'connected';
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	async function submit(uid?: number) {
		connecting = true;
		connectError = null;
		try {
			const body: Record<string, string | number> = { ...cookie };
			if (uid !== undefined) body.uid = uid;
			const r = await api.connect(body);
			if (r.status === 'choose') {
				accounts = r.accounts;
			} else {
				accounts = null;
				cookie = {};
				showForm = false;
				await sync.loadConnection();
				await sync.poll();
				await load();
			}
		} catch (e) {
			connectError = errorMessage(e);
		} finally {
			connecting = false;
		}
	}

	async function saveInterval() {
		try {
			settings = await api.saveSettings({ sync_interval_minutes: interval });
			savedNote = 'Saved.';
		} catch (e) {
			savedNote = errorMessage(e);
		}
	}

	async function saveTargets(t: Targets) {
		try {
			settings = await api.saveSettings({ default_targets: t });
		} catch (e) {
			error = errorMessage(e);
		}
	}

	async function refreshGamedata() {
		refreshing = true;
		try {
			await api.refreshGamedata();
			await load();
		} finally {
			refreshing = false;
		}
	}
</script>

<h1>Settings</h1>
{#if error}<p class="error">{error}</p>{/if}

{#if settings}
	<section class="panel">
		<h2>HoYoLAB</h2>
		{#if settings.connection.status === 'connected'}
			<p>Connected as UID {settings.connection.uid}.</p>
		{:else if settings.connection.status === 'expired'}
			<p class="error">Your HoYoLAB login expired. Paste fresh cookie values to reconnect.</p>
		{:else}
			<p>Not connected.</p>
		{/if}
		{#if !showForm}
			<button type="button" onclick={() => (showForm = true)}>Reconnect HoYoLAB</button>
		{:else}
			<ol class="steps">
				<li>Log in at <b>hoyolab.com</b> in your browser.</li>
				<li>Press <b>F12</b> → <b>Application</b> (Firefox: <b>Storage</b>) → <b>Cookies</b> → <code>https://www.hoyolab.com</code>.</li>
				<li>Copy each value below. Only the first two are required. Treat them like a password.</li>
			</ol>
			<form onsubmit={(e) => { e.preventDefault(); submit(); }}>
				{#each FIELDS as f (f.key)}
					<label>
						<span><code>{f.key}</code>{f.required ? ' *' : ''}</span>
						<input type="password" autocomplete="off" bind:value={cookie[f.key]} aria-label={f.key} />
					</label>
				{/each}
				<button class="primary" type="submit" disabled={connecting}>
					{connecting ? 'Testing…' : 'Connect'}
				</button>
			</form>
			{#if connectError}<p class="error">{connectError}</p>{/if}
			{#if accounts}
				<p>This login has several Genshin accounts. Which one?</p>
				{#each accounts as a (a.uid)}
					<button type="button" onclick={() => submit(a.uid)}>
						{a.nickname} · UID {a.uid} · {a.server} · AR {a.level}
					</button>
				{/each}
			{/if}
		{/if}
	</section>

	<section class="panel">
		<h2>Sync</h2>
		<label class="inline">
			Auto-sync when data is older than
			<input type="number" min="1" max="1440" bind:value={interval} aria-label="Sync interval minutes" />
			minutes
		</label>
		<button type="button" onclick={saveInterval}>Save</button>
		{#if savedNote}<span class="muted">{savedNote}</span>{/if}
		<table>
			<thead><tr><th>When</th><th>Trigger</th><th>Roster</th><th>Details</th><th>Notes</th></tr></thead>
			<tbody>
				{#each runs as r (r.id)}
					<tr>
						<td>{timeAgo(r.started_at, now)}</td>
						<td>{r.trigger}</td>
						{#each ['roster', 'details', 'notes'] as p (p)}
							<td title={r.parts[p]?.error ?? ''} class:error={r.parts[p] && !r.parts[p].ok}>
								{#if !r.finished_at}…{:else if !r.parts[p]}—{:else if r.parts[p].ok}ok{:else}failed{/if}
							</td>
						{/each}
					</tr>
				{:else}
					<tr><td colspan="5" class="muted">No syncs yet.</td></tr>
				{/each}
			</tbody>
		</table>
	</section>

	<section class="panel">
		<h2>Default build targets</h2>
		<p class="muted">Used when you set a character to Build for the first time.</p>
		<TargetsEditor targets={settings.default_targets} levelCaps={settings.level_caps} onchange={saveTargets} />
	</section>

	<section class="panel">
		<h2>Game data</h2>
		<p>
			{settings.gamedata.count} characters ·
			{settings.gamedata.fetched_at ? `updated ${timeAgo(settings.gamedata.fetched_at, now)}` : 'never downloaded'}
		</p>
		{#if settings.gamedata.last_error}<p class="error">Last error: {settings.gamedata.last_error}</p>{/if}
		<button type="button" onclick={refreshGamedata} disabled={refreshing}>
			{refreshing ? 'Refreshing…' : 'Refresh game data'}
		</button>
	</section>
{/if}

<style>
	section { margin-bottom: 14px; }
	form { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; align-items: end; }
	label { display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--muted); }
	label.inline { flex-direction: row; align-items: center; gap: 8px; display: inline-flex; }
	label.inline input { width: 80px; }
	.steps { color: var(--muted); }
	table { margin-top: 10px; border-collapse: collapse; }
	th, td { text-align: left; padding: 3px 14px 3px 0; font-size: 12px; }
</style>
```

- [ ] **Step 2: Check and build**

Run: `npm run check` → Expected: 0 errors.
Run: `npm run build` → Expected: success.

Manual check with the seeded server: `/settings` shows "Not connected" with the form open; submitting with empty fields shows "ltuid_v2 and ltoken_v2 are required."; changing the interval to 15 and saving persists after reload; changing a default target persists after reload; "Refresh game data" with `GT_OFFLINE=1` still calls Yatta (it is an explicit request) — with no network it shows a "Last error" line instead of crashing.

- [ ] **Step 3: Commit**

```bash
git add frontend
git commit -m "feat: settings page with HoYoLAB connect flow"
```

---

### Task 18: Dashboard page

**Files:**
- Modify: `frontend/src/routes/+page.svelte` (replace fully)

**Interfaces:**
- Consumes: `api.dashboard`, `formatDuration`, `timeAgo`, `imgSrc`, `sync.version`.
- Produces: Dashboard with `data-testid="resin"` element.

- [ ] **Step 1: Write the page**

`frontend/src/routes/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { imgSrc } from '$lib/img';
	import { sync } from '$lib/sync.svelte';
	import { formatDuration, timeAgo } from '$lib/time';
	import type { Dashboard } from '$lib/types';

	let data = $state<Dashboard | null>(null);
	let error = $state<string | null>(null);
	let now = $state(Date.now());

	$effect(() => {
		void sync.version;
		load();
	});

	onMount(() => {
		const t = setInterval(() => (now = Date.now()), 1000);
		return () => clearInterval(t);
	});

	async function load() {
		try {
			data = await api.dashboard();
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	const notes = $derived(data?.notes ?? null);
	const resinFullIn = $derived(notes ? Date.parse(notes.resin_full_at) - now : 0);
</script>

<h1>Dashboard</h1>
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.connection.status === 'missing'}
		<section class="panel">Connect HoYoLAB in <a href="/settings">Settings</a> to see your account here.</section>
	{/if}

	<div class="tiles">
		<section class="panel tile" data-testid="resin">
			<h2>Original Resin</h2>
			{#if notes}
				<div class="big">{notes.resin}<span class="muted">/{notes.resin_max}</span></div>
				<div class="muted">{resinFullIn <= 0 ? 'Full' : `Full in ${formatDuration(resinFullIn)}`}</div>
			{:else}<div class="muted">No data yet</div>{/if}
		</section>
		<section class="panel tile">
			<h2>Commissions</h2>
			{#if notes}<div class="big">{notes.commissions_done}<span class="muted">/{notes.commissions_max}</span></div>
			{:else}<div class="muted">No data yet</div>{/if}
		</section>
		<section class="panel tile">
			<h2>Realm Currency</h2>
			{#if notes}<div class="big">{notes.realm_currency}<span class="muted">/{notes.realm_currency_max}</span></div>
			{:else}<div class="muted">No data yet</div>{/if}
		</section>
		<section class="panel tile">
			<h2>Building</h2>
			<div class="big">{data.building.count}</div>
			<div class="muted">
				{data.building.average_progress === null
					? 'Nothing set to Build yet'
					: `Average ${Math.round(data.building.average_progress * 100)}% to target`}
			</div>
			<a href="/characters">Characters →</a>
		</section>
	</div>

	{#if notes}
		<section class="panel">
			<h2>Expeditions</h2>
			<div class="expeditions">
				{#each notes.expeditions as e, i (i)}
					<div class="exp">
						{#if imgSrc(e.icon)}<img src={imgSrc(e.icon)} alt="" />{/if}
						<span>
							{e.finished || Date.parse(e.return_at) <= now
								? 'Done'
								: `Back in ${formatDuration(Date.parse(e.return_at) - now)}`}
						</span>
					</div>
				{:else}
					<span class="muted">No expeditions running.</span>
				{/each}
			</div>
		</section>
		<p class="muted">As of {timeAgo(notes.fetched_at, now)}.</p>
	{/if}
{/if}

<style>
	.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 12px; }
	.big { font-size: 28px; font-weight: 700; }
	.big .muted { font-size: 16px; font-weight: 400; }
	.expeditions { display: flex; flex-wrap: wrap; gap: 12px; }
	.exp { display: flex; align-items: center; gap: 6px; }
	.exp img { width: 36px; height: 36px; border-radius: 50%; background: var(--panel-2); }
</style>
```

- [ ] **Step 2: Check and build**

Run: `npm test` → Expected: all pass (formatDuration covers the resin-full case).
Run: `npm run check` → Expected: 0 errors.
Run: `npm run build` → Expected: success.

Manual check with the seeded server: `/` shows Resin 120/200 with "Full in 10h 40m" (counting down each minute), Commissions 3/4, Realm Currency 900/2400, Building 2 with an average %, "No expeditions running.", and the "Connect HoYoLAB" panel.

- [ ] **Step 3: Commit**

```bash
git add frontend
git commit -m "feat: dashboard with live notes and building summary"
```

---

### Task 19: End-to-end test and full verification

**Files:**
- Create: `frontend/playwright.config.ts`, `frontend/e2e/characters.spec.ts`

**Interfaces:**
- Consumes: `python -m app.devseed` (Task 12), `run.py --no-build` (Task 12), test ids from Tasks 15–16.

- [ ] **Step 1: Write the end-to-end test**

`frontend/playwright.config.ts`:

```ts
import { defineConfig } from '@playwright/test';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const PORT = 8799;
const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const python = process.env.PYTHON ?? 'python';

export default defineConfig({
	testDir: 'e2e',
	use: { baseURL: `http://127.0.0.1:${PORT}` },
	webServer: {
		// Fresh fake data every run; offline so no network or HoYoLAB is touched.
		command: `${python} -m app.devseed --root "${resolve(root, '.e2e-data')}" && ${python} "${resolve(root, 'run.py')}" --no-build`,
		cwd: resolve(root, 'backend'),
		url: `http://127.0.0.1:${PORT}/api/health`,
		reuseExistingServer: false,
		timeout: 60_000,
		env: { GT_ROOT: resolve(root, '.e2e-data'), GT_OFFLINE: '1', PORT: String(PORT) }
	}
});
```

`frontend/e2e/characters.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('setting a character to Build moves it into Actively building', async ({ page }) => {
	await page.goto('/characters');

	const obtained = page.getByTestId('section-obtained');
	const card = obtained.getByTestId('card-xiangling');
	await expect(card).toBeVisible();
	await card.hover();
	await card.getByRole('button', { name: 'Build' }).click();

	const building = page.getByTestId('section-building');
	const moved = building.getByTestId('card-xiangling');
	await expect(moved).toBeVisible();
	await expect(moved.getByRole('progressbar')).toBeVisible();
	await expect(obtained.getByTestId('card-xiangling')).toHaveCount(0);

	await moved.getByRole('link', { name: 'Xiangling' }).click();
	await expect(page).toHaveURL(/\/characters\/xiangling$/);
	await expect(page.getByLabel('Target level')).toBeVisible();
	await expect(page.getByLabel('Target normal attack')).toBeVisible();
});

test('unobtained section starts collapsed and expands', async ({ page }) => {
	await page.goto('/characters');
	const section = page.getByTestId('section-unobtained');
	await expect(section.getByTestId('card-xingqiu')).toHaveCount(0);
	await section.getByRole('button', { name: /Unobtained/ }).click();
	await expect(section.getByTestId('card-xingqiu')).toBeVisible();
});
```

- [ ] **Step 2: Run the end-to-end tests**

From `frontend/`, with the repo venv activated so `python` is the venv's Python:

```powershell
npx playwright install chromium
npm run build
npm run e2e
```

Expected: 2 passed.

- [ ] **Step 3: Full verification against the spec's "done when" list**

Run each and confirm:

1. Backend: from `backend/`, `python -m pytest` → all pass.
2. Frontend: from `frontend/`, `npm run check` → 0 errors; `npm test` → all pass; `npm run e2e` → all pass.
3. Fresh-clone check: `git status --ignored` shows `.env`, `data/`, `.e2e-data/`, `node_modules/`, `frontend/build/` as ignored, and no tracked file contains a cookie value, a real UID, or a `.png` (`git ls-files | Select-String -Pattern '\.png$'` prints nothing).
4. Live run (needs the user): `python run.py` → open http://127.0.0.1:8765 → Settings → connect HoYoLAB with real cookies → Characters shows the full roster grouped by status with no manual entry; Dashboard shows resin, commissions, expeditions, realm currency.
5. Goals persist: set a character to Build, restart `python run.py`, press Sync → the character is still in Actively building with its targets.
6. Live API shape check: from `backend/`, `python -m app.smoke` prints roster count, talents for 3 characters, and notes.

Items 4–6 need the user's HoYoLAB login; report their results (or that they are pending the user) rather than assuming them.

- [ ] **Step 4: Commit**

```bash
git add frontend
git commit -m "test: end-to-end characters flow on seeded data"
```
