# Phase 6 — GOOD Inventory Import Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Users who opt in can upload a GOOD scanner export. The Inventory page then shows exact owned material counts and a full owned list, and gains Weapons and Artifacts tabs. Live HoYoLAB data stays the source of every to-farm number.

**Architecture:** A new pure package `backend/app/good/` (parse → match against the catalogue → store) has no network access. A new API router `app/api/good.py` and small additions to `/api/inventory`, `/api/weapons` and `/api/settings` expose it, all gated by the setting `good_import_enabled`. Game data gains artifact sets from Yatta `/reliquary` and a list of every Yatta material key, so food and quest items are "ignored" rather than "unmatched". The frontend applies the tile rules in the existing `tileView`, adds a Settings section, an import button, and Weapons/Artifacts tabs.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, SQLite, pytest (+ httpx MockTransport); SvelteKit (Svelte 5 runes, TypeScript), Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-22-phase6-good-import-design.md` (read it before starting any task; §-references below point into it).

## Global Constraints

- Python for every backend command: `C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe` (called `PY` below). Run backend tests from `backend/`: `PY -m pytest -q`.
- Frontend commands run from `frontend/`: `npm run check`, `npx vitest run`, `npm run build`, `PYTHON=<PY> npx playwright test`.
- `good_import_enabled` defaults to **false**. While it is false, every GOOD field in every response is null or absent, import returns 409, and stored data is kept.
- The uploaded file is parsed in memory, **never written to disk, and its contents never logged**. Log lines may name keys (collisions) but never counts.
- Upload limit: **20 MB** (413 above it). Versions accepted: **1–3**.
- Each import **replaces** all `good_*` rows in one transaction; a failed parse changes nothing.
- To-farm, crafting, Farm today, Weekly bosses and Building cards **never** read GOOD data.
- Unofficial HoYoLAB code stays in `backend/app/sync/`; `app/good/` must not import from `app/sync/`.
- Test fixtures: invented counts only; any UID used is 800000001. No real GOOD export, cookie, UID, nickname or game art is committed.
- Settings risk note text (verbatim): "The import only reads a file. The scanner that creates it is third-party software, which HoYoverse's terms forbid; use at your own risk."
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A real scanner file full of food, potions and quest items.** These must be counted as *ignored*, not *unmatched*, or the summary is useless and keeps suggesting "Refresh game data". Pinned in Task 3 (`test_food_is_ignored_not_unmatched`).
2. **Re-importing a smaller file.** Weapons and artifacts from the earlier file must be gone entirely (replace, not merge). Pinned in Task 3 (`test_reimport_replaces_everything`).
3. **Turning the toggle off with data stored.** Inventory `scan` must be null, `/api/weapons` `owned` null, `/api/good/weapons` 404. Turning it back on restores everything without a re-import. Pinned in Task 4 (`test_toggle_off_hides_and_on_restores`).
4. **A material that is live-short while the scan disagrees.** The tile must keep the live `have/need`, and `to_farm` must be identical with and without an import. Pinned in Task 4 (`test_inventory_to_farm_unchanged_by_import`) and Task 6 (`tileView` short case).
5. **A weapon or artifact held by a character we can't match** (a brand-new character, or Traveler variants). It must not show as "Unequipped". Traveler keys map to the Traveler; unknown holders show "Equipped" and are listed as `character:<Key>`. Pinned in Task 3 (`test_holders_traveler_and_unknown`) and Task 6 (`holderLabel`).

---

## File Structure

**Backend — create**
- `backend/app/good/__init__.py`: empty.
- `backend/app/good/keys.py`: `good_key(name)`, `KeyIndex`.
- `backend/app/good/parse.py`: `parse_good(bytes) -> GoodFile`, `GoodFormatError`.
- `backend/app/good/store.py`: `match_file`, `replace_snapshot`, `delete_snapshot`, `good_active`, `scan_counts`, `owned_weapons`, `ImportSummary`.
- `backend/app/good/check.py`: CLI that prints only the match summary for a real file (live check).
- `backend/app/gamedata/artifacts.py`: Yatta `/reliquary` parsing.
- `backend/app/api/good.py`: the `/api/good/*` router.
- `backend/migrations/versions/0006_good_import.py`
- `backend/tests/fixtures/good_sample.json`, `backend/tests/fixtures/yatta_reliquary.json`
- `backend/tests/test_good_keys.py`, `test_good_parse.py`, `test_good_store.py`, `test_api_good.py`

**Backend — modify**
- `backend/app/db/models.py`: 5 new tables.
- `backend/app/gamedata/materials.py`: `fetch_material_catalogue`.
- `backend/app/gamedata/service.py`: artifact-set refresh, `material_keys_all` meta, status.
- `backend/app/settings/store.py`: default `good_import_enabled`.
- `backend/app/api/settings.py`: field in `SettingsIn` and payload.
- `backend/app/api/planner.py`: `scan` and `good` in `/inventory`; `owned` in `/weapons`.
- `backend/app/api/__init__.py`: register the router.
- `backend/app/config.py`: `GOOD_UPLOAD_MAX_BYTES`.
- `backend/app/devseed.py`: artifact sets for e2e.
- `backend/tests/helpers.py`: serve `/reliquary` in `yatta_transport`.
- `backend/tests/test_db.py`, `test_gamedata.py`, `test_api_settings.py`.

**Frontend — create**
- `frontend/src/lib/good.ts` + `good.test.ts`: stat names, filters, labels.
- `frontend/src/lib/GoodImportButton.svelte`
- `frontend/src/lib/WeaponsTab.svelte`, `frontend/src/lib/ArtifactsTab.svelte`
- `frontend/e2e/good.spec.ts`, `frontend/e2e/fixtures/good-sample.json`

**Frontend — modify**
- `frontend/src/lib/types.ts`, `api.ts`, `materials.ts` (+ `materials.test.ts`), `MaterialPopover.svelte`
- `frontend/src/routes/inventory/+page.svelte`, `frontend/src/routes/settings/+page.svelte`, `frontend/src/routes/characters/[slug]/+page.svelte` (picker; confirm the exact folder name with `ls frontend/src/routes/characters`)
- `README.md`: a GOOD import section.

---

### Task 1: GOOD keys and file parsing (pure)

**Files:**
- Create: `backend/app/good/__init__.py`, `backend/app/good/keys.py` (only `good_key` in this task), `backend/app/good/parse.py`
- Create: `backend/tests/fixtures/good_sample.json`
- Test: `backend/tests/test_good_keys.py`, `backend/tests/test_good_parse.py`

**Interfaces:**
- Produces:
  - `good_key(name: str) -> str`
  - `class GoodFormatError(ValueError)`
  - `SLOTS: tuple[str, ...] = ("flower", "plume", "sands", "goblet", "circlet")`
  - `@dataclass(frozen=True) GoodWeapon(key: str, level: int, ascension: int, refinement: int, location: str, lock: bool)`
  - `@dataclass(frozen=True) GoodArtifact(set_key: str, slot: str, rarity: int, level: int, main_stat: str, substats: tuple[tuple[str, float], ...], location: str, lock: bool)`
  - `@dataclass(frozen=True) GoodFile(version: int, source: str | None, materials: dict[str, int], weapons: list[GoodWeapon], artifacts: list[GoodArtifact])`
  - `parse_good(content: bytes) -> GoodFile`

- [ ] **Step 1: Write the fixture** `backend/tests/fixtures/good_sample.json` (invented data; later tasks rely on these exact values):

```json
{
  "format": "GOOD",
  "version": 2,
  "source": "Test_Scanner",
  "materials": {
    "Mora": 1234567,
    "TeachingsOfFreedom": 40,
    "GuideToFreedom": 12,
    "DvalinsPlume": 3,
    "Fowl": 9,
    "NotARealItem": 1
  },
  "weapons": [
    {"key": "FavoniusSword", "level": 90, "ascension": 6, "refinement": 3, "location": "Bennett", "lock": true},
    {"key": "MistsplitterReforged", "level": 1, "ascension": 0, "refinement": 1, "location": "", "lock": false},
    {"key": "FavoniusSword", "level": 20, "ascension": 1, "refinement": 1, "location": "", "lock": false},
    {"key": "UnknownBlade", "level": 1, "ascension": 0, "refinement": 1, "location": "", "lock": false}
  ],
  "artifacts": [
    {"setKey": "GladiatorsFinale", "slotKey": "flower", "rarity": 5, "level": 20, "mainStatKey": "hp",
     "location": "TravelerAnemo", "lock": true,
     "substats": [{"key": "critRate_", "value": 3.9}, {"key": "atk_", "value": 5.8}, {"key": "", "value": 0}]},
    {"setKey": "NoblesseOblige", "slotKey": "goblet", "rarity": 5, "level": 16, "mainStatKey": "hydro_dmg_",
     "location": "", "lock": false, "substats": [{"key": "critDMG_", "value": 7.8}]},
    {"setKey": "NoblesseOblige", "slotKey": "sands", "rarity": 4, "level": 0, "mainStatKey": "enerRech_",
     "location": "SomeNewCharacter", "lock": false, "substats": []}
  ],
  "characters": [{"key": "Bennett", "level": 80}]
}
```

- [ ] **Step 2: Write the failing tests**

`backend/tests/test_good_keys.py`:

```python
import pytest

from app.good.keys import good_key


@pytest.mark.parametrize("name, key", [
    ("Shivada Jade Gemstone", "ShivadaJadeGemstone"),
    ("Wolf's Gravestone", "WolfsGravestone"),
    ("Dvalin's Plume", "DvalinsPlume"),
    ("Thrilling Tales of Dragon Slayers", "ThrillingTalesOfDragonSlayers"),
    ("Key of Khaj-Nisut", "KeyOfKhajNisut"),
    ('Philosophies of "Freedom"', "PhilosophiesOfFreedom"),
    ("Mora", "Mora"),
    ("Déjà vu", "DejaVu"),
    ("Kagotsurube Isshin", "KagotsurubeIsshin"),
    ("Amos' Bow", "AmosBow"),
    ("  The  Catch ", "TheCatch"),
    ("", ""),
])
def test_good_key(name, key):
    assert good_key(name) == key
```

`backend/tests/test_good_parse.py`:

```python
import json

import pytest

from app.good.parse import GoodArtifact, GoodFormatError, GoodWeapon, parse_good
from helpers import FIXTURES


def raw(**over) -> bytes:
    body = {"format": "GOOD", "version": 2, "source": "X"}
    body.update(over)
    return json.dumps(body).encode()


def test_parses_the_sample():
    f = parse_good((FIXTURES / "good_sample.json").read_bytes())
    assert f.version == 2 and f.source == "Test_Scanner"
    assert f.materials["Mora"] == 1234567 and len(f.materials) == 6
    assert f.weapons[0] == GoodWeapon("FavoniusSword", 90, 6, 3, "Bennett", True)
    assert len(f.weapons) == 4
    assert f.artifacts[0] == GoodArtifact("GladiatorsFinale", "flower", 5, 20, "hp",
                                          (("critRate_", 3.9), ("atk_", 5.8)), "TravelerAnemo", True)
    assert len(f.artifacts) == 3


@pytest.mark.parametrize("version", [1, 2, 3])
def test_supported_versions(version):
    assert parse_good(raw(version=version)).version == version


def test_missing_blocks_are_empty_and_unknown_fields_ignored():
    f = parse_good(raw(materials={"Mora": 5}, somethingNew={"a": 1}))
    assert f.materials == {"Mora": 5} and f.weapons == [] and f.artifacts == []


def test_utf8_bom_is_accepted():
    assert parse_good(b"\xef\xbb\xbf" + raw()).version == 2


def test_source_is_truncated_and_optional():
    assert parse_good(raw(source="S" * 100)).source == "S" * 64
    body = json.loads(raw())
    del body["source"]
    assert parse_good(json.dumps(body).encode()).source is None


@pytest.mark.parametrize("content, message", [
    (b"not json", "Not a GOOD file (could not read JSON)"),
    (b"\xff\xfe\x00", "Not a GOOD file (could not read JSON)"),
    (b"[1, 2]", "Not a GOOD file"),
    (json.dumps({"format": "XYZ", "version": 2}).encode(), "Not a GOOD file"),
    (json.dumps({"format": "GOOD", "version": 9}).encode(), "Unsupported GOOD version 9"),
    (json.dumps({"format": "GOOD", "version": "2"}).encode(), "Unsupported GOOD version 2"),
])
def test_whole_file_errors(content, message):
    with pytest.raises(GoodFormatError) as e:
        parse_good(content)
    assert str(e.value) == message


@pytest.mark.parametrize("over, block", [
    ({"materials": [1, 2]}, "materials"),
    ({"materials": {"Mora": -1}}, "materials"),
    ({"materials": {"Mora": True}}, "materials"),
    ({"materials": {"Mora": "5"}}, "materials"),
    ({"weapons": {"a": 1}}, "weapons"),
    ({"weapons": [{"key": "X"}]}, "weapons"),
    ({"weapons": [{"key": "", "level": 1, "refinement": 1}]}, "weapons"),
    ({"artifacts": [{"setKey": "A", "slotKey": "boots", "rarity": 5, "level": 0, "mainStatKey": "hp"}]}, "artifacts"),
    ({"artifacts": [{"setKey": "A", "slotKey": "flower", "rarity": 5, "level": 0}]}, "artifacts"),
    ({"artifacts": [{"setKey": "A", "slotKey": "flower", "rarity": 5, "level": 0, "mainStatKey": "hp",
                     "substats": "x"}]}, "artifacts"),
])
def test_block_errors_name_the_block(over, block):
    with pytest.raises(GoodFormatError) as e:
        parse_good(raw(**over))
    assert block in str(e.value)
```

- [ ] **Step 3: Run the tests and verify they fail**

Run: `PY -m pytest -q tests/test_good_keys.py tests/test_good_parse.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.good'`.

- [ ] **Step 4: Implement**

`backend/app/good/__init__.py`: empty file.

`backend/app/good/keys.py`:

```python
"""GOOD keys: the English name in PascalCase with punctuation removed, e.g. "Wolf's Gravestone" -> WolfsGravestone."""
from __future__ import annotations

import re
import unicodedata

_WORD_SPLIT = re.compile(r"[\s\-]+")
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


def good_key(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    parts = (_NON_ALNUM.sub("", w) for w in _WORD_SPLIT.split(ascii_name))
    return "".join(p[0].upper() + p[1:] for p in parts if p)
```

`backend/app/good/parse.py`:

```python
"""Validate and parse a GOOD (Genshin Open Object Description) export. In memory only; nothing is logged."""
from __future__ import annotations

import json
from dataclasses import dataclass

SUPPORTED_VERSIONS = (1, 2, 3)
SLOTS: tuple[str, ...] = ("flower", "plume", "sands", "goblet", "circlet")
SOURCE_MAX = 64


class GoodFormatError(ValueError):
    """A user-facing reason the file was rejected."""


@dataclass(frozen=True)
class GoodWeapon:
    key: str
    level: int
    ascension: int
    refinement: int
    location: str
    lock: bool


@dataclass(frozen=True)
class GoodArtifact:
    set_key: str
    slot: str
    rarity: int
    level: int
    main_stat: str
    substats: tuple[tuple[str, float], ...]
    location: str
    lock: bool


@dataclass(frozen=True)
class GoodFile:
    version: int
    source: str | None
    materials: dict[str, int]
    weapons: list[GoodWeapon]
    artifacts: list[GoodArtifact]


def _bad(block: str) -> GoodFormatError:
    return GoodFormatError(f"The {block} section of this GOOD file is not in the expected format")


def _int(value, block: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise _bad(block)
    return value


def _str(value, block: str, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value):
        raise _bad(block)
    return value


def _materials(value) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _bad("materials")
    return {_str(k, "materials"): _int(v, "materials") for k, v in value.items()}


def _list(value, block: str) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
        raise _bad(block)
    return value


def _weapon(w: dict) -> GoodWeapon:
    b = "weapons"
    return GoodWeapon(_str(w.get("key"), b), _int(w.get("level"), b, 1), _int(w.get("ascension", 0), b),
                      _int(w.get("refinement"), b, 1), _str(w.get("location"), b, required=False),
                      bool(w.get("lock", False)))


def _artifact(a: dict) -> GoodArtifact:
    b = "artifacts"
    slot = _str(a.get("slotKey"), b)
    if slot not in SLOTS:
        raise _bad(b)
    subs_raw = a.get("substats", [])
    if not isinstance(subs_raw, list) or not all(isinstance(x, dict) for x in subs_raw):
        raise _bad(b)
    subs: list[tuple[str, float]] = []
    for sub in subs_raw:
        key, value = sub.get("key"), sub.get("value")
        if not key:
            continue                      # scanners emit {"key": ""} for unrolled substats
        if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _bad(b)
        subs.append((key, float(value)))
    return GoodArtifact(_str(a.get("setKey"), b), slot, _int(a.get("rarity"), b, 1), _int(a.get("level"), b),
                        _str(a.get("mainStatKey"), b), tuple(subs), _str(a.get("location"), b, required=False),
                        bool(a.get("lock", False)))


def parse_good(content: bytes) -> GoodFile:
    try:
        body = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GoodFormatError("Not a GOOD file (could not read JSON)") from None
    if not isinstance(body, dict) or body.get("format") != "GOOD":
        raise GoodFormatError("Not a GOOD file")
    version = body.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version not in SUPPORTED_VERSIONS:
        raise GoodFormatError(f"Unsupported GOOD version {version}")
    source = body.get("source")
    return GoodFile(
        version=version,
        source=source[:SOURCE_MAX] if isinstance(source, str) and source else None,
        materials=_materials(body.get("materials")),
        weapons=[_weapon(w) for w in _list(body.get("weapons"), "weapons")],
        artifacts=[_artifact(a) for a in _list(body.get("artifacts"), "artifacts")],
    )
```

- [ ] **Step 5: Run the tests and verify they pass**

Run: `PY -m pytest -q tests/test_good_keys.py tests/test_good_parse.py`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/app/good backend/tests/test_good_keys.py backend/tests/test_good_parse.py backend/tests/fixtures/good_sample.json
git commit -m "feat(good): GOOD key normalisation and file parsing"
```

---

### Task 2: Tables, migration, artifact sets and material keys in game data

**Files:**
- Modify: `backend/app/db/models.py`
- Create: `backend/migrations/versions/0006_good_import.py`
- Create: `backend/app/gamedata/artifacts.py`, `backend/tests/fixtures/yatta_reliquary.json`
- Modify: `backend/app/gamedata/materials.py`, `backend/app/gamedata/service.py`, `backend/tests/helpers.py`
- Test: `backend/tests/test_db.py`, `backend/tests/test_gamedata.py`

**Interfaces:**
- Consumes: `good_key` (Task 1).
- Produces:
  - Models `GameArtifactSet(id, name, icon, sort_order)`, `GoodImport(id, imported_at, source, counts, unmatched)`, `GoodMaterial(material_id, count)`, `GoodWeapon` model named **`GoodWeaponRow`**, `GoodArtifactRow` (the `Row` suffix avoids clashing with the parse dataclasses).
  - `app.gamedata.artifacts.ArtifactSetData(id, name, icon, sort_order)`, `parse_reliquary_list(payload) -> list[ArtifactSetData]`, `fetch_reliquary_list(http)`.
  - `app.gamedata.materials.fetch_material_catalogue(http) -> tuple[list[MaterialData], list[str]]`
  - `app.gamedata.service.META_MAT_KEYS = "material_keys_all"`, `refresh_artifact_sets(session_factory, http, now=None, force=False) -> bool`; `gamedata_status(...)["artifact_sets"] == {"fetched_at", "last_error", "count"}`.

- [ ] **Step 1: Write the Yatta fixture** `backend/tests/fixtures/yatta_reliquary.json` (trimmed public shape, verified 2026-11-22):

```json
{"response": 200, "data": {"items": {
  "15001": {"id": 15001, "name": "Gladiator's Finale", "levelList": [4, 5], "affixList": {}, "icon": "UI_RelicIcon_15001_4", "route": "Gladiator's Finale", "sortOrder": 100},
  "15007": {"id": 15007, "name": "Noblesse Oblige", "levelList": [4, 5], "affixList": {}, "icon": "UI_RelicIcon_15007_4", "route": "Noblesse Oblige", "sortOrder": 120}
}}}
```

In `backend/tests/helpers.py` `yatta_transport`, load it next to the others (`reliquary = load_fixture("yatta_reliquary.json")`) and add a branch before the final 404:

```python
        if path.endswith("/reliquary"):
            return httpx.Response(200, json=reliquary)
```

- [ ] **Step 2: Write the failing tests**

Append to `backend/tests/test_db.py` (follow the imports already at the top of that file: `inspect`, `make_engine`, `migrate`):

```python
def test_phase6_tables_exist(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    names = set(inspect(engine).get_table_names())
    assert {"game_artifact_set", "good_import", "good_material", "good_weapon", "good_artifact"} <= names
```

Append to `backend/tests/test_gamedata.py` (add `refresh_artifact_sets`, `META_MAT_KEYS`, `_get_meta` and `GameArtifactSet` to the imports):

```python
async def test_refresh_materials_remembers_every_yatta_material_key(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_materials(session_factory, http)
    with session_factory() as s:
        keys = set(_get_meta(s, META_MAT_KEYS))
        assert {"Fowl", "SomeQuestItem", "Mora", "GuideToFreedom"} <= keys   # food/quest kept for matching
        assert s.get(GameMaterial, 100001) is None                           # but not in the catalogue


async def test_missing_material_keys_meta_forces_a_refresh(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_materials(session_factory, http)
        with session_factory.begin() as s:
            s.delete(s.get(GameMeta, META_MAT_KEYS))
        assert await refresh_materials(session_factory, http) is True


async def test_refresh_artifact_sets(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh_artifact_sets(session_factory, http) is True
        assert await refresh_artifact_sets(session_factory, http) is False      # fresh
    with session_factory() as s:
        assert s.get(GameArtifactSet, 15001).name == "Gladiator's Finale"
        assert s.get(GameArtifactSet, 15007).icon == "UI_RelicIcon_15007_4"
        assert gamedata_status(s)["artifact_sets"]["count"] == 2


async def test_artifact_set_failure_keeps_cache(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_artifact_sets(session_factory, http)
    async with httpx.AsyncClient(transport=yatta_transport(status=503)) as http:
        assert await refresh_artifact_sets(session_factory, http, force=True) is False
    with session_factory() as s:
        status = gamedata_status(s)["artifact_sets"]
        assert status["count"] == 2 and "503" in status["last_error"]
```

(If `GameMeta` is not yet imported in `test_gamedata.py`, add it from `app.db.models`.)

- [ ] **Step 3: Run the tests and verify they fail**

Run: `PY -m pytest -q tests/test_db.py tests/test_gamedata.py`
Expected: FAIL (`ImportError` on `refresh_artifact_sets` / missing tables).

- [ ] **Step 4: Implement the models** in `backend/app/db/models.py`. Add `GameArtifactSet` after `GameWeapon`, and a new section after the user-data tables:

```python
class GameArtifactSet(Base):
    __tablename__ = "game_artifact_set"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String)
    icon: Mapped[str] = mapped_column(String)
    sort_order: Mapped[int] = mapped_column(Integer)
```

```python
# --- GOOD import (user data; sync never writes these) -----------------------
class GoodImport(Base):
    __tablename__ = "good_import"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)          # always 1
    imported_at: Mapped[datetime] = mapped_column(DateTime)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    counts: Mapped[dict] = mapped_column(JSON)
    unmatched: Mapped[list] = mapped_column(JSON)


class GoodMaterial(Base):
    __tablename__ = "good_material"
    material_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    count: Mapped[int] = mapped_column(Integer)


class GoodWeaponRow(Base):
    __tablename__ = "good_weapon"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    weapon_id: Mapped[int] = mapped_column(Integer, index=True)
    level: Mapped[int] = mapped_column(Integer)
    ascension: Mapped[int] = mapped_column(Integer)
    refinement: Mapped[int] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String, nullable=True)     # raw GOOD character key
    character_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lock: Mapped[bool] = mapped_column(Boolean)


class GoodArtifactRow(Base):
    __tablename__ = "good_artifact"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    set_id: Mapped[int] = mapped_column(Integer)
    slot: Mapped[str] = mapped_column(String)
    rarity: Mapped[int] = mapped_column(Integer)
    level: Mapped[int] = mapped_column(Integer)
    main_stat: Mapped[str] = mapped_column(String)
    substats: Mapped[list] = mapped_column(JSON)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    character_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lock: Mapped[bool] = mapped_column(Boolean)
```

- [ ] **Step 5: Write the migration** `backend/migrations/versions/0006_good_import.py`:

```python
"""phase 6 GOOD import

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-22
"""
from alembic import op
import sqlalchemy as sa

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_artifact_set",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
    )
    op.create_table(
        "good_import",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("imported_at", sa.DateTime(), nullable=False),
        sa.Column("source", sa.String(), nullable=True),
        sa.Column("counts", sa.JSON(), nullable=False),
        sa.Column("unmatched", sa.JSON(), nullable=False),
    )
    op.create_table(
        "good_material",
        sa.Column("material_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("count", sa.Integer(), nullable=False),
    )
    op.create_table(
        "good_weapon",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("weapon_id", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("ascension", sa.Integer(), nullable=False),
        sa.Column("refinement", sa.Integer(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("lock", sa.Boolean(), nullable=False),
    )
    op.create_index("ix_good_weapon_weapon_id", "good_weapon", ["weapon_id"])
    op.create_table(
        "good_artifact",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("set_id", sa.Integer(), nullable=False),
        sa.Column("slot", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("level", sa.Integer(), nullable=False),
        sa.Column("main_stat", sa.String(), nullable=False),
        sa.Column("substats", sa.JSON(), nullable=False),
        sa.Column("location", sa.String(), nullable=True),
        sa.Column("character_id", sa.Integer(), nullable=True),
        sa.Column("lock", sa.Boolean(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("good_artifact")
    op.drop_index("ix_good_weapon_weapon_id", table_name="good_weapon")
    op.drop_table("good_weapon")
    op.drop_table("good_material")
    op.drop_table("good_import")
    op.drop_table("game_artifact_set")
```

- [ ] **Step 6: Implement the game-data parts**

`backend/app/gamedata/artifacts.py`:

```python
"""Artifact set names and icons from Yatta (gi.yatta.moe /reliquary); used to match GOOD setKeys."""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.gamedata.materials import _get_json


@dataclass(frozen=True)
class ArtifactSetData:
    id: int
    name: str
    icon: str
    sort_order: int


def parse_reliquary_list(payload: dict) -> list[ArtifactSetData]:
    sets = [ArtifactSetData(int(v["id"]), str(v["name"]), str(v["icon"]), int(v.get("sortOrder") or 0))
            for v in payload["data"]["items"].values()]
    return sorted(sets, key=lambda a: a.id)


async def fetch_reliquary_list(http: httpx.AsyncClient) -> list[ArtifactSetData]:
    return parse_reliquary_list(await _get_json(http, "reliquary"))
```

In `backend/app/gamedata/materials.py`, add below `fetch_material_list` (keep `fetch_material_list` for existing callers):

```python
async def fetch_material_catalogue(http: httpx.AsyncClient) -> tuple[list[MaterialData], list[str]]:
    """The eight-category catalogue plus the GOOD key of every Yatta item (food, quest items...),
    so a GOOD import can tell 'not a planner material' apart from 'unknown'."""
    from app.good.keys import good_key
    payload = await _get_json(http, "material")
    keys = sorted({good_key(str(v["name"])) for v in payload["data"]["items"].values()} - {""})
    return parse_material_list(payload), keys
```

In `backend/app/gamedata/service.py`:

1. Import `GameArtifactSet` and `from app.gamedata.artifacts import fetch_reliquary_list`; import `fetch_material_catalogue` instead of `fetch_material_list`.
2. Add `META_MAT_KEYS = "material_keys_all"` beside `META_MAT_FETCHED`.
3. In `materials_need_refresh`, return True when `_get_meta(session, META_MAT_KEYS) is None` (put it right after the `fetched` check).
4. In `refresh_materials`, replace `mats = await fetch_material_list(http)` with `mats, all_keys = await fetch_material_catalogue(http)`, and inside the `with session_factory.begin() as s:` block that calls `_store_catalogue`, add `_set_meta(s, META_MAT_KEYS, all_keys)`.
5. Add the artifact-set refresh and include it in `refresh_all` and `gamedata_status`:

```python
META_SETS_FETCHED = "artifact_sets_fetched_at"
META_SETS_ERROR = "artifact_sets_last_error"


def artifact_sets_need_refresh(session: Session, now: datetime) -> bool:
    fetched = _get_meta(session, META_SETS_FETCHED)
    if not fetched or session.scalar(select(func.count()).select_from(GameArtifactSet)) == 0:
        return True
    return now - datetime.fromisoformat(fetched.rstrip("Z")) > timedelta(days=GAMEDATA_MAX_AGE_DAYS)


async def refresh_artifact_sets(session_factory: sessionmaker, http: httpx.AsyncClient,
                                now: datetime | None = None, force: bool = False) -> bool:
    now = now or utcnow()
    with session_factory() as s:
        if not force and not artifact_sets_need_refresh(s, now):
            return False
    try:
        sets = await fetch_reliquary_list(http)
    except FETCH_ERRORS as e:
        message = f"{type(e).__name__}: {e}"[:300]
        log.warning("Artifact set refresh failed: %s", message)
        with session_factory.begin() as s:
            _set_meta(s, META_SETS_ERROR, message)
        return False
    with session_factory.begin() as s:
        for a in sets:
            s.merge(GameArtifactSet(id=a.id, name=a.name, icon=a.icon, sort_order=a.sort_order))
        _set_meta(s, META_SETS_FETCHED, iso(now))
        _set_meta(s, META_SETS_ERROR, None)
    return True
```

`refresh_all` becomes:

```python
    characters = await refresh(session_factory, http, now=now, force=force)
    materials = await refresh_materials(session_factory, http, now=now, force=force)
    sets = await refresh_artifact_sets(session_factory, http, now=now, force=force)
    banners = await refresh_banners(session_factory, http, now=now, force=force or characters or materials)
    return characters or materials or sets or banners
```

`gamedata_status` gains:

```python
        "artifact_sets": {
            "fetched_at": _get_meta(session, META_SETS_FETCHED),
            "last_error": _get_meta(session, META_SETS_ERROR),
            "count": session.scalar(select(func.count()).select_from(GameArtifactSet)) or 0,
        },
```

- [ ] **Step 7: Run the whole backend suite**

Run: `PY -m pytest -q`
Expected: all PASS. Earlier tests with a hard-coded `refresh_all` call count or a full `gamedata_status` dict equality may need the new key added. Update such assertions; don't weaken them.

- [ ] **Step 8: Commit**

```bash
git add backend
git commit -m "feat(good): GOOD tables, artifact sets and every material key in game data"
```

---

### Task 3: Matching and storing a snapshot

**Files:**
- Modify: `backend/app/good/keys.py` (add `KeyIndex`)
- Create: `backend/app/good/store.py`
- Modify: `backend/app/settings/store.py` (default)
- Test: `backend/tests/test_good_store.py`

**Interfaces:**
- Consumes: `good_key`, `parse_good`, `GoodFile` (Task 1); models and `META_MAT_KEYS` (Task 2); `TRAVELER_ID`, `MANEKIN_ID` from `app.gamedata.yatta`.
- Produces:
  - `KeyIndex(materials: dict[str, int], weapons: dict[str, int], sets: dict[str, int], characters: dict[str, int], known_material_keys: frozenset[str])`, `KeyIndex.build(session) -> KeyIndex`, `KeyIndex.character(key: str) -> int | None`
  - `MatchResult(materials: dict[int, int], weapons: list[dict], artifacts: list[dict], counts: dict, unmatched: list[str])`. Weapon dicts have the `GoodWeaponRow` column names minus `id`; artifact dicts have the `GoodArtifactRow` names minus `id`.
  - `match_file(parsed: GoodFile, index: KeyIndex) -> MatchResult`
  - `ImportSummary(imported_at: str, source: str | None, counts: dict, unmatched: list[str])` with `.to_dict()`
  - `replace_snapshot(session, parsed, index, now) -> ImportSummary`, `delete_snapshot(session) -> None`
  - `good_enabled(session) -> bool`, `good_active(session) -> GoodImport | None` (enabled **and** imported), `import_summary(row: GoodImport) -> ImportSummary`
  - `scan_counts(session) -> dict[int, int]`, `owned_weapons(session) -> dict[int, dict]` (`{"count", "best_level", "best_refinement"}`)
  - `counts` shape: `{"materials": {"matched", "ignored", "unmatched"}, "weapons": {"matched", "unmatched"}, "artifacts": {"matched", "unmatched"}}`; `unmatched` entries are `"<block>:<Key>"` with block in `material|weapon|set|character`, sorted, unique, capped at 200.
  - Settings default `"good_import_enabled": False`.

- [ ] **Step 1: Write the failing tests** `backend/tests/test_good_store.py`:

```python
import json
import logging
from datetime import datetime

from sqlalchemy import func, select

from app.db.models import (GameArtifactSet, GameMaterial, GameMeta, GameWeapon, GoodArtifactRow, GoodImport,
                           GoodMaterial, GoodWeaponRow)
from app.gamedata.service import META_MAT_KEYS
from app.good.keys import KeyIndex
from app.good.parse import parse_good
from app.good.store import (delete_snapshot, good_active, match_file, owned_weapons, replace_snapshot,
                            scan_counts)
from app.settings.store import set_setting
from helpers import FIXTURES, seed_game

NOW = datetime(2026, 11, 22, 12, 0)
SAMPLE = (FIXTURES / "good_sample.json").read_bytes()


def seed_catalogue(sf):
    seed_game(sf)
    with sf.begin() as s:
        for order, (mid, name) in enumerate([(202, "Mora"), (104301, "Teachings of Freedom"),
                                             (104302, "Guide to Freedom"), (113003, "Dvalin's Plume")]):
            s.add(GameMaterial(id=mid, name=name, icon=f"UI_ItemIcon_{mid}", rarity=3, yatta_type="x",
                               category="talent", family=mid, craft_from=None, sources=[], sort_order=order,
                               detail_fetched=True))
        s.add(GameWeapon(id=11401, name="Favonius Sword", icon="UI_EquipIcon_Sword_Zephyrus", rarity=4,
                         weapon_type="Sword"))
        s.add(GameWeapon(id=11509, name="Mistsplitter Reforged", icon="UI_EquipIcon_Sword_Narukami", rarity=5,
                         weapon_type="Sword"))
        s.add(GameArtifactSet(id=15001, name="Gladiator's Finale", icon="UI_RelicIcon_15001_4", sort_order=1))
        s.add(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=2))
        s.merge(GameMeta(key=META_MAT_KEYS, value=["Fowl", "GuideToFreedom", "Mora", "SweetMadame"]))


def index(sf) -> KeyIndex:
    with sf() as s:
        return KeyIndex.build(s)


def test_match_counts_and_unmatched(session_factory):
    seed_catalogue(session_factory)
    m = match_file(parse_good(SAMPLE), index(session_factory))
    assert m.materials == {202: 1234567, 104301: 40, 104302: 12, 113003: 3}
    assert m.counts == {"materials": {"matched": 4, "ignored": 1, "unmatched": 1},
                        "weapons": {"matched": 3, "unmatched": 1},
                        "artifacts": {"matched": 3, "unmatched": 0}}
    assert m.unmatched == ["character:SomeNewCharacter", "material:NotARealItem", "weapon:UnknownBlade"]


def test_food_is_ignored_not_unmatched(session_factory):
    seed_catalogue(session_factory)
    body = {"format": "GOOD", "version": 2, "materials": {"Fowl": 3, "SweetMadame": 2, "Mora": 5}}
    m = match_file(parse_good(json.dumps(body).encode()), index(session_factory))
    assert m.counts["materials"] == {"matched": 1, "ignored": 2, "unmatched": 0}
    assert m.unmatched == []


def test_holders_traveler_and_unknown(session_factory):
    seed_catalogue(session_factory)
    m = match_file(parse_good(SAMPLE), index(session_factory))
    bennett = next(w for w in m.weapons if w["location"] == "Bennett")
    assert bennett["character_id"] == 10000032
    free = [w for w in m.weapons if w["location"] is None]
    assert len(free) == 2 and all(w["character_id"] is None for w in free)
    traveler = next(a for a in m.artifacts if a["location"] == "TravelerAnemo")
    assert traveler["character_id"] == 10000005
    unknown = next(a for a in m.artifacts if a["location"] == "SomeNewCharacter")
    assert unknown["character_id"] is None            # equipped by someone we can't name, not "unequipped"


def test_index_maps_manekina_and_collisions_keep_first(session_factory, caplog):
    seed_catalogue(session_factory)
    with session_factory.begin() as s:
        s.add(GameWeapon(id=99999, name="Favonius-Sword", icon="x", rarity=4, weapon_type="Sword"))
    caplog.set_level(logging.INFO)
    idx = index(session_factory)
    assert idx.weapons["FavoniusSword"] == 11401
    assert idx.character("Manekina") == idx.character("Manekin") == 10000117
    assert idx.character("") is None
    assert "FavoniusSword" in caplog.text


def test_replace_snapshot_writes_everything(session_factory):
    seed_catalogue(session_factory)
    with session_factory.begin() as s:
        summary = replace_snapshot(s, parse_good(SAMPLE), KeyIndex.build(s), NOW)
    assert summary.imported_at == "2026-11-22T12:00:00Z" and summary.source == "Test_Scanner"
    with session_factory() as s:
        assert s.get(GoodImport, 1).counts["weapons"]["matched"] == 3
        assert s.scalar(select(func.count()).select_from(GoodWeaponRow)) == 3
        assert s.scalar(select(func.count()).select_from(GoodArtifactRow)) == 3
        assert s.get(GoodMaterial, 104302).count == 12
        art = s.scalars(select(GoodArtifactRow).where(GoodArtifactRow.slot == "flower")).one()
        assert art.substats == [{"key": "critRate_", "value": 3.9}, {"key": "atk_", "value": 5.8}]


def test_reimport_replaces_everything(session_factory):
    seed_catalogue(session_factory)
    with session_factory.begin() as s:
        replace_snapshot(s, parse_good(SAMPLE), KeyIndex.build(s), NOW)
    small = {"format": "GOOD", "version": 1, "materials": {"Mora": 7}}
    with session_factory.begin() as s:
        replace_snapshot(s, parse_good(json.dumps(small).encode()), KeyIndex.build(s), NOW)
    with session_factory() as s:
        assert s.scalar(select(func.count()).select_from(GoodWeaponRow)) == 0
        assert s.scalar(select(func.count()).select_from(GoodArtifactRow)) == 0
        assert {r.material_id: r.count for r in s.scalars(select(GoodMaterial))} == {202: 7}
        assert s.get(GoodImport, 1).source is None


def test_delete_and_active_and_aggregates(session_factory):
    seed_catalogue(session_factory)
    with session_factory.begin() as s:
        replace_snapshot(s, parse_good(SAMPLE), KeyIndex.build(s), NOW)
    with session_factory() as s:
        assert good_active(s) is None                     # toggle is off by default
    with session_factory.begin() as s:
        set_setting(s, "good_import_enabled", True)
    with session_factory() as s:
        assert good_active(s).id == 1
        assert scan_counts(s)[202] == 1234567
        assert owned_weapons(s)[11401] == {"count": 2, "best_level": 90, "best_refinement": 3}
    with session_factory.begin() as s:
        delete_snapshot(s)
    with session_factory() as s:
        assert good_active(s) is None and scan_counts(s) == {}
        assert s.scalar(select(func.count()).select_from(GoodArtifactRow)) == 0


def test_unmatched_is_capped_at_200(session_factory):
    seed_catalogue(session_factory)
    body = {"format": "GOOD", "version": 2, "materials": {f"Nope{i:04d}": 1 for i in range(300)}}
    m = match_file(parse_good(json.dumps(body).encode()), index(session_factory))
    assert len(m.unmatched) == 200 and m.counts["materials"]["unmatched"] == 300
```

- [ ] **Step 2: Run them and verify they fail**

Run: `PY -m pytest -q tests/test_good_store.py`
Expected: FAIL (`ImportError: cannot import name 'KeyIndex'`).

- [ ] **Step 3: Add the setting default** in `backend/app/settings/store.py` `DEFAULTS`:

```python
    "good_import_enabled": False,   # opt-in GOOD scanner import (Phase 6)
```

- [ ] **Step 4: Add `KeyIndex`** to `backend/app/good/keys.py`:

```python
import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)


def _index(rows, label: str) -> dict[str, int]:
    """First id wins on a key collision; collisions are logged by key only."""
    out: dict[str, int] = {}
    for rid, name in rows:
        key = good_key(name)
        if not key:
            continue
        if key in out and out[key] != rid:
            log.info("GOOD %s key collision: %s", label, key)
            continue
        out[key] = rid
    return out


@dataclass(frozen=True)
class KeyIndex:
    materials: dict[str, int]
    weapons: dict[str, int]
    sets: dict[str, int]
    characters: dict[str, int]
    known_material_keys: frozenset[str]

    @classmethod
    def build(cls, session: Session) -> "KeyIndex":
        from app.db.models import GameArtifactSet, GameCharacter, GameMaterial, GameMeta, GameWeapon
        from app.gamedata.service import META_MAT_KEYS
        meta = session.get(GameMeta, META_MAT_KEYS)
        return cls(
            materials=_index(session.execute(select(GameMaterial.id, GameMaterial.name)
                                             .order_by(GameMaterial.sort_order, GameMaterial.id)), "material"),
            weapons=_index(session.execute(select(GameWeapon.id, GameWeapon.name).order_by(GameWeapon.id)), "weapon"),
            sets=_index(session.execute(select(GameArtifactSet.id, GameArtifactSet.name)
                                        .order_by(GameArtifactSet.id)), "set"),
            characters=_index(session.execute(select(GameCharacter.id, GameCharacter.name)
                                              .order_by(GameCharacter.id)), "character"),
            known_material_keys=frozenset(meta.value or []) if meta is not None else frozenset(),
        )

    def character(self, key: str) -> int | None:
        from app.gamedata.yatta import MANEKIN_ID, TRAVELER_ID
        if not key:
            return None
        if key.startswith("Traveler"):
            return TRAVELER_ID
        if key in ("Manekin", "Manekina"):
            return MANEKIN_ID
        return self.characters.get(key)
```

(Keep the imports of `models`/`service` local to avoid an import cycle: `service.py` → `materials.py` → `keys.py`.)

- [ ] **Step 5: Implement** `backend/app/good/store.py`:

```python
"""Match a parsed GOOD file against our catalogue and store it as the single current snapshot."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import GoodArtifactRow, GoodImport, GoodMaterial, GoodWeaponRow
from app.good.keys import KeyIndex
from app.good.parse import GoodFile
from app.settings.store import get_setting
from app.timeutil import iso

UNMATCHED_MAX = 200


@dataclass
class MatchResult:
    materials: dict[int, int] = field(default_factory=dict)
    weapons: list[dict] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    unmatched: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImportSummary:
    imported_at: str
    source: str | None
    counts: dict
    unmatched: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _holder(index: KeyIndex, location: str, missing: set[str]) -> tuple[str | None, int | None]:
    if not location:
        return None, None
    cid = index.character(location)
    if cid is None:
        missing.add(f"character:{location}")
    return location, cid


def match_file(parsed: GoodFile, index: KeyIndex) -> MatchResult:
    out = MatchResult()
    missing: set[str] = set()
    mat = {"matched": 0, "ignored": 0, "unmatched": 0}
    for key, count in parsed.materials.items():
        mid = index.materials.get(key)
        if mid is not None:
            out.materials[mid] = out.materials.get(mid, 0) + count
            mat["matched"] += 1
        elif key in index.known_material_keys:
            mat["ignored"] += 1
        else:
            mat["unmatched"] += 1
            missing.add(f"material:{key}")
    wpn = {"matched": 0, "unmatched": 0}
    for w in parsed.weapons:
        wid = index.weapons.get(w.key)
        if wid is None:
            wpn["unmatched"] += 1
            missing.add(f"weapon:{w.key}")
            continue
        location, cid = _holder(index, w.location, missing)
        out.weapons.append({"weapon_id": wid, "level": w.level, "ascension": w.ascension,
                            "refinement": w.refinement, "location": location, "character_id": cid,
                            "lock": w.lock})
        wpn["matched"] += 1
    art = {"matched": 0, "unmatched": 0}
    for a in parsed.artifacts:
        sid = index.sets.get(a.set_key)
        if sid is None:
            art["unmatched"] += 1
            missing.add(f"set:{a.set_key}")
            continue
        location, cid = _holder(index, a.location, missing)
        out.artifacts.append({"set_id": sid, "slot": a.slot, "rarity": a.rarity, "level": a.level,
                              "main_stat": a.main_stat,
                              "substats": [{"key": k, "value": v} for k, v in a.substats],
                              "location": location, "character_id": cid, "lock": a.lock})
        art["matched"] += 1
    out.counts = {"materials": mat, "weapons": wpn, "artifacts": art}
    out.unmatched = sorted(missing)[:UNMATCHED_MAX]
    return out


def _clear(session: Session) -> None:
    for model in (GoodArtifactRow, GoodWeaponRow, GoodMaterial, GoodImport):
        session.execute(delete(model))


def replace_snapshot(session: Session, parsed: GoodFile, index: KeyIndex, now: datetime) -> ImportSummary:
    """Caller owns the transaction (use session_factory.begin()), so a failure rolls everything back."""
    m = match_file(parsed, index)
    _clear(session)
    session.add(GoodImport(id=1, imported_at=now, source=parsed.source, counts=m.counts, unmatched=m.unmatched))
    session.add_all(GoodMaterial(material_id=mid, count=n) for mid, n in m.materials.items())
    session.add_all(GoodWeaponRow(**w) for w in m.weapons)
    session.add_all(GoodArtifactRow(**a) for a in m.artifacts)
    session.flush()
    return ImportSummary(iso(now), parsed.source, m.counts, m.unmatched)


def delete_snapshot(session: Session) -> None:
    _clear(session)
    session.flush()


def import_summary(row: GoodImport) -> ImportSummary:
    return ImportSummary(iso(row.imported_at), row.source, row.counts, row.unmatched)


def good_enabled(session: Session) -> bool:
    return bool(get_setting(session, "good_import_enabled"))


def good_active(session: Session) -> GoodImport | None:
    """The current snapshot, but only while the user has GOOD import switched on."""
    return session.get(GoodImport, 1) if good_enabled(session) else None


def scan_counts(session: Session) -> dict[int, int]:
    return {r.material_id: r.count for r in session.scalars(select(GoodMaterial))}


def owned_weapons(session: Session) -> dict[int, dict]:
    rows = session.execute(select(GoodWeaponRow.weapon_id, func.count(), func.max(GoodWeaponRow.level),
                                  func.max(GoodWeaponRow.refinement)).group_by(GoodWeaponRow.weapon_id))
    return {wid: {"count": n, "best_level": lvl, "best_refinement": ref} for wid, n, lvl, ref in rows}
```

Check `iso()` in `app/timeutil.py` produces `"2026-11-22T12:00:00Z"` for a naive UTC datetime (the gamedata tests already rely on that format). If not, adjust the test expectation to match `iso`'s format, not the other way round.

- [ ] **Step 6: Run the tests and verify they pass**

Run: `PY -m pytest -q tests/test_good_store.py tests/test_settings_store.py`
Expected: all PASS.

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat(good): match GOOD keys to the catalogue and store one snapshot"
```

---

### Task 4: API — import, status, delete, lists, inventory scan, owned weapons, setting

**Files:**
- Create: `backend/app/api/good.py`
- Modify: `backend/app/api/__init__.py`, `backend/app/api/planner.py`, `backend/app/api/settings.py`, `backend/app/config.py`
- Test: `backend/tests/test_api_good.py`, `backend/tests/test_api_settings.py` (leak test)

**Interfaces:**
- Consumes: everything in `app.good.store` (Task 3), `parse_good`/`GoodFormatError` (Task 1), models (Task 2).
- Produces (HTTP, used by the frontend in Tasks 6–8):
  - `GET /api/good/status` → `{enabled: bool, imported_at: str|null, source: str|null, counts: dict|null, unmatched: list[str]}` (data is reported even when disabled, so Settings can show "Last import").
  - `POST /api/good/import` (multipart `file`) → `ImportSummary.to_dict()`; 409 `"Turn on GOOD inventory import in Settings first."` / 409 `"Refresh game data first"`; 400 `GoodFormatError` message; 413 `"The file is larger than 20 MB."`
  - `DELETE /api/good` → 204.
  - `GET /api/good/weapons` → list of `{id, weapon_id, name, icon, rarity, weapon_type, level, ascension, refinement, lock, location, holder: {id, name, slug, icon}|null}` sorted rarity desc, name, level desc; 404 `"No GOOD import"` when not active.
  - `GET /api/good/artifacts` → list of `{id, set_id, set_name, icon, slot, rarity, level, main_stat, substats, lock, location, holder}` sorted rarity desc, set name, slot order, level desc; 404 when not active. `icon` is the set icon with its slot suffix swapped: flower `_4`, plume `_2`, sands `_5`, goblet `_1`, circlet `_3`.
  - `GET /api/inventory` adds `good: {imported_at, source}|null` at top level and `scan: int|null` on every material.
  - `GET /api/weapons` adds `owned: {count, best_level, best_refinement}|null`; when active, owned weapons sort first.
  - `GET/PUT /api/settings` include `good_import_enabled: bool`.

- [ ] **Step 1: Write the failing tests** `backend/tests/test_api_good.py`:

```python
import json

from app.db.engine import make_engine, make_session_factory, migrate
from app.db.models import CharacterGoal, GameArtifactSet, GameMaterial, GameMeta, GameWeapon
from app.gamedata.service import META_MAT_KEYS
from app.sync.persist import save_gaps
from app.sync.hoyolab import GapResult, MaterialAmount
from app.planner.requests import snapshot
from app.timeutil import utcnow
from helpers import FIXTURES, make_client, seed_game

SAMPLE = (FIXTURES / "good_sample.json").read_bytes()


def setup(paths, catalogue=True, gaps=True):
    engine = make_engine(paths.db_file)
    migrate(engine)
    sf = make_session_factory(engine)
    seed_game(sf)
    now = utcnow()
    with sf.begin() as s:
        if catalogue:
            for order, (mid, name, cat) in enumerate([(202, "Mora", "exp"), (104301, "Teachings of Freedom", "talent"),
                                                      (104302, "Guide to Freedom", "talent"),
                                                      (113003, "Dvalin's Plume", "weekly"),
                                                      (100055, "Small Lamp Grass", "specialty")]):
                s.add(GameMaterial(id=mid, name=name, icon=f"UI_ItemIcon_{mid}", rarity=3, yatta_type="x",
                                   category=cat, family=mid, craft_from=None, sources=[], sort_order=order,
                                   detail_fetched=True))
            s.add(GameWeapon(id=11401, name="Favonius Sword", icon="UI_EquipIcon_Sword_Zephyrus", rarity=4,
                             weapon_type="Sword"))
            s.add(GameWeapon(id=11509, name="Mistsplitter Reforged", icon="UI_EquipIcon_Sword_Narukami",
                             rarity=5, weapon_type="Sword"))
            s.add(GameWeapon(id=11301, name="Cool Steel", icon="UI_EquipIcon_Sword_Steel", rarity=3,
                             weapon_type="Sword"))
            s.add(GameArtifactSet(id=15001, name="Gladiator's Finale", icon="UI_RelicIcon_15001_4", sort_order=1))
            s.add(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=2))
            s.merge(GameMeta(key=META_MAT_KEYS, value=["Fowl"]))
        if catalogue and gaps:
            s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                                target_skill=8, target_burst=8, target_weapon_level=90, updated_at=now))
            s.flush()
            amt = lambda mid, need, short: MaterialAmount(mid, "x", "", 3, need, short)  # noqa: E731
            save_gaps(s, GapResult(per_character={10000032: [amt(104302, 15, 7), amt(104301, 10, 0),
                                                             amt(113003, 2, 0)]},
                                   total=[amt(104302, 15, 7), amt(104301, 10, 0), amt(113003, 2, 0)], spare=[]),
                      snapshot(s), [], now)
    engine.dispose()


def enable(client, on=True):
    assert client.put("/api/settings", json={"good_import_enabled": on}).status_code == 200


def upload(client, content=SAMPLE, name="good.json"):
    return client.post("/api/good/import", files={"file": (name, content, "application/json")})


def mats(client) -> dict[int, dict]:
    body = client.get("/api/inventory").json()
    return {m["id"]: m for c in body["categories"] for m in c["materials"]}


def test_import_requires_the_toggle(paths):
    setup(paths)
    with make_client(paths) as client:
        r = upload(client)
        assert r.status_code == 409 and "Settings" in r.json()["detail"]
        assert client.get("/api/good/status").json() == {"enabled": False, "imported_at": None, "source": None,
                                                        "counts": None, "unmatched": []}


def test_import_and_status(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        r = upload(client)
        assert r.status_code == 200
        body = r.json()
        assert body["source"] == "Test_Scanner"
        assert body["counts"]["materials"] == {"matched": 4, "ignored": 1, "unmatched": 1}
        assert "weapon:UnknownBlade" in body["unmatched"]
        status = client.get("/api/good/status").json()
        assert status["enabled"] is True and status["imported_at"] == body["imported_at"]


def test_bad_files_change_nothing(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        upload(client)
        before = client.get("/api/good/status").json()
        r = upload(client, b'{"format": "GOOD", "version": 9}')
        assert r.status_code == 400 and r.json()["detail"] == "Unsupported GOOD version 9"
        assert upload(client, b"not json").status_code == 400
        assert client.get("/api/good/status").json() == before


def test_size_limit(paths, monkeypatch):
    import app.api.good as good_api
    monkeypatch.setattr(good_api, "GOOD_UPLOAD_MAX_BYTES", 100)
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        assert upload(client, b" " * 101).status_code == 413


def test_empty_catalogue_is_409(paths):
    setup(paths, catalogue=False)
    with make_client(paths) as client:
        enable(client)
        r = upload(client)
        assert r.status_code == 409 and r.json()["detail"] == "Refresh game data first"


def test_inventory_scan_fields(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        before = mats(client)
        assert before[104302]["scan"] is None and client.get("/api/inventory").json()["good"] is None
        upload(client)
        body = client.get("/api/inventory").json()
        assert body["good"]["source"] == "Test_Scanner"
        after = mats(client)
        assert after[104302]["scan"] == 12 and after[100055]["scan"] == 0   # absent from the file = 0
        assert after[202]["scan"] == 1234567


def test_inventory_to_farm_unchanged_by_import(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        before = mats(client)
        upload(client)
        after = mats(client)
        for mid, m in before.items():
            for k in ("state", "need", "short", "have", "craftable", "to_farm"):
                assert after[mid][k] == m[k], (mid, k)


def test_weapons_and_artifacts_lists(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        assert client.get("/api/good/weapons").status_code == 404
        upload(client)
        ws = client.get("/api/good/weapons").json()
        assert [w["name"] for w in ws] == ["Mistsplitter Reforged", "Favonius Sword", "Favonius Sword"]
        assert ws[1]["level"] == 90 and ws[1]["holder"]["slug"] == "bennett"
        assert ws[0]["holder"] is None and ws[0]["location"] is None
        arts = client.get("/api/good/artifacts").json()
        assert [(a["set_name"], a["slot"]) for a in arts] == [
            ("Gladiator's Finale", "flower"), ("Noblesse Oblige", "goblet"), ("Noblesse Oblige", "sands")]
        assert arts[0]["icon"] == "UI_RelicIcon_15001_4" and arts[1]["icon"] == "UI_RelicIcon_15007_1"
        assert arts[0]["holder"]["slug"] == "traveler"
        assert arts[2]["holder"] is None and arts[2]["location"] == "SomeNewCharacter"


def test_weapon_picker_marks_owned_first(paths):
    setup(paths)
    with make_client(paths) as client:
        assert all(w["owned"] is None for w in client.get("/api/weapons?type=Sword").json())
        enable(client)
        upload(client)
        ws = client.get("/api/weapons?type=Sword").json()
        assert [w["name"] for w in ws] == ["Mistsplitter Reforged", "Favonius Sword", "Cool Steel"]
        assert ws[1]["owned"] == {"count": 2, "best_level": 90, "best_refinement": 3}
        assert ws[2]["owned"] is None


def test_toggle_off_hides_and_on_restores(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        upload(client)
        enable(client, False)
        assert mats(client)[104302]["scan"] is None
        assert client.get("/api/inventory").json()["good"] is None
        assert client.get("/api/good/weapons").status_code == 404
        assert client.get("/api/good/artifacts").status_code == 404
        assert all(w["owned"] is None for w in client.get("/api/weapons?type=Sword").json())
        assert client.get("/api/good/status").json()["imported_at"] is not None   # kept for Settings
        assert client.get("/api/settings").json()["good_import_enabled"] is False
        enable(client)
        assert mats(client)[104302]["scan"] == 12


def test_delete(paths):
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        upload(client)
        enable(client, False)
        assert client.delete("/api/good").status_code == 204     # allowed while disabled
        enable(client)
        assert client.get("/api/good/status").json()["imported_at"] is None
        assert mats(client)[104302]["scan"] is None


def test_file_contents_never_logged(paths, caplog):
    import logging
    caplog.set_level(logging.DEBUG)
    setup(paths)
    with make_client(paths) as client:
        enable(client)
        upload(client)
    assert "1234567" not in caplog.text and "Test_Scanner" not in caplog.text
```

In `backend/tests/test_api_settings.py` `test_no_endpoint_leaks_cookie_values`, extend the `bodies += [client.get(p).text for p in (...)]` tuple with `"/api/good/status"`, and add `client.put("/api/settings", json={"good_import_enabled": True}).text` to the earlier `bodies` list.

- [ ] **Step 2: Run them and verify they fail**

Run: `PY -m pytest -q tests/test_api_good.py`
Expected: FAIL (404 on `/api/good/import`, missing `scan`).

- [ ] **Step 3: Config and setting**

`backend/app/config.py`, next to `WISH_UPLOAD_MAX_BYTES`:

```python
GOOD_UPLOAD_MAX_BYTES = 20 * 1024 * 1024
```

`backend/app/api/settings.py`: add `good_import_enabled: bool | None = None` to `SettingsIn`; in `put_settings` add

```python
        if body.good_import_enabled is not None:
            set_setting(s, "good_import_enabled", body.good_import_enabled)
```

and in `settings_payload` add `"good_import_enabled": bool(get_setting(s, "good_import_enabled")),`.

- [ ] **Step 4: Implement** `backend/app/api/good.py`:

```python
"""GOOD (scanner export) import. Opt-in via the good_import_enabled setting; the file is parsed in memory only."""
import re

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import GOOD_UPLOAD_MAX_BYTES
from app.context import AppContext, get_ctx
from app.db.models import GameArtifactSet, GameCharacter, GameMaterial, GameWeapon, GoodArtifactRow, GoodImport, GoodWeaponRow
from app.good.keys import KeyIndex
from app.good.parse import SLOTS, GoodFormatError, parse_good
from app.good.store import delete_snapshot, good_active, good_enabled, import_summary, replace_snapshot
from app.timeutil import utcnow

router = APIRouter()
NOT_ENABLED = "Turn on GOOD inventory import in Settings first."
SLOT_ICON = {"flower": 4, "plume": 2, "sands": 5, "goblet": 1, "circlet": 3}


def holders(session: Session, ids: set[int]) -> dict[int, dict]:
    if not ids:
        return {}
    rows = session.scalars(select(GameCharacter).where(GameCharacter.id.in_(ids)))
    return {c.id: {"id": c.id, "name": c.name, "slug": c.slug, "icon": c.icon} for c in rows}


def _require_active(session: Session) -> None:
    if good_active(session) is None:
        raise HTTPException(404, "No GOOD import")


@router.get("/good/status")
def status(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        row = s.get(GoodImport, 1)
        base = {"enabled": good_enabled(s), "imported_at": None, "source": None, "counts": None, "unmatched": []}
        return base | ({k: v for k, v in import_summary(row).to_dict().items()} if row else {})


@router.post("/good/import")
async def import_good(file: UploadFile, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        if not good_enabled(s):
            raise HTTPException(409, NOT_ENABLED)
    content = await file.read(GOOD_UPLOAD_MAX_BYTES + 1)
    if len(content) > GOOD_UPLOAD_MAX_BYTES:
        raise HTTPException(413, "The file is larger than 20 MB.")
    try:
        parsed = parse_good(content)
    except GoodFormatError as e:
        raise HTTPException(400, str(e)) from None
    finally:
        del content
    with ctx.session_factory.begin() as s:
        if not s.scalar(select(func.count()).select_from(GameMaterial)):
            raise HTTPException(409, "Refresh game data first")
        return replace_snapshot(s, parsed, KeyIndex.build(s), utcnow()).to_dict()


@router.delete("/good", status_code=204)
def delete_good(ctx: AppContext = Depends(get_ctx)) -> Response:
    with ctx.session_factory.begin() as s:
        delete_snapshot(s)
    return Response(status_code=204)


@router.get("/good/weapons")
def good_weapons(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        _require_active(s)
        rows = s.execute(select(GoodWeaponRow, GameWeapon).join(GameWeapon, GameWeapon.id == GoodWeaponRow.weapon_id)).all()
        who = holders(s, {w.character_id for w, _ in rows if w.character_id})
        out = [{"id": w.id, "weapon_id": w.weapon_id, "name": g.name, "icon": g.icon, "rarity": g.rarity,
                "weapon_type": g.weapon_type, "level": w.level, "ascension": w.ascension,
                "refinement": w.refinement, "lock": w.lock, "location": w.location,
                "holder": who.get(w.character_id)} for w, g in rows]
        return sorted(out, key=lambda x: (-x["rarity"], x["name"], -x["level"], x["id"]))


@router.get("/good/artifacts")
def good_artifacts(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        _require_active(s)
        rows = s.execute(select(GoodArtifactRow, GameArtifactSet)
                         .join(GameArtifactSet, GameArtifactSet.id == GoodArtifactRow.set_id)).all()
        who = holders(s, {a.character_id for a, _ in rows if a.character_id})
        out = [{"id": a.id, "set_id": a.set_id, "set_name": g.name,
                "icon": re.sub(r"_\d+$", f"_{SLOT_ICON[a.slot]}", g.icon), "slot": a.slot, "rarity": a.rarity,
                "level": a.level, "main_stat": a.main_stat, "substats": a.substats, "lock": a.lock,
                "location": a.location, "holder": who.get(a.character_id)} for a, g in rows]
        return sorted(out, key=lambda x: (-x["rarity"], x["set_name"], SLOTS.index(x["slot"]), -x["level"], x["id"]))
```

Register it in `backend/app/api/__init__.py`: add `good` to the import list and `good.router` to `ROUTERS` (before `img.router`).

- [ ] **Step 5: Inventory and weapon-picker additions** in `backend/app/api/planner.py`:

```python
from app.good.store import good_active, owned_weapons, scan_counts
from app.timeutil import iso, utcnow
```

```python
@router.get("/inventory")
def get_inventory(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        data, index = planner_view(s)
        categories = inventory(data, index)
        active = good_active(s)
        counts = scan_counts(s) if active is not None else None
        for c in categories:
            for m in c["materials"]:
                m["scan"] = counts.get(m["id"], 0) if counts is not None else None
        good = {"imported_at": iso(active.imported_at), "source": active.source} if active is not None else None
        return {"gaps": gaps_for(ctx, s), "categories": categories, "good": good}


@router.get("/weapons")
def list_weapons(type: str | None = None, ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        q = select(GameWeapon).order_by(GameWeapon.rarity.desc(), GameWeapon.name)
        if type:
            q = q.where(GameWeapon.weapon_type == type)
        owned = owned_weapons(s) if good_active(s) is not None else {}
        out = [{"id": w.id, "name": w.name, "icon": w.icon, "rarity": w.rarity, "weapon_type": w.weapon_type,
                "owned": owned.get(w.id)} for w in s.scalars(q)]
        return sorted(out, key=lambda w: w["owned"] is None)      # stable: owned first, order kept within
```

(`material_index` builds fresh dicts each request, so adding `scan` here doesn't leak into the dashboard.)

- [ ] **Step 6: Run the whole backend suite**

Run: `PY -m pytest -q`
Expected: all PASS. If an existing test compares the full `/api/inventory` body or a `/api/weapons` item for equality, add the new keys (`good`, `scan`, `owned`) to its expectation.

- [ ] **Step 7: Commit**

```bash
git add backend
git commit -m "feat(good): GOOD import API, inventory scan counts and owned weapons"
```

---

### Task 5: Live check against the user's real file (read-only, nothing committed from it)

**Files:**
- Create: `backend/app/good/check.py`
- Test: `backend/tests/test_good_store.py` (one CLI test)

**Interfaces:**
- Consumes: `parse_good`, `KeyIndex`, `match_file`, `refresh_all`, `default_paths` from `app.config`.
- Produces: `python -m app.good.check --db PATH [--refresh] FILE`, which prints the match counts and unmatched keys only. Exit code 0 on success, 2 on a format error.

- [ ] **Step 1: Write the failing test** (append to `backend/tests/test_good_store.py`):

```python
def test_check_cli_prints_only_the_summary(session_factory, paths, capsys):
    from app.good.check import main
    seed_catalogue(session_factory)
    assert main(["--db", str(paths.db_file), str(FIXTURES / "good_sample.json")]) == 0
    out = capsys.readouterr().out
    assert "materials: 4 matched, 1 ignored, 1 unmatched" in out
    assert "weapon:UnknownBlade" in out
    assert "1234567" not in out and "Test_Scanner" not in out
```

- [ ] **Step 2: Run it and verify it fails**

Run: `PY -m pytest -q tests/test_good_store.py::test_check_cli_prints_only_the_summary`
Expected: FAIL (`ModuleNotFoundError: app.good.check`).

- [ ] **Step 3: Implement** `backend/app/good/check.py`:

```python
"""Check how a real GOOD export matches the game data, printing only counts and unmatched keys.

    python -m app.good.check --db COPY_OF_DB.sqlite [--refresh] FILE

Point --db at a COPY of the database: --refresh downloads public game data from Yatta into it.
Nothing from the file except unmatched key names is printed; nothing is written to the database's GOOD tables.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import httpx

from app.db.engine import make_engine, make_session_factory, migrate
from app.good.keys import KeyIndex
from app.good.parse import GoodFormatError, parse_good
from app.good.store import match_file


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.good.check")
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--refresh", action="store_true", help="download game data into the (copied) database first")
    ap.add_argument("file", type=Path)
    args = ap.parse_args(argv)
    engine = make_engine(args.db)
    migrate(engine)
    sf = make_session_factory(engine)
    try:
        if args.refresh:
            from app.gamedata.service import refresh_all

            async def go():
                async with httpx.AsyncClient() as http:
                    await refresh_all(sf, http, force=True)
            asyncio.run(go())
        try:
            parsed = parse_good(args.file.read_bytes())
        except GoodFormatError as e:
            print(f"error: {e}")
            return 2
        with sf() as s:
            result = match_file(parsed, KeyIndex.build(s))
        c = result.counts
        print(f"materials: {c['materials']['matched']} matched, {c['materials']['ignored']} ignored, "
              f"{c['materials']['unmatched']} unmatched")
        print(f"weapons: {c['weapons']['matched']} matched, {c['weapons']['unmatched']} unmatched")
        print(f"artifacts: {c['artifacts']['matched']} matched, {c['artifacts']['unmatched']} unmatched")
        for key in result.unmatched:
            print(f"  unmatched {key}")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run the test and verify it passes**

Run: `PY -m pytest -q tests/test_good_store.py`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/app/good/check.py backend/tests/test_good_store.py
git commit -m "feat(good): summary-only check command for a real GOOD export"
```

- [ ] **Step 6: Live check (controller, with the user)**

Ask the user for the path to a real GOOD export from their scanner (Inventory Kamera, Irminsul or another). If they have none, record "live check skipped: no export" in the ledger and move on.

Otherwise, copy the real database to the scratchpad (find it via `PY -c "from app.config import default_paths; print(default_paths().db_file)"` from `backend/`), then run:

```
PY -m app.good.check --db <scratchpad copy> --refresh "<user's file>"
```

Report only the printed summary to the user. Expect `unmatched` to be small. A pattern of unmatched keys (e.g. a whole naming style) means `good_key` needs a rule: add a parametrized case in `test_good_keys.py`, fix `good_key`, commit, and re-run. Delete the scratchpad copy afterwards. Never copy the user's file into the repo.

---

### Task 6: Frontend types, API client and pure helpers

**Files:**
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/lib/materials.ts`, `frontend/src/lib/materials.test.ts`
- Create: `frontend/src/lib/good.ts`, `frontend/src/lib/good.test.ts`

**Interfaces:**
- Consumes: the HTTP shapes from Task 4.
- Produces:
  - Types: `GoodRef`, `GoodCounts`, `GoodSummary`, `GoodStatus`, `GoodWeapon`, `GoodArtifact`, `ArtifactSlot`, `OwnedWeapon`; `Material.scan?: number | null`; `Inventory.good: GoodRef | null`; `WeaponOption.owned?: OwnedWeapon | null`; `Settings.good_import_enabled: boolean`; `Settings.gamedata.artifact_sets`.
  - `api.goodStatus()`, `api.importGood(file)`, `api.deleteGood()`, `api.goodWeapons()`, `api.goodArtifacts()`; `api.saveSettings` accepts `good_import_enabled`.
  - `materials.ts`: `InventoryFilter` gains `'owned'`; `tileView` applies spec §5.1; new `tileDim(m: Material): boolean`.
  - `good.ts`: `SLOTS`, `SLOT_NAMES`, `STAT_NAMES`, `statName(key)`, `statValue(key, value)`, `holderLabel(item)`, `isUnequipped(item)`, `WeaponFilter`, `filterWeapons(ws, f)`, `ArtifactFilter`, `DEFAULT_ARTIFACT_FILTER`, `filterArtifacts(as, f)`, `importSummaryText(s)`, `scanAgeNote(importedAt, now)`, `ownedLabel(o)`, `ARTIFACT_PAGE = 100`.

- [ ] **Step 1: Write the failing tests**

Append to `frontend/src/lib/materials.test.ts` (reuse that file's existing material factory if it has one, otherwise add this `mat` helper):

```ts
import { filterMaterials, tileDim, tileView } from './materials';
import type { Material } from './types';

const mat = (over: Partial<Material>): Material => ({
	id: 1, name: 'X', icon: 'UI_X', rarity: 3, category: 'talent', state: 'unneeded', need: 0, short: 0,
	have: null, craftable: 0, to_farm: 0, sources: [], characters: [], ...over
});

describe('tileView with a GOOD scan', () => {
	it('short keeps the live count even when the scan disagrees', () => {
		const m = mat({ state: 'short', need: 15, short: 7, have: 8, to_farm: 7, scan: 2 });
		expect(tileView(m).main).toBe('8/15');
		expect(tileView(m).badge).toBe('−7');
	});
	it('met shows the scan when it agrees, else ✓ need', () => {
		expect(tileView(mat({ state: 'met', need: 20, scan: 120 })).main).toBe('120/20 ✓');
		expect(tileView(mat({ state: 'met', need: 20, scan: 5 })).main).toBe('✓ 20');
		expect(tileView(mat({ state: 'met', need: 20 })).main).toBe('✓ 20');
	});
	it('unneeded shows the scan and is only dimmed at zero or without a scan', () => {
		expect(tileView(mat({ scan: 37 })).main).toBe('37');
		expect(tileDim(mat({ scan: 37 }))).toBe(false);
		expect(tileView(mat({ scan: 0 })).main).toBe('0');
		expect(tileDim(mat({ scan: 0 }))).toBe(true);
		expect(tileView(mat({ scan: null })).main).toBe('');
		expect(tileDim(mat({}))).toBe(true);
		expect(tileDim(mat({ state: 'met', need: 2 }))).toBe(false);
	});
	it('owned filter keeps scan > 0 only', () => {
		const ms = [mat({ id: 1, scan: 3 }), mat({ id: 2, scan: 0 }), mat({ id: 3 })];
		expect(filterMaterials(ms, 'owned', '').map((m) => m.id)).toEqual([1]);
	});
});
```

`frontend/src/lib/good.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import {
	DEFAULT_ARTIFACT_FILTER, filterArtifacts, filterWeapons, holderLabel, importSummaryText, isUnequipped,
	ownedLabel, scanAgeNote, statName, statValue
} from './good';
import type { GoodArtifact, GoodSummary, GoodWeapon } from './types';

const bennett = { id: 10000032, name: 'Bennett', slug: 'bennett', icon: 'UI_AvatarIcon_Bennett' };
const weapon = (over: Partial<GoodWeapon>): GoodWeapon => ({
	id: 1, weapon_id: 11401, name: 'Favonius Sword', icon: 'UI_W', rarity: 4, weapon_type: 'Sword', level: 90,
	ascension: 6, refinement: 3, lock: false, location: null, holder: null, ...over
});
const artifact = (over: Partial<GoodArtifact>): GoodArtifact => ({
	id: 1, set_id: 15007, set_name: 'Noblesse Oblige', icon: 'UI_R', slot: 'flower', rarity: 5, level: 20,
	main_stat: 'hp', substats: [], lock: false, location: null, holder: null, ...over
});

describe('stats', () => {
	it('names and formats GOOD stat keys', () => {
		expect(statName('critRate_')).toBe('CRIT Rate');
		expect(statName('hydro_dmg_')).toBe('Hydro DMG Bonus');
		expect(statName('mystery')).toBe('mystery');
		expect(statValue('critRate_', 3.9)).toBe('3.9%');
		expect(statValue('atk', 18.0)).toBe('18');
		expect(statValue('eleMas', 23)).toBe('23');
	});
});

describe('holders', () => {
	it('distinguishes unequipped from an unknown holder', () => {
		expect(holderLabel(weapon({ holder: bennett, location: 'Bennett' }))).toBe('Bennett');
		expect(holderLabel(weapon({ location: 'SomeNewCharacter' }))).toBe('Equipped');
		expect(holderLabel(weapon({}))).toBe('Unequipped');
		expect(isUnequipped(weapon({ location: 'SomeNewCharacter' }))).toBe(false);
		expect(isUnequipped(weapon({}))).toBe(true);
	});
});

describe('filters', () => {
	const ws = [weapon({ id: 1, holder: bennett, location: 'Bennett' }),
		weapon({ id: 2, name: 'Mistsplitter Reforged', rarity: 5 }),
		weapon({ id: 3, name: 'Slingshot', weapon_type: 'Bow', rarity: 3 })];
	it('filters weapons by type, rarity, unequipped and name', () => {
		const base = { type: '', rarity: 0, unequippedOnly: false, query: '' };
		expect(filterWeapons(ws, { ...base, type: 'Sword' }).map((w) => w.id)).toEqual([1, 2]);
		expect(filterWeapons(ws, { ...base, rarity: 5 }).map((w) => w.id)).toEqual([2]);
		expect(filterWeapons(ws, { ...base, unequippedOnly: true }).map((w) => w.id)).toEqual([2, 3]);
		expect(filterWeapons(ws, { ...base, query: 'mist' }).map((w) => w.id)).toEqual([2]);
	});
	const as = [artifact({ id: 1 }), artifact({ id: 2, slot: 'goblet', main_stat: 'hydro_dmg_' }),
		artifact({ id: 3, rarity: 3, set_id: 15001 }), artifact({ id: 4, location: 'X' })];
	it('filters artifacts; default hides below 4★', () => {
		expect(filterArtifacts(as, DEFAULT_ARTIFACT_FILTER).map((a) => a.id)).toEqual([1, 2, 4]);
		expect(filterArtifacts(as, { ...DEFAULT_ARTIFACT_FILTER, slot: 'goblet' }).map((a) => a.id)).toEqual([2]);
		expect(filterArtifacts(as, { ...DEFAULT_ARTIFACT_FILTER, mainStat: 'hp' }).map((a) => a.id)).toEqual([1, 4]);
		expect(filterArtifacts(as, { ...DEFAULT_ARTIFACT_FILTER, unequippedOnly: true }).map((a) => a.id)).toEqual([1, 2]);
		expect(filterArtifacts(as, { ...DEFAULT_ARTIFACT_FILTER, minRarity: 1, setId: 15001 }).map((a) => a.id)).toEqual([3]);
	});
});

describe('labels', () => {
	const summary = (over: Partial<GoodSummary['counts']['materials']>, wUnmatched = 1): GoodSummary => ({
		imported_at: '2026-11-22T12:00:00Z', source: 'X',
		counts: { materials: { matched: 412, ignored: 90, unmatched: 2, ...over },
			weapons: { matched: 318, unmatched: wUnmatched }, artifacts: { matched: 1804, unmatched: 0 } },
		unmatched: []
	});
	it('summarises an import', () => {
		expect(importSummaryText(summary({}))).toBe('Imported 412 materials, 318 weapons, 1804 artifacts. 3 keys not recognised.');
		expect(importSummaryText(summary({ unmatched: 0 }, 0))).toBe('Imported 412 materials, 318 weapons, 1804 artifacts.');
		expect(importSummaryText(summary({ unmatched: 11 }))).toContain('Try Refresh game data in Settings.');
	});
	it('warns about old scans only after 30 days', () => {
		const now = Date.parse('2026-11-22T12:00:00Z');
		expect(scanAgeNote('2026-11-01T12:00:00Z', now)).toBeNull();
		expect(scanAgeNote('2026-10-01T12:00:00Z', now)).toBe('scan is 52 days old');
	});
	it('labels owned weapons', () => {
		expect(ownedLabel({ count: 2, best_level: 90, best_refinement: 3 })).toBe('owned · Lv 90 · R3');
	});
});
```

- [ ] **Step 2: Run and verify they fail**

Run (in `frontend/`): `npx vitest run src/lib/good.test.ts src/lib/materials.test.ts`
Expected: FAIL (`good.ts` missing; `tileDim` not exported).

- [ ] **Step 3: Types** in `frontend/src/lib/types.ts`:

- In `Material`, add `scan?: number | null;`.
- Change `Inventory` to `{ gaps: GapStatus; categories: InventoryCategory[]; good: GoodRef | null }`.
- Add `owned?: OwnedWeapon | null` to `WeaponOption`.
- Add `good_import_enabled: boolean;` to `Settings`, and `artifact_sets: { fetched_at: string | null; last_error: string | null; count: number };` inside `Settings.gamedata`.
- Append:

```ts
export interface GoodRef { imported_at: string; source: string | null }
export interface GoodCounts {
	materials: { matched: number; ignored: number; unmatched: number };
	weapons: { matched: number; unmatched: number };
	artifacts: { matched: number; unmatched: number };
}
export interface GoodSummary { imported_at: string; source: string | null; counts: GoodCounts; unmatched: string[] }
export interface GoodStatus { enabled: boolean; imported_at: string | null; source: string | null; counts: GoodCounts | null; unmatched: string[] }
export interface OwnedWeapon { count: number; best_level: number; best_refinement: number }
export interface GoodWeapon {
	id: number; weapon_id: number; name: string; icon: string; rarity: number; weapon_type: string; level: number;
	ascension: number; refinement: number; lock: boolean; location: string | null; holder: CharRef | null;
}
export type ArtifactSlot = 'flower' | 'plume' | 'sands' | 'goblet' | 'circlet';
export interface GoodArtifact {
	id: number; set_id: number; set_name: string; icon: string; slot: ArtifactSlot; rarity: number; level: number;
	main_stat: string; substats: { key: string; value: number }[]; lock: boolean; location: string | null;
	holder: CharRef | null;
}
```

- [ ] **Step 4: API client** in `frontend/src/lib/api.ts`:

- At the top of `parse`, after the `!res.ok` block: `if (res.status === 204) return undefined as T;`
- Import the new types, and add to `api`:

```ts
	goodStatus: () => request<GoodStatus>('GET', '/good/status'),
	importGood: (file: File) => upload<GoodSummary>('/good/import', file),
	deleteGood: () => request<void>('DELETE', '/good'),
	goodWeapons: () => request<GoodWeapon[]>('GET', '/good/weapons'),
	goodArtifacts: () => request<GoodArtifact[]>('GET', '/good/artifacts'),
```

- Widen the `saveSettings` body type with `good_import_enabled?: boolean`.

- [ ] **Step 5: `materials.ts`**: change the filter type, the tile rules and the filter:

```ts
export type InventoryFilter = 'all' | 'needed' | 'farm' | 'owned';

export function tileView(m: Material): TileView {
	if (m.state === 'short') {
		return {
			main: `${m.have ?? 0}/${m.need}`,
			badge: m.to_farm > 0 ? `−${m.to_farm}` : null,
			hint: m.craftable > 0 ? `craft ${m.craftable}` : null,
			tone: 'short'
		};
	}
	if (m.state === 'met') {
		const main = m.scan != null && m.scan >= m.need ? `${m.scan}/${m.need} ✓` : `✓ ${m.need}`;
		return { main, badge: null, hint: null, tone: 'met' };
	}
	return { main: m.scan != null ? String(m.scan) : '', badge: null, hint: null, tone: 'none' };
}

/** Unneeded tiles are dimmed unless a GOOD scan says you own some. */
export function tileDim(m: Material): boolean {
	return m.state === 'unneeded' && !((m.scan ?? 0) > 0);
}
```

In `filterMaterials`, replace the `passes` line with:

```ts
		const passes =
			filter === 'all' ? true
			: filter === 'needed' ? m.state !== 'unneeded'
			: filter === 'owned' ? (m.scan ?? 0) > 0
			: m.to_farm > 0;
```

- [ ] **Step 6: `good.ts`**:

```ts
import type { ArtifactSlot, CharRef, GoodArtifact, GoodSummary, GoodWeapon, OwnedWeapon } from './types';

export const ARTIFACT_PAGE = 100;
export const SLOTS: ArtifactSlot[] = ['flower', 'plume', 'sands', 'goblet', 'circlet'];
export const SLOT_NAMES: Record<ArtifactSlot, string> = {
	flower: 'Flower', plume: 'Plume', sands: 'Sands', goblet: 'Goblet', circlet: 'Circlet'
};
export const STAT_NAMES: Record<string, string> = {
	hp: 'HP', hp_: 'HP', atk: 'ATK', atk_: 'ATK', def: 'DEF', def_: 'DEF', eleMas: 'Elemental Mastery',
	enerRech_: 'Energy Recharge', critRate_: 'CRIT Rate', critDMG_: 'CRIT DMG', heal_: 'Healing Bonus',
	physical_dmg_: 'Physical DMG Bonus', anemo_dmg_: 'Anemo DMG Bonus', geo_dmg_: 'Geo DMG Bonus',
	electro_dmg_: 'Electro DMG Bonus', hydro_dmg_: 'Hydro DMG Bonus', pyro_dmg_: 'Pyro DMG Bonus',
	cryo_dmg_: 'Cryo DMG Bonus', dendro_dmg_: 'Dendro DMG Bonus'
};

export function statName(key: string): string {
	const base = STAT_NAMES[key] ?? key;
	return ['hp_', 'atk_', 'def_'].includes(key) ? `${base}%` : base;
}

export function statValue(key: string, value: number): string {
	return key.endsWith('_') ? `${Math.round(value * 10) / 10}%` : `${Math.round(value)}`;
}

type Held = { holder: CharRef | null; location: string | null };
export function isUnequipped(item: Held): boolean {
	return !item.holder && !item.location;
}
export function holderLabel(item: Held): string {
	return item.holder?.name ?? (item.location ? 'Equipped' : 'Unequipped');
}

export interface WeaponFilter { type: string; rarity: number; unequippedOnly: boolean; query: string }
export function filterWeapons(ws: GoodWeapon[], f: WeaponFilter): GoodWeapon[] {
	const q = f.query.trim().toLowerCase();
	return ws.filter((w) =>
		(!f.type || w.weapon_type === f.type) && (!f.rarity || w.rarity === f.rarity) &&
		(!f.unequippedOnly || isUnequipped(w)) && (!q || w.name.toLowerCase().includes(q)));
}

export interface ArtifactFilter { setId: number; slot: ArtifactSlot | ''; mainStat: string; unequippedOnly: boolean; minRarity: number }
export const DEFAULT_ARTIFACT_FILTER: ArtifactFilter = { setId: 0, slot: '', mainStat: '', unequippedOnly: false, minRarity: 4 };
export function filterArtifacts(as: GoodArtifact[], f: ArtifactFilter): GoodArtifact[] {
	return as.filter((a) =>
		(!f.setId || a.set_id === f.setId) && (!f.slot || a.slot === f.slot) &&
		(!f.mainStat || a.main_stat === f.mainStat) && (!f.unequippedOnly || isUnequipped(a)) &&
		a.rarity >= f.minRarity);
}

export function importSummaryText(s: GoodSummary): string {
	const c = s.counts;
	const unknown = c.materials.unmatched + c.weapons.unmatched + c.artifacts.unmatched;
	let text = `Imported ${c.materials.matched} materials, ${c.weapons.matched} weapons, ${c.artifacts.matched} artifacts.`;
	if (unknown > 0) text += ` ${unknown} ${unknown === 1 ? 'key' : 'keys'} not recognised.`;
	if (c.materials.unmatched + c.weapons.unmatched > 10) text += ' Try Refresh game data in Settings.';
	return text;
}

const DAY = 86_400_000;
export function scanAgeNote(importedAt: string, now: number): string | null {
	const days = Math.floor((now - Date.parse(importedAt)) / DAY);
	return days > 30 ? `scan is ${days} days old` : null;
}

export function ownedLabel(o: OwnedWeapon): string {
	return `owned · Lv ${o.best_level} · R${o.best_refinement}`;
}
```

- [ ] **Step 7: Run vitest and svelte-check**

Run: `npx vitest run` then `npm run check`
Expected: all PASS, 0 errors. `npm run check` may flag existing callers that build an `Inventory` object without `good` (test fixtures): add `good: null` there.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib
git commit -m "feat(good): frontend types, API client, tile rules and list helpers"
```

---

### Task 7: Settings section, import button, Inventory header, tabs and Materials tab

**Files:**
- Create: `frontend/src/lib/GoodImportButton.svelte`
- Modify: `frontend/src/routes/settings/+page.svelte`, `frontend/src/routes/inventory/+page.svelte`, `frontend/src/lib/MaterialPopover.svelte`

**Interfaces:**
- Consumes: `api.goodStatus/importGood/deleteGood/saveSettings`, `tileView`, `tileDim`, `importSummaryText`, `scanAgeNote` (Task 6).
- Produces: `<GoodImportButton onimported={(s: GoodSummary) => void} />`, which renders a hidden `<input type="file" accept=".json,application/json" data-testid="good-file-input">`, a visible "Import GOOD file" button, and a status line `data-testid="good-toast"`. Inventory tabs are `role="tab"` buttons named "Materials", "Weapons" and "Artifacts". The Settings section has `data-testid="good-settings"` and a checkbox labelled "Use GOOD inventory import". Task 8 renders `<WeaponsTab version={...} />` and `<ArtifactsTab version={...} />` into the Inventory tab panel. In this task, put placeholder `{#if tab === 'weapons'}…{/if}` branches that Task 8 fills; until then they render nothing.

- [ ] **Step 1: `GoodImportButton.svelte`**

```svelte
<script lang="ts">
	import { api, errorMessage } from './api';
	import { importSummaryText } from './good';
	import type { GoodSummary } from './types';

	let { onimported }: { onimported?: (s: GoodSummary) => void } = $props();
	let input: HTMLInputElement;
	let busy = $state(false);
	let message = $state<string | null>(null);
	let failed = $state(false);

	async function pick(e: Event & { currentTarget: HTMLInputElement }) {
		const file = e.currentTarget.files?.[0];
		e.currentTarget.value = '';
		if (!file) return;
		busy = true;
		try {
			const s = await api.importGood(file);
			message = importSummaryText(s);
			failed = false;
			onimported?.(s);
		} catch (err) {
			message = errorMessage(err);
			failed = true;
		} finally {
			busy = false;
		}
	}
</script>

<input bind:this={input} type="file" accept=".json,application/json" hidden data-testid="good-file-input" onchange={pick} />
<button type="button" onclick={() => input.click()} disabled={busy}>{busy ? 'Importing…' : 'Import GOOD file'}</button>
{#if message}<span class:error={failed} class:muted={!failed} data-testid="good-toast" role="status">{message}</span>{/if}
```

- [ ] **Step 2: Settings section.** In `frontend/src/routes/settings/+page.svelte`, add state and loaders beside the existing ones (follow the file's pattern for `load`/errors):

```ts
	import GoodImportButton from '$lib/GoodImportButton.svelte';
	import type { GoodStatus } from '$lib/types';
	let good = $state<GoodStatus | null>(null);
	let goodNote = $state<string | null>(null);

	async function loadGood() {
		try { good = await api.goodStatus(); } catch (e) { goodNote = errorMessage(e); }
	}
	async function setGoodEnabled(on: boolean) {
		try {
			settings = await api.saveSettings({ good_import_enabled: on });
			await loadGood();
		} catch (e) { goodNote = errorMessage(e); }
	}
	async function deleteGood() {
		if (!confirm('Delete the imported GOOD data? This cannot be undone.')) return;
		try { await api.deleteGood(); await loadGood(); goodNote = 'Imported data deleted.'; }
		catch (e) { goodNote = errorMessage(e); }
	}
```

Call `loadGood()` wherever the page first loads `settings`. Insert this section after the "Default build targets" section:

```svelte
	<section class="panel" data-testid="good-settings">
		<h2>Inventory import (GOOD)</h2>
		<label class="inline">
			<input type="checkbox" checked={settings.good_import_enabled}
				onchange={(e) => setGoodEnabled(e.currentTarget.checked)} />
			Use GOOD inventory import
		</label>
		<p class="muted">The import only reads a file. The scanner that creates it is third-party software, which HoYoverse's terms forbid; use at your own risk.</p>
		{#if good?.imported_at}
			<p>Last import: {new Date(good.imported_at).toLocaleString()}{good.source ? ` from ${good.source}` : ''}
				· {good.counts?.materials.matched ?? 0} materials, {good.counts?.weapons.matched ?? 0} weapons,
				{good.counts?.artifacts.matched ?? 0} artifacts</p>
			{#if good.unmatched.length}<p class="muted">Not recognised: {good.unmatched.join(', ')}</p>{/if}
		{:else}
			<p class="muted">No import yet.</p>
		{/if}
		{#if settings.good_import_enabled}<GoodImportButton onimported={loadGood} />{/if}
		<button type="button" onclick={deleteGood} disabled={!good?.imported_at}>Delete imported data</button>
		{#if goodNote}<span class="muted">{goodNote}</span>{/if}
	</section>
```

In the "Game data" section, add a line after the banners line:

```svelte
		<p>
			{settings.gamedata.artifact_sets.count} artifact sets ·
			{settings.gamedata.artifact_sets.fetched_at ? `updated ${timeAgo(settings.gamedata.artifact_sets.fetched_at, now)}` : 'never downloaded'}
		</p>
		{#if settings.gamedata.artifact_sets.last_error}<p class="error">Artifact sets: {settings.gamedata.artifact_sets.last_error}</p>{/if}
```

- [ ] **Step 3: Inventory page.** In `frontend/src/routes/inventory/+page.svelte`:

1. Imports: add `tileDim` from `$lib/materials`; `scanAgeNote` from `$lib/good`; `timeAgo` from `$lib/time`; `GoodImportButton`; and `api.settings` to learn whether the toggle is on.
2. Filters: make `FILTERS` derived so **Owned** appears only with `data?.good`:

```ts
	const BASE_FILTERS: { key: InventoryFilter; label: string }[] = [
		{ key: 'all', label: 'All' }, { key: 'needed', label: 'Needed' }, { key: 'farm', label: 'To farm' }
	];
	const filters = $derived(data?.good ? [...BASE_FILTERS, { key: 'owned' as const, label: 'Owned' }] : BASE_FILTERS);
	const activeFilter = $derived(filter === 'owned' && !data?.good ? 'all' : filter);
```

   `readFilter` also accepts `'owned'`. `sections` uses `activeFilter`, and the chip loop iterates `filters` and compares to `activeFilter`.
3. Tabs:

```ts
	type Tab = 'materials' | 'weapons' | 'artifacts';
	const TAB_KEY = 'gt.inventory.tab';
	function readTab(): Tab {
		try { const v = localStorage.getItem(TAB_KEY); return v === 'weapons' || v === 'artifacts' ? v : 'materials'; }
		catch { return 'materials'; }
	}
	let tab = $state<Tab>(readTab());
	const activeTab = $derived<Tab>(data?.good ? tab : 'materials');
	function setTab(t: Tab) { tab = t; try { localStorage.setItem(TAB_KEY, t); } catch { /* convenience only */ } }
	let goodEnabled = $state(false);
	$effect(() => { void sync.version; api.settings().then((s) => (goodEnabled = s.good_import_enabled)).catch(() => {}); });
```

4. Markup above the filter bar:

```svelte
	<div class="bar">
		{#if data.good}
			<div role="tablist" class="chips">
				{#each [['materials', 'Materials'], ['weapons', 'Weapons'], ['artifacts', 'Artifacts']] as [key, label] (key)}
					<button type="button" role="tab" class="chip" class:on={activeTab === key}
						aria-selected={activeTab === key} onclick={() => setTab(key as Tab)}>{label}</button>
				{/each}
			</div>
		{/if}
		{#if goodEnabled}<GoodImportButton onimported={load} />{/if}
		{#if data.good}
			<span class="muted" data-testid="scan-status">Scan: {new Date(data.good.imported_at).toLocaleDateString()}
				({timeAgo(data.good.imported_at, now)}){data.good.source ? ` from ${data.good.source}` : ''}
				{#if scanAgeNote(data.good.imported_at, now)} · ⚠ {scanAgeNote(data.good.imported_at, now)}{/if}</span>
		{/if}
	</div>
```

5. Wrap the existing filter bar, notes and category sections in `{#if activeTab === 'materials'} … {/if}`, and add the empty `{:else if activeTab === 'weapons'}{:else}{/if}` branches for Task 8.
6. On the tile, replace `dim={m.state === 'unneeded'}` with `dim={tileDim(m)}`.

- [ ] **Step 4: Popover.** In `frontend/src/lib/MaterialPopover.svelte`, add an optional prop and line:

```svelte
	let { material, scannedAt = null }: { material: Material; scannedAt?: string | null } = $props();
```

```svelte
{#if material.scan != null && scannedAt}
	<div class="muted">Scanned: {material.scan} (as of {new Date(scannedAt).toLocaleDateString()})</div>
{/if}
```

Pass `scannedAt={data.good?.imported_at ?? null}` from the Inventory page.

- [ ] **Step 5: Check**

Run: `npm run check` then `npx vitest run`
Expected: 0 errors; all tests pass.

- [ ] **Step 6: Manual smoke in the browser.** Seed and start the app the way `playwright.config.ts` does:

```
cd backend; PY -m app.devseed --root ../.e2e-data; $env:GT_ROOT="../.e2e-data"; $env:GT_OFFLINE="1"; PY ../run.py
```

Turn on the toggle in Settings, import `backend/tests/fixtures/good_sample.json`, and confirm the toast and the header "Scan:" line appear. That fixture matches only a few devseed items. Stop the server afterwards.

- [ ] **Step 7: Commit**

```bash
git add frontend/src
git commit -m "feat(good): Settings opt-in, import button, Inventory scan header and tabs"
```

---

### Task 8: Weapons tab, Artifacts tab, planned-weapon owned mark

**Files:**
- Create: `frontend/src/lib/WeaponsTab.svelte`, `frontend/src/lib/ArtifactsTab.svelte`
- Modify: `frontend/src/routes/inventory/+page.svelte`, `frontend/src/routes/characters/[slug]/+page.svelte` (confirm the folder name)

**Interfaces:**
- Consumes: `api.goodWeapons/goodArtifacts`, `filterWeapons`, `filterArtifacts`, `DEFAULT_ARTIFACT_FILTER`, `holderLabel`, `isUnequipped`, `statName`, `statValue`, `SLOTS`, `SLOT_NAMES`, `ARTIFACT_PAGE`, `ownedLabel`, `imgSrc`.
- Produces: `<WeaponsTab version={string} />` and `<ArtifactsTab version={string} />`, which reload when `version` (the import time) changes. Weapon tiles carry `data-testid="weapon-card"`, artifact cards `data-testid="artifact-card"`. Filter controls have accessible names "Weapon type", "Rarity", "Unequipped only", "Search weapons", "Set", "Slot", "Main stat" and "Minimum rarity".

- [ ] **Step 1: `WeaponsTab.svelte`**

```svelte
<script lang="ts">
	import { api, errorMessage } from './api';
	import { filterWeapons, holderLabel, isUnequipped, type WeaponFilter } from './good';
	import { imgSrc } from './img';
	import type { GoodWeapon } from './types';

	let { version }: { version: string } = $props();
	let weapons = $state<GoodWeapon[]>([]);
	let error = $state<string | null>(null);
	let f = $state<WeaponFilter>({ type: '', rarity: 0, unequippedOnly: false, query: '' });

	$effect(() => {
		void version;
		api.goodWeapons().then((w) => { weapons = w; error = null; }).catch((e) => (error = errorMessage(e)));
	});
	const types = $derived([...new Set(weapons.map((w) => w.weapon_type))].sort());
	const shown = $derived(filterWeapons(weapons, f));
</script>

{#if error}<p class="error">{error}</p>{/if}
<div class="bar">
	<select aria-label="Weapon type" bind:value={f.type}>
		<option value="">All types</option>
		{#each types as t (t)}<option value={t}>{t}</option>{/each}
	</select>
	<select aria-label="Rarity" bind:value={f.rarity}>
		<option value={0}>Any rarity</option>
		{#each [5, 4, 3, 2, 1] as r (r)}<option value={r}>{r}★</option>{/each}
	</select>
	<label class="inline"><input type="checkbox" bind:checked={f.unequippedOnly} /> Unequipped only</label>
	<input type="search" placeholder="Search weapons" aria-label="Search weapons" bind:value={f.query} />
	<span class="muted">{shown.length} of {weapons.length} · holders as of scan</span>
</div>
<div class="grid">
	{#each shown as w (w.id)}
		<div class="card" data-testid="weapon-card">
			<div class="face r{w.rarity}">{#if imgSrc(w.icon)}<img src={imgSrc(w.icon)} alt="" loading="lazy" />{/if}</div>
			<div class="name">{w.name}</div>
			<div class="muted">Lv {w.level} · R{w.refinement}</div>
			<div class="holder" class:free={isUnequipped(w)}>
				{#if w.holder && imgSrc(w.holder.icon)}<img src={imgSrc(w.holder.icon)} alt="" class="avatar" />{/if}
				{holderLabel(w)}
			</div>
		</div>
	{/each}
</div>

<style>
	.bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px; }
	label.inline { display: inline-flex; gap: 6px; align-items: center; font-size: 12px; }
	.grid { display: flex; flex-wrap: wrap; gap: 10px; }
	.card { width: 96px; text-align: center; font-size: 12px; }
	.face { width: 64px; height: 64px; margin: 0 auto; border-radius: 8px; background: var(--r0); }
	.face.r1 { background: var(--r1); } .face.r2 { background: var(--r2); } .face.r3 { background: var(--r3); }
	.face.r4 { background: var(--r4); } .face.r5 { background: var(--r5); }
	.face img { width: 64px; height: 64px; display: block; }
	.name { line-height: 1.2; }
	.holder { display: flex; gap: 4px; align-items: center; justify-content: center; color: var(--muted); }
	.holder.free { color: var(--warn); }
	.avatar { width: 18px; height: 18px; border-radius: 50%; }
</style>
```

- [ ] **Step 2: `ArtifactsTab.svelte`**

```svelte
<script lang="ts">
	import { api, errorMessage } from './api';
	import {
		ARTIFACT_PAGE, DEFAULT_ARTIFACT_FILTER, SLOT_NAMES, SLOTS, filterArtifacts, holderLabel, isUnequipped,
		statName, statValue, type ArtifactFilter
	} from './good';
	import { imgSrc } from './img';
	import type { GoodArtifact } from './types';

	let { version }: { version: string } = $props();
	let artifacts = $state<GoodArtifact[]>([]);
	let error = $state<string | null>(null);
	let f = $state<ArtifactFilter>({ ...DEFAULT_ARTIFACT_FILTER });
	let limit = $state(ARTIFACT_PAGE);

	$effect(() => {
		void version;
		api.goodArtifacts().then((a) => { artifacts = a; error = null; }).catch((e) => (error = errorMessage(e)));
	});
	$effect(() => { void [f.setId, f.slot, f.mainStat, f.unequippedOnly, f.minRarity]; limit = ARTIFACT_PAGE; });
	const sets = $derived([...new Map(artifacts.map((a) => [a.set_id, a.set_name])).entries()].sort((a, b) => a[1].localeCompare(b[1])));
	const mainStats = $derived([...new Set(artifacts.map((a) => a.main_stat))].sort());
	const shown = $derived(filterArtifacts(artifacts, f));
	const unequipped = $derived(artifacts.filter(isUnequipped).length);
</script>

{#if error}<p class="error">{error}</p>{/if}
<p class="muted" data-testid="artifact-count">{artifacts.length} artifacts · {unequipped} unequipped</p>
<div class="bar">
	<select aria-label="Set" bind:value={f.setId}>
		<option value={0}>All sets</option>
		{#each sets as [id, name] (id)}<option value={id}>{name}</option>{/each}
	</select>
	<select aria-label="Slot" bind:value={f.slot}>
		<option value="">All slots</option>
		{#each SLOTS as s (s)}<option value={s}>{SLOT_NAMES[s]}</option>{/each}
	</select>
	<select aria-label="Main stat" bind:value={f.mainStat}>
		<option value="">Any main stat</option>
		{#each mainStats as k (k)}<option value={k}>{statName(k)}</option>{/each}
	</select>
	<select aria-label="Minimum rarity" bind:value={f.minRarity}>
		{#each [5, 4, 3, 1] as r (r)}<option value={r}>{r}★+</option>{/each}
	</select>
	<label class="inline"><input type="checkbox" bind:checked={f.unequippedOnly} /> Unequipped only</label>
	<span class="muted">{shown.length} shown</span>
</div>
<div class="list">
	{#each shown.slice(0, limit) as a (a.id)}
		<div class="card" data-testid="artifact-card">
			<div class="face r{a.rarity}">{#if imgSrc(a.icon)}<img src={imgSrc(a.icon)} alt="" loading="lazy" />{/if}</div>
			<div class="body">
				<div><b>{a.set_name}</b> · {SLOT_NAMES[a.slot]} · {'★'.repeat(a.rarity)} · +{a.level}</div>
				<div>{statName(a.main_stat)}</div>
				<ul>{#each a.substats as s (s.key)}<li>{statName(s.key)} +{statValue(s.key, s.value)}</li>{/each}</ul>
				<div class="holder" class:free={isUnequipped(a)}>
					{#if a.holder && imgSrc(a.holder.icon)}<img src={imgSrc(a.holder.icon)} alt="" class="avatar" />{/if}
					{holderLabel(a)}
				</div>
			</div>
		</div>
	{/each}
</div>
{#if shown.length > limit}
	<button type="button" onclick={() => (limit += ARTIFACT_PAGE)}>Show more ({shown.length - limit} left)</button>
{/if}

<style>
	.bar { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; margin-bottom: 12px; }
	label.inline { display: inline-flex; gap: 6px; align-items: center; font-size: 12px; }
	.list { display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 10px; }
	.card { display: flex; gap: 10px; padding: 8px; border: 1px solid var(--line); border-radius: 8px; font-size: 12px; }
	.face { width: 56px; height: 56px; flex: none; border-radius: 8px; background: var(--r0); }
	.face.r1 { background: var(--r1); } .face.r2 { background: var(--r2); } .face.r3 { background: var(--r3); }
	.face.r4 { background: var(--r4); } .face.r5 { background: var(--r5); }
	.face img { width: 56px; height: 56px; display: block; }
	ul { margin: 4px 0; padding-left: 16px; color: var(--muted); }
	.holder { display: flex; gap: 4px; align-items: center; color: var(--muted); }
	.holder.free { color: var(--warn); }
	.avatar { width: 18px; height: 18px; border-radius: 50%; }
</style>
```

- [ ] **Step 3: Wire the tabs** in `frontend/src/routes/inventory/+page.svelte`: fill the Task 7 branches:

```svelte
	{:else if activeTab === 'weapons' && data.good}
		<WeaponsTab version={data.good.imported_at} />
	{:else if data.good}
		<ArtifactsTab version={data.good.imported_at} />
```

(import both components).

- [ ] **Step 4: Picker owned mark.** In the character detail page's planned-weapon `<select>`, change the option label:

```svelte
{#each weapons as w (w.id)}<option value={w.id}>{'★'.repeat(w.rarity)} {w.name}{w.owned ? ` · ${ownedLabel(w.owned)}` : ''}</option>{/each}
```

and import `ownedLabel` from `$lib/good`. Ordering comes from the API (owned first).

- [ ] **Step 5: Check**

Run: `npm run check`, `npx vitest run`, `npm run build`
Expected: 0 errors, tests pass, build succeeds.

- [ ] **Step 6: Commit**

```bash
git add frontend/src
git commit -m "feat(good): Weapons and Artifacts tabs, owned mark in the weapon picker"
```

---

### Task 9: End-to-end test, dev seed and README

**Files:**
- Modify: `backend/app/devseed.py` (artifact sets)
- Create: `frontend/e2e/fixtures/good-sample.json`, `frontend/e2e/good.spec.ts`
- Modify: `README.md`
- Test: `backend/tests/test_devseed.py` (if it asserts seeded tables)

**Interfaces:**
- Consumes: the whole feature.
- Produces: a Playwright spec covering spec §9's flow.

- [ ] **Step 1: Dev seed.** In `backend/app/devseed.py`, import `GameArtifactSet`, and right after the `GameWeapon` loop add:

```python
        s.add(GameArtifactSet(id=15001, name="Gladiator's Finale", icon="UI_RelicIcon_15001_4", sort_order=1))
        s.add(GameArtifactSet(id=15007, name="Noblesse Oblige", icon="UI_RelicIcon_15007_4", sort_order=2))
        s.merge(GameMeta(key="artifact_sets_fetched_at", value=iso(now)))
```

(Do not enable `good_import_enabled` in the seed; the e2e test turns it on through the UI.)

- [ ] **Step 2: e2e fixture** `frontend/e2e/fixtures/good-sample.json` (invented, matches devseed names):

```json
{
  "format": "GOOD", "version": 2, "source": "E2E_Scanner",
  "materials": {"SmallLampGrass": 37, "HerosWit": 120, "GuideToFreedom": 2, "Fowl": 4},
  "weapons": [
    {"key": "FavoniusSword", "level": 90, "ascension": 6, "refinement": 3, "location": "Bennett", "lock": true},
    {"key": "MistsplitterReforged", "level": 20, "ascension": 1, "refinement": 1, "location": "", "lock": false}
  ],
  "artifacts": [
    {"setKey": "NoblesseOblige", "slotKey": "flower", "rarity": 5, "level": 20, "mainStatKey": "hp",
     "location": "Furina", "lock": true, "substats": [{"key": "critRate_", "value": 3.9}]},
    {"setKey": "GladiatorsFinale", "slotKey": "goblet", "rarity": 5, "level": 12, "mainStatKey": "pyro_dmg_",
     "location": "", "lock": false, "substats": [{"key": "critDMG_", "value": 7.8}]},
    {"setKey": "NoblesseOblige", "slotKey": "plume", "rarity": 4, "level": 0, "mainStatKey": "atk",
     "location": "", "lock": false, "substats": []}
  ]
}
```

- [ ] **Step 3: Write the e2e test** `frontend/e2e/good.spec.ts`:

```ts
import { expect, test } from '@playwright/test';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const fixture = resolve(dirname(fileURLToPath(import.meta.url)), 'fixtures', 'good-sample.json');

test('GOOD import: opt in, import, exact counts, weapons, artifacts, opt out', async ({ page }) => {
	await page.goto('/inventory');
	await expect(page.getByRole('button', { name: 'Import GOOD file' })).toHaveCount(0);   // off by default

	await page.goto('/settings');
	await page.getByTestId('good-settings').getByRole('checkbox', { name: 'Use GOOD inventory import' }).check();
	await expect(page.getByTestId('good-settings').getByRole('button', { name: 'Import GOOD file' })).toBeVisible();

	await page.goto('/inventory');
	await page.getByTestId('good-file-input').setInputFiles(fixture);
	await expect(page.getByTestId('good-toast')).toContainText('Imported 3 materials, 2 weapons, 3 artifacts.');
	await expect(page.getByTestId('scan-status')).toContainText('E2E_Scanner');

	const lamp = page.getByTestId('tile-100055');           // unneeded, now owned
	await expect(lamp).toContainText('37');
	await expect(lamp).not.toHaveClass(/dim/);
	await expect(page.getByTestId('tile-104003')).toContainText('120/20 ✓');   // met, scan agrees
	await expect(page.getByTestId('tile-104302')).toContainText('8/15');      // short: live wins over scan 2

	await page.getByRole('button', { name: 'Owned' }).click();
	await expect(page.getByTestId('tile-100055')).toBeVisible();
	await expect(page.getByTestId('tile-104319')).toHaveCount(0);           // Crown: not in the scan
	await page.getByRole('button', { name: 'All' }).click();

	await page.getByRole('tab', { name: 'Weapons' }).click();
	const mist = page.getByTestId('weapon-card').filter({ hasText: 'Mistsplitter Reforged' });
	await expect(mist).toContainText('Unequipped');
	await expect(page.getByTestId('weapon-card').filter({ hasText: 'Favonius Sword' })).toContainText('Bennett');
	await page.getByRole('checkbox', { name: 'Unequipped only' }).check();
	await expect(page.getByTestId('weapon-card')).toHaveCount(1);

	await page.getByRole('tab', { name: 'Artifacts' }).click();
	await expect(page.getByTestId('artifact-count')).toHaveText('3 artifacts · 2 unequipped');
	await expect(page.getByTestId('artifact-card')).toHaveCount(3);
	await page.getByRole('combobox', { name: 'Slot' }).selectOption('goblet');
	await expect(page.getByTestId('artifact-card')).toHaveCount(1);
	await expect(page.getByTestId('artifact-card')).toContainText('Pyro DMG Bonus');

	await page.goto('/settings');
	await page.getByTestId('good-settings').getByRole('checkbox', { name: 'Use GOOD inventory import' }).uncheck();
	await page.goto('/inventory');
	await expect(page.getByRole('tab', { name: 'Weapons' })).toHaveCount(0);
	await expect(page.getByTestId('tile-100055')).not.toContainText('37');
	await expect(page.getByTestId('tile-100055')).toHaveClass(/dim/);
});
```

`MaterialTile` puts `class:dim` on the `.tile` element that carries `data-testid`, so the class assertions work as written. If tile ids differ in the dev seed, read `devseed.py` `MATERIALS` and correct the test, not the seed.

- [ ] **Step 4: Run the e2e test**

Run (in `frontend/`): `$env:PYTHON="C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe"; npx playwright test e2e/good.spec.ts`
Expected: PASS. Then run the full Playwright suite: `npx playwright test`. All other specs must still pass. If a spec shares the server and runs in parallel, the GOOD test must leave the toggle off at its end, which it does.

- [ ] **Step 5: README.** Add a section after "## Planner (phase 2)":

```markdown
## Inventory import (GOOD, optional)

The Inventory page works without this: the HoYoLAB calculator already reports what your Build characters need and how much you're short. If you also want exact counts for every material, a list of all your weapons (including unequipped ones), and your artifacts, you can import a **GOOD** file exported by a scanner tool such as Inventory Kamera or Irminsul.

1. Settings → **Inventory import (GOOD)** → tick **Use GOOD inventory import**.
2. Inventory → **Import GOOD file** → choose the scanner's `.json` export.

Each import replaces the previous one. Live HoYoLAB data always wins where it is exact, and to-farm numbers never use the scan. Turning the option off hides everything imported (it is kept until you press **Delete imported data**).

**Risk:** this app only reads the file. The scanner that creates it is third-party software, which HoYoverse's terms forbid; use at your own risk.

To see how a real export matches the game data without importing it: `python -m app.good.check --db <copy of the database> --refresh <file>` (from `backend/`; prints only counts and unrecognised keys).
```

- [ ] **Step 6: Run every suite**

```
cd backend; PY -m pytest -q
cd ../frontend; npm run check; npx vitest run; npm run build; $env:PYTHON="<PY>"; npx playwright test
```

Expected: all green.

- [ ] **Step 7: Commit**

```bash
git add backend/app/devseed.py frontend/e2e README.md backend/tests
git commit -m "test(good): end-to-end GOOD import flow, dev seed sets, README"
```
