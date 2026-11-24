# Ad Astra Sub-project 9 — Build Recommendations and Guides Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Store HoYoLAB's official recommended artifact main stats and substats at sync, prefill them into a new Build character's artifact target, show them on Build with Apply, and replace the Guide's "How to play" slot with a community-guide link.

**Architecture:** Migration 0013 adds a `stat_recommendation` table. `backend/app/sync/recommend.py` parses the `recommend_relic_property` block that the HoYoLAB character-detail response already carries (genshin.py ignores it, so `get_details` reads the raw response). `persist.save_details` upserts rows; `targets.prefill_artifact_target` fills an empty artifact target when a character enters Build (goal switch and Teams). The character payload gains `stat_recommendation`; the front end adds `BuildSuggestions.svelte` and `GuideLink.svelte` with pure helpers in `lib/recommend.ts` and `lib/guides.ts`.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, pytest (backend); SvelteKit with Svelte 5 runes, TypeScript, vitest, Playwright (frontend).

**Spec:** `docs/superpowers/specs/2026-11-24-ad-astra-build-guides-design.md`

## Global Constraints

- Cookie values only in the git-ignored `.env`; never logged, returned or committed.
- Unofficial API code stays in `backend/app/sync/` and `backend/app/wishes/`; public game-data code stays in `backend/app/gamedata/`.
- No new requests: the recommendation comes from the character-detail response the sync already fetches. The community site is only linked, never fetched.
- `custom_properties` (the player's own HoYoLAB choices) is never stored.
- Test fixtures use made-up UID 800000001 where a UID is needed; no game art or personal data committed; no user name, email, Windows user name or absolute user path in any committed file.
- New migration is `0013` (revises `0012`).
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

**Commands** (`PY` = the project venv python, `.venv/Scripts/python.exe` in the main checkout):
- Backend, from `backend/`: `PY -m pytest -q` (697 passing at start).
- Frontend, from `frontend/` (run `npm ci` first in a new worktree): `npm run check`, `npx vitest run` (181 at start), `npm run build`, `PYTHON=PY npx playwright test` (64 at start; workers 1, one shared seeded server: any test that changes state restores it).

## Plan-time spec amendments (made in the same commit as this plan)

1. **Guide URL needs no Traveler parameter.** Comparing all 129 of our slugs with the site's list showed our Traveler slugs (`anemo-traveler` …) already match the site's `<element>-traveler` URLs. The only exception is `raiden-shogun` → `shogun-raiden`. So `communityGuideUrl(slug)` takes the slug only.
2. **Model name.** The ORM class is `CharacterStatRecommendation` (table `stat_recommendation`), so it does not clash with the `StatRecommendation` dataclass in `sync/recommend.py`.

## Review Focus

1. **HoYoLAB sends the block in a different shape** (missing, `null`, a list instead of a dict, ids as strings, unknown ids, a main stat not valid for its slot): parsing must return `None` or drop the bad parts, never raise and never fail the sync — pinned in Task 2 (`test_parse_*` cases).
2. **genshin.py's validator mutates the raw dict** (it copies `base` keys up and rewrites `relic_property_options`): recommendations must be read before the model is built, and the model must get a copy — pinned in Task 2 (`test_get_details_attaches_recommendation` asserts the raw dict passed to the model is not the original object).
3. **A sync without the field after one with it**: the stored recommendation must stay — pinned in Task 3 (`test_save_details_none_keeps_row`).
4. **Character enters Build that already has a target (even sets-only), or the same request carries an explicit target**: nothing overwritten; explicit wins — pinned in Task 4 (`test_prefill_keeps_existing_target`, `test_explicit_target_wins_over_prefill`).
5. **Apply on a character with no target yet, or while another save is in flight**: Apply builds a full target with empty sets and is disabled while saving — pinned in Task 5 (`applyRecommendation(null, rec)`) and Task 6 (button `disabled` while saving).

---

## File Structure

**Backend**
- Create `backend/migrations/versions/0013_stat_recommendation.py` — the table.
- Modify `backend/app/db/models.py` — `CharacterStatRecommendation`.
- Create `backend/app/sync/recommend.py` — `StatRecommendation`, `PROPERTY_KEYS`, `parse_recommendation`, `recommendations_by_raw_id`.
- Modify `backend/app/sync/hoyolab.py` — `DetailEntry.recommendation`, `to_detail_entry(c, recommendation=None)`, raw `get_details`.
- Modify `backend/app/sync/persist.py` — upsert in `save_details`.
- Modify `backend/app/targets.py` — `prefill_artifact_target`, `recommendation_payload`.
- Modify `backend/app/api/characters.py` — prefill in `set_goal`, `stat_recommendation` in the slug payload.
- Modify `backend/app/teams/goals.py` — prefill in `raise_to_build`.
- Modify `backend/app/devseed.py` — seeded recommendations.
- Tests: create `tests/test_migration_0013.py`, `tests/test_recommend.py`, `tests/test_prefill.py`; modify `tests/test_persist.py`, `tests/test_devseed.py`.

**Frontend**
- Modify `frontend/src/lib/types.ts` — `StatRecommendation`, `CharacterDetail.stat_recommendation`.
- Create `frontend/src/lib/recommend.ts` + `recommend.test.ts`; `frontend/src/lib/guides.ts` + `guides.test.ts`.
- Create `frontend/src/lib/BuildSuggestions.svelte`, `frontend/src/lib/GuideLink.svelte`.
- Modify `frontend/src/routes/characters/[slug]/build/+page.svelte`, `frontend/src/routes/characters/[slug]/guide/+page.svelte`.
- Modify `frontend/e2e/characters.spec.ts` (slot assertions); create `frontend/e2e/build-guides.spec.ts`.

---

### Task 1: Migration 0013 and model

**Files:**
- Create: `backend/migrations/versions/0013_stat_recommendation.py`
- Modify: `backend/app/db/models.py` (after `class GameArtifactDomain`)
- Test: `backend/tests/test_migration_0013.py`

**Interfaces:**
- Produces: ORM class `CharacterStatRecommendation(character_id: int PK, data: dict JSON, synced_at: datetime)`, table `stat_recommendation`.

- [ ] **Step 1: Write the failing test**

```python
# backend/tests/test_migration_0013.py
from sqlalchemy import inspect

from app.db.engine import make_engine
from test_migration_0007 import downgrade, upgrade


def test_0013_creates_table(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0013")
    cols = {c["name"] for c in inspect(engine).get_columns("stat_recommendation")}
    assert cols == {"character_id", "data", "synced_at"}
    engine.dispose()


def test_0013_downgrade(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0013")
    downgrade(engine, "0012")
    assert "stat_recommendation" not in inspect(engine).get_table_names()
    engine.dispose()
```

- [ ] **Step 2: Run it and see it fail**

Run (from `backend/`): `PY -m pytest tests/test_migration_0013.py -q`
Expected: FAIL (no revision `0013`).

- [ ] **Step 3: Write the migration**

```python
# backend/migrations/versions/0013_stat_recommendation.py
"""Ad Astra sub-project 9: HoYoLAB artifact-stat recommendations

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-24
"""
import sqlalchemy as sa
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stat_recommendation",
        sa.Column("character_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("synced_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("stat_recommendation")
```

- [ ] **Step 4: Add the model** in `backend/app/db/models.py`, right after `class GameArtifactDomain`:

```python
class CharacterStatRecommendation(Base):
    """HoYoLAB's recommended artifact main stats and substats for a character, in our stat keys (sub-project 9)."""
    __tablename__ = "stat_recommendation"
    character_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    data: Mapped[dict] = mapped_column(JSON)
    synced_at: Mapped[datetime] = mapped_column(DateTime)
```

- [ ] **Step 5: Run the tests**

Run: `PY -m pytest tests/test_migration_0013.py tests/test_db.py -q`
Expected: PASS (`test_db.py` checks models match migrations; if it compares table sets, the new table must appear in both).

- [ ] **Step 6: Commit**

```bash
git add backend/migrations/versions/0013_stat_recommendation.py backend/app/db/models.py backend/tests/test_migration_0013.py
git commit -m "feat(db): stat_recommendation table (migration 0013)"
```

---

### Task 2: Parse the recommendation at sync

**Files:**
- Create: `backend/app/sync/recommend.py`
- Modify: `backend/app/sync/hoyolab.py` (`DetailEntry`, `to_detail_entry`, `GenshinPySource.get_details`)
- Test: `backend/tests/test_recommend.py`

**Interfaces:**
- Consumes: `SLOT_OPTIONS`, `SUB_KEYS`, `MAIN_SLOTS` from `app.artifacts.stats`.
- Produces:
  - `@dataclass(frozen=True) class StatRecommendation: main: dict[str, list[str]]; subs: list[str]` with method `to_json() -> dict` returning `{"main": {...}, "subs": [...]}`.
  - `PROPERTY_KEYS: dict[int, str]`.
  - `parse_recommendation(raw_entry: Any) -> StatRecommendation | None`.
  - `recommendations_by_raw_id(raw: Any) -> dict[int, StatRecommendation]`.
  - `DetailEntry.recommendation: StatRecommendation | None = None` (last field, default `None`, so `make_detail` in `tests/fakes.py` keeps working).
  - `to_detail_entry(c, recommendation: StatRecommendation | None = None) -> DetailEntry`.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_recommend.py
import asyncio
from types import SimpleNamespace as NS

import genshin

from app.sync import hoyolab
from app.sync.recommend import PROPERTY_KEYS, StatRecommendation, parse_recommendation, recommendations_by_raw_id


def entry(props, cid=10000032):
    return {"base": {"id": cid}, "recommend_relic_property": {
        "recommend_properties": props, "custom_properties": {"sand_main_property_list": [28]},
        "has_set_recommend_prop": False}}


FULL = {"sand_main_property_list": [23, 3], "goblet_main_property_list": [40, 3],
        "circlet_main_property_list": [26, 3], "sub_property_list": [23, 3, 2, 20]}


def test_property_keys_pinned():
    assert PROPERTY_KEYS == {2: "hp", 3: "hp%", 5: "atk", 6: "atk%", 8: "def", 9: "def%", 20: "crit_rate",
                             22: "crit_dmg", 23: "er", 26: "heal", 28: "em", 30: "phys", 40: "pyro",
                             41: "electro", 42: "hydro", 43: "dendro", 44: "anemo", 45: "geo", 46: "cryo"}


def test_parse_full_block():
    r = parse_recommendation(entry(FULL))
    assert r == StatRecommendation(main={"sands": ["er", "hp%"], "goblet": ["pyro", "hp%"], "circlet": ["heal", "hp%"]},
                                   subs=["er", "hp%", "hp", "crit_rate"])
    assert r.to_json() == {"main": {"sands": ["er", "hp%"], "goblet": ["pyro", "hp%"], "circlet": ["heal", "hp%"]},
                           "subs": ["er", "hp%", "hp", "crit_rate"]}


def test_parse_ignores_custom_properties():
    r = parse_recommendation(entry({"sand_main_property_list": [6]}))
    assert r.main["sands"] == ["atk%"]                 # custom 28 (em) never used


def test_parse_missing_or_odd_block_is_none():
    assert parse_recommendation({}) is None
    assert parse_recommendation({"recommend_relic_property": None}) is None
    assert parse_recommendation({"recommend_relic_property": []}) is None
    assert parse_recommendation({"recommend_relic_property": {"recommend_properties": "x"}}) is None
    assert parse_recommendation("nope") is None


def test_parse_drops_unknown_invalid_and_duplicates():
    r = parse_recommendation(entry({
        "sand_main_property_list": [23, 999, 40, 23],   # 999 unknown, pyro not a sands stat, duplicate er
        "goblet_main_property_list": "x",               # not a list -> empty
        "circlet_main_property_list": ["22", None],     # string id accepted, None dropped
        "sub_property_list": [40, 20, 20, 22],          # pyro is not a substat
    }))
    assert r.main == {"sands": ["er"], "goblet": [], "circlet": ["crit_dmg"]}
    assert r.subs == ["crit_rate", "crit_dmg"]


def test_parse_all_empty_is_none():
    assert parse_recommendation(entry({"sand_main_property_list": [999], "sub_property_list": []})) is None


def test_recommendations_by_raw_id():
    raw = {"list": [entry(FULL, 10000032), {"base": {"id": 10000089}}, "junk", {"id": 10000023, **entry(FULL, 0)}]}
    got = recommendations_by_raw_id(raw)
    assert set(got) == {10000032}                      # entry without block skipped; base id 0 ignored
    assert recommendations_by_raw_id(None) == {}
    assert recommendations_by_raw_id({"list": "x"}) == {}


def test_get_details_attaches_recommendation(monkeypatch):
    raw = {"list": [entry(FULL, 10000032)]}
    seen = {}

    class Client:
        async def get_genshin_detailed_characters(self, uid, *, characters, return_raw_data):
            assert return_raw_data is True and list(characters) == [10000032]
            return raw

    def fake_model(**data):
        seen["data"] = data
        weapon = NS(id=1, icon="https://act-webstatic.hoyoverse.com/w.png", name="W", rarity=4, level=90,
                    refinement=1)
        return NS(characters=[NS(id=10000032, weapon=weapon, artifacts=[], skills=[], base_properties=[],
                                 extra_properties=[])])

    monkeypatch.setattr(genshin.models, "GenshinDetailCharacters", fake_model)
    src = object.__new__(hoyolab.GenshinPySource)
    src._client, src._uid, src._delays = Client(), 800000001, ()
    out = asyncio.run(src.get_details([10000032]))
    assert out[0].id == 10000032 and out[0].recommendation.main["sands"] == ["er", "hp%"]
    assert seen["data"] is not raw and seen["data"]["list"] is not raw["list"]   # model got a copy


def test_detail_entry_without_recommendation_defaults_to_none():
    weapon = NS(id=1, icon="i", name="W", rarity=4, level=90, refinement=1)
    c = NS(id=10000032, weapon=weapon, artifacts=[], skills=[], base_properties=[], extra_properties=[])
    assert hoyolab.to_detail_entry(c).recommendation is None
```

- [ ] **Step 2: Run them and see them fail**

Run: `PY -m pytest tests/test_recommend.py -q`
Expected: FAIL (`ModuleNotFoundError: app.sync.recommend`).

- [ ] **Step 3: Write `backend/app/sync/recommend.py`**

```python
"""HoYoLAB's recommended artifact stats (character detail `recommend_relic_property`) in our stat keys (sub-project 9).
Only `recommend_properties` is read; the player's own `custom_properties` is ignored and never stored."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.artifacts.stats import MAIN_SLOTS, SLOT_OPTIONS, SUB_KEYS

# Game fight-property ids as HoYoLAB reports them.
PROPERTY_KEYS: dict[int, str] = {
    2: "hp", 3: "hp%", 5: "atk", 6: "atk%", 8: "def", 9: "def%", 20: "crit_rate", 22: "crit_dmg", 23: "er",
    26: "heal", 28: "em", 30: "phys", 40: "pyro", 41: "electro", 42: "hydro", 43: "dendro", 44: "anemo",
    45: "geo", 46: "cryo",
}
_LISTS = {"sands": "sand_main_property_list", "goblet": "goblet_main_property_list",
          "circlet": "circlet_main_property_list"}


@dataclass(frozen=True)
class StatRecommendation:
    main: dict[str, list[str]]
    subs: list[str]

    def to_json(self) -> dict:
        return {"main": {k: list(v) for k, v in self.main.items()}, "subs": list(self.subs)}


def _keys(values: Any, allowed: tuple[str, ...]) -> list[str]:
    out: list[str] = []
    if not isinstance(values, list):
        return out
    for v in values:
        try:
            key = PROPERTY_KEYS.get(int(v))
        except (TypeError, ValueError):
            continue
        if key in allowed and key not in out:
            out.append(key)
    return out


def parse_recommendation(raw_entry: Any) -> StatRecommendation | None:
    """Never raises. None when the block is missing, malformed or maps to nothing."""
    if not isinstance(raw_entry, dict):
        return None
    block = raw_entry.get("recommend_relic_property")
    props = block.get("recommend_properties") if isinstance(block, dict) else None
    if not isinstance(props, dict):
        return None
    main = {slot: _keys(props.get(_LISTS[slot]), SLOT_OPTIONS[slot]) for slot in MAIN_SLOTS}
    subs = _keys(props.get("sub_property_list"), SUB_KEYS)
    if not subs and not any(main.values()):
        return None
    return StatRecommendation(main=main, subs=subs)


def recommendations_by_raw_id(raw: Any) -> dict[int, StatRecommendation]:
    """HoYoLAB character id -> recommendation, from a raw character/detail response."""
    out: dict[int, StatRecommendation] = {}
    entries = raw.get("list") if isinstance(raw, dict) else None
    if not isinstance(entries, list):
        return out
    for e in entries:
        if not isinstance(e, dict):
            continue
        base = e.get("base") if isinstance(e.get("base"), dict) else {}
        try:
            cid = int(base.get("id") or 0)
        except (TypeError, ValueError):
            continue
        rec = parse_recommendation(e)
        if cid and rec is not None:
            out[cid] = rec
    return out
```

- [ ] **Step 4: Wire it into `backend/app/sync/hoyolab.py`**

Add imports at the top (with the other imports): `import copy` and `from app.sync.recommend import StatRecommendation, recommendations_by_raw_id`.

Change `DetailEntry` (add the last field):

```python
@dataclass(frozen=True)
class DetailEntry:
    id: int        # our id (Traveler: element id)
    normal: int
    skill: int
    burst: int
    weapon: WeaponInfo
    artifacts: list[ArtifactInfo]
    stats: list[dict]
    recommendation: StatRecommendation | None = None
```

Change `to_detail_entry`'s signature and its `return`:

```python
def to_detail_entry(c: Any, recommendation: StatRecommendation | None = None) -> DetailEntry:
    ...  # body unchanged up to the return
    return DetailEntry(id=canonical_id(c.id, getattr(c, "element", None) or None), normal=normal, skill=skill,
                       burst=burst,
                       weapon=_weapon(c.weapon), artifacts=artifacts, stats=stats, recommendation=recommendation)
```

Replace `GenshinPySource.get_details`:

```python
    async def get_details(self, raw_ids: Sequence[int]) -> list[DetailEntry]:
        out: list[DetailEntry] = []
        ids = list(raw_ids)
        for i in range(0, len(ids), DETAIL_BATCH):
            raw = await call_api(self._client.get_genshin_detailed_characters, self._uid,
                                 characters=ids[i:i + DETAIL_BATCH], return_raw_data=True, delays=self._delays)
            recs = recommendations_by_raw_id(raw)          # read before the model's validator mutates a dict
            result = genshin.models.GenshinDetailCharacters(**copy.deepcopy(raw))
            out.extend(e for e in (to_detail_entry(c, recs.get(int(c.id))) for c in result.characters)
                       if e.id is not None)
        return out
```

- [ ] **Step 5: Run the tests**

Run: `PY -m pytest tests/test_recommend.py tests/test_hoyolab.py tests/test_persist.py tests/test_sync_runner.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/sync/recommend.py backend/app/sync/hoyolab.py backend/tests/test_recommend.py
git commit -m "feat(sync): read HoYoLAB recommended artifact stats from character detail"
```

---

### Task 3: Store recommendations at sync

**Files:**
- Modify: `backend/app/sync/persist.py` (`save_details`)
- Test: `backend/tests/test_persist.py` (append)

**Interfaces:**
- Consumes: `DetailEntry.recommendation`, `StatRecommendation.to_json()`, `CharacterStatRecommendation`.
- Produces: `save_details(session, details, now: datetime | None = None)` — upserts a row per entry with a recommendation; `synced_at = now or utcnow()`. Existing callers keep passing two arguments.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_persist.py`; add `CharacterStatRecommendation` to its `app.db.models` import and `from dataclasses import replace` + `from app.sync.recommend import StatRecommendation` at the top)

```python
REC = StatRecommendation(main={"sands": ["er"], "goblet": ["pyro"], "circlet": ["crit_rate"]}, subs=["er", "crit_rate"])


def test_save_details_stores_recommendation(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], NOW)
        save_details(s, [replace(make_detail(10000032), recommendation=REC)], NOW)
    with session_factory() as s:
        row = s.get(CharacterStatRecommendation, 10000032)
        assert row.data == REC.to_json() and row.synced_at == NOW


def test_save_details_updates_recommendation(session_factory):
    seed_game(session_factory)
    newer = StatRecommendation(main={"sands": ["hp%"], "goblet": [], "circlet": []}, subs=[])
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], NOW)
        save_details(s, [replace(make_detail(10000032), recommendation=REC)], NOW)
        save_details(s, [replace(make_detail(10000032), recommendation=newer)], NOW + timedelta(days=1))
    with session_factory() as s:
        row = s.get(CharacterStatRecommendation, 10000032)
        assert row.data["main"]["sands"] == ["hp%"] and row.synced_at == NOW + timedelta(days=1)


def test_save_details_none_keeps_row(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], NOW)
        save_details(s, [replace(make_detail(10000032), recommendation=REC)], NOW)
        save_details(s, [make_detail(10000032)], NOW + timedelta(days=1))      # field missing this time
    with session_factory() as s:
        assert s.get(CharacterStatRecommendation, 10000032).data == REC.to_json()


def test_recommendation_survives_losing_the_character(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032), make_roster(10000089)], NOW)
        save_details(s, [replace(make_detail(10000032), recommendation=REC)], NOW)
        save_roster(s, [make_roster(10000089)], NOW)                            # 10000032 gone
    with session_factory() as s:
        assert s.get(CharacterStatRecommendation, 10000032) is not None
```

- [ ] **Step 2: Run them and see them fail**

Run: `PY -m pytest tests/test_persist.py -q -k recommendation`
Expected: FAIL (`save_details` takes 2 positional arguments / no row).

- [ ] **Step 3: Implement** in `backend/app/sync/persist.py` (add `CharacterStatRecommendation` to the `app.db.models` import):

```python
def save_details(session: Session, details: list[DetailEntry], now: datetime | None = None) -> None:
    when = now or utcnow()
    for d in details:
        if d.recommendation is not None:
            rec = session.get(CharacterStatRecommendation, d.id)
            if rec is None:
                session.add(CharacterStatRecommendation(character_id=d.id, data=d.recommendation.to_json(),
                                                        synced_at=when))
            else:
                rec.data, rec.synced_at = d.recommendation.to_json(), when
        row = session.get(OwnedCharacter, d.id)
        if row is None:
            continue
        ...  # the rest of the existing loop body and function, unchanged
```

(The recommendation is written before the `OwnedCharacter` check so a Traveler element id is stored even when its owned row is refreshed later in the same call.)

- [ ] **Step 4: Run the tests**

Run: `PY -m pytest tests/test_persist.py tests/test_sync_runner.py tests/test_traveler_sync.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/sync/persist.py backend/tests/test_persist.py
git commit -m "feat(sync): store stat recommendations per character"
```

---

### Task 4: Prefill on entering Build and the API field

**Files:**
- Modify: `backend/app/targets.py`
- Modify: `backend/app/api/characters.py` (`set_goal`, `get_character` slug payload)
- Modify: `backend/app/teams/goals.py` (`raise_to_build`)
- Test: `backend/tests/test_prefill.py`

**Interfaces:**
- Consumes: `CharacterStatRecommendation`.
- Produces:
  - `prefill_artifact_target(s: Session, row: CharacterGoal) -> None`.
  - `recommendation_payload(s: Session, cid: int) -> dict | None` → `{"main": {...}, "subs": [...], "synced_at": "2026-11-24T00:00:00Z"}`.
  - `GET /api/characters/{slug}` field `stat_recommendation` (Task 5 types it).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_prefill.py
from datetime import datetime

from app.db.models import CharacterGoal, CharacterStatRecommendation
from app.sync.persist import save_details, save_roster
from app.teams.goals import raise_to_build
from fakes import make_detail, make_roster
from helpers import make_client, seed_game
from test_api_characters import sf_for

NOW = datetime(2026, 11, 24)
REC = {"main": {"sands": ["er"], "goblet": ["pyro"], "circlet": ["crit_rate", "crit_dmg"]},
       "subs": ["er", "crit_rate", "crit_dmg"]}
SETS_ONLY = {"sets": [{"set_id": 15007, "pieces": 4}], "main": {"sands": [], "goblet": [], "circlet": []}, "subs": []}


def setup(paths, rec=True, goal_row=None):
    sf = sf_for(paths)
    seed_game(sf)
    with sf.begin() as s:
        save_roster(s, [make_roster(10000032, name="Bennett")], NOW)
        save_details(s, [make_detail(10000032)], NOW)
        if rec:
            s.add(CharacterStatRecommendation(character_id=10000032, data=REC, synced_at=NOW))
        if goal_row is not None:
            s.add(goal_row)
    return sf


def test_goal_switch_prefills_empty_target(paths):
    setup(paths)
    with make_client(paths) as client:
        body = client.put("/api/characters/10000032/goal", json={"goal": "build"}).json()
    assert body["artifact_target"] == {"sets": [], **REC}


def test_prefill_keeps_existing_target(paths):
    from app.db.models import GameArtifactSet
    sf = setup(paths, goal_row=CharacterGoal(character_id=10000032, goal="want", artifact_target=SETS_ONLY,
                                             updated_at=NOW))
    with sf.begin() as s:
        s.add(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=1))
    with make_client(paths) as client:
        body = client.put("/api/characters/10000032/goal", json={"goal": "build"}).json()
    assert body["artifact_target"] == SETS_ONLY


def test_no_recommendation_leaves_target_empty(paths):
    setup(paths, rec=False)
    with make_client(paths) as client:
        body = client.put("/api/characters/10000032/goal", json={"goal": "build"}).json()
    assert body["artifact_target"] is None


def test_explicit_target_wins_over_prefill(paths):
    setup(paths)
    explicit = {"sets": [], "main": {"sands": ["atk%"], "goblet": [], "circlet": []}, "subs": []}
    with make_client(paths) as client:
        body = client.put("/api/characters/10000032/goal", json={"goal": "build", "artifact_target": explicit}).json()
    assert body["artifact_target"] == explicit


def test_leaving_and_reentering_build_keeps_stored_target(paths):
    setup(paths)
    edited = {"sets": [], "main": {"sands": ["hp%"], "goblet": [], "circlet": []}, "subs": []}
    with make_client(paths) as client:
        client.put("/api/characters/10000032/goal", json={"goal": "build"})
        client.put("/api/characters/10000032/goal", json={"artifact_target": edited})
        client.put("/api/characters/10000032/goal", json={"goal": "none"})
        body = client.put("/api/characters/10000032/goal", json={"goal": "build"}).json()
    assert body["artifact_target"] == edited


def test_already_build_is_not_changed_retroactively(paths):
    setup(paths, goal_row=CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=6,
                                        target_skill=9, target_burst=9, target_weapon_level=90, priority=1,
                                        updated_at=NOW))
    with make_client(paths) as client:
        body = client.put("/api/characters/10000032/goal", json={"goal": "build"}).json()
    assert body["artifact_target"] is None


def test_teams_raise_prefills(paths):
    sf = setup(paths)
    with sf.begin() as s:
        assert raise_to_build(s, [10000032]) == [10000032]
    with sf() as s:
        assert s.get(CharacterGoal, 10000032).artifact_target == {"sets": [], **REC}


def test_character_payload_has_recommendation(paths):
    setup(paths)
    with make_client(paths) as client:
        d = client.get("/api/characters/bennett").json()
    assert d["stat_recommendation"] == {**REC, "synced_at": "2026-11-24T00:00:00Z"}


def test_character_payload_without_recommendation(paths):
    setup(paths, rec=False)
    with make_client(paths) as client:
        assert client.get("/api/characters/bennett").json()["stat_recommendation"] is None
```

- [ ] **Step 2: Run them and see them fail**

Run: `PY -m pytest tests/test_prefill.py -q`
Expected: FAIL (no prefill, no `stat_recommendation` key).

- [ ] **Step 3: Add the helpers** to `backend/app/targets.py` (add `CharacterStatRecommendation` to its `app.db.models` import and `from app.timeutil import iso`):

```python
def prefill_artifact_target(s: Session, row: CharacterGoal) -> None:
    """A Build character with no artifact target starts from HoYoLAB's recommendation, when one is stored."""
    if row.goal != "build" or row.artifact_target is not None:
        return
    rec = s.get(CharacterStatRecommendation, row.character_id)
    if rec is None:
        return
    row.artifact_target = {"sets": [], "main": dict(rec.data["main"]), "subs": list(rec.data["subs"])}


def recommendation_payload(s: Session, cid: int) -> dict | None:
    rec = s.get(CharacterStatRecommendation, cid)
    if rec is None:
        return None
    return {"main": rec.data["main"], "subs": rec.data["subs"], "synced_at": iso(rec.synced_at)}
```

- [ ] **Step 4: Call them**

In `backend/app/api/characters.py`, import `prefill_artifact_target, recommendation_payload` from `app.targets`. In `set_goal`, replace the single line `apply_goal(s, row, new_goal)` with these three lines (everything before and after stays as it is, so `write_targets` and the `artifact_target` block still follow):

```python
        was_build = row.goal == "build"
        apply_goal(s, row, new_goal)
        if not was_build:
            prefill_artifact_target(s, row)
```

(`was_build` keeps the "already on Build: no retroactive change" rule; the explicit `artifact_target` block below still runs after and wins.)

In the slug GET handler, next to `payload["artifact_check"] = ...`:

```python
            payload["stat_recommendation"] = recommendation_payload(s, payload["id"])
```

In `backend/app/teams/goals.py` `raise_to_build`, import `prefill_artifact_target` from `app.targets` and add after `write_targets(row, targets)`:

```python
        prefill_artifact_target(session, row)
```

- [ ] **Step 5: Run the tests**

Run: `PY -m pytest tests/test_prefill.py tests/test_api_characters.py tests/test_api_artifacts.py tests/test_teams_goals.py tests/test_api_teams.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/targets.py backend/app/api/characters.py backend/app/teams/goals.py backend/tests/test_prefill.py
git commit -m "feat: prefill artifact targets from HoYoLAB recommendations on entering Build"
```

---

### Task 5: Dev seed recommendations

**Files:**
- Modify: `backend/app/devseed.py`
- Test: `backend/tests/test_devseed.py` (append)

**Interfaces:**
- Produces (relied on by Task 7's e2e): seeded rows —
  - Bennett (10000032): differs from his target → Apply shown.
  - Furina (10000089): equals her target's main and subs → "Your target matches".
  - Xiangling (10000023, owned, goal none): for the prefill e2e.
  - Neuvillette (10000087): none → empty state.

- [ ] **Step 1: Write the failing test** (append to `backend/tests/test_devseed.py`)

```python
def test_devseed_stat_recommendations(tmp_path):
    seed(tmp_path)
    with make_client(Paths(tmp_path)) as client:
        bennett = client.get("/api/characters/bennett").json()
        furina = client.get("/api/characters/furina").json()
        neuv = client.get("/api/characters/neuvillette").json()
        xiangling = client.get("/api/characters/xiangling").json()
    assert bennett["stat_recommendation"]["main"]["sands"] == ["er", "hp%"]
    assert furina["stat_recommendation"]["main"] == furina["artifact_target"]["main"]
    assert furina["stat_recommendation"]["subs"] == furina["artifact_target"]["subs"]
    assert xiangling["stat_recommendation"] is not None and xiangling["artifact_target"] is None
    assert neuv["stat_recommendation"] is None
```

- [ ] **Step 2: Run it and see it fail**

Run: `PY -m pytest tests/test_devseed.py -q -k stat_recommendations`
Expected: FAIL (`stat_recommendation` is `None` for Bennett).

- [ ] **Step 3: Implement** in `backend/app/devseed.py`: add `CharacterStatRecommendation` to the `app.db.models` import, add this constant below `ARTIFACT_TARGETS`:

```python
# HoYoLAB-style stat recommendations (sub-project 9): Bennett differs from his target, Furina matches hers,
# Xiangling (goal none) shows the prefill, Neuvillette has none.
STAT_RECOMMENDATIONS = {
    10000032: {"main": {"sands": ["er", "hp%"], "goblet": ["pyro", "hp%"], "circlet": ["heal", "hp%"]},
               "subs": ["er", "hp%", "hp", "crit_rate"]},
    10000089: {"main": {"sands": ["hp%"], "goblet": ["hydro"], "circlet": ["crit_rate", "crit_dmg"]},
               "subs": ["crit_rate", "crit_dmg", "hp%", "er"]},
    10000023: {"main": {"sands": ["er", "em"], "goblet": ["pyro"], "circlet": ["crit_rate", "crit_dmg"]},
               "subs": ["er", "crit_rate", "crit_dmg", "em"]},
}
```

and right after the `for cid, goal in GOALS.items():` loop that adds `CharacterGoal` rows:

```python
        for cid, data in STAT_RECOMMENDATIONS.items():
            s.add(CharacterStatRecommendation(character_id=cid, data=data, synced_at=now))
```

- [ ] **Step 4: Run the tests**

Run: `PY -m pytest tests/test_devseed.py -q`
Expected: PASS.

- [ ] **Step 5: Run the whole backend suite**

Run: `PY -m pytest -q`
Expected: PASS (697 + the new tests).

- [ ] **Step 6: Commit**

```bash
git add backend/app/devseed.py backend/tests/test_devseed.py
git commit -m "feat(devseed): seeded stat recommendations"
```

---

### Task 6: Front-end types and pure helpers

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/recommend.ts`, `frontend/src/lib/recommend.test.ts`
- Create: `frontend/src/lib/guides.ts`, `frontend/src/lib/guides.test.ts`

**Interfaces:**
- Consumes: `ArtifactTarget`, `MainSlot`; `emptyTarget`, `MAIN_SLOTS` from `lib/artifacts.ts`.
- Produces:
  - `interface StatRecommendation { main: Record<MainSlot, string[]>; subs: string[]; synced_at: string }`; `CharacterDetail.stat_recommendation: StatRecommendation | null`.
  - `applyRecommendation(target: ArtifactTarget | null, rec: StatRecommendation): ArtifactTarget`.
  - `matchesRecommendation(target: ArtifactTarget | null, rec: StatRecommendation): boolean`.
  - `COMMUNITY_GUIDE_BASE: string`; `communityGuideUrl(slug: string): string`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/recommend.test.ts
import { describe, expect, it } from 'vitest';
import { applyRecommendation, matchesRecommendation } from './recommend';
import type { ArtifactTarget, StatRecommendation } from './types';

const rec: StatRecommendation = {
	main: { sands: ['er', 'hp%'], goblet: ['pyro'], circlet: ['crit_rate', 'crit_dmg'] },
	subs: ['er', 'crit_rate'], synced_at: '2026-11-24T00:00:00Z'
};
const target: ArtifactTarget = {
	sets: [{ set_id: 15007, pieces: 4 }],
	main: { sands: ['atk%'], goblet: [], circlet: [] }, subs: ['em']
};

describe('applyRecommendation', () => {
	it('replaces main and subs and keeps sets', () => {
		expect(applyRecommendation(target, rec)).toEqual({
			sets: [{ set_id: 15007, pieces: 4 }],
			main: { sands: ['er', 'hp%'], goblet: ['pyro'], circlet: ['crit_rate', 'crit_dmg'] },
			subs: ['er', 'crit_rate']
		});
	});
	it('builds a full target when there is none', () => {
		expect(applyRecommendation(null, rec).sets).toEqual([]);
		expect(applyRecommendation(null, rec).subs).toEqual(['er', 'crit_rate']);
	});
	it('does not share arrays with the recommendation', () => {
		const out = applyRecommendation(null, rec);
		out.main.sands.push('em');
		expect(rec.main.sands).toEqual(['er', 'hp%']);
	});
});

describe('matchesRecommendation', () => {
	it('is true after applying', () => {
		expect(matchesRecommendation(applyRecommendation(target, rec), rec)).toBe(true);
	});
	it('ignores order within a main slot', () => {
		const t = applyRecommendation(null, rec);
		t.main.sands = ['hp%', 'er'];
		expect(matchesRecommendation(t, rec)).toBe(true);
	});
	it('is order-sensitive for substats', () => {
		const t = applyRecommendation(null, rec);
		t.subs = ['crit_rate', 'er'];
		expect(matchesRecommendation(t, rec)).toBe(false);
	});
	it('is false for a different target or none', () => {
		expect(matchesRecommendation(target, rec)).toBe(false);
		expect(matchesRecommendation(null, rec)).toBe(false);
	});
});
```

```ts
// frontend/src/lib/guides.test.ts
import { describe, expect, it } from 'vitest';
import { COMMUNITY_GUIDE_BASE, communityGuideUrl } from './guides';

describe('communityGuideUrl', () => {
	it('uses our slug', () => {
		expect(communityGuideUrl('bennett')).toBe(`${COMMUNITY_GUIDE_BASE}bennett`);
		expect(communityGuideUrl('hu-tao')).toBe(`${COMMUNITY_GUIDE_BASE}hu-tao`);
	});
	it('maps the exceptions', () => {
		expect(communityGuideUrl('raiden-shogun')).toBe(`${COMMUNITY_GUIDE_BASE}shogun-raiden`);
	});
	it('keeps Traveler element slugs', () => {
		expect(communityGuideUrl('anemo-traveler')).toBe(`${COMMUNITY_GUIDE_BASE}anemo-traveler`);
	});
	it('points at the English site', () => {
		expect(COMMUNITY_GUIDE_BASE).toBe('https://genshin-impact-helper-team.github.io/genshin-builds/en/');
	});
});
```

- [ ] **Step 2: Run them and see them fail**

Run (from `frontend/`): `npx vitest run src/lib/recommend.test.ts src/lib/guides.test.ts`
Expected: FAIL (modules not found).

- [ ] **Step 3: Add the types** to `frontend/src/lib/types.ts`, after `interface ArtifactTarget`:

```ts
export interface StatRecommendation {
	main: Record<MainSlot, string[]>;
	subs: string[];
	synced_at: string;
}
```

and in `interface CharacterDetail` add `stat_recommendation: StatRecommendation | null;` after `artifact_check`.

- [ ] **Step 4: Write the helpers**

```ts
// frontend/src/lib/recommend.ts
import { emptyTarget, MAIN_SLOTS } from './artifacts';
import type { ArtifactTarget, StatRecommendation } from './types';

/** The target with HoYoLAB's main stats and substats; sets are kept. */
export function applyRecommendation(target: ArtifactTarget | null, rec: StatRecommendation): ArtifactTarget {
	const base = target ?? emptyTarget();
	return {
		sets: base.sets.map((s) => ({ ...s })),
		main: { sands: [...rec.main.sands], goblet: [...rec.main.goblet], circlet: [...rec.main.circlet] },
		subs: [...rec.subs]
	};
}

const sameSet = (a: string[], b: string[]) => a.length === b.length && a.every((k) => b.includes(k));

/** Main stats compared per slot ignoring order; substats compared in order. */
export function matchesRecommendation(target: ArtifactTarget | null, rec: StatRecommendation): boolean {
	if (!target) return false;
	return MAIN_SLOTS.every((slot) => sameSet(target.main[slot] ?? [], rec.main[slot] ?? []))
		&& target.subs.length === rec.subs.length && target.subs.every((k, i) => rec.subs[i] === k);
}
```

```ts
// frontend/src/lib/guides.ts
/** Third-party community build guides (Genshin Impact Helper Team). Linked only, never fetched. */
export const COMMUNITY_GUIDE_BASE = 'https://genshin-impact-helper-team.github.io/genshin-builds/en/';

// Our slug -> theirs, where they differ (checked against their full character list on 2026-11-24).
const EXCEPTIONS: Record<string, string> = { 'raiden-shogun': 'shogun-raiden' };

export function communityGuideUrl(slug: string): string {
	return COMMUNITY_GUIDE_BASE + (EXCEPTIONS[slug] ?? slug);
}
```

- [ ] **Step 5: Run the tests and type check**

Run: `npx vitest run src/lib/recommend.test.ts src/lib/guides.test.ts` then `npm run check`
Expected: PASS; `svelte-check` 0 errors 0 warnings.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/recommend.ts frontend/src/lib/recommend.test.ts frontend/src/lib/guides.ts frontend/src/lib/guides.test.ts
git commit -m "feat(frontend): recommendation and community-guide helpers"
```

---

### Task 7: Suggestions card, Guide link and e2e

**Files:**
- Create: `frontend/src/lib/BuildSuggestions.svelte`, `frontend/src/lib/GuideLink.svelte`
- Modify: `frontend/src/routes/characters/[slug]/build/+page.svelte` (the `Suggestions` section at the end)
- Modify: `frontend/src/routes/characters/[slug]/guide/+page.svelte` (line with `guide-howto-slot` and the `.howto` styles)
- Modify: `frontend/e2e/characters.spec.ts` (the two slot assertions)
- Create: `frontend/e2e/build-guides.spec.ts`

**Interfaces:**
- Consumes: `getCharacterPage()` (`p.c`, `p.saveGoal(body)`), `applyRecommendation`, `matchesRecommendation`, `communityGuideUrl`, `STAT_LABELS`, `MAIN_SLOTS`; seeded data from Task 5.
- Produces: test ids `build-suggestions`, `suggestion-{slot}-{key}`, `suggestion-sub-{key}`, `suggestions-apply`, `suggestions-match`, `suggestions-empty`, `guide-howto`, `community-guide-link`.

- [ ] **Step 1: Write the e2e tests first**

```ts
// frontend/e2e/build-guides.spec.ts
import { expect, test } from '@playwright/test';

type Snap = { id: number; goal: string; artifact_target: unknown; artifacts_done: boolean };

async function snapshot(page: import('@playwright/test').Page, slug: string): Promise<Snap> {
	const c = await (await page.request.get(`/api/characters/${slug}`)).json();
	return { id: c.id, goal: c.goal, artifact_target: c.artifact_target, artifacts_done: c.artifacts_done };
}

async function restore(page: import('@playwright/test').Page, s: Snap) {
	await page.request.put(`/api/characters/${s.id}/goal`, { data: { goal: s.goal } });
	await page.request.put(`/api/characters/${s.id}/goal`,
		{ data: { artifact_target: s.artifact_target, artifacts_done: s.artifacts_done } });
}

test('Build suggestions show HoYoLAB stats and Apply updates the target', async ({ page }) => {
	const original = await snapshot(page, 'bennett');
	try {
		await page.goto('/characters/bennett/build');
		const card = page.getByTestId('build-suggestions');
		await expect(card).toContainText('HoYoLAB recommends');
		await expect(card.getByTestId('suggestion-sands-er')).toBeVisible();
		await expect(card.getByTestId('suggestion-sub-hp')).toBeVisible();
		await card.getByTestId('suggestions-apply').click();
		await expect(card.getByTestId('suggestions-match')).toBeVisible();
		const arts = page.getByTestId('build-artifacts');
		await expect(arts.getByTestId('stat-goblet-pyro').locator('button')).toHaveAttribute('aria-pressed', 'true');
		await expect(arts.getByTestId('artifact-set-0')).toHaveValue('15007');           // sets kept
	} finally {
		await restore(page, original);
	}
});

test('Build suggestions say when the target already matches', async ({ page }) => {
	await page.goto('/characters/furina/build');
	await expect(page.getByTestId('suggestions-match')).toBeVisible();
	await expect(page.getByTestId('suggestions-apply')).toHaveCount(0);
});

test('Build suggestions empty state', async ({ page }) => {
	await page.goto('/characters/neuvillette/build');
	await expect(page.getByTestId('suggestions-empty')).toContainText('No HoYoLAB recommendation yet');
});

test('Setting Build prefills the artifact target from the recommendation', async ({ page }) => {
	const original = await snapshot(page, 'xiangling');
	try {
		await page.goto('/characters/xiangling/build');
		await expect(page.getByTestId('suggestions-apply')).toHaveCount(0);              // not Build: read-only
		await page.getByTestId('set-build').click();
		const arts = page.getByTestId('build-artifacts');
		await expect(arts.getByTestId('stat-sands-em').locator('button')).toHaveAttribute('aria-pressed', 'true');
		await expect(page.getByTestId('suggestions-match')).toBeVisible();
	} finally {
		await restore(page, { ...original, artifact_target: null });
	}
});

test('Guide links to the community build guide', async ({ page }) => {
	await page.goto('/characters/bennett/guide');
	const link = page.getByTestId('community-guide-link');
	await expect(link).toHaveAttribute('href', 'https://genshin-impact-helper-team.github.io/genshin-builds/en/bennett');
	await expect(link).toHaveAttribute('target', '_blank');
	await expect(link).toHaveAttribute('rel', 'noopener noreferrer');
	await expect(page.getByTestId('guide-howto')).toContainText('not affiliated with Ad Astra');
});
```

In `frontend/e2e/characters.spec.ts` replace
`await expect(page.getByTestId('build-suggestions-slot')).toContainText('sub-project 9');` with
`await expect(page.getByTestId('build-suggestions')).toContainText('Suggestions');`
and
`await expect(page.getByTestId('guide-howto-slot')).toContainText('sub-project 9');` with
`await expect(page.getByTestId('guide-howto')).toContainText('How to play');`.

- [ ] **Step 2: Run them and see them fail**

Run (from `frontend/`): `PYTHON=PY npx playwright test e2e/build-guides.spec.ts e2e/characters.spec.ts`
Expected: FAIL (test ids not found).

- [ ] **Step 3: Write `frontend/src/lib/BuildSuggestions.svelte`**

```svelte
<script lang="ts">
	import { MAIN_SLOTS, STAT_LABELS } from './artifacts';
	import { getCharacterPage } from './characterPage.svelte';
	import { applyRecommendation, matchesRecommendation } from './recommend';

	let { editing }: { editing: boolean } = $props();
	const p = getCharacterPage();
	const c = $derived(p.c!);
	const rec = $derived(c.stat_recommendation);
	const matches = $derived(rec ? matchesRecommendation(c.artifact_target, rec) : false);
	let saving = $state(false);

	async function apply() {
		if (!rec || saving) return;
		saving = true;
		try {
			await p.saveGoal({ artifact_target: applyRecommendation(c.artifact_target, rec) });
		} finally {
			saving = false;
		}
	}
	const label = (k: string) => STAT_LABELS[k] ?? k;
	const date = (iso: string) => iso.slice(0, 10);
</script>

<section class="card" data-testid="build-suggestions">
	<h2>Suggestions</h2>
	{#if rec}
		<p class="muted small">HoYoLAB recommends · synced {date(rec.synced_at)}</p>
		{#each MAIN_SLOTS as slot (slot)}
			<div class="row">
				<span class="label">{slot[0].toUpperCase() + slot.slice(1)}</span>
				{#each rec.main[slot] as key (key)}
					<span class="pill" data-testid="suggestion-{slot}-{key}">{label(key)}</span>
				{:else}
					<span class="muted small">No preference</span>
				{/each}
			</div>
		{/each}
		<div class="row">
			<span class="label">Substats</span>
			{#each rec.subs as key, i (key)}
				<span class="pill" data-testid="suggestion-sub-{key}">{i + 1}. {label(key)}</span>
			{/each}
		</div>
		{#if matches}
			<p class="ok small" data-testid="suggestions-match">Your target matches.</p>
		{:else if editing}
			<button type="button" data-testid="suggestions-apply" disabled={saving} onclick={apply}>
				Apply to artifact target
			</button>
		{/if}
	{:else}
		<p class="muted" data-testid="suggestions-empty">
			No HoYoLAB recommendation yet. It arrives with the next sync of an owned character.
		</p>
	{/if}
	<p class="muted small foot">Talent, set and team suggestions are not available from any open source.</p>
</section>

<style>
	.row { display: flex; flex-wrap: wrap; gap: 4px; align-items: center; margin-bottom: 6px; }
	.label { width: 64px; font-size: 12px; color: var(--muted); }
	.pill { font-size: 12px; padding: 2px 8px; border-radius: 999px; border: 1px solid var(--el, var(--gold));
		color: var(--text); }
	.small { font-size: 11px; }
	.ok { color: var(--building); }
	.foot { margin-top: 10px; }
	button { margin-top: 6px; }
</style>
```

- [ ] **Step 4: Write `frontend/src/lib/GuideLink.svelte`**

```svelte
<script lang="ts">
	import { communityGuideUrl } from './guides';

	let { slug }: { slug: string } = $props();
</script>

<section class="card howto" data-testid="guide-howto">
	<h2>How to play</h2>
	<a data-testid="community-guide-link" href={communityGuideUrl(slug)} target="_blank" rel="noopener noreferrer">
		Community build guide ↗
	</a>
	<p class="muted small">
		Third-party guide by the Genshin Impact Helper Team (all rights reserved), not affiliated with Ad Astra.
	</p>
</section>

<style>
	.howto { margin-bottom: 12px; }
	a { color: var(--el, var(--gold)); font-weight: 600; }
	.small { font-size: 11px; margin-top: 6px; }
</style>
```

- [ ] **Step 5: Use them in the pages**

`build/+page.svelte`: add `import BuildSuggestions from '$lib/BuildSuggestions.svelte';` and replace

```svelte
	<section class="card">
		<h2>Suggestions</h2>
		<div class="slot" data-testid="build-suggestions-slot">Recommended targets arrive with sub-project 9 (Build recommendations).</div>
	</section>
```

with

```svelte
	<BuildSuggestions {editing} />
```

If the `.slot` style in this file is now unused, remove it (svelte-check warns on unused selectors).

`guide/+page.svelte`: add `import GuideLink from '$lib/GuideLink.svelte';`, replace the `guide-howto-slot` line with `<GuideLink slug={c.slug} />`, and delete the `.howto` and `.howto b` style rules (and `.slot` if now unused).

- [ ] **Step 6: Run the checks and the e2e tests**

Run (from `frontend/`): `npm run check`, then `PYTHON=PY npx playwright test e2e/build-guides.spec.ts e2e/characters.spec.ts e2e/artifacts.spec.ts`
Expected: svelte-check 0/0; all PASS.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/BuildSuggestions.svelte frontend/src/lib/GuideLink.svelte "frontend/src/routes/characters/[slug]/build/+page.svelte" "frontend/src/routes/characters/[slug]/guide/+page.svelte" frontend/e2e/characters.spec.ts frontend/e2e/build-guides.spec.ts
git commit -m "feat(frontend): Build suggestions card and Guide community link"
```

---

### Task 8: Full verification

**Files:** none changed unless a check fails.

- [ ] **Step 1: Backend** — from `backend/`: `PY -m pytest -q`. Expected: all pass (697 + about 29 new).
- [ ] **Step 2: Frontend** — from `frontend/`: `npm run check` (0/0), `npx vitest run` (181 + 11 new), `npm run build` (ok), `PYTHON=PY npx playwright test` (64 + 5 new).
- [ ] **Step 3: Leftovers** — `git grep -n "sub-project 9" -- frontend/src` returns nothing; `git grep -n "build-suggestions-slot\|guide-howto-slot"` returns nothing.
- [ ] **Step 4: Sensitive scan** — `git diff main --stat` and `git diff main | grep -n -i -E "ltoken|cookie_token|account_id|@gmail|users[/\\\\][a-z]"` return nothing new.
- [ ] **Step 5: Commit** any fix with a message describing it.

---

## Self-review

- **Spec coverage:** §3.1 → Task 1; §3.2 → Task 2 (+ persist in Task 3); §3.3 → no change (noted); §4 → Task 4; §5 → Task 4; §6.1 → Tasks 6–7; §6.2 → Tasks 6–7 (amendment 1); §7 rows → Tasks 2, 3, 4, 7; §8 → Global Constraints + Task 8 scan; §9 → tests in each task; §11 → Task 8.
- **Types:** `StatRecommendation` (Python dataclass, `to_json`) / `CharacterStatRecommendation` (ORM) / `StatRecommendation` (TS, has `synced_at`) are used consistently; test ids in Task 7 match the components.
