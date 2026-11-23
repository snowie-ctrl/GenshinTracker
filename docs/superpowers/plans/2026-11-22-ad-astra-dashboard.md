# Ad Astra Dashboard (sub-project 3) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the Dashboard as a two-column, urgency-ordered page. Build characters get a user-set priority, and material counts are allocated to the highest priority first.

**Architecture:** One `GET /api/dashboard` payload is reshaped around the new layout.
- A pure allocator, `backend/app/planner/priority.py`, gives each Build character its `have/need/craft` in priority order.
- Priority is stored as `character_goal.priority`. A new helper, `backend/app/planner/order.py`, sets it whenever a goal changes, and `PUT /api/priority` saves a new order.
- Migration 0008 adds the priority column and four new HoYoLAB notes fields. The calendar snapshot gains each event's `finished` flag.
- The front end becomes a thin page shell plus small components in `frontend/src/lib/dashboard/`.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy 2, Alembic, SQLite, pytest.
- Frontend: SvelteKit (Svelte 5 runes, TypeScript, adapter-static), vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-22-ad-astra-dashboard-design.md`. Read it before starting any task.

## Global Constraints

- Cookie values live only in the git-ignored `.env`; they are never logged, returned by the API or committed.
- Unofficial API code stays in `backend/app/sync/` and `backend/app/wishes/`.
- Test fixtures use only made-up UIDs (800000001).
- No personal data or game art is committed. Images load at runtime through `/api/img` (named `UI_…` icons) or `/api/img/remote`.
- The user's email is never sent to external services.
- The HoYoLAB nickname is never stored. The greeting uses the local `display_name` setting, and "Traveler" when that is blank.
- No manual timers. The only timers are resin, realm currency, the Parametric Transformer and expeditions, all from HoYoLAB notes.
- No new npm or pip dependencies.
- Commands:
  - **Backend tests:** `C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe -m pytest -q`, run from `backend/`. Later steps write this as `PY -m pytest`.
  - **Frontend:** run from `frontend/`: `npm run check`, `npx vitest run`, `npm run build`, and `PYTHON=<that python> npx playwright test`.
- Bubble icon names were verified on 2026-11-22: both enka.network/ui and gi.yatta.moe return 200 for these.
  - `UI_ItemIcon_210` (Original Resin)
  - `UI_ItemIcon_204` (Realm Currency)
  - `UI_ItemIcon_220021` (Parametric Transformer)

  No game icon was found for commissions or expeditions, so they use new original icons (`commission`, `expedition`) added to `frontend/src/lib/icons.ts`.

## Review Focus

1. **An empty account.** Not connected, no notes, no calendar, no Build characters and no wishes. Every panel must show its empty text and nothing may throw. Owner: Task 6 (`test_dashboard_empty_account`) and Task 8 (empty-state markup).
2. **The priority list changing while a save is in flight.** A sync or goal change can land between the user's drag and the save. `PUT /api/priority` must accept a list that is missing new Build ids, appending them, and must reject ids that are no longer Build with 400 rather than crashing. Owner: Task 6 (`test_put_priority_appends_unlisted_and_rejects_stale`).
3. **A material held by nobody, or not needed by everyone.** If the bag holds 0 of an item, or a character has no gap row for an item another character needs, allocation must never go negative or carry items across materials. Owner: Task 3 (`test_allocate_zero_held_and_disjoint_materials`).
4. **A Traveler element alongside a normal character needing the same talent book.** The two elements are separate entries and the shared book is split by priority. Owner: Task 3 (`test_traveler_elements_are_separate_entries`).
5. **An event the user ticked done that HoYoLAB later reports finished, or the reverse.** It must show as done once, never twice, with its toggle locked. Unticking a finished event must not make it look not done. Owner: Task 4 (`test_event_rows_finished_counts_as_done`).

---

## File map

| File | Change | Responsibility |
|---|---|---|
| `backend/migrations/versions/0008_dashboard.py` | create | priority + notes columns, backfill priorities |
| `backend/app/db/models.py` | modify | `CharacterGoal.priority`, four `LiveNotes` columns |
| `backend/app/planner/order.py` | create | `build_order`, `apply_goal`, `set_order` |
| `backend/app/planner/priority.py` | create | `held_counts`, `allocate`, `build_sections` |
| `backend/app/planner/today.py` | modify | priority-ranked characters and card order |
| `backend/app/api/characters.py` | modify | use `apply_goal` |
| `backend/app/teams/goals.py` | modify | use `apply_goal` |
| `backend/app/sync/hoyolab.py` | modify | four new `NotesInfo` fields |
| `backend/app/sync/persist.py` | modify | save the new notes fields |
| `backend/app/sync/chronicle.py` | modify | `EventInfo.finished` |
| `backend/app/events/view.py` | modify | finished counts as done, `ending_within` |
| `backend/app/settings/store.py`, `backend/app/api/settings.py` | modify | `display_name` setting |
| `backend/app/dashboard/__init__.py`, `backend/app/dashboard/view.py` | create | `timers`, `event_list`, `banners_with_pity`, `build_progress` |
| `backend/app/api/dashboard.py` | rewrite | new payload + `PUT /api/priority` |
| `backend/app/devseed.py` | modify | priorities, notes fields, finished event |
| `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts` | modify | new types, `setPriority`, `display_name` |
| `frontend/src/lib/dashboard.ts` (+ `.test.ts`) | create | pure helpers |
| `frontend/src/lib/icons.ts` | modify | `commission`, `expedition` icons |
| `frontend/src/lib/dashboard/*.svelte` | create | the eleven components |
| `frontend/src/routes/+page.svelte` | rewrite | two-column shell |
| `frontend/src/routes/settings/+page.svelte` | modify | Display name field |
| `frontend/src/routes/events/+page.svelte` | modify | lock the toggle on finished events |
| `frontend/e2e/dashboard.spec.ts` | create | Dashboard e2e |
| `frontend/e2e/{planner,events,wishes,profile}.spec.ts` | modify | new test ids |

---

### Task 1: Migration 0008 and model columns

**Files:**
- Create: `backend/migrations/versions/0008_dashboard.py`
- Modify: `backend/app/db/models.py` (classes `LiveNotes` around line 126, `CharacterGoal` around line 188)
- Test: `backend/tests/test_migration_0008.py`

**Interfaces:**
- Produces:
  - `CharacterGoal.priority: int | None`
  - `LiveNotes.commission_bonus_claimed: bool | None`
  - `LiveNotes.realm_currency_full_at: datetime | None`
  - `LiveNotes.transformer_ready_at: datetime | None`
  - `LiveNotes.expeditions_max: int | None`

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_migration_0008.py
from sqlalchemy import inspect, text

from app.db.engine import make_engine
from test_migration_0007 import NOW, downgrade, upgrade


def goal(conn, cid, kind):
    conn.execute(text("INSERT INTO character_goal (character_id, goal, target_level, updated_at) "
                      "VALUES (:c, :g, 90, :t)"), dict(c=cid, g=kind, t=NOW))


def test_upgrade_numbers_existing_build_rows_by_id(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0007")
    with engine.begin() as conn:
        goal(conn, 10000089, "build")
        goal(conn, 10000032, "build")
        goal(conn, 10000047, "want")
    upgrade(engine, "0008")
    with engine.begin() as conn:
        rows = dict(conn.execute(text("SELECT character_id, priority FROM character_goal")).all())
    assert rows == {10000032: 1, 10000089: 2, 10000047: None}
    cols = {c["name"] for c in inspect(engine).get_columns("live_notes")}
    assert {"commission_bonus_claimed", "realm_currency_full_at", "transformer_ready_at",
            "expeditions_max"} <= cols
    engine.dispose()


def test_downgrade_drops_columns(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0008")
    downgrade(engine, "0007")
    insp = inspect(engine)
    assert "priority" not in {c["name"] for c in insp.get_columns("character_goal")}
    assert "expeditions_max" not in {c["name"] for c in insp.get_columns("live_notes")}
    engine.dispose()
```

- [ ] **Step 2: Run the test to see it fail**

Run: `PY -m pytest tests/test_migration_0008.py -q`
Expected: FAIL. Alembic reports that it can't locate revision `0008`.

- [ ] **Step 3: Write the migration**

```python
# backend/migrations/versions/0008_dashboard.py
"""Ad Astra sub-project 3: Dashboard (build priority, more HoYoLAB notes fields)

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-22
"""
import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

NOTES_COLUMNS = (
    ("commission_bonus_claimed", sa.Boolean()),
    ("realm_currency_full_at", sa.DateTime()),
    ("transformer_ready_at", sa.DateTime()),
    ("expeditions_max", sa.Integer()),
)


def upgrade() -> None:
    with op.batch_alter_table("character_goal") as b:
        b.add_column(sa.Column("priority", sa.Integer(), nullable=True))
    with op.batch_alter_table("live_notes") as b:
        for name, type_ in NOTES_COLUMNS:
            b.add_column(sa.Column(name, type_, nullable=True))
    bind = op.get_bind()
    ids = [r[0] for r in bind.execute(sa.text(
        "SELECT character_id FROM character_goal WHERE goal = 'build' ORDER BY character_id"))]
    for n, cid in enumerate(ids, start=1):
        bind.execute(sa.text("UPDATE character_goal SET priority = :p WHERE character_id = :c"),
                     {"p": n, "c": cid})


def downgrade() -> None:
    with op.batch_alter_table("live_notes") as b:
        for name, _type in reversed(NOTES_COLUMNS):
            b.drop_column(name)
    with op.batch_alter_table("character_goal") as b:
        b.drop_column("priority")
```

- [ ] **Step 4: Add the model columns**

In `backend/app/db/models.py`, add a line to `LiveNotes` after `weekly_discounts_max`:

```python
    commission_bonus_claimed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    realm_currency_full_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    transformer_ready_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    expeditions_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

In `CharacterGoal`, add a line after `planned_weapon_id`:

```python
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)   # Build order, 1 = first (sub-project 3)
```

- [ ] **Step 5: Run the tests**

Run: `PY -m pytest tests/test_migration_0008.py tests/test_db.py tests/test_migration_0007.py -q`
Expected: PASS. `test_models_match_migrations` confirms that the model and the migration agree.

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/versions/0008_dashboard.py backend/app/db/models.py backend/tests/test_migration_0008.py
git commit -m "feat(dashboard): migration 0008 adds build priority and notes fields"
```

---

### Task 2: Build priority order and goal transitions

**Files:**
- Create: `backend/app/planner/order.py`
- Modify: `backend/app/api/characters.py` (in `set_goal`, the line `row.goal = new_goal`)
- Modify: `backend/app/teams/goals.py` (in `raise_to_build`, the line `row.goal = "build"`)
- Test: `backend/tests/test_planner_order.py`

**Interfaces:**
- Consumes: `CharacterGoal.priority` (Task 1).
- Produces:
  - `build_order(session) -> list[int]`: all Build character ids in effective order.
  - `apply_goal(session, row: CharacterGoal, new_goal: str) -> None`
  - `set_order(session, order: list[int]) -> None`. Raises `ValueError` with a user-facing message.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_planner_order.py
import pytest

from app.db.models import CharacterGoal
from app.planner.order import apply_goal, build_order, set_order
from app.teams.goals import raise_to_build
from app.domain import Targets
from app.timeutil import utcnow
from helpers import make_client, seed_game


def add(s, cid, goal="none", priority=None):
    row = CharacterGoal(character_id=cid, goal=goal, priority=priority, updated_at=utcnow())
    s.add(row)
    return row


def test_entering_build_appends_and_leaving_clears(session_factory):
    with session_factory.begin() as s:
        a, b, c = add(s, 1), add(s, 2), add(s, 3)
        s.flush()
        apply_goal(s, a, "build")
        apply_goal(s, b, "build")
        assert (a.priority, b.priority) == (1, 2)
        apply_goal(s, a, "want")
        assert a.priority is None
        apply_goal(s, c, "build")
        apply_goal(s, a, "build")
        assert build_order(s) == [2, 3, 1]
        apply_goal(s, b, "build")            # unchanged goal keeps its place
        assert build_order(s) == [2, 3, 1]


def test_rows_without_priority_sort_last_by_id(session_factory):
    with session_factory.begin() as s:
        add(s, 30, "build", None)
        add(s, 20, "build", None)
        add(s, 99, "build", 1)
        add(s, 5, "want", None)
        s.flush()
        assert build_order(s) == [99, 20, 30]


def test_set_order_renumbers_appends_unlisted_and_validates(session_factory):
    with session_factory.begin() as s:
        for cid, p in [(1, 1), (2, 2), (3, 3)]:
            add(s, cid, "build", p)
        add(s, 4, "want")
        s.flush()
        set_order(s, [3, 1])
        assert build_order(s) == [3, 1, 2]
        with pytest.raises(ValueError, match="not set to Build"):
            set_order(s, [4, 1])
        with pytest.raises(ValueError, match="more than once"):
            set_order(s, [1, 1])
        assert build_order(s) == [3, 1, 2]   # failed calls change nothing


def test_teams_raise_appends_priority(session_factory):
    with session_factory.begin() as s:
        add(s, 1, "build", 1)
        s.flush()
        raise_to_build(s, [7, 1], Targets(90, 8, 8, 8, 90))
        assert build_order(s) == [1, 7]


def test_goal_endpoint_sets_and_clears_priority(paths):
    from test_api_characters import setup_data
    from test_api_planner import sf_for
    setup_data(paths)               # Bennett and Nahida are Build rows written directly (priority NULL); Furina owned
    sf = sf_for(paths)

    def furina():
        with sf() as s:
            return s.get(CharacterGoal, 10000089).priority

    with make_client(paths) as client:
        client.put("/api/characters/10000089/goal", json={"goal": "build"})
        assert furina() == 1                                    # NULL rows do not count towards the max
        client.put("/api/characters/10000089/goal", json={"goal": "want"})
        assert furina() is None
        client.put("/api/characters/10000089/goal", json={"goal": "build"})
        assert furina() == 1
        client.put("/api/characters/10000089/goal", json={"targets": {"level": 80, "normal": 6, "skill": 6,
                                                                       "burst": 6, "weapon_level": 80}})
        assert furina() == 1                                    # editing targets keeps the place
    with sf() as s:
        assert build_order(s) == [10000089, 10000032, 10000073]
```

`setup_data` in `backend/tests/test_api_characters.py` seeds Furina (10000089) as owned with no goal row, and Bennett and Nahida as Build. Check the `targets` body against `TargetsIn` in `backend/app/schemas.py` and adjust the key names if they differ.

- [ ] **Step 2: Run the tests to see them fail**

Run: `PY -m pytest tests/test_planner_order.py -q`
Expected: FAIL with `ModuleNotFoundError: app.planner.order`.

- [ ] **Step 3: Implement `order.py`**

```python
# backend/app/planner/order.py
"""Build priority: the order the Dashboard allocates materials in (1 = first)."""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import CharacterGoal

BUILD = "build"


def build_order(session: Session) -> list[int]:
    rows = session.scalars(select(CharacterGoal).where(CharacterGoal.goal == BUILD))
    ordered = sorted(rows, key=lambda r: (r.priority is None, r.priority or 0, r.character_id))
    return [r.character_id for r in ordered]


def _next_priority(session: Session) -> int:
    top = session.scalar(select(func.max(CharacterGoal.priority)).where(CharacterGoal.goal == BUILD))
    return (top or 0) + 1


def apply_goal(session: Session, row: CharacterGoal, new_goal: str) -> None:
    """Change a goal. Entering Build goes to the end of the order; leaving Build forgets the place."""
    if new_goal == row.goal:
        return
    priority = _next_priority(session) if new_goal == BUILD else None
    row.goal = new_goal
    row.priority = priority


def set_order(session: Session, order: list[int]) -> None:
    """Number `order` 1..n; Build characters it leaves out follow in their current order."""
    if len(set(order)) != len(order):
        raise ValueError("A character is listed more than once.")
    rows = {r.character_id: r for r in session.scalars(select(CharacterGoal).where(CharacterGoal.goal == BUILD))}
    stale = [cid for cid in order if cid not in rows]
    if stale:
        raise ValueError(f"Not set to Build: {', '.join(str(c) for c in stale)}. Reload the Dashboard.")
    listed = set(order)
    rest = [cid for cid in build_order(session) if cid not in listed]
    for n, cid in enumerate([*order, *rest], start=1):
        rows[cid].priority = n
    session.flush()
```

- [ ] **Step 4: Use `apply_goal` in both places that change goals**

In `backend/app/api/characters.py`, add `from app.planner.order import apply_goal` and replace `row.goal = new_goal` with:

```python
        apply_goal(s, row, new_goal)
```

In `backend/app/teams/goals.py`, add `from app.planner.order import apply_goal` and replace `row.goal = "build"` with:

```python
        apply_goal(session, row, "build")
```

- [ ] **Step 5: Run the tests**

Run: `PY -m pytest tests/test_planner_order.py tests/test_teams_goals.py tests/test_api_characters.py tests/test_api_teams.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/planner/order.py backend/app/api/characters.py backend/app/teams/goals.py backend/tests/test_planner_order.py
git commit -m "feat(dashboard): build priority order kept on every goal change"
```

---

### Task 3: Priority allocation

**Files:**
- Create: `backend/app/planner/priority.py`
- Test: `backend/tests/test_planner_priority.py`

**Interfaces:**
- Consumes: `PlannerData`, `Total`, `CharRef`, `Material`, `CATEGORY_ORDER` (`app.planner.data`); `chains` (`app.planner.crafting`); `CATEGORY_LABELS` (`app.gamedata.materials`).
- Produces:
  - `held_counts(data) -> dict[int, int]`
  - `allocate(data, order: list[int]) -> dict[int, dict[int, Allocation]]`, where `Allocation(need: int, have: int, craft: int)` is a frozen dataclass.
  - `build_sections(data, order, index, progress: dict[int, float | None]) -> {"builds": [...], "completed": [...]}`.
    - Each `builds` item: `{"character": CharRef dict, "priority": int (1-based position), "progress", "calculated": bool, "ready": bool, "materials": [{"id", "name", "icon", "rarity", "category", "category_label", "need", "have", "craft"}]}`.
    - `completed`: a list of `CharRef` dicts.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_planner_priority.py
from app.planner.data import CharRef, Material, PlannerData, Total
from app.planner.inventory import material_index
from app.planner.priority import Allocation, allocate, build_sections, held_counts


def mat(mid, rarity=3, craft_from=None, category="talent"):
    return Material(mid, f"M{mid}", f"UI_ItemIcon_{mid}", rarity, category, craft_from, [], mid)


BOOKS = {1: mat(1, 2), 2: mat(2, 3, craft_from=1), 3: mat(3, 4, craft_from=2)}
CHARS = {10: CharRef(10, "Bennett", "bennett", None), 20: CharRef(20, "Furina", "furina", None),
         1000000507: CharRef(1000000507, "Cryo Traveler", "cryo-traveler", None),
         1000000502: CharRef(1000000502, "Anemo Traveler", "anemo-traveler", None)}


def data(totals, gaps, netted=False, calculated=frozenset({10, 20, 1000000507, 1000000502})):
    return PlannerData(materials=dict(BOOKS), totals=totals, gaps=gaps, characters=dict(CHARS), domains=[],
                       lack_includes_crafting=netted, calculated=calculated)


def test_held_counts_need_minus_short_plus_spare():
    assert held_counts(data({2: Total(50, 36, 0), 1: Total(0, 0, 9)}, {})) == {2: 14, 1: 9}


def test_user_examples_14_and_32_held():
    gaps = {10: {2: (20, 6)}, 20: {2: (30, 16)}}
    d = data({2: Total(50, 36, 0)}, gaps)                  # 14 held
    a = allocate(d, [10, 20])
    assert a[10][2] == Allocation(20, 14, 0) and a[20][2] == Allocation(30, 0, 0)
    d = data({2: Total(50, 18, 0)}, gaps)                  # 32 held
    a = allocate(d, [10, 20])
    assert a[10][2] == Allocation(20, 20, 0) and a[20][2] == Allocation(30, 12, 0)


def test_leftover_lower_tiers_craft_for_p1_before_p2():
    gaps = {10: {2: (9, 4)}, 20: {2: (6, 4)}}
    d = data({2: Total(15, 7, 0), 1: Total(0, 0, 9)}, gaps)   # 8 blue, 9 green held
    a = allocate(d, [10, 20])
    assert a[10][2] == Allocation(9, 8, 1)                  # 3 green -> 1 blue
    assert a[20][2] == Allocation(6, 0, 2)                  # 6 green left -> 2 blue
    a = allocate(d, [20, 10])
    assert a[20][2] == Allocation(6, 6, 0) and a[10][2] == Allocation(9, 2, 3)


def test_crafting_goes_through_two_tiers():
    d = data({3: Total(1, 1, 0), 1: Total(0, 0, 9)}, {10: {3: (1, 1)}})  # 9 green -> 3 blue -> 1 gold
    assert allocate(d, [10])[10][3] == Allocation(1, 0, 1)


def test_netted_mode_never_crafts():
    d = data({2: Total(15, 7, 0), 1: Total(0, 0, 9)}, {10: {2: (9, 4)}}, netted=True)
    assert allocate(d, [10])[10][2] == Allocation(9, 8, 0)


def test_allocate_zero_held_and_disjoint_materials():
    gaps = {10: {2: (5, 5)}, 20: {3: (2, 0)}}
    d = data({2: Total(5, 5, 0), 3: Total(2, 0, 0)}, gaps)
    a = allocate(d, [10, 20])
    assert a[10] == {2: Allocation(5, 0, 0)} and a[20] == {3: Allocation(2, 2, 0)}


def test_traveler_elements_are_separate_entries():
    gaps = {1000000507: {2: (6, 6)}, 1000000502: {2: (6, 6)}, 10: {2: (6, 6)}}
    d = data({2: Total(18, 10, 0)}, gaps)                  # 8 held
    a = allocate(d, [1000000502, 10, 1000000507])
    assert [a[c][2].have for c in (1000000502, 10, 1000000507)] == [6, 2, 0]


def test_build_sections_ready_completed_and_not_calculated():
    gaps = {10: {2: (9, 4)}, 20: {2: (6, 4)}}
    d = data({2: Total(15, 7, 0), 1: Total(0, 0, 9)}, gaps,
             calculated=frozenset({10, 20, 1000000507}))
    out = build_sections(d, [20, 10, 1000000507, 1000000502], material_index(d), {10: 0.5})
    builds = {b["character"]["id"]: b for b in out["builds"]}
    assert [b["character"]["id"] for b in out["builds"]] == [20, 10, 1000000502]
    assert [b["priority"] for b in out["builds"]] == [1, 2, 3]
    assert builds[20]["ready"] is True and builds[10]["ready"] is False  # Bennett: 2 held + 3 craft < 9
    m = builds[10]["materials"][0]
    assert (m["need"], m["have"], m["craft"], m["category_label"]) == (9, 2, 3, "Talent books")
    assert builds[10]["progress"] == 0.5 and builds[20]["progress"] is None
    nc = builds[1000000502]
    assert (nc["calculated"], nc["ready"], nc["materials"]) == (False, False, [])
    assert [c["id"] for c in out["completed"]] == [1000000507]          # calculated, no gap rows
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `PY -m pytest tests/test_planner_priority.py -q`
Expected: FAIL with `ModuleNotFoundError: app.planner.priority`.

- [ ] **Step 3: Implement `priority.py`**

```python
# backend/app/planner/priority.py
"""Allocate held materials to Build characters in priority order (spec sub-project 3, section 5)."""
from __future__ import annotations

from dataclasses import dataclass

from app.gamedata.materials import CATEGORY_LABELS
from app.planner.crafting import chains
from app.planner.data import CATEGORY_ORDER, PlannerData


@dataclass(frozen=True)
class Allocation:
    need: int
    have: int
    craft: int


def held_counts(data: PlannerData) -> dict[int, int]:
    """need - short + spare: exact while short overall, a lower bound otherwise (then everyone is covered)."""
    return {mid: max(0, t.need - t.short + t.spare) for mid, t in data.totals.items()}


def _lower_tiers(data: PlannerData) -> dict[int, list[int]]:
    """Material id -> the tiers below it in its crafting chain, lowest first."""
    out: dict[int, list[int]] = {}
    for chain in chains(data.materials):
        for i, mid in enumerate(chain):
            out[mid] = chain[:i]
    return out


def _craft(remaining: dict[int, int], lower: list[int], n: int) -> int:
    """Make up to n of the tier above `lower[-1]` from `remaining`, 3 -> 1, recursing down the chain."""
    if not lower or n <= 0:
        return 0
    below = lower[-1]
    want = 3 * n
    direct = min(want, remaining.get(below, 0))
    remaining[below] = remaining.get(below, 0) - direct
    total = direct + _craft(remaining, lower[:-1], want - direct)
    made = total // 3
    remaining[below] += total - made * 3          # unused units (held or just crafted) stay in the bag
    return made


def allocate(data: PlannerData, order: list[int]) -> dict[int, dict[int, Allocation]]:
    remaining = held_counts(data)
    rows: dict[int, dict[int, list[int]]] = {}
    for cid in order:                               # exact pass
        row: dict[int, list[int]] = {}
        for mid, (need, _short) in data.gaps.get(cid, {}).items():
            if need <= 0:
                continue
            got = min(need, remaining.get(mid, 0))
            remaining[mid] = remaining.get(mid, 0) - got
            row[mid] = [need, got, 0]
        rows[cid] = row
    if not data.lack_includes_crafting:             # craft pass
        lower = _lower_tiers(data)
        for cid in order:
            for mid in sorted(rows[cid], key=lambda m: (data.materials[m].rarity if m in data.materials else 0, m)):
                need, have, _ = rows[cid][mid]
                if have < need and lower.get(mid):
                    rows[cid][mid][2] = _craft(remaining, lower[mid], need - have)
    return {cid: {mid: Allocation(*v) for mid, v in row.items()} for cid, row in rows.items()}


def _material_rows(alloc: dict[int, Allocation], index: dict[int, dict]) -> list[dict]:
    out = []
    for mid, a in alloc.items():
        m = index.get(mid)
        if m is None:
            continue
        out.append({"id": mid, "name": m["name"], "icon": m["icon"], "rarity": m["rarity"],
                    "category": m["category"], "category_label": CATEGORY_LABELS[m["category"]],
                    "need": a.need, "have": a.have, "craft": a.craft,
                    "_order": (CATEGORY_ORDER.index(m["category"]), m["sort_order"], mid)})
    out.sort(key=lambda r: r["_order"])
    for r in out:
        del r["_order"]
    return out


def build_sections(data: PlannerData, order: list[int], index: dict[int, dict],
                   progress: dict[int, float | None]) -> dict:
    order = [cid for cid in order if cid in data.characters]
    alloc = allocate(data, order)
    builds, completed = [], []
    for cid in order:
        ref = data.characters[cid]
        calculated = cid in data.calculated
        if calculated and not data.gaps.get(cid):
            completed.append(ref.to_dict())
            continue
        materials = _material_rows(alloc[cid], index) if calculated else []
        builds.append({"character": ref.to_dict(), "priority": len(builds) + 1, "progress": progress.get(cid),
                       "calculated": calculated,
                       "ready": calculated and all(m["have"] + m["craft"] >= m["need"] for m in materials),
                       "materials": materials})
    return {"builds": builds, "completed": completed}
```

`CATEGORY_LABELS` has keys for every key in `CATEGORY_ORDER`, including `"other"`; `character_shortfall` relies on the same thing.

- [ ] **Step 4: Run the tests**

Run: `PY -m pytest tests/test_planner_priority.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/planner/priority.py backend/tests/test_planner_priority.py
git commit -m "feat(dashboard): allocate held materials to Build characters by priority"
```

---

### Task 4: New HoYoLAB notes fields and finished events

**Files:**
- Modify: `backend/app/sync/hoyolab.py` (`NotesInfo` around line 93, `to_notes` around line 196; add helpers next to `_opt_int` around line 163)
- Modify: `backend/app/sync/persist.py` (`save_notes` around line 87)
- Modify: `backend/app/sync/chronicle.py` (`EventInfo` around line 49, `to_calendar` around line 145)
- Modify: `backend/app/events/view.py` (`ENDING_SOON` line 16, `event_rows` line 32)
- Modify: `frontend/src/lib/types.ts` (`EventRow`), `frontend/src/routes/events/+page.svelte` (the checkbox at line 127)
- Test: `backend/tests/test_hoyolab.py`, `backend/tests/test_persist.py`, `backend/tests/test_chronicle.py`, `backend/tests/test_events_view.py`

**Interfaces:**
- Produces:
  - New `NotesInfo` fields, all defaulting to `None`: `commission_bonus_claimed: bool | None`, `realm_recovery_seconds: int | None`, `transformer_recovery_seconds: int | None`, `expeditions_max: int | None`.
  - `EventInfo.finished: bool = False`.
  - Event rows gain `"finished": bool`. `"done"` becomes manual tick OR finished.
  - `ENDING_STRIP = timedelta(days=3)` and `ending_within(rows, now, window=ENDING_STRIP) -> list[dict]` in `app.events.view`.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_hoyolab.py`:

```python
def test_notes_new_fields_and_missing_transformer():
    base = dict(current_resin=10, max_resin=200, remaining_resin_recovery_time=timedelta(minutes=1),
                completed_commissions=4, max_commissions=4, current_realm_currency=0,
                max_realm_currency=2400, expeditions=[])
    notes = to_notes(NS(**base))
    assert (notes.commission_bonus_claimed, notes.realm_recovery_seconds,
            notes.transformer_recovery_seconds, notes.expeditions_max) == (None, None, None, None)
    notes = to_notes(NS(**base, claimed_commission_reward=True,
                        remaining_realm_currency_recovery_time=timedelta(hours=5),
                        remaining_transformer_recovery_time=timedelta(days=2, hours=3),
                        max_expeditions=5))
    assert notes.commission_bonus_claimed is True
    assert notes.realm_recovery_seconds == 5 * 3600
    assert notes.transformer_recovery_seconds == 51 * 3600
    assert notes.expeditions_max == 5
```

Append to `backend/tests/test_persist.py`. Check the existing imports at the top of the file first and reuse them; add `LiveNotes`, `NotesInfo`, `save_notes`, `datetime` and `timedelta` only where they are missing.

```python
def test_save_notes_new_fields(session_factory):
    from datetime import datetime, timedelta

    from app.db.models import LiveNotes
    from app.sync.hoyolab import NotesInfo
    from app.sync.persist import save_notes

    now = datetime(2026, 11, 22, 12, 0, 0)
    with session_factory.begin() as s:
        save_notes(s, NotesInfo(1, 200, 60, 4, 4, 10, 2400, [], None, None, True, 7200, 0, 5), now)
        row = s.get(LiveNotes, 1)
        assert row.commission_bonus_claimed is True and row.expeditions_max == 5
        assert row.realm_currency_full_at == now + timedelta(hours=2)
        assert row.transformer_ready_at == now
        save_notes(s, NotesInfo(1, 200, 60, 4, 4, 10, 2400, []), now)
        assert row.transformer_ready_at is None and row.realm_currency_full_at is None
```

Append to `backend/tests/test_chronicle.py`:

```python
def test_calendar_event_finished_flag():
    cal = NS(character_banners=[], weapon_banners=[], chronicled_banners=[],
             events=[event(id=1), event(id=2, is_finished=True)], challenges=[])
    info = to_calendar(cal)
    assert [e.finished for e in info.events] == [False, True]
    assert to_json(info)["events"][1]["finished"] is True
```

Append to `backend/tests/test_events_view.py`. Add `ending_within` to the `from app.events.view import …` line.

```python
def test_event_rows_finished_counts_as_done():
    cal = {"banners": [], "challenges": [], "events": [
        {**ev(1, "2026-11-30T04:00:00Z"), "finished": True},
        ev(2, "2026-11-30T04:00:00Z"),                         # old snapshot: no "finished" key
        {**ev(3, "2026-11-30T04:00:00Z"), "finished": True},
    ]}
    rows = {r["id"]: r for r in event_rows(cal, {3}, NOW)}
    assert (rows[1]["done"], rows[1]["finished"]) == (True, True)
    assert (rows[2]["done"], rows[2]["finished"]) == (False, False)
    assert (rows[3]["done"], rows[3]["finished"]) == (True, True)       # ticked and finished: done once


def test_ending_within_three_days_skips_done_and_far():
    rows = event_rows(CAL, {2}, NOW)          # 2 ends in 16h but is done; 1 ends in 8d16h; 3 in 13d
    assert ending_within(rows, NOW) == []
    rows = event_rows(CAL, set(), NOW)
    assert [r["id"] for r in ending_within(rows, NOW)] == [2]
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `PY -m pytest tests/test_hoyolab.py tests/test_persist.py tests/test_chronicle.py tests/test_events_view.py -q`
Expected: FAIL. The cause is an `AttributeError` or `TypeError` on the new fields, or an `ImportError` for `ending_within`.

- [ ] **Step 3: Implement the notes changes**

In `backend/app/sync/hoyolab.py`, add four fields to `NotesInfo` after `weekly_discounts_max`:

```python
    commission_bonus_claimed: bool | None = None
    realm_recovery_seconds: int | None = None
    transformer_recovery_seconds: int | None = None   # None = no Parametric Transformer on the account
    expeditions_max: int | None = None
```

Next to `_opt_int`, add:

```python
def _opt_bool(v: Any) -> bool | None:
    return None if v is None else bool(v)


def _opt_seconds(v: Any) -> int | None:
    return None if v is None else max(0, int(v.total_seconds()))
```

In `to_notes`, add these arguments after `weekly_discounts_max=…`:

```python
        commission_bonus_claimed=_opt_bool(getattr(n, "claimed_commission_reward", None)),
        realm_recovery_seconds=_opt_seconds(getattr(n, "remaining_realm_currency_recovery_time", None)),
        transformer_recovery_seconds=_opt_seconds(getattr(n, "remaining_transformer_recovery_time", None)),
        expeditions_max=_opt_int(getattr(n, "max_expeditions", None)),
```

genshin.py's `TransformerTimedelta` overrides `.seconds`, but `total_seconds()` is the C implementation and is still correct, which is why the code uses it.

In `backend/app/sync/persist.py`, inside `save_notes`, add these lines before `row.fetched_at = now`:

```python
    row.commission_bonus_claimed = notes.commission_bonus_claimed
    row.realm_currency_full_at = (None if notes.realm_recovery_seconds is None
                                  else now + timedelta(seconds=notes.realm_recovery_seconds))
    row.transformer_ready_at = (None if notes.transformer_recovery_seconds is None
                                else now + timedelta(seconds=notes.transformer_recovery_seconds))
    row.expeditions_max = notes.expeditions_max
```

- [ ] **Step 4: Implement the calendar and events changes**

In `backend/app/sync/chronicle.py`, add a field to `EventInfo` after `rewards`:

```python
    finished: bool = False          # HoYoLAB says the player completed it
```

In `to_calendar`, change the `EventInfo(...)` call to pass the flag as the last argument:

```python
    events = [EventInfo(int(e.id), e.name, _plain(e.description), _ts(e.start_timestamp), _ts(e.end_timestamp),
                        [Reward(int(r.id), r.name, r.icon, int(r.num), int(r.rarity)) for r in e.rewards],
                        bool(getattr(e, "is_finished", False)))
              for e in cal.events]
```

In `backend/app/events/view.py`, add `ENDING_STRIP = timedelta(days=3)` under `ENDING_SOON`, then replace `event_rows` and add `ending_within`:

```python
def event_rows(calendar: dict, done: set[int], now: datetime) -> list[dict]:
    rows = []
    for e in calendar.get("events", []):
        end = parse_iso(e.get("end"))
        if end is not None and end <= now:
            continue
        finished = bool(e.get("finished", False))
        rows.append({**e, "primogems": primogems(e["rewards"]), "finished": finished,
                     "done": finished or e["id"] in done,
                     "ending_soon": end is not None and end - now <= ENDING_SOON})
    far = datetime.max
    rows.sort(key=lambda r: (r["done"], parse_iso(r.get("end")) or far, r["id"]))
    return rows


def ending_within(rows: list[dict], now: datetime, window: timedelta = ENDING_STRIP) -> list[dict]:
    """Not-done events that end within `window` (the Dashboard's ending-soon strip)."""
    out = []
    for r in rows:
        end = parse_iso(r.get("end"))
        if not r["done"] and end is not None and now < end <= now + window:
            out.append(r)
    return out
```

- [ ] **Step 5: Lock the toggle on the Events page**

In `frontend/src/lib/types.ts`, add `finished: boolean;` to `EventRow`, after `done: boolean;`.

In `frontend/src/routes/events/+page.svelte`, replace line 127 with:

```svelte
					<label title={ev.finished ? 'Completed in game' : undefined}><input type="checkbox" checked={ev.done} disabled={ev.finished} onchange={() => toggle(ev)} aria-label="Done: {ev.name}" /></label>
```

- [ ] **Step 6: Run the tests**

Run: `PY -m pytest -q` from `backend/`. Then run `npm run check` from `frontend/`.
Expected: everything passes. `test_api_events` still works, because `"finished"` is an extra key.

- [ ] **Step 7: Commit**

```bash
git add backend/app/sync/hoyolab.py backend/app/sync/persist.py backend/app/sync/chronicle.py backend/app/events/view.py backend/tests frontend/src/lib/types.ts frontend/src/routes/events/+page.svelte
git commit -m "feat(dashboard): store transformer, realm, bonus and expedition max; events finished in game count as done"
```

---

### Task 5: Display name setting

**Files:**
- Modify: `backend/app/settings/store.py` (`DEFAULTS`)
- Modify: `backend/app/api/settings.py` (`SettingsIn`, `settings_payload`, `put_settings`)
- Modify: `frontend/src/lib/types.ts` (`Settings`), `frontend/src/lib/api.ts` (`saveSettings` body)
- Modify: `frontend/src/routes/settings/+page.svelte` (the Appearance section around line 333)
- Test: `backend/tests/test_api_settings.py`, `frontend/e2e/settings.spec.ts`

**Interfaces:**
- Produces: the setting `display_name: str` (default `""`), returned by `GET/PUT /api/settings` as `display_name`. Values are stripped and cut to 40 characters.

- [ ] **Step 1: Write the failing test**

Append to `backend/tests/test_api_settings.py`. `make_client` is already imported there; confirm before adding.

```python
def test_display_name_default_trim_and_cap(paths):
    with make_client(paths) as client:
        assert client.get("/api/settings").json()["display_name"] == ""
        assert client.put("/api/settings", json={"display_name": "  Aether  "}).json()["display_name"] == "Aether"
        long = client.put("/api/settings", json={"display_name": "x" * 60}).json()["display_name"]
        assert long == "x" * 40
        assert client.put("/api/settings", json={"display_name": ""}).json()["display_name"] == ""
        assert client.put("/api/settings", json={"display_name": "y" * 201}).status_code == 422
```

- [ ] **Step 2: Run the test to see it fail**

Run: `PY -m pytest tests/test_api_settings.py::test_display_name_default_trim_and_cap -q`
Expected: FAIL with `KeyError: 'display_name'`.

- [ ] **Step 3: Implement**

`backend/app/settings/store.py`: add `"display_name": "",   # Dashboard greeting (sub-project 3); local only` to `DEFAULTS`.

`backend/app/api/settings.py`:

```python
DISPLAY_NAME_MAX = 40
```

Add `display_name: str | None = Field(default=None, max_length=200)` to `SettingsIn`.

Add `"display_name": str(get_setting(s, "display_name") or ""),` to the dict in `settings_payload`.

In `put_settings`, before `return`:

```python
        if body.display_name is not None:
            set_setting(s, "display_name", body.display_name.strip()[:DISPLAY_NAME_MAX])
```

- [ ] **Step 4: Front end**

`frontend/src/lib/types.ts`: add `display_name: string;` to `Settings`.

`frontend/src/lib/api.ts`: add `display_name?: string` to the `saveSettings` body type.

`frontend/src/routes/settings/+page.svelte`: in the script, next to `appearanceNote`, add:

```ts
	let displayNameNote = $state<string | null>(null);

	async function saveDisplayName(input: HTMLInputElement) {
		displayNameNote = null;
		try {
			const saved = await api.saveSettings({ display_name: input.value });
			input.value = saved.display_name;
			displayNameNote = 'Saved';
		} catch (e) {
			displayNameNote = errorMessage(e);
		}
	}
```

Check whether `api` and `errorMessage` are already imported in the file, and add them to the existing imports if not. Then, inside the Appearance section, add this after the background `<p class="muted">…</p>` and before the `appearanceNote` line:

```svelte
					<label class="inline">
						Display name
						<input type="text" maxlength="40" value={settings?.display_name ?? ''}
							onchange={(e) => saveDisplayName(e.currentTarget)} data-testid="display-name" />
					</label>
					<p class="muted">Shown in the Dashboard greeting. Leave blank for “Traveler”. Kept on this computer only.</p>
					{#if displayNameNote}<span class="muted" data-testid="display-name-note">{displayNameNote}</span>{/if}
```

The page's loaded settings may be held in a variable other than `settings`. Read the top of the script and use the actual name.

- [ ] **Step 5: Add an e2e check**

Append to `frontend/e2e/settings.spec.ts`:

```ts
test('display name saves and trims', async ({ page }) => {
	await page.goto('/settings');
	const input = page.getByTestId('display-name');
	await input.fill('  Lumine  ');
	await input.blur();
	await expect(page.getByTestId('display-name-note')).toHaveText('Saved');
	await expect(input).toHaveValue('Lumine');
	await input.fill('');
	await input.blur();
	await expect(input).toHaveValue('');
});
```

- [ ] **Step 6: Run the checks**

Run: `PY -m pytest tests/test_api_settings.py -q`, then `npm run check` from `frontend/`.
Expected: PASS. Playwright runs in Task 9.

- [ ] **Step 7: Commit**

```bash
git add backend/app/settings/store.py backend/app/api/settings.py backend/tests/test_api_settings.py frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/routes/settings/+page.svelte frontend/e2e/settings.spec.ts
git commit -m "feat(dashboard): local Display name setting for the greeting"
```

---

### Task 6: Dashboard API, priority endpoint, dev seed

**Files:**
- Create: `backend/app/dashboard/__init__.py` (empty), `backend/app/dashboard/view.py`
- Modify: `backend/app/planner/today.py`
- Rewrite: `backend/app/api/dashboard.py`
- Modify: `backend/app/devseed.py`
- Test: `backend/tests/test_dashboard_view.py` (new), `backend/tests/test_api_dashboard.py` (new)
- Update tests that read dropped fields:
  - `backend/tests/test_api_planner.py`
  - `backend/tests/test_api_characters.py::test_dashboard`
  - `backend/tests/test_api_events.py`
  - `backend/tests/test_api_profile.py`
  - `backend/tests/test_api_teams.py` (two tests)
  - `backend/tests/test_api_wishes.py` (line about 75)
  - `backend/tests/test_devseed.py`

**Interfaces:**
- Consumes:
  - `build_order`, `set_order` (Task 2)
  - `build_sections` (Task 3)
  - `ending_within`, `"finished"` (Task 4)
  - the `display_name` setting (Task 5)
  - the `LiveNotes` columns (Task 1)
- Produces:
  - **`GET /api/dashboard`** has these keys:
    - `connection`, `display_name`, `notes`
    - `timers`, `ending_soon`, `server_weekday`, `domains_by_day`
    - `weekly_bosses`, `builds`, `completed`
    - `live_banners`, `events`
    - `calendar_fetched_at`, `gaps`
  - **`notes`** adds `commission_bonus_claimed`, `realm_currency_full_at`, `expeditions_max`.
  - **`timers`** is a list of `{kind, label, icon, ready_at}`, sorted by `ready_at`.
  - **`domains_by_day`** is keyed `"0"`…`"6"`. Each value is `{weekday, domains}`.
  - **`live_banners`** are the existing banner rows plus `pity` (a pity line or null).
  - **`events`** mixes the existing event rows plus `kind: "event"` with reset rows `{kind: "reset", id: "reset-<key>", key, name, end, done: false}`. Resets are limited to the abyss, theater and stygian keys.
  - **`PUT /api/priority`** takes `{order: number[]}` and returns `{builds, completed}`, or 400 with `detail`.
  - `farm_today(data, weekday, index, rank=None)` and `weekly_bosses(data, done, index, rank=None)` take a new optional `rank: dict[int, int]` (character id → 0-based position).

- [ ] **Step 1: Write the failing unit tests for the view helpers and ranking**

```python
# backend/tests/test_dashboard_view.py
from datetime import datetime

from app.dashboard.view import RESET_KEYS, banners_with_pity, event_list, timers
from app.db.models import LiveNotes
from app.planner.data import CharRef, Domain, Material, PlannerData, Total
from app.planner.inventory import material_index
from app.planner.today import farm_today, weekly_bosses

NOW = datetime(2026, 11, 22, 12, 0, 0)


def notes(**kw):
    base = dict(id=1, resin=100, resin_max=200, resin_full_at=datetime(2026, 11, 22, 20), commissions_done=1,
                commissions_max=4, realm_currency=0, realm_currency_max=2400, expeditions=[], fetched_at=NOW)
    base.update(kw)
    return LiveNotes(**base)


def test_timers_sorted_and_optional_rows():
    rows = timers(notes(realm_currency_full_at=datetime(2026, 11, 23), transformer_ready_at=datetime(2026, 11, 22, 13),
                        expeditions=[{"icon": "https://x/e.png", "finished": False, "return_at": "2026-11-22T14:00:00Z"}]))
    assert [t["kind"] for t in rows] == ["transformer", "expedition", "resin", "realm"]
    assert rows[0]["icon"] == "UI_ItemIcon_220021" and rows[2]["icon"] == "UI_ItemIcon_210"
    assert [t["kind"] for t in timers(notes())] == ["resin"]


def test_event_list_merges_challenge_resets_only():
    events = [{"id": 1, "end": "2026-11-25T04:00:00Z", "done": False},
              {"id": 2, "end": "2026-11-23T04:00:00Z", "done": True}]
    resets = [{"key": "daily", "label": "Daily reset", "at": "2026-11-23T04:00:00Z"},
              {"key": "abyss", "label": "Spiral Abyss", "at": "2026-11-24T04:00:00Z"}]
    out = event_list(events, resets)
    assert [(r["kind"], r.get("id")) for r in out] == [("reset", "reset-abyss"), ("event", 1), ("event", 2)]
    assert out[0]["name"] == "Spiral Abyss" and out[0]["done"] is False
    assert RESET_KEYS == ("abyss", "theater", "stygian")


def test_banners_with_pity_by_pool():
    lines = [{"pool": "character", "pity5": 62, "hard": 90, "next_state": "guaranteed", "fate_points": None}]
    out = banners_with_pity([{"id": 1, "pool": "character"}, {"id": 2, "pool": "weapon"}], lines)
    assert out[0]["pity"]["pity5"] == 62 and out[1]["pity"] is None


def _data():
    mats = {5: Material(5, "Book", "i", 3, "talent", None, [], 1),
            6: Material(6, "Plume", "i", 5, "weekly", None, [{"kind": "weekly_boss", "name": "Stormterror", "days": []}], 2),
            7: Material(7, "Horn", "i", 5, "weekly", None, [{"kind": "weekly_boss", "name": "Andrius", "days": []}], 3)}
    chars = {10: CharRef(10, "Amber", "amber", None), 20: CharRef(20, "Zhongli", "zhongli", None)}
    return PlannerData(materials=mats, totals={5: Total(4, 4, 0), 6: Total(1, 1, 0), 7: Total(1, 1, 0)},
                       gaps={10: {5: (2, 2), 7: (1, 1)}, 20: {5: (2, 2), 6: (1, 1)}}, characters=chars,
                       domains=[Domain(1, "A domain", "talent", 1, [0, 3], [5]),
                                Domain(2, "B domain", "talent", 1, [0, 3], [5])])


def test_ranked_characters_and_cards():
    d = _data()
    idx = material_index(d)
    day = farm_today(d, 0, idx, {20: 0, 10: 1})
    assert [c["name"] for c in day["domains"][0]["characters"]] == ["Zhongli", "Amber"]
    assert [x["name"] for x in day["domains"]] == ["A domain", "B domain"]          # same best rank -> name
    assert farm_today(d, 1, idx, {})["domains"] == []
    assert len(farm_today(d, 6, idx, {})["domains"]) == 2                            # Sunday: all open
    bosses = weekly_bosses(d, {"Stormterror"}, idx, {10: 0, 20: 1})
    assert [b["name"] for b in bosses] == ["Andrius", "Stormterror"]                 # done sinks
    bosses = weekly_bosses(d, set(), idx, {20: 0, 10: 1})
    assert [b["name"] for b in bosses] == ["Stormterror", "Andrius"]                 # Zhongli first
```

- [ ] **Step 2: Run it to see it fail**

Run: `PY -m pytest tests/test_dashboard_view.py -q`
Expected: FAIL with `ModuleNotFoundError: app.dashboard`.

- [ ] **Step 3: Implement `app/dashboard/view.py` and rank `today.py`**

```python
# backend/app/dashboard/view.py
"""Dashboard-only shaping: timers, the side-column event list, pity on live banners, build progress."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.characters import goal_targets
from app.db.models import CharacterGoal, LiveNotes, OwnedCharacter
from app.domain import Current, progress
from app.timeutil import iso

ICONS = {"resin": "UI_ItemIcon_210", "realm": "UI_ItemIcon_204", "transformer": "UI_ItemIcon_220021"}
RESET_KEYS = ("abyss", "theater", "stygian")


def timers(n: LiveNotes) -> list[dict]:
    out = [{"kind": "resin", "label": "Original Resin full", "icon": ICONS["resin"], "ready_at": iso(n.resin_full_at)}]
    if n.realm_currency_full_at is not None:
        out.append({"kind": "realm", "label": "Realm Currency full", "icon": ICONS["realm"],
                    "ready_at": iso(n.realm_currency_full_at)})
    if n.transformer_ready_at is not None:
        out.append({"kind": "transformer", "label": "Parametric Transformer", "icon": ICONS["transformer"],
                    "ready_at": iso(n.transformer_ready_at)})
    for e in n.expeditions or []:
        out.append({"kind": "expedition", "label": "Expedition", "icon": e["icon"], "ready_at": e["return_at"]})
    return sorted(out, key=lambda t: t["ready_at"])


def event_list(events: list[dict], resets: list[dict]) -> list[dict]:
    rows = [{**e, "kind": "event"} for e in events]
    rows += [{"kind": "reset", "id": f"reset-{r['key']}", "key": r["key"], "name": r["label"], "end": r["at"],
              "done": False} for r in resets if r["key"] in RESET_KEYS]
    return sorted(rows, key=lambda r: (r["done"], r.get("end") or "9999"))


def banners_with_pity(banners: list[dict], lines: list[dict]) -> list[dict]:
    by_pool = {line["pool"]: line for line in lines}
    return [{**b, "pity": by_pool.get(b["pool"])} for b in banners]


def build_progress(s: Session) -> dict[int, float | None]:
    owned = {o.character_id: o for o in s.scalars(select(OwnedCharacter))}
    out: dict[int, float | None] = {}
    for row in s.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")):
        o, t = owned.get(row.character_id), goal_targets(row)
        out[row.character_id] = (progress(Current(o.level, o.talent_normal, o.talent_skill, o.talent_burst), t)
                                 if o is not None and t is not None else None)
    return out
```

All ISO strings here come from `app.timeutil.iso`, which writes `YYYY-MM-DDTHH:MM:SSZ`, so sorting them as strings is the same as sorting by time. Before relying on that, check that `iso()` really ends in `Z`: `test_api_characters` asserts `resin_full_at.endswith("Z")`.

If importing `app.api.characters` from `app.dashboard.view` causes a circular import, move the import of `goal_targets` inside `build_progress`.

Replace `backend/app/planner/today.py` with:

```python
"""Dashboard: domains open on a weekday and weekly bosses, limited to what is still to farm.
Characters on each card follow Build priority; cards follow their best (lowest) priority, then name."""
from __future__ import annotations

from app.planner.data import PlannerData

SUNDAY = 6


def _characters(materials: list[dict], rank: dict[int, int]) -> list[dict]:
    seen: dict[int, dict] = {}
    for m in materials:
        for c in m["characters"]:
            seen.setdefault(c["id"], {k: c[k] for k in ("id", "name", "slug", "icon")})
    return sorted(seen.values(), key=lambda c: (rank.get(c["id"], len(rank)), c["name"]))


def _best(characters: list[dict], rank: dict[int, int]) -> int:
    return min((rank.get(c["id"], len(rank)) for c in characters), default=len(rank))


def farm_today(data: PlannerData, weekday: int, index: dict[int, dict], rank: dict[int, int] | None = None) -> dict:
    rank = rank or {}
    domains = []
    for d in data.domains:
        if weekday != SUNDAY and weekday not in d.weekdays:
            continue
        mats = [index[mid] for mid in d.material_ids if mid in index and index[mid]["to_farm"] > 0]
        if mats:
            domains.append({"id": d.id, "name": d.name, "kind": d.kind, "weekdays": d.weekdays,
                            "materials": mats, "characters": _characters(mats, rank)})
    domains.sort(key=lambda d: (_best(d["characters"], rank), d["name"]))
    return {"weekday": weekday, "domains": domains}


def weekly_bosses(data: PlannerData, done: set[str], index: dict[int, dict],
                  rank: dict[int, int] | None = None) -> list[dict]:
    rank = rank or {}
    by_boss: dict[str, list[dict]] = {}
    for row in sorted(index.values(), key=lambda r: (r["sort_order"], r["id"])):
        if row["category"] != "weekly" or row["to_farm"] <= 0:
            continue
        boss = next((s["name"] for s in row["sources"] if s["kind"] == "weekly_boss"), "Unknown boss")
        by_boss.setdefault(boss, []).append(row)
    bosses = [{"name": name, "done": name in done, "materials": mats, "characters": _characters(mats, rank)}
              for name, mats in by_boss.items()]
    return sorted(bosses, key=lambda b: (b["done"], _best(b["characters"], rank), b["name"]))
```

- [ ] **Step 4: Run the unit tests**

Run: `PY -m pytest tests/test_dashboard_view.py -q`
Expected: PASS.

- [ ] **Step 5: Write the failing API tests**

```python
# backend/tests/test_api_dashboard.py
from app.db.models import CharacterGoal, HoyolabSnapshot, MaterialGap, MaterialTotal
from app.timeutil import utcnow
from helpers import make_client
from test_api_planner import mark_calculated, setup, sf_for

KEYS = {"connection", "display_name", "notes", "timers", "ending_soon", "server_weekday", "domains_by_day",
        "weekly_bosses", "builds", "completed", "live_banners", "events", "calendar_fetched_at", "gaps"}


def test_dashboard_empty_account(paths):
    sf_for(paths)
    with make_client(paths) as client:
        body = client.get("/api/dashboard").json()
    assert set(body) == KEYS
    assert body["notes"] is None and body["timers"] == [] and body["builds"] == [] and body["completed"] == []
    assert body["ending_soon"] == [] and body["live_banners"] == [] and body["display_name"] == ""
    assert sorted(body["domains_by_day"]) == [str(d) for d in range(7)]
    assert all(e["kind"] == "reset" for e in body["events"])


def test_dashboard_shape_and_allocation(paths):
    sf = setup(paths)
    with sf.begin() as s:
        s.get(CharacterGoal, 10000032).priority = 1
    mark_calculated(sf)               # only calculated characters list materials
    with make_client(paths) as client:
        body = client.get("/api/dashboard").json()
    assert set(body) == KEYS
    assert body["notes"]["expeditions_max"] is None and "commission_bonus_claimed" in body["notes"]
    assert body["domains_by_day"]["0"]["domains"][0]["name"] == "Domain of Mastery: Forsaken Rift"
    card = body["builds"][0]
    assert card["character"]["name"] == "Bennett" and card["priority"] == 1
    guide = next(m for m in card["materials"] if m["id"] == 104302)
    assert (guide["need"], guide["have"], guide["craft"]) == (9, 5, 0)
    assert body["timers"][0]["kind"] in {"resin", "expedition"}


def test_put_priority_reorders_and_recomputes(paths):
    sf = setup(paths)
    with sf.begin() as s:
        s.add(CharacterGoal(character_id=10000089, goal="build", target_level=90, target_normal=8, target_skill=8,
                            target_burst=8, target_weapon_level=90, priority=2, updated_at=utcnow()))
        s.get(CharacterGoal, 10000032).priority = 1
        s.add(MaterialGap(character_id=10000089, material_id=104302, need=6, short=6))
        total = s.get(MaterialTotal, 104302)
        total.need, total.short = 15, 10                     # 5 held
    mark_calculated(sf)
    with make_client(paths) as client:
        before = client.get("/api/dashboard").json()["builds"]
        assert [b["character"]["id"] for b in before] == [10000032, 10000089]
        res = client.put("/api/priority", json={"order": [10000089, 10000032]})
        assert res.status_code == 200
        builds = {b["character"]["id"]: b for b in res.json()["builds"]}
        assert next(m for m in builds[10000089]["materials"] if m["id"] == 104302)["have"] == 5
        assert next(m for m in builds[10000032]["materials"] if m["id"] == 104302)["have"] == 0
        assert [b["priority"] for b in res.json()["builds"]] == [1, 2]
        assert set(res.json()) == {"builds", "completed"}


def test_put_priority_appends_unlisted_and_rejects_stale(paths):
    sf = setup(paths)
    with sf.begin() as s:
        s.add(CharacterGoal(character_id=10000089, goal="build", target_level=90, target_normal=8, target_skill=8,
                            target_burst=8, target_weapon_level=90, updated_at=utcnow()))
    with make_client(paths) as client:
        assert client.put("/api/priority", json={"order": [10000089]}).status_code == 200
        res = client.put("/api/priority", json={"order": [10000047]})
        assert res.status_code == 400 and "Not set to Build" in res.json()["detail"]
        assert client.put("/api/priority", json={"order": [10000089, 10000089]}).status_code == 400
    with sf() as s:
        assert (s.get(CharacterGoal, 10000089).priority, s.get(CharacterGoal, 10000032).priority) == (1, 2)


def test_dashboard_events_ending_soon_and_finished(paths):
    sf = sf_for(paths)
    now = utcnow()
    from datetime import timedelta
    from app.timeutil import iso
    cal = {"banners": [], "challenges": [], "events": [
        {"id": 1, "name": "Soon", "description": "", "start": None, "end": iso(now + timedelta(days=2)),
         "rewards": []},
        {"id": 2, "name": "Finished", "description": "", "start": None, "end": iso(now + timedelta(days=1)),
         "rewards": [], "finished": True},
        {"id": 3, "name": "Later", "description": "", "start": None, "end": iso(now + timedelta(days=9)),
         "rewards": []}]}
    with sf.begin() as s:
        s.add(HoyolabSnapshot(part="calendar", data=cal, fetched_at=now))
    with make_client(paths) as client:
        body = client.get("/api/dashboard").json()
    assert [e["id"] for e in body["ending_soon"]] == [1]
    finished = next(e for e in body["events"] if e.get("id") == 2)
    assert finished["done"] is True and finished["finished"] is True
```

- [ ] **Step 6: Run them to see them fail**

Run: `PY -m pytest tests/test_api_dashboard.py -q`
Expected: FAIL. The dashboard still returns the old keys and `/api/priority` returns 404 or 405.

- [ ] **Step 7: Rewrite `backend/app/api/dashboard.py`**

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select

from app.api.events import events_payload
from app.api.planner import gaps_for, planner_view, region
from app.api.wishes import pity_lines
from app.context import AppContext, get_ctx
from app.dashboard.view import banners_with_pity, build_progress, event_list, timers
from app.db.models import LiveNotes, WeeklyBossDone
from app.events.view import ending_within
from app.planner.order import build_order, set_order
from app.planner.priority import build_sections
from app.planner.today import farm_today, weekly_bosses
from app.servertime import offset_hours, server_weekday, week_start
from app.settings.envfile import connection_status, read_env
from app.settings.store import get_setting
from app.timeutil import iso, utcnow
from app.wishes.pity import summarize

router = APIRouter()


def _opt_iso(value):
    return iso(value) if value is not None else None


def notes_payload(n: LiveNotes) -> dict:
    return {
        "resin": n.resin, "resin_max": n.resin_max, "resin_full_at": iso(n.resin_full_at),
        "commissions_done": n.commissions_done, "commissions_max": n.commissions_max,
        "commission_bonus_claimed": n.commission_bonus_claimed,
        "realm_currency": n.realm_currency, "realm_currency_max": n.realm_currency_max,
        "realm_currency_full_at": _opt_iso(n.realm_currency_full_at),
        "expeditions": n.expeditions, "expeditions_max": n.expeditions_max, "fetched_at": iso(n.fetched_at),
    }


def _builds(s) -> tuple[dict, dict[int, int], object, dict]:
    data, index = planner_view(s)
    order = [cid for cid in build_order(s) if cid in data.characters]
    rank = {cid: i for i, cid in enumerate(order)}
    return build_sections(data, order, index, build_progress(s)), rank, data, index


@router.get("/dashboard")
def dashboard(ctx: AppContext = Depends(get_ctx)) -> dict:
    now, reg = utcnow(), region(ctx)
    with ctx.session_factory() as s:
        notes = s.get(LiveNotes, 1)
        results = summarize(s, now, offset_hours(reg))
        ev = events_payload(ctx, s, results)
        sections, rank, data, index = _builds(s)
        done = set(s.scalars(select(WeeklyBossDone.boss).where(WeeklyBossDone.week_start == week_start(now, reg))))
        return {
            "connection": connection_status(read_env(ctx.paths.env_file), get_setting(s, "hoyolab_status")),
            "display_name": str(get_setting(s, "display_name") or ""),
            "notes": notes_payload(notes) if notes is not None else None,
            "timers": timers(notes) if notes is not None else [],
            "ending_soon": ending_within(ev["events"], now),
            "server_weekday": server_weekday(now, reg),
            "domains_by_day": {str(d): farm_today(data, d, index, rank) for d in range(7)},
            "weekly_bosses": {
                "discounts_left": notes.weekly_discounts_left if notes is not None else None,
                "discounts_max": notes.weekly_discounts_max if notes is not None else None,
                "bosses": weekly_bosses(data, done, index, rank),
            },
            **sections,
            "live_banners": banners_with_pity(ev["banners"]["current"], pity_lines(results)),
            "events": event_list(ev["events"], ev["resets"]),
            "calendar_fetched_at": ev["fetched_at"],
            "gaps": gaps_for(ctx, s),
        }


class PriorityIn(BaseModel):
    order: list[int]


@router.put("/priority")
def put_priority(body: PriorityIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory.begin() as s:
        try:
            set_order(s, body.order)
        except ValueError as e:
            raise HTTPException(400, str(e)) from None
        sections, _rank, _data, _index = _builds(s)
        return sections
```

Check how `backend/app/main.py` mounts the dashboard router (for example with prefix `/api`). `/priority` sits on the same router, so it is served as `/api/priority` with no change there.

`goal_targets` used to be imported here and is now imported by `app.dashboard.view`. Check that nothing else imported it from `app.api.dashboard`; `grep -rn "from app.api.dashboard" backend` should show only `main.py`.

- [ ] **Step 8: Update the dev seed**

In `backend/app/devseed.py`:

1. **Notes.** Replace the `save_notes(...)` line with:

```python
        save_notes(s, NotesInfo(120, 200, 80 * 8 * 60, 3, 4, 900, 2400,
                                [ExpeditionInfo("https://act-webstatic.hoyoverse.com/demo-exp.png", False, 2 * 3600),
                                 ExpeditionInfo("https://act-webstatic.hoyoverse.com/demo-exp.png", True, 0)],
                                2, 3, False, 9 * 3600, 0, 5), now)
```

   Add `ExpeditionInfo` to the existing `from app.sync.hoyolab import …` line.

2. **Goals.** In the goals loop, give Build rows a priority in dict order (Bennett 1, Furina 2, Neuvillette 3):

```python
        build_rank = {cid: n for n, cid in enumerate((c for c, g in GOALS.items() if g == "build"), start=1)}
        for cid, goal in GOALS.items():
            build = goal == "build"
            s.add(CharacterGoal(character_id=cid, goal=goal, target_level=90 if build else None,
                                target_normal=8 if build else None, target_skill=8 if build else None,
                                target_burst=8 if build else None,
                                target_weapon_level=90 if build else None, priority=build_rank.get(cid),
                                updated_at=now))
```

3. **Calendar events.** Change 9003 "Photo Event" to end at `now + timedelta(days=2)`, so it falls in the ending-soon strip. Add a finished event after 9003:

```python
                {"id": 9004, "name": "Daily Check-in Event", "description": "", "start": None,
                 "end": iso(now + timedelta(days=5)), "rewards": [], "finished": True},
```

   9004 has no primogems and counts as done, so the Events page totals ("3 events left · 480 primos" before any tick) stay the same.

4. **Challenges.** Add a stygian period so all three reset rows show:

```python
                           {"kind": "stygian", "name": "Stygian Onslaught", "start": None,
                            "end": iso(now + timedelta(days=12))},
```

With this seed, Guide to Freedom (104302) gives 15 − 7 + 0 = 8 held, and Teachings (104301) has 9 spare. Bennett (P1) needs 9: he gets 8 plus 1 craft. Furina (P2) needs 6: she gets 0 plus 2 craft. With Furina first, she gets 6 and Bennett gets 2 plus 3 craft. Task 9's e2e test relies on these numbers.

- [ ] **Step 9: Update tests that read dropped fields**

- **`backend/tests/test_api_planner.py`:**
  - Add this helper below `sf_for`. `test_api_dashboard.py` imports it. It is the same as the one in `test_api_teams.py`, which may keep its own copy.

```python
def mark_calculated(sf):
    """A successful gap run whose snapshot matches the current goals: Build characters count as calculated."""
    from app.planner.requests import snapshot
    with sf.begin() as s:
        s.merge(GapRun(id=1, ok=True, error=None, skipped=[], computed_at=datetime(2026, 11, 21),
                       snapshot=snapshot(s)))
```

  - In `test_dashboard_planner_sections`, call `mark_calculated(sf)` after `sf = setup(paths)` (change `setup(paths)` to `sf = setup(paths)`). The Dashboard lists materials only for calculated characters. Then replace `body["farm_today"]` with `body["domains_by_day"]["0"]`. Replace the `building_cards` lines with:

```python
    card = body["builds"][0]
    assert card["character"]["name"] == "Bennett" and {m["id"] for m in card["materials"]} == {104302, 113003}
```

  - In `test_calculated_flag_on_cards_and_detail`, replace both `["building_cards"][0]["calculated"]` with `["builds"][0]["calculated"]`.

- **`backend/tests/test_api_characters.py::test_dashboard`:**
  - Replace `empty["building"] == {"count": 0, "average_progress": None}` with `empty["builds"] == []`.
  - Replace `d["building"]["count"] == 1` with `len(d["builds"]) == 1`.

- **`backend/tests/test_api_events.py::test_events_endpoint_and_done`:** replace the dashboard line with:

```python
        dash = client.get("/api/dashboard").json()
        assert next(e for e in dash["events"] if e.get("id") == 9002)["done"] is True
```

- **`backend/tests/test_api_profile.py`:** the Dashboard no longer shows the profile, so drop the `dash = …` request and its assert. Keep the `/api/profile` asserts.

- **`backend/tests/test_api_teams.py`:** the two tests that read `build_teams` from the dashboard now read the cards directly. Add a helper near the top:

```python
from app.api.teams import team_views
from app.teams.view import build_team_cards


def team_cards(sf):
    with sf() as s:
        return build_team_cards(team_views(s))
```

  Then replace `client.get("/api/dashboard").json()["build_teams"]` with `team_cards(sf)` and keep every assert. Rename the tests to `test_character_detail_and_build_team_cards` and `test_build_team_card_calculation_flags`.

- **`backend/tests/test_api_wishes.py`** (line about 75): delete the line `dash = client.get("/api/dashboard").json()["pity"]` and the assert after it. Pity now appears on the live banners, which `test_dashboard_view.py::test_banners_with_pity_by_pool` and the e2e cover. The test's `/api/wishes/summary` asserts already cover the standard pool's pity.

- **`backend/tests/test_devseed.py`:**
  - Replace the `farm_today` line with:

```python
    assert dash["domains_by_day"][str(dash["server_weekday"])]["domains"][0]["name"] == "Domain of Mastery: Forsaken Rift"
```

  - Replace the `building_cards` block with:

```python
    builds = {b["character"]["slug"]: b for b in dash["builds"]}
    assert [b["character"]["slug"] for b in dash["builds"]] == ["bennett", "furina"]
    assert all(b["calculated"] for b in builds.values())
    guide = next(m for m in builds["bennett"]["materials"] if m["id"] == 104302)
    assert (guide["have"], guide["craft"]) == (8, 1)
    assert [c["slug"] for c in dash["completed"]] == ["neuvillette"]      # Build, no rows, in snapshot
    assert {t["kind"] for t in dash["timers"]} == {"resin", "realm", "transformer", "expedition"}
    assert [e["id"] for e in dash["ending_soon"]] == [9002, 9003]
```

- [ ] **Step 10: Run the whole backend suite**

Run: `PY -m pytest -q`
Expected: PASS. Any remaining failure that names `farm_today`, `building`, `build_teams`, `pity`, `resets`, `events_left` or `profile_summary` is a test still reading a dropped field. Update it the same way.

- [ ] **Step 11: Commit**

```bash
git add backend/app/dashboard backend/app/planner/today.py backend/app/api/dashboard.py backend/app/devseed.py backend/tests
git commit -m "feat(dashboard): reshaped dashboard payload and PUT /api/priority"
```

---

### Task 7: Front-end types, API client, helpers and icons

**Files:**
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/icons.ts`, `frontend/src/lib/icons.test.ts` (if it lists names)
- Create: `frontend/src/lib/dashboard.ts`, `frontend/src/lib/dashboard.test.ts`

**Interfaces:**
- Consumes: the API shapes from Task 6.
- Produces:
  - **Types:** `Timer`, `DayFarm`, `BuildMaterial`, `BuildCard`, `DashBanner`, `DashEvent`, `DashReset`, `DashEventItem`, `PriorityResult`, and the new `Dashboard`.
  - **`api.setPriority(order: number[]): Promise<PriorityResult>`**
  - **Helpers in `$lib/dashboard`:** `greeting(hour, name)`, `DAY_LABELS`, `dayButtons(viewed, today)`, `moveItem(list, from, to)`, `buildTileView(m)`, `covered(m)`, `topReward(rewards)`, `expeditionsReady(exps, now)`, `bannerPity(line)`.
  - **Icons:** `commission`, `expedition`.

- [ ] **Step 1: Write the failing vitest file**

```ts
// frontend/src/lib/dashboard.test.ts
import { describe, expect, it } from 'vitest';
import {
	bannerPity, buildTileView, covered, dayButtons, expeditionsReady, greeting, moveItem, topReward
} from './dashboard';
import type { BuildMaterial } from './types';

const m = (need: number, have: number, craft: number): BuildMaterial => ({
	id: 1, name: 'Guide', icon: 'x', rarity: 3, category: 'talent', category_label: 'Talent books', need, have, craft
});

describe('greeting', () => {
	it('picks the part of the day and falls back to Traveler', () => {
		expect(greeting(4, '')).toBe('Good evening, Traveler');
		expect(greeting(5, 'Lumine')).toBe('Good morning, Lumine');
		expect(greeting(12, '  ')).toBe('Good afternoon, Traveler');
		expect(greeting(18, 'Aether')).toBe('Good evening, Aether');
	});
});

describe('dayButtons', () => {
	it('marks viewed and today separately', () => {
		const b = dayButtons(2, 4);
		expect(b.map((x) => x.label)).toEqual(['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']);
		expect(b.filter((x) => x.viewed).map((x) => x.day)).toEqual([2]);
		expect(b.filter((x) => x.today).map((x) => x.day)).toEqual([4]);
	});
});

describe('moveItem', () => {
	it('moves and ignores out-of-range moves', () => {
		expect(moveItem(['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b']);
		expect(moveItem(['a', 'b', 'c'], 0, 1)).toEqual(['b', 'a', 'c']);
		expect(moveItem(['a', 'b'], 0, -1)).toEqual(['a', 'b']);
		expect(moveItem(['a', 'b'], 1, 2)).toEqual(['a', 'b']);
	});
});

describe('buildTileView', () => {
	it('shows allocation, craft hint and what is still missing', () => {
		expect(buildTileView(m(9, 8, 1))).toEqual({ main: '8/9', badge: null, hint: '+1 craft', tone: 'met' });
		expect(buildTileView(m(9, 2, 3))).toEqual({ main: '2/9', badge: '−4', hint: '+3 craft', tone: 'short' });
		expect(buildTileView(m(20, 0, 0))).toEqual({ main: '0/20', badge: '−20', hint: null, tone: 'short' });
		expect(covered(m(9, 8, 1))).toBe(true);
		expect(covered(m(9, 8, 0))).toBe(false);
	});
});

describe('misc', () => {
	it('topReward prefers rarity, then count', () => {
		const r = (id: number, rarity: number, count: number) => ({ id, name: `R${id}`, icon: '', rarity, count });
		expect(topReward([])).toBeNull();
		expect(topReward([r(1, 4, 100), r(2, 5, 60), r(3, 5, 420)])?.id).toBe(3);
	});
	it('expeditionsReady counts finished or returned', () => {
		const now = Date.parse('2026-11-22T12:00:00Z');
		expect(expeditionsReady([
			{ icon: '', finished: true, return_at: '2026-11-22T15:00:00Z' },
			{ icon: '', finished: false, return_at: '2026-11-22T11:00:00Z' },
			{ icon: '', finished: false, return_at: '2026-11-22T13:00:00Z' }
		], now)).toBe(2);
	});
	it('bannerPity', () => {
		expect(bannerPity(null)).toBeNull();
		expect(bannerPity({ pool: 'character', pity5: 2, hard: 90, next_state: '50/50', fate_points: null }))
			.toBe('Pity 2/90 · 50/50');
		expect(bannerPity({ pool: 'weapon', pity5: 62, hard: 80, next_state: 'guaranteed', fate_points: 1 }))
			.toBe('Pity 62/80 · guaranteed');
	});
});
```

- [ ] **Step 2: Run it to see it fail**

Run: `npx vitest run src/lib/dashboard.test.ts`, from `frontend/`.
Expected: FAIL, because `./dashboard` cannot be resolved.

- [ ] **Step 3: Update the types**

In `frontend/src/lib/types.ts`, extend `Notes`:

```ts
export interface Notes {
	resin: number; resin_max: number; resin_full_at: string;
	commissions_done: number; commissions_max: number; commission_bonus_claimed: boolean | null;
	realm_currency: number; realm_currency_max: number; realm_currency_full_at: string | null;
	expeditions: Expedition[]; expeditions_max: number | null; fetched_at: string;
}
```

Replace `interface Dashboard` with:

```ts
export interface Timer { kind: 'resin' | 'realm' | 'transformer' | 'expedition'; label: string; icon: string; ready_at: string }
export interface DayFarm { weekday: number; domains: FarmDomain[] }
export interface BuildMaterial {
	id: number; name: string; icon: string; rarity: number; category: string; category_label: string;
	need: number; have: number; craft: number;
}
export interface BuildCard {
	character: CharRef; priority: number; progress: number | null; calculated: boolean; ready: boolean;
	materials: BuildMaterial[];
}
export interface PriorityResult { builds: BuildCard[]; completed: CharRef[] }
export interface DashEvent extends EventRow { kind: 'event' }
export interface DashReset { kind: 'reset'; id: string; key: string; name: string; end: string; done: false }
export type DashEventItem = DashEvent | DashReset;
export interface Dashboard {
	connection: Connection;
	display_name: string;
	notes: Notes | null;
	timers: Timer[];
	ending_soon: EventRow[];
	server_weekday: number;
	domains_by_day: Record<string, DayFarm>;
	weekly_bosses: { discounts_left: number | null; discounts_max: number | null; bosses: WeeklyBoss[] };
	builds: BuildCard[];
	completed: CharRef[];
	live_banners: DashBanner[];
	events: DashEventItem[];
	calendar_fetched_at: string | null;
	gaps: GapStatus;
}
```

`LiveBanner` and `PityLine` are declared further down the file. Add this after `interface LiveBanner`:

```ts
export interface DashBanner extends LiveBanner { pity: PityLine | null }
```

`BuildingCard` and `BuildTeamCard` may now be unused. Leave them; deleting them is out of scope.

- [ ] **Step 4: Update the API client**

In `frontend/src/lib/api.ts`, add `PriorityResult` to the type import and add this next to `dashboard`:

```ts
	setPriority: (order: number[]) => request<PriorityResult>('PUT', '/priority', { order }),
```

- [ ] **Step 5: Add the helpers**

```ts
// frontend/src/lib/dashboard.ts
import type { TileView } from './materials';
import type { BuildMaterial, Expedition, PityLine, Reward } from './types';

export function greeting(hour: number, name: string): string {
	const part = hour >= 5 && hour < 12 ? 'Good morning' : hour >= 12 && hour < 18 ? 'Good afternoon' : 'Good evening';
	return `${part}, ${name.trim() || 'Traveler'}`;
}

export const DAY_LABELS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'] as const;
export interface DayButton { day: number; label: string; viewed: boolean; today: boolean }

export function dayButtons(viewed: number, today: number): DayButton[] {
	return DAY_LABELS.map((label, day) => ({ day, label, viewed: day === viewed, today: day === today }));
}

export function moveItem<T>(list: T[], from: number, to: number): T[] {
	const out = list.slice();
	if (from === to || from < 0 || to < 0 || from >= list.length || to >= list.length) return out;
	const [item] = out.splice(from, 1);
	out.splice(to, 0, item);
	return out;
}

export function covered(m: BuildMaterial): boolean {
	return m.have + m.craft >= m.need;
}

export function buildTileView(m: BuildMaterial): TileView {
	const left = Math.max(0, m.need - m.have - m.craft);
	return {
		main: `${m.have}/${m.need}`,
		badge: left > 0 ? `−${left}` : null,
		hint: m.craft > 0 ? `+${m.craft} craft` : null,
		tone: left === 0 ? 'met' : 'short'
	};
}

export function topReward(rewards: Reward[]): Reward | null {
	return rewards.reduce<Reward | null>(
		(best, r) => (!best || r.rarity > best.rarity || (r.rarity === best.rarity && r.count > best.count) ? r : best),
		null
	);
}

export function expeditionsReady(exps: Expedition[], now: number): number {
	return exps.filter((e) => e.finished || Date.parse(e.return_at) <= now).length;
}

export function bannerPity(line: PityLine | null): string | null {
	if (!line) return null;
	const state = line.next_state === 'guaranteed' ? ' · guaranteed'
		: line.next_state === '50/50' || line.next_state === '75/25' ? ` · ${line.next_state}` : '';
	return `Pity ${line.pity5}/${line.hard}${state}`;
}
```

- [ ] **Step 6: Add the two original icons**

In `frontend/src/lib/icons.ts`, add `'commission'` and `'expedition'` to the end of `ICON_NAMES`, and add these entries to `ICONS`:

```ts
	commission: [{ d: 'M5 2h11l4 4v16H5zm10 1.5V7h3.5zM8 10v2h9v-2zm0 4v2h9v-2zm0 4v2h6v-2z', evenodd: true }],
	expedition: [{ d: 'M12 2a7 7 0 0 1 7 7c0 5-7 13-7 13S5 14 5 9a7 7 0 0 1 7-7zm0 4a3 3 0 1 0 0 6 3 3 0 0 0 0-6z', evenodd: true }],
```

If `icons.test.ts` asserts an exact list of names, update that list to include the two new names.

- [ ] **Step 7: Run the checks**

Run from `frontend/`: `npx vitest run`, then `npm run check`.

Expected:
- vitest passes.
- `npm run check` may now **fail** in `src/routes/+page.svelte`, which still reads the old fields. That is expected; Task 8 rewrites the page.
- No other file may report errors. Check that with `npm run check 2>&1 | grep -v "routes/+page.svelte"`.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/lib/icons.ts frontend/src/lib/icons.test.ts frontend/src/lib/dashboard.ts frontend/src/lib/dashboard.test.ts
git commit -m "feat(dashboard): front-end types, priority API and dashboard helpers"
```

---

### Task 8: Dashboard components and page

**Files:**
- Create in `frontend/src/lib/dashboard/`:
  - `Greeting.svelte`
  - `NoteBubbles.svelte`
  - `EndingSoon.svelte`
  - `DomainDays.svelte`
  - `WeeklyBosses.svelte`
  - `BuildList.svelte`
  - `BuildCard.svelte`
  - `CompletedBuilds.svelte`
  - `TimerList.svelte`
  - `LiveBanners.svelte`
  - `EventList.svelte`
- Rewrite: `frontend/src/routes/+page.svelte`

**Interfaces:**
- Consumes: everything from Task 7, plus these existing pieces:
  - `MaterialTile`, `MaterialPopover`, `Countdown`, `Icon`
  - `imgSrc`
  - `tileView`, `gapLabel`, `gapsSettled`, `notCalculatedLabel`, `shouldPoll` from `$lib/materials`
  - `timeLeft`, `countdownWarn` from `$lib/events`
  - `formatDuration`, `timeAgo` from `$lib/time`
  - `api`, `errorMessage`, `sync`
- Produces these test ids (Task 9 relies on them):
  - `greeting`
  - `bubbles`, `bubble-resin`, `bubble-commissions`, `bubble-realm`, `bubble-expeditions`
  - `ending-soon`
  - `domains`, `day-<0..6>`
  - `weekly-bosses`, `boss-<name>`
  - `builds`, `build-card-<slug>`, `build-<slug>-<materialId>`
  - `completed`
  - `timers`
  - `dash-banners`
  - `dash-events`, `dash-event-<id>`

Every component uses the global `.panel` glass class from Foundation, and every timestamp shown is driven by the page's `now`.

- [ ] **Step 1: `Greeting.svelte`**

```svelte
<script lang="ts">
	import { greeting } from '$lib/dashboard';
	let { name, now }: { name: string; now: number } = $props();
	const text = $derived(greeting(new Date(now).getHours(), name));
</script>

<h1 class="greeting" data-testid="greeting">{text}</h1>

<style>
	.greeting { margin: 0 0 12px; font-size: 26px; }
</style>
```

- [ ] **Step 2: `NoteBubbles.svelte`**

```svelte
<script lang="ts">
	import Icon from '$lib/Icon.svelte';
	import { expeditionsReady } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import { formatDuration } from '$lib/time';
	import type { Connection, Notes } from '$lib/types';

	let { notes, connection, now }: { notes: Notes | null; connection: Connection; now: number } = $props();
	const fullIn = (iso: string | null) => (iso ? Date.parse(iso) - now : null);
	const resinIn = $derived(notes ? fullIn(notes.resin_full_at) : null);
	const realmIn = $derived(notes ? fullIn(notes.realm_currency_full_at) : null);
	const ready = $derived(notes ? expeditionsReady(notes.expeditions, now) : 0);
	const expTotal = $derived(notes ? (notes.expeditions_max ?? notes.expeditions.length) : 0);
	const fullText = (ms: number | null) => (ms === null ? '' : ms <= 0 ? 'Full' : `Full in ${formatDuration(ms)}`);
</script>

{#if connection.status === 'missing'}
	<section class="panel" data-testid="bubbles">Connect HoYoLAB in <a href="/settings">Settings</a> to see your account here.</section>
{:else}
	<div class="bubbles" data-testid="bubbles">
		<section class="panel bubble" data-testid="bubble-resin">
			<img src={imgSrc('UI_ItemIcon_210')} alt="" />
			<div><div class="label">Original Resin</div>
				<div class="big">{notes ? notes.resin : '—'}{#if notes}<span class="muted">/{notes.resin_max}</span>{/if}</div>
				<div class="muted">{fullText(resinIn)}</div></div>
		</section>
		<section class="panel bubble" data-testid="bubble-commissions">
			<span class="icon"><Icon name="commission" size={36} /></span>
			<div><div class="label">Commissions</div>
				<div class="big">{notes ? notes.commissions_done : '—'}{#if notes}<span class="muted">/{notes.commissions_max}</span>{/if}</div>
				{#if notes && notes.commission_bonus_claimed !== null}
					<div class:ok={notes.commission_bonus_claimed} class="muted">{notes.commission_bonus_claimed ? 'Bonus claimed' : 'Bonus not claimed'}</div>
				{/if}</div>
		</section>
		<section class="panel bubble" data-testid="bubble-realm">
			<img src={imgSrc('UI_ItemIcon_204')} alt="" />
			<div><div class="label">Realm Currency</div>
				<div class="big">{notes ? notes.realm_currency : '—'}{#if notes}<span class="muted">/{notes.realm_currency_max}</span>{/if}</div>
				<div class="muted">{fullText(realmIn)}</div></div>
		</section>
		<section class="panel bubble" data-testid="bubble-expeditions">
			<span class="icon"><Icon name="expedition" size={36} /></span>
			<div><div class="label">Expeditions</div>
				<div class="big">{notes ? ready : '—'}{#if notes}<span class="muted">/{expTotal} ready</span>{/if}</div>
				{#if notes}<div class="exps">{#each notes.expeditions as e, i (i)}
					{#if imgSrc(e.icon)}<img class="exp" class:away={!(e.finished || Date.parse(e.return_at) <= now)} src={imgSrc(e.icon)} alt="" />{/if}
				{/each}</div>{/if}</div>
		</section>
	</div>
{/if}

<style>
	.bubbles { display: grid; grid-template-columns: repeat(auto-fit, minmax(190px, 1fr)); gap: 12px; }
	.bubble { display: flex; gap: 12px; align-items: center; }
	.bubble > img, .icon { width: 44px; height: 44px; flex: none; display: inline-flex; align-items: center; justify-content: center; color: var(--gold); }
	.label { font-size: 13px; color: var(--muted); }
	.big { font-size: 26px; font-weight: 700; }
	.big .muted { font-size: 15px; font-weight: 400; }
	.ok { color: var(--accent); }
	.exps { display: flex; gap: 4px; margin-top: 4px; }
	.exp { width: 26px; height: 26px; border-radius: 50%; background: var(--panel-2); }
	.exp.away { opacity: 0.4; }
</style>
```

- [ ] **Step 3: `EndingSoon.svelte`**

```svelte
<script lang="ts">
	import Countdown from '$lib/Countdown.svelte';
	import { topReward } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import type { EventRow } from '$lib/types';
	let { events, now }: { events: EventRow[]; now: number } = $props();
</script>

{#if events.length > 0}
	<section class="panel strip" data-testid="ending-soon">
		<h2>Ending soon</h2>
		<ul>
			{#each events as e (e.id)}
				{@const r = topReward(e.rewards)}
				<li>{#if r && imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt="" />{/if}<a href="/events">{e.name}</a> <Countdown at={e.end} {now} warn /></li>
			{/each}
		</ul>
	</section>
{/if}

<style>
	.strip { border-color: var(--warn); }
	ul { list-style: none; margin: 0; padding: 0; display: flex; flex-wrap: wrap; gap: 8px 20px; }
	li { display: inline-flex; gap: 8px; align-items: center; }
	img { width: 28px; height: 28px; }
	h2 { margin-top: 0; }
</style>
```

- [ ] **Step 4: `DomainDays.svelte`**

```svelte
<script lang="ts">
	import MaterialPopover from '$lib/MaterialPopover.svelte';
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { DAY_LABELS, dayButtons } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import { gapsSettled, notCalculatedLabel, tileView } from '$lib/materials';
	import type { DayFarm, GapStatus } from '$lib/types';

	let { days, today, hasBuilds, gaps, now }: {
		days: Record<string, DayFarm>; today: number; hasBuilds: boolean; gaps: GapStatus; now: number;
	} = $props();
	let viewed = $state<number | null>(null);
	const shown = $derived(viewed ?? today);
	const buttons = $derived(dayButtons(shown, today));
	const domains = $derived(days[String(shown)]?.domains ?? []);
</script>

<section class="panel" data-testid="domains">
	<div class="head">
		<h2>Domains</h2>
		<div class="days" role="group" aria-label="Day">
			{#each buttons as b (b.day)}
				<button type="button" class="day" class:viewed={b.viewed} class:today={b.today} aria-pressed={b.viewed}
					data-testid="day-{b.day}" onclick={() => (viewed = b.day)}>{b.label}</button>
			{/each}
			<button type="button" class="day" onclick={() => (viewed = null)} disabled={shown === today}>Today</button>
		</div>
	</div>
	{#if !hasBuilds}
		<p class="muted">Mark characters as Build on <a href="/characters">Characters</a> to plan farming.</p>
	{:else if domains.length === 0}
		<p class="muted">{gapsSettled(gaps) ? `Nothing to farm on ${DAY_LABELS[shown]}` : notCalculatedLabel(gaps, now)}</p>
	{:else}
		<div class="cards">
			{#each domains as d (d.id)}
				<div class="card">
					<div class="image" aria-hidden="true"></div>
					<div class="title">{d.name}</div>
					<div class="tiles-row">
						{#each d.materials as m (m.id)}
							<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={tileView(m)}>
								{#snippet popover()}<MaterialPopover material={m} />{/snippet}
							</MaterialTile>
						{/each}
					</div>
					<div class="avatars">
						{#each d.characters as c (c.id)}
							<a href="/characters/{c.slug}" title={c.name}>{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt={c.name} />{/if}</a>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</section>

<style>
	.head { display: flex; flex-wrap: wrap; gap: 8px 16px; align-items: center; justify-content: space-between; }
	.head h2 { margin: 0; }
	.days { display: flex; flex-wrap: wrap; gap: 4px; }
	.day { border: 1px solid var(--glass-border); background: transparent; color: var(--text); border-radius: 999px; padding: 3px 10px; cursor: pointer; }
	.day.today { border-color: var(--gold); color: var(--gold); }
	.day.viewed { background: var(--accent); border-color: var(--accent); color: var(--bg); }
	.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; margin-top: 10px; }
	.card { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
	.image { height: 64px; border-radius: 8px; background: linear-gradient(135deg, var(--panel), var(--panel-2)); margin-bottom: 6px; }
	.title { font-weight: 600; }
	.tiles-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
	.avatars { display: flex; gap: 4px; }
	.avatars img { width: 28px; height: 28px; border-radius: 50%; background: var(--r0); }
</style>
```

The `.image` element is the empty slot sub-project 8 fills. The day buttons have two distinct styles: `.today` is a gold outline and `.viewed` is filled with the accent colour. When both apply, `.viewed` wins because it comes later in the CSS.

- [ ] **Step 5: `WeeklyBosses.svelte`**

This keeps the existing optimistic toggle from the old page.

```svelte
<script lang="ts">
	import MaterialPopover from '$lib/MaterialPopover.svelte';
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { api, errorMessage } from '$lib/api';
	import { imgSrc } from '$lib/img';
	import { gapsSettled, notCalculatedLabel, tileView } from '$lib/materials';
	import type { GapStatus, WeeklyBoss } from '$lib/types';

	let { weekly, hasBuilds, gaps, now }: {
		weekly: { discounts_left: number | null; discounts_max: number | null; bosses: WeeklyBoss[] };
		hasBuilds: boolean; gaps: GapStatus; now: number;
	} = $props();
	let toast = $state<string | null>(null);
	let overrides = $state<Record<string, boolean>>({});
	const bosses = $derived(weekly.bosses.map((b) => ({ ...b, done: overrides[b.name] ?? b.done }))
		.sort((a, b) => Number(a.done) - Number(b.done)));

	async function toggle(b: WeeklyBoss) {
		const done = !b.done;
		overrides = { ...overrides, [b.name]: done };
		try {
			await api.setBossDone(b.name, done);
			toast = null;
		} catch (e) {
			overrides = { ...overrides, [b.name]: !done };
			toast = errorMessage(e);
		}
	}
</script>

<section class="panel" data-testid="weekly-bosses">
	<h2>Weekly bosses {#if weekly.discounts_left !== null}<span class="muted small">Discounts {weekly.discounts_left}/{weekly.discounts_max} left</span>{/if}</h2>
	{#if toast}<p class="error">{toast}</p>{/if}
	{#if !hasBuilds}
		<p class="muted">Mark characters as Build on <a href="/characters">Characters</a> to plan farming.</p>
	{:else if bosses.length === 0}
		<p class="muted">{gapsSettled(gaps) ? 'No weekly boss drops to farm ✓' : notCalculatedLabel(gaps, now)}</p>
	{:else}
		<div class="cards">
			{#each bosses as b (b.name)}
				<div class="card" class:done={b.done} data-testid="boss-{b.name}">
					<label class="title"><input type="checkbox" checked={b.done} onchange={() => toggle(b)} aria-label="Done this week" />{b.name}</label>
					<div class="tiles-row">
						{#each b.materials as m (m.id)}
							<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={tileView(m)}>
								{#snippet popover()}<MaterialPopover material={m} />{/snippet}
							</MaterialTile>
						{/each}
					</div>
					<div class="avatars">
						{#each b.characters as c (c.id)}
							<a href="/characters/{c.slug}" title={c.name}>{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt={c.name} />{/if}</a>
						{/each}
					</div>
				</div>
			{/each}
		</div>
	{/if}
</section>

<style>
	.small { font-size: 13px; font-weight: 400; margin-left: 8px; }
	.cards { display: grid; grid-template-columns: repeat(auto-fill, minmax(240px, 1fr)); gap: 12px; }
	.card { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
	.card.done { opacity: 0.45; }
	.title { font-weight: 600; display: flex; gap: 6px; align-items: center; }
	.tiles-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
	.avatars { display: flex; gap: 4px; }
	.avatars img { width: 28px; height: 28px; border-radius: 50%; background: var(--r0); }
</style>
```

- [ ] **Step 6: `BuildCard.svelte` and `BuildList.svelte`**

```svelte
<!-- BuildCard.svelte -->
<script lang="ts">
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { buildTileView, covered } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import { notCalculatedLabel } from '$lib/materials';
	import type { BuildCard, GapStatus } from '$lib/types';

	let { card, position, gaps, now, disabled, first, last, onup, ondown }: {
		card: BuildCard; position: number; gaps: GapStatus; now: number; disabled: boolean;
		first: boolean; last: boolean; onup: () => void; ondown: () => void;
	} = $props();
</script>

<div class="card" data-testid="build-card-{card.character.slug}">
	<div class="head">
		<span class="handle" aria-hidden="true">⋮⋮</span>
		<span class="badge">P{position}</span>
		{#if imgSrc(card.character.icon)}<img src={imgSrc(card.character.icon)} alt="" />{/if}
		<div class="who">
			<a class="title" href="/characters/{card.character.slug}">{card.character.name}</a>
			{#if card.progress !== null}
				<div class="bar" role="progressbar" aria-valuenow={Math.round(card.progress * 100)} aria-valuemin={0} aria-valuemax={100}><span style="width: {card.progress * 100}%"></span></div>
			{/if}
		</div>
		<span class="moves">
			<button type="button" aria-label="Move {card.character.name} up" disabled={disabled || first} onclick={onup}>▲</button>
			<button type="button" aria-label="Move {card.character.name} down" disabled={disabled || last} onclick={ondown}>▼</button>
		</span>
	</div>
	{#if !card.calculated}
		<p class="muted">{notCalculatedLabel(gaps, now)}</p>
	{:else}
		{#if card.ready}<p class="ok">Ready to level up</p>{/if}
		<div class="tiles-row">
			{#each card.materials as m (m.id)}
				<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={buildTileView(m)} dim={covered(m)}
					testid="build-{card.character.slug}-{m.id}" />
			{/each}
		</div>
	{/if}
</div>

<style>
	.card { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; padding: 10px; }
	.head { display: flex; gap: 8px; align-items: center; }
	.handle { cursor: grab; color: var(--muted); user-select: none; }
	.badge { font-weight: 700; color: var(--gold); min-width: 28px; }
	.head img { width: 40px; height: 40px; border-radius: 8px; background: var(--r0); }
	.who { flex: 1; }
	.title { font-weight: 600; }
	.moves { display: inline-flex; gap: 4px; }
	.moves button { background: transparent; border: 1px solid var(--glass-border); color: var(--text); border-radius: 6px; width: 28px; height: 26px; cursor: pointer; }
	.moves button:disabled { opacity: 0.35; cursor: default; }
	.bar { width: 140px; height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; }
	.bar span { display: block; height: 100%; background: var(--building); }
	.tiles-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
	.ok { color: var(--accent); margin: 6px 0 0; }
</style>
```

```svelte
<!-- BuildList.svelte -->
<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import { moveItem } from '$lib/dashboard';
	import type { BuildCard as Card, GapStatus, PriorityResult } from '$lib/types';
	import BuildCard from './BuildCard.svelte';

	let { builds, gaps, now, onsaved }: {
		builds: Card[]; gaps: GapStatus; now: number; onsaved: (r: PriorityResult) => void;
	} = $props();
	let pending = $state<Card[] | null>(null);
	let saving = $state(false);
	let error = $state<string | null>(null);
	let dragFrom = $state<number | null>(null);
	const shown = $derived(pending ?? builds);

	async function move(from: number, to: number) {
		if (saving || from === to || to < 0 || to >= shown.length) return;
		const next = moveItem(shown, from, to);
		pending = next;
		saving = true;
		error = null;
		try {
			onsaved(await api.setPriority(next.map((c) => c.character.id)));
		} catch (e) {
			error = errorMessage(e);
		} finally {
			pending = null;
			saving = false;
		}
	}
</script>

<section class="panel" data-testid="builds">
	<h2>Building</h2>
	{#if error}<p class="error" role="alert">{error}</p>{/if}
	{#if shown.length === 0}
		<p class="muted">Mark characters as Build on <a href="/characters">Characters</a> to plan here.</p>
	{:else}
		<ol class="list">
			{#each shown as card, i (card.character.id)}
				<li draggable={!saving}
					ondragstart={() => (dragFrom = i)}
					ondragover={(e) => e.preventDefault()}
					ondrop={(e) => { e.preventDefault(); if (dragFrom !== null) move(dragFrom, i); dragFrom = null; }}
					ondragend={() => (dragFrom = null)}>
					<BuildCard {card} position={i + 1} {gaps} {now} disabled={saving} first={i === 0}
						last={i === shown.length - 1} onup={() => move(i, i - 1)} ondown={() => move(i, i + 1)} />
				</li>
			{/each}
		</ol>
	{/if}
</section>

<style>
	.list { list-style: none; margin: 0; padding: 0; display: grid; gap: 10px; }
</style>
```

- [ ] **Step 7: `CompletedBuilds.svelte`**

```svelte
<script lang="ts">
	import { imgSrc } from '$lib/img';
	import type { CharRef } from '$lib/types';
	let { completed }: { completed: CharRef[] } = $props();
</script>

{#if completed.length > 0}
	<section class="panel" data-testid="completed">
		<h2>Completed builds</h2>
		<div class="row">
			{#each completed as c (c.id)}
				<a href="/characters/{c.slug}" title={c.name}>
					{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt="" />{:else}<span class="initial">{c.name.slice(0, 1)}</span>{/if}
					<span>{c.name}</span>
				</a>
			{/each}
		</div>
	</section>
{/if}

<style>
	.row { display: flex; flex-wrap: wrap; gap: 12px; }
	a { display: inline-flex; flex-direction: column; align-items: center; gap: 4px; font-size: 12px; color: inherit; text-decoration: none; width: 64px; text-align: center; }
	img, .initial { width: 48px; height: 48px; border-radius: 50%; background: var(--r0); display: inline-flex; align-items: center; justify-content: center; }
</style>
```

- [ ] **Step 8: `TimerList.svelte`**

```svelte
<script lang="ts">
	import { timeLeft } from '$lib/events';
	import { imgSrc } from '$lib/img';
	import type { Timer } from '$lib/types';
	let { timers, now }: { timers: Timer[]; now: number } = $props();
</script>

<section class="panel" data-testid="timers">
	<h2>Timers</h2>
	{#if timers.length === 0}
		<p class="muted">Sync to load timers</p>
	{:else}
		<ul>
			{#each timers as t, i (i)}
				{@const ready = Date.parse(t.ready_at) <= now}
				<li>{#if imgSrc(t.icon)}<img src={imgSrc(t.icon)} alt="" />{/if}<span class="label">{t.label}</span>
					<span class:ready>{ready ? 'Ready' : timeLeft(t.ready_at, now)}</span></li>
			{/each}
		</ul>
	{/if}
</section>

<style>
	ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
	li { display: flex; gap: 8px; align-items: center; }
	img { width: 28px; height: 28px; border-radius: 50%; }
	.label { flex: 1; }
	.ready { color: var(--accent); font-weight: 600; }
</style>
```

- [ ] **Step 9: `LiveBanners.svelte`**

```svelte
<script lang="ts">
	import Countdown from '$lib/Countdown.svelte';
	import { bannerPity } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import type { DashBanner } from '$lib/types';
	let { banners, fetchedAt, now }: { banners: DashBanner[]; fetchedAt: string | null; now: number } = $props();
</script>

<section class="panel" data-testid="dash-banners">
	<h2><a href="/events">Live banners</a></h2>
	{#if banners.length === 0}
		<p class="muted">{fetchedAt ? 'No live banners.' : 'Sync to load events'}</p>
	{:else}
		<ul>
			{#each banners as b (b.id)}
				{@const five = b.items.find((i) => i.rarity === 5)}
				<li>
					{#if five && imgSrc(five.icon)}<img src={imgSrc(five.icon)} alt={five.name} />{/if}
					<div><div>{b.name}</div>
						<div class="muted small">Ends <Countdown at={b.end} {now} warn />{#if bannerPity(b.pity)} · {bannerPity(b.pity)}{/if}</div></div>
				</li>
			{/each}
		</ul>
	{/if}
</section>

<style>
	ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 8px; }
	li { display: flex; gap: 10px; align-items: center; }
	img { width: 40px; height: 40px; border-radius: 50%; background: var(--r5); }
	.small { font-size: 12px; }
</style>
```

- [ ] **Step 10: `EventList.svelte`**

```svelte
<script lang="ts">
	import Countdown from '$lib/Countdown.svelte';
	import { api, errorMessage } from '$lib/api';
	import { topReward } from '$lib/dashboard';
	import { imgSrc } from '$lib/img';
	import type { DashEventItem } from '$lib/types';

	let { events, fetchedAt, now }: { events: DashEventItem[]; fetchedAt: string | null; now: number } = $props();
	let overrides = $state<Record<number, boolean>>({});
	let toast = $state<string | null>(null);
	const rows = $derived(events.map((e) => (e.kind === 'event' && e.id in overrides ? { ...e, done: overrides[e.id] } : e)));

	async function toggle(id: number, done: boolean) {
		overrides = { ...overrides, [id]: done };
		try {
			await api.setEventDone(id, done);
			toast = null;
		} catch (e) {
			overrides = { ...overrides, [id]: !done };
			toast = errorMessage(e);
		}
	}
</script>

<section class="panel" data-testid="dash-events">
	<h2><a href="/events">Events</a></h2>
	{#if toast}<p class="error">{toast}</p>{/if}
	{#if !fetchedAt}<p class="muted">Sync to load events</p>{/if}
	<ul>
		{#each rows as e (e.id)}
			<li class:done={e.done} data-testid="dash-event-{e.id}">
				{#if e.kind === 'event'}
					{@const r = topReward(e.rewards)}
					<input type="checkbox" checked={e.done} disabled={e.finished} aria-label="Done: {e.name}"
						onchange={() => toggle(e.id, !e.done)} />
					{#if r && imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt="" />{/if}
					<span class="name">{e.name}</span>
					<Countdown at={e.end} {now} warn={!e.done} />
				{:else}
					<span class="reset">↻</span><span class="name">{e.name}</span><Countdown at={e.end} {now} />
				{/if}
			</li>
		{/each}
	</ul>
</section>

<style>
	ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 6px; }
	li { display: flex; gap: 8px; align-items: center; }
	li.done { opacity: 0.45; }
	img { width: 24px; height: 24px; }
	.name { flex: 1; }
	.reset { width: 13px; text-align: center; color: var(--muted); }
</style>
```

`Countdown` with `warn` turns red under 24 hours through the existing `countdownWarn`, and `timeLeft` already formats "4d 6h" and "5h 12m".

`{@const}` sits directly inside `{#if}` because Svelte 5 requires it to be the block's first child.

- [ ] **Step 11: Rewrite `+page.svelte`**

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import BuildList from '$lib/dashboard/BuildList.svelte';
	import CompletedBuilds from '$lib/dashboard/CompletedBuilds.svelte';
	import DomainDays from '$lib/dashboard/DomainDays.svelte';
	import EndingSoon from '$lib/dashboard/EndingSoon.svelte';
	import EventList from '$lib/dashboard/EventList.svelte';
	import Greeting from '$lib/dashboard/Greeting.svelte';
	import LiveBanners from '$lib/dashboard/LiveBanners.svelte';
	import NoteBubbles from '$lib/dashboard/NoteBubbles.svelte';
	import TimerList from '$lib/dashboard/TimerList.svelte';
	import WeeklyBosses from '$lib/dashboard/WeeklyBosses.svelte';
	import { gapLabel, shouldPoll } from '$lib/materials';
	import { sync } from '$lib/sync.svelte';
	import { timeAgo } from '$lib/time';
	import type { Dashboard, PriorityResult } from '$lib/types';

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

	$effect(() => {
		if (!shouldPoll(data?.gaps)) return;
		const t = setTimeout(load, 2000);
		return () => clearTimeout(t);
	});

	function saved(r: PriorityResult) {
		if (data) data = { ...data, builds: r.builds, completed: r.completed };
		void load();   // domain and boss cards re-rank by the new priority
	}
</script>

<svelte:head><title>Dashboard · Ad Astra</title></svelte:head>

{#if error}<p class="error">{error}</p>{/if}
{#if data}
	<div class="dash">
		<div class="centre">
			<Greeting name={data.display_name} {now} />
			<NoteBubbles notes={data.notes} connection={data.connection} {now} />
			{#if data.notes}<p class="muted small">As of {timeAgo(data.notes.fetched_at, now)} · {gapLabel(data.gaps, now)}</p>{/if}
			<EndingSoon events={data.ending_soon} {now} />
			<DomainDays days={data.domains_by_day} today={data.server_weekday}
				hasBuilds={data.builds.length + data.completed.length > 0} gaps={data.gaps} {now} />
			<WeeklyBosses weekly={data.weekly_bosses} hasBuilds={data.builds.length + data.completed.length > 0}
				gaps={data.gaps} {now} />
			<!-- Sub-project 8 adds the Artifact domains section here. -->
			<BuildList builds={data.builds} gaps={data.gaps} {now} onsaved={saved} />
			<CompletedBuilds completed={data.completed} />
		</div>
		<aside class="side">
			<TimerList timers={data.timers} {now} />
			<LiveBanners banners={data.live_banners} fetchedAt={data.calendar_fetched_at} {now} />
			<EventList events={data.events} fetchedAt={data.calendar_fetched_at} {now} />
		</aside>
	</div>
{/if}

<style>
	.dash { display: grid; grid-template-columns: minmax(0, 2fr) minmax(280px, 1fr); gap: 16px; align-items: start; }
	.centre, .side { display: grid; gap: 12px; min-width: 0; }
	.small { font-size: 12px; margin: 0; }
	@media (max-width: 1100px) { .dash { grid-template-columns: minmax(0, 1fr); } }
</style>
```

Before saving, check how other pages set the title: `grep -rn "svelte:head" frontend/src/routes`. Match their pattern; drop the line if no page sets one.

- [ ] **Step 12: Run the checks**

Run from `frontend/`: `npm run check`, `npx vitest run`, `npm run build`.
Expected: 0 errors and 0 warnings from svelte-check, vitest passes, and the build succeeds.

Fix any accessibility warnings svelte-check raises. For example, a `draggable` `<li>` may need `role="listitem"`, which it already has implicitly; if a warning still asks for it, add `aria-roledescription="sortable item"`.

- [ ] **Step 13: Commit**

```bash
git add frontend/src/lib/dashboard frontend/src/routes/+page.svelte
git commit -m "feat(dashboard): two-column dashboard with priority build list and side column"
```

---

### Task 9: End-to-end tests and full verification

**Files:**
- Create: `frontend/e2e/dashboard.spec.ts`
- Modify:
  - `frontend/e2e/planner.spec.ts` (first test)
  - `frontend/e2e/events.spec.ts` (first test)
  - `frontend/e2e/wishes.spec.ts` (`dashboard shows the pity card`)
  - `frontend/e2e/profile.spec.ts` (drop the dashboard lines)

**Interfaces:**
- Consumes: the test ids from Task 8 and the dev-seed numbers from Task 6 Step 8.

Playwright spec files share one seeded server and may run in parallel workers. So any test that changes state must either put it back or touch only data no other spec reads.

- [ ] **Step 1: Write `dashboard.spec.ts`**

```ts
import { expect, test } from '@playwright/test';

test('dashboard shows every section in order', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('greeting')).toContainText(/Good (morning|afternoon|evening), /);
	for (const id of ['bubble-resin', 'bubble-commissions', 'bubble-realm', 'bubble-expeditions', 'ending-soon',
		'domains', 'weekly-bosses', 'builds', 'completed', 'timers', 'dash-banners', 'dash-events']) {
		await expect(page.getByTestId(id)).toBeVisible();
	}
	await expect(page.getByTestId('bubble-commissions')).toContainText('Bonus not claimed');
	await expect(page.getByTestId('bubble-expeditions')).toContainText('1/5 ready');
	await expect(page.getByTestId('completed')).toContainText('Neuvillette');
	await expect(page.getByTestId('timers')).toContainText('Parametric Transformer');
	await expect(page.getByTestId('timers')).toContainText('Ready');
	await expect(page.getByTestId('ending-soon')).toContainText('Photo Event');
	await expect(page.getByTestId('dash-event-9004').getByRole('checkbox')).toBeDisabled();   // finished in game
	await expect(page.getByTestId('dash-events')).toContainText('Stygian Onslaught');
});

test('day picker switches the viewed day and keeps today marked', async ({ page }) => {
	await page.goto('/');
	const domains = page.getByTestId('domains');
	const today = domains.locator('button.day.today');
	await expect(today).toHaveAttribute('aria-pressed', 'true');
	const todayId = await today.getAttribute('data-testid');
	const other = todayId === 'day-0' ? 'day-1' : 'day-0';
	await page.getByTestId(other).click();
	await expect(page.getByTestId(other)).toHaveAttribute('aria-pressed', 'true');
	await expect(page.getByTestId(todayId!)).toHaveAttribute('aria-pressed', 'false');
	await expect(page.getByTestId(todayId!)).toHaveClass(/today/);
	await expect(domains).toContainText('Domain of Mastery: Forsaken Rift');      // open every day in the seed
	await domains.getByRole('button', { name: 'Today' }).click();
	await expect(page.getByTestId(todayId!)).toHaveAttribute('aria-pressed', 'true');
});

test('moving a character up re-allocates counts, then moving back restores them', async ({ page }) => {
	await page.goto('/');
	const benGuide = page.getByTestId('build-bennett-104302');
	const furGuide = page.getByTestId('build-furina-104302');
	await expect(benGuide).toContainText('8/9');
	await expect(benGuide).toContainText('+1 craft');
	await expect(furGuide).toContainText('0/6');
	await expect(furGuide).toContainText('+2 craft');
	await page.getByRole('button', { name: 'Move Furina up' }).click();
	await expect(page.getByTestId('build-card-furina')).toContainText('P1');
	await expect(furGuide).toContainText('6/6');
	await expect(benGuide).toContainText('2/9');
	await expect(benGuide).toContainText('+3 craft');
	await page.reload();
	await expect(page.getByTestId('build-card-furina')).toContainText('P1');      // saved
	await page.getByRole('button', { name: 'Move Furina down' }).click();
	await expect(page.getByTestId('build-card-bennett')).toContainText('P1');
	await expect(benGuide).toContainText('8/9');
});

test('display name shows in the greeting', async ({ page }) => {
	await page.goto('/settings');
	const input = page.getByTestId('display-name');
	await input.fill('Paimon');
	await input.blur();
	await expect(page.getByTestId('display-name-note')).toHaveText('Saved');
	await page.goto('/');
	await expect(page.getByTestId('greeting')).toContainText(', Paimon');
	await page.goto('/settings');
	await page.getByTestId('display-name').fill('');
	await page.getByTestId('display-name').blur();
	await expect(page.getByTestId('display-name-note')).toHaveText('Saved');
});
```

The `settings.spec.ts` test from Task 5 and this greeting test both write `display_name` and both reset it at the end. If they still race under parallel workers, move the greeting test into `settings.spec.ts` straight after the Task 5 test, since tests in one file run serially.

- [ ] **Step 2: Update the existing specs**

`frontend/e2e/planner.spec.ts`, first test: replace `page.getByTestId('farm-today')` with `page.getByTestId('domains')`. The boss lines stay the same, because `boss-Stormterror` and the "Done this week" checkbox are kept.

`frontend/e2e/events.spec.ts`, first test: replace it with:

```ts
test('ticking an event Done on the Events page shows it done on the Dashboard', async ({ page }) => {
	await page.goto('/events');
	const row = page.getByTestId('event-9002');
	await row.getByRole('checkbox').check();
	await expect(row).toHaveClass(/done/);
	await expect(page.getByTestId('events-left')).toContainText('2 events left · 420 primos unclaimed');
	await page.goto('/');
	await expect(page.getByTestId('dash-event-9002')).toHaveClass(/done/);
	await expect(page.getByTestId('dash-banners')).toContainText('Tide of Furina');
	await expect(page.getByTestId('dash-events')).toContainText('Spiral Abyss');
	await page.goto('/events');
	await page.getByTestId('event-9002').getByRole('checkbox').uncheck();
});
```

The test now unticks 9002 at the end, so it no longer leaves state behind for `dashboard.spec.ts`. That spec asserts on 9003 and 9004 only, so it would not be affected either way.

`frontend/e2e/wishes.spec.ts`: replace `dashboard shows the pity card` with:

```ts
test('dashboard shows pity on the live character banner', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('dash-banners')).toContainText('Pity 2/90 · 50/50');
});
```

`frontend/e2e/profile.spec.ts`: delete the last two lines, `await page.goto('/');` and the `dash-profile` assertion.

- [ ] **Step 3: Run the full verification**

Backend, from `backend/`:
`C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe -m pytest -q`

Frontend, from `frontend/`:
`npm run check`, then `npx vitest run`, then `npm run build`, then `PYTHON=C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe npx playwright test`.

Expected: everything passes. Record the counts in the commit message body, for example "pytest N, vitest N, Playwright N".

- [ ] **Step 4: Check the layout in the real app**

Start the dev seed and server the way `playwright.config.ts` does, and open `/` in the in-app browser.

Check:
1. The two columns appear at 1400px and stack at 900px.
2. There is no horizontal scroll.
3. The day buttons show distinct "viewed" and "today" styles.
4. Dragging a card onto another card reorders the list.
5. The resin, realm and transformer icons load. They come through `/api/img` and need network; offline, the slot is empty, which is acceptable.

Stop the server afterwards.

- [ ] **Step 5: Check that nothing sensitive is staged**

Run: `git diff --cached | grep -inE "ltoken|cookie_token|account_id_v2|@gmail|password|[0-9]{9}"`.
Expected: no output, except the made-up UID `800000001` if it appears.

- [ ] **Step 6: Commit**

```bash
git add frontend/e2e
git commit -m "test(dashboard): e2e for sections, day picker, priority re-allocation and greeting"
```

---

## Spec coverage check (done while writing)

| Spec section | Task |
|---|---|
| 2 data sources: new notes fields, `is_finished` | 4 |
| 3.1 greeting / bubbles / ending soon / domains / bosses / artifact slot / building / completed | 5, 6, 8 |
| 3.2 timers / banners + pity / events + resets | 6, 8 |
| 3.3 removals | 6 (payload), 8 (page), 9 (e2e) |
| 4 data model, priority rule, `display_name` | 1, 2, 5 |
| 5 allocation | 3 |
| 6 API | 6 |
| 7 front end, reorder rollback | 7, 8 |
| 8 errors and empty states | 6 (`test_dashboard_empty_account`), 8 |
| 9 testing, dev seed | every task; dev seed in 6, e2e in 9 |
