# Phase 3 — Wishes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Import the user's whole wish history (one button from the game cache, plus paimon.moe .xlsx and UIGF JSON files) and show pity, 50/50 / guarantee state, fate points, history, stats, and charts on a new Wishes page, without ever losing or duplicating a pull.

**Architecture:** A new `backend/app/wishes/` package: `authkey.py` reads the wish link from the game's web cache, `fetch.py` pages the gacha log API, `uigf.py` / `paimon_xlsx.py` parse files, `merge.py` is the single de-duplicating write path, `importer.py` runs one import at a time (backup → read → merge in one transaction → UIGF snapshot). `banners.py` turns paimon.moe's `banners.js` into a `game_banner` table during the normal game-data refresh; `pity.py` and `stats.py` are pure functions over `wish` + `game_banner`. The API (`api/wishes.py`) and SvelteKit pages only read those.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, SQLite, httpx, genshin.py 1.7.32, openpyxl, python-multipart, pytest; SvelteKit (Svelte 5 runes, TypeScript), Vitest, Playwright.

**Spec:** [docs/superpowers/specs/2026-11-20-phase3-wishes-design.md](../specs/2026-11-20-phase3-wishes-design.md)

**Where to work:** a git worktree on branch `phase3-wishes` (user preference for multi-commit work). Copy `.env` and `data/` into the worktree only for Task 5's live checks and delete the copies afterwards; never commit them.

## Global Constraints

- Unofficial-API code lives only in `backend/app/sync/` and `backend/app/wishes/`; within `wishes/`, only `fetch.py` makes network calls and only `authkey.py` reads game files.
- The authkey and the wish-history URL are never logged, stored (database, files, backups), returned by the API, or exported. Error messages are fixed strings or exception **class names** — never `str(e)` of a network/genshin exception (their text can contain the URL).
- Cookie values, UID, nickname, and region are never logged or returned (phase 1 rule). Test fixtures use made-up UIDs (`800000001`) and synthetic pulls only.
- Every new table goes through Alembic migration `0003`; `test_models_match_migrations` must stay green.
- Pools: `100→beginner`, `200→standard`, `301→character`, `400→character`, `302→weapon`, `500→chronicled`.
- Pity table: character 90/74/10, weapon 80/63/10, standard 90/74/10, chronicled 90/74/10, beginner 50/none/10 (hard / soft-from / 4★).
- Server offsets: `os_usa` UTC−5, `os_euro` UTC+1, `os_asia` and `os_cht` UTC+8 (`app.servertime.offset_hours`).
- Wish backups: `data/backups/wishes/tracker-<ts>.db` keep **10**; `data/backups/wishes/uigf-<ts>.json` keep **10**. Separate from sync backups (`data/backups/tracker-*.db`, keep 5).
- Upload limit **20 MB**. History page size **50**. Import status polling **2 s**.
- Capturing Radiance counts only 5★s at or after server-local `2024-08-28`.
- Banner times (as paimon.moe's own `src/functions/wish.js` reads them): a `timezoneDependent` start / `timezoneDependentEnd` end is a UTC+8 instant → server-local = `shift_time(t, 8, offset)`; unmarked times are already server-local.
- Generated UIGF ids: `<UTC unix seconds, 10 digits>` + `9` + `<seq, 8 digits>`.
- `localStorage` access always wrapped in try/catch.
- Error message texts (copy exactly):
  - `Couldn't find the game's web cache. Set the game install path in Settings.`
  - `Close Genshin Impact and try again.`
  - `Open Wish History in-game once, then press Import again.`
  - `Your wish link has expired. Open Wish History in-game once, then press Import again.`
  - `This wish history belongs to a different account.`
  - `Connect HoYoLAB in Settings first, so imports can be checked against your UID.`
- **Refinements found while planning (already written into the spec's §16):**
  1. The wish URL carries no UID, so the game-import UID check uses the `uid` field of the fetched records (still before anything is written).
  2. Merge §5 rule 1: when an incoming **file** row has an unknown real id but its key matches an unclaimed row that already holds a **game** id, it is skipped (same pull, game id authoritative) instead of inserted — this prevents duplicates from trackers that invent ids.
  3. All imports require `GENSHIN_UID` (connected HoYoLAB); without it they fail with the "Connect HoYoLAB…" message.
- Commands (PowerShell, from the repo root unless stated): backend tests `cd backend; ..\.venv\Scripts\python -m pytest -q`; frontend `cd frontend; npm run check; npm test; npm run e2e`.

## Review Focus

1. **Game still running while importing** → `data_2` is locked; the user must see "Close Genshin Impact and try again." and nothing changes (test in Task 3 and Task 10).
2. **Importing the same paimon.moe file twice, or a paimon file overlapping game pulls** → 0 added the second time; overlapping pulls are not duplicated (tests in Task 9).
3. **A network error mid-fetch whose message contains the full wish URL** → the stored/returned error contains only the class name, never the authkey (tests in Task 10 and the leak test in Task 13).
4. **Webcache version folders like `2.9.0.0` and `2.40.0.0` side by side** → the newest by version number is used, not by string order (test in Task 3).
5. **Pulls before banner data exists (fresh install, offline)** → pity is still exact; outcomes show Unknown, never a wrong Won/Lost (tests in Task 11).

---

## File Structure

**Backend — new**

| File | Responsibility |
|---|---|
| `backend/migrations/versions/0003_wishes.py` | `wish`, `wish_import`, `wish_chart`, `game_banner` |
| `backend/app/wishes/__init__.py` | Package marker |
| `backend/app/wishes/types.py` | `IncomingWish`, pool mapping, pity table, time helpers, name→id resolver |
| `backend/app/wishes/authkey.py` | Find `data_2`, extract the last wish link (`WishLink`), cache status |
| `backend/app/wishes/fetch.py` | Incremental gacha-log paging; genshin.py page function; error mapping |
| `backend/app/wishes/uigf.py` | UIGF v3/v4 parse, v4 build, generated ids |
| `backend/app/wishes/paimon_xlsx.py` | paimon.moe workbook parse |
| `backend/app/wishes/merge.py` | De-duplicating merge into `wish` |
| `backend/app/wishes/banners.py` | `banners.js` → JSON, slug mapping, attribution |
| `backend/app/wishes/pity.py` | Pity, outcomes, next state, fate points, Radiance estimate |
| `backend/app/wishes/stats.py` | Headline stats and chart series |
| `backend/app/wishes/importer.py` | `WishImporter` (single flight, backups, snapshot, `wish_import` rows) |
| `backend/app/api/wishes.py` | `/wishes/*` endpoints |
| `backend/tests/fixtures/paimon_banners.js` | Trimmed `banners.js` (public data) |
| `backend/tests/wishdata.py` | Synthetic wish builders, fake `data_2`, fake page function, xlsx builder |
| `backend/tests/test_wish_*.py` | Tests per module (named in each task) |

**Backend — modified:** `pyproject.toml`, `app/config.py`, `app/db/models.py`, `app/settings/store.py`, `app/gamedata/service.py`, `app/context.py`, `app/main.py`, `app/api/__init__.py`, `app/api/dashboard.py`, `app/api/settings.py`, `app/smoke.py`, `app/devseed.py`, `tests/helpers.py`, `tests/test_db.py`, `tests/test_api_settings.py`.

**Frontend — new:** `src/lib/wishes.ts` (+ `wishes.test.ts`), `src/lib/PityPanel.svelte`, `src/lib/BarChart.svelte`, `src/lib/WishHistory.svelte`, `src/routes/wishes/+page.svelte`, `e2e/wishes.spec.ts`.

**Frontend — modified:** `src/lib/types.ts`, `src/lib/api.ts`, `src/routes/+layout.svelte`, `src/routes/+page.svelte`, `src/routes/settings/+page.svelte`.

**Docs:** `README.md`, `docs/superpowers/notes/2026-11-20-phase3-wish-findings.md` (anonymized live findings).

---

### Task 1: Schema, config, dependencies

**Files:**
- Create: `backend/migrations/versions/0003_wishes.py`
- Modify: `backend/app/db/models.py`, `backend/app/config.py`, `backend/app/settings/store.py`, `backend/pyproject.toml`
- Test: `backend/tests/test_db.py`, `backend/tests/test_settings_store.py`

**Interfaces:**
- Produces: models `Wish`, `WishImport`, `WishChart`, `GameBanner` (columns below); `Paths.wish_backups` (`data/backups/wishes`, created by `Paths.ensure()`); config constants `WISH_BACKUPS_KEPT = 10`, `WISH_UPLOAD_MAX_BYTES = 20 * 1024 * 1024`, `WISH_PAGE_DELAY = 0.3`, `WISH_HISTORY_PAGE_SIZE = 50`, `BANNERS_URL`; setting key `game_install_path` (default `""`).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_db.py`:

```python
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
```

Append to `backend/tests/test_settings_store.py`:

```python
def test_game_install_path_defaults_empty(session_factory):
    from app.settings.store import get_setting, set_setting
    with session_factory.begin() as s:
        assert get_setting(s, "game_install_path") == ""
        set_setting(s, "game_install_path", "D:/Games/Genshin Impact")
    with session_factory() as s:
        assert get_setting(s, "game_install_path") == "D:/Games/Genshin Impact"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_db.py tests/test_settings_store.py -q`
Expected: FAIL (`wish` table missing, `Paths` has no `wish_backups`, `KeyError: 'game_install_path'`).

- [ ] **Step 3: Add dependencies**

In `backend/pyproject.toml` `dependencies`, add after `"genshin==1.7.32",`:

```toml
  "openpyxl>=3.1,<4",
  "python-multipart>=0.0.18",
```

Run: `.\.venv\Scripts\python -m pip install -e "backend[dev]"`
Expected: installs openpyxl and python-multipart.

- [ ] **Step 4: Config**

In `backend/app/config.py` add after `LACK_INCLUDES_CRAFTING = False`:

```python
WISH_BACKUPS_KEPT = 10
WISH_UPLOAD_MAX_BYTES = 20 * 1024 * 1024
WISH_PAGE_DELAY = 0.3          # seconds between gacha-log pages (be gentle with the API)
WISH_HISTORY_PAGE_SIZE = 50
BANNERS_URL = "https://raw.githubusercontent.com/MadeBaruna/paimon-moe/main/src/data/banners.js"
```

In `Paths`, add after the `backups` property:

```python
    @property
    def wish_backups(self) -> Path:
        return self.backups / "wishes"
```

and change `ensure()` to:

```python
    def ensure(self) -> None:
        for d in (self.data, self.backups, self.wish_backups, self.img_cache):
            d.mkdir(parents=True, exist_ok=True)
```

In `backend/app/settings/store.py` add to `DEFAULTS`:

```python
    "game_install_path": "",   # blank = auto-detect from the game's log file
```

- [ ] **Step 5: Models**

In `backend/app/db/models.py`, change the sqlalchemy import to:

```python
from sqlalchemy import JSON, Boolean, DateTime, Index, Integer, String, UniqueConstraint
```

Add under `# --- game data` (after `GameWeapon`):

```python
class GameBanner(Base):
    __tablename__ = "game_banner"
    key: Mapped[str] = mapped_column(String, primary_key=True)        # f"{pool}|{start}|{order}"
    pool: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    short_name: Mapped[str] = mapped_column(String)
    start: Mapped[str] = mapped_column(String)                       # as given by paimon.moe
    end: Mapped[str] = mapped_column(String)
    timezone_dependent: Mapped[bool] = mapped_column(Boolean)       # start is a UTC+8 instant
    timezone_dependent_end: Mapped[bool] = mapped_column(Boolean)   # end is a UTC+8 instant
    order: Mapped[int] = mapped_column(Integer)
    featured_5: Mapped[list] = mapped_column(JSON)                   # item ids
    featured_4: Mapped[list] = mapped_column(JSON)
    version: Mapped[str | None] = mapped_column(String, nullable=True)
```

Add under `# --- user data` (after `WeeklyBossDone`):

```python
class Wish(Base):
    __tablename__ = "wish"
    __table_args__ = (
        UniqueConstraint("id", name="uq_wish_id"),
        Index("ix_wish_pool_time_seq", "pool", "time", "seq"),
    )
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str | None] = mapped_column(String, nullable=True)     # real pull id; None for paimon rows
    pool: Mapped[str] = mapped_column(String)
    gacha_type: Mapped[str | None] = mapped_column(String, nullable=True)
    time: Mapped[str] = mapped_column(String)                        # server-local "YYYY-MM-DD HH:MM:SS"
    seq: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_type: Mapped[str] = mapped_column(String)                   # character | weapon
    rarity: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String)                      # game | uigf | paimon
    imported_at: Mapped[datetime] = mapped_column(DateTime)


class WishImport(Base):
    __tablename__ = "wish_import"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String)
    ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)   # None while running
    added: Mapped[int] = mapped_column(Integer)
    upgraded: Mapped[int] = mapped_column(Integer)
    skipped: Mapped[int] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    backup_file: Mapped[str | None] = mapped_column(String, nullable=True)
    snapshot_file: Mapped[str | None] = mapped_column(String, nullable=True)


class WishChart(Base):
    __tablename__ = "wish_chart"
    pool: Mapped[str] = mapped_column(String, primary_key=True)      # weapon | chronicled
    item_id: Mapped[int] = mapped_column(Integer)
    set_at: Mapped[datetime] = mapped_column(DateTime)
```

- [ ] **Step 6: Migration**

Create `backend/migrations/versions/0003_wishes.py`:

```python
"""phase 3 wishes

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-20
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_banner",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("pool", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("short_name", sa.String(), nullable=False),
        sa.Column("start", sa.String(), nullable=False),
        sa.Column("end", sa.String(), nullable=False),
        sa.Column("timezone_dependent", sa.Boolean(), nullable=False),
        sa.Column("timezone_dependent_end", sa.Boolean(), nullable=False),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.Column("featured_5", sa.JSON(), nullable=False),
        sa.Column("featured_4", sa.JSON(), nullable=False),
        sa.Column("version", sa.String(), nullable=True),
    )
    op.create_table(
        "wish",
        sa.Column("pk", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id", sa.String(), nullable=True),
        sa.Column("pool", sa.String(), nullable=False),
        sa.Column("gacha_type", sa.String(), nullable=True),
        sa.Column("time", sa.String(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("item_id", sa.Integer(), nullable=True),
        sa.Column("item_type", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("id", name="uq_wish_id"),
    )
    op.create_index("ix_wish_pool_time_seq", "wish", ["pool", "time", "seq"])
    op.create_table(
        "wish_import",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("started_at", sa.DateTime(), nullable=False),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("ok", sa.Boolean(), nullable=True),
        sa.Column("added", sa.Integer(), nullable=False),
        sa.Column("upgraded", sa.Integer(), nullable=False),
        sa.Column("skipped", sa.Integer(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("backup_file", sa.String(), nullable=True),
        sa.Column("snapshot_file", sa.String(), nullable=True),
    )
    op.create_table(
        "wish_chart",
        sa.Column("pool", sa.String(), primary_key=True),
        sa.Column("item_id", sa.Integer(), nullable=False),
        sa.Column("set_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("wish_chart")
    op.drop_table("wish_import")
    op.drop_index("ix_wish_pool_time_seq", table_name="wish")
    op.drop_table("wish")
    op.drop_table("game_banner")
```

- [ ] **Step 7: Run the tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: all pass, including `test_models_match_migrations` (if it reports the unique constraint or index, the model's `__table_args__` names must equal the migration's names exactly).

- [ ] **Step 8: Commit**

```powershell
git add backend/pyproject.toml backend/app/config.py backend/app/db/models.py backend/app/settings/store.py backend/migrations/versions/0003_wishes.py backend/tests/test_db.py backend/tests/test_settings_store.py
git commit -m "feat(wishes): schema, config and dependencies for phase 3"
```

---

### Task 2: Wish types, pools, time helpers, name resolver

**Files:**
- Create: `backend/app/wishes/__init__.py` (empty), `backend/app/wishes/types.py`
- Test: `backend/tests/test_wish_types.py`

**Interfaces:**
- Produces:
  - `POOL_BY_GACHA_TYPE: dict[str, str]`, `POOLS: tuple[str, ...] = ("character", "weapon", "chronicled", "standard", "beginner")`, `SINGLE_TYPE: dict[str, str]` (pool → its only gacha type; no `character`)
  - `UID_MISMATCH`, `NEEDS_UID` (exact message texts), `bad_rows_message(errors: list[str]) -> str` (first 50 shown)
  - `PityRule(hard: int, soft: int | None, four: int)`, `PITY: dict[str, PityRule]`
  - `@dataclass(frozen=True) IncomingWish(id: str | None, pool: str, gacha_type: str | None, time: str, name: str, item_type: str, rarity: int)`
  - `ImportFailed(Exception)` with `.message: str` (user-facing)
  - `normalize_time(value: str | datetime) -> str` → `"YYYY-MM-DD HH:MM:SS"` (raises `ValueError`)
  - `shift_time(time: str, from_offset: int, to_offset: int) -> str`
  - `to_utc_seconds(time: str, offset: int) -> int`
  - `server_local_now(now_utc: datetime, offset: int) -> str`
  - `item_type_of(value: str) -> str` → `"character" | "weapon"` (raises `ValueError`)
  - `ItemResolver.from_session(session) -> ItemResolver`; `.resolve(name: str) -> int | None`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_wish_types.py
from datetime import datetime

import pytest

from app.db.models import GameWeapon
from app.wishes.types import (PITY, POOL_BY_GACHA_TYPE, ItemResolver, item_type_of, normalize_time,
                              server_local_now, shift_time, to_utc_seconds)
from helpers import seed_game


def test_pools_and_pity_table():
    assert POOL_BY_GACHA_TYPE == {"100": "beginner", "200": "standard", "301": "character",
                                  "400": "character", "302": "weapon", "500": "chronicled"}
    assert (PITY["character"].hard, PITY["character"].soft, PITY["character"].four) == (90, 74, 10)
    assert (PITY["weapon"].hard, PITY["weapon"].soft) == (80, 63)
    assert PITY["beginner"].hard == 50 and PITY["beginner"].soft is None


def test_normalize_time_accepts_strings_and_datetimes():
    assert normalize_time("2024-03-01 18:02:11") == "2024-03-01 18:02:11"
    assert normalize_time("2024-03-01T18:02:11") == "2024-03-01 18:02:11"
    assert normalize_time(datetime(2024, 3, 1, 18, 2, 11)) == "2024-03-01 18:02:11"
    with pytest.raises(ValueError):
        normalize_time("yesterday")


def test_shift_and_utc_seconds():
    assert shift_time("2024-03-01 02:00:00", 8, -5) == "2024-02-29 13:00:00"
    assert to_utc_seconds("2024-01-01 08:00:00", 8) == 1704067200
    assert server_local_now(datetime(2024, 1, 1, 0, 0, 0), 1) == "2024-01-01 01:00:00"


def test_bad_rows_message_caps_at_50():
    from app.wishes.types import bad_rows_message
    msg = bad_rows_message([f"row {i}: bad time" for i in range(60)])
    assert msg.startswith("Nothing was imported: 60 row(s)")
    assert "row 49: bad time" in msg and "row 50: bad time" not in msg and "(and 10 more)" in msg


def test_item_type_of():
    assert item_type_of("Character") == "character"
    assert item_type_of("weapon") == "weapon"
    with pytest.raises(ValueError):
        item_type_of("角色")


def test_resolver_maps_character_and_weapon_names(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        s.add(GameWeapon(id=11401, name="Favonius Sword", icon="x", rarity=4, weapon_type="Sword"))
    with session_factory() as s:
        r = ItemResolver.from_session(s)
    assert r.resolve("Furina") == 10000089
    assert r.resolve("Favonius Sword") == 11401
    assert r.resolve("Nobody") is None
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_types.py -q`
Expected: FAIL (`ModuleNotFoundError: app.wishes`).

- [ ] **Step 3: Implement**

```python
# backend/app/wishes/types.py
"""Shared wish vocabulary: pools, pity rules, the normalized incoming row, time helpers."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, GameWeapon

POOL_BY_GACHA_TYPE = {"100": "beginner", "200": "standard", "301": "character",
                      "400": "character", "302": "weapon", "500": "chronicled"}
POOLS = ("character", "weapon", "chronicled", "standard", "beginner")
SINGLE_TYPE = {"beginner": "100", "standard": "200", "weapon": "302", "chronicled": "500"}
TIME_FMT = "%Y-%m-%d %H:%M:%S"
UID_MISMATCH = "This wish history belongs to a different account."
NEEDS_UID = "Connect HoYoLAB in Settings first, so imports can be checked against your UID."
BAD_ROWS_SHOWN = 50


def bad_rows_message(errors: list[str]) -> str:
    shown = "; ".join(errors[:BAD_ROWS_SHOWN])
    more = f" (and {len(errors) - BAD_ROWS_SHOWN} more)" if len(errors) > BAD_ROWS_SHOWN else ""
    return f"Nothing was imported: {len(errors)} row(s) could not be read: {shown}{more}"


@dataclass(frozen=True)
class PityRule:
    hard: int
    soft: int | None
    four: int


PITY = {
    "character": PityRule(90, 74, 10),
    "weapon": PityRule(80, 63, 10),
    "standard": PityRule(90, 74, 10),
    "chronicled": PityRule(90, 74, 10),
    "beginner": PityRule(50, None, 10),
}


@dataclass(frozen=True)
class IncomingWish:
    id: str | None
    pool: str
    gacha_type: str | None
    time: str
    name: str
    item_type: str
    rarity: int


class ImportFailed(Exception):
    """An import that must not change anything. `message` is shown to the user verbatim."""

    def __init__(self, message: str):
        super().__init__(message)
        self.message = message


def normalize_time(value: str | datetime) -> str:
    if isinstance(value, datetime):
        return value.strftime(TIME_FMT)
    text = str(value).strip().replace("T", " ")
    return datetime.strptime(text[:19], TIME_FMT).strftime(TIME_FMT)


def shift_time(time: str, from_offset: int, to_offset: int) -> str:
    return (datetime.strptime(time, TIME_FMT) + timedelta(hours=to_offset - from_offset)).strftime(TIME_FMT)


def to_utc_seconds(time: str, offset: int) -> int:
    local = datetime.strptime(time, TIME_FMT).replace(tzinfo=timezone(timedelta(hours=offset)))
    return int(local.timestamp())


def server_local_now(now_utc: datetime, offset: int) -> str:
    return (now_utc + timedelta(hours=offset)).strftime(TIME_FMT)


def item_type_of(value: str) -> str:
    v = str(value).strip().lower()
    if v in ("character", "weapon"):
        return v
    raise ValueError(f"unknown item type {value!r} (export in English)")


class ItemResolver:
    def __init__(self, by_name: dict[str, int]):
        self._by_name = by_name

    @classmethod
    def from_session(cls, session: Session) -> "ItemResolver":
        by_name = {name.casefold(): wid for wid, name in session.execute(select(GameWeapon.id, GameWeapon.name))}
        by_name.update({name.casefold(): cid for cid, name in
                        session.execute(select(GameCharacter.id, GameCharacter.name))})
        return cls(by_name)

    def resolve(self, name: str) -> int | None:
        return self._by_name.get(name.casefold())
```

- [ ] **Step 4: Run the tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_types.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/wishes backend/tests/test_wish_types.py
git commit -m "feat(wishes): pools, pity rules, incoming row and time helpers"
```

---

### Task 3: Wish link from the game cache (`authkey.py`)

**Files:**
- Create: `backend/app/wishes/authkey.py`, `backend/tests/wishdata.py`
- Test: `backend/tests/test_wish_authkey.py`

**Interfaces:**
- Consumes: `ImportFailed` (Task 2).
- Produces:
  - `CACHE_NOT_FOUND`, `CACHE_LOCKED`, `NO_WISH_LINK` (message strings, exact texts from Global Constraints)
  - `@dataclass(frozen=True, repr=False) WishLink(authkey: str, region: str | None, cached_at: datetime)` — `repr()` never shows the authkey
  - `find_data_2(game_path: str, locallow: Path) -> Path` — raises `ImportFailed(CACHE_NOT_FOUND)`
  - `read_wish_link(data_2: Path) -> WishLink` — raises `ImportFailed(CACHE_LOCKED | NO_WISH_LINK)`
  - `load_wish_link(game_path: str, locallow: Path) -> WishLink`
  - `link_status(load: Callable[[], WishLink]) -> dict` and `cache_status(game_path: str, locallow: Path) -> dict` → `{"status": "found" | "no_link" | "not_found" | "locked", "cached_at": datetime | None}`
  - `default_locallow() -> Path` (`~/AppData/LocalLow`)
- Test helper (`tests/wishdata.py`): `make_game_install(root: Path, *, versions=("2.40.0.0",), urls=(...), log=True) -> tuple[Path, Path]` returning `(game_dir, locallow)`.

- [ ] **Step 1: Write the test helper**

```python
# backend/tests/wishdata.py
"""Synthetic wish data for tests: fake game installs, pulls, gacha pages, workbooks. No real data."""
from __future__ import annotations

from pathlib import Path

FAKE_AUTHKEY = "SECRET-AUTHKEY+abc/def=="
FAKE_UID = 800000001


def wish_url(authkey: str = FAKE_AUTHKEY, host: str = "public-operation-hk4e-sg.hoyoverse.com") -> str:
    from urllib.parse import quote
    return (f"https://{host}/gacha_info/api/getGachaLog?win_mode=fullscreen&authkey_ver=1"
            f"&authkey={quote(authkey, safe='')}&lang=en&region=os_euro&game_biz=hk4e_global")


def make_game_install(root: Path, *, versions=("2.40.0.0",), urls: tuple[str, ...] | None = None,
                      log: bool = True, newest_has_data: bool = True) -> tuple[Path, Path]:
    """A fake install under root/'Genshin Impact game' with webCaches/<v>/Cache/Cache_Data/data_2.
    The newest version (by number) gets `urls`; older ones get an outdated URL."""
    game_dir = root / "Genshin Impact game"
    data_dir = game_dir / "GenshinImpact_Data"
    urls = (wish_url(),) if urls is None else urls
    ordered = sorted(versions, key=lambda v: tuple(int(p) for p in v.split(".")))
    for v in ordered:
        cache = data_dir / "webCaches" / v / "Cache" / "Cache_Data"
        cache.mkdir(parents=True)
        newest = v == ordered[-1]
        if newest and not newest_has_data:
            continue
        body = urls if newest else (wish_url("OLD-KEY"),)
        payload = b"\x00binary\x00".join(u.encode() + b"\x00" for u in body)
        (cache / "data_2").write_bytes(b"\x00\x01junk" + payload + b"\x00tail")
    locallow = root / "LocalLow"
    if log:
        log_dir = locallow / "miHoYo" / "Genshin Impact"
        log_dir.mkdir(parents=True)
        (log_dir / "output_log.txt").write_text(
            f"[Subsystems] Discovering subsystems at path {data_dir.as_posix()}/UnitySubsystems\n",
            encoding="utf-8")
    return game_dir, locallow
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_wish_authkey.py
from pathlib import Path

import pytest

from app.wishes import authkey as ak
from app.wishes.types import ImportFailed
from wishdata import FAKE_AUTHKEY, make_game_install, wish_url


def test_reads_last_link_from_newest_version_by_number(tmp_path):
    later = wish_url("NEWER-KEY")
    game_dir, locallow = make_game_install(tmp_path, versions=("2.9.0.0", "2.40.0.0"),
                                           urls=(wish_url(), later))
    link = ak.load_wish_link("", locallow)                # auto-detect via the log
    assert link.authkey == "NEWER-KEY"
    assert link.region == "os_euro"


def test_authkey_is_url_decoded_without_plus_to_space(tmp_path):
    game_dir, locallow = make_game_install(tmp_path)
    assert ak.load_wish_link(str(game_dir), locallow).authkey == FAKE_AUTHKEY


def test_game_path_setting_wins_over_log(tmp_path):
    game_dir, _ = make_game_install(tmp_path, log=False)
    assert ak.find_data_2(str(game_dir), tmp_path / "nowhere").name == "data_2"
    assert ak.find_data_2(str(game_dir.parent), tmp_path / "nowhere").name == "data_2"  # install root works too


def test_not_found_message(tmp_path):
    with pytest.raises(ImportFailed) as e:
        ak.find_data_2("", tmp_path / "LocalLow")
    assert e.value.message == ak.CACHE_NOT_FOUND


def test_no_link_message(tmp_path):
    game_dir, locallow = make_game_install(tmp_path, urls=())
    with pytest.raises(ImportFailed) as e:
        ak.load_wish_link("", locallow)
    assert e.value.message == ak.NO_WISH_LINK


def test_locked_file_message(tmp_path, monkeypatch):
    game_dir, locallow = make_game_install(tmp_path)

    def locked(self, *a, **k):
        raise PermissionError("in use")
    monkeypatch.setattr(Path, "read_bytes", locked)
    with pytest.raises(ImportFailed) as e:
        ak.load_wish_link("", locallow)
    assert e.value.message == ak.CACHE_LOCKED


def test_repr_hides_authkey(tmp_path):
    _, locallow = make_game_install(tmp_path)
    link = ak.load_wish_link("", locallow)
    assert FAKE_AUTHKEY not in repr(link) and "SECRET" not in repr(link)


def test_cache_status(tmp_path):
    _, locallow = make_game_install(tmp_path)
    st = ak.cache_status("", locallow)
    assert st["status"] == "found" and st["cached_at"] is not None
    assert ak.cache_status("", tmp_path / "missing")["status"] == "not_found"
    _, empty_ll = make_game_install(tmp_path / "b", urls=())
    assert ak.cache_status("", empty_ll)["status"] == "no_link"
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_authkey.py -q`
Expected: FAIL (`ImportError: cannot import name 'authkey'`).

- [ ] **Step 4: Implement**

```python
# backend/app/wishes/authkey.py
"""Find the wish-history link in the game's web cache. Read-only; the authkey stays in memory.
genshin.py's get_authkey() is deliberately not used: it writes the authkey to a temp file."""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.wishes.types import ImportFailed

CACHE_NOT_FOUND = "Couldn't find the game's web cache. Set the game install path in Settings."
CACHE_LOCKED = "Close Genshin Impact and try again."
NO_WISH_LINK = "Open Wish History in-game once, then press Import again."

DATA_DIR_NAMES = ("GenshinImpact_Data", "YuanShen_Data")
LOG_DIRS = [(company, game) for company in ("miHoYo", "HoYoverse", "Cognosphere")
            for game in ("Genshin Impact", "原神")]
LOG_NAMES = ("output_log.txt", "Player.log")
LOG_DATA_RE = re.compile(r"([A-Za-z]:/[^\n\r]*?/(?:GenshinImpact|YuanShen)_Data)")
URL_RE = re.compile(rb"https://[^\x00\s\"'<>]+")
AUTHKEY_RE = re.compile(r"[?&]authkey=([^&#]+)")
REGION_RE = re.compile(r"[?&]region=([^&#]+)")


@dataclass(frozen=True, repr=False)
class WishLink:
    authkey: str = field(repr=False)
    region: str | None
    cached_at: datetime

    def __repr__(self) -> str:
        return f"WishLink(region={self.region!r}, cached_at={self.cached_at!r})"


def default_locallow() -> Path:
    return Path.home() / "AppData" / "LocalLow"


def _version_key(p: Path) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in p.name.split("."))
    except ValueError:
        return (-1,)


def _data_2_in(data_dir: Path) -> Path | None:
    caches = data_dir / "webCaches"
    if not caches.is_dir():
        return None
    versions = sorted((d for d in caches.iterdir() if d.is_dir()), key=_version_key, reverse=True)
    for v in versions:
        f = v / "Cache" / "Cache_Data" / "data_2"
        if f.is_file():
            return f
    return None


def _data_dirs_under(game_path: Path) -> list[Path]:
    if game_path.name in DATA_DIR_NAMES:
        return [game_path]
    out = []
    for base in (game_path, game_path / "Genshin Impact game"):
        out += [base / n for n in DATA_DIR_NAMES]
    return out


def _data_dirs_from_log(locallow: Path) -> list[Path]:
    for company, game in LOG_DIRS:
        for name in LOG_NAMES:
            log = locallow / company / game / name
            if log.is_file():
                try:
                    text = log.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                return [Path(m) for m in dict.fromkeys(LOG_DATA_RE.findall(text))]
    return []


def find_data_2(game_path: str, locallow: Path) -> Path:
    candidates = _data_dirs_under(Path(game_path)) if game_path.strip() else _data_dirs_from_log(locallow)
    for d in candidates:
        found = _data_2_in(d)
        if found is not None:
            return found
    raise ImportFailed(CACHE_NOT_FOUND)


def read_wish_link(data_2: Path) -> WishLink:
    try:
        raw = data_2.read_bytes()
        mtime = data_2.stat().st_mtime
    except PermissionError:
        raise ImportFailed(CACHE_LOCKED) from None
    except OSError:
        raise ImportFailed(CACHE_NOT_FOUND) from None
    last: str | None = None
    for m in URL_RE.finditer(raw):
        url = m.group(0).decode("utf-8", errors="replace")
        if "authkey=" in url and ("gacha" in url or "getGachaLog" in url):
            last = url
    if last is None:
        raise ImportFailed(NO_WISH_LINK)
    key = AUTHKEY_RE.search(last)
    if key is None:
        raise ImportFailed(NO_WISH_LINK)
    region = REGION_RE.search(last)
    return WishLink(authkey=urllib.parse.unquote(key.group(1)),
                    region=region.group(1) if region else None,
                    cached_at=datetime.fromtimestamp(mtime, timezone.utc).replace(tzinfo=None))


def load_wish_link(game_path: str, locallow: Path) -> WishLink:
    return read_wish_link(find_data_2(game_path, locallow))


STATUS_BY_MESSAGE = {CACHE_NOT_FOUND: "not_found", CACHE_LOCKED: "locked", NO_WISH_LINK: "no_link"}


def link_status(load: Callable[[], WishLink]) -> dict:
    """Status for Settings; never exposes the link itself."""
    try:
        link = load()
    except ImportFailed as e:
        return {"status": STATUS_BY_MESSAGE.get(e.message, "not_found"), "cached_at": None}
    return {"status": "found", "cached_at": link.cached_at}


def cache_status(game_path: str, locallow: Path) -> dict:
    return link_status(lambda: load_wish_link(game_path, locallow))
```

- [ ] **Step 5: Run the tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_authkey.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/wishes/authkey.py backend/tests/wishdata.py backend/tests/test_wish_authkey.py
git commit -m "feat(wishes): read the wish link from the game web cache without persisting it"
```

---

### Task 4: Incremental gacha-log fetch (`fetch.py`)

**Files:**
- Create: `backend/app/wishes/fetch.py`
- Modify: `backend/tests/wishdata.py`
- Test: `backend/tests/test_wish_fetch.py`

**Interfaces:**
- Consumes: `WishLink` (Task 3), `IncomingWish`, `POOL_BY_GACHA_TYPE`, `normalize_time`, `item_type_of`, `ImportFailed` (Task 2).
- Produces:
  - `FETCH_TYPES = ("100", "200", "301", "400", "302", "500")`
  - `LINK_EXPIRED` (message)
  - `class RateLimited(Exception)`, `class WishLinkExpired(Exception)`, `class FetchFailed(Exception)` (`.kind: str`, a class name only)
  - `PageFn = Callable[[str, str], Awaitable[list[dict]]]` — `(gacha_type, end_id) -> raw records, newest first`
  - `async fetch_new(page: PageFn, known_ids: set[str], *, sleep=asyncio.sleep, page_delay: float = WISH_PAGE_DELAY) -> list[dict]` — raw records not yet stored, each id once
  - `to_incoming(raw: dict) -> IncomingWish`
  - `record_uid(raw: list[dict]) -> int | None`
  - `genshin_page_fn(link: WishLink) -> PageFn`
- Test helper: `FakeGachaApi(records: dict[str, list[dict]])` with `.page` (a `PageFn`), `.calls`, optional `expire_after: int | None`, `rate_limit_times: int`; `raw_wish(id, gacha_type, time, name, rarity, item_type="Weapon", uid=FAKE_UID) -> dict`.

- [ ] **Step 1: Extend the test helper**

Append to `backend/tests/wishdata.py`:

```python
def raw_wish(id_: str, gacha_type: str, time: str, name: str, rarity: int,
             item_type: str = "Weapon", uid: int = FAKE_UID) -> dict:
    """One record as the gacha log API returns it."""
    return {"uid": str(uid), "gacha_type": gacha_type, "item_id": "", "count": "1", "time": time,
            "name": name, "lang": "en-us", "item_type": item_type, "rank_type": str(rarity), "id": id_}


class FakeGachaApi:
    """Pages of 20, newest first, per queried gacha type. Querying 301 or 400 returns both
    (as the real API does); other types return only their own records."""

    def __init__(self, records: list[dict], expire_after: int | None = None, rate_limit_times: int = 0):
        self.records = sorted(records, key=lambda r: int(r["id"]), reverse=True)
        self.calls: list[tuple[str, str]] = []
        self.expire_after = expire_after
        self.rate_limit_times = rate_limit_times

    async def page(self, gacha_type: str, end_id: str) -> list[dict]:
        from app.wishes.fetch import RateLimited, WishLinkExpired
        self.calls.append((gacha_type, end_id))
        if self.rate_limit_times > 0:
            self.rate_limit_times -= 1
            raise RateLimited()
        if self.expire_after is not None and len(self.calls) > self.expire_after:
            raise WishLinkExpired()
        group = {"301", "400"} if gacha_type in ("301", "400") else {gacha_type}
        rows = [r for r in self.records if r["gacha_type"] in group]
        if end_id != "0":
            rows = [r for r in rows if int(r["id"]) < int(end_id)]
        return rows[:20]
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_wish_fetch.py
import pytest

from app.wishes.fetch import FETCH_TYPES, FetchFailed, WishLinkExpired, fetch_new, record_uid, to_incoming
from wishdata import FAKE_UID, FakeGachaApi, raw_wish


def weapon_rows(n: int, start_id: int = 1_700_000_000_000_000_000) -> list[dict]:
    return [raw_wish(str(start_id + i), "302", f"2024-01-01 10:{i // 60:02d}:{i % 60:02d}", "Slingshot", 3)
            for i in range(n)]


async def no_sleep(_s):
    return None


async def test_pages_until_short_page_and_dedupes_301_400():
    char = [raw_wish("1700000000000000101", "301", "2024-01-02 10:00:00", "Furina", 5, "Character"),
            raw_wish("1700000000000000102", "400", "2024-01-02 10:00:01", "Bennett", 4, "Character")]
    api = FakeGachaApi(weapon_rows(45) + char)
    out = await fetch_new(api.page, set(), sleep=no_sleep)
    assert len(out) == 47
    assert len({r["id"] for r in out}) == 47
    assert [c[0] for c in api.calls].count("302") == 3          # 20 + 20 + 5
    assert {c[0] for c in api.calls} == set(FETCH_TYPES)


async def test_stops_at_first_known_id():
    rows = weapon_rows(45)
    known = {r["id"] for r in rows[:30]}                          # oldest 30 already stored
    api = FakeGachaApi(rows)
    out = await fetch_new(api.page, known, sleep=no_sleep)
    assert sorted(r["id"] for r in out) == sorted(r["id"] for r in rows[30:])
    assert [c for c in api.calls if c[0] == "302"] == [("302", "0")]   # first page already hit a known id


async def test_rate_limit_is_retried_then_fails():
    api = FakeGachaApi(weapon_rows(3), rate_limit_times=2)
    assert len(await fetch_new(api.page, set(), sleep=no_sleep)) == 3
    api = FakeGachaApi(weapon_rows(3), rate_limit_times=10)
    with pytest.raises(FetchFailed) as e:
        await fetch_new(api.page, set(), sleep=no_sleep)
    assert e.value.kind == "RateLimited"


async def test_expired_link_propagates():
    api = FakeGachaApi(weapon_rows(45), expire_after=1)
    with pytest.raises(WishLinkExpired):
        await fetch_new(api.page, set(), sleep=no_sleep)


def test_to_incoming_and_uid():
    raw = raw_wish("1700000000000000101", "400", "2024-01-02 10:00:00", "Furina", 5, "Character")
    w = to_incoming(raw)
    assert (w.id, w.pool, w.gacha_type, w.time, w.name, w.item_type, w.rarity) == (
        "1700000000000000101", "character", "400", "2024-01-02 10:00:00", "Furina", "character", 5)
    assert record_uid([raw]) == FAKE_UID and record_uid([]) is None
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_fetch.py -q`
Expected: FAIL (`ModuleNotFoundError: app.wishes.fetch`).

- [ ] **Step 4: Implement**

```python
# backend/app/wishes/fetch.py
"""The only network code for wishes: page the gacha log API, newest first, stopping at known ids."""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from app.config import WISH_PAGE_DELAY
from app.wishes.authkey import WishLink
from app.wishes.types import POOL_BY_GACHA_TYPE, IncomingWish, item_type_of, normalize_time

FETCH_TYPES = ("100", "200", "301", "400", "302", "500")
PAGE_SIZE = 20
RETRY_DELAYS = (2.0, 4.0, 8.0)
LINK_EXPIRED = "Your wish link has expired. Open Wish History in-game once, then press Import again."

PageFn = Callable[[str, str], Awaitable[list[dict]]]


class RateLimited(Exception):
    pass


class WishLinkExpired(Exception):
    pass


class FetchFailed(Exception):
    """Carries only an exception class name: genshin/httpx messages can contain the wish URL."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


async def _page_with_retry(page: PageFn, gacha_type: str, end_id: str, sleep) -> list[dict]:
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            return await page(gacha_type, end_id)
        except RateLimited:
            if attempt == len(RETRY_DELAYS):
                raise FetchFailed("RateLimited") from None
            await sleep(RETRY_DELAYS[attempt])
    raise AssertionError("unreachable")


async def fetch_new(page: PageFn, known_ids: set[str], *, sleep=asyncio.sleep,
                    page_delay: float = WISH_PAGE_DELAY) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for gacha_type in FETCH_TYPES:
        end_id = "0"
        while True:
            records = await _page_with_retry(page, gacha_type, end_id, sleep)
            hit_known = False
            for r in records:
                rid = str(r["id"])
                if rid in known_ids:
                    hit_known = True
                    break
                if rid not in seen:
                    seen.add(rid)
                    out.append(r)
            if hit_known or len(records) < PAGE_SIZE:
                break
            end_id = str(records[-1]["id"])
            await sleep(page_delay)
    return out


def to_incoming(raw: dict) -> IncomingWish:
    gacha_type = str(raw["gacha_type"])
    return IncomingWish(id=str(raw["id"]), pool=POOL_BY_GACHA_TYPE[gacha_type], gacha_type=gacha_type,
                        time=normalize_time(raw["time"]), name=str(raw["name"]),
                        item_type=item_type_of(raw["item_type"]), rarity=int(raw["rank_type"]))


def record_uid(raw: list[dict]) -> int | None:
    for r in raw:
        if r.get("uid"):
            return int(r["uid"])
    return None


def genshin_page_fn(link: WishLink) -> PageFn:
    import genshin
    from genshin import errors as gerrors

    client = genshin.Client(lang="en-us", game=genshin.Game.GENSHIN)

    async def page(gacha_type: str, end_id: str) -> list[dict]:
        try:
            data = await client.request_gacha_info(
                "getGachaLog", lang="en-us", authkey=link.authkey,
                params={"gacha_type": gacha_type, "size": PAGE_SIZE, "end_id": end_id})
        except gerrors.AuthkeyException:
            raise WishLinkExpired() from None
        except gerrors.VisitsTooFrequently:
            raise RateLimited() from None
        except Exception as e:  # noqa: BLE001 - message may contain the URL; keep the class name only
            raise FetchFailed(type(e).__name__) from None
        return list(data.get("list") or [])

    return page
```

- [ ] **Step 5: Run the tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_fetch.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/wishes/fetch.py backend/tests/wishdata.py backend/tests/test_wish_fetch.py
git commit -m "feat(wishes): incremental gacha-log fetch with retry and safe error mapping"
```

---

### Task 5: Live verification checkpoint (smoke `--wishes`, `--paimon`)

This task needs the user: Wish History opened in-game within the last ~24 h, and their paimon.moe Excel export saved somewhere outside the repo. **Stop and ask the user for both before running Step 3.** Results go into an anonymized note; nothing personal is committed.

**Files:**
- Modify: `backend/app/smoke.py`
- Create: `docs/superpowers/notes/2026-11-20-phase3-wish-findings.md`

**Interfaces:**
- Consumes: `load_wish_link`, `default_locallow` (Task 3); `fetch_new`, `genshin_page_fn`, `record_uid` (Task 4); `POOL_BY_GACHA_TYPE`.
- Produces: `python -m app.smoke --wishes` (read-only, prints per-pool counts, pity to last 5★, 400-type presence, id-format check); `python -m app.smoke --paimon PATH` (prints sheet names, header rows, row counts only — no names/times).

- [ ] **Step 1: Add the smoke commands**

In `backend/app/smoke.py`, add these imports at the top:

```python
from collections import Counter

from app.settings.store import get_setting
from app.wishes.authkey import default_locallow, load_wish_link
from app.wishes.fetch import fetch_new, genshin_page_fn, record_uid
from app.wishes.types import POOL_BY_GACHA_TYPE, ImportFailed
```

Add these functions:

```python
async def wishes() -> None:
    """Read-only: never writes the database, never prints the URL or authkey."""
    paths = default_paths()
    engine = make_engine(paths.db_file)
    migrate(engine)
    with make_session_factory(engine)() as s:
        game_path = get_setting(s, "game_install_path")
    try:
        link = load_wish_link(game_path, default_locallow())
    except ImportFailed as e:
        sys.exit(e.message)
    print(f"check 1 (wish link): found, cached at {link.cached_at:%Y-%m-%d %H:%M} UTC, region {link.region}")
    raw = await fetch_new(genshin_page_fn(link), set())
    env_uid = read_env(paths.env_file).get("GENSHIN_UID")
    print(f"  records: {len(raw)}; uid matches .env: {str(record_uid(raw)) == env_uid}")
    by_type = Counter(r["gacha_type"] for r in raw)
    print(f"  per gacha type: {dict(sorted(by_type.items()))} (400 present: {'400' in by_type})")
    for pool in ("character", "weapon", "chronicled", "standard", "beginner"):
        rows = sorted((r for r in raw if POOL_BY_GACHA_TYPE[r["gacha_type"]] == pool), key=lambda r: int(r["id"]))
        pity = 0
        for r in rows:
            pity = 0 if r["rank_type"] == "5" else pity + 1
        print(f"  {pool}: {len(rows)} pulls, pity since last 5★: {pity}")
    marked = [r["id"] for r in raw if len(str(r["id"])) == 19 and str(r["id"])[10] == "9"]
    print(f"check 5 (id format): {len(raw)} ids, all 19 digits: "
          f"{all(len(str(r['id'])) == 19 for r in raw)}, ids with '9' as 11th digit: {len(marked)}")


def paimon(path: str) -> None:
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None)
        count = sum(1 for r in rows if any(c is not None for c in r))
        print(f"sheet {ws.title!r}: header {list(header) if header else None}, data rows {count}")
```

Replace the `__main__` block at the bottom with (these two need no cookie, so they run before `main()`):

```python
if __name__ == "__main__":
    if "--paimon" in sys.argv:
        paimon(sys.argv[sys.argv.index("--paimon") + 1])
    elif "--wishes" in sys.argv:
        asyncio.run(wishes())
    else:
        asyncio.run(main())
```

Update the module docstring with the two new lines:

```
python -m app.smoke --wishes          read-only wish fetch check (needs Wish History opened in-game)
python -m app.smoke --paimon FILE     print sheet names/headers/row counts of a paimon.moe export
```

- [ ] **Step 2: Check it still imports**

Run: `cd backend; ..\.venv\Scripts\python -c "import app.smoke"`
Expected: no output, exit 0.

- [ ] **Step 3: Run the live checks (with the user)**

Ask the user to open Wish History in-game once and tell you the path to their paimon.moe export. Then, in the worktree with a copied `.env` and `data/`:

Run: `cd backend; ..\.venv\Scripts\python -m app.smoke --wishes`
Run: `cd backend; ..\.venv\Scripts\python -m app.smoke --paimon "<path the user gave>"`

Ask the user to compare, for each pool, "pity since last 5★" with a manual count from the in-game history.

- [ ] **Step 4: Research Capturing Radiance**

Search the web for the current community model of Capturing Radiance (e.g. "Capturing Radiance consecutive 50/50 losses counter"). Decide one value for `RADIANCE_LIKELY_AT` (the count of consecutive lost 50/50s at which the next 50/50 is considered "likely Radiance"), or `None` if sources disagree. Record the sources' URLs in the note.

- [ ] **Step 5: Write the findings note**

Create `docs/superpowers/notes/2026-11-20-phase3-wish-findings.md` with **counts and yes/no answers only** (no UID, URL, authkey, item names, or times):

```markdown
# Phase 3 — live wish findings

**Run:** <date>, `python -m app.smoke --wishes` and `--paimon` in the phase 3 worktree.

1. Wish link found: yes/no. Records fetched: N. UID matches .env: yes/no.
2. 400-type records returned by the 301/400 queries: yes/no (N).
3. paimon.moe workbook: sheet names <list>; header row <list>; data rows per sheet <counts>.
4. Per-pool pity from the smoke run matched the user's in-game count: <pool: yes/no ...>.
5. Ids: all 19 digits yes/no; ids with `9` as 11th digit: N (must be 0 for the generated-id marker).
6. Capturing Radiance: RADIANCE_LIKELY_AT = <n or None>, sources: <urls>.
```

- [ ] **Step 6: Apply the findings**

- If (5) found any id with `9` as the 11th digit, stop and ask the user; the generated-id marker in Task 7 must change.
- Put the confirmed sheet names and headers into Task 8's `SHEETS` / `COLUMNS` constants before starting Task 8 (edit this plan's Task 8 code if they differ from the defaults written there).
- Put the Radiance value into Task 11's `RADIANCE_LIKELY_AT`.
- If (2) shows no 400 records but the user has pulled on the second character banner, keep 400 in `FETCH_TYPES` (already there) and note it.

- [ ] **Step 7: Delete the copied `.env`/`data/` from the worktree, then commit**

```powershell
git add backend/app/smoke.py docs/superpowers/notes/2026-11-20-phase3-wish-findings.md
git commit -m "chore(wishes): live wish smoke checks and anonymized findings"
```

---
### Task 6: Banner data from paimon.moe (`banners.py`) and its game-data refresh

**Files:**
- Create: `backend/app/wishes/banners.py`, `backend/tests/fixtures/paimon_banners.js`
- Modify: `backend/app/gamedata/service.py`, `backend/tests/helpers.py`, `backend/tests/test_api_settings.py`
- Test: `backend/tests/test_wish_banners.py`

**Interfaces:**
- Consumes: `GameBanner` (Task 1), `BANNERS_URL` (Task 1), `GameCharacter`, `GameWeapon`.
- Produces:
  - `class BannerParseError(ValueError)`
  - `js_to_json(text: str) -> str`, `parse_banners(text: str) -> dict[str, list[dict]]`
  - `POOL_BY_KEY = {"beginners": "beginner", "standard": "standard", "characters": "character", "weapons": "weapon", "chronicled": "chronicled"}`
  - `name_slug(name: str) -> str`, `SLUG_OVERRIDES: dict[str, str]` (paimon slug → our `name_slug`)
  - `slug_index(session) -> dict[str, int]`
  - `@dataclass(frozen=True) BannerData(key, pool, name, short_name, start, end, timezone_dependent, timezone_dependent_end, order, featured_5: list[int], featured_4: list[int], version: str | None)` — as in paimon.moe's own `src/functions/wish.js`: a `timezoneDependent` start (`timezoneDependentEnd` end) is a UTC+8 instant to be shifted to server time; other times are already server-local clock times
  - `build_banners(parsed: dict, slugs: dict[str, int], overrides: dict[str, str] = SLUG_OVERRIDES) -> tuple[list[BannerData], set[str]]` (banners, unmapped slugs)
  - `async fetch_banners_js(http: httpx.AsyncClient) -> str`
  - In `gamedata/service.py`: `refresh_banners(session_factory, http, now=None, force=False) -> bool`; `refresh_all` also refreshes banners (after characters and materials); `gamedata_status()` gains `"banners": {"fetched_at", "last_error", "count", "unmapped": list[str]}`.
- Test helper: `yatta_transport()` also serves `tests/fixtures/paimon_banners.js` for any URL path ending in `banners.js`.

- [ ] **Step 1: Create the fixture** (hand-made, in paimon.moe's format)

```js
// backend/tests/fixtures/paimon_banners.js
export const banners = {
  beginners: [
    {
      name: "Beginners' Wish",
      shortName: "Beginners' Wish",
      image: 1,
      start: '2000-01-01 00:00:00',
      end: '2200-01-01 00:00:00',
      color: '#FFFFFF',
    },
  ],
  standard: [
    {
      name: 'Wanderlust Invocation',
      shortName: 'Wanderlust Invocation',
      image: 1,
      start: '2000-01-01 00:00:00',
      end: '2200-01-01 00:00:00',
      color: '#FFFFFF',
    },
  ],
  characters: [
    // {
    //   name: 'Commented Out',
    // },
    {
      name: 'Tide of Furina',
      image: 1,
      shortName: 'Furina',
      start: '2024-01-10 06:00:00',
      end: '2024-01-30 17:59:00',
      color: '#55E4B0',
      timezoneDependent: true,
      featured: ['furina'],
      featuredRare: ['bennett', 'xiangling', 'xingqiu'],
      version: '4.3',
    },
    {
      name: 'Bloom of Nahida',
      image: 1,
      shortName: 'Nahida',
      start: '2024-01-10 06:00:00',
      end: '2024-01-30 17:59:00',
      color: '#55E4B0',
      timezoneDependent: true,
      timezoneDependentEnd: true,
      featured: ['nahida'],
      featuredRare: ['bennett', 'xiangling', 'xingqiu'],
      version: '4.3',
    },
    {
      name: 'Tide of Furina',
      image: 2,
      shortName: 'Furina',
      start: '2024-01-30 18:00:00',
      end: '2024-02-20 14:59:00',
      color: '#55E4B0',
      featured: ['furina'],
      featuredRare: ['bennett'],
      version: '4.4',
    },
  ],
  weapons: [
    {
      name: 'Epitome Invocation',
      image: 1,
      start: '2024-01-10 06:00:00',
      end: '2024-01-30 17:59:00',
      shortName: 'Mistsplitter',
      color: '#ffb169',
      timezoneDependent: true,
      featured: ['mistsplitter_reforged', 'a_thousand_floating_dreams'],
      featuredRare: ['favonius_sword', 'the_flute'],
      version: '4.3',
    },
  ],
  chronicled: [
    {
      name: 'Ode to the Dawn Breeze',
      image: 1,
      shortName: 'Mondstadt',
      start: '2024-03-13 06:00:00',
      end: '2024-04-02 17:59:00',
      color: '#eee8e1',
      featured: ['furina', 'mistsplitter_reforged'],
      featuredRare: ['bennett'],
      version: '4.5',
    },
  ],
};
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_wish_banners.py
import json

import pytest

from app.db.models import GameBanner, GameMeta, GameWeapon
from app.gamedata.service import gamedata_status, refresh_banners
from app.wishes.banners import (BannerParseError, build_banners, js_to_json, name_slug, parse_banners,
                                slug_index)
from helpers import FIXTURES, seed_game, yatta_transport
import httpx

JS = (FIXTURES / "paimon_banners.js").read_text(encoding="utf-8")
WEAPONS = [(11401, "Favonius Sword", 4), (11509, "Mistsplitter Reforged", 5),
           (14504, "A Thousand Floating Dreams", 5)]


def seed_weapons(sf):
    with sf.begin() as s:
        for wid, name, rarity in WEAPONS:
            s.merge(GameWeapon(id=wid, name=name, icon="x", rarity=rarity, weapon_type="Sword"))


def test_js_to_json_handles_comments_quotes_and_trailing_commas():
    data = json.loads(js_to_json("export const banners = { a: [ { b: \"It's\", c: 'x', d: true, }, ], // c\n };"))
    assert data == {"a": [{"b": "It's", "c": "x", "d": True}]}


def test_js_to_json_rejects_unexpected_syntax():
    with pytest.raises(BannerParseError):
        js_to_json("export const banners = { a: someVariable };")
    with pytest.raises(BannerParseError):
        js_to_json("export const banners = { a: 'unterminated };")


def test_parse_fixture_keys():
    parsed = parse_banners(JS)
    assert set(parsed) == {"beginners", "standard", "characters", "weapons", "chronicled"}
    assert len(parsed["characters"]) == 3                      # the commented-out banner is ignored


def test_name_slug():
    assert name_slug("Wolf's Gravestone") == "wolfs_gravestone"
    assert name_slug("Amos' Bow") == "amos_bow"
    assert name_slug("Raiden Shogun") == "raiden_shogun"


def test_build_banners_maps_slugs_orders_parallel_and_reports_unmapped(session_factory):
    seed_game(session_factory)
    seed_weapons(session_factory)
    with session_factory() as s:
        slugs = slug_index(s)
    banners, unmapped = build_banners(parse_banners(JS), slugs)
    by_name = {(b.pool, b.name, b.order, b.start): b for b in banners}
    furina = by_name[("character", "Tide of Furina", 0, "2024-01-10 06:00:00")]
    nahida = by_name[("character", "Bloom of Nahida", 1, "2024-01-10 06:00:00")]
    assert furina.featured_5 == [10000089] and nahida.featured_5 == [10000073]
    assert furina.featured_4 == [10000032, 10000023] and furina.timezone_dependent
    assert not furina.timezone_dependent_end and nahida.timezone_dependent_end
    later = by_name[("character", "Tide of Furina", 0, "2024-01-30 18:00:00")]
    assert not later.timezone_dependent
    weapon = next(b for b in banners if b.pool == "weapon")
    assert weapon.featured_5 == [11509, 14504] and weapon.featured_4 == [11401]
    assert unmapped == {"xingqiu", "the_flute"}
    assert {b.pool for b in banners} == {"beginner", "standard", "character", "weapon", "chronicled"}
    assert len({b.key for b in banners}) == len(banners)


def test_overrides_map_odd_slugs(session_factory):
    seed_game(session_factory)
    with session_factory() as s:
        slugs = slug_index(s)
    parsed = {"characters": [{"name": "X", "shortName": "X", "start": "2024-01-01 00:00:00",
                              "end": "2024-01-02 00:00:00", "featured": ["hydro_archon"], "featuredRare": []}]}
    banners, unmapped = build_banners(parsed, slugs, overrides={"hydro_archon": "furina"})
    assert banners[0].featured_5 == [10000089] and unmapped == set()


async def test_refresh_banners_stores_rows_and_status(session_factory):
    seed_game(session_factory)
    seed_weapons(session_factory)
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh_banners(session_factory, http, force=True) is True
    with session_factory() as s:
        assert s.query(GameBanner).count() == 7
        status = gamedata_status(s)["banners"]
    assert status["count"] == 7 and status["last_error"] is None
    assert status["unmapped"] == ["the_flute", "xingqiu"]


async def test_refresh_banners_failure_keeps_cache(session_factory):
    seed_game(session_factory)
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_banners(session_factory, http, force=True)

    def broken(request):
        return httpx.Response(200, text="export const banners = { a: nope };")
    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as http:
        assert await refresh_banners(session_factory, http, force=True) is False
    with session_factory() as s:
        assert s.query(GameBanner).count() == 7
        assert gamedata_status(s)["banners"]["last_error"].startswith("BannerParseError")
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_banners.py -q`
Expected: FAIL (`ModuleNotFoundError: app.wishes.banners`).

- [ ] **Step 4: Implement `banners.py`**

```python
# backend/app/wishes/banners.py
"""paimon.moe's banners.js (MIT, github.com/MadeBaruna/paimon-moe) → GameBanner rows.
The converter is deliberately strict: anything unexpected raises and the cached banners stay."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BANNERS_URL
from app.db.models import GameCharacter, GameWeapon

POOL_BY_KEY = {"beginners": "beginner", "standard": "standard", "characters": "character",
               "weapons": "weapon", "chronicled": "chronicled"}
# paimon.moe slug -> our name_slug, for the few names that do not normalise to the same slug.
SLUG_OVERRIDES: dict[str, str] = {}
ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}


class BannerParseError(ValueError):
    pass


def js_to_json(text: str) -> str:
    try:
        start, end = text.index("{"), text.rindex("}")
    except ValueError:
        raise BannerParseError("no object literal found") from None
    src, out, i, n = text[start:end + 1], [], 0, end + 1 - start
    while i < n:
        c = src[i]
        if c in "'\"":
            j, buf = i + 1, []
            while True:
                if j >= n:
                    raise BannerParseError("unterminated string")
                d = src[j]
                if d == "\\" and j + 1 < n:
                    buf.append(ESCAPES.get(src[j + 1], src[j + 1]))
                    j += 2
                    continue
                if d == c:
                    break
                buf.append(d)
                j += 1
            out.append(json.dumps("".join(buf)))
            i = j + 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/*", i):
            j = src.find("*/", i)
            if j < 0:
                raise BannerParseError("unterminated comment")
            i = j + 2
        elif c.isalpha() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            word = src[i:j]
            k = j
            while k < n and src[k].isspace():
                k += 1
            if word in ("true", "false", "null"):
                out.append(word)
            elif k < n and src[k] == ":":
                out.append(json.dumps(word))
            else:
                raise BannerParseError(f"unexpected identifier {word!r}")
            i = j
        elif c in "]}":
            if out and out[-1] == ",":
                out.pop()                      # trailing comma
            out.append(c)
            i += 1
        elif c in "{[:,":
            out.append(c)
            i += 1
        elif c.isspace():
            i += 1
        elif c.isdigit() or c == "-":
            j = i + 1
            while j < n and (src[j].isdigit() or src[j] in ".eE+-"):
                j += 1
            out.append(src[i:j])
            i = j
        else:
            raise BannerParseError(f"unexpected character {c!r}")
    return "".join(out)


def parse_banners(text: str) -> dict[str, list[dict]]:
    try:
        data = json.loads(js_to_json(text))
    except json.JSONDecodeError as e:
        raise BannerParseError(f"invalid JSON after conversion: {e.msg}") from None
    if not isinstance(data, dict) or not set(POOL_BY_KEY) & set(data):
        raise BannerParseError("no banner lists found")
    return {k: v for k, v in data.items() if k in POOL_BY_KEY and isinstance(v, list)}


def name_slug(name: str) -> str:
    cleaned = re.sub(r"['’\"]", "", name.lower())
    return re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")


def slug_index(session: Session) -> dict[str, int]:
    out = {name_slug(n): i for i, n in session.execute(select(GameWeapon.id, GameWeapon.name))}
    out.update({name_slug(n): i for i, n in session.execute(select(GameCharacter.id, GameCharacter.name))})
    return out


@dataclass(frozen=True)
class BannerData:
    key: str
    pool: str
    name: str
    short_name: str
    start: str
    end: str
    timezone_dependent: bool
    timezone_dependent_end: bool
    order: int
    featured_5: list[int]
    featured_4: list[int]
    version: str | None


def build_banners(parsed: dict, slugs: dict[str, int],
                  overrides: dict[str, str] = SLUG_OVERRIDES) -> tuple[list[BannerData], set[str]]:
    unmapped: set[str] = set()

    def ids(values) -> list[int]:
        out = []
        for slug in values or []:
            item = slugs.get(overrides.get(slug, slug))
            if item is None:
                unmapped.add(slug)
            else:
                out.append(item)
        return out

    banners: dict[str, BannerData] = {}
    for key, pool in POOL_BY_KEY.items():
        seen_starts: dict[str, int] = defaultdict(int)
        for b in parsed.get(key, []):
            start = str(b["start"])
            order = seen_starts[start] if pool == "character" else 0
            seen_starts[start] += 1
            data = BannerData(
                key=f"{pool}|{start}|{order}", pool=pool, name=str(b["name"]),
                short_name=str(b.get("shortName") or b["name"]), start=start, end=str(b["end"]),
                timezone_dependent=bool(b.get("timezoneDependent", False)),
                timezone_dependent_end=bool(b.get("timezoneDependentEnd", False)), order=order,
                featured_5=ids(b.get("featured")), featured_4=ids(b.get("featuredRare")),
                version=str(b["version"]) if b.get("version") is not None else None)
            banners[data.key] = data
    return list(banners.values()), unmapped


async def fetch_banners_js(http: httpx.AsyncClient) -> str:
    r = await http.get(BANNERS_URL, timeout=30)
    r.raise_for_status()
    return r.text
```

- [ ] **Step 5: Hook into the game-data refresh**

In `backend/app/gamedata/service.py`:

Change the models import to include `GameBanner`:

```python
from app.db.models import GameBanner, GameCharacter, GameDomain, GameMaterial, GameMeta, GameWeapon
```

Add after `refresh_materials` (before `refresh_all`):

```python
META_BANNERS_FETCHED = "banners_fetched_at"
META_BANNERS_ERROR = "banners_last_error"
META_BANNERS_UNMAPPED = "banners_unmapped"


def banners_need_refresh(session: Session, now: datetime) -> bool:
    fetched = _get_meta(session, META_BANNERS_FETCHED)
    if not fetched or session.scalar(select(func.count()).select_from(GameBanner)) == 0:
        return True
    return now - datetime.fromisoformat(fetched.rstrip("Z")) > timedelta(days=GAMEDATA_MAX_AGE_DAYS)


async def refresh_banners(session_factory: sessionmaker, http: httpx.AsyncClient,
                          now: datetime | None = None, force: bool = False) -> bool:
    """Download paimon.moe's banner list if stale (or forced). Needs characters and weapons first."""
    from app.wishes.banners import BannerParseError, build_banners, fetch_banners_js, parse_banners, slug_index
    now = now or utcnow()
    with session_factory() as s:
        if not force and not banners_need_refresh(s, now):
            return False
    try:
        parsed = parse_banners(await fetch_banners_js(http))
    except (*FETCH_ERRORS, BannerParseError) as e:
        message = f"{type(e).__name__}: {e}"[:300]
        log.warning("Banner data refresh failed: %s", message)
        with session_factory.begin() as s:
            _set_meta(s, META_BANNERS_ERROR, message)
        return False
    with session_factory.begin() as s:
        banners, unmapped = build_banners(parsed, slug_index(s))
        s.execute(delete(GameBanner))
        for b in banners:
            s.add(GameBanner(key=b.key, pool=b.pool, name=b.name, short_name=b.short_name, start=b.start,
                             end=b.end, timezone_dependent=b.timezone_dependent,
                             timezone_dependent_end=b.timezone_dependent_end, order=b.order,
                             featured_5=b.featured_5, featured_4=b.featured_4, version=b.version))
        _set_meta(s, META_BANNERS_FETCHED, iso(now))
        _set_meta(s, META_BANNERS_ERROR, None)
        _set_meta(s, META_BANNERS_UNMAPPED, sorted(unmapped))
    return True
```

Change `refresh_all` to:

```python
async def refresh_all(session_factory: sessionmaker, http: httpx.AsyncClient,
                      now: datetime | None = None, force: bool = False) -> bool:
    characters = await refresh(session_factory, http, now=now, force=force)
    materials = await refresh_materials(session_factory, http, now=now, force=force)
    banners = await refresh_banners(session_factory, http, now=now, force=force or characters or materials)
    return characters or materials or banners
```

In `gamedata_status`, add a `"banners"` entry after `"materials"`:

```python
        "banners": {
            "fetched_at": _get_meta(session, META_BANNERS_FETCHED),
            "last_error": _get_meta(session, META_BANNERS_ERROR),
            "count": session.scalar(select(func.count()).select_from(GameBanner)) or 0,
            "unmapped": _get_meta(session, META_BANNERS_UNMAPPED) or [],
        },
```

- [ ] **Step 6: Serve the fixture from the test transport and update the settings defaults test**

In `backend/tests/helpers.py` `yatta_transport`, read the fixture once next to the others:

```python
    banners_js = (FIXTURES / "paimon_banners.js").read_text(encoding="utf-8")
```

and add as the first branch inside `handler` after the `status != 200` check:

```python
        if path.endswith("banners.js"):
            return httpx.Response(200, text=banners_js)
```

In `backend/tests/test_api_settings.py::test_settings_defaults`, change the `gamedata` assertion to:

```python
    assert body["gamedata"] == {"fetched_at": None, "last_error": None, "count": 0,
                               "materials": {"fetched_at": None, "last_error": None, "count": 0},
                               "banners": {"fetched_at": None, "last_error": None, "count": 0,
                                           "unmapped": []}}
```

- [ ] **Step 7: Run the whole backend suite**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: PASS (existing game-data tests still pass; the fixture transport answers the banner URL).

- [ ] **Step 8: Commit**

```powershell
git add backend/app/wishes/banners.py backend/app/gamedata/service.py backend/tests/fixtures/paimon_banners.js backend/tests/helpers.py backend/tests/test_wish_banners.py backend/tests/test_api_settings.py
git commit -m "feat(wishes): banner data from paimon.moe banners.js with the game-data refresh"
```

---

### Task 7: UIGF import and export (`uigf.py`)

**Files:**
- Create: `backend/app/wishes/uigf.py`
- Test: `backend/tests/test_wish_uigf.py`

**Interfaces:**
- Consumes: `IncomingWish`, `ImportFailed`, `POOL_BY_GACHA_TYPE`, `SINGLE_TYPE`, `UID_MISMATCH`, `bad_rows_message`, `normalize_time`, `shift_time`, `to_utc_seconds`, `item_type_of` (Task 2); `Wish` model.
- Produces:
  - `GEN_MARK = "9"`, `generated_id(time: str, seq: int, offset: int) -> str`, `is_generated(id_: str, time: str, offset: int) -> bool`
  - `NOT_UIGF = "This file is not a UIGF export."`
  - `parse_uigf(data: dict, uid: int, offset: int) -> list[IncomingWish]` (raises `ImportFailed`)
  - `build_uigf(rows: Sequence[Wish], uid: int, offset: int, now: datetime, app_version: str) -> dict`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_wish_uigf.py
from datetime import datetime

import pytest

from app.db.models import Wish
from app.wishes.types import ImportFailed, UID_MISMATCH
from app.wishes.uigf import NOT_UIGF, build_uigf, generated_id, is_generated, parse_uigf

UID = 800000001


def rec(id_, gacha_type, time, name, rarity, item_type="Weapon", uigf_type=None):
    r = {"gacha_type": gacha_type, "item_id": "", "count": "1", "time": time, "name": name,
         "item_type": item_type, "rank_type": str(rarity), "id": id_}
    if uigf_type:
        r["uigf_gacha_type"] = uigf_type
    return r


def v4(records, uid=UID, tz=1):
    return {"info": {"export_timestamp": 1, "export_app": "x", "export_app_version": "1", "version": "v4.0"},
            "hk4e": [{"uid": uid, "timezone": tz, "lang": "en-us", "list": records}]}


def test_generated_ids_round_trip():
    gid = generated_id("2024-01-01 09:00:00", 7, 1)            # 08:00 UTC
    assert gid == "1704096000" + "9" + "00000007"
    assert is_generated(gid, "2024-01-01 09:00:00", 1)
    assert not is_generated("1704096000000000007", "2024-01-01 09:00:00", 1)
    assert not is_generated(gid, "2024-01-01 09:00:01", 1)


def test_parse_v4_maps_pools_and_types():
    out = parse_uigf(v4([rec("1704096000000000001", "400", "2024-01-01 09:00:00", "Furina", 5, "Character", "301"),
                         rec("1704096000000000002", "302", "2024-01-01 09:01:00", "Slingshot", 3)]), UID, 1)
    assert [(w.pool, w.gacha_type, w.item_type, w.rarity) for w in out] == [
        ("character", "400", "character", 5), ("weapon", "302", "weapon", 3)]


def test_parse_v4_converts_timezone_to_server_time():
    out = parse_uigf(v4([rec("1", "200", "2024-01-01 16:00:00", "Slingshot", 3)], tz=8), UID, 1)
    assert out[0].time == "2024-01-01 09:00:00"


def test_parse_v4_wrong_uid():
    with pytest.raises(ImportFailed) as e:
        parse_uigf(v4([], uid=800000009), UID, 1)
    assert e.value.message == UID_MISMATCH


def test_parse_v3():
    data = {"info": {"uid": str(UID), "lang": "en-us", "uigf_version": "v3.0", "region_time_zone": 1},
            "list": [rec("5", "200", "2024-01-01 09:00:00", "Slingshot", 3, uigf_type="200")]}
    assert parse_uigf(data, UID, 1)[0].id == "5"
    data["info"]["uid"] = "800000009"
    with pytest.raises(ImportFailed):
        parse_uigf(data, UID, 1)


def test_parse_reports_bad_rows_and_imports_nothing():
    bad = v4([rec("1", "999", "2024-01-01 09:00:00", "X", 3), rec("2", "200", "nope", "X", 3),
              rec("3", "200", "2024-01-01 09:00:00", "X", 3, item_type="武器")])
    with pytest.raises(ImportFailed) as e:
        parse_uigf(bad, UID, 1)
    assert "3 row(s)" in e.value.message and "row 1:" in e.value.message


def test_not_uigf():
    with pytest.raises(ImportFailed) as e:
        parse_uigf({"hello": 1}, UID, 1)
    assert e.value.message == NOT_UIGF


def test_generated_ids_read_back_as_idless():
    gid = generated_id("2024-01-01 09:00:00", 0, 1)
    assert parse_uigf(v4([rec(gid, "200", "2024-01-01 09:00:00", "Slingshot", 3)]), UID, 1)[0].id is None


def test_build_v4():
    rows = [Wish(id=None, pool="character", gacha_type=None, time="2024-01-01 09:00:00", seq=0, name="Furina",
                 item_id=10000089, item_type="character", rarity=5, source="paimon", imported_at=datetime(2024, 1, 2)),
            Wish(id="1704096000000000002", pool="weapon", gacha_type="302", time="2024-01-01 09:01:00", seq=0,
                 name="Slingshot", item_id=None, item_type="weapon", rarity=3, source="game",
                 imported_at=datetime(2024, 1, 2))]
    out = build_uigf(rows, UID, 1, datetime(2024, 1, 3), "0.3.0")
    assert out["info"]["version"] == "v4.0" and out["info"]["export_app"] == "GenshinTracker"
    entry = out["hk4e"][0]
    assert entry["uid"] == UID and entry["timezone"] == 1 and entry["lang"] == "en-us"
    first, second = entry["list"]
    assert first == {"uigf_gacha_type": "301", "gacha_type": "301", "item_id": "10000089", "count": "1",
                     "time": "2024-01-01 09:00:00", "name": "Furina", "item_type": "Character",
                     "rank_type": "5", "id": generated_id("2024-01-01 09:00:00", 0, 1)}
    assert second["item_id"] == "" and second["id"] == "1704096000000000002"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_uigf.py -q`
Expected: FAIL (`ModuleNotFoundError: app.wishes.uigf`).

- [ ] **Step 3: Implement**

```python
# backend/app/wishes/uigf.py
"""UIGF (uigf.org) v3/v4 import and v4 export for Genshin (hk4e)."""
from __future__ import annotations

import calendar
from datetime import datetime
from typing import Sequence

from app.db.models import Wish
from app.wishes.types import (POOL_BY_GACHA_TYPE, SINGLE_TYPE, UID_MISMATCH, ImportFailed, IncomingWish,
                              bad_rows_message, item_type_of, normalize_time, shift_time, to_utc_seconds)

GEN_MARK = "9"
NOT_UIGF = "This file is not a UIGF export."


def generated_id(time: str, seq: int, offset: int) -> str:
    return f"{to_utc_seconds(time, offset):010d}{GEN_MARK}{seq:08d}"


def is_generated(id_: str, time: str, offset: int) -> bool:
    return (len(id_) == 19 and id_[10] == GEN_MARK
            and id_[:10] == f"{to_utc_seconds(time, offset):010d}")


def _entries(data: dict, uid: int) -> tuple[list, int | None]:
    if isinstance(data.get("hk4e"), list):
        mine = [e for e in data["hk4e"] if str(e.get("uid")) == str(uid)]
        if not mine:
            raise ImportFailed(UID_MISMATCH)
        tz = mine[0].get("timezone")
        return list(mine[0].get("list") or []), int(tz) if tz is not None else None
    info = data.get("info")
    if isinstance(info, dict) and isinstance(data.get("list"), list):
        if str(info.get("uid")) != str(uid):
            raise ImportFailed(UID_MISMATCH)
        tz = info.get("region_time_zone")
        return list(data["list"]), int(tz) if tz is not None else None
    raise ImportFailed(NOT_UIGF)


def parse_uigf(data: dict, uid: int, offset: int) -> list[IncomingWish]:
    if not isinstance(data, dict):
        raise ImportFailed(NOT_UIGF)
    rows, tz = _entries(data, uid)
    tz = offset if tz is None else tz
    out, errors = [], []
    for i, r in enumerate(rows, start=1):
        try:
            gacha_type = str(r.get("gacha_type") or "")
            uigf_type = str(r.get("uigf_gacha_type") or gacha_type)
            if uigf_type not in POOL_BY_GACHA_TYPE:
                raise ValueError(f"unknown banner type {uigf_type!r}")
            time = normalize_time(r["time"])
            if tz != offset:
                time = shift_time(time, tz, offset)
            rarity = int(r["rank_type"])
            if rarity not in (3, 4, 5):
                raise ValueError(f"unknown rarity {rarity}")
            name = str(r["name"]).strip()
            if not name:
                raise ValueError("empty name")
            id_ = str(r.get("id") or "").strip() or None
            if id_ is not None and is_generated(id_, time, offset):
                id_ = None
            out.append(IncomingWish(id=id_, pool=POOL_BY_GACHA_TYPE[uigf_type],
                                    gacha_type=gacha_type if gacha_type in POOL_BY_GACHA_TYPE else None,
                                    time=time, name=name, item_type=item_type_of(r["item_type"]), rarity=rarity))
        except KeyError as e:
            errors.append(f"row {i}: missing {e.args[0]}")
        except (ValueError, TypeError) as e:
            errors.append(f"row {i}: {e}")
    if errors:
        raise ImportFailed(bad_rows_message(errors))
    return out


def build_uigf(rows: Sequence[Wish], uid: int, offset: int, now: datetime, app_version: str) -> dict:
    records = []
    for w in sorted(rows, key=lambda w: (w.time, w.pool, w.seq)):
        gacha_type = w.gacha_type or ("301" if w.pool == "character" else SINGLE_TYPE[w.pool])
        records.append({
            "uigf_gacha_type": "301" if gacha_type in ("301", "400") else gacha_type,
            "gacha_type": gacha_type,
            "item_id": str(w.item_id) if w.item_id else "",
            "count": "1",
            "time": w.time,
            "name": w.name,
            "item_type": w.item_type.capitalize(),
            "rank_type": str(w.rarity),
            "id": w.id or generated_id(w.time, w.seq, offset),
        })
    return {
        "info": {"export_timestamp": calendar.timegm(now.timetuple()), "export_app": "GenshinTracker",
                 "export_app_version": app_version, "version": "v4.0"},
        "hk4e": [{"uid": uid, "timezone": offset, "lang": "en-us", "list": records}],
    }
```

- [ ] **Step 4: Run the tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_uigf.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/wishes/uigf.py backend/tests/test_wish_uigf.py
git commit -m "feat(wishes): UIGF v3/v4 import and v4 export with generated ids for id-less pulls"
```

---

### Task 8: paimon.moe Excel import (`paimon_xlsx.py`)

Use the sheet names and headers confirmed in Task 5 (the defaults below are paimon.moe's current export; adjust `SHEETS`/`COLUMNS` if the findings note says otherwise).

**Files:**
- Create: `backend/app/wishes/paimon_xlsx.py`
- Modify: `backend/tests/wishdata.py`
- Test: `backend/tests/test_wish_paimon.py`

**Interfaces:**
- Consumes: `IncomingWish`, `ImportFailed`, `SINGLE_TYPE`, `bad_rows_message`, `normalize_time`, `item_type_of` (Task 2).
- Produces: `SHEETS: dict[str, str]` (sheet name → pool), `IGNORED_SHEETS`, `COLUMNS`, `NOT_XLSX = "This file is not an Excel workbook."`, `parse_paimon_xlsx(content: bytes) -> list[IncomingWish]` (file order kept; ids are `None`).
- Test helper: `make_paimon_xlsx(sheets: dict[str, list[tuple]], header=("Type", "Name", "Time", "⭐", "Pity", "#Roll", "Group", "Banner", "Part")) -> bytes`.

- [ ] **Step 1: Extend the test helper**

Append to `backend/tests/wishdata.py`:

```python
PAIMON_HEADER = ("Type", "Name", "Time", "⭐", "Pity", "#Roll", "Group", "Banner", "Part")


def make_paimon_xlsx(sheets: dict[str, list[tuple]], header: tuple = PAIMON_HEADER) -> bytes:
    """rows are (type, name, time, rarity); the other paimon columns are filled with filler."""
    from io import BytesIO
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        ws.append(list(header))
        for n, (type_, name, time, rarity) in enumerate(rows, start=1):
            ws.append([type_, name, time, rarity, 1, n, n, "Some Banner", ""])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_wish_paimon.py
from datetime import datetime

import pytest

from app.wishes.paimon_xlsx import NOT_XLSX, parse_paimon_xlsx
from app.wishes.types import ImportFailed
from wishdata import make_paimon_xlsx


def test_parses_sheets_in_file_order():
    content = make_paimon_xlsx({
        "Character Event": [("Character", "Furina", "2024-01-10 10:00:00", 5),
                            ("Weapon", "Slingshot", "2024-01-10 10:00:00", 3)],
        "Weapon Event": [("Weapon", "Favonius Sword", datetime(2024, 1, 11, 9, 30, 0), 4)],
        "Standard": [], "Beginners' Wish": [], "Chronicled Wish": [],
        "Information": [],
    })
    out = parse_paimon_xlsx(content)
    assert [(w.pool, w.gacha_type, w.name, w.time, w.rarity, w.id) for w in out] == [
        ("character", None, "Furina", "2024-01-10 10:00:00", 5, None),
        ("character", None, "Slingshot", "2024-01-10 10:00:00", 3, None),
        ("weapon", "302", "Favonius Sword", "2024-01-11 09:30:00", 4, None),
    ]


def test_bad_rows_import_nothing():
    content = make_paimon_xlsx({"Weapon Event": [("Weapon", "A", "not a time", 4), ("Thing", "B", "2024-01-01 00:00:00", 4)],
                                "Mystery Sheet": [("Weapon", "C", "2024-01-01 00:00:00", 3)]})
    with pytest.raises(ImportFailed) as e:
        parse_paimon_xlsx(content)
    msg = e.value.message
    assert "Mystery Sheet" in msg and 'sheet "Weapon Event" row 2' in msg and 'row 3' in msg


def test_missing_column():
    content = make_paimon_xlsx({"Standard": [("Weapon", "A", "2024-01-01 00:00:00", 3)]},
                               header=("Type", "Name", "When", "⭐"))
    with pytest.raises(ImportFailed) as e:
        parse_paimon_xlsx(content)
    assert "missing column Time" in e.value.message


def test_not_a_workbook():
    with pytest.raises(ImportFailed) as e:
        parse_paimon_xlsx(b"definitely not a zip")
    assert e.value.message == NOT_XLSX
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_paimon.py -q`
Expected: FAIL (`ModuleNotFoundError: app.wishes.paimon_xlsx`).

- [ ] **Step 4: Implement**

```python
# backend/app/wishes/paimon_xlsx.py
"""paimon.moe "Export to Excel" workbook → IncomingWish rows (no pull ids; file order kept)."""
from __future__ import annotations

import zipfile
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.wishes.types import SINGLE_TYPE, ImportFailed, IncomingWish, bad_rows_message, item_type_of, normalize_time

SHEETS = {"Character Event": "character", "Weapon Event": "weapon", "Standard": "standard",
          "Beginners' Wish": "beginner", "Chronicled Wish": "chronicled"}
IGNORED_SHEETS = {"Information"}
COLUMNS = {"type": "Type", "name": "Name", "time": "Time", "rarity": "⭐"}
NOT_XLSX = "This file is not an Excel workbook."


def parse_paimon_xlsx(content: bytes) -> list[IncomingWish]:
    try:
        wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError, OSError):
        raise ImportFailed(NOT_XLSX) from None
    out, errors = [], []
    for ws in wb.worksheets:
        if ws.title in IGNORED_SHEETS:
            continue
        pool = SHEETS.get(ws.title)
        if pool is None:
            errors.append(f'sheet "{ws.title}": unknown banner sheet')
            continue
        rows = ws.iter_rows(values_only=True)
        header = [str(c).strip() if c is not None else "" for c in (next(rows, None) or [])]
        missing = [label for label in COLUMNS.values() if label not in header]
        if missing:
            errors.append(f'sheet "{ws.title}": missing column {", ".join(missing)}')
            continue
        col = {k: header.index(label) for k, label in COLUMNS.items()}
        for n, row in enumerate(rows, start=2):
            if row is None or all(c is None for c in row):
                continue
            try:
                rarity = int(row[col["rarity"]])
                if rarity not in (3, 4, 5):
                    raise ValueError(f"unknown rarity {rarity}")
                name = str(row[col["name"]] or "").strip()
                if not name:
                    raise ValueError("empty name")
                out.append(IncomingWish(id=None, pool=pool, gacha_type=SINGLE_TYPE.get(pool),
                                        time=normalize_time(row[col["time"]]), name=name,
                                        item_type=item_type_of(row[col["type"]]), rarity=rarity))
            except (ValueError, TypeError, IndexError) as e:
                errors.append(f'sheet "{ws.title}" row {n}: {e}')
    wb.close()
    if errors:
        raise ImportFailed(bad_rows_message(errors))
    return out
```

- [ ] **Step 5: Run the tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_paimon.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/wishes/paimon_xlsx.py backend/tests/wishdata.py backend/tests/test_wish_paimon.py
git commit -m "feat(wishes): paimon.moe Excel import"
```

---

### Task 9: Merge and de-duplication (`merge.py`)

**Files:**
- Create: `backend/app/wishes/merge.py`
- Modify: `backend/tests/wishdata.py`
- Test: `backend/tests/test_wish_merge.py`

**Interfaces:**
- Consumes: `Wish` (Task 1); `IncomingWish`, `ItemResolver` (Task 2).
- Produces: `@dataclass MergeResult(added: int = 0, upgraded: int = 0, skipped: int = 0, unknown_names: set[str])`; `merge(session: Session, incoming: list[IncomingWish], source: str, now: datetime) -> MergeResult`. Caller owns the transaction (call inside `session_factory.begin()`); `merge` flushes but never commits.
- Test helper: `inc(id_, pool, time, name, rarity=3, gacha_type=None, item_type="weapon") -> IncomingWish`.

Rules (spec §5 plus the Global Constraints refinement):
1. Incoming rows with a real id: known id → skipped (and that stored row is *claimed*). Duplicate ids within one input → skipped.
2. Unknown id → look for an unclaimed stored row with the same `(pool, time, name)`; for **game** input, rows whose `source == "game"` are not candidates. Prefer an id-less candidate, then a file-sourced one. Id-less candidate → upgrade. Game input + file-sourced candidate with an id → upgrade (replace id). File input + candidate holding an id → skipped. No candidate → insert.
3. Id-less incoming rows: per key, insert only `incoming count − stored count` (stored count after steps 1–2), using the *last* occurrences so file order is kept.
4. `seq` is renumbered for every touched `(pool, time)`: all-id groups by numeric id; otherwise by current `seq` (inserted rows get `seq = 1_000_000 + input index` first, so they keep input order after stored rows).

- [ ] **Step 1: Extend the test helper**

Append to `backend/tests/wishdata.py`:

```python
def inc(id_, pool, time, name, rarity=3, gacha_type=None, item_type="weapon"):
    from app.wishes.types import IncomingWish
    return IncomingWish(id=id_, pool=pool, gacha_type=gacha_type, time=time, name=name,
                        item_type=item_type, rarity=rarity)
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_wish_merge.py
from datetime import datetime

from sqlalchemy import select

from app.db.models import GameWeapon, Wish
from app.wishes.merge import merge
from helpers import seed_game
from wishdata import inc

NOW = datetime(2024, 2, 1)
T = "2024-01-10 10:00:00"


def run(sf, rows, source):
    with sf.begin() as s:
        return merge(s, rows, source, NOW)


def stored(sf, pool=None):
    with sf() as s:
        q = select(Wish).order_by(Wish.pool, Wish.time, Wish.seq)
        if pool:
            q = q.where(Wish.pool == pool)
        return list(s.scalars(q))


def test_game_import_then_reimport_adds_nothing(session_factory):
    rows = [inc("1704880800000000002", "weapon", T, "Slingshot", gacha_type="302"),
            inc("1704880800000000001", "weapon", T, "Favonius Sword", 4, "302")]
    r = run(session_factory, rows, "game")
    assert (r.added, r.upgraded, r.skipped) == (2, 0, 0)
    assert [w.name for w in stored(session_factory)] == ["Favonius Sword", "Slingshot"]   # seq by id
    r = run(session_factory, rows, "game")
    assert (r.added, r.upgraded, r.skipped) == (0, 0, 2)


def test_paimon_ten_pull_multiset_counting(session_factory):
    run(session_factory, [inc(None, "weapon", T, "Slingshot", gacha_type="302")], "paimon")
    r = run(session_factory, [inc(None, "weapon", T, "Slingshot", gacha_type="302"),
                              inc(None, "weapon", T, "Slingshot", gacha_type="302")], "paimon")
    assert (r.added, r.skipped) == (1, 1)
    assert len(stored(session_factory)) == 2


def test_paimon_twice_adds_nothing_and_keeps_file_order(session_factory):
    rows = [inc(None, "character", T, "Furina", 5, item_type="character"),
            inc(None, "character", T, "Slingshot"),
            inc(None, "character", T, "Bennett", 4, item_type="character")]
    assert run(session_factory, rows, "paimon").added == 3
    assert run(session_factory, rows, "paimon").added == 0
    assert [w.name for w in stored(session_factory)] == ["Furina", "Slingshot", "Bennett"]


def test_game_upgrades_idless_rows(session_factory):
    run(session_factory, [inc(None, "character", T, "Furina", 5, item_type="character")], "paimon")
    r = run(session_factory, [inc("1704880800000000009", "character", T, "Furina", 5, "301", "character")], "game")
    assert (r.added, r.upgraded) == (0, 1)
    (w,) = stored(session_factory)
    assert (w.id, w.source, w.gacha_type) == ("1704880800000000009", "game", "301")


def test_game_replaces_ids_invented_by_other_trackers(session_factory):
    run(session_factory, [inc("1111111111000000001", "weapon", T, "Slingshot", gacha_type="302")], "uigf")
    r = run(session_factory, [inc("1704880800000000003", "weapon", T, "Slingshot", gacha_type="302")], "game")
    assert (r.added, r.upgraded) == (0, 1)
    assert stored(session_factory)[0].id == "1704880800000000003"


def test_file_with_other_ids_does_not_duplicate_game_rows(session_factory):
    run(session_factory, [inc("1704880800000000003", "weapon", T, "Slingshot", gacha_type="302")], "game")
    r = run(session_factory, [inc("1111111111000000001", "weapon", T, "Slingshot", gacha_type="302")], "uigf")
    assert (r.added, r.skipped) == (0, 1)
    assert stored(session_factory)[0].id == "1704880800000000003"


def test_two_game_pulls_same_key_second_is_inserted(session_factory):
    a = inc("1704880800000000001", "weapon", T, "Slingshot", gacha_type="302")
    b = inc("1704880800000000002", "weapon", T, "Slingshot", gacha_type="302")
    run(session_factory, [a], "game")
    r = run(session_factory, [a, b], "game")
    assert (r.added, r.skipped) == (1, 1)
    assert len(stored(session_factory)) == 2


def test_resolves_item_ids_and_reports_unknown_names(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        s.add(GameWeapon(id=11401, name="Favonius Sword", icon="x", rarity=4, weapon_type="Sword"))
    r = run(session_factory, [inc(None, "weapon", T, "Favonius Sword", 4, "302"),
                              inc(None, "weapon", T, "Brand New Bow", 4, "302")], "paimon")
    assert r.unknown_names == {"Brand New Bow"}
    assert {w.name: w.item_id for w in stored(session_factory)} == {"Favonius Sword": 11401, "Brand New Bow": None}


def test_pools_are_separate(session_factory):
    run(session_factory, [inc(None, "weapon", T, "Slingshot", gacha_type="302")], "paimon")
    r = run(session_factory, [inc(None, "standard", T, "Slingshot", gacha_type="200")], "paimon")
    assert r.added == 1
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_merge.py -q`
Expected: FAIL (`ModuleNotFoundError: app.wishes.merge`).

- [ ] **Step 4: Implement**

```python
# backend/app/wishes/merge.py
"""The only write path into `wish`: de-duplicate by id, then by (pool, time, name) multisets."""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Wish
from app.wishes.types import IncomingWish, ItemResolver

TEMP_SEQ = 1_000_000


@dataclass
class MergeResult:
    added: int = 0
    upgraded: int = 0
    skipped: int = 0
    unknown_names: set[str] = field(default_factory=set)


def merge(session: Session, incoming: list[IncomingWish], source: str, now: datetime) -> MergeResult:
    result = MergeResult()
    if not incoming:
        return result
    resolver = ItemResolver.from_session(session)
    pools = {w.pool for w in incoming}
    existing = list(session.scalars(select(Wish).where(Wish.pool.in_(pools)).order_by(Wish.time, Wish.seq)))
    by_id = {w.id: w for w in existing if w.id}
    by_key: dict[tuple, list[Wish]] = defaultdict(list)
    by_time: dict[tuple, list[Wish]] = defaultdict(list)
    for w in existing:
        by_key[(w.pool, w.time, w.name)].append(w)
        by_time[(w.pool, w.time)].append(w)
    claimed: set[int] = set()
    touched: set[tuple] = set()

    def insert(w: IncomingWish, index: int) -> None:
        item_id = resolver.resolve(w.name)
        row = Wish(id=w.id, pool=w.pool, gacha_type=w.gacha_type, time=w.time, seq=TEMP_SEQ + index,
                   name=w.name, item_id=item_id, item_type=w.item_type, rarity=w.rarity, source=source,
                   imported_at=now)
        session.add(row)
        claimed.add(id(row))
        by_key[(w.pool, w.time, w.name)].append(row)
        by_time[(w.pool, w.time)].append(row)
        if w.id:
            by_id[w.id] = row
        if item_id is None:
            result.unknown_names.add(w.name)
        touched.add((w.pool, w.time))
        result.added += 1

    # 1) rows with real ids: known ids first, so they claim their stored rows
    pending: list[tuple[int, IncomingWish]] = []
    seen: set[str] = set()
    for index, w in enumerate(incoming):
        if not w.id:
            continue
        if w.id in seen:
            result.skipped += 1
            continue
        seen.add(w.id)
        row = by_id.get(w.id)
        if row is not None:
            claimed.add(id(row))
            result.skipped += 1
        else:
            pending.append((index, w))

    # 2) unknown ids: upgrade a matching row, skip a same pull stored under a game id, or insert
    for index, w in pending:
        cands = [r for r in by_key[(w.pool, w.time, w.name)]
                 if id(r) not in claimed and not (source == "game" and r.source == "game")]
        cand = (next((r for r in cands if r.id is None), None)
                or next((r for r in cands if r.source != "game"), None)
                or (cands[0] if cands else None))
        if cand is None:
            insert(w, index)
            continue
        claimed.add(id(cand))
        if cand.id is None or source == "game":
            if cand.id:
                by_id.pop(cand.id, None)
            cand.id, cand.source = w.id, source
            cand.gacha_type = w.gacha_type or cand.gacha_type
            cand.item_id = cand.item_id or resolver.resolve(w.name)
            by_id[w.id] = cand
            touched.add((w.pool, w.time))
            result.upgraded += 1
        else:
            result.skipped += 1

    # 3) id-less rows: insert only the surplus per key, keeping the last occurrences
    idless = [(i, w) for i, w in enumerate(incoming) if not w.id]
    wanted = Counter((w.pool, w.time, w.name) for _, w in idless)
    have = {k: len(by_key[k]) for k in wanted}
    remaining = dict(wanted)
    for index, w in idless:
        k = (w.pool, w.time, w.name)
        surplus = wanted[k] - have[k]
        if remaining[k] <= surplus:
            insert(w, index)
        else:
            result.skipped += 1
        remaining[k] -= 1

    # 4) renumber seq inside every touched timestamp
    session.flush()
    for key in touched:
        group = by_time[key]
        if all(r.id for r in group):
            group.sort(key=lambda r: int(r.id))
        else:
            group.sort(key=lambda r: r.seq)
        for i, r in enumerate(group):
            r.seq = i
    session.flush()
    return result
```

Note for step 3: `remaining[k]` counts down from the number of occurrences; an occurrence is inserted only when at most `surplus` occurrences (itself included) are left, i.e. the last `surplus` ones.

- [ ] **Step 5: Run the tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_merge.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```powershell
git add backend/app/wishes/merge.py backend/tests/wishdata.py backend/tests/test_wish_merge.py
git commit -m "feat(wishes): de-duplicating merge with id upgrades and multiset key matching"
```

---
### Task 10: Import runner (`importer.py`) and app wiring

**Files:**
- Create: `backend/app/wishes/importer.py`
- Modify: `backend/app/config.py`, `backend/app/gamedata/service.py`, `backend/app/context.py`, `backend/app/main.py`, `backend/tests/helpers.py`, `backend/tests/wishdata.py`
- Test: `backend/tests/test_wish_importer.py`

**Interfaces:**
- Consumes: `backup_db` (`app.sync.backup`), `WishLink`, `link_status` (Task 3), `fetch_new`, `to_incoming`, `record_uid`, `WishLinkExpired`, `FetchFailed`, `LINK_EXPIRED`, `PageFn` (Task 4), `parse_uigf`, `build_uigf`, `NOT_UIGF` (Task 7), `parse_paimon_xlsx` (Task 8), `merge` (Task 9), `ImportFailed`, `NEEDS_UID`, `UID_MISMATCH` (Task 2).
- Produces:
  - `APP_VERSION = "0.3.0"` in `config.py`
  - `class ImportBusy(Exception)`
  - `WishImporter(session_factory, paths: Paths, link_reader: Callable[[str], WishLink], page_factory: Callable[[WishLink], PageFn], on_unknown: Callable[[set[str]], Awaitable[None]], clock=utcnow, sleep=asyncio.sleep)` with:
    - `running: bool` (property)
    - `async start_game() -> int` (joins a running game import; raises `ImportBusy` if a file import runs)
    - `async import_file(filename: str, content: bytes) -> dict` (raises `ImportBusy`; `.xlsx` → paimon, anything else → UIGF JSON)
    - `async wait() -> None`
    - `status() -> dict` → `{"running": bool, "last": None | {"id", "source", "started_at", "finished_at", "ok", "added", "upgraded", "skipped", "error"}}` (times ISO `...Z`)
    - `cache_status() -> dict` → `{"status": ..., "cached_at": datetime | None}`
  - `claim_unknown_ids_refresh(session, ids, now, meta_key=META_UNKNOWN_REFRESH)` gains the `meta_key` parameter; `META_WISH_UNKNOWN_REFRESH = "wish_unknown_refresh"`
  - `AppContext.wishes: WishImporter`; `create_app(..., wish_link_reader=None, wish_page_factory=None)`; `make_client(..., wish_link_reader=None, wish_page_factory=None)`
- Test helper: `write_env(paths, uid=FAKE_UID, region="os_euro")`, `fake_link()`.

- [ ] **Step 1: Extend the test helper**

Append to `backend/tests/wishdata.py`:

```python
def write_env(paths, uid: int = FAKE_UID, region: str = "os_euro") -> None:
    paths.env_file.write_text(f"GENSHIN_UID={uid}\nGENSHIN_REGION={region}\n", encoding="utf-8")


def fake_link():
    from datetime import datetime
    from app.wishes.authkey import WishLink
    return WishLink(authkey=FAKE_AUTHKEY, region="os_euro", cached_at=datetime(2024, 1, 1))


def uigf_bytes(records: list[dict], uid: int = FAKE_UID, tz: int = 1) -> bytes:
    import json
    return json.dumps({"info": {"export_timestamp": 1, "export_app": "test", "export_app_version": "1",
                                "version": "v4.0"},
                       "hk4e": [{"uid": uid, "timezone": tz, "lang": "en-us", "list": records}]}).encode()
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_wish_importer.py
import asyncio
import json
import logging
from datetime import datetime

import pytest
from sqlalchemy import func, select

from app.db.models import Wish, WishImport
from app.wishes import importer as importer_mod
from app.wishes.authkey import CACHE_LOCKED
from app.wishes.fetch import LINK_EXPIRED
from app.wishes.importer import INTERRUPTED, ImportBusy, WishImporter
from app.wishes.types import NEEDS_UID, UID_MISMATCH, ImportFailed
from wishdata import (FakeGachaApi, fake_link, make_paimon_xlsx, raw_wish, uigf_bytes, wish_url,
                      write_env)

GAME = [raw_wish(str(1704880800000000000 + i), "302", f"2024-01-10 10:00:{i:02d}", "Slingshot", 3)
        for i in range(5)] + [raw_wish("1704880800000000100", "301", "2024-01-10 11:00:00", "Furina", 5,
                                       "Character")]


async def no_sleep(_s):
    return None


def make(paths, sf, page=None, api=None, link_error=None):
    unknown: list[set[str]] = []

    def reader(game_path: str):
        if link_error:
            raise ImportFailed(link_error)
        return fake_link()

    async def on_unknown(names):
        unknown.append(names)

    imp = WishImporter(sf, paths, reader, lambda link: page or api.page, on_unknown, sleep=no_sleep)
    imp.unknown = unknown
    return imp


def count(sf, model=Wish):
    with sf() as s:
        return s.scalar(select(func.count()).select_from(model))


async def run_game(imp):
    await imp.start_game()
    await imp.wait()
    return imp.status()["last"]


async def test_game_import_backs_up_merges_and_snapshots(paths, session_factory):
    write_env(paths)
    imp = make(paths, session_factory, api=FakeGachaApi(GAME))
    last = await run_game(imp)
    assert last["ok"] is True and last["added"] == 6 and imp.running is False
    assert len(list(paths.wish_backups.glob("tracker-*.db"))) == 1
    (snap,) = paths.wish_backups.glob("uigf-*.json")
    assert len(json.loads(snap.read_text("utf-8"))["hk4e"][0]["list"]) == 6
    assert list(paths.backups.glob("tracker-*.db")) == []          # sync backups untouched
    assert (await run_game(imp))["added"] == 0                      # incremental: stops at known ids


async def test_expired_link_changes_nothing(paths, session_factory):
    write_env(paths)
    last = await run_game(make(paths, session_factory, api=FakeGachaApi(GAME, expire_after=0)))
    assert last["ok"] is False and last["error"] == LINK_EXPIRED
    assert count(session_factory) == 0


async def test_locked_cache_message_and_no_backup(paths, session_factory):
    write_env(paths)
    last = await run_game(make(paths, session_factory, api=FakeGachaApi(GAME), link_error=CACHE_LOCKED))
    assert last["error"] == CACHE_LOCKED
    assert list(paths.wish_backups.glob("*")) == []


async def test_other_account_is_refused(paths, session_factory):
    write_env(paths)
    rows = [raw_wish("1704880800000000001", "302", "2024-01-10 10:00:00", "Slingshot", 3, uid=800000002)]
    last = await run_game(make(paths, session_factory, api=FakeGachaApi(rows)))
    assert last["error"] == UID_MISMATCH and count(session_factory) == 0


async def test_needs_uid(paths, session_factory):
    last = await run_game(make(paths, session_factory, api=FakeGachaApi(GAME)))
    assert last["error"] == NEEDS_UID


async def test_unexpected_error_never_exposes_the_url(paths, session_factory, caplog):
    caplog.set_level(logging.DEBUG)
    write_env(paths)

    async def page(gacha_type, end_id):
        raise RuntimeError(f"request to {wish_url()} failed")
    last = await run_game(make(paths, session_factory, page=page))
    assert last["error"] == "Import failed (RuntimeError)."
    assert "SECRET-AUTHKEY" not in caplog.text


async def test_single_flight(paths, session_factory):
    write_env(paths)
    gate = asyncio.Event()

    async def page(gacha_type, end_id):
        await gate.wait()
        return []
    imp = make(paths, session_factory, page=page)
    first = await imp.start_game()
    assert await imp.start_game() == first
    with pytest.raises(ImportBusy):
        await imp.import_file("x.json", b"{}")
    gate.set()
    await imp.wait()
    assert count(session_factory, WishImport) == 1


async def test_paimon_file_twice(paths, session_factory):
    write_env(paths)
    imp = make(paths, session_factory)
    content = make_paimon_xlsx({"Weapon Event": [("Weapon", "Slingshot", "2024-01-10 10:00:00", 3),
                                                 ("Weapon", "Mystery Blade", "2024-01-10 10:00:00", 3)]})
    assert (await imp.import_file("paimon.xlsx", content))["last"]["added"] == 2
    assert imp.unknown == [{"Slingshot", "Mystery Blade"}]
    assert (await imp.import_file("paimon.xlsx", content))["last"]["added"] == 0


async def test_bad_json_file(paths, session_factory):
    write_env(paths)
    status = await make(paths, session_factory).import_file("x.json", b"not json")
    assert status["last"]["error"] == "This file is not a UIGF export."


async def test_backup_and_snapshot_rotation_keep_ten(paths, session_factory):
    write_env(paths)
    imp = make(paths, session_factory)
    for _ in range(12):
        await imp.import_file("u.json", uigf_bytes([]))
    assert len(list(paths.wish_backups.glob("tracker-*.db"))) == 10
    assert len(list(paths.wish_backups.glob("uigf-*.json"))) == 10


async def test_merge_failure_rolls_back(paths, session_factory, monkeypatch):
    write_env(paths)

    def broken_merge(session, incoming, source, now):
        session.add(Wish(id=None, pool="standard", gacha_type="200", time="2024-01-01 00:00:00", seq=0,
                         name="X", item_id=None, item_type="weapon", rarity=3, source="uigf", imported_at=now))
        session.flush()
        raise RuntimeError("boom")
    monkeypatch.setattr(importer_mod, "merge", broken_merge)
    status = await make(paths, session_factory).import_file("u.json", uigf_bytes([]))
    assert status["last"]["error"] == "Import failed (RuntimeError)."
    assert count(session_factory) == 0


def test_interrupted_imports_are_closed_on_start(paths, session_factory):
    with session_factory.begin() as s:
        s.add(WishImport(started_at=datetime(2024, 1, 1), source="game", ok=None, added=0, upgraded=0, skipped=0))
    imp = make(paths, session_factory)
    last = imp.status()["last"]
    assert last["ok"] is False and last["error"] == INTERRUPTED


def test_cache_status_hides_link(paths, session_factory):
    assert make(paths, session_factory).cache_status()["status"] == "found"
    assert make(paths, session_factory, link_error=CACHE_LOCKED).cache_status()["status"] == "locked"
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_importer.py -q`
Expected: FAIL (`ModuleNotFoundError: app.wishes.importer`).

- [ ] **Step 4: Implement the importer**

Add to `backend/app/config.py` (next to the other wish constants):

```python
APP_VERSION = "0.3.0"
```

```python
# backend/app/wishes/importer.py
"""One wish import at a time: (link) → backup → read → merge in one transaction → UIGF snapshot."""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Awaitable, Callable

from sqlalchemy import select, update
from sqlalchemy.orm import sessionmaker

from app.config import APP_VERSION, WISH_BACKUPS_KEPT, Paths
from app.db.models import Wish, WishImport
from app.servertime import offset_hours
from app.settings.envfile import read_env
from app.settings.store import get_setting
from app.sync.backup import backup_db
from app.timeutil import iso, utcnow
from app.wishes.authkey import WishLink, link_status
from app.wishes.fetch import (LINK_EXPIRED, FetchFailed, PageFn, WishLinkExpired, fetch_new, record_uid,
                              to_incoming)
from app.wishes.merge import merge
from app.wishes.paimon_xlsx import parse_paimon_xlsx
from app.wishes.types import NEEDS_UID, UID_MISMATCH, ImportFailed, IncomingWish
from app.wishes.uigf import NOT_UIGF, build_uigf, parse_uigf

log = logging.getLogger(__name__)
FETCH_FAILED = "Couldn't read the wish history ({kind}). Try again in a minute."
INTERRUPTED = "Interrupted: the app was closed during the import."


class ImportBusy(Exception):
    pass


def import_dict(row: WishImport) -> dict:
    return {"id": row.id, "source": row.source, "started_at": iso(row.started_at),
            "finished_at": iso(row.finished_at), "ok": row.ok, "added": row.added,
            "upgraded": row.upgraded, "skipped": row.skipped, "error": row.error}


class WishImporter:
    def __init__(self, session_factory: sessionmaker, paths: Paths,
                 link_reader: Callable[[str], WishLink], page_factory: Callable[[WishLink], PageFn],
                 on_unknown: Callable[[set[str]], Awaitable[None]], clock=utcnow, sleep=asyncio.sleep):
        self._sf = session_factory
        self._paths = paths
        self._link_reader = link_reader
        self._page_factory = page_factory
        self._on_unknown = on_unknown
        self._clock = clock
        self._sleep = sleep
        self._busy = False
        self._source: str | None = None
        self._current_id: int | None = None
        self._task: asyncio.Task | None = None
        with session_factory.begin() as s:
            s.execute(update(WishImport).where(WishImport.ok.is_(None))
                      .values(ok=False, error=INTERRUPTED, finished_at=clock()))

    @property
    def running(self) -> bool:
        return self._busy

    async def start_game(self) -> int:
        if self._busy:
            if self._source == "game" and self._current_id is not None:
                return self._current_id
            raise ImportBusy()
        import_id = self._begin("game")
        self._task = asyncio.create_task(self._run(import_id, "game", self._prepare_game, self._read_game))
        return import_id

    async def import_file(self, filename: str, content: bytes) -> dict:
        if self._busy:
            raise ImportBusy()
        source = "paimon" if filename.lower().endswith(".xlsx") else "uigf"
        import_id = self._begin(source)

        async def prepare():
            return None

        async def read(_ctx, uid: int, offset: int) -> list[IncomingWish]:
            return await asyncio.to_thread(self._parse_file, source, content, uid, offset)

        await self._run(import_id, source, prepare, read)
        return self.status()

    async def wait(self) -> None:
        if self._task is not None:
            await asyncio.gather(self._task, return_exceptions=True)

    def status(self) -> dict:
        with self._sf() as s:
            row = s.scalars(select(WishImport).order_by(WishImport.id.desc()).limit(1)).first()
            return {"running": self._busy, "last": None if row is None else import_dict(row)}

    def cache_status(self) -> dict:
        with self._sf() as s:
            game_path = get_setting(s, "game_install_path")
        return link_status(lambda: self._link_reader(game_path))

    # --- internals -------------------------------------------------------
    def _begin(self, source: str) -> int:
        self._busy, self._source = True, source
        try:
            with self._sf.begin() as s:
                row = WishImport(started_at=self._clock(), source=source, ok=None, added=0, upgraded=0, skipped=0)
                s.add(row)
                s.flush()
                self._current_id = row.id
        except Exception:
            self._busy = False
            raise
        return self._current_id

    def _account(self) -> tuple[int, int]:
        env = read_env(self._paths.env_file)
        if not env.get("GENSHIN_UID"):
            raise ImportFailed(NEEDS_UID)
        return int(env["GENSHIN_UID"]), offset_hours(env.get("GENSHIN_REGION"))

    async def _prepare_game(self) -> WishLink:
        with self._sf() as s:
            game_path = get_setting(s, "game_install_path")
        return await asyncio.to_thread(self._link_reader, game_path)

    async def _read_game(self, link: WishLink, uid: int, offset: int) -> list[IncomingWish]:
        with self._sf() as s:
            known = set(s.scalars(select(Wish.id).where(Wish.id.is_not(None))))
        try:
            raw = await fetch_new(self._page_factory(link), known, sleep=self._sleep)
        except WishLinkExpired:
            raise ImportFailed(LINK_EXPIRED) from None
        except FetchFailed as e:
            raise ImportFailed(FETCH_FAILED.format(kind=e.kind)) from None
        found = record_uid(raw)
        if found is not None and found != uid:
            raise ImportFailed(UID_MISMATCH)
        try:
            return [to_incoming(r) for r in raw]
        except (KeyError, ValueError, TypeError) as e:
            raise ImportFailed(f"Unexpected wish data from the server ({type(e).__name__}).") from None

    def _parse_file(self, source: str, content: bytes, uid: int, offset: int) -> list[IncomingWish]:
        if source == "paimon":
            return parse_paimon_xlsx(content)
        try:
            data = json.loads(content.decode("utf-8-sig"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ImportFailed(NOT_UIGF) from None
        return parse_uigf(data, uid, offset)

    def _write_snapshot(self, uid: int, offset: int) -> str:
        now = self._clock()
        with self._sf() as s:
            rows = list(s.scalars(select(Wish)))
        data = build_uigf(rows, uid, offset, now, APP_VERSION)
        path = self._paths.wish_backups / f"uigf-{now:%Y%m%d-%H%M%S-%f}.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        for old in sorted(self._paths.wish_backups.glob("uigf-*.json"))[:-WISH_BACKUPS_KEPT]:
            old.unlink()
        return path.name

    def _finish(self, import_id: int, *, ok: bool, result=None, error: str | None = None,
                backup: str | None = None, snapshot: str | None = None) -> None:
        with self._sf.begin() as s:
            row = s.get(WishImport, import_id)
            row.ok, row.error, row.finished_at = ok, error, self._clock()
            row.backup_file, row.snapshot_file = backup, snapshot
            if result is not None:
                row.added, row.upgraded, row.skipped = result.added, result.upgraded, result.skipped

    async def _run(self, import_id: int, source: str, prepare, read) -> None:
        backup_name = None
        try:
            uid, offset = self._account()
            ctx = await prepare()
            backup = await asyncio.to_thread(backup_db, self._paths.db_file, self._paths.wish_backups,
                                             self._clock(), WISH_BACKUPS_KEPT)
            backup_name = backup.name if backup is not None else None
            incoming = await read(ctx, uid, offset)
            with self._sf.begin() as s:
                result = merge(s, incoming, source, self._clock())
            snapshot = None
            try:
                snapshot = await asyncio.to_thread(self._write_snapshot, uid, offset)
            except OSError as e:
                log.warning("Wish snapshot failed: %s", type(e).__name__)
            self._finish(import_id, ok=True, result=result, backup=backup_name, snapshot=snapshot)
            if result.unknown_names:
                try:
                    await self._on_unknown(result.unknown_names)
                except Exception as e:  # noqa: BLE001
                    log.warning("Game-data refresh after a wish import failed: %s", type(e).__name__)
        except ImportFailed as e:
            self._finish(import_id, ok=False, error=e.message, backup=backup_name)
        except Exception as e:  # noqa: BLE001 - never str(e): network errors can carry the wish URL
            log.warning("Wish import failed: %s", type(e).__name__)
            self._finish(import_id, ok=False, error=f"Import failed ({type(e).__name__}).", backup=backup_name)
        finally:
            self._busy = False
```

- [ ] **Step 5: Throttle key for unknown wish names**

In `backend/app/gamedata/service.py`, replace `claim_unknown_ids_refresh` with:

```python
META_WISH_UNKNOWN_REFRESH = "wish_unknown_refresh"


def claim_unknown_ids_refresh(session: Session, ids: set, now: datetime,
                              meta_key: str = META_UNKNOWN_REFRESH) -> bool:
    """True (and remembered) unless this same set of unknown ids/names already forced a
    refresh within the last hour; a gaps run every few edits must not re-download everything."""
    key = sorted(ids)
    last = _get_meta(session, meta_key)
    if (last and last.get("ids") == key
            and now - datetime.fromisoformat(last["at"].rstrip("Z")) < UNKNOWN_REFRESH_EVERY):
        return False
    _set_meta(session, meta_key, {"ids": key, "at": iso(now)})
    return True
```

- [ ] **Step 6: Wire into the app**

In `backend/app/context.py`, import `from app.wishes.importer import WishImporter` and add the field `wishes: WishImporter` to `AppContext` after `sync`.

In `backend/app/main.py`:

Add imports:

```python
from app.gamedata.service import META_WISH_UNKNOWN_REFRESH, claim_unknown_ids_refresh, refresh_all
from app.wishes.authkey import default_locallow, load_wish_link
from app.wishes.fetch import genshin_page_fn
from app.wishes.importer import WishImporter
```

(replacing the existing `from app.gamedata.service import claim_unknown_ids_refresh, refresh_all`).

Change the signature to:

```python
def create_app(paths: Paths | None = None, *, source_factory=None, accounts_fetcher=None,
               http_client: httpx.AsyncClient | None = None, offline: bool | None = None,
               wish_link_reader=None, wish_page_factory=None) -> FastAPI:
```

After `sync = SyncManager(...)`, add:

```python
    async def on_unknown_wish_names(names: set[str]) -> None:
        if is_offline:
            return
        with session_factory.begin() as s:
            if not claim_unknown_ids_refresh(s, names, utcnow(), meta_key=META_WISH_UNKNOWN_REFRESH):
                return
        await refresh_all(session_factory, http, force=True)

    wishes = WishImporter(session_factory, paths,
                          wish_link_reader or (lambda game_path: load_wish_link(game_path, default_locallow())),
                          wish_page_factory or genshin_page_fn, on_unknown_wish_names)
```

and pass `wishes=wishes` when building `AppContext`. In `lifespan`, before `engine.dispose()`, add:

```python
        await wishes.wait()
```

In `backend/tests/helpers.py` `make_client`, add keyword parameters `wish_link_reader=None, wish_page_factory=None` and pass them through to `create_app`.

- [ ] **Step 7: Run the whole backend suite**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```powershell
git add backend/app/config.py backend/app/wishes/importer.py backend/app/gamedata/service.py backend/app/context.py backend/app/main.py backend/tests/helpers.py backend/tests/wishdata.py backend/tests/test_wish_importer.py
git commit -m "feat(wishes): single-flight importer with wish backups, snapshots and safe errors"
```

---

### Task 11: Pity, outcomes, fate points, Radiance (`pity.py`)

**Files:**
- Create: `backend/app/wishes/pity.py`
- Test: `backend/tests/test_wish_pity.py`

**Interfaces:**
- Consumes: `Wish`, `WishChart`, `GameBanner`, `GameCharacter`, `GameWeapon` (Task 1); `PITY`, `POOLS`, `shift_time`, `server_local_now` (Task 2).
- Produces:
  - `RADIANCE_START = "2024-08-28 00:00:00"`, `RADIANCE_LIKELY_AT: int | None` (value from Task 5)
  - `@dataclass(frozen=True) BannerWindow(key, pool, name, short_name, start, end, order, featured_5: tuple[int, ...], featured_4: tuple[int, ...])` (start/end in server-local time)
  - `banner_windows(banners: Iterable[GameBanner], offset: int) -> dict[str, list[BannerWindow]]`
  - `attribute(w: Wish, windows: list[BannerWindow]) -> BannerWindow | None`
  - `@dataclass PullView(pk, name, item_id, item_type, rarity, time, pity, outcome: str | None, banner: str | None, banner_key: str | None)`
  - `@dataclass PoolResult(pool, total, pity5, pity4, hard, soft, next_state, fives, fours, fate, radiance, pity_at: dict[int, int], banner_at: dict[int, BannerWindow | None])` with property `in_soft`
  - `summarize_pool(pool, rows, windows, chart, now_local, offset, names) -> PoolResult`
  - `load_names(session) -> dict[int, str]`, `summarize(session, now_utc: datetime, offset: int) -> dict[str, PoolResult]`
  - Outcomes: `won`, `lost`, `guaranteed`, `unknown` (character, weapon), `charted`, `not_charted` (chronicled with an active chart), `None` otherwise. `next_state`: `50/50`, `75/25`, `guaranteed`, `unknown` (character/weapon), else `None`.
  - `fate` (weapon/chronicled): `{"points": 0 | 1 | None, "max": 1, "chart_item_id": int | None, "chart_name": str | None, "choices": [{"item_id", "name"}], "banner": str | None}`; a chart whose item was obtained, or that was set outside the current banner, is inactive (`points: None`).
  - `radiance` (character): `{"losses": int | None, "likely": bool | None, "estimate": True}`.

Banner times follow paimon.moe's own `src/functions/wish.js`: a `timezone_dependent` start (`timezone_dependent_end` end) is a UTC+8 time and becomes server-local via `shift_time(t, 8, offset)`; other times are already server-local.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_wish_pity.py
from datetime import datetime, timedelta

from app.db.models import GameBanner, Wish, WishChart
from app.wishes import pity as pity_mod
from app.wishes.pity import attribute, banner_windows, summarize_pool

FURINA, NAHIDA, DILUC = 10000089, 10000073, 10000016
MIST, DREAMS, WOLF = 11509, 14504, 12502
NAMES = {FURINA: "Furina", NAHIDA: "Nahida", DILUC: "Diluc", MIST: "Mistsplitter Reforged",
         DREAMS: "A Thousand Floating Dreams", WOLF: "Wolf's Gravestone"}


def banner(pool, start, end, order=0, f5=(), tz=False, tz_end=False, name="B"):
    return GameBanner(key=f"{pool}|{start}|{order}", pool=pool, name=name, short_name=name, start=start, end=end,
                      timezone_dependent=tz, timezone_dependent_end=tz_end, order=order, featured_5=list(f5),
                      featured_4=[], version="4.3")


def pulls(pool, items, start="2024-01-15 10:00:00", gacha_type="301"):
    """items: 3 / 4 for filler, or (rarity, item_id) tuples. One pull per minute."""
    t0 = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
    out = []
    for i, it in enumerate(items):
        rarity, item_id = (it, None) if isinstance(it, int) else it
        gt = gacha_type[i] if isinstance(gacha_type, list) else gacha_type
        out.append(Wish(pk=i + 1, id=None, pool=pool, gacha_type=gt,
                        time=(t0 + timedelta(minutes=i)).strftime("%Y-%m-%d %H:%M:%S"), seq=0,
                        name=NAMES.get(item_id, "Filler"), item_id=item_id if rarity == 5 else 999,
                        item_type="character", rarity=rarity, source="game", imported_at=t0))
    return out


CHAR_WINDOWS = [banner("character", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [FURINA], name="Furina"),
                banner("character", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 1, [NAHIDA], name="Nahida")]


def summ(pool, rows, banners=(), chart=None, now_local="2024-01-20 00:00:00", offset=8):
    return summarize_pool(pool, rows, banner_windows(banners, offset).get(pool, []), chart, now_local, offset, NAMES)


def test_pity_counts_reset_and_carry_over():
    r = summ("standard", pulls("standard", [3, 3, 4, 3, (5, DILUC), 3, 3, 4, 3], gacha_type="200"))
    assert r.total == 9 and [p.pity for p in r.fives] == [5]
    assert [p.pity for p in r.fours] == [3, 3]
    assert (r.pity5, r.pity4, r.hard, r.next_state) == (4, 1, 90, None)


def test_soft_flag():
    r = summ("character", pulls("character", [3] * 73))
    assert r.pity5 == 73 and r.in_soft


def test_character_outcomes_and_next_state():
    rows = pulls("character", [3, (5, DILUC), 3, (5, FURINA), (5, FURINA), (5, NAHIDA)],
                 gacha_type=["301", "301", "301", "301", "301", "400"])
    r = summ("character", rows, CHAR_WINDOWS)
    assert [p.outcome for p in r.fives] == ["lost", "guaranteed", "won", "won"]
    assert [p.banner for p in r.fives] == ["Furina", "Furina", "Furina", "Nahida"]
    assert r.next_state == "50/50"
    r = summ("character", rows + pulls("character", [(5, DILUC)], start="2024-01-16 10:00:00"), CHAR_WINDOWS)
    assert r.next_state == "guaranteed"


def test_no_banner_data_means_unknown_not_wrong():
    r = summ("character", pulls("character", [(5, FURINA), 3]))
    assert [p.outcome for p in r.fives] == ["unknown"] and r.next_state == "unknown"
    assert r.pity5 == 1                                       # pity is still exact


def test_unknown_then_featured_is_unknown_then_known_again():
    early = pulls("character", [(5, DILUC)], start="2023-12-01 10:00:00")        # before any banner
    later = pulls("character", [(5, FURINA), (5, FURINA)], start="2024-01-15 10:00:00")
    for i, w in enumerate(later):
        w.pk = 10 + i
    r = summ("character", early + later, CHAR_WINDOWS)
    assert [p.outcome for p in r.fives] == ["unknown", "unknown", "won"]


def test_unknown_item_name_is_unknown():
    rows = pulls("character", [(5, FURINA)])
    rows[0].item_id = None
    assert summ("character", rows, CHAR_WINDOWS).fives[0].outcome == "unknown"


def test_rows_without_gacha_type_use_the_featured_banner():
    rows = pulls("character", [(5, NAHIDA), (5, DILUC)], gacha_type=None)
    r = summ("character", rows, CHAR_WINDOWS)
    assert [(p.outcome, p.banner) for p in r.fives] == [("won", "Nahida"), ("lost", "Furina")]


def test_timezone_dependent_times_shift_to_server_time():
    b = [banner("character", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [FURINA], tz=True, tz_end=True)]
    w = pulls("character", [(5, FURINA)], start="2024-01-09 18:00:00")[0]
    assert attribute(w, banner_windows(b, -5)["character"]) is not None    # starts 2024-01-09 17:00 in America
    assert attribute(w, banner_windows(b, 8)["character"]) is None
    late = pulls("character", [(5, FURINA)], start="2024-01-30 12:00:00")[0]
    assert attribute(late, banner_windows(b, 1)["character"]) is None       # ends 10:59 in Europe


def test_weapon_75_25():
    wb = [banner("weapon", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [MIST, DREAMS], name="Mist")]
    r = summ("weapon", pulls("weapon", [(5, WOLF), (5, DREAMS)], gacha_type="302"), wb)
    assert [p.outcome for p in r.fives] == ["lost", "guaranteed"] and r.next_state == "75/25"
    assert r.hard == 80


def test_fate_points_follow_the_chart():
    wb = [banner("weapon", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [MIST, DREAMS], name="Mist")]
    chart = WishChart(pool="weapon", item_id=MIST, set_at=datetime(2024, 1, 15, 0, 0))   # 08:00 local (UTC+8)
    rows = pulls("weapon", [3, (5, DREAMS)], start="2024-01-15 10:00:00", gacha_type="302")
    r = summ("weapon", rows, wb, chart)
    assert r.fate["points"] == 1 and r.fate["chart_name"] == "Mistsplitter Reforged"
    assert [c["item_id"] for c in r.fate["choices"]] == [MIST, DREAMS]
    rows += pulls("weapon", [(5, MIST)], start="2024-01-16 10:00:00", gacha_type="302")
    rows[-1].pk = 99
    assert summ("weapon", rows, wb, chart).fate["points"] is None           # chart used up
    old = WishChart(pool="weapon", item_id=MIST, set_at=datetime(2024, 1, 1))
    assert summ("weapon", rows[:2], wb, old).fate["points"] is None         # set before this banner


def test_chronicled_chart_marks_outcomes():
    cb = [banner("chronicled", "2024-01-10 06:00:00", "2024-01-30 17:59:00", 0, [FURINA, MIST], name="Ode")]
    chart = WishChart(pool="chronicled", item_id=FURINA, set_at=datetime(2024, 1, 15, 0, 0))
    r = summ("chronicled", pulls("chronicled", [(5, MIST)], gacha_type="500"), cb, chart)
    assert r.fives[0].outcome == "not_charted" and r.fate["points"] == 1


def test_radiance_counts_losses_since_5_0(monkeypatch):
    monkeypatch.setattr(pity_mod, "RADIANCE_LIKELY_AT", 2)
    cw = [banner("character", "2024-01-01 00:00:00", "2025-12-31 00:00:00", 0, [FURINA])]
    before = pulls("character", [(5, DILUC), (5, FURINA)], start="2024-08-01 10:00:00")
    after = pulls("character", [(5, DILUC), (5, FURINA), (5, DILUC)], start="2024-09-01 10:00:00")
    for i, w in enumerate(after):
        w.pk = 50 + i
    r = summ("character", before + after, cw)
    assert r.radiance == {"losses": 2, "likely": True, "estimate": True}   # guarantee keeps the count
    won = pulls("character", [(5, FURINA)], start="2024-10-01 10:00:00")
    won[0].pk = 90
    r = summ("character", before + after + pulls("character", [(5, FURINA)], start="2024-09-20 10:00:00") + won, cw)
    assert r.radiance["losses"] == 0
```

Note: in `test_radiance_counts_losses_since_5_0` the second `summ` call's sequence is lost, guaranteed, lost, guaranteed (09-20), won (10-01) → count reset to 0; pk collisions do not matter to `summarize_pool` except in `pity_at`/`banner_at`, which these tests do not read.

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_pity.py -q`
Expected: FAIL (`ModuleNotFoundError: app.wishes.pity`).

- [ ] **Step 3: Implement**

```python
# backend/app/wishes/pity.py
"""Pity, 5★ outcomes, next-5★ state, fate points and the Capturing Radiance estimate.
Pure functions over Wish rows (ordered by time, seq within a pool) and GameBanner rows."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GameBanner, GameCharacter, GameWeapon, Wish, WishChart
from app.wishes.types import PITY, POOLS, server_local_now, shift_time

RADIANCE_START = "2024-08-28 00:00:00"
# Consecutive lost 50/50s at which the next 50/50 is "likely Radiance" (community estimate).
# Set from docs/superpowers/notes/2026-11-20-phase3-wish-findings.md; None = show the count only.
RADIANCE_LIKELY_AT: int | None = None
ASIA_OFFSET = 8


@dataclass(frozen=True)
class BannerWindow:
    key: str
    pool: str
    name: str
    short_name: str
    start: str
    end: str
    order: int
    featured_5: tuple[int, ...]
    featured_4: tuple[int, ...]


@dataclass
class PullView:
    pk: int
    name: str
    item_id: int | None
    item_type: str
    rarity: int
    time: str
    pity: int
    outcome: str | None
    banner: str | None
    banner_key: str | None


@dataclass
class PoolResult:
    pool: str
    total: int
    pity5: int
    pity4: int
    hard: int
    soft: int | None
    next_state: str | None
    fives: list[PullView]
    fours: list[PullView]
    fate: dict | None
    radiance: dict | None
    pity_at: dict[int, int] = field(default_factory=dict)
    banner_at: dict[int, "BannerWindow | None"] = field(default_factory=dict)

    @property
    def in_soft(self) -> bool:
        return self.soft is not None and self.pity5 + 1 >= self.soft


def banner_windows(banners: Iterable[GameBanner], offset: int) -> dict[str, list[BannerWindow]]:
    out: dict[str, list[BannerWindow]] = {p: [] for p in POOLS}
    for b in banners:
        start = shift_time(b.start, ASIA_OFFSET, offset) if b.timezone_dependent else b.start
        end = shift_time(b.end, ASIA_OFFSET, offset) if b.timezone_dependent_end else b.end
        out.setdefault(b.pool, []).append(BannerWindow(b.key, b.pool, b.name, b.short_name, start, end, b.order,
                                                       tuple(b.featured_5), tuple(b.featured_4)))
    for windows in out.values():
        windows.sort(key=lambda w: (w.start, w.order))
    return out


def attribute(w: Wish, windows: list[BannerWindow]) -> BannerWindow | None:
    hits = [b for b in windows if b.start <= w.time <= b.end]
    if not hits:
        return None
    if w.pool != "character" or len(hits) == 1:
        return hits[0]
    if w.gacha_type in ("301", "400"):
        want = 1 if w.gacha_type == "400" else 0
    else:
        featured = next((b for b in hits if w.item_id is not None and w.item_id in b.featured_5), None)
        if featured is not None:
            return featured
        want = 0
    return next((b for b in hits if b.order == want), hits[0])


def _outcome(w: Wish, banner: BannerWindow | None, prev_lost: bool | None) -> tuple[str, bool | None]:
    if banner is None or not banner.featured_5 or w.item_id is None:
        return "unknown", None
    if w.item_id in banner.featured_5:
        if prev_lost is None:
            return "unknown", False
        return ("guaranteed" if prev_lost else "won"), False
    return "lost", True


def _radiance(count: int | None, outcome: str) -> int | None:
    if outcome == "won":
        return 0
    if outcome == "lost":
        return None if count is None else count + 1
    if outcome == "unknown":
        return None
    return count                                   # guaranteed: unchanged


def _view(w: Wish, pity: int, outcome: str | None, banner: BannerWindow | None) -> PullView:
    return PullView(w.pk, w.name, w.item_id, w.item_type, w.rarity, w.time, pity, outcome,
                    banner.short_name if banner else None, banner.key if banner else None)


def _fate(pool: str, chart: WishChart | None, current: BannerWindow | None, fives: list[PullView],
          offset: int, names: dict[int, str]) -> dict:
    choices = [{"item_id": i, "name": names.get(i, str(i))} for i in (current.featured_5 if current else ())]
    base = {"points": None, "max": 1, "chart_item_id": None, "chart_name": None, "choices": choices,
            "banner": current.short_name if current else None}
    if chart is None or current is None or chart.item_id not in current.featured_5:
        return base
    set_local = server_local_now(chart.set_at, offset)
    if not (current.start <= set_local <= current.end):
        return base
    points = 0
    for p in fives:
        if p.time < set_local:
            continue
        hit = p.item_id == chart.item_id
        if pool == "chronicled":
            p.outcome = "charted" if hit else "not_charted"
        if hit:
            return base                            # charted item obtained: the chart is used up
        points = 1
    return {**base, "points": points, "chart_item_id": chart.item_id, "chart_name": names.get(chart.item_id)}


def summarize_pool(pool: str, rows: list[Wish], windows: list[BannerWindow], chart: WishChart | None,
                   now_local: str, offset: int, names: dict[int, str]) -> PoolResult:
    rule = PITY[pool]
    c5 = c4 = 0
    prev_lost: bool | None = False
    radiance: int | None = 0
    fives: list[PullView] = []
    fours: list[PullView] = []
    pity_at: dict[int, int] = {}
    banner_at: dict[int, BannerWindow | None] = {}
    for w in rows:
        c5 += 1
        c4 += 1
        banner = attribute(w, windows)
        banner_at[w.pk], pity_at[w.pk] = banner, c5
        if w.rarity == 5:
            outcome = None
            if pool in ("character", "weapon"):
                outcome, prev_lost = _outcome(w, banner, prev_lost)
                if pool == "character" and w.time >= RADIANCE_START:
                    radiance = _radiance(radiance, outcome)
            fives.append(_view(w, c5, outcome, banner))
            c5 = c4 = 0
        elif w.rarity == 4:
            fours.append(_view(w, c4, None, banner))
            c4 = 0
    current = next((b for b in reversed(windows) if b.start <= now_local <= b.end), None)
    fate = _fate(pool, chart, current, fives, offset, names) if pool in ("weapon", "chronicled") else None
    next_state = None
    if pool in ("character", "weapon"):
        next_state = ("unknown" if prev_lost is None else "guaranteed" if prev_lost
                      else "50/50" if pool == "character" else "75/25")
    rad = None
    if pool == "character":
        likely = (radiance >= RADIANCE_LIKELY_AT
                  if radiance is not None and RADIANCE_LIKELY_AT is not None else None)
        rad = {"losses": radiance, "likely": likely, "estimate": True}
    return PoolResult(pool, len(rows), c5, c4, rule.hard, rule.soft, next_state, fives, fours, fate, rad,
                      pity_at, banner_at)


def load_names(session: Session) -> dict[int, str]:
    names = {i: n for i, n in session.execute(select(GameWeapon.id, GameWeapon.name))}
    names.update({i: n for i, n in session.execute(select(GameCharacter.id, GameCharacter.name))})
    return names


def summarize(session: Session, now_utc: datetime, offset: int) -> dict[str, PoolResult]:
    rows = list(session.scalars(select(Wish).order_by(Wish.time, Wish.seq, Wish.pk)))
    windows = banner_windows(list(session.scalars(select(GameBanner))), offset)
    charts = {c.pool: c for c in session.scalars(select(WishChart))}
    names = load_names(session)
    now_local = server_local_now(now_utc, offset)
    by_pool: dict[str, list[Wish]] = {p: [] for p in POOLS}
    for w in rows:
        by_pool.setdefault(w.pool, []).append(w)
    return {p: summarize_pool(p, by_pool[p], windows.get(p, []), charts.get(p), now_local, offset, names)
            for p in POOLS}
```

- [ ] **Step 4: Run the tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_pity.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/wishes/pity.py backend/tests/test_wish_pity.py
git commit -m "feat(wishes): pity, 50/50 outcomes, fate points and Radiance estimate"
```

---

### Task 12: Stats and chart series (`stats.py`)

**Files:**
- Create: `backend/app/wishes/stats.py`
- Test: `backend/tests/test_wish_stats.py`

**Interfaces:**
- Consumes: `PoolResult`, `PullView`, `BannerWindow` (Task 11); `Wish`; `POOLS`.
- Produces:
  - `PRIMOGEMS_PER_PULL = 160`
  - `pool_stats(r: PoolResult) -> dict` → `{"pulls", "primogems", "five", "four", "avg_five_pity": float | None, "won", "lost", "win_rate": float | None}`
  - `overall_stats(results: dict[str, PoolResult]) -> dict` (same keys; won/lost/win rate over character + weapon)
  - `monthly(rows: list[Wish]) -> list[dict]` → `[{"month": "2024-01", "character": n, "weapon": n, "chronicled": n, "standard": n, "beginner": n}]` sorted
  - `pity_histogram(results) -> list[dict]` → 9 buckets `{"bucket": "1-10" … "81-90", "count"}` (pity > 90 counts in the last bucket)
  - `banner_timeline(results) -> list[dict]` → `{"key", "pool", "name", "short_name", "start", "pulls", "fives": [names]}` sorted by `(start, pool)`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_wish_stats.py
from datetime import datetime

from app.db.models import Wish
from app.wishes.pity import BannerWindow, PoolResult, PullView
from app.wishes.stats import banner_timeline, monthly, overall_stats, pity_histogram, pool_stats

B = BannerWindow("character|2024-01-10 06:00:00|0", "character", "Tide", "Furina", "2024-01-10 06:00:00",
                 "2024-01-30 17:59:00", 0, (1,), ())


def pv(pk, pity, outcome, rarity=5, banner=B):
    return PullView(pk, f"I{pk}", 1, "character", rarity, "2024-01-15 10:00:00", pity, outcome,
                    banner.short_name if banner else None, banner.key if banner else None)


def result(pool, total, fives, fours=(), banner_at=None):
    return PoolResult(pool, total, 0, 0, 90, 74, None, list(fives), list(fours), None, None, {},
                      banner_at or {})


def test_pool_stats_excludes_guaranteed_and_unknown_from_win_rate():
    r = result("character", 200, [pv(1, 80, "lost"), pv(2, 10, "guaranteed"), pv(3, 60, "won"),
                                  pv(4, 70, "unknown")], [pv(5, 9, None, 4)])
    s = pool_stats(r)
    assert s == {"pulls": 200, "primogems": 32000, "five": 4, "four": 1, "avg_five_pity": 55.0,
                 "won": 1, "lost": 1, "win_rate": 0.5}
    assert pool_stats(result("standard", 0, []))["avg_five_pity"] is None


def test_overall_stats():
    results = {"character": result("character", 100, [pv(1, 80, "won")]),
               "weapon": result("weapon", 50, [pv(2, 60, "lost")]),
               "standard": result("standard", 10, [pv(3, 10, None)])}
    s = overall_stats(results)
    assert (s["pulls"], s["five"], s["won"], s["lost"], s["win_rate"], s["avg_five_pity"]) == (160, 3, 1, 1, 0.5, 50.0)


def test_monthly_buckets():
    def w(pool, time):
        return Wish(pool=pool, time=time, seq=0, name="x", item_type="weapon", rarity=3, source="game",
                    imported_at=datetime(2024, 1, 1))
    out = monthly([w("character", "2024-02-01 00:00:00"), w("weapon", "2024-01-31 23:59:59"),
                   w("character", "2024-01-05 00:00:00")])
    assert out == [{"month": "2024-01", "character": 1, "weapon": 1, "chronicled": 0, "standard": 0, "beginner": 0},
                   {"month": "2024-02", "character": 1, "weapon": 0, "chronicled": 0, "standard": 0, "beginner": 0}]


def test_pity_histogram():
    h = pity_histogram({"character": result("character", 0, [pv(1, 1, "won"), pv(2, 10, "won"), pv(3, 77, "won"),
                                                             pv(4, 95, "won")])})
    assert len(h) == 9 and h[0] == {"bucket": "1-10", "count": 2}
    assert h[7] == {"bucket": "71-80", "count": 1} and h[8] == {"bucket": "81-90", "count": 1}


def test_banner_timeline():
    r = result("character", 3, [pv(2, 2, "won")], banner_at={1: B, 2: B, 3: None})
    assert banner_timeline({"character": r}) == [
        {"key": B.key, "pool": "character", "name": "Tide", "short_name": "Furina", "start": B.start,
         "pulls": 2, "fives": ["I2"]}]
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_stats.py -q`
Expected: FAIL (`ModuleNotFoundError: app.wishes.stats`).

- [ ] **Step 3: Implement**

```python
# backend/app/wishes/stats.py
"""Headline numbers and chart series. Pure functions over pity.PoolResult and Wish rows."""
from __future__ import annotations

from collections import Counter, defaultdict

from app.db.models import Wish
from app.wishes.pity import PoolResult, PullView
from app.wishes.types import POOLS

PRIMOGEMS_PER_PULL = 160
BUCKETS = 9


def _summary(pulls: int, fives: list[PullView], four: int, judged: list[PullView]) -> dict:
    won = sum(1 for p in judged if p.outcome == "won")
    lost = sum(1 for p in judged if p.outcome == "lost")
    return {
        "pulls": pulls, "primogems": pulls * PRIMOGEMS_PER_PULL, "five": len(fives), "four": four,
        "avg_five_pity": round(sum(p.pity for p in fives) / len(fives), 1) if fives else None,
        "won": won, "lost": lost, "win_rate": round(won / (won + lost), 3) if won + lost else None,
    }


def pool_stats(r: PoolResult) -> dict:
    return _summary(r.total, r.fives, len(r.fours), r.fives)


def overall_stats(results: dict[str, PoolResult]) -> dict:
    fives = [p for r in results.values() for p in r.fives]
    judged = [p for pool in ("character", "weapon") if pool in results for p in results[pool].fives]
    return _summary(sum(r.total for r in results.values()), fives,
                    sum(len(r.fours) for r in results.values()), judged)


def monthly(rows: list[Wish]) -> list[dict]:
    months: dict[str, Counter] = defaultdict(Counter)
    for w in rows:
        months[w.time[:7]][w.pool] += 1
    return [{"month": m, **{p: months[m].get(p, 0) for p in POOLS}} for m in sorted(months)]


def pity_histogram(results: dict[str, PoolResult]) -> list[dict]:
    counts = [0] * BUCKETS
    for r in results.values():
        for p in r.fives:
            counts[min((p.pity - 1) // 10, BUCKETS - 1)] += 1
    return [{"bucket": f"{i * 10 + 1}-{i * 10 + 10}", "count": c} for i, c in enumerate(counts)]


def banner_timeline(results: dict[str, PoolResult]) -> list[dict]:
    out: dict[str, dict] = {}
    for r in results.values():
        for banner in r.banner_at.values():
            if banner is None:
                continue
            entry = out.setdefault(banner.key, {"key": banner.key, "pool": banner.pool, "name": banner.name,
                                                "short_name": banner.short_name, "start": banner.start,
                                                "pulls": 0, "fives": []})
            entry["pulls"] += 1
        for p in r.fives:
            if p.banner_key in out:
                out[p.banner_key]["fives"].append(p.name)
    return sorted(out.values(), key=lambda e: (e["start"], e["pool"]))
```

- [ ] **Step 4: Run the tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_wish_stats.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/wishes/stats.py backend/tests/test_wish_stats.py
git commit -m "feat(wishes): headline stats and chart series"
```

---

### Task 13: Wishes API, Dashboard pity, Settings game path, leak test

**Files:**
- Create: `backend/app/api/wishes.py`
- Modify: `backend/app/api/__init__.py`, `backend/app/api/dashboard.py`, `backend/app/api/settings.py`
- Test: `backend/tests/test_api_wishes.py`

**Interfaces:**
- Consumes: `WishImporter`, `ImportBusy` (Task 10); `summarize`, `PoolResult`, `PullView` (Task 11); `pool_stats`, `overall_stats`, `monthly`, `pity_histogram`, `banner_timeline` (Task 12); `build_uigf` (Task 7); `NEEDS_UID`, `POOLS`.
- Produces (HTTP):
  - `POST /api/wishes/import/game` → `{"import_id": int}`; 409 `Another import is running.`
  - `POST /api/wishes/import/file` (multipart field `file`) → importer status; 400 wrong extension; 413 > 20 MB; 409 busy
  - `GET /api/wishes/import/status` → importer status
  - `GET /api/wishes/summary` → `{"pools": [PoolPayload], "overall": stats, "charts": {"monthly", "pity_histogram", "banners"}, "banners_available": bool, "import": status}`; `PoolPayload = {"pool", "total", "pity5", "pity4", "hard", "soft", "in_soft", "next_state", "fate", "radiance", "stats", "fives": [Pull], "fours": [Pull]}` (lists newest first); `Pull = {"name", "item_id", "icon", "item_type", "rarity", "time", "pity", "outcome", "banner"}`; pools with 0 pulls are left out
  - `GET /api/wishes?pool&rarity&type&banner&q&page` → `{"total", "page", "page_size": 50, "rows": [{"time", "name", "item_id", "icon", "item_type", "rarity", "pool", "banner", "banner_key", "pity"}]}` newest first
  - `PUT /api/wishes/chart/{pool}` body `{"item_id": int | null}` → `PoolPayload`; 404 for pools other than weapon/chronicled; 400 if the item is not a current featured 5★
  - `GET /api/wishes/export` → UIGF v4 JSON with `Content-Disposition: attachment; filename="genshintracker-uigf-<YYYY-MM-DD>.json"`; 400 `NEEDS_UID`
  - `GET /api/wishes/cache-status` → `{"status", "cached_at": iso | null}`
  - `GET /api/dashboard` gains `"pity": [{"pool", "pity5", "hard", "next_state", "fate_points"}]`
  - `GET/PUT /api/settings` gain `game_install_path` (string, ≤ 500 chars, stored stripped)
- Python: `pity_lines(results: dict[str, PoolResult]) -> list[dict]` in `api/wishes.py`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_api_wishes.py
import json
import logging
import time
from datetime import datetime, timedelta

from app.db.models import GameBanner, GameWeapon
from app.timeutil import utcnow
from app.wishes import authkey as ak
from app.wishes.types import ImportFailed, NEEDS_UID
from helpers import make_client, seed_game
from wishdata import (FAKE_AUTHKEY, FakeGachaApi, fake_link, make_game_install, make_paimon_xlsx, raw_wish,
                      wish_url, write_env)

MIST, DREAMS = 11509, 14504


def wait_import(client, timeout=5.0):
    deadline = time.monotonic() + timeout
    while True:
        st = client.get("/api/wishes/import/status").json()
        if not st["running"]:
            return st
        assert time.monotonic() < deadline, "import never finished"
        time.sleep(0.02)


def game_rows():
    rows = [raw_wish(str(1704880800000000000 + i), "200", f"2024-01-10 10:{i // 60:02d}:{i % 60:02d}",
                     "Slingshot", 3) for i in range(60)]
    rows.append(raw_wish("1704880800000000100", "301", "2024-01-11 10:00:00", "Furina", 5, "Character"))
    return rows


def client_with(paths, api=None, reader=None):
    return make_client(paths, wish_link_reader=reader or (lambda game_path: fake_link()),
                       wish_page_factory=lambda link: api.page if api else None)


def seed_current_weapon_banner(client):
    sf = client.app.state.ctx.session_factory
    local = utcnow() + timedelta(hours=1)        # os_euro server time
    start = (local - timedelta(days=3)).strftime("%Y-%m-%d %H:%M:%S")
    end = (local + timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
    with sf.begin() as s:
        s.add(GameWeapon(id=MIST, name="Mistsplitter Reforged", icon="UI_EquipIcon_Sword_Narukami", rarity=5,
                         weapon_type="Sword"))
        s.add(GameWeapon(id=DREAMS, name="A Thousand Floating Dreams", icon="UI_EquipIcon_Catalyst_Ayus",
                         rarity=5, weapon_type="Catalyst"))
        s.add(GameBanner(key=f"weapon|{start}|0", pool="weapon", name="Epitome Invocation", short_name="Mist",
                         start=start, end=end, timezone_dependent=False, timezone_dependent_end=False, order=0,
                         featured_5=[MIST, DREAMS], featured_4=[], version="9.9"))


def test_game_import_summary_history_and_dashboard(paths):
    write_env(paths)
    with client_with(paths, FakeGachaApi(game_rows())) as client:
        seed_game(client.app.state.ctx.session_factory)
        assert client.post("/api/wishes/import/game").status_code == 200
        st = wait_import(client)
        assert st["last"]["ok"] is True and st["last"]["added"] == 61
        summary = client.get("/api/wishes/summary").json()
        pools = {p["pool"]: p for p in summary["pools"]}
        assert set(pools) == {"standard", "character"}
        assert pools["standard"]["pity5"] == 60 and pools["standard"]["in_soft"] is False
        assert pools["character"]["fives"][0]["name"] == "Furina"
        assert pools["character"]["fives"][0]["outcome"] == "unknown"        # no banner data yet
        assert summary["overall"]["pulls"] == 61 and summary["banners_available"] is False
        page1 = client.get("/api/wishes?pool=standard").json()
        assert page1["total"] == 60 and len(page1["rows"]) == 50 and page1["page_size"] == 50
        assert len(client.get("/api/wishes?pool=standard&page=2").json()["rows"]) == 10
        five = client.get("/api/wishes?rarity=5").json()
        assert five["total"] == 1 and five["rows"][0]["pity"] == 1
        assert client.get("/api/wishes?q=furi").json()["total"] == 1
        dash = client.get("/api/dashboard").json()["pity"]
        assert {"pool": "standard", "pity5": 60, "hard": 90, "next_state": None, "fate_points": None} in dash


def test_upload_paimon_then_export_round_trip(paths):
    write_env(paths)
    content = make_paimon_xlsx({"Weapon Event": [("Weapon", "Slingshot", "2024-01-10 10:00:00", 3)] * 2})
    with client_with(paths) as client:
        r = client.post("/api/wishes/import/file", files={"file": ("paimon.xlsx", content)})
        assert r.status_code == 200 and r.json()["last"]["added"] == 2
        exp = client.get("/api/wishes/export")
        assert exp.status_code == 200
        assert 'filename="genshintracker-uigf-' in exp.headers["content-disposition"]
        r = client.post("/api/wishes/import/file", files={"file": ("again.json", exp.content)})
        assert r.json()["last"]["ok"] is True and r.json()["last"]["added"] == 0


def test_upload_validation(paths, monkeypatch):
    write_env(paths)
    with client_with(paths) as client:
        assert client.post("/api/wishes/import/file", files={"file": ("x.csv", b"a")}).status_code == 400
        monkeypatch.setattr("app.api.wishes.WISH_UPLOAD_MAX_BYTES", 10)
        assert client.post("/api/wishes/import/file", files={"file": ("x.json", b"x" * 11)}).status_code == 413


def test_export_needs_uid(paths):
    with client_with(paths) as client:
        r = client.get("/api/wishes/export")
    assert r.status_code == 400 and r.json()["detail"] == NEEDS_UID


def test_chart_validation_and_fate(paths):
    write_env(paths)
    with client_with(paths) as client:
        seed_current_weapon_banner(client)
        assert client.put("/api/wishes/chart/standard", json={"item_id": MIST}).status_code == 404
        assert client.put("/api/wishes/chart/weapon", json={"item_id": 1}).status_code == 400
        body = client.put("/api/wishes/chart/weapon", json={"item_id": MIST}).json()
        assert body["fate"]["points"] == 0 and body["fate"]["chart_name"] == "Mistsplitter Reforged"
        body = client.put("/api/wishes/chart/weapon", json={"item_id": None}).json()
        assert body["fate"]["points"] is None


def test_cache_status(paths):
    def reader(game_path):
        raise ImportFailed(ak.NO_WISH_LINK)
    with client_with(paths, reader=reader) as client:
        assert client.get("/api/wishes/cache-status").json() == {"status": "no_link", "cached_at": None}


def test_settings_game_install_path(paths):
    with client_with(paths) as client:
        assert client.get("/api/settings").json()["game_install_path"] == ""
        body = client.put("/api/settings", json={"game_install_path": "  D:/Games/Genshin Impact  "}).json()
        assert body["game_install_path"] == "D:/Games/Genshin Impact"
        assert client.put("/api/settings", json={"game_install_path": "x" * 501}).status_code == 422


def test_no_wish_endpoint_leaks_the_authkey(paths, caplog, tmp_path):
    caplog.set_level(logging.DEBUG)
    write_env(paths)
    game_dir, locallow = make_game_install(tmp_path / "game")
    attempts = {"n": 0}
    good = FakeGachaApi(game_rows())

    def factory(link):
        assert link.authkey == FAKE_AUTHKEY                # the real reader found the key...
        attempts["n"] += 1
        if attempts["n"] == 1:
            async def broken(gacha_type, end_id):
                raise RuntimeError(f"GET {wish_url()} failed")
            return broken
        return good.page

    with make_client(paths, wish_link_reader=lambda gp: ak.load_wish_link(gp, locallow),
                     wish_page_factory=factory) as client:
        client.put("/api/settings", json={"game_install_path": str(game_dir)})
        bodies = []
        for _ in range(2):
            bodies.append(client.post("/api/wishes/import/game").text)
            bodies.append(json.dumps(wait_import(client)))
        bodies += [client.get(p).text for p in ("/api/wishes/summary", "/api/wishes", "/api/wishes/export",
                                                 "/api/wishes/cache-status", "/api/settings", "/api/dashboard")]
    files = [f.read_bytes().decode("utf-8", "replace") for f in paths.wish_backups.glob("uigf-*.json")]
    dbs = [paths.db_file.read_bytes().decode("latin-1")] + [
        f.read_bytes().decode("latin-1") for f in paths.wish_backups.glob("tracker-*.db")]
    for text in [*bodies, caplog.text, *files, *dbs]:
        assert "SECRET-AUTHKEY" not in text and "authkey=" not in text
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_api_wishes.py -q`
Expected: FAIL (404s / missing `game_install_path`).

- [ ] **Step 3: Implement the router**

```python
# backend/app/api/wishes.py
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import func, select

from app.config import APP_VERSION, WISH_HISTORY_PAGE_SIZE, WISH_UPLOAD_MAX_BYTES
from app.context import AppContext, get_ctx
from app.db.models import GameBanner, GameCharacter, GameWeapon, Wish, WishChart
from app.servertime import offset_hours
from app.settings.envfile import read_env
from app.timeutil import iso, utcnow
from app.wishes.importer import ImportBusy
from app.wishes.pity import PoolResult, PullView, summarize
from app.wishes.stats import banner_timeline, monthly, overall_stats, pity_histogram, pool_stats
from app.wishes.types import NEEDS_UID, POOLS
from app.wishes.uigf import build_uigf

router = APIRouter()
BUSY = "Another import is running."


class ChartIn(BaseModel):
    item_id: int | None


def _env(ctx: AppContext) -> dict:
    return read_env(ctx.paths.env_file)


def _offset(ctx: AppContext) -> int:
    return offset_hours(_env(ctx).get("GENSHIN_REGION"))


def _icons(session) -> dict[int, str]:
    icons = {i: icon for i, icon in session.execute(select(GameWeapon.id, GameWeapon.icon))}
    icons.update({i: icon for i, icon in session.execute(select(GameCharacter.id, GameCharacter.icon))})
    return icons


def _pull(p: PullView, icons: dict[int, str]) -> dict:
    return {"name": p.name, "item_id": p.item_id, "icon": icons.get(p.item_id), "item_type": p.item_type,
            "rarity": p.rarity, "time": p.time, "pity": p.pity, "outcome": p.outcome, "banner": p.banner}


def pool_payload(r: PoolResult, icons: dict[int, str]) -> dict:
    return {"pool": r.pool, "total": r.total, "pity5": r.pity5, "pity4": r.pity4, "hard": r.hard, "soft": r.soft,
            "in_soft": r.in_soft, "next_state": r.next_state, "fate": r.fate, "radiance": r.radiance,
            "stats": pool_stats(r), "fives": [_pull(p, icons) for p in reversed(r.fives)],
            "fours": [_pull(p, icons) for p in reversed(r.fours)]}


def pity_lines(results: dict[str, PoolResult]) -> list[dict]:
    return [{"pool": p, "pity5": results[p].pity5, "hard": results[p].hard, "next_state": results[p].next_state,
             "fate_points": (results[p].fate or {}).get("points")} for p in POOLS if results[p].total]


@router.post("/wishes/import/game")
async def import_game(ctx: AppContext = Depends(get_ctx)) -> dict:
    try:
        return {"import_id": await ctx.wishes.start_game()}
    except ImportBusy:
        raise HTTPException(409, BUSY) from None


@router.post("/wishes/import/file")
async def import_file(file: UploadFile, ctx: AppContext = Depends(get_ctx)) -> dict:
    name = file.filename or ""
    if not name.lower().endswith((".json", ".xlsx")):
        raise HTTPException(400, "Upload a UIGF .json file or a paimon.moe .xlsx export.")
    content = await file.read(WISH_UPLOAD_MAX_BYTES + 1)
    if len(content) > WISH_UPLOAD_MAX_BYTES:
        raise HTTPException(413, "The file is larger than 20 MB.")
    try:
        return await ctx.wishes.import_file(name, content)
    except ImportBusy:
        raise HTTPException(409, BUSY) from None


@router.get("/wishes/import/status")
def import_status(ctx: AppContext = Depends(get_ctx)) -> dict:
    return ctx.wishes.status()


@router.get("/wishes/summary")
def summary(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        results = summarize(s, utcnow(), _offset(ctx))
        icons = _icons(s)
        rows = list(s.scalars(select(Wish)))
        banners_available = (s.scalar(select(func.count()).select_from(GameBanner)) or 0) > 0
    return {
        "pools": [pool_payload(results[p], icons) for p in POOLS if results[p].total],
        "overall": overall_stats(results),
        "charts": {"monthly": monthly(rows), "pity_histogram": pity_histogram(results),
                   "banners": banner_timeline(results)},
        "banners_available": banners_available,
        "import": ctx.wishes.status(),
    }


@router.get("/wishes")
def history(pool: str | None = None, rarity: int | None = None,
            type: Literal["character", "weapon"] | None = None, banner: str | None = None,
            q: str | None = None, page: int = Query(1, ge=1), ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        results = summarize(s, utcnow(), _offset(ctx))
        icons = _icons(s)
        rows = list(s.scalars(select(Wish).order_by(Wish.time.desc(), Wish.seq.desc(), Wish.pk.desc())))
    pity_at = {pk: v for r in results.values() for pk, v in r.pity_at.items()}
    banner_at = {pk: v for r in results.values() for pk, v in r.banner_at.items()}
    needle = (q or "").strip().casefold()

    def keep(w: Wish) -> bool:
        b = banner_at.get(w.pk)
        return ((pool is None or w.pool == pool) and (rarity is None or w.rarity == rarity)
                and (type is None or w.item_type == type) and (banner is None or (b is not None and b.key == banner))
                and (not needle or needle in w.name.casefold()))

    filtered = [w for w in rows if keep(w)]
    size = WISH_HISTORY_PAGE_SIZE
    chunk = filtered[(page - 1) * size: page * size]
    return {"total": len(filtered), "page": page, "page_size": size, "rows": [
        {"time": w.time, "name": w.name, "item_id": w.item_id, "icon": icons.get(w.item_id),
         "item_type": w.item_type, "rarity": w.rarity, "pool": w.pool,
         "banner": banner_at[w.pk].short_name if banner_at.get(w.pk) else None,
         "banner_key": banner_at[w.pk].key if banner_at.get(w.pk) else None,
         "pity": pity_at.get(w.pk)} for w in chunk]}


@router.put("/wishes/chart/{pool}")
def set_chart(pool: str, body: ChartIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    if pool not in ("weapon", "chronicled"):
        raise HTTPException(404, "Only the Weapon and Chronicled banners have a chart.")
    offset = _offset(ctx)
    with ctx.session_factory.begin() as s:
        if body.item_id is None:
            row = s.get(WishChart, pool)
            if row is not None:
                s.delete(row)
        else:
            fate = summarize(s, utcnow(), offset)[pool].fate or {}
            if body.item_id not in {c["item_id"] for c in fate.get("choices", [])}:
                raise HTTPException(400, "Pick one of the current banner's featured 5★ items.")
            s.merge(WishChart(pool=pool, item_id=body.item_id, set_at=utcnow()))
    with ctx.session_factory() as s:
        return pool_payload(summarize(s, utcnow(), offset)[pool], _icons(s))


@router.get("/wishes/export")
def export(ctx: AppContext = Depends(get_ctx)) -> JSONResponse:
    env = _env(ctx)
    if not env.get("GENSHIN_UID"):
        raise HTTPException(400, NEEDS_UID)
    now = utcnow()
    with ctx.session_factory() as s:
        rows = list(s.scalars(select(Wish)))
    data = build_uigf(rows, int(env["GENSHIN_UID"]), offset_hours(env.get("GENSHIN_REGION")), now, APP_VERSION)
    filename = f"genshintracker-uigf-{now:%Y-%m-%d}.json"
    return JSONResponse(data, headers={"Content-Disposition": f'attachment; filename="{filename}"'})


@router.get("/wishes/cache-status")
def cache_status(ctx: AppContext = Depends(get_ctx)) -> dict:
    st = ctx.wishes.cache_status()
    return {"status": st["status"], "cached_at": iso(st["cached_at"])}
```

- [ ] **Step 4: Register and extend Dashboard / Settings**

`backend/app/api/__init__.py`:

```python
from app.api import characters, dashboard, img, planner, settings, sync, wishes

ROUTERS = [settings.router, sync.router, characters.router, dashboard.router, planner.router, wishes.router,
           img.router]
```

In `backend/app/api/dashboard.py`, add imports:

```python
from app.api.wishes import pity_lines
from app.servertime import offset_hours
from app.wishes.pity import summarize
```

and add to the returned dict (inside the `with` block, after `"gaps"`):

```python
            "pity": pity_lines(summarize(s, now, offset_hours(reg))),
```

In `backend/app/api/settings.py`:

```python
class SettingsIn(BaseModel):
    sync_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    default_targets: TargetsIn | None = None
    game_install_path: str | None = Field(default=None, max_length=500)
```

In `settings_payload` add `"game_install_path": get_setting(s, "game_install_path"),`; in `put_settings` add:

```python
        if body.game_install_path is not None:
            set_setting(s, "game_install_path", body.game_install_path.strip())
```

- [ ] **Step 5: Run the whole backend suite**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: PASS (the dashboard secret-leakage test in `test_api_settings.py` still passes; the new leak test passes).

- [ ] **Step 6: Commit**

```powershell
git add backend/app/api backend/tests/test_api_wishes.py
git commit -m "feat(wishes): wishes API, dashboard pity lines, game install path setting"
```

---

### Task 14: Demo and end-to-end seed data

**Files:**
- Modify: `backend/app/devseed.py`
- Test: `backend/tests/test_devseed.py`

**Interfaces:**
- Consumes: `merge` (Task 9), `IncomingWish`, `server_local_now` (Task 2), `GameBanner`.
- Produces (seeded, Asia offset because devseed writes no `.env`): a current character banner (Furina featured) and a current weapon banner (Mistsplitter Reforged + A Thousand Floating Dreams featured) spanning now−7 d … now+14 d, a standard banner; 30 character pulls (pity 2 after Neuvillette lost then Furina guaranteed → next 50/50), 12 weapon pulls (pity 12), 60 standard pulls (one Kaedehara Kazuha 5★ at pull 45, pity 15). Weapon "Slingshot" (3★) is added to the weapon list.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_devseed.py`:

```python
def test_devseed_wishes(tmp_path):
    from app.config import Paths
    from app.db.engine import make_engine, make_session_factory
    from app.devseed import seed
    from app.timeutil import utcnow
    from app.wishes.pity import summarize

    seed(tmp_path)
    engine = make_engine(Paths(tmp_path).db_file)
    with make_session_factory(engine)() as s:
        r = summarize(s, utcnow(), 8)
    engine.dispose()
    assert (r["character"].total, r["character"].pity5, r["character"].next_state) == (30, 2, "50/50")
    assert [p.outcome for p in r["character"].fives] == ["lost", "guaranteed"]
    assert (r["weapon"].total, r["weapon"].pity5) == (12, 12)
    assert [c["name"] for c in r["weapon"].fate["choices"]] == ["Mistsplitter Reforged", "A Thousand Floating Dreams"]
    assert (r["standard"].total, r["standard"].pity5) == (60, 15)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_devseed.py -q`
Expected: FAIL (`KeyError`/assertion: no wishes).

- [ ] **Step 3: Implement**

In `backend/app/devseed.py`:

Add imports:

```python
from datetime import timedelta

from app.db.models import GameBanner
from app.wishes.merge import merge
from app.wishes.types import IncomingWish, server_local_now
```

(extend the existing `datetime` import line instead of adding a second one if you prefer: `from datetime import datetime, timedelta`).

Add `(15301, "Slingshot", "UI_EquipIcon_Bow_Sling", 3, "Bow")` to `WEAPONS`.

Add this helper above `seed`:

```python
def demo_wishes(start_local: str) -> list[IncomingWish]:
    """Pulls one minute apart from start_local; ids increase with time."""
    t0 = datetime.strptime(start_local, "%Y-%m-%d %H:%M:%S") + timedelta(hours=1)
    plans = [
        ("character", "301", 30, {10: ("Bennett", 4, "character"), 20: ("Neuvillette", 5, "character"),
                                  28: ("Furina", 5, "character")}),
        ("weapon", "302", 12, {5: ("Favonius Sword", 4, "weapon")}),
        ("standard", "200", 60, {30: ("Xingqiu", 4, "character"), 45: ("Kaedehara Kazuha", 5, "character")}),
    ]
    out, n = [], 0
    for pool, gacha_type, count, special in plans:
        for i in range(1, count + 1):
            name, rarity, item_type = special.get(i, ("Slingshot", 3, "weapon"))
            time = (t0 + timedelta(minutes=n)).strftime("%Y-%m-%d %H:%M:%S")
            out.append(IncomingWish(id=str(1700000000000000000 + n), pool=pool, gacha_type=gacha_type, time=time,
                                    name=name, item_type=item_type, rarity=rarity))
            n += 1
    return out
```

At the end of `seed()`, before `engine.dispose()`, add:

```python
    with sf.begin() as s:
        local = datetime.strptime(server_local_now(now, 8), "%Y-%m-%d %H:%M:%S")
        start = (local - timedelta(days=7)).strftime("%Y-%m-%d %H:%M:%S")
        end = (local + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
        banners = [
            ("character", "Tide of Furina", "Furina", start, end, [10000089], [10000032, 10000025]),
            ("weapon", "Epitome Invocation", "Mistsplitter", start, end, [11509, 14504], [11401, 13407]),
            ("standard", "Wanderlust Invocation", "Wanderlust Invocation", "2000-01-01 00:00:00",
             "2200-01-01 00:00:00", [], []),
        ]
        for pool, name, short, b_start, b_end, f5, f4 in banners:
            s.add(GameBanner(key=f"{pool}|{b_start}|0", pool=pool, name=name, short_name=short, start=b_start,
                             end=b_end, timezone_dependent=False, timezone_dependent_end=False, order=0,
                             featured_5=f5, featured_4=f4, version="9.9"))
        s.merge(GameMeta(key="banners_fetched_at", value=iso(now)))
        s.flush()
        merge(s, demo_wishes(start), "game", now)
```

(`Xingqiu`, `Neuvillette`, `Kaedehara Kazuha`, `Bennett`, `Furina` are in `CHARACTERS`; the weapon list now contains `Slingshot`, so every demo item resolves to an id.)

- [ ] **Step 4: Run the tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_devseed.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```powershell
git add backend/app/devseed.py backend/tests/test_devseed.py
git commit -m "chore(wishes): demo wishes and banners in the seed data"
```

---
### Task 15: Frontend foundations — types, API client, wish helpers, nav, Dashboard card, Settings

**Files:**
- Create: `frontend/src/lib/wishes.ts`, `frontend/src/lib/wishes.test.ts`
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/routes/+layout.svelte`, `frontend/src/routes/+page.svelte`, `frontend/src/routes/settings/+page.svelte`

**Interfaces:**
- Consumes: the HTTP API from Task 13.
- Produces (TypeScript):
  - types `Pool`, `Outcome`, `WishPull`, `Fate`, `Radiance`, `WishStats`, `PoolSummary`, `WishImport`, `ImportStatus`, `MonthRow`, `BannerRow`, `WishSummary`, `HistoryRow`, `HistoryPage`, `HistoryFilters`, `CacheStatus`, `PityLine`; `Dashboard.pity: PityLine[]`; `Settings.game_install_path: string`; `Settings.gamedata.banners`
  - `api.wishSummary()`, `api.wishHistory(f, page)`, `api.importStatus()`, `api.importGame()`, `api.uploadWishes(file)`, `api.setChart(pool, itemId)`, `api.cacheStatus()`; `saveSettings` accepts `game_install_path`
  - `wishes.ts`: `POOLS`, `POOL_LABEL`, `POOL_COLOR`, `outcomeLabel`, `nextStateLabel`, `pityBar`, `fateLine`, `radianceLine`, `importResultLine`, `cacheStatusLabel`, `pityLine`, `scaleTo`, `niceMax`, `historyQuery`, `DEFAULT_FILTERS`, `loadFilters`, `saveFilters`, `stackedMonths`, `histogramBars`

- [ ] **Step 1: Types**

Append to `frontend/src/lib/types.ts`:

```ts
export type Pool = 'character' | 'weapon' | 'chronicled' | 'standard' | 'beginner';
export type Outcome = 'won' | 'lost' | 'guaranteed' | 'unknown' | 'charted' | 'not_charted';
export interface WishPull {
	name: string; item_id: number | null; icon: string | null; item_type: 'character' | 'weapon';
	rarity: number; time: string; pity: number; outcome: Outcome | null; banner: string | null;
}
export interface Fate {
	points: number | null; max: number; chart_item_id: number | null; chart_name: string | null;
	choices: { item_id: number; name: string }[]; banner: string | null;
}
export interface Radiance { losses: number | null; likely: boolean | null; estimate: boolean }
export interface WishStats {
	pulls: number; primogems: number; five: number; four: number; avg_five_pity: number | null;
	won: number; lost: number; win_rate: number | null;
}
export interface PoolSummary {
	pool: Pool; total: number; pity5: number; pity4: number; hard: number; soft: number | null; in_soft: boolean;
	next_state: string | null; fate: Fate | null; radiance: Radiance | null; stats: WishStats;
	fives: WishPull[]; fours: WishPull[];
}
export interface WishImport {
	id: number; source: 'game' | 'uigf' | 'paimon'; started_at: string; finished_at: string | null;
	ok: boolean | null; added: number; upgraded: number; skipped: number; error: string | null;
}
export interface ImportStatus { running: boolean; last: WishImport | null }
export interface MonthRow { month: string; character: number; weapon: number; chronicled: number; standard: number; beginner: number }
export interface BannerRow { key: string; pool: Pool; name: string; short_name: string; start: string; pulls: number; fives: string[] }
export interface WishSummary {
	pools: PoolSummary[]; overall: WishStats;
	charts: { monthly: MonthRow[]; pity_histogram: { bucket: string; count: number }[]; banners: BannerRow[] };
	banners_available: boolean; import: ImportStatus;
}
export interface HistoryRow {
	time: string; name: string; item_id: number | null; icon: string | null; item_type: 'character' | 'weapon';
	rarity: number; pool: Pool; banner: string | null; banner_key: string | null; pity: number | null;
}
export interface HistoryPage { total: number; page: number; page_size: number; rows: HistoryRow[] }
export interface HistoryFilters { pool: Pool | ''; rarity: number | ''; type: 'character' | 'weapon' | ''; banner: string; q: string }
export interface CacheStatus { status: 'found' | 'no_link' | 'not_found' | 'locked'; cached_at: string | null }
export interface PityLine { pool: Pool; pity5: number; hard: number; next_state: string | null; fate_points: number | null }
```

In `Dashboard` add `pity: PityLine[];`. In `Settings` add `game_install_path: string;` and inside `gamedata` add
`banners: { fetched_at: string | null; last_error: string | null; count: number; unmapped: string[] };`.

- [ ] **Step 2: API client**

In `frontend/src/lib/api.ts`, replace `request` with a shared response parser plus an upload helper, and add the wish calls:

```ts
async function parse<T>(res: Response): Promise<T> {
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

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
	return parse<T>(await fetch(`/api${path}`, {
		method,
		headers: body === undefined ? {} : { 'Content-Type': 'application/json' },
		body: body === undefined ? undefined : JSON.stringify(body)
	}));
}

async function upload<T>(path: string, file: File): Promise<T> {
	const form = new FormData();
	form.append('file', file);
	return parse<T>(await fetch(`/api${path}`, { method: 'POST', body: form }));
}
```

Add to the type import: `CacheStatus, HistoryFilters, HistoryPage, ImportStatus, Pool, PoolSummary, WishSummary`, and `import { historyQuery } from './wishes';`. Change `saveSettings` to accept `game_install_path?: string` and add to `api`:

```ts
	wishSummary: () => request<WishSummary>('GET', '/wishes/summary'),
	wishHistory: (f: HistoryFilters, page: number) => request<HistoryPage>('GET', `/wishes?${historyQuery(f, page)}`),
	importStatus: () => request<ImportStatus>('GET', '/wishes/import/status'),
	importGame: () => request<{ import_id: number }>('POST', '/wishes/import/game'),
	uploadWishes: (file: File) => upload<ImportStatus>('/wishes/import/file', file),
	setChart: (pool: Pool, item_id: number | null) => request<PoolSummary>('PUT', `/wishes/chart/${pool}`, { item_id }),
	cacheStatus: () => request<CacheStatus>('GET', '/wishes/cache-status'),
```

- [ ] **Step 3: Write the failing helper tests**

```ts
// frontend/src/lib/wishes.test.ts
import { describe, expect, it } from 'vitest';
import type { Fate, WishImport } from './types';
import {
	DEFAULT_FILTERS, cacheStatusLabel, fateLine, histogramBars, historyQuery, importResultLine, loadFilters,
	nextStateLabel, niceMax, outcomeLabel, pityBar, pityLine, radianceLine, saveFilters, scaleTo, stackedMonths
} from './wishes';

const fate = (p: Partial<Fate>): Fate => ({
	points: null, max: 1, chart_item_id: null, chart_name: null,
	choices: [{ item_id: 1, name: 'Mistsplitter Reforged' }], banner: 'Mist', ...p
});
const imp = (p: Partial<WishImport>): WishImport => ({
	id: 1, source: 'game', started_at: '2024-01-01T00:00:00Z', finished_at: '2024-01-01T00:01:00Z',
	ok: true, added: 0, upgraded: 0, skipped: 0, error: null, ...p
});

describe('labels', () => {
	it('outcomes and next state', () => {
		expect(outcomeLabel('won')).toBe('Won');
		expect(outcomeLabel('not_charted')).toBe('Not charted');
		expect(outcomeLabel(null)).toBe('');
		expect(nextStateLabel('guaranteed')).toBe('Next 5★: guaranteed featured');
		expect(nextStateLabel('75/25')).toBe('Next 5★: 75/25');
		expect(nextStateLabel(null)).toBe('');
	});
	it('fate line', () => {
		expect(fateLine(fate({}), 'weapon')).toBe('Pick your charted weapon to track fate points');
		expect(fateLine(fate({}), 'chronicled')).toBe('Pick your charted item to track fate points');
		expect(fateLine(fate({ choices: [] }), 'weapon')).toBe('No banner is running right now');
		expect(fateLine(fate({ points: 1, chart_item_id: 1, chart_name: 'Mistsplitter Reforged' }), 'weapon'))
			.toBe('Fate point 1/1 → next 5★ is Mistsplitter Reforged');
		expect(fateLine(fate({ points: 0, chart_item_id: 1, chart_name: 'Mistsplitter Reforged' }), 'weapon'))
			.toBe('Fate point 0/1 · charted Mistsplitter Reforged');
	});
	it('radiance line', () => {
		expect(radianceLine({ losses: 2, likely: true, estimate: true }))
			.toBe('Lost 50/50s in a row: 2 (estimate) · Capturing Radiance likely on your next 50/50');
		expect(radianceLine({ losses: null, likely: null, estimate: true })).toBe('Lost 50/50s in a row: unknown (estimate)');
	});
	it('import result line', () => {
		expect(importResultLine(null)).toBe('No imports yet');
		expect(importResultLine(imp({ added: 37, upgraded: 2 }))).toBe('+37 new · 2 upgraded');
		expect(importResultLine(imp({}))).toBe('No new pulls');
		expect(importResultLine(imp({ ok: false, error: 'Close Genshin Impact and try again.' })))
			.toBe('Close Genshin Impact and try again.');
		expect(importResultLine(imp({ ok: null }))).toBe('Importing…');
	});
	it('cache status label', () => {
		const now = Date.parse('2024-01-01T03:00:00Z');
		expect(cacheStatusLabel({ status: 'found', cached_at: '2024-01-01T00:00:00Z' }, now)).toBe('Wish link found (cached 3 h ago)');
		expect(cacheStatusLabel({ status: 'locked', cached_at: null }, now)).toBe('Game is running (cache locked)');
	});
	it('dashboard pity line', () => {
		expect(pityLine({ pool: 'character', pity5: 42, hard: 90, next_state: 'guaranteed', fate_points: null }))
			.toBe('Character 42/90 · Guaranteed');
		expect(pityLine({ pool: 'weapon', pity5: 12, hard: 80, next_state: '75/25', fate_points: 1 }))
			.toBe('Weapon 12/80 · 75/25 · Fate 1/1');
	});
});

describe('numbers', () => {
	it('pity bar marks', () => {
		expect(pityBar(45, 90, 74)).toEqual({ fill: 50, soft: 82.2 });
		expect(pityBar(120, 90, null)).toEqual({ fill: 100, soft: null });
	});
	it('scales and nice maxima', () => {
		expect(scaleTo([0, 5, 10], 100)).toEqual([0, 50, 100]);
		expect(scaleTo([0, 0], 100)).toEqual([0, 0]);
		expect([niceMax(0), niceMax(7), niceMax(13), niceMax(260)]).toEqual([0, 10, 20, 500]);
	});
	it('stacked months and histogram bars', () => {
		const bars = stackedMonths([{ month: '2024-01', character: 3, weapon: 1, chronicled: 0, standard: 0, beginner: 0 }]);
		expect(bars[0].label).toBe('01/24');
		expect(bars[0].segments.map((s) => [s.name, s.value])).toEqual([
			['Character Event', 3], ['Weapon Event', 1], ['Chronicled Wish', 0], ['Standard', 0], ["Beginners' Wish", 0]
		]);
		expect(histogramBars([{ bucket: '1-10', count: 2 }])[0]).toEqual({
			label: '1-10', segments: [{ name: '5★', value: 2, color: 'var(--wanted)' }]
		});
	});
});

describe('history filters', () => {
	it('builds a query without empty values', () => {
		expect(historyQuery(DEFAULT_FILTERS, 1)).toBe('page=1');
		expect(historyQuery({ pool: 'weapon', rarity: 5, type: '', banner: '', q: 'mist' }, 2))
			.toBe('pool=weapon&rarity=5&q=mist&page=2');
	});
	it('survives unavailable storage', () => {
		const broken = () => { throw new Error('denied'); };
		expect(loadFilters(broken)).toEqual(DEFAULT_FILTERS);
		expect(() => saveFilters(broken, DEFAULT_FILTERS)).not.toThrow();
		const store = new Map<string, string>();
		const fake = () => ({ getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) }) as unknown as Storage;
		saveFilters(fake, { ...DEFAULT_FILTERS, rarity: 5 });
		expect(loadFilters(fake).rarity).toBe(5);
	});
});
```

- [ ] **Step 4: Run to verify failure**

Run: `cd frontend; npm test`
Expected: FAIL (`Cannot find module './wishes'`).

- [ ] **Step 5: Implement `wishes.ts`**

```ts
// frontend/src/lib/wishes.ts
import { timeAgo } from './time';
import type { CacheStatus, Fate, HistoryFilters, MonthRow, Outcome, PityLine, Pool, Radiance, WishImport } from './types';

export const POOLS: Pool[] = ['character', 'weapon', 'chronicled', 'standard', 'beginner'];
export const POOL_LABEL: Record<Pool, string> = {
	character: 'Character Event', weapon: 'Weapon Event', chronicled: 'Chronicled Wish',
	standard: 'Standard', beginner: "Beginners' Wish"
};
const POOL_SHORT: Record<Pool, string> = {
	character: 'Character', weapon: 'Weapon', chronicled: 'Chronicled', standard: 'Standard', beginner: 'Beginner'
};
export const POOL_COLOR: Record<Pool, string> = {
	character: 'var(--wanted)', weapon: 'var(--obtained)', chronicled: 'var(--building)',
	standard: 'var(--muted)', beginner: 'var(--unobtained)'
};
const OUTCOME: Record<Outcome, string> = {
	won: 'Won', lost: 'Lost', guaranteed: 'Guaranteed', unknown: 'Unknown', charted: 'Charted', not_charted: 'Not charted'
};
const NEXT: Record<string, string> = {
	'50/50': 'Next 5★: 50/50', '75/25': 'Next 5★: 75/25', guaranteed: 'Next 5★: guaranteed featured',
	unknown: 'Next 5★: unknown (import older history)'
};

export function outcomeLabel(o: Outcome | null): string {
	return o ? OUTCOME[o] : '';
}

export function nextStateLabel(s: string | null): string {
	return s ? (NEXT[s] ?? '') : '';
}

export function pityBar(pity: number, hard: number, soft: number | null): { fill: number; soft: number | null } {
	const pct = (n: number) => Math.round((n / hard) * 1000) / 10;
	return { fill: Math.min(100, Math.max(0, pct(pity))), soft: soft === null ? null : pct(soft) };
}

export function fateLine(f: Fate | null, pool: Pool): string {
	if (!f) return '';
	if (f.points === null) {
		if (f.choices.length === 0) return 'No banner is running right now';
		return `Pick your charted ${pool === 'weapon' ? 'weapon' : 'item'} to track fate points`;
	}
	return f.points >= 1
		? `Fate point 1/1 → next 5★ is ${f.chart_name}`
		: `Fate point 0/1 · charted ${f.chart_name}`;
}

export function radianceLine(r: Radiance | null): string {
	if (!r) return '';
	const base = `Lost 50/50s in a row: ${r.losses ?? 'unknown'} (estimate)`;
	return r.likely ? `${base} · Capturing Radiance likely on your next 50/50` : base;
}

export function importResultLine(last: WishImport | null): string {
	if (!last) return 'No imports yet';
	if (last.ok === null) return 'Importing…';
	if (!last.ok) return last.error ?? 'Import failed';
	if (!last.added && !last.upgraded) return 'No new pulls';
	return `+${last.added} new` + (last.upgraded ? ` · ${last.upgraded} upgraded` : '');
}

export function cacheStatusLabel(st: CacheStatus, now: number): string {
	switch (st.status) {
		case 'found':
			return st.cached_at ? `Wish link found (cached ${timeAgo(st.cached_at, now)})` : 'Wish link found';
		case 'no_link':
			return 'No wish link in the cache: open Wish History in-game';
		case 'locked':
			return 'Game is running (cache locked)';
		default:
			return 'Game cache not found';
	}
}

export function pityLine(l: PityLine): string {
	const state = l.next_state === 'guaranteed' ? ' · Guaranteed'
		: l.next_state === '50/50' || l.next_state === '75/25' ? ` · ${l.next_state}` : '';
	const fate = l.fate_points === null ? '' : ` · Fate ${l.fate_points}/1`;
	return `${POOL_SHORT[l.pool]} ${l.pity5}/${l.hard}${state}${fate}`;
}

export function scaleTo(values: number[], size: number): number[] {
	const max = Math.max(0, ...values);
	return values.map((v) => (max ? Math.round((v / max) * size * 10) / 10 : 0));
}

export function niceMax(n: number): number {
	if (n <= 0) return 0;
	const p = 10 ** Math.floor(Math.log10(n));
	for (const m of [1, 2, 5, 10]) if (m * p >= n) return m * p;
	return 10 * p;
}

export type Bar = { label: string; segments: { name: string; value: number; color: string }[] };

export function stackedMonths(rows: MonthRow[]): Bar[] {
	return rows.map((r) => ({
		label: `${r.month.slice(5, 7)}/${r.month.slice(2, 4)}`,
		segments: POOLS.map((p) => ({ name: POOL_LABEL[p], value: r[p], color: POOL_COLOR[p] }))
	}));
}

export function histogramBars(buckets: { bucket: string; count: number }[]): Bar[] {
	return buckets.map((b) => ({ label: b.bucket, segments: [{ name: '5★', value: b.count, color: 'var(--wanted)' }] }));
}

export const DEFAULT_FILTERS: HistoryFilters = { pool: '', rarity: '', type: '', banner: '', q: '' };
const FILTER_KEY = 'wishes.historyFilters';

export function historyQuery(f: HistoryFilters, page: number): string {
	const params = new URLSearchParams();
	if (f.pool) params.set('pool', f.pool);
	if (f.rarity !== '') params.set('rarity', String(f.rarity));
	if (f.type) params.set('type', f.type);
	if (f.banner) params.set('banner', f.banner);
	if (f.q.trim()) params.set('q', f.q.trim());
	params.set('page', String(page));
	return params.toString();
}

export function loadFilters(storage: () => Storage): HistoryFilters {
	try {
		const raw = storage().getItem(FILTER_KEY);
		return raw ? { ...DEFAULT_FILTERS, ...JSON.parse(raw) } : { ...DEFAULT_FILTERS };
	} catch {
		return { ...DEFAULT_FILTERS };
	}
}

export function saveFilters(storage: () => Storage, f: HistoryFilters): void {
	try {
		storage().setItem(FILTER_KEY, JSON.stringify(f));
	} catch {
		/* storage unavailable: filters just aren't remembered */
	}
}
```

- [ ] **Step 6: Nav, Dashboard card, Settings**

`frontend/src/routes/+layout.svelte`: change `{ label: 'Wishes', phase: 3 },` to `{ label: 'Wishes', href: '/wishes' },`.

`frontend/src/routes/+page.svelte`: add `import { pityLine } from '$lib/wishes';` and, right after the closing `</div>` of `<div class="tiles">`, add:

```svelte
	<section class="panel" data-testid="pity-card">
		<h2>Pity</h2>
		{#if data.pity.length === 0}
			<p class="muted"><a href="/wishes">Import your wish history</a></p>
		{:else}
			<ul class="pity-lines">
				{#each data.pity as line (line.pool)}
					<li><a href="/wishes">{pityLine(line)}</a></li>
				{/each}
			</ul>
		{/if}
	</section>
```

and in its `<style>`: `.pity-lines { list-style: none; padding: 0; margin: 0; display: flex; flex-wrap: wrap; gap: 6px 18px; }`.

`frontend/src/routes/settings/+page.svelte`:

Script additions:

```ts
	import { cacheStatusLabel } from '$lib/wishes';
	import type { CacheStatus } from '$lib/types';

	let gamePath = $state('');
	let gamePathNote = $state<string | null>(null);
	let cache = $state<CacheStatus | null>(null);

	async function loadCache() {
		try {
			cache = await api.cacheStatus();
		} catch {
			cache = null;
		}
	}

	async function saveGamePath() {
		try {
			settings = await api.saveSettings({ game_install_path: gamePath });
			gamePathNote = 'Saved.';
			await loadCache();
		} catch (e) {
			gamePathNote = errorMessage(e);
		}
	}
```

In `load()`, after `interval = s.sync_interval_minutes;` add `gamePath = s.game_install_path;` and after the `try/catch` add `void loadCache();`.

Markup: add before the **Game data** section:

```svelte
	<section class="panel">
		<h2>Wishes</h2>
		<label>
			Game install path (leave blank to detect it automatically)
			<input type="text" bind:value={gamePath} placeholder="D:\Games\Genshin Impact" />
		</label>
		<button type="button" onclick={saveGamePath}>Save</button>
		{#if gamePathNote}<span class="muted">{gamePathNote}</span>{/if}
		<p class="muted" data-testid="wish-cache">{cache ? cacheStatusLabel(cache, now) : 'Checking the game cache…'}</p>
	</section>
```

Inside the **Game data** section, before the button, add:

```svelte
		<p>
			{settings.gamedata.banners.count} banners ·
			{settings.gamedata.banners.fetched_at ? `updated ${timeAgo(settings.gamedata.banners.fetched_at, now)}` : 'never downloaded'}
		</p>
		{#if settings.gamedata.banners.last_error}<p class="error">Banners: {settings.gamedata.banners.last_error}</p>{/if}
		{#if settings.gamedata.banners.unmapped.length}
			<p class="muted">Banner items not matched to game data: {settings.gamedata.banners.unmapped.join(', ')}</p>
		{/if}
```

- [ ] **Step 7: Check and test**

Run: `cd frontend; npm run check; npm test`
Expected: `svelte-check` 0 errors; all Vitest suites pass.

- [ ] **Step 8: Commit**

```powershell
git add frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/lib/wishes.ts frontend/src/lib/wishes.test.ts frontend/src/routes/+layout.svelte frontend/src/routes/+page.svelte frontend/src/routes/settings/+page.svelte
git commit -m "feat(wishes): frontend types, API client, wish helpers, pity card and game path setting"
```

---

### Task 16: Wishes page — header, imports, pity panels, chart picker

**Files:**
- Create: `frontend/src/lib/PityPanel.svelte`, `frontend/src/routes/wishes/+page.svelte`

**Interfaces:**
- Consumes: `api.*` wish calls, `POOL_LABEL`, `pityBar`, `nextStateLabel`, `fateLine`, `radianceLine`, `importResultLine` (Task 15).
- Produces: `PityPanel` props `{ pool: PoolSummary; onChart: (itemId: number | null) => void }` (root `data-testid="pity-<pool>"`, fate text `data-testid="fate"`, select labelled "Charted weapon" / "Charted item"); page state `data`, `tab`, `version` used by Task 17.

- [ ] **Step 1: `PityPanel.svelte`**

```svelte
<!-- frontend/src/lib/PityPanel.svelte -->
<script lang="ts">
	import type { PoolSummary } from './types';
	import { POOL_LABEL, fateLine, nextStateLabel, pityBar, radianceLine } from './wishes';

	let { pool, onChart }: { pool: PoolSummary; onChart: (itemId: number | null) => void } = $props();
	const bar = $derived(pityBar(pool.pity5, pool.hard, pool.soft));

	function change(e: Event) {
		const v = (e.currentTarget as HTMLSelectElement).value;
		onChart(v === '' ? null : Number(v));
	}
</script>

<section class="panel pity" data-testid="pity-{pool.pool}">
	<h2>{POOL_LABEL[pool.pool]}</h2>
	<div class="big">{pool.pity5}<span class="muted"> / {pool.hard}</span></div>
	<div class="bar" role="progressbar" aria-label="5★ pity" aria-valuenow={pool.pity5} aria-valuemin={0}
		aria-valuemax={pool.hard}>
		<span class="fill" class:soft={pool.in_soft} style="width: {bar.fill}%"></span>
		{#if bar.soft !== null}<span class="mark" style="left: {bar.soft}%" title="Soft pity from {pool.soft}"></span>{/if}
	</div>
	<div class="muted small">4★ pity {pool.pity4} / 10{pool.in_soft ? ' · in soft pity' : ''}</div>
	{#if pool.next_state}<div class="state">{nextStateLabel(pool.next_state)}</div>{/if}
	{#if pool.radiance}
		<div class="muted small" title="Community estimate: the game does not show this counter.">
			{radianceLine(pool.radiance)}
		</div>
	{/if}
	{#if pool.fate}
		<label class="small">
			{pool.pool === 'weapon' ? 'Charted weapon' : 'Charted item'}
			<select onchange={change} value={pool.fate.chart_item_id ?? ''} disabled={pool.fate.choices.length === 0}>
				<option value="">None</option>
				{#each pool.fate.choices as c (c.item_id)}<option value={c.item_id}>{c.name}</option>{/each}
			</select>
		</label>
		<div class="small" data-testid="fate">{fateLine(pool.fate, pool.pool)}</div>
	{/if}
</section>

<style>
	.pity { min-width: 220px; display: flex; flex-direction: column; gap: 6px; }
	.big { font-size: 28px; font-weight: 700; }
	.big .muted { font-size: 16px; font-weight: 400; }
	.bar { position: relative; height: 8px; background: var(--line); border-radius: 4px; }
	.fill { display: block; height: 100%; border-radius: 4px; background: var(--accent); }
	.fill.soft { background: var(--warn); }
	.mark { position: absolute; top: -3px; width: 2px; height: 14px; background: var(--warn); }
	.state { font-weight: 600; }
	.small { font-size: 12px; }
	label { display: flex; flex-direction: column; gap: 4px; color: var(--muted); }
</style>
```

- [ ] **Step 2: Page skeleton (header, imports, pity panels, empty state)**

```svelte
<!-- frontend/src/routes/wishes/+page.svelte -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import PityPanel from '$lib/PityPanel.svelte';
	import { timeAgo } from '$lib/time';
	import type { ImportStatus, Pool, WishSummary } from '$lib/types';
	import { POOL_LABEL, importResultLine } from '$lib/wishes';

	let data = $state<WishSummary | null>(null);
	let status = $state<ImportStatus | null>(null);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let tab = $state<Pool>('character');
	let version = $state(0);
	let now = $state(Date.now());
	const running = $derived(status?.running ?? false);

	async function load() {
		try {
			data = await api.wishSummary();
			status = data.import;
			if (data.pools.length && !data.pools.some((p) => p.pool === tab)) tab = data.pools[0].pool;
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	onMount(() => {
		load().then(() => {
			if (status?.running) void poll();
		});
		const t = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(t);
	});

	async function poll() {
		for (;;) {
			status = await api.importStatus();
			if (!status.running) break;
			await new Promise((r) => setTimeout(r, 2000));
		}
		await load();
		version++;
	}

	async function importGame() {
		toast = null;
		try {
			await api.importGame();
			status = { running: true, last: status?.last ?? null };
			await poll();
		} catch (e) {
			toast = errorMessage(e);
		}
	}

	async function upload(e: Event) {
		const input = e.currentTarget as HTMLInputElement;
		const file = input.files?.[0];
		input.value = '';
		if (!file) return;
		toast = null;
		status = { running: true, last: status?.last ?? null };
		try {
			status = await api.uploadWishes(file);
		} catch (err) {
			toast = errorMessage(err);
		}
		await load();
		version++;
	}

	async function exportUigf() {
		toast = null;
		try {
			const res = await fetch('/api/wishes/export');
			if (!res.ok) throw new Error((await res.json()).detail ?? res.statusText);
			const name = /filename="([^"]+)"/.exec(res.headers.get('content-disposition') ?? '')?.[1]
				?? 'genshintracker-uigf.json';
			const a = document.createElement('a');
			a.href = URL.createObjectURL(await res.blob());
			a.download = name;
			a.click();
			URL.revokeObjectURL(a.href);
		} catch (e) {
			toast = errorMessage(e);
		}
	}

	async function setChart(pool: Pool, itemId: number | null) {
		if (!data) return;
		const before = data;
		data = {
			...data,
			pools: data.pools.map((p) => (p.pool === pool && p.fate ? { ...p, fate: { ...p.fate, chart_item_id: itemId } } : p))
		};
		try {
			const updated = await api.setChart(pool, itemId);
			data = { ...data, pools: data.pools.map((p) => (p.pool === pool ? updated : p)) };
		} catch (e) {
			data = before;
			toast = errorMessage(e);
		}
	}
</script>

<h1>Wishes</h1>
{#if error}<p class="error">{error}</p>{/if}
{#if toast}<p class="error" role="alert">{toast}</p>{/if}

<section class="panel header">
	<button type="button" class="primary" onclick={importGame} disabled={running}>
		{running ? 'Importing…' : 'Import from game'}
	</button>
	<label class="upload">
		<span>Upload file</span>
		<input type="file" accept=".json,.xlsx" onchange={upload} disabled={running} />
	</label>
	<button type="button" onclick={exportUigf} disabled={running}>Export UIGF</button>
	<span class="muted" data-testid="import-result">
		{#if running}<span class="spinner" aria-hidden="true"></span> Importing…
		{:else if status?.last}
			{importResultLine(status.last)}{status.last.finished_at ? ` · ${timeAgo(status.last.finished_at, now)}` : ''}
		{:else}No imports yet{/if}
	</span>
</section>

{#if data}
	{#if !data.banners_available && data.pools.length}
		<p class="muted">Banner data isn't downloaded yet, so 50/50 results show as Unknown until game data refreshes.</p>
	{/if}
	{#if data.pools.length === 0}
		<section class="panel empty">
			<h2>No wishes yet</h2>
			<ol>
				<li><strong>From the game:</strong> open Wish History in-game once (any banner), then press <em>Import from game</em>. Close the game first if the import says the cache is locked.</li>
				<li><strong>From paimon.moe:</strong> Settings → Export to Excel, then <em>Upload file</em> with the .xlsx.</li>
				<li><strong>From another tracker:</strong> export UIGF JSON, then <em>Upload file</em>.</li>
			</ol>
		</section>
	{:else}
		<div class="panels">
			{#each data.pools as pool (pool.pool)}
				<PityPanel {pool} onChart={(id) => setChart(pool.pool, id)} />
			{/each}
		</div>
		<!-- Task 17: tabs, charts, history -->
	{/if}
{/if}

<style>
	.header { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
	.upload { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
	.upload input { max-width: 220px; }
	.panels { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; margin: 12px 0; }
	.empty ol { margin: 0; padding-left: 20px; display: grid; gap: 6px; }
	.spinner { display: inline-block; width: 10px; height: 10px; border: 2px solid var(--muted);
		border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; }
	@keyframes spin { to { transform: rotate(360deg); } }
	section.panel { margin-top: 12px; }
</style>
```

- [ ] **Step 3: Check, then look at it**

Run: `cd frontend; npm run check`
Expected: 0 errors.

Seed and run locally (offline, fake data), then open `http://127.0.0.1:8765/wishes` and confirm: three pity panels (Character 2/90 with "Next 5★: 50/50", Weapon 12/80 with the chart picker, Standard 15/90); choosing Mistsplitter Reforged shows "Fate point 0/1 · charted Mistsplitter Reforged"; Import from game shows the cache-not-found message (no game on the seeded root).

```powershell
cd backend; ..\.venv\Scripts\python -m app.devseed --root ..\.demo-data
```

```powershell
$env:GT_ROOT = (Resolve-Path ..\.demo-data); $env:GT_OFFLINE = '1'; ..\.venv\Scripts\python ..\run.py
```

Stop the server afterwards and delete `.demo-data`.

- [ ] **Step 4: Commit**

```powershell
git add frontend/src/lib/PityPanel.svelte frontend/src/routes/wishes/+page.svelte
git commit -m "feat(wishes): Wishes page with imports, export, pity panels and chart picker"
```

---

### Task 17: Wishes page — pool tabs, charts, history table

**Files:**
- Create: `frontend/src/lib/BarChart.svelte`, `frontend/src/lib/WishHistory.svelte`
- Modify: `frontend/src/routes/wishes/+page.svelte`

**Interfaces:**
- Consumes: `Bar`, `niceMax`, `scaleTo`, `stackedMonths`, `histogramBars`, `outcomeLabel`, `historyQuery`, `loadFilters`, `saveFilters`, `DEFAULT_FILTERS`, `POOLS`, `POOL_LABEL`, `POOL_COLOR` (Task 15); page state from Task 16.
- Produces: `BarChart` props `{ bars: Bar[]; title: string; height?: number }`; `WishHistory` props `{ banners: BannerRow[]; version: number }` (rows `data-testid="history-row"`, rarity select labelled "Rarity"); tabs with `role="tab"` named by `POOL_LABEL`; tab panel `data-testid="tab-<pool>"`.

- [ ] **Step 1: `BarChart.svelte`**

```svelte
<!-- frontend/src/lib/BarChart.svelte -->
<script lang="ts">
	import { niceMax, type Bar } from './wishes';

	let { bars, title, height = 140 }: { bars: Bar[]; title: string; height?: number } = $props();
	const W = 26;
	const GAP = 6;
	const LABEL = 18;
	const total = (b: Bar) => b.segments.reduce((a, s) => a + s.value, 0);
	const max = $derived(niceMax(Math.max(0, ...bars.map(total))));
	const width = $derived(Math.max(bars.length * (W + GAP), W));
	const summary = $derived(bars.map((b) => `${b.label}: ${total(b)}`).join(', '));
	const h = (v: number) => (max ? (v / max) * height : 0);
</script>

<figure>
	<figcaption>{title}</figcaption>
	{#if bars.length === 0}
		<p class="muted">No data yet.</p>
	{:else}
		<div class="scroll">
			<svg viewBox="0 0 {width} {height + LABEL}" {width} height={height + LABEL} role="img" aria-label="{title}: {summary}">
				{#each bars as b, i (b.label)}
					{#each b.segments as s, j (s.name)}
						{#if s.value > 0}
							<rect x={i * (W + GAP)} width={W} height={h(s.value)} fill={s.color}
								y={height - h(b.segments.slice(0, j + 1).reduce((a, t) => a + t.value, 0))}>
								<title>{b.label} · {s.name}: {s.value}</title>
							</rect>
						{/if}
					{/each}
					<text x={i * (W + GAP) + W / 2} y={height + 13} text-anchor="middle">{b.label}</text>
				{/each}
			</svg>
		</div>
	{/if}
	<p class="sr-only">{summary}</p>
</figure>

<style>
	figure { margin: 0; }
	figcaption { font-size: 12px; color: var(--muted); margin-bottom: 6px; }
	.scroll { overflow-x: auto; }
	text { font-size: 9px; fill: var(--muted); }
	.sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
</style>
```

- [ ] **Step 2: `WishHistory.svelte`**

```svelte
<!-- frontend/src/lib/WishHistory.svelte -->
<script lang="ts">
	import { api, errorMessage } from './api';
	import { imgSrc } from './img';
	import type { BannerRow, HistoryFilters, HistoryPage } from './types';
	import { POOLS, POOL_LABEL, loadFilters, saveFilters } from './wishes';

	let { banners, version }: { banners: BannerRow[]; version: number } = $props();
	let filters = $state<HistoryFilters>(loadFilters(() => localStorage));
	let page = $state(1);
	let data = $state<HistoryPage | null>(null);
	let error = $state<string | null>(null);
	const pages = $derived(data ? Math.max(1, Math.ceil(data.total / data.page_size)) : 1);

	$effect(() => {
		void version;
		const f = { ...filters };
		const p = page;
		saveFilters(() => localStorage, f);
		api.wishHistory(f, p)
			.then((d) => { data = d; error = null; })
			.catch((e) => (error = errorMessage(e)));
	});

	function set<K extends keyof HistoryFilters>(key: K, value: HistoryFilters[K]) {
		filters = { ...filters, [key]: value };
		page = 1;
	}
</script>

<section class="panel">
	<h2>History</h2>
	<div class="filters">
		<select aria-label="Banner type" value={filters.pool}
			onchange={(e) => set('pool', e.currentTarget.value as HistoryFilters['pool'])}>
			<option value="">All banner types</option>
			{#each POOLS as p (p)}<option value={p}>{POOL_LABEL[p]}</option>{/each}
		</select>
		<select aria-label="Rarity" value={String(filters.rarity)}
			onchange={(e) => set('rarity', e.currentTarget.value === '' ? '' : Number(e.currentTarget.value))}>
			<option value="">All rarities</option>
			<option value="5">5★</option>
			<option value="4">4★</option>
			<option value="3">3★</option>
		</select>
		<select aria-label="Item type" value={filters.type}
			onchange={(e) => set('type', e.currentTarget.value as HistoryFilters['type'])}>
			<option value="">Characters and weapons</option>
			<option value="character">Characters</option>
			<option value="weapon">Weapons</option>
		</select>
		<select aria-label="Banner" value={filters.banner} onchange={(e) => set('banner', e.currentTarget.value)}>
			<option value="">All banners</option>
			{#each banners as b (b.key)}<option value={b.key}>{b.short_name} ({b.start.slice(0, 10)})</option>{/each}
		</select>
		<input type="search" placeholder="Search name" aria-label="Search name" value={filters.q}
			oninput={(e) => set('q', e.currentTarget.value)} />
	</div>
	{#if error}<p class="error">{error}</p>{/if}
	{#if data}
		<table>
			<thead><tr><th>Time</th><th>Item</th><th>★</th><th>Banner type</th><th>Banner</th><th>Pity</th></tr></thead>
			<tbody>
				{#each data.rows as r, i (`${r.time}-${r.name}-${i}`)}
					<tr data-testid="history-row" class="r{r.rarity}">
						<td>{r.time}</td>
						<td class="item">{#if imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt="" />{/if}{r.name}</td>
						<td>{r.rarity}★</td>
						<td>{POOL_LABEL[r.pool]}</td>
						<td>{r.banner ?? '—'}</td>
						<td>{r.pity ?? ''}</td>
					</tr>
				{/each}
			</tbody>
		</table>
		{#if data.total === 0}<p class="muted">No pulls match these filters.</p>{/if}
		<div class="paging">
			<button type="button" onclick={() => (page = page - 1)} disabled={page <= 1}>Previous</button>
			<span class="muted">Page {page} of {pages} · {data.total} pulls</span>
			<button type="button" onclick={() => (page = page + 1)} disabled={page >= pages}>Next</button>
		</div>
	{/if}
</section>

<style>
	.filters { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 10px; }
	table { width: 100%; border-collapse: collapse; font-size: 13px; }
	th, td { text-align: left; padding: 4px 10px 4px 0; border-bottom: 1px solid var(--line); }
	.item { display: flex; align-items: center; gap: 6px; }
	.item img { width: 24px; height: 24px; border-radius: 4px; background: var(--r0); }
	tr.r5 td { color: #e8c15a; }
	tr.r4 td { color: #b69be0; }
	.paging { display: flex; gap: 10px; align-items: center; margin-top: 10px; }
</style>
```

- [ ] **Step 3: Tabs, lists, charts in the page**

In `frontend/src/routes/wishes/+page.svelte`, add imports:

```ts
	import BarChart from '$lib/BarChart.svelte';
	import WishHistory from '$lib/WishHistory.svelte';
	import { imgSrc } from '$lib/img';
	import { POOL_COLOR, histogramBars, outcomeLabel, scaleTo, stackedMonths } from '$lib/wishes';
```

and the derived values:

```ts
	const current = $derived(data?.pools.find((p) => p.pool === tab) ?? null);
	const bannerWidths = $derived(data ? scaleTo(data.charts.banners.map((b) => b.pulls), 100) : []);
	const pct = (n: number | null) => (n === null ? '—' : `${Math.round(n * 100)}%`);
```

Replace `<!-- Task 17: tabs, charts, history -->` with:

```svelte
		<div class="tabs" role="tablist" aria-label="Banner type">
			{#each data.pools as p (p.pool)}
				<button type="button" role="tab" aria-selected={tab === p.pool} class:active={tab === p.pool}
					onclick={() => (tab = p.pool)}>{POOL_LABEL[p.pool]}</button>
			{/each}
		</div>
		{#if current}
			<section class="panel" role="tabpanel" data-testid="tab-{current.pool}">
				<div class="stats">
					<div><span class="muted">Pulls</span><strong>{current.stats.pulls}</strong></div>
					<div><span class="muted">Primogems</span><strong>{current.stats.primogems.toLocaleString()}</strong></div>
					<div><span class="muted">5★</span><strong>{current.stats.five}</strong></div>
					<div><span class="muted">Average 5★ pity</span><strong>{current.stats.avg_five_pity ?? '—'}</strong></div>
					{#if current.pool === 'character' || current.pool === 'weapon'}
						<div><span class="muted">{current.pool === 'weapon' ? '75/25' : '50/50'} win rate</span>
							<strong>{pct(current.stats.win_rate)}</strong></div>
					{/if}
				</div>
				<h2>5★</h2>
				{#if current.fives.length === 0}<p class="muted">No 5★ yet.</p>{/if}
				<ul class="pulls">
					{#each current.fives as p, i (`${p.time}-${i}`)}
						<li class="r5">
							{#if imgSrc(p.icon)}<img src={imgSrc(p.icon)} alt="" />{/if}
							<span class="name">{p.name}</span>
							<span class="pity">{p.pity}</span>
							{#if p.outcome}<span class="badge {p.outcome}">{outcomeLabel(p.outcome)}</span>{/if}
							<span class="muted">{p.banner ?? ''} · {p.time.slice(0, 10)}</span>
						</li>
					{/each}
				</ul>
				<h2>4★</h2>
				{#if current.fours.length === 0}<p class="muted">No 4★ yet.</p>{/if}
				<ul class="pulls compact">
					{#each current.fours as p, i (`${p.time}-${i}`)}
						<li><span class="name">{p.name}</span><span class="pity">{p.pity}</span>
							<span class="muted">{p.time.slice(0, 10)}</span></li>
					{/each}
				</ul>
			</section>
		{/if}

		<section class="panel charts">
			<BarChart title="Pulls per month" bars={stackedMonths(data.charts.monthly)} />
			<BarChart title="5★ pity" bars={histogramBars(data.charts.pity_histogram)} />
		</section>

		<section class="panel">
			<h2>Banners</h2>
			{#if data.charts.banners.length === 0}<p class="muted">No pulls are matched to banners yet.</p>{/if}
			<ul class="timeline">
				{#each data.charts.banners as b, i (b.key)}
					<li>
						<span class="bname">{b.short_name} <span class="muted">{b.start.slice(0, 10)}</span></span>
						<span class="track"><span style="width: {bannerWidths[i]}%; background: {POOL_COLOR[b.pool]}"></span></span>
						<span>{b.pulls}</span>
						<span class="muted">{b.fives.join(', ')}</span>
					</li>
				{/each}
			</ul>
		</section>

		<WishHistory banners={data.charts.banners} {version} />
```

Add to the page `<style>`:

```css
	.tabs { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 12px; }
	.tabs button.active { border-color: var(--accent); color: var(--accent); }
	.stats { display: flex; flex-wrap: wrap; gap: 24px; margin-bottom: 10px; }
	.stats div { display: flex; flex-direction: column; }
	.stats strong { font-size: 20px; }
	.pulls { list-style: none; padding: 0; margin: 0 0 12px; display: grid; gap: 6px; }
	.pulls li { display: flex; align-items: center; gap: 10px; }
	.pulls img { width: 32px; height: 32px; border-radius: 6px; background: var(--r5); }
	.pulls .name { min-width: 180px; font-weight: 600; }
	.pulls .pity { min-width: 28px; text-align: right; font-variant-numeric: tabular-nums; }
	.pulls.compact { grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
	.pulls.compact .name { min-width: 150px; font-weight: 400; }
	.badge { font-size: 11px; padding: 1px 6px; border-radius: 8px; background: var(--panel-2); border: 1px solid var(--line); }
	.badge.won, .badge.charted { color: var(--building); border-color: var(--building); }
	.badge.lost, .badge.not_charted { color: var(--error); border-color: var(--error); }
	.badge.guaranteed { color: var(--wanted); border-color: var(--wanted); }
	.charts { display: grid; grid-template-columns: repeat(auto-fit, minmax(300px, 1fr)); gap: 16px; }
	.timeline { list-style: none; padding: 0; margin: 0; display: grid; gap: 4px; }
	.timeline li { display: grid; grid-template-columns: 220px 1fr 50px 2fr; gap: 10px; align-items: center; font-size: 13px; }
	.track { height: 8px; background: var(--line); border-radius: 4px; overflow: hidden; }
	.track span { display: block; height: 100%; }
```

- [ ] **Step 4: Check, then look at it**

Run: `cd frontend; npm run check; npm test`
Expected: 0 errors; tests pass.

With the seeded demo server from Task 16 Step 3: the Character tab lists Furina (Guaranteed) and Neuvillette (Lost); the Standard tab shows 60 pulls; the monthly chart and histogram render; the banner list shows Furina and Mistsplitter; the history table pages 50 rows and the Rarity filter `5★` shows 3 rows.

- [ ] **Step 5: Commit**

```powershell
git add frontend/src/lib/BarChart.svelte frontend/src/lib/WishHistory.svelte frontend/src/routes/wishes/+page.svelte
git commit -m "feat(wishes): pool tabs with 5★/4★ lists, SVG charts and filterable history"
```

---

### Task 18: End-to-end test, README, live verification, final checks

**Files:**
- Create: `frontend/e2e/wishes.spec.ts`
- Modify: `README.md`, `docs/superpowers/notes/2026-11-20-phase3-wish-findings.md`

- [ ] **Step 1: Playwright test**

```ts
// frontend/e2e/wishes.spec.ts
import { expect, test } from '@playwright/test';

test('wishes page shows pity and tracks a weapon chart', async ({ page }) => {
	await page.goto('/wishes');
	const character = page.getByTestId('pity-character');
	await expect(character).toContainText('2 / 90');
	await expect(character).toContainText('Next 5★: 50/50');
	await page.getByRole('tab', { name: 'Weapon Event' }).click();
	await expect(page.getByTestId('tab-weapon')).toContainText('Pulls');
	const weapon = page.getByTestId('pity-weapon');
	await weapon.getByLabel('Charted weapon').selectOption({ label: 'Mistsplitter Reforged' });
	await expect(weapon.getByTestId('fate')).toContainText('Fate point 0/1');
	await page.reload();
	await expect(page.getByTestId('pity-weapon').getByTestId('fate')).toContainText('charted Mistsplitter Reforged');
});

test('history rarity filter shows only 5★ rows', async ({ page }) => {
	await page.goto('/wishes');
	await expect(page.getByTestId('history-row').first()).toBeVisible();
	await page.getByLabel('Rarity').selectOption('5');
	await expect(page.getByTestId('history-row')).toHaveCount(3);
	for (const row of await page.getByTestId('history-row').all()) await expect(row).toContainText('5★');
});

test('dashboard shows the pity card', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('pity-card')).toContainText('Character 2/90 · 50/50');
});
```

Run: `cd frontend; npm run build; npm run e2e`
Expected: all Playwright tests pass (existing characters/planner specs included).

- [ ] **Step 2: README**

Add a **Wishes** section to `README.md` after the planner section:

```markdown
## Wishes

- **Import from game:** open Wish History in-game once (any banner), then press **Import from game** on the Wishes page. The link the game caches is valid for about a day; if the import says it expired, open Wish History again. If it says the cache is locked, close the game and retry. If the game cache isn't found, set the game install path in Settings.
- **Older history:** paimon.moe → Settings → *Export to Excel*, then **Upload file** with the `.xlsx`. UIGF JSON (v3/v4) from other trackers works the same way. Pulls are de-duplicated, so importing overlapping files is safe.
- **Export:** **Export UIGF** downloads your whole history as UIGF v4 JSON.
- **Backups:** before every import the database is copied to `data/backups/wishes/`, and after every import a UIGF snapshot is written there (10 of each are kept). Sync backups in `data/backups/` are separate.
- **Privacy:** the wish link's authkey is read from the game cache into memory only; it is never stored, logged, or shown.
- **Estimates:** the Capturing Radiance counter is a community estimate. Pity and the 50/50 guarantee are exact once banner data has been downloaded (Settings → Game data). Banner data comes from paimon.moe's open-source banner list (MIT).
```

- [ ] **Step 3: Full automated verification**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Run: `cd frontend; npm run check; npm test; npm run build; npm run e2e`
Expected: everything passes. Fix anything that does not before continuing.

- [ ] **Step 4: Live verification with the user ("Done when")**

With the user, on their real setup (main checkout's `.env`/`data/` copied into the worktree, deleted afterwards):

1. Open Wish History in-game, press **Import from game** → pulls imported; the result line shows the count.
2. Upload the paimon.moe `.xlsx` → overlapping period adds no duplicates (compare total pulls per pool with paimon.moe's counts).
3. Compare each pool's pity with a manual count from the in-game history.
4. **Export UIGF**, upload that file → "No new pulls".
5. Run the import from game again → "No new pulls".

Append the results (counts and yes/no only) to `docs/superpowers/notes/2026-11-20-phase3-wish-findings.md` under "Done-when check".

- [ ] **Step 5: Secret scan before committing**

Run: `git diff main --stat`
Run: `git diff main | Select-String -Pattern 'authkey=[A-Za-z0-9%]{8,}','ltoken','ltuid_v2=\d','GENSHIN_UID=\d'`
Expected: no matches other than the test fixtures' obviously fake values (`SECRET-AUTHKEY…`, `800000001`). No `.env`, `data/`, `.demo-data/`, or `.e2e-data/` files in the diff.

- [ ] **Step 6: Commit**

```powershell
git add frontend/e2e/wishes.spec.ts README.md docs/superpowers/notes/2026-11-20-phase3-wish-findings.md
git commit -m "test(wishes): end-to-end wishes flow; README wishes section; live done-when results"
```

- [ ] **Step 7: Finish the branch**

Use superpowers:finishing-a-development-branch (merge `phase3-wishes` into `main` the way phases 1 and 2 were merged, push after the secret check).
