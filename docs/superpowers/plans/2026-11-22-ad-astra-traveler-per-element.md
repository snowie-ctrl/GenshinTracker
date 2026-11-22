# Traveler per Element Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split the single Traveler into seven plannable characters ("Anemo Traveler" … "Cryo Traveler"), each with its own talents, constellation, goal and material plan. Also remove the Manekin as a character.

**Architecture:**
- **Ids:** each element gets an Ad Astra-only id `10000005 * 100 + calc_element` (Pyro 1 … Cryo 7, the HoYoLAB calculator's element numbers). These ids live in `game_character`, `owned_character` and every table keyed on `character_id`, so goals, teams and gaps need no structural change.
- **Per-element state:** a new user-data table `traveler_element` holds what HoYoLAB cannot report for elements other than the current one (unlocked flag, talents, constellation).
- **Sync fan-out:** sync writes shared fields (level, weapon, friendship, stats, artifacts) to every owned element row.
- **Planner:** sends the body id plus `element_attr_id` to the calculator, and counts the shared level and weapon once through a "carrier" element.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, SQLite; genshin.py 1.7.32; SvelteKit (Svelte 5 runes, TypeScript), Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-22-ad-astra-traveler-per-element-design.md` (approved 2026-11-22). Read it before starting any task.

## Global Constraints

- Cookie values live only in the git-ignored `.env`. They are never logged, returned by the API or committed.
- Code that talks to HoYoLAB stays in `backend/app/sync/` (and `wishes/`). `backend/app/gamedata/traveler.py` holds pure id helpers only.
- Test fixtures use only the made-up UID 800000001. No personal data or game art is committed; images load at runtime via `/api/img`.
- The user's email is never sent anywhere.
- Element ids: Pyro 1000000501, Anemo 1000000502, Geo 1000000503, Dendro 1000000504, Electro 1000000505, Hydro 1000000506, Cryo 1000000507.
- Display name `"{Element} Traveler"`; slug `"{element}-traveler"` (lower case).
- Body ids: boy 10000005, girl 10000007. Manekin raw ids 10000117 and 10000118 are dropped everywhere.
- Settings keys: `traveler_body` (`"boy"` | `"girl"`, default `"girl"`) and `traveler_current_element` (element name or `None`, default `None`).
- Shared across elements: level, weapon, friendship, stats, artifacts. Per element: talents and constellation.
- Backend tests: `C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe -m pytest -q`, run from `backend/`.
- Frontend: run `npm ci` once in `frontend/` in a fresh worktree. Then `npm run check`, `npx vitest run`, `npm run build`, and `PYTHON=<that python> npx playwright test`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

**Spec clarification (applied in Task 2):** the migration seeds `traveler_element` and `traveler_current_element` **only when an old Traveler `owned_character` row exists**. On a fresh database it would otherwise invent a "seen" Anemo Traveler. When there is no old row, goals and teams on 10000005 still move to Anemo (1000000502).

## Review Focus

1. **HoYoLAB reports a Traveler element Ad Astra doesn't know yet** (a future element). Expected: the sync logs the element name and keeps the previous Traveler rows. The rest of the roster still saves and nothing crashes. Test in Task 3.
2. **Fresh database with no Traveler at all, upgraded to 0007.** Expected: the table is created and no `traveler_element` row or setting is written. Test in Task 2.
3. **The user edits talents for an element, then switches to that element in game and syncs.** Expected: the synced values replace the manual ones, and `source` becomes `"sync"`. Test in Task 3.
4. **The user ticks "Unlocked" before the Traveler has ever been synced** (no owned Traveler row to copy level and weapon from). Expected: the flag is saved, no owned row is created, and there is no 500. The element appears as owned after the next sync. Test in Task 6.
5. **An old client or saved payload sends the raw body id (10000007) or a Manekin id to the team save.** Expected: 422 "Unknown character …", never a team holding an id with no character. Test in Task 5.

---

## File Map

| File | Change | Responsibility |
|---|---|---|
| `backend/app/gamedata/traveler.py` | create | Pure id helpers and constants |
| `backend/app/gamedata/yatta.py` | modify | Per-element parse, Manekin skipped, new `canonical_id` |
| `backend/app/gamedata/service.py` | modify | Pass `traveler_body` to the parser |
| `backend/app/settings/store.py` | modify | Two new setting defaults |
| `backend/app/db/models.py` | modify | `TravelerElement` model |
| `backend/migrations/versions/0007_traveler_elements.py` | create | Data migration |
| `backend/app/traveler/__init__.py`, `backend/app/traveler/store.py` | create | `traveler_element` state, owned-element fan-out |
| `backend/app/sync/hoyolab.py` | modify | Element-aware mappers, `GapCharacter` fields, talent ids per element |
| `backend/app/sync/chronicle.py` | modify | Element-aware team ids, Manekin dropped |
| `backend/app/sync/persist.py` | modify | Call the traveler store from roster, details and challenge saves |
| `backend/app/sync/runner.py` | modify | Talent-id lookup by body and element |
| `backend/app/planner/requests.py`, `backend/app/planner/characters.py` | modify | Carrier logic; `UNSUPPORTED` removed |
| `backend/app/good/keys.py` | modify | Per-element GOOD keys |
| `backend/app/teams/store.py` | modify | No more `canonical_id` on save |
| `backend/app/api/traveler.py` | create | `PUT /api/traveler/{element_id}` |
| `backend/app/api/characters.py`, `backend/app/main.py` | modify | `traveler` block in the detail payload; router registration |
| `backend/app/devseed.py` | modify | Cryo Traveler owned, Anemo Traveler game row |
| `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts` | modify | `TravelerInfo` type, `setTraveler` call |
| `frontend/src/lib/traveler.ts` (+ test) | create | Pure form helpers |
| `frontend/src/lib/TravelerElementCard.svelte` | create | Unlocked toggle and talent/constellation editor |
| `frontend/src/routes/characters/[slug]/+page.svelte` | modify | Render the card for Traveler elements |
| `frontend/e2e/characters.spec.ts` | modify | Traveler e2e test |

---

### Task 1: Traveler ids and Yatta parsing

**Files:**
- Create: `backend/app/gamedata/traveler.py`
- Modify: `backend/app/gamedata/yatta.py`, `backend/app/gamedata/service.py:49-66` (`refresh`), `backend/app/settings/store.py:9-17`
- Test: `backend/tests/test_traveler_ids.py` (new), `backend/tests/test_gamedata.py:16-30`, `backend/tests/test_hoyolab.py:20-25`

**Interfaces:**
- Produces (in `app.gamedata.traveler`): `BASE = 10000005`, `BODY_IDS: dict[str, int]`, `MANEKIN_RAW_IDS: frozenset[int]`, `TRAVELER_ELEMENTS: dict[str, int]`, `TRAVELER_IDS: dict[int, str]`, `TRAVELER_PENDING = 10000005`, `traveler_id(element: str) -> int`, `is_traveler(cid: int) -> bool`, `element_of(cid: int) -> str`, `calc_element(cid: int) -> int`, `body_of(raw_id: int) -> str | None`, `traveler_name(element: str) -> str`, `body_icon(body: str) -> str`.
- Produces (in `app.gamedata.yatta`): `canonical_id(raw: int | str, element: str | None = None) -> int | None`, `parse_avatar_list(payload: dict, body: str = "girl") -> list[CharacterData]`, `fetch_avatar_list(http, body: str = "girl")`. `VARIANT_ICONS` keeps only the two Traveler body icons. `TRAVELER_ID` and `MANEKIN_ID` stay **temporarily** as legacy constants, because `requests.py` and `keys.py` still import them; Tasks 4 and 5 remove them.
- Produces: setting defaults `traveler_body = "girl"` and `traveler_current_element = None`.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_traveler_ids.py`:

```python
import pytest

from app.gamedata.traveler import (TRAVELER_IDS, TRAVELER_PENDING, body_icon, body_of, calc_element, element_of,
                                   is_traveler, traveler_id, traveler_name)
from app.gamedata.yatta import canonical_id


def test_ids_are_base_times_100_plus_calculator_number():
    assert traveler_id("Pyro") == 1000000501
    assert traveler_id("Anemo") == 1000000502
    assert traveler_id("Cryo") == 1000000507
    assert sorted(TRAVELER_IDS) == list(range(1000000501, 1000000508))
    assert element_of(1000000503) == "Geo" and calc_element(1000000503) == 3
    assert is_traveler(1000000505) and not is_traveler(10000005) and not is_traveler(10000032)


def test_body_helpers():
    assert body_of(10000005) == "boy" and body_of(10000007) == "girl" and body_of(10000032) is None
    assert body_icon("boy") == "UI_AvatarIcon_PlayerBoy" and body_icon("girl") == "UI_AvatarIcon_PlayerGirl"
    assert traveler_name("Hydro") == "Hydro Traveler"


def test_unknown_element_raises():
    with pytest.raises(KeyError):
        traveler_id("Lunar")


def test_canonical_id():
    assert canonical_id(10000007, "Geo") == 1000000503
    assert canonical_id("10000005-anemo", "Anemo") == 1000000502
    assert canonical_id(10000005) == TRAVELER_PENDING          # element not known: resolved later
    assert canonical_id(10000007, "Lunar") == TRAVELER_PENDING  # element Ad Astra doesn't know
    assert canonical_id(10000117) is None and canonical_id(10000118, "Cryo") is None
    assert canonical_id(10000032) == 10000032 and canonical_id(10000032, "Pyro") == 10000032
```

In `backend/tests/test_gamedata.py`, replace `test_canonical_id` and `test_parse_collapses_variants_and_maps_names` with:

```python
def test_parse_splits_traveler_per_element_and_drops_manekin():
    chars = {c.id: c for c in parse_avatar_list(load_fixture("yatta_avatar.json"))}
    assert set(chars) == {10000032, 10000089, 10000052, 1000000502, 1000000501, 1000000503, 10000999}
    anemo = chars[1000000502]
    assert (anemo.name, anemo.slug, anemo.element, anemo.icon) == (
        "Anemo Traveler", "anemo-traveler", "Anemo", "UI_AvatarIcon_PlayerGirl")
    assert anemo.splash == "UI_Gacha_AvatarImg_PlayerGirl"
    assert chars[1000000503].name == "Geo Traveler"          # came from a 10000007-* key
    raiden = chars[10000052]
    assert (raiden.element, raiden.weapon_type, raiden.slug) == ("Electro", "Polearm", "raiden-shogun")
    assert raiden.splash == "UI_Gacha_AvatarImg_Shougun"


def test_parse_uses_body_icon():
    chars = {c.id: c for c in parse_avatar_list(load_fixture("yatta_avatar.json"), body="boy")}
    assert chars[1000000501].icon == "UI_AvatarIcon_PlayerBoy"
```

Keep the existing `canonical_id` import line, and remove its now-unused names if the linter complains. In `backend/tests/test_hoyolab.py:24`, change the expected tuple to `(1000000503, 10000007, "Geo", 90)`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `...python.exe -m pytest -q tests/test_traveler_ids.py tests/test_gamedata.py tests/test_hoyolab.py`
Expected: FAIL. `ModuleNotFoundError: app.gamedata.traveler`, and wrong ids in the parse tests.

- [ ] **Step 3: Implement**

Create `backend/app/gamedata/traveler.py`:

```python
"""Traveler element ids. Inside Ad Astra the Traveler is one character per element; HoYoLAB only knows
the body id (10000005 boy, 10000007 girl) plus a calculator element number. Pure helpers, no I/O."""
from __future__ import annotations

BASE = 10000005
BODY_IDS: dict[str, int] = {"boy": 10000005, "girl": 10000007}
MANEKIN_RAW_IDS = frozenset({10000117, 10000118})
# HoYoLAB calculator element numbers (genshin.py CALCULATOR_ELEMENTS)
TRAVELER_ELEMENTS: dict[str, int] = {"Pyro": 1, "Anemo": 2, "Geo": 3, "Dendro": 4, "Electro": 5, "Hydro": 6, "Cryo": 7}
TRAVELER_IDS: dict[int, str] = {BASE * 100 + n: el for el, n in TRAVELER_ELEMENTS.items()}
TRAVELER_PENDING = BASE  # a Traveler whose element is not known yet; persist resolves it to the current element


def traveler_id(element: str) -> int:
    return BASE * 100 + TRAVELER_ELEMENTS[element]


def is_traveler(cid: int) -> bool:
    return cid in TRAVELER_IDS


def element_of(cid: int) -> str:
    return TRAVELER_IDS[cid]


def calc_element(cid: int) -> int:
    return TRAVELER_ELEMENTS[TRAVELER_IDS[cid]]


def body_of(raw_id: int) -> str | None:
    return next((b for b, i in BODY_IDS.items() if i == raw_id), None)


def traveler_name(element: str) -> str:
    return f"{element} Traveler"


def body_icon(body: str) -> str:
    return "UI_AvatarIcon_PlayerBoy" if body == "boy" else "UI_AvatarIcon_PlayerGirl"
```

In `backend/app/gamedata/yatta.py`, replace the block from `TRAVELER_ID = 10000005` through `_FIXED_NAMES = …` and the functions `canonical_id` and `parse_avatar_list` with:

```python
from app.gamedata.traveler import (BODY_IDS, MANEKIN_RAW_IDS, TRAVELER_ELEMENTS, TRAVELER_PENDING, body_icon,
                                   traveler_id, traveler_name)

TRAVELER_ID = 10000005   # legacy: removed in Task 4 (planner) and Task 5 (GOOD keys)
MANEKIN_ID = 10000117    # legacy: removed in Task 5
VARIANT_ICONS = {10000005: "UI_AvatarIcon_PlayerBoy", 10000007: "UI_AvatarIcon_PlayerGirl"}
```

```python
def canonical_id(raw: int | str, element: str | None = None) -> int | None:
    """Our id for a HoYoLAB/Yatta character id. Traveler: the element's id (TRAVELER_PENDING when the
    element is missing or unknown). Manekin: None (not a character in Ad Astra)."""
    n = int(str(raw).split("-")[0])
    if n in MANEKIN_RAW_IDS:
        return None
    if n in BODY_IDS.values():
        return traveler_id(element) if element in TRAVELER_ELEMENTS else TRAVELER_PENDING
    return n


def parse_avatar_list(payload: dict, body: str = "girl") -> list[CharacterData]:
    by_id: dict[int, CharacterData] = {}
    for key, v in payload["data"]["items"].items():
        element = ELEMENTS.get(v.get("element") or "")
        cid = canonical_id(key, element)
        if cid is None or cid == TRAVELER_PENDING:
            continue  # Manekin, or a Traveler element we have no id for yet
        traveler = int(str(key).split("-")[0]) in BODY_IDS.values()
        name = traveler_name(element) if traveler else v["name"]
        icon = body_icon(body) if traveler else v["icon"]
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


async def fetch_avatar_list(http: httpx.AsyncClient, body: str = "girl") -> list[CharacterData]:
    response = await http.get(YATTA_AVATAR_URL, timeout=30)
    response.raise_for_status()
    return parse_avatar_list(response.json(), body)
```

In `backend/app/gamedata/service.py` `refresh`, read the body before fetching:

```python
    with session_factory() as s:
        if not force and not needs_refresh(s, now):
            return False
        body = str(get_setting(s, "traveler_body"))
    try:
        chars = await fetch_avatar_list(http, body)
```

Add `from app.settings.store import get_setting` to the imports. If that creates an import cycle, import it inside the function.

In `backend/app/settings/store.py` `DEFAULTS`, add:

```python
    "traveler_body": "girl",             # "boy" | "girl", from the synced Traveler (sub-project 2)
    "traveler_current_element": None,    # e.g. "Cryo"; the element HoYoLAB reported last
```

In `backend/app/sync/persist.py` the import `from app.gamedata.yatta import VARIANT_ICONS` stays valid.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `...python.exe -m pytest -q`
Expected: all pass. `test_teams_store.py::test_traveler_variant_is_stored_canonically` still passes, because 10000007 now maps to `TRAVELER_PENDING` (10000005), which is still in `GAME_ROWS`. Task 5 replaces that test. If `test_settings_store.py` asserts the exact `DEFAULTS` keys, add the two new keys to its expectation.

- [ ] **Step 5: Commit**

```bash
git add backend/app/gamedata/traveler.py backend/app/gamedata/yatta.py backend/app/gamedata/service.py backend/app/settings/store.py backend/tests
git commit -m "feat(traveler): per-element Traveler ids and Yatta parsing, Manekin dropped from game data"
```

---

### Task 2: `traveler_element` table and migration 0007

**Files:**
- Modify: `backend/app/db/models.py` (add the model after `CharacterGoal`)
- Create: `backend/migrations/versions/0007_traveler_elements.py`
- Test: `backend/tests/test_migration_0007.py` (new), `backend/tests/test_db.py` (add the table name to `TABLES`)

**Interfaces:**
- Consumes: none (the migration copies its constants on purpose, so later code changes can't alter it).
- Produces: model `TravelerElement(element_id: int PK, seen: bool, unlocked: bool, talent_normal: int, talent_skill: int, talent_burst: int, constellation: int, source: str, updated_at: datetime)`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_db.py`, add `"traveler_element"` to `TABLES`. `test_models_match_migrations` will then catch any mismatch between model and migration.

Create `backend/tests/test_migration_0007.py`:

```python
import json
from datetime import datetime

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from app.db.engine import BACKEND_DIR, make_engine

NOW = "2026-11-22 12:00:00"


def upgrade(engine, rev: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.upgrade(cfg, rev)


def downgrade(engine, rev: str) -> None:
    cfg = Config(str(BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    with engine.begin() as conn:
        cfg.attributes["connection"] = conn
        command.downgrade(cfg, rev)


def owned(conn, cid, element, icon, talents=(4, 9, 10), cons=2):
    conn.execute(text(
        "INSERT INTO owned_character (character_id, name, element, icon, level, constellation, friendship, "
        "talent_normal, talent_skill, talent_burst, weapon_name, weapon_icon, weapon_rarity, weapon_level, "
        "weapon_refinement, weapon_id, stats, synced_at) VALUES (:c, 'X', :e, :i, 80, :k, 10, :n, :s, :b, "
        "'W', 'w', 4, 90, 1, NULL, '[]', :t)"),
        dict(c=cid, e=element, i=icon, k=cons, n=talents[0], s=talents[1], b=talents[2], t=NOW))


def goal(conn, cid):
    conn.execute(text("INSERT INTO character_goal (character_id, goal, target_level, updated_at) "
                      "VALUES (:c, 'build', 90, :t)"), dict(c=cid, t=NOW))


def team(conn, tid, members):
    conn.execute(text("INSERT INTO team (id, name, notes, sort_order, created_at, updated_at) "
                      "VALUES (:i, 'T', '', 0, :t, :t)"), dict(i=tid, t=NOW))
    for slot, cid in enumerate(members):
        conn.execute(text("INSERT INTO team_member (team_id, slot, character_id, role) VALUES (:t, :s, :c, '')"),
                     dict(t=tid, s=slot, c=cid))


def seeded(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0006")
    with engine.begin() as conn:
        owned(conn, 10000005, "Cryo", "UI_AvatarIcon_PlayerGirl")
        owned(conn, 10000117, "Cryo", "UI_AvatarIcon_MannequinGirl")
        owned(conn, 10000032, "Pyro", "UI_AvatarIcon_Bennett")
        goal(conn, 10000005)
        goal(conn, 10000117)
        team(conn, 1, [10000032, 10000117, 10000005])
        team(conn, 2, [10000117])
        conn.execute(text("INSERT INTO good_weapon (weapon_id, level, ascension, refinement, location, character_id, lock) "
                          "VALUES (11401, 90, 6, 1, 'Manekina', 10000117, 0), (11401, 90, 6, 1, 'Traveler', 10000005, 0)"))
        conn.execute(text("INSERT INTO challenge_run (kind, season, start, \"end\", summary, teams, seen_at, updated_at) "
                          "VALUES ('abyss', '77', NULL, NULL, '{}', :teams, :t, :t)"),
                     dict(teams=json.dumps([[10000005, 10000117, 10000032]]), t=NOW))
        conn.execute(text("INSERT INTO game_meta (key, value) VALUES ('talent_ids', :v)"),
                     dict(v=json.dumps({"10000005": [1, 2, 3], "10000032": [4, 5, 6]})))
    return engine


def test_upgrade_moves_traveler_to_current_element_and_drops_manekin(paths):
    engine = seeded(paths)
    upgrade(engine, "head")
    cryo = 1000000507
    with engine.connect() as conn:
        q = lambda sql: conn.execute(text(sql)).all()  # noqa: E731
        assert q("SELECT character_id FROM character_goal") == [(cryo,)]
        assert q("SELECT team_id, slot, character_id FROM team_member ORDER BY team_id, slot") == [
            (1, 0, 10000032), (1, 1, cryo)]                       # slots closed up
        assert q("SELECT id FROM team") == [(1,)]                  # a Manekin-only team is deleted
        assert q("SELECT location, character_id FROM good_weapon ORDER BY location") == [
            ("Manekina", None), ("Traveler", cryo)]
        assert json.loads(q("SELECT teams FROM challenge_run")[0][0]) == [[cryo, 10000032]]
        assert q("SELECT character_id FROM owned_character") == [(10000032,)]
        row = q("SELECT element_id, seen, unlocked, talent_normal, talent_skill, talent_burst, constellation, source "
                "FROM traveler_element")
        assert row == [(cryo, 1, 0, 4, 9, 10, 2, "sync")]
        settings = dict(q("SELECT key, value FROM setting"))
        assert json.loads(settings["traveler_current_element"]) == "Cryo"
        assert json.loads(settings["traveler_body"]) == "girl"
        assert json.loads(q("SELECT value FROM game_meta WHERE key='talent_ids'")[0][0]) == {"10000032": [4, 5, 6]}
    engine.dispose()


def test_fresh_database_gets_no_invented_traveler(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0006")
    with engine.begin() as conn:
        goal(conn, 10000005)        # a goal without any synced Traveler
    upgrade(engine, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT character_id FROM character_goal")).all() == [(1000000502,)]
        assert conn.execute(text("SELECT count(*) FROM traveler_element")).scalar() == 0
        assert conn.execute(text("SELECT count(*) FROM setting WHERE key LIKE 'traveler_%'")).scalar() == 0
    engine.dispose()


def test_downgrade_folds_elements_back(paths):
    engine = seeded(paths)
    upgrade(engine, "head")
    with engine.begin() as conn:
        goal(conn, 1000000502)      # a second element goal; the current element's (Cryo) one wins
    downgrade(engine, "0006")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT character_id FROM character_goal")).all() == [(10000005,)]
        assert conn.execute(text("SELECT character_id FROM team_member WHERE team_id=1 ORDER BY slot")).all() == [
            (10000032,), (10000005,)]
    engine.dispose()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `...python.exe -m pytest -q tests/test_migration_0007.py tests/test_db.py`
Expected: FAIL. Alembic error "Can't locate revision", or the table is missing.

- [ ] **Step 3: Implement**

Add to `backend/app/db/models.py` after `CharacterGoal`:

```python
class TravelerElement(Base):
    """What HoYoLAB cannot report for Traveler elements other than the current one (sub-project 2)."""
    __tablename__ = "traveler_element"
    element_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    seen: Mapped[bool] = mapped_column(Boolean)              # a sync reported it as the current element
    unlocked: Mapped[bool] = mapped_column(Boolean)          # ticked by the user
    talent_normal: Mapped[int] = mapped_column(Integer)
    talent_skill: Mapped[int] = mapped_column(Integer)
    talent_burst: Mapped[int] = mapped_column(Integer)
    constellation: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String)              # sync | manual
    updated_at: Mapped[datetime] = mapped_column(DateTime)
```

Create `backend/migrations/versions/0007_traveler_elements.py`:

```python
"""Ad Astra sub-project 2: Traveler per element, Manekin removed

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-22

Downgrade folds every element back into 10000005 (keeping the current element's goal) and drops
traveler_element. Manekin data deleted by the upgrade is NOT restored.
"""
import json
from datetime import datetime, timezone

import sqlalchemy as sa
from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

# Frozen copies: later code changes must not change what this migration does.
BASE = 10000005
RAW_TRAVELER = (10000005, 10000007)
MANEKIN = (10000117, 10000118)
ELEMENTS = {"Pyro": 1, "Anemo": 2, "Geo": 3, "Dendro": 4, "Electro": 5, "Hydro": 6, "Cryo": 7}
ELEMENT_IDS = [BASE * 100 + n for n in ELEMENTS.values()]


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(sep=" ")


def _set_setting(bind, key: str, value) -> None:
    bind.execute(sa.text("INSERT INTO setting (key, value) VALUES (:k, :v) "
                         "ON CONFLICT(key) DO UPDATE SET value = excluded.value"),
                 {"k": key, "v": json.dumps(value)})


def _close_slots(bind, team_ids) -> None:
    for tid in team_ids:
        slots = [r[0] for r in bind.execute(sa.text("SELECT slot FROM team_member WHERE team_id=:t ORDER BY slot"),
                                            {"t": tid})]
        if not slots:
            bind.execute(sa.text("DELETE FROM team_tag WHERE team_id=:t"), {"t": tid})
            bind.execute(sa.text("DELETE FROM team WHERE id=:t"), {"t": tid})
            continue
        for new, old in enumerate(slots):
            if new != old:
                bind.execute(sa.text("UPDATE team_member SET slot=:n WHERE team_id=:t AND slot=:o"),
                             {"n": new, "t": tid, "o": old})


def _map_challenge_teams(bind, fn) -> None:
    for kind, season, teams in bind.execute(sa.text("SELECT kind, season, teams FROM challenge_run")).all():
        old = json.loads(teams) if isinstance(teams, str) else teams
        new = [[m for m in (fn(c) for c in team) if m is not None] for team in old or []]
        if new != old:
            bind.execute(sa.text("UPDATE challenge_run SET teams=:v WHERE kind=:k AND season=:s"),
                         {"v": json.dumps(new), "k": kind, "s": season})


def _drop_talent_cache(bind, ids) -> None:
    row = bind.execute(sa.text("SELECT value FROM game_meta WHERE key='talent_ids'")).first()
    if row is None or row[0] is None:
        return
    value = json.loads(row[0]) if isinstance(row[0], str) else row[0]
    kept = {k: v for k, v in value.items() if int(k) not in ids}
    bind.execute(sa.text("UPDATE game_meta SET value=:v WHERE key='talent_ids'"), {"v": json.dumps(kept)})


def upgrade() -> None:
    op.create_table(
        "traveler_element",
        sa.Column("element_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("seen", sa.Boolean(), nullable=False),
        sa.Column("unlocked", sa.Boolean(), nullable=False),
        sa.Column("talent_normal", sa.Integer(), nullable=False),
        sa.Column("talent_skill", sa.Integer(), nullable=False),
        sa.Column("talent_burst", sa.Integer(), nullable=False),
        sa.Column("constellation", sa.Integer(), nullable=False),
        sa.Column("source", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    bind = op.get_bind()
    old = bind.execute(sa.text(
        "SELECT element, icon, talent_normal, talent_skill, talent_burst, constellation "
        "FROM owned_character WHERE character_id=:i"), {"i": BASE}).first()
    element = old.element if old is not None and old.element in ELEMENTS else "Anemo"
    new_id = BASE * 100 + ELEMENTS[element]
    if old is not None:
        bind.execute(sa.text(
            "INSERT INTO traveler_element (element_id, seen, unlocked, talent_normal, talent_skill, talent_burst, "
            "constellation, source, updated_at) VALUES (:e, 1, 0, :n, :s, :b, :c, 'sync', :t)"),
            {"e": new_id, "n": old.talent_normal or 1, "s": old.talent_skill or 1, "b": old.talent_burst or 1,
             "c": old.constellation or 0, "t": _now()})
        _set_setting(bind, "traveler_current_element", element)
        _set_setting(bind, "traveler_body", "boy" if old.icon == "UI_AvatarIcon_PlayerBoy" else "girl")

    for table in ("character_goal", "team_member", "good_weapon", "good_artifact"):
        bind.execute(sa.text(f"UPDATE {table} SET character_id=:n WHERE character_id IN (:a, :b)"),
                     {"n": new_id, "a": RAW_TRAVELER[0], "b": RAW_TRAVELER[1]})

    manekin = {"a": MANEKIN[0], "b": MANEKIN[1]}
    teams = [r[0] for r in bind.execute(sa.text(
        "SELECT DISTINCT team_id FROM team_member WHERE character_id IN (:a, :b)"), manekin)]
    bind.execute(sa.text("DELETE FROM team_member WHERE character_id IN (:a, :b)"), manekin)
    _close_slots(bind, teams)
    for table in ("character_goal", "owned_character", "owned_artifact", "material_gap"):
        bind.execute(sa.text(f"DELETE FROM {table} WHERE character_id IN (:a, :b)"), manekin)
    for table in ("good_weapon", "good_artifact"):
        bind.execute(sa.text(f"UPDATE {table} SET character_id=NULL WHERE character_id IN (:a, :b)"), manekin)
    traveler_raw = {"a": RAW_TRAVELER[0], "b": RAW_TRAVELER[1]}
    for table in ("owned_character", "owned_artifact", "material_gap"):
        bind.execute(sa.text(f"DELETE FROM {table} WHERE character_id IN (:a, :b)"), traveler_raw)
    bind.execute(sa.text("DELETE FROM game_character WHERE id IN (:a, :b, :c, :d)"),
                 {"a": RAW_TRAVELER[0], "b": RAW_TRAVELER[1], "c": MANEKIN[0], "d": MANEKIN[1]})
    bind.execute(sa.text("DELETE FROM game_meta WHERE key='characters_fetched_at'"))  # refresh on next start
    _drop_talent_cache(bind, {*RAW_TRAVELER, *MANEKIN})
    _map_challenge_teams(bind, lambda c: new_id if c in RAW_TRAVELER else (None if c in MANEKIN else c))


def downgrade() -> None:
    bind = op.get_bind()
    row = bind.execute(sa.text("SELECT value FROM setting WHERE key='traveler_current_element'")).first()
    current = json.loads(row[0]) if row is not None and row[0] is not None else None
    keep = BASE * 100 + ELEMENTS[current] if current in ELEMENTS else None
    goal_ids = [r[0] for r in bind.execute(sa.text(
        f"SELECT character_id FROM character_goal WHERE character_id IN ({','.join(map(str, ELEMENT_IDS))}) "
        "ORDER BY character_id"))]
    if goal_ids:
        winner = keep if keep in goal_ids else goal_ids[0]
        bind.execute(sa.text(f"DELETE FROM character_goal WHERE character_id IN "
                             f"({','.join(map(str, ELEMENT_IDS))}) AND character_id != :w"), {"w": winner})
    ids = ",".join(map(str, ELEMENT_IDS))
    # A team may hold two Traveler elements; after folding they would collide on uq_team_member_character.
    bind.execute(sa.text(
        f"DELETE FROM team_member WHERE character_id IN ({ids}) AND slot > ("
        f"SELECT min(m2.slot) FROM team_member m2 WHERE m2.team_id = team_member.team_id "
        f"AND m2.character_id IN ({ids}))"))
    _close_slots(bind, [r[0] for r in bind.execute(sa.text("SELECT id FROM team"))])
    for table in ("character_goal", "team_member", "good_weapon", "good_artifact"):
        bind.execute(sa.text(f"UPDATE {table} SET character_id=:b WHERE character_id IN ({ids})"), {"b": BASE})
    for table in ("owned_character", "owned_artifact", "material_gap"):
        bind.execute(sa.text(f"DELETE FROM {table} WHERE character_id IN ({ids})"))
    bind.execute(sa.text(f"DELETE FROM game_character WHERE id IN ({ids})"))
    bind.execute(sa.text("DELETE FROM setting WHERE key IN ('traveler_current_element', 'traveler_body')"))
    _map_challenge_teams(bind, lambda c: BASE if c in ELEMENT_IDS else c)
    op.drop_table("traveler_element")
```

Add a team with two elements to `test_downgrade_folds_elements_back` before the downgrade (`team(conn, 3, [1000000502, 10000032, 1000000507])`), and assert afterwards that team 3's members are `[(10000005,), (10000032,)]`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `...python.exe -m pytest -q`
Expected: all pass, including `test_models_match_migrations`.

- [ ] **Step 5: Commit**

```bash
git add backend/app/db/models.py backend/migrations/versions/0007_traveler_elements.py backend/tests/test_migration_0007.py backend/tests/test_db.py
git commit -m "feat(traveler): traveler_element table and migration 0007 (Traveler per element, Manekin removed)"
```

---

### Task 3: Traveler state store and sync fan-out

**Files:**
- Create: `backend/app/traveler/__init__.py` (empty), `backend/app/traveler/store.py`
- Modify: `backend/app/sync/hoyolab.py:170-190` (`to_roster_entry`, `to_detail_entry`), `backend/app/sync/chronicle.py` (`_banner`, `to_abyss_run`, `to_theater_runs`, `to_stygian_runs`), `backend/app/sync/persist.py` (`save_roster`, `save_details`, `save_challenge_runs`, `unknown_character_ids`), `backend/tests/helpers.py:12-18` (`GAME_ROWS`)
- Test: `backend/tests/test_traveler_sync.py` (new); update `test_persist.py:41-45`, `test_api_characters.py:29`, `test_chronicle.py:62-65`

**Interfaces:**
- Consumes: Task 1 helpers; Task 2 `TravelerElement`.
- Produces (in `app.traveler.store`):
  - `owned_elements(s) -> list[int]`: element ids with `seen or unlocked`, sorted.
  - `current_element_id(s) -> int | None`: from setting `traveler_current_element`.
  - `get_or_create(s, element_id) -> TravelerElement`: defaults are 1/1/1, C0, `source="manual"`, both flags false.
  - `record_current(s, element_id, raw_id, constellation)`: sets the settings, `seen`, constellation and `source="sync"`. On a body change it also updates game icons and clears the Traveler talent-id cache.
  - `record_current_talents(s, element_id, normal, skill, burst)`.
  - `refresh_owned(s, now) -> set[int]`: builds or updates `OwnedCharacter` and artifact rows for every owned non-current element from the current element's row. Deletes owned rows for elements no longer owned. Returns the ids now owned. Does nothing (returns the existing owned Traveler ids) when the current element has no owned row.
  - `resolve(s, cid) -> int | None`: maps `TRAVELER_PENDING` to the current element id (or `None` when unknown); returns other ids unchanged.
- `RosterEntry.id` for the Traveler is now the element id (or `TRAVELER_PENDING` for an unknown element). `DetailEntry.id` likewise.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/helpers.py`, replace the Traveler row in `GAME_ROWS` with:

```python
    (1000000507, "Cryo Traveler", "cryo-traveler", 5, "Cryo", "Sword", "UI_AvatarIcon_PlayerGirl"),
    (1000000502, "Anemo Traveler", "anemo-traveler", 5, "Anemo", "Sword", "UI_AvatarIcon_PlayerGirl"),
    (1000000503, "Geo Traveler", "geo-traveler", 5, "Geo", "Sword", "UI_AvatarIcon_PlayerGirl"),
```

Create `backend/tests/test_traveler_sync.py`:

```python
from app.db.models import GameMeta, OwnedArtifact, OwnedCharacter, TravelerElement
from app.settings.store import get_setting
from app.sync.persist import save_challenge_runs, save_details, save_roster
from app.sync.chronicle import ChallengeRunInfo
from app.gamedata.traveler import TRAVELER_PENDING
from app.timeutil import utcnow
from app.traveler.store import get_or_create, owned_elements, refresh_owned, resolve
from fakes import make_detail, make_roster
from helpers import seed_game

CRYO, ANEMO, GEO = 1000000507, 1000000502, 1000000503


def sync_cryo(sf, level=80, talents=(4, 9, 10)):
    with sf.begin() as s:
        save_roster(s, [make_roster(10000032, name="Bennett"),
                        make_roster(CRYO, level=level, raw_id=10000007, name="Traveler", element="Cryo")], utcnow())
        save_details(s, [make_detail(10000032), make_detail(CRYO, talents=talents)])


def test_current_element_recorded(session_factory):
    seed_game(session_factory)
    sync_cryo(session_factory)
    with session_factory() as s:
        assert get_setting(s, "traveler_current_element") == "Cryo"
        assert get_setting(s, "traveler_body") == "girl"
        te = s.get(TravelerElement, CRYO)
        assert (te.seen, te.talent_normal, te.talent_skill, te.talent_burst, te.constellation, te.source) == (
            True, 4, 9, 10, 2, "sync")
        assert owned_elements(s) == [CRYO]


def test_unlocked_element_gets_shared_fields_and_its_own_talents(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        te = get_or_create(s, ANEMO)
        te.unlocked, te.talent_normal, te.talent_skill, te.talent_burst, te.constellation = True, 2, 3, 4, 6
    sync_cryo(session_factory, level=90)
    with session_factory() as s:
        a = s.get(OwnedCharacter, ANEMO)
        c = s.get(OwnedCharacter, CRYO)
        assert (a.name, a.element, a.level, a.weapon_name) == ("Anemo Traveler", "Anemo", 90, c.weapon_name)
        assert (a.talent_normal, a.talent_skill, a.talent_burst, a.constellation) == (2, 3, 4, 6)
        assert a.stats == c.stats
        assert [x.set_name for x in s.query(OwnedArtifact).filter_by(character_id=ANEMO)] == ["Noblesse Oblige"]
        assert s.get(OwnedCharacter, 10000032) is not None


def test_switching_element_overwrites_manual_values(session_factory):
    seed_game(session_factory)
    sync_cryo(session_factory)
    with session_factory.begin() as s:
        te = get_or_create(s, GEO)
        te.unlocked, te.talent_normal, te.source = True, 7, "manual"
    with session_factory.begin() as s:
        save_roster(s, [make_roster(GEO, raw_id=10000007, name="Traveler", element="Geo")], utcnow())
        save_details(s, [make_detail(GEO, talents=(1, 2, 3))])
    with session_factory() as s:
        te = s.get(TravelerElement, GEO)
        assert (te.talent_normal, te.talent_skill, te.talent_burst, te.source, te.seen) == (1, 2, 3, "sync", True)
        assert get_setting(s, "traveler_current_element") == "Geo"
        cryo = s.get(OwnedCharacter, CRYO)                     # previous element stays owned with its talents
        assert (cryo.talent_normal, cryo.talent_skill, cryo.talent_burst) == (4, 9, 10)


def test_unknown_element_keeps_previous_rows(session_factory, caplog):
    seed_game(session_factory)
    sync_cryo(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032, name="Bennett"),
                        make_roster(TRAVELER_PENDING, raw_id=10000007, name="Traveler", element="Lunar")], utcnow())
    with session_factory() as s:
        assert s.get(OwnedCharacter, CRYO) is not None
        assert s.get(OwnedCharacter, TRAVELER_PENDING) is None
        assert get_setting(s, "traveler_current_element") == "Cryo"
    assert "Lunar" in caplog.text


def test_body_change_updates_icons_and_clears_talent_cache(session_factory):
    seed_game(session_factory)
    sync_cryo(session_factory)
    with session_factory.begin() as s:
        s.merge(GameMeta(key="talent_ids", value={str(CRYO): [1, 2, 3], "10000032": [4, 5, 6]}))
    with session_factory.begin() as s:
        save_roster(s, [make_roster(CRYO, raw_id=10000005, name="Traveler", element="Cryo")], utcnow())
    with session_factory() as s:
        assert get_setting(s, "traveler_body") == "boy"
        assert s.get(OwnedCharacter, CRYO).icon == "UI_AvatarIcon_PlayerBoy"
        from app.db.models import GameCharacter
        assert s.get(GameCharacter, ANEMO).icon == "UI_AvatarIcon_PlayerBoy"
        assert s.get(GameMeta, "talent_ids").value == {"10000032": [4, 5, 6]}


def test_untick_never_seen_element_removes_owned_row(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        get_or_create(s, ANEMO).unlocked = True
    sync_cryo(session_factory)
    with session_factory.begin() as s:
        s.get(TravelerElement, ANEMO).unlocked = False
        refresh_owned(s, utcnow())
    with session_factory() as s:
        assert s.get(OwnedCharacter, ANEMO) is None
        assert s.query(OwnedArtifact).filter_by(character_id=ANEMO).count() == 0


def test_challenge_teams_resolve_pending_and_drop_none(session_factory):
    seed_game(session_factory)
    sync_cryo(session_factory)
    with session_factory.begin() as s:
        assert resolve(s, TRAVELER_PENDING) == CRYO and resolve(s, 10000032) == 10000032
        save_challenge_runs(s, [ChallengeRunInfo("abyss", "9", None, None, {}, [[TRAVELER_PENDING, 10000032]])],
                            utcnow())
        from app.db.models import ChallengeRun
        assert s.get(ChallengeRun, ("abyss", "9")).teams == [[CRYO, 10000032]]
```

Update existing tests:
- `test_persist.py:41-45`: change the roster to `make_roster(1000000503, raw_id=10000007, name="Traveler", element="Geo")`, and read back `OwnedCharacter` `1000000503`. Keep whatever that test asserts about the icon (`UI_AvatarIcon_PlayerGirl`).
- `test_api_characters.py:29`: use `make_roster(1000000503, raw_id=10000007, name="Traveler", element="Geo")`. Any slug assertion `"traveler"` in that file becomes `"geo-traveler"`.
- `test_chronicle.py:62-65`: the banner `char(10000007, name="Traveler")` has element `"Hydro"`, so assert `b.items[0].id == 1000000506`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `...python.exe -m pytest -q tests/test_traveler_sync.py`
Expected: FAIL. `ModuleNotFoundError: app.traveler`.

- [ ] **Step 3: Implement**

Create `backend/app/traveler/store.py`:

```python
"""Traveler element state (user data) and the fan-out of shared Traveler fields to every owned element.
HoYoLAB only reports the current element; other elements keep what was last seen or typed in."""
from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, GameMeta, OwnedArtifact, OwnedCharacter, TravelerElement
from app.gamedata.traveler import (TRAVELER_ELEMENTS, TRAVELER_IDS, TRAVELER_PENDING, body_icon, body_of,
                                   element_of, traveler_id, traveler_name)
from app.settings.store import get_setting, set_setting
from app.timeutil import utcnow

log = logging.getLogger(__name__)
TALENT_META = "talent_ids"   # same key as app.sync.persist.TALENT_META


def get_or_create(s: Session, element_id: int) -> TravelerElement:
    row = s.get(TravelerElement, element_id)
    if row is None:
        row = TravelerElement(element_id=element_id, seen=False, unlocked=False, talent_normal=1, talent_skill=1,
                              talent_burst=1, constellation=0, source="manual", updated_at=utcnow())
        s.add(row)
        s.flush()
    return row


def owned_elements(s: Session) -> list[int]:
    return sorted(r.element_id for r in s.scalars(select(TravelerElement)) if r.seen or r.unlocked)


def current_element_id(s: Session) -> int | None:
    el = get_setting(s, "traveler_current_element")
    return traveler_id(el) if el in TRAVELER_ELEMENTS else None


def resolve(s: Session, cid: int) -> int | None:
    return current_element_id(s) if cid == TRAVELER_PENDING else cid


def _set_body(s: Session, body: str) -> None:
    if get_setting(s, "traveler_body") == body:
        return
    set_setting(s, "traveler_body", body)
    icon = body_icon(body)
    for g in s.scalars(select(GameCharacter).where(GameCharacter.id.in_(list(TRAVELER_IDS)))):
        g.icon, g.splash = icon, icon.replace("UI_AvatarIcon_", "UI_Gacha_AvatarImg_", 1)
    meta = s.get(GameMeta, TALENT_META)
    if meta is not None and meta.value:
        meta.value = {k: v for k, v in meta.value.items() if int(k) not in TRAVELER_IDS}
    s.flush()


def record_current(s: Session, element_id: int, raw_id: int, constellation: int) -> None:
    set_setting(s, "traveler_current_element", element_of(element_id))
    body = body_of(raw_id)
    if body is not None:
        _set_body(s, body)
    row = get_or_create(s, element_id)
    row.seen, row.constellation, row.source, row.updated_at = True, constellation, "sync", utcnow()
    s.flush()


def record_current_talents(s: Session, element_id: int, normal: int, skill: int, burst: int) -> None:
    row = get_or_create(s, element_id)
    row.talent_normal, row.talent_skill, row.talent_burst = normal, skill, burst
    row.source, row.updated_at = "sync", utcnow()
    s.flush()


def refresh_owned(s: Session, now: datetime) -> set[int]:
    """Copy the current element's shared fields to every other owned element; drop elements no longer owned."""
    current = current_element_id(s)
    src = s.get(OwnedCharacter, current) if current is not None else None
    if src is None:
        return {i for i in TRAVELER_IDS if s.get(OwnedCharacter, i) is not None}
    owned = set(owned_elements(s)) | {current}
    for cid in TRAVELER_IDS:
        if cid == current:
            continue
        if cid not in owned:
            s.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id == cid))
            s.execute(delete(OwnedCharacter).where(OwnedCharacter.character_id == cid))
            continue
        te = get_or_create(s, cid)
        row = s.get(OwnedCharacter, cid)
        if row is None:
            row = OwnedCharacter(character_id=cid, stats=[])
            s.add(row)
        row.name, row.element, row.icon = traveler_name(element_of(cid)), element_of(cid), src.icon
        row.level, row.friendship = src.level, src.friendship
        row.constellation = te.constellation
        row.talent_normal, row.talent_skill, row.talent_burst = te.talent_normal, te.talent_skill, te.talent_burst
        row.weapon_name, row.weapon_icon, row.weapon_rarity = src.weapon_name, src.weapon_icon, src.weapon_rarity
        row.weapon_level, row.weapon_refinement, row.weapon_id = src.weapon_level, src.weapon_refinement, src.weapon_id
        row.stats, row.synced_at = list(src.stats or []), now
        s.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id == cid))
        for a in s.scalars(select(OwnedArtifact).where(OwnedArtifact.character_id == current)).all():
            s.add(OwnedArtifact(character_id=cid, slot=a.slot, set_name=a.set_name, rarity=a.rarity, level=a.level,
                                main_stat=a.main_stat, substats=list(a.substats), icon=a.icon))
    s.flush()
    return owned
```

In `backend/app/sync/hoyolab.py`:
- `to_roster_entry`: `id=canonical_id(c.id, c.element or None)`.
- `to_detail_entry`: `id=canonical_id(c.id, getattr(c, "element", None) or None)`.
- `GenshinPySource.get_roster`: drop entries whose id is `None` (Manekin): `return [e for e in (to_roster_entry(c) for c in chars) if e.id is not None]`.
- `get_details`: same filter, `if e.id is not None`.
- Change the `RosterEntry.id` and `DetailEntry.id` comments to `# our id (Traveler: element id)`.

In `backend/app/sync/chronicle.py`, pass the element and drop `None`:
- `_banner`: `items = [BannerItem(cid, c.name, c.icon, int(c.rarity), "character") for c in b.characters if (cid := canonical_id(c.id, getattr(c, "element", None) or None)) is not None]`
- In `to_abyss_run`, `to_theater_runs` and `to_stygian_runs`, replace each `[canonical_id(c.id) for c in X]` with `_team(X)`, where:

```python
def _team(chars: Any) -> list[int]:
    return [cid for c in chars if (cid := canonical_id(c.id, getattr(c, "element", None) or None)) is not None]
```

In `backend/app/sync/persist.py`:

```python
from app.gamedata.traveler import TRAVELER_PENDING, is_traveler
from app.traveler.store import record_current, record_current_talents, refresh_owned, resolve
```

Rewrite the loop in `save_roster`:

```python
def save_roster(session: Session, entries: list[RosterEntry], now: datetime) -> set[int]:
    known = set(session.scalars(select(GameCharacter.id)))
    seen: set[int] = set()
    traveler_seen = False
    for e in entries:
        if e.id == TRAVELER_PENDING:
            log.warning("Traveler element %r is not known yet; keeping the previous Traveler rows", e.element)
            seen |= {cid for cid in TRAVELER_IDS if session.get(OwnedCharacter, cid) is not None}
            continue
        seen.add(e.id)
        row = session.get(OwnedCharacter, e.id)
        if row is None:
            row = OwnedCharacter(character_id=e.id, stats=[])
            session.add(row)
        row.name = traveler_name(e.element) if is_traveler(e.id) else e.name
        # … keep the remaining existing assignments unchanged …
        if is_traveler(e.id):
            traveler_seen = True
            session.flush()
            record_current(session, e.id, e.raw_id, e.constellation)
    session.flush()
    if traveler_seen:
        seen |= refresh_owned(session, now)
    session.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id.not_in(seen)))
    session.execute(delete(OwnedCharacter).where(OwnedCharacter.character_id.not_in(seen)))
    return seen - known
```

Add `import logging`, `log = logging.getLogger(__name__)`, and import `TRAVELER_IDS` and `traveler_name` from `app.gamedata.traveler`. `record_current` calls `_set_body` before the row's icon is read, so the row's `icon = VARIANT_ICONS.get(e.raw_id)` stays as is.

In `save_details`, after the existing per-row update and inside the loop, add:

```python
        if is_traveler(d.id):
            record_current_talents(session, d.id, d.normal, d.skill, d.burst)
```

After the loop, add `if any(is_traveler(d.id) for d in details): refresh_owned(session, utcnow())`, importing `utcnow` from `app.timeutil`.

In `save_challenge_runs`, map the teams before storing:

```python
        teams = [[cid for cid in (resolve(session, c) for c in team) if cid is not None] for team in r.teams]
        row.start, row.end, row.summary, row.teams, row.updated_at = r.start, r.end, r.summary, teams, now
```

In `unknown_character_ids`, skip the pending sentinel: `{i for i in ids if i != TRAVELER_PENDING and …}`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `...python.exe -m pytest -q`
Expected: all pass, apart from tests owned by Task 4 (planner) and Task 5 (GOOD, teams) that still reference 10000005 with `seed_game`. Those tests are `test_requests.py::test_owned_prefarm_and_unsupported`, `test_sync_runner.py::test_traveler_is_skipped_but_others_calculated`, `test_planner.py::test_building_cards_only_short_and_fully_built`, `test_good_store.py` (two tests) and `test_teams_store.py` (validation and traveler variant). Mark exactly these with `@pytest.mark.xfail(reason="rewritten in Task 4/5", strict=False)` and list them in the commit message. Any other failure is a bug in this task.

- [ ] **Step 5: Commit**

```bash
git add backend/app/traveler backend/app/sync backend/tests
git commit -m "feat(traveler): record the current element and fan shared Traveler data out to owned elements"
```

---

### Task 4: Planner (calculator element, shared level and weapon counted once)

**Files:**
- Modify: `backend/app/sync/hoyolab.py` (`GapCharacter`, `build_batch_body`, `HoyolabSource.get_talent_ids`, `GenshinPySource.get_talent_ids`), `backend/app/sync/runner.py:156-166` (`_gaps_part`), `backend/app/planner/requests.py` (whole file), `backend/app/planner/characters.py:6,35`, `backend/tests/fakes.py:66-70`
- Test: `backend/tests/test_traveler_planner.py` (new); rewrite the xfailed tests in `test_requests.py`, `test_sync_runner.py` and `test_planner.py`

**Interfaces:**
- Consumes: `traveler_id`, `is_traveler`, `calc_element`, `BODY_IDS` (Task 1); setting `traveler_body`; `current_element_id` (Task 3).
- Produces:
  - `GapCharacter(character_id, level_current, level_target, talents, weapon, avatar_id: int | None = None, element_attr_id: int | None = None)`.
  - `HoyolabSource.get_talent_ids(avatar_id: int, element_attr_id: int | None = None) -> TalentIds`.
  - `PlanInput` gains `avatar_id: int`, `element_attr_id: int | None` and `weapon_planned: bool`.
  - `build_inputs(s)` still returns `(inputs, skipped)`; `skipped` is now always `[]`.
  - `share_traveler(inputs, current: int | None) -> list[PlanInput]` is new and pure.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_traveler_planner.py`:

```python
from app.domain import Targets
from app.planner.requests import PlanInput, gap_requests, has_work, share_traveler
from app.sync.hoyolab import GapCharacter, TalentIds, build_batch_body

CRYO, ANEMO, GEO = 1000000507, 1000000502, 1000000503


def inp(cid, level=80, talents=(1, 1, 1), t=Targets(90, 8, 8, 8, 90), weapon=(11401, 80), planned=False, el=7):
    return PlanInput(cid, "X", level, talents, t, weapon, avatar_id=10000007, element_attr_id=el,
                     weapon_planned=planned)


def test_carrier_takes_highest_level_and_weapon_others_talents_only():
    a = inp(ANEMO, t=Targets(80, 6, 6, 6, 80), el=2)
    c = inp(CRYO, t=Targets(90, 8, 8, 8, 90), el=7)
    out = {i.character_id: i for i in share_traveler([a, c], current=CRYO)}
    assert out[CRYO].targets.level == 90 and out[CRYO].targets.weapon_level == 90 and out[CRYO].weapon == (11401, 80)
    assert out[ANEMO].targets.level == 80 and out[ANEMO].weapon is None      # 80 = its current level
    assert out[ANEMO].targets.normal == 6


def test_carrier_is_lowest_id_when_current_has_no_goal_and_level_only_element_drops():
    a = inp(ANEMO, t=Targets(90, 1, 1, 1, 80), el=2)            # only level work
    g = inp(GEO, t=Targets(80, 8, 8, 8, 80), el=3)
    out = {i.character_id: i for i in share_traveler([g, a], current=CRYO)}
    assert out[ANEMO].targets.level == 90                        # carrier (lowest id) gets the max level
    assert out[GEO].targets.level == 80 and out[GEO].weapon is None
    reqs = gap_requests([i for i in out.values() if has_work(i)],
                        {ANEMO: TalentIds(731, 732, 739), GEO: TalentIds(731, 932, 939)})
    assert {r.character_id for r in reqs} == {ANEMO, GEO}
    geo = next(r for r in reqs if r.character_id == GEO)
    assert (geo.level_current, geo.level_target, geo.weapon, geo.avatar_id, geo.element_attr_id) == (
        80, 80, None, 10000007, 3)


def test_planned_weapon_of_another_element_moves_to_carrier():
    a = inp(ANEMO, el=2, weapon=(11509, 1), planned=True)
    c = inp(CRYO, el=7, weapon=(11401, 80))
    out = {i.character_id: i for i in share_traveler([a, c], current=CRYO)}
    assert out[CRYO].weapon == (11509, 1) and out[ANEMO].weapon is None


def test_non_travelers_untouched():
    b = PlanInput(10000032, "Bennett", 80, (6, 8, 8), Targets(90, 8, 8, 8, 90), (11401, 90), avatar_id=10000032,
                  element_attr_id=None, weapon_planned=False)
    assert share_traveler([b], current=None) == [b]


def test_batch_body_sends_body_id_and_element():
    body = build_batch_body([GapCharacter(CRYO, 80, 90, ((832, 1, 8),), None, avatar_id=10000007, element_attr_id=7),
                             GapCharacter(10000032, 80, 90, (), None)], 800000001, "os_usa")
    assert body["items"][0]["avatar_id"] == 10000007 and body["items"][0]["element_attr_id"] == 7
    assert body["items"][1]["avatar_id"] == 10000032 and "element_attr_id" not in body["items"][1]
```

Rewrite the xfailed tests:
- In `test_requests.py`, the setup roster's Traveler becomes `make_roster(1000000507, raw_id=10000007, name="Traveler", element="Cryo")`. Rename `test_owned_prefarm_and_unsupported` to `test_owned_prefarm_and_traveler`, set the goals to `[goal(10000032), goal(10000073), goal(1000000507)]`, and assert `skipped == []` and that `by_id[1000000507].element_attr_id == 7 and by_id[1000000507].avatar_id == 10000007`. Keep the file's other assertions about 10000032 and 10000073.
- In `test_sync_runner.py`, rename the test to `test_traveler_is_calculated_with_element`. Use `build_goal(session_factory, 1000000507)` and roster `make_roster(1000000507, raw_id=10000007, name="Traveler", element="Cryo")`. Assert `last_run(...).parts["gaps"] == {"ok": True, "count": 2}`, `("talents", 10000007, 7) in source.calls`, and `("gaps", (10000032, 1000000507)) in source.calls`.
- In `test_planner.py::test_building_cards_only_short_and_fully_built`, delete the last two lines (the 10000005 card) and remove the xfail.
- `backend/tests/fakes.py` `get_talent_ids`:

```python
    async def get_talent_ids(self, avatar_id, element_attr_id=None):
        self.calls.append(("talents", avatar_id, element_attr_id) if element_attr_id else ("talents", avatar_id))
        if "talents" in self.fail:
            raise self.fail["talents"]
        return TalentIds(avatar_id * 10 + 1, avatar_id * 10 + 2, avatar_id * 10 + 9)
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `...python.exe -m pytest -q tests/test_traveler_planner.py tests/test_requests.py tests/test_sync_runner.py`
Expected: FAIL. `ImportError: cannot import name 'share_traveler'`, or unexpected keyword `avatar_id`.

- [ ] **Step 3: Implement**

`backend/app/sync/hoyolab.py`:

```python
@dataclass(frozen=True)
class GapCharacter:
    character_id: int
    level_current: int
    level_target: int
    talents: tuple[tuple[int, int, int], ...]
    weapon: tuple[int, int, int] | None
    avatar_id: int | None = None          # HoYoLAB id when it differs from ours (Traveler body id)
    element_attr_id: int | None = None    # Traveler only: calculator element number
```

In `build_batch_body`, replace `"avatar_id": c.character_id,` with `"avatar_id": c.avatar_id or c.character_id,`. After building `item`, add `if c.element_attr_id is not None: item["element_attr_id"] = c.element_attr_id`.

Protocol: `async def get_talent_ids(self, avatar_id: int, element_attr_id: int | None = None) -> TalentIds: ...`

`GenshinPySource.get_talent_ids`:

```python
    async def get_talent_ids(self, avatar_id: int, element_attr_id: int | None = None) -> TalentIds:
        params: dict[str, int] = {"avatar_id": avatar_id}
        if element_attr_id is not None:
            params["element_attr_id"] = element_attr_id
        data = await call_api(self._client.request_calculator, "avatarSkill/list", method="GET",
                              params=params, delays=self._delays)
        return to_talent_ids(data.get("list") or [])
```

Note: `to_talent_ids` already drops `max_level == 1` passives. The Traveler list (probed: 831/832/839 plus passives) yields normal, skill and burst correctly.

`backend/app/sync/runner.py` `_gaps_part`: replace the `missing` loop with:

```python
            missing = [i for i in work if i.character_id not in cache]
            for i in missing:
                cache[i.character_id] = await source.get_talent_ids(i.avatar_id, i.element_attr_id)
```

`backend/app/planner/requests.py`, full new version:

```python
"""Turn Build goals plus synced account data into calculator requests."""
from __future__ import annotations

from dataclasses import dataclass, replace

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CharacterGoal, GameCharacter, OwnedCharacter
from app.domain import Targets
from app.gamedata.traveler import BODY_IDS, TRAVELER_IDS, calc_element, is_traveler
from app.settings.store import get_setting
from app.sync.hoyolab import GapCharacter, TalentIds
from app.traveler.store import current_element_id


@dataclass(frozen=True)
class PlanInput:
    character_id: int
    name: str
    level: int
    talents: tuple[int, int, int]
    targets: Targets
    weapon: tuple[int, int] | None
    avatar_id: int = 0
    element_attr_id: int | None = None
    weapon_planned: bool = False

    def __post_init__(self):
        if not self.avatar_id:
            object.__setattr__(self, "avatar_id", self.character_id)


def _build_rows(session: Session) -> list[CharacterGoal]:
    rows = session.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")
                           .order_by(CharacterGoal.character_id))
    return [r for r in rows if r.target_level is not None]


def _shared_traveler_row(session: Session) -> OwnedCharacter | None:
    """Level and weapon are shared: an element without its own owned row borrows them from one that has."""
    cur = current_element_id(session)
    for cid in ([cur] if cur else []) + sorted(TRAVELER_IDS):
        o = session.get(OwnedCharacter, cid)
        if o is not None:
            return o
    return None


def build_inputs(session: Session) -> tuple[list[PlanInput], list[str]]:
    inputs: list[PlanInput] = []
    body_id = BODY_IDS.get(str(get_setting(session, "traveler_body")), BODY_IDS["girl"])
    for row in _build_rows(session):
        cid = row.character_id
        g = session.get(GameCharacter, cid)
        o = session.get(OwnedCharacter, cid)
        if g is None and o is None:
            continue
        traveler = is_traveler(cid)
        shared = (o or _shared_traveler_row(session)) if traveler else o
        targets = Targets(row.target_level, row.target_normal, row.target_skill, row.target_burst,
                          row.target_weapon_level)
        level = shared.level if shared is not None else 1
        talents = ((o.talent_normal or 1, o.talent_skill or 1, o.talent_burst or 1) if o is not None else (1, 1, 1))
        weapon: tuple[int, int] | None = None
        equipped = shared.weapon_id if shared is not None else None
        planned = row.planned_weapon_id is not None and row.planned_weapon_id != equipped
        if planned:
            weapon = (row.planned_weapon_id, 1)
        elif equipped:
            weapon = (equipped, shared.weapon_level)
        inputs.append(PlanInput(cid, g.name if g is not None else o.name, level, talents, targets, weapon,
                                avatar_id=body_id if traveler else cid,
                                element_attr_id=calc_element(cid) if traveler else None,
                                weapon_planned=planned))
    return share_traveler(inputs, current_element_id(session)), []


def share_traveler(inputs: list[PlanInput], current: int | None) -> list[PlanInput]:
    """Level and weapon are shared by all Traveler elements: send them once, with one carrier element."""
    group = [i for i in inputs if is_traveler(i.character_id) and has_work(i)]
    if not group:
        return inputs
    ids = {i.character_id for i in group}
    carrier_id = current if current in ids else min(ids)
    level = max(i.targets.level for i in group)
    weapon_level = max(i.targets.weapon_level for i in group)
    ordered = sorted(group, key=lambda i: (i.character_id != carrier_id, i.character_id))
    weapon = next((i.weapon for i in ordered if i.weapon_planned), None) or next(
        (i.weapon for i in ordered if i.weapon is not None), None)
    out: list[PlanInput] = []
    for i in inputs:
        if i.character_id not in ids:
            out.append(i)
        elif i.character_id == carrier_id:
            out.append(replace(i, targets=replace(i.targets, level=level, weapon_level=weapon_level), weapon=weapon))
        else:
            out.append(replace(i, targets=replace(i.targets, level=i.level), weapon=None))
    return out


def has_work(i: PlanInput) -> bool:
    t = i.targets
    talents_up = any(tgt > cur for cur, tgt in zip(i.talents, (t.normal, t.skill, t.burst)))
    weapon_up = i.weapon is not None and t.weapon_level > i.weapon[1]
    return t.level > i.level or talents_up or weapon_up


def snapshot(session: Session) -> list[list]:
    return [[r.character_id, r.target_level, r.target_normal, r.target_skill, r.target_burst,
             r.target_weapon_level, r.planned_weapon_id] for r in _build_rows(session)]


def gap_requests(inputs: list[PlanInput], talent_ids: dict[int, TalentIds]) -> list[GapCharacter]:
    out: list[GapCharacter] = []
    for i in inputs:
        if not has_work(i):
            continue
        t = i.targets
        talents: tuple[tuple[int, int, int], ...] = ()
        if any(tgt > cur for cur, tgt in zip(i.talents, (t.normal, t.skill, t.burst))):
            ids = talent_ids[i.character_id]
            talents = tuple((gid, cur, tgt) for gid, cur, tgt in
                            zip((ids.normal, ids.skill, ids.burst), i.talents, (t.normal, t.skill, t.burst))
                            if tgt > cur)
        weapon = None
        if i.weapon is not None and t.weapon_level > i.weapon[1]:
            weapon = (i.weapon[0], i.weapon[1], t.weapon_level)
        out.append(GapCharacter(i.character_id, i.level, max(i.level, t.level), talents, weapon,
                                avatar_id=i.avatar_id if i.avatar_id != i.character_id else None,
                                element_attr_id=i.element_attr_id))
    return out
```

`Targets` must be a dataclass for `replace` to work. Check `backend/app/domain.py:9`: if it isn't decorated with `@dataclass(frozen=True)`, use `Targets(level, t.normal, t.skill, t.burst, weapon_level)` instead.

`backend/app/planner/characters.py`: remove the `UNSUPPORTED` import, and set `"skipped": False` in `building_cards`. The frontend still reads the field.

`backend/app/gamedata/yatta.py`: delete the legacy line `TRAVELER_ID = 10000005`. `MANEKIN_ID` stays for Task 5. `grep -rn TRAVELER_ID backend/app` must show only `keys.py`, which Task 5 fixes. To keep the suite green now, change `keys.py`'s import to `from app.gamedata.yatta import MANEKIN_ID` plus `TRAVELER_ID = 10000005` locally inside that function, marked `# Task 5`.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `...python.exe -m pytest -q`
Expected: all pass except the Task 5 xfails (`test_good_store.py`, `test_teams_store.py`).

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(traveler): plan Traveler elements via element_attr_id; shared level and weapon counted once"
```

---

### Task 5: GOOD keys and team saves

**Files:**
- Modify: `backend/app/good/keys.py:40-70`, `backend/app/teams/store.py:118`, `backend/app/gamedata/yatta.py` (delete `MANEKIN_ID`)
- Test: `backend/tests/test_good_store.py:60-82`, `backend/tests/test_teams_store.py:78-98`, `backend/tests/test_good_keys.py` (add a test)

**Interfaces:**
- Consumes: `traveler_id`, `TRAVELER_ELEMENTS`, `MANEKIN_RAW_IDS` (Task 1); setting `traveler_current_element`.
- Produces: `KeyIndex` gains the field `traveler_current: int | None`. `KeyIndex.character(key)` maps `TravelerAnemo` and the like to element ids, a bare `Traveler` to `traveler_current`, and `Manekin`/`Manekina` to `None`.

- [ ] **Step 1: Write the failing tests**

In `test_good_store.py`, remove the xfail marks:
- In `test_holders_traveler_and_unknown`, change `assert traveler["character_id"] == 10000005` to `== 1000000502` (Anemo).
- In `test_index_maps_manekina_and_collisions_keep_first`, change the Manekin line to `assert idx.character("Manekina") is None and idx.character("Manekin") is None`.

Add to `test_good_keys.py` (it uses the repo's `session_factory` fixture; follow that file's imports):

```python
def test_traveler_keys_per_element_and_bare_traveler_uses_current(session_factory):
    from app.good.keys import KeyIndex
    from app.settings.store import set_setting
    with session_factory.begin() as s:
        set_setting(s, "traveler_current_element", "Cryo")
    with session_factory() as s:
        idx = KeyIndex.build(s)
    assert idx.character("TravelerGeo") == 1000000503
    assert idx.character("TravelerCryo") == 1000000507
    assert idx.character("Traveler") == 1000000507
    assert idx.character("TravelerLunar") is None
```

In `test_teams_store.py`, remove the xfails:
- In `test_validation`, replace `10000005` in the five-member case with `1000000507`.
- Replace `test_traveler_variant_is_stored_canonically` with:

```python
def test_traveler_element_ids_saved_and_raw_or_manekin_ids_rejected(sf):
    tid, _ = save(sf, members=(1000000507,))
    assert members_of(sf, tid) == [(0, 1000000507, "")]
    for bad in (10000007, 10000005, 10000117):
        with pytest.raises(TeamError) as e:
            save(sf, members=(bad,))
        assert e.value.status == 422 and "Unknown character" in e.value.message
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `...python.exe -m pytest -q tests/test_good_store.py tests/test_good_keys.py tests/test_teams_store.py`
Expected: FAIL (old mapping).

- [ ] **Step 3: Implement**

`backend/app/good/keys.py`: add the field `traveler_current: int | None = None` to the `KeyIndex` dataclass (last, with its default). In `build`, pass:

```python
            traveler_current=current_element_id(session),
```

with `from app.traveler.store import current_element_id` inside `build`. Then replace `character`:

```python
    def character(self, key: str) -> int | None:
        from app.gamedata.traveler import TRAVELER_ELEMENTS, traveler_id
        if not key or key in ("Manekin", "Manekina"):
            return None
        if key == "Traveler":
            return self.traveler_current
        if key.startswith("Traveler"):
            element = key[len("Traveler"):]
            return traveler_id(element) if element in TRAVELER_ELEMENTS else None
        return self.characters.get(key)
```

Remove the local `TRAVELER_ID` and `MANEKIN_ID` lines from Task 4. Delete `MANEKIN_ID` from `yatta.py`. `grep -rn "MANEKIN_ID\|TRAVELER_ID" backend` must return nothing.

`backend/app/teams/store.py:118`: replace `ids = [canonical_id(m.character_id) for m in members]` with `ids = [m.character_id for m in members]`, and remove the now-unused `canonical_id` import. The client always sends our ids; `_known_character` rejects raw body ids and Manekin ids, because neither exists in `game_character` or `owned_character` after Task 2.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `...python.exe -m pytest -q`
Expected: all pass, with no xfail marks left (`grep -rn "Task 4/5" backend/tests` is empty).

- [ ] **Step 5: Commit**

```bash
git add backend/app backend/tests
git commit -m "feat(traveler): GOOD Traveler keys per element, Manekin unmatched, teams store our ids as given"
```

---

### Task 6: Traveler API (detail payload and PUT endpoint)

**Files:**
- Create: `backend/app/api/traveler.py`
- Modify: `backend/app/api/characters.py` (`get_character`), `backend/app/main.py` (include the router the same way the other routers are included, under `/api`)
- Test: `backend/tests/test_api_traveler.py` (new)

**Interfaces:**
- Consumes: `app.traveler.store` (`get_or_create`, `current_element_id`, `refresh_owned`, `owned_elements`); `is_traveler`.
- Produces:
  - The `GET /api/characters/{slug}` payload gains `"traveler": {"element_id", "current", "seen", "unlocked", "talents": {"normal", "skill", "burst"}, "constellation", "source"}` for Traveler element ids, and `"traveler": null` otherwise.
  - `PUT /api/traveler/{element_id}` takes the body `{unlocked?: bool, talents?: {normal, skill, burst}, constellation?: int}` and returns the same `traveler` object.
  - Errors: 404 for a non-Traveler id. 409 "Set by HoYoLAB: this is your current element" when talents or constellation are sent for the current element. 409 "Seen in sync: always unlocked" for `unlocked: false` on a seen element. 422 for out-of-range values (talents 1–10, constellation 0–6), via pydantic.

- [ ] **Step 1: Write the failing tests**

Create `backend/tests/test_api_traveler.py`. Copy the client setup used in `test_api_characters.py`: `make_client(paths)` plus `seed_game` against the client's own session factory. Open `test_api_characters.py` and use its `sf_for(paths)` helper.

```python
from app.db.models import OwnedCharacter, TravelerElement
from app.sync.persist import save_details, save_roster
from app.timeutil import utcnow
from fakes import make_detail, make_roster
from helpers import make_client, seed_game
from test_api_characters import sf_for

CRYO, ANEMO = 1000000507, 1000000502


def synced(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with sf.begin() as s:
        save_roster(s, [make_roster(CRYO, raw_id=10000007, name="Traveler", element="Cryo")], utcnow())
        save_details(s, [make_detail(CRYO, talents=(4, 9, 10))])
    return sf


def test_detail_has_traveler_block(paths):
    synced(paths)
    with make_client(paths) as c:
        t = c.get("/api/characters/cryo-traveler").json()["traveler"]
        assert t == {"element_id": CRYO, "current": True, "seen": True, "unlocked": False,
                     "talents": {"normal": 4, "skill": 9, "burst": 10}, "constellation": 2, "source": "sync"}
        assert c.get("/api/characters/bennett").json()["traveler"] is None
        anemo = c.get("/api/characters/anemo-traveler").json()
        assert anemo["owned"] is False and anemo["traveler"]["unlocked"] is False


def test_unlock_and_edit_other_element(paths):
    sf = synced(paths)
    with make_client(paths) as c:
        r = c.put(f"/api/traveler/{ANEMO}", json={"unlocked": True, "talents": {"normal": 2, "skill": 6, "burst": 6},
                                                  "constellation": 1})
        assert r.status_code == 200 and r.json()["source"] == "manual"
        a = c.get("/api/characters/anemo-traveler").json()
        assert a["owned"] is True and a["talents"] == {"normal": 2, "skill": 6, "burst": 6} and a["constellation"] == 1
        assert a["level"] == 80
    with sf() as s:
        assert s.get(OwnedCharacter, ANEMO) is not None


def test_errors(paths):
    synced(paths)
    with make_client(paths) as c:
        assert c.put("/api/traveler/10000032", json={"unlocked": True}).status_code == 404
        assert c.put(f"/api/traveler/{CRYO}", json={"constellation": 3}).status_code == 409
        assert c.put(f"/api/traveler/{CRYO}", json={"unlocked": False}).status_code == 409
        assert c.put(f"/api/traveler/{ANEMO}", json={"constellation": 7}).status_code == 422
        assert c.put(f"/api/traveler/{ANEMO}", json={"talents": {"normal": 0, "skill": 1, "burst": 1}}).status_code == 422


def test_unlock_before_any_sync_saves_flag_only(paths):
    sf = sf_for(paths)
    seed_game(sf)
    with make_client(paths) as c:
        r = c.put(f"/api/traveler/{ANEMO}", json={"unlocked": True})
        assert r.status_code == 200 and r.json()["unlocked"] is True and r.json()["current"] is False
        assert c.get("/api/characters/anemo-traveler").json()["owned"] is False   # needs a sync for level/weapon
    with sf() as s:
        assert s.get(TravelerElement, ANEMO).unlocked is True
```

If `make_client` is a plain object rather than a context manager in this repo, follow `test_api_characters.py`'s usage instead of `with`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `...python.exe -m pytest -q tests/test_api_traveler.py`
Expected: FAIL (`KeyError: 'traveler'`, 404 on PUT).

- [ ] **Step 3: Implement**

Create `backend/app/api/traveler.py`:

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.context import AppContext, get_ctx
from app.db.models import TravelerElement
from app.gamedata.traveler import is_traveler
from app.timeutil import utcnow
from app.traveler.store import current_element_id, get_or_create, refresh_owned

router = APIRouter()


class TalentsIn(BaseModel):
    normal: int = Field(ge=1, le=10)
    skill: int = Field(ge=1, le=10)
    burst: int = Field(ge=1, le=10)


class TravelerIn(BaseModel):
    unlocked: bool | None = None
    talents: TalentsIn | None = None
    constellation: int | None = Field(default=None, ge=0, le=6)


def traveler_payload(row: TravelerElement | None, element_id: int, current: int | None) -> dict:
    return {
        "element_id": element_id,
        "current": element_id == current,
        "seen": bool(row and row.seen),
        "unlocked": bool(row and row.unlocked),
        "talents": {"normal": row.talent_normal if row else 1, "skill": row.talent_skill if row else 1,
                    "burst": row.talent_burst if row else 1},
        "constellation": row.constellation if row else 0,
        "source": row.source if row else "manual",
    }


@router.put("/traveler/{element_id}")
async def set_traveler(element_id: int, body: TravelerIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    if not is_traveler(element_id):
        raise HTTPException(404, "Not a Traveler element")
    with ctx.session_factory.begin() as s:
        current = current_element_id(s)
        row = get_or_create(s, element_id)
        if (body.talents is not None or body.constellation is not None) and element_id == current:
            raise HTTPException(409, "Set by HoYoLAB: this is your current element")
        if body.unlocked is False and row.seen:
            raise HTTPException(409, "Seen in sync: always unlocked")
        if body.unlocked is not None:
            row.unlocked = body.unlocked
        if body.talents is not None:
            row.talent_normal, row.talent_skill, row.talent_burst = (
                body.talents.normal, body.talents.skill, body.talents.burst)
            row.source = "manual"
        if body.constellation is not None:
            row.constellation, row.source = body.constellation, "manual"
        row.updated_at = utcnow()
        s.flush()
        refresh_owned(s, utcnow())
        payload = traveler_payload(row, element_id, current)
    ctx.sync.schedule_gaps()
    return payload
```

Because `HTTPException` is raised inside `session_factory.begin()`, the transaction rolls back. That also rolls back the `get_or_create` insert.

`backend/app/api/characters.py` `get_character`: after `payload["teams"] = …`, add:

```python
            if is_traveler(payload["id"]):
                payload["traveler"] = traveler_payload(s.get(TravelerElement, payload["id"]), payload["id"],
                                                       current_element_id(s))
            else:
                payload["traveler"] = None
```

Add the imports: `from app.api.traveler import traveler_payload`, `from app.db.models import TravelerElement`, `from app.gamedata.traveler import is_traveler`, `from app.traveler.store import current_element_id`.

`backend/app/main.py`: register `traveler.router` next to `characters.router`, with the same prefix argument.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `...python.exe -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/api backend/app/main.py backend/tests/test_api_traveler.py
git commit -m "feat(traveler): traveler block on the character detail and PUT /api/traveler/{element_id}"
```

---

### Task 7: Frontend card, dev seed and e2e

**Files:**
- Create: `frontend/src/lib/traveler.ts`, `frontend/src/lib/traveler.test.ts`, `frontend/src/lib/TravelerElementCard.svelte`
- Modify: `frontend/src/lib/types.ts` (`CharacterDetail`), `frontend/src/lib/api.ts`, `frontend/src/routes/characters/[slug]/+page.svelte`, `frontend/src/lib/syncLabel.test.ts:9-10`, `backend/app/devseed.py`, `frontend/e2e/characters.spec.ts`
- Test: `frontend/src/lib/traveler.test.ts`; `frontend/e2e/characters.spec.ts`; `backend/tests/test_devseed.py` (if it counts characters, update its counts)

**Interfaces:**
- Consumes: the Task 6 API shape.
- Produces:
  - TS `TravelerInfo { element_id: number; current: boolean; seen: boolean; unlocked: boolean; talents: Talents; constellation: number; source: 'sync' | 'manual' }`.
  - `CharacterDetail.traveler: TravelerInfo | null`.
  - `api.setTraveler(id, body)`.
  - `traveler.ts`: `clampTalent(n: number): number` (1–10, NaN → 1), `clampCons(n: number): number` (0–6, NaN → 0), `editable(t: TravelerInfo): boolean` (= `!t.current`), `unlockLocked(t: TravelerInfo): boolean` (= `t.seen`).

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/traveler.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { clampCons, clampTalent, editable, unlockLocked } from './traveler';
import type { TravelerInfo } from './types';

const t = (p: Partial<TravelerInfo>): TravelerInfo => ({
	element_id: 1000000502, current: false, seen: false, unlocked: false,
	talents: { normal: 1, skill: 1, burst: 1 }, constellation: 0, source: 'manual', ...p
});

describe('traveler helpers', () => {
	it('clamps talents and constellation', () => {
		expect([clampTalent(0), clampTalent(11), clampTalent(NaN), clampTalent(7.6)]).toEqual([1, 10, 1, 7]);
		expect([clampCons(-1), clampCons(9), clampCons(NaN), clampCons(3)]).toEqual([0, 6, 0, 3]);
	});
	it('locks the current element and seen unlocks', () => {
		expect(editable(t({ current: true }))).toBe(false);
		expect(editable(t({}))).toBe(true);
		expect(unlockLocked(t({ seen: true }))).toBe(true);
		expect(unlockLocked(t({}))).toBe(false);
	});
});
```

In `frontend/src/lib/syncLabel.test.ts:9-10`, replace `'Traveler'` with `'Aloy'` and the second list with `['Aloy', 'Nefer']`, updating the expected strings to match (`'not planned: Aloy'`, `'not planned: Aloy, Nefer'`).

Add to `frontend/e2e/characters.spec.ts` (follow the file's existing imports and `page.goto` style):

```ts
test('Traveler element card: unlock another element', async ({ page }) => {
	await page.goto('/characters/cryo-traveler');
	await expect(page.getByRole('heading', { name: 'Cryo Traveler' })).toBeVisible();
	await expect(page.getByText('From HoYoLAB: current element')).toBeVisible();
	await page.goto('/characters/anemo-traveler');
	const toggle = page.getByRole('checkbox', { name: 'Unlocked' });
	await expect(toggle).not.toBeChecked();
	await toggle.check();
	await expect(page.getByRole('heading', { name: 'Current' })).toBeVisible();
	await expect(page.getByText('Lv 90')).toBeVisible();
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (in `frontend/`): `npx vitest run src/lib/traveler.test.ts`
Expected: FAIL (cannot resolve `./traveler`).

- [ ] **Step 3: Implement**

`frontend/src/lib/types.ts`: add `TravelerInfo` (above), and `traveler: TravelerInfo | null;` to `CharacterDetail`.

`frontend/src/lib/api.ts`: add to `api` (import `Talents` and `TravelerInfo` in the type import):

```ts
	setTraveler: (id: number, body: { unlocked?: boolean; talents?: Talents; constellation?: number }) =>
		request<TravelerInfo>('PUT', `/traveler/${id}`, body),
```

`frontend/src/lib/traveler.ts`:

```ts
import type { TravelerInfo } from './types';

export function clampTalent(n: number): number {
	return Number.isFinite(n) ? Math.min(10, Math.max(1, Math.floor(n))) : 1;
}
export function clampCons(n: number): number {
	return Number.isFinite(n) ? Math.min(6, Math.max(0, Math.floor(n))) : 0;
}
export const editable = (t: TravelerInfo) => !t.current;
export const unlockLocked = (t: TravelerInfo) => t.seen;
```

`frontend/src/lib/TravelerElementCard.svelte`:

```svelte
<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import { clampCons, clampTalent, editable, unlockLocked } from '$lib/traveler';
	import type { TravelerInfo } from '$lib/types';

	let { info, onsaved }: { info: TravelerInfo; onsaved: () => void } = $props();
	let error = $state<string | null>(null);

	async function save(body: Parameters<typeof api.setTraveler>[1]) {
		try {
			await api.setTraveler(info.element_id, body);
			error = null;
			onsaved();
		} catch (e) {
			error = errorMessage(e);
		}
	}

	function talent(key: 'normal' | 'skill' | 'burst', value: string) {
		save({ talents: { ...info.talents, [key]: clampTalent(Number(value)) } });
	}
</script>

<section class="panel" data-testid="traveler-element">
	<h2>Traveler element</h2>
	<label class="row">
		<input type="checkbox" checked={info.seen || info.unlocked} disabled={unlockLocked(info)}
			onchange={(e) => save({ unlocked: e.currentTarget.checked })} />
		<span>Unlocked</span>
	</label>
	{#if info.current}<p class="muted">From HoYoLAB: current element</p>{/if}
	<div class="fields">
		{#each [['normal', 'Normal attack'], ['skill', 'Skill'], ['burst', 'Burst']] as [key, label] (key)}
			<label>
				<span>{label}</span>
				<input type="number" min="1" max="10" value={info.talents[key as 'normal' | 'skill' | 'burst']}
					disabled={!editable(info)} aria-label={label}
					onchange={(e) => talent(key as 'normal' | 'skill' | 'burst', e.currentTarget.value)} />
			</label>
		{/each}
		<label>
			<span>Constellation</span>
			<input type="number" min="0" max="6" value={info.constellation} disabled={!editable(info)}
				aria-label="Constellation"
				onchange={(e) => save({ constellation: clampCons(Number(e.currentTarget.value)) })} />
		</label>
	</div>
	{#if error}<p class="error">{error}</p>{/if}
</section>

<style>
	.row { display: inline-flex; gap: 8px; align-items: center; }
	.fields { display: flex; flex-wrap: wrap; gap: 12px; margin-top: 10px; }
	.fields label { display: inline-flex; flex-direction: column; gap: 4px; }
	.fields input { width: 5rem; }
</style>
```

`frontend/src/routes/characters/[slug]/+page.svelte`: import `TravelerElementCard`, and insert it directly after the `</header>`:

```svelte
	{#if c.traveler}
		<TravelerElementCard info={c.traveler} onsaved={() => load(page.params.slug ?? '')} />
	{/if}
```

`backend/app/devseed.py`:
- Add two rows to `CHARACTERS`: `(1000000507, "Cryo Traveler", "cryo-traveler", 5, "Cryo", "Sword", "UI_AvatarIcon_PlayerGirl")` and `(1000000502, "Anemo Traveler", "anemo-traveler", 5, "Anemo", "Sword", "UI_AvatarIcon_PlayerGirl")`.
- Add `1000000507: (90, (4, 9, 10))` to `OWNED`.
- The `save_roster` call builds `RosterEntry(cid, cid, names[cid], None, …)`. For the Traveler it must pass `raw_id=10000007` and `element="Cryo"`. Change the comprehension to:

```python
        save_roster(s, [RosterEntry(cid, 10000007 if cid == 1000000507 else cid, names[cid],
                                    "Cryo" if cid == 1000000507 else None, lvl, 1, 10, WEAPON)
                        for cid, (lvl, _t) in OWNED.items()], now)
```

`save_details` already runs over `OWNED` and records the Cryo talents. If `backend/tests/test_devseed.py` asserts character or owned counts, raise them by 2 and 1.

- [ ] **Step 4: Run the tests to verify they pass**

Run in `frontend/`: `npm run check`, `npx vitest run`, `npm run build`, then `PYTHON=C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe npx playwright test`. Run in `backend/`: `...python.exe -m pytest -q`.
Expected: all green; svelte-check reports 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend backend/app/devseed.py backend/tests
git commit -m "feat(traveler): Traveler element card (unlock, talents, constellation) with dev seed and e2e"
```

---

### Task 8: Final verification and live smoke

**Files:** none new. This task only fixes what the checks find.

- [ ] **Step 1: Full suites**

Run all five commands from Global Constraints. Expected: all green. Record the counts in the commit or ledger.

- [ ] **Step 2: Grep for leftovers**

Run: `git grep -n "TRAVELER_ID\|MANEKIN_ID\|UNSUPPORTED\|10000117\|\"traveler\"" -- backend/app frontend/src`
Expected: no hits in app code (tests and the migration may still mention 10000117).

- [ ] **Step 3: Live smoke against the user's own data (read-only for HoYoLAB)**

From `backend/`, with the user's real `data/` folder, the app performs migration 0007 on start. The startup backup already exists in `data/backups/`. Run `python run.py`, open the app, trigger a manual sync, then check:
- The Characters list shows "Cryo Traveler" (the current element) as owned.
- Setting a Build goal on Cryo Traveler produces Charity books in its material shortfall after the gaps recalculation.
- The sync status no longer shows "not planned: Traveler".

Report what you saw. Never paste the UID or cookies.

- [ ] **Step 4: Commit any fixes**

```bash
git add -A backend frontend
git commit -m "fix(traveler): final verification fixes"
```

(Skip this if there is nothing to commit.)
