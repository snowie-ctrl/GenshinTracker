# Ad Astra Sub-project 10 — Teapot Materials Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add wood, Fabric and dyes as a new "Serenitea Pot" material category (from the public Yatta catalogue), shown as the last card in the Inventory backpack with GOOD scan counts or "—".

**Architecture:** `categorize()` in `backend/app/gamedata/materials.py` maps Yatta type `material` ids 101300–101499 to a new `teapot` category, appended to `CATEGORIES`. A catalogue version constant in `backend/app/gamedata/service.py` forces one catalogue refresh on existing databases. Everything downstream (GOOD key matching, the inventory endpoint, the Materials tab) already works per category, so it needs only tests, devseed rows and e2e coverage.

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest (backend); SvelteKit with Svelte 5 runes, TypeScript, vitest, Playwright (frontend).

**Spec:** `docs/superpowers/specs/2026-11-24-ad-astra-teapot-materials-design.md`

## Global Constraints

- Only public Yatta endpoints the app already calls; no cookie, UID, email or HoYoLAB call is added. No new code in `backend/app/sync/`.
- Public game-data code stays in `backend/app/gamedata/`.
- No migration (`game_material.category` is a plain string). Migration number 0014 stays free.
- Category key `teapot`; label exactly `Serenitea Pot: wood, fabric & dyes`; last entry of `CATEGORIES`.
- Selection rule exactly: `yatta_type == "material"` and `101300 <= id <= 101499`.
- `MATERIAL_CATALOGUE_VERSION = 2`, meta key `material_catalogue_version`.
- Test fixtures use names and ids only; made-up UID 800000001 where a UID is needed; no game art or personal data committed; no user name, email, Windows user name or absolute user path in any committed file.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

**Commands** (`PY` = the project venv python, `.venv/Scripts/python.exe` in the main checkout):
- Backend, from `backend/`: `PY -m pytest -q` (728 passing at start).
- Frontend, from `frontend/` (run `npm ci` first in a new worktree): `npm run check`, `npx vitest run` (192 at start), `npm run build`, `PYTHON=PY npx playwright test` (69 at start; workers 1, one shared seeded server: any test that changes state restores it; the server serves the built frontend, so build first).

## Plan-time note on the spec

The spec calls the Teapot card "last". `CATEGORY_ORDER` in `backend/app/planner/data.py` is `(*CATEGORIES, "other")`, so a synthetic "Other" group (materials that have totals but are missing from the catalogue) still comes after it. That group is empty whenever the catalogue is loaded. The plan keeps that order: Teapot is the last *catalogue* category.

## Review Focus

1. **An existing database whose catalogue is fresh (fetched under 7 days ago, keys and details all present) upgrades to this version.** It must refetch once so the teapot rows appear, then stop refetching. Pinned in Task 2 (`test_old_catalogue_version_forces_one_refresh`).
2. **A catalogue refresh that fails before storing.** The version must stay unset so the next start retries. Pinned in Task 2 (`test_failed_refresh_leaves_version_unset`).
3. **Teapot materials leaking into planning views.** No character needs wood, so they must be `unneeded` with `to_farm == 0` and never appear in the To-farm strip. Pinned in Task 3 (`test_inventory_teapot_group_is_last_catalogue_group`) and Task 4 (no `farm-101301` in the strip).
4. **Ids at the edges of the range, and non-`material` types inside it.** Pinned in Task 1 (`test_categorize_teapot_range`).
5. **Searching and the Owned filter with teapot tiles.** Searching "Birch" shows Birch Wood. With a scan, Owned keeps scanned teapot tiles. Pinned in Task 4.

---

## File map

| File | Change |
|---|---|
| `backend/app/gamedata/materials.py` | `teapot` category, label, id-range constants, `categorize` rule |
| `backend/app/gamedata/service.py` | `MATERIAL_CATALOGUE_VERSION`, `META_MAT_VERSION`, refresh check and store |
| `backend/app/devseed.py` | four teapot rows; version meta |
| `backend/tests/fixtures/yatta_material.json` | Birch Wood, Fabric, Strange Tooth items |
| `backend/tests/fixtures/yatta_material_details.json` | Birch Wood detail with sources |
| `backend/tests/test_materials.py` | categorize and parse tests |
| `backend/tests/test_gamedata.py` | ordering, sources, version refresh tests |
| `backend/tests/test_good_store.py` | GOOD keys match teapot rows |
| `backend/tests/test_api_planner.py` | inventory group order and label |
| `backend/tests/test_devseed.py` | devseed teapot group |
| `frontend/e2e/fixtures/good-sample.json` | `BirchWood`, `Fabric` counts |
| `frontend/e2e/good.spec.ts` | teapot counts after import, "—" after opt-out |
| `frontend/e2e/planner.spec.ts` | Teapot card last, faded "—", search |

---

### Task 1: Teapot category in the material catalogue

**Files:**
- Modify: `backend/app/gamedata/materials.py` (constants block at top; `categorize`)
- Modify: `backend/tests/fixtures/yatta_material.json`, `backend/tests/fixtures/yatta_material_details.json`
- Test: `backend/tests/test_materials.py`, `backend/tests/test_gamedata.py`

**Interfaces:**
- Produces: `CATEGORIES` ending in `"teapot"`; `CATEGORY_LABELS["teapot"] == "Serenitea Pot: wood, fabric & dyes"`; `TEAPOT_ID_MIN = 101300`, `TEAPOT_ID_MAX = 101499`; `categorize(yatta_type: str, rank: int, material_id: int) -> str | None` returning `"teapot"` for the range.

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_materials.py` (add `CATEGORIES, CATEGORY_LABELS` to the existing `from app.gamedata.materials import (...)` list):

```python
def test_categorize_teapot_range():
    assert categorize("material", 1, 101299) is None
    assert categorize("material", 1, 101300) == "teapot"
    assert categorize("material", 1, 101301) == "teapot"      # Birch Wood
    assert categorize("material", 1, 101404) == "teapot"      # Blue Dye
    assert categorize("material", 1, 101499) == "teapot"
    assert categorize("material", 1, 101500) is None
    assert categorize("material", 1, 100618) is None          # Strange Tooth: type material, outside range
    assert categorize("cookingIngredient", 1, 101301) is None  # inside range, wrong type


def test_teapot_category_is_last_and_labelled():
    assert CATEGORIES[-1] == "teapot"
    assert CATEGORY_LABELS["teapot"] == "Serenitea Pot: wood, fabric & dyes"
    assert set(CATEGORIES) <= set(CATEGORY_LABELS)


def test_parse_material_list_keeps_teapot_materials():
    mats = {m.id: m for m in parse_material_list(load_fixture("yatta_material.json"))}
    assert mats[101301].category == "teapot" and mats[101301].name == "Birch Wood"
    assert mats[101401].category == "teapot" and mats[101401].region is None
    assert 100618 not in mats
```

- [ ] **Step 2: Add the fixture items**

In `backend/tests/fixtures/yatta_material.json`, add three entries to `data.items` (keep the JSON valid; match the existing one-item-per-line style):

```json
    "100618": {"id": 100618, "name": "Strange Tooth", "type": "material", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_100618", "rank": 1, "route": "Strange Tooth"},
    "101301": {"id": 101301, "name": "Birch Wood", "type": "material", "recipe": null, "mapMark": true, "icon": "UI_ItemIcon_101301", "rank": 1, "route": "Birch Wood"},
    "101401": {"id": 101401, "name": "Fabric", "type": "material", "recipe": null, "mapMark": false, "icon": "UI_ItemIcon_101401", "rank": 1, "route": "Fabric"},
```

In `backend/tests/fixtures/yatta_material_details.json`, add a top-level entry:

```json
  "101301": {"response": 200, "data": {"name": "Birch Wood", "type": "Material", "recipe": null,
    "source": [{"name": "Found in the wild", "type": "single"},
               {"name": "Recommendation: Cut from Windwail Highland", "type": "single"},
               {"name": "Purchased from Realm Depot: Wood", "type": "single"},
               {"name": "Convert Wood", "type": "single"}],
    "icon": "UI_ItemIcon_101301", "rank": 1, "route": "Birch Wood"}},
```

- [ ] **Step 3: Update the refresh ordering test and add a sources assertion**

In `backend/tests/test_gamedata.py`, `test_refresh_materials_stores_catalogue_chains_and_domains`: change the category order list to include `"teapot"`, and add assertions after the `talent` order line:

```python
        assert cats == sorted(cats, key=["exp", "ascension", "specialty", "talent", "weapon",
                                         "enemy", "weekly", "special", "teapot"].index)
        assert [m.id for m in order if m.category == "teapot"] == [101301, 101401]
        assert order[-1].category == "teapot"
        assert mats[101301].sources == [
            {"kind": "text", "name": "Found in the wild", "days": []},
            {"kind": "text", "name": "Recommendation: Cut from Windwail Highland", "days": []},
            {"kind": "text", "name": "Purchased from Realm Depot: Wood", "days": []},
            {"kind": "text", "name": "Convert Wood", "days": []},
        ]
        assert 100618 not in mats
```

- [ ] **Step 4: Run the tests to verify they fail**

Run (from `backend/`): `PY -m pytest tests/test_materials.py tests/test_gamedata.py -q`
Expected: FAIL. `categorize` returns `None` for 101301; `CATEGORIES[-1] == "special"`; `KeyError: 101301` in the refresh test.

- [ ] **Step 5: Implement**

In `backend/app/gamedata/materials.py`:

```python
CATEGORIES: tuple[str, ...] = ("exp", "ascension", "specialty", "talent", "weapon", "enemy", "weekly", "special",
                               "teapot")
CATEGORY_LABELS = {
    "exp": "Character EXP & weapon enhancement",
    "ascension": "Character ascension",
    "specialty": "Local specialties",
    "talent": "Talent books",
    "weapon": "Weapon ascension",
    "enemy": "Common enemy drops",
    "weekly": "Weekly boss drops",
    "special": "Crowns & special",
    "teapot": "Serenitea Pot: wood, fabric & dyes",
    "other": "Other",
}
```

Below `CROWN_ID = 104319` add:

```python
TEAPOT_ID_MIN, TEAPOT_ID_MAX = 101300, 101499   # Yatta 'material': 1013xx woods, 1014xx Fabric and dyes
```

In `categorize`, before the final `return None`:

```python
    if yatta_type == "material" and TEAPOT_ID_MIN <= material_id <= TEAPOT_ID_MAX:
        return "teapot"
```

Update the `fetch_material_catalogue` docstring "The eight-category catalogue" to "The material catalogue (every category in CATEGORIES)".

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_materials.py tests/test_gamedata.py -q`
Expected: PASS.

Then the whole suite, because the fixture is shared: `PY -m pytest -q`
Expected: all pass (728 + 3 new = 731). If a test that counts catalogue rows from `yatta_material.json` fails, update its expected count by the two new teapot rows and say so in the report.

- [ ] **Step 7: Commit**

```bash
git add backend/app/gamedata/materials.py backend/tests/fixtures/yatta_material.json backend/tests/fixtures/yatta_material_details.json backend/tests/test_materials.py backend/tests/test_gamedata.py
git commit -m "feat(gamedata): teapot category for wood, fabric and dyes

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Catalogue version forces one refresh on existing databases

**Files:**
- Modify: `backend/app/gamedata/service.py` (constants near `META_MAT_KEYS`; `materials_need_refresh`; `refresh_materials` final transaction)
- Test: `backend/tests/test_gamedata.py`

**Interfaces:**
- Consumes: `refresh_materials(session_factory, http, now=None, force=False) -> bool`, `_get_meta(session, key)`, `_set_meta(session, key, value)` (existing).
- Produces: `MATERIAL_CATALOGUE_VERSION: int = 2`, `META_MAT_VERSION: str = "material_catalogue_version"` (Task 3's devseed imports both).

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_gamedata.py`, add `MATERIAL_CATALOGUE_VERSION, META_MAT_VERSION` to the `from app.gamedata.service import (...)` list, then append:

```python
async def test_refresh_materials_stores_catalogue_version(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_materials(session_factory, http)
    with session_factory() as s:
        assert _get_meta(s, META_MAT_VERSION) == MATERIAL_CATALOGUE_VERSION


async def test_old_catalogue_version_forces_one_refresh(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_materials(session_factory, http)
        with session_factory.begin() as s:
            s.merge(GameMeta(key=META_MAT_VERSION, value=MATERIAL_CATALOGUE_VERSION - 1))
        assert await refresh_materials(session_factory, http) is True     # fresh otherwise, but old version
        assert await refresh_materials(session_factory, http) is False    # now current: no more refetching


async def test_missing_catalogue_version_forces_a_refresh(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport()) as http:
        await refresh_materials(session_factory, http)
        with session_factory.begin() as s:
            s.delete(s.get(GameMeta, META_MAT_VERSION))
        assert await refresh_materials(session_factory, http) is True


async def test_failed_refresh_leaves_version_unset(session_factory):
    async with httpx.AsyncClient(transport=yatta_transport(status=500)) as http:
        assert await refresh_materials(session_factory, http) is False
    with session_factory() as s:
        assert _get_meta(s, META_MAT_VERSION) is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_gamedata.py -q -k version`
Expected: FAIL with `ImportError: cannot import name 'MATERIAL_CATALOGUE_VERSION'`.

- [ ] **Step 3: Implement**

In `backend/app/gamedata/service.py`, after `META_MAT_KEYS = "material_keys_all"`:

```python
META_MAT_VERSION = "material_catalogue_version"
MATERIAL_CATALOGUE_VERSION = 2   # bump when categorize() changes, so existing databases refetch once
```

In `materials_need_refresh`, after the `META_MAT_KEYS` check:

```python
    if _get_meta(session, META_MAT_VERSION) != MATERIAL_CATALOGUE_VERSION:
        return True
```

In `refresh_materials`, in the final `with session_factory.begin() as s:` block, after `_set_meta(s, META_MAT_FETCHED, iso(now))`:

```python
        _set_meta(s, META_MAT_VERSION, MATERIAL_CATALOGUE_VERSION)
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_gamedata.py -q`
Expected: PASS (including the existing `test_refresh_materials_is_skipped_when_fresh`).

Then: `PY -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/gamedata/service.py backend/tests/test_gamedata.py
git commit -m "feat(gamedata): catalogue version forces one material refresh

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Devseed rows, GOOD matching and inventory grouping

**Files:**
- Modify: `backend/app/devseed.py` (`MATERIALS` list; meta block near `s.merge(GameMeta(key="materials_fetched_at", ...))`)
- Test: `backend/tests/test_good_store.py`, `backend/tests/test_api_planner.py`, `backend/tests/test_devseed.py`

**Interfaces:**
- Consumes: `MATERIAL_CATALOGUE_VERSION`, `META_MAT_VERSION` (Task 2); `CATEGORY_LABELS["teapot"]` (Task 1); `match_file`, `KeyIndex.build`, `GET /api/inventory` (existing).
- Produces: devseed teapot rows 101301 Birch Wood, 101302 Cuihua Wood, 101401 Fabric, 101402 Red Dye (Task 4's e2e tests use 101301 and 101401).

- [ ] **Step 1: Write the failing tests**

Append to `backend/tests/test_good_store.py`:

```python
def test_teapot_materials_match_by_name(session_factory):
    seed_catalogue(session_factory)
    with session_factory.begin() as s:
        for order, (mid, name) in enumerate([(101301, "Birch Wood"), (101401, "Fabric")], start=10):
            s.add(GameMaterial(id=mid, name=name, icon=f"UI_ItemIcon_{mid}", rarity=1, yatta_type="material",
                               category="teapot", family=mid, craft_from=None, sources=[], sort_order=order,
                               detail_fetched=True))
    body = {"format": "GOOD", "version": 2, "materials": {"BirchWood": 250, "Fabric": 40, "Fowl": 3}}
    m = match_file(parse_good(json.dumps(body).encode()), index(session_factory))
    assert m.materials == {101301: 250, 101401: 40}
    assert m.counts["materials"] == {"matched": 2, "ignored": 1, "unmatched": 0}
```

Append to `backend/tests/test_api_planner.py`:

```python
def test_inventory_teapot_group_is_last_catalogue_group(paths):
    sf = setup(paths)
    with sf.begin() as s:
        for mid, name in [(101301, "Birch Wood"), (101401, "Fabric")]:
            s.add(GameMaterial(id=mid, name=name, icon=f"UI_ItemIcon_{mid}", rarity=1, yatta_type="material",
                               category="teapot", family=mid, craft_from=None, sources=[], sort_order=mid,
                               detail_fetched=True))
    with make_client(paths) as client:
        body = client.get("/api/inventory").json()
    assert body["categories"][-1]["key"] == "teapot"
    teapot = body["categories"][-1]
    assert teapot["label"] == "Serenitea Pot: wood, fabric & dyes"
    assert [m["id"] for m in teapot["materials"]] == [101301, 101401]
    assert all(m["state"] == "unneeded" and m["to_farm"] == 0 and m["characters"] == []
               for m in teapot["materials"])
```

Append to `backend/tests/test_devseed.py`:

```python
def test_devseed_teapot_materials(tmp_path):
    from app.db.models import GameMeta
    from app.gamedata.service import MATERIAL_CATALOGUE_VERSION, META_MAT_VERSION

    seed(tmp_path)
    with make_client(Paths(tmp_path)) as client:
        inv = client.get("/api/inventory").json()
    teapot = inv["categories"][-1]
    assert teapot["key"] == "teapot"
    assert [m["id"] for m in teapot["materials"]] == [101301, 101302, 101401, 101402]
    assert teapot["materials"][0]["sources"] == [{"kind": "text", "name": "Found in the wild", "days": []}]
    sf = make_session_factory(make_engine(Paths(tmp_path).db_file))
    with sf() as s:
        assert s.get(GameMeta, META_MAT_VERSION).value == MATERIAL_CATALOGUE_VERSION
```

(`Paths`, `make_engine`, `make_session_factory`, `make_client` and `seed` are already imported at the top of `test_devseed.py`.)

- [ ] **Step 2: Run the tests to verify which fail**

Run: `PY -m pytest tests/test_good_store.py tests/test_api_planner.py tests/test_devseed.py -q`
Expected: `test_devseed_teapot_materials` FAILS (no teapot group). The GOOD and inventory tests should already PASS, because they pin behaviour that needs no code change (spec sections 4 and 5). If either fails, stop and report: it means a downstream view does not handle the new category.

- [ ] **Step 3: Implement the devseed rows**

In `backend/app/devseed.py`, before `MATERIALS = [` add:

```python
WILD_SOURCE = {"kind": "text", "name": "Found in the wild", "days": []}
```

Append to the end of `MATERIALS` (after the Crown row):

```python
    (101301, "Birch Wood", "teapot", 1, None, "material", [WILD_SOURCE]),
    (101302, "Cuihua Wood", "teapot", 1, None, "material", [WILD_SOURCE]),
    (101401, "Fabric", "teapot", 1, None, "material", [WILD_SOURCE]),
    (101402, "Red Dye", "teapot", 1, None, "material", [WILD_SOURCE]),
```

After `s.merge(GameMeta(key="materials_fetched_at", value=iso(now)))` add:

```python
        s.merge(GameMeta(key=META_MAT_VERSION, value=MATERIAL_CATALOGUE_VERSION))
```

and add `from app.gamedata.service import MATERIAL_CATALOGUE_VERSION, META_MAT_VERSION` to the imports at the top of `devseed.py`, next to the other `app.` imports in alphabetical position.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_good_store.py tests/test_api_planner.py tests/test_devseed.py -q`
Expected: PASS.

Then: `PY -m pytest -q`
Expected: all pass (731 + 4 from Task 2 + 3 here = 738).

- [ ] **Step 5: Commit**

```bash
git add backend/app/devseed.py backend/tests/test_good_store.py backend/tests/test_api_planner.py backend/tests/test_devseed.py
git commit -m "feat(devseed): teapot materials; pin GOOD matching and inventory order

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: Inventory e2e coverage

**Files:**
- Modify: `frontend/e2e/fixtures/good-sample.json`
- Test: `frontend/e2e/good.spec.ts`, `frontend/e2e/planner.spec.ts`

**Interfaces:**
- Consumes: devseed rows 101301 Birch Wood and 101401 Fabric (Task 3). The Materials tab renders each category as `section[data-testid="category-<key>"]` with an `h2` label and tiles `data-testid="tile-<id>"`; faded tiles have class `dim`; the To-farm strip is `data-testid="to-farm"` with tiles `farm-<id>` (existing, `frontend/src/routes/inventory/+page.svelte`).

- [ ] **Step 1: Write the failing tests**

In `frontend/e2e/planner.spec.ts`, append:

```ts
test('Serenitea Pot card is the last backpack card, faded without a scan, searchable', async ({ page }) => {
	await page.goto('/inventory');
	const card = page.getByTestId('category-teapot');
	await expect(card.getByRole('heading')).toHaveText('Serenitea Pot: wood, fabric & dyes');
	await expect(page.locator('section[data-testid^="category-"]').last()).toHaveAttribute('data-testid', 'category-teapot');
	await expect(card.getByTestId('tile-101301')).toContainText('—');       // Birch Wood, no scan
	await expect(card.getByTestId('tile-101301')).toHaveClass(/dim/);
	await expect(page.getByTestId('to-farm').getByTestId('farm-101301')).toHaveCount(0);
	await page.getByLabel('Search materials').fill('Birch');
	await expect(page.getByTestId('tile-101301')).toBeVisible();
	await expect(page.getByTestId('tile-101401')).toHaveCount(0);          // Fabric filtered out
	await page.getByLabel('Search materials').fill('');
});
```

In `frontend/e2e/fixtures/good-sample.json`, change the `materials` line to:

```json
  "materials": {"SmallLampGrass": 37, "HerosWit": 120, "GuideToFreedom": 2, "Fowl": 4, "BirchWood": 250, "Fabric": 40},
```

In `frontend/e2e/good.spec.ts`:

- Change the toast assertion to `'Imported 5 materials, 2 weapons, 3 artifacts.'`.
- After the `tile-104302` assertions (before the Owned click), add:

```ts
	await expect(page.getByTestId('tile-101301')).toContainText('250');      // Birch Wood from the scan
	await expect(page.getByTestId('tile-101301')).not.toHaveClass(/dim/);
	await expect(page.getByTestId('tile-101401')).toContainText('40');       // Fabric
```

- Inside the Owned block, after `await expect(page.getByTestId('tile-100055')).toBeVisible();`, add:

```ts
	await expect(page.getByTestId('tile-101301')).toBeVisible();            // scanned teapot tile kept
	await expect(page.getByTestId('tile-101302')).toHaveCount(0);           // Cuihua Wood: not in the scan
```

- After opting out, after `await expect(page.getByTestId('tile-100055')).not.toContainText('37');`, add:

```ts
	await expect(page.getByTestId('tile-101301')).toContainText('—');
```

- [ ] **Step 2: Build and run the e2e tests to verify the new ones pass against Task 3's seed**

These tests exercise behaviour delivered by Tasks 1–3 with no frontend change, so they are expected to pass at once. To confirm they really test something, first run the new planner test with `'category-teapot'` temporarily changed to `'category-teapotx'` in the `.last()` assertion. It must FAIL. Then revert that change.

Run (from `frontend/`): `npm run build` then `PYTHON=PY npx playwright test e2e/planner.spec.ts e2e/good.spec.ts`
Expected: PASS (with the temporary mutation: the planner teapot test FAILS).

- [ ] **Step 3: Run the whole e2e suite**

Run: `PYTHON=PY npx playwright test`
Expected: 70 passed (69 + 1 new). The GOOD test opts out at the end, so the shared server state is restored.

- [ ] **Step 4: Commit**

```bash
git add frontend/e2e/fixtures/good-sample.json frontend/e2e/good.spec.ts frontend/e2e/planner.spec.ts
git commit -m "test(e2e): Serenitea Pot card in the Inventory backpack

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Verification

- [ ] **Step 1: Run every gate**

From `backend/`: `PY -m pytest -q`. Expected: 738 passed.
From `frontend/`: `npm run check` (0 errors, 0 warnings), `npx vitest run` (192 passed), `npm run build` (succeeds), `PYTHON=PY npx playwright test` (70 passed).

- [ ] **Step 2: Check the upgrade path on a copy of the real database (read-only on the original)**

Copy the real database file to the scratchpad (never modify the original). Against the copy, run a small script with `PY -I` that opens it, calls `materials_need_refresh(session, utcnow())` and prints only `True`/`False`. Expected: `True` (the version meta is missing). Print nothing else from the database, no personal data. Do not run migrations on the original.

- [ ] **Step 3: Sensitive-content scan**

Run `git diff main...HEAD` and check it for cookie values, tokens, email addresses, real UIDs (anything other than 800000001), absolute user paths and Windows user names. Write the search terms into the shell command only, never into a committed file. Expected: nothing found.

- [ ] **Step 4: Report** the counts from Step 1, the Step 2 result and the Step 3 result.
