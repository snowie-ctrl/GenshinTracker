# Ad Astra Sub-project 8 — Artifact Planning Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user set artifact targets (sets, main stats, substat order) per Build character, check them against equipped gear, and show which artifact domains to run (from genshin-db) on the Dashboard.

**Architecture:** Migration 0012 adds `character_goal.artifact_target` (JSON) + `artifacts_done` and a `game_artifact_domain` table. `backend/app/gamedata/genshindb.py` parses genshin-db's domain list and the game-data service refreshes it weekly after the Yatta artifact sets. A pure `backend/app/artifacts/` package parses HoYoLAB main-stat strings and checks a target against equipped gear; `backend/app/dashboard/artifacts.py` groups counted characters by domain. The Build tab's `BuildArtifacts.svelte` becomes the editor; a new `ArtifactDomains.svelte` sits between Weekly bosses and Building on the Dashboard.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest (backend); SvelteKit with Svelte 5 runes, TypeScript, vitest, Playwright (frontend).

**Spec:** `docs/superpowers/specs/2026-11-24-ad-astra-artifact-planning-design.md`

## Global Constraints

- Cookie values only in the git-ignored `.env`; never logged, returned or committed.
- Unofficial API code stays in `backend/app/sync/` and `backend/app/wishes/`; public game-data code (genshin-db, Yatta) stays in `backend/app/gamedata/`.
- The genshin-db request carries no cookie, UID or email. No new image host: set icons load through `/api/img/<name>` (existing allow-list).
- Test fixtures use made-up UID 800000001 and trimmed public game data; no game art or personal data committed; no user name, email, Windows user name or absolute user path in any committed file.
- New migration is `0012` (revises `0011`).
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

**Commands** (`PY` = the project venv python, `.venv/Scripts/python.exe` in the main checkout):
- Backend, from `backend/`: `PY -m pytest -q` (642 passing at start).
- Frontend, from `frontend/` (run `npm ci` first in a new worktree): `npm run check`, `npx vitest run` (174 at start), `npm run build`, `PYTHON=PY npx playwright test` (62 at start; workers 1, one shared seeded server: any test that changes state restores it).

## Plan-time spec amendments (made in the same commit as this plan)

1. **API field placement.** The artifact target is sent and returned as a top-level `artifact_target` (and `artifacts_done`) on `PUT /goal` and the character payload, not as `targets.artifacts`. Reason: `TargetsIn` requires every level field and feeds the material planner's `Targets` dataclass; keeping artifacts separate leaves the planner untouched.
2. **Single 2-piece allowed.** `sets` may hold one 2-piece entry (the "2 + 2" mode with the second set not chosen yet). Still rejected: more than two entries, two entries that are not both 2-piece, two entries with the same id.
3. **Spec §6.4 was wrong.** `DomainDays.svelte` does have an empty `.image` div. It is removed (as agreed with the user in brainstorming: the spike found no source).
4. **Dev seed.** Bennett's target is *met by the tick* (`artifacts_done = true`) rather than by gear, so existing Teams/Profile seed gear stays unchanged; the pytest suite covers `met` by gear.

## Review Focus

1. **genshin-db returns something that is not the expected list** (HTML error page, `{}` object, an entry without `rewardPreview`): refresh must store an error / skip the entry and keep stored domains, never crash startup — pinned in Task 2 (`test_parse_rejects_non_list`, malformed entry in the fixture, `test_refresh_domains_failure_keeps_rows`).
2. **Domains refreshed before any artifact set exists** (fresh install, Yatta reliquary failed): no domains stored, no error loop, retried next time — pinned in Task 2 (`test_refresh_domains_waits_for_sets`).
3. **Main-stat strings HoYoLAB words differently** (`"HP%"`, `"ER"`, unknown text): parser maps aliases, unknown → `None` → slot shows ✗ with raw text — pinned in Task 3 (`test_main_key_aliases`, `test_check_unparseable_main`).
4. **Traveler element that is not the synced one**: check must use the synced element's gear, not report "No artifacts equipped" — pinned in Task 4 (`test_traveler_element_uses_synced_gear`).
5. **Rapid edits on the Build card** (toggle mode, pick set, add substat in quick succession): later saves must build on the latest draft, not the stale loaded target — pinned in Task 8 by the draft pattern and in Task 10 e2e (pick set then mains without waiting for reload).

---

## File Structure

**Backend**
- Create `backend/migrations/versions/0012_artifact_planning.py` — columns + table.
- Modify `backend/app/db/models.py` — `CharacterGoal.artifact_target`, `CharacterGoal.artifacts_done`, new `GameArtifactDomain`.
- Create `backend/app/gamedata/genshindb.py` — fetch + pure parse of artifact domains.
- Modify `backend/app/gamedata/service.py` — `refresh_artifact_domains`, `refresh_all`, `gamedata_status`.
- Create `backend/app/artifacts/__init__.py`, `stats.py` (stat keys, slot options, `main_key`), `check.py` (pure `check`), `gear.py` (DB lookups: equipped gear, set names, `check_for`).
- Modify `backend/app/schemas.py` — `ArtifactTargetIn`.
- Modify `backend/app/planner/order.py` — leaving Build clears `artifacts_done`.
- Modify `backend/app/api/characters.py` — `GoalIn` fields, payload fields, `artifact_check`.
- Create `backend/app/api/artifacts.py` — `GET /api/artifact-sets`; register in `backend/app/api/__init__.py`.
- Create `backend/app/dashboard/artifacts.py` — pure grouping; modify `backend/app/api/dashboard.py`.
- Modify `backend/app/devseed.py`.
- Tests: `tests/test_migration_0012.py`, `tests/test_genshindb.py`, `tests/fixtures/genshindb_domains.json`, `tests/test_artifact_check.py`, `tests/test_api_artifacts.py`, `tests/test_dashboard_artifacts.py`; modify `tests/helpers.py`, `tests/test_gamedata.py`, `tests/test_devseed.py`, `tests/test_planner_order.py`.

**Frontend**
- Modify `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/characterPage.svelte.ts`.
- Create `frontend/src/lib/artifacts.ts` + `artifacts.test.ts`.
- Rewrite `frontend/src/lib/BuildArtifacts.svelte`; create `ArtifactSetPicker.svelte`, `StatPills.svelte`, `SubstatOrder.svelte` in `frontend/src/lib/`.
- Create `frontend/src/lib/dashboard/ArtifactDomains.svelte`; modify `frontend/src/routes/+page.svelte`, `frontend/src/lib/dashboard/DomainDays.svelte`.
- Modify `frontend/src/routes/settings/+page.svelte` (status line).
- Create `frontend/e2e/artifacts.spec.ts`; modify `frontend/e2e/characters.spec.ts`.

---

### Task 1: Migration 0012 and models

**Files:**
- Create: `backend/migrations/versions/0012_artifact_planning.py`
- Modify: `backend/app/db/models.py` (class `CharacterGoal` ~line 200; add `GameArtifactDomain` after `GameArtifactSet` ~line 81)
- Test: `backend/tests/test_migration_0012.py`

**Interfaces:**
- Produces: `CharacterGoal.artifact_target: dict | None`, `CharacterGoal.artifacts_done: bool` (ORM default `False`); `GameArtifactDomain(id, name, entrance, region, elements, set_ids)`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_migration_0012.py
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
```

- [ ] **Step 2: Run test to verify it fails**

Run (from `backend/`): `PY -m pytest tests/test_migration_0012.py -q`
Expected: FAIL (`Can't locate revision identified by '0012'`).

- [ ] **Step 3: Write the migration and models**

```python
# backend/migrations/versions/0012_artifact_planning.py
"""Ad Astra sub-project 8: artifact targets and artifact domains

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("character_goal") as b:
        b.add_column(sa.Column("artifact_target", sa.JSON(), nullable=True))
        b.add_column(sa.Column("artifacts_done", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_table(
        "game_artifact_domain",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("entrance", sa.String(), nullable=False),
        sa.Column("region", sa.String(), nullable=True),
        sa.Column("elements", sa.JSON(), nullable=False),
        sa.Column("set_ids", sa.JSON(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("game_artifact_domain")
    with op.batch_alter_table("character_goal") as b:
        b.drop_column("artifacts_done")
        b.drop_column("artifact_target")
```

In `backend/app/db/models.py`, add to `CharacterGoal` after `priority`:

```python
    artifact_target: Mapped[dict | None] = mapped_column(JSON, nullable=True)        # sub-project 8
    artifacts_done: Mapped[bool] = mapped_column(Boolean, default=False)             # sub-project 8
```

and after `GameArtifactSet`:

```python
class GameArtifactDomain(Base):
    """An artifact domain from genshin-db and the two 5★ sets it drops (sub-project 8)."""
    __tablename__ = "game_artifact_domain"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String)
    entrance: Mapped[str] = mapped_column(String)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    elements: Mapped[list] = mapped_column(JSON)
    set_ids: Mapped[list] = mapped_column(JSON)
```

(`0010_character_detail.py` uses the same `batch_alter_table` style.)

- [ ] **Step 4: Run tests**

Run: `PY -m pytest tests/test_migration_0012.py tests/test_db.py -q`
Expected: PASS. Then `PY -m pytest -q` — all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/migrations/versions/0012_artifact_planning.py backend/app/db/models.py backend/tests/test_migration_0012.py
git commit -m "feat(db): migration 0012 - artifact targets and artifact domains"
```

---

### Task 2: genshin-db artifact domains and the weekly refresh

**Files:**
- Create: `backend/app/gamedata/genshindb.py`, `backend/tests/fixtures/genshindb_domains.json`, `backend/tests/test_genshindb.py`
- Modify: `backend/app/gamedata/service.py` (after `refresh_artifact_sets` ~line 199; `refresh_all` ~line 246; `gamedata_status` ~line 275), `backend/tests/helpers.py` (`yatta_transport`), `backend/tests/test_gamedata.py` (status dict ~line 44), `frontend/src/lib/types.ts` (gamedata status ~line 162), `frontend/src/routes/settings/+page.svelte` (~line 305)

**Interfaces:**
- Consumes: `GameArtifactDomain`, `GameArtifactSet` (Task 1).
- Produces: `parse_artifact_domains(payload, set_ids_by_name: dict[str, int]) -> tuple[list[ArtifactDomainData], list[str]]`; `refresh_artifact_domains(session_factory, http, now=None, force=False) -> bool`; `gamedata_status(s)["artifact_domains"] == {fetched_at, last_error, count, unmatched}`.

- [ ] **Step 1: Write the fixture**

`backend/tests/fixtures/genshindb_domains.json` (trimmed public genshin-db data; tier ids are illustrative):

```json
[
  {"id": 5101, "name": "Domain of Blessing: Stone Chamber I", "regionName": "Liyue", "entranceName": "Clear Pool and Mountain Cavern",
   "domainType": "UI_ABYSSUS_RELIC", "recommendedLevel": 30, "recommendedElements": ["Cryo"],
   "rewardPreview": [{"id": 202, "name": "Mora", "count": 1000}, {"id": 400020, "name": "Noblesse Oblige", "rarity": 4}]},
  {"id": 5103, "name": "Domain of Blessing: Stone Chamber III", "regionName": "Liyue", "entranceName": "Clear Pool and Mountain Cavern",
   "domainType": "UI_ABYSSUS_RELIC", "recommendedLevel": 81, "recommendedElements": ["Hydro", "Pyro"],
   "rewardPreview": [{"id": 202, "name": "Mora", "count": 2525}, {"id": 400030, "name": "Bloodstained Chivalry", "rarity": 5},
                     {"id": 400031, "name": "Noblesse Oblige", "rarity": 5}, {"id": 400032, "name": "Noblesse Oblige", "rarity": 5}]},
  {"id": 5102, "name": "Domain of Blessing: Stone Chamber II", "regionName": "Liyue", "entranceName": "Clear Pool and Mountain Cavern",
   "domainType": "UI_ABYSSUS_RELIC", "recommendedLevel": 59, "recommendedElements": ["Hydro"],
   "rewardPreview": [{"id": 400025, "name": "Noblesse Oblige", "rarity": 4}]},
  {"id": 5006, "name": "Domain of Blessing: Fires of Purification VI", "regionName": "Mondstadt", "entranceName": "Midsummer Courtyard",
   "domainType": "UI_ABYSSUS_RELIC", "recommendedLevel": 90, "recommendedElements": ["Pyro"],
   "rewardPreview": [{"id": 400108, "name": "Thundering Fury", "rarity": 5}, {"id": 400073, "name": "Thundersoother", "rarity": 5}]},
  {"id": 5201, "name": "Domain of Blessing: Broken Tier I", "domainType": "UI_ABYSSUS_RELIC", "recommendedLevel": 20},
  {"id": 4213, "name": "Domain of Mastery: Forsaken Rift I", "regionName": "Mondstadt", "entranceName": "Forsaken Rift",
   "domainType": "UI_ABYSSUS_AVATAR_PROUD", "recommendedLevel": 20, "recommendedElements": [],
   "rewardPreview": [{"id": 104301, "name": "Teachings of Freedom", "rarity": 2}]}
]
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_genshindb.py
from datetime import datetime, timedelta

import httpx
import pytest

from app.db.models import GameArtifactDomain, GameArtifactSet
from app.gamedata.genshindb import base_name, parse_artifact_domains
from app.gamedata.service import gamedata_status, refresh_all, refresh_artifact_domains, refresh_artifact_sets
from helpers import load_fixture, yatta_transport

NOW = datetime(2026, 11, 24, 12, 0)
BY_NAME = {"Gladiator's Finale": 15001, "Noblesse Oblige": 15007, "Bloodstained Chivalry": 15008}


def test_base_name_strips_tier():
    assert base_name("Domain of Blessing: Stone Chamber III") == "Domain of Blessing: Stone Chamber"
    assert base_name("Domain of Blessing: Dance of Steel V") == "Domain of Blessing: Dance of Steel"


def test_parse_groups_tiers_and_maps_top_tier_sets():
    domains, unmatched = parse_artifact_domains(load_fixture("genshindb_domains.json"), BY_NAME)
    assert [d.name for d in domains] == ["Domain of Blessing: Stone Chamber"]
    d = domains[0]
    assert d.id == 5101                                    # lowest tier id
    assert d.entrance == "Clear Pool and Mountain Cavern" and d.region == "Liyue"
    assert d.elements == ["Hydro", "Pyro"]                 # from the highest tier
    assert d.set_ids == [15008, 15007]                     # 5★ names, de-duplicated, in reward order
    assert unmatched == ["Thundering Fury", "Thundersoother"]   # Fires of Purification dropped


def test_parse_keeps_domain_with_one_matched_set():
    domains, unmatched = parse_artifact_domains(load_fixture("genshindb_domains.json"),
                                                {"Noblesse Oblige": 15007})
    assert domains[0].set_ids == [15007]
    assert "Bloodstained Chivalry" in unmatched


def test_parse_rejects_non_list():
    with pytest.raises(ValueError):
        parse_artifact_domains({"error": "nope"}, BY_NAME)


async def test_refresh_domains_stores_rows_and_status(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_artifact_sets(session_factory, http, now=NOW)
        assert await refresh_artifact_domains(session_factory, http, now=NOW) is True
        assert await refresh_artifact_domains(session_factory, http, now=NOW + timedelta(days=1)) is False
    with session_factory() as s:
        row = s.get(GameArtifactDomain, 5101)
        assert row.set_ids == [15007] and row.entrance == "Clear Pool and Mountain Cavern"
        status = gamedata_status(s)["artifact_domains"]
        assert status["count"] == 1 and status["last_error"] is None
        assert status["unmatched"] == ["Bloodstained Chivalry", "Thundering Fury", "Thundersoother"]


async def test_refresh_domains_waits_for_sets(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh_artifact_domains(session_factory, http, now=NOW) is False
    with session_factory() as s:
        assert gamedata_status(s)["artifact_domains"] == {
            "fetched_at": None, "last_error": None, "count": 0, "unmatched": []}


async def test_refresh_domains_failure_keeps_rows(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_artifact_sets(session_factory, http, now=NOW)
        await refresh_artifact_domains(session_factory, http, now=NOW)
    def broken(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>oops</html>")
    async with httpx.AsyncClient(transport=httpx.MockTransport(broken)) as http:
        assert await refresh_artifact_domains(session_factory, http, now=NOW, force=True) is False
    with session_factory() as s:
        status = gamedata_status(s)["artifact_domains"]
        assert status["count"] == 1 and status["last_error"]


async def test_refresh_all_refreshes_domains_after_sets(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_all(session_factory, http, now=NOW)
    with session_factory() as s:
        assert s.get(GameArtifactSet, 15007) is not None
        assert s.get(GameArtifactDomain, 5101) is not None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `PY -m pytest tests/test_genshindb.py -q`
Expected: FAIL (`ModuleNotFoundError: app.gamedata.genshindb`).

- [ ] **Step 4: Implement**

```python
# backend/app/gamedata/genshindb.py
"""Artifact domains from genshin-db (MIT, genshin-db-api.vercel.app): which domain drops which 5★ sets.
Public game data only; the request carries no cookie, UID or email (sub-project 8)."""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

GENSHINDB_DOMAINS_URL = "https://genshin-db-api.vercel.app/api/v5/domains"
GENSHINDB_PARAMS = {"query": "names", "matchCategories": "true", "verboseCategories": "true"}
RELIC = "UI_ABYSSUS_RELIC"
_TIER = re.compile(r"\s+[IVX]+$")


@dataclass(frozen=True)
class ArtifactDomainData:
    id: int
    name: str
    entrance: str
    region: str | None
    elements: list[str]
    set_ids: list[int]


def base_name(name: str) -> str:
    return _TIER.sub("", name.strip())


def _valid(d) -> bool:
    try:
        return (d.get("domainType") == RELIC and isinstance(d["rewardPreview"], list)
                and int(d["id"]) > 0 and bool(str(d["name"]).strip()))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _level(d: dict) -> int:
    try:
        return int(d.get("recommendedLevel") or 0)
    except (TypeError, ValueError):
        return 0


def parse_artifact_domains(payload, set_ids_by_name: dict[str, int]) -> tuple[list[ArtifactDomainData], list[str]]:
    """Group tiers by name, take the top tier's 5★ set names, map them to our set ids.
    Returns (domains sorted by id, sorted unmatched set names). Malformed entries are skipped."""
    if not isinstance(payload, list):
        raise ValueError("genshin-db domains: expected a list")
    groups: dict[str, list[dict]] = {}
    for d in payload:
        if isinstance(d, dict) and _valid(d):
            groups.setdefault(base_name(str(d["name"])), []).append(d)
    domains: list[ArtifactDomainData] = []
    unmatched: set[str] = set()
    for name, tiers in groups.items():
        top = max(tiers, key=_level)
        names = list(dict.fromkeys(str(r["name"]) for r in top["rewardPreview"]
                                   if isinstance(r, dict) and r.get("rarity") == 5 and r.get("name")))
        ids: list[int] = []
        for n in names:
            if n in set_ids_by_name:
                ids.append(set_ids_by_name[n])
            else:
                unmatched.add(n)
        if not ids:
            continue
        domains.append(ArtifactDomainData(
            id=min(int(t["id"]) for t in tiers), name=name,
            entrance=str(top.get("entranceName") or name), region=(str(top["regionName"]) if top.get("regionName") else None),
            elements=[str(e) for e in (top.get("recommendedElements") or [])], set_ids=ids))
    return sorted(domains, key=lambda d: d.id), sorted(unmatched)


async def fetch_domains(http: httpx.AsyncClient) -> object:
    response = await http.get(GENSHINDB_DOMAINS_URL, params=GENSHINDB_PARAMS, timeout=30)
    response.raise_for_status()
    return response.json()
```

Note: `response.json()` on the HTML body raises `json.JSONDecodeError`, a `ValueError` subclass, so it is inside `FETCH_ERRORS`.

In `backend/app/gamedata/service.py` import `GameArtifactDomain` and `from app.gamedata.genshindb import fetch_domains, parse_artifact_domains`, then add after `refresh_artifact_sets`:

```python
META_DOMAINS_FETCHED = "artifact_domains_fetched_at"
META_DOMAINS_ERROR = "artifact_domains_last_error"
META_DOMAINS_UNMATCHED = "artifact_domains_unmatched"


def artifact_domains_need_refresh(session: Session, now: datetime) -> bool:
    fetched = _get_meta(session, META_DOMAINS_FETCHED)
    if not fetched or session.scalar(select(func.count()).select_from(GameArtifactDomain)) == 0:
        return True
    return now - datetime.fromisoformat(fetched.rstrip("Z")) > timedelta(days=GAMEDATA_MAX_AGE_DAYS)


async def refresh_artifact_domains(session_factory: sessionmaker, http: httpx.AsyncClient,
                                   now: datetime | None = None, force: bool = False) -> bool:
    """genshin-db artifact domains, mapped to our set ids by name. Needs artifact sets first."""
    now = now or utcnow()
    with session_factory() as s:
        if not force and not artifact_domains_need_refresh(s, now):
            return False
        by_name = {a.name: a.id for a in s.scalars(select(GameArtifactSet))}
    if not by_name:
        return False
    try:
        domains, unmatched = parse_artifact_domains(await fetch_domains(http), by_name)
    except FETCH_ERRORS as e:
        message = f"{type(e).__name__}: {e}"[:300]
        log.warning("Artifact domain refresh failed: %s", message)
        with session_factory.begin() as s:
            _set_meta(s, META_DOMAINS_ERROR, message)
        return False
    if unmatched:
        log.info("Artifact domain sets not matched to game data: %s", ", ".join(unmatched))
    with session_factory.begin() as s:
        s.execute(delete(GameArtifactDomain))
        for d in domains:
            s.add(GameArtifactDomain(id=d.id, name=d.name, entrance=d.entrance, region=d.region,
                                     elements=d.elements, set_ids=d.set_ids))
        _set_meta(s, META_DOMAINS_FETCHED, iso(now))
        _set_meta(s, META_DOMAINS_ERROR, None)
        _set_meta(s, META_DOMAINS_UNMATCHED, unmatched)
    return True
```

In `refresh_all`, after the `sets = …` line:

```python
    domains = await refresh_artifact_domains(session_factory, http, now=now, force=force or sets)
```

and return `characters or materials or sets or banners or domains`.

In `gamedata_status`, add after `"artifact_sets"`:

```python
        "artifact_domains": {
            "fetched_at": _get_meta(session, META_DOMAINS_FETCHED),
            "last_error": _get_meta(session, META_DOMAINS_ERROR),
            "count": session.scalar(select(func.count()).select_from(GameArtifactDomain)) or 0,
            "unmatched": _get_meta(session, META_DOMAINS_UNMATCHED) or [],
        },
```

In `backend/tests/helpers.py` `yatta_transport`, load `domains = load_fixture("genshindb_domains.json")` and add before the final 404 (and before the `status != 200` check is fine either way — keep the existing order, put it with the others):

```python
        if path.endswith("/api/v5/domains"):
            return httpx.Response(200, json=domains)
```

In `backend/tests/test_gamedata.py` `test_refresh_stores_rows_and_meta`, add to the expected dict:

```python
                      "artifact_domains": {"fetched_at": None, "last_error": None, "count": 0, "unmatched": []},
```

Frontend: in `frontend/src/lib/types.ts` gamedata block add
`artifact_domains: { fetched_at: string | null; last_error: string | null; count: number; unmatched: string[] };`
and in `frontend/src/routes/settings/+page.svelte` after the artifact-sets error line:

```svelte
						<p>
							{settings.gamedata.artifact_domains.count} artifact domains ·
							{settings.gamedata.artifact_domains.fetched_at ? `updated ${timeAgo(settings.gamedata.artifact_domains.fetched_at, now)}` : 'never downloaded'}
						</p>
						{#if settings.gamedata.artifact_domains.last_error}<p class="error">Artifact domains: {settings.gamedata.artifact_domains.last_error}</p>{/if}
						{#if settings.gamedata.artifact_domains.unmatched.length}
							<p class="muted">Domain sets not matched to game data: {settings.gamedata.artifact_domains.unmatched.join(', ')}</p>
						{/if}
```

(Check `backend/app/api/settings.py` passes `gamedata_status` through unchanged; if it picks keys, add `artifact_domains`.)

- [ ] **Step 5: Run tests**

Run: `PY -m pytest tests/test_genshindb.py tests/test_gamedata.py tests/test_api_settings.py -q` → PASS. Then `PY -m pytest -q` and, from `frontend/`, `npm run check` → 0 errors.

- [ ] **Step 6: Commit**

```bash
git add backend/app/gamedata/genshindb.py backend/app/gamedata/service.py backend/tests/fixtures/genshindb_domains.json backend/tests/test_genshindb.py backend/tests/helpers.py backend/tests/test_gamedata.py frontend/src/lib/types.ts frontend/src/routes/settings/+page.svelte
git commit -m "feat(gamedata): artifact domains from genshin-db, refreshed weekly"
```

---

### Task 3: Stat keys, main-stat parser and the artifact check (pure)

**Files:**
- Create: `backend/app/artifacts/__init__.py` (empty docstring), `backend/app/artifacts/stats.py`, `backend/app/artifacts/check.py`
- Test: `backend/tests/test_artifact_check.py`

**Interfaces:**
- Produces:
  - `stats.MAIN_SLOTS = ("sands", "goblet", "circlet")`, `stats.SLOT_NAMES: dict[int, str]` (1 flower … 5 circlet), `stats.SLOT_OPTIONS: dict[str, tuple[str, ...]]`, `stats.SUB_KEYS: tuple[str, ...]`, `stats.main_key(text: str) -> str | None`.
  - `check.check(target: dict | None, equipped: Sequence[GearLike], sets_by_id: dict[int, tuple[str, str | None]]) -> dict` where `GearLike` has `.slot: int`, `.set_name: str`, `.main_stat: str`, `.icon: str`. Returns `{"status": "none"|"met"|"missing", "sets": [{set_id, name, icon, pieces, equipped}], "slots": [{slot, set_name, icon, main_stat, key, ok}], "missing": [str]}`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_artifact_check.py
from dataclasses import dataclass

import pytest

from app.artifacts.check import check
from app.artifacts.stats import SLOT_OPTIONS, main_key


@dataclass
class Gear:
    slot: int
    set_name: str
    main_stat: str
    icon: str = "UI_RelicIcon_x"


SETS = {15007: ("Noblesse Oblige", "UI_RelicIcon_15007_4"), 15001: ("Gladiator's Finale", "UI_RelicIcon_15001_4")}
NO = "Noblesse Oblige"
GL = "Gladiator's Finale"


@pytest.mark.parametrize("text,key", [
    ("HP 4780", "hp"), ("ATK 311", "atk"), ("HP 46.6%", "hp%"), ("ATK 46.6%", "atk%"), ("DEF 58.3%", "def%"),
    ("Elemental Mastery 187", "em"), ("Energy Recharge 51.8%", "er"), ("CRIT Rate 31.1%", "crit_rate"),
    ("CRIT DMG 62.2%", "crit_dmg"), ("Healing Bonus 35.9%", "heal"), ("Pyro DMG Bonus 46.6%", "pyro"),
    ("Dendro DMG Bonus 46.6%", "dendro"), ("Physical DMG Bonus 58.3%", "phys"),
])
def test_main_key(text, key):
    assert main_key(text) == key


def test_main_key_aliases():
    assert main_key("HP% 46.6%") == "hp%"
    assert main_key("ER 51.8%") == "er"
    assert main_key("Mystery Stat 12") is None
    assert main_key("") is None
    assert main_key("Shiny DMG Bonus 46.6%") is None


def test_slot_options():
    assert "er" in SLOT_OPTIONS["sands"] and "crit_rate" not in SLOT_OPTIONS["sands"]
    assert "pyro" in SLOT_OPTIONS["goblet"] and "phys" in SLOT_OPTIONS["goblet"]
    assert "heal" in SLOT_OPTIONS["circlet"] and "er" not in SLOT_OPTIONS["circlet"]


FULL_NO = [Gear(1, NO, "HP 4780"), Gear(2, NO, "ATK 311"), Gear(3, NO, "Energy Recharge 51.8%"),
           Gear(4, NO, "Pyro DMG Bonus 46.6%"), Gear(5, GL, "CRIT Rate 31.1%")]


def test_no_target_is_none():
    r = check(None, FULL_NO, SETS)
    assert r["status"] == "none" and r["missing"] == [] and len(r["slots"]) == 5
    assert check({"sets": [], "main": {"sands": []}, "subs": ["er"]}, FULL_NO, SETS)["status"] == "none"


def test_four_piece_and_mains_met():
    t = {"sets": [{"set_id": 15007, "pieces": 4}],
         "main": {"sands": ["er", "atk%"], "goblet": ["pyro"], "circlet": ["crit_rate", "crit_dmg"]}, "subs": []}
    r = check(t, FULL_NO, SETS)
    assert r["status"] == "met"
    assert r["sets"] == [{"set_id": 15007, "name": NO, "icon": "UI_RelicIcon_15007_4", "pieces": 4, "equipped": 4}]
    assert [s["ok"] for s in r["slots"]] == [None, None, True, True, True]


def test_two_plus_two():
    gear = [Gear(1, NO, "HP 4780"), Gear(2, NO, "ATK 311"), Gear(3, GL, "ATK 46.6%"), Gear(4, GL, "ATK 46.6%")]
    t = {"sets": [{"set_id": 15007, "pieces": 2}, {"set_id": 15001, "pieces": 2}], "main": {}, "subs": []}
    assert check(t, gear, SETS)["status"] == "met"


def test_partial_set_and_wrong_main():
    gear = [Gear(1, NO, "HP 4780"), Gear(2, NO, "ATK 311"), Gear(3, GL, "ATK 46.6%"), Gear(4, GL, "HP 46.6%")]
    t = {"sets": [{"set_id": 15007, "pieces": 4}], "main": {"goblet": ["pyro"]}, "subs": []}
    r = check(t, gear, SETS)
    assert r["status"] == "missing"
    assert r["missing"] == ["4pc Noblesse Oblige (2/4)", "Goblet"]
    assert [s["ok"] for s in r["slots"]] == [None, None, None, False]   # sands has no preference


def test_missing_slot_counts():
    gear = [Gear(1, NO, "HP 4780"), Gear(2, NO, "ATK 311"), Gear(4, NO, "Pyro DMG Bonus 46.6%"), Gear(5, NO, "CRIT DMG 62.2%")]
    t = {"sets": [{"set_id": 15007, "pieces": 4}], "main": {"sands": ["er"]}, "subs": []}
    assert check(t, gear, SETS)["missing"] == ["Sands"]


def test_no_gear():
    t = {"sets": [{"set_id": 15007, "pieces": 4}], "main": {}, "subs": []}
    r = check(t, [], SETS)
    assert r["status"] == "missing" and r["missing"] == ["No artifacts equipped"]
    assert r["sets"][0]["equipped"] == 0


def test_check_unparseable_main():
    gear = [Gear(3, NO, "Mystery Stat 12")]
    r = check({"sets": [], "main": {"sands": ["er"]}, "subs": []}, gear, SETS)
    assert r["slots"][0] == {"slot": "sands", "set_name": NO, "icon": "UI_RelicIcon_x",
                             "main_stat": "Mystery Stat 12", "key": None, "ok": False}
    assert r["status"] == "missing" and r["missing"] == ["Sands"]


def test_unknown_set_id_gets_a_placeholder_name():
    r = check({"sets": [{"set_id": 99999, "pieces": 4}], "main": {}, "subs": []}, FULL_NO, SETS)
    assert r["sets"][0]["name"] == "Set 99999" and r["sets"][0]["icon"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PY -m pytest tests/test_artifact_check.py -q`
Expected: FAIL (`ModuleNotFoundError: app.artifacts`).

- [ ] **Step 3: Implement**

```python
# backend/app/artifacts/__init__.py
"""Artifact targets and the check against equipped gear (sub-project 8)."""
```

```python
# backend/app/artifacts/stats.py
"""Stat keys for artifact targets and the parser for HoYoLAB main-stat strings ("ATK 46.6%")."""
from __future__ import annotations

ELEMENTS = ("pyro", "hydro", "electro", "cryo", "anemo", "geo", "dendro")
MAIN_SLOTS = ("sands", "goblet", "circlet")
SLOT_NAMES = {1: "flower", 2: "plume", 3: "sands", 4: "goblet", 5: "circlet"}
SLOT_OPTIONS: dict[str, tuple[str, ...]] = {
    "sands": ("hp%", "atk%", "def%", "em", "er"),
    "goblet": ("hp%", "atk%", "def%", "em", *ELEMENTS, "phys"),
    "circlet": ("hp%", "atk%", "def%", "em", "crit_rate", "crit_dmg", "heal"),
}
SUB_KEYS = ("hp", "atk", "def", "hp%", "atk%", "def%", "em", "er", "crit_rate", "crit_dmg")

_NAMES = {"Elemental Mastery": "em", "Energy Recharge": "er", "ER": "er", "CRIT Rate": "crit_rate",
          "CRIT DMG": "crit_dmg", "Healing Bonus": "heal", "Physical DMG Bonus": "phys"}


def main_key(text: str) -> str | None:
    """'Pyro DMG Bonus 46.6%' -> 'pyro'; 'ATK 311' -> 'atk'; anything unknown -> None."""
    name, _, value = (text or "").strip().rpartition(" ")
    if not name:
        return None
    pct = value.endswith("%")
    if name.endswith("%"):
        name, pct = name[:-1], True
    if name in ("HP", "ATK", "DEF"):
        return name.lower() + ("%" if pct else "")
    if name in _NAMES:
        return _NAMES[name]
    if name.endswith(" DMG Bonus"):
        element = name[: -len(" DMG Bonus")].lower()
        if element in ELEMENTS:
            return element
    return None
```

```python
# backend/app/artifacts/check.py
"""Does a character's equipped gear meet its artifact target? Sets and main stats only; substats are
the user's call (they tick Artifacts done)."""
from __future__ import annotations

from collections import Counter
from collections.abc import Sequence
from typing import Protocol

from app.artifacts.stats import MAIN_SLOTS, SLOT_NAMES, main_key


class GearLike(Protocol):
    slot: int
    set_name: str
    main_stat: str
    icon: str


def check(target: dict | None, equipped: Sequence[GearLike], sets_by_id: dict[int, tuple[str, str | None]]) -> dict:
    t = target or {}
    mains = {slot: list(v) for slot, v in (t.get("main") or {}).items() if v}
    slots = []
    for a in sorted(equipped, key=lambda a: a.slot):
        slot = SLOT_NAMES.get(a.slot, str(a.slot))
        key = main_key(a.main_stat)
        allowed = mains.get(slot) if slot in MAIN_SLOTS else None
        slots.append({"slot": slot, "set_name": a.set_name, "icon": a.icon, "main_stat": a.main_stat,
                      "key": key, "ok": None if not allowed else key in allowed})
    target_sets = t.get("sets") or []
    if not target_sets and not mains:
        return {"status": "none", "sets": [], "slots": slots, "missing": []}
    worn = Counter(a.set_name for a in equipped)
    sets, missing = [], []
    for e in target_sets:
        name, icon = sets_by_id.get(e["set_id"], (f"Set {e['set_id']}", None))
        have = worn.get(name, 0)
        sets.append({"set_id": e["set_id"], "name": name, "icon": icon, "pieces": e["pieces"], "equipped": have})
        if have < e["pieces"]:
            missing.append(f"{e['pieces']}pc {name} ({have}/{e['pieces']})")
    if not equipped:
        missing = ["No artifacts equipped"]
    else:
        for slot in MAIN_SLOTS:
            if slot in mains and not any(s["slot"] == slot and s["ok"] for s in slots):
                missing.append(slot.capitalize())
    return {"status": "missing" if missing else "met", "sets": sets, "slots": slots, "missing": missing}
```

- [ ] **Step 4: Run tests**

Run: `PY -m pytest tests/test_artifact_check.py -q` → PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/artifacts backend/tests/test_artifact_check.py
git commit -m "feat(artifacts): stat keys, main-stat parser and target check"
```

---

### Task 4: Goal API — target validation, storage, check, and `/api/artifact-sets`

**Files:**
- Create: `backend/app/artifacts/gear.py`, `backend/app/api/artifacts.py`, `backend/tests/test_api_artifacts.py`
- Modify: `backend/app/schemas.py`, `backend/app/planner/order.py` (`apply_goal`), `backend/app/api/characters.py` (`GoalIn`, `character_payload`, `get_character`, `set_goal`), `backend/app/api/__init__.py`, `backend/tests/test_planner_order.py`

**Interfaces:**
- Consumes: `check`, `SLOT_OPTIONS`, `SUB_KEYS` (Task 3); models (Task 1).
- Produces:
  - `schemas.ArtifactTargetIn` (fields `sets: list[ArtifactSetIn]`, `main: ArtifactMainIn`, `subs: list[str]`).
  - `gear.equipped_for(s, cid) -> list[OwnedArtifact]`, `gear.sets_by_id(s) -> dict[int, tuple[str, str | None]]`, `gear.check_for(s, cid, target: dict | None) -> dict`.
  - Character payload keys `artifact_target` (dict | None), `artifacts_done` (bool); detail adds `artifact_check`.
  - `PUT /api/characters/{id}/goal` body keys `artifact_target` (object or `null`), `artifacts_done` (bool).
  - `GET /api/artifact-sets` → `[{id, name, icon, domain: {id, name, entrance, region} | null}]` sorted by name.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_api_artifacts.py
from app.db.models import CharacterGoal, GameArtifactDomain, GameArtifactSet
from app.sync.persist import save_details, save_roster
from app.timeutil import utcnow
from fakes import make_detail, make_roster
from helpers import make_client, seed_game
from test_api_characters import sf_for

TARGET = {"sets": [{"set_id": 15007, "pieces": 4}],
          "main": {"sands": ["er"], "goblet": ["pyro"], "circlet": ["crit_rate", "crit_dmg"]},
          "subs": ["crit_rate", "crit_dmg", "er"]}


def setup(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with sf.begin() as s:
        now = utcnow()
        save_roster(s, [make_roster(10000032, name="Bennett"),
                        make_roster(1000000503, raw_id=10000007, name="Traveler", element="Geo")], now)
        save_details(s, [make_detail(10000032), make_detail(1000000503)])   # one Noblesse flower each
        s.add(GameArtifactSet(id=15001, name="Gladiator's Finale", icon="UI_RelicIcon_15001_4", sort_order=1))
        s.add(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=2))
        s.add(GameArtifactDomain(id=5101, name="Domain of Blessing: Stone Chamber",
                                 entrance="Clear Pool and Mountain Cavern", region="Liyue",
                                 elements=["Hydro"], set_ids=[15007]))
        s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, priority=1, updated_at=now))
    return sf


def test_goal_stores_target_and_returns_check(paths):
    setup(paths)
    with make_client(paths) as client:
        r = client.put("/api/characters/10000032/goal", json={"artifact_target": TARGET})
        assert r.status_code == 200 and r.json()["artifact_target"] == TARGET
        d = client.get("/api/characters/bennett").json()
    assert d["artifact_target"] == TARGET and d["artifacts_done"] is False
    assert d["artifact_check"]["status"] == "missing"
    assert d["artifact_check"]["sets"][0]["equipped"] == 1
    assert d["artifact_check"]["missing"][0] == "4pc Noblesse Oblige (1/4)"


def test_omit_keeps_and_null_clears(paths):
    setup(paths)
    with make_client(paths) as client:
        client.put("/api/characters/10000032/goal", json={"artifact_target": TARGET})
        client.put("/api/characters/10000032/goal", json={"artifacts_done": True})
        d = client.get("/api/characters/bennett").json()
        assert d["artifact_target"] == TARGET and d["artifacts_done"] is True
        client.put("/api/characters/10000032/goal", json={"artifact_target": None})
        d = client.get("/api/characters/bennett").json()
    assert d["artifact_target"] is None and d["artifact_check"]["status"] == "none"


def test_no_target_check_is_none(paths):
    setup(paths)
    with make_client(paths) as client:
        d = client.get("/api/characters/bennett").json()
    assert d["artifact_target"] is None and d["artifact_check"]["status"] == "none"
    assert d["artifact_check"]["slots"][0]["slot"] == "flower"


def test_invalid_targets_are_422(paths):
    setup(paths)
    bad = [
        {"sets": [{"set_id": 15007, "pieces": 3}]},
        {"sets": [{"set_id": 15007, "pieces": 4}, {"set_id": 15001, "pieces": 2}]},
        {"sets": [{"set_id": 15007, "pieces": 2}, {"set_id": 15007, "pieces": 2}]},
        {"sets": [{"set_id": 15007, "pieces": 2}, {"set_id": 15001, "pieces": 2}, {"set_id": 15001, "pieces": 2}]},
        {"main": {"sands": ["crit_rate"]}},
        {"main": {"goblet": ["shiny"]}},
        {"subs": ["er", "er"]},
        {"subs": ["heal"]},
        {"sets": [{"set_id": 99999, "pieces": 4}]},
        {"extra": 1},
    ]
    with make_client(paths) as client:
        for body in bad:
            assert client.put("/api/characters/10000032/goal", json={"artifact_target": body}).status_code == 422, body


def test_single_two_piece_is_allowed(paths):
    setup(paths)
    with make_client(paths) as client:
        r = client.put("/api/characters/10000032/goal",
                       json={"artifact_target": {"sets": [{"set_id": 15007, "pieces": 2}]}})
    assert r.status_code == 200
    assert r.json()["artifact_target"] == {"sets": [{"set_id": 15007, "pieces": 2}],
                                           "main": {"sands": [], "goblet": [], "circlet": []}, "subs": []}


def test_leaving_build_clears_done_keeps_target(paths):
    setup(paths)
    with make_client(paths) as client:
        client.put("/api/characters/10000032/goal", json={"artifact_target": TARGET, "artifacts_done": True})
        client.put("/api/characters/10000032/goal", json={"goal": "none"})
        d = client.get("/api/characters/bennett").json()
    assert d["artifacts_done"] is False and d["artifact_target"] == TARGET


def test_traveler_element_uses_synced_gear(paths):
    setup(paths)
    with make_client(paths) as client:
        client.put("/api/characters/1000000502/goal",
                   json={"goal": "build", "artifact_target": {"sets": [{"set_id": 15007, "pieces": 4}]}})
        d = client.get("/api/characters/anemo-traveler").json()
    assert d["artifact_check"]["sets"][0]["equipped"] == 1           # the synced Geo element's flower
    assert d["artifact_check"]["missing"] != ["No artifacts equipped"]


def test_artifact_sets_lists_domains(paths):
    setup(paths)
    with make_client(paths) as client:
        rows = client.get("/api/artifact-sets").json()
    assert [r["name"] for r in rows] == ["Gladiator's Finale", "Noblesse Oblige"]
    assert rows[0]["domain"] is None
    assert rows[1]["domain"] == {"id": 5101, "name": "Domain of Blessing: Stone Chamber",
                                 "entrance": "Clear Pool and Mountain Cavern", "region": "Liyue"}
```

Add to `backend/tests/test_planner_order.py` (use the file's existing session fixture style):

```python
def test_leaving_build_clears_artifacts_done(session_factory):
    from app.db.models import CharacterGoal
    from app.planner.order import apply_goal
    from app.timeutil import utcnow
    with session_factory.begin() as s:
        row = CharacterGoal(character_id=10000032, goal="build", priority=1, artifacts_done=True, updated_at=utcnow())
        s.add(row)
        s.flush()
        apply_goal(s, row, "none")
        assert row.artifacts_done is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PY -m pytest tests/test_api_artifacts.py tests/test_planner_order.py -q`
Expected: FAIL (unknown keys ignored, `artifact_target` missing from payload, 404 on `/api/artifact-sets`).

- [ ] **Step 3: Implement**

`backend/app/schemas.py` — add (keep `TargetsIn` unchanged):

```python
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.artifacts.stats import SLOT_OPTIONS, SUB_KEYS


class ArtifactSetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set_id: int
    pieces: Literal[2, 4]


class ArtifactMainIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sands: list[str] = Field(default_factory=list)
    goblet: list[str] = Field(default_factory=list)
    circlet: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _allowed(self):
        for slot, options in SLOT_OPTIONS.items():
            values = getattr(self, slot)
            if len(set(values)) != len(values):
                raise ValueError(f"{slot}: a stat is listed twice")
            bad = [v for v in values if v not in options]
            if bad:
                raise ValueError(f"{slot}: not a {slot} main stat: {', '.join(bad)}")
        return self


class ArtifactTargetIn(BaseModel):
    """One 4-piece set, or up to two 2-piece sets; allowed main stats per slot; ordered substats."""
    model_config = ConfigDict(extra="forbid")
    sets: list[ArtifactSetIn] = Field(default_factory=list, max_length=2)
    main: ArtifactMainIn = Field(default_factory=ArtifactMainIn)
    subs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self):
        if len(self.sets) == 2:
            if any(e.pieces != 2 for e in self.sets):
                raise ValueError("Two sets must both be 2-piece")
            if self.sets[0].set_id == self.sets[1].set_id:
                raise ValueError("Pick two different sets, or one 4-piece set")
        if len(set(self.subs)) != len(self.subs):
            raise ValueError("A substat is listed twice")
        bad = [v for v in self.subs if v not in SUB_KEYS]
        if bad:
            raise ValueError(f"Not a substat: {', '.join(bad)}")
        return self
```

(Merge the imports with the file's existing ones.)

`backend/app/planner/order.py` `apply_goal` — after `row.priority = priority` add:

```python
    if new_goal != BUILD:
        row.artifacts_done = False
```

and extend the docstring: "Leaving Build also clears the Artifacts done tick (sub-project 8)."

```python
# backend/app/artifacts/gear.py
"""Database lookups for the artifact check: equipped gear (Traveler elements share it) and set names."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.artifacts.check import check
from app.db.models import GameArtifactSet, OwnedArtifact
from app.gamedata.traveler import TRAVELER_IDS, is_traveler
from app.traveler.store import current_element_id


def equipped_for(s: Session, cid: int) -> list[OwnedArtifact]:
    """A character's equipped pieces. Sync stores gear only for the synced Traveler element, and all
    elements share it in game, so other elements borrow it."""
    ids = [cid]
    if is_traveler(cid):
        cur = current_element_id(s)
        ids += ([cur] if cur else []) + sorted(TRAVELER_IDS)
    for i in dict.fromkeys(ids):
        rows = s.scalars(select(OwnedArtifact).where(OwnedArtifact.character_id == i)
                         .order_by(OwnedArtifact.slot)).all()
        if rows:
            return list(rows)
    return []


def sets_by_id(s: Session) -> dict[int, tuple[str, str | None]]:
    return {a.id: (a.name, a.icon) for a in s.scalars(select(GameArtifactSet))}


def check_for(s: Session, cid: int, target: dict | None) -> dict:
    return check(target, equipped_for(s, cid), sets_by_id(s))
```

`backend/app/api/characters.py`:

- Import `from app.artifacts.gear import check_for` and `from app.schemas import ArtifactTargetIn, TargetsIn` and `GameArtifactSet` from models.
- `GoalIn` gains:

```python
    artifact_target: ArtifactTargetIn | None = None
    artifacts_done: bool | None = None
```

- `character_payload` return dict gains (after `"planned_weapon_id"`):

```python
        "artifact_target": goal_row.artifact_target if goal_row else None,
        "artifacts_done": bool(goal_row.artifacts_done) if goal_row else False,
```

- `get_character`: after `payload["teams"] = …` add `payload["artifact_check"] = check_for(s, payload["id"], payload["artifact_target"])`.
- `set_goal`: after the `planned_weapon_id` block (still inside the session, before `changed = …`):

```python
        if "artifact_target" in body.model_fields_set:
            t = body.artifact_target
            if t is not None:
                unknown = [e.set_id for e in t.sets if s.get(GameArtifactSet, e.set_id) is None]
                if unknown:
                    raise HTTPException(422, f"Unknown artifact set: {', '.join(map(str, unknown))}")
            row.artifact_target = None if t is None else t.model_dump()
        if body.artifacts_done is not None:
            row.artifacts_done = body.artifacts_done if row.goal == "build" else False
```

`artifacts_done` must be set after `apply_goal` (already the case: the block is below it). The artifact fields are not added to `state()`: they do not change material gaps.

```python
# backend/app/api/artifacts.py
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.context import AppContext, get_ctx
from app.db.models import GameArtifactDomain, GameArtifactSet

router = APIRouter()


@router.get("/artifact-sets")
def artifact_sets(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    """Every known set with the domain that drops it (None: bosses, Strongbox, or unknown)."""
    with ctx.session_factory() as s:
        source: dict[int, dict] = {}
        for d in s.scalars(select(GameArtifactDomain).order_by(GameArtifactDomain.id)):
            for sid in d.set_ids:
                source.setdefault(sid, {"id": d.id, "name": d.name, "entrance": d.entrance, "region": d.region})
        rows = [{"id": a.id, "name": a.name, "icon": a.icon, "domain": source.get(a.id)}
                for a in s.scalars(select(GameArtifactSet))]
    return sorted(rows, key=lambda r: r["name"])
```

Register in `backend/app/api/__init__.py`: import `artifacts` and append `artifacts.router` to `ROUTERS`.

- [ ] **Step 4: Run tests**

Run: `PY -m pytest tests/test_api_artifacts.py tests/test_planner_order.py tests/test_api_characters.py tests/test_teams_goals.py -q` → PASS. Then `PY -m pytest -q`; if an existing test compares a whole character payload dict, add the two new keys to its expectation.

- [ ] **Step 5: Commit**

```bash
git add backend/app/schemas.py backend/app/planner/order.py backend/app/artifacts/gear.py backend/app/api/characters.py backend/app/api/artifacts.py backend/app/api/__init__.py backend/tests/test_api_artifacts.py backend/tests/test_planner_order.py
git commit -m "feat(api): artifact targets on the goal, equipped check, /api/artifact-sets"
```

---

### Task 5: Dashboard `artifact_domains`

**Files:**
- Create: `backend/app/dashboard/artifacts.py`, `backend/tests/test_dashboard_artifacts.py`
- Modify: `backend/app/api/dashboard.py`, `backend/tests/test_api_dashboard.py`

**Interfaces:**
- Consumes: `check_for`, `sets_by_id` (Task 4); `build_order` (`app/planner/order.py`).
- Produces: `group_artifact_domains(builds: list[dict], sets: dict[int, dict], domains: list[dict]) -> dict` (pure) and `artifact_domains_view(s: Session) -> dict`; dashboard key `artifact_domains = {"domains": [...], "other": [...], "hint": str | None}`. Domain row: `{id, name, entrance, region, elements, sets: [SetRow]}`; `SetRow = {id, name, icon, needed: bool, characters: [{id, name, slug, icon, pieces, equipped}]}`; `other` is a list of `SetRow`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_dashboard_artifacts.py
from app.dashboard.artifacts import HINT, group_artifact_domains

SETS = {15007: {"id": 15007, "name": "Noblesse Oblige", "icon": "N"},
        15008: {"id": 15008, "name": "Bloodstained Chivalry", "icon": "B"},
        15001: {"id": 15001, "name": "Gladiator's Finale", "icon": "G"},
        15020: {"id": 15020, "name": "Emblem of Severed Fate", "icon": "E"},
        15019: {"id": 15019, "name": "Shimenawa's Reminiscence", "icon": "S"}}
DOMAINS = [{"id": 5101, "name": "Domain of Blessing: Stone Chamber", "entrance": "Clear Pool and Mountain Cavern",
            "region": "Liyue", "elements": ["Hydro"], "set_ids": [15008, 15007]},
           {"id": 5301, "name": "Domain of Blessing: Autumn Hunt", "entrance": "Momiji-Dyed Court",
            "region": "Inazuma", "elements": ["Electro"], "set_ids": [15020, 15019]}]


def char(cid, name):
    return {"id": cid, "name": name, "slug": name.lower(), "icon": f"UI_{name}"}


def build(cid, name, sets, status="missing", done=False, equipped=None):
    target = {"sets": [{"set_id": sid, "pieces": p} for sid, p in sets], "main": {}, "subs": []} if sets is not None else None
    eq = equipped or {}
    return {"character": char(cid, name), "target": target, "done": done,
            "check": {"status": status, "sets": [{"set_id": sid, "equipped": eq.get(sid, 0)} for sid, _ in (sets or [])]}}


def test_groups_by_domain_in_priority_order():
    builds = [build(1, "Ayaka", [(15020, 4)], equipped={15020: 2}),
              build(2, "Furina", [(15007, 2), (15001, 2)]),
              build(3, "Neuvi", [(15008, 4)])]
    r = group_artifact_domains(builds, SETS, DOMAINS)
    assert [d["entrance"] for d in r["domains"]] == ["Momiji-Dyed Court", "Clear Pool and Mountain Cavern"]
    autumn = r["domains"][0]
    assert [(s["name"], s["needed"]) for s in autumn["sets"]] == [("Emblem of Severed Fate", True),
                                                                 ("Shimenawa's Reminiscence", False)]
    assert autumn["sets"][0]["characters"] == [{**char(1, "Ayaka"), "pieces": 4, "equipped": 2}]
    stone = r["domains"][1]
    assert [c["name"] for c in stone["sets"][0]["characters"]] == ["Neuvi"]     # Bloodstained
    assert [c["name"] for c in stone["sets"][1]["characters"]] == ["Furina"]    # Noblesse
    assert [o["name"] for o in r["other"]] == ["Gladiator's Finale"]
    assert r["other"][0]["characters"][0]["name"] == "Furina" and r["hint"] is None


def test_met_done_and_no_sets_are_not_counted():
    builds = [build(1, "Met", [(15007, 4)], status="met"),
              build(2, "Done", [(15007, 4)], done=True),
              build(3, "Stats", []),
              build(4, "None", None, status="none")]
    r = group_artifact_domains(builds, SETS, DOMAINS)
    assert r == {"domains": [], "other": [], "hint": None}


def test_hint_when_builds_have_no_set_targets():
    r = group_artifact_domains([build(1, "A", None, status="none")], SETS, DOMAINS)
    assert r == {"domains": [], "other": [], "hint": HINT}
    assert group_artifact_domains([], SETS, DOMAINS)["hint"] is None


def test_ties_sort_by_name_and_unknown_set_goes_to_other():
    builds = [build(1, "A", [(15020, 2), (15008, 2)]), build(2, "B", [(77777, 4)])]
    r = group_artifact_domains(builds, SETS, DOMAINS)
    assert [d["name"] for d in r["domains"]] == ["Domain of Blessing: Autumn Hunt", "Domain of Blessing: Stone Chamber"]
    assert r["other"][0]["name"] == "Set 77777" and r["other"][0]["icon"] is None
```

In `backend/tests/test_api_dashboard.py` add `"artifact_domains"` to the `KEYS` set, and add (the file's `setup` comes from `test_api_planner` and makes Bennett 10000032 a Build character):

```python
def test_dashboard_artifact_domains(paths):
    sf = setup(paths)
    from app.db.models import GameArtifactDomain, GameArtifactSet
    with sf.begin() as s:
        s.merge(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=2))
        s.add(GameArtifactDomain(id=5101, name="Domain of Blessing: Stone Chamber", entrance="Clear Pool and Mountain Cavern",
                                 region="Liyue", elements=["Hydro"], set_ids=[15007]))
        s.get(CharacterGoal, 10000032).artifact_target = {"sets": [{"set_id": 15007, "pieces": 4}], "main": {}, "subs": []}
    with make_client(paths) as client:
        block = client.get("/api/dashboard").json()["artifact_domains"]
    assert block["domains"][0]["entrance"] == "Clear Pool and Mountain Cavern"
    assert block["domains"][0]["sets"][0]["characters"][0]["id"] == 10000032
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PY -m pytest tests/test_dashboard_artifacts.py -q` → FAIL (module missing).

- [ ] **Step 3: Implement**

```python
# backend/app/dashboard/artifacts.py
"""Dashboard Artifact domains: which domains to run and for whom, in Build priority order (sub-project 8)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.artifacts.gear import check_for
from app.db.models import CharacterGoal, GameArtifactDomain, GameArtifactSet, GameCharacter, OwnedCharacter
from app.planner.order import build_order

HINT = "Set artifact targets on a character's Build tab to plan domains here"


def group_artifact_domains(builds: list[dict], sets: dict[int, dict], domains: list[dict]) -> dict:
    """`builds`: Build characters in priority order, each {character, target, done, check}.
    A character counts when its target has sets, it is not ticked done and its check is "missing"."""
    wanted: dict[int, list[dict]] = {}
    best: dict[int, int] = {}
    for rank, b in enumerate(builds):
        target_sets = (b["target"] or {}).get("sets") or []
        if not target_sets or b["done"] or b["check"]["status"] != "missing":
            continue
        worn = {e["set_id"]: e["equipped"] for e in b["check"].get("sets", [])}
        for e in target_sets:
            sid = e["set_id"]
            wanted.setdefault(sid, []).append({**b["character"], "pieces": e["pieces"], "equipped": worn.get(sid, 0)})
            best.setdefault(sid, rank)

    def set_row(sid: int) -> dict:
        info = sets.get(sid) or {"id": sid, "name": f"Set {sid}", "icon": None}
        chars = wanted.get(sid, [])
        return {"id": sid, "name": info["name"], "icon": info["icon"], "needed": bool(chars), "characters": chars}

    shown, covered = [], set()
    for d in domains:
        needed = [sid for sid in d["set_ids"] if sid in wanted]
        if not needed:
            continue
        covered.update(d["set_ids"])
        row = {k: d[k] for k in ("id", "name", "entrance", "region", "elements")}
        row["sets"] = [set_row(sid) for sid in d["set_ids"]]
        shown.append((min(best[sid] for sid in needed), d["name"], row))
    shown.sort(key=lambda t: (t[0], t[1]))
    other = sorted((set_row(sid) for sid in wanted if sid not in covered), key=lambda r: (best[r["id"]], r["name"]))
    has_targets = any((b["target"] or {}).get("sets") for b in builds)
    return {"domains": [r for _, _, r in shown], "other": other,
            "hint": HINT if builds and not has_targets else None}


def artifact_domains_view(s: Session) -> dict:
    goals = {r.character_id: r for r in s.scalars(select(CharacterGoal))}
    games = {g.id: g for g in s.scalars(select(GameCharacter))}
    owned = {o.character_id: o for o in s.scalars(select(OwnedCharacter))}
    builds = []
    for cid in build_order(s):
        g, o, row = games.get(cid), owned.get(cid), goals[cid]
        if g is None and o is None:
            continue
        icon = (o.icon if o is not None and o.icon else None) or (g.icon if g is not None else None)
        builds.append({
            "character": {"id": cid, "name": g.name if g is not None else o.name,
                          "slug": g.slug if g is not None else f"id-{cid}", "icon": icon},
            "target": row.artifact_target, "done": bool(row.artifacts_done),
            "check": check_for(s, cid, row.artifact_target)})
    sets = {a.id: {"id": a.id, "name": a.name, "icon": a.icon} for a in s.scalars(select(GameArtifactSet))}
    domains = [{"id": d.id, "name": d.name, "entrance": d.entrance, "region": d.region, "elements": d.elements,
                "set_ids": d.set_ids} for d in s.scalars(select(GameArtifactDomain).order_by(GameArtifactDomain.id))]
    return group_artifact_domains(builds, sets, domains)
```

`check_for` re-reads the set table per character; fine for a handful of Build characters. If a reviewer flags it, pass `sets_by_id(s)` once into `check()` directly — behaviour is identical.

In `backend/app/api/dashboard.py` import `artifact_domains_view` and add to the returned dict after `"weekly_bosses"`:

```python
            "artifact_domains": artifact_domains_view(s),
```

- [ ] **Step 4: Run tests**

Run: `PY -m pytest tests/test_dashboard_artifacts.py tests/test_api_dashboard.py -q` → PASS; then `PY -m pytest -q`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/dashboard/artifacts.py backend/app/api/dashboard.py backend/tests/test_dashboard_artifacts.py backend/tests/test_api_dashboard.py
git commit -m "feat(dashboard): artifact domains grouped by Build priority"
```

---

### Task 6: Dev seed

**Files:**
- Modify: `backend/app/devseed.py`, `backend/tests/test_devseed.py`

**Interfaces:**
- Consumes: models (Task 1). Produces seed data the e2e tests (Task 10) rely on:
  - Sets 15001 Gladiator's Finale, 15007 Noblesse Oblige, **15008 Bloodstained Chivalry** (`UI_RelicIcon_15008_4`).
  - Domain 5101 "Domain of Blessing: Stone Chamber", entrance "Clear Pool and Mountain Cavern", region "Liyue", elements `["Hydro", "Pyro"]`, `set_ids [15008, 15007]`; meta `artifact_domains_fetched_at` = now.
  - Bennett (10000032, P1): target 4pc Noblesse, sands `["er"]`, `artifacts_done = True`.
  - Furina (10000089, P2): target 2pc Noblesse + 2pc Gladiator, sands `["hp%"]`, goblet `["hydro"]`, circlet `["crit_rate", "crit_dmg"]`, subs `["crit_rate", "crit_dmg", "hp%", "er"]`, not done.
  - Neuvillette (10000087, P3, unowned): target 4pc Bloodstained Chivalry, not done.

- [ ] **Step 1: Write the failing test**

```python
# add to backend/tests/test_devseed.py
def test_devseed_artifact_domains(tmp_path):
    seed(tmp_path)
    with make_client(Paths(tmp_path)) as client:
        block = client.get("/api/dashboard").json()["artifact_domains"]
        furina = client.get("/api/characters/furina").json()
    assert [d["entrance"] for d in block["domains"]] == ["Clear Pool and Mountain Cavern"]
    sets = {s["name"]: [c["slug"] for c in s["characters"]] for s in block["domains"][0]["sets"]}
    assert sets == {"Bloodstained Chivalry": ["neuvillette"], "Noblesse Oblige": ["furina"]}   # Bennett ticked done
    assert [(o["name"], [c["slug"] for c in o["characters"]]) for o in block["other"]] == [("Gladiator's Finale", ["furina"])]
    assert furina["artifact_check"]["status"] == "missing"
```

- [ ] **Step 2: Run** `PY -m pytest tests/test_devseed.py -q` → FAIL (`KeyError`/empty block).

- [ ] **Step 3: Implement** in `backend/app/devseed.py` (import `GameArtifactDomain`):

After the two existing `GameArtifactSet` adds:

```python
        s.add(GameArtifactSet(id=15008, name="Bloodstained Chivalry", icon="UI_RelicIcon_15008_4", sort_order=3))
        s.add(GameArtifactDomain(id=5101, name="Domain of Blessing: Stone Chamber",
                                 entrance="Clear Pool and Mountain Cavern", region="Liyue",
                                 elements=["Hydro", "Pyro"], set_ids=[15008, 15007]))
        s.merge(GameMeta(key="artifact_domains_fetched_at", value=iso(now)))
```

Add a module constant next to `GOALS`:

```python
# Artifact targets (sub-project 8): Bennett is ticked done; Furina and Neuvillette still need domain runs.
ARTIFACT_TARGETS = {
    10000032: ({"sets": [{"set_id": 15007, "pieces": 4}], "main": {"sands": ["er"], "goblet": [], "circlet": []},
                "subs": []}, True),
    10000089: ({"sets": [{"set_id": 15007, "pieces": 2}, {"set_id": 15001, "pieces": 2}],
                "main": {"sands": ["hp%"], "goblet": ["hydro"], "circlet": ["crit_rate", "crit_dmg"]},
                "subs": ["crit_rate", "crit_dmg", "hp%", "er"]}, False),
    10000087: ({"sets": [{"set_id": 15008, "pieces": 4}], "main": {"sands": [], "goblet": [], "circlet": []},
                "subs": []}, False),
}
```

and in the `CharacterGoal(...)` constructor add:

```python
                                artifact_target=ARTIFACT_TARGETS.get(cid, (None, False))[0],
                                artifacts_done=ARTIFACT_TARGETS.get(cid, (None, False))[1],
```

- [ ] **Step 4: Run** `PY -m pytest tests/test_devseed.py -q` → PASS; `PY -m pytest -q` → all pass (if a test counts artifact sets in the seed, update it to 3).

- [ ] **Step 5: Commit**

```bash
git add backend/app/devseed.py backend/tests/test_devseed.py
git commit -m "chore(devseed): artifact domain and targets for Build characters"
```

---

### Task 7: Frontend types, API and `lib/artifacts.ts`

**Files:**
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/characterPage.svelte.ts`
- Create: `frontend/src/lib/artifacts.ts`, `frontend/src/lib/artifacts.test.ts`

**Interfaces:**
- Produces (types): `MainSlot = 'sands' | 'goblet' | 'circlet'`; `ArtifactTarget { sets: { set_id: number; pieces: 2 | 4 }[]; main: Record<MainSlot, string[]>; subs: string[] }`; `ArtifactCheck { status: 'none' | 'met' | 'missing'; sets: { set_id: number; name: string; icon: string | null; pieces: number; equipped: number }[]; slots: { slot: string; set_name: string; icon: string; main_stat: string; key: string | null; ok: boolean | null }[]; missing: string[] }`; `ArtifactSetOption { id; name; icon; domain: { id: number; name: string; entrance: string; region: string | null } | null }`; `ArtifactDomainChar { id; name; slug; icon: string | null; pieces: number; equipped: number }`; `ArtifactSetRow { id; name; icon: string | null; needed: boolean; characters: ArtifactDomainChar[] }`; `ArtifactDomainsView { domains: { id; name; entrance; region: string | null; elements: string[]; sets: ArtifactSetRow[] }[]; other: ArtifactSetRow[]; hint: string | null }`.
  - `Character` gains `artifact_target: ArtifactTarget | null; artifacts_done: boolean`; `CharacterDetail` gains `artifact_check: ArtifactCheck`; `Dashboard` gains `artifact_domains: ArtifactDomainsView`.
  - `GoalBody = { goal?: Goal; targets?: Targets; planned_weapon_id?: number | null; artifact_target?: ArtifactTarget | null; artifacts_done?: boolean }` used by `api.setGoal` and `CharacterPage.saveGoal`.
  - `api.artifactSets(): Promise<ArtifactSetOption[]>`.
  - `lib/artifacts.ts`: `STAT_LABELS: Record<string, string>`, `SLOT_OPTIONS: Record<MainSlot, string[]>`, `SUB_KEYS: string[]`, `MAIN_SLOTS: MainSlot[]`, `emptyTarget(): ArtifactTarget`, `toggleStat(list, key): string[]`, `moveSub(order, from, to): string[]`, `setsFor(mode: 4 | 2, sets): ArtifactTarget['sets']`, `setSlot(sets, index, setId: number | null, mode): ArtifactTarget['sets']`, `sourceLabel(opt: ArtifactSetOption | undefined): string`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/artifacts.test.ts
import { describe, expect, it } from 'vitest';
import { emptyTarget, moveSub, setSlot, setsFor, SLOT_OPTIONS, sourceLabel, STAT_LABELS, SUB_KEYS, toggleStat } from './artifacts';

describe('artifacts helpers', () => {
	it('labels every option and substat', () => {
		for (const k of [...SLOT_OPTIONS.sands, ...SLOT_OPTIONS.goblet, ...SLOT_OPTIONS.circlet, ...SUB_KEYS]) {
			expect(STAT_LABELS[k]).toBeTruthy();
		}
		expect(STAT_LABELS['crit_dmg']).toBe('CRIT DMG');
		expect(SLOT_OPTIONS.goblet).toContain('pyro');
		expect(SLOT_OPTIONS.sands).not.toContain('crit_rate');
	});
	it('empty target', () => {
		expect(emptyTarget()).toEqual({ sets: [], main: { sands: [], goblet: [], circlet: [] }, subs: [] });
	});
	it('toggles a stat', () => {
		expect(toggleStat(['er'], 'atk%')).toEqual(['er', 'atk%']);
		expect(toggleStat(['er', 'atk%'], 'er')).toEqual(['atk%']);
	});
	it('moves a substat', () => {
		expect(moveSub(['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b']);
		expect(moveSub(['a', 'b'], 0, 5)).toEqual(['a', 'b']);
	});
	it('switching mode keeps the first set', () => {
		expect(setsFor(2, [{ set_id: 1, pieces: 4 }])).toEqual([{ set_id: 1, pieces: 2 }]);
		expect(setsFor(4, [{ set_id: 1, pieces: 2 }, { set_id: 2, pieces: 2 }])).toEqual([{ set_id: 1, pieces: 4 }]);
		expect(setsFor(4, [])).toEqual([]);
	});
	it('sets a picker slot', () => {
		expect(setSlot([], 0, 5, 4)).toEqual([{ set_id: 5, pieces: 4 }]);
		expect(setSlot([{ set_id: 5, pieces: 2 }], 1, 6, 2)).toEqual([{ set_id: 5, pieces: 2 }, { set_id: 6, pieces: 2 }]);
		expect(setSlot([{ set_id: 5, pieces: 2 }, { set_id: 6, pieces: 2 }], 0, null, 2)).toEqual([{ set_id: 6, pieces: 2 }]);
		expect(setSlot([{ set_id: 5, pieces: 2 }], 1, 5, 2)).toEqual([{ set_id: 5, pieces: 2 }]);   // same set twice: ignored
	});
	it('source label', () => {
		expect(sourceLabel({ id: 1, name: 'N', icon: 'x', domain: { id: 2, name: 'D', entrance: 'Clear Pool', region: 'Liyue' } })).toBe('Clear Pool');
		expect(sourceLabel({ id: 1, name: 'G', icon: 'x', domain: null })).toBe('Not from a domain');
		expect(sourceLabel(undefined)).toBe('Drop source unknown');
	});
});
```

- [ ] **Step 2: Run** (from `frontend/`) `npx vitest run src/lib/artifacts.test.ts` → FAIL (module missing).

- [ ] **Step 3: Implement**

```ts
// frontend/src/lib/artifacts.ts
import type { ArtifactSetOption, ArtifactTarget, MainSlot } from './types';

export const MAIN_SLOTS: MainSlot[] = ['sands', 'goblet', 'circlet'];
const ELEMENTS = ['pyro', 'hydro', 'electro', 'cryo', 'anemo', 'geo', 'dendro'];
export const SLOT_OPTIONS: Record<MainSlot, string[]> = {
	sands: ['hp%', 'atk%', 'def%', 'em', 'er'],
	goblet: ['hp%', 'atk%', 'def%', 'em', ...ELEMENTS, 'phys'],
	circlet: ['hp%', 'atk%', 'def%', 'em', 'crit_rate', 'crit_dmg', 'heal']
};
export const SUB_KEYS = ['crit_rate', 'crit_dmg', 'er', 'em', 'atk%', 'hp%', 'def%', 'atk', 'hp', 'def'];
export const STAT_LABELS: Record<string, string> = {
	hp: 'HP', atk: 'ATK', def: 'DEF', 'hp%': 'HP%', 'atk%': 'ATK%', 'def%': 'DEF%', em: 'EM', er: 'ER',
	crit_rate: 'CRIT Rate', crit_dmg: 'CRIT DMG', heal: 'Healing', phys: 'Physical',
	pyro: 'Pyro', hydro: 'Hydro', electro: 'Electro', cryo: 'Cryo', anemo: 'Anemo', geo: 'Geo', dendro: 'Dendro'
};

export function emptyTarget(): ArtifactTarget {
	return { sets: [], main: { sands: [], goblet: [], circlet: [] }, subs: [] };
}

export function toggleStat(list: string[], key: string): string[] {
	return list.includes(key) ? list.filter((k) => k !== key) : [...list, key];
}

export function moveSub(order: string[], from: number, to: number): string[] {
	if (from < 0 || from >= order.length || to < 0 || to >= order.length) return order;
	const next = [...order];
	const [item] = next.splice(from, 1);
	next.splice(to, 0, item);
	return next;
}

/** Switch between one 4-piece set and 2 + 2; the first chosen set is kept. */
export function setsFor(mode: 4 | 2, sets: ArtifactTarget['sets']): ArtifactTarget['sets'] {
	return sets.length ? [{ set_id: sets[0].set_id, pieces: mode }] : [];
}

/** Put `setId` in picker `index` (null clears it). The same set twice is ignored. */
export function setSlot(sets: ArtifactTarget['sets'], index: number, setId: number | null, mode: 4 | 2): ArtifactTarget['sets'] {
	const ids = sets.map((s) => s.set_id);
	if (setId !== null && ids.some((id, i) => id === setId && i !== index)) return sets;
	if (setId === null) ids.splice(index, 1);
	else ids[index] = setId;
	return ids.filter((id) => id !== undefined).map((set_id) => ({ set_id, pieces: mode }));
}

export function sourceLabel(opt: ArtifactSetOption | undefined): string {
	if (!opt) return 'Drop source unknown';
	return opt.domain ? opt.domain.entrance : 'Not from a domain';
}
```

Types (`frontend/src/lib/types.ts`): add the interfaces listed under **Interfaces** verbatim, add the fields to `Character`, `CharacterDetail`, `Dashboard`, and export `GoalBody`.

`frontend/src/lib/api.ts`: import the new types; change `setGoal` to `(id: number, body: GoalBody) => request<Character>('PUT', `/characters/${id}/goal`, body)`; add `artifactSets: () => request<ArtifactSetOption[]>('GET', '/artifact-sets'),`.

`frontend/src/lib/characterPage.svelte.ts`: `saveGoal(body: GoalBody)`.

- [ ] **Step 4: Run** `npx vitest run` → PASS (174 + 7); `npm run check` → 0 errors (fix any test fixture objects typed as `Character`/`Dashboard` that now miss the new fields by adding `artifact_target: null, artifacts_done: false` / `artifact_domains: { domains: [], other: [], hint: null }`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/lib/characterPage.svelte.ts frontend/src/lib/artifacts.ts frontend/src/lib/artifacts.test.ts
git commit -m "feat(frontend): artifact target types, API and helpers"
```

(Include any test files touched for the type fix.)

---

### Task 8: Build tab artifact editor

**Files:**
- Rewrite: `frontend/src/lib/BuildArtifacts.svelte`
- Create: `frontend/src/lib/ArtifactSetPicker.svelte`, `frontend/src/lib/StatPills.svelte`, `frontend/src/lib/SubstatOrder.svelte`
- Modify: `frontend/src/routes/characters/[slug]/build/+page.svelte` (pass `editing`)

**Interfaces:**
- Consumes: `getCharacterPage()` (`p.c.artifact_target`, `p.c.artifacts_done`, `p.c.artifact_check`, `p.saveGoal`), `api.artifactSets()`, everything in `lib/artifacts.ts`, `FilterPill`, `imgSrc`.
- Produces: `<BuildArtifacts editing={boolean} />`; test ids `build-artifacts`, `artifact-mode-4`, `artifact-mode-2`, `artifact-set-0`, `artifact-set-1` (each an `<select>`), `artifact-source-0`, `stat-sands-er` style pill test ids (`stat-<slot>-<key>`), `sub-add` (`<select>`), `sub-<key>` chips with `sub-up-<key>` / `sub-down-<key>` / `sub-remove-<key>` buttons, `artifact-status`, `artifacts-done` (checkbox).

Implementation notes (the component is UI glue; behaviour is covered by the Task 10 e2e test):

- [ ] **Step 1: `StatPills.svelte`**

```svelte
<script lang="ts">
	import FilterPill from './FilterPill.svelte';
	import { STAT_LABELS } from './artifacts';

	let { slot, options, selected, onchange }: {
		slot: string; options: string[]; selected: string[]; onchange: (key: string) => void;
	} = $props();
</script>

<div class="row" role="group" aria-label="{slot} main stat">
	<span class="label">{slot[0].toUpperCase() + slot.slice(1)}</span>
	{#each options as key (key)}
		<span data-testid="stat-{slot}-{key}">
			<FilterPill label={STAT_LABELS[key] ?? key} on={selected.includes(key)} color="var(--el, var(--gold))"
				onclick={() => onchange(key)} />
		</span>
	{/each}
</div>

<style>
	.row { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; }
	.label { width: 64px; font-size: 12px; color: var(--muted); }
</style>
```

- [ ] **Step 2: `ArtifactSetPicker.svelte`** — a labelled `<select>` (searchable enough: the browser's type-ahead; ~60 options) plus icon and source:

```svelte
<script lang="ts">
	import { sourceLabel } from './artifacts';
	import { imgSrc } from './img';
	import type { ArtifactSetOption } from './types';

	let { index, options, value, onchange }: {
		index: number; options: ArtifactSetOption[]; value: number | null; onchange: (id: number | null) => void;
	} = $props();
	const chosen = $derived(options.find((o) => o.id === value));
</script>

<div class="picker">
	<div class="icon">{#if chosen && imgSrc(chosen.icon)}<img src={imgSrc(chosen.icon)} alt="" />{/if}</div>
	<div class="body">
		<select aria-label="Artifact set {index + 1}" data-testid="artifact-set-{index}" value={value ?? ''}
			onchange={(e) => onchange(e.currentTarget.value === '' ? null : Number(e.currentTarget.value))}>
			<option value="">Choose a set…</option>
			{#each options as o (o.id)}<option value={o.id}>{o.name}</option>{/each}
		</select>
		{#if value !== null}
			<span class="muted small" data-testid="artifact-source-{index}">{sourceLabel(chosen)}</span>
		{/if}
	</div>
</div>

<style>
	.picker { display: flex; gap: 8px; align-items: center; }
	.icon { width: 44px; height: 44px; border-radius: 8px; background: rgba(255, 255, 255, 0.06); }
	.icon img { width: 44px; height: 44px; }
	.body { display: flex; flex-direction: column; gap: 2px; }
	.small { font-size: 11px; }
</style>
```

- [ ] **Step 3: `SubstatOrder.svelte`**

```svelte
<script lang="ts">
	import { moveSub, STAT_LABELS, SUB_KEYS } from './artifacts';

	let { subs, onchange }: { subs: string[]; onchange: (next: string[]) => void } = $props();
	const left = $derived(SUB_KEYS.filter((k) => !subs.includes(k)));
</script>

<ol class="subs">
	{#each subs as key, i (key)}
		<li class="chip" data-testid="sub-{key}">
			<span class="n">{i + 1}</span>{STAT_LABELS[key] ?? key}
			<button type="button" aria-label="Move {STAT_LABELS[key]} up" data-testid="sub-up-{key}" disabled={i === 0}
				onclick={() => onchange(moveSub(subs, i, i - 1))}>↑</button>
			<button type="button" aria-label="Move {STAT_LABELS[key]} down" data-testid="sub-down-{key}" disabled={i === subs.length - 1}
				onclick={() => onchange(moveSub(subs, i, i + 1))}>↓</button>
			<button type="button" aria-label="Remove {STAT_LABELS[key]}" data-testid="sub-remove-{key}"
				onclick={() => onchange(subs.filter((k) => k !== key))}>✕</button>
		</li>
	{/each}
	{#if left.length}
		<li>
			<select aria-label="Add substat" data-testid="sub-add" value=""
				onchange={(e) => { const v = e.currentTarget.value; if (v) onchange([...subs, v]); e.currentTarget.value = ''; }}>
				<option value="">Add substat…</option>
				{#each left as key (key)}<option value={key}>{STAT_LABELS[key]}</option>{/each}
			</select>
		</li>
	{/if}
</ol>

<style>
	.subs { display: flex; flex-wrap: wrap; gap: 6px; list-style: none; padding: 0; margin: 0; }
	.chip { display: inline-flex; align-items: center; gap: 4px; border: 1px solid var(--glass-border); border-radius: 999px; padding: 2px 8px; font-size: 12px; }
	.n { color: var(--el, var(--gold)); font-weight: 700; }
	.chip button { background: none; border: none; color: var(--muted); cursor: pointer; padding: 0 2px; }
</style>
```

- [ ] **Step 4: `BuildArtifacts.svelte`**

```svelte
<script lang="ts">
	import { api } from './api';
	import ArtifactSetPicker from './ArtifactSetPicker.svelte';
	import { emptyTarget, MAIN_SLOTS, setSlot, setsFor, SLOT_OPTIONS, STAT_LABELS, toggleStat } from './artifacts';
	import { getCharacterPage } from './characterPage.svelte';
	import { imgSrc } from './img';
	import StatPills from './StatPills.svelte';
	import SubstatOrder from './SubstatOrder.svelte';
	import type { ArtifactSetOption, ArtifactTarget, MainSlot } from './types';

	let { editing }: { editing: boolean } = $props();
	const p = getCharacterPage();
	const c = $derived(p.c!);
	const loaded = $derived<ArtifactTarget>(c.artifact_target ?? emptyTarget());
	const check = $derived(c.artifact_check);

	let options = $state<ArtifactSetOption[]>([]);
	$effect(() => { api.artifactSets().then((o) => (options = o)).catch(() => (options = [])); });

	// Rapid edits build on the latest unsaved draft (same pattern as the Build page targets).
	let draft: ArtifactTarget | null = null;
	let inflight = $state(0);
	const t = $derived(loaded);
	let modeOverride = $state<4 | 2 | null>(null);
	const mode = $derived<4 | 2>(modeOverride ?? (t.sets.length === 2 || t.sets[0]?.pieces === 2 ? 2 : 4));

	async function save(next: ArtifactTarget) {
		draft = next;
		inflight++;
		try {
			await p.saveGoal({ artifact_target: next });
		} finally {
			if (--inflight === 0) { draft = null; modeOverride = null; }
		}
	}
	const base = () => draft ?? t;
	function setMode(m: 4 | 2) {
		modeOverride = m;
		const cur = base();
		if (cur.sets.length) save({ ...cur, sets: setsFor(m, cur.sets) });
	}
	function pick(index: number, id: number | null) {
		const cur = base();
		save({ ...cur, sets: setSlot(cur.sets, index, id, mode) });
	}
	function toggleMain(slot: MainSlot, key: string) {
		const cur = base();
		save({ ...cur, main: { ...cur.main, [slot]: toggleStat(cur.main[slot], key) } });
	}
	function setSubs(subs: string[]) { save({ ...base(), subs }); }
	function setDone(done: boolean) { p.saveGoal({ artifacts_done: done }); }
	const SLOT_LABEL: Record<string, string> = { flower: 'Flower', plume: 'Plume', sands: 'Sands', goblet: 'Goblet', circlet: 'Circlet' };
</script>

<section class="card span2" data-testid="build-artifacts">
	<h2>Artifacts</h2>
	<fieldset disabled={!editing || inflight > 0}>
		<div class="sets">
			<div class="mode" role="group" aria-label="Set mode">
				<button type="button" class:on={mode === 4} aria-pressed={mode === 4} data-testid="artifact-mode-4" onclick={() => setMode(4)}>4-piece</button>
				<button type="button" class:on={mode === 2} aria-pressed={mode === 2} data-testid="artifact-mode-2" onclick={() => setMode(2)}>2 + 2</button>
			</div>
			<ArtifactSetPicker index={0} {options} value={t.sets[0]?.set_id ?? null} onchange={(id) => pick(0, id)} />
			{#if mode === 2}
				<ArtifactSetPicker index={1} {options} value={t.sets[1]?.set_id ?? null} onchange={(id) => pick(1, id)} />
			{/if}
		</div>

		<h3>Main stats</h3>
		<div class="mains">
			<div class="fixed muted small">Flower HP · Plume ATK</div>
			{#each MAIN_SLOTS as slot (slot)}
				<StatPills {slot} options={SLOT_OPTIONS[slot]} selected={t.main[slot]} onchange={(k) => toggleMain(slot, k)} />
			{/each}
		</div>

		<h3>Substat priority</h3>
		<SubstatOrder subs={t.subs} onchange={setSubs} />
	</fieldset>

	<h3>Equipped</h3>
	<div class="equipped">
		{#each check.slots as s (s.slot)}
			<div class="piece" data-testid="equipped-{s.slot}">
				{#if imgSrc(s.icon)}<img src={imgSrc(s.icon)} alt={s.set_name} />{/if}
				<span class="muted small">{SLOT_LABEL[s.slot] ?? s.slot}</span>
				<span class="small">{s.key ? (STAT_LABELS[s.key] ?? s.main_stat) : s.main_stat}</span>
				{#if s.ok === true}<span class="ok">✓</span>{:else if s.ok === false}<span class="bad">✗</span>{/if}
			</div>
		{/each}
	</div>
	<div class="status">
		<span data-testid="artifact-status">
			{#if check.status === 'met'}Matches target
			{:else if check.status === 'missing'}Missing: {check.missing.join(', ')}
			{:else}No artifact target set{/if}
		</span>
		{#each check.sets as s (s.set_id)}<span class="muted small">{s.name} {s.equipped}/{s.pieces}</span>{/each}
		<label class="done">
			<input type="checkbox" data-testid="artifacts-done" checked={c.artifacts_done} disabled={!editing}
				onchange={(e) => setDone(e.currentTarget.checked)} />
			Artifacts done
		</label>
	</div>
</section>

<style>
	fieldset { border: none; padding: 0; margin: 0; display: flex; flex-direction: column; gap: 10px; }
	.sets { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; }
	.mode { display: flex; gap: 4px; }
	.mode button { border: 1px solid var(--glass-border); background: transparent; color: var(--text); border-radius: 999px; padding: 3px 10px; }
	.mode button.on { background: var(--el, var(--gold)); color: var(--bg); }
	h3 { margin: 6px 0 2px; font-size: 13px; color: var(--muted); }
	.mains { display: flex; flex-direction: column; gap: 6px; }
	.equipped { display: flex; flex-wrap: wrap; gap: 10px; }
	.piece { display: flex; flex-direction: column; align-items: center; gap: 2px; min-width: 64px; }
	.piece img { width: 40px; height: 40px; }
	.ok { color: var(--building); }
	.bad { color: var(--danger, #e06c6c); }
	.status { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-top: 8px; }
	.done { margin-left: auto; display: flex; gap: 6px; align-items: center; }
	.small { font-size: 11px; }
</style>
```

Notes: `inflight` is `$state` so the fieldset disables while saving (spec 6.1). The `draft` is a plain variable on purpose (same as the Build page). `modeOverride` keeps "2 + 2" visible after switching with no set chosen yet; it resets once saves settle and the loaded target shows the mode.

In `build/+page.svelte` change `<BuildArtifacts />` to `<BuildArtifacts {editing} />`.

- [ ] **Step 5: Verify**

Run (from `frontend/`): `npm run check` → 0 errors and 0 warnings; `npx vitest run` → PASS; `npm run build` → ok. Start the seeded dev server the way earlier sub-projects did (see `frontend/playwright.config.ts` webServer command) and open `/characters/furina/build`: picker shows Noblesse + Gladiator in 2 + 2, the status reads "Missing: …", toggling a pill saves.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/BuildArtifacts.svelte frontend/src/lib/ArtifactSetPicker.svelte frontend/src/lib/StatPills.svelte frontend/src/lib/SubstatOrder.svelte "frontend/src/routes/characters/[slug]/build/+page.svelte"
git commit -m "feat(build): artifact set, main stat and substat targets with equipped check"
```

---

### Task 9: Dashboard Artifact domains section

**Files:**
- Create: `frontend/src/lib/dashboard/ArtifactDomains.svelte`
- Modify: `frontend/src/routes/+page.svelte` (replace the `<!-- Sub-project 8 … -->` comment), `frontend/src/lib/dashboard/DomainDays.svelte` (remove `.image` div and its CSS rule)

**Interfaces:**
- Consumes: `Dashboard.artifact_domains: ArtifactDomainsView` (Task 7), `imgSrc`, element icons via `/api/img` names `UI_Buff_Element_<Fire|Water|Electric|Ice|Wind|Rock|Grass>` (check `frontend/src/lib/elements.ts` for an existing name helper and use it).
- Produces: test ids `artifact-domains`, `artifact-domain-<id>`, `artifact-set-row-<setId>` (inside a card), `artifact-other`, `artifact-hint`.

- [ ] **Step 1: Write the component**

```svelte
<!-- frontend/src/lib/dashboard/ArtifactDomains.svelte -->
<script lang="ts">
	import { imgSrc } from '$lib/img';
	import type { ArtifactDomainsView, ArtifactSetRow } from '$lib/types';

	let { view }: { view: ArtifactDomainsView } = $props();
	const shown = $derived(view.domains.length > 0 || view.other.length > 0 || view.hint !== null);
</script>

{#snippet setRow(s: ArtifactSetRow)}
	{#if s.needed}
		<div class="set-row" data-testid="artifact-set-row-{s.id}">
			<div class="set-name">{s.name}</div>
			<div class="avatars">
				{#each s.characters as c (c.id)}
					<a href="/characters/{c.slug}/build" title="{c.name} · {c.pieces}pc · {c.equipped}/{c.pieces} equipped">
						{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt={c.name} />{/if}
						<span class="hint">{c.pieces}pc · {c.equipped}/{c.pieces}</span>
					</a>
				{/each}
			</div>
		</div>
	{/if}
{/snippet}

{#if shown}
	<section class="panel" data-testid="artifact-domains">
		<h2>Artifact domains</h2>
		{#if view.hint}
			<p class="muted" data-testid="artifact-hint">{view.hint}</p>
		{/if}
		<div class="cards">
			{#each view.domains as d (d.id)}
				<div class="card" data-testid="artifact-domain-{d.id}">
					<div class="art">
						{#each d.sets as s (s.id)}
							<div class="set-icon" class:dim={!s.needed} title={s.name}>
								{#if imgSrc(s.icon)}<img src={imgSrc(s.icon)} alt={s.name} />{/if}
							</div>
						{/each}
					</div>
					<div class="title">{d.entrance}</div>
					<div class="muted small">{d.region ?? ''}{d.elements.length ? ` · ${d.elements.join(', ')}` : ''}</div>
					{#each d.sets as s (s.id)}{@render setRow(s)}{/each}
				</div>
			{/each}
			{#if view.other.length}
				<div class="card" data-testid="artifact-other">
					<div class="title">Not from a domain</div>
					<div class="muted small">Bosses / Strongbox</div>
					{#each view.other as s (s.id)}{@render setRow(s)}{/each}
				</div>
			{/if}
		</div>
	</section>
{/if}

<style>
	.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; margin-top: 10px; }
	.card { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
	.art { display: flex; gap: 8px; justify-content: center; padding: 6px; border-radius: 8px;
		background: linear-gradient(135deg, var(--panel), var(--panel-2)); margin-bottom: 6px; }
	.set-icon img { width: 72px; height: 72px; display: block; }
	.set-icon.dim { opacity: 0.3; filter: grayscale(1); }
	.title { font-weight: 600; }
	.small { font-size: 11px; }
	.set-row { margin-top: 8px; }
	.set-name { font-size: 12px; }
	.avatars { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 4px; }
	.avatars a { display: flex; flex-direction: column; align-items: center; text-decoration: none; color: var(--muted); }
	.avatars img { width: 28px; height: 28px; border-radius: 50%; background: var(--r0); }
	.hint { font-size: 10px; }
</style>
```

Element icons: `frontend/src/lib/elements.ts` exports `elementStyle(name) -> { color, icon }`. Replace the `d.elements.join(', ')` text with one 16px icon per element (`{#each d.elements as el (el)}{#if imgSrc(elementStyle(el).icon)}<img class="el" src={imgSrc(elementStyle(el).icon)} alt={el} title={el} />{/if}{/each}`), keeping the region text before them; add `.el { width: 16px; height: 16px; vertical-align: middle; }`.

- [ ] **Step 2: Wire it in**

In `frontend/src/routes/+page.svelte` import `ArtifactDomains` and replace the comment line with:

```svelte
			<ArtifactDomains view={data.artifact_domains} />
```

In `frontend/src/lib/dashboard/DomainDays.svelte` delete `<div class="image" aria-hidden="true"></div>` and the `.image { … }` style rule.

- [ ] **Step 3: Verify**

`npm run check` → 0/0; `npm run build` → ok; on the seeded dev server `/` shows "Artifact domains" between Weekly bosses and Building with the Stone Chamber card (Bloodstained lit with Neuvillette, Noblesse lit with Furina) and the "Not from a domain" card with Gladiator's Finale.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/lib/dashboard/ArtifactDomains.svelte frontend/src/routes/+page.svelte frontend/src/lib/dashboard/DomainDays.svelte
git commit -m "feat(dashboard): artifact domains section with set-icon art"
```

---

### Task 10: End-to-end tests

**Files:**
- Create: `frontend/e2e/artifacts.spec.ts`
- Modify: `frontend/e2e/characters.spec.ts` (line ~151), `frontend/e2e/dashboard.spec.ts` (section list)

**Interfaces:**
- Consumes: seed data (Task 6), test ids (Tasks 8–9).

- [ ] **Step 1: Write the tests**

```ts
// frontend/e2e/artifacts.spec.ts
import { expect, test } from '@playwright/test';

type Goal = { artifact_target: unknown; artifacts_done: boolean };

async function snapshot(page: import('@playwright/test').Page, slug: string): Promise<Goal & { id: number }> {
	const c = await (await page.request.get(`/api/characters/${slug}`)).json();
	return { id: c.id, artifact_target: c.artifact_target, artifacts_done: c.artifacts_done };
}

async function restore(page: import('@playwright/test').Page, g: Goal & { id: number }) {
	await page.request.put(`/api/characters/${g.id}/goal`,
		{ data: { artifact_target: g.artifact_target, artifacts_done: g.artifacts_done } });
}

test('Build tab sets a 4-piece target and main stats', async ({ page }) => {
	const original = await snapshot(page, 'furina');
	try {
		await page.goto('/characters/furina/build');
		const card = page.getByTestId('build-artifacts');
		await expect(card.getByTestId('artifact-set-0')).toHaveValue('15007');
		await expect(card.getByTestId('artifact-set-1')).toHaveValue('15001');
		await card.getByTestId('artifact-mode-4').click();
		await expect(card.getByTestId('artifact-set-1')).toHaveCount(0);
		await card.getByTestId('artifact-set-0').selectOption('15008');
		await card.getByTestId('stat-goblet-pyro').locator('button').click();      // no wait: builds on the draft
		await expect(card.getByTestId('artifact-source-0')).toHaveText('Clear Pool and Mountain Cavern');
		await expect(card.getByTestId('stat-goblet-pyro').locator('button')).toHaveAttribute('aria-pressed', 'true');
		await expect(card.getByTestId('stat-goblet-hydro').locator('button')).toHaveAttribute('aria-pressed', 'true');
		await expect(card.getByTestId('artifact-status')).toContainText('4pc Bloodstained Chivalry (0/4)');
		await card.getByTestId('sub-add').selectOption('em');
		await expect(card.getByTestId('sub-em')).toContainText('5');
		await card.getByTestId('sub-up-em').click();
		await expect(card.getByTestId('sub-em')).toContainText('4');
		await page.reload();
		await expect(page.getByTestId('artifact-set-0')).toHaveValue('15008');
	} finally {
		await restore(page, original);
	}
});

test('Dashboard lists the domain and Artifacts done removes the character', async ({ page }) => {
	const original = await snapshot(page, 'furina');
	try {
		await page.goto('/');
		const section = page.getByTestId('artifact-domains');
		await expect(section).toBeVisible();
		const card = section.getByTestId('artifact-domain-5101');
		await expect(card).toContainText('Clear Pool and Mountain Cavern');
		await expect(card.getByTestId('artifact-set-row-15007').getByRole('link')).toHaveAttribute('href', '/characters/furina/build');
		await expect(card.getByTestId('artifact-set-row-15008').getByRole('link')).toHaveAttribute('href', '/characters/neuvillette/build');
		await expect(section.getByTestId('artifact-other')).toContainText("Gladiator's Finale");
		await expect(section.locator('a[href="/characters/bennett/build"]')).toHaveCount(0);   // ticked done

		await page.goto('/characters/furina/build');
		await page.getByTestId('artifacts-done').check();
		await expect(page.getByTestId('artifacts-done')).toBeChecked();
		await page.goto('/');
		await expect(page.getByTestId('artifact-set-row-15007')).toHaveCount(0);
		await expect(page.getByTestId('artifact-other')).toHaveCount(0);
		await expect(page.getByTestId('artifact-set-row-15008')).toBeVisible();      // Neuvillette still needs it
	} finally {
		await restore(page, original);
	}
});
```

In `frontend/e2e/characters.spec.ts` replace
`await expect(page.getByTestId('build-artifacts-slot')).toContainText('sub-project 8');`
with
`await expect(page.getByTestId('build-artifacts')).toContainText('Substat priority');`.

In `frontend/e2e/dashboard.spec.ts` add `'artifact-domains'` to the id list in the first test, between `'weekly-bosses'` and `'builds'`.

- [ ] **Step 2: Run**

From `frontend/`: `PYTHON=PY npx playwright test e2e/artifacts.spec.ts e2e/characters.spec.ts e2e/dashboard.spec.ts` → PASS. Then the full suite: `PYTHON=PY npx playwright test` → all pass (62 + 2).

- [ ] **Step 3: Commit**

```bash
git add frontend/e2e/artifacts.spec.ts frontend/e2e/characters.spec.ts frontend/e2e/dashboard.spec.ts
git commit -m "test(e2e): artifact targets on Build and the Dashboard artifact domains"
```

---

### Task 11: Full verification

- [ ] **Step 1:** From `backend/`: `PY -m pytest -q` → all pass (642 + new).
- [ ] **Step 2:** From `frontend/`: `npm run check` (0 errors, 0 warnings), `npx vitest run`, `npm run build`, `PYTHON=PY npx playwright test` → all pass.
- [ ] **Step 3:** Sensitive-content scan of the branch diff: `git diff main --stat` and `git diff main | grep -niE "cookie|ltoken|ltuid|password|@gmail|users[/\\\\]"` → only expected code identifiers (e.g. existing `cookie` words in unchanged context), no values, no absolute user paths.
- [ ] **Step 4:** Confirm the spec's Done-when list (section 11) item by item and note any gap in the ledger.

---

## Self-review notes

- Spec coverage: §3.1 → Task 1; §3.2 → Task 4 (validation) + Task 1 (storage); §3.3 → Task 2; §4 → Tasks 3–4; §5 → Tasks 4–5; §6.1 → Task 8; §6.2 → Tasks 5, 9; §6.3 → Tasks 7–9; §7 errors → Tasks 2, 3, 4, 8; §9 testing → every task; Settings status line → Task 2.
- Names used across tasks: `check_for(s, cid, target)`, `sets_by_id(s)`, `group_artifact_domains(builds, sets, domains)`, `artifact_domains_view(s)`, `refresh_artifact_domains(...)`, `ArtifactTargetIn`, `GoalBody`, `ArtifactDomainsView`.
