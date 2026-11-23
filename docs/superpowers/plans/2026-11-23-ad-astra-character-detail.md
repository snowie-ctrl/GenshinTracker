# Ad Astra Sub-project 5 — Character Detail Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the character detail page with a splash banner and Current / Build / Guide sub-pages themed in the character's element colour, move build targets to per-character values (baseline rule, plus target constellation and refinement), and add a Guide built from Yatta talent and constellation data.

**Architecture:** Backend: `build_defaults()` in `domain.py` plus `app/targets.py` (current values, stored targets, writing targets) replace the `default_targets` setting everywhere goals are raised; migration 0010 adds two target columns, deletes the setting row and creates `game_character_kit`; `gamedata/kit.py` fetches, parses and caches Yatta `avatar/<id>` data served by `GET /api/characters/{slug}/kit`. Frontend: a `[slug]/+layout.svelte` loads the character, kit and level caps once into a context object, draws `CharacterBanner`, sets the dust tint; three child routes render Current, Build and Guide.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, SQLite, httpx (backend); SvelteKit with Svelte 5 runes, TypeScript, Vitest, Playwright (frontend).

**Spec:** `docs/superpowers/specs/2026-11-23-ad-astra-character-detail-design.md`

## Global Constraints

- Python: `C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe`. Backend tests: `<python> -m pytest -q` from `backend/`.
- Frontend checks from `frontend/`: `npm run check`, `npx vitest run`, `npm run build`, `PYTHON=<python> npx playwright test` (workers 1; all specs share one seeded server; restore any state a test changes).
- Run `npm ci` in `frontend/` once before the first frontend task if `node_modules` is missing.
- Cookie values only in the git-ignored `.env`; never logged, returned or committed. The kit request sends no cookie, UID or email.
- Unofficial HoYoLAB code stays in `backend/app/sync/` and `wishes/`; Yatta code stays in `backend/app/gamedata/`.
- Test fixtures use made-up UIDs (800000001). No personal data or game art committed; images load at runtime via `/api/img`.
- No `{@html}` anywhere: kit text renders as plain `<span>` segments.
- Baseline targets: character level 90, talents normal 6 / skill 9 / burst 9, weapon level 90; each raised to the current value when higher; constellation and refinement targets start at the current values (unowned: C0, R1).
- `GAMEDATA_MAX_AGE_DAYS` (7) is the kit freshness window.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **Switching between two characters keeps the page in sync.** SvelteKit reuses `[slug]/+layout.svelte` when only the slug changes, so the character, kit, tint and tab links must all follow the new slug, and a late response for the old slug must not overwrite the new one. Test: Task 6 e2e goes Furina → Bennett and checks the name, the tint and the Guide content.
2. **Mona-style kits with no `linkedConstellations` level links.** C3/C5 must still be mapped (by the "Increases the Level of <talent>" text), or boosted levels and the max of 13 would be wrong. Test: Task 2 `test_mona_raises_by_text`.
3. **Offline (`GT_OFFLINE=1`) with no cached kit.** This must return `unavailable` without any HTTP call, so Playwright and offline runs never reach Yatta. Test: Task 3 `test_kit_offline_never_fetches`.
4. **Rows from before this sub-project (`target_constellation`/`target_refinement` NULL).** Build must show "same as current", not C0/R1 or a crash, and saving another target must not write junk into them. Tests: Task 1 `test_targets_omitting_new_fields_keeps_stored`; Task 4 `buildValue` vitest.
5. **A target already below the current value** (the character was levelled in game). Build shows it as reached, with no negative or confusing arrow. Test: Task 4 `isReached` vitest.

---

## File Structure

**Backend**
- `backend/app/domain.py` (modify): `Targets` gains `constellation`, `refinement`; `Current` gains `constellation`, `weapon_level`, `refinement`; new `BASELINE`, `build_defaults()`.
- `backend/app/targets.py` (create): `current_for()`, `defaults_for()`, `stored_targets()`, `write_targets()`, the one place goal rows' targets are read and written.
- `backend/app/planner/requests.py` (modify): rename `_shared_traveler_row` → `shared_traveler_row`.
- `backend/app/api/characters.py` (modify): use `app.targets`; payload adds `priority`; new `GET /characters/{slug}/kit`.
- `backend/app/teams/goals.py`, `backend/app/teams/store.py` (modify): `raise_to_build(session, ids)` without defaults.
- `backend/app/schemas.py` (modify): `TargetsIn` optional `constellation`, `refinement`.
- `backend/app/settings/store.py`, `backend/app/config.py`, `backend/app/api/settings.py` (modify): remove `default_targets`.
- `backend/app/db/models.py` (modify): two `CharacterGoal` columns, `GameCharacterKit` model.
- `backend/migrations/versions/0010_character_detail.py` (create).
- `backend/app/gamedata/kit.py` (create): `yatta_key`, `fetch_kit`, `parse_kit`, `load_kit`.
- `backend/app/context.py` (modify): `kit_locks`.
- `backend/app/devseed.py` (modify): seed a made-up kit per seeded character.
- Tests: `tests/test_domain.py`, `tests/test_targets.py` (create), `tests/test_api_characters.py`, `tests/test_teams_goals.py`, `tests/test_planner_order.py`, `tests/test_settings_store.py`, `tests/test_api_settings.py`, `tests/test_migration_0010.py` (create), `tests/test_kit_parse.py` (create), `tests/test_api_kit.py` (create), `tests/helpers.py` (modify), fixtures `tests/fixtures/yatta_kit_furina.json`, `yatta_kit_mona.json`, `yatta_kit_traveler_anemo.json` (create).

**Frontend**
- `frontend/src/lib/types.ts`, `api.ts` (modify): `Targets` new fields, `priority`, kit types, `characterKit`, drop `default_targets`.
- `frontend/src/lib/kit.ts` + `kit.test.ts` (create): pure kit/target helpers.
- `frontend/src/lib/elements.ts` + `elements.test.ts` (modify): `ELEMENT_HEX`, `elementHex`.
- `frontend/src/lib/starfield.ts` + `starfield.test.ts`, `Starfield.svelte` (modify): tint.
- `frontend/src/lib/appearance.svelte.ts` (modify): `tint`.
- `frontend/src/lib/nav.ts` + `nav.test.ts` (modify): `isWide` for character sub-paths.
- `frontend/src/lib/characterPage.svelte.ts` (create): the layout's context object.
- Components (create): `CharacterBanner.svelte`, `TalentBadge.svelte`, `ConstellationRow.svelte`, `KitText.svelte`, `ScalingTable.svelte`, `BuildArtifacts.svelte`.
- Routes: `frontend/src/routes/characters/[slug]/+layout.svelte` (create), `+page.svelte` (rewrite: Current), `build/+page.svelte`, `guide/+page.svelte` (create); `routes/+layout.svelte` (pass tint); `routes/settings/+page.svelte` (drop Planner block).
- Delete: `frontend/src/lib/TargetsEditor.svelte`.
- E2E: `frontend/e2e/characters.spec.ts`, `frontend/e2e/settings.spec.ts` (modify).

---

### Task 1: Per-character build targets (backend)

**Files:**
- Modify: `backend/app/domain.py`, `backend/app/planner/requests.py`, `backend/app/api/characters.py`, `backend/app/teams/goals.py`, `backend/app/teams/store.py`, `backend/app/schemas.py`, `backend/app/settings/store.py`, `backend/app/config.py`, `backend/app/api/settings.py`, `backend/app/db/models.py`
- Create: `backend/app/targets.py`, `backend/migrations/versions/0010_character_detail.py`
- Test: `backend/tests/test_domain.py`, `backend/tests/test_targets.py` (create), `backend/tests/test_api_characters.py`, `backend/tests/test_teams_goals.py`, `backend/tests/test_planner_order.py`, `backend/tests/test_settings_store.py`, `backend/tests/test_api_settings.py`, `backend/tests/test_migration_0010.py` (create)

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `domain.Targets(level, normal, skill, burst, weapon_level, constellation: int | None = None, refinement: int | None = None)`; `to_dict()` now has 7 keys.
  - `domain.Current(level, normal, skill, burst, constellation: int = 0, weapon_level: int | None = None, refinement: int | None = None)`.
  - `domain.build_defaults(current: Current | None) -> Targets`.
  - `app.targets.current_for(s, cid) -> Current | None`, `defaults_for(s, cid) -> Targets`, `stored_targets(row: CharacterGoal | None) -> Targets | None`, `write_targets(row, t: Targets) -> None`.
  - `teams.goals.raise_to_build(session, character_ids) -> list[int]` (no `defaults` argument).
  - `models.CharacterGoal.target_constellation`, `.target_refinement`; `models.GameCharacterKit(character_id, data, fetched_at)`.
  - `GET /api/characters/{slug}` and list payloads gain `"priority"`; `targets` has `constellation` and `refinement`.
  - Settings API has no `default_targets`.

- [ ] **Step 1: Write failing domain tests**

Append to `backend/tests/test_domain.py`:

```python
from app.domain import Current, Targets, build_defaults


def test_build_defaults_baseline_for_unowned():
    assert build_defaults(None) == Targets(90, 6, 9, 9, 90, constellation=0, refinement=1)


def test_build_defaults_never_below_current():
    cur = Current(level=90, normal=10, skill=8, burst=10, constellation=2, weapon_level=80, refinement=5)
    assert build_defaults(cur) == Targets(90, 10, 9, 10, 90, constellation=2, refinement=5)


def test_build_defaults_missing_current_values():
    cur = Current(level=40, normal=None, skill=None, burst=None)
    assert build_defaults(cur) == Targets(90, 6, 9, 9, 90, constellation=0, refinement=1)


def test_targets_from_dict_without_new_fields():
    t = Targets.from_dict({"level": 80, "normal": 6, "skill": 6, "burst": 6, "weapon_level": 80})
    assert (t.constellation, t.refinement) == (None, None)
    assert t.to_dict()["constellation"] is None
```

- [ ] **Step 2: Run them to verify they fail**

Run: `<python> -m pytest -q tests/test_domain.py`
Expected: FAIL with `ImportError: cannot import name 'build_defaults'`.

- [ ] **Step 3: Implement in `backend/app/domain.py`**

Replace the `Targets` and `Current` dataclasses and add the baseline below them:

```python
@dataclass(frozen=True)
class Targets:
    level: int
    normal: int
    skill: int
    burst: int
    weapon_level: int
    constellation: int | None = None   # wish goal; the material planner ignores it (sub-project 5)
    refinement: int | None = None      # wish goal; the material planner ignores it (sub-project 5)

    @classmethod
    def from_dict(cls, d: dict) -> Targets:
        return cls(
            level=int(d["level"]),
            normal=int(d["normal"]),
            skill=int(d["skill"]),
            burst=int(d["burst"]),
            weapon_level=int(d["weapon_level"]),
            constellation=None if d.get("constellation") is None else int(d["constellation"]),
            refinement=None if d.get("refinement") is None else int(d["refinement"]),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Current:
    level: int
    normal: int | None
    skill: int | None
    burst: int | None
    constellation: int = 0
    weapon_level: int | None = None
    refinement: int | None = None


BASELINE = Targets(level=90, normal=6, skill=9, burst=9, weapon_level=90)


def build_defaults(current: Current | None) -> Targets:
    """Starting targets when a character first goes to Build. Sub-project 9 replaces the body, not the callers."""
    c = current or Current(level=1, normal=1, skill=1, burst=1)
    return Targets(
        level=max(BASELINE.level, c.level),
        normal=max(BASELINE.normal, c.normal or 1),
        skill=max(BASELINE.skill, c.skill or 1),
        burst=max(BASELINE.burst, c.burst or 1),
        weapon_level=max(BASELINE.weapon_level, c.weapon_level or 1),
        constellation=c.constellation,
        refinement=c.refinement or 1,
    )
```

`progress()` and the dashboard keep calling `Current(o.level, o.talent_normal, o.talent_skill, o.talent_burst)`; the new fields have defaults.

- [ ] **Step 4: Run domain tests**

Run: `<python> -m pytest -q tests/test_domain.py`
Expected: PASS.

- [ ] **Step 5: Write the migration test**

Create `backend/tests/test_migration_0010.py`:

```python
from sqlalchemy import inspect, text

from app.db.engine import make_engine
from test_migration_0007 import downgrade, upgrade


def test_0010_adds_columns_kit_table_and_drops_setting(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0009")
    with engine.begin() as conn:
        conn.execute(text("INSERT INTO setting (key, value) VALUES ('default_targets', '{\"level\": 90}')"))
        conn.execute(text("INSERT INTO setting (key, value) VALUES ('display_name', '\"x\"')"))
    upgrade(engine, "0010")
    insp = inspect(engine)
    cols = {c["name"] for c in insp.get_columns("character_goal")}
    assert {"target_constellation", "target_refinement"} <= cols
    assert {c["name"] for c in insp.get_columns("game_character_kit")} == {"character_id", "data", "fetched_at"}
    with engine.begin() as conn:
        keys = {k for (k,) in conn.execute(text("SELECT key FROM setting"))}
    assert "default_targets" not in keys and "display_name" in keys
    engine.dispose()


def test_0010_downgrade(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0010")
    downgrade(engine, "0009")
    insp = inspect(engine)
    assert "game_character_kit" not in insp.get_table_names()
    assert "target_constellation" not in {c["name"] for c in insp.get_columns("character_goal")}
    engine.dispose()
```

- [ ] **Step 6: Run it to verify it fails**

Run: `<python> -m pytest -q tests/test_migration_0010.py`
Expected: FAIL (`Can't locate revision identified by '0010'`).

- [ ] **Step 7: Create the migration and models**

Create `backend/migrations/versions/0010_character_detail.py`:

```python
"""Ad Astra sub-project 5: Character detail (per-character targets, talent kit cache)

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-23
"""
import sqlalchemy as sa
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("character_goal") as b:
        b.add_column(sa.Column("target_constellation", sa.Integer(), nullable=True))
        b.add_column(sa.Column("target_refinement", sa.Integer(), nullable=True))
    op.execute(sa.text("DELETE FROM setting WHERE key = 'default_targets'"))
    op.create_table(
        "game_character_kit",
        sa.Column("character_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("game_character_kit")
    with op.batch_alter_table("character_goal") as b:
        b.drop_column("target_refinement")
        b.drop_column("target_constellation")
```

In `backend/app/db/models.py`, add to `CharacterGoal` after `target_weapon_level`:

```python
    target_constellation: Mapped[int | None] = mapped_column(Integer, nullable=True)   # sub-project 5
    target_refinement: Mapped[int | None] = mapped_column(Integer, nullable=True)      # sub-project 5
```

and after `class GameMeta`:

```python
class GameCharacterKit(Base):
    """Parsed Yatta talents, passives and constellations per character (sub-project 5)."""
    __tablename__ = "game_character_kit"
    character_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    data: Mapped[object] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)
```

- [ ] **Step 8: Run the migration test**

Run: `<python> -m pytest -q tests/test_migration_0010.py`
Expected: PASS.

- [ ] **Step 9: Write failing tests for `app.targets`**

Create `backend/tests/test_targets.py`:

```python
from datetime import datetime

from app.db.models import CharacterGoal, OwnedCharacter, TravelerElement
from app.domain import Current, Targets
from app.sync.persist import save_details, save_roster
from app.targets import current_for, defaults_for, stored_targets, write_targets
from fakes import make_detail, make_roster
from helpers import seed_game

NOW = datetime(2026, 11, 23)


def test_current_for_owned(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000089, level=90, name="Furina")], NOW)
        save_details(s, [make_detail(10000089, talents=(6, 8, 10))])
    with session_factory() as s:
        assert current_for(s, 10000089) == Current(90, 6, 8, 10, constellation=2, weapon_level=90, refinement=5)
        assert current_for(s, 10000023) is None                      # not owned


def test_current_for_traveler_other_element_uses_shared_level(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(1000000503, raw_id=10000007, name="Traveler", element="Geo", level=80)], NOW)
        s.add(TravelerElement(element_id=1000000502, seen=False, unlocked=True, talent_normal=3, talent_skill=4,
                              talent_burst=5, constellation=1, source="manual", updated_at=NOW))
    with session_factory() as s:
        cur = current_for(s, 1000000502)
        assert (cur.level, cur.normal, cur.skill, cur.burst, cur.constellation) == (80, 3, 4, 5, 1)
        assert current_for(s, 1000000507) is None                    # never seen, not unlocked


def test_defaults_for_unowned(session_factory):
    seed_game(session_factory)
    with session_factory() as s:
        assert defaults_for(s, 10000023) == Targets(90, 6, 9, 9, 90, constellation=0, refinement=1)


def test_write_targets_keeps_stored_wish_targets_when_none(session_factory):
    with session_factory.begin() as s:
        row = CharacterGoal(character_id=1, goal="build", updated_at=NOW)
        s.add(row)
        write_targets(row, Targets(90, 6, 9, 9, 90, constellation=6, refinement=5))
        write_targets(row, Targets(80, 6, 9, 9, 90))                 # no wish targets given
        assert stored_targets(row) == Targets(80, 6, 9, 9, 90, constellation=6, refinement=5)
    assert stored_targets(None) is None
```

- [ ] **Step 10: Run them to verify they fail**

Run: `<python> -m pytest -q tests/test_targets.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.targets'`.

- [ ] **Step 11: Create `backend/app/targets.py`**

First rename `_shared_traveler_row` to `shared_traveler_row` in `backend/app/planner/requests.py` (definition and its one call in `build_inputs`). Then:

```python
"""The one place a character's current values and stored build targets are read and written (sub-project 5)."""
from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import CharacterGoal, OwnedCharacter, TravelerElement
from app.domain import Current, Targets, build_defaults
from app.gamedata.traveler import is_traveler
from app.planner.requests import shared_traveler_row


def current_for(s: Session, cid: int) -> Current | None:
    o = s.get(OwnedCharacter, cid)
    if o is not None:
        return Current(o.level, o.talent_normal, o.talent_skill, o.talent_burst, constellation=o.constellation or 0,
                       weapon_level=o.weapon_level, refinement=o.weapon_refinement)
    if not is_traveler(cid):
        return None
    te = s.get(TravelerElement, cid)
    shared = shared_traveler_row(s)
    if te is None or not (te.seen or te.unlocked) or shared is None:
        return None
    return Current(shared.level, te.talent_normal, te.talent_skill, te.talent_burst, constellation=te.constellation,
                   weapon_level=shared.weapon_level, refinement=shared.weapon_refinement)


def defaults_for(s: Session, cid: int) -> Targets:
    return build_defaults(current_for(s, cid))


def stored_targets(row: CharacterGoal | None) -> Targets | None:
    if row is None or row.target_level is None:
        return None
    return Targets(row.target_level, row.target_normal, row.target_skill, row.target_burst, row.target_weapon_level,
                   constellation=row.target_constellation, refinement=row.target_refinement)


def write_targets(row: CharacterGoal, t: Targets) -> None:
    """Write targets; a None constellation/refinement keeps what is stored (old clients omit them)."""
    row.target_level, row.target_normal = t.level, t.normal
    row.target_skill, row.target_burst = t.skill, t.burst
    row.target_weapon_level = t.weapon_level
    if t.constellation is not None:
        row.target_constellation = t.constellation
    if t.refinement is not None:
        row.target_refinement = t.refinement
```

If importing `app.planner.requests` from `app.targets` causes an import cycle when `teams.goals` imports `app.targets`, move `shared_traveler_row` into `app/traveler/store.py` (it only needs `OwnedCharacter`, `TRAVELER_IDS`, `current_element_id`) and import it from there in both places.

- [ ] **Step 12: Run them**

Run: `<python> -m pytest -q tests/test_targets.py`
Expected: PASS.

- [ ] **Step 13: Update goal-endpoint, teams and settings tests (failing first)**

In `backend/tests/test_api_characters.py`, replace `test_set_goal_build_fills_defaults_and_leaving_keeps_targets` with:

```python
def test_set_goal_build_fills_baseline_and_leaving_keeps_targets(paths):
    setup_data(paths)
    with make_client(paths) as client:
        c = client.put("/api/characters/10000089/goal", json={"goal": "build"}).json()
        assert c["status"] == "building"
        # Furina: Lv 90, talents 6/8/8, C2, The Flute Lv 90 R5 (fakes.make_detail / WEAPON)
        assert c["targets"] == {"level": 90, "normal": 6, "skill": 9, "burst": 9, "weapon_level": 90,
                                "constellation": 2, "refinement": 5}
        custom = {"level": 80, "normal": 6, "skill": 9, "burst": 9, "weapon_level": 80,
                  "constellation": 6, "refinement": 5}
        client.put("/api/characters/10000089/goal", json={"targets": custom})
        c = client.put("/api/characters/10000089/goal", json={"goal": "none"}).json()
        assert c["status"] == "obtained" and c["targets"] == custom
        c = client.put("/api/characters/10000089/goal", json={"goal": "build"}).json()
        assert c["targets"] == custom


def test_targets_omitting_new_fields_keeps_stored(paths):
    setup_data(paths)
    with make_client(paths) as client:
        client.put("/api/characters/10000089/goal", json={"goal": "build", "targets": {
            "level": 90, "normal": 6, "skill": 9, "burst": 9, "weapon_level": 90, "constellation": 4, "refinement": 3}})
        c = client.put("/api/characters/10000089/goal", json={"targets": {
            "level": 80, "normal": 6, "skill": 9, "burst": 9, "weapon_level": 90}}).json()
        assert (c["targets"]["level"], c["targets"]["constellation"], c["targets"]["refinement"]) == (80, 4, 3)
        assert client.put("/api/characters/10000089/goal", json={"targets": {
            "level": 80, "normal": 6, "skill": 9, "burst": 9, "weapon_level": 90, "constellation": 7}}).status_code == 422


def test_detail_has_priority(paths):
    setup_data(paths)
    with make_client(paths) as client:
        client.put("/api/characters/10000089/goal", json={"goal": "build"})
        assert client.get("/api/characters/furina").json()["priority"] is not None
        assert client.get("/api/characters/xiangling").json()["priority"] is None
```

In `backend/tests/test_teams_goals.py`: delete `DEFAULTS = Targets(90, 8, 8, 8, 90)` and the `Targets` import; change every `raise_to_build(s, [...], DEFAULTS)` to `raise_to_build(s, [...])` and `raise_to_build(None, [], DEFAULTS)` to `raise_to_build(None, [])`. In `test_raise_none_want_and_missing_rows` the last assertion becomes the baseline for unowned id 4:

```python
        assert (four.target_level, four.target_skill, four.target_weapon_level) == (90, 9, 90)
        assert (four.target_normal, four.target_constellation, four.target_refinement) == (6, 0, 1)
```

In `backend/tests/test_planner_order.py` line 62: `raise_to_build(s, [7, 1])` (drop the `Targets` argument; remove the `Targets` import if now unused).

In `backend/tests/test_settings_store.py`: remove `default_targets` and `Targets` from the imports, delete the `assert default_targets(s) == ...` line, and delete `test_default_value_is_a_copy` entirely (`default_targets` was the only mutable default; every remaining default is a scalar). Add:

```python
def test_default_targets_setting_is_gone(session_factory):
    with session_factory() as s, pytest.raises(KeyError):
        set_setting(s, "default_targets", {})
```

In `backend/tests/test_api_settings.py`: in `test_settings_defaults` replace the `default_targets` assertion with `assert "default_targets" not in body`; in `test_put_settings_validates_and_saves` replace the body after the first 422 check with:

```python
        body = client.put("/api/settings", json={"sync_interval_minutes": 30,
                                                 "default_targets": {"level": 1}}).json()   # ignored field
    assert body["sync_interval_minutes"] == 30 and "default_targets" not in body
```

In `backend/tests/test_db.py` lines 52–54 (a generic Setting round-trip), change the key `"default_targets"` to `"display_name"` and the value to `{"x": 1}` in both lines.

- [ ] **Step 14: Run them to verify they fail**

Run: `<python> -m pytest -q tests/test_api_characters.py tests/test_teams_goals.py tests/test_planner_order.py tests/test_settings_store.py tests/test_api_settings.py tests/test_db.py`
Expected: FAIL (old 5-key targets, `raise_to_build()` signature, `default_targets` still present).

- [ ] **Step 15: Wire the callers and remove the setting**

`backend/app/schemas.py` — `TargetsIn` gains:

```python
    constellation: int | None = Field(default=None, ge=0, le=6)
    refinement: int | None = Field(default=None, ge=1, le=5)
```

`backend/app/api/characters.py`:
- Remove `from app.settings.store import default_targets` and the local `goal_targets`; import `from app.targets import defaults_for, stored_targets, write_targets`. Replace `goal_targets(row)`/`goal_targets(goal_row)` uses with `stored_targets(...)`.
- In `character_payload` add `"priority": goal_row.priority if goal_row else None,` after `"planned_weapon_id"`.
- In `set_goal`, extend `state()` with `row.target_constellation, row.target_refinement`, and replace the targets block with:

```python
        new_goal = body.goal or row.goal
        if body.targets is not None:
            targets = Targets(**body.targets.model_dump())
        else:
            targets = resolve_targets(new_goal, stored_targets(row), defaults_for(s, character_id))
        apply_goal(s, row, new_goal)
        if targets is not None:
            write_targets(row, targets)
```

`backend/app/teams/goals.py` — delete `_stored`, import `from app.targets import defaults_for, stored_targets, write_targets`, and:

```python
def raise_to_build(session: Session, character_ids: Iterable[int]) -> list[int]:
    """Set goal build for every id whose goal is none/want (no row = none). Returns the ids changed."""
    raised: list[int] = []
    for cid in dict.fromkeys(character_ids):
        row = session.get(CharacterGoal, cid)
        if row is None:
            row = CharacterGoal(character_id=cid, goal="none", updated_at=utcnow())
            session.add(row)
        if row.goal == "build":
            continue
        targets = resolve_targets("build", stored_targets(row), defaults_for(session, cid))
        apply_goal(session, row, "build")
        write_targets(row, targets)
        row.updated_at = utcnow()
        raised.append(cid)
    if raised:
        session.flush()
    return raised
```

(Remove the unused `Targets` import.)

`backend/app/teams/store.py` — remove `from app.settings.store import default_targets`; `raise_to_build(s, to_raise, default_targets(s))` → `raise_to_build(s, to_raise)`; `raise_to_build(s, members, default_targets(s))` → `raise_to_build(s, members)`.

`backend/app/settings/store.py` — delete the `"default_targets": DEFAULT_TARGETS,` entry, the `default_targets()` function, and the `DEFAULT_TARGETS` and `Targets` imports.

`backend/app/config.py` — delete `DEFAULT_TARGETS = {...}`.

`backend/app/api/settings.py` — delete `default_targets` from `SettingsIn`, from `settings_payload`, and the `if body.default_targets ...` block; remove the `TargetsIn` import if unused.

Then grep: `grep -rn "default_targets\|DEFAULT_TARGETS" backend/app` must print nothing except the migration.

- [ ] **Step 16: Run the full backend suite**

Run: `<python> -m pytest -q`
Expected: PASS (all tests, including the earlier 554 minus/plus the edits).

- [ ] **Step 17: Commit**

```bash
git add backend
git commit -m "feat(targets): per-character build baseline replaces default targets setting; target constellation and refinement; migration 0010"
```

---

### Task 2: Talent kit parser

**Files:**
- Create: `backend/app/gamedata/kit.py`, `backend/tests/test_kit_parse.py`, fixtures `backend/tests/fixtures/yatta_kit_furina.json`, `yatta_kit_mona.json`, `yatta_kit_traveler_anemo.json`

**Interfaces:**
- Consumes: `app.gamedata.traveler` (`is_traveler`, `element_of(element_id) -> str`, `BODY_IDS`).
- Produces (pure):
  - `yatta_key(character_id: int, traveler_body: str) -> str`
  - `parse_kit(payload: dict) -> dict` with shape:
    `{"talents": [{"name", "icon", "role": "normal"|"skill"|"burst"|"other", "cooldown": float|None, "cost": int|None, "description": [[{"text", "color", "italic"}]], "scaling": [{"label", "values": [str]}]}], "passives": [{"name", "icon", "description"}], "constellations": [{"index": 1..6, "name", "icon", "description", "raises": "normal"|"skill"|"burst"|None}]}`
  - `segments(text: str) -> list[list[dict]]`, `fill(template: str, params: list[float]) -> str`
  - `YATTA_AVATAR_DETAIL_URL = "https://gi.yatta.moe/api/v2/en/avatar/{key}"`

- [ ] **Step 1: Record trimmed fixtures (public game data only)**

Run once from `backend/` (writes three files, keeping only `id`, `name`, `element`, `talent`, `constellation`):

```bash
<python> -I - <<'EOF'
import json, urllib.request
for key, name in [("10000089", "furina"), ("10000041", "mona"), ("10000005-anemo", "traveler_anemo")]:
    req = urllib.request.Request(f"https://gi.yatta.moe/api/v2/en/avatar/{key}", headers={"User-Agent": "AdAstra-tests"})
    data = json.load(urllib.request.urlopen(req, timeout=30))["data"]
    keep = {k: data[k] for k in ("id", "name", "element", "talent", "constellation")}
    for t in keep["talent"].values():
        t.pop("advancedProps", None)
        for lv in (t.get("promote") or {}).values():
            lv.pop("costItems", None); lv.pop("coinCost", None)
    with open(f"tests/fixtures/yatta_kit_{name}.json", "w", encoding="utf-8") as f:
        json.dump({"response": 200, "data": keep}, f, ensure_ascii=False, indent=1)
EOF
```

Check: each file has `data.talent` and `data.constellation`; `grep -c "800000\|ltoken\|@" tests/fixtures/yatta_kit_*.json` finds no UID, cookie or email.

- [ ] **Step 2: Write failing parser tests**

Create `backend/tests/test_kit_parse.py`:

```python
from app.gamedata.kit import fill, parse_kit, segments, yatta_key
from helpers import load_fixture


def kit(name):
    return parse_kit(load_fixture(f"yatta_kit_{name}.json"))


def test_furina_roles_and_scaling():
    k = kit("furina")
    roles = [(t["role"], t["name"]) for t in k["talents"]]
    assert roles == [("normal", "Soloist's Solicitation"), ("skill", "Salon Solitaire"),
                     ("burst", "Let the People Rejoice")]
    skill = k["talents"][1]
    assert skill["icon"] == "Skill_S_Furina_01" and skill["cooldown"] == 20.0 and skill["cost"] is None
    assert k["talents"][2]["cost"] == 60
    row = next(r for r in skill["scaling"] if r["label"] == "Ousia Bubble DMG")
    assert len(row["values"]) == 15 and row["values"][0].endswith("% Max HP")
    assert [p["name"] for p in k["passives"]][:2] == ["Endless Waltz", "Unheard Confession"]


def test_furina_constellations_raise_by_link():
    k = kit("furina")
    assert [c["index"] for c in k["constellations"]] == [1, 2, 3, 4, 5, 6]
    raises = {c["index"]: c["raises"] for c in k["constellations"]}
    assert raises == {1: None, 2: None, 3: "burst", 4: None, 5: "skill", 6: None}


def test_mona_sprint_is_other_and_raises_by_text():
    k = kit("mona")
    assert [t["role"] for t in k["talents"]] == ["normal", "skill", "other", "burst"]
    raises = {c["index"]: c["raises"] for c in k["constellations"]}
    assert raises[3] == "burst" and raises[5] == "skill"
    assert len(k["passives"]) == 4


def test_traveler_link_markup_keeps_text():
    k = kit("traveler_anemo")
    text = "".join(s["text"] for line in k["talents"][0]["description"] for s in line)
    assert "{LINK" not in text and "<color" not in text


def test_segments_colour_italic_and_lines():
    out = segments("Deal <color=#80C0FFFF>Hydro DMG</color>.\\nThen <i>rest</i>{LINK#N1}buffs{/LINK}")
    assert out == [
        [{"text": "Deal ", "color": None, "italic": False}, {"text": "Hydro DMG", "color": "#80C0FF", "italic": False},
         {"text": ".", "color": None, "italic": False}],
        [{"text": "Then ", "color": None, "italic": False}, {"text": "rest", "color": None, "italic": True},
         {"text": "buffs", "color": None, "italic": False}],
    ]


def test_fill_formats():
    p = [0.114064, 18, 0.01, 300, 0.0007, 1.5]
    assert fill("{param1:F1P} Max HP", p) == "11.4% Max HP"
    assert fill("{param2:F1}s", p) == "18.0s"
    assert fill("{param4:I}", p) == "300"
    assert fill("{param5:F2P}", p) == "0.07%"
    assert fill("{param3:P}/{param6:F2}", p) == "1%/1.50"
    assert fill("{param9:F1P}", p) == "?"                   # missing param
    assert fill("{param1:ZZ}", p) == "0.114064"             # unknown format prints the raw number


def test_skips_malformed_entries():
    payload = load_fixture("yatta_kit_furina.json")
    payload["data"]["talent"]["99"] = {"type": 2}            # no name
    payload["data"]["constellation"]["9"] = None
    k = parse_kit(payload)
    assert len(k["passives"]) == 3 and len(k["constellations"]) == 6


def test_yatta_key():
    assert yatta_key(10000089, "girl") == "10000089"
    assert yatta_key(1000000502, "girl") == "10000007-anemo"
    assert yatta_key(1000000503, "boy") == "10000005-geo"
```

Note for the implementer: confirm the exact passive names and counts against the recorded fixtures (Yatta may add passives in later game versions); adjust only the expected literals, not the rules.

- [ ] **Step 3: Run them to verify they fail**

Run: `<python> -m pytest -q tests/test_kit_parse.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.gamedata.kit'`.

- [ ] **Step 4: Implement `backend/app/gamedata/kit.py` (parser part)**

```python
"""Talents, passives and constellations per character from Yatta (gi.yatta.moe avatar/<id>), parsed to plain
text segments and pre-formatted scaling values (sub-project 5)."""
from __future__ import annotations

import re

from app.gamedata.traveler import BODY_IDS, element_of, is_traveler

YATTA_AVATAR_DETAIL_URL = "https://gi.yatta.moe/api/v2/en/avatar/{key}"

_PARAM = re.compile(r"\{param(\d+):([A-Za-z0-9]+)\}")
_TOKEN = re.compile(
    r"<color=#([0-9A-Fa-f]{6})[0-9A-Fa-f]{0,2}>|(</color>)|(<i>)|(</i>)|\{[A-Z_]+#[^}]*\}|\{/[A-Z_]+\}|<[^>]*>")


def yatta_key(character_id: int, traveler_body: str) -> str:
    if not is_traveler(character_id):
        return str(character_id)
    body = BODY_IDS.get(traveler_body, BODY_IDS["girl"])
    return f"{body}-{element_of(character_id).lower()}"


def _fmt(v: float, spec: str) -> str:
    pct = spec.endswith("P")
    core = spec[:-1] if pct else spec
    if core == "I":
        return str(int(round(v)))
    if core == "":
        digits = 0
    elif core.startswith("F") and core[1:].isdigit():
        digits = int(core[1:])
    else:
        return str(v)
    x = v * 100 if pct else v
    return f"{x:.{digits}f}" + ("%" if pct else "")


def fill(template: str, params: list[float]) -> str:
    def one(m: re.Match) -> str:
        i = int(m.group(1)) - 1
        if i < 0 or i >= len(params):
            return "?"
        return _fmt(float(params[i]), m.group(2))
    return _PARAM.sub(one, template)


def segments(text: str) -> list[list[dict]]:
    """Yatta markup -> lines of {text, color, italic}. Plain text only; unknown tags are dropped."""
    text = (text or "").replace("\\n", "\n")
    lines: list[list[dict]] = [[]]
    color: str | None = None
    italic = False

    def emit(chunk: str) -> None:
        for n, part in enumerate(chunk.split("\n")):
            if n:
                lines.append([])
            if part:
                lines[-1].append({"text": part, "color": color, "italic": italic})

    pos = 0
    for m in _TOKEN.finditer(text):
        emit(text[pos:m.start()])
        if m.group(1):
            color = "#" + m.group(1).upper()
        elif m.group(2):
            color = None
        elif m.group(3):
            italic = True
        elif m.group(4):
            italic = False
        pos = m.end()
    emit(text[pos:])
    return lines


def _plain(text: str) -> str:
    return "".join(s["text"] for line in segments(text) for s in line)


def _num(v) -> float | None:
    try:
        return None if v in (None, "", "None") else float(v)
    except (TypeError, ValueError):
        return None


def _scaling(promote: dict | None) -> list[dict]:
    if not promote:
        return []
    levels = sorted(promote, key=int)
    first = promote[levels[0]].get("description") or []
    rows = []
    for i, template in enumerate(first):
        if not template or "|" not in template:
            continue
        label = template.split("|", 1)[0]
        values = []
        for lv in levels:
            desc = promote[lv].get("description") or []
            line = desc[i] if i < len(desc) else ""
            values.append(fill(line.split("|", 1)[1], promote[lv].get("params") or []) if "|" in line else "")
        rows.append({"label": label, "values": values})
    return rows


def _entries(d: dict | None) -> list[dict]:
    out = []
    for k in sorted((d or {}), key=lambda x: int(x) if str(x).isdigit() else 10**6):
        v = d[k]
        if isinstance(v, dict) and v.get("name"):
            out.append(v)
    return out


def parse_kit(payload: dict) -> dict:
    data = payload["data"]
    talents, passives = [], []
    normal_seen = skill_seen = burst_seen = False
    raw_active: list[tuple[dict, dict]] = []
    for t in _entries(data.get("talent")):
        kind = int(t.get("type", -1)) if str(t.get("type", "")).lstrip("-").isdigit() else -1
        if kind == 2:
            passives.append({"name": t["name"], "icon": t.get("icon") or None,
                             "description": segments(t.get("description", ""))})
            continue
        if kind not in (0, 1):
            continue
        cooldown = _num(t.get("cooldown"))
        if kind == 1 and not burst_seen:
            role, burst_seen = "burst", True
        elif kind == 0 and not normal_seen:
            role, normal_seen = "normal", True
        elif kind == 0 and cooldown is not None and not skill_seen:
            role, skill_seen = "skill", True
        else:
            role = "other"
        cost = _num(t.get("cost"))
        item = {"name": t["name"], "icon": t.get("icon") or None, "role": role, "cooldown": cooldown,
                "cost": int(cost) if cost is not None else None,
                "description": segments(t.get("description", "")), "scaling": _scaling(t.get("promote"))}
        talents.append(item)
        raw_active.append((t, item))

    raises: dict[int, str] = {}
    for t, item in raw_active:
        if item["role"] not in ("skill", "burst"):
            continue
        linked = t.get("linkedConstellations") or {}
        for p in (linked.get("prop") or []) if isinstance(linked, dict) else []:
            if p.get("type") == "level":
                raises[int(p["id"]) + 1] = item["role"]

    constellations = []
    for n, c in enumerate(_entries(data.get("constellation")), start=1):
        if n > 6:
            break
        constellations.append({"index": n, "name": c["name"], "icon": c.get("icon") or None,
                               "description": segments(c.get("description", "")), "raises": raises.get(n)})
    for c in constellations:                                   # no link data (e.g. Mona): match the text
        if c["raises"] is None and c["index"] in (3, 5):
            text = _plain_lines(c["description"])
            for t, item in raw_active:
                if item["role"] in ("skill", "burst") and f"Increases the Level of {item['name']}" in text:
                    c["raises"] = item["role"]
    return {"talents": talents, "passives": passives, "constellations": constellations}


def _plain_lines(lines: list[list[dict]]) -> str:
    return "".join(s["text"] for line in lines for s in line)
```

`_plain` is unused by the parser itself; delete it if the linter flags it.

- [ ] **Step 5: Run the parser tests**

Run: `<python> -m pytest -q tests/test_kit_parse.py`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/gamedata/kit.py backend/tests/test_kit_parse.py backend/tests/fixtures/yatta_kit_*.json
git commit -m "feat(kit): parse Yatta talents, passives and constellations into safe text segments"
```

---

### Task 3: Kit cache and endpoint, devseed kits

**Files:**
- Modify: `backend/app/gamedata/kit.py`, `backend/app/context.py`, `backend/app/api/characters.py`, `backend/app/devseed.py`, `backend/tests/helpers.py`
- Test: `backend/tests/test_api_kit.py` (create), `backend/tests/test_devseed.py`

**Interfaces:**
- Consumes: `parse_kit`, `yatta_key`, `YATTA_AVATAR_DETAIL_URL` (Task 2); `GameCharacterKit` (Task 1).
- Produces:
  - `async fetch_kit(http, key) -> dict`
  - `async load_kit(session_factory, http, character_id, key, offline, lock, now) -> dict` returning `{"state": "fresh"|"stale"|"unavailable", "kit": dict | None}`
  - `AppContext.kit_locks: dict[int, asyncio.Lock]`
  - `GET /api/characters/{slug}/kit`
  - `helpers.make_client(..., offline=True)` parameter; `helpers.kit_transport(fail=False, calls=None)`.

- [ ] **Step 1: Add test helpers**

In `backend/tests/helpers.py`, add an `offline: bool = True` parameter to `make_client` and pass `offline=offline` to `create_app` instead of `offline=True`. Then add:

```python
def kit_transport(fail: bool = False, calls: list | None = None) -> httpx.MockTransport:
    furina = load_fixture("yatta_kit_furina.json")
    traveler = load_fixture("yatta_kit_traveler_anemo.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if "/avatar/" not in path:
            return httpx.Response(404)
        if calls is not None:
            calls.append(path.rsplit("/", 1)[1])
        if fail:
            return httpx.Response(500)
        return httpx.Response(200, json=traveler if "-" in path.rsplit("/", 1)[1] else furina)

    return httpx.MockTransport(handler)
```

- [ ] **Step 2: Write failing endpoint tests**

Create `backend/tests/test_api_kit.py`:

```python
import asyncio
from datetime import timedelta

from app.db.models import GameCharacterKit
from app.gamedata.kit import load_kit
from app.timeutil import utcnow
from helpers import kit_transport, make_client, seed_game
from test_api_characters import sf_for


def test_kit_fetches_once_then_serves_cache(paths):
    sf = sf_for(paths)
    seed_game(sf)
    calls: list = []
    with make_client(paths, transport=kit_transport(calls=calls), offline=False) as client:
        first = client.get("/api/characters/furina/kit").json()
        second = client.get("/api/characters/furina/kit").json()
    assert first["state"] == "fresh" and first["kit"]["talents"][1]["name"] == "Salon Solitaire"
    assert second == first and calls == ["10000089"]


def test_kit_stale_cache_is_refetched_and_failure_serves_stale(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with sf.begin() as s:
        s.add(GameCharacterKit(character_id=10000089, data={"talents": [], "passives": [], "constellations": []},
                               fetched_at=utcnow() - timedelta(days=30)))
    with make_client(paths, transport=kit_transport(fail=True), offline=False) as client:
        body = client.get("/api/characters/furina/kit").json()
    assert body == {"state": "stale", "kit": {"talents": [], "passives": [], "constellations": []}}
    with make_client(paths, transport=kit_transport(), offline=False) as client:
        assert client.get("/api/characters/furina/kit").json()["state"] == "fresh"


def test_kit_unavailable_without_cache(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with make_client(paths, transport=kit_transport(fail=True), offline=False) as client:
        assert client.get("/api/characters/furina/kit").json() == {"state": "unavailable", "kit": None}
        assert client.get("/api/characters/nobody/kit").status_code == 404


def test_kit_offline_never_fetches(paths):
    sf = sf_for(paths)
    seed_game(sf)
    calls: list = []
    with make_client(paths, transport=kit_transport(calls=calls)) as client:   # offline=True
        assert client.get("/api/characters/furina/kit").json() == {"state": "unavailable", "kit": None}
    assert calls == []


def test_traveler_kit_uses_body_and_element_key(paths):
    sf = sf_for(paths)
    seed_game(sf)
    calls: list = []
    with make_client(paths, transport=kit_transport(calls=calls), offline=False) as client:
        assert client.get("/api/characters/anemo-traveler/kit").json()["state"] == "fresh"
    assert calls == ["10000007-anemo"]


def test_concurrent_loads_fetch_once(session_factory):
    import httpx
    seed_game(session_factory)
    calls: list = []

    async def run():
        http = httpx.AsyncClient(transport=kit_transport(calls=calls))
        lock = asyncio.Lock()
        a, b = await asyncio.gather(*[load_kit(session_factory, http, 10000089, "10000089", False, lock, utcnow())
                                      for _ in range(2)])
        await http.aclose()
        return a, b

    a, b = asyncio.run(run())
    assert a["state"] == b["state"] == "fresh" and len(calls) == 1
```

- [ ] **Step 3: Run them to verify they fail**

Run: `<python> -m pytest -q tests/test_api_kit.py`
Expected: FAIL with `ImportError: cannot import name 'load_kit'`.

- [ ] **Step 4: Implement fetching and caching in `backend/app/gamedata/kit.py`**

Add at the top: `import asyncio`, `from datetime import datetime, timedelta`, `import httpx`, `from sqlalchemy.orm import sessionmaker`, `from app.config import GAMEDATA_MAX_AGE_DAYS`, `from app.db.models import GameCharacterKit`. Then:

```python
FETCH_ERRORS = (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError)


async def fetch_kit(http: httpx.AsyncClient, key: str) -> dict:
    response = await http.get(YATTA_AVATAR_DETAIL_URL.format(key=key), timeout=30)
    response.raise_for_status()
    return response.json()


async def load_kit(session_factory: sessionmaker, http: httpx.AsyncClient, character_id: int, key: str,
                   offline: bool, lock: asyncio.Lock, now: datetime) -> dict:
    """Cached kit if fresh; else fetch (never when offline). Fetch failure falls back to the stale copy."""
    async with lock:
        with session_factory() as s:
            row = s.get(GameCharacterKit, character_id)
            cached = (row.data, row.fetched_at) if row is not None else None
        if cached is not None and now - cached[1] <= timedelta(days=GAMEDATA_MAX_AGE_DAYS):
            return {"state": "fresh", "kit": cached[0]}
        if not offline:
            try:
                kit = parse_kit(await fetch_kit(http, key))
            except FETCH_ERRORS:
                kit = None
            if kit is not None:
                with session_factory.begin() as s:
                    s.merge(GameCharacterKit(character_id=character_id, data=kit, fetched_at=now))
                return {"state": "fresh", "kit": kit}
        if cached is not None:
            return {"state": "stale", "kit": cached[0]}
        return {"state": "unavailable", "kit": None}
```

In `backend/app/context.py` add `import asyncio`, `from dataclasses import dataclass, field`, and a last field on `AppContext`:

```python
    kit_locks: dict[int, asyncio.Lock] = field(default_factory=dict)
```

In `backend/app/api/characters.py` add imports `from app.gamedata.kit import load_kit, yatta_key` and `from app.settings.store import get_setting`, then:

```python
@router.get("/characters/{slug}/kit")
async def get_kit(slug: str, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        g = s.scalar(select(GameCharacter).where(GameCharacter.slug == slug))
        if g is None:
            raise HTTPException(404, "Unknown character")
        cid, body = g.id, str(get_setting(s, "traveler_body"))
    lock = ctx.kit_locks.setdefault(cid, asyncio.Lock())
    return await load_kit(ctx.session_factory, ctx.http, cid, yatta_key(cid, body), ctx.offline, lock, utcnow())
```

(add `import asyncio` at the top). The route must be declared before nothing that would shadow it; `/characters/{slug}/kit` does not clash with `/characters/{slug}`.

- [ ] **Step 5: Run them**

Run: `<python> -m pytest -q tests/test_api_kit.py`
Expected: PASS.

- [ ] **Step 6: Seed made-up kits in devseed (failing test first)**

Append to `backend/tests/test_devseed.py`:

```python
def test_devseed_stores_a_kit_per_character(tmp_path):
    from app.config import Paths
    from app.db.engine import make_engine, make_session_factory
    from app.db.models import GameCharacter, GameCharacterKit
    from app.devseed import seed
    seed(tmp_path)
    engine = make_engine(Paths(tmp_path).db_file)
    with make_session_factory(engine)() as s:
        chars = s.query(GameCharacter).count()
        kits = s.query(GameCharacterKit).all()
        assert len(kits) == chars
        k = kits[0].data
        assert [t["role"] for t in k["talents"]] == ["normal", "skill", "burst"]
        assert len(k["constellations"]) == 6 and k["constellations"][2]["raises"] == "skill"
    engine.dispose()
```

Run: `<python> -m pytest -q tests/test_devseed.py` → FAIL (`len(kits) == 0`).

In `backend/app/devseed.py` add `GameCharacterKit` to the models import and, inside `seed()` after the `GameCharacter` loop:

```python
        for cid, name, *_rest in CHARACTERS:
            s.add(GameCharacterKit(character_id=cid, data=demo_kit(name), fetched_at=now))
```

and a module-level helper (made-up text, real public icon names that `/api/img` resolves at runtime):

```python
def _seg(text: str) -> list[list[dict]]:
    return [[{"text": text, "color": None, "italic": False}]]


def demo_kit(name: str) -> dict:
    """Made-up kit so the offline e2e server never calls Yatta (sub-project 5)."""
    def scale(label: str) -> dict:
        return {"label": label, "values": [f"{10 + n}.0%" for n in range(15)]}
    talents = [
        {"name": f"{name} Strike", "icon": "Skill_A_01", "role": "normal", "cooldown": None, "cost": None,
         "description": _seg("Demo normal attack text."), "scaling": [scale("1-Hit DMG")]},
        {"name": f"{name} Skill", "icon": "Skill_S_Furina_01", "role": "skill", "cooldown": 10.0, "cost": None,
         "description": [[{"text": "Deals ", "color": None, "italic": False},
                          {"text": "demo DMG", "color": "#80C0FF", "italic": False}]],
         "scaling": [scale("Skill DMG")]},
        {"name": f"{name} Burst", "icon": "Skill_E_Furina_01", "role": "burst", "cooldown": 15.0, "cost": 60,
         "description": _seg("Demo burst text."), "scaling": [scale("Burst DMG")]},
    ]
    passives = [{"name": f"{name} Passive {n}", "icon": "UI_Talent_S_Furina_05", "description": _seg("Demo passive.")}
                for n in (1, 2, 3)]
    raises = {3: "skill", 5: "burst"}
    constellations = [{"index": n, "name": f"{name} C{n}", "icon": "UI_Talent_S_Furina_01",
                       "description": _seg(f"Demo constellation {n}."), "raises": raises.get(n)} for n in range(1, 7)]
    return {"talents": talents, "passives": passives, "constellations": constellations}
```

Run: `<python> -m pytest -q tests/test_devseed.py` → PASS.

- [ ] **Step 7: Full backend suite**

Run: `<python> -m pytest -q`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add backend
git commit -m "feat(kit): cached GET /api/characters/{slug}/kit with per-character lock; devseed demo kits"
```

---

### Task 4: Frontend foundations (types, kit helpers, element hex, tint, wide routes, Settings)

**Files:**
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/elements.ts`, `frontend/src/lib/elements.test.ts`, `frontend/src/lib/starfield.ts`, `frontend/src/lib/starfield.test.ts`, `frontend/src/lib/Starfield.svelte`, `frontend/src/lib/appearance.svelte.ts`, `frontend/src/lib/nav.ts`, `frontend/src/lib/nav.test.ts`, `frontend/src/routes/+layout.svelte`, `frontend/src/routes/settings/+page.svelte`, `frontend/e2e/settings.spec.ts`
- Create: `frontend/src/lib/kit.ts`, `frontend/src/lib/kit.test.ts`

**Interfaces:**
- Consumes: Task 1 payload (`priority`, 7-key `targets`), Task 3 kit response.
- Produces:
  - Types `Targets` (+ `constellation?: number | null; refinement?: number | null`), `Character.priority: number | null`, `Segment`, `KitTalent`, `KitPassive`, `KitConstellation`, `Kit`, `KitResponse`, `TalentRole = 'normal' | 'skill' | 'burst'`.
  - `api.characterKit(slug): Promise<KitResponse>`; `saveSettings` without `default_targets`; `Settings` without `default_targets`.
  - `lib/kit.ts`: `raisedBy(kit, role): number | null`, `boost(kit, role, constellation): number`, `effectiveLevel(base, kit, role, constellation): number`, `maxLevel(kit, role, owned, target): number`, `scalingColumns(kit, role, now, target): Column[]`, `valueAt(row, level): string`, `buildValue(stored, current): number`, `isReached(current, target): boolean`, `type Column = { key: 'now' | 'target' | 'max'; label: string; level: number }`.
  - `elements.ts`: `ELEMENT_HEX`, `elementHex(name): string | null`.
  - `starfield.ts`: `layerColors(tint: string | null): string[]`, `nebula(tint: string | null): string`.
  - `appearance.tint: string | null` (`$state`).
  - `Starfield` prop `tint` and attribute `data-tint`.
  - `isWide('/characters/<slug>[/...]') === true`.

- [ ] **Step 1: Write failing vitest tests**

Create `frontend/src/lib/kit.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { boost, buildValue, effectiveLevel, isReached, maxLevel, raisedBy, scalingColumns, valueAt } from './kit';
import type { Kit } from './types';

const seg = (text: string) => [[{ text, color: null, italic: false }]];
const KIT: Kit = {
	talents: [
		{ name: 'N', icon: null, role: 'normal', cooldown: null, cost: null, description: seg('n'), scaling: [] },
		{ name: 'S', icon: null, role: 'skill', cooldown: 10, cost: null, description: seg('s'),
			scaling: [{ label: 'DMG', values: Array.from({ length: 15 }, (_, i) => `${i + 1}%`) }] },
		{ name: 'B', icon: null, role: 'burst', cooldown: 15, cost: 60, description: seg('b'), scaling: [] }
	],
	passives: [],
	constellations: [1, 2, 3, 4, 5, 6].map((index) => ({
		index, name: `C${index}`, icon: null, description: seg('c'),
		raises: index === 3 ? ('burst' as const) : index === 5 ? ('skill' as const) : null
	}))
};

describe('kit levels', () => {
	it('finds which constellation raises a talent', () => {
		expect(raisedBy(KIT, 'skill')).toBe(5);
		expect(raisedBy(KIT, 'normal')).toBeNull();
		expect(raisedBy(null, 'skill')).toBeNull();
	});
	it('adds 3 only when that constellation is owned', () => {
		expect(boost(KIT, 'skill', 4)).toBe(0);
		expect(boost(KIT, 'skill', 5)).toBe(3);
		expect(effectiveLevel(9, KIT, 'burst', 3)).toBe(12);
	});
	it('max is 13 when the raising constellation is owned or targeted', () => {
		expect(maxLevel(KIT, 'skill', 2, 2)).toBe(10);
		expect(maxLevel(KIT, 'skill', 2, 6)).toBe(13);
		expect(maxLevel(KIT, 'normal', 6, 6)).toBe(10);
	});
	it('builds now / target / max columns with effective levels', () => {
		expect(scalingColumns(KIT, 'skill', { base: 6, constellation: 2 }, { base: 9, constellation: 6 })).toEqual([
			{ key: 'now', label: 'Lv 6 (now)', level: 6 },
			{ key: 'target', label: 'Lv 12 (target)', level: 12 },
			{ key: 'max', label: 'Lv 13 (max)', level: 13 }
		]);
		expect(scalingColumns(KIT, 'skill', null, null)).toEqual([{ key: 'max', label: 'Lv 10 (max)', level: 10 }]);
	});
	it('reads a value at a level, with a dash past the end', () => {
		const row = KIT.talents[1].scaling[0];
		expect(valueAt(row, 1)).toBe('1%');
		expect(valueAt(row, 16)).toBe('—');
	});
});

describe('build values', () => {
	it('a stored null target means same as current', () => {
		expect(buildValue(null, 2)).toBe(2);
		expect(buildValue(undefined, 2)).toBe(2);
		expect(buildValue(6, 2)).toBe(6);
	});
	it('a target at or below current is reached', () => {
		expect(isReached(90, 80)).toBe(true);
		expect(isReached(80, 80)).toBe(true);
		expect(isReached(70, 80)).toBe(false);
	});
});
```

Append to `frontend/src/lib/elements.test.ts`:

```ts
import { ELEMENT_HEX, elementHex } from './elements';

describe('elementHex', () => {
	it('maps every element to a hex colour and unknowns to null', () => {
		expect(Object.keys(ELEMENT_HEX).sort()).toEqual(['Anemo', 'Cryo', 'Dendro', 'Electro', 'Geo', 'Hydro', 'Pyro']);
		expect(elementHex('Hydro')).toBe('#4cc2f1');
		expect(elementHex(null)).toBeNull();
		expect(elementHex('Light')).toBeNull();
	});
});
```

(If `describe`/`expect`/`it` are not yet imported at the top of `elements.test.ts`, add them to its existing vitest import.)

Append to `frontend/src/lib/starfield.test.ts`:

```ts
import { LAYERS, layerColors, nebula } from './starfield';

describe('tint', () => {
	it('keeps the fine layer white and tints the two nearer layers', () => {
		expect(layerColors(null)).toEqual(LAYERS.map((l) => l.color));
		expect(layerColors('#4cc2f1')).toEqual(['#ffffff', '#4cc2f1', '#4cc2f1']);
	});
	it('tints the nebula', () => {
		expect(nebula(null)).toContain('rgba(59, 47, 107');
		expect(nebula('#ef7a4a')).toContain('#ef7a4a');
	});
});
```

In `frontend/src/lib/nav.test.ts` replace `expect(isWide('/characters/bennett')).toBe(false);` with:

```ts
		expect(isWide('/characters/bennett')).toBe(true);
		expect(isWide('/characters/bennett/guide')).toBe(true);
		expect(isWide('/charactersx')).toBe(false);
```

- [ ] **Step 2: Run them to verify they fail**

Run (from `frontend/`): `npx vitest run src/lib/kit.test.ts src/lib/elements.test.ts src/lib/starfield.test.ts src/lib/nav.test.ts`
Expected: FAIL (missing module `./kit`, missing exports).

- [ ] **Step 3: Types and API**

In `frontend/src/lib/types.ts`:

```ts
export interface Targets {
	level: number; normal: number; skill: number; burst: number; weapon_level: number;
	constellation?: number | null; refinement?: number | null;
}
export type TalentRole = 'normal' | 'skill' | 'burst';
export interface Segment { text: string; color: string | null; italic: boolean }
export interface ScaleRow { label: string; values: string[] }
export interface KitTalent {
	name: string; icon: string | null; role: TalentRole | 'other'; cooldown: number | null; cost: number | null;
	description: Segment[][]; scaling: ScaleRow[];
}
export interface KitPassive { name: string; icon: string | null; description: Segment[][] }
export interface KitConstellation {
	index: number; name: string; icon: string | null; description: Segment[][]; raises: TalentRole | null;
}
export interface Kit { talents: KitTalent[]; passives: KitPassive[]; constellations: KitConstellation[] }
export interface KitResponse { state: 'fresh' | 'stale' | 'unavailable'; kit: Kit | null }
```

Add `priority: number | null;` to `Character` (after `planned_weapon_id`). Delete `default_targets: Targets;` from `Settings`.

In `frontend/src/lib/api.ts`: add after `character:`

```ts
	characterKit: (slug: string) => request<KitResponse>('GET', `/characters/${encodeURIComponent(slug)}/kit`),
```

(import `KitResponse`), and remove `default_targets?: Targets;` from `saveSettings`' body type.

- [ ] **Step 4: `frontend/src/lib/kit.ts`**

```ts
import type { Kit, ScaleRow, TalentRole } from './types';

export interface Column { key: 'now' | 'target' | 'max'; label: string; level: number }
export interface LevelPoint { base: number; constellation: number }

export function raisedBy(kit: Kit | null, role: TalentRole): number | null {
	return kit?.constellations.find((c) => c.raises === role)?.index ?? null;
}

export function boost(kit: Kit | null, role: TalentRole, constellation: number): number {
	const c = raisedBy(kit, role);
	return c !== null && constellation >= c ? 3 : 0;
}

export function effectiveLevel(base: number, kit: Kit | null, role: TalentRole, constellation: number): number {
	return base + boost(kit, role, constellation);
}

export function maxLevel(kit: Kit | null, role: TalentRole, owned: number, target: number): number {
	return 10 + boost(kit, role, Math.max(owned, target));
}

export function scalingColumns(kit: Kit | null, role: TalentRole, now: LevelPoint | null,
	target: LevelPoint | null): Column[] {
	const cols: Column[] = [];
	if (now) {
		const level = effectiveLevel(now.base, kit, role, now.constellation);
		cols.push({ key: 'now', label: `Lv ${level} (now)`, level });
	}
	if (target) {
		const level = effectiveLevel(target.base, kit, role, target.constellation);
		cols.push({ key: 'target', label: `Lv ${level} (target)`, level });
	}
	const max = maxLevel(kit, role, now?.constellation ?? 0, target?.constellation ?? 0);
	cols.push({ key: 'max', label: `Lv ${max} (max)`, level: max });
	return cols;
}

export function valueAt(row: ScaleRow, level: number): string {
	return row.values[level - 1] || '—';
}

/** A stored wish target of null (rows from before sub-project 5) means "same as current". */
export function buildValue(stored: number | null | undefined, current: number): number {
	return stored ?? current;
}

export function isReached(current: number, target: number): boolean {
	return target <= current;
}
```

- [ ] **Step 5: Element hex, starfield tint, appearance, wide routes**

`frontend/src/lib/elements.ts` — add:

```ts
/** Hex copies of the --pyro … --geo tokens, for places CSS variables cannot reach (SVG data URIs). */
export const ELEMENT_HEX: Record<string, string> = {
	Pyro: '#ef7a4a', Hydro: '#4cc2f1', Anemo: '#5fd3b8', Electro: '#b38cf0',
	Dendro: '#9bd25a', Cryo: '#9fe0ef', Geo: '#f0c45a'
};

export function elementHex(name: string | null | undefined): string | null {
	return (name && ELEMENT_HEX[name]) || null;
}
```

`frontend/src/lib/starfield.ts` — add:

```ts
/** Layer colours: the fine far layer stays white; the two nearer layers take the tint (sub-project 5). */
export function layerColors(tint: string | null): string[] {
	return LAYERS.map((l, i) => (tint && i > 0 ? tint : l.color));
}

export function nebula(tint: string | null): string {
	if (!tint) {
		return 'radial-gradient(ellipse 50% 35% at 70% 30%, rgba(59, 47, 107, 0.25), transparent 70%), ' +
			'radial-gradient(ellipse 45% 45% at 20% 75%, rgba(29, 74, 107, 0.25), transparent 70%)';
	}
	return `radial-gradient(ellipse 50% 35% at 70% 30%, ${tint}33, transparent 70%), ` +
		`radial-gradient(ellipse 45% 45% at 20% 75%, ${tint}26, transparent 70%)`;
}
```

`frontend/src/lib/Starfield.svelte` — props become `let { animated, tint = null }: { animated: boolean; tint?: string | null } = $props();`; import `layerColors, nebula`; replace the `tiles` constant with:

```ts
	const stars = LAYERS.map((l) => makeStars(l.seed, l.count, l.r[0], l.r[1]));
	const tiles = $derived(
		layerColors(tint).map((color, i) => ({ ...LAYERS[i], image: starTile(stars[i], color) }))
	);
```

and the markup root/nebula to:

```svelte
<div class="starfield" class:paused={!moving} data-testid="starfield" data-animated={String(moving)}
	data-tint={tint ?? ''} aria-hidden="true" style="--tile-w: {TILE.w}px; --tile-h: {TILE.h}px">
	<div class="nebula" style="background: {nebula(tint)}"></div>
```

Delete the `background:` declaration from the `.nebula` CSS rule (keep `position` and `inset`).

`frontend/src/lib/appearance.svelte.ts` — add to `AppearanceStore`: `tint = $state<string | null>(null);` (with a comment: "Element colour set by the character page; null elsewhere").

`frontend/src/routes/+layout.svelte` — `<Starfield animated={appearance.backgroundAnimated} tint={appearance.tint} />`.

`frontend/src/lib/nav.ts`:

```ts
export function isWide(pathname: string): boolean {
	return WIDE_ROUTES.some((r) => pathname === r) || pathname.startsWith('/characters/');
}
```

- [ ] **Step 6: Remove the Settings Planner block**

In `frontend/src/routes/settings/+page.svelte`: delete the `{ id: 'planner', label: 'Planner' },` index entry, the whole `<section class="panel group" id="planner" …>…</section>`, the `saveTargets` function, the `TargetsEditor` import, and `Targets` from the type import. In `frontend/e2e/settings.spec.ts` line 21 remove `'Planner', ` from the label list.

- [ ] **Step 7: Run checks**

Run: `npx vitest run` then `npm run check`
Expected: vitest PASS; `svelte-check` reports errors only in `routes/characters/[slug]/+page.svelte` if it still imports removed things — it does not (TargetsEditor is still present until Task 6), so expect 0 errors. If `svelte-check` flags the old detail page's `Targets` usage, leave it: Task 5 rewrites that file.

- [ ] **Step 8: Commit**

```bash
git add frontend
git commit -m "feat(fe): kit types and helpers, element hex, tinted starfield, wide character pages, drop default targets setting"
```

---

### Task 5: Character layout, banner and Current tab

**Files:**
- Create: `frontend/src/lib/characterPage.svelte.ts`, `frontend/src/lib/CharacterBanner.svelte`, `frontend/src/lib/TalentBadge.svelte`, `frontend/src/lib/ConstellationRow.svelte`, `frontend/src/routes/characters/[slug]/+layout.svelte`
- Rewrite: `frontend/src/routes/characters/[slug]/+page.svelte`
- Test: `frontend/e2e/characters.spec.ts`

**Interfaces:**
- Consumes: Task 4 types, `api.characterKit`, `elementHex`, `appearance.tint`, `isWide`; existing `GoalSwitch`, `TravelerElementCard`, `TagChip`, `imgSrc`, `elementStyle`, `sync.version`.
- Produces:
  - `CharacterPage` class (context): `c`, `kit`, `kitState`, `caps`, `error`, `saveError`, `load(slug)`, `loadKit(slug)`, `saveGoal(body)`; `setCharacterPage(p)`, `getCharacterPage()`.
  - `TalentBadge` props `{ icon: string | null; label: string; base: number; bonus?: number; target?: number | null; testid?: string }`.
  - `ConstellationRow` props `{ kit: Kit | null; owned: number; target?: number | null }`.
  - Test ids: `banner`, `tab-current`, `tab-build`, `tab-guide`, `current-level`, `current-constellation`, `talent-normal|skill|burst`, `in-teams`.

- [ ] **Step 1: Write the failing e2e tests**

Replace the first test and the two Traveler tests in `frontend/e2e/characters.spec.ts`, and add banner tests (keep the overview tests — unobtained section, pills, large tiles, sort — unchanged):

```ts
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
	await moved.getByRole('link', { name: 'Xiangling' }).click();
	await expect(page).toHaveURL(/\/characters\/xiangling$/);
	await expect(page.getByTestId('banner').getByRole('heading', { name: 'Xiangling' })).toBeVisible();
	await page.getByTestId('banner').getByRole('button', { name: 'None' }).click();     // restore
	await expect(page.getByTestId('banner').getByRole('button', { name: 'None' })).toHaveAttribute('aria-pressed', 'true');
});

test('banner shows the character, element tint and tabs', async ({ page }) => {
	await page.goto('/characters/furina');
	const banner = page.getByTestId('banner');
	await expect(banner.getByRole('heading', { name: 'Furina' })).toBeVisible();
	await expect(banner.getByText('Hydro')).toBeVisible();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-tint', '#4cc2f1');
	await expect(page.getByTestId('tab-current')).toHaveAttribute('aria-current', 'page');
	await expect(page.getByTestId('current-level')).toContainText('90');
	await expect(page.getByTestId('talent-skill')).toBeVisible();
	await expect(page.getByTestId('in-teams')).toBeVisible();
	await page.getByTestId('tab-build').click();
	await expect(page).toHaveURL(/\/characters\/furina\/build$/);
	await page.getByTestId('tab-guide').click();
	await expect(page).toHaveURL(/\/characters\/furina\/guide$/);
});

test('switching character updates the banner and tint; leaving clears the tint', async ({ page }) => {
	await page.goto('/characters/furina');
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-tint', '#4cc2f1');
	await page.goto('/characters/bennett');
	await expect(page.getByTestId('banner').getByRole('heading', { name: 'Bennett' })).toBeVisible();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-tint', '#ef7a4a');
	await page.getByRole('navigation', { name: 'Main' }).getByRole('link', { name: 'Characters', exact: true }).click();
	await expect(page).toHaveURL(/\/characters$/);
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-tint', '');
});

test('Traveler element card: unlock another element', async ({ page }) => {
	await page.goto('/characters/cryo-traveler');
	await expect(page.getByTestId('banner').getByRole('heading', { name: 'Cryo Traveler' })).toBeVisible();
	await expect(page.getByText('From HoYoLAB: current element')).toBeVisible();
	await page.goto('/characters/anemo-traveler');
	const toggle = page.getByRole('checkbox', { name: 'Unlocked' });
	await expect(toggle).not.toBeChecked();
	await toggle.check();
	await expect(page.getByTestId('current-level')).toContainText('90');
	await expect(page.getByTestId('current-constellation')).toContainText('C0');
	await toggle.uncheck();                                                          // restore
	await expect(toggle).not.toBeChecked();
});

test('Traveler element card: out-of-range talent snaps back to the saved value', async ({ page }) => {
	await page.goto('/characters/anemo-traveler');
	await page.getByRole('checkbox', { name: 'Unlocked' }).check();
	await expect(page.getByTestId('current-level')).toBeVisible();
	const normal = page.getByRole('spinbutton', { name: 'Normal attack' });
	await normal.fill('15');
	await normal.blur();
	await expect(normal).toHaveValue('10');
	await page.getByRole('checkbox', { name: 'Unlocked' }).uncheck();               // restore
});
```

(If unchecking "Unlocked" is not supported by `TravelerElementCard`, restore through the API instead: `await page.request.put('/api/traveler/1000000502', { data: { unlocked: false } })` — check `TravelerIn` in `backend/app/api/traveler.py` for the field name.)

- [ ] **Step 2: Run them to verify they fail**

Run (from `frontend/`): `npm run build && PYTHON=<python> npx playwright test e2e/characters.spec.ts`
Expected: FAIL (no `banner` test id).

- [ ] **Step 3: Context object `frontend/src/lib/characterPage.svelte.ts`**

```ts
import { getContext, setContext } from 'svelte';
import { api, errorMessage } from './api';
import type { CharacterDetail, Goal, Kit, KitResponse, Targets } from './types';

const KEY = Symbol('character-page');

/** Data shared by the character layout and its Current / Build / Guide tabs. */
export class CharacterPage {
	slug = $state('');
	c = $state<CharacterDetail | null>(null);
	kit = $state<Kit | null>(null);
	kitState = $state<KitResponse['state'] | 'loading'>('loading');
	caps = $state<number[]>([20, 40, 50, 60, 70, 80, 90]);
	error = $state<string | null>(null);
	saveError = $state<string | null>(null);

	async load(slug: string): Promise<void> {
		this.slug = slug;
		try {
			const [detail, settings] = await Promise.all([api.character(slug), api.settings()]);
			if (this.slug !== slug) return;            // a newer character was opened meanwhile
			this.c = detail;
			this.caps = settings.level_caps;
			this.error = null;
		} catch (e) {
			if (this.slug === slug) this.error = errorMessage(e);
		}
	}

	async loadKit(slug: string): Promise<void> {
		this.kitState = 'loading';
		try {
			const res = await api.characterKit(slug);
			if (this.slug !== slug) return;
			this.kit = res.kit;
			this.kitState = res.state;
		} catch {
			if (this.slug === slug) {
				this.kit = null;
				this.kitState = 'unavailable';
			}
		}
	}

	async saveGoal(body: { goal?: Goal; targets?: Targets; planned_weapon_id?: number | null }): Promise<void> {
		if (!this.c) return;
		try {
			await api.setGoal(this.c.id, body);
			this.saveError = null;
		} catch (e) {
			this.saveError = errorMessage(e);
		}
		await this.load(this.slug);
	}
}

export function setCharacterPage(p: CharacterPage): void {
	setContext(KEY, p);
}

export function getCharacterPage(): CharacterPage {
	return getContext<CharacterPage>(KEY);
}
```

- [ ] **Step 4: `frontend/src/lib/CharacterBanner.svelte`**

```svelte
<script lang="ts">
	import { page } from '$app/state';
	import GoalSwitch from './GoalSwitch.svelte';
	import { elementStyle } from './elements';
	import { imgSrc } from './img';
	import type { CharacterDetail, Goal } from './types';

	let { c, onGoal }: { c: CharacterDetail; onGoal: (g: Goal) => void } = $props();

	const base = $derived(`/characters/${c.slug}`);
	const tabs = $derived([
		{ id: 'current', label: 'Current', href: base },
		{ id: 'build', label: 'Build', href: `${base}/build` },
		{ id: 'guide', label: 'Guide', href: `${base}/guide` }
	]);
	const el = $derived(elementStyle(c.element));
</script>

<header class="banner" data-testid="banner">
	{#if imgSrc(c.splash)}<img class="art" src={imgSrc(c.splash)} alt="" />{/if}
	<div class="fade"></div>
	<div class="text">
		<h1>{c.name}</h1>
		<div class="meta">
			<span class="stars">{'★'.repeat(c.rarity || 0)}</span>
			{#if el.icon && imgSrc(el.icon)}<img class="el" src={imgSrc(el.icon)} alt="" />{/if}
			<span>{c.element ?? '—'}</span><span>·</span><span>{c.weapon_type ?? '—'}</span>
		</div>
		<div class="goal">
			<GoalSwitch goal={c.goal} onchange={onGoal} />
			{#if c.prefarming}<span class="muted">Pre-farming</span>{/if}
			{#if c.goal === 'build' && c.priority}<a class="prio" href="/">Priority #{c.priority}</a>{/if}
		</div>
	</div>
	<nav class="tabs" aria-label="Character sections">
		{#each tabs as t (t.id)}
			<a href={t.href} data-testid="tab-{t.id}" aria-current={page.url.pathname === t.href ? 'page' : undefined}>{t.label}</a>
		{/each}
	</nav>
</header>

<style>
	.banner { position: relative; height: 300px; border-radius: 14px; overflow: hidden; border: 1px solid var(--glass-border);
		background: var(--glass-bg); margin: 12px 0 16px; }
	.art { position: absolute; inset: 0; width: 100%; height: 100%; object-fit: cover; object-position: 62% 25%; }
	.fade { position: absolute; inset: 0; background: linear-gradient(90deg, rgba(7, 10, 20, 0.95) 0%,
		rgba(7, 10, 20, 0.75) 30%, rgba(7, 10, 20, 0) 62%), linear-gradient(0deg, rgba(7, 10, 20, 0.85), transparent 30%); }
	.text { position: relative; padding: 24px 28px; }
	h1 { font-size: 36px; margin: 0; color: var(--el, var(--cream)); text-shadow: 0 2px 12px rgba(0, 0, 0, 0.6); }
	.meta { display: flex; gap: 8px; align-items: center; margin-top: 6px; color: var(--cream); }
	.stars { color: var(--rarity-5); letter-spacing: 2px; }
	.el { width: 22px; height: 22px; }
	.goal { display: flex; gap: 10px; align-items: center; margin-top: 14px; }
	.prio { font-size: 12px; padding: 3px 10px; border-radius: 999px; border: 1px solid var(--glass-border); color: var(--text); text-decoration: none; }
	.tabs { position: absolute; left: 0; right: 0; bottom: 0; display: flex; gap: 4px; padding: 0 20px; }
	.tabs a { padding: 10px 18px; color: var(--muted); text-decoration: none; border-bottom: 2px solid transparent; }
	.tabs a[aria-current='page'] { color: var(--el, var(--gold)); border-bottom-color: var(--el, var(--gold)); }
	@media (max-width: 900px) {
		.banner { height: 220px; }
		.fade { background: linear-gradient(90deg, rgba(7, 10, 20, 0.95) 0%, rgba(7, 10, 20, 0.6) 70%),
			linear-gradient(0deg, rgba(7, 10, 20, 0.85), transparent 30%); }
		h1 { font-size: 26px; }
	}
</style>
```

- [ ] **Step 5: `TalentBadge.svelte` and `ConstellationRow.svelte`**

`frontend/src/lib/TalentBadge.svelte`:

```svelte
<script lang="ts">
	import { imgSrc } from './img';

	let { icon, label, base, bonus = 0, testid }: {
		icon: string | null; label: string; base: number; bonus?: number; testid?: string;
	} = $props();
</script>

<div class="badge" data-testid={testid}>
	<div class="ic">{#if imgSrc(icon)}<img src={imgSrc(icon)} alt="" />{/if}</div>
	<span class="lv" class:crown={base >= 10}>{base}{#if bonus}<small> +{bonus}</small>{/if}</span>
	<span class="label">{label}</span>
</div>

<style>
	.badge { display: flex; flex-direction: column; align-items: center; gap: 4px; width: 76px; text-align: center; }
	.ic { width: 52px; height: 52px; border-radius: 50%; background: rgba(255, 255, 255, 0.07);
		border: 1px solid var(--glass-border); display: flex; align-items: center; justify-content: center; }
	.ic img { width: 42px; height: 42px; }
	.lv { font-size: 16px; font-weight: 700; }
	.lv.crown { color: var(--gold); }
	.lv small { color: var(--el, var(--gold)); font-size: 12px; }
	.label { font-size: 11px; color: var(--muted); }
</style>
```

`frontend/src/lib/ConstellationRow.svelte`:

```svelte
<script lang="ts">
	import { imgSrc } from './img';
	import type { Kit } from './types';

	let { kit, owned, target = null }: { kit: Kit | null; owned: number; target?: number | null } = $props();
	const items = $derived(
		[1, 2, 3, 4, 5, 6].map((n) => ({ n, icon: kit?.constellations.find((c) => c.index === n)?.icon ?? null }))
	);
</script>

<div class="row">
	{#each items as it (it.n)}
		<div class="c" class:on={it.n <= owned} class:want={target !== null && it.n > owned && it.n <= target}
			title="C{it.n}">
			{#if imgSrc(it.icon)}<img src={imgSrc(it.icon)} alt="" />{:else}<span>{it.n}</span>{/if}
		</div>
	{/each}
</div>

<style>
	.row { display: flex; gap: 8px; flex-wrap: wrap; }
	.c { width: 40px; height: 40px; border-radius: 50%; background: rgba(255, 255, 255, 0.06);
		border: 1px solid var(--glass-border); display: flex; align-items: center; justify-content: center; color: var(--muted); }
	.c img { width: 32px; height: 32px; opacity: 0.25; filter: grayscale(1); }
	.c.on { border-color: var(--el, var(--gold)); }
	.c.on img { opacity: 1; filter: none; }
	.c.want { border: 1px dashed var(--el, var(--gold)); }
</style>
```

- [ ] **Step 6: Layout `frontend/src/routes/characters/[slug]/+layout.svelte`**

```svelte
<script lang="ts">
	import { page } from '$app/state';
	import { appearance } from '$lib/appearance.svelte';
	import CharacterBanner from '$lib/CharacterBanner.svelte';
	import { CharacterPage, setCharacterPage } from '$lib/characterPage.svelte';
	import { elementHex } from '$lib/elements';
	import { sync } from '$lib/sync.svelte';

	let { children } = $props();
	const p = new CharacterPage();
	setCharacterPage(p);

	$effect(() => {
		const slug = page.params.slug ?? '';
		void sync.version;
		p.load(slug);
	});

	$effect(() => {
		const slug = page.params.slug ?? '';
		p.loadKit(slug);
	});

	const hex = $derived(elementHex(p.c?.element));
	$effect(() => {
		appearance.tint = hex;
		return () => {
			appearance.tint = null;
		};
	});
</script>

<div class="character" style={hex ? `--el: ${hex}` : undefined}>
	<a href="/characters">← Characters</a>
	{#if p.error}
		<p class="error">{p.error}</p>
	{:else if !p.c || p.c.slug !== (page.params.slug ?? '')}
		<p class="muted">Loading…</p>
	{:else}
		<CharacterBanner c={p.c} onGoal={(g) => p.saveGoal({ goal: g })} />
		{#if p.saveError}<p class="error">{p.saveError}</p>{/if}
		{@render children()}
	{/if}
</div>

<style>
	.character :global(.card) { background: var(--glass-bg); border: 1px solid var(--glass-border); border-radius: 12px;
		padding: 12px 14px; box-shadow: var(--glass-highlight); }
	.character :global(.card h2) { margin: 0 0 10px; font-size: 12px; letter-spacing: 0.08em; color: var(--el, var(--muted)); }
	.character :global(.grid) { display: grid; grid-template-columns: 1.1fr 1fr 1fr; gap: 12px; }
	.character :global(.span2) { grid-column: span 2; }
	.character :global(.slot) { border: 1px dashed var(--glass-border); border-radius: 10px; padding: 12px; color: var(--muted); }
	@media (max-width: 1100px) {
		.character :global(.grid) { grid-template-columns: 1fr; }
		.character :global(.span2) { grid-column: auto; }
	}
</style>
```

Note the `p.c.slug !== slug` guard: while a new character loads, the old one is not shown under the new URL.

- [ ] **Step 7: Current tab — rewrite `frontend/src/routes/characters/[slug]/+page.svelte`**

```svelte
<script lang="ts">
	import { getCharacterPage } from '$lib/characterPage.svelte';
	import ConstellationRow from '$lib/ConstellationRow.svelte';
	import { imgSrc } from '$lib/img';
	import { boost } from '$lib/kit';
	import TagChip from '$lib/TagChip.svelte';
	import TalentBadge from '$lib/TalentBadge.svelte';
	import TravelerElementCard from '$lib/TravelerElementCard.svelte';
	import type { TalentRole } from '$lib/types';

	const p = getCharacterPage();
	const c = $derived(p.c!);
	const SLOTS: Record<number, string> = { 1: 'Flower', 2: 'Plume', 3: 'Sands', 4: 'Goblet', 5: 'Circlet' };
	const TALENTS: { role: TalentRole; label: string }[] = [
		{ role: 'normal', label: 'Normal' }, { role: 'skill', label: 'Skill' }, { role: 'burst', label: 'Burst' }
	];
	const icon = (role: TalentRole) => p.kit?.talents.find((t) => t.role === role)?.icon ?? null;
	const cons = $derived(c.constellation ?? 0);
</script>

{#if c.traveler}
	<TravelerElementCard info={c.traveler} onsaved={() => p.load(p.slug)} />
{/if}

{#if !c.owned}
	<div class="grid">
		<section class="card"><h2>Current</h2><p class="muted">Not obtained yet.</p></section>
		<section class="card" data-testid="in-teams">{@render teams()}</section>
	</div>
{:else}
	<div class="grid">
		<section class="card">
			<h2>Level</h2>
			<div data-testid="current-level"><span class="big">{c.level}</span> <span class="muted">/ 90 · Friendship {c.friendship}</span></div>
			<h2 class="gap" data-testid="current-constellation">Constellations · C{cons}</h2>
			<ConstellationRow kit={p.kit} owned={cons} />
		</section>
		<section class="card">
			<h2>Talents</h2>
			<div class="talents">
				{#each TALENTS as t (t.role)}
					<TalentBadge testid="talent-{t.role}" icon={icon(t.role)} label={t.label}
						base={c.talents?.[t.role] ?? 1} bonus={boost(p.kit, t.role, cons)} />
				{/each}
			</div>
		</section>
		<section class="card">
			<h2>Weapon</h2>
			{#if c.weapon}
				<div class="weapon">
					{#if imgSrc(c.weapon.icon)}<img src={imgSrc(c.weapon.icon)} alt="" />{/if}
					<div><b>{c.weapon.name}</b><div class="muted">{'★'.repeat(c.weapon.rarity)} · Lv {c.weapon.level} · R{c.weapon.refinement}</div></div>
				</div>
			{:else}<p class="muted">No weapon data.</p>{/if}
			<div class="gap" data-testid="in-teams">{@render teams()}</div>
		</section>
		<section class="card span2">
			<h2>Artifacts</h2>
			<div class="artifacts">
				{#each c.artifacts as a (a.slot)}
					<div class="artifact">
						{#if imgSrc(a.icon)}<img src={imgSrc(a.icon)} alt="" />{/if}
						<div class="muted">{SLOTS[a.slot] ?? `Slot ${a.slot}`} · +{a.level}</div>
						<b>{a.main_stat}</b>
						<ul>{#each a.substats as s (s)}<li>{s}</li>{/each}</ul>
						<div class="muted">{a.set_name}</div>
					</div>
				{:else}<p class="muted">No artifact data yet.</p>{/each}
			</div>
		</section>
		<section class="card">
			<h2>Stats</h2>
			<table><tbody>{#each c.stats as s (s.name)}<tr><td>{s.name}</td><td>{s.value}</td></tr>{/each}</tbody></table>
		</section>
	</div>
{/if}

{#snippet teams()}
	<h2>In teams</h2>
	{#if c.teams.length === 0}<p class="muted">Not in any team</p>{:else}
		<ul class="teams">{#each c.teams as t (t.id)}<li><a href="/teams#team-{t.id}">{t.name}</a> {#each t.tags as tag (tag.id)}<TagChip {tag} />{/each}</li>{/each}</ul>
	{/if}
{/snippet}

<style>
	.big { font-size: 28px; font-weight: 700; color: var(--el, var(--cream)); }
	.gap { margin-top: 14px; }
	.talents { display: flex; gap: 12px; }
	.weapon { display: flex; gap: 10px; align-items: center; }
	.weapon img { width: 56px; height: 56px; border-radius: 8px; background: var(--r4); }
	.artifacts { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 8px; }
	.artifact { background: var(--panel-2); border-radius: 8px; padding: 8px; font-size: 12px; }
	.artifact img { width: 34px; height: 34px; }
	.artifact ul { margin: 4px 0; padding-left: 16px; color: var(--muted); }
	.teams { list-style: none; padding: 0; margin: 0; }
	.teams li { display: flex; gap: 6px; align-items: center; padding: 2px 0; }
	table { width: 100%; font-size: 12px; } td:last-child { text-align: right; }
</style>
```

Then remove the old `.hero`/shortfall code (the file is fully replaced). `TravelerElementCard`'s heading "Current" used by old tests no longer exists; the new tests use test ids.

- [ ] **Step 8: Run checks and e2e**

Run: `npm run check && npx vitest run && npm run build && PYTHON=<python> npx playwright test e2e/characters.spec.ts e2e/shell.spec.ts`
Expected: PASS (Build and Guide tab links lead to 404 pages until Tasks 6–7, but the tab tests above only assert the URL — if SvelteKit renders an error page without the banner, the URL assertion still passes).

- [ ] **Step 9: Commit**

```bash
git add frontend
git commit -m "feat(character): banner layout with element tint and Current tab"
```

---

### Task 6: Build tab

**Files:**
- Create: `frontend/src/routes/characters/[slug]/build/+page.svelte`, `frontend/src/lib/BuildArtifacts.svelte`
- Delete: `frontend/src/lib/TargetsEditor.svelte`
- Test: `frontend/e2e/characters.spec.ts`

**Interfaces:**
- Consumes: `getCharacterPage()` (`c`, `kit`, `caps`, `saveGoal`), `buildValue`, `isReached`, `boost` (Task 4), `TalentBadge`, `ConstellationRow` (Task 5), `api.weapons(type)`, `ownedLabel` from `$lib/good`.
- Produces: aria labels `Target level`, `Target normal attack`, `Target elemental skill`, `Target elemental burst`, `Target constellation`, `Planned weapon`, `Target weapon level`, `Target refinement`; test ids `build-artifacts-slot`, `build-suggestions-slot`, `set-build`.

- [ ] **Step 1: Write the failing e2e test**

Append to `frontend/e2e/characters.spec.ts`:

```ts
test('Build tab edits targets and keeps them', async ({ page }) => {
	await page.goto('/characters/furina/build');               // dev seed: Furina is Build, Lv 90, talents 9/9/9
	const skill = page.getByLabel('Target elemental skill');
	const before = await skill.inputValue();
	await skill.selectOption('10');
	await page.getByLabel('Target constellation').selectOption('6');
	await page.reload();
	await expect(page.getByLabel('Target elemental skill')).toHaveValue('10');
	await expect(page.getByLabel('Target constellation')).toHaveValue('6');
	await expect(page.getByTestId('build-artifacts-slot')).toContainText('sub-project 8');
	await expect(page.getByTestId('build-suggestions-slot')).toContainText('sub-project 9');
	await page.getByLabel('Target elemental skill').selectOption(before);          // restore
	await page.getByLabel('Target constellation').selectOption('1');               // devseed roster has C1
	await expect(page.getByLabel('Target elemental skill')).toHaveValue(before);
});

test('Build tab on a non-Build character offers Set to Build', async ({ page }) => {
	await page.goto('/characters/nahida/build');               // dev seed: Nahida owned, goal none
	await expect(page.getByLabel('Target level')).toBeDisabled();
	await page.getByTestId('set-build').click();
	await expect(page.getByLabel('Target level')).toBeEnabled();
	await expect(page.getByLabel('Target elemental skill')).toHaveValue('9');    // baseline, Nahida has 8
	await page.getByTestId('banner').getByRole('button', { name: 'None' }).click();     // restore
	await expect(page.getByLabel('Target level')).toBeDisabled();
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run build && PYTHON=<python> npx playwright test e2e/characters.spec.ts -g "Build tab"`
Expected: FAIL (404 page, no labels).

- [ ] **Step 3: `frontend/src/lib/BuildArtifacts.svelte`**

```svelte
<!-- Sub-project 8 fills this card with target artifact sets and main/sub stats. -->
<section class="card span2">
	<h2>Artifacts</h2>
	<div class="slot" data-testid="build-artifacts-slot">Target sets and main/sub stats arrive with sub-project 8 (Artifact planning).</div>
</section>
```

- [ ] **Step 4: `frontend/src/routes/characters/[slug]/build/+page.svelte`**

```svelte
<script lang="ts">
	import { api } from '$lib/api';
	import BuildArtifacts from '$lib/BuildArtifacts.svelte';
	import { getCharacterPage } from '$lib/characterPage.svelte';
	import ConstellationRow from '$lib/ConstellationRow.svelte';
	import { ownedLabel } from '$lib/good';
	import { imgSrc } from '$lib/img';
	import { buildValue, isReached } from '$lib/kit';
	import type { TalentRole, Targets, WeaponOption } from '$lib/types';

	const p = getCharacterPage();
	const c = $derived(p.c!);
	const editing = $derived(c.goal === 'build');
	const cur = $derived({
		level: c.level ?? 1,
		normal: c.talents?.normal ?? 1, skill: c.talents?.skill ?? 1, burst: c.talents?.burst ?? 1,
		constellation: c.constellation ?? 0,
		weapon_level: c.weapon?.level ?? 1, refinement: c.weapon?.refinement ?? 1
	});
	// Read-only preview before Build: the stored targets if any, else the current values.
	const t = $derived<Targets>(c.targets ?? { level: cur.level, normal: cur.normal, skill: cur.skill, burst: cur.burst,
		weapon_level: cur.weapon_level });
	const tCons = $derived(buildValue(t.constellation, cur.constellation));
	const tRef = $derived(buildValue(t.refinement, cur.refinement));
	const TALENTS: { role: TalentRole; label: string; aria: string }[] = [
		{ role: 'normal', label: 'Normal', aria: 'Target normal attack' },
		{ role: 'skill', label: 'Skill', aria: 'Target elemental skill' },
		{ role: 'burst', label: 'Burst', aria: 'Target elemental burst' }
	];
	const TALENT_LEVELS = Array.from({ length: 10 }, (_, i) => i + 1);
	const WEAPON_LEVELS = [20, 40, 50, 60, 70, 80, 90];
	const levelOptions = $derived([...new Set([...p.caps, t.level])].sort((a, b) => a - b));
	const icon = (role: TalentRole) => p.kit?.talents.find((k) => k.role === role)?.icon ?? null;

	let weapons = $state<WeaponOption[]>([]);
	const weaponType = $derived(c.weapon_type);
	$effect(() => {
		const type = weaponType;
		if (!type) return;
		api.weapons(type).then((w) => (weapons = w)).catch(() => (weapons = []));
	});

	function save(patch: Partial<Targets>) {
		p.saveGoal({ targets: { ...t, constellation: tCons, refinement: tRef, ...patch } });
	}
	function setWeapon(value: string) {
		p.saveGoal({ planned_weapon_id: value === '' ? null : Number(value) });
	}
</script>

{#if !editing}
	<div class="notice card">
		<span class="muted">Not planned yet. These are the current values.</span>
		<button type="button" data-testid="set-build" onclick={() => p.saveGoal({ goal: 'build' })}>Set to Build</button>
	</div>
{/if}

<div class="grid">
	<section class="card">
		<h2>Level</h2>
		<div class="pair">
			<span class="now">{cur.level}</span><span class="arrow">→</span>
			<select aria-label="Target level" disabled={!editing} value={t.level}
				onchange={(e) => save({ level: Number(e.currentTarget.value) })}>
				{#each levelOptions as l (l)}<option value={l}>{l}</option>{/each}
			</select>
			{#if isReached(cur.level, t.level)}<span class="done">✓</span>{/if}
		</div>
		<h2 class="gap">Constellations · C{cur.constellation} →
			<select aria-label="Target constellation" disabled={!editing} value={tCons}
				onchange={(e) => save({ constellation: Number(e.currentTarget.value) })}>
				{#each [0, 1, 2, 3, 4, 5, 6] as n (n)}<option value={n}>C{n}</option>{/each}
			</select>
		</h2>
		<ConstellationRow kit={p.kit} owned={cur.constellation} target={tCons} />
		<p class="muted small">Dashed = wanted, not owned yet. Wishes, not farming: the planner ignores it.</p>
	</section>

	<section class="card">
		<h2>Talents</h2>
		<div class="talents">
			{#each TALENTS as k (k.role)}
				<div class="talent">
					<div class="ic">{#if imgSrc(icon(k.role))}<img src={imgSrc(icon(k.role))} alt="" />{/if}</div>
					<div class="pair">
						<span class="now">{cur[k.role]}</span><span class="arrow">→</span>
						<select aria-label={k.aria} disabled={!editing} value={t[k.role]}
							onchange={(e) => save({ [k.role]: Number(e.currentTarget.value) } as Partial<Targets>)}>
							{#each TALENT_LEVELS as l (l)}<option value={l}>{l}</option>{/each}
						</select>
					</div>
					<span class="muted small">{k.label}</span>
				</div>
			{/each}
		</div>
	</section>

	<section class="card">
		<h2>Weapon</h2>
		<label class="field">
			<span class="muted small">Planned weapon</span>
			<select aria-label="Planned weapon" disabled={!editing} value={c.planned_weapon_id ?? ''}
				onchange={(e) => setWeapon(e.currentTarget.value)}>
				<option value="">{c.owned && c.weapon ? `Equipped: ${c.weapon.name}` : 'None'}</option>
				{#each weapons as w (w.id)}<option value={w.id}>{'★'.repeat(w.rarity)} {w.name}{w.owned ? ` · ${ownedLabel(w.owned)}` : ''}</option>{/each}
			</select>
		</label>
		<div class="pair gap">
			<span class="muted small">Lv {cur.weapon_level} →</span>
			<select aria-label="Target weapon level" disabled={!editing} value={t.weapon_level}
				onchange={(e) => save({ weapon_level: Number(e.currentTarget.value) })}>
				{#each [...new Set([...WEAPON_LEVELS, t.weapon_level])].sort((a, b) => a - b) as l (l)}<option value={l}>{l}</option>{/each}
			</select>
			<span class="muted small">R{cur.refinement} →</span>
			<select aria-label="Target refinement" disabled={!editing} value={tRef}
				onchange={(e) => save({ refinement: Number(e.currentTarget.value) })}>
				{#each [1, 2, 3, 4, 5] as r (r)}<option value={r}>R{r}</option>{/each}
			</select>
		</div>
	</section>

	<BuildArtifacts />

	<section class="card">
		<h2>Suggestions</h2>
		<div class="slot" data-testid="build-suggestions-slot">Recommended targets arrive with sub-project 9 (Build recommendations).</div>
	</section>
</div>

<style>
	.notice { display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; }
	.pair { display: flex; gap: 6px; align-items: center; }
	.now { font-size: 20px; font-weight: 700; }
	.arrow { color: var(--el, var(--gold)); font-weight: 700; }
	.done { color: var(--building); }
	.gap { margin-top: 14px; }
	.small { font-size: 11px; }
	.talents { display: flex; gap: 14px; flex-wrap: wrap; }
	.talent { display: flex; flex-direction: column; align-items: center; gap: 4px; }
	.ic { width: 48px; height: 48px; border-radius: 50%; background: rgba(255, 255, 255, 0.07); border: 1px solid var(--glass-border);
		display: flex; align-items: center; justify-content: center; }
	.ic img { width: 40px; height: 40px; }
	.field { display: flex; flex-direction: column; gap: 4px; }
	select:not(:disabled) { border-color: var(--el, var(--glass-border)); }
</style>
```

Delete `frontend/src/lib/TargetsEditor.svelte` (`grep -rn TargetsEditor frontend/src` must print nothing first).

- [ ] **Step 5: Run checks and e2e**

Run: `npm run check && npm run build && PYTHON=<python> npx playwright test e2e/characters.spec.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat(character): Build tab with per-character targets, constellation and refinement; slots for sub-projects 8 and 9"
```

---

### Task 7: Guide tab

**Files:**
- Create: `frontend/src/lib/KitText.svelte`, `frontend/src/lib/ScalingTable.svelte`, `frontend/src/routes/characters/[slug]/guide/+page.svelte`
- Test: `frontend/e2e/characters.spec.ts`

**Interfaces:**
- Consumes: `getCharacterPage()` (`c`, `kit`, `kitState`, `loadKit`, `slug`), `scalingColumns`, `valueAt`, `buildValue` (Task 4).
- Produces: `KitText` props `{ lines: Segment[][] }`; `ScalingTable` props `{ rows: ScaleRow[]; columns: Column[] }`; test ids `guide-howto-slot`, `guide-talents`, `guide-constellations`, `kit-unavailable`, `kit-stale`.

- [ ] **Step 1: Write the failing e2e tests**

Append to `frontend/e2e/characters.spec.ts`:

```ts
test('Guide shows talents with numbers, passives and constellations', async ({ page }) => {
	await page.goto('/characters/furina/guide');               // dev seed kit: "Furina Skill", C1..C6
	await expect(page.getByTestId('guide-howto-slot')).toContainText('sub-project 9');
	const talents = page.getByTestId('guide-talents');
	await expect(talents.getByText('Furina Skill')).toBeVisible();
	await expect(talents.getByRole('columnheader', { name: /\(now\)/ }).first()).toBeVisible();
	await expect(talents.getByRole('columnheader', { name: /\(target\)/ }).first()).toBeVisible();
	await expect(talents.getByText('demo DMG')).toBeVisible();
	await expect(page.getByText('Furina Passive 1')).toBeVisible();
	await expect(page.getByTestId('guide-constellations').getByText('Furina C6')).toBeVisible();
	await page.goto('/characters/bennett/guide');
	await expect(page.getByTestId('guide-talents').getByText('Bennett Skill')).toBeVisible();
});

test('Guide shows a notice when the kit is unavailable', async ({ page }) => {
	await page.route('**/api/characters/furina/kit', (route) =>
		route.fulfill({ status: 200, contentType: 'application/json', body: JSON.stringify({ state: 'unavailable', kit: null }) }));
	await page.goto('/characters/furina/guide');
	await expect(page.getByTestId('kit-unavailable')).toBeVisible();
	await expect(page.getByTestId('kit-unavailable').getByRole('button', { name: 'Retry' })).toBeVisible();
	await page.goto('/characters/furina');                     // Current still renders without the kit
	await expect(page.getByTestId('talent-skill')).toBeVisible();
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npm run build && PYTHON=<python> npx playwright test e2e/characters.spec.ts -g "Guide"`
Expected: FAIL.

- [ ] **Step 3: `KitText.svelte` and `ScalingTable.svelte`**

`frontend/src/lib/KitText.svelte`:

```svelte
<script lang="ts">
	import type { Segment } from './types';

	let { lines }: { lines: Segment[][] } = $props();
</script>

<div class="kit-text">
	{#each lines as line, i (i)}
		<p>{#each line as s, j (j)}<span style={s.color ? `color: ${s.color}` : undefined} class:i={s.italic}>{s.text}</span>{/each}</p>
	{/each}
</div>

<style>
	.kit-text p { margin: 0 0 4px; min-height: 0.6em; font-size: 12.5px; line-height: 1.5; color: #d8d6e2; }
	.i { font-style: italic; }
</style>
```

`frontend/src/lib/ScalingTable.svelte`:

```svelte
<script lang="ts">
	import { valueAt, type Column } from './kit';
	import type { ScaleRow } from './types';

	let { rows, columns }: { rows: ScaleRow[]; columns: Column[] } = $props();
</script>

{#if rows.length}
	<table>
		<thead><tr><th></th>{#each columns as c (c.key)}<th class={c.key}>{c.label}</th>{/each}</tr></thead>
		<tbody>
			{#each rows as r (r.label)}
				<tr><td class="label">{r.label}</td>{#each columns as c (c.key)}<td class={c.key}>{valueAt(r, c.level)}</td>{/each}</tr>
			{/each}
		</tbody>
	</table>
{/if}

<style>
	table { font-size: 12px; border-collapse: collapse; margin-top: 4px; }
	th { color: var(--muted); font-weight: 500; text-align: right; padding: 2px 10px; }
	td { padding: 2px 10px; text-align: right; }
	td.label { text-align: left; padding-left: 0; color: var(--muted); }
	td.target { color: var(--el, var(--gold)); font-weight: 600; }
</style>
```

- [ ] **Step 4: `frontend/src/routes/characters/[slug]/guide/+page.svelte`**

```svelte
<script lang="ts">
	import { getCharacterPage } from '$lib/characterPage.svelte';
	import { imgSrc } from '$lib/img';
	import { buildValue, scalingColumns } from '$lib/kit';
	import KitText from '$lib/KitText.svelte';
	import ScalingTable from '$lib/ScalingTable.svelte';
	import type { KitTalent, TalentRole } from '$lib/types';

	const p = getCharacterPage();
	const c = $derived(p.c!);
	const owned = $derived(c.constellation ?? 0);
	const KIND: Record<string, string> = { normal: 'Normal Attack', skill: 'Elemental Skill', burst: 'Elemental Burst', other: 'Other' };

	function columns(t: KitTalent) {
		if (t.role === 'other') return [];
		const role = t.role as TalentRole;
		const now = c.owned && c.talents ? { base: c.talents[role], constellation: owned } : null;
		const target = c.goal === 'build' && c.targets
			? { base: c.targets[role], constellation: Math.max(owned, buildValue(c.targets.constellation, owned)) }
			: null;
		return scalingColumns(p.kit, role, now, target);
	}
	function kind(t: KitTalent): string {
		const parts = [KIND[t.role]];
		if (t.cooldown !== null) parts.push(`CD ${t.cooldown}s`);
		if (t.cost !== null) parts.push(`${t.cost} Energy`);
		return parts.join(' · ');
	}
</script>

<div class="slot howto" data-testid="guide-howto-slot"><b>How to play</b> · Role, team comps, rotations and talent priority arrive with sub-project 9.</div>

{#if p.kitState === 'loading'}
	<p class="muted">Loading talents…</p>
{:else if !p.kit}
	<div class="card" data-testid="kit-unavailable">
		<p>Talent data unavailable.</p>
		<button type="button" onclick={() => p.loadKit(p.slug)}>Retry</button>
	</div>
{:else}
	{#if p.kitState === 'stale'}<p class="muted" data-testid="kit-stale">Talent data may be out of date.</p>{/if}
	<div class="two">
		<div>
			<section class="card" data-testid="guide-talents">
				<h2>Talents</h2>
				{#each p.kit.talents as t (t.name)}
					<div class="t">
						<div class="ic">{#if imgSrc(t.icon)}<img src={imgSrc(t.icon)} alt="" />{/if}</div>
						<div>
							<b class="name">{t.name}</b><span class="k">{kind(t)}</span>
							<KitText lines={t.description} />
							<ScalingTable rows={t.scaling} columns={columns(t)} />
						</div>
					</div>
				{/each}
			</section>
			<section class="card gap">
				<h2>Passives</h2>
				{#each p.kit.passives as ps (ps.name)}
					<div class="t">
						<div class="ic">{#if imgSrc(ps.icon)}<img src={imgSrc(ps.icon)} alt="" />{/if}</div>
						<div><b class="name">{ps.name}</b><KitText lines={ps.description} /></div>
					</div>
				{/each}
			</section>
		</div>
		<section class="card" data-testid="guide-constellations">
			<h2>Constellations · C{owned}</h2>
			{#each p.kit.constellations as k (k.index)}
				<div class="cons" class:off={k.index > owned}>
					<div class="ic small">{#if imgSrc(k.icon)}<img src={imgSrc(k.icon)} alt="" />{/if}</div>
					<div><b>C{k.index} · {k.name}</b><KitText lines={k.description} /></div>
				</div>
			{/each}
		</section>
	</div>
{/if}

<style>
	.howto { margin-bottom: 12px; }
	.howto b { color: var(--text); }
	.two { display: grid; grid-template-columns: 1.4fr 1fr; gap: 12px; align-items: start; }
	.gap { margin-top: 12px; }
	.t, .cons { display: flex; gap: 12px; margin-bottom: 14px; }
	.ic { flex: 0 0 48px; height: 48px; border-radius: 50%; background: rgba(255, 255, 255, 0.07);
		border: 1px solid var(--glass-border); display: flex; align-items: center; justify-content: center; }
	.ic img { width: 40px; height: 40px; }
	.ic.small { flex-basis: 40px; height: 40px; border-color: var(--el, var(--gold)); }
	.ic.small img { width: 32px; height: 32px; }
	.cons.off .ic.small { border-color: var(--glass-border); }
	.cons.off img { opacity: 0.3; filter: grayscale(1); }
	.name { color: var(--el, var(--cream)); }
	.k { font-size: 11px; color: var(--muted); margin-left: 6px; }
	@media (max-width: 1100px) { .two { grid-template-columns: 1fr; } }
</style>
```

- [ ] **Step 5: Run checks and e2e**

Run: `npm run check && npx vitest run && npm run build && PYTHON=<python> npx playwright test e2e/characters.spec.ts`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend
git commit -m "feat(character): Guide tab with talents, scaling at now/target/max, passives and constellations"
```

---

### Task 8: Verification

**Files:** none new (fixes only, if a check fails).

- [ ] **Step 1: Leftover references**

Run: `grep -rn "default_targets\|DEFAULT_TARGETS\|TargetsEditor\|data-testid=\"shortfall\"" backend/app frontend/src frontend/e2e`
Expected: only `backend/migrations/versions/0010_character_detail.py` (the DELETE). Fix anything else.

- [ ] **Step 2: Backend**

Run (from `backend/`): `<python> -m pytest -q`
Expected: all pass.

- [ ] **Step 3: Frontend**

Run (from `frontend/`): `npm run check`, `npx vitest run`, `npm run build`, `PYTHON=<python> npx playwright test`
Expected: svelte-check 0 errors / 0 warnings; vitest, build and all Playwright specs pass (workers 1).

- [ ] **Step 4: Sensitive-data check before pushing**

Run: `git diff origin/main --stat` and `git diff origin/main | grep -inE "ltoken|ltuid=|cookie_token|@gmail.com"`
Expected: no matches (fixtures hold only public Yatta game data).

- [ ] **Step 5: Commit any fixes**

```bash
git add -A
git commit -m "fix(character): final verification fixes"
```

(Skip when there is nothing to commit.)

---

## Self-review notes

- Spec §3 (targets) → Task 1; §4 (kit) → Tasks 2–3; §5 (API) → Tasks 1, 3; §6.1–6.3 → Tasks 4–5; §6.4 → Task 5; §6.5 → Task 6; §6.6 → Task 7; §6.7 → Tasks 4–7; §7 errors → Tasks 3, 5, 7; §9 testing → every task; devseed kits → Task 3.
- The detail payload keeps `shortfall` (spec §5); only the page stops showing it.
- Name consistency: `raise_to_build(session, ids)`, `defaults_for`, `stored_targets`, `write_targets`, `load_kit`, `yatta_key`, `parse_kit`, `CharacterPage.loadKit`, `scalingColumns(kit, role, now, target)`.
