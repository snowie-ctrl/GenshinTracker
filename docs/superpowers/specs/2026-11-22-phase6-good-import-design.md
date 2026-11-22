# Phase 6 — GOOD Inventory Import: Design

**Date:** 2026-11-22
**Status:** Approved 2026-11-22 (amended while planning: §2 ignored keys, §3 module list, §4 `location` column)
**Parent:** [Overview design](2026-11-19-genshintracker-overview-design.md). Delivers the item the overview promised ("optional GOOD import", "full owned list only when a GOOD import exists", §10 "GOOD files from existing tools are imported") and that [Phase 2](2026-11-19-phase2-planner-design.md) deferred ("exact counts for every tile", "weapon inventory").

---

## 1. Goal

Users who choose to can import a **GOOD** file (Genshin Open Object Description, exported by scanner tools such as Inventory Kamera or Irminsul). The Inventory page then shows exact owned counts on every material tile, a full list of owned weapons (including unequipped ones), and a raw list of owned artifacts.

The HoYoLAB calculator stays the core. Without an import, or with the feature switched off, the app behaves exactly as it does today.

### Why opt-in

The app only reads a JSON file and never touches the game. The scanner that produces the file is a third-party tool, and HoYoverse's terms forbid those. Screen-scanning tools simulate input; packet-reading tools read game traffic. Users who don't want that risk keep the full calculator-based experience.

### Agreed decisions

| Topic | Decision |
|---|---|
| Scope | GOOD import only; no other deferred items |
| Opt-in | Settings toggle `good_import_enabled`, **off by default**. Off hides all GOOD UI and API fields, but keeps the stored data. A separate **Delete imported data** button wipes it. |
| Freshness | **Live first, GOOD fills in.** Live calculator data wins wherever it is exact; to-farm math never uses GOOD. |
| Data used | Materials, weapons, artifacts. GOOD `characters` are ignored (characters come live from HoYoLAB). |
| Artifacts | Raw owned list with filters only; no scoring or planning. |
| Mechanism | Browser upload of the `.json`; each import **replaces** the previous snapshot; only the latest is kept. |

### Out of scope

- Watched folders, auto-import, import history or diffs.
- Writing a scanner, or calling any scanner.
- Artifact scoring, optimisation or planning.
- Using GOOD counts in to-farm, crafting, Farm today, Weekly bosses or Building cards.
- Importing GOOD `characters`, or exporting GOOD.

---

## 2. GOOD format (what we read)

A JSON object with `format: "GOOD"`, `version` 1–3, an optional `source` string, and optional blocks:

- `materials`: object `{ "<MaterialKey>": count }`. Scanners leave out items with a count of zero.
- `weapons`: list of `{ key, level, ascension, refinement, location, lock }`. `location` is a character key or `""`.
- `artifacts`: list of `{ setKey, slotKey, rarity, level, mainStatKey, substats: [{ key, value }], location, lock }`. `slotKey` is one of `flower`, `plume`, `sands`, `goblet`, `circlet`.
- `characters`: ignored.

Unknown extra fields are ignored. Missing blocks count as empty, so a materials-only file is valid.

### Key matching

A GOOD key is the English name in PascalCase with every non-alphanumeric character removed, for example `ShivadaJadeGemstone`, `WolfsGravestone` (from "Wolf's Gravestone") and `GladiatorsFinale`. One function, `good_key(name)`, builds that form: fold accents to ASCII, split on whitespace and hyphens, drop the remaining non-alphanumerics in each word, capitalise each word's first letter, and join. It is applied to:

- `game_material.name` → material ids,
- `game_weapon.name` → weapon ids,
- `game_artifact_set.name` → artifact set ids (new table, §4),
- `game_character.name` → character ids (for `location`). The Traveler keys (`Traveler`, or any key starting with `Traveler`) map to the owned Traveler, if exactly one is found.

If two catalogue names produce the same key, the first id by `sort_order`/id wins, and the collision is logged by key only, without counts. Material keys that are not in the planner catalogue but are known Yatta items (food, potions, quest items) are counted as **ignored**. Game-data refresh stores the GOOD key of every Yatta material in `game_meta.material_keys_all` for this. Other keys that match nothing are counted as **unmatched** and listed in the import summary as `<block>:<Key>` (`material`, `weapon`, `set`, `character`), then dropped.

---

## 3. Module layout

`backend/app/good/` is a new package with no network access. It is not unofficial API code, so it lives outside `sync/`.

| File | Responsibility |
|---|---|
| `parse.py` | Validate and parse the uploaded bytes into dataclasses (`GoodFile`, `GoodWeapon`, `GoodArtifact`). Raises `GoodFormatError` with a user-facing message. |
| `keys.py` | `good_key(name)` and `KeyIndex.build(session)`, which looks up material, weapon, set and character ids. |
| `store.py` | `replace_snapshot(session, parsed, index, now)` returns an `ImportSummary`. `delete_snapshot(session)`. `load_snapshot(session)` is read-only and returns what the planner and API need. |
| `check.py` | `python -m app.good.check --db COPY --refresh FILE` prints only match counts and unmatched keys for a real export (live check). |

The §5.1 tile rules live in the frontend's existing `tileView`; the backend only supplies `scan`.

Setting access goes through the existing `settings/store.py`.

---

## 4. Data model

One Alembic migration.

### Game data

| Table | Columns |
|---|---|
| `game_artifact_set` | `id` PK, `name`, `icon`, `sort_order` (from Yatta `/reliquary`, refreshed with the other game data; an unreachable endpoint keeps the cache and stores the error like the other game-data parts) |

### User data (sync never writes these)

| Table | Columns |
|---|---|
| `good_import` | single row (`id = 1`): `imported_at`, `source` (string from the file, truncated to 64 chars, or null), `counts` (JSON: matched/unmatched per block), `unmatched` (JSON list of keys, capped at 200) |
| `good_material` | `material_id` PK, `count` |
| `good_weapon` | `id` PK (autoincrement), `weapon_id`, `level`, `ascension`, `refinement`, `location` (raw GOOD character key or null), `character_id` (nullable), `lock` |
| `good_artifact` | `id` PK (autoincrement), `set_id`, `slot`, `rarity`, `level`, `main_stat`, `substats` (JSON list of `{key, value}`), `location`, `character_id` (nullable), `lock` |

### Setting

`good_import_enabled`: bool, default `false`, stored in the existing `setting` table.

### Rules

- An import deletes and rewrites all four `good_*` rows in **one transaction**. A file that fails validation changes nothing.
- Delete removes all four in one transaction. The toggle is left as it is.
- The file is parsed in memory and never written to disk. Its contents are never logged.

---

## 5. Behaviour

### 5.1 Material tiles

`has_import` is true when the toggle is on and a `good_import` row exists. `scan` is the scanned count, or 0 when the material is missing from an existing import.

| Live state | `has_import = false` (today) | `has_import = true` |
|---|---|---|
| `short` | `have/need`, red −N to farm | unchanged |
| `met` | "✓ need" | `scan/need ✓` if `scan ≥ need`, else "✓ need" |
| `unneeded` | dimmed, no number | `scan` shown and **not dimmed** if `scan > 0`; dimmed "0" otherwise |

- Materials in the catalogue's eight categories only. Scanned materials outside those categories, such as food or gadgets, are counted as ignored and not shown. A holder key we cannot match shows as **Equipped** (never Unequipped).
- `to_farm`, `craftable`, Farm today, Weekly bosses and Building cards all keep using live calculator data only.
- The popover adds "Scanned: N (as of <date>)" when `has_import`.
- The filter chips add **Owned** (`scan > 0`) when `has_import`.

### 5.2 Weapons tab

All scanned weapons that matched. Each tile shows the icon on a rarity background, the name, "Lv <level> · R<refinement>", and the holder's avatar or an **Unequipped** badge. Filters: weapon type, rarity, *Unequipped only*, and name search. Sorted by rarity (high first), then name, then level (high first). A note says holders are as of the scan.

### 5.3 Artifacts tab

All scanned artifacts that matched. Each card shows the set name and icon, slot, rarity stars, +level, main stat, the substats with values, and the holder's avatar or **Unequipped**. Filters: set, slot, main stat, *Unequipped only*, and minimum rarity (default 4★). Header: "<N> artifacts · <M> unequipped". Sorted by rarity, then set, then slot, then level. The list is paged by 100 on the client.

Stat keys (GOOD's, e.g. `critRate_`, `atk_`, `hp`) map to display names in one frontend table: `critRate_` → "CRIT Rate%", `atk_` → "ATK%", `atk` → "ATK", and so on. Values with `_` show as percentages.

### 5.4 Planned-weapon picker

When `has_import`, weapons of the character's type that you own get an "owned · Lv <best level> · R<best refinement>" mark and are listed first. `GET /api/weapons` adds `owned: {count, best_level, best_refinement} | null`.

### 5.5 Inventory header

Existing: "Calculated <age> ago" and the Updating/warning states. When `has_import`, it adds "Scan: <date> (<age>) from <source>", plus a soft "scan is N days old" note when it is older than 30 days. **Import GOOD file** button shown only when the toggle is on. Tabs: Materials · Weapons · Artifacts, where Weapons and Artifacts appear only when `has_import`. The selected tab is kept in `localStorage` (try/catch).

### 5.6 Settings

A new section, **Inventory import (GOOD)**, with:

- the toggle, with the risk note: "The import only reads a file. The scanner that creates it is third-party software, which HoYoverse's terms forbid; use at your own risk.",
- "Last import: <date> from <source>: <summary>" or "No import yet",
- **Import GOOD file** (shown when the toggle is on),
- **Delete imported data**, with a confirm dialog, enabled when an import exists.

### 5.7 Import summary

The upload response shows a toast like "Imported 412 materials, 318 weapons, 1 804 artifacts. 3 keys not recognised." Unrecognised keys are listed in Settings (up to 200). If more than 10 material or weapon keys are unmatched, the toast suggests "Refresh game data".

---

## 6. API

| Method & path | Purpose |
|---|---|
| `POST /api/good/import` | Multipart `file`. Returns `ImportSummary` (`imported_at`, `source`, `counts`, `unmatched`). 409 when the toggle is off or the material catalogue is empty; 400 on a format error; 413 over 20 MB. |
| `DELETE /api/good` | Deletes the snapshot; 204. Allowed even when the toggle is off. |
| `GET /api/good/status` | `{enabled, imported_at, source, counts, unmatched}` |
| `GET /api/good/weapons` | Scanned weapons with names, icons, rarity, type and holder; 404 when there is no `has_import`. |
| `GET /api/good/artifacts` | Scanned artifacts with set names and icons and holder; 404 when there is no `has_import`. |
| `GET /api/inventory` | Each material adds `scan: int | null` (null when there is no `has_import`). The top level adds `good: {imported_at, source} | null`. |
| `GET /api/weapons` | Adds `owned` per weapon (§5.4). |
| `GET/PUT /api/settings` | Includes `good_import_enabled`. |

When the toggle is off, every GOOD field is null or absent, as if no import existed.

---

## 7. Errors

| Situation | Behaviour |
|---|---|
| Not valid JSON / not an object | 400 "Not a GOOD file (could not read JSON)" |
| `format` ≠ "GOOD" | 400 "Not a GOOD file" |
| `version` not 1–3 | 400 "Unsupported GOOD version <v>" |
| Block of the wrong type, or an entry missing required fields | 400 naming the block. A whole-file error leaves existing data untouched. |
| Over 20 MB | 413 |
| Toggle off | 409 on import; no GOOD fields in responses; UI hides the button and tabs |
| Material catalogue empty | 409 "Refresh game data first" |
| Unmatched keys | Import succeeds; keys listed in the summary |
| Scan older than 30 days | Soft note in the Inventory header |

---

## 8. Privacy

- GOOD files contain no UID or cookies. Even so, contents are never logged and the file is never written to disk.
- Test fixtures are small hand-made GOOD files with invented counts.
- The existing secret-leakage test is extended to the new endpoints.
- No game art is committed. Icons come through the existing image proxy at runtime.

---

## 9. Testing

### Backend (pytest)

- `parse`: valid v1/v2/v3; every error case in §7; a materials-only file; unknown fields ignored.
- `good_key`: punctuation, apostrophes, hyphens, digits, accented letters (normalised to ASCII), and the Traveler keys.
- `KeyIndex`: matches for materials, weapons, sets and characters; collisions; unmatched keys.
- `replace_snapshot`: replaces the previous rows; a failure leaves the earlier snapshot intact; summary counts.
- `tile_view` merge rules: each state × with or without import × scan above or below need.
- API: import, status, delete, weapons, artifacts, toggle off returns 409 or null fields, an empty catalogue returns 409, the size limit, inventory `scan` fields, and `/api/weapons` `owned`.
- Yatta `/reliquary` parsing from a trimmed public fixture.

### Frontend

- `svelte-check` with no errors.
- Vitest: tile text in each state with and without a scan; weapon filters; artifact filters and stat-name mapping.
- Playwright (seeded data plus a fixture GOOD file): enable the toggle in Settings → import on Inventory → an unneeded tile shows its exact count → the Weapons tab shows an Unequipped weapon → the Artifacts slot filter narrows the list → turn the toggle off → the tabs and button disappear.

### Live check (first build step)

If the user has a real GOOD export, import it through the API in the worktree and report only the match summary (counts and unmatched keys), never its contents. The file stays outside the repo.

---

## 10. Done when

1. With the toggle on and a GOOD file imported, every material tile in the eight categories shows an exact count under the §5.1 rules, and Weapons and Artifacts list the scanned items.
2. With the toggle off, or with no import, the app behaves exactly as before Phase 6.
3. To-farm numbers are identical with and without an import.
4. Delete removes all imported data.
5. All suites pass; the repository contains no cookie values, UID, real GOOD export, or game art.
