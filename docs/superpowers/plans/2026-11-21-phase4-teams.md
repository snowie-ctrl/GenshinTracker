# Phase 4 — Teams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user group characters into teams with free-form tags, where the built-in **Build** tag raises members' goals to `build` and each team shows what is still left to farm to finish it.

**Architecture:** A new database-only package `backend/app/teams/`: `goals.py` (the only place teams change goals), `artifacts.py` (artifact set line), `store.py` (team and tag writes, validation, one transaction per write), `shortfall.py` (team-first shortfall from the existing `PlannerData` plus the existing crafting rollup), and `view.py` (API payloads). `api/teams.py` exposes teams and tags; `api/characters.py` and `api/dashboard.py` gain team fields. The SvelteKit frontend gets a Teams page, a team editor, a Dashboard card, a Characters tag filter, and an In teams panel. No HoYoLAB calls are added.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, SQLite, pytest; SvelteKit (Svelte 5 runes, TypeScript, adapter-static), Vitest, Playwright.

**Spec:** [docs/superpowers/specs/2026-11-21-phase4-teams-design.md](../specs/2026-11-21-phase4-teams-design.md)

**Where to work:** a git worktree on branch `phase4-teams` (user preference for multi-commit work). No `.env` or `data/` is needed: every test runs on fake data.

## Global Constraints

- `backend/app/teams/` makes **no network calls** and never imports from `app.sync` or `app.wishes`. HoYoLAB access stays in `sync/` and `wishes/`.
- Teams change goals **only** through `app.teams.goals.raise_to_build`, and only (1) when a team gains the Build tag (all members) or (2) when a Build-tagged team gains a member (that member). Nothing a team does lowers a goal.
- Built-in tag: `id = 1`, name `Build`, `builtin = true`, created by migration `0004`; rename/delete → `409` with the message `Build is a built-in tag`.
- Limits: team name 1–60 chars (stripped), notes ≤ 2000 chars, role ≤ 40 chars, tag name 1–30 chars (stripped), 1–4 members per team, a character at most once per team.
- Tag names are unique case-insensitively (stored as typed, compared through `name_key = name.lower()`).
- Tag colours are tokens from `TAG_COLORS = ("orange", "red", "yellow", "green", "teal", "blue", "purple", "pink")`; new tags take `TAG_COLORS[tag_count % 8]`.
- Every new table goes through Alembic migration `0004`; `test_models_match_migrations` must stay green.
- Member character ids are canonical (`app.gamedata.yatta.canonical_id`): Traveler variants → `10000005`, Manekin/Manekina → `10000117`.
- Every team write (team, members, tags, new tags, goal raises) is **one transaction**: all or nothing.
- After a write that raised any goal, the API calls `ctx.sync.schedule_gaps()` from an `async def` handler (it needs the running event loop).
- Test fixtures and the dev seed use made-up data only (UID `800000001`). No cookie values, UID, nickname, or game art in the repository.
- `localStorage` access is always wrapped in try/catch.
- Copy texts (use exactly):
  - `Build is a built-in tag`
  - `A tag with that name exists`
  - `A team needs 1 to 4 members`
  - `A character can be in a team only once`
  - `Team not found` / `Tag not found`
  - `The order must list every team once`
  - Frontend: `Raised 1 character to Build` / `Raised N characters to Build`, `Everything in the bag ✓`, `Shortfall appears after the next sync`, `Connect HoYoLAB to calculate`, `Make your first team`, `Tag a team Build to plan it here`, `Not in any team`, `This team no longer exists`.
- Commands (PowerShell, from the worktree root): backend tests `cd backend; ..\.venv\Scripts\python -m pytest -q`; frontend `cd frontend; npm run check; npm test; npm run e2e`.

### Refinements made while planning (to be added to the spec as §13 in Task 11)

1. Tags get a `name_key` column (lower-cased name, unique) to enforce case-insensitive uniqueness portably.
2. Notes are capped at 2000 characters (the spec gave no cap).
3. When the editor's typed new tag matches an existing tag case-insensitively, the existing tag is reused instead of failing with `409`.
4. Member ids are validated on save, so an unknown member can only appear if the catalogue later drops a character; it renders as a placeholder, and no extra game-data refresh is triggered (sync already refreshes on unknown owned ids).
5. `GET /api/teams` returns `{gaps, connected, teams}` and `GET /api/teams/{id}` returns `{gaps, connected, team}`; tag filtering happens in the page.
6. The Characters page filters are not persisted today, so the Team tag filter is not persisted either (consistent with the other Characters filters).

## Review Focus

1. **Re-saving an unchanged Build team after the user lowered a member's goal** → the lowered member stays lowered (only newly added members are raised). Test in Task 3 (`test_build_team_gaining_member_raises_only_that_member`).
2. **Typing a new tag "Abyss" when "abyss" exists** → the team saves with the existing tag; no duplicate tag, no error. Test in Task 3 (`test_new_tag_reuses_existing_case_insensitively`).
3. **Removing the second of three members and saving** → remaining members sit in slots 0 and 1 in their order. Test in Task 3 (`test_slots_are_contiguous_after_removal`).
4. **A member just raised to Build but not yet calculated** → shown as Not calculated and left out of the team shortfall, never shown as "Everything in the bag ✓". Tests in Task 4 (`test_not_calculated_members_contribute_nothing`) and Task 5 (`test_newly_raised_member_is_not_calculated`).
5. **Reordering while another tab deleted a team** → `422` with `The order must list every team once`; the page reverts. Test in Task 3 (`test_reorder_requires_every_team_once`) and Task 5 (`test_reorder_endpoint`).

---

## File Structure

**Backend — new**

| File | Responsibility |
|---|---|
| `backend/migrations/versions/0004_teams.py` | `team`, `team_member`, `tag`, `team_tag`; inserts the Build tag |
| `backend/app/teams/__init__.py` | Package marker |
| `backend/app/teams/goals.py` | `raise_to_build` |
| `backend/app/teams/artifacts.py` | `set_line` |
| `backend/app/teams/store.py` | Team/tag writes, validation, ordering, reads (`team_rows`, `memberships`, `list_tags`) |
| `backend/app/teams/shortfall.py` | `team_totals`, `team_shortfall`, `team_progress` |
| `backend/app/teams/view.py` | `member_view`, `team_view`, `build_team_cards` |
| `backend/app/api/teams.py` | Teams and tags endpoints; `team_views` used by the Dashboard |
| `backend/tests/test_teams_goals.py`, `test_teams_store.py`, `test_teams_shortfall.py`, `test_api_teams.py` | Tests |

**Backend — modified**

| File | Change |
|---|---|
| `backend/app/db/models.py` | `Team`, `TeamMember`, `Tag`, `TeamTag` |
| `backend/app/api/__init__.py` | Register `teams.router` |
| `backend/app/api/characters.py` | `team_tags` in the list, `teams` in the detail |
| `backend/app/api/dashboard.py` | `build_teams` |
| `backend/app/devseed.py` | Two demo teams and an `abyss` tag |
| `backend/tests/test_db.py`, `test_devseed.py`, `test_api_settings.py` | Schema, seed, leak-test additions |

**Frontend — new**

| File | Responsibility |
|---|---|
| `frontend/src/lib/teams.ts` (+ `teams.test.ts`) | Filters, slot helpers, raise preview, tile view, text helpers |
| `frontend/src/lib/TagChip.svelte` | Coloured tag chip |
| `frontend/src/lib/TeamCard.svelte` | One team card with members and shortfall panel |
| `frontend/src/lib/TagManager.svelte` | Manage tags panel |
| `frontend/src/lib/TeamEditor.svelte` | Editor used by the two editor routes |
| `frontend/src/routes/teams/+page.svelte` | Teams page |
| `frontend/src/routes/teams/new/+page.svelte`, `frontend/src/routes/teams/[id]/+page.svelte` | Editor routes |
| `frontend/e2e/teams.spec.ts` | End-to-end flow |

**Frontend — modified:** `src/lib/types.ts`, `src/lib/api.ts`, `src/lib/status.ts` (+ `status.test.ts`), `src/routes/+layout.svelte`, `src/routes/+page.svelte`, `src/routes/characters/+page.svelte`, `src/routes/characters/[slug]/+page.svelte`. Docs: `README.md`, spec §13.

---

### Task 1: Schema (migration 0004 and models)

**Files:**
- Create: `backend/migrations/versions/0004_teams.py`
- Modify: `backend/app/db/models.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces: models `Team(id, name, notes, sort_order, created_at, updated_at)`, `TeamMember(team_id, slot, character_id, role)`, `Tag(id, name, name_key, color, builtin)`, `TeamTag(team_id, tag_id)`; the Build tag row `id=1`.

- [ ] **Step 1: Write the failing tests** — append to `backend/tests/test_db.py`:

```python
def test_phase4_tables_and_build_tag(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    insp = inspect(engine)
    assert {"team", "team_member", "tag", "team_tag"} <= set(insp.get_table_names())
    with engine.connect() as conn:
        row = conn.exec_driver_sql("SELECT id, name, name_key, color, builtin FROM tag").one()
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
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_db.py -q`
Expected: FAIL (`team` table missing / ImportError for `Team`).

- [ ] **Step 3: Add the models** — in `backend/app/db/models.py` change the import line to include `ForeignKey`:

```python
from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
```

and add after `WeeklyBossDone`:

```python
class Team(Base):
    __tablename__ = "team"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    notes: Mapped[str] = mapped_column(String)
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class TeamMember(Base):
    __tablename__ = "team_member"
    __table_args__ = (UniqueConstraint("team_id", "character_id", name="uq_team_member_character"),)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id", ondelete="CASCADE"), primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)                 # 0-3, contiguous
    character_id: Mapped[int] = mapped_column(Integer)                           # canonical id
    role: Mapped[str] = mapped_column(String)


class Tag(Base):
    __tablename__ = "tag"
    __table_args__ = (UniqueConstraint("name_key", name="uq_tag_name_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    name_key: Mapped[str] = mapped_column(String)                                # name.lower()
    color: Mapped[str] = mapped_column(String)
    builtin: Mapped[bool] = mapped_column(Boolean)


class TeamTag(Base):
    __tablename__ = "team_tag"
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True)
```

- [ ] **Step 4: Write the migration** — `backend/migrations/versions/0004_teams.py`:

```python
"""phase 4 teams

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "team",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("notes", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "team_member",
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("team.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("slot", sa.Integer(), primary_key=True),
        sa.Column("character_id", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(), nullable=False),
        sa.UniqueConstraint("team_id", "character_id", name="uq_team_member_character"),
    )
    tag = op.create_table(
        "tag",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("name_key", sa.String(), nullable=False),
        sa.Column("color", sa.String(), nullable=False),
        sa.Column("builtin", sa.Boolean(), nullable=False),
        sa.UniqueConstraint("name_key", name="uq_tag_name_key"),
    )
    op.create_table(
        "team_tag",
        sa.Column("team_id", sa.Integer(), sa.ForeignKey("team.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("tag_id", sa.Integer(), sa.ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True),
    )
    op.bulk_insert(tag, [{"id": 1, "name": "Build", "name_key": "build", "color": "orange", "builtin": True}])


def downgrade() -> None:
    op.drop_table("team_tag")
    op.drop_table("tag")
    op.drop_table("team_member")
    op.drop_table("team")
```

- [ ] **Step 5: Run the whole db test file**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_db.py -q`
Expected: all PASS, including `test_models_match_migrations`. If `compare_metadata` reports a nullable or FK difference, align the model with the migration (models must declare the same `ForeignKey(..., ondelete="CASCADE")` and constraint names).

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/versions/0004_teams.py backend/app/db/models.py backend/tests/test_db.py
git commit -m "feat(teams): team, member, tag tables with the built-in Build tag"
```

---

### Task 2: Goal raising and the artifact set line

**Files:**
- Create: `backend/app/teams/__init__.py` (empty docstring `"""Teams: user-defined groups of characters with tags."""`), `backend/app/teams/goals.py`, `backend/app/teams/artifacts.py`
- Test: `backend/tests/test_teams_goals.py`

**Interfaces:**
- Consumes: `CharacterGoal` (models), `Targets`, `resolve_targets` (`app.domain`).
- Produces: `raise_to_build(session: Session, character_ids: Iterable[int], defaults: Targets) -> list[int]`; `set_line(set_names: list[str]) -> str`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_teams_goals.py`:

```python
from datetime import datetime

from app.db.models import CharacterGoal
from app.domain import Targets
from app.teams.artifacts import set_line
from app.teams.goals import raise_to_build

DEFAULTS = Targets(90, 8, 8, 8, 90)
NOW = datetime(2026, 11, 21)


def add_goal(s, cid, goal, targets=None):
    t = targets or (None, None, None, None, None)
    s.add(CharacterGoal(character_id=cid, goal=goal, target_level=t[0], target_normal=t[1], target_skill=t[2],
                        target_burst=t[3], target_weapon_level=t[4], updated_at=NOW))


def test_raise_none_want_and_missing_rows(session_factory):
    with session_factory.begin() as s:
        add_goal(s, 1, "none")
        add_goal(s, 2, "want")
        add_goal(s, 3, "build", (80, 6, 6, 6, 80))
    with session_factory.begin() as s:
        raised = raise_to_build(s, [1, 2, 3, 4, 1], DEFAULTS)
    assert raised == [1, 2, 4]
    with session_factory() as s:
        assert {cid: s.get(CharacterGoal, cid).goal for cid in (1, 2, 3, 4)} == dict.fromkeys((1, 2, 3, 4), "build")
        three = s.get(CharacterGoal, 3)
        assert (three.target_level, three.target_normal) == (80, 6)          # untouched
        four = s.get(CharacterGoal, 4)
        assert (four.target_level, four.target_skill, four.target_weapon_level) == (90, 8, 90)


def test_raise_restores_stored_targets(session_factory):
    with session_factory.begin() as s:
        add_goal(s, 1, "want", (70, 9, 9, 9, 70))
    with session_factory.begin() as s:
        assert raise_to_build(s, [1], DEFAULTS) == [1]
    with session_factory() as s:
        row = s.get(CharacterGoal, 1)
        assert (row.goal, row.target_level, row.target_burst) == ("build", 70, 9)


def test_raise_nothing():
    assert raise_to_build(None, [], DEFAULTS) == []


def test_set_line():
    assert set_line(["A", "A", "A", "A", "B"]) == "4pc A"
    assert set_line(["A"] * 5) == "4pc A"
    assert set_line(["A", "A", "B", "B"]) == "2pc A + 2pc B"
    assert set_line(["B", "B", "A", "A", "C"]) == "2pc A + 2pc B"
    assert set_line(["B", "B", "B", "A", "A"]) == "2pc B + 2pc A"
    assert set_line(["A", "B", "C", "D", "E"]) == ""
    assert set_line([]) == ""
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_teams_goals.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.teams'`.

- [ ] **Step 3: Implement** — `backend/app/teams/goals.py`:

```python
"""The only place teams change goals. Goals are only ever raised to build, never lowered."""
from __future__ import annotations

from collections.abc import Iterable

from sqlalchemy.orm import Session

from app.db.models import CharacterGoal
from app.domain import Targets, resolve_targets
from app.timeutil import utcnow


def _stored(row: CharacterGoal) -> Targets | None:
    if row.target_level is None:
        return None
    return Targets(row.target_level, row.target_normal, row.target_skill, row.target_burst,
                   row.target_weapon_level)


def raise_to_build(session: Session, character_ids: Iterable[int], defaults: Targets) -> list[int]:
    """Set goal build for every id whose goal is none/want (no row = none). Returns the ids changed."""
    raised: list[int] = []
    for cid in dict.fromkeys(character_ids):
        row = session.get(CharacterGoal, cid)
        if row is None:
            row = CharacterGoal(character_id=cid, goal="none", updated_at=utcnow())
            session.add(row)
        if row.goal == "build":
            continue
        targets = resolve_targets("build", _stored(row), defaults)
        row.goal = "build"
        row.target_level, row.target_normal = targets.level, targets.normal
        row.target_skill, row.target_burst = targets.skill, targets.burst
        row.target_weapon_level = targets.weapon_level
        row.updated_at = utcnow()
        raised.append(cid)
    if raised:
        session.flush()
    return raised
```

`backend/app/teams/artifacts.py`:

```python
"""One short line describing the artifact sets a character wears."""
from __future__ import annotations

from collections import Counter


def set_line(set_names: list[str]) -> str:
    counts = Counter(n for n in set_names if n)
    four = sorted(n for n, c in counts.items() if c >= 4)
    if four:
        return f"4pc {four[0]}"
    twos = sorted((n for n, c in counts.items() if c >= 2), key=lambda n: (-counts[n], n))
    return " + ".join(f"2pc {n}" for n in twos)
```

- [ ] **Step 4: Run tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_teams_goals.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/teams backend/tests/test_teams_goals.py
git commit -m "feat(teams): raise goals to build and describe artifact sets"
```

---

### Task 3: Team and tag store

**Files:**
- Create: `backend/app/teams/store.py`
- Test: `backend/tests/test_teams_store.py`

**Interfaces:**
- Consumes: `raise_to_build` (Task 2), models (Task 1), `default_targets(session)` (`app.settings.store`), `canonical_id` (`app.gamedata.yatta`), `utcnow` (`app.timeutil`).
- Produces (all take an open `Session`; callers own the transaction):
  - `BUILD_TAG_ID = 1`, `TAG_COLORS: tuple[str, ...]`
  - `class TeamError(Exception)` with `.status: int` and `.message: str`
  - `@dataclass(frozen=True) class MemberIn: character_id: int; role: str = ""`
  - `save_team(s, team_id: int | None, name: str, notes: str, members: list[MemberIn], tag_ids: list[int], new_tags: list[str]) -> tuple[Team, list[int]]` (team, raised ids)
  - `delete_team(s, team_id: int) -> None`
  - `reorder(s, ids: list[int]) -> None`
  - `create_tag(s, name: str, color: str | None = None) -> Tag`, `update_tag(s, tag_id: int, name: str | None, color: str | None) -> Tag`, `delete_tag(s, tag_id: int) -> None`
  - `tag_dict(t: Tag) -> dict` → `{"id", "name", "color", "builtin"}`
  - `list_tags(s) -> list[dict]` → tag dicts plus `team_count`, Build first then by name
  - `team_rows(s) -> list[tuple[Team, list[TeamMember], list[Tag]]]` ordered by `sort_order, id`; members by slot; tags Build first then by name
  - `memberships(s) -> dict[int, list[dict]]` → per character id: `[{"id", "name", "tags": [tag dicts]}]` in team order

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_teams_store.py`:

```python
import pytest
from sqlalchemy import func, select

from app.db.models import CharacterGoal, Tag, Team, TeamMember
from app.teams import store
from app.teams.store import BUILD_TAG_ID, MemberIn, TeamError
from helpers import seed_game

BEN, FUR, XL, NAH = 10000032, 10000089, 10000023, 10000073


@pytest.fixture
def sf(session_factory):
    seed_game(session_factory)
    return session_factory


def save(sf, team_id=None, members=(BEN,), tags=(), new_tags=(), name="Team", notes="", roles=None):
    roles = roles or {}
    with sf.begin() as s:
        team, raised = store.save_team(s, team_id, name, notes,
                                       [MemberIn(c, roles.get(c, "")) for c in members], list(tags), list(new_tags))
        return team.id, raised


def goals(sf, *ids):
    with sf() as s:
        return [(s.get(CharacterGoal, i).goal if s.get(CharacterGoal, i) else "none") for i in ids]


def set_goal(sf, cid, goal):
    from datetime import datetime
    with sf.begin() as s:
        row = s.get(CharacterGoal, cid) or CharacterGoal(character_id=cid, goal=goal, updated_at=datetime(2026, 1, 1))
        row.goal = goal
        s.add(row)


def members_of(sf, team_id):
    with sf() as s:
        return [(m.slot, m.character_id, m.role) for m in
                s.scalars(select(TeamMember).where(TeamMember.team_id == team_id).order_by(TeamMember.slot))]


def test_create_without_build_changes_no_goals(sf):
    tid, raised = save(sf, members=(BEN, FUR), roles={FUR: "driver"})
    assert raised == []
    assert goals(sf, BEN, FUR) == ["none", "none"]
    assert members_of(sf, tid) == [(0, BEN, ""), (1, FUR, "driver")]


def test_adding_build_raises_all_members(sf):
    set_goal(sf, FUR, "build")
    tid, _ = save(sf, members=(BEN, FUR))
    _, raised = save(sf, tid, members=(BEN, FUR), tags=(BUILD_TAG_ID,))
    assert raised == [BEN]
    assert goals(sf, BEN, FUR) == ["build", "build"]


def test_build_team_gaining_member_raises_only_that_member(sf):
    tid, raised = save(sf, members=(BEN, FUR), tags=(BUILD_TAG_ID,))
    assert raised == [BEN, FUR]
    set_goal(sf, FUR, "want")                                   # the user lowers Furina elsewhere
    _, raised = save(sf, tid, members=(BEN, FUR), tags=(BUILD_TAG_ID,))
    assert raised == [] and goals(sf, FUR) == ["want"]          # unchanged re-save keeps the drift
    _, raised = save(sf, tid, members=(BEN, FUR, XL), tags=(BUILD_TAG_ID,))
    assert raised == [XL] and goals(sf, FUR, XL) == ["want", "build"]


def test_removals_change_no_goals(sf):
    tid, _ = save(sf, members=(BEN, FUR), tags=(BUILD_TAG_ID,))
    save(sf, tid, members=(BEN,), tags=())                      # remove the tag and a member
    with sf.begin() as s:
        store.delete_team(s, tid)
    assert goals(sf, BEN, FUR) == ["build", "build"]


def test_validation(sf):
    cases = [
        dict(members=()), dict(members=(BEN, FUR, XL, NAH, 10000005)), dict(members=(BEN, BEN)),
        dict(members=(424242,)), dict(name="   "), dict(name="x" * 61), dict(notes="x" * 2001),
        dict(roles={BEN: "x" * 41}), dict(tags=(999,)),
    ]
    for case in cases:
        with pytest.raises(TeamError) as e:
            save(sf, **case)
        assert e.value.status == 422, case
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(Team)) == 0
    with pytest.raises(TeamError) as e:
        save(sf, team_id=77)
    assert e.value.status == 404 and e.value.message == "Team not found"


def test_traveler_variant_is_stored_canonically(sf):
    tid, _ = save(sf, members=(10000007,))
    assert members_of(sf, tid) == [(0, 10000005, "")]


def test_new_tag_reuses_existing_case_insensitively(sf):
    with sf.begin() as s:
        abyss = store.create_tag(s, "abyss").id
    tid, _ = save(sf, new_tags=("Abyss", "fun", "FUN"))
    with sf() as s:
        names = [t.name for t in s.scalars(select(Tag).order_by(Tag.id))]
        tag_ids = [t.id for t in store.team_rows(s)[0][2]]
    assert names == ["Build", "abyss", "fun"]
    assert abyss in tag_ids and len(tag_ids) == 2


def test_slots_are_contiguous_after_removal(sf):
    tid, _ = save(sf, members=(BEN, FUR, XL))
    save(sf, tid, members=(BEN, XL))
    assert members_of(sf, tid) == [(0, BEN, ""), (1, XL, "")]


def test_new_teams_go_first_and_reorder(sf):
    a, _ = save(sf, name="A")
    b, _ = save(sf, name="B")
    with sf() as s:
        assert [t.name for t, _m, _t in store.team_rows(s)] == ["B", "A"]
    with sf.begin() as s:
        store.reorder(s, [a, b])
    with sf() as s:
        assert [t.name for t, _m, _t in store.team_rows(s)] == ["A", "B"]


def test_reorder_requires_every_team_once(sf):
    a, _ = save(sf, name="A")
    b, _ = save(sf, name="B")
    for ids in ([a], [a, b, 99], [a, a]):
        with pytest.raises(TeamError) as e:
            with sf.begin() as s:
                store.reorder(s, ids)
        assert e.value.status == 422 and e.value.message == "The order must list every team once"


def test_tags(sf):
    with sf.begin() as s:
        fun = store.create_tag(s, " fun ")
        assert fun.name == "fun"
    with pytest.raises(TeamError) as e:
        with sf.begin() as s:
            store.create_tag(s, "FUN")
    assert (e.value.status, e.value.message) == (409, "A tag with that name exists")
    with pytest.raises(TeamError) as e:
        with sf.begin() as s:
            store.create_tag(s, "x", color="black")
    assert e.value.status == 422
    for call in (lambda s: store.update_tag(s, BUILD_TAG_ID, "Farm", None), lambda s: store.delete_tag(s, BUILD_TAG_ID)):
        with pytest.raises(TeamError) as e:
            with sf.begin() as s:
                call(s)
        assert (e.value.status, e.value.message) == (409, "Build is a built-in tag")
    with sf.begin() as s:
        assert store.update_tag(s, BUILD_TAG_ID, None, "blue").color == "blue"
        assert store.update_tag(s, BUILD_TAG_ID, "Build", None).name == "Build"   # same name is not a rename
    tid, _ = save(sf, tags=(fun.id,))
    with sf() as s:
        listed = store.list_tags(s)
    assert [(t["name"], t["team_count"]) for t in listed] == [("Build", 0), ("fun", 1)]
    with sf.begin() as s:
        store.delete_tag(s, fun.id)
    with sf() as s:
        assert store.team_rows(s)[0][2] == []
    with pytest.raises(TeamError) as e:
        with sf.begin() as s:
            store.delete_tag(s, 12345)
    assert (e.value.status, e.value.message) == (404, "Tag not found")


def test_new_tag_colours_cycle(sf):
    with sf.begin() as s:
        colours = [store.create_tag(s, f"t{i}").color for i in range(3)]
    # Build is tag #1, so the next three tags take palette positions 1, 2, 3.
    assert colours == list(store.TAG_COLORS[1:4])


def test_memberships(sf):
    tid, _ = save(sf, name="Abyss", members=(BEN, FUR), tags=(BUILD_TAG_ID,))
    with sf() as s:
        m = store.memberships(s)
    assert m[BEN] == [{"id": tid, "name": "Abyss",
                       "tags": [{"id": 1, "name": "Build", "color": "orange", "builtin": True}]}]
    assert XL not in m


def test_failed_write_rolls_back_everything(sf, monkeypatch):
    def boom(*_a, **_k):
        raise RuntimeError("boom")
    monkeypatch.setattr(store, "raise_to_build", boom)
    with pytest.raises(RuntimeError):
        save(sf, members=(BEN,), tags=(BUILD_TAG_ID,), new_tags=("fresh",))
    with sf() as s:
        assert s.scalar(select(func.count()).select_from(Team)) == 0
        assert s.scalar(select(Tag).where(Tag.name_key == "fresh")) is None
    assert goals(sf, BEN) == ["none"]
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_teams_store.py -q`
Expected: FAIL with `ImportError` for `app.teams.store`.

- [ ] **Step 3: Implement** — `backend/app/teams/store.py`:

```python
"""Team and tag writes and reads. Every function works inside the caller's transaction."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, OwnedCharacter, Tag, Team, TeamMember, TeamTag
from app.gamedata.yatta import canonical_id
from app.settings.store import default_targets
from app.teams.goals import raise_to_build
from app.timeutil import utcnow

BUILD_TAG_ID = 1
TAG_COLORS = ("orange", "red", "yellow", "green", "teal", "blue", "purple", "pink")
NAME_MAX, NOTES_MAX, ROLE_MAX, TAG_MAX, MEMBERS_MAX = 60, 2000, 40, 30, 4


class TeamError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class MemberIn:
    character_id: int
    role: str = ""


def _text(raw: str, max_len: int, what: str, required: bool = True) -> str:
    value = (raw or "").strip()
    if required and not value:
        raise TeamError(422, f"{what} is required")
    if len(value) > max_len:
        raise TeamError(422, f"{what} can be at most {max_len} characters")
    return value


def _known_character(s: Session, cid: int) -> bool:
    if s.get(OwnedCharacter, cid) is not None:
        return True
    g = s.get(GameCharacter, cid)
    return g is not None and g.release_at <= utcnow()


def tag_dict(t: Tag) -> dict:
    return {"id": t.id, "name": t.name, "color": t.color, "builtin": t.builtin}


def _tag_order(t: Tag) -> tuple:
    return (not t.builtin, t.name_key)


def _find_tag(s: Session, name: str) -> Tag | None:
    return s.scalar(select(Tag).where(Tag.name_key == name.strip().lower()))


def create_tag(s: Session, name: str, color: str | None = None) -> Tag:
    clean = _text(name, TAG_MAX, "Tag name")
    if _find_tag(s, clean) is not None:
        raise TeamError(409, "A tag with that name exists")
    if color is None:
        count = s.scalar(select(func.count()).select_from(Tag)) or 0
        color = TAG_COLORS[count % len(TAG_COLORS)]
    elif color not in TAG_COLORS:
        raise TeamError(422, "Unknown tag colour")
    tag = Tag(name=clean, name_key=clean.lower(), color=color, builtin=False)
    s.add(tag)
    s.flush()
    return tag


def update_tag(s: Session, tag_id: int, name: str | None, color: str | None) -> Tag:
    tag = s.get(Tag, tag_id)
    if tag is None:
        raise TeamError(404, "Tag not found")
    if name is not None:
        clean = _text(name, TAG_MAX, "Tag name")
        if clean != tag.name:
            if tag.builtin:
                raise TeamError(409, "Build is a built-in tag")
            other = _find_tag(s, clean)
            if other is not None and other.id != tag.id:
                raise TeamError(409, "A tag with that name exists")
            tag.name, tag.name_key = clean, clean.lower()
    if color is not None:
        if color not in TAG_COLORS:
            raise TeamError(422, "Unknown tag colour")
        tag.color = color
    s.flush()
    return tag


def delete_tag(s: Session, tag_id: int) -> None:
    tag = s.get(Tag, tag_id)
    if tag is None:
        raise TeamError(404, "Tag not found")
    if tag.builtin:
        raise TeamError(409, "Build is a built-in tag")
    s.execute(delete(Tag).where(Tag.id == tag_id))


def list_tags(s: Session) -> list[dict]:
    counts = dict(s.execute(select(TeamTag.tag_id, func.count()).group_by(TeamTag.tag_id)).all())
    tags = sorted(s.scalars(select(Tag)), key=_tag_order)
    return [{**tag_dict(t), "team_count": counts.get(t.id, 0)} for t in tags]


def save_team(s: Session, team_id: int | None, name: str, notes: str, members: list[MemberIn],
              tag_ids: list[int], new_tags: list[str]) -> tuple[Team, list[int]]:
    clean_name = _text(name, NAME_MAX, "Team name")
    clean_notes = _text(notes, NOTES_MAX, "Notes", required=False)
    if not 1 <= len(members) <= MEMBERS_MAX:
        raise TeamError(422, "A team needs 1 to 4 members")
    ids = [canonical_id(m.character_id) for m in members]
    if len(set(ids)) != len(ids):
        raise TeamError(422, "A character can be in a team only once")
    roles = [_text(m.role, ROLE_MAX, "Role", required=False) for m in members]
    for cid in ids:
        if not _known_character(s, cid):
            raise TeamError(422, f"Unknown character {cid}")
    final_tags: list[int] = []
    for tid in tag_ids:
        if s.get(Tag, tid) is None:
            raise TeamError(422, "Unknown tag")
        if tid not in final_tags:
            final_tags.append(tid)

    if team_id is None:
        lowest = s.scalar(select(func.min(Team.sort_order)))
        team = Team(name=clean_name, notes=clean_notes, sort_order=(lowest if lowest is not None else 1) - 1,
                    created_at=utcnow(), updated_at=utcnow())
        s.add(team)
        s.flush()
        old_members: set[int] = set()
        had_build = False
    else:
        team = s.get(Team, team_id)
        if team is None:
            raise TeamError(404, "Team not found")
        old_members = set(s.scalars(select(TeamMember.character_id).where(TeamMember.team_id == team.id)))
        had_build = s.get(TeamTag, (team.id, BUILD_TAG_ID)) is not None

    for raw in new_tags:
        if not (raw or "").strip():
            continue
        tag = _find_tag(s, raw) or create_tag(s, raw)
        if tag.id not in final_tags:
            final_tags.append(tag.id)

    s.execute(delete(TeamMember).where(TeamMember.team_id == team.id))
    s.execute(delete(TeamTag).where(TeamTag.team_id == team.id))
    s.flush()
    for slot, (cid, role) in enumerate(zip(ids, roles)):
        s.add(TeamMember(team_id=team.id, slot=slot, character_id=cid, role=role))
    for tid in final_tags:
        s.add(TeamTag(team_id=team.id, tag_id=tid))
    team.name, team.notes, team.updated_at = clean_name, clean_notes, utcnow()
    s.flush()

    to_raise: list[int] = []
    if BUILD_TAG_ID in final_tags:
        to_raise = ids if not had_build else [cid for cid in ids if cid not in old_members]
    raised = raise_to_build(s, to_raise, default_targets(s)) if to_raise else []
    return team, raised


def delete_team(s: Session, team_id: int) -> None:
    if s.get(Team, team_id) is None:
        raise TeamError(404, "Team not found")
    s.execute(delete(Team).where(Team.id == team_id))


def reorder(s: Session, ids: list[int]) -> None:
    teams = {t.id: t for t in s.scalars(select(Team))}
    if len(ids) != len(set(ids)) or set(ids) != set(teams):
        raise TeamError(422, "The order must list every team once")
    for order, tid in enumerate(ids):
        teams[tid].sort_order = order
    s.flush()


def team_rows(s: Session) -> list[tuple[Team, list[TeamMember], list[Tag]]]:
    teams = s.scalars(select(Team).order_by(Team.sort_order, Team.id)).all()
    members: dict[int, list[TeamMember]] = {}
    for m in s.scalars(select(TeamMember).order_by(TeamMember.team_id, TeamMember.slot)):
        members.setdefault(m.team_id, []).append(m)
    tags = {t.id: t for t in s.scalars(select(Tag))}
    links: dict[int, list[Tag]] = {}
    for link in s.scalars(select(TeamTag)):
        links.setdefault(link.team_id, []).append(tags[link.tag_id])
    for tag_list in links.values():
        tag_list.sort(key=_tag_order)
    return [(t, members.get(t.id, []), links.get(t.id, [])) for t in teams]


def memberships(s: Session) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for team, members, tags in team_rows(s):
        ref = {"id": team.id, "name": team.name, "tags": [tag_dict(t) for t in tags]}
        for m in members:
            out.setdefault(m.character_id, []).append(ref)
    return out
```

Note: `test_failed_write_rolls_back_everything` monkeypatches `store.raise_to_build`, which works because `save_team` looks the name up in the module namespace at call time.

- [ ] **Step 4: Run tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_teams_store.py -q`
Expected: PASS. If `test_new_tag_colours_cycle` fails, check that `create_tag` counts existing tags before inserting.

- [ ] **Step 5: Commit**

```bash
git add backend/app/teams/store.py backend/tests/test_teams_store.py
git commit -m "feat(teams): team and tag store with Build-tag goal raising in one transaction"
```

---

### Task 4: Team-first shortfall

**Files:**
- Create: `backend/app/teams/shortfall.py`
- Test: `backend/tests/test_teams_shortfall.py`

**Interfaces:**
- Consumes: `PlannerData`, `Material`, `Total`, `CharRef`, `CATEGORY_ORDER` (`app.planner.data`); `rollup`, `Crafted` (`app.planner.crafting`); `material_index` (`app.planner.inventory`) returns `{mid: {"id","name","icon","rarity","category","sort_order",...}}`; `CATEGORY_LABELS` (`app.gamedata.materials`).
- Produces:
  - `team_totals(data: PlannerData, build_ids: list[int]) -> dict[int, Total]`
  - `team_shortfall(data: PlannerData, build_ids: list[int], index: dict[int, dict]) -> list[dict]` — rows `{"id","name","icon","rarity","category","category_label","need","short","craftable","to_farm","shared"}`, only materials with team need > 0, ordered by category then `sort_order`
  - `team_progress(values: list[float | None]) -> float | None`

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_teams_shortfall.py`:

```python
from dataclasses import replace

from app.planner.data import CharRef, Material, PlannerData, Total
from app.planner.inventory import material_index
from app.teams.shortfall import team_progress, team_shortfall, team_totals

BEN, FUR = 10000032, 10000089
TEACH, GUIDE, PHIL, PLUME = 104301, 104302, 104303, 113003


def data(lack_includes_crafting=False) -> PlannerData:
    materials = {
        TEACH: Material(TEACH, "Teachings", "", 2, "talent", None, [], 1),
        GUIDE: Material(GUIDE, "Guide", "", 3, "talent", TEACH, [], 2),
        PHIL: Material(PHIL, "Philosophies", "", 4, "talent", GUIDE, [], 3),
        PLUME: Material(PLUME, "Plume", "", 5, "weekly", None, [], 4),
    }
    totals = {
        TEACH: Total(0, 0, 9),     # 9 spare Teachings -> 3 Guides
        GUIDE: Total(15, 7, 0),    # have 8
        PHIL: Total(6, 0, 0),      # have >= 6
        PLUME: Total(2, 2, 0),     # have 0
    }
    gaps = {
        BEN: {GUIDE: (9, 4), PHIL: (6, 0), PLUME: (2, 2)},
        FUR: {GUIDE: (6, 4)},
    }
    chars = {BEN: CharRef(BEN, "Bennett", "bennett", None), FUR: CharRef(FUR, "Furina", "furina", None)}
    return PlannerData(materials, totals, gaps, chars, [], lack_includes_crafting, frozenset({BEN, FUR}))


def rows_by_id(d, ids):
    return {r["id"]: r for r in team_shortfall(d, ids, material_index(d))}


def test_team_totals_team_goes_first():
    t = team_totals(data(), [BEN])
    assert t[GUIDE] == Total(9, 1, 0)        # need 9, have 8
    assert t[PHIL] == Total(6, 0, 0)
    assert t[PLUME] == Total(2, 2, 0)
    assert t[TEACH] == Total(0, 0, 9)


def test_shared_material_and_crafting():
    rows = rows_by_id(data(), [BEN])
    guide = rows[GUIDE]
    assert (guide["need"], guide["short"], guide["craftable"], guide["to_farm"]) == (9, 1, 1, 0)
    assert guide["shared"] is True                     # Furina, outside the team, needs it too
    assert rows[PLUME]["shared"] is False and rows[PLUME]["to_farm"] == 2
    assert rows[PHIL]["short"] == 0
    assert TEACH not in rows                           # the team does not need it
    assert [r["id"] for r in team_shortfall(data(), [BEN], material_index(data()))] == [GUIDE, PHIL, PLUME]
    assert rows[PLUME]["category_label"] == "Weekly boss drops"


def test_whole_roster_team_matches_combined_short():
    rows = rows_by_id(data(), [BEN, FUR])
    assert rows[GUIDE]["short"] == 7 and rows[GUIDE]["shared"] is False


def test_netted_mode_keeps_hint_but_farms_short():
    rows = rows_by_id(data(lack_includes_crafting=True), [BEN])
    assert (rows[GUIDE]["craftable"], rows[GUIDE]["to_farm"]) == (1, 1)


def test_not_calculated_members_contribute_nothing():
    # The caller passes only calculated Build members; an empty list gives an empty shortfall.
    assert team_shortfall(data(), [], material_index(data())) == []
    d = replace(data(), gaps={BEN: data().gaps[BEN]})
    assert rows_by_id(d, [BEN, FUR])[GUIDE]["need"] == 9    # Furina has no gap rows: adds nothing


def test_team_progress():
    assert team_progress([0.5, None, 1.0]) == 0.75
    assert team_progress([None]) is None
    assert team_progress([]) is None
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_teams_shortfall.py -q`
Expected: FAIL with `ImportError`.

- [ ] **Step 3: Implement** — `backend/app/teams/shortfall.py`:

```python
"""What is still left to farm to finish one team, using the whole bag for it ("team goes first")."""
from __future__ import annotations

from dataclasses import replace

from app.gamedata.materials import CATEGORY_LABELS
from app.planner.crafting import Crafted, rollup
from app.planner.data import CATEGORY_ORDER, PlannerData, Total

EMPTY = Total(0, 0, 0)


def team_totals(data: PlannerData, build_ids: list[int]) -> dict[int, Total]:
    """Per material (team need, team short, team spare). `have` is exact when short overall, else a lower bound."""
    need: dict[int, int] = {}
    for cid in build_ids:
        for mid, (n, _short) in data.gaps.get(cid, {}).items():
            need[mid] = need.get(mid, 0) + n
    out: dict[int, Total] = {}
    for mid in set(data.totals) | set(need):
        t = data.totals.get(mid, EMPTY)
        have = t.need - t.short + t.spare
        team_need = need.get(mid, 0)
        out[mid] = Total(team_need, max(0, team_need - have), max(0, have - team_need))
    return out


def team_shortfall(data: PlannerData, build_ids: list[int], index: dict[int, dict]) -> list[dict]:
    totals = team_totals(data, build_ids)
    crafted = rollup(replace(data, totals=totals))
    members = set(build_ids)
    rows = []
    for mid, t in totals.items():
        m = index.get(mid)
        if t.need <= 0 or m is None:
            continue
        c = crafted.get(mid, Crafted(0, t.short))
        shared = any(cid not in members and mats.get(mid, (0, 0))[0] > 0 for cid, mats in data.gaps.items())
        rows.append({"id": mid, "name": m["name"], "icon": m["icon"], "rarity": m["rarity"],
                     "category": m["category"], "category_label": CATEGORY_LABELS[m["category"]],
                     "need": t.need, "short": t.short, "craftable": c.craftable, "to_farm": c.to_farm,
                     "shared": shared,
                     "_order": (CATEGORY_ORDER.index(m["category"]), m["sort_order"], mid)})
    rows.sort(key=lambda r: r["_order"])
    for r in rows:
        del r["_order"]
    return rows


def team_progress(values: list[float | None]) -> float | None:
    known = [v for v in values if v is not None]
    return round(sum(known) / len(known), 4) if known else None
```

- [ ] **Step 4: Run tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_teams_shortfall.py tests/test_planner.py -q`
Expected: PASS (planner tests unchanged).

- [ ] **Step 5: Commit**

```bash
git add backend/app/teams/shortfall.py backend/tests/test_teams_shortfall.py
git commit -m "feat(teams): team-first shortfall with crafting and shared marks"
```

---

### Task 5: Teams API, payloads, characters and dashboard additions, leak test

**Files:**
- Create: `backend/app/teams/view.py`, `backend/app/api/teams.py`
- Modify: `backend/app/api/__init__.py`, `backend/app/api/characters.py`, `backend/app/api/dashboard.py`, `backend/tests/test_api_settings.py`
- Test: `backend/tests/test_api_teams.py`

**Interfaces:**
- Consumes: Task 3 store functions, Task 4 shortfall functions, `set_line` (Task 2); `character_payload`, `_all` (`app.api.characters`); `planner_view`, `gaps_for`, `is_connected` (`app.api.planner`); `UNSUPPORTED` (`app.planner.requests`).
- Produces:
  - `view.member_view(char: dict | None, cid: int, role: str, artifact_line: str, in_build_team: bool, calculated: bool) -> dict`
  - `view.team_view(team, members, tags, chars: dict[int, dict], arts: dict[int, str], data, index) -> dict` → `{"id","name","notes","sort_order","tags","has_build_tag","members","shortfall","progress"}`
  - `view.build_team_cards(views: list[dict]) -> list[dict]` → `{"id","name","members":[{"id","name","slug","icon"}],"progress","top","more","has_shortfall"}`
  - `api.teams.team_views(s: Session) -> list[dict]`
  - Endpoints: `GET/POST /api/teams`, `PUT /api/teams/order`, `GET/PUT/DELETE /api/teams/{id}`, `GET/POST /api/tags`, `PUT/DELETE /api/tags/{id}`. Save responses: `{"team": <team view>, "raised": [ids]}`.
  - `GET /api/characters` rows gain `team_tags: list[list[int]]`; `GET /api/characters/{slug}` gains `teams: [{"id","name","tags"}]`; `GET /api/dashboard` gains `build_teams`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_api_teams.py`:

```python
from datetime import datetime

from sqlalchemy import delete

from app.db.models import GapRun, OwnedArtifact
from app.planner.requests import snapshot
from test_api_planner import setup                  # Bennett owned + Build, catalogue, totals, gaps
from helpers import make_client

BEN, FUR, XL, NAH = 10000032, 10000089, 10000023, 10000073


def mark_calculated(sf):
    """Record a successful gap run whose snapshot matches the current goals, so Build members count as calculated."""
    with sf.begin() as s:
        s.merge(GapRun(id=1, ok=True, error=None, skipped=[], computed_at=datetime(2026, 11, 21), snapshot=snapshot(s)))


def body(members=(BEN,), tags=(), new_tags=(), name="Abyss Pyro", notes="", roles=None):
    roles = roles or {}
    return {"name": name, "notes": notes, "members": [{"character_id": c, "role": roles.get(c, "")} for c in members],
            "tag_ids": list(tags), "new_tags": list(new_tags)}


def test_create_list_get_update_delete(paths):
    sf = setup(paths)
    mark_calculated(sf)
    with sf.begin() as s:
        s.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id == BEN))
        for slot in range(1, 5):
            s.add(OwnedArtifact(character_id=BEN, slot=slot, set_name="Noblesse Oblige", rarity=5, level=20,
                                main_stat="HP", substats=[], icon=""))
    with make_client(paths) as client:
        r = client.post("/api/teams", json=body(members=(BEN, XL), new_tags=("abyss",), roles={BEN: "battery"}))
        assert r.status_code == 200, r.text
        created = r.json()
        assert created["raised"] == []
        team = created["team"]
        assert [t["name"] for t in team["tags"]] == ["abyss"] and team["has_build_tag"] is False
        ben = team["members"][0]
        assert (ben["name"], ben["role"], ben["status"], ben["level"]) == ("Bennett", "battery", "building", 80)
        assert ben["artifact_line"] == "4pc Noblesse Oblige" and ben["not_building"] is False and ben["not_calculated"] is False
        assert team["shortfall"][0]["id"] == 104302           # Bennett is Build, so the team has a shortfall
        listing = client.get("/api/teams").json()
        assert listing["connected"] is False and [t["id"] for t in listing["teams"]] == [team["id"]]
        one = client.get(f"/api/teams/{team['id']}").json()
        assert one["team"]["name"] == "Abyss Pyro" and "gaps" in one
        r = client.put(f"/api/teams/{team['id']}", json=body(members=(XL,), name="Renamed"))
        assert r.json()["team"]["name"] == "Renamed" and r.json()["team"]["shortfall"] is None
        assert client.delete(f"/api/teams/{team['id']}").status_code == 200
        assert client.get(f"/api/teams/{team['id']}").status_code == 404
        assert client.put(f"/api/teams/{team['id']}", json=body()).json()["detail"] == "Team not found"


def test_build_tag_raises_and_schedules_gaps(paths):
    sf = setup(paths)
    with make_client(paths) as client:
        sync = client.app.state.ctx.sync
        r = client.post("/api/teams", json=body(members=(BEN, NAH), tags=(1,))).json()
        assert r["raised"] == [NAH]
        assert sync.gaps_pending                               # a gaps-only run was scheduled
        assert r["team"]["has_build_tag"] is True
        chars = {c["id"]: c for c in client.get("/api/characters").json()}
        assert chars[NAH]["goal"] == "build" and chars[NAH]["team_tags"] == [[1]]
        assert chars[XL]["team_tags"] == []


def test_newly_raised_member_is_not_calculated(paths):
    sf = setup(paths)
    mark_calculated(sf)                                        # Bennett calculated; Nahida not yet
    with make_client(paths) as client:
        team = client.post("/api/teams", json=body(members=(BEN, NAH), tags=(1,))).json()["team"]
    flags = {m["id"]: m["not_calculated"] for m in team["members"]}
    assert flags == {BEN: False, NAH: True}
    assert {r["id"] for r in team["shortfall"]} == {104302, 113003}   # from Bennett only


def test_not_building_badge(paths):
    sf = setup(paths)
    with make_client(paths) as client:
        tid = client.post("/api/teams", json=body(members=(BEN, NAH), tags=(1,))).json()["team"]["id"]
        client.put(f"/api/characters/{NAH}/goal", json={"goal": "want"})
        team = client.get(f"/api/teams/{tid}").json()["team"]
    assert {m["id"]: m["not_building"] for m in team["members"]} == {BEN: False, NAH: True}


def test_validation_errors(paths):
    setup(paths)
    with make_client(paths) as client:
        assert client.post("/api/teams", json=body(members=())).json()["detail"] == "A team needs 1 to 4 members"
        assert client.post("/api/teams", json=body(members=(BEN, BEN))).status_code == 422
        assert client.post("/api/teams", json=body(name="")).status_code == 422
        assert client.post("/api/teams", json={"name": "x"}).status_code == 422   # members missing
        assert client.get("/api/teams").json()["teams"] == []


def test_reorder_endpoint(paths):
    setup(paths)
    with make_client(paths) as client:
        a = client.post("/api/teams", json=body(name="A")).json()["team"]["id"]
        b = client.post("/api/teams", json=body(name="B")).json()["team"]["id"]
        assert [t["name"] for t in client.get("/api/teams").json()["teams"]] == ["B", "A"]
        assert client.put("/api/teams/order", json={"ids": [a, b]}).status_code == 200
        assert [t["name"] for t in client.get("/api/teams").json()["teams"]] == ["A", "B"]
        client.delete(f"/api/teams/{b}")
        r = client.put("/api/teams/order", json={"ids": [a, b]})
        assert (r.status_code, r.json()["detail"]) == (422, "The order must list every team once")


def test_tag_endpoints(paths):
    setup(paths)
    with make_client(paths) as client:
        fun = client.post("/api/tags", json={"name": "fun"}).json()
        assert client.post("/api/tags", json={"name": "FUN"}).status_code == 409
        assert client.put(f"/api/tags/{fun['id']}", json={"name": "party", "color": "pink"}).json()["color"] == "pink"
        assert client.put("/api/tags/1", json={"name": "Farm"}).json()["detail"] == "Build is a built-in tag"
        assert client.delete("/api/tags/1").status_code == 409
        client.post("/api/teams", json=body(tags=(fun["id"],)))
        tags = client.get("/api/tags").json()
        assert [(t["name"], t["team_count"]) for t in tags] == [("Build", 0), ("party", 1)]
        assert client.delete(f"/api/tags/{fun['id']}").status_code == 200
        assert client.delete(f"/api/tags/{fun['id']}").status_code == 404


def test_character_detail_and_dashboard(paths):
    sf = setup(paths)
    mark_calculated(sf)
    with make_client(paths) as client:
        tid = client.post("/api/teams", json=body(members=(BEN,), tags=(1,), name="Pyro")).json()["team"]["id"]
        client.post("/api/teams", json=body(members=(XL,), name="Fun"))
        detail = client.get("/api/characters/bennett").json()
        assert [t["name"] for t in detail["teams"]] == ["Pyro"]
        assert client.get("/api/characters/xiangling").json()["teams"] == [
            {"id": tid + 1, "name": "Fun", "tags": []}]
        cards = client.get("/api/dashboard").json()["build_teams"]
    assert [c["name"] for c in cards] == ["Pyro"]
    card = cards[0]
    assert [m["id"] for m in card["members"]] == [BEN]
    assert [(m["id"], m["to_farm"]) for m in card["top"]] == [(104302, 4), (113003, 2)]   # most missing first
    assert card["has_shortfall"] is True and card["more"] == 0
```

Then extend `test_no_endpoint_leaks_cookie_values` in `backend/tests/test_api_settings.py`: after the existing `bodies = [...]` list is created (before the wait loop), append the team calls, and add the team GETs to the final list:

```python
        bodies += [
            client.post("/api/teams", json={"name": "Leak check", "notes": "", "tag_ids": [1], "new_tags": ["abyss"],
                                            "members": [{"character_id": 10000032, "role": ""}]}).text,
            client.get("/api/tags").text,
        ]
```

and change the GET tuple to also include `"/api/teams"`. (Bennett is already Build, so the team raises nobody and the existing `== 2` gaps-call assertion still holds.)

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_api_teams.py -q`
Expected: FAIL (404 on `/api/teams`).

- [ ] **Step 3: Implement the payloads** — `backend/app/teams/view.py`:

```python
"""Team payloads for the API. Character rows come in already built by the characters API."""
from __future__ import annotations

from app.planner.data import PlannerData
from app.planner.requests import UNSUPPORTED
from app.teams.shortfall import team_progress, team_shortfall
from app.teams.store import BUILD_TAG_ID, tag_dict

MEMBER_KEYS = ("id", "name", "slug", "icon", "element", "rarity", "owned", "goal", "status", "prefarming",
               "level", "talents", "weapon", "progress")
TOP_MATERIALS = 5


def placeholder(cid: int) -> dict:
    return {"id": cid, "name": f"Unknown character {cid}", "slug": None, "icon": None, "element": None,
            "rarity": 0, "owned": False, "goal": "none", "status": "unobtained", "prefarming": False,
            "level": None, "talents": None, "weapon": None, "progress": None}


def member_view(char: dict | None, cid: int, role: str, artifact_line: str, in_build_team: bool,
                calculated: bool) -> dict:
    base = {k: char[k] for k in MEMBER_KEYS} if char is not None else placeholder(cid)
    is_build = base["goal"] == "build"
    return {**base, "role": role, "artifact_line": artifact_line,
            "not_building": in_build_team and not is_build,
            "not_calculated": is_build and not calculated}


def team_view(team, members, tags, chars: dict[int, dict], arts: dict[int, str], data: PlannerData,
              index: dict[int, dict]) -> dict:
    has_build = any(t.id == BUILD_TAG_ID for t in tags)
    views = [member_view(chars.get(m.character_id), m.character_id, m.role, arts.get(m.character_id, ""), has_build,
                         m.character_id in data.calculated and m.character_id not in UNSUPPORTED)
             for m in members]
    build = [v for v in views if v["goal"] == "build"]
    counted = [v["id"] for v in build if not v["not_calculated"]]
    return {"id": team.id, "name": team.name, "notes": team.notes, "sort_order": team.sort_order,
            "tags": [tag_dict(t) for t in tags], "has_build_tag": has_build, "members": views,
            "shortfall": team_shortfall(data, counted, index) if build else None,
            "progress": team_progress([v["progress"] for v in build])}


def build_team_cards(views: list[dict]) -> list[dict]:
    cards = []
    for v in views:
        if not v["has_build_tag"]:
            continue
        farm = sorted((m for m in (v["shortfall"] or []) if m["to_farm"] > 0),
                      key=lambda m: (-m["to_farm"], m["name"]))
        cards.append({"id": v["id"], "name": v["name"],
                      "members": [{k: m[k] for k in ("id", "name", "slug", "icon")} for m in v["members"]],
                      "progress": v["progress"], "top": farm[:TOP_MATERIALS],
                      "more": max(0, len(farm) - TOP_MATERIALS), "has_shortfall": v["shortfall"] is not None})
    return cards
```

- [ ] **Step 4: Implement the router** — `backend/app/api/teams.py`:

```python
"""Teams and tags. The only side effect on other data is raising goals to build (app.teams.goals)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.characters import _all, character_payload
from app.api.planner import gaps_for, is_connected, planner_view
from app.context import AppContext, get_ctx
from app.db.models import OwnedArtifact
from app.teams import store
from app.teams.artifacts import set_line
from app.teams.store import MemberIn, TeamError
from app.teams.view import team_view

router = APIRouter()


class MemberBody(BaseModel):
    character_id: int
    role: str = ""


class TeamBody(BaseModel):
    name: str
    notes: str = ""
    members: list[MemberBody]
    tag_ids: list[int] = []
    new_tags: list[str] = []


class OrderBody(BaseModel):
    ids: list[int]


class TagBody(BaseModel):
    name: str
    color: str | None = None


class TagPatch(BaseModel):
    name: str | None = None
    color: str | None = None


def artifact_lines(s: Session) -> dict[int, str]:
    sets: dict[int, list[str]] = {}
    for a in s.scalars(select(OwnedArtifact)):
        sets.setdefault(a.character_id, []).append(a.set_name)
    return {cid: set_line(names) for cid, names in sets.items()}


def team_views(s: Session) -> list[dict]:
    chars = {p["id"]: p for p in (character_payload(g, o, r) for g, o, r in _all(s))}
    data, index = planner_view(s)
    arts = artifact_lines(s)
    return [team_view(t, members, tags, chars, arts, data, index) for t, members, tags in store.team_rows(s)]


def _one(s: Session, team_id: int) -> dict:
    for v in team_views(s):
        if v["id"] == team_id:
            return v
    raise HTTPException(404, "Team not found")


def _save(ctx: AppContext, team_id: int | None, body: TeamBody) -> dict:
    try:
        with ctx.session_factory.begin() as s:
            team, raised = store.save_team(s, team_id, body.name, body.notes,
                                           [MemberIn(m.character_id, m.role) for m in body.members],
                                           body.tag_ids, body.new_tags)
            tid = team.id
    except TeamError as e:
        raise HTTPException(e.status, e.message) from None
    if raised:
        ctx.sync.schedule_gaps()
    with ctx.session_factory() as s:
        return {"team": _one(s, tid), "raised": raised}


def _write(ctx: AppContext, fn) -> object:
    try:
        with ctx.session_factory.begin() as s:
            result = fn(s)
            return store.tag_dict(result) if result is not None else {"ok": True}
    except TeamError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/teams")
def list_teams(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        return {"gaps": gaps_for(ctx, s), "connected": is_connected(ctx, s), "teams": team_views(s)}


@router.post("/teams")
async def create_team(body: TeamBody, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _save(ctx, None, body)


@router.put("/teams/order")
def reorder_teams(body: OrderBody, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _write(ctx, lambda s: store.reorder(s, body.ids))


@router.get("/teams/{team_id}")
def get_team(team_id: int, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        return {"gaps": gaps_for(ctx, s), "connected": is_connected(ctx, s), "team": _one(s, team_id)}


@router.put("/teams/{team_id}")
async def update_team(team_id: int, body: TeamBody, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _save(ctx, team_id, body)


@router.delete("/teams/{team_id}")
def remove_team(team_id: int, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _write(ctx, lambda s: store.delete_team(s, team_id))


@router.get("/tags")
def get_tags(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        return store.list_tags(s)


@router.post("/tags")
def add_tag(body: TagBody, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _write(ctx, lambda s: store.create_tag(s, body.name, body.color))


@router.put("/tags/{tag_id}")
def edit_tag(tag_id: int, body: TagPatch, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _write(ctx, lambda s: store.update_tag(s, tag_id, body.name, body.color))


@router.delete("/tags/{tag_id}")
def remove_tag(tag_id: int, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _write(ctx, lambda s: store.delete_tag(s, tag_id))
```

Register it — `backend/app/api/__init__.py`:

```python
from app.api import characters, dashboard, img, planner, settings, sync, teams, wishes

ROUTERS = [settings.router, sync.router, characters.router, dashboard.router, planner.router, wishes.router,
           teams.router, img.router]
```

- [ ] **Step 5: Characters additions** — in `backend/app/api/characters.py` add the import `from app.teams.store import memberships` and change the two GET handlers:

```python
@router.get("/characters")
def list_characters(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        teams = memberships(s)
        rows = []
        for g, o, r in _all(s):
            p = character_payload(g, o, r)
            p["team_tags"] = [[t["id"] for t in m["tags"]] for m in teams.get(p["id"], [])]
            rows.append(p)
        return rows
```

and in `get_character`, right after `payload["planned_weapon"] = planned_weapon(s, r, o)`:

```python
            payload["teams"] = memberships(s).get(payload["id"], [])
```

(`app.teams.store` does not import `app.api`, so there is no import cycle.)

- [ ] **Step 6: Dashboard addition** — in `backend/app/api/dashboard.py` add imports `from app.api.teams import team_views` and `from app.teams.view import build_team_cards`, and add to the returned dict:

```python
            "build_teams": build_team_cards(team_views(s)),
```

- [ ] **Step 7: Run the tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_api_teams.py tests/test_api_characters.py tests/test_api_planner.py tests/test_api_settings.py -q`
Expected: PASS. If `test_build_tag_raises_and_schedules_gaps` sees `gaps_pending` False, check `_save` is reached from the `async def` handler (the timer task needs the event loop).

- [ ] **Step 8: Run the whole backend suite**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: all PASS.

- [ ] **Step 9: Commit**

```bash
git add backend/app/teams/view.py backend/app/api backend/tests/test_api_teams.py backend/tests/test_api_settings.py
git commit -m "feat(teams): teams and tags API, team fields on characters and dashboard"
```

---

### Task 6: Demo teams in the dev seed

**Files:**
- Modify: `backend/app/devseed.py`
- Test: `backend/tests/test_devseed.py`

**Interfaces:**
- Consumes: models `Tag`, `Team`, `TeamMember`, `TeamTag` (Task 1). Rows are inserted directly (not through `save_team`) so the seeded goals stay exactly as `test_devseed_creates_expected_statuses` expects.
- Produces: tag `abyss` (id 2, colour `red`); team "Abyss Furina" (Build + abyss; Furina "on-field", Bennett "battery", Xingqiu "off-field hydro" — Xingqiu is unobtained, so the demo shows a Not building member); team "Archons only" (no tags; Furina, Nahida, Raiden Shogun).

- [ ] **Step 1: Write the failing test** — append to `backend/tests/test_devseed.py`:

```python
def test_devseed_teams(tmp_path):
    seed(tmp_path)
    with make_client(Paths(tmp_path)) as client:
        teams = client.get("/api/teams").json()["teams"]
        tags = client.get("/api/tags").json()
    assert [t["name"] for t in teams] == ["Abyss Furina", "Archons only"]
    abyss = teams[0]
    assert [t["name"] for t in abyss["tags"]] == ["Build", "abyss"]
    assert [m["slug"] for m in abyss["members"]] == ["furina", "bennett", "xingqiu"]
    assert [m["not_building"] for m in abyss["members"]] == [False, False, True]
    assert abyss["shortfall"] and teams[1]["tags"] == []
    assert [(t["name"], t["team_count"]) for t in tags] == [("Build", 1), ("abyss", 1)]
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_devseed.py -q`
Expected: FAIL (`teams == []`).

- [ ] **Step 3: Implement** — in `backend/app/devseed.py` add `Tag, Team, TeamMember, TeamTag` to the models import and, at the end of `seed()` (after the existing last `with sf.begin()` block), add:

```python
    with sf.begin() as s:
        ids = {c[2]: c[0] for c in CHARACTERS}             # slug -> id
        s.add(Tag(id=2, name="abyss", name_key="abyss", color="red", builtin=False))
        teams = [
            (1, "Abyss Furina", "Demo: Build + abyss.", [("furina", "on-field"), ("bennett", "battery"),
                                                         ("xingqiu", "off-field hydro")], [1, 2]),
            (2, "Archons only", "", [("furina", ""), ("nahida", ""), ("raiden-shogun", "")], []),
        ]
        for order, (tid, name, notes, members, tags) in enumerate(teams):
            s.add(Team(id=tid, name=name, notes=notes, sort_order=order, created_at=now, updated_at=now))
            s.flush()
            for slot, (slug, role) in enumerate(members):
                s.add(TeamMember(team_id=tid, slot=slot, character_id=ids[slug], role=role))
            for tag_id in tags:
                s.add(TeamTag(team_id=tid, tag_id=tag_id))
```

If `CHARACTERS` tuples do not carry the slug at index 2, read the tuple layout at the top of `devseed.py` (it matches `(id, name, slug, rarity, element, weapon, icon)`) and adjust the index.

- [ ] **Step 4: Run the devseed tests**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_devseed.py -q`
Expected: PASS (the existing status test is unchanged because goals were not touched).

- [ ] **Step 5: Commit**

```bash
git add backend/app/devseed.py backend/tests/test_devseed.py
git commit -m "chore(teams): demo teams and an abyss tag in the seed data"
```

---

### Task 7: Frontend foundations — types, API client, team helpers, nav, Characters filter logic

**Files:**
- Create: `frontend/src/lib/teams.ts`, `frontend/src/lib/teams.test.ts`, `frontend/src/lib/TagChip.svelte`
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/status.ts`, `frontend/src/lib/status.test.ts`, `frontend/src/routes/+layout.svelte`

**Interfaces:**
- Consumes: backend payloads from Task 5.
- Produces (TypeScript):
  - Types `Tag`, `TagWithCount`, `TeamMember`, `TeamMaterial`, `Team`, `TeamsResponse`, `TeamResponse`, `MemberDraft`, `TeamBody`, `SaveTeamResponse`, `BuildTeamCard`, `TeamRef`; `Character.team_tags: number[][]`; `CharacterDetail.teams: TeamRef[]`; `Dashboard.build_teams: BuildTeamCard[]`.
  - `api.teams()`, `api.team(id)`, `api.createTeam(body)`, `api.updateTeam(id, body)`, `api.deleteTeam(id)`, `api.reorderTeams(ids)`, `api.tags()`, `api.createTag(name, color?)`, `api.updateTag(id, patch)`, `api.deleteTag(id)`.
  - `teams.ts`: `BUILD_TAG_ID`, `TAG_COLORS`, `TAG_HEX`, `TeamFilter`, `emptyTeamFilter()`, `toggleTag(f, id)`, `toggleUntagged(f)`, `filterTeams(teams, f)`, `loadTeamFilter()`, `saveTeamFilter(f)`, `matchesTeamTags(teamTags, selected)`, `addMember(members, id)`, `removeMember(members, index)`, `moveItem(list, from, to)`, `willRaise(chars, draft, original)`, `raisedMessage(n)`, `memberLine(m)`, `weaponLine(m)`, `teamTileView(m)`, `farmRows(rows)`.
  - `status.ts`: `Filters.teamTags: number[]`, used by `matches`.

- [ ] **Step 1: Write the failing tests** — `frontend/src/lib/teams.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import type { Character, Team, TeamMaterial, TeamMember } from './types';
import {
	addMember, emptyTeamFilter, farmRows, filterTeams, matchesTeamTags, memberLine, moveItem, raisedMessage,
	removeMember, teamTileView, toggleTag, toggleUntagged, weaponLine, willRaise
} from './teams';

const tag = (id: number, name: string) => ({ id, name, color: 'red', builtin: id === 1 });

function team(id: number, tagIds: number[]): Team {
	return {
		id, name: `T${id}`, notes: '', sort_order: id, tags: tagIds.map((t) => tag(t, `t${t}`)),
		has_build_tag: tagIds.includes(1), members: [], shortfall: null, progress: null
	};
}

function char(id: number, goal: Character['goal'], name = `C${id}`): Character {
	return {
		id, slug: `c${id}`, name, rarity: 4, element: 'Pyro', weapon_type: 'Sword', icon: null, splash: null,
		owned: true, level: 80, constellation: 0, friendship: 10, talents: null, weapon: null, goal,
		targets: null, status: 'obtained', prefarming: false, progress: null, planned_weapon_id: null, team_tags: []
	};
}

describe('team filter', () => {
	const teams = [team(1, [1, 2]), team(2, [2]), team(3, [])];
	it('All shows everything', () => expect(filterTeams(teams, emptyTeamFilter()).map((t) => t.id)).toEqual([1, 2, 3]));
	it('tags combine with AND', () => {
		expect(filterTeams(teams, { tagIds: [2], untagged: false }).map((t) => t.id)).toEqual([1, 2]);
		expect(filterTeams(teams, { tagIds: [1, 2], untagged: false }).map((t) => t.id)).toEqual([1]);
	});
	it('Untagged and tags exclude each other', () => {
		const u = toggleUntagged(toggleTag(emptyTeamFilter(), 2));
		expect(u).toEqual({ tagIds: [], untagged: true });
		expect(filterTeams(teams, u).map((t) => t.id)).toEqual([3]);
		expect(toggleTag(u, 1)).toEqual({ tagIds: [1], untagged: false });
		expect(toggleTag({ tagIds: [1], untagged: false }, 1)).toEqual({ tagIds: [], untagged: false });
	});
	it('character tag match needs one team with all selected tags', () => {
		expect(matchesTeamTags([[1, 2], [3]], [])).toBe(true);
		expect(matchesTeamTags([[1, 2], [3]], [1, 2])).toBe(true);
		expect(matchesTeamTags([[1], [2]], [1, 2])).toBe(false);
		expect(matchesTeamTags([], [1])).toBe(false);
	});
});

describe('slots', () => {
	it('adds to the first free slot, ignores duplicates and a full team', () => {
		let m = addMember([], 5);
		m = addMember(m, 6);
		expect(addMember(m, 5)).toEqual(m);
		const full = [5, 6, 7, 8].reduce((acc, id) => addMember(acc, id), [] as { character_id: number; role: string }[]);
		expect(addMember(full, 9)).toEqual(full);
		expect(m).toEqual([{ character_id: 5, role: '' }, { character_id: 6, role: '' }]);
	});
	it('removes and compacts, moves', () => {
		const m = [5, 6, 7].map((id) => ({ character_id: id, role: '' }));
		expect(removeMember(m, 1).map((x) => x.character_id)).toEqual([5, 7]);
		expect(moveItem([1, 2, 3], 0, 2)).toEqual([2, 3, 1]);
		expect(moveItem([1, 2, 3], 2, 0)).toEqual([3, 1, 2]);
		expect(moveItem([1, 2, 3], 0, 5)).toEqual([1, 2, 3]);
	});
});

describe('raise preview', () => {
	const chars = [char(1, 'none', 'Xiangling'), char(2, 'build', 'Bennett'), char(3, 'want', 'Kazuha')];
	const members = [1, 2, 3].map((id) => ({ character_id: id, role: '' }));
	it('adding Build raises every non-build member', () => {
		expect(willRaise(chars, { members, hasBuild: true }, { memberIds: [1, 2, 3], hadBuild: false }))
			.toEqual(['Xiangling', 'Kazuha']);
	});
	it('an existing Build team raises only new members', () => {
		expect(willRaise(chars, { members, hasBuild: true }, { memberIds: [1, 2], hadBuild: true })).toEqual(['Kazuha']);
	});
	it('no Build tag raises nobody', () => {
		expect(willRaise(chars, { members, hasBuild: false }, { memberIds: [], hadBuild: false })).toEqual([]);
	});
	it('messages', () => {
		expect(raisedMessage(1)).toBe('Raised 1 character to Build');
		expect(raisedMessage(3)).toBe('Raised 3 characters to Build');
	});
});

describe('text helpers', () => {
	const m = {
		id: 1, name: 'Bennett', slug: 'bennett', icon: null, element: 'Pyro', rarity: 4, owned: true, goal: 'build',
		status: 'building', prefarming: false, level: 80, talents: { normal: 6, skill: 8, burst: 8 },
		weapon: { name: 'Sword', icon: '', rarity: 4, level: 90, refinement: 5 }, progress: 0.5, role: '',
		artifact_line: '4pc Noblesse Oblige', not_building: false, not_calculated: false
	} as TeamMember;
	it('member and weapon lines', () => {
		expect(memberLine(m)).toBe('Lv 80 · 6/8/8');
		expect(memberLine({ ...m, owned: false, level: null, talents: null })).toBe('');
		expect(weaponLine(m)).toBe('Lv 90 R5');
		expect(weaponLine({ ...m, weapon: null })).toBe('');
	});
	it('tile view and farm rows', () => {
		const row: TeamMaterial = {
			id: 1, name: 'Guide', icon: '', rarity: 3, category: 'talent', category_label: 'Talent books',
			need: 9, short: 1, craftable: 1, to_farm: 0, shared: true
		};
		expect(teamTileView(row)).toEqual({ main: '8/9', badge: null, hint: 'craft 1 · shared', tone: 'short' });
		expect(teamTileView({ ...row, short: 0, craftable: 0 })).toEqual({ main: '✓ 9', badge: null, hint: 'shared', tone: 'met' });
		expect(teamTileView({ ...row, to_farm: 2, short: 2, craftable: 0, shared: false }).badge).toBe('−2');
		expect(farmRows([row, { ...row, id: 2, short: 0 }]).map((r) => r.id)).toEqual([1]);
	});
});
```

In `frontend/src/lib/status.test.ts`, add `team_tags: []` to the object returned by the `char()` helper, and add:

```ts
it('team tag filter keeps characters in a team with every selected tag', () => {
	const f = { ...emptyFilters(), teamTags: [2] };
	const a = char({ id: 1, slug: 'a', team_tags: [[1, 2]] });
	const b = char({ id: 2, slug: 'b', team_tags: [[1]] });
	expect(groupCharacters([a, b], f).obtained.map((c) => c.slug)).toEqual(['a']);
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend; npm test`
Expected: FAIL (cannot resolve `./teams`).

- [ ] **Step 3: Types** — add to `frontend/src/lib/types.ts`: `team_tags: number[][];` as the last field of `Character`; `teams: TeamRef[];` in `CharacterDetail`; `build_teams: BuildTeamCard[];` in `Dashboard`; and at the end:

```ts
export interface Tag { id: number; name: string; color: string; builtin: boolean }
export interface TagWithCount extends Tag { team_count: number }
export interface TeamMember {
	id: number; name: string; slug: string | null; icon: string | null; element: string | null; rarity: number;
	owned: boolean; goal: Goal; status: Status; prefarming: boolean; level: number | null; talents: Talents | null;
	weapon: Weapon | null; progress: number | null; role: string; artifact_line: string;
	not_building: boolean; not_calculated: boolean;
}
export interface TeamMaterial {
	id: number; name: string; icon: string; rarity: number; category: string; category_label: string;
	need: number; short: number; craftable: number; to_farm: number; shared: boolean;
}
export interface Team {
	id: number; name: string; notes: string; sort_order: number; tags: Tag[]; has_build_tag: boolean;
	members: TeamMember[]; shortfall: TeamMaterial[] | null; progress: number | null;
}
export interface TeamsResponse { gaps: GapStatus; connected: boolean; teams: Team[] }
export interface TeamResponse { gaps: GapStatus; connected: boolean; team: Team }
export interface MemberDraft { character_id: number; role: string }
export interface TeamBody { name: string; notes: string; members: MemberDraft[]; tag_ids: number[]; new_tags: string[] }
export interface SaveTeamResponse { team: Team; raised: number[] }
export interface BuildTeamCard {
	id: number; name: string; members: CharRef[]; progress: number | null; top: TeamMaterial[]; more: number;
	has_shortfall: boolean;
}
export interface TeamRef { id: number; name: string; tags: Tag[] }
```

- [ ] **Step 4: API client** — in `frontend/src/lib/api.ts` add the new types to the import list and these entries to `api`:

```ts
	teams: () => request<TeamsResponse>('GET', '/teams'),
	team: (id: number) => request<TeamResponse>('GET', `/teams/${id}`),
	createTeam: (body: TeamBody) => request<SaveTeamResponse>('POST', '/teams', body),
	updateTeam: (id: number, body: TeamBody) => request<SaveTeamResponse>('PUT', `/teams/${id}`, body),
	deleteTeam: (id: number) => request<{ ok: boolean }>('DELETE', `/teams/${id}`),
	reorderTeams: (ids: number[]) => request<{ ok: boolean }>('PUT', '/teams/order', { ids }),
	tags: () => request<TagWithCount[]>('GET', '/tags'),
	createTag: (name: string, color?: string) => request<Tag>('POST', '/tags', { name, color }),
	updateTag: (id: number, patch: { name?: string; color?: string }) => request<Tag>('PUT', `/tags/${id}`, patch),
	deleteTag: (id: number) => request<{ ok: boolean }>('DELETE', `/tags/${id}`),
```

- [ ] **Step 5: Helpers** — `frontend/src/lib/teams.ts`:

```ts
import type { TileView } from './materials';
import type { Character, MemberDraft, Team, TeamMaterial, TeamMember } from './types';

export const BUILD_TAG_ID = 1;
export const TAG_COLORS = ['orange', 'red', 'yellow', 'green', 'teal', 'blue', 'purple', 'pink'] as const;
export const TAG_HEX: Record<string, string> = {
	orange: '#d9822b', red: '#d64545', yellow: '#c9a227', green: '#3f9c5a',
	teal: '#2f9c95', blue: '#3d7bd9', purple: '#8a5cd6', pink: '#d65c9c'
};
export const MAX_MEMBERS = 4;

export interface TeamFilter { tagIds: number[]; untagged: boolean }
const FILTER_KEY = 'gt.teamFilter';

export function emptyTeamFilter(): TeamFilter {
	return { tagIds: [], untagged: false };
}

export function toggleTag(f: TeamFilter, id: number): TeamFilter {
	const tagIds = f.tagIds.includes(id) ? f.tagIds.filter((t) => t !== id) : [...f.tagIds, id];
	return { tagIds, untagged: false };
}

export function toggleUntagged(f: TeamFilter): TeamFilter {
	return { tagIds: [], untagged: !f.untagged };
}

export function filterTeams(teams: Team[], f: TeamFilter): Team[] {
	if (f.untagged) return teams.filter((t) => t.tags.length === 0);
	return teams.filter((t) => f.tagIds.every((id) => t.tags.some((tag) => tag.id === id)));
}

export function loadTeamFilter(): TeamFilter {
	try {
		const raw = localStorage.getItem(FILTER_KEY);
		if (raw) {
			const v = JSON.parse(raw);
			if (Array.isArray(v.tagIds)) return { tagIds: v.tagIds.filter(Number.isInteger), untagged: !!v.untagged };
		}
	} catch {
		/* storage blocked or corrupt: default */
	}
	return emptyTeamFilter();
}

export function saveTeamFilter(f: TeamFilter): void {
	try {
		localStorage.setItem(FILTER_KEY, JSON.stringify(f));
	} catch {
		/* ignore */
	}
}

/** A character matches when one of its teams carries every selected tag. */
export function matchesTeamTags(teamTags: number[][], selected: number[]): boolean {
	if (selected.length === 0) return true;
	return teamTags.some((tags) => selected.every((id) => tags.includes(id)));
}

export function addMember(members: MemberDraft[], id: number): MemberDraft[] {
	if (members.length >= MAX_MEMBERS || members.some((m) => m.character_id === id)) return members;
	return [...members, { character_id: id, role: '' }];
}

export function removeMember(members: MemberDraft[], index: number): MemberDraft[] {
	return members.filter((_m, i) => i !== index);
}

export function moveItem<T>(list: T[], from: number, to: number): T[] {
	if (from < 0 || from >= list.length || to < 0 || to >= list.length || from === to) return list;
	const copy = [...list];
	const [item] = copy.splice(from, 1);
	copy.splice(to, 0, item);
	return copy;
}

/** Names of members a save would raise to Build (mirrors app.teams.store.save_team). */
export function willRaise(
	chars: Character[],
	draft: { members: MemberDraft[]; hasBuild: boolean },
	original: { memberIds: number[]; hadBuild: boolean }
): string[] {
	if (!draft.hasBuild) return [];
	const byId = new Map(chars.map((c) => [c.id, c]));
	return draft.members
		.filter((m) => !original.hadBuild || !original.memberIds.includes(m.character_id))
		.map((m) => byId.get(m.character_id))
		.filter((c): c is Character => !!c && c.goal !== 'build')
		.map((c) => c.name);
}

export function raisedMessage(n: number): string {
	return `Raised ${n} ${n === 1 ? 'character' : 'characters'} to Build`;
}

export function memberLine(m: TeamMember): string {
	if (!m.owned || m.level === null) return '';
	return m.talents ? `Lv ${m.level} · ${m.talents.normal}/${m.talents.skill}/${m.talents.burst}` : `Lv ${m.level}`;
}

export function weaponLine(m: TeamMember): string {
	return m.weapon ? `Lv ${m.weapon.level} R${m.weapon.refinement}` : '';
}

export function teamTileView(m: TeamMaterial): TileView {
	const hints = [m.craftable > 0 ? `craft ${m.craftable}` : null, m.shared ? 'shared' : null].filter(Boolean);
	const hint = hints.length ? hints.join(' · ') : null;
	if (m.short > 0) {
		return { main: `${m.need - m.short}/${m.need}`, badge: m.to_farm > 0 ? `−${m.to_farm}` : null, hint, tone: 'short' };
	}
	return { main: `✓ ${m.need}`, badge: null, hint, tone: 'met' };
}

/** The panel lists only what is still short for the team. */
export function farmRows(rows: TeamMaterial[]): TeamMaterial[] {
	return rows.filter((r) => r.short > 0);
}
```

`frontend/src/lib/TagChip.svelte`:

```svelte
<script lang="ts">
	import { TAG_HEX } from './teams';
	import type { Tag } from './types';

	let { tag, on = true, onclick }: { tag: Tag; on?: boolean; onclick?: () => void } = $props();
	const color = $derived(TAG_HEX[tag.color] ?? '#888');
</script>

{#if onclick}
	<button type="button" class="tag" class:off={!on} style="--c: {color}" {onclick} aria-pressed={on}>
		{#if tag.builtin}<span aria-hidden="true">🔒</span>{/if}{tag.name}
	</button>
{:else}
	<span class="tag" style="--c: {color}">{tag.name}</span>
{/if}

<style>
	.tag { display: inline-flex; gap: 3px; align-items: center; border: 1px solid var(--c); color: var(--text);
		background: color-mix(in srgb, var(--c) 30%, transparent); border-radius: 10px; padding: 1px 8px;
		font-size: 12px; line-height: 18px; }
	button.tag { cursor: pointer; }
	.off { background: transparent; opacity: 0.7; }
</style>
```

- [ ] **Step 6: Characters filter logic** — in `frontend/src/lib/status.ts` import `matchesTeamTags` from `./teams`, extend `Filters` and `emptyFilters`, and add the check to `matches`:

```ts
export interface Filters { elements: string[]; weapons: string[]; rarities: number[]; search: string; teamTags: number[] }

export function emptyFilters(): Filters {
	return { elements: [], weapons: [], rarities: [], search: '', teamTags: [] };
}
```

and in `matches`, before the search check:

```ts
	if (!matchesTeamTags(c.team_tags ?? [], f.teamTags)) return false;
```

- [ ] **Step 7: Enable the nav** — in `frontend/src/routes/+layout.svelte` change the Teams entry to `{ label: 'Teams', href: '/teams' },`.

- [ ] **Step 8: Run checks**

Run: `cd frontend; npm test; npm run check`
Expected: tests PASS. `svelte-check` may report the new `Dashboard.build_teams` / `CharacterDetail.teams` fields as unused — that is fine; it must report **0 errors**. If an existing test fixture builds a `Character` or `Dashboard` object literal, add `team_tags: []` / `build_teams: []` to it.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/lib frontend/src/routes/+layout.svelte
git commit -m "feat(teams): frontend types, API client, team helpers, tag chip, nav"
```

---

### Task 8: Teams page — cards, shortfall panel, tag filter, reorder, Manage tags

**Files:**
- Create: `frontend/src/lib/TeamCard.svelte`, `frontend/src/lib/TagManager.svelte`, `frontend/src/routes/teams/+page.svelte`

**Interfaces:**
- Consumes: Task 7 helpers and API; `MaterialTile` (`{name, icon, rarity, view, testid}`), `gapLabel`, `gapsSettled`, `shouldPoll` (`$lib/materials`), `imgSrc` (`$lib/img`), `sync.version` (`$lib/sync.svelte`).
- Produces: `TeamCard` props `{ team: Team; gaps: GapStatus; connected: boolean; now: number; onBuildAgain: (m: TeamMember) => void; onMove: (delta: -1 | 1) => void; first: boolean; last: boolean }`; `TagManager` props `{ onChange: () => void }`. Test ids used by Task 11: `team-<id>`, `team-shortfall-<id>`, `tag-filter`, `new-team`.

- [ ] **Step 1: TeamCard** — `frontend/src/lib/TeamCard.svelte`:

```svelte
<script lang="ts">
	import { imgSrc } from './img';
	import { gapLabel, gapsSettled } from './materials';
	import MaterialTile from './MaterialTile.svelte';
	import TagChip from './TagChip.svelte';
	import { MAX_MEMBERS, farmRows, memberLine, teamTileView, weaponLine } from './teams';
	import type { GapStatus, Team, TeamMember } from './types';

	let { team, gaps, connected, now, onBuildAgain, onMove, first, last }: {
		team: Team; gaps: GapStatus; connected: boolean; now: number; onBuildAgain: (m: TeamMember) => void;
		onMove: (delta: -1 | 1) => void; first: boolean; last: boolean;
	} = $props();

	let notesOpen = $state(false);
	const empty = $derived(Array.from({ length: MAX_MEMBERS - team.members.length }));
	const rows = $derived(farmRows(team.shortfall ?? []));
	const anyNotCalculated = $derived(team.members.some((m) => m.not_calculated));
	const pct = (v: number | null) => Math.round((v ?? 0) * 100);
</script>

<article class="team panel" id="team-{team.id}" data-testid="team-{team.id}">
	<header>
		<span class="handle" title="Drag to reorder" aria-hidden="true">⋮⋮</span>
		<h2>{team.name}</h2>
		<div class="tags">{#each team.tags as t (t.id)}<TagChip tag={t} />{/each}</div>
		<div class="actions">
			<button type="button" onclick={() => onMove(-1)} disabled={first} aria-label="Move {team.name} up">↑</button>
			<button type="button" onclick={() => onMove(1)} disabled={last} aria-label="Move {team.name} down">↓</button>
			<a href="/teams/{team.id}">Edit</a>
		</div>
	</header>

	<div class="slots">
		{#each team.members as m (m.id)}
			<div class="slot r{m.rarity} st-{m.status}">
				<a href={m.slug ? `/characters/${m.slug}` : undefined} class="face" aria-label={m.name}>
					{#if imgSrc(m.icon)}<img src={imgSrc(m.icon)} alt="" />{:else}<div class="ph">?</div>{/if}
				</a>
				<div class="name">{m.name}</div>
				<div class="badge st-{m.status}">{m.prefarming ? 'Pre-farming' : m.status}</div>
				{#if memberLine(m)}<div class="line">{memberLine(m)}</div>{/if}
				{#if m.goal === 'build' && m.progress !== null}
					<div class="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct(m.progress)}>
						<i style="width: {pct(m.progress)}%"></i>
					</div>
				{/if}
				{#if m.weapon}
					<div class="line weapon">
						{#if imgSrc(m.weapon.icon)}<img src={imgSrc(m.weapon.icon)} alt="" />{/if}{weaponLine(m)}
					</div>
				{/if}
				{#if m.artifact_line}<div class="line muted">{m.artifact_line}</div>{/if}
				{#if m.role}<div class="role">{m.role}</div>{/if}
				{#if m.not_building}
					<div class="warn">Not building <button type="button" onclick={() => onBuildAgain(m)}>Build again</button></div>
				{/if}
				{#if m.not_calculated}<div class="muted small">Not calculated</div>{/if}
			</div>
		{/each}
		{#each empty as _e, i (i)}<div class="slot empty" aria-hidden="true"></div>{/each}
	</div>

	{#if team.notes}
		<p class="notes" class:open={notesOpen}>{team.notes}</p>
		<button type="button" class="link" onclick={() => (notesOpen = !notesOpen)}>{notesOpen ? 'Less' : 'More'}</button>
	{/if}

	{#if team.shortfall !== null}
		<section class="shortfall" data-testid="team-shortfall-{team.id}">
			<h3>To finish this team {#if team.progress !== null}<span class="muted">· {pct(team.progress)}%</span>{/if}</h3>
			{#if !connected}
				<p class="muted">Connect HoYoLAB to calculate</p>
			{:else if !gaps.computed_at}
				<p class="muted">Shortfall appears after the next sync</p>
			{:else}
				{#if gaps.stale || gaps.pending || gaps.ok === false}<p class="muted">{gapLabel(gaps, now)}</p>{/if}
				{#if rows.length > 0}
					<div class="tiles">
						{#each rows as r (r.id)}
							<MaterialTile name={r.name} icon={r.icon} rarity={r.rarity} view={teamTileView(r)} testid="team-{team.id}-tile-{r.id}" />
						{/each}
					</div>
				{:else if !anyNotCalculated && gapsSettled(gaps)}
					<p class="ok">Everything in the bag ✓</p>
				{:else}
					<p class="muted">Not calculated yet</p>
				{/if}
			{/if}
		</section>
	{/if}
</article>

<style>
	.team { margin-bottom: 12px; }
	header { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; }
	header h2 { margin: 0; font-size: 18px; }
	.handle { cursor: grab; color: var(--muted); }
	.tags { display: flex; gap: 4px; flex-wrap: wrap; }
	.actions { margin-left: auto; display: flex; gap: 6px; align-items: center; }
	.slots { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; margin-top: 10px; }
	.slot { background: var(--panel-2); border-radius: 10px; padding: 8px; font-size: 12px; min-height: 120px; }
	.slot.empty { border: 2px dashed var(--line); background: none; }
	.face img, .ph { width: 64px; height: 64px; border-radius: 8px; display: block; background: var(--r0); }
	.r5 .face img { background: var(--r5); } .r4 .face img { background: var(--r4); }
	.ph { display: grid; place-items: center; color: var(--muted); }
	.st-unobtained .face img { filter: grayscale(1); opacity: 0.5; }
	.name { font-weight: 600; margin-top: 4px; }
	.badge { font-size: 11px; color: var(--muted); text-transform: capitalize; }
	.badge.st-building { color: var(--building); }
	.line { color: var(--text); }
	.weapon { display: flex; gap: 4px; align-items: center; }
	.weapon img { width: 20px; height: 20px; }
	.role { font-style: italic; color: var(--muted); }
	.warn { color: var(--warn); }
	.bar { height: 5px; background: #444; border-radius: 3px; margin: 4px 0; }
	.bar i { display: block; height: 100%; background: var(--building); border-radius: 3px; }
	.notes { white-space: pre-wrap; overflow: hidden; display: -webkit-box; -webkit-line-clamp: 2; line-clamp: 2;
		-webkit-box-orient: vertical; margin: 8px 0 0; }
	.notes.open { display: block; }
	.link { background: none; border: none; color: var(--accent); padding: 0; cursor: pointer; }
	.shortfall { margin-top: 10px; border-top: 1px solid var(--line); padding-top: 8px; }
	.shortfall h3 { margin: 0 0 6px; font-size: 14px; }
	.tiles { display: flex; flex-wrap: wrap; gap: 8px; }
	.ok { color: var(--accent); }
	.small { font-size: 11px; }
</style>
```

- [ ] **Step 2: TagManager** — `frontend/src/lib/TagManager.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from './api';
	import TagChip from './TagChip.svelte';
	import { TAG_COLORS, TAG_HEX } from './teams';
	import type { TagWithCount } from './types';

	let { onChange }: { onChange: () => void } = $props();
	let tags = $state<TagWithCount[]>([]);
	let newName = $state('');
	let error = $state<string | null>(null);

	onMount(load);

	async function load() {
		try {
			tags = await api.tags();
		} catch (e) {
			error = errorMessage(e);
		}
	}

	async function run(fn: () => Promise<unknown>) {
		try {
			await fn();
			error = null;
			await load();
			onChange();
		} catch (e) {
			error = errorMessage(e);
		}
	}

	function rename(t: TagWithCount, name: string) {
		if (name.trim() && name.trim() !== t.name) run(() => api.updateTag(t.id, { name: name.trim() }));
	}

	function remove(t: TagWithCount) {
		const n = t.team_count;
		if (confirm(`Delete tag "${t.name}"? ${n} ${n === 1 ? 'team loses' : 'teams lose'} it. Goals are not changed.`)) {
			run(() => api.deleteTag(t.id));
		}
	}

	function create(ev: SubmitEvent) {
		ev.preventDefault();
		const name = newName.trim();
		if (name) run(async () => { await api.createTag(name); newName = ''; });
	}
</script>

<section class="panel" data-testid="tag-manager">
	<h2>Tags</h2>
	{#if error}<p class="error">{error}</p>{/if}
	<ul>
		{#each tags as t (t.id)}
			<li>
				<TagChip tag={t} />
				{#if t.builtin}
					<span class="muted">built-in</span>
				{:else}
					<input value={t.name} aria-label="Rename {t.name}" maxlength="30"
						onchange={(e) => rename(t, (e.currentTarget as HTMLInputElement).value)} />
				{/if}
				<span class="swatches">
					{#each TAG_COLORS as c (c)}
						<button type="button" class="sw" class:on={t.color === c} style="background: {TAG_HEX[c]}"
							aria-label="Colour {c} for {t.name}" onclick={() => run(() => api.updateTag(t.id, { color: c }))}></button>
					{/each}
				</span>
				<span class="muted">{t.team_count} {t.team_count === 1 ? 'team' : 'teams'}</span>
				{#if !t.builtin}<button type="button" onclick={() => remove(t)}>Delete</button>{/if}
			</li>
		{/each}
	</ul>
	<form onsubmit={create}>
		<input bind:value={newName} placeholder="New tag" maxlength="30" aria-label="New tag name" />
		<button type="submit">Add tag</button>
	</form>
</section>

<style>
	ul { list-style: none; padding: 0; margin: 0 0 8px; }
	li { display: flex; align-items: center; gap: 8px; padding: 4px 0; flex-wrap: wrap; }
	.swatches { display: inline-flex; gap: 3px; }
	.sw { width: 16px; height: 16px; border-radius: 50%; border: 2px solid transparent; padding: 0; cursor: pointer; }
	.sw.on { border-color: var(--text); }
</style>
```

- [ ] **Step 3: Teams page** — `frontend/src/routes/teams/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { shouldPoll } from '$lib/materials';
	import { sync } from '$lib/sync.svelte';
	import TagChip from '$lib/TagChip.svelte';
	import TagManager from '$lib/TagManager.svelte';
	import TeamCard from '$lib/TeamCard.svelte';
	import {
		filterTeams, loadTeamFilter, moveItem, saveTeamFilter, toggleTag, toggleUntagged, type TeamFilter
	} from '$lib/teams';
	import type { TagWithCount, TeamMember, TeamsResponse } from '$lib/types';

	let data = $state<TeamsResponse | null>(null);
	let tags = $state<TagWithCount[]>([]);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let filter = $state<TeamFilter>(loadTeamFilter());
	let showTags = $state(false);
	let dragId = $state<number | null>(null);
	let now = $state(Date.now());
	const shown = $derived(data ? filterTeams(data.teams, filter) : []);

	$effect(() => {
		void sync.version;
		load();
	});

	onMount(() => {
		const t = setInterval(() => {
			now = Date.now();
			if (shouldPoll(data?.gaps)) load();
		}, 3000);
		return () => clearInterval(t);
	});

	async function load() {
		try {
			[data, tags] = await Promise.all([api.teams(), api.tags()]);
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	function setFilter(f: TeamFilter) {
		filter = f;
		saveTeamFilter(f);
	}

	async function reorderTo(from: number, to: number) {
		if (!data) return;
		const before = data.teams;
		const teams = moveItem(before, from, to);
		if (teams === before) return;
		data = { ...data, teams };
		try {
			await api.reorderTeams(teams.map((t) => t.id));
		} catch (e) {
			data = { ...data, teams: before };
			toast = `Could not reorder: ${errorMessage(e)}`;
		}
	}

	function indexOf(id: number): number {
		return data ? data.teams.findIndex((t) => t.id === id) : -1;
	}

	function drop(targetId: number) {
		if (dragId !== null && dragId !== targetId) reorderTo(indexOf(dragId), indexOf(targetId));
		dragId = null;
	}

	async function buildAgain(m: TeamMember) {
		try {
			await api.setGoal(m.id, { goal: 'build' });
			await load();
		} catch (e) {
			toast = `Could not set ${m.name} to Build: ${errorMessage(e)}`;
		}
	}
</script>

<div class="head">
	<h1>Teams</h1>
	<a class="button primary" href="/teams/new" data-testid="new-team">New team</a>
	<button type="button" onclick={() => (showTags = !showTags)} aria-expanded={showTags}>Manage tags</button>
</div>

<div class="filters" data-testid="tag-filter">
	<button type="button" class="chip" class:on={!filter.untagged && filter.tagIds.length === 0}
		onclick={() => setFilter({ tagIds: [], untagged: false })}>All</button>
	{#each tags as t (t.id)}
		<TagChip tag={t} on={filter.tagIds.includes(t.id)} onclick={() => setFilter(toggleTag(filter, t.id))} />
	{/each}
	<button type="button" class="chip" class:on={filter.untagged} onclick={() => setFilter(toggleUntagged(filter))}>Untagged</button>
</div>

{#if showTags}<TagManager onChange={load} />{/if}
{#if toast}<div class="toast error">{toast} <button type="button" onclick={() => (toast = null)}>Dismiss</button></div>{/if}
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.teams.length === 0}
		<section class="panel">
			<h2>Make your first team</h2>
			<p class="muted">Tag a team <strong>Build</strong> to add its members to the planner.</p>
			<a href="/teams/new">New team</a>
		</section>
	{:else if shown.length === 0}
		<p class="muted">No team has these tags.</p>
	{/if}
	{#each shown as team (team.id)}
		<div role="listitem" draggable="true" ondragstart={() => (dragId = team.id)} ondragend={() => (dragId = null)}
			ondragover={(e) => e.preventDefault()} ondrop={() => drop(team.id)}>
			<TeamCard {team} gaps={data.gaps} connected={data.connected} {now} onBuildAgain={buildAgain}
				onMove={(d) => reorderTo(indexOf(team.id), indexOf(team.id) + d)}
				first={indexOf(team.id) === 0} last={indexOf(team.id) === data.teams.length - 1} />
		</div>
	{/each}
{:else if !error}
	<p class="muted">Loading…</p>
{/if}

<style>
	.head { display: flex; align-items: center; gap: 12px; }
	.filters { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0 12px; align-items: center; }
</style>
```

If the global stylesheet has no `.button`/`.primary`/`.chip`/`.toast` classes, check `frontend/src/app.css` and the Characters page for the classes already in use and reuse those names (the Characters page uses `chip`, `on`, `toast error`).

- [ ] **Step 4: Check**

Run: `cd frontend; npm run check; npm test`
Expected: 0 errors; tests PASS.

- [ ] **Step 5: Look at it** — run `cd backend; ..\.venv\Scripts\python -m app.devseed --root ..\.e2e-data` then start the app on the seeded data (`$env:GT_ROOT='..\.e2e-data'; $env:GT_OFFLINE='1'; ..\.venv\Scripts\python ..\run.py`) and open `/teams`: two cards; "Abyss Furina" shows the shortfall panel and Xingqiu "Not building"; the abyss chip filters to one card; ↓ on the first card swaps them and survives a reload. Stop the server afterwards.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/TeamCard.svelte frontend/src/lib/TagManager.svelte frontend/src/routes/teams/+page.svelte
git commit -m "feat(teams): Teams page with tag filter, reorder, shortfall panel and tag manager"
```

---

### Task 9: Team editor

**Files:**
- Create: `frontend/src/lib/TeamEditor.svelte`, `frontend/src/routes/teams/new/+page.svelte`, `frontend/src/routes/teams/[id]/+page.svelte`

**Interfaces:**
- Consumes: `api.characters/team/tags/createTeam/updateTeam/deleteTeam`; `addMember`, `removeMember`, `moveItem`, `willRaise`, `raisedMessage`, `BUILD_TAG_ID`, `MAX_MEMBERS` (Task 7); `CharacterCard` is **not** reused (its hover goal switch would change goals from the editor) — the editor renders its own picker buttons with the same art; `ELEMENTS`, `WEAPON_TYPES`, `emptyFilters`, `matches` (`$lib/status`).
- Produces: `TeamEditor` props `{ teamId: number | null }`. Test ids for Task 11: `pick-<slug>`, `slot-<index>`, labels `Team name`, `Add tag`, buttons `Save`, `Delete team`.

- [ ] **Step 1: The editor** — `frontend/src/lib/TeamEditor.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { beforeNavigate, goto } from '$app/navigation';
	import { ApiError, api, errorMessage } from './api';
	import { imgSrc } from './img';
	import { ELEMENTS, WEAPON_TYPES, emptyFilters, matches, type Filters } from './status';
	import TagChip from './TagChip.svelte';
	import { BUILD_TAG_ID, MAX_MEMBERS, addMember, moveItem, raisedMessage, removeMember, willRaise } from './teams';
	import type { Character, MemberDraft, TagWithCount } from './types';

	let { teamId }: { teamId: number | null } = $props();

	let chars = $state<Character[]>([]);
	let tags = $state<TagWithCount[]>([]);
	let name = $state('');
	let notes = $state('');
	let members = $state<MemberDraft[]>([]);
	let tagIds = $state<number[]>([]);
	let newTags = $state<string[]>([]);
	let tagInput = $state('');
	let filters = $state<Filters>(emptyFilters());
	let original = $state({ memberIds: [] as number[], hadBuild: false });
	let snapshot = $state('');
	let loading = $state(true);
	let missing = $state(false);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let fieldError = $state<string | null>(null);

	const byId = $derived(new Map(chars.map((c) => [c.id, c])));
	const hasBuild = $derived(tagIds.includes(BUILD_TAG_ID));   // a typed "build" resolves to the Build tag itself
	const raising = $derived(willRaise(chars, { members, hasBuild }, original));
	const pickable = $derived(chars.filter((c) => matches(c, filters)));
	let dragSlot = $state<number | null>(null);
	const formState = () => JSON.stringify({ name, notes, members, tagIds, newTags });
	const dirty = $derived(!loading && formState() !== snapshot);

	onMount(async () => {
		try {
			const [c, t] = await Promise.all([api.characters(), api.tags()]);
			chars = c;
			tags = t;
			if (teamId !== null) {
				const { team } = await api.team(teamId);
				name = team.name;
				notes = team.notes;
				members = team.members.map((m) => ({ character_id: m.id, role: m.role }));
				tagIds = team.tags.map((x) => x.id);
				original = { memberIds: members.map((m) => m.character_id), hadBuild: team.has_build_tag };
			}
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) missing = true;
			else error = errorMessage(e);
		} finally {
			loading = false;
			snapshot = formState();
		}
	});

	beforeNavigate(({ cancel }) => {
		if (dirty && !saving && !confirm('Leave without saving this team?')) cancel();
	});

	$effect(() => {
		const warn = (e: BeforeUnloadEvent) => {
			if (dirty) e.preventDefault();
		};
		window.addEventListener('beforeunload', warn);
		return () => window.removeEventListener('beforeunload', warn);
	});

	function toggleTagId(id: number) {
		tagIds = tagIds.includes(id) ? tagIds.filter((t) => t !== id) : [...tagIds, id];
	}

	function addTypedTag(ev: SubmitEvent) {
		ev.preventDefault();
		const typed = tagInput.trim();
		if (!typed) return;
		const existing = tags.find((t) => t.name.toLowerCase() === typed.toLowerCase());
		if (existing) {
			if (!tagIds.includes(existing.id)) tagIds = [...tagIds, existing.id];
		} else if (!newTags.some((t) => t.toLowerCase() === typed.toLowerCase())) {
			newTags = [...newTags, typed];
		}
		tagInput = '';
	}

	function toggle<T>(list: T[], value: T): T[] {
		return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
	}

	async function save() {
		fieldError = null;
		if (!name.trim()) return void (fieldError = 'Team name is required');
		if (members.length === 0) return void (fieldError = 'A team needs 1 to 4 members');
		saving = true;
		const body = { name, notes, members, tag_ids: tagIds, new_tags: newTags };
		try {
			const res = teamId === null ? await api.createTeam(body) : await api.updateTeam(teamId, body);
			const msg = res.raised.length ? `Saved · ${raisedMessage(res.raised.length)}` : 'Saved';
			snapshot = formState();
			await goto(`/teams?saved=${encodeURIComponent(msg)}#team-${res.team.id}`);
		} catch (e) {
			if (e instanceof ApiError && e.status === 422) fieldError = e.message;
			else error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	async function remove() {
		if (teamId === null || !confirm(`Delete "${name}"? Goals are not changed.`)) return;
		try {
			saving = true;
			await api.deleteTeam(teamId);
			snapshot = formState();
			await goto('/teams');
		} catch (e) {
			error = errorMessage(e);
		} finally {
			saving = false;
		}
	}
</script>

{#if loading}
	<p class="muted">Loading…</p>
{:else if missing}
	<p>This team no longer exists. <a href="/teams">Back to Teams</a></p>
{:else}
	<h1>{teamId === null ? 'New team' : 'Edit team'}</h1>
	{#if error}<div class="toast error">{error} <button type="button" onclick={() => (error = null)}>Dismiss</button></div>{/if}

	<section class="panel form">
		<label>Team name <input bind:value={name} maxlength="60" aria-label="Team name" /></label>
		<label>Notes <textarea bind:value={notes} maxlength="2000" rows="3" aria-label="Notes"></textarea></label>

		<div class="tagrow">
			{#each tags as t (t.id)}<TagChip tag={t} on={tagIds.includes(t.id)} onclick={() => toggleTagId(t.id)} />{/each}
			{#each newTags as nt (nt)}
				<TagChip tag={{ id: -1, name: `${nt} (new)`, color: 'blue', builtin: false }}
					onclick={() => (newTags = newTags.filter((x) => x !== nt))} />
			{/each}
			<form onsubmit={addTypedTag}>
				<input bind:value={tagInput} maxlength="30" placeholder="Add or create tag" aria-label="Add tag" />
			</form>
		</div>

		<div class="slots">
			{#each Array.from({ length: MAX_MEMBERS }) as _x, i (i)}
				{@const m = members[i]}
				{@const c = m ? byId.get(m.character_id) : undefined}
				<div class="slot" class:empty={!m} data-testid="slot-{i}" role="listitem" draggable={!!m}
					ondragstart={() => (dragSlot = i)} ondragend={() => (dragSlot = null)}
					ondragover={(e) => e.preventDefault()}
					ondrop={() => { if (dragSlot !== null && m) members = moveItem(members, dragSlot, i); dragSlot = null; }}>
					{#if m}
						{#if c && imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt="" />{/if}
						<div class="name">{c?.name ?? `Character ${m.character_id}`}</div>
						<input value={m.role} maxlength="40" placeholder="Role" aria-label="Role for {c?.name ?? m.character_id}"
							oninput={(e) => (members = members.map((x, j) => (j === i ? { ...x, role: (e.currentTarget as HTMLInputElement).value } : x)))} />
						<div class="slot-actions">
							<button type="button" disabled={i === 0} onclick={() => (members = moveItem(members, i, i - 1))} aria-label="Move left">←</button>
							<button type="button" disabled={i === members.length - 1} onclick={() => (members = moveItem(members, i, i + 1))} aria-label="Move right">→</button>
							<button type="button" onclick={() => (members = removeMember(members, i))} aria-label="Remove {c?.name ?? m.character_id}">×</button>
						</div>
					{:else}
						<span class="muted">Empty</span>
					{/if}
				</div>
			{/each}
		</div>
		{#if raising.length}<p class="warn">Saving raises {raising.join(', ')} to Build</p>{/if}
		{#if fieldError}<p class="error">{fieldError}</p>{/if}

		<div class="buttons">
			<button type="button" class="primary" onclick={save} disabled={saving}>Save</button>
			<a href="/teams">Cancel</a>
			{#if teamId !== null}<button type="button" class="danger" onclick={remove} disabled={saving}>Delete team</button>{/if}
		</div>
	</section>

	<section class="panel">
		<h2>Add members</h2>
		<div class="filters">
			<input placeholder="Search name" bind:value={filters.search} aria-label="Search characters" />
			{#each ELEMENTS as el (el)}
				<button type="button" class="chip" class:on={filters.elements.includes(el)} onclick={() => (filters.elements = toggle(filters.elements, el))}>{el}</button>
			{/each}
			{#each WEAPON_TYPES as w (w)}
				<button type="button" class="chip" class:on={filters.weapons.includes(w)} onclick={() => (filters.weapons = toggle(filters.weapons, w))}>{w}</button>
			{/each}
			{#each [5, 4] as r (r)}
				<button type="button" class="chip" class:on={filters.rarities.includes(r)} onclick={() => (filters.rarities = toggle(filters.rarities, r))}>{r}★</button>
			{/each}
		</div>
		{#if members.length >= MAX_MEMBERS}<p class="muted">The team is full. Remove a member to add another.</p>{/if}
		<div class="grid">
			{#each pickable as c (c.id)}
				{@const inTeam = members.some((m) => m.character_id === c.id)}
				<button type="button" class="pick r{c.rarity} st-{c.status}" data-testid="pick-{c.slug}"
					disabled={inTeam || members.length >= MAX_MEMBERS} onclick={() => (members = addMember(members, c.id))}
					aria-label="Add {c.name}">
					{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt="" loading="lazy" />{:else}<div class="ph">?</div>{/if}
					<span>{c.name}</span>
					{#if inTeam}<span class="muted small">In team</span>{/if}
				</button>
			{/each}
		</div>
	</section>
{/if}

<style>
	.form label { display: flex; flex-direction: column; gap: 4px; margin-bottom: 8px; }
	.tagrow { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 10px; }
	.slots { display: grid; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); gap: 10px; }
	.slot { background: var(--panel-2); border-radius: 10px; padding: 8px; min-height: 110px; }
	.slot.empty { border: 2px dashed var(--line); background: none; display: grid; place-items: center; }
	.slot img { width: 56px; height: 56px; border-radius: 8px; }
	.slot input { width: 100%; }
	.slot-actions { display: flex; gap: 4px; margin-top: 4px; }
	.buttons { display: flex; gap: 10px; align-items: center; margin-top: 10px; }
	.danger { margin-left: auto; }
	.warn { color: var(--warn); }
	.filters { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 10px; }
	.grid { display: flex; flex-wrap: wrap; gap: 8px; }
	.pick { width: 96px; display: flex; flex-direction: column; align-items: center; gap: 2px; padding: 4px;
		background: var(--panel-2); border: none; border-radius: 10px; color: var(--text); cursor: pointer; font-size: 12px; }
	.pick:disabled { opacity: 0.5; cursor: default; }
	.pick img, .pick .ph { width: 80px; height: 80px; border-radius: 8px; background: var(--r0); }
	.pick.r5 img { background: var(--r5); } .pick.r4 img { background: var(--r4); }
	.pick.st-unobtained img { filter: grayscale(1); opacity: 0.6; }
	.small { font-size: 11px; }
</style>
```

- [ ] **Step 2: Routes** — `frontend/src/routes/teams/new/+page.svelte`:

```svelte
<script lang="ts">
	import TeamEditor from '$lib/TeamEditor.svelte';
</script>

<TeamEditor teamId={null} />
```

`frontend/src/routes/teams/[id]/+page.svelte`:

```svelte
<script lang="ts">
	import { page } from '$app/state';
	import TeamEditor from '$lib/TeamEditor.svelte';

	const id = $derived(Number(page.params.id));
</script>

{#key id}
	{#if Number.isInteger(id)}
		<TeamEditor teamId={id} />
	{:else}
		<p>This team no longer exists. <a href="/teams">Back to Teams</a></p>
	{/if}
{/key}
```

- [ ] **Step 3: Show the save message on the Teams page** — in `frontend/src/routes/teams/+page.svelte` import `page` from `$app/state` and add, inside the `<script>`:

```ts
	let saved = $state<string | null>(page.url.searchParams.get('saved'));
	onMount(() => {
		if (saved) history.replaceState(history.state, '', `/teams${location.hash}`);
	});
```

and right under the `toast` block in the markup:

```svelte
{#if saved}<div class="toast ok" role="status">{saved} <button type="button" onclick={() => (saved = null)}>Dismiss</button></div>{/if}
```

(If the app has no `.toast.ok` style, add `.ok { color: var(--accent); }` in this page's `<style>`.)

- [ ] **Step 4: Check**

Run: `cd frontend; npm run check; npm test`
Expected: 0 errors; tests PASS.

- [ ] **Step 5: Look at it** — with the seeded app running (Task 8 Step 5): New team → pick Nahida and Xiangling → type `abyss` + Enter (existing tag selected, not "(new)") → click Build chip → "Saving raises Nahida, Xiangling to Build" appears → Save → Teams page shows "Saved · Raised 2 characters to Build". Edit the team, change the name, click the Teams nav link → the leave warning appears. Open `/teams/9999` → "This team no longer exists". Stop the server.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/TeamEditor.svelte frontend/src/routes/teams
git commit -m "feat(teams): team editor with character picker, tags, raise preview and leave warning"
```

---

### Task 10: Dashboard Build teams card, Characters tag filter, In teams panel

**Files:**
- Modify: `frontend/src/routes/+page.svelte`, `frontend/src/routes/characters/+page.svelte`, `frontend/src/routes/characters/[slug]/+page.svelte`

**Interfaces:**
- Consumes: `Dashboard.build_teams`, `CharacterDetail.teams`, `Character.team_tags`, `api.tags()`, `TagChip`, `teamTileView`, `MaterialTile`, `imgSrc`. Test ids for Task 11: `build-teams`, `team-tag-filter`, `in-teams`.

- [ ] **Step 1: Dashboard card** — in `frontend/src/routes/+page.svelte` import `{ teamTileView } from '$lib/teams'` and add this section right after the Pity section (`data-testid="pity-card"`):

```svelte
	<section class="panel" data-testid="build-teams">
		<h2>Build teams</h2>
		{#if data.build_teams.length === 0}
			<p class="muted"><a href="/teams">Tag a team Build to plan it here</a></p>
		{:else}
			{#each data.build_teams as t (t.id)}
				<div class="team-row">
					<a class="title" href="/teams#team-{t.id}">{t.name}</a>
					<span class="avatars">
						{#each t.members as m (m.id)}
							<a href="/characters/{m.slug}" title={m.name}>{#if imgSrc(m.icon)}<img src={imgSrc(m.icon)} alt={m.name} />{/if}</a>
						{/each}
					</span>
					{#if t.progress !== null}<span class="muted">{Math.round(t.progress * 100)}%</span>{/if}
					<span class="tiles-row">
						{#each t.top as m (m.id)}
							<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={teamTileView(m)} />
						{/each}
					</span>
					{#if t.more > 0}<a href="/teams#team-{t.id}">+{t.more} more</a>{/if}
					{#if t.has_shortfall && t.top.length === 0 && gapsSettled(data.gaps)}<span class="ok">Everything in the bag ✓</span>{/if}
				</div>
			{/each}
		{/if}
	</section>
```

and add to that file's `<style>`:

```css
	.team-row { display: flex; align-items: center; gap: 10px; flex-wrap: wrap; padding: 6px 0; border-bottom: 1px solid var(--line); }
	.team-row:last-child { border-bottom: none; }
	.team-row .avatars img { width: 32px; height: 32px; border-radius: 50%; }
	.ok { color: var(--accent); }
```

(`gapsSettled`, `imgSrc`, `MaterialTile` are already imported on this page; if `.avatars` / `.tiles-row` already exist there, keep the existing rules.)

- [ ] **Step 2: Characters tag filter** — in `frontend/src/routes/characters/+page.svelte` import `TagChip` and the `Tag` type, add `let tags = $state<Tag[]>([]);`, load tags alongside characters (`[chars, tags] = await Promise.all([api.characters(), api.tags()]);`), and add after the existing filters `<div>`:

```svelte
{#if tags.length}
	<div class="filters" data-testid="team-tag-filter">
		<span class="muted">Team tag</span>
		{#each tags as t (t.id)}
			<TagChip tag={t} on={filters.teamTags.includes(t.id)} onclick={() => (filters.teamTags = toggle(filters.teamTags, t.id))} />
		{/each}
	</div>
{/if}
```

- [ ] **Step 3: In teams panel** — in `frontend/src/routes/characters/[slug]/+page.svelte` import `TagChip` and add a section after the Build targets panel:

```svelte
		<section class="panel" data-testid="in-teams">
			<h2>In teams</h2>
			{#if c.teams.length === 0}
				<p class="muted">Not in any team</p>
			{:else}
				<ul class="teams">
					{#each c.teams as t (t.id)}
						<li><a href="/teams#team-{t.id}">{t.name}</a> {#each t.tags as tag (tag.id)}<TagChip {tag} />{/each}</li>
					{/each}
				</ul>
			{/if}
		</section>
```

Use the page's existing variable name for the loaded `CharacterDetail` (read the top of the file; the plan assumes `c`). Add `.teams { list-style: none; padding: 0; margin: 0; } .teams li { display: flex; gap: 6px; align-items: center; padding: 2px 0; }` to the page style.

- [ ] **Step 4: Check**

Run: `cd frontend; npm run check; npm test`
Expected: 0 errors; tests PASS.

- [ ] **Step 5: Look at it** — on the seeded app: Dashboard shows "Build teams" with Abyss Furina and up to 5 tiles; Characters → click the `abyss` team-tag chip → only Furina, Bennett, Xingqiu remain (Xingqiu in the collapsed Unobtained section); Bennett's page lists "Abyss Furina" with its tags; Xiangling's says "Not in any team".

- [ ] **Step 6: Commit**

```bash
git add frontend/src/routes
git commit -m "feat(teams): Build teams on the dashboard, team tag filter, In teams panel"
```

---

### Task 11: End-to-end test, README, spec refinements, final checks

**Files:**
- Create: `frontend/e2e/teams.spec.ts`
- Modify: `README.md`, `docs/superpowers/specs/2026-11-21-phase4-teams-design.md` (append §13)

**Interfaces:**
- Consumes: test ids from Tasks 8–10 and the seeded data from Task 6 (Nahida is owned with goal `none` and in no Build team; no other e2e spec changes Nahida).

- [ ] **Step 1: Write the e2e test** — `frontend/e2e/teams.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('a new Build team raises its member and appears with a shortfall panel', async ({ page }) => {
	await page.goto('/teams');
	await expect(page.getByTestId('team-1')).toBeVisible();                    // seeded Abyss Furina
	await expect(page.getByTestId('team-shortfall-1')).toBeVisible();

	await page.getByTestId('new-team').click();
	await page.getByLabel('Team name').fill('Dendro test');
	await page.getByTestId('pick-nahida').click();
	await expect(page.getByTestId('slot-0')).toContainText('Nahida');
	await page.getByRole('button', { name: 'Build', exact: true }).click();
	await expect(page.getByText('Saving raises Nahida to Build')).toBeVisible();
	await page.getByLabel('Add tag').fill('dendro');
	await page.getByLabel('Add tag').press('Enter');
	await page.getByRole('button', { name: 'Save' }).click();

	await expect(page).toHaveURL(/\/teams/);
	await expect(page.getByText('Raised 1 character to Build')).toBeVisible();
	const card = page.locator('article', { hasText: 'Dendro test' });
	await expect(card).toBeVisible();
	await expect(card.locator('[data-testid^="team-shortfall-"]')).toBeVisible();

	await page.getByTestId('tag-filter').getByRole('button', { name: 'dendro' }).click();
	await expect(page.locator('article')).toHaveCount(1);
	await page.getByTestId('tag-filter').getByRole('button', { name: 'All' }).click();
	await expect(page.locator('article')).toHaveCount(3);

	await page.goto('/characters');
	await expect(page.getByTestId('section-building').getByTestId('card-nahida')).toBeVisible();
});
```

- [ ] **Step 2: Run it**

Run: `cd frontend; npm run e2e`
Expected: all specs PASS (characters, planner, wishes, teams). If the Build chip's accessible name includes the lock emoji, change the locator to `getByRole('button', { name: /Build$/ })`.

- [ ] **Step 3: README** — add after the Wishes section:

```markdown
## Teams

Group up to four characters into a team and label it with tags (for example *abyss*, *exploration*, *main*, or none for fun teams). Tags are yours to create, rename, recolour and delete under **Teams → Manage tags**.

**Build** is a built-in tag. Adding it to a team sets every member to Build, so the planner starts farming for them; adding a member to a Build team does the same for that member. Removing the tag, a member or a team never lowers a goal. If you later set a member back to Want or None, the team marks them **Not building** with a **Build again** button.

Each team with Build members shows what is still left to farm **to finish just that team**, as if it got your whole bag first. Materials other Build characters also need are marked *shared*. Build teams also appear on the Dashboard, and the Characters page can filter by team tag.
```

- [ ] **Step 4: Spec refinements** — append to `docs/superpowers/specs/2026-11-21-phase4-teams-design.md`:

```markdown
---

## 13. Refinements made during planning (2026-11-21)

1. Tags get a `name_key` column (lower-cased name, unique) to enforce case-insensitive uniqueness.
2. Notes are capped at 2000 characters.
3. A typed new tag that matches an existing tag case-insensitively reuses that tag instead of failing.
4. Member ids are validated on save, so an unknown member can only appear if the catalogue later drops a character; it renders as a placeholder and no extra game-data refresh is triggered.
5. `GET /api/teams` returns `{gaps, connected, teams}` and `GET /api/teams/{id}` returns `{gaps, connected, team}`; tag filtering happens in the page.
6. The Characters page filters are not persisted, so the Team tag filter is not persisted either.
```

- [ ] **Step 5: Full verification**

Run, and read every result:

```powershell
cd backend; ..\.venv\Scripts\python -m pytest -q
```

```powershell
cd frontend; npm run check; npm test; npm run build; npm run e2e
```

Expected: all backend tests PASS; `svelte-check` 0 errors; Vitest PASS; build succeeds; all Playwright specs PASS.

- [ ] **Step 6: Secret and personal-data check** — `git diff main --stat` lists only code, tests, docs; then:

```powershell
git diff main | Select-String -Pattern 'ltoken|ltuid|cookie_token|authkey=|@gmail|GENSHIN_UID=\d'
```

Expected: no matches (test strings like `SECRET-LTOKEN-222` live in existing tests and are not in this diff). No `.env`, `data/`, or `.e2e-data/` files are staged (`git status --short`).

- [ ] **Step 7: Commit**

```bash
git add frontend/e2e/teams.spec.ts README.md docs/superpowers/specs/2026-11-21-phase4-teams-design.md
git commit -m "test(teams): end-to-end team flow; README Teams section; spec planning refinements"
```
