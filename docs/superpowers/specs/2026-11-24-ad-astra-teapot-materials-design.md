# Ad Astra Sub-project 10 — Teapot Materials

**Date:** 2026-11-24
**Status:** Approved by the user 2026-11-24
**Frame:** `2026-11-22-ad-astra-revision-overview-design.md` (sub-project 10 of 10, the last of the revision). Extends the Inventory backpack from Inventory and Events (`2026-11-23-ad-astra-inventory-events-design.md`, section 5) and the GOOD import from Phase 6 (`2026-11-22-phase6-good-import-design.md`).
**Scope:** Wood, Fabric and dyes become a new material category, "Serenitea Pot", taken from the public Yatta catalogue. They show as the last card in the Inventory backpack with the existing best-known count (a GOOD scan count, or "—"). Counts only: no "needed" amounts, no furnishing planner.

---

## 1. Decisions made with the user

| Topic | Decision |
|---|---|
| What the app does with teapot materials | **Counts only.** A Teapot category in the backpack showing GOOD scan counts. A furnishing planner (pick furnishings or sets, compute wood needed) and teapot replica share codes were offered and declined |
| Which materials | **Wood, Fabric, dyes**: the 33 woods plus Fabric, Red Dye, Yellow Dye and Blue Dye. Forging ores (Iron Chunk etc.) were offered and declined |
| Selection rule | Yatta type `material` with id 101300–101499, so new woods join automatically. No hand-curated list (the user does not want data that needs maintaining every patch) |
| Card without a GOOD scan | Shown like every other category: tiles faded with "—"; the existing "Import a GOOD scan to see every count" hint covers it. Hiding the card without a scan was offered and declined |
| Existing databases | A catalogue version constant triggers one catalogue refresh at the next start. No migration |

---

## 2. Feasibility (probed 2026-11-24, public hosts only, no cookie/UID/email)

| Candidate | Finding | Verdict |
|---|---|---|
| Yatta `material` list (`gi.yatta.moe/api/v2/en/material`, already used) | Type `material` (71 items) holds the woods at ids 101301–101334 (Birch Wood … Larch Wood; 101306 unused) and Fabric 101401, Red/Yellow/Blue Dye 101402–101404. No id in 101300–101499 belongs to anything else. All rarity 1. Today `categorize()` returns `None` for them, so they are not in `game_material` and a GOOD scan's wood counts are "ignored" | **Used** |
| Yatta `material/<id>` detail (already used) | Wood: `recipe: null`; `source` lists "Found in the wild", "Recommendation: Cut from Windwail Highland", "Purchased from Realm Depot: Wood", "Convert Wood". The existing parser keeps these as `text` sources | Popover sources for free |
| Yatta `furniture` (2,409 items) and `furniture/<id>` | Detail has `recipe.input` (e.g. 8 Fragrant Cedar Wood + 4 White Iron Chunk) | Would serve a furnishing planner; not used (declined) |
| Yatta `furnitureSuite` and `furnitureSuite/<id>` | Set pieces with counts (`suiteItemList`), gift-set `favoriteNpcList` | Not used (declined) |
| HoYoLAB furnishing calculator (genshin.py; needs the cookie, unofficial) | Lists furnishings and reads a teapot replica share code's blueprint. No endpoint for backpack counts or owned blueprints | Not used (declined) |
| Icons | `UI_ItemIcon_<id>` through `/api/img` (enka.network then Yatta, both already allowed) | No change |

Licence note: Yatta data is datamined game data, the same risk as the material catalogue the app already uses. A public site would need the same review as for the rest of `gamedata/`.

---

## 3. Data (`backend/app/gamedata/`)

### 3.1 Category

`materials.py`:

- `CATEGORIES` gains `"teapot"` as the last entry: `("exp", "ascension", "specialty", "talent", "weapon", "enemy", "weekly", "special", "teapot")`.
- `CATEGORY_LABELS["teapot"] = "Serenitea Pot: wood, fabric & dyes"`.
- Constants `TEAPOT_ID_MIN = 101300`, `TEAPOT_ID_MAX = 101499`.
- `categorize(yatta_type, rank, material_id)` returns `"teapot"` when `yatta_type == "material"` and `TEAPOT_ID_MIN <= material_id <= TEAPOT_ID_MAX`. The check sits with the other rules; no existing rule matches type `material`, so no other category changes.

Order inside the card follows the existing `_recompute_family_and_order` sort (category, Yatta type, family, rarity, id). Every teapot material has the same type and rarity and no craft chain, so tiles go by id: woods first, then Fabric, then the dyes.

The planner, Dashboard, Teams shortfall and To-farm strip need no change: they read `CATEGORY_LABELS` by key, and no character or team needs wood, so `to_farm` stays 0 and the new materials never appear outside the backpack.

### 3.2 Refresh for existing databases

`service.py`:

- `MATERIAL_CATALOGUE_VERSION = 2` and meta key `META_MAT_VERSION = "material_catalogue_version"`.
- `materials_need_refresh` also returns `True` when the stored version is missing or differs from the constant.
- `refresh_materials` stores the constant after a successful refresh (in the same transaction as `META_MAT_FETCHED`).

At the next app start the catalogue refreshes once: 37 new rows, 37 detail fetches (concurrency 4, as today). A failed refresh leaves the version unset, so it retries on the next start, as for any other refresh failure. Future category changes bump the constant.

No migration: `game_material.category` is a plain string column. Migration number 0014 stays free.

---

## 4. GOOD import

No code change. GOOD keys are built from catalogue names (`good_key`): `BirchWood`, `CuihuaWood`, `Fabric`, `RedDye`, and so on. Once the materials are in `game_material`, an import counts them as matched instead of ignored and stores them in `good_material`. A snapshot imported before this change keeps its old rows; re-importing the file fills the teapot counts. The Settings import summary already shows matched/ignored/unmatched counts.

---

## 5. Inventory (frontend)

No component change. `GET /api/planner/inventory` already returns one group per category in `CATEGORY_ORDER`, and the Materials tab renders each group as a category card. The new card appears last, titled with the label above.

- Tiles use the best-known count from sub-project 6: the GOOD scan count when a scan is active, otherwise "—". Zero or "—" tiles are faded.
- The "All" and "Owned" filters, search, and the popover (sources; no "needed by" list) work unchanged.
- The To-farm strip never lists teapot materials.

---

## 6. Errors and empty states

| Situation | Behaviour |
|---|---|
| No GOOD scan | Card shows 37 faded "—" tiles; the existing hint under the filter bar suggests importing a scan |
| Scan imported before this change | Teapot tiles show "—" (0 rows) until the file is re-imported; old counts for other materials are unchanged |
| Catalogue refresh fails | Same as today: `materials_last_error` set, the version stays unset, retried next start; the card is absent until a refresh succeeds |
| Yatta adds a non-teapot item in 101300–101499 | It would show in the Teapot card. Accepted: the range has held only wood, fabric and dye since teapot release |

---

## 7. Security and data safety

- Only public Yatta endpoints the app already calls; no cookie, UID, email or HoYoLAB call is added.
- No new code in `backend/app/sync/`.
- Icons load at runtime through `/api/img`; no game art is committed. Test fixtures use names and ids only.

---

## 8. Testing

Backend (pytest):

- `categorize`: `material` at 101299 → `None`, 101300 → teapot, 101301 → teapot, 101404 → teapot, 101499 → teapot, 101500 → `None`; a non-`material` type inside the range (e.g. `cookingIngredient` at 101301) → `None`.
- `parse_material_list`: a trimmed fixture with a wood, Fabric and a food item keeps the wood and Fabric as `teapot` with no region.
- `CATEGORIES` ends with `teapot`; `CATEGORY_LABELS` has every category.
- `materials_need_refresh`: true when the version meta is missing or old, false when current and otherwise fresh; `refresh_materials` stores the version.
- Ordering: teapot rows sort after `special`, by id.
- GOOD: `match_file` counts `BirchWood` and `Fabric` as matched when they are in the catalogue.
- Inventory endpoint: the `teapot` group is last and has the label.

Frontend: no logic change. Existing Vitest stays green.

Playwright (shared seeded server, 1 worker; state restored):

- Inventory without a scan: the Serenitea Pot card is present, last, with faded "—" tiles.
- `good.spec.ts`: after importing the sample fixture (which gains `BirchWood` and `Fabric` counts), the teapot tiles show those counts; opting out restores "—".

Dev seed (`devseed.py`): adds Birch Wood, Cuihua Wood, Fabric and Red Dye as `teapot` rows with `UI_ItemIcon_<id>` icons and a "Found in the wild" source.

---

## 9. Out of scope

- "Needed" amounts and a furnishing or furnishing-set planner (Yatta recipes are available if this is wanted later).
- Teapot replica share codes and any HoYoLAB furnishing calculator call.
- Forging ores.
- Realm currency, the Realm Depot and Tubby's shop.
- Showing teapot materials anywhere but the Inventory backpack.

---

## 10. Done when

- After one app start, the Inventory Materials tab shows a last "Serenitea Pot: wood, fabric & dyes" card with every wood, Fabric and the three dyes.
- A GOOD import fills their counts; without a scan they show "—".
- pytest, `npm run check`, Vitest, `npm run build` and Playwright all pass.

---

## 11. Hard constraints (unchanged)

Cookie values only in the git-ignored `.env`; unofficial API code only in `backend/app/sync/` and `wishes/`, public game data in `backend/app/gamedata/`; test fixtures use made-up UIDs (800000001); no personal data or game art committed; images load through `/api/img`; the user's name, email or any absolute user path never goes into a committed file or to an external service.
