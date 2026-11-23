# Ad Astra Sub-project 4 — Characters Overview and Teams Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the Characters overview (small/large tiles, stacked sort toggles, greyed unowned, full width) and redesign Teams (18° splash ribbons, team info section with a Build switch that raises *and* lowers goals, shortfall drawer, popup editor, coloured default tags).

**Architecture:** Build stays the built-in tag (id 1). A new `lower_from_build` in `backend/app/teams/goals.py` mirrors `raise_to_build`; `store.save_team`, `store.delete_team` and a new `store.set_build` return `(raised, lowered)`. Migration 0009 adds eight default tags. The frontend gets shared pure helpers (`sortCharacters`, `willLower`, `talentParts`, `slantInset`), a shared `CharacterFilterBar` and `CharacterTile`, a ribbon-based `TeamRow`, and a `<dialog>`-based `TeamEditorModal` driven by `/teams?edit=<id|new>`.

**Tech Stack:** FastAPI + SQLAlchemy 2 + Alembic + SQLite (backend); SvelteKit 2, Svelte 5 runes, TypeScript, Vitest, Playwright (frontend).

**Spec:** `docs/superpowers/specs/2026-11-23-ad-astra-characters-teams-design.md` (read it with this plan).

## Global Constraints

- Cookie values only in the git-ignored `.env`; never logged, returned or committed.
- Unofficial API code stays in `backend/app/sync/` and `backend/app/wishes/`; this plan adds none.
- Test fixtures and the dev seed use made-up data only (UID 800000001).
- No game art or personal data committed; images load at runtime through `/api/img/<UI_name>` (`imgSrc()` in the frontend).
- Every goal change goes through `app.planner.order.apply_goal` (keeps Build priority right).
- `schedule_gaps()` must be called from inside the event loop: any endpoint that may call it is `async def`.
- Ribbon slant is 18°; the info block inset is `slantInset(height)` + 10px; the team info section inset is `slantInset(row height)` + 12px.
- Tag palette (in this order): `orange, red, yellow, green, teal, blue, purple, pink, navy, gold`; navy `#2a3f8f`, gold `#a9842c`.
- Default tags: Abyss navy, Theater purple, Nuke red, AoE yellow, Boss gold, Exploration green, Main teal, Fun pink.
- `localStorage` key `aa.characterView`; every access in try/catch.
- Commands (Windows; run from the named folder):
  - Backend: `C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe -m pytest -q` from `backend/`
  - Frontend: `npm run check`, `npx vitest run`, `npm run build` from `frontend/` (run `npm ci` once if `node_modules` is missing)
  - E2E: `PYTHON=C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe npx playwright test` from `frontend/` (one shared seeded server; every test restores what it changes)
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A character in two Build teams**: switching one team off must leave that character on Build — pinned in Task 2 (`test_lower_keeps_member_of_other_build_team`) and Task 4 (`willLower` shared-team case).
2. **Swap in one save** (remove one member, add another, Build kept): exactly one raise and one lower in one transaction — Task 2 (`test_swap_raises_and_lowers`).
3. **Switch toggled to the state it already has** (double click, stale page): no goal change, empty lists — Task 3 (`test_build_endpoint_noop`).
4. **A user tag already named like a default** ("abyss", "FUN"): migration must not duplicate or recolour it — Task 1 (`test_0009_skips_existing_names`).
5. **Unsaved popup closed by back button / Esc / backdrop**: must ask before discarding — Task 7 e2e (`popup asks before discarding`).

---

## File map

| File | Change |
|---|---|
| `backend/migrations/versions/0009_default_tags.py` | Create: default tags |
| `backend/app/teams/goals.py` | Add `BUILD_TAG_ID`, `lower_from_build` |
| `backend/app/teams/store.py` | Palette; `save_team`/`delete_team` return lowered; new `set_build` |
| `backend/app/teams/artifacts.py` | Add `artifact_sets` |
| `backend/app/teams/view.py` | Member gains `constellation`, `splash`, `artifact_sets` |
| `backend/app/api/teams.py` | `lowered` in responses; async delete; `PUT /teams/{id}/build` |
| `backend/app/api/characters.py` | `release_at` in payload |
| `backend/app/devseed.py` | Reuse migration's Abyss tag |
| `backend/tests/helpers.py` | `drop_default_tags` |
| `backend/tests/test_migration_0009.py` | Create |
| `backend/tests/test_teams_goals.py`, `test_teams_store.py`, `test_api_teams.py`, `test_devseed.py`, `test_api_settings.py`, `test_api_characters.py` | Update / extend |
| `frontend/src/lib/types.ts`, `api.ts` | New fields / endpoint |
| `frontend/src/lib/teams.ts` (+ test) | Palette, `willLower`, `memberLookup`, `loweredMessage`, `talentParts`, `slantInset` |
| `frontend/src/lib/status.ts` (+ test) | `SortKeys`, `sortCharacters`; `groupCharacters` uses it |
| `frontend/src/lib/characterView.ts` (+ test) | Create: tile size + sort preference |
| `frontend/src/lib/nav.ts` (+ test), `routes/+layout.svelte` | `WIDE_ROUTES` / `isWide` |
| `frontend/src/lib/CharacterTile.svelte` | Create (replaces `CharacterCard.svelte`) |
| `frontend/src/lib/CharacterFilterBar.svelte` | Create |
| `frontend/src/routes/characters/+page.svelte` | Use the above |
| `frontend/src/lib/TeamRibbon.svelte`, `TeamInfo.svelte`, `TeamShortfall.svelte`, `TeamRow.svelte` | Create (replace `TeamCard.svelte`) |
| `frontend/src/routes/teams/+page.svelte` | Rewrite |
| `frontend/src/lib/TeamEditorModal.svelte` | Create (replaces `TeamEditor.svelte`) |
| `frontend/src/routes/teams/new/+page.ts`, `teams/[id]/+page.ts` | Redirects (replace the `+page.svelte` files) |
| `frontend/e2e/teams.spec.ts`, `characters.spec.ts` | Rewrite / extend |

---

### Task 1: Default tags migration, palette, dev seed

**Files:**
- Create: `backend/migrations/versions/0009_default_tags.py`, `backend/tests/test_migration_0009.py`
- Modify: `backend/app/teams/store.py:15` (palette), `backend/app/devseed.py:164-178`, `backend/tests/helpers.py`, `backend/tests/test_teams_store.py` (fixture), `backend/tests/test_api_teams.py`, `backend/tests/test_devseed.py:70-80`

**Interfaces:**
- Produces: `store.TAG_COLORS` with 10 entries (navy, gold appended); `helpers.drop_default_tags(sf)`; DB contains tags Build(1) + 8 defaults after `migrate()`.

- [ ] **Step 1: Write the failing migration test** — `backend/tests/test_migration_0009.py`:

```python
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
```

- [ ] **Step 2: Run it — expect FAIL** (`Can't locate revision identified by '0009'`)

Run (from `backend/`): `C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe -m pytest -q tests/test_migration_0009.py`

- [ ] **Step 3: Write the migration** — `backend/migrations/versions/0009_default_tags.py`:

```python
"""Ad Astra sub-project 4: default coloured team tags

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-23
"""
import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

DEFAULT_TAGS = (("Abyss", "navy"), ("Theater", "purple"), ("Nuke", "red"), ("AoE", "yellow"), ("Boss", "gold"),
                ("Exploration", "green"), ("Main", "teal"), ("Fun", "pink"))


def upgrade() -> None:
    bind = op.get_bind()
    existing = {r[0] for r in bind.execute(sa.text("SELECT name_key FROM tag"))}
    for name, color in DEFAULT_TAGS:
        if name.lower() in existing:
            continue
        bind.execute(sa.text("INSERT INTO tag (name, name_key, color, builtin) VALUES (:n, :k, :c, 0)"),
                     {"n": name, "k": name.lower(), "c": color})


def downgrade() -> None:
    bind = op.get_bind()
    for name, _color in DEFAULT_TAGS:
        bind.execute(sa.text("DELETE FROM tag WHERE name_key = :k AND builtin = 0 "
                             "AND id NOT IN (SELECT tag_id FROM team_tag)"), {"k": name.lower()})
```

- [ ] **Step 4: Extend the palette** — `backend/app/teams/store.py` line 15:

```python
TAG_COLORS = ("orange", "red", "yellow", "green", "teal", "blue", "purple", "pink", "navy", "gold")
```

- [ ] **Step 5: Add the test helper** — append to `backend/tests/helpers.py`:

```python
def drop_default_tags(sf) -> None:
    """Remove the migration's default tags so a test starts with only Build."""
    from sqlalchemy import delete
    from app.db.models import Tag
    with sf.begin() as s:
        s.execute(delete(Tag).where(Tag.builtin.is_(False)))
```

- [ ] **Step 6: Make the existing tag tests start from Build only**
  - `backend/tests/test_teams_store.py`: import `drop_default_tags` from `helpers` and change the fixture to

    ```python
    @pytest.fixture
    def sf(session_factory):
        seed_game(session_factory)
        drop_default_tags(session_factory)
        return session_factory
    ```
  - `backend/tests/test_api_teams.py`: import `drop_default_tags` from `helpers`; in `test_create_list_get_update_delete` and `test_tag_endpoints` call `drop_default_tags(sf)` right after `sf = setup(paths)` (in `test_tag_endpoints` change `setup(paths)` to `sf = setup(paths)`).
  - Add a test to `backend/tests/test_teams_store.py`:

    ```python
    def test_palette_accepts_navy_and_gold(sf):
        with sf.begin() as s:
            t = store.create_tag(s, "night", color="navy")
            assert store.update_tag(s, t.id, None, "gold").color == "gold"
    ```

- [ ] **Step 7: Dev seed reuses the migration's Abyss tag** — in `backend/app/devseed.py` replace `s.add(Tag(id=2, name="abyss", name_key="abyss", color="red", builtin=False))` and the `[1, 2]` tag list:

```python
        abyss = s.scalar(select(Tag).where(Tag.name_key == "abyss")).id   # created by migration 0009
        teams = [
            (1, "Abyss Furina", "Demo: Build + abyss.", [("furina", "on-field"), ("bennett", "battery"),
                                                         ("xingqiu", "off-field hydro")], [1, abyss]),
            (2, "Archons only", "", [("furina", ""), ("nahida", ""), ("raiden-shogun", "")], []),
        ]
```

(Add `from sqlalchemy import select` to the imports if it is not there yet.) Update `backend/tests/test_devseed.py` `test_devseed_teams`:

```python
    assert [t["name"] for t in abyss["tags"]] == ["Build", "Abyss"]
    ...
    assert [(t["name"], t["team_count"]) for t in tags] == [
        ("Build", 1), ("Abyss", 1), ("AoE", 0), ("Boss", 0), ("Exploration", 0), ("Fun", 0), ("Main", 0),
        ("Nuke", 0), ("Theater", 0)]
```

- [ ] **Step 8: Run the whole backend suite — expect PASS**

Run: `C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe -m pytest -q`
If any other test fails only because the defaults now exist, call `drop_default_tags` in its setup rather than changing its assertions.

- [ ] **Step 9: Commit**

```bash
git add backend/migrations/versions/0009_default_tags.py backend/app/teams/store.py backend/app/devseed.py backend/tests
git commit -m "feat(teams): default coloured tags (migration 0009), navy and gold palette

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: `lower_from_build` and the store's raise/lower rules

**Files:**
- Modify: `backend/app/teams/goals.py`, `backend/app/teams/store.py` (`save_team`, `delete_team`, new `set_build`)
- Test: `backend/tests/test_teams_goals.py`, `backend/tests/test_teams_store.py`

**Interfaces:**
- Consumes: `apply_goal(session, row, new_goal)` from `app.planner.order`.
- Produces:
  - `goals.BUILD_TAG_ID = 1` (store re-exports it: `from app.teams.goals import BUILD_TAG_ID, lower_from_build, raise_to_build`)
  - `lower_from_build(session: Session, character_ids: Iterable[int], exclude_team_id: int | None) -> list[int]`
  - `store.save_team(...) -> tuple[Team, list[int], list[int]]` (team, raised, lowered)
  - `store.delete_team(s, team_id) -> list[int]` (lowered)
  - `store.set_build(s, team_id: int, on: bool) -> tuple[list[int], list[int]]` (raised, lowered)

- [ ] **Step 1: Write failing goal tests** — append to `backend/tests/test_teams_goals.py`:

```python
from app.db.models import Tag, Team, TeamMember, TeamTag
from app.teams.goals import lower_from_build


def team_with(s, tid, members, build):
    s.add(Team(id=tid, name=f"T{tid}", notes="", sort_order=tid, created_at=NOW, updated_at=NOW))
    s.flush()
    for slot, cid in enumerate(members):
        s.add(TeamMember(team_id=tid, slot=slot, character_id=cid, role=""))
    if build:
        s.add(TeamTag(team_id=tid, tag_id=1))


def test_lower_build_to_none_and_clears_priority(session_factory):
    with session_factory.begin() as s:
        add_goal(s, 1, "build", (80, 6, 6, 6, 80))
        s.get(CharacterGoal, 1).priority = 3
        add_goal(s, 2, "want")
    with session_factory.begin() as s:
        assert lower_from_build(s, [1, 2, 3], None) == [1]
    with session_factory() as s:
        row = s.get(CharacterGoal, 1)
        assert (row.goal, row.priority, row.target_level) == ("none", None, 80)   # targets kept
        assert s.get(CharacterGoal, 2).goal == "want" and s.get(CharacterGoal, 3) is None


def test_lower_keeps_member_of_other_build_team(session_factory):
    with session_factory.begin() as s:
        for cid in (1, 2):
            add_goal(s, cid, "build")
        team_with(s, 10, [1, 2], build=False)     # the team being switched off
        team_with(s, 11, [1], build=True)         # another Build team still has 1
        team_with(s, 12, [2], build=False)        # a non-Build team does not protect 2
    with session_factory.begin() as s:
        assert lower_from_build(s, [1, 2], exclude_team_id=10) == [2]


def test_lower_then_raise_restores_targets(session_factory):
    with session_factory.begin() as s:
        add_goal(s, 1, "build", (70, 9, 9, 9, 70))
    with session_factory.begin() as s:
        lower_from_build(s, [1], None)
    with session_factory.begin() as s:
        assert raise_to_build(s, [1], DEFAULTS) == [1]
    with session_factory() as s:
        assert s.get(CharacterGoal, 1).target_level == 70
```

- [ ] **Step 2: Run — expect FAIL** (`ImportError: cannot import name 'lower_from_build'`)

Run: `...python.exe -m pytest -q tests/test_teams_goals.py`

- [ ] **Step 3: Implement** — in `backend/app/teams/goals.py` add below the imports and after `raise_to_build`:

```python
from sqlalchemy import select

from app.db.models import TeamMember, TeamTag

BUILD_TAG_ID = 1
```

```python
def _in_other_build_team(session: Session, exclude_team_id: int | None) -> set[int]:
    q = (select(TeamMember.character_id)
         .join(TeamTag, TeamTag.team_id == TeamMember.team_id)
         .where(TeamTag.tag_id == BUILD_TAG_ID))
    if exclude_team_id is not None:
        q = q.where(TeamMember.team_id != exclude_team_id)
    return set(session.scalars(q))


def lower_from_build(session: Session, character_ids: Iterable[int], exclude_team_id: int | None) -> list[int]:
    """Build -> none for ids no other Build team still lists. Targets are kept. Returns the ids changed."""
    ids = list(dict.fromkeys(character_ids))
    if not ids:
        return []
    covered = _in_other_build_team(session, exclude_team_id)
    lowered: list[int] = []
    for cid in ids:
        row = session.get(CharacterGoal, cid)
        if row is None or row.goal != "build" or cid in covered:
            continue
        apply_goal(session, row, "none")
        row.updated_at = utcnow()
        lowered.append(cid)
    if lowered:
        session.flush()
    return lowered
```

Update the module docstring to: `"""The only place teams change goals: raise to build, or lower build -> none when no Build team still needs it."""`

- [ ] **Step 4: Run — expect PASS** (`tests/test_teams_goals.py`)

- [ ] **Step 5: Write failing store tests** — in `backend/tests/test_teams_store.py`:
  - change the `save` helper to return three values:

    ```python
    def save(sf, team_id=None, members=(BEN,), tags=(), new_tags=(), name="Team", notes="", roles=None):
        roles = roles or {}
        with sf.begin() as s:
            team, raised, lowered = store.save_team(s, team_id, name, notes,
                                                    [MemberIn(c, roles.get(c, "")) for c in members],
                                                    list(tags), list(new_tags))
            return team.id, raised, lowered
    ```
  - update every existing caller: `tid, raised = save(...)` → `tid, raised, _ = save(...)`, `_, raised = save(...)` → `_, raised, _ = save(...)`, `tid, _ = save(...)` / `a, _ = save(...)` → `tid, _, _ = ...` / `a, _, _ = ...`.
  - replace `test_removals_change_no_goals` with:

    ```python
    def test_build_off_lowers_all_members(sf):
        tid, _, _ = save(sf, members=(BEN, FUR), tags=(BUILD_TAG_ID,))
        _, raised, lowered = save(sf, tid, members=(BEN, FUR), tags=())
        assert (raised, lowered) == ([], [BEN, FUR])
        assert goals(sf, BEN, FUR) == ["none", "none"]


    def test_removing_member_from_build_team_lowers_it(sf):
        tid, _, _ = save(sf, members=(BEN, FUR), tags=(BUILD_TAG_ID,))
        _, _, lowered = save(sf, tid, members=(BEN,), tags=(BUILD_TAG_ID,))
        assert lowered == [FUR] and goals(sf, BEN, FUR) == ["build", "none"]


    def test_swap_raises_and_lowers(sf):
        tid, _, _ = save(sf, members=(BEN, FUR), tags=(BUILD_TAG_ID,))
        _, raised, lowered = save(sf, tid, members=(BEN, XL), tags=(BUILD_TAG_ID,))
        assert (raised, lowered) == ([XL], [FUR])
        assert goals(sf, BEN, FUR, XL) == ["build", "none", "build"]


    def test_team_without_build_never_lowers(sf):
        set_goal(sf, BEN, "build")
        tid, _, _ = save(sf, members=(BEN, FUR))
        _, _, lowered = save(sf, tid, members=(FUR,))
        with sf.begin() as s:
            assert store.delete_team(s, tid) == []
        assert lowered == [] and goals(sf, BEN) == ["build"]


    def test_delete_build_team_lowers_except_shared(sf):
        a, _, _ = save(sf, name="A", members=(BEN, FUR), tags=(BUILD_TAG_ID,))
        save(sf, name="B", members=(FUR,), tags=(BUILD_TAG_ID,))
        with sf.begin() as s:
            assert store.delete_team(s, a) == [BEN]
        assert goals(sf, BEN, FUR) == ["none", "build"]


    def test_set_build(sf):
        tid, _, _ = save(sf, members=(BEN, FUR))
        with sf.begin() as s:
            assert store.set_build(s, tid, True) == ([BEN, FUR], [])
        with sf.begin() as s:
            assert store.set_build(s, tid, True) == ([], [])          # already on: no-op
        with sf.begin() as s:
            assert store.set_build(s, tid, False) == ([], [BEN, FUR])
        with sf.begin() as s:
            assert store.set_build(s, tid, False) == ([], [])
        with pytest.raises(TeamError) as e:
            with sf.begin() as s:
                store.set_build(s, 999, True)
        assert (e.value.status, e.value.message) == (404, "Team not found")
    ```
  - in `test_failed_write_rolls_back_everything` keep the monkeypatch of `store.raise_to_build` (store imports the name, so patching `store.raise_to_build` still works).

- [ ] **Step 6: Run — expect FAIL** (unpacking errors / `set_build` missing)

- [ ] **Step 7: Implement in `backend/app/teams/store.py`**
  - imports: replace `from app.teams.goals import raise_to_build` and the `BUILD_TAG_ID = 1` line with `from app.teams.goals import BUILD_TAG_ID, lower_from_build, raise_to_build`.
  - `save_team`: change the return annotation to `tuple[Team, list[int], list[int]]` and replace its tail (from `to_raise: list[int] = []`) with:

    ```python
        has_build = BUILD_TAG_ID in final_tags
        to_raise: list[int] = []
        if has_build:
            to_raise = ids if not had_build else [cid for cid in ids if cid not in old_members]
        raised = raise_to_build(s, to_raise, default_targets(s)) if to_raise else []
        to_lower: list[int] = []
        if had_build and not has_build:
            to_lower = list(dict.fromkeys([*ids, *sorted(old_members)]))
        elif had_build:
            to_lower = sorted(old_members - set(ids))
        lowered = lower_from_build(s, to_lower, team.id) if to_lower else []
        return team, raised, lowered
    ```
  - `delete_team`:

    ```python
    def delete_team(s: Session, team_id: int) -> list[int]:
        if s.get(Team, team_id) is None:
            raise TeamError(404, "Team not found")
        had_build = s.get(TeamTag, (team_id, BUILD_TAG_ID)) is not None
        members = list(s.scalars(select(TeamMember.character_id).where(TeamMember.team_id == team_id)
                                 .order_by(TeamMember.slot)))
        s.execute(delete(Team).where(Team.id == team_id))
        s.flush()
        return lower_from_build(s, members, team_id) if had_build else []
    ```
  - new `set_build` after `delete_team`:

    ```python
    def set_build(s: Session, team_id: int, on: bool) -> tuple[list[int], list[int]]:
        team = s.get(Team, team_id)
        if team is None:
            raise TeamError(404, "Team not found")
        has = s.get(TeamTag, (team_id, BUILD_TAG_ID)) is not None
        if has == on:
            return [], []
        members = list(s.scalars(select(TeamMember.character_id).where(TeamMember.team_id == team_id)
                                 .order_by(TeamMember.slot)))
        if on:
            s.add(TeamTag(team_id=team_id, tag_id=BUILD_TAG_ID))
        else:
            s.execute(delete(TeamTag).where(TeamTag.team_id == team_id, TeamTag.tag_id == BUILD_TAG_ID))
        team.updated_at = utcnow()
        s.flush()
        if on:
            return raise_to_build(s, members, default_targets(s)), []
        return [], lower_from_build(s, members, team_id)
    ```
    Deleting a team relies on `ON DELETE CASCADE` for members and tag links (as today); if SQLite foreign keys are not enforced in this session, the existing `test_teams_store` cascade tests would already fail, so no extra code is needed.

- [ ] **Step 8: Fix the one non-test caller** — `backend/app/api/teams.py` `_save`: `team, raised = store.save_team(...)` → `team, raised, lowered = store.save_team(...)` and return `{"team": _one(s, tid), "raised": raised, "lowered": lowered}`; schedule gaps when `raised or lowered`. (Task 3 finishes the API.)

- [ ] **Step 9: Run the backend suite — expect PASS**

- [ ] **Step 10: Commit**

```bash
git add backend/app/teams backend/app/api/teams.py backend/tests
git commit -m "feat(teams): switching Build off, removing or deleting moves members off Build unless another Build team has them

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: API — build endpoint, lowered, member art and sets, release date

**Files:**
- Modify: `backend/app/api/teams.py`, `backend/app/teams/artifacts.py`, `backend/app/teams/view.py`, `backend/app/api/characters.py:52-76`
- Test: `backend/tests/test_api_teams.py`, `backend/tests/test_teams_goals.py`, `backend/tests/test_api_characters.py`, `backend/tests/test_api_settings.py:139-143`

**Interfaces:**
- Consumes: `store.set_build`, `store.delete_team -> list[int]`, `save_team -> (team, raised, lowered)` (Task 2).
- Produces (JSON):
  - `PUT /api/teams/{id}/build` body `{on: bool}` → `{team, raised: int[], lowered: int[]}`
  - `POST/PUT /api/teams[/{id}]` → `{team, raised, lowered}`
  - `DELETE /api/teams/{id}` → `{ok: true, lowered: int[]}`
  - member keys added: `constellation: int|null`, `splash: str|null`, `artifact_sets: [{name: str, icon: str|null, pieces: 4|2}]`
  - character key added: `release_at: "YYYY-MM-DD" | null`
  - `artifacts.artifact_sets(set_names: list[str], icons: dict[str, str]) -> list[dict]`

- [ ] **Step 1: Failing unit test for `artifact_sets`** — append to `backend/tests/test_teams_goals.py`:

```python
from app.teams.artifacts import artifact_sets

ICONS = {"A": "UI_RelicIcon_1_4", "B": "UI_RelicIcon_2_4"}


def test_artifact_sets_match_set_line():
    cases = {
        ("A", "A", "A", "A", "B"): [("A", 4)],
        ("A", "A", "B", "B"): [("A", 2), ("B", 2)],
        ("B", "B", "B", "A", "A"): [("B", 2), ("A", 2)],
        ("A", "A", "B", "B", "C"): [("A", 2), ("B", 2)],
        ("A", "B", "C", "D", "E"): [],
        (): [],
    }
    for names, expected in cases.items():
        got = artifact_sets(list(names), ICONS)
        assert [(x["name"], x["pieces"]) for x in got] == expected
        assert " + ".join(f"{x['pieces']}pc {x['name']}" for x in got) == set_line(list(names))


def test_artifact_sets_unknown_icon():
    assert artifact_sets(["Z"] * 4, ICONS) == [{"name": "Z", "icon": None, "pieces": 4}]
```

- [ ] **Step 2: Run — expect FAIL** (ImportError)

- [ ] **Step 3: Implement** — append to `backend/app/teams/artifacts.py`:

```python
def artifact_sets(set_names: list[str], icons: dict[str, str]) -> list[dict]:
    """Same thresholds as set_line, as data: [{name, icon, pieces}] with pieces 4 or 2."""
    counts = Counter(n for n in set_names if n)
    four = sorted(n for n, c in counts.items() if c >= 4)
    if four:
        return [{"name": four[0], "icon": icons.get(four[0]), "pieces": 4}]
    twos = sorted((n for n, c in counts.items() if c >= 2), key=lambda n: (-counts[n], n))
    return [{"name": n, "icon": icons.get(n), "pieces": 2} for n in twos]
```

- [ ] **Step 4: Run — expect PASS**

- [ ] **Step 5: Failing API tests** — append to `backend/tests/test_api_teams.py` (add `GameArtifactSet` to the `app.db.models` import):

```python
def test_member_payload_has_art_constellation_and_sets(paths):
    sf = setup(paths)
    drop_default_tags(sf)
    with sf.begin() as s:
        s.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id == BEN))
        s.merge(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=0))
        for slot in range(1, 5):
            s.add(OwnedArtifact(character_id=BEN, slot=slot, set_name="Noblesse Oblige", rarity=5, level=20,
                                main_stat="HP", substats=[], icon=""))
    with make_client(paths) as client:
        team = client.post("/api/teams", json=body(members=(BEN, XL))).json()["team"]
    ben, xl = team["members"]
    assert ben["artifact_sets"] == [{"name": "Noblesse Oblige", "icon": "UI_RelicIcon_15007_4", "pieces": 4}]
    assert ben["splash"].startswith("UI_Gacha_AvatarImg_") and isinstance(ben["constellation"], int)
    assert xl["artifact_sets"] == [] and xl["constellation"] is None


def test_build_endpoint_on_off_and_lowered_in_responses(paths):
    sf = setup(paths)
    with make_client(paths) as client:
        sync = client.app.state.ctx.sync
        tid = client.post("/api/teams", json=body(members=(BEN, NAH))).json()["team"]["id"]
        on = client.put(f"/api/teams/{tid}/build", json={"on": True}).json()
        assert on["raised"] == [NAH] and on["lowered"] == [] and on["team"]["has_build_tag"] is True
        assert sync.gaps_pending
        off = client.put(f"/api/teams/{tid}/build", json={"on": False}).json()
        assert off["raised"] == [] and set(off["lowered"]) == {BEN, NAH}
        chars = {c["id"]: c for c in client.get("/api/characters").json()}
        assert chars[NAH]["goal"] == "none" and chars[BEN]["goal"] == "none"
        client.put(f"/api/teams/{tid}/build", json={"on": True})
        r = client.put(f"/api/teams/{tid}", json=body(members=(BEN,), tags=(1,))).json()
        assert r["lowered"] == [NAH] and r["raised"] == []
        d = client.delete(f"/api/teams/{tid}").json()
        assert d == {"ok": True, "lowered": [BEN]}


def test_build_endpoint_noop(paths):
    setup(paths)
    with make_client(paths) as client:
        tid = client.post("/api/teams", json=body(members=(XL,))).json()["team"]["id"]
        r = client.put(f"/api/teams/{tid}/build", json={"on": False}).json()
        assert (r["raised"], r["lowered"]) == ([], [])
        assert client.put("/api/teams/999/build", json={"on": True}).status_code == 404
```

Also in `test_create_list_get_update_delete` change `assert client.delete(...).status_code == 200` to also check `.json() == {"ok": True, "lowered": []}`, and in `created` assert `created["lowered"] == []`.

Append to `backend/tests/test_api_characters.py` (use that file's existing setup/client helpers; this is the shape):

```python
def test_characters_have_release_date(paths):
    setup(paths)                      # the same setup the other tests in this file use
    with make_client(paths) as client:
        chars = client.get("/api/characters").json()
    import re
    assert all(c["release_at"] is None or re.fullmatch(r"\d{4}-\d{2}-\d{2}", c["release_at"]) for c in chars)
    assert any(c["release_at"] for c in chars)
```

In `backend/tests/test_api_settings.py` leak test, add after the team POST: `client.put("/api/teams/1/build", json={"on": False}).text,` (team 1 is the one just created there; if the created id differs, read it from the POST response and use it).

- [ ] **Step 6: Run — expect FAIL**

- [ ] **Step 7: Implement**
  - `backend/app/api/characters.py` `character_payload`: add after `"weapon_type"`:

    ```python
            "release_at": g.release_at.date().isoformat() if g is not None and g.release_at else None,
    ```
  - `backend/app/teams/view.py`:

    ```python
    MEMBER_KEYS = ("id", "name", "slug", "icon", "splash", "element", "rarity", "owned", "goal", "status",
                   "prefarming", "level", "constellation", "talents", "weapon", "progress")
    ```
    In `placeholder` add `"splash": None, "constellation": None`. Change `member_view` to take the artifact pair:

    ```python
    def member_view(char: dict | None, cid: int, role: str, arts: tuple[str, list[dict]], in_build_team: bool,
                    calculated: bool) -> dict:
        base = {k: char[k] for k in MEMBER_KEYS} if char is not None else placeholder(cid)
        is_build = base["goal"] == "build"
        line, sets = arts
        return {**base, "role": role, "artifact_line": line, "artifact_sets": sets,
                "not_building": in_build_team and not is_build,
                "not_calculated": is_build and not calculated}
    ```
    In `team_view` change the `arts` annotation to `dict[int, tuple[str, list[dict]]]` and the lookup to `arts.get(m.character_id, ("", []))`.
  - `backend/app/api/teams.py`:

    ```python
    from app.db.models import GameArtifactSet, OwnedArtifact
    from app.teams.artifacts import artifact_sets, set_line


    class BuildBody(BaseModel):
        on: bool


    def artifact_info(s: Session) -> dict[int, tuple[str, list[dict]]]:
        icons = {a.name: a.icon for a in s.scalars(select(GameArtifactSet))}
        sets: dict[int, list[str]] = {}
        for a in s.scalars(select(OwnedArtifact)):
            sets.setdefault(a.character_id, []).append(a.set_name)
        return {cid: (set_line(names), artifact_sets(names, icons)) for cid, names in sets.items()}
    ```
    In `team_views` use `arts = artifact_info(s)` (delete `artifact_lines`).

    ```python
    def _changed(ctx: AppContext, raised: list[int], lowered: list[int]) -> None:
        if raised or lowered:
            ctx.sync.schedule_gaps()
    ```
    `_save`: unpack `team, raised, lowered`, call `_changed(ctx, raised, lowered)`, return `{"team": _one(s, tid), "raised": raised, "lowered": lowered}`.

    ```python
    @router.put("/teams/{team_id}/build")
    async def set_team_build(team_id: int, body: BuildBody, ctx: AppContext = Depends(get_ctx)) -> dict:
        try:
            with ctx.session_factory.begin() as s:
                raised, lowered = store.set_build(s, team_id, body.on)
        except TeamError as e:
            raise HTTPException(e.status, e.message) from None
        _changed(ctx, raised, lowered)
        with ctx.session_factory() as s:
            return {"team": _one(s, team_id), "raised": raised, "lowered": lowered}


    @router.delete("/teams/{team_id}")
    async def remove_team(team_id: int, ctx: AppContext = Depends(get_ctx)) -> dict:
        try:
            with ctx.session_factory.begin() as s:
                lowered = store.delete_team(s, team_id)
        except TeamError as e:
            raise HTTPException(e.status, e.message) from None
        _changed(ctx, [], lowered)
        return {"ok": True, "lowered": lowered}
    ```
    Register `set_team_build` before `@router.get("/teams/{team_id}")` is fine (different method), but keep `PUT /teams/order` above `PUT /teams/{team_id}` as today. Update the module docstring to `"""Teams and tags. Side effects on other data: raising or lowering Build goals (app.teams.goals)."""`

- [ ] **Step 8: Run the backend suite — expect PASS**

- [ ] **Step 9: Commit**

```bash
git add backend
git commit -m "feat(api): team Build switch endpoint, lowered ids, member splash/constellation/artifact sets, release dates

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Frontend helpers, types and API client

**Files:**
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/teams.ts`, `frontend/src/lib/teams.test.ts`, `frontend/src/lib/status.ts`, `frontend/src/lib/status.test.ts`, `frontend/src/lib/nav.ts`, `frontend/src/lib/nav.test.ts`
- Create: `frontend/src/lib/characterView.ts`, `frontend/src/lib/characterView.test.ts`

**Interfaces:**
- Consumes: Task 3 JSON.
- Produces:
  - types: `Character.release_at: string | null`; `ArtifactSetRef { name: string; icon: string | null; pieces: number }`; `TeamMember` gains `splash: string | null; constellation: number | null; artifact_sets: ArtifactSetRef[]`; `SaveTeamResponse { team; raised: number[]; lowered: number[] }`; `DeleteTeamResponse { ok: boolean; lowered: number[] }`
  - `api.setTeamBuild(id: number, on: boolean): Promise<SaveTeamResponse>`; `api.deleteTeam` → `Promise<DeleteTeamResponse>`
  - `teams.ts`: `TAG_COLORS` (10), `TAG_HEX`, `memberLookup(teams: Team[]): Map<number, GoalRef>`, `charLookup(chars: Character[]): Map<number, GoalRef>`, `willLower(teams, lookup, teamId, draft)`, `loweredMessage(n)`, `changeMessage(prefix, raised, lowered)`, `talentParts(t)`, `slantInset(heightPx, deg?)`, `RIBBON_DEG = 18`
  - `status.ts`: `SortKeys`, `DEFAULT_SORT`, `sortCharacters(chars, keys)`, `groupCharacters(chars, f, keys = DEFAULT_SORT)`
  - `characterView.ts`: `TileSize`, `CharacterView`, `loadCharacterView()`, `saveCharacterView(v)`
  - `nav.ts`: `WIDE_ROUTES`, `isWide(pathname)`

- [ ] **Step 1: Write failing tests**

Append to `frontend/src/lib/teams.test.ts` (reuse its existing `member()`/`team()` builders if present; otherwise these local ones):

```ts
import { changeMessage, loweredMessage, memberLookup, slantInset, talentParts, willLower } from './teams';
import type { Team, TeamMember } from './types';

const m = (id: number, name: string, goal: 'build' | 'want' | 'none' = 'build') =>
	({ id, name, goal }) as unknown as TeamMember;
const t = (id: number, build: boolean, members: TeamMember[]) =>
	({ id, has_build_tag: build, members }) as unknown as Team;

describe('willLower', () => {
	const teams = [t(1, true, [m(10, 'Ben'), m(11, 'Fur'), m(12, 'Xq', 'want')]), t(2, true, [m(11, 'Fur')]), t(3, false, [m(10, 'Ben')])];
	const look = memberLookup(teams);
	it('switch off: every Build member not in another Build team', () => {
		expect(willLower(teams, look, 1, { memberIds: [10, 11, 12], hasBuild: false })).toEqual(['Ben']);
	});
	it('remove a member from a Build team', () => {
		expect(willLower(teams, look, 1, { memberIds: [11, 12], hasBuild: true })).toEqual(['Ben']);
	});
	it('delete', () => {
		expect(willLower(teams, look, 1, null)).toEqual(['Ben']);
	});
	it('team without Build or new team lowers nothing', () => {
		expect(willLower(teams, look, 3, null)).toEqual([]);
		expect(willLower(teams, look, null, { memberIds: [10], hasBuild: false })).toEqual([]);
	});
});

describe('messages and geometry', () => {
	it('builds change messages', () => {
		expect(loweredMessage(1)).toBe('Moved 1 character off Build');
		expect(changeMessage('Saved', [1], [2, 3])).toBe('Saved · Raised 1 character to Build · Moved 2 characters off Build');
		expect(changeMessage('Saved', [], [])).toBe('Saved');
	});
	it('marks crowned talents', () => {
		expect(talentParts({ normal: 10, skill: 9, burst: 10 })).toEqual([
			{ value: 10, crowned: true }, { value: 9, crowned: false }, { value: 10, crowned: true }]);
		expect(talentParts(null)).toEqual([]);
	});
	it('computes the slant inset', () => {
		expect(slantInset(100)).toBe(33);   // ceil(100 * tan 18°) = ceil(32.49)
		expect(slantInset(330)).toBe(108);
		expect(slantInset(100, 0)).toBe(0);
	});
});
```

Replace the `groupCharacters` sort test in `frontend/src/lib/status.test.ts` (`'sorts building by progress ascending…'`) with:

```ts
	it('sorts every section with the same keys (default: rarity then name)', () => {
		const g = groupCharacters(list, emptyFilters());
		for (const section of Object.values(g)) {
			expect(section).toEqual(sortCharacters(section, DEFAULT_SORT));
		}
	});
```

and add (import `sortCharacters, DEFAULT_SORT` from `./status`):

```ts
describe('sortCharacters', () => {
	const c = (name: string, rarity: number, level: number | null, release_at: string | null, owned = level !== null) =>
		({ name, rarity, level, release_at, owned }) as unknown as Character;
	const list = [c('Bennett', 4, 90, '2020-09-28'), c('Albedo', 5, 20, '2020-12-23'), c('Nahida', 5, 90, '2022-11-02'),
		c('Yelan', 5, null, '2022-05-31'), c('Mystery', 4, null, null)];
	const names = (k: { az: boolean; rarity: boolean; level: boolean }) => sortCharacters(list, k).map((x) => x.name);
	it('A–Z only', () => expect(names({ az: true, rarity: false, level: false })).toEqual(['Albedo', 'Bennett', 'Mystery', 'Nahida', 'Yelan']));
	it('rarity then A–Z', () => expect(names({ az: true, rarity: true, level: false })).toEqual(['Albedo', 'Nahida', 'Yelan', 'Bennett', 'Mystery']));
	it('rarity, level, A–Z; unowned count as 0', () =>
		expect(names({ az: true, rarity: true, level: true })).toEqual(['Nahida', 'Albedo', 'Yelan', 'Bennett', 'Mystery']));
	it('A–Z off: newest first, unknown release last', () =>
		expect(names({ az: false, rarity: false, level: false })).toEqual(['Nahida', 'Yelan', 'Albedo', 'Bennett', 'Mystery']));
	it('does not mutate its input', () => {
		const before = list.map((x) => x.name);
		sortCharacters(list, { az: true, rarity: true, level: true });
		expect(list.map((x) => x.name)).toEqual(before);
	});
});
```

Create `frontend/src/lib/characterView.test.ts`:

```ts
import { afterEach, describe, expect, it, vi } from 'vitest';
import { loadCharacterView, saveCharacterView } from './characterView';

describe('character view preference', () => {
	afterEach(() => { vi.unstubAllGlobals(); localStorage.clear(); });
	it('defaults', () => {
		expect(loadCharacterView()).toEqual({ size: 'small', sort: { az: true, rarity: true, level: false } });
	});
	it('round-trips', () => {
		saveCharacterView({ size: 'large', sort: { az: false, rarity: false, level: true } });
		expect(loadCharacterView()).toEqual({ size: 'large', sort: { az: false, rarity: false, level: true } });
	});
	it('ignores corrupt data and blocked storage', () => {
		localStorage.setItem('aa.characterView', '{"size":"huge","sort":7}');
		expect(loadCharacterView().size).toBe('small');
		vi.stubGlobal('localStorage', { getItem: () => { throw new Error('blocked'); }, setItem: () => { throw new Error('blocked'); } });
		expect(loadCharacterView().size).toBe('small');
		expect(() => saveCharacterView({ size: 'large', sort: { az: true, rarity: true, level: false } })).not.toThrow();
	});
});
```

(If Vitest runs without a DOM, check `frontend/vite.config.ts`: existing tests already use `localStorage` in `teams.test.ts`/`collapse.test.ts`; follow whatever they do.)

Append to `frontend/src/lib/nav.test.ts`:

```ts
import { isWide } from './nav';
describe('isWide', () => {
	it('covers Characters and Teams but not character detail', () => {
		expect(isWide('/characters')).toBe(true);
		expect(isWide('/teams')).toBe(true);
		expect(isWide('/characters/bennett')).toBe(false);
		expect(isWide('/inventory')).toBe(false);
	});
});
```

- [ ] **Step 2: Run — expect FAIL** — `npx vitest run` (from `frontend/`)

- [ ] **Step 3: Implement**

`frontend/src/lib/types.ts`: add `release_at: string | null;` to `Character` (after `weapon_type`); add

```ts
export interface ArtifactSetRef { name: string; icon: string | null; pieces: number }
```

extend `TeamMember` with `splash: string | null; constellation: number | null; artifact_sets: ArtifactSetRef[];`; change `SaveTeamResponse` to `{ team: Team; raised: number[]; lowered: number[] }`; add `export interface DeleteTeamResponse { ok: boolean; lowered: number[] }`.

`frontend/src/lib/api.ts` (add `DeleteTeamResponse` to the type import):

```ts
	deleteTeam: (id: number) => request<DeleteTeamResponse>('DELETE', `/teams/${id}`),
	setTeamBuild: (id: number, on: boolean) => request<SaveTeamResponse>('PUT', `/teams/${id}/build`, { on }),
```

`frontend/src/lib/teams.ts`:

```ts
export const TAG_COLORS = ['orange', 'red', 'yellow', 'green', 'teal', 'blue', 'purple', 'pink', 'navy', 'gold'] as const;
export const TAG_HEX: Record<string, string> = {
	orange: '#d9822b', red: '#d64545', yellow: '#c9a227', green: '#3f9c5a',
	teal: '#2f9c95', blue: '#3d7bd9', purple: '#8a5cd6', pink: '#d65c9c', navy: '#2a3f8f', gold: '#a9842c'
};
export const RIBBON_DEG = 18;

export interface GoalRef { name: string; goal: Goal }

export function memberLookup(teams: Team[]): Map<number, GoalRef> {
	const out = new Map<number, GoalRef>();
	for (const t of teams) for (const m of t.members) out.set(m.id, { name: m.name, goal: m.goal });
	return out;
}

export function charLookup(chars: Character[]): Map<number, GoalRef> {
	return new Map(chars.map((c) => [c.id, { name: c.name, goal: c.goal }]));
}

/** Names of members a change would move off Build (mirrors app.teams.store / goals.lower_from_build).
 *  draft = null means the team is deleted. */
export function willLower(
	teams: Team[], lookup: Map<number, GoalRef>, teamId: number | null,
	draft: { memberIds: number[]; hasBuild: boolean } | null
): string[] {
	const team = teams.find((t) => t.id === teamId);
	if (!team || !team.has_build_tag) return [];
	const old = team.members.map((x) => x.id);
	const candidates = draft === null || !draft.hasBuild
		? [...new Set([...(draft?.memberIds ?? []), ...old])]
		: old.filter((id) => !draft.memberIds.includes(id));
	const covered = new Set(teams.filter((t) => t.id !== teamId && t.has_build_tag).flatMap((t) => t.members.map((x) => x.id)));
	return candidates
		.filter((id) => lookup.get(id)?.goal === 'build' && !covered.has(id))
		.map((id) => lookup.get(id)!.name);
}

export function loweredMessage(n: number): string {
	return `Moved ${n} ${n === 1 ? 'character' : 'characters'} off Build`;
}

export function changeMessage(prefix: string, raised: number[], lowered: number[]): string {
	return [prefix, raised.length ? raisedMessage(raised.length) : null, lowered.length ? loweredMessage(lowered.length) : null]
		.filter(Boolean).join(' · ');
}

export function talentParts(t: Talents | null): { value: number; crowned: boolean }[] {
	return t ? [t.normal, t.skill, t.burst].map((value) => ({ value, crowned: value >= 10 })) : [];
}

/** Horizontal offset of a slanted edge over `heightPx` (keeps text clear of the ribbon edge). */
export function slantInset(heightPx: number, deg: number = RIBBON_DEG): number {
	return Math.ceil(heightPx * Math.tan((deg * Math.PI) / 180));
}
```

(Add `Goal, Talents` to the `./types` import.) Keep `willRaise`, `memberLine` and `weaponLine`; delete nothing else yet.

`frontend/src/lib/status.ts`:

```ts
export interface SortKeys { az: boolean; rarity: boolean; level: boolean }
export const DEFAULT_SORT: SortKeys = { az: true, rarity: true, level: false };

const levelOf = (c: Character) => (c.owned ? c.level ?? 0 : 0);

export function sortCharacters(chars: Character[], k: SortKeys): Character[] {
	return [...chars].sort((a, b) =>
		(k.rarity ? b.rarity - a.rarity : 0) ||
		(k.level ? levelOf(b) - levelOf(a) : 0) ||
		(k.az ? a.name.localeCompare(b.name)
			: (b.release_at ?? '').localeCompare(a.release_at ?? '') || a.name.localeCompare(b.name)));
}

export function groupCharacters(chars: Character[], f: Filters, keys: SortKeys = DEFAULT_SORT): Record<Status, Character[]> {
	const groups: Record<Status, Character[]> = { building: [], obtained: [], wanted: [], unobtained: [] };
	for (const c of chars) if (matches(c, f)) groups[c.status].push(c);
	for (const s of Object.keys(groups) as Status[]) groups[s] = sortCharacters(groups[s], keys);
	return groups;
}
```

Remove the now-unused `elementRank` helper.

Create `frontend/src/lib/characterView.ts`:

```ts
import { DEFAULT_SORT, type SortKeys } from './status';

export type TileSize = 'small' | 'large';
export interface CharacterView { size: TileSize; sort: SortKeys }
const KEY = 'aa.characterView';

export function loadCharacterView(): CharacterView {
	const fallback: CharacterView = { size: 'small', sort: { ...DEFAULT_SORT } };
	try {
		const raw = localStorage.getItem(KEY);
		if (!raw) return fallback;
		const v = JSON.parse(raw);
		const size: TileSize = v?.size === 'large' ? 'large' : 'small';
		const s = v?.sort;
		const sort = s && typeof s === 'object'
			? { az: s.az !== false, rarity: s.rarity !== false, level: s.level === true }
			: { ...DEFAULT_SORT };
		return { size, sort };
	} catch {
		return fallback;
	}
}

export function saveCharacterView(v: CharacterView): void {
	try {
		localStorage.setItem(KEY, JSON.stringify(v));
	} catch {
		/* storage blocked: keep the in-memory choice */
	}
}
```

`frontend/src/lib/nav.ts` (below `isFluid`):

```ts
/** Pages that use the full content width (no 1600px cap) but scroll normally. */
export const WIDE_ROUTES = ['/characters', '/teams'];

export function isWide(pathname: string): boolean {
	return WIDE_ROUTES.some((r) => pathname === r);
}
```

- [ ] **Step 4: Run — expect PASS** — `npx vitest run`, then `npm run check` (fix any type errors the new `Character.release_at` field causes in test builders by adding `release_at: null`).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib
git commit -m "feat(frontend): sort, lower-preview, talent and slant helpers; team Build API; view preference

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Characters page — tiles, filter bar, full width

**Files:**
- Create: `frontend/src/lib/CharacterTile.svelte`, `frontend/src/lib/CharacterFilterBar.svelte`
- Modify: `frontend/src/routes/characters/+page.svelte`, `frontend/src/routes/+layout.svelte`
- Delete: `frontend/src/lib/CharacterCard.svelte` (after `grep -rn CharacterCard frontend/src` shows no other user)
- Test: `frontend/e2e/characters.spec.ts`

**Interfaces:**
- Consumes: `sortCharacters`, `groupCharacters(chars, f, keys)`, `loadCharacterView`/`saveCharacterView`, `talentParts`, `isWide`, `elementStyle`, `RARITY_STYLE`, `imgSrc`, `GoalSwitch`, `FilterPill`.
- Produces:
  - `<CharacterTile character size="small|large" onGoal? onpick? picked? disabled? />` — root `data-testid="card-{slug}"` (or `pick-{slug}` when `onpick` is set), classes `tile small|large`, `unowned` when not owned.
  - `<CharacterFilterBar bind:filters bind:sort bind:size? />` — `size` omitted hides the Small/Large switch. Buttons: sort pills labelled `A–Z`, `Rarity`, `Level`; size buttons labelled `Small`, `Large` with `aria-pressed`.

- [ ] **Step 1: Write the failing e2e** — append to `frontend/e2e/characters.spec.ts`:

```ts
test('large tiles persist across a reload and switch back', async ({ page }) => {
	await page.goto('/characters');
	await page.getByRole('button', { name: 'Large', exact: true }).click();
	await expect(page.getByTestId('card-xiangling')).toHaveClass(/large/);
	await page.reload();
	await expect(page.getByTestId('card-xiangling')).toHaveClass(/large/);
	await page.getByRole('button', { name: 'Small', exact: true }).click();
	await expect(page.getByTestId('card-xiangling')).toHaveClass(/small/);
});

test('sort toggles reorder sections; unowned tiles are grey', async ({ page }) => {
	await page.goto('/characters');
	const rarity = page.getByRole('button', { name: 'Rarity', exact: true });
	await expect(rarity).toHaveAttribute('aria-pressed', 'true');
	await rarity.click();
	const ids = await page.getByTestId('section-obtained').locator('[data-testid^="card-"]')
		.evaluateAll((els) => els.map((e) => (e.textContent ?? '').trim()));
	expect(ids).toEqual([...ids].sort((a, b) => a.localeCompare(b)));
	await rarity.click();                                   // restore the default
	await expect(rarity).toHaveAttribute('aria-pressed', 'true');

	const section = page.getByTestId('section-unobtained');
	await section.getByRole('button', { name: /Unobtained/ }).click();
	await expect(section.getByTestId('card-xingqiu')).toHaveClass(/unowned/);
	await section.getByRole('button', { name: /Unobtained/ }).click();
});
```

(Text content starts with the character name in both tile sizes, so sorting the text sorts by name.)

- [ ] **Step 2: Run — expect FAIL** — `PYTHON=... npx playwright test e2e/characters.spec.ts`

- [ ] **Step 3: Add the wide-page class** — `frontend/src/routes/+layout.svelte`: import `isWide` next to `isFluid`, add `const wide = $derived(isWide(page.url.pathname));`, change `<main class:fluid>` to `<main class:fluid class:wide>`, and add the style `main.wide { max-width: none; }`.

- [ ] **Step 4: Create `frontend/src/lib/CharacterTile.svelte`**

```svelte
<script lang="ts">
	import { elementStyle } from './elements';
	import GoalSwitch from './GoalSwitch.svelte';
	import { imgSrc } from './img';
	import { progressTooltip } from './status';
	import { talentParts } from './teams';
	import type { Character, Goal } from './types';

	let { character: c, size = 'small', onGoal, onpick, picked = false, disabled = false }: {
		character: Character; size?: 'small' | 'large'; onGoal?: (g: Goal) => void;
		onpick?: () => void; picked?: boolean; disabled?: boolean;
	} = $props();

	const src = $derived(imgSrc(c.icon));
	const el = $derived(elementStyle(c.element));
	const pct = $derived(Math.round((c.progress ?? 0) * 100));
	const owned = $derived(c.owned);
	const stars = $derived('★'.repeat(Math.max(0, c.rarity)));
	const line = $derived(owned ? `Lv ${c.level} · C${c.constellation ?? 0}` : c.goal === 'none' ? 'Not owned' : 'Not owned · Wanted');
</script>

{#snippet face()}
	<div class="pic r{c.rarity}">
		{#if src}<img class="art" {src} alt="" loading="lazy" />{:else}<div class="ph">?</div>{/if}
		{#if el.icon && size === 'small'}<img class="el" src={imgSrc(el.icon)} alt="" />{/if}
	</div>
{/snippet}

{#snippet bar()}
	<div class="bar" role="progressbar" aria-valuemin={0} aria-valuemax={100} aria-valuenow={pct} title={progressTooltip(c)}>
		<i style="width: {pct}%"></i>
	</div>
{/snippet}

{#snippet body()}
	{#if size === 'small'}
		<div class="name">{c.name}</div>
		{#if c.status === 'building'}{@render bar()}{:else}<div class="sub">{line}</div>{/if}
	{:else}
		<div class="info">
			<div class="name">{#if el.icon}<img class="el-inline" src={imgSrc(el.icon)} alt="" />{/if}{c.name}</div>
			<div class="stars">{stars}</div>
			<div>{line}</div>
			{#if owned && c.talents}
				<div>Talents {#each talentParts(c.talents) as p, i (i)}{#if i}/{/if}<span class:crown={p.crowned}>{p.value}</span>{/each}</div>
			{/if}
			{#if owned && c.weapon}
				<div class="weapon">{#if imgSrc(c.weapon.icon)}<img src={imgSrc(c.weapon.icon)} alt="" />{/if}Lv {c.weapon.level} R{c.weapon.refinement}</div>
			{/if}
			{#if c.status === 'building'}{@render bar()}{/if}
		</div>
	{/if}
{/snippet}

{#if onpick}
	<button type="button" class="tile {size}" class:unowned={!owned} class:picked data-testid="pick-{c.slug}"
		{disabled} onclick={onpick} aria-label="Add {c.name}">
		{@render face()}{@render body()}
	</button>
{:else}
	<div class="tile {size} st-{c.status}" class:unowned={!owned} data-testid="card-{c.slug}">
		<a href="/characters/{c.slug}" class="link" aria-label={c.name}>{@render face()}{@render body()}</a>
		{#if onGoal}<div class="switch"><GoalSwitch goal={c.goal} onchange={onGoal} compact /></div>{/if}
	</div>
{/if}

<style>
	.tile { position: relative; border-radius: 10px; overflow: hidden; background: var(--glass-bg-strong, rgba(18, 22, 38, 0.7));
		color: var(--text); padding: 0; border: none; text-align: center; }
	.link { display: block; color: inherit; text-decoration: none; }
	.small { width: 104px; }
	.small .pic, .small .art, .small .ph { width: 104px; height: 104px; }
	.large { width: 330px; height: 150px; }
	.large .link, button.large { display: flex; height: 100%; text-align: left; }
	.large .pic, .large .art, .large .ph { width: 150px; height: 150px; flex: none; }
	.pic { position: relative; background: var(--r0); }
	.pic.r5 { background: var(--r5); } .pic.r4 { background: var(--r4); }
	.art { display: block; }
	.ph { display: grid; place-items: center; font-size: 32px; color: var(--muted); }
	.el { position: absolute; left: 4px; top: 4px; width: 18px; height: 18px; }
	.name { font-size: 12px; padding: 4px 4px 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.sub { font-size: 11px; color: var(--muted); min-height: 20px; padding-bottom: 4px; }
	.info { padding: 10px; display: flex; flex-direction: column; gap: 3px; font-size: 12px; min-width: 0; }
	.info .name { font-size: 14px; font-weight: 700; padding: 0; display: flex; gap: 5px; align-items: center; }
	.el-inline { width: 16px; height: 16px; }
	.stars { color: var(--rarity-5); font-size: 11px; }
	.crown { color: var(--gold); font-weight: 700; }
	.weapon { display: flex; gap: 6px; align-items: center; }
	.weapon img { width: 24px; height: 24px; }
	.bar { height: 5px; margin: 6px 8px 9px; background: #444; border-radius: 3px; }
	.info .bar { margin: 4px 0 0; }
	.bar i { display: block; height: 100%; background: var(--building); border-radius: 3px; }
	.st-building { outline: 2px solid var(--building); outline-offset: -2px; }
	.unowned .pic { background: #2a2d38; }
	.unowned .art, .unowned .el, .unowned .el-inline { filter: grayscale(1); opacity: 0.5; }
	.switch { position: absolute; top: 4px; left: 0; right: 0; display: flex; justify-content: center; opacity: 0; transition: opacity 0.12s; }
	.tile:hover .switch, .tile:focus-within .switch { opacity: 1; }
	button.tile { cursor: pointer; }
	button.tile:disabled { opacity: 0.55; cursor: default; }
	.picked { outline: 2px solid var(--gold); outline-offset: -2px; }
</style>
```

- [ ] **Step 5: Create `frontend/src/lib/CharacterFilterBar.svelte`**

```svelte
<script lang="ts">
	import { RARITY_STYLE, elementStyle } from './elements';
	import FilterPill from './FilterPill.svelte';
	import { ELEMENTS, WEAPON_TYPES, type Filters, type SortKeys } from './status';

	let { filters = $bindable(), sort = $bindable(), size = $bindable() }: {
		filters: Filters; sort: SortKeys; size?: 'small' | 'large';
	} = $props();

	function toggle<T>(list: T[], value: T): T[] {
		return list.includes(value) ? list.filter((v) => v !== value) : [...list, value];
	}
	const SORTS: { key: keyof SortKeys; label: string }[] = [
		{ key: 'az', label: 'A–Z' }, { key: 'rarity', label: 'Rarity' }, { key: 'level', label: 'Level' }
	];
</script>

<div class="bar">
	<input placeholder="Search name" bind:value={filters.search} aria-label="Search characters" />
	{#each ELEMENTS as el (el)}
		<FilterPill label={el} on={filters.elements.includes(el)} color={elementStyle(el).color}
			image={elementStyle(el).icon} onclick={() => (filters.elements = toggle(filters.elements, el))} />
	{/each}
	{#each WEAPON_TYPES as w (w)}
		<FilterPill label={w} on={filters.weapons.includes(w)} onclick={() => (filters.weapons = toggle(filters.weapons, w))} />
	{/each}
	{#each [5, 4] as r (r)}
		<FilterPill label="{r}★" on={filters.rarities.includes(r)} color={RARITY_STYLE[r].color} ink={RARITY_STYLE[r].ink}
			onclick={() => (filters.rarities = toggle(filters.rarities, r))} />
	{/each}
	<span class="sep muted">Sort</span>
	{#each SORTS as s (s.key)}
		<FilterPill label={s.label} on={sort[s.key]} color="var(--gold)" onclick={() => (sort = { ...sort, [s.key]: !sort[s.key] })} />
	{/each}
	{#if size !== undefined}
		<span class="sep muted">Tiles</span>
		<FilterPill label="Small" on={size === 'small'} color="var(--gold)" onclick={() => (size = 'small')} />
		<FilterPill label="Large" on={size === 'large'} color="var(--gold)" onclick={() => (size = 'large')} />
	{/if}
</div>

<style>
	.bar { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 12px; }
	input { width: 180px; }
	.sep { margin-left: 10px; font-size: 12px; text-transform: uppercase; letter-spacing: 0.06em; }
</style>
```

- [ ] **Step 6: Rewrite the Characters page** — `frontend/src/routes/characters/+page.svelte`: keep the script's load/setGoal/collapse logic and the team-tag row; replace imports of `CharacterCard`, `FilterPill`, `RARITY_STYLE/elementStyle`, `ELEMENTS/WEAPON_TYPES` with `CharacterTile`, `CharacterFilterBar`, `loadCharacterView`, `saveCharacterView`; then:

```ts
	const view = loadCharacterView();
	let sort = $state(view.sort);
	let size = $state(view.size);
	const groups = $derived(groupCharacters(chars, filters, sort));
	$effect(() => saveCharacterView({ size, sort }));
```

Markup: replace the first `.filters` div with `<CharacterFilterBar bind:filters bind:sort bind:size />`, and the grid body with

```svelte
{#each groups[section.status] as c (c.id)}
	<CharacterTile character={c} {size} onGoal={(g) => setGoal(c, g)} />
{:else}
	<p class="muted">None.</p>
{/each}
```

Remove the now-unused `toggle` helper only if the team-tag row no longer uses it (it does; keep it). Change `.grid` gap to `10px` (unchanged) — large tiles wrap naturally.

- [ ] **Step 7: Delete `CharacterCard.svelte`** once `grep -rn "CharacterCard" frontend/src` returns only the file itself.

- [ ] **Step 8: Run** — `npm run check` (0 errors), `npx vitest run`, then `PYTHON=... npx playwright test e2e/characters.spec.ts` — expect PASS (existing tests use `card-<slug>` and the Build switch inside the tile; both are kept).

- [ ] **Step 9: Commit**

```bash
git add frontend/src frontend/e2e/characters.spec.ts
git commit -m "feat(characters): small/large tiles, stacked sort toggles, greyed unowned, full width

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Teams page — ribbons, info section, Build switch, drawer, hover arrows

**Files:**
- Create: `frontend/src/lib/TeamRibbon.svelte`, `frontend/src/lib/TeamInfo.svelte`, `frontend/src/lib/TeamShortfall.svelte`, `frontend/src/lib/TeamRow.svelte`
- Modify: `frontend/src/routes/teams/+page.svelte`
- Delete: `frontend/src/lib/TeamCard.svelte`

**Interfaces:**
- Consumes: `slantInset`, `RIBBON_DEG`, `talentParts`, `willLower`, `memberLookup`, `changeMessage`, `api.setTeamBuild`, `farmRows`, `teamTileView`, `gapLabel`, `gapsSettled`, `MaterialTile`, `TagChip`, `elementStyle`, `imgSrc`.
- Produces (test hooks used by Task 7's e2e):
  - row: `<article data-testid="team-{id}" id="team-{id}">`
  - ribbon: `data-testid="ribbon-{slug}"` (`ribbon-{id}` for placeholders), class `unowned` when not owned
  - switch: `<button role="switch" aria-checked aria-label="Build" data-testid="build-switch-{id}">`
  - drawer toggle: `data-testid="shortfall-toggle-{id}"`; drawer: `data-testid="team-shortfall-{id}"`
  - arrows: `aria-label="Move {name} up|down"`
  - `TeamRow` props: `{ team, gaps, connected, now, reorderable, first, last, onMove(delta), onOpen(), onBuild(on), onBuildAgain(m) }`

- [ ] **Step 1: Create `frontend/src/lib/TeamShortfall.svelte`** — the shortfall section moved out of `TeamCard.svelte` unchanged in behaviour:

```svelte
<script lang="ts">
	import { gapLabel, gapsSettled } from './materials';
	import MaterialTile from './MaterialTile.svelte';
	import { farmRows, teamTileView } from './teams';
	import type { GapStatus, Team } from './types';

	let { team, gaps, connected, now }: { team: Team; gaps: GapStatus; connected: boolean; now: number } = $props();
	const rows = $derived(farmRows(team.shortfall ?? []));
	const anyNotCalculated = $derived(team.members.some((m) => m.not_calculated));
</script>

<section class="shortfall" data-testid="team-shortfall-{team.id}">
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

<style>
	.shortfall { padding: 10px 16px 14px; border-top: 1px solid var(--glass-border); }
	.tiles { display: flex; flex-wrap: wrap; gap: 8px; }
	.ok { color: var(--accent); }
</style>
```

- [ ] **Step 2: Create `frontend/src/lib/TeamRibbon.svelte`**

```svelte
<script lang="ts">
	import { elementStyle } from './elements';
	import { imgSrc } from './img';
	import { RIBBON_DEG, slantInset, talentParts } from './teams';
	import type { TeamMember } from './types';

	let { member: m, onBuildAgain }: { member: TeamMember | null; onBuildAgain: (m: TeamMember) => void } = $props();

	const INFO_H = 150;                                   // fixed info block height (px) so the inset is known
	const inset = slantInset(INFO_H) + 10;
	const el = $derived(elementStyle(m?.element));
	const splash = $derived(m ? imgSrc(m.splash) : null);
</script>

<div class="rib" class:unowned={m && !m.owned} class:empty={!m} style="--sk: -{RIBBON_DEG}deg; --el: {el.color}; --inset: {inset}px; --info-h: {INFO_H}px"
	data-testid={m ? `ribbon-${m.slug ?? m.id}` : undefined}>
	{#if m}
		<div class="bg"></div>
		{#if splash}<div class="art" style="background-image: url({splash})"></div>{/if}
		<div class="info">
			<div class="nm">{#if el.icon}<img src={imgSrc(el.icon)} alt="" />{/if}<span>{m.name}</span>
				{#if m.owned && m.constellation !== null}<span class="muted">C{m.constellation}</span>{/if}</div>
			{#if m.owned}
				<div class="line">Lv {m.level}{#if m.talents} · {#each talentParts(m.talents) as p, i (i)}{#if i}/{/if}<span class:crown={p.crowned}>{p.value}</span>{/each}{/if}</div>
				{#if m.weapon}<div class="line">{#if imgSrc(m.weapon.icon)}<img class="wp" src={imgSrc(m.weapon.icon)} alt="" />{/if}Lv {m.weapon.level} R{m.weapon.refinement}</div>{/if}
				{#if m.artifact_sets.length}
					<div class="line" title={m.artifact_line}>
						{#each m.artifact_sets as a (a.name)}
							<span class="set" title="{a.pieces}pc {a.name}">{#if a.icon}<img src={imgSrc(a.icon)} alt="" />{:else}<span class="noicon">?</span>{/if}<b>{a.pieces}</b></span>
						{/each}
					</div>
				{/if}
			{:else}
				<div class="line"><span class="badge">Not owned</span></div>
			{/if}
			{#if m.role}<div class="role">{m.role}</div>{/if}
			{#if m.not_building}
				<div class="warn">Not building {#if m.slug !== null}<button type="button" onclick={(e) => { e.stopPropagation(); onBuildAgain(m); }}>Build again</button>{/if}</div>
			{/if}
			{#if m.not_calculated}<div class="muted small">Not calculated</div>{/if}
		</div>
	{:else}
		<div class="plus" aria-hidden="true">+</div>
	{/if}
</div>

<style>
	.rib { position: relative; overflow: hidden; transform: skewX(var(--sk)); height: 100%;
		border-left: 1px solid rgba(255, 255, 255, 0.15); border-right: 1px solid rgba(255, 255, 255, 0.15); }
	.bg { position: absolute; inset: 0; background: linear-gradient(180deg, color-mix(in srgb, var(--el) 55%, #0b0e1a) 0%, #0b0e1a 85%); }
	.art { position: absolute; top: 0; bottom: 0; left: -45%; right: -45%; transform: skewX(calc(var(--sk) * -1));
		background-repeat: no-repeat; background-size: auto 125%; background-position: center 20%; }
	.unowned .art { filter: grayscale(1) brightness(0.55); }
	.unowned .bg { background: linear-gradient(180deg, #2a2d38, #0b0e1a 85%); }
	.unowned .nm img { filter: grayscale(1); }
	.info { position: absolute; left: 0; right: 0; bottom: 0; height: var(--info-h); box-sizing: border-box; overflow: hidden;
		padding: 28px 10px 10px var(--inset); transform: skewX(calc(var(--sk) * -1)); transform-origin: bottom left;
		background: linear-gradient(180deg, transparent, rgba(6, 8, 16, 0.92) 30%); font-size: 12px; text-align: left; }
	.nm { font-weight: 700; font-size: 14px; display: flex; gap: 5px; align-items: center; white-space: nowrap; }
	.nm span:first-of-type { overflow: hidden; text-overflow: ellipsis; }
	.nm img { width: 16px; height: 16px; }
	.line { display: flex; gap: 6px; align-items: center; margin-top: 3px; white-space: nowrap; }
	.crown { color: var(--gold); font-weight: 700; }
	.wp { width: 24px; height: 24px; }
	.set { position: relative; width: 24px; height: 24px; }
	.set img, .noicon { width: 24px; height: 24px; display: grid; place-items: center; }
	.set b { position: absolute; right: -3px; bottom: -3px; font-size: 9px; background: #10131f; border-radius: 6px; padding: 0 3px; }
	.role { font-style: italic; color: var(--cream-dim, #b9ad95); margin-top: 3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
	.badge { font-size: 10px; padding: 1px 6px; border-radius: 8px; background: #3a3f50; color: #cfd3df; }
	.warn { color: var(--warn); margin-top: 3px; }
	.small { font-size: 11px; }
	.empty { border: 2px dashed rgba(255, 255, 255, 0.2); }
	.plus { position: absolute; inset: 0; display: grid; place-items: center; font-size: 32px; color: var(--muted); transform: skewX(calc(var(--sk) * -1)); }
</style>
```

Note on the inset: the info block is counter-skewed with `transform-origin: bottom left`, so its bottom-left corner sits on the ribbon's bottom-left corner and the ribbon's left edge moves right by `tan(18°) × y` going up. Padding-left of `slantInset(INFO_H) + 10` keeps every line clear of that edge; the right edge moves away from the text going up, so no right inset is needed beyond `10px`.

- [ ] **Step 3: Create `frontend/src/lib/TeamInfo.svelte`**

```svelte
<script lang="ts">
	import TagChip from './TagChip.svelte';
	import { farmRows } from './teams';
	import type { GapStatus, Team } from './types';

	let { team, gaps, connected, drawerOpen, onBuild, onToggleDrawer }: {
		team: Team; gaps: GapStatus; connected: boolean; drawerOpen: boolean;
		onBuild: (on: boolean) => void; onToggleDrawer: () => void;
	} = $props();

	const short = $derived(farmRows(team.shortfall ?? []).length);
	const pct = $derived(team.progress === null ? null : Math.round(team.progress * 100));
	const summary = $derived.by(() => {
		if (team.shortfall === null) return null;
		if (!connected) return 'Connect HoYoLAB to calculate';
		if (!gaps.computed_at) return 'Shortfall appears after the next sync';
		if (gaps.stale || gaps.pending) return 'Updating…';
		if (short > 0) return `${short} ${short === 1 ? 'material' : 'materials'} short`;
		return team.members.some((m) => m.not_calculated) ? 'Not calculated yet' : 'Ready ✓';
	});
</script>

<div class="info">
	<h2>{team.name}</h2>
	<label class="sw-row">
		<button type="button" role="switch" aria-checked={team.has_build_tag} aria-label="Build" class="sw" class:on={team.has_build_tag}
			data-testid="build-switch-{team.id}" onclick={(e) => { e.stopPropagation(); onBuild(!team.has_build_tag); }}></button>
		Build
	</label>
	<div class="tags">{#each team.tags.filter((t) => !t.builtin) as t (t.id)}<TagChip tag={t} />{/each}</div>
	{#if team.notes}<p class="notes">{team.notes}</p>{/if}
	{#if summary}
		<button type="button" class="link" data-testid="shortfall-toggle-{team.id}" aria-expanded={drawerOpen}
			onclick={(e) => { e.stopPropagation(); onToggleDrawer(); }}>
			{summary}{#if pct !== null} · {pct}%{/if} {drawerOpen ? '▾' : '▸'}
		</button>
	{/if}
</div>

<style>
	.info { display: flex; flex-direction: column; gap: 8px; min-width: 0; }
	h2 { margin: 0; font-size: 18px; color: var(--cream); overflow-wrap: anywhere; }
	.sw-row { display: flex; gap: 6px; align-items: center; font-size: 12px; }
	.sw { width: 32px; height: 18px; border-radius: 9px; padding: 0; border: 1px solid var(--glass-border); background: #3a3f50; position: relative; cursor: pointer; }
	.sw::after { content: ''; position: absolute; left: 2px; top: 2px; width: 12px; height: 12px; border-radius: 50%; background: var(--cream); transition: left 0.12s; }
	.sw.on { background: var(--gold); }
	.sw.on::after { left: 16px; background: #17130b; }
	.tags { display: flex; flex-wrap: wrap; gap: 4px; }
	.notes { margin: 0; font-size: 12px; color: var(--cream-dim, #b9ad95); white-space: pre-wrap; overflow: hidden;
		display: -webkit-box; -webkit-line-clamp: 3; line-clamp: 3; -webkit-box-orient: vertical; }
	.link { background: none; border: none; color: var(--accent); padding: 0; cursor: pointer; text-align: left; font-size: 12px; }
</style>
```

(The Build tag itself is shown as the switch, so the tag chips skip it.)

- [ ] **Step 4: Create `frontend/src/lib/TeamRow.svelte`**

```svelte
<script lang="ts">
	import TeamInfo from './TeamInfo.svelte';
	import TeamRibbon from './TeamRibbon.svelte';
	import TeamShortfall from './TeamShortfall.svelte';
	import { MAX_MEMBERS, slantInset } from './teams';
	import type { GapStatus, Team, TeamMember } from './types';

	let { team, gaps, connected, now, reorderable, first, last, onMove, onOpen, onBuild, onBuildAgain }: {
		team: Team; gaps: GapStatus; connected: boolean; now: number; reorderable: boolean; first: boolean; last: boolean;
		onMove: (delta: -1 | 1) => void; onOpen: () => void; onBuild: (on: boolean) => void; onBuildAgain: (m: TeamMember) => void;
	} = $props();

	const ROW_H = 330;
	let drawerOpen = $state(false);
	const slots = $derived(Array.from({ length: MAX_MEMBERS }, (_x, i) => team.members[i] ?? null));

	function open(e: MouseEvent) {
		if ((e.target as HTMLElement).closest('button, a, input')) return;
		onOpen();
	}
</script>

<article class="team" id="team-{team.id}" data-testid="team-{team.id}">
	<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_static_element_interactions -->
	<div class="row" style="--row-h: {ROW_H}px; --side-inset: {slantInset(ROW_H) + 12}px" onclick={open}>
		{#each slots as m, i (m?.id ?? `empty-${i}`)}
			<TeamRibbon member={m} {onBuildAgain} />
		{/each}
		<div class="side">
			<TeamInfo {team} {gaps} {connected} {drawerOpen} {onBuild} onToggleDrawer={() => (drawerOpen = !drawerOpen)} />
			<button type="button" class="edit" onclick={onOpen} aria-label="Edit {team.name}">Edit</button>
		</div>
		<div class="arrows">
			<button type="button" onclick={() => onMove(-1)} disabled={!reorderable || first} aria-label="Move {team.name} up">▲</button>
			<button type="button" onclick={() => onMove(1)} disabled={!reorderable || last} aria-label="Move {team.name} down">▼</button>
		</div>
	</div>
	{#if drawerOpen && team.shortfall !== null}<TeamShortfall {team} {gaps} {connected} {now} />{/if}
</article>

<style>
	.team { margin-bottom: 14px; background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 12px;
		backdrop-filter: blur(var(--glass-blur)); overflow: hidden; }
	.row { position: relative; display: grid; grid-template-columns: repeat(4, 1fr) 1.15fr; gap: 6px; height: var(--row-h);
		padding: 0 40px 0 60px; cursor: pointer; }
	.side { padding: 16px 0 16px var(--side-inset); display: flex; flex-direction: column; gap: 8px; min-width: 0; cursor: default; }
	.edit { align-self: flex-start; font-size: 12px; }
	.arrows { position: absolute; right: 8px; top: 50%; transform: translateY(-50%); display: flex; flex-direction: column; gap: 4px;
		opacity: 0; transition: opacity 0.12s; }
	.team:hover .arrows, .team:focus-within .arrows { opacity: 1; }
	.arrows button { width: 26px; height: 26px; border-radius: 50%; padding: 0; }
	@media (max-width: 1100px) {
		.row { grid-template-columns: repeat(4, 1fr); height: auto; padding: 0 40px 0 40px; }
		.row > :global(.rib) { height: var(--row-h); }
		.side { grid-column: 1 / -1; padding: 12px 0; }
	}
</style>
```

(The `.rib` root in `TeamRibbon` carries class `rib`, so the `:global(.rib)` selector targets it.)

- [ ] **Step 5: Rewrite `frontend/src/routes/teams/+page.svelte`** — keep `load`, `setFilter`, `reorderTo`, `indexOf`, `buildAgain`, the poll interval, the tag filter header and Manage tags; remove the drag handlers, the `saved` query handling, and the `TeamCard` import. Add:

```ts
	import { goto } from '$app/navigation';
	import TeamRow from '$lib/TeamRow.svelte';
	import { changeMessage, memberLookup, willLower } from '$lib/teams';

	let notice = $state<string | null>(null);

	function openEditor(id: number | 'new') {
		void goto(`/teams?edit=${id}`, { noScroll: true, keepFocus: true });
	}

	async function setBuild(team: Team, on: boolean) {
		if (!data) return;
		if (!on) {
			const names = willLower(data.teams, memberLookup(data.teams), team.id, { memberIds: team.members.map((m) => m.id), hasBuild: false });
			if (names.length && !confirm(`Turn off Build? This moves ${names.join(', ')} off Build.`)) return;
		}
		const before = data.teams;
		data = { ...data, teams: data.teams.map((t) => (t.id === team.id ? { ...t, has_build_tag: on } : t)) };
		try {
			const r = await api.setTeamBuild(team.id, on);
			const msg = changeMessage('', r.raised, r.lowered).replace(/^ · /, '');
			if (msg) notice = msg;
			await load();
		} catch (e) {
			if (data) data = { ...data, teams: before };
			toast = `Could not change Build for ${team.name}: ${errorMessage(e)}`;
		}
	}
```

(Add `Team` to the `$lib/types` import.) Change the **New team** link to `<button type="button" class="primary" data-testid="new-team" onclick={() => openEditor('new')}>New team</button>`; replace the `saved` toast with `{#if notice}<div class="toast ok" role="status">{notice} <button type="button" onclick={() => (notice = null)}>Dismiss</button></div>{/if}`; render rows with

```svelte
{#each shown as team (team.id)}
	<TeamRow {team} gaps={data.gaps} connected={data.connected} {now} reorderable={canReorder}
		first={indexOf(team.id) === 0} last={indexOf(team.id) === data.teams.length - 1}
		onMove={(d) => reorderTo(indexOf(team.id), indexOf(team.id) + d)} onOpen={() => openEditor(team.id)}
		onBuild={(on) => setBuild(team, on)} onBuildAgain={buildAgain} />
{/each}
```

and in the empty state replace the `/teams/new` link with a button calling `openEditor('new')`. (Task 7 mounts the modal from `?edit=`.)

- [ ] **Step 6: Delete `TeamCard.svelte`** once `grep -rn TeamCard frontend/src` shows no other user.

- [ ] **Step 7: Run** — `npm run check` (0 errors), `npx vitest run`, `npm run build`. Then start the e2e server and look at `/teams` in a browser at 1600px and 1000px wide: no ribbon text crosses a slanted edge; the team name is not under the fourth ribbon. (The old `teams.spec.ts` will fail until Task 7 rewrites it; do not run it here.)

- [ ] **Step 8: Commit**

```bash
git add frontend/src
git commit -m "feat(teams): slanted splash ribbons, team info with Build switch, shortfall drawer, hover arrows

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Popup team editor, redirects, Teams e2e

**Files:**
- Create: `frontend/src/lib/TeamEditorModal.svelte`, `frontend/src/routes/teams/new/+page.ts`, `frontend/src/routes/teams/[id]/+page.ts`
- Delete: `frontend/src/lib/TeamEditor.svelte`, `frontend/src/routes/teams/new/+page.svelte`, `frontend/src/routes/teams/[id]/+page.svelte`
- Modify: `frontend/src/routes/teams/+page.svelte`
- Test: `frontend/e2e/teams.spec.ts` (rewrite)

**Interfaces:**
- Consumes: everything from `TeamEditor.svelte` (`addMember`, `removeMember`, `moveItem`, `validateTeam`, `teamErrorField`, `willRaise`, `BUILD_TAG_ID`, `MAX_MEMBERS`), plus `willLower`, `charLookup`, `changeMessage`, `CharacterFilterBar`, `CharacterTile`, `loadCharacterView`, `sortCharacters`, `matches`, `emptyFilters`.
- Produces: `<TeamEditorModal teamId={number | null} teams={Team[]} onClose={() => void} onDone={(message: string) => void} />`; test hooks: `getByLabel('Team name')`, `getByRole('switch', { name: 'Build' })` inside the dialog, `slot-{i}`, `pick-{slug}`, `error-name`, `error-members`, buttons `Save`, `Cancel`, `Delete team`, `Close`.

- [ ] **Step 1: Rewrite `frontend/e2e/teams.spec.ts`** (seed: team 1 "Abyss Furina" = Build + Abyss with Furina, Bennett, Xingqiu (not owned); team 2 "Archons only"; Nahida obtained, goal none):

```ts
import { expect, test } from '@playwright/test';

test('create a Build team in the popup, then switch Build off from the row', async ({ page }) => {
	await page.goto('/teams');
	await page.getByTestId('new-team').click();
	await expect(page).toHaveURL(/\/teams\?edit=new$/);
	const dialog = page.getByRole('dialog');
	await dialog.getByLabel('Team name').fill('Dendro test');
	await dialog.getByTestId('pick-nahida').click();
	await expect(dialog.getByTestId('slot-0')).toContainText('Nahida');
	await dialog.getByRole('switch', { name: 'Build' }).click();
	await expect(dialog.getByText('Saving raises Nahida to Build')).toBeVisible();
	await dialog.getByLabel('Add tag').fill('dendro');
	await dialog.getByLabel('Add tag').press('Enter');
	await dialog.getByRole('button', { name: 'Save' }).click();

	await expect(page).toHaveURL(/\/teams$/);
	await expect(page.getByText('Raised 1 character to Build')).toBeVisible();
	const row = page.locator('article', { hasText: 'Dendro test' });
	await expect(row).toBeVisible();
	await page.getByTestId('tag-filter').getByRole('button', { name: 'dendro' }).click();
	await expect(page.locator('article')).toHaveCount(1);
	await page.getByTestId('tag-filter').getByRole('button', { name: 'All' }).click();

	await page.goto('/characters');
	await expect(page.getByTestId('section-building').getByTestId('card-nahida')).toBeVisible();

	await page.goto('/teams');
	page.once('dialog', (d) => d.accept());               // "Turn off Build? This moves Nahida off Build."
	await row.getByRole('switch', { name: 'Build' }).click();
	await expect(page.getByText('Moved 1 character off Build')).toBeVisible();
	await page.goto('/characters');
	await expect(page.getByTestId('section-obtained').getByTestId('card-nahida')).toBeVisible();

	// restore: delete the team and its tag
	await page.goto('/teams');
	await row.getByRole('button', { name: 'Edit Dendro test' }).click();
	page.once('dialog', (d) => d.accept());
	await page.getByRole('dialog').getByRole('button', { name: 'Delete team' }).click();
	await expect(page.locator('article', { hasText: 'Dendro test' })).toHaveCount(0);
	const tags = await (await page.request.get('/api/tags')).json();
	const dendro = tags.find((t: { name: string }) => t.name === 'dendro');
	if (dendro) await page.request.delete(`/api/tags/${dendro.id}`);
});

test('ribbons grey out unowned members; the shortfall drawer opens', async ({ page }) => {
	await page.goto('/teams');
	const team = page.getByTestId('team-1');
	await expect(team.getByTestId('ribbon-xingqiu')).toHaveClass(/unowned/);
	await expect(team.getByTestId('ribbon-xingqiu')).toContainText('Not owned');
	await expect(page.getByTestId('team-shortfall-1')).toHaveCount(0);
	await page.getByTestId('shortfall-toggle-1').click();
	await expect(page.getByTestId('team-shortfall-1')).toBeVisible();
});

test('hover arrows reorder; reordering is off while a tag filter is on', async ({ page }) => {
	await page.goto('/teams');
	const rows = page.locator('article[data-testid^="team-"]');
	await page.getByTestId('team-2').hover();
	await page.getByRole('button', { name: 'Move Archons only up' }).click();
	await expect(rows.first()).toHaveAttribute('data-testid', 'team-2');
	await page.getByTestId('team-2').hover();
	await page.getByRole('button', { name: 'Move Archons only down' }).click();   // restore
	await expect(rows.first()).toHaveAttribute('data-testid', 'team-1');

	await page.getByTestId('tag-filter').getByRole('button', { name: 'Abyss' }).click();
	await expect(page.getByTestId('reorder-hint')).toBeVisible();
	await expect(page.getByRole('button', { name: 'Move Abyss Furina down' })).toBeDisabled();
	await page.getByTestId('tag-filter').getByRole('button', { name: 'All' }).click();
});

test('old editor URLs open the popup; errors sit by their field; Delete names the saved team', async ({ page }) => {
	await page.goto('/teams/new');
	await expect(page).toHaveURL(/\/teams\?edit=new$/);
	await page.getByRole('dialog').getByRole('button', { name: 'Close' }).click();

	await page.goto('/teams/2');
	await expect(page).toHaveURL(/\/teams\?edit=2$/);
	const dialog = page.getByRole('dialog');
	await expect(dialog.getByLabel('Team name')).toHaveValue('Archons only');
	await dialog.getByLabel('Team name').fill('');
	await dialog.getByRole('button', { name: 'Save' }).click();
	await expect(dialog.getByTestId('error-name')).toHaveText('Team name is required');
	await dialog.getByLabel('Team name').fill('Renamed but unsaved');
	let message = '';
	page.once('dialog', (d) => { message = d.message(); void d.dismiss(); });
	await dialog.getByRole('button', { name: 'Delete team' }).click();
	await expect.poll(() => message).toContain('"Archons only"');
});

test('popup asks before discarding unsaved changes', async ({ page }) => {
	await page.goto('/teams');
	await page.getByRole('button', { name: 'Edit Archons only' }).click();   // so /teams sits behind ?edit=2 in history
	await expect(page).toHaveURL(/\/teams\?edit=2$/);
	const dialog = page.getByRole('dialog');
	await dialog.getByLabel('Team name').fill('Changed');
	let asked = '';
	page.once('dialog', (d) => { asked = d.message(); void d.dismiss(); });
	await page.keyboard.press('Escape');
	await expect.poll(() => asked).toContain('Discard changes?');
	await expect(dialog).toBeVisible();
	page.once('dialog', (d) => d.accept());
	await page.goBack();
	await expect(page.getByRole('dialog')).toHaveCount(0);
	await expect(page.getByTestId('team-2')).toContainText('Archons only');
});

test('a rejected tag rename restores the old name; a deleted tag leaves the filter', async ({ page }) => {
	await page.goto('/teams');
	await page.getByRole('button', { name: 'Manage tags' }).click();
	const manager = page.getByTestId('tag-manager');
	const rename = manager.getByLabel('Rename Abyss');
	await rename.fill('Build');
	await rename.press('Tab');
	await expect(manager.locator('.error')).toBeVisible();
	await expect(rename).toHaveValue('Abyss');

	await manager.getByLabel('New tag name').fill('scratch');
	await manager.getByRole('button', { name: 'Add tag' }).click();
	const filter = page.getByTestId('tag-filter');
	await filter.getByRole('button', { name: 'scratch' }).click();
	await expect(page.getByText('No team has these tags.')).toBeVisible();
	page.once('dialog', (d) => d.accept());
	await manager.locator('li', { hasText: 'scratch' }).getByRole('button', { name: 'Delete' }).click();
	await expect(filter.getByRole('button', { name: 'scratch' })).toHaveCount(0);
	await expect(filter.getByRole('button', { name: 'All' })).toHaveClass(/on/);
});
```

(The popup is opened from the row so `page.goBack()` returns to `/teams`; the `beforeNavigate` guard asks first, which the `once('dialog')` accepts.)

- [ ] **Step 2: Run — expect FAIL** — `PYTHON=... npx playwright test e2e/teams.spec.ts`

- [ ] **Step 3: Redirect routes** — delete both `+page.svelte` files under `routes/teams/new` and `routes/teams/[id]`, and create:

`frontend/src/routes/teams/new/+page.ts`:

```ts
import { redirect } from '@sveltejs/kit';

export function load() {
	redirect(307, '/teams?edit=new');
}
```

`frontend/src/routes/teams/[id]/+page.ts`:

```ts
import { redirect } from '@sveltejs/kit';

export function load({ params }) {
	redirect(307, `/teams?edit=${encodeURIComponent(params.id)}`);
}
```

- [ ] **Step 4: Create `frontend/src/lib/TeamEditorModal.svelte`** — move `TeamEditor.svelte`'s script into it with these changes, then delete `TeamEditor.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { beforeNavigate } from '$app/navigation';
	import { ApiError, api, errorMessage } from './api';
	import CharacterFilterBar from './CharacterFilterBar.svelte';
	import { loadCharacterView } from './characterView';
	import CharacterTile from './CharacterTile.svelte';
	import { imgSrc } from './img';
	import { emptyFilters, matches, sortCharacters, type Filters } from './status';
	import TagChip from './TagChip.svelte';
	import {
		BUILD_TAG_ID, MAX_MEMBERS, addMember, changeMessage, charLookup, moveItem, removeMember, teamErrorField,
		validateTeam, willLower, willRaise, type FieldError
	} from './teams';
	import type { Character, MemberDraft, TagWithCount, Team } from './types';

	let { teamId, teams, onClose, onDone }: {
		teamId: number | null; teams: Team[]; onClose: () => void; onDone: (message: string) => void;
	} = $props();

	let dialog: HTMLDialogElement;
	// state identical to TeamEditor.svelte: chars, tags, name, notes, members, tagIds, newTags, tagInput, original,
	// snapshot, loading, missing, loadFailed, saving, error, fieldError, savedName, dragSlot, formState, dirty, byId,
	// hasBuild, raising, load(), toggleTagId(), addTypedTag()
	let filters = $state<Filters>(emptyFilters());
	let sort = $state(loadCharacterView().sort);
	const pickable = $derived(sortCharacters(chars.filter((c) => matches(c, filters)), sort));
	const lowering = $derived(willLower(teams, charLookup(chars), teamId, { memberIds: members.map((m) => m.character_id), hasBuild }));

	onMount(() => {
		dialog.showModal();
		load();
	});

	function setBuild(on: boolean) {
		tagIds = on ? [...new Set([...tagIds, BUILD_TAG_ID])] : tagIds.filter((t) => t !== BUILD_TAG_ID);
	}

	function requestClose() {
		if (dirty && !saving && !confirm('Discard changes?')) return;
		snapshot = formState();                          // so the navigation guard does not ask again
		onClose();
	}

	beforeNavigate(({ cancel }) => {
		if (dirty && !saving && !confirm('Discard changes?')) cancel();
	});

	async function save() {
		fieldError = validateTeam(name, members.length);
		if (fieldError) return;
		saving = true;
		const body = { name, notes, members, tag_ids: tagIds, new_tags: newTags };
		try {
			const res = teamId === null ? await api.createTeam(body) : await api.updateTeam(teamId, body);
			snapshot = formState();
			onDone(changeMessage('Saved', res.raised, res.lowered));
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) missing = true;
			else if (e instanceof ApiError && e.status === 422) fieldError = { field: teamErrorField(e.message), message: e.message };
			else error = errorMessage(e);
		} finally {
			saving = false;
		}
	}

	async function remove() {
		if (teamId === null) return;
		const moving = willLower(teams, charLookup(chars), teamId, null);
		const extra = moving.length ? ` This moves ${moving.join(', ')} off Build.` : '';
		if (!confirm(`Delete "${savedName}"?${extra}`)) return;
		try {
			saving = true;
			const res = await api.deleteTeam(teamId);
			snapshot = formState();
			onDone(changeMessage('Deleted', [], res.lowered));
		} catch (e) {
			if (e instanceof ApiError && e.status === 404) missing = true;
			else error = errorMessage(e);
		} finally {
			saving = false;
		}
	}
</script>
```

Remove `TeamEditor.svelte`'s `beforeunload` effect only if you keep an equivalent one here (keep it: copy the `$effect` that warns on `beforeunload` when `dirty`).

Markup:

```svelte
<!-- svelte-ignore a11y_click_events_have_key_events, a11y_no_noninteractive_element_interactions -->
<dialog bind:this={dialog} class="modal" aria-label={teamId === null ? 'New team' : 'Edit team'}
	oncancel={(e) => { e.preventDefault(); requestClose(); }}
	onclick={(e) => { if (e.target === dialog) requestClose(); }}>
	{#if loading}
		<p class="muted">Loading…</p>
	{:else if missing}
		<p>This team no longer exists.</p>
		<button type="button" onclick={onClose}>Close</button>
	{:else if loadFailed}
		<div class="toast error">Could not load the team editor: {error} <button type="button" onclick={load}>Retry</button></div>
		<button type="button" onclick={onClose}>Close</button>
	{:else}
		<div class="head">
			<input class="name" bind:value={name} maxlength="60" aria-label="Team name"
				aria-invalid={fieldError?.field === 'name'} aria-describedby={fieldError?.field === 'name' ? 'err-name' : undefined} />
			<label class="sw-row"><button type="button" role="switch" aria-checked={hasBuild} aria-label="Build" class="sw" class:on={hasBuild}
				onclick={() => setBuild(!hasBuild)}></button> Build</label>
			<button type="button" class="x" onclick={requestClose} aria-label="Close">✕</button>
		</div>
		{#if fieldError?.field === 'name'}<p class="error" id="err-name" data-testid="error-name">{fieldError.message}</p>{/if}
		{#if error}<div class="toast error">{error} <button type="button" onclick={() => (error = null)}>Dismiss</button></div>{/if}

		<div class="tagrow">
			{#each tags.filter((t) => !t.builtin) as t (t.id)}<TagChip tag={t} on={tagIds.includes(t.id)} onclick={() => toggleTagId(t.id)} />{/each}
			{#each newTags as nt (nt)}
				<TagChip tag={{ id: -1, name: `${nt} (new)`, color: 'blue', builtin: false }} onclick={() => (newTags = newTags.filter((x) => x !== nt))} />
			{/each}
			<form onsubmit={addTypedTag}><input bind:value={tagInput} maxlength="30" placeholder="+ new tag" aria-label="Add tag" /></form>
			<textarea bind:value={notes} maxlength="2000" rows="2" aria-label="Notes" placeholder="Notes"
				aria-invalid={fieldError?.field === 'notes'}></textarea>
		</div>
		{#if fieldError?.field === 'tags' || fieldError?.field === 'notes'}<p class="error">{fieldError.message}</p>{/if}

		<div class="slots">
			{#each Array.from({ length: MAX_MEMBERS }) as _x, i (i)}
				{@const m = members[i]}
				{@const c = m ? byId.get(m.character_id) : undefined}
				<div class="slot" class:empty={!m} class:unowned={c && !c.owned} data-testid="slot-{i}" role="listitem" draggable={!!m}
					ondragstart={() => (dragSlot = i)} ondragend={() => (dragSlot = null)} ondragover={(e) => e.preventDefault()}
					ondrop={() => { if (dragSlot !== null && m) members = moveItem(members, dragSlot, i); dragSlot = null; }}>
					{#if m}
						<div class="art" style={c?.splash ? `background-image: url(${imgSrc(c.splash)})` : ''}></div>
						<div class="ft">
							<b>{c?.name ?? `Character ${m.character_id}`}</b>{#if c && !c.owned}<span class="muted"> Not owned</span>{/if}
							<input value={m.role} maxlength="40" placeholder="Role" aria-label="Role for {c?.name ?? m.character_id}"
								oninput={(e) => (members = members.map((x, j) => (j === i ? { ...x, role: (e.currentTarget as HTMLInputElement).value } : x)))} />
							<div class="slot-actions">
								<button type="button" disabled={i === 0} onclick={() => (members = moveItem(members, i, i - 1))} aria-label="Move left">◀</button>
								<button type="button" disabled={i === members.length - 1} onclick={() => (members = moveItem(members, i, i + 1))} aria-label="Move right">▶</button>
								<button type="button" onclick={() => (members = removeMember(members, i))} aria-label="Remove {c?.name ?? m.character_id}">✕</button>
							</div>
						</div>
					{:else}
						<span class="muted">Empty slot</span>
					{/if}
				</div>
			{/each}
		</div>
		{#if fieldError?.field === 'members'}<p class="error" data-testid="error-members">{fieldError.message}</p>{/if}
		{#if raising.length}<p class="warn">Saving raises {raising.join(', ')} to Build</p>{/if}
		{#if lowering.length}<p class="warn">Saving moves {lowering.join(', ')} off Build</p>{/if}
		{#if fieldError && fieldError.field === null}<p class="error">{fieldError.message}</p>{/if}

		<CharacterFilterBar bind:filters bind:sort />
		{#if members.length >= MAX_MEMBERS}<p class="muted">The team is full. Remove a member to add another.</p>{/if}
		<div class="grid">
			{#each pickable as c (c.id)}
				{@const inTeam = members.some((m) => m.character_id === c.id)}
				<CharacterTile character={c} picked={inTeam} disabled={inTeam || members.length >= MAX_MEMBERS}
					onpick={() => (members = addMember(members, c.id))} />
			{/each}
		</div>

		<div class="foot">
			{#if teamId !== null}<button type="button" class="danger" onclick={remove} disabled={saving}>Delete team</button>{/if}
			<span class="spacer"></span>
			<button type="button" onclick={requestClose}>Cancel</button>
			<button type="button" class="primary" onclick={save} disabled={saving}>Save</button>
		</div>
	{/if}
</dialog>

<style>
	.modal { width: 90vw; max-width: 1500px; height: 90vh; padding: 16px; border-radius: 14px; color: var(--text);
		background: rgba(22, 26, 44, 0.96); border: 1px solid var(--glass-border); overflow: auto; }
	.modal::backdrop { background: rgba(4, 6, 12, 0.7); }
	.head { display: flex; gap: 12px; align-items: center; margin-bottom: 10px; }
	.name { width: 280px; font-size: 16px; }
	.x { margin-left: auto; }
	.sw-row { display: flex; gap: 6px; align-items: center; font-size: 13px; }
	.sw { width: 32px; height: 18px; border-radius: 9px; padding: 0; border: 1px solid var(--glass-border); background: #3a3f50; position: relative; }
	.sw::after { content: ''; position: absolute; left: 2px; top: 2px; width: 12px; height: 12px; border-radius: 50%; background: var(--cream); }
	.sw.on { background: var(--gold); } .sw.on::after { left: 16px; background: #17130b; }
	.tagrow { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; margin-bottom: 10px; }
	.tagrow textarea { flex: 1; min-width: 240px; }
	.slots { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
	.slot { border-radius: 10px; overflow: hidden; background: rgba(255, 255, 255, 0.05); min-height: 180px; }
	.slot.empty { border: 2px dashed rgba(255, 255, 255, 0.2); background: none; display: grid; place-items: center; }
	.art { height: 120px; background-size: auto 130%; background-position: center 20%; background-repeat: no-repeat; }
	.unowned .art { filter: grayscale(1) brightness(0.55); }
	.ft { padding: 6px; display: flex; flex-direction: column; gap: 4px; }
	.ft input { width: 100%; }
	.slot-actions { display: flex; gap: 4px; }
	.warn { color: var(--warn); margin: 6px 0; }
	.grid { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 4px; }
	.foot { display: flex; gap: 10px; align-items: center; margin-top: 14px; position: sticky; bottom: -16px;
		background: rgba(22, 26, 44, 0.96); padding: 10px 0; }
	.spacer { flex: 1; }
</style>
```

- [ ] **Step 5: Mount the modal on the Teams page** — in `frontend/src/routes/teams/+page.svelte`:

```ts
	import TeamEditorModal from '$lib/TeamEditorModal.svelte';

	const editParam = $derived(page.url.searchParams.get('edit'));
	const editId = $derived(editParam === 'new' ? null : editParam !== null && /^\d+$/.test(editParam) ? Number(editParam) : undefined);

	function closeEditor() {
		void goto('/teams', { noScroll: true, keepFocus: true });
	}

	async function editorDone(message: string) {
		notice = message;
		await goto('/teams', { noScroll: true });
		await load();
	}
```

Markup at the end of the page:

```svelte
{#if editParam !== null && data}
	{#key editParam}
		{#if editId === undefined}
			<TeamEditorModal teamId={-1} teams={data.teams} onClose={closeEditor} onDone={editorDone} />
		{:else}
			<TeamEditorModal teamId={editId} teams={data.teams} onClose={closeEditor} onDone={editorDone} />
		{/if}
	{/key}
{/if}
```

(`teamId={-1}` makes the modal load a team that cannot exist, so a malformed `?edit=abc` shows "This team no longer exists" with Close.)

- [ ] **Step 6: Run** — `npm run check` (0 errors), `npx vitest run`, `npm run build`, then the full Playwright suite `PYTHON=... npx playwright test` — expect all PASS. Fix `shell.spec.ts` only if it referenced `/teams/new` (it currently only lists `/teams`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src frontend/e2e
git commit -m "feat(teams): popup team editor with Build switch and lower preview; old editor URLs redirect

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Whole-branch verification

**Files:** none new (fixes only, in the task's own commit).

- [ ] **Step 1: Backend** — from `backend/`: `C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe -m pytest -q` → all pass.
- [ ] **Step 2: Frontend** — from `frontend/`: `npm run check` (0 errors; no new warnings), `npx vitest run`, `npm run build`, `PYTHON=... npx playwright test` → all pass.
- [ ] **Step 3: Leftovers** — `grep -rn "CharacterCard\|TeamCard\|TeamEditor\b\|artifact_lines" frontend/src backend/app` returns nothing; `git grep -n -i "ltoken\|cookie_token\|800000001" -- ':!backend/tests' ':!backend/app/devseed.py'` shows nothing new.
- [ ] **Step 4: Visual check** — run the e2e server (`python -m app.devseed --root ../.e2e-data` then `python ../run.py --no-build` with `GT_ROOT=../.e2e-data GT_OFFLINE=1`; offline images are placeholders) and open `/characters` and `/teams` at 1600px and 1000px; confirm the ribbon/info clipping rules from the spec §6.3–6.4.
- [ ] **Step 5: Commit any fixes** with a `fix(...)` message ending in the Co-Authored-By line.
