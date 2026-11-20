# Phase 2 — Planner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** For every character with goal `build`, show what is still left to farm (Inventory grid, Dashboard "Active today" / weekly bosses / Building cards, per-character shortfall) with no manual entry.

**Architecture:** A new `gaps` sync part makes one HoYoLAB `batch_compute` request for all Build characters and stores per-character and combined need/short. Yatta supplies the material catalogue, craft chains, domain weekdays, weekly-boss names, and the weapon list. A new pure `planner/` package turns those tables into page data (crafting rollup, farm today, weekly bosses, character shortfall); the API and SvelteKit pages only read from it.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, SQLite, httpx, genshin.py 1.7.32, pytest; SvelteKit (Svelte 5 runes, TypeScript), Vitest, Playwright.

**Spec:** [docs/superpowers/specs/2026-11-19-phase2-planner-design.md](../specs/2026-11-19-phase2-planner-design.md)

## Global Constraints

- Unofficial-API code lives only in `backend/app/sync/`; everything else reads the database.
- Cookie values, UID, and region are never logged, returned by the API, or committed. Test fixtures use made-up ids only.
- Backend binds `127.0.0.1` only; the browser only talks to `/api`.
- Images go through `/api/img/...` (`imgSrc()` in the frontend); no art is committed.
- Every new table/column goes through Alembic migration `0002`; `test_models_match_migrations` must stay green.
- Server time: America (`os_usa`) UTC−5, Europe (`os_euro`) UTC+1, Asia (`os_asia`) and TW/HK/MO (`os_cht`) UTC+8. Daily reset 04:00 server time; weekly reset Monday 04:00 server time.
- Gaps-only recalculation runs **3 s** after the last goal/target/planned-weapon change.
- Crafting: 3 of tier *k−1* make 1 of tier *k*; Mora cost of crafting ignored.
- `localStorage` access always wrapped in try/catch.
- **Plan-level deviation from the spec (flagged to the user):** Traveler and Manekin are skipped by the gaps part in phase 2 (their calculator ids are element-specific); their cards say so instead of showing materials.
- Commands run from the repo root unless stated: backend tests `cd backend; ..\.venv\Scripts\python -m pytest -q`; frontend `cd frontend; npm run check; npm test; npm run e2e`.

## Review Focus

1. **Traveler/Manekin set to Build** → the gaps part must still succeed for everyone else, and the UI shows "Traveler planning isn't supported yet" (tests in Task 6 and Task 8).
2. **A Build character already at or above every target** → no calculator item is sent, no crash, card shows "Everything in the bag ✓" (tests in Task 6 and Task 10).
3. **Calculator returns a material id missing from the catalogue** (new patch, or catalogue never downloaded) → tile appears under **Other** with HoYoLAB's name/icon and a game-data refresh is triggered (tests in Task 6, Task 9, Task 11).
4. **Several quick edits, or an edit while a full sync is running** → exactly one gaps run afterwards, never a loop (tests in Task 8).
5. **Not connected / cookie expired after editing targets** → pages must not poll "Updating…" forever (tests in Task 9 `gap_status` and Task 11).

---

## File Structure

**Backend — new**

| File | Responsibility |
|---|---|
| `backend/app/servertime.py` | Region offsets, server day/weekday, weekly reset instant |
| `backend/app/gamedata/materials.py` | Yatta material/domain/weapon parsing + fetch; category rules |
| `backend/app/planner/__init__.py` | Package marker |
| `backend/app/planner/requests.py` | Build calculator inputs from goals/owned data; snapshot of goals |
| `backend/app/planner/data.py` | `PlannerData` loader (one read of all planner tables) |
| `backend/app/planner/crafting.py` | Craft chains and rollup |
| `backend/app/planner/inventory.py` | Material rows, states, category grouping, material index |
| `backend/app/planner/today.py` | Farm today, weekly bosses |
| `backend/app/planner/characters.py` | Per-character shortfall, Building cards |
| `backend/app/planner/status.py` | `gap_status()` for the UI |
| `backend/app/api/planner.py` | `/inventory`, `/weapons`, `/weekly-bosses/{boss}` |
| `backend/migrations/versions/0002_planner.py` | Phase 2 schema |
| `backend/tests/fixtures/yatta_material.json`, `yatta_material_details.json`, `yatta_daily_dungeon.json`, `yatta_weapon.json`, `calculator_batch.json` | Trimmed/hand-made fixtures |
| `backend/tests/test_servertime.py`, `test_materials.py`, `test_requests.py`, `test_planner.py`, `test_api_planner.py` | Tests |

**Backend — modified:** `db/models.py`, `gamedata/service.py`, `sync/hoyolab.py`, `sync/persist.py`, `sync/runner.py`, `context.py`, `main.py`, `config.py`, `smoke.py`, `devseed.py`, `api/__init__.py`, `api/characters.py`, `api/dashboard.py`, `api/settings.py`, `tests/fakes.py`, `tests/helpers.py`, existing tests where exact sync-part dicts are asserted.

**Frontend — new:** `src/lib/materials.ts` (+ `materials.test.ts`), `src/lib/MaterialTile.svelte`, `src/lib/MaterialPopover.svelte`, `src/routes/inventory/+page.svelte`, `e2e/planner.spec.ts`.

**Frontend — modified:** `src/lib/types.ts`, `src/lib/api.ts`, `src/app.css`, `src/routes/+layout.svelte`, `src/routes/+page.svelte`, `src/routes/characters/[slug]/+page.svelte`, `src/routes/settings/+page.svelte`.

**Docs:** `README.md`, `docs/superpowers/notes/2026-11-19-phase2-calculator-findings.md` (anonymized live findings).

---

### Task 1: Server time

**Files:**
- Create: `backend/app/servertime.py`
- Test: `backend/tests/test_servertime.py`

**Interfaces:**
- Produces: `offset_hours(region: str | None) -> int`, `server_day(now: datetime, region: str | None) -> date`, `server_weekday(now, region) -> int` (0 = Monday), `week_start(now, region) -> datetime` (naive UTC). `now` is always naive UTC (as `app.timeutil.utcnow()` returns).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_servertime.py
from datetime import datetime

import pytest

from app.servertime import offset_hours, server_weekday, week_start


@pytest.mark.parametrize("region,before,after", [
    ("os_euro", datetime(2026, 11, 23, 2, 59), datetime(2026, 11, 23, 3, 0)),
    ("os_usa", datetime(2026, 11, 23, 8, 59), datetime(2026, 11, 23, 9, 0)),
    ("os_asia", datetime(2026, 11, 22, 19, 59), datetime(2026, 11, 22, 20, 0)),
    ("os_cht", datetime(2026, 11, 22, 19, 59), datetime(2026, 11, 22, 20, 0)),
])
def test_day_changes_at_0400_server_time(region, before, after):
    assert server_weekday(before, region) == 6  # still Sunday
    assert server_weekday(after, region) == 0   # Monday after reset


def test_unknown_region_defaults_to_utc_plus_8():
    assert offset_hours(None) == 8
    assert offset_hours("something") == 8


def test_week_start_is_latest_monday_reset():
    assert week_start(datetime(2026, 11, 25, 12, 0), "os_euro") == datetime(2026, 11, 23, 3, 0)
    assert week_start(datetime(2026, 11, 23, 2, 0), "os_euro") == datetime(2026, 11, 16, 3, 0)
    assert week_start(datetime(2026, 11, 23, 9, 0), "os_usa") == datetime(2026, 11, 23, 9, 0)
    assert week_start(datetime(2026, 11, 23, 8, 59), "os_usa") == datetime(2026, 11, 16, 9, 0)
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_servertime.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.servertime'`

- [ ] **Step 3: Implement**

```python
# backend/app/servertime.py
"""Game server time. Daily reset 04:00 server time; weekly reset Monday 04:00 server time.
All datetimes in and out are naive UTC, like everything stored in SQLite."""
from __future__ import annotations

from datetime import date, datetime, timedelta

REGION_OFFSETS = {"os_usa": -5, "os_euro": 1, "os_asia": 8, "os_cht": 8}
DEFAULT_OFFSET = 8
RESET_HOUR = 4


def offset_hours(region: str | None) -> int:
    return REGION_OFFSETS.get(region or "", DEFAULT_OFFSET)


def server_day(now: datetime, region: str | None) -> date:
    """The game day `now` belongs to: server-local time shifted back by the 04:00 reset."""
    return (now + timedelta(hours=offset_hours(region) - RESET_HOUR)).date()


def server_weekday(now: datetime, region: str | None) -> int:
    return server_day(now, region).weekday()


def week_start(now: datetime, region: str | None) -> datetime:
    """Naive UTC instant of the latest Monday 04:00 server time at or before `now`."""
    day = server_day(now, region)
    monday = day - timedelta(days=day.weekday())
    return datetime(monday.year, monday.month, monday.day) + timedelta(hours=RESET_HOUR - offset_hours(region))
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_servertime.py -q`
Expected: 6 passed

- [ ] **Step 5: Commit**

```bash
git add backend/app/servertime.py backend/tests/test_servertime.py
git commit -m "feat: server time helpers for daily and weekly resets"
```

---

### Task 2: Yatta material, domain, and weapon parsing

**Files:**
- Create: `backend/app/gamedata/materials.py`
- Create: `backend/tests/fixtures/yatta_material.json`, `backend/tests/fixtures/yatta_material_details.json`, `backend/tests/fixtures/yatta_daily_dungeon.json`, `backend/tests/fixtures/yatta_weapon.json`
- Test: `backend/tests/test_materials.py`

**Interfaces:**
- Consumes: `app.gamedata.yatta.WEAPONS` (maps `WEAPON_*` → "Sword" etc.).
- Produces:
  - `CATEGORIES: tuple[str, ...] = ("exp", "ascension", "specialty", "talent", "weapon", "enemy", "weekly", "special")`, `CATEGORY_LABELS: dict[str, str]` (also has `"other"`).
  - `categorize(yatta_type: str, rank: int, material_id: int) -> str | None`
  - `MaterialData(id, name, icon, rarity, yatta_type, category, region: str | None)` frozen dataclass; `parse_material_list(payload) -> list[MaterialData]`
  - `MaterialDetail(craft_from: int | None, sources: list[dict])`; `parse_material_detail(payload, rarity: int) -> MaterialDetail`. Source dicts: `{"kind": "domain" | "weekly_boss" | "region" | "text", "name": str, "days": list[int]}`.
  - `DomainData(id, name, kind: "talent" | "weapon", city: int | None, weekdays: list[int], material_ids: list[int])`; `parse_daily_dungeon(payload, material_ids: set[int]) -> list[DomainData]`
  - `WeaponData(id, name, icon, rarity, weapon_type)`; `parse_weapon_list(payload) -> list[WeaponData]`
  - async `fetch_material_list(http)`, `fetch_material_detail(http, material_id, rarity)`, `fetch_daily_dungeon(http, material_ids)`, `fetch_weapon_list(http)`.

- [ ] **Step 1: Create the fixtures** (shapes copied from the live Yatta API on 2026-11-19, trimmed)

`backend/tests/fixtures/yatta_material.json`:

```json
{"response": 200, "data": {
  "types": {"localSpecialtyMondstadt": "Local Specialty (Mondstadt)"},
  "items": {
    "202": {"id": 202, "name": "Mora", "type": "commonCurrency", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_202", "rank": 3, "route": "Mora"},
    "104003": {"id": 104003, "name": "Hero's Wit", "type": "characterEXPMaterial", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_104003", "rank": 4, "route": "Hero's Wit"},
    "104013": {"id": 104013, "name": "Mystic Enhancement Ore", "type": "weaponEnhancementMaterial", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_104013", "rank": 3, "route": "Mystic Enhancement Ore"},
    "104111": {"id": 104111, "name": "Agnidus Agate Sliver", "type": "characterAscensionMaterial", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_104111", "rank": 2, "route": "Agnidus Agate Sliver"},
    "104112": {"id": 104112, "name": "Agnidus Agate Fragment", "type": "characterAscensionMaterial", "recipe": true, "mapMark": false, "icon": "UI_ItemIcon_104112", "rank": 3, "route": "Agnidus Agate Fragment"},
    "113001": {"id": 113001, "name": "Hurricane Seed", "type": "characterLevelUpMaterial", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_113001", "rank": 4, "route": "Hurricane Seed"},
    "113003": {"id": 113003, "name": "Dvalin's Plume", "type": "characterLevelUpMaterial", "recipe": true, "mapMark": false, "icon": "UI_ItemIcon_113003", "rank": 5, "route": "Dvalin's Plume"},
    "113021": {"id": 113021, "name": "Dream Solvent", "type": "characterLevelUpMaterial", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_113021", "rank": 4, "route": "Dream Solvent"},
    "100055": {"id": 100055, "name": "Small Lamp Grass", "type": "localSpecialtyMondstadt", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_100055", "rank": 1, "route": "Small Lamp Grass"},
    "104301": {"id": 104301, "name": "Teachings of Freedom", "type": "characterTalentMaterial", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_104301", "rank": 2, "route": "Teachings of Freedom"},
    "104302": {"id": 104302, "name": "Guide to Freedom", "type": "characterTalentMaterial", "recipe": true, "mapMark": false, "icon": "UI_ItemIcon_104302", "rank": 3, "route": "Guide to Freedom"},
    "104303": {"id": 104303, "name": "Philosophies of Freedom", "type": "characterTalentMaterial", "recipe": true, "mapMark": false, "icon": "UI_ItemIcon_104303", "rank": 4, "route": "Philosophies of Freedom"},
    "104319": {"id": 104319, "name": "Crown of Insight", "type": "characterTalentMaterial", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_104319", "rank": 5, "route": "Crown of Insight"},
    "114001": {"id": 114001, "name": "Tile of Decarabian's Tower", "type": "weaponAscensionMaterial", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_114001", "rank": 2, "route": "Tile of Decarabian's Tower"},
    "112002": {"id": 112002, "name": "Slime Condensate", "type": "characterandWeaponEnhancementMaterial", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_112002", "rank": 1, "route": "Slime Condensate"},
    "100001": {"id": 100001, "name": "Fowl", "type": "cookingIngredient", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_100001", "rank": 1, "route": "Fowl"},
    "100100": {"id": 100100, "name": "Some Quest Item", "type": "questItem", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_100100", "rank": 4, "route": "Some Quest Item"}
  }
}}
```

`backend/tests/fixtures/yatta_material_details.json` (keyed by material id; each value is the full detail response):

```json
{
  "104112": {"response": 200, "data": {"name": "Agnidus Agate Fragment", "type": "Character Ascension Material",
    "recipe": {"15001": {"104111": {"name": "Agnidus Agate Sliver", "icon": "UI_ItemIcon_104111", "rank": 2, "count": 3}},
               "50007": {"104122": {"name": "Varunada Lazurite Fragment", "icon": "UI_ItemIcon_104122", "rank": 3, "count": 1},
                         "104201": {"name": "Dust of Azoth", "icon": "UI_ItemIcon_104201", "rank": 2, "count": 3}}},
    "source": [{"name": "Check the Enemies Tab in the Adventurer Handbook", "type": "single"},
               {"name": "Placeholder - Craftable Amount: {0}", "type": "single"}]}},
  "104302": {"response": 200, "data": {"name": "Guide to Freedom", "type": "Character Talent Material",
    "recipe": {"15002": {"104301": {"name": "Teachings of Freedom", "icon": "UI_ItemIcon_104301", "rank": 2, "count": 3}}},
    "source": [{"name": "Domain of Mastery: Forsaken Rift", "type": "domain", "days": ["monday", "thursday", "sunday"]}]}},
  "104303": {"response": 200, "data": {"name": "Philosophies of Freedom", "type": "Character Talent Material",
    "recipe": {"15003": {"104302": {"name": "Guide to Freedom", "icon": "UI_ItemIcon_104302", "rank": 3, "count": 3}}},
    "source": [{"name": "Domain of Mastery: Forsaken Rift", "type": "domain", "days": ["monday", "thursday", "sunday"]}]}},
  "104301": {"response": 200, "data": {"name": "Teachings of Freedom", "type": "Character Talent Material", "recipe": null,
    "source": [{"name": "Domain of Mastery: Forsaken Rift", "type": "domain", "days": ["monday", "thursday", "sunday"]}]}},
  "113003": {"response": 200, "data": {"name": "Dvalin's Plume", "type": "Character Level-Up Material",
    "recipe": {"60001": {"113004": {"name": "Dvalin's Claw", "icon": "UI_ItemIcon_113004", "rank": 5, "count": 1},
                         "113021": {"name": "Dream Solvent", "icon": "UI_ItemIcon_113021", "rank": 4, "count": 1}}},
    "source": [{"name": "Lv. 70+ Stormterror Challenge Reward", "type": "single"},
               {"name": "Obtained from the Crafting Bench Conversion Tab", "type": "single"}]}}
}
```

`backend/tests/fixtures/yatta_daily_dungeon.json`:

```json
{"response": 200, "data": {
  "monday": {
    "domainofMasteryForsakenRift": {"id": 4213, "name": "Domain of Mastery: Forsaken Rift", "reward": [102, 202, 105, 104303, 104302, 104301], "city": 1},
    "domainofForgeryCecilia": {"id": 4313, "name": "Domain of Forgery: Cecilia Garden", "reward": [102, 202, 105, 114001], "city": 1}
  },
  "thursday": {
    "domainofMasteryForsakenRift": {"id": 4213, "name": "Domain of Mastery: Forsaken Rift", "reward": [102, 202, 105, 104303, 104302, 104301], "city": 1}
  },
  "sunday": {
    "domainofMasteryForsakenRift": {"id": 4213, "name": "Domain of Mastery: Forsaken Rift", "reward": [102, 202, 105, 104303, 104302, 104301], "city": 1},
    "domainofForgeryCecilia": {"id": 4313, "name": "Domain of Forgery: Cecilia Garden", "reward": [102, 202, 105, 114001], "city": 1},
    "trounceDomain": {"id": 9999, "name": "Trounce Domain: Something", "reward": [113003], "city": 1}
  }
}}
```

`backend/tests/fixtures/yatta_weapon.json`:

```json
{"response": 200, "data": {"types": {}, "items": {
  "11401": {"id": 11401, "rank": 4, "type": "WEAPON_SWORD_ONE_HAND", "name": "Favonius Sword", "specialProp": "FIGHT_PROP_CHARGE_EFFICIENCY", "icon": "UI_EquipIcon_Sword_Zephyrus", "route": "Favonius Sword"},
  "11509": {"id": 11509, "rank": 5, "type": "WEAPON_SWORD_ONE_HAND", "name": "Mistsplitter Reforged", "specialProp": "FIGHT_PROP_CRITICAL_HURT", "icon": "UI_EquipIcon_Sword_Narukami", "route": "Mistsplitter Reforged"},
  "13407": {"id": 13407, "rank": 4, "type": "WEAPON_POLE", "name": "Favonius Lance", "specialProp": "FIGHT_PROP_CHARGE_EFFICIENCY", "icon": "UI_EquipIcon_Pole_Zephyrus", "route": "Favonius Lance"}
}}}
```

- [ ] **Step 2: Write the failing tests**

```python
# backend/tests/test_materials.py
from app.gamedata.materials import (
    categorize, parse_daily_dungeon, parse_material_detail, parse_material_list, parse_weapon_list,
)
from helpers import load_fixture


def test_categorize_rules():
    assert categorize("commonCurrency", 3, 202) == "exp"            # Mora
    assert categorize("characterEXPMaterial", 4, 104003) == "exp"
    assert categorize("weaponEnhancementMaterial", 3, 104013) == "exp"
    assert categorize("characterAscensionMaterial", 2, 104111) == "ascension"
    assert categorize("characterLevelUpMaterial", 4, 113001) == "ascension"   # normal boss drop
    assert categorize("characterLevelUpMaterial", 5, 113003) == "weekly"
    assert categorize("characterLevelUpMaterial", 4, 113021) == "special"     # Dream Solvent
    assert categorize("characterTalentMaterial", 5, 104319) == "special"      # Crown
    assert categorize("characterTalentMaterial", 3, 104302) == "talent"
    assert categorize("localSpecialtyMondstadt", 1, 100055) == "specialty"
    assert categorize("weaponAscensionMaterial", 2, 114001) == "weapon"
    assert categorize("characterandWeaponEnhancementMaterial", 1, 112002) == "enemy"
    assert categorize("cookingIngredient", 1, 100001) is None
    assert categorize("questItem", 4, 100100) is None


def test_parse_material_list_keeps_upgrade_materials_only():
    mats = {m.id: m for m in parse_material_list(load_fixture("yatta_material.json"))}
    assert 100001 not in mats and 100100 not in mats
    assert mats[104302].category == "talent" and mats[104302].rarity == 3
    assert mats[100055].region == "Mondstadt"
    assert mats[104302].region is None


def test_parse_material_detail_craft_chain_and_sources():
    details = load_fixture("yatta_material_details.json")
    frag = parse_material_detail(details["104112"], rarity=3)
    assert frag.craft_from == 104111                      # 3 slivers -> 1 fragment; conversions ignored
    assert frag.sources == [{"kind": "text", "name": "Check the Enemies Tab in the Adventurer Handbook", "days": []}]
    guide = parse_material_detail(details["104302"], rarity=3)
    assert guide.craft_from == 104301
    assert guide.sources == [{"kind": "domain", "name": "Domain of Mastery: Forsaken Rift", "days": [0, 3, 6]}]
    plume = parse_material_detail(details["113003"], rarity=5)
    assert plume.craft_from is None                       # Dream Solvent conversion is not a 3:1 craft
    assert plume.sources[0] == {"kind": "weekly_boss", "name": "Stormterror", "days": []}


def test_parse_daily_dungeon_merges_weekdays_and_filters_rewards():
    domains = parse_daily_dungeon(load_fixture("yatta_daily_dungeon.json"), {104301, 104302, 104303, 114001})
    by_id = {d.id: d for d in domains}
    assert set(by_id) == {4213, 4313}                     # trounce domain dropped
    assert by_id[4213].kind == "talent" and by_id[4213].weekdays == [0, 3, 6]
    assert by_id[4213].material_ids == [104303, 104302, 104301]   # 102/202/105 filtered out
    assert by_id[4313].kind == "weapon" and by_id[4313].weekdays == [0, 6]


def test_parse_weapon_list_maps_types():
    weapons = parse_weapon_list(load_fixture("yatta_weapon.json"))
    assert [w.name for w in weapons] == ["Mistsplitter Reforged", "Favonius Lance", "Favonius Sword"]
    assert {w.weapon_type for w in weapons} == {"Sword", "Polearm"}
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_materials.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.gamedata.materials'`

- [ ] **Step 4: Implement**

```python
# backend/app/gamedata/materials.py
"""Material catalogue, daily-domain schedule and weapon list from Yatta (gi.yatta.moe)."""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from app.gamedata.yatta import WEAPONS

YATTA_BASE = "https://gi.yatta.moe/api/v2/en"

CATEGORIES: tuple[str, ...] = ("exp", "ascension", "specialty", "talent", "weapon", "enemy", "weekly", "special")
CATEGORY_LABELS = {
    "exp": "Character EXP & weapon enhancement",
    "ascension": "Character ascension",
    "specialty": "Local specialties",
    "talent": "Talent books",
    "weapon": "Weapon ascension",
    "enemy": "Common enemy drops",
    "weekly": "Weekly boss drops",
    "special": "Crowns & special",
    "other": "Other",
}
MORA_ID = 202
DREAM_SOLVENT_ID = 113021
CROWN_ID = 104319
DAY_INDEX = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
WEEKLY_RE = re.compile(r"^Lv\. \d+\+ (?P<boss>.+?) Challenge Reward$")
SPECIALTY_RE = re.compile(r"\((?P<region>[^)]+)\)")


@dataclass(frozen=True)
class MaterialData:
    id: int
    name: str
    icon: str
    rarity: int
    yatta_type: str
    category: str
    region: str | None


@dataclass(frozen=True)
class MaterialDetail:
    craft_from: int | None
    sources: list[dict]


@dataclass(frozen=True)
class DomainData:
    id: int
    name: str
    kind: str
    city: int | None
    weekdays: list[int]
    material_ids: list[int]


@dataclass(frozen=True)
class WeaponData:
    id: int
    name: str
    icon: str
    rarity: int
    weapon_type: str


def categorize(yatta_type: str, rank: int, material_id: int) -> str | None:
    if material_id == MORA_ID or yatta_type in ("characterEXPMaterial", "weaponEnhancementMaterial"):
        return "exp"
    if material_id in (DREAM_SOLVENT_ID, CROWN_ID):
        return "special"
    if yatta_type == "characterAscensionMaterial":
        return "ascension"
    if yatta_type == "characterLevelUpMaterial":
        return "weekly" if rank >= 5 else "ascension"
    if yatta_type.startswith("localSpecialty"):
        return "specialty"
    if yatta_type == "characterTalentMaterial":
        return "talent"
    if yatta_type == "weaponAscensionMaterial":
        return "weapon"
    if yatta_type == "characterandWeaponEnhancementMaterial":
        return "enemy"
    return None


def parse_material_list(payload: dict) -> list[MaterialData]:
    types = payload["data"].get("types") or {}
    out: list[MaterialData] = []
    for v in payload["data"]["items"].values():
        mid, rank, ytype = int(v["id"]), int(v["rank"]), str(v["type"])
        category = categorize(ytype, rank, mid)
        if category is None:
            continue
        region = None
        if category == "specialty":
            m = SPECIALTY_RE.search(str(types.get(ytype, "")))
            region = m["region"] if m else ytype.removeprefix("localSpecialty")
        out.append(MaterialData(mid, str(v["name"]), str(v["icon"]), rank, ytype, category, region))
    return sorted(out, key=lambda m: m.id)


def parse_material_detail(payload: dict, rarity: int) -> MaterialDetail:
    d = payload["data"]
    craft_from = None
    for ingredients in (d.get("recipe") or {}).values():
        if len(ingredients) != 1:
            continue
        (iid, info), = ingredients.items()
        if int(info.get("count", 0)) == 3 and int(info.get("rank", 0)) == rarity - 1:
            craft_from = int(iid)
            break
    sources: list[dict] = []
    for s in d.get("source") or []:
        name = str(s.get("name", "")).strip()
        if s.get("type") == "domain":
            days = sorted(DAY_INDEX[x] for x in s.get("days") or [] if x in DAY_INDEX)
            sources.append({"kind": "domain", "name": name, "days": days})
        elif (m := WEEKLY_RE.match(name)) is not None:
            sources.append({"kind": "weekly_boss", "name": m["boss"], "days": []})
        elif name and "Placeholder" not in name:
            sources.append({"kind": "text", "name": name, "days": []})
    return MaterialDetail(craft_from, sources)


def parse_daily_dungeon(payload: dict, material_ids: set[int]) -> list[DomainData]:
    found: dict[int, dict] = {}
    for day, domains in payload["data"].items():
        if day not in DAY_INDEX:
            continue
        for v in domains.values():
            name = str(v["name"])
            kind = ("talent" if name.startswith("Domain of Mastery")
                    else "weapon" if name.startswith("Domain of Forgery") else None)
            if kind is None:
                continue
            entry = found.setdefault(int(v["id"]), {"name": name, "kind": kind, "city": v.get("city"),
                                                     "days": set(), "mats": []})
            entry["days"].add(DAY_INDEX[day])
            for r in v.get("reward") or []:
                if int(r) in material_ids and int(r) not in entry["mats"]:
                    entry["mats"].append(int(r))
    return [DomainData(did, e["name"], e["kind"], e["city"], sorted(e["days"]), e["mats"])
            for did, e in sorted(found.items())]


def parse_weapon_list(payload: dict) -> list[WeaponData]:
    weapons = [WeaponData(int(v["id"]), str(v["name"]), str(v["icon"]), int(v["rank"]),
                          WEAPONS.get(v["type"], v["type"]))
               for v in payload["data"]["items"].values()]
    return sorted(weapons, key=lambda w: (-w.rarity, w.name))


async def _get_json(http: httpx.AsyncClient, path: str) -> dict:
    response = await http.get(f"{YATTA_BASE}/{path}", timeout=30)
    response.raise_for_status()
    return response.json()


async def fetch_material_list(http: httpx.AsyncClient) -> list[MaterialData]:
    return parse_material_list(await _get_json(http, "material"))


async def fetch_material_detail(http: httpx.AsyncClient, material_id: int, rarity: int) -> MaterialDetail:
    return parse_material_detail(await _get_json(http, f"material/{material_id}"), rarity)


async def fetch_daily_dungeon(http: httpx.AsyncClient, material_ids: set[int]) -> list[DomainData]:
    return parse_daily_dungeon(await _get_json(http, "dailyDungeon"), material_ids)


async def fetch_weapon_list(http: httpx.AsyncClient) -> list[WeaponData]:
    return parse_weapon_list(await _get_json(http, "weapon"))
```

- [ ] **Step 5: Run to verify pass**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_materials.py -q`
Expected: 5 passed

- [ ] **Step 6: Commit**

```bash
git add backend/app/gamedata/materials.py backend/tests/test_materials.py backend/tests/fixtures/yatta_*.json
git commit -m "feat: parse Yatta materials, craft chains, domains and weapons"
```

---

### Task 3: Schema — migration 0002 and models

**Files:**
- Create: `backend/migrations/versions/0002_planner.py`
- Modify: `backend/app/db/models.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces ORM classes `GameMaterial`, `GameDomain`, `GameWeapon`, `MaterialGap`, `MaterialTotal`, `GapRun`, `WeeklyBossDone`; new columns `OwnedCharacter.weapon_id`, `LiveNotes.weekly_discounts_left`, `LiveNotes.weekly_discounts_max`, `CharacterGoal.planned_weapon_id`.

- [ ] **Step 1: Update the failing test**

In `backend/tests/test_db.py` replace `TABLES` with:

```python
TABLES = {
    "game_character", "game_meta", "owned_character", "owned_artifact",
    "live_notes", "sync_run", "character_goal", "setting",
    "game_material", "game_domain", "game_weapon", "material_gap", "material_total",
    "gap_run", "weekly_boss_done",
}
```

and add:

```python
def test_phase2_columns_exist(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    cols = {t: {c["name"] for c in inspect(engine).get_columns(t)}
            for t in ("owned_character", "live_notes", "character_goal")}
    assert "weapon_id" in cols["owned_character"]
    assert {"weekly_discounts_left", "weekly_discounts_max"} <= cols["live_notes"]
    assert "planned_weapon_id" in cols["character_goal"]
    engine.dispose()
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_db.py -q`
Expected: FAIL — missing tables/columns

- [ ] **Step 3: Write the migration**

```python
# backend/migrations/versions/0002_planner.py
"""phase 2 planner

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-19
"""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "game_material",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("yatta_type", sa.String(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("family", sa.Integer(), nullable=True),
        sa.Column("craft_from", sa.Integer(), nullable=True),
        sa.Column("sources", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("detail_fetched", sa.Boolean(), nullable=False),
    )
    op.create_table(
        "game_domain",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("city", sa.Integer(), nullable=True),
        sa.Column("weekdays", sa.JSON(), nullable=False),
        sa.Column("material_ids", sa.JSON(), nullable=False),
    )
    op.create_table(
        "game_weapon",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("weapon_type", sa.String(), nullable=False),
    )
    op.create_table(
        "material_gap",
        sa.Column("character_id", sa.Integer(), primary_key=True),
        sa.Column("material_id", sa.Integer(), primary_key=True),
        sa.Column("need", sa.Integer(), nullable=False),
        sa.Column("short", sa.Integer(), nullable=False),
    )
    op.create_table(
        "material_total",
        sa.Column("material_id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("icon", sa.String(), nullable=False),
        sa.Column("rarity", sa.Integer(), nullable=False),
        sa.Column("need", sa.Integer(), nullable=False),
        sa.Column("short", sa.Integer(), nullable=False),
        sa.Column("spare", sa.Integer(), nullable=False),
    )
    op.create_table(
        "gap_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("computed_at", sa.DateTime(), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("ok", sa.Boolean(), nullable=False),
        sa.Column("error", sa.String(), nullable=True),
        sa.Column("skipped", sa.JSON(), nullable=False),
    )
    op.create_table(
        "weekly_boss_done",
        sa.Column("boss", sa.String(), primary_key=True),
        sa.Column("week_start", sa.DateTime(), primary_key=True),
    )
    op.add_column("owned_character", sa.Column("weapon_id", sa.Integer(), nullable=True))
    op.add_column("live_notes", sa.Column("weekly_discounts_left", sa.Integer(), nullable=True))
    op.add_column("live_notes", sa.Column("weekly_discounts_max", sa.Integer(), nullable=True))
    op.add_column("character_goal", sa.Column("planned_weapon_id", sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("character_goal") as b:
        b.drop_column("planned_weapon_id")
    with op.batch_alter_table("live_notes") as b:
        b.drop_column("weekly_discounts_max")
        b.drop_column("weekly_discounts_left")
    with op.batch_alter_table("owned_character") as b:
        b.drop_column("weapon_id")
    for table in ("weekly_boss_done", "gap_run", "material_total", "material_gap",
                  "game_weapon", "game_domain", "game_material"):
        op.drop_table(table)
```

- [ ] **Step 4: Add the models**

In `backend/app/db/models.py` change the import to `from sqlalchemy import JSON, Boolean, DateTime, Integer, String`, then add to the existing classes:

```python
# OwnedCharacter — after weapon_refinement:
    weapon_id: Mapped[int | None] = mapped_column(Integer, nullable=True)

# LiveNotes — after realm_currency_max:
    weekly_discounts_left: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekly_discounts_max: Mapped[int | None] = mapped_column(Integer, nullable=True)

# CharacterGoal — after target_weapon_level:
    planned_weapon_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

Add under `# --- game data`:

```python
class GameMaterial(Base):
    __tablename__ = "game_material"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    icon: Mapped[str] = mapped_column(String)
    rarity: Mapped[int] = mapped_column(Integer)
    yatta_type: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    family: Mapped[int | None] = mapped_column(Integer, nullable=True)
    craft_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sources: Mapped[list] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer)
    detail_fetched: Mapped[bool] = mapped_column(Boolean)


class GameDomain(Base):
    __tablename__ = "game_domain"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    city: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekdays: Mapped[list] = mapped_column(JSON)
    material_ids: Mapped[list] = mapped_column(JSON)


class GameWeapon(Base):
    __tablename__ = "game_weapon"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    icon: Mapped[str] = mapped_column(String)
    rarity: Mapped[int] = mapped_column(Integer)
    weapon_type: Mapped[str] = mapped_column(String)
```

Add under `# --- account data`:

```python
class MaterialGap(Base):
    __tablename__ = "material_gap"
    character_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    need: Mapped[int] = mapped_column(Integer)
    short: Mapped[int] = mapped_column(Integer)


class MaterialTotal(Base):
    __tablename__ = "material_total"
    material_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)   # HoYoLAB's name/icon, used for ids missing from the catalogue
    icon: Mapped[str] = mapped_column(String)
    rarity: Mapped[int] = mapped_column(Integer)
    need: Mapped[int] = mapped_column(Integer)
    short: Mapped[int] = mapped_column(Integer)
    spare: Mapped[int] = mapped_column(Integer)


class GapRun(Base):
    __tablename__ = "gap_run"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    snapshot: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    skipped: Mapped[list] = mapped_column(JSON)
```

Add under `# --- user data`:

```python
class WeeklyBossDone(Base):
    __tablename__ = "weekly_boss_done"
    boss: Mapped[str] = mapped_column(String, primary_key=True)
    week_start: Mapped[datetime] = mapped_column(DateTime, primary_key=True)
```

- [ ] **Step 5: Run to verify pass**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_db.py -q`
Expected: all pass (including `test_models_match_migrations`)

- [ ] **Step 6: Run the full backend suite**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add backend/migrations/versions/0002_planner.py backend/app/db/models.py backend/tests/test_db.py
git commit -m "feat: phase 2 schema for materials, gaps and weekly bosses"
```

---

### Task 4: Game-data refresh for materials, domains, weapons

**Files:**
- Modify: `backend/app/gamedata/service.py`, `backend/app/main.py`, `backend/app/api/settings.py`, `backend/tests/helpers.py`
- Test: `backend/tests/test_gamedata.py`, `backend/tests/test_api_settings.py`

**Interfaces:**
- Consumes: everything from Task 2; models from Task 3.
- Produces:
  - `refresh_materials(session_factory, http, now=None, force=False) -> bool`
  - `refresh_all(session_factory, http, now=None, force=False) -> bool` (True if either refreshed)
  - `gamedata_status(session)` gains `"materials": {"fetched_at", "last_error", "count"}`.
  - `helpers.yatta_transport(status=200, fail_details: set[int] = frozenset())` serves avatar, material, material/{id}, dailyDungeon, weapon.

- [ ] **Step 1: Extend the test transport**

Replace `yatta_transport` in `backend/tests/helpers.py`:

```python
def yatta_transport(status: int = 200, fail_details: frozenset[int] = frozenset()) -> httpx.MockTransport:
    avatar = load_fixture("yatta_avatar.json")
    material = load_fixture("yatta_material.json")
    details = load_fixture("yatta_material_details.json")
    dungeon = load_fixture("yatta_daily_dungeon.json")
    weapon = load_fixture("yatta_weapon.json")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if status != 200:
            return httpx.Response(status, json={})
        if path.endswith("/avatar"):
            return httpx.Response(200, json=avatar)
        if path.endswith("/material"):
            return httpx.Response(200, json=material)
        if "/material/" in path:
            mid = int(path.rsplit("/", 1)[1])
            if mid in fail_details:
                return httpx.Response(500)
            body = details.get(str(mid), {"response": 200, "data": {"recipe": None, "source": []}})
            return httpx.Response(200, json=body)
        if path.endswith("/dailyDungeon"):
            return httpx.Response(200, json=dungeon)
        if path.endswith("/weapon"):
            return httpx.Response(200, json=weapon)
        return httpx.Response(404)

    return httpx.MockTransport(handler)
```

- [ ] **Step 2: Write the failing tests** (append to `backend/tests/test_gamedata.py`)

```python
import httpx
from sqlalchemy import select

from app.db.models import GameDomain, GameMaterial, GameWeapon
from app.gamedata.service import gamedata_status, refresh_all, refresh_materials
from helpers import yatta_transport


async def test_refresh_materials_stores_catalogue_chains_and_domains(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh_materials(session_factory, http) is True
    with session_factory() as s:
        mats = {m.id: m for m in s.scalars(select(GameMaterial))}
        assert mats[104302].craft_from == 104301 and mats[104303].craft_from == 104302
        assert mats[104301].family == mats[104302].family == mats[104303].family == 104301
        assert mats[113003].sources[0] == {"kind": "weekly_boss", "name": "Stormterror", "days": []}
        assert mats[100055].sources == [{"kind": "region", "name": "Mondstadt", "days": []}]
        assert all(m.detail_fetched for m in mats.values())
        order = sorted(mats.values(), key=lambda m: m.sort_order)
        cats = [m.category for m in order]
        assert cats == sorted(cats, key=["exp", "ascension", "specialty", "talent", "weapon",
                                         "enemy", "weekly", "special"].index)
        assert [m.id for m in order if m.category == "talent"] == [104301, 104302, 104303]
        assert {d.id for d in s.scalars(select(GameDomain))} == {4213, 4313}
        assert s.get(GameWeapon, 11401).weapon_type == "Sword"
        assert gamedata_status(s)["materials"]["count"] == len(mats)


async def test_refresh_materials_is_skipped_when_fresh(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_materials(session_factory, http)
        assert await refresh_materials(session_factory, http) is False


async def test_failed_detail_is_retried_next_time_and_reported(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport(fail_details=frozenset({104302}))) as http:
        assert await refresh_materials(session_factory, http) is True
    with session_factory() as s:
        assert s.get(GameMaterial, 104302).detail_fetched is False
        assert "1 material detail" in gamedata_status(s)["materials"]["last_error"]
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh_materials(session_factory, http) is True   # unfetched detail forces a refresh
    with session_factory() as s:
        assert s.get(GameMaterial, 104302).craft_from == 104301
        assert gamedata_status(s)["materials"]["last_error"] is None


async def test_refresh_materials_failure_keeps_cache(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_materials(session_factory, http)
    async with httpx.AsyncClient(transport=yatta_transport(status=500)) as http:
        assert await refresh_materials(session_factory, http, force=True) is False
    with session_factory() as s:
        assert s.get(GameMaterial, 104302) is not None
        assert gamedata_status(s)["materials"]["last_error"].startswith("HTTPStatusError")


async def test_refresh_all_runs_both(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        assert await refresh_all(session_factory, http) is True
    with session_factory() as s:
        status = gamedata_status(s)
        assert status["count"] > 0 and status["materials"]["count"] > 0
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_gamedata.py -q`
Expected: FAIL — `ImportError: cannot import name 'refresh_all'`

- [ ] **Step 4: Implement in `backend/app/gamedata/service.py`**

Add imports: `import asyncio`, `from sqlalchemy import delete`, `from app.db.models import GameDomain, GameMaterial, GameWeapon`, and `from app.gamedata.materials import CATEGORIES, fetch_daily_dungeon, fetch_material_detail, fetch_material_list, fetch_weapon_list`. Then add:

```python
META_MAT_FETCHED = "materials_fetched_at"
META_MAT_ERROR = "materials_last_error"
DETAIL_CONCURRENCY = 4
FETCH_ERRORS = (httpx.HTTPError, KeyError, ValueError, TypeError)


def materials_need_refresh(session: Session, now: datetime) -> bool:
    fetched = _get_meta(session, META_MAT_FETCHED)
    if not fetched or session.scalar(select(func.count()).select_from(GameMaterial)) == 0:
        return True
    if session.scalar(select(func.count()).select_from(GameMaterial).where(GameMaterial.detail_fetched.is_(False))):
        return True
    return now - datetime.fromisoformat(fetched.rstrip("Z")) > timedelta(days=GAMEDATA_MAX_AGE_DAYS)


def _store_catalogue(session: Session, mats, weapons, domains) -> list[tuple[int, int]]:
    """Upsert list data; keep details already fetched. Returns (id, rarity) still needing details."""
    for m in mats:
        row = session.get(GameMaterial, m.id)
        region = [{"kind": "region", "name": m.region, "days": []}] if m.region else []
        if row is None:
            row = GameMaterial(id=m.id, sources=region, detail_fetched=False, sort_order=0)
            session.add(row)
        row.name, row.icon, row.rarity = m.name, m.icon, m.rarity
        row.yatta_type, row.category = m.yatta_type, m.category
    for w in weapons:
        session.merge(GameWeapon(id=w.id, name=w.name, icon=w.icon, rarity=w.rarity, weapon_type=w.weapon_type))
    session.execute(delete(GameDomain))
    for d in domains:
        session.add(GameDomain(id=d.id, name=d.name, kind=d.kind, city=d.city, weekdays=d.weekdays,
                               material_ids=d.material_ids))
    session.flush()
    return [(r.id, r.rarity) for r in session.scalars(select(GameMaterial).where(GameMaterial.detail_fetched.is_(False)))]


def _recompute_family_and_order(session: Session) -> None:
    rows = list(session.scalars(select(GameMaterial)))
    by_id = {r.id: r for r in rows}
    for r in rows:
        root, steps = r, 0
        while root.craft_from in by_id and steps < 10:
            root, steps = by_id[root.craft_from], steps + 1
        r.family = root.id
    ordered = sorted(rows, key=lambda r: (CATEGORIES.index(r.category), r.yatta_type, r.family, r.rarity, r.id))
    for i, r in enumerate(ordered):
        r.sort_order = i


async def refresh_materials(session_factory: sessionmaker, http: httpx.AsyncClient,
                            now: datetime | None = None, force: bool = False) -> bool:
    """Download material/weapon/domain data if stale (or forced). Returns True if data was stored."""
    now = now or utcnow()
    with session_factory() as s:
        if not force and not materials_need_refresh(s, now):
            return False
    try:
        mats = await fetch_material_list(http)
        weapons = await fetch_weapon_list(http)
        domains = await fetch_daily_dungeon(http, {m.id for m in mats if m.category in ("talent", "weapon")})
    except FETCH_ERRORS as e:
        message = f"{type(e).__name__}: {e}"[:300]
        log.warning("Material data refresh failed: %s", message)
        with session_factory.begin() as s:
            _set_meta(s, META_MAT_ERROR, message)
        return False
    with session_factory.begin() as s:
        todo = _store_catalogue(s, mats, weapons, domains)

    sem = asyncio.Semaphore(DETAIL_CONCURRENCY)

    async def one(mid: int, rarity: int):
        async with sem:
            try:
                return mid, await fetch_material_detail(http, mid, rarity)
            except FETCH_ERRORS:
                return mid, None

    results = await asyncio.gather(*(one(mid, rarity) for mid, rarity in todo))
    failures = 0
    with session_factory.begin() as s:
        for mid, detail in results:
            if detail is None:
                failures += 1
                continue
            row = s.get(GameMaterial, mid)
            row.craft_from = detail.craft_from
            row.sources = [x for x in row.sources if x["kind"] == "region"] + detail.sources
            row.detail_fetched = True
        _recompute_family_and_order(s)
        _set_meta(s, META_MAT_FETCHED, iso(now))
        _set_meta(s, META_MAT_ERROR,
                  f"{failures} material detail(s) failed; retried on next refresh" if failures else None)
    return True


async def refresh_all(session_factory: sessionmaker, http: httpx.AsyncClient,
                      now: datetime | None = None, force: bool = False) -> bool:
    characters = await refresh(session_factory, http, now=now, force=force)
    materials = await refresh_materials(session_factory, http, now=now, force=force)
    return characters or materials
```

Replace `gamedata_status`:

```python
def gamedata_status(session: Session) -> dict:
    return {
        "fetched_at": _get_meta(session, META_FETCHED),
        "last_error": _get_meta(session, META_ERROR),
        "count": session.scalar(select(func.count()).select_from(GameCharacter)) or 0,
        "materials": {
            "fetched_at": _get_meta(session, META_MAT_FETCHED),
            "last_error": _get_meta(session, META_MAT_ERROR),
            "count": session.scalar(select(func.count()).select_from(GameMaterial)) or 0,
        },
    }
```

- [ ] **Step 5: Use `refresh_all` everywhere**

In `backend/app/main.py`: import `refresh_all` instead of `refresh`; in `on_unknown_ids` call `await refresh_all(session_factory, http, force=True)`; in `lifespan` use `asyncio.create_task(refresh_all(session_factory, http))`.

In `backend/app/api/settings.py`: import `refresh_all` and change the endpoint body to `refreshed = await refresh_all(ctx.session_factory, ctx.http, force=True)`.

Add to `backend/tests/test_api_settings.py` `test_gamedata_refresh_endpoint`:

```python
    assert body["gamedata"]["materials"]["count"] > 0
```

- [ ] **Step 6: Run to verify pass**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/gamedata/service.py backend/app/main.py backend/app/api/settings.py backend/tests/helpers.py backend/tests/test_gamedata.py backend/tests/test_api_settings.py
git commit -m "feat: download material catalogue, domain schedule and weapons"
```

---

### Task 5: HoYoLAB wrapper — weapon id, discounts, talent ids, batch calculator

**Files:**
- Modify: `backend/app/sync/hoyolab.py`, `backend/app/context.py`, `backend/app/smoke.py` (constructor only), `backend/tests/fakes.py`
- Create: `backend/tests/fixtures/calculator_batch.json`
- Test: `backend/tests/test_hoyolab.py`

**Interfaces:**
- Produces in `app.sync.hoyolab`:
  - `WeaponInfo` gains `id: int = 0` (last field). `NotesInfo` gains `weekly_discounts_left: int | None = None`, `weekly_discounts_max: int | None = None` (last fields).
  - `NoInventoryData(HoyolabError)`
  - `TalentIds(normal: int, skill: int, burst: int)` frozen dataclass
  - `GapCharacter(character_id: int, level_current: int, level_target: int, talents: tuple[tuple[int, int, int], ...], weapon: tuple[int, int, int] | None)` — talents are `(group_id, current, target)`, weapon `(weapon_id, current, target)`
  - `MaterialAmount(id: int, name: str, icon: str, rarity: int, need: int, short: int)`
  - `GapResult(per_character: dict[int, list[MaterialAmount]], total: list[MaterialAmount], spare: list[MaterialAmount])` — for `spare`, `need` holds the spare count
  - `to_talent_ids(items: list[Mapping]) -> TalentIds`, `build_batch_body(chars, uid: int, region: str) -> dict`, `to_gap_result(raw: Mapping, character_ids: list[int]) -> GapResult`
  - `HoyolabSource` protocol gains `get_talent_ids(character_id: int) -> TalentIds` and `compute_gaps(chars: Sequence[GapCharacter]) -> GapResult`
  - `GenshinPySource(cookies, uid, delays=RETRY_DELAYS, *, region: str | None = None)`
- `tests/fakes.py`: `FakeSource(..., gaps: GapResult | None = None)`, records `("talents", id)` and `("gaps", ids)` calls; `fail` accepts `"talents"` and `"gaps"`.

- [ ] **Step 1: Create the anonymized calculator fixture** (`backend/tests/fixtures/calculator_batch.json`; shape of the `batch_compute` v3 `data` payload, values made up)

```json
{
  "items": [{}, {}],
  "has_user_info": true,
  "overall_consume": [
    {"id": 104302, "name": "Guide to Freedom", "icon": "https://act-webstatic.hoyoverse.com/m/104302.png", "level": 3, "num": 18, "lack_num": 7, "wiki_url": ""},
    {"id": 104303, "name": "Philosophies of Freedom", "icon": "https://act-webstatic.hoyoverse.com/m/104303.png", "level": 4, "num": 12, "lack_num": 0, "wiki_url": ""},
    {"id": 999001, "name": "Brand New Material", "icon": "https://act-webstatic.hoyoverse.com/m/999001.png", "level": 4, "num": 3, "lack_num": 3, "wiki_url": ""}
  ],
  "available_material": [
    {"id": 104301, "name": "Teachings of Freedom", "icon": "https://act-webstatic.hoyoverse.com/m/104301.png", "level": 2, "num": 10, "lack_num": 0, "wiki_url": ""}
  ],
  "single_role_result": [
    {"has_user_info": true, "overall_consume": [
      {"id": 104302, "name": "Guide to Freedom", "icon": "", "level": 3, "num": 9, "lack_num": 0, "wiki_url": ""},
      {"id": 104303, "name": "Philosophies of Freedom", "icon": "", "level": 4, "num": 6, "lack_num": 0, "wiki_url": ""}
    ]},
    {"has_user_info": true, "overall_consume": [
      {"id": 104302, "name": "Guide to Freedom", "icon": "", "level": 3, "num": 9, "lack_num": 0, "wiki_url": ""},
      {"id": 104303, "name": "Philosophies of Freedom", "icon": "", "level": 4, "num": 6, "lack_num": 0, "wiki_url": ""},
      {"id": 999001, "name": "Brand New Material", "icon": "", "level": 4, "num": 3, "lack_num": 3, "wiki_url": ""}
    ]}
  ]
}
```

- [ ] **Step 2: Write the failing tests** (append to `backend/tests/test_hoyolab.py`; extend its import list with `GapCharacter, NoInventoryData, build_batch_body, to_gap_result, to_talent_ids`)

```python
from helpers import load_fixture


def test_roster_entry_keeps_weapon_id():
    c = NS(id=10000032, name="Bennett", element="Pyro", rarity=4, icon="x", level=80,
           friendship=10, constellation=6, weapon=WEAPON)
    assert to_roster_entry(c).weapon.id == 1


def test_notes_weekly_discounts_optional():
    base = dict(current_resin=10, max_resin=200, remaining_resin_recovery_time=timedelta(minutes=1),
                completed_commissions=4, max_commissions=4, current_realm_currency=0,
                max_realm_currency=2400, expeditions=[])
    assert to_notes(NS(**base)).weekly_discounts_left is None
    notes = to_notes(NS(**base, remaining_resin_discounts=1, max_resin_discounts=3))
    assert (notes.weekly_discounts_left, notes.weekly_discounts_max) == (1, 3)


def test_to_talent_ids_picks_normal_skill_burst():
    items = [
        {"id": 10321, "group_id": 3201, "max_level": 10},   # normal
        {"id": 10322, "group_id": 3202, "max_level": 10},   # skill
        {"id": 10323, "group_id": 3203, "max_level": 10},   # alternate sprint (order 3) — dropped
        {"id": 10329, "group_id": 3209, "max_level": 10},   # burst
        {"id": 3221, "group_id": 3221, "max_level": 1},     # passive
    ]
    ids = to_talent_ids(items)
    assert (ids.normal, ids.skill, ids.burst) == (3201, 3202, 3209)


def test_to_talent_ids_rejects_short_lists():
    with pytest.raises(HoyolabError):
        to_talent_ids([{"id": 1, "group_id": 1, "max_level": 10}])


def test_build_batch_body_includes_uid_region_and_only_given_parts():
    chars = [GapCharacter(10000032, 80, 90, ((3201, 6, 8),), (11401, 90, 90)),
             GapCharacter(10000089, 1, 90, (), None)]
    body = build_batch_body(chars, uid=700000001, region="os_euro")
    assert body["uid"] == 700000001 and body["region"] == "os_euro"
    first, second = body["items"]
    assert first == {"avatar_id": 10000032, "avatar_level_current": 80, "avatar_level_target": 90,
                     "skill_list": [{"id": 3201, "level_current": 6, "level_target": 8}],
                     "weapon": {"id": 11401, "level_current": 90, "level_target": 90}}
    assert "weapon" not in second and second["skill_list"] == []


def test_to_gap_result_maps_per_character_total_and_spare():
    result = to_gap_result(load_fixture("calculator_batch.json"), [10000032, 10000089])
    assert [m.id for m in result.per_character[10000089]] == [104302, 104303, 999001]
    guide = next(m for m in result.total if m.id == 104302)
    assert (guide.need, guide.short, guide.rarity) == (18, 7, 3)
    assert result.spare[0].id == 104301 and result.spare[0].need == 10


def test_to_gap_result_without_user_info_fails():
    raw = load_fixture("calculator_batch.json") | {"has_user_info": False}
    with pytest.raises(NoInventoryData):
        to_gap_result(raw, [10000032, 10000089])


def test_to_gap_result_single_character_without_single_results():
    raw = load_fixture("calculator_batch.json") | {"single_role_result": []}
    result = to_gap_result(raw, [10000032])
    assert result.per_character[10000032] == result.total


def test_to_gap_result_count_mismatch_fails():
    with pytest.raises(HoyolabError):
        to_gap_result(load_fixture("calculator_batch.json"), [1, 2, 3])
```

- [ ] **Step 3: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_hoyolab.py -q`
Expected: FAIL — `ImportError: cannot import name 'GapCharacter'`

- [ ] **Step 4: Implement in `backend/app/sync/hoyolab.py`**

Change `from typing import ...` to include `Mapping`. Update dataclasses and mappers:

```python
@dataclass(frozen=True)
class WeaponInfo:
    name: str
    icon: str
    rarity: int
    level: int
    refinement: int
    id: int = 0


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
    weekly_discounts_left: int | None = None
    weekly_discounts_max: int | None = None
```

```python
def _weapon(w: Any) -> WeaponInfo:
    return WeaponInfo(name=w.name, icon=w.icon, rarity=int(w.rarity), level=int(w.level),
                      refinement=int(w.refinement), id=int(getattr(w, "id", 0) or 0))
```

In `to_notes`, add the two keyword arguments:

```python
        weekly_discounts_left=_opt_int(getattr(n, "remaining_resin_discounts", None)),
        weekly_discounts_max=_opt_int(getattr(n, "max_resin_discounts", None)),
```

with helper `def _opt_int(v: Any) -> int | None: return None if v is None else int(v)`.

Add the new types and pure mappers (after `to_account`):

```python
class NoInventoryData(HoyolabError):
    pass


@dataclass(frozen=True)
class TalentIds:
    normal: int
    skill: int
    burst: int


@dataclass(frozen=True)
class GapCharacter:
    character_id: int
    level_current: int
    level_target: int
    talents: tuple[tuple[int, int, int], ...]
    weapon: tuple[int, int, int] | None


@dataclass(frozen=True)
class MaterialAmount:
    id: int
    name: str
    icon: str
    rarity: int
    need: int
    short: int


@dataclass(frozen=True)
class GapResult:
    per_character: dict[int, list[MaterialAmount]]
    total: list[MaterialAmount]
    spare: list[MaterialAmount]


def to_talent_ids(items: Sequence[Mapping]) -> TalentIds:
    upgradeable = [i for i in items if int(i.get("max_level", 1) or 1) > 1]
    if len(upgradeable) > 3:  # alternate sprint (group id order digit 3) sits between skill and burst
        upgradeable = [i for i in upgradeable if int(i["group_id"]) % 10 != 3]
    if len(upgradeable) < 3:
        raise HoyolabError("Unexpected talent list from HoYoLAB.")
    return TalentIds(int(upgradeable[0]["group_id"]), int(upgradeable[1]["group_id"]),
                     int(upgradeable[-1]["group_id"]))


def build_batch_body(chars: Sequence[GapCharacter], uid: int, region: str) -> dict:
    items = []
    for c in chars:
        item: dict[str, Any] = {
            "avatar_id": c.character_id,
            "avatar_level_current": c.level_current,
            "avatar_level_target": c.level_target,
            "skill_list": [{"id": g, "level_current": cur, "level_target": tgt} for g, cur, tgt in c.talents],
        }
        if c.weapon is not None:
            wid, cur, tgt = c.weapon
            item["weapon"] = {"id": wid, "level_current": cur, "level_target": tgt}
        items.append(item)
    return {"items": items, "uid": uid, "region": region}


def _amount(m: Mapping) -> MaterialAmount:
    return MaterialAmount(id=int(m["id"]), name=str(m.get("name") or ""), icon=str(m.get("icon") or ""),
                          rarity=int(m.get("level") or 0), need=int(m.get("num") or 0),
                          short=int(m.get("lack_num") or 0))


def to_gap_result(raw: Mapping, character_ids: list[int]) -> GapResult:
    if not raw.get("has_user_info"):
        raise NoInventoryData("HoYoLAB returned no inventory data.")
    total = [_amount(m) for m in raw.get("overall_consume") or []]
    singles = list(raw.get("single_role_result") or [])
    if not singles and len(character_ids) == 1:
        per = {character_ids[0]: total}
    elif len(singles) != len(character_ids):
        raise HoyolabError(f"Calculator returned {len(singles)} results for {len(character_ids)} characters.")
    else:
        per = {cid: [_amount(m) for m in s.get("overall_consume") or []] for cid, s in zip(character_ids, singles)}
    return GapResult(per_character=per, total=total,
                     spare=[_amount(m) for m in raw.get("available_material") or []])
```

Extend the protocol and `GenshinPySource`:

```python
class HoyolabSource(Protocol):
    async def get_roster(self) -> list[RosterEntry]: ...
    async def get_details(self, raw_ids: Sequence[int]) -> list[DetailEntry]: ...
    async def get_notes(self) -> NotesInfo: ...
    async def get_talent_ids(self, character_id: int) -> TalentIds: ...
    async def compute_gaps(self, chars: Sequence[GapCharacter]) -> GapResult: ...
```

```python
class GenshinPySource:
    def __init__(self, cookies: dict[str, str], uid: int, delays: Sequence[float] = RETRY_DELAYS,
                 *, region: str | None = None):
        self._client = genshin.Client(cookies, game=genshin.Game.GENSHIN, uid=uid)
        self._uid = uid
        self._region = region or genshin.utility.recognize_genshin_server(uid)
        self._delays = delays

    # get_roster / get_details / get_notes unchanged

    async def get_talent_ids(self, character_id: int) -> TalentIds:
        data = await call_api(self._client.request_calculator, "avatarSkill/list", method="GET",
                              params={"avatar_id": character_id}, delays=self._delays)
        return to_talent_ids(data.get("list") or [])

    async def compute_gaps(self, chars: Sequence[GapCharacter]) -> GapResult:
        body = build_batch_body(chars, self._uid, self._region)
        raw = await call_api(self._client.request_calculator, "batch_compute", data=body,
                             api_version=3, delays=self._delays)
        return to_gap_result(raw, [c.character_id for c in chars])
```

- [ ] **Step 5: Pass the region from `.env`**

In `backend/app/context.py` change the return line of `factory()` to:

```python
        return GenshinPySource(cookies, int(env["GENSHIN_UID"]), region=env.get("GENSHIN_REGION"))
```

In `backend/app/smoke.py` change the constructor call to `GenshinPySource(cookies_from_env(env), int(env["GENSHIN_UID"]), region=env.get("GENSHIN_REGION"))`.

- [ ] **Step 6: Extend `FakeSource`** in `backend/tests/fakes.py`

Add imports `GapResult, MaterialAmount, TalentIds` from `app.sync.hoyolab`, give `__init__` a `gaps=None` parameter stored as `self.gaps`, and add:

```python
    async def get_talent_ids(self, character_id):
        self.calls.append(("talents", character_id))
        if "talents" in self.fail:
            raise self.fail["talents"]
        return TalentIds(character_id * 10 + 1, character_id * 10 + 2, character_id * 10 + 9)

    async def compute_gaps(self, chars):
        self.calls.append(("gaps", tuple(c.character_id for c in chars)))
        if "gaps" in self.fail:
            raise self.fail["gaps"]
        if self.gaps is not None:
            return self.gaps
        guide = MaterialAmount(104302, "Guide to Freedom", "", 3, 9, 4)
        return GapResult(per_character={c.character_id: [guide] for c in chars},
                         total=[MaterialAmount(104302, "Guide to Freedom", "", 3, 9 * len(chars), 4 * len(chars))],
                         spare=[])
```

- [ ] **Step 7: Run to verify pass**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add backend/app/sync/hoyolab.py backend/app/context.py backend/app/smoke.py backend/tests/fakes.py backend/tests/test_hoyolab.py backend/tests/fixtures/calculator_batch.json
git commit -m "feat: batch calculator, talent ids and weekly discounts in the HoYoLAB wrapper"
```

---

### Task 6: Calculator inputs and gap persistence

**Files:**
- Create: `backend/app/planner/__init__.py` (empty), `backend/app/planner/requests.py`
- Modify: `backend/app/sync/persist.py`
- Test: `backend/tests/test_requests.py`, `backend/tests/test_persist.py`

**Interfaces:**
- Consumes: `GapCharacter`, `GapResult`, `TalentIds`, `MaterialAmount` (Task 5); models (Task 3); `Targets` from `app.domain`; `TRAVELER_ID`, `MANEKIN_ID` from `app.gamedata.yatta`.
- Produces:
  - `planner.requests.UNSUPPORTED: dict[int, str]` (`{10000005: "Traveler", 10000117: "Manekin"}`)
  - `PlanInput(character_id: int, name: str, level: int, talents: tuple[int, int, int], targets: Targets, weapon: tuple[int, int] | None)` — weapon is `(weapon_id, current_level)`
  - `build_inputs(session) -> tuple[list[PlanInput], list[str]]` (inputs, skipped names)
  - `has_work(i: PlanInput) -> bool`
  - `snapshot(session) -> list[list]`
  - `gap_requests(inputs: list[PlanInput], talent_ids: dict[int, TalentIds]) -> list[GapCharacter]`
  - `persist.save_roster`/`save_details` store `weapon_id`; `save_notes` stores weekly discounts
  - `persist.save_gaps(session, result: GapResult | None, snapshot: list, skipped: list[str], now) -> set[int]` (material ids not in `game_material`)
  - `persist.save_gap_failure(session, error: str, now) -> None`
  - `persist.load_talent_ids(session) -> dict[int, TalentIds]`, `persist.save_talent_ids(session, ids: dict[int, TalentIds]) -> None` (stored in `game_meta["talent_ids"]`)

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_requests.py
from app.db.models import CharacterGoal
from app.planner.requests import build_inputs, gap_requests, has_work, snapshot
from app.sync.hoyolab import TalentIds
from app.sync.persist import save_details, save_roster
from app.timeutil import utcnow
from fakes import make_detail, make_roster
from helpers import seed_game


def goal(cid, level=90, talents=(8, 8, 8), weapon_level=90, planned=None):
    return CharacterGoal(character_id=cid, goal="build", target_level=level, target_normal=talents[0],
                         target_skill=talents[1], target_burst=talents[2], target_weapon_level=weapon_level,
                         planned_weapon_id=planned, updated_at=utcnow())


def setup(session_factory, goals):
    seed_game(session_factory)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032, level=80, name="Bennett"),
                        make_roster(10000005, raw_id=10000007, name="Traveler")], utcnow())
        save_details(s, [make_detail(10000032, talents=(6, 8, 8))])
        for g in goals:
            s.add(g)


def test_owned_prefarm_and_unsupported(session_factory):
    setup(session_factory, [goal(10000032), goal(10000073), goal(10000005)])
    with session_factory() as s:
        inputs, skipped = build_inputs(s)
    by_id = {i.character_id: i for i in inputs}
    assert skipped == ["Traveler"]
    assert set(by_id) == {10000032, 10000073}
    bennett, nahida = by_id[10000032], by_id[10000073]
    assert (bennett.level, bennett.talents) == (80, (6, 8, 8))
    assert bennett.weapon == (1, 90)             # equipped weapon id from the fake roster (WEAPON.id == 1)
    assert (nahida.level, nahida.talents, nahida.weapon) == (1, (1, 1, 1), None)


def test_planned_weapon_starts_at_level_1(session_factory):
    setup(session_factory, [goal(10000032, planned=11509), goal(10000073, planned=13407)])
    with session_factory() as s:
        by_id = {i.character_id: i for i in build_inputs(s)[0]}
    assert by_id[10000032].weapon == (11509, 1)
    assert by_id[10000073].weapon == (13407, 1)


def test_planned_weapon_equal_to_equipped_keeps_current_level(session_factory):
    setup(session_factory, [goal(10000032, planned=1)])
    with session_factory() as s:
        assert build_inputs(s)[0][0].weapon == (1, 90)


def test_fully_built_character_has_no_work_and_no_request(session_factory):
    setup(session_factory, [goal(10000032, level=80, talents=(6, 8, 8), weapon_level=90)])
    with session_factory() as s:
        inputs, _ = build_inputs(s)
    assert has_work(inputs[0]) is False
    assert gap_requests([i for i in inputs if has_work(i)], {}) == []


def test_gap_requests_only_raise_parts_below_target(session_factory):
    setup(session_factory, [goal(10000032, level=90, talents=(9, 8, 10), weapon_level=90)])
    with session_factory() as s:
        inputs, _ = build_inputs(s)
    (req,) = gap_requests(inputs, {10000032: TalentIds(3201, 3202, 3209)})
    assert (req.level_current, req.level_target) == (80, 90)
    assert req.talents == ((3201, 6, 9), (3209, 8, 10))
    assert req.weapon is None                     # weapon already at target


def test_snapshot_changes_with_targets(session_factory):
    setup(session_factory, [goal(10000032)])
    with session_factory() as s:
        before = snapshot(s)
    with session_factory.begin() as s:
        s.get(CharacterGoal, 10000032).target_skill = 10
    with session_factory() as s:
        assert snapshot(s) != before
```

Append to `backend/tests/test_persist.py` (add imports `from app.db.models import GameMaterial, GapRun, LiveNotes, MaterialGap, MaterialTotal, OwnedCharacter` and `from app.sync.hoyolab import GapResult, MaterialAmount, NotesInfo, TalentIds` and `from app.sync.persist import load_talent_ids, save_gap_failure, save_gaps, save_notes, save_talent_ids, save_roster` as needed):

```python
def _catalogue(sf, ids):
    with sf.begin() as s:
        for mid in ids:
            s.add(GameMaterial(id=mid, name=f"M{mid}", icon=f"UI_ItemIcon_{mid}", rarity=3, yatta_type="x",
                               category="talent", sources=[], sort_order=0, detail_fetched=True))


def _result():
    a = MaterialAmount(104302, "Guide to Freedom", "https://act-webstatic.hoyoverse.com/g.png", 3, 9, 4)
    new = MaterialAmount(999001, "Brand New", "https://act-webstatic.hoyoverse.com/n.png", 4, 3, 3)
    spare = MaterialAmount(104301, "Teachings of Freedom", "", 2, 10, 0)
    return GapResult(per_character={10000032: [a], 10000089: [a, new]},
                     total=[MaterialAmount(104302, "Guide to Freedom", "", 3, 18, 7), new], spare=[spare])


def test_save_gaps_replaces_rows_and_reports_unknown_ids(session_factory):
    _catalogue(session_factory, [104301, 104302])
    with session_factory.begin() as s:
        unknown = save_gaps(s, _result(), [[10000032]], ["Traveler"], datetime(2026, 11, 19, 12))
    assert unknown == {999001}
    with session_factory() as s:
        assert s.get(MaterialGap, (10000089, 999001)).short == 3
        total = s.get(MaterialTotal, 104302)
        assert (total.need, total.short, total.spare) == (18, 7, 0)
        assert s.get(MaterialTotal, 104301).spare == 10        # spare-only material kept
        run = s.get(GapRun, 1)
        assert run.ok and run.snapshot == [[10000032]] and run.skipped == ["Traveler"]
    with session_factory.begin() as s:
        save_gaps(s, None, [], [], datetime(2026, 11, 19, 13))
    with session_factory() as s:
        assert s.query(MaterialGap).count() == 0 and s.query(MaterialTotal).count() == 0


def test_save_gap_failure_keeps_last_rows_and_snapshot(session_factory):
    with session_factory.begin() as s:
        save_gaps(s, _result(), [[1]], [], datetime(2026, 11, 19, 12))
    with session_factory.begin() as s:
        save_gap_failure(s, "NoInventoryData: no data", datetime(2026, 11, 19, 13))
    with session_factory() as s:
        run = s.get(GapRun, 1)
        assert run.ok is False and run.error == "NoInventoryData: no data"
        assert run.snapshot == [[1]] and run.computed_at == datetime(2026, 11, 19, 12)
        assert s.query(MaterialTotal).count() > 0


def test_roster_stores_weapon_id_and_notes_store_discounts(session_factory):
    seed_game(session_factory)
    now = datetime(2026, 11, 19, 12)
    notes = NotesInfo(10, 200, 0, 4, 4, 0, 2400, [], weekly_discounts_left=2, weekly_discounts_max=3)
    with session_factory.begin() as s:
        save_roster(s, [make_roster(10000032)], now)
        save_notes(s, notes, now)
    with session_factory() as s:
        assert s.get(OwnedCharacter, 10000032).weapon_id == 1
        assert s.get(LiveNotes, 1).weekly_discounts_left == 2


def test_talent_id_cache_round_trip(session_factory):
    with session_factory.begin() as s:
        save_talent_ids(s, {10000032: TalentIds(1, 2, 9)})
    with session_factory() as s:
        assert load_talent_ids(s) == {10000032: TalentIds(1, 2, 9)}
```

Note: `fakes.WEAPON` has no id; for `weapon_id == 1` in the tests above, change `fakes.WEAPON` to `WeaponInfo("The Flute", "https://act-webstatic.hoyoverse.com/w.png", 4, 90, 5, 1)`.

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_requests.py tests/test_persist.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.planner'`

- [ ] **Step 3: Implement `backend/app/planner/requests.py`**

```python
"""Turn Build goals plus synced account data into calculator requests."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CharacterGoal, GameCharacter, OwnedCharacter
from app.domain import Targets
from app.gamedata.yatta import MANEKIN_ID, TRAVELER_ID
from app.sync.hoyolab import GapCharacter, TalentIds

UNSUPPORTED = {TRAVELER_ID: "Traveler", MANEKIN_ID: "Manekin"}


@dataclass(frozen=True)
class PlanInput:
    character_id: int
    name: str
    level: int
    talents: tuple[int, int, int]
    targets: Targets
    weapon: tuple[int, int] | None


def _build_rows(session: Session) -> list[CharacterGoal]:
    rows = session.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")
                           .order_by(CharacterGoal.character_id))
    return [r for r in rows if r.target_level is not None]


def build_inputs(session: Session) -> tuple[list[PlanInput], list[str]]:
    inputs: list[PlanInput] = []
    skipped: list[str] = []
    for row in _build_rows(session):
        cid = row.character_id
        g = session.get(GameCharacter, cid)
        o = session.get(OwnedCharacter, cid)
        if g is None and o is None:
            continue
        if cid in UNSUPPORTED:
            skipped.append(UNSUPPORTED[cid])
            continue
        targets = Targets(row.target_level, row.target_normal, row.target_skill, row.target_burst,
                          row.target_weapon_level)
        level = o.level if o is not None else 1
        talents = ((o.talent_normal or 1, o.talent_skill or 1, o.talent_burst or 1) if o is not None else (1, 1, 1))
        weapon: tuple[int, int] | None = None
        equipped = o.weapon_id if o is not None else None
        if row.planned_weapon_id is not None and row.planned_weapon_id != equipped:
            weapon = (row.planned_weapon_id, 1)
        elif equipped:
            weapon = (equipped, o.weapon_level)
        inputs.append(PlanInput(cid, g.name if g is not None else o.name, level, talents, targets, weapon))
    return inputs, skipped


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
        out.append(GapCharacter(i.character_id, i.level, max(i.level, t.level), talents, weapon))
    return out
```

- [ ] **Step 4: Implement the persistence functions** in `backend/app/sync/persist.py`

Add `weapon_id` lines: in `save_roster` after `row.weapon_refinement = ...` add `row.weapon_id = e.weapon.id or None`; in `save_details` likewise `row.weapon_id = d.weapon.id or None`. In `save_notes` add:

```python
    row.weekly_discounts_left = notes.weekly_discounts_left
    row.weekly_discounts_max = notes.weekly_discounts_max
```

Extend imports (`GameMaterial, GameMeta, GapRun, MaterialGap, MaterialTotal`; `GapResult, MaterialAmount, TalentIds`), then add:

```python
TALENT_META = "talent_ids"


def save_gaps(session: Session, result: GapResult | None, snapshot: list, skipped: list[str],
              now: datetime) -> set[int]:
    """Replace gap rows with a successful result (None = nothing to calculate). Returns unknown ids."""
    session.execute(delete(MaterialGap))
    session.execute(delete(MaterialTotal))
    seen: set[int] = set()
    if result is not None:
        for cid, mats in result.per_character.items():
            merged: dict[int, list[int]] = {}
            for m in mats:
                acc = merged.setdefault(m.id, [0, 0])
                acc[0] += m.need
                acc[1] += m.short
            for mid, (need, short) in merged.items():
                if need > 0 or short > 0:
                    session.add(MaterialGap(character_id=cid, material_id=mid, need=need, short=short))
        spare: dict[int, MaterialAmount] = {m.id: m for m in result.spare}
        for m in result.total:
            extra = spare.pop(m.id, None)
            session.add(MaterialTotal(material_id=m.id, name=m.name, icon=m.icon, rarity=m.rarity,
                                      need=m.need, short=m.short, spare=extra.need if extra else 0))
            seen.add(m.id)
        for m in spare.values():
            session.add(MaterialTotal(material_id=m.id, name=m.name, icon=m.icon, rarity=m.rarity,
                                      need=0, short=0, spare=m.need))
            seen.add(m.id)
    run = session.get(GapRun, 1) or GapRun(id=1)
    run.computed_at, run.snapshot, run.ok, run.error, run.skipped = now, snapshot, True, None, list(skipped)
    session.merge(run)
    session.flush()
    known = set(session.scalars(select(GameMaterial.id)))
    return seen - known


def save_gap_failure(session: Session, error: str, now: datetime) -> None:
    run = session.get(GapRun, 1)
    if run is None:
        run = GapRun(id=1, computed_at=None, snapshot=None, skipped=[])
        session.add(run)
    run.ok = False
    run.error = error[:300]
    session.flush()


def load_talent_ids(session: Session) -> dict[int, TalentIds]:
    row = session.get(GameMeta, TALENT_META)
    return {int(k): TalentIds(*v) for k, v in (row.value or {}).items()} if row else {}


def save_talent_ids(session: Session, ids: dict[int, TalentIds]) -> None:
    session.merge(GameMeta(key=TALENT_META,
                           value={str(k): [v.normal, v.skill, v.burst] for k, v in sorted(ids.items())}))
    session.flush()
```

(`now` is unused in `save_gap_failure` by design: `computed_at` keeps the last success time. Keep the parameter for a uniform call site.)

- [ ] **Step 5: Run to verify pass**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/planner backend/app/sync/persist.py backend/tests/test_requests.py backend/tests/test_persist.py backend/tests/fakes.py
git commit -m "feat: calculator inputs from goals and gap persistence"
```

---

### Task 7: Live verification checkpoint (smoke `--gaps`)

**Files:**
- Modify: `backend/app/smoke.py`, `backend/app/config.py`
- Create: `docs/superpowers/notes/2026-11-19-phase2-calculator-findings.md`

**Interfaces:**
- Consumes: `build_inputs`, `has_work`, `gap_requests` (Task 6); `GenshinPySource.get_talent_ids`, `compute_gaps`, `build_batch_body` (Task 5).
- Produces: `config.LACK_INCLUDES_CRAFTING: bool` (default `False`; set from the finding).

This task touches the user's real account through `.env`. It prints counts, ids, and names only — never cookie values, UID, or nickname.

- [ ] **Step 1: Add the config flag** to `backend/app/config.py`

```python
GAPS_DEBOUNCE_SECONDS = 3.0
# Set from the phase 2 live check (docs/superpowers/notes/2026-11-19-phase2-calculator-findings.md):
# True if HoYoLAB's lack_num already subtracts what can be crafted from spare lower tiers.
LACK_INCLUDES_CRAFTING = False
```

- [ ] **Step 2: Add `--gaps` to `backend/app/smoke.py`**

```python
"""Live check against your real account (manual, never in CI):
python -m app.smoke          roster/details/notes
python -m app.smoke --gaps   calculator checks for phase 2 (uses your Build goals from data/tracker.db)"""
import asyncio
import sys

from sqlalchemy import select

from app.config import default_paths
from app.db.engine import make_engine, make_session_factory, migrate
from app.db.models import GameMaterial
from app.planner.requests import build_inputs, gap_requests, has_work
from app.settings.envfile import cookies_from_env, read_env
from app.sync.hoyolab import GenshinPySource


async def basic(source: GenshinPySource) -> None:
    roster = await source.get_roster()
    print(f"roster: {len(roster)} characters")
    details = await source.get_details([r.raw_id for r in roster[:3]])
    for d in details:
        print(f"  {d.id}: talents {d.normal}/{d.skill}/{d.burst}, artifacts {len(d.artifacts)}, stats {len(d.stats)}")
    notes = await source.get_notes()
    print(f"notes: resin {notes.resin}/{notes.resin_max}, commissions "
          f"{notes.commissions_done}/{notes.commissions_max}, expeditions {len(notes.expeditions)}, "
          f"weekly discounts {notes.weekly_discounts_left}/{notes.weekly_discounts_max}")


async def gaps(source: GenshinPySource) -> None:
    paths = default_paths()
    engine = make_engine(paths.db_file)
    migrate(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        inputs, skipped = build_inputs(s)
        catalogue = set(s.scalars(select(GameMaterial.id)))
    work = [i for i in inputs if has_work(i)]
    print(f"build characters: {len(inputs)} ({len(work)} with work), skipped: {skipped}")
    if not work:
        sys.exit("Set at least one owned character to Build with targets above current, then rerun.")
    talent_ids = {i.character_id: await source.get_talent_ids(i.character_id) for i in work}
    print("check 0 (talent ids):", {k: (v.normal, v.skill, v.burst) for k, v in talent_ids.items()})
    requests = gap_requests(work, talent_ids)
    print(f"check 2 (character limit): sending {len(requests)} characters in one request")
    result = await source.compute_gaps(requests)
    print(f"  per-character results: {len(result.per_character)} / {len(requests)}")
    print("check 1/5 (crafting, spare): available_material entries:")
    for m in result.spare:
        print(f"  spare {m.id} {m.name} r{m.rarity}: num={m.need}")
    print("totals (id, name, rarity, need, short, in catalogue):")
    for m in result.total:
        print(f"  {m.id} {m.name} r{m.rarity}: need {m.need} short {m.short} {'yes' if m.id in catalogue else 'NO'}")
    weapons = [r for r in requests if r.weapon is not None]
    print(f"check 3 (weapons): {len(weapons)} requests had a weapon part: "
          f"{[(r.character_id, r.weapon) for r in weapons]}")
    print("check 4 (ascension at caps): characters at a cap level:",
          [(i.character_id, i.level) for i in work if i.level in (20, 40, 50, 60, 70, 80)])
    engine.dispose()


async def main() -> None:
    env = read_env(default_paths().env_file)
    if not env.get("GENSHIN_UID"):
        sys.exit("Connect from the app's Settings page first (GENSHIN_UID missing in .env).")
    source = GenshinPySource(cookies_from_env(env), int(env["GENSHIN_UID"]), region=env.get("GENSHIN_REGION"))
    await (gaps(source) if "--gaps" in sys.argv else basic(source))


if __name__ == "__main__":
    asyncio.run(main())
```

- [ ] **Step 3: Prepare the account data**

Start the app (`python run.py`), let a sync finish, open Settings → "Refresh game data" so the material catalogue exists, and make sure at least two characters are set to **Build** with targets above their current levels — ideally one owned character at a level cap such as 80 and one pre-farming character — and give one owned character a planned weapon above its current level. If the user's account has no suitable characters set to Build, ask the user which ones to use.

- [ ] **Step 4: Run the live check**

Run: `cd backend; ..\.venv\Scripts\python -m app.smoke --gaps`
Expected: prints talent ids, per-character results equal to the request count, totals with `short` values that are not all equal to `need`, and spare entries.

If it fails with `NoInventoryData` ("HoYoLAB returned no inventory data"): in `build_batch_body` also add `"uid": uid, "region": region` to every item dict, update `test_build_batch_body_includes_uid_region_and_only_given_parts` to expect them, and rerun.
If `get_talent_ids` fails: stop and report the error to the user (the endpoint name `avatarSkill/list` needs replacing).

- [ ] **Step 5: Decide each check and record it**

Write `docs/superpowers/notes/2026-11-19-phase2-calculator-findings.md` with one short paragraph per check (counts, ids and material names only; no UID, nickname, or cookie data):

1. **Crafting in `lack_num`:** compare a short higher-tier book with the spare lower tier you know you hold in-game. If `short` is already reduced by what crafting covers, set `LACK_INCLUDES_CRAFTING = True` in `config.py`.
2. **Character limit:** if per-character results < requests or HoYoLAB errors for many characters, **stop and ask the user** (spec §5.4 says the spec gets amended).
3. **Weapons:** if the planned/equipped weapon requests produce no weapon materials (e.g. no weapon ascension materials in totals although the weapon is below target), **stop and ask the user** whether to drop planned weapons from phase 2.
4. **Ascension at caps:** note whether a level-80 character's need includes the 80→90 ascension gems; record the assumption for the README (Task 17).
5. **`available_material`:** confirm `num` is the spare count; if entries are absent or meaningless, leave `spare` as is (the rollup then shows no craft hints) and note it.

Also confirm every total id shows `in catalogue: yes` except genuinely new items; if many are `NO`, the HoYoLAB and Yatta ids differ — **stop and ask the user**.

- [ ] **Step 6: Run the backend suite and commit**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q` → all pass.

Before committing, read the findings file and confirm it contains no UID, nickname, or cookie value.

```bash
git add backend/app/smoke.py backend/app/config.py backend/app/sync/hoyolab.py backend/tests/test_hoyolab.py docs/superpowers/notes/2026-11-19-phase2-calculator-findings.md
git commit -m "chore: live calculator checks for phase 2 and recorded findings"
```

---

### Task 8: Sync runner — gaps part, gaps-only runs, debounce

**Files:**
- Modify: `backend/app/sync/runner.py`, `backend/app/main.py`
- Test: `backend/tests/test_sync_runner.py` (new tests + update exact `parts` dicts in existing tests to include `"gaps"`)

**Interfaces:**
- Consumes: Task 5 source methods; Task 6 `build_inputs`, `has_work`, `gap_requests`, `snapshot`, `save_gaps`, `save_gap_failure`, `load_talent_ids`, `save_talent_ids`; `config.GAPS_DEBOUNCE_SECONDS`.
- Produces on `SyncManager`:
  - constructor kwarg `gaps_delay: float = GAPS_DEBOUNCE_SECONDS`
  - `schedule_gaps() -> None` (must be called from inside the running event loop)
  - `start_gaps() -> SyncRequestResult` (sync; reasons `"started"`, `"queued"`, `"not_connected"`)
  - `gaps_pending: bool` property (timer waiting or run queued)
  - `wait()` now also waits for a pending timer and queued gaps runs
  - `PARTS = ("roster", "details", "notes", "gaps")`; gaps-only runs have trigger `"gaps"` and only a `"gaps"` part
  - `request()` ignores `gaps` runs for the 60 s manual limit and the auto "recent" check

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_sync_runner.py`; add imports `from app.db.models import CharacterGoal, GapRun, MaterialTotal` and `from app.sync.hoyolab import NoInventoryData`, `from app.timeutil import utcnow`)

```python
def build_goal(session_factory, cid, skill=8):
    with session_factory.begin() as s:
        s.merge(CharacterGoal(character_id=cid, goal="build", target_level=90, target_normal=8,
                              target_skill=skill, target_burst=8, target_weapon_level=90, updated_at=utcnow()))


async def test_full_sync_runs_gaps_part(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    source = FakeSource()
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    assert last_run(session_factory).parts["gaps"] == {"ok": True, "count": 1}
    assert ("talents", 10000032) in source.calls and ("gaps", (10000032,)) in source.calls
    with session_factory() as s:
        assert s.get(MaterialTotal, 104302).short == 4
        assert s.get(GapRun, 1).ok is True


async def test_gaps_failure_is_isolated_and_recorded(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    m = manager(paths, session_factory, FakeSource(fail={"gaps": NoInventoryData("HoYoLAB returned no inventory data.")}))
    await m.request("manual")
    await m.wait()
    parts = last_run(session_factory).parts
    assert parts["gaps"]["ok"] is False and "no inventory data" in parts["gaps"]["error"]
    assert parts["roster"]["ok"] and parts["notes"]["ok"]
    with session_factory() as s:
        assert s.get(GapRun, 1).ok is False


async def test_traveler_is_skipped_but_others_calculated(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    build_goal(session_factory, 10000005)
    source = FakeSource(roster=[make_roster(10000032, name="Bennett"),
                                make_roster(10000005, raw_id=10000007, name="Traveler")])
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    assert last_run(session_factory).parts["gaps"] == {"ok": True, "count": 1, "skipped": ["Traveler"]}
    assert ("gaps", (10000032,)) in source.calls


async def test_no_work_skips_calculator_call(paths, session_factory):
    seed_game(session_factory)
    source = FakeSource()
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    assert last_run(session_factory).parts["gaps"] == {"ok": True, "count": 0}
    assert not any(isinstance(c, tuple) and c[0] == "gaps" for c in source.calls)


async def test_talent_ids_are_cached(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    clock = Clock(START)
    source = FakeSource()
    m = manager(paths, session_factory, source, clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(minutes=2)
    await m.request("manual")
    await m.wait()
    assert source.calls.count(("talents", 10000032)) == 1


async def test_schedule_gaps_debounces_edits(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    source = FakeSource()
    m = SyncManager(session_factory, paths.db_file, paths.backups, lambda: source,
                    lambda ids: asyncio.sleep(0), clock=Clock(START), gaps_delay=0.05)
    m.schedule_gaps()
    m.schedule_gaps()
    m.schedule_gaps()
    assert m.gaps_pending
    await m.wait()
    gap_calls = [c for c in source.calls if isinstance(c, tuple) and c[0] == "gaps"]
    assert len(gap_calls) == 1
    run = last_run(session_factory)
    assert run.trigger == "gaps" and set(run.parts) == {"gaps"}
    assert "roster" not in source.calls                   # gaps-only run touches nothing else
    assert not m.gaps_pending


async def test_gaps_request_during_full_sync_is_queued_once(paths, session_factory):
    seed_game(session_factory)
    build_goal(session_factory, 10000032)
    gate = asyncio.Event()
    source = FakeSource(gate=gate)
    m = manager(paths, session_factory, source)
    await m.request("manual")
    assert m.start_gaps().reason == "queued"
    assert m.start_gaps().reason == "queued"
    gate.set()
    await m.wait()
    gap_calls = [c for c in source.calls if isinstance(c, tuple) and c[0] == "gaps"]
    assert len(gap_calls) == 2                            # one inside the full sync, one queued run
    assert last_run(session_factory).trigger == "gaps"


async def test_gaps_runs_do_not_count_for_manual_limit(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(), clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(seconds=61)
    m.start_gaps()
    await m.wait()
    result = await m.request("manual")                    # last non-gaps run is 61 s old
    assert result.started


async def test_start_gaps_not_connected(paths, session_factory):
    m = manager(paths, session_factory, None)
    assert m.start_gaps().reason == "not_connected"
```

Update existing exact assertions: in `test_full_sync_saves_everything` the expected dict gains `"gaps": {"ok": True, "count": 0}`; any test asserting all parts after a roster failure expects `"gaps": {"ok": False, "error": "skipped: roster failed"}`; expired-cookie tests expect `"gaps"` with the expired message (added automatically by `PARTS`).

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_sync_runner.py -q`
Expected: FAIL — `KeyError: 'gaps'` / `AttributeError: 'SyncManager' object has no attribute 'schedule_gaps'`

- [ ] **Step 3: Implement in `backend/app/sync/runner.py`**

Imports: add `from app.config import GAPS_DEBOUNCE_SECONDS, MANUAL_SYNC_MIN_SECONDS`, `from app.planner.requests import build_inputs, gap_requests, has_work, snapshot`, `from app.sync.persist import load_talent_ids, save_gap_failure, save_gaps, save_talent_ids` (keep existing persist imports), and `HoyolabSource` already imported.

```python
PARTS = ("roster", "details", "notes", "gaps")
```

Constructor additions:

```python
    def __init__(self, session_factory: sessionmaker, db_file: Path, backups_dir: Path,
                 source_factory: Callable[[], HoyolabSource | None],
                 on_unknown_ids: Callable[[set[int]], Awaitable[None]],
                 clock: Callable[[], datetime] = utcnow, gaps_delay: float = GAPS_DEBOUNCE_SECONDS):
        ...existing assignments...
        self._gaps_delay = gaps_delay
        self._gaps_timer: asyncio.Task | None = None
        self._gaps_queued = False
```

In `request()`, change the "last run" query so gaps runs are ignored:

```python
            last = s.scalars(select(SyncRun).where(SyncRun.trigger != "gaps")
                             .order_by(SyncRun.id.desc()).limit(1)).first()
```

and after creating the task add `self._task.add_done_callback(self._on_task_done)`.

New members:

```python
    @property
    def gaps_pending(self) -> bool:
        timer = self._gaps_timer is not None and not self._gaps_timer.done()
        return timer or self._gaps_queued

    async def wait(self) -> None:
        while True:
            if self._gaps_timer is not None and not self._gaps_timer.done():
                await self._gaps_timer
                continue
            if self._task is not None and not self._task.done():
                await self._task
                await asyncio.sleep(0)  # let the done callback start a queued gaps run
                continue
            return

    def schedule_gaps(self) -> None:
        """Recalculate gaps a few seconds after the last edit; later edits restart the timer."""
        if self._gaps_timer is not None and not self._gaps_timer.done():
            self._gaps_timer.cancel()
        self._gaps_timer = asyncio.create_task(self._gaps_after_delay())

    async def _gaps_after_delay(self) -> None:
        await asyncio.sleep(self._gaps_delay)
        self.start_gaps()

    def start_gaps(self) -> SyncRequestResult:
        if self.running:
            self._gaps_queued = True
            return SyncRequestResult(self._run_id, False, "queued")
        source = self._source_factory()
        if source is None:
            return SyncRequestResult(None, False, "not_connected")
        with self._sf.begin() as s:
            run = SyncRun(started_at=self._clock(), trigger="gaps", parts={})
            s.add(run)
            s.flush()
            run_id = run.id
        self._run_id = run_id
        self._task = asyncio.create_task(self._run_gaps_only(run_id, source, self._auth_generation))
        self._task.add_done_callback(self._on_task_done)
        return SyncRequestResult(run_id, True, "started")

    def _on_task_done(self, _task: asyncio.Task) -> None:
        if self._gaps_queued:
            self._gaps_queued = False
            self.start_gaps()

    async def _gaps_part(self, source: HoyolabSource) -> tuple[dict, set[int]]:
        """Raises AuthExpired; any other failure is recorded and returned as a failed part."""
        try:
            with self._sf() as s:
                inputs, skipped = build_inputs(s)
                snap = snapshot(s)
                cache = load_talent_ids(s)
            work = [i for i in inputs if has_work(i)]
            missing = [i.character_id for i in work if i.character_id not in cache]
            for cid in missing:
                cache[cid] = await source.get_talent_ids(cid)
            if missing:
                with self._sf.begin() as s:
                    save_talent_ids(s, cache)
            result = await source.compute_gaps(gap_requests(work, cache)) if work else None
            with self._sf.begin() as s:
                unknown = save_gaps(s, result, snap, skipped, self._clock())
            part: dict = {"ok": True, "count": len(work)}
            if skipped:
                part["skipped"] = skipped
            return part, unknown
        except AuthExpired:
            raise
        except Exception as e:  # isolated like every other part
            log.warning("Sync part gaps failed: %s", type(e).__name__)
            failure = _failure(e)
            with self._sf.begin() as s:
                save_gap_failure(s, failure["error"], self._clock())
            return failure, set()

    async def _run_gaps_only(self, run_id: int, source: HoyolabSource, generation: int) -> None:
        parts: dict[str, dict] = {}
        unknown: set[int] = set()
        try:
            try:
                parts["gaps"], unknown = await self._gaps_part(source)
            except AuthExpired:
                parts["gaps"] = {"ok": False, "error": EXPIRED_MSG}
                if generation == self._auth_generation:
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

In `_run`, after the notes block and before `if expired:`, add:

```python
            if not expired:
                if roster is None:
                    parts["gaps"] = {"ok": False, "error": "skipped: roster failed"}
                else:
                    try:
                        parts["gaps"], gap_unknown = await self._gaps_part(source)
                        unknown |= gap_unknown
                    except AuthExpired:
                        expired = True
```

- [ ] **Step 4: Run to verify pass**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/sync/runner.py backend/tests/test_sync_runner.py
git commit -m "feat: gaps sync part and debounced gaps-only recalculation"
```

---

### Task 9: Planner data, crafting rollup, inventory, gap status

**Files:**
- Create: `backend/app/planner/data.py`, `backend/app/planner/crafting.py`, `backend/app/planner/inventory.py`, `backend/app/planner/status.py`
- Test: `backend/tests/test_planner.py`

**Interfaces:**
- Consumes: models; `CATEGORIES`, `CATEGORY_LABELS` (Task 2); `snapshot`, `UNSUPPORTED` (Task 6); `config.LACK_INCLUDES_CRAFTING`.
- Produces:
  - `data.Material(id, name, icon, rarity, category, craft_from, sources, sort_order)`, `data.Total(need, short, spare)`, `data.CharRef(id, name, slug, icon)`, `data.Domain(id, name, kind, city, weekdays, material_ids)`, `data.PlannerData(materials, totals, gaps, characters, domains, lack_includes_crafting=False)`, `data.load(session) -> PlannerData`, `data.CATEGORY_ORDER` (CATEGORIES + `"other"`)
  - `crafting.Crafted(craftable, to_farm)`, `crafting.chains(materials) -> list[list[int]]`, `crafting.rollup(data) -> dict[int, Crafted]`
  - `inventory.needers(data, material_id) -> list[dict]`, `inventory.material_index(data) -> dict[int, dict]`, `inventory.inventory(data, index) -> list[dict]`
  - `status.gap_status(session, pending: bool, connected: bool) -> dict`
  - Material dict shape (used by every page): `{"id", "name", "icon", "rarity", "category", "state", "need", "short", "have", "craftable", "to_farm", "sources", "characters"}`; `characters` items `{"id", "name", "slug", "icon", "need"}`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_planner.py
from datetime import datetime

from app.db.models import CharacterGoal, GameMaterial, GapRun, MaterialGap, MaterialTotal
from app.planner.crafting import chains, rollup
from app.planner.data import CharRef, Material, PlannerData, Total, load
from app.planner.inventory import inventory, material_index
from app.planner.status import gap_status
from app.timeutil import utcnow
from helpers import seed_game


def mat(mid, category="talent", rarity=3, craft_from=None, sources=(), order=0, name=None):
    return Material(mid, name or f"M{mid}", f"UI_ItemIcon_{mid}", rarity, category, craft_from, list(sources), order)


BOOKS = {1: mat(1, rarity=2, order=1), 2: mat(2, rarity=3, craft_from=1, order=2),
         3: mat(3, rarity=4, craft_from=2, order=3)}


def data(totals, gaps=None, materials=BOOKS, netted=False):
    chars = {10: CharRef(10, "Bennett", "bennett", "UI_AvatarIcon_Bennett"),
             20: CharRef(20, "Furina", "furina", "UI_AvatarIcon_Furina")}
    return PlannerData(materials=dict(materials), totals=totals, gaps=gaps or {}, characters=chars,
                       domains=[], lack_includes_crafting=netted)


def test_chains_follow_craft_from():
    assert chains(BOOKS) == [[1, 2, 3]]


def test_rollup_crafts_from_spare_lower_tiers():
    d = data({1: Total(0, 0, 40), 2: Total(10, 5, 0), 3: Total(6, 2, 0)})
    r = rollup(d)
    assert (r[2].craftable, r[2].to_farm) == (5, 0)     # 40 green -> 13 blue
    assert (r[3].craftable, r[3].to_farm) == (2, 0)     # (13 - 5) // 3 = 2 gold


def test_rollup_partial_and_nothing_spare():
    r = rollup(data({1: Total(0, 0, 7), 2: Total(10, 5, 0), 3: Total(6, 2, 0)}))
    assert (r[2].craftable, r[2].to_farm) == (2, 3)
    assert (r[3].craftable, r[3].to_farm) == (0, 2)
    r = rollup(data({2: Total(10, 5, 0)}))
    assert (r[2].craftable, r[2].to_farm) == (0, 5)


def test_rollup_netted_mode_does_not_subtract_again():
    r = rollup(data({1: Total(0, 0, 40), 2: Total(10, 5, 0)}, netted=True))
    assert (r[2].craftable, r[2].to_farm) == (0, 5)


def test_material_states_and_have():
    idx = material_index(data({2: Total(10, 4, 0), 3: Total(6, 0, 0)},
                              gaps={10: {2: (6, 4)}, 20: {2: (4, 4), 3: (6, 0)}}))
    assert idx[1]["state"] == "unneeded" and idx[1]["have"] is None
    assert idx[2]["state"] == "short" and idx[2]["have"] == 6 and idx[2]["to_farm"] == 4
    assert [c["name"] for c in idx[2]["characters"]] == ["Bennett", "Furina"]
    assert idx[3]["state"] == "met" and idx[3]["need"] == 6


def test_inventory_groups_in_category_order_and_adds_other():
    mats = {**BOOKS, 9: mat(9, category="exp", order=0),
            999: Material(999, "Brand New", "https://x/n.png", 4, "other", None, [], 10**6)}
    d = data({999: Total(3, 3, 0)}, materials=mats)
    cats = inventory(d, material_index(d))
    assert [c["key"] for c in cats] == ["exp", "talent", "other"]
    assert cats[-1]["label"] == "Other" and cats[-1]["materials"][0]["name"] == "Brand New"


def test_load_reads_tables_and_creates_other_for_unknown(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        s.add(GameMaterial(id=2, name="Guide", icon="UI_ItemIcon_2", rarity=3, yatta_type="t", category="talent",
                           craft_from=None, sources=[], sort_order=0, detail_fetched=True))
        s.add(MaterialTotal(material_id=2, name="Guide", icon="", rarity=3, need=9, short=4, spare=0))
        s.add(MaterialTotal(material_id=999, name="Brand New", icon="https://act-webstatic.hoyoverse.com/n.png",
                            rarity=4, need=3, short=3, spare=0))
        s.add(MaterialGap(character_id=10000032, material_id=2, need=9, short=4))
        s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, updated_at=utcnow()))
    with session_factory() as s:
        d = load(s)
    assert d.materials[999].category == "other" and d.materials[999].name == "Brand New"
    assert d.totals[2] == Total(9, 4, 0)
    assert d.gaps == {10000032: {2: (9, 4)}}
    assert d.characters[10000032].slug == "bennett"


def test_gap_status_stale_pending_failed_and_disconnected(session_factory):
    seed_game(session_factory)
    with session_factory() as s:
        assert gap_status(s, pending=False, connected=True)["stale"] is False   # nothing to build
    with session_factory.begin() as s:
        s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, updated_at=utcnow()))
    with session_factory() as s:
        assert gap_status(s, pending=False, connected=True)["stale"] is True    # never calculated
        assert gap_status(s, pending=False, connected=False)["stale"] is False  # cannot calculate
    with session_factory.begin() as s:
        s.add(GapRun(id=1, computed_at=datetime(2026, 11, 19, 12), ok=True, error=None, skipped=[],
                     snapshot=[[10000032, 90, 8, 8, 8, 90, None]]))
    with session_factory() as s:
        st = gap_status(s, pending=False, connected=True)
        assert st["stale"] is False and st["computed_at"] == "2026-11-19T12:00:00Z"
        assert gap_status(s, pending=True, connected=True)["stale"] is True
    with session_factory.begin() as s:
        s.get(GapRun, 1).ok = False
        s.get(GapRun, 1).error = "HoyolabError: down"
    with session_factory() as s:
        st = gap_status(s, pending=False, connected=True)
        assert st["ok"] is False and st["error"] == "HoyolabError: down"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_planner.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.planner.crafting'`

- [ ] **Step 3: Implement `backend/app/planner/data.py`**

```python
"""One read of everything the planner needs. All other planner modules are pure functions over this."""
from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import LACK_INCLUDES_CRAFTING
from app.db.models import (
    CharacterGoal, GameCharacter, GameDomain, GameMaterial, MaterialGap, MaterialTotal, OwnedCharacter,
)
from app.gamedata.materials import CATEGORIES

CATEGORY_ORDER: tuple[str, ...] = (*CATEGORIES, "other")
OTHER_ORDER = 10**6


@dataclass(frozen=True)
class Material:
    id: int
    name: str
    icon: str
    rarity: int
    category: str
    craft_from: int | None
    sources: list = field(default_factory=list)
    sort_order: int = 0


@dataclass(frozen=True)
class Total:
    need: int
    short: int
    spare: int


@dataclass(frozen=True)
class CharRef:
    id: int
    name: str
    slug: str
    icon: str | None

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "slug": self.slug, "icon": self.icon}


@dataclass(frozen=True)
class Domain:
    id: int
    name: str
    kind: str
    city: int | None
    weekdays: list
    material_ids: list


@dataclass
class PlannerData:
    materials: dict[int, Material]
    totals: dict[int, Total]
    gaps: dict[int, dict[int, tuple[int, int]]]
    characters: dict[int, CharRef]
    domains: list[Domain]
    lack_includes_crafting: bool = False


def load(session: Session) -> PlannerData:
    materials = {m.id: Material(m.id, m.name, m.icon, m.rarity, m.category, m.craft_from, list(m.sources or []),
                                m.sort_order) for m in session.scalars(select(GameMaterial))}
    totals: dict[int, Total] = {}
    for t in session.scalars(select(MaterialTotal)):
        totals[t.material_id] = Total(t.need, t.short, t.spare)
        if t.material_id not in materials:
            materials[t.material_id] = Material(t.material_id, t.name or f"Material {t.material_id}", t.icon,
                                                t.rarity, "other", None, [], OTHER_ORDER + t.material_id)
    gaps: dict[int, dict[int, tuple[int, int]]] = {}
    for g in session.scalars(select(MaterialGap)):
        gaps.setdefault(g.character_id, {})[g.material_id] = (g.need, g.short)
        if g.material_id not in materials:
            materials[g.material_id] = Material(g.material_id, f"Material {g.material_id}", "", 0, "other", None,
                                                [], OTHER_ORDER + g.material_id)
    characters: dict[int, CharRef] = {}
    for row in session.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")):
        g = session.get(GameCharacter, row.character_id)
        o = session.get(OwnedCharacter, row.character_id)
        if g is None and o is None:
            continue
        icon = (o.icon if o is not None and o.icon else None) or (g.icon if g is not None else None)
        characters[row.character_id] = CharRef(row.character_id, g.name if g is not None else o.name,
                                               g.slug if g is not None else f"id-{row.character_id}", icon)
    domains = [Domain(d.id, d.name, d.kind, d.city, list(d.weekdays), list(d.material_ids))
               for d in session.scalars(select(GameDomain).order_by(GameDomain.id))]
    return PlannerData(materials, totals, gaps, characters, domains, LACK_INCLUDES_CRAFTING)
```

- [ ] **Step 4: Implement `backend/app/planner/crafting.py`**

```python
"""3 of tier k-1 craft into 1 of tier k. Spare lower tiers reduce what is left to farm."""
from __future__ import annotations

from dataclasses import dataclass

from app.planner.data import Material, PlannerData, Total


@dataclass(frozen=True)
class Crafted:
    craftable: int
    to_farm: int


def chains(materials: dict[int, Material]) -> list[list[int]]:
    up = {m.craft_from: m.id for m in materials.values() if m.craft_from is not None and m.craft_from in materials}
    roots = sorted(mid for mid in up if materials[mid].craft_from not in materials)
    out = []
    for root in roots:
        chain = [root]
        while chain[-1] in up and len(chain) < 10:
            chain.append(up[chain[-1]])
        out.append(chain)
    return out


def rollup(data: PlannerData) -> dict[int, Crafted]:
    result = {mid: Crafted(0, t.short) for mid, t in data.totals.items()}
    if data.lack_includes_crafting:
        return result
    empty = Total(0, 0, 0)
    for chain in chains(data.materials):
        carry = 0  # spare lower-tier items, already converted to this tier's units
        for mid in chain:
            t = data.totals.get(mid, empty)
            craftable = min(t.short, carry)
            if mid in data.totals:
                result[mid] = Crafted(craftable, t.short - craftable)
            carry = (t.spare + carry - craftable) // 3
    return result
```

- [ ] **Step 5: Implement `backend/app/planner/inventory.py`**

```python
"""Material rows for the Inventory grid and every other planner view."""
from __future__ import annotations

from app.gamedata.materials import CATEGORY_LABELS
from app.planner.crafting import Crafted, rollup
from app.planner.data import CATEGORY_ORDER, PlannerData, Total


def needers(data: PlannerData, material_id: int) -> list[dict]:
    out = []
    for cid, mats in data.gaps.items():
        need = mats.get(material_id, (0, 0))[0]
        ref = data.characters.get(cid)
        if need > 0 and ref is not None:
            out.append({**ref.to_dict(), "need": need})
    return sorted(out, key=lambda c: c["name"])


def material_index(data: PlannerData) -> dict[int, dict]:
    crafted = rollup(data)
    empty = Total(0, 0, 0)
    index: dict[int, dict] = {}
    for mid, m in data.materials.items():
        t = data.totals.get(mid, empty)
        c = crafted.get(mid, Crafted(0, t.short))
        state = "short" if t.short > 0 else "met" if t.need > 0 else "unneeded"
        index[mid] = {
            "id": mid, "name": m.name, "icon": m.icon, "rarity": m.rarity, "category": m.category,
            "sort_order": m.sort_order, "state": state, "need": t.need, "short": t.short,
            "have": t.need - t.short if t.short > 0 else None,
            "craftable": c.craftable, "to_farm": c.to_farm, "sources": m.sources,
            "characters": needers(data, mid) if t.need > 0 else [],
        }
    return index


def inventory(data: PlannerData, index: dict[int, dict]) -> list[dict]:
    out = []
    for key in CATEGORY_ORDER:
        rows = sorted((r for r in index.values() if r["category"] == key), key=lambda r: (r["sort_order"], r["id"]))
        if rows:
            out.append({"key": key, "label": CATEGORY_LABELS[key], "materials": rows})
    return out
```

- [ ] **Step 6: Implement `backend/app/planner/status.py`**

```python
from sqlalchemy.orm import Session

from app.db.models import GapRun
from app.planner.requests import snapshot
from app.timeutil import iso


def gap_status(session: Session, pending: bool, connected: bool) -> dict:
    """`stale` means "a recalculation is coming": only possible while connected."""
    run = session.get(GapRun, 1)
    current = snapshot(session)
    if run is None:
        return {"computed_at": None, "ok": None, "error": None, "skipped": [],
                "stale": connected and (pending or bool(current))}
    return {
        "computed_at": iso(run.computed_at), "ok": run.ok, "error": run.error, "skipped": run.skipped or [],
        "stale": connected and (pending or run.snapshot != current),
    }
```

- [ ] **Step 7: Run to verify pass**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_planner.py -q`
Expected: all pass

- [ ] **Step 8: Commit**

```bash
git add backend/app/planner backend/tests/test_planner.py
git commit -m "feat: planner data, crafting rollup, inventory states and gap status"
```

---

### Task 10: Farm today, weekly bosses, character shortfall, Building cards

**Files:**
- Create: `backend/app/planner/today.py`, `backend/app/planner/characters.py`
- Test: `backend/tests/test_planner.py` (append)

**Interfaces:**
- Consumes: Task 9 (`PlannerData`, `material_index` output dicts, `CATEGORY_ORDER`), `UNSUPPORTED` (Task 6).
- Produces:
  - `today.farm_today(data, weekday: int, index) -> dict` → `{"weekday", "domains": [{"id", "name", "kind", "weekdays", "materials": [material dict], "characters": [CharRef dict]}]}`
  - `today.weekly_bosses(data, done: set[str], index) -> list[dict]` → `[{"name", "done", "materials", "characters"}]`, not-done first
  - `characters.character_shortfall(data, character_id, index) -> list[dict]` → `[{"id", "name", "icon", "rarity", "category", "need", "short", "shared"}]`
  - `characters.building_cards(data, progress: dict[int, float | None], index) -> list[dict]` → `[{"character": CharRef dict, "progress", "materials": [shortfall rows with short > 0], "skipped": bool}]`

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_planner.py`)

```python
from app.planner.characters import building_cards, character_shortfall
from app.planner.data import Domain
from app.planner.today import farm_today, weekly_bosses


def planner_fixture():
    mats = {**BOOKS,
            50: mat(50, category="weekly", rarity=5, sources=[{"kind": "weekly_boss", "name": "Stormterror", "days": []}]),
            51: mat(51, category="weekly", rarity=5, sources=[{"kind": "weekly_boss", "name": "Childe", "days": []}])}
    d = data({2: Total(18, 7, 0), 3: Total(6, 0, 0), 50: Total(2, 2, 0), 51: Total(1, 1, 0)},
             gaps={10: {2: (9, 4), 50: (2, 2)}, 20: {2: (9, 4), 3: (6, 0), 51: (1, 1)}}, materials=mats)
    d.domains = [Domain(4213, "Domain of Mastery: Forsaken Rift", "talent", 1, [0, 3, 6], [3, 2, 1]),
                 Domain(4313, "Domain of Forgery: Cecilia Garden", "weapon", 1, [0, 3, 6], [114001])]
    return d


def test_farm_today_lists_open_domains_with_something_to_farm():
    d = planner_fixture()
    idx = material_index(d)
    today = farm_today(d, 0, idx)
    assert [x["name"] for x in today["domains"]] == ["Domain of Mastery: Forsaken Rift"]
    assert [m["id"] for m in today["domains"][0]["materials"]] == [2]
    assert {c["name"] for c in today["domains"][0]["characters"]} == {"Bennett", "Furina"}
    assert farm_today(d, 1, idx)["domains"] == []      # Tuesday: closed
    d.domains[0] = Domain(4213, "Domain of Mastery: Forsaken Rift", "talent", 1, [0, 3], [3, 2, 1])
    assert len(farm_today(d, 6, idx)["domains"]) == 1  # Sunday: everything open


def test_weekly_bosses_grouped_and_done_last():
    d = planner_fixture()
    bosses = weekly_bosses(d, {"Childe"}, material_index(d))
    assert [(b["name"], b["done"]) for b in bosses] == [("Stormterror", False), ("Childe", True)]
    assert bosses[0]["characters"][0]["name"] == "Bennett"


def test_character_shortfall_marks_shared():
    d = planner_fixture()
    rows = {r["id"]: r for r in character_shortfall(d, 10, material_index(d))}
    assert rows[2]["short"] == 4 and rows[2]["shared"] is True   # combined short 7 > own 4
    assert rows[50]["shared"] is False


def test_building_cards_only_short_and_fully_built():
    d = planner_fixture()
    d.characters[30] = CharRef(30, "Xiangling", "xiangling", None)
    cards = {c["character"]["id"]: c for c in building_cards(d, {10: 0.5, 20: 0.8, 30: 1.0}, material_index(d))}
    assert [m["id"] for m in cards[20]["materials"]] == [2, 51]     # 3 is met, so not listed
    assert cards[30]["materials"] == [] and cards[30]["skipped"] is False
    d.characters[10000005] = CharRef(10000005, "Traveler", "traveler", None)
    assert any(c["skipped"] for c in building_cards(d, {}, material_index(d)))
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_planner.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.planner.characters'`

- [ ] **Step 3: Implement `backend/app/planner/today.py`**

```python
"""Dashboard: domains open today and weekly bosses, limited to what is still to farm."""
from __future__ import annotations

from app.planner.data import PlannerData

SUNDAY = 6


def _characters(materials: list[dict]) -> list[dict]:
    seen: dict[int, dict] = {}
    for m in materials:
        for c in m["characters"]:
            seen.setdefault(c["id"], {k: c[k] for k in ("id", "name", "slug", "icon")})
    return sorted(seen.values(), key=lambda c: c["name"])


def farm_today(data: PlannerData, weekday: int, index: dict[int, dict]) -> dict:
    domains = []
    for d in data.domains:
        if weekday != SUNDAY and weekday not in d.weekdays:
            continue
        mats = [index[mid] for mid in d.material_ids if mid in index and index[mid]["to_farm"] > 0]
        if mats:
            domains.append({"id": d.id, "name": d.name, "kind": d.kind, "weekdays": d.weekdays,
                            "materials": mats, "characters": _characters(mats)})
    return {"weekday": weekday, "domains": domains}


def weekly_bosses(data: PlannerData, done: set[str], index: dict[int, dict]) -> list[dict]:
    by_boss: dict[str, list[dict]] = {}
    for row in sorted(index.values(), key=lambda r: (r["sort_order"], r["id"])):
        if row["category"] != "weekly" or row["to_farm"] <= 0:
            continue
        boss = next((s["name"] for s in row["sources"] if s["kind"] == "weekly_boss"), "Unknown boss")
        by_boss.setdefault(boss, []).append(row)
    bosses = [{"name": name, "done": name in done, "materials": mats, "characters": _characters(mats)}
              for name, mats in by_boss.items()]
    return sorted(bosses, key=lambda b: b["done"])
```

- [ ] **Step 4: Implement `backend/app/planner/characters.py`**

```python
"""Per-character shortfall (own numbers, with a shared mark) and Dashboard Building cards."""
from __future__ import annotations

from app.planner.data import CATEGORY_ORDER, PlannerData, Total
from app.planner.requests import UNSUPPORTED


def character_shortfall(data: PlannerData, character_id: int, index: dict[int, dict]) -> list[dict]:
    rows = []
    for mid, (need, short) in data.gaps.get(character_id, {}).items():
        m = index.get(mid)
        if m is None:
            continue
        others = any(cid != character_id and mats.get(mid, (0, 0))[0] > 0 for cid, mats in data.gaps.items())
        combined = data.totals.get(mid, Total(0, 0, 0)).short
        rows.append({"id": mid, "name": m["name"], "icon": m["icon"], "rarity": m["rarity"],
                     "category": m["category"], "need": need, "short": short,
                     "shared": others and combined > short,
                     "_order": (CATEGORY_ORDER.index(m["category"]), m["sort_order"], mid)})
    rows.sort(key=lambda r: r["_order"])
    for r in rows:
        del r["_order"]
    return rows


def building_cards(data: PlannerData, progress: dict[int, float | None], index: dict[int, dict]) -> list[dict]:
    cards = []
    for cid, ref in data.characters.items():
        materials = [r for r in character_shortfall(data, cid, index) if r["short"] > 0]
        cards.append({"character": ref.to_dict(), "progress": progress.get(cid),
                      "materials": materials, "skipped": cid in UNSUPPORTED})
    return sorted(cards, key=lambda c: (c["progress"] if c["progress"] is not None else -1, c["character"]["name"]))
```

- [ ] **Step 5: Run to verify pass**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add backend/app/planner/today.py backend/app/planner/characters.py backend/tests/test_planner.py
git commit -m "feat: farm today, weekly bosses, character shortfall and building cards"
```

---

### Task 11: API — inventory, weapons, weekly bosses, dashboard and character additions

**Files:**
- Create: `backend/app/api/planner.py`
- Modify: `backend/app/api/__init__.py`, `backend/app/api/dashboard.py`, `backend/app/api/characters.py`
- Test: `backend/tests/test_api_planner.py`, `backend/tests/test_api_settings.py` (leak test)

**Interfaces:**
- Consumes: Tasks 1, 8, 9, 10.
- Produces HTTP:
  - `GET /api/inventory` → `{"gaps": GapStatus, "categories": [{"key", "label", "materials": [material]}]}`
  - `GET /api/weapons?type=Sword` → `[{"id", "name", "icon", "rarity", "weapon_type"}]`
  - `PUT /api/weekly-bosses/{boss}` body `{"done": bool}` → `{"name", "done"}`
  - `GET /api/dashboard` adds `"farm_today"`, `"weekly_bosses": {"discounts_left", "discounts_max", "bosses"}`, `"building_cards"`, `"gaps"`
  - `GET /api/characters/{slug}` adds `"shortfall": {"gaps", "materials"} | null` and `"planned_weapon": {"id", "name", "icon", "rarity", "equipped"} | null`
  - every character payload adds `"planned_weapon_id"`
  - `PUT /api/characters/{id}/goal` accepts `"planned_weapon_id": int | null`; returns 400 for an unknown weapon or a wrong weapon type; any change calls `ctx.sync.schedule_gaps()`
  - helper `app.api.planner.planner_view(session) -> tuple[PlannerData, dict[int, dict]]`, `app.api.planner.region(ctx) -> str | None`, `app.api.planner.is_connected(ctx, session) -> bool`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_api_planner.py
import time
from datetime import datetime

from app.db.engine import make_engine, make_session_factory, migrate
from app.db.models import (
    CharacterGoal, GameDomain, GameMaterial, GameWeapon, MaterialGap, MaterialTotal, WeeklyBossDone,
)
from app.sync.persist import save_details, save_notes, save_roster
from app.timeutil import utcnow
from fakes import NOTES, FakeSource, make_detail, make_roster
from helpers import make_client, seed_game, wait_for_sync


def sf_for(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    return make_session_factory(engine)


def setup(paths, catalogue=True):
    sf = sf_for(paths)
    seed_game(sf)
    now = utcnow()
    with sf.begin() as s:
        save_roster(s, [make_roster(10000032, level=80, name="Bennett")], now)
        save_details(s, [make_detail(10000032, talents=(6, 8, 8))])
        save_notes(s, NOTES, now)
        s.add(CharacterGoal(character_id=10000032, goal="build", target_level=90, target_normal=8,
                            target_skill=8, target_burst=8, target_weapon_level=90, updated_at=now))
        if catalogue:
            for mid, name, cat, rarity, craft, sources in [
                (104301, "Teachings of Freedom", "talent", 2, None, []),
                (104302, "Guide to Freedom", "talent", 3, 104301, []),
                (113003, "Dvalin's Plume", "weekly", 5, None, [{"kind": "weekly_boss", "name": "Stormterror", "days": []}]),
            ]:
                s.add(GameMaterial(id=mid, name=name, icon=f"UI_ItemIcon_{mid}", rarity=rarity, yatta_type="x",
                                   category=cat, family=104301 if cat == "talent" else mid, craft_from=craft,
                                   sources=sources, sort_order=mid, detail_fetched=True))
            s.add(GameDomain(id=4213, name="Domain of Mastery: Forsaken Rift", kind="talent", city=1,
                             weekdays=[0, 1, 2, 3, 4, 5, 6], material_ids=[104302, 104301]))
            s.add(GameWeapon(id=11401, name="Favonius Sword", icon="UI_EquipIcon_Sword_Zephyrus", rarity=4,
                             weapon_type="Sword"))
            s.add(GameWeapon(id=13407, name="Favonius Lance", icon="UI_EquipIcon_Pole_Zephyrus", rarity=4,
                             weapon_type="Polearm"))
        s.add(MaterialTotal(material_id=104302, name="Guide to Freedom", icon="", rarity=3, need=9, short=4, spare=0))
        s.add(MaterialTotal(material_id=113003, name="Dvalin's Plume", icon="", rarity=5, need=2, short=2, spare=0))
        s.add(MaterialGap(character_id=10000032, material_id=104302, need=9, short=4))
        s.add(MaterialGap(character_id=10000032, material_id=113003, need=2, short=2))
    return sf


def test_inventory_endpoint(paths):
    setup(paths)
    with make_client(paths) as client:
        body = client.get("/api/inventory").json()
    cats = {c["key"]: c for c in body["categories"]}
    guide = next(m for m in cats["talent"]["materials"] if m["id"] == 104302)
    assert guide["state"] == "short" and guide["have"] == 5 and guide["to_farm"] == 4
    assert guide["characters"][0]["name"] == "Bennett"
    assert body["gaps"]["stale"] is False            # not connected in tests -> never stale


def test_inventory_without_catalogue_shows_other(paths):
    setup(paths, catalogue=False)
    with make_client(paths) as client:
        body = client.get("/api/inventory").json()
    assert [c["key"] for c in body["categories"]] == ["other"]
    with make_client(paths) as client:
        dash = client.get("/api/dashboard")
    assert dash.status_code == 200


def test_dashboard_planner_sections(paths):
    setup(paths)
    with make_client(paths) as client:
        body = client.get("/api/dashboard").json()
    assert body["farm_today"]["domains"][0]["name"] == "Domain of Mastery: Forsaken Rift"
    boss = body["weekly_bosses"]["bosses"][0]
    assert boss["name"] == "Stormterror" and boss["done"] is False
    card = body["building_cards"][0]
    assert card["character"]["name"] == "Bennett" and {m["id"] for m in card["materials"]} == {104302, 113003}
    assert "gaps" in body


def test_weekly_boss_toggle_round_trip(paths):
    sf = setup(paths)
    with make_client(paths) as client:
        assert client.put("/api/weekly-bosses/Stormterror", json={"done": True}).json() == {"name": "Stormterror", "done": True}
        assert client.get("/api/dashboard").json()["weekly_bosses"]["bosses"][0]["done"] is True
        client.put("/api/weekly-bosses/Stormterror", json={"done": False})
        assert client.get("/api/dashboard").json()["weekly_bosses"]["bosses"][0]["done"] is False
        assert client.put("/api/weekly-bosses/Dvalin%27s%20Lair", json={"done": True}).json()["name"] == "Dvalin's Lair"
    with sf() as s:
        assert s.query(WeeklyBossDone).count() == 1


def test_old_weekly_rows_are_pruned(paths):
    sf = setup(paths)
    with sf.begin() as s:
        s.add(WeeklyBossDone(boss="Stormterror", week_start=datetime(2020, 1, 6, 20)))
    with make_client(paths) as client:
        client.put("/api/weekly-bosses/Childe", json={"done": True})
    with sf() as s:
        assert [r.boss for r in s.query(WeeklyBossDone)] == ["Childe"]


def test_weapons_filtered_by_type(paths):
    setup(paths)
    with make_client(paths) as client:
        assert [w["name"] for w in client.get("/api/weapons?type=Sword").json()] == ["Favonius Sword"]


def test_character_detail_shortfall_and_planned_weapon(paths):
    setup(paths)
    with make_client(paths) as client:
        body = client.get("/api/characters/bennett").json()
        assert {m["id"] for m in body["shortfall"]["materials"]} == {104302, 113003}
        assert body["planned_weapon"]["equipped"] is True and body["planned_weapon_id"] is None
        r = client.put("/api/characters/10000032/goal", json={"planned_weapon_id": 11401})
        assert r.status_code == 200 and r.json()["planned_weapon_id"] == 11401
        body = client.get("/api/characters/bennett").json()
        assert body["planned_weapon"]["name"] == "Favonius Sword" and body["planned_weapon"]["equipped"] is False
        assert client.put("/api/characters/10000032/goal", json={"planned_weapon_id": 13407}).status_code == 400
        assert client.put("/api/characters/10000032/goal", json={"planned_weapon_id": 1}).status_code == 400
        assert client.put("/api/characters/10000032/goal", json={"planned_weapon_id": None}).json()["planned_weapon_id"] is None
        assert client.get("/api/characters/furina").json()["shortfall"] is None   # not Build


def test_goal_change_schedules_gaps_run(paths):
    setup(paths)
    source = FakeSource()
    with make_client(paths, source=source) as client:
        client.app.state.ctx.sync._gaps_delay = 0.01
        client.put("/api/characters/10000032/goal", json={"targets": {"level": 90, "normal": 9, "skill": 8,
                                                                       "burst": 8, "weapon_level": 90}})
        deadline = time.monotonic() + 5
        while not any(isinstance(c, tuple) and c[0] == "gaps" for c in source.calls):
            assert time.monotonic() < deadline, "gaps run never started"
            time.sleep(0.05)
        wait_for_sync(client)
    assert any(isinstance(c, tuple) and c[0] == "gaps" for c in source.calls)
```

In `backend/tests/test_api_settings.py` `test_no_endpoint_leaks_cookie_values`, extend the endpoint tuple with `"/api/inventory"`, `"/api/weapons?type=Sword"`, and `"/api/characters/bennett"`.

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_api_planner.py -q`
Expected: FAIL — 404 for `/api/inventory`

- [ ] **Step 3: Implement `backend/app/api/planner.py`**

```python
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.context import AppContext, get_ctx
from app.db.models import GameWeapon, WeeklyBossDone
from app.planner.data import PlannerData, load
from app.planner.inventory import inventory, material_index
from app.planner.status import gap_status
from app.servertime import week_start
from app.settings.envfile import connection_status, read_env
from app.settings.store import get_setting
from app.timeutil import utcnow

router = APIRouter()
KEEP_WEEKS = 8


class BossDoneIn(BaseModel):
    done: bool


def region(ctx: AppContext) -> str | None:
    return read_env(ctx.paths.env_file).get("GENSHIN_REGION")


def is_connected(ctx: AppContext, session: Session) -> bool:
    status = connection_status(read_env(ctx.paths.env_file), get_setting(session, "hoyolab_status"))
    return status["status"] == "connected"


def planner_view(session: Session) -> tuple[PlannerData, dict[int, dict]]:
    data = load(session)
    return data, material_index(data)


def gaps_for(ctx: AppContext, session: Session) -> dict:
    return gap_status(session, pending=ctx.sync.gaps_pending, connected=is_connected(ctx, session))


@router.get("/inventory")
def get_inventory(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        data, index = planner_view(s)
        return {"gaps": gaps_for(ctx, s), "categories": inventory(data, index)}


@router.get("/weapons")
def list_weapons(type: str | None = None, ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        q = select(GameWeapon).order_by(GameWeapon.rarity.desc(), GameWeapon.name)
        if type:
            q = q.where(GameWeapon.weapon_type == type)
        return [{"id": w.id, "name": w.name, "icon": w.icon, "rarity": w.rarity, "weapon_type": w.weapon_type}
                for w in s.scalars(q)]


@router.put("/weekly-bosses/{boss}")
def set_boss_done(boss: str, body: BossDoneIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    if not boss or len(boss) > 100:
        raise HTTPException(422, "Bad boss name")
    ws = week_start(utcnow(), region(ctx))
    with ctx.session_factory.begin() as s:
        row = s.get(WeeklyBossDone, (boss, ws))
        if body.done and row is None:
            s.add(WeeklyBossDone(boss=boss, week_start=ws))
        elif not body.done and row is not None:
            s.delete(row)
        s.execute(delete(WeeklyBossDone).where(WeeklyBossDone.week_start < ws - timedelta(weeks=KEEP_WEEKS)))
    return {"name": boss, "done": body.done}
```

Register it in `backend/app/api/__init__.py`:

```python
from app.api import characters, dashboard, img, planner, settings, sync

ROUTERS = [settings.router, sync.router, characters.router, dashboard.router, planner.router, img.router]
```

- [ ] **Step 4: Extend the dashboard** (`backend/app/api/dashboard.py`)

```python
from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.characters import goal_targets
from app.api.planner import gaps_for, planner_view, region
from app.context import AppContext, get_ctx
from app.db.models import CharacterGoal, LiveNotes, OwnedCharacter, WeeklyBossDone
from app.domain import Current, progress
from app.planner.characters import building_cards
from app.planner.today import farm_today, weekly_bosses
from app.servertime import server_weekday, week_start
from app.settings.envfile import connection_status, read_env
from app.settings.store import get_setting
from app.timeutil import iso, utcnow

router = APIRouter()

# notes_payload unchanged


@router.get("/dashboard")
def dashboard(ctx: AppContext = Depends(get_ctx)) -> dict:
    now, reg = utcnow(), region(ctx)
    with ctx.session_factory() as s:
        owned = {o.character_id: o for o in s.scalars(select(OwnedCharacter))}
        progress_by_id: dict[int, float | None] = {}
        for row in s.scalars(select(CharacterGoal).where(CharacterGoal.goal == "build")):
            o, t = owned.get(row.character_id), goal_targets(row)
            progress_by_id[row.character_id] = (
                progress(Current(o.level, o.talent_normal, o.talent_skill, o.talent_burst), t)
                if o is not None and t is not None else None)
        values = [v for v in progress_by_id.values() if v is not None]
        notes = s.get(LiveNotes, 1)
        data, index = planner_view(s)
        done = set(s.scalars(select(WeeklyBossDone.boss).where(WeeklyBossDone.week_start == week_start(now, reg))))
        return {
            "connection": connection_status(read_env(ctx.paths.env_file), get_setting(s, "hoyolab_status")),
            "notes": notes_payload(notes) if notes is not None else None,
            "building": {
                "count": len(values),
                "average_progress": round(sum(values) / len(values), 4) if values else None,
            },
            "farm_today": farm_today(data, server_weekday(now, reg), index),
            "weekly_bosses": {
                "discounts_left": notes.weekly_discounts_left if notes is not None else None,
                "discounts_max": notes.weekly_discounts_max if notes is not None else None,
                "bosses": weekly_bosses(data, done, index),
            },
            "building_cards": building_cards(data, progress_by_id, index),
            "gaps": gaps_for(ctx, s),
        }
```

(Existing behaviour kept: `building.count` counts owned Build characters with targets, as before.)

- [ ] **Step 5: Extend characters** (`backend/app/api/characters.py`)

`GoalIn` gains `planned_weapon_id: int | None = None`. In `character_payload` add `"planned_weapon_id": goal_row.planned_weapon_id if goal_row else None,`. Add imports `from app.api.planner import gaps_for, planner_view`, `from app.db.models import GameWeapon` (extend the existing models import) and `from app.planner.characters import character_shortfall`. (`api/planner.py` does not import `api/characters.py`, so there is no import cycle.)

Add helper:

```python
def planned_weapon(s: Session, row: CharacterGoal | None, o: OwnedCharacter | None) -> dict | None:
    if row is not None and row.planned_weapon_id is not None:
        w = s.get(GameWeapon, row.planned_weapon_id)
        if w is not None:
            return {"id": w.id, "name": w.name, "icon": w.icon, "rarity": w.rarity,
                    "equipped": o is not None and o.weapon_id == w.id}
    if o is not None and o.weapon_id:
        return {"id": o.weapon_id, "name": o.weapon_name, "icon": o.weapon_icon, "rarity": o.weapon_rarity,
                "equipped": True}
    return None
```

In `get_character`, before `return payload`:

```python
            payload["planned_weapon"] = planned_weapon(s, r, o)
            if payload["goal"] == "build":
                data, index = planner_view(s)
                payload["shortfall"] = {"gaps": gaps_for(ctx, s),
                                        "materials": character_shortfall(data, payload["id"], index)}
            else:
                payload["shortfall"] = None
```

Make `set_goal` async and schedule a recalculation when anything changed:

```python
@router.put("/characters/{character_id}/goal")
async def set_goal(character_id: int, body: GoalIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory.begin() as s:
        g = s.get(GameCharacter, character_id)
        o = s.get(OwnedCharacter, character_id)
        if g is None and o is None:
            raise HTTPException(404, "Unknown character")
        row = s.get(CharacterGoal, character_id)
        if row is None:
            row = CharacterGoal(character_id=character_id, goal="none", updated_at=utcnow())
            s.add(row)

        def state() -> tuple:
            return (row.goal, row.target_level, row.target_normal, row.target_skill, row.target_burst,
                    row.target_weapon_level, row.planned_weapon_id)

        before = state()
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
        if "planned_weapon_id" in body.model_fields_set:
            wid = body.planned_weapon_id
            if wid is not None:
                w = s.get(GameWeapon, wid)
                if w is None or (g is not None and w.weapon_type != g.weapon_type):
                    raise HTTPException(400, "That weapon does not fit this character.")
            row.planned_weapon_id = wid
        changed = state() != before
        row.updated_at = utcnow()
        s.flush()
        payload = character_payload(g, o, row)
    if changed:
        ctx.sync.schedule_gaps()
    return payload
```

- [ ] **Step 6: Run to verify pass**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add backend/app/api backend/tests/test_api_planner.py backend/tests/test_api_settings.py
git commit -m "feat: planner API for inventory, dashboard, weekly bosses and weapons"
```

---

### Task 12: Seed data for demos and end-to-end tests

**Files:**
- Modify: `backend/app/devseed.py`
- Test: `backend/tests/test_devseed.py`

**Interfaces:**
- Consumes: models, `save_gaps`, `snapshot`, `GapResult`, `MaterialAmount`, `WeaponInfo` (with id).
- Produces: a seeded database where Dashboard shows one open domain ("Domain of Mastery: Forsaken Rift", open every day in seed data), a Stormterror boss card, Building cards for Bennett and Furina, and an Inventory with short (Guide 104302), met (Hero's Wit 104003), and unneeded (Small Lamp Grass 100055) tiles; gap status not stale.

- [ ] **Step 1: Write the failing test** (append to `backend/tests/test_devseed.py`)

```python
def test_devseed_contains_planner_data(tmp_path):
    from fastapi.testclient import TestClient

    from app.devseed import seed
    from app.main import create_app
    from app.config import Paths

    seed(tmp_path)
    with TestClient(create_app(Paths(tmp_path), offline=True)) as client:
        dash = client.get("/api/dashboard").json()
        inv = client.get("/api/inventory").json()
    assert dash["farm_today"]["domains"][0]["name"] == "Domain of Mastery: Forsaken Rift"
    assert dash["weekly_bosses"]["bosses"][0]["name"] == "Stormterror"
    assert dash["gaps"]["stale"] is False
    states = {m["id"]: m["state"] for c in inv["categories"] for m in c["materials"]}
    assert states[104302] == "short" and states[104003] == "met" and states[100055] == "unneeded"
```

- [ ] **Step 2: Run to verify failure**

Run: `cd backend; ..\.venv\Scripts\python -m pytest tests/test_devseed.py -q`
Expected: FAIL — `IndexError` (no domains)

- [ ] **Step 3: Implement** — in `backend/app/devseed.py`:

Change `WEAPON` to `WeaponInfo("Favonius Sword", "https://enka.network/ui/UI_EquipIcon_Sword_Zephyrus.png", 4, 90, 3, 11401)`.

Add data and imports (`GameDomain, GameMaterial, GameWeapon` from models; `GapResult, MaterialAmount` from hoyolab; `save_gaps` from persist; `snapshot` from `app.planner.requests`):

```python
# (id, name, category, rarity, craft_from, yatta_type, sources)
MATERIALS = [
    (202, "Mora", "exp", 3, None, "commonCurrency", []),
    (104003, "Hero's Wit", "exp", 4, None, "characterEXPMaterial", []),
    (104111, "Agnidus Agate Sliver", "ascension", 2, None, "characterAscensionMaterial", []),
    (104112, "Agnidus Agate Fragment", "ascension", 3, 104111, "characterAscensionMaterial", []),
    (100055, "Small Lamp Grass", "specialty", 1, None, "localSpecialtyMondstadt",
     [{"kind": "region", "name": "Mondstadt", "days": []}]),
    (104301, "Teachings of Freedom", "talent", 2, None, "characterTalentMaterial", []),
    (104302, "Guide to Freedom", "talent", 3, 104301, "characterTalentMaterial", []),
    (104303, "Philosophies of Freedom", "talent", 4, 104302, "characterTalentMaterial", []),
    (113003, "Dvalin's Plume", "weekly", 5, None, "characterLevelUpMaterial",
     [{"kind": "weekly_boss", "name": "Stormterror", "days": []}]),
    (104319, "Crown of Insight", "special", 5, None, "characterTalentMaterial", []),
]
FREEDOM_SOURCE = {"kind": "domain", "name": "Domain of Mastery: Forsaken Rift", "days": [0, 1, 2, 3, 4, 5, 6]}
WEAPONS = [(11401, "Favonius Sword", "UI_EquipIcon_Sword_Zephyrus", 4, "Sword"),
           (11509, "Mistsplitter Reforged", "UI_EquipIcon_Sword_Narukami", 5, "Sword"),
           (13407, "Favonius Lance", "UI_EquipIcon_Pole_Zephyrus", 4, "Polearm"),
           (14504, "A Thousand Floating Dreams", "UI_EquipIcon_Catalyst_Ayus", 5, "Catalyst")]


def _amount(mid, need, short):
    name = next(m[1] for m in MATERIALS if m[0] == mid)
    return MaterialAmount(mid, name, "", 3, need, short)
```

At the end of the `with sf.begin() as s:` block in `seed()` add:

```python
        for order, (mid, name, cat, rarity, craft, ytype, sources) in enumerate(MATERIALS):
            src = [FREEDOM_SOURCE] if cat == "talent" else sources
            s.add(GameMaterial(id=mid, name=name, icon=f"UI_ItemIcon_{mid}", rarity=rarity, yatta_type=ytype,
                               category=cat, family=104301 if cat == "talent" else (104111 if mid in (104111, 104112) else mid),
                               craft_from=craft, sources=src, sort_order=order, detail_fetched=True))
        s.add(GameDomain(id=4213, name="Domain of Mastery: Forsaken Rift", kind="talent", city=1,
                         weekdays=[0, 1, 2, 3, 4, 5, 6], material_ids=[104303, 104302, 104301]))
        for wid, name, icon, rarity, wtype in WEAPONS:
            s.add(GameWeapon(id=wid, name=name, icon=icon, rarity=rarity, weapon_type=wtype))
        s.merge(GameMeta(key="materials_fetched_at", value=iso(now)))
        s.flush()
        result = GapResult(
            per_character={
                10000032: [_amount(104302, 9, 4), _amount(104303, 6, 0), _amount(113003, 2, 2), _amount(104003, 20, 0)],
                10000089: [_amount(104302, 6, 4), _amount(104319, 1, 1)],
            },
            total=[_amount(104302, 15, 7), _amount(104303, 6, 0), _amount(113003, 2, 2), _amount(104003, 20, 0),
                   _amount(104319, 1, 1)],
            spare=[_amount(104301, 9, 0)],
        )
        save_gaps(s, result, snapshot(s), [], now)
```

(Neuvillette is Build but not owned and gets no rows: his card shows "Everything in the bag ✓" in seed data, which exercises that state.)

- [ ] **Step 4: Run to verify pass**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add backend/app/devseed.py backend/tests/test_devseed.py
git commit -m "feat: planner seed data for demos and e2e"
```

---

### Task 13: Frontend foundations — types, API client, tile logic, tile components, nav, settings line

**Files:**
- Create: `frontend/src/lib/materials.ts`, `frontend/src/lib/materials.test.ts`, `frontend/src/lib/MaterialTile.svelte`, `frontend/src/lib/MaterialPopover.svelte`
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/app.css`, `frontend/src/routes/+layout.svelte`, `frontend/src/routes/settings/+page.svelte`

**Interfaces:**
- Consumes: API shapes from Task 11.
- Produces:
  - Types: `MaterialState`, `MaterialSource`, `CharRef`, `Needer`, `Material`, `CharMaterial`, `GapStatus`, `InventoryCategory`, `Inventory`, `FarmDomain`, `WeeklyBoss`, `BuildingCard`, `WeaponOption`, `PlannedWeapon`; `Dashboard`, `CharacterDetail`, `Character`, `Settings` extended.
  - `api.inventory()`, `api.weapons(type)`, `api.setBossDone(name, done)`, `api.setGoal(id, {goal?, targets?, planned_weapon_id?})`
  - `materials.ts`: `InventoryFilter`, `Tone`, `TileView`, `tileView(m: Material)`, `charTileView(m: CharMaterial)`, `filterMaterials(ms, filter, query)`, `weekdayNames(days)`, `gapLabel(g, now)`, `shouldPoll(g)`
  - `<MaterialTile name icon rarity view dim? testid? popover?>` and `<MaterialPopover material>`

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/materials.test.ts
import { describe, expect, it } from 'vitest';
import type { CharMaterial, GapStatus, Material } from './types';
import { charTileView, filterMaterials, gapLabel, shouldPoll, tileView, weekdayNames } from './materials';

function m(over: Partial<Material>): Material {
	return {
		id: 1, name: 'Guide to Freedom', icon: 'UI_ItemIcon_1', rarity: 3, category: 'talent', state: 'unneeded',
		need: 0, short: 0, have: null, craftable: 0, to_farm: 0, sources: [], characters: [], ...over
	};
}
const gaps = (over: Partial<GapStatus>): GapStatus =>
	({ computed_at: null, ok: null, error: null, stale: false, skipped: [], ...over });

describe('tileView', () => {
	it('short shows have/need, to-farm badge and craft hint', () => {
		expect(tileView(m({ state: 'short', need: 18, short: 7, have: 11, to_farm: 4, craftable: 3 })))
			.toEqual({ main: '11/18', badge: '−4', hint: 'craft 3', tone: 'short' });
	});
	it('short fully covered by crafting has no badge', () => {
		expect(tileView(m({ state: 'short', need: 5, short: 2, have: 3, to_farm: 0, craftable: 2 })).badge).toBeNull();
	});
	it('met and unneeded', () => {
		expect(tileView(m({ state: 'met', need: 24 }))).toEqual({ main: '✓ 24', badge: null, hint: null, tone: 'met' });
		expect(tileView(m({}))).toEqual({ main: '', badge: null, hint: null, tone: 'none' });
	});
});

describe('charTileView', () => {
	const c = (over: Partial<CharMaterial>): CharMaterial =>
		({ id: 1, name: 'x', icon: 'i', rarity: 3, category: 'talent', need: 9, short: 0, shared: false, ...over });
	it('short with shared mark', () => {
		expect(charTileView(c({ short: 4, shared: true }))).toEqual({ main: '5/9', badge: '−4', hint: 'shared', tone: 'short' });
	});
	it('met', () => {
		expect(charTileView(c({}))).toEqual({ main: '✓ 9', badge: null, hint: null, tone: 'met' });
	});
});

describe('filterMaterials', () => {
	const list = [m({ id: 1, state: 'unneeded', name: 'Mora' }), m({ id: 2, state: 'met', need: 3, name: 'Hero' }),
		m({ id: 3, state: 'short', need: 3, short: 1, to_farm: 1, name: 'Guide' }),
		m({ id: 4, state: 'short', need: 3, short: 1, to_farm: 0, craftable: 1, name: 'Philosophies' })];
	it('all / needed / farm', () => {
		expect(filterMaterials(list, 'all', '').map((x) => x.id)).toEqual([1, 2, 3, 4]);
		expect(filterMaterials(list, 'needed', '').map((x) => x.id)).toEqual([2, 3, 4]);
		expect(filterMaterials(list, 'farm', '').map((x) => x.id)).toEqual([3]);
	});
	it('search is case-insensitive', () => {
		expect(filterMaterials(list, 'all', 'gUiD').map((x) => x.id)).toEqual([3]);
	});
});

describe('labels', () => {
	it('weekday names', () => expect(weekdayNames([0, 3, 6])).toBe('Mon/Thu/Sun'));
	it('gap label priorities', () => {
		expect(gapLabel(gaps({ ok: false, error: 'boom', stale: true }), 0)).toBe('⚠ Shortfall update failed: boom');
		expect(gapLabel(gaps({ stale: true }), 0)).toBe('Updating…');
		expect(gapLabel(gaps({}), 0)).toBe('Not calculated yet');
		expect(gapLabel(gaps({ computed_at: new Date(0).toISOString() }), 60_000)).toContain('Calculated');
	});
	it('polls only while stale and not failed', () => {
		expect(shouldPoll(gaps({ stale: true }))).toBe(true);
		expect(shouldPoll(gaps({ stale: true, ok: false }))).toBe(false);
		expect(shouldPoll(gaps({}))).toBe(false);
	});
});
```

- [ ] **Step 2: Run to verify failure**

Run: `cd frontend; npm test`
Expected: FAIL — cannot resolve `./materials`

- [ ] **Step 3: Add types** (append to `frontend/src/lib/types.ts`; extend existing interfaces as shown)

```ts
export type MaterialState = 'short' | 'met' | 'unneeded';
export interface MaterialSource { kind: 'domain' | 'weekly_boss' | 'region' | 'text'; name: string; days: number[] }
export interface CharRef { id: number; name: string; slug: string; icon: string | null }
export interface Needer extends CharRef { need: number }
export interface Material {
	id: number; name: string; icon: string; rarity: number; category: string; state: MaterialState;
	need: number; short: number; have: number | null; craftable: number; to_farm: number;
	sources: MaterialSource[]; characters: Needer[];
}
export interface CharMaterial {
	id: number; name: string; icon: string; rarity: number; category: string;
	need: number; short: number; shared: boolean;
}
export interface GapStatus { computed_at: string | null; ok: boolean | null; error: string | null; stale: boolean; skipped: string[] }
export interface InventoryCategory { key: string; label: string; materials: Material[] }
export interface Inventory { gaps: GapStatus; categories: InventoryCategory[] }
export interface FarmDomain { id: number; name: string; kind: 'talent' | 'weapon'; weekdays: number[]; materials: Material[]; characters: CharRef[] }
export interface WeeklyBoss { name: string; done: boolean; materials: Material[]; characters: CharRef[] }
export interface BuildingCard { character: CharRef; progress: number | null; materials: CharMaterial[]; skipped: boolean }
export interface WeaponOption { id: number; name: string; icon: string; rarity: number; weapon_type: string }
export interface PlannedWeapon { id: number; name: string; icon: string; rarity: number; equipped: boolean }
```

Extend: `Character` gets `planned_weapon_id: number | null;` `CharacterDetail` gets `shortfall: { gaps: GapStatus; materials: CharMaterial[] } | null; planned_weapon: PlannedWeapon | null;` `Dashboard` gets

```ts
	farm_today: { weekday: number; domains: FarmDomain[] };
	weekly_bosses: { discounts_left: number | null; discounts_max: number | null; bosses: WeeklyBoss[] };
	building_cards: BuildingCard[];
	gaps: GapStatus;
```

and `Settings.gamedata` gets `materials: { fetched_at: string | null; last_error: string | null; count: number };`. Update the `char()` helper in `status.test.ts` with `planned_weapon_id: null`.

- [ ] **Step 4: API client** (`frontend/src/lib/api.ts`; extend the type import list)

```ts
	setGoal: (id: number, body: { goal?: Goal; targets?: Targets; planned_weapon_id?: number | null }) =>
		request<Character>('PUT', `/characters/${id}/goal`, body),
	inventory: () => request<Inventory>('GET', '/inventory'),
	weapons: (type: string) => request<WeaponOption[]>('GET', `/weapons?type=${encodeURIComponent(type)}`),
	setBossDone: (name: string, done: boolean) =>
		request<{ name: string; done: boolean }>('PUT', `/weekly-bosses/${encodeURIComponent(name)}`, { done }),
```

- [ ] **Step 5: Tile logic** (`frontend/src/lib/materials.ts`)

```ts
import type { CharMaterial, GapStatus, Material } from './types';
import { timeAgo } from './time';

export type InventoryFilter = 'all' | 'needed' | 'farm';
export type Tone = 'short' | 'met' | 'none';
export interface TileView { main: string; badge: string | null; hint: string | null; tone: Tone }

export function tileView(m: Material): TileView {
	if (m.state === 'short') {
		return {
			main: `${m.have ?? 0}/${m.need}`,
			badge: m.to_farm > 0 ? `−${m.to_farm}` : null,
			hint: m.craftable > 0 ? `craft ${m.craftable}` : null,
			tone: 'short'
		};
	}
	if (m.state === 'met') return { main: `✓ ${m.need}`, badge: null, hint: null, tone: 'met' };
	return { main: '', badge: null, hint: null, tone: 'none' };
}

export function charTileView(m: CharMaterial): TileView {
	const hint = m.shared ? 'shared' : null;
	if (m.short > 0) return { main: `${m.need - m.short}/${m.need}`, badge: `−${m.short}`, hint, tone: 'short' };
	return { main: `✓ ${m.need}`, badge: null, hint, tone: 'met' };
}

export function filterMaterials(ms: Material[], filter: InventoryFilter, query: string): Material[] {
	const q = query.trim().toLowerCase();
	return ms.filter((m) => {
		const passes = filter === 'all' ? true : filter === 'needed' ? m.state !== 'unneeded' : m.to_farm > 0;
		return passes && (!q || m.name.toLowerCase().includes(q));
	});
}

const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
export function weekdayNames(days: number[]): string {
	return days.map((d) => DAYS[d] ?? '?').join('/');
}

export function gapLabel(g: GapStatus, now: number): string {
	if (g.ok === false) return `⚠ Shortfall update failed: ${g.error ?? 'unknown error'}`;
	if (g.stale) return 'Updating…';
	if (g.computed_at) return `Calculated ${timeAgo(g.computed_at, now)}`;
	return 'Not calculated yet';
}

export function shouldPoll(g: GapStatus | null | undefined): boolean {
	return !!g && g.stale && g.ok !== false;
}
```

- [ ] **Step 6: Components**

`frontend/src/lib/MaterialTile.svelte`:

```svelte
<script lang="ts">
	import type { Snippet } from 'svelte';
	import { imgSrc } from './img';
	import type { TileView } from './materials';

	let { name, icon, rarity, view, dim = false, testid, popover }: {
		name: string; icon: string | null; rarity: number; view: TileView; dim?: boolean; testid?: string;
		popover?: Snippet;
	} = $props();
</script>

<div class="tile" class:dim data-testid={testid}>
	<button type="button" class="face r{rarity}" aria-label={name}>
		{#if imgSrc(icon)}<img src={imgSrc(icon)} alt="" loading="lazy" />{/if}
		{#if view.badge}<span class="badge">{view.badge}</span>{/if}
	</button>
	<div class="count {view.tone}">{view.main}</div>
	{#if view.hint}<div class="hint">{view.hint}</div>{/if}
	<div class="name">{name}</div>
	{#if popover}<div class="popover" role="tooltip">{@render popover()}</div>{/if}
</div>

<style>
	.tile { position: relative; width: 76px; text-align: center; font-size: 12px; }
	.tile.dim { opacity: 0.45; }
	.face { position: relative; width: 64px; height: 64px; padding: 0; border-radius: 8px; border: none;
		background: var(--r0); cursor: default; }
	.face.r1 { background: var(--r1); } .face.r2 { background: var(--r2); } .face.r3 { background: var(--r3); }
	.face.r4 { background: var(--r4); } .face.r5 { background: var(--r5); }
	.face img { width: 64px; height: 64px; display: block; }
	.badge { position: absolute; top: -6px; right: -6px; background: var(--error); color: #fff;
		border-radius: 10px; padding: 1px 6px; font-weight: 700; font-size: 11px; }
	.count { font-weight: 600; min-height: 16px; }
	.count.short { color: var(--error); } .count.met { color: var(--accent); }
	.hint { color: var(--warn); font-size: 11px; }
	.name { color: var(--muted); font-size: 11px; line-height: 1.2; overflow: hidden; display: -webkit-box;
		-webkit-line-clamp: 2; line-clamp: 2; -webkit-box-orient: vertical; }
	.popover { display: none; position: absolute; z-index: 20; top: 70px; left: 50%; transform: translateX(-50%);
		width: 220px; text-align: left; background: var(--panel-2); border: 1px solid var(--line);
		border-radius: 8px; padding: 10px; box-shadow: 0 6px 20px rgba(0, 0, 0, 0.4); }
	.tile:hover .popover, .tile:focus-within .popover { display: block; }
</style>
```

`frontend/src/lib/MaterialPopover.svelte`:

```svelte
<script lang="ts">
	import { weekdayNames } from './materials';
	import type { Material } from './types';

	let { material }: { material: Material } = $props();
</script>

<strong>{material.name}</strong>
{#each material.sources as s, i (i)}
	<div class="muted">
		{#if s.kind === 'domain'}{s.name} · {weekdayNames(s.days)}
		{:else if s.kind === 'weekly_boss'}Weekly boss: {s.name}
		{:else if s.kind === 'region'}Local specialty · {s.name}
		{:else}{s.name}{/if}
	</div>
{/each}
{#if material.characters.length}
	<div class="needers">
		{#each material.characters as c (c.id)}<div>{c.name}: {c.need}</div>{/each}
	</div>
{/if}
{#if material.craftable > 0}<div class="muted">Craft {material.craftable} from spare lower tiers</div>{/if}

<style>
	.needers { margin-top: 6px; }
</style>
```

- [ ] **Step 7: CSS, nav, settings line**

`frontend/src/app.css` `:root` — add after `--r4`:

```css
	--r3: linear-gradient(160deg, #3d5a8a, #5c86c6);
	--r2: linear-gradient(160deg, #3d6b52, #5a9b74);
	--r1: linear-gradient(160deg, #55555f, #77778a);
```

`frontend/src/routes/+layout.svelte` — change the Inventory nav entry to `{ label: 'Inventory', href: '/inventory' },`.

`frontend/src/routes/settings/+page.svelte` — in the Game data section, after the characters line, add:

```svelte
		<p>
			{settings.gamedata.materials.count} materials ·
			{settings.gamedata.materials.fetched_at ? `updated ${timeAgo(settings.gamedata.materials.fetched_at, now)}` : 'never downloaded'}
		</p>
		{#if settings.gamedata.materials.last_error}<p class="error">Materials: {settings.gamedata.materials.last_error}</p>{/if}
```

- [ ] **Step 8: Run checks**

Run: `cd frontend; npm test; npm run check`
Expected: all Vitest tests pass; svelte-check 0 errors

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "feat: frontend types, API client and material tiles for the planner"
```

---

### Task 14: Inventory page

**Files:**
- Create: `frontend/src/routes/inventory/+page.svelte`

**Interfaces:**
- Consumes: `api.inventory`, `MaterialTile`, `MaterialPopover`, `filterMaterials`, `tileView`, `gapLabel`, `shouldPoll`, `sync.version`.
- Produces test ids used by e2e: `tile-<material id>`, filter buttons named "All", "Needed", "To farm".

- [ ] **Step 1: Implement**

```svelte
<script lang="ts">
	import { api, errorMessage } from '$lib/api';
	import MaterialPopover from '$lib/MaterialPopover.svelte';
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { filterMaterials, gapLabel, shouldPoll, tileView, type InventoryFilter } from '$lib/materials';
	import { sync } from '$lib/sync.svelte';
	import type { Inventory } from '$lib/types';

	const FILTER_KEY = 'gt.inventory.filter';
	const FILTERS: { key: InventoryFilter; label: string }[] = [
		{ key: 'all', label: 'All' },
		{ key: 'needed', label: 'Needed' },
		{ key: 'farm', label: 'To farm' }
	];

	function readFilter(): InventoryFilter {
		try {
			const v = localStorage.getItem(FILTER_KEY);
			return v === 'needed' || v === 'farm' ? v : 'all';
		} catch {
			return 'all';
		}
	}

	let data = $state<Inventory | null>(null);
	let error = $state<string | null>(null);
	let filter = $state<InventoryFilter>(readFilter());
	let query = $state('');
	let now = $state(Date.now());

	function setFilter(f: InventoryFilter) {
		filter = f;
		try {
			localStorage.setItem(FILTER_KEY, f);
		} catch {
			/* remembered filter is a convenience only */
		}
	}

	async function load() {
		try {
			data = await api.inventory();
			error = null;
			now = Date.now();
		} catch (e) {
			error = errorMessage(e);
		}
	}

	$effect(() => {
		void sync.version;
		load();
	});

	$effect(() => {
		if (!shouldPoll(data?.gaps)) return;
		const t = setTimeout(load, 2000);
		return () => clearTimeout(t);
	});

	const sections = $derived(
		(data?.categories ?? [])
			.map((c) => ({ ...c, shown: filterMaterials(c.materials, filter, query) }))
			.filter((c) => c.shown.length > 0)
	);
	const anyNeeded = $derived((data?.categories ?? []).some((c) => c.materials.some((m) => m.state !== 'unneeded')));
</script>

<h1>Inventory</h1>
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	<div class="bar">
		<div class="chips">
			{#each FILTERS as f (f.key)}
				<button type="button" class="chip" class:on={filter === f.key} onclick={() => setFilter(f.key)}>{f.label}</button>
			{/each}
		</div>
		<input type="search" placeholder="Search materials" aria-label="Search materials" bind:value={query} />
		<span class="muted status" data-testid="gap-status">{gapLabel(data.gaps, now)}</span>
	</div>
	{#if data.gaps.skipped.length}
		<p class="muted">{data.gaps.skipped.join(', ')} planning isn't supported yet.</p>
	{/if}
	{#if !anyNeeded}<p class="muted">Set characters to Build to plan farming.</p>{/if}

	{#each sections as c (c.key)}
		<section class="panel" data-testid="category-{c.key}">
			<h2>{c.label}</h2>
			<div class="grid">
				{#each c.shown as m (m.id)}
					<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={tileView(m)}
						dim={m.state === 'unneeded'} testid="tile-{m.id}">
						{#snippet popover()}<MaterialPopover material={m} />{/snippet}
					</MaterialTile>
				{/each}
			</div>
		</section>
	{/each}
{:else if !error}
	<p class="muted">Loading…</p>
{/if}

<style>
	.bar { display: flex; flex-wrap: wrap; gap: 12px; align-items: center; margin-bottom: 12px; }
	.chips { display: flex; gap: 6px; }
	.status { margin-left: auto; }
	section { margin-bottom: 12px; }
	.grid { display: flex; flex-wrap: wrap; gap: 10px; }
</style>
```

- [ ] **Step 2: Check and look at it**

Run: `cd frontend; npm run check` → 0 errors. Then seed and run: `cd backend; ..\.venv\Scripts\python -m app.devseed --root ..\.e2e-data`, then from the repo root with `GT_ROOT` set to `.e2e-data` and `GT_OFFLINE=1`, `python run.py`. Open `http://127.0.0.1:8765/inventory`: the talent section shows Guide to Freedom `8/15` with `−4` and `craft 3` (9 spare Teachings), Hero's Wit shows `✓ 20`, Small Lamp Grass is dimmed; "To farm" hides Hero's Wit; hovering a tile shows the popover.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/inventory
git commit -m "feat: inventory page with backpack-style material grid"
```

---

### Task 15: Dashboard sections

**Files:**
- Modify: `frontend/src/routes/+page.svelte`

**Interfaces:**
- Consumes: `Dashboard` additions, `api.setBossDone`, `MaterialTile`, `MaterialPopover`, `tileView`, `charTileView`, `weekdayNames`, `gapLabel`, `shouldPoll`.
- Produces test ids: `farm-today`, `boss-<name>` (with class `done` when ticked), `building-card-<slug>`; checkbox label "Done this week".

- [ ] **Step 1: Implement** — add to the `<script>`:

```ts
	import MaterialPopover from '$lib/MaterialPopover.svelte';
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { charTileView, gapLabel, shouldPoll, tileView, weekdayNames } from '$lib/materials';
	import type { WeeklyBoss } from '$lib/types';

	let toast = $state<string | null>(null);

	$effect(() => {
		if (!shouldPoll(data?.gaps)) return;
		const t = setTimeout(load, 2000);
		return () => clearTimeout(t);
	});

	const bosses = $derived([...(data?.weekly_bosses.bosses ?? [])].sort((a, b) => Number(a.done) - Number(b.done)));

	async function toggleBoss(b: WeeklyBoss) {
		const done = !b.done;
		b.done = done;
		try {
			await api.setBossDone(b.name, done);
			toast = null;
		} catch (e) {
			b.done = !done;
			toast = errorMessage(e);
		}
	}
```

Add after the expeditions panel (inside `{#if data}`):

```svelte
	{#if toast}<p class="error">{toast}</p>{/if}
	<p class="muted">{gapLabel(data.gaps, now)}</p>

	<section class="panel" data-testid="farm-today">
		<h2>Active today</h2>
		{#if data.building_cards.length === 0}
			<p class="muted">Set characters to Build to plan farming.</p>
		{:else if data.farm_today.domains.length === 0}
			<p class="muted">Nothing to farm in domains today ✓</p>
		{:else}
			<div class="cards">
				{#each data.farm_today.domains as d (d.id)}
					<div class="card">
						<div class="title">{d.name}</div>
						<div class="muted small">{weekdayNames(d.weekdays)}</div>
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

	<section class="panel">
		<h2>Weekly bosses</h2>
		{#if data.weekly_bosses.discounts_left !== null}
			<p class="muted">Discounted runs left {data.weekly_bosses.discounts_left}/{data.weekly_bosses.discounts_max}</p>
		{/if}
		{#if bosses.length === 0}
			<p class="muted">No weekly boss drops to farm ✓</p>
		{:else}
			<div class="cards">
				{#each bosses as b (b.name)}
					<div class="card" class:done={b.done} data-testid="boss-{b.name}">
						<label class="title">
							<input type="checkbox" checked={b.done} onchange={() => toggleBoss(b)} aria-label="Done this week" />
							{b.name}
						</label>
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

	<section class="panel">
		<h2>Building</h2>
		<div class="cards">
			{#each data.building_cards as card (card.character.id)}
				<div class="card build" data-testid="building-card-{card.character.slug}">
					<div class="head">
						{#if imgSrc(card.character.icon)}<img src={imgSrc(card.character.icon)} alt="" />{/if}
						<div>
							<a class="title" href="/characters/{card.character.slug}">{card.character.name}</a>
							{#if card.progress !== null}
								<div class="bar" role="progressbar" aria-valuenow={Math.round(card.progress * 100)}
									aria-valuemin={0} aria-valuemax={100}><span style="width: {card.progress * 100}%"></span></div>
							{/if}
						</div>
					</div>
					{#if card.skipped}
						<p class="muted">{card.character.name} planning isn't supported yet.</p>
					{:else if card.materials.length === 0}
						<p class="muted">Everything in the bag ✓</p>
					{:else}
						<div class="tiles-row">
							{#each card.materials as m (m.id)}
								<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={charTileView(m)} />
							{/each}
						</div>
					{/if}
				</div>
			{/each}
		</div>
	</section>
```

Add styles to the page's `<style>`:

```css
	.cards { display: flex; flex-wrap: wrap; gap: 12px; }
	.card { background: var(--panel-2); border: 1px solid var(--line); border-radius: 10px; padding: 10px;
		min-width: 220px; color: inherit; text-decoration: none; }
	.card.done { opacity: 0.45; }
	.card .title { font-weight: 600; display: flex; gap: 6px; align-items: center; }
	.small { font-size: 12px; }
	.tiles-row { display: flex; flex-wrap: wrap; gap: 8px; margin: 8px 0; }
	.avatars { display: flex; gap: 4px; }
	.avatars img { width: 28px; height: 28px; border-radius: 50%; background: var(--r0); }
	.card.build .head { display: flex; gap: 8px; align-items: center; }
	.card.build .head img { width: 40px; height: 40px; border-radius: 8px; background: var(--r0); }
	.bar { width: 140px; height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; }
	.bar span { display: block; height: 100%; background: var(--building); }
	section.panel { margin-top: 12px; }
```

- [ ] **Step 2: Check and look at it**

Run: `cd frontend; npm run check` → 0 errors. With the seeded app running, open `/`: Active today lists "Domain of Mastery: Forsaken Rift" with Guide to Freedom `−4`; Weekly bosses shows Stormterror with a checkbox that dims the card; Building shows Bennett and Furina with only short tiles and Neuvillette with "Everything in the bag ✓".

- [ ] **Step 3: Commit**

```bash
git add frontend/src/routes/+page.svelte
git commit -m "feat: dashboard active-today, weekly bosses and building cards"
```

---

### Task 16: Character detail — shortfall panel and planned weapon

**Files:**
- Modify: `frontend/src/routes/characters/[slug]/+page.svelte`

**Interfaces:**
- Consumes: `CharacterDetail.shortfall`, `.planned_weapon`, `.planned_weapon_id`; `api.weapons`, `api.setGoal`; `MaterialTile`, `charTileView`, `gapLabel`, `shouldPoll`.
- Produces test ids: `shortfall`, select labelled "Planned weapon".

- [ ] **Step 1: Implement** — in the `<script>` add:

```ts
	import MaterialTile from '$lib/MaterialTile.svelte';
	import { charTileView, gapLabel, shouldPoll } from '$lib/materials';
	import type { WeaponOption } from '$lib/types';

	let weapons = $state<WeaponOption[]>([]);
	let now = $state(Date.now());
	const weaponType = $derived(c?.weapon_type ?? null);

	$effect(() => {
		const type = weaponType; // derived: only refetches when the weapon type itself changes
		if (!type) return;
		api.weapons(type).then((w) => (weapons = w)).catch(() => (weapons = []));
	});

	$effect(() => {
		if (!shouldPoll(c?.shortfall?.gaps)) return;
		const t = setTimeout(() => load(page.params.slug ?? ''), 2000);
		return () => clearTimeout(t);
	});

	async function setPlannedWeapon(value: string) {
		if (!c) return;
		try {
			await api.setGoal(c.id, { planned_weapon_id: value === '' ? null : Number(value) });
			saveError = null;
			await load(page.params.slug ?? '');
		} catch (e) {
			saveError = errorMessage(e);
		}
	}
```

In `load()`, after `c = detail;` add `now = Date.now();`. In `update()`, after `c = { ...c, ...updated };` add `await load(page.params.slug ?? '');` so the shortfall panel shows "Updating…" right away.

Below the `<TargetsEditor ... />` (inside the same `build` block), add:

```svelte
			<label class="weapon-pick">
				<span>Planned weapon</span>
				<select aria-label="Planned weapon" value={c.planned_weapon_id ?? ''}
					onchange={(e) => setPlannedWeapon(e.currentTarget.value)}>
					<option value="">{c.owned && c.weapon ? `Equipped: ${c.weapon.name}` : 'None'}</option>
					{#each weapons as w (w.id)}<option value={w.id}>{'★'.repeat(w.rarity)} {w.name}</option>{/each}
				</select>
			</label>
```

Replace `<section class="panel muted">Material shortfall — arrives in phase 2.</section>` with:

```svelte
	{#if c.shortfall}
		<section class="panel" data-testid="shortfall">
			<h2>Material shortfall</h2>
			<p class="muted">{gapLabel(c.shortfall.gaps, now)}</p>
			{#if c.shortfall.gaps.skipped.includes(c.name)}
				<p class="muted">{c.name} planning isn't supported yet.</p>
			{:else if c.shortfall.materials.length === 0}
				<p class="muted">Everything in the bag ✓</p>
			{:else}
				<div class="tiles-row">
					{#each c.shortfall.materials as m (m.id)}
						<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={charTileView(m)} testid="short-{m.id}" />
					{/each}
				</div>
			{/if}
		</section>
	{/if}
```

Add styles: `.tiles-row { display: flex; flex-wrap: wrap; gap: 10px; } .weapon-pick { display: inline-flex; flex-direction: column; gap: 4px; margin-top: 12px; }`.

- [ ] **Step 2: Check and look at it**

Run: `cd frontend; npm run check` → 0 errors. With the seeded app: `/characters/bennett` shows the shortfall panel with Guide to Freedom `5/9 −4 shared`; choosing "Mistsplitter Reforged" in Planned weapon saves and the list keeps that choice after reload.

- [ ] **Step 3: Commit**

```bash
git add "frontend/src/routes/characters/[slug]/+page.svelte"
git commit -m "feat: character shortfall panel and planned weapon picker"
```

---

### Task 17: End-to-end test, README, final verification

**Files:**
- Create: `frontend/e2e/planner.spec.ts`
- Modify: `README.md`

- [ ] **Step 1: Write the e2e test**

```ts
// frontend/e2e/planner.spec.ts
import { expect, test } from '@playwright/test';

test('dashboard shows active domains and a weekly boss that can be ticked', async ({ page }) => {
	await page.goto('/');
	const today = page.getByTestId('farm-today');
	await expect(today.getByText('Domain of Mastery: Forsaken Rift')).toBeVisible();
	const boss = page.getByTestId('boss-Stormterror');
	await expect(boss).toBeVisible();
	await boss.getByRole('checkbox', { name: 'Done this week' }).check();
	await expect(boss).toHaveClass(/done/);
	await page.reload();
	await expect(page.getByTestId('boss-Stormterror')).toHaveClass(/done/);
});

test('inventory To farm filter shows only short tiles', async ({ page }) => {
	await page.goto('/inventory');
	await expect(page.getByTestId('tile-104003')).toBeVisible();   // Hero's Wit, met
	await page.getByRole('button', { name: 'To farm' }).click();
	await expect(page.getByTestId('tile-104302')).toBeVisible();   // Guide to Freedom, short
	await expect(page.getByTestId('tile-104003')).toHaveCount(0);
	await expect(page.getByTestId('tile-100055')).toHaveCount(0);  // unneeded
});
```

- [ ] **Step 2: Run all frontend checks**

Run: `cd frontend; npm run check; npm test; npm run build; npm run e2e`
Expected: svelte-check 0 errors; Vitest all pass; build succeeds; Playwright 4 passed (2 existing + 2 new)

- [ ] **Step 3: README** — add a "Planner (phase 2)" section to `README.md`:

```markdown
## Planner (phase 2)

Set characters to **Build** on the Characters page and pick targets. After each sync — and a few seconds after any
target change — the app asks HoYoLAB's calculator what is still missing:

- **Inventory** shows every upgrade material like the in-game backpack. Red `−N` = still to farm; `craft N` = you can
  craft it from spare lower tiers; `✓` = you have enough. Without a scanner import the app only knows counts for
  materials a Build character needs, so other tiles show no number.
- **Dashboard** shows domains open today (server time, reset 04:00), weekly bosses (tick them when done; they reset
  Monday 04:00 server time) and what each Build character still needs.
- **Planned weapon**: on a character's page you can plan for a weapon other than the equipped one; it is planned from
  level 1 because HoYoLAB only reports equipped weapons.

Known limits: Traveler and Manekin are not planned yet. <ascension-at-cap note from the Task 7 findings>.

Live check of the calculator against your account: `cd backend; ..\.venv\Scripts\python -m app.smoke --gaps`.
```

Replace `<ascension-at-cap note from the Task 7 findings>` with the one-sentence finding recorded in `docs/superpowers/notes/2026-11-19-phase2-calculator-findings.md` check 4.

- [ ] **Step 4: Full backend run and live sanity check**

Run: `cd backend; ..\.venv\Scripts\python -m pytest -q` → all pass.
Then `python run.py` against the real `.env`, press **Sync**, and confirm on the Dashboard that Active today matches the domains open in-game today and the Inventory shows shortfalls for the user's Build characters.

- [ ] **Step 5: Secret check and commit**

Run: `git diff --cached --stat` after staging and confirm no `.env`, `data/`, or `.e2e-data/` files are included; grep the staged diff for `ltoken`, `ltuid`, `cookie_token` and the user's UID digits — expect no matches.

```bash
git add frontend/e2e/planner.spec.ts README.md
git commit -m "test: planner e2e flow; docs: planner usage and limits"
```
