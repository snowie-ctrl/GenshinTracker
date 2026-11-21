# Phase 3 — Wishes: Design

**Date:** 2026-11-20
**Status:** Approved 2026-11-20; corrected during planning (see §16)
**Parent:** [Overview design](2026-11-19-genshintracker-overview-design.md). Builds on [Phase 1 — Foundation](2026-11-19-phase1-foundation-design.md) and [Phase 2 — Planner](2026-11-19-phase2-planner-design.md); stays within the overview's architecture, data model, and rules (§4.3, §6, §7).

---

## 1. Goal

The user's complete wish history lives in the app, imported with **one button** from the game plus a one-time import of older history from paimon.moe, and the Wishes page shows **pity, 50/50 / guarantee state, and fate points** for every banner type, with history, stats, and charts. Wish history is irreplaceable, so every import is backed up first and can never duplicate or half-apply.

### Agreed decisions

| Topic | Decision |
|---|---|
| Older history | The user has history in **paimon.moe**; importing it is a day-one need. |
| File formats | **paimon.moe .xlsx** (native) **and UIGF JSON** (v3 and v4 import, v4 export). |
| Luck state | Exact pity everywhere; exact Character guarantee state; **Capturing Radiance as a labelled estimate**; **fate points derived from a charted item the user picks** (Weapon, Chronicled). |
| History and stats | Pity panels, per-pool 5★/4★ lists, headline stats, **charts** (pulls per month, 5★ pity histogram, banner timeline), full filterable history table, per-banner attribution. |
| Import trigger | **Button only.** No automatic import on page load or as part of the normal sync. |
| Backups | **Separate wish backups:** database copy before each import (keep 10) and a UIGF JSON snapshot after each successful import (keep 10). |
| Banner data | **Fetched at runtime** from paimon.moe's open-source `banners.js` (MIT) with the other game data; cached in the database; no snapshot committed. |

### In scope

- `backend/app/wishes/`: authkey discovery, gacha-log fetch, UIGF and paimon.moe import, UIGF export, merge/de-duplication, banner data and attribution, pity logic, stats.
- Pages: **Wishes** (new), a **Pity** card on the Dashboard, a **Game install path** field in Settings.

### Out of scope

- Miliastra Wonderland wishes.
- 4★ rate-up win tracking.
- Beginner/Standard pity crossover.
- Other trackers' native formats (anything other than UIGF JSON and paimon.moe .xlsx).
- Automatic or scheduled wish import.
- Multiple accounts.

---

## 2. Architecture

`backend/app/wishes/` is the second module allowed to call an unofficial API (overview §3). Within it, **only `fetch.py`** performs network calls to the gacha log API, and only `authkey.py` reads game files; everything else is pure code over database rows.

| File | Responsibility |
|---|---|
| `authkey.py` | Locate `data_2` in the game's web cache: from the `game_install_path` setting if set, otherwise from the game's `output_log.txt`/`Player.log` under `%USERPROFILE%/AppData/LocalLow/miHoYo/Genshin Impact/`. Extract the **last** wish-history URL (one containing `authkey=`). Read-only. Returns an in-memory value object (authkey, UID from the URL's query if present, region/host); never writes it anywhere. genshin.py's `get_authkey()` is **not** used, because it writes the authkey to a temp file. Its path-expansion logic may be reused. |
| `fetch.py` | Page the gacha log API (genshin.py `wish_history(authkey=...)` or the equivalent `_get_wish_page` call) per gacha type 100, 200, 301, 400, 302, 500 with `lang=en-us`, newest first, 20 per page; stop a gacha type at the first record whose id is already stored. Converts results to our own dataclasses at the boundary. Rate-limit responses use the phase 1 back-off (3 retries, increasing delay). |
| `uigf.py` | Parse UIGF v3 and v4 JSON; build UIGF v4 JSON. |
| `paimon_xlsx.py` | Parse paimon.moe's "Export to Excel" workbook (`openpyxl`, new backend dependency). |
| `merge.py` | One merge path for all sources (§5). |
| `banners.py` | Convert paimon.moe `banners.js` to JSON, map slugs to game ids, attribute pulls to banners (§6). |
| `pity.py` | Pity, outcomes, next-5★ state, fate points, Radiance estimate (§7). |
| `stats.py` | Headline stats and chart series (§8). |
| `importer.py` | `WishImporter`: single-flight import runner: backup → read → merge (one transaction) → UIGF snapshot → `wish_import` row. Independent of `SyncManager`, which stays HoYoLAB-only. |

`gamedata/service.py` gains the banner fetch on its existing triggers (first run, data older than 7 days, unknown id seen, "Refresh game data"). Failure keeps cached banners and records the error in `game_meta`, shown in Settings.

---

## 3. Data model (one Alembic migration)

### User data (permanent; never written by sync)

**`wish`**: one row per pull.

| Column | Notes |
|---|---|
| `pk` | integer PK |
| `id` | real pull id (string of digits), **nullable, unique**. Null for rows imported without an id (paimon.moe). |
| `pool` | `beginner` / `standard` / `character` / `weapon` / `chronicled` (pity pools; gacha types 301 and 400 both map to `character`) |
| `gacha_type` | `100`/`200`/`301`/`400`/`302`/`500`; null when the source does not distinguish 301 from 400 (paimon.moe) |
| `time` | server-local time exactly as the game shows it (`YYYY-MM-DD HH:MM:SS`, naive) |
| `seq` | integer ordering pulls within one pool that share a `time` (file order for id-less rows; id order otherwise) |
| `name` | item name (English) |
| `item_id` | game id resolved from the catalogue; null if unknown |
| `item_type` | `character` / `weapon` |
| `rarity` | 3 / 4 / 5 |
| `source` | `game` / `uigf` / `paimon`: where the row's current identity came from |
| `imported_at` | UTC |

Index on `(pool, time, seq)`.

**`wish_import`**: one row per import attempt: `id`, `started_at`, `finished_at`, `source` (`game`/`uigf`/`paimon`), `ok`, `added`, `upgraded`, `skipped`, `error` (message, ≤300 chars, never containing the URL or authkey), `backup_file`, `snapshot_file`.

**`wish_chart`**: `pool` PK (`weapon`/`chronicled`), `item_id`, `set_at` (UTC). Deleted when cleared.

**`setting`** gains `game_install_path` (string, default empty = auto-detect).

### Game data

**`game_banner`**: `key` PK (stable: pool + start + order), `pool`, `name`, `short_name`, `start`, `end` (stored as given), `timezone_dependent` (bool, start), `timezone_dependent_end` (bool, end), `order` (0/1 for the two parallel character banners; 0 otherwise), `featured_5` (JSON list of item ids), `featured_4` (JSON list), `version`.

The UID is never stored in `wish`. The account UID is `GENSHIN_UID` from `.env`.

---

## 4. Import flows

All imports go through `WishImporter`: one at a time; a second request returns the running import's id. Each import:

1. Copies the database to `data/backups/wishes/tracker-<timestamp>.db` (SQLite backup API; keep the **10** newest). This rotation is separate from the sync backups in `data/backups/`.
2. Reads and validates the whole input before touching the database.
3. Merges in **one transaction** (§5). Any error rolls back everything.
4. On success writes `data/backups/wishes/uigf-<timestamp>.json` (full UIGF v4 export; keep the 10 newest).
5. Records a `wish_import` row (also on failure).

### 4.1 Import from game (button)

1. Find `data_2`. Not found → "Couldn't find the game's web cache. Set the game install path in Settings." File locked → "Close Genshin Impact and try again."
2. Take the last wish-history URL. None → "Open Wish History in-game once, then press Import again."
3. The wish URL carries no UID, so after fetching (step 4) the records' `uid` field is compared with `GENSHIN_UID`; a mismatch → "This wish history belongs to a different account." Nothing changes.
4. Back up, then fetch each gacha type incrementally (§2 `fetch.py`).
5. Authkey rejected (gacha API retcode `-101` "authkey timeout" or `-100` "authkey error", or the genshin.py equivalent) → "Your wish link has expired. Open Wish History in-game once, then press Import again." Nothing changes.
6. Merge, snapshot, record.

### 4.2 Upload file

`.json` → UIGF; `.xlsx` → paimon.moe. Max 20 MB.

- **UIGF v4:** use the `hk4e` entry whose `uid` equals `GENSHIN_UID`; none → error listing that no entry matches. Times are in the entry's `timezone`; converted to server-local time if it differs from the region offset.
- **UIGF v3:** `info.uid` must equal `GENSHIN_UID`; times use `info.region_time_zone` the same way.
- **paimon.moe .xlsx:** one sheet per banner type (Character Event, Weapon Event, Standard, Beginners' Wish, Chronicled Wish; exact sheet and column names are confirmed against the user's file in the first build step and kept in one mapping). Each data row gives type, name, time, rarity. Rows keep their sheet order for `seq`. `gacha_type` is null except for single-type sheets (standard 200, weapon 302, beginner 100, chronicled 500).
- Any unparseable row (unknown sheet, bad time, unknown rarity) → nothing is imported; the result lists the row errors (`sheet "Weapon Event" row 412: bad time`), at most 50 shown.

---

## 5. Merge rules (`merge.py`)

**Match key:** `(pool, time, name)`, compared **as multisets per timestamp**. A 10-pull is one timestamp; if it holds two "Favonius Sword" and the database already has one matching row, one more is added.

For each incoming row, in source order:

1. **Incoming row with a real id**
   - id already stored → skip.
   - Otherwise, if an existing row with the same key is **id-less**, or has an id from a file (`source` `uigf`/`paimon`) while the incoming row comes from the **game** → **upgrade** that row: set `id`, `gacha_type`, `item_id`, `source`. (Game ids are authoritative; this also absorbs fake ids other trackers invented for imported paimon data.)
   - Otherwise, if the incoming row comes from a **file** and an unclaimed stored row with the same key already holds an id → skip it (same pull; protects against trackers that invent ids).
   - Otherwise insert.
2. **Incoming row without a real id** (paimon.moe, or a UIGF row whose id is one of our generated ids, see §9): insert only the surplus over existing rows with the same key.

Ordering: rows with real ids get `seq` by id order within their timestamp; id-less rows keep file order. Pity and lists order by `(time, seq)` within a pool.

Item names resolve to `item_id` through `game_character` and `game_weapon` (3★ weapons included). Unknown names are stored with `item_id = null` and trigger a game-data refresh after the import.

Result counts: `added`, `upgraded`, `skipped`.

---

## 6. Banner data (`banners.py`)

- **Source:** `https://raw.githubusercontent.com/MadeBaruna/paimon-moe/main/src/data/banners.js`, an `export const banners = {...}` object literal with keys `beginners`, `standard`, `characters`, `weapons`, `chronicled`. Each banner has `name`, `shortName`, `start`, `end`, optional `timezoneDependent` / `timezoneDependentEnd`, `featured` (5★ slugs), `featuredRare` (4★ slugs), `version`.
- **Conversion:** a strict, small converter for this literal (quote bare keys, single-quoted strings to JSON strings, drop trailing commas and the `export const` wrapper) followed by `json.loads`. Anything it does not understand raises, and cached banners stay.
- **Slug → id:** normalise Yatta names (lowercase, non-alphanumerics to `_`, collapse repeats) and match; a short override table handles exceptions. Unmapped slugs are recorded in `game_meta` and shown in Settings; the banner still loads.
- **Parallel character banners:** banners in `characters` sharing the same start get `order` 0 and 1 in file order.
- **Time windows** (as paimon.moe's own `src/functions/wish.js` reads them): a start marked `timezoneDependent` (an end marked `timezoneDependentEnd`) is a UTC+8 instant and is converted to server-local time with the `GENSHIN_REGION` offset (America UTC−5, Europe UTC+1, Asia/TW-HK-MO UTC+8); unmarked times are already server-local clock times.
- **Attribution:** a pull belongs to the banner of its pool whose window contains its time; for `character`, gacha type 301 → `order` 0, 400 → `order` 1. When `gacha_type` is null (paimon rows), the banner whose `featured_5` contains the pulled 5★ is chosen, otherwise `order` 0. No match → **unattributed**.

---

## 7. Pity and luck state (`pity.py`)

Pure functions over `wish` rows and `game_banner`, ordered by `(time, seq)` within a pool. Pity and guarantees **carry over between banners of the same pool**.

| Pool | 5★ hard pity | Soft pity from | 4★ pity |
|---|---|---|---|
| Character | 90 | 74 | 10 |
| Weapon | 80 | 63 | 10 |
| Standard | 90 | 74 | 10 |
| Chronicled | 90 | 74 | 10 |
| Beginner | 50 | none | 10 |

- **Pity:** pulls since the last 5★; pulls since the last 4★-or-better; "N to hard pity"; `soft` flag.
- **Pity at each 5★/4★:** the count at which it arrived (shown in lists).

### 7.1 Character outcomes

For each 5★:
- not the attributed banner's featured 5★ → **Lost**
- featured, previous 5★ in the pool was Lost → **Guaranteed**
- featured otherwise → **Won**
- unattributed → **Unknown**; the following 5★ is also **Unknown** if it is featured (win vs. guarantee can't be told)

**Next-5★ state:** `50/50`, `guaranteed`, or `unknown`.

### 7.2 Weapon outcomes and fate points

- Outcome: featured (either featured 5★) vs. standard, same Won/Lost/Guaranteed/Unknown logic (75/25 rule).
- **Fate points (since 5.0, max 1):** only when a `wish_chart` row exists for `weapon` and its `set_at` falls inside the **current** weapon banner's window (otherwise the chart counts as unset). Walk the weapon pool's 5★s after `max(set_at, banner start)`: non-charted 5★ → point = 1; charted 5★ → point = 0 and the chart is cleared (row deleted).
- Display: "Fate point 1/1 → next 5★ is <charted weapon>", or "Pick your charted weapon to track fate points".
- Chart choices: the current weapon banner's `featured_5`.

### 7.3 Chronicled

Pity as above. The same chart and fate-point mechanism, with chart choices from the current Chronicled banner's `featured_5`. Outcome badges: Charted / Not charted when a chart was active at the time, else none.

### 7.4 Capturing Radiance (estimate)

- Counts **consecutive Lost 50/50s** on the Character pool among 5★s on or after **2024-08-28** (version 5.0). A **Won** resets the count to 0; a **Guaranteed** leaves it unchanged; **Unknown** makes the count unknown until the next Won.
- Shown as "Lost 50/50s in a row: N", labelled **estimate**, with a one-line explainer and a link to the community analysis.
- The "Radiance likely on your next 50/50" line uses one constant (`RADIANCE_LIKELY_AT`). **The first build step confirms the current community model and sets this constant**; if no reliable model is found, only the count is shown.
- Radiance wins cannot be distinguished from normal wins in the history; both show as **Won**.

### 7.5 Standard and Beginner

Pity only.

---

## 8. Stats (`stats.py`)

Per pool and overall:

- Total pulls; Primogems equivalent (`pulls × 160`).
- 5★ and 4★ counts; average 5★ pity.
- 50/50 win rate = Won / (Won + Lost), excluding Guaranteed and Unknown (Character and Weapon only).
- Chart series:
  - **Pulls per month:** stacked by pool, server-local months.
  - **5★ pity histogram:** buckets of 10.
  - **Banner timeline:** per attributed banner, pull count and 5★s obtained, in time order.

---

## 9. UIGF export

- `GET /api/wishes/export` returns UIGF v4 JSON for `GENSHIN_UID`: `info` (`export_timestamp`, `export_app: "GenshinTracker"`, `export_app_version`, `version: "v4.0"`), one `hk4e` entry (`uid`, `timezone` from the region offset, `lang: "en-us"`, `list`). Each record includes `uigf_gacha_type` (301 for 301/400), `gacha_type`, `item_id`, `count: "1"`, `time`, `name`, `item_type` (`Character`/`Weapon`), `rank_type`, `id`.
- **Id-less rows get generated ids:** `<UTC unix seconds of the pull, 10 digits>9<seq, 8 digits zero-padded>`. Real ids observed in the community start with the pull's unix seconds followed by `0`, so the `9` marker should not collide; the first build step confirms this against the user's real ids (§14), and the marker digit is one constant if it must change. On import, a UIGF id whose 11th digit is `9` and whose first 10 digits equal the row's own time is treated as **id-less** (§5 rule 2), so re-importing our own export adds nothing and later game imports still upgrade those rows.
- Rows with `gacha_type` null export as `301` (character pool) or the pool's single type.
- Rows with `item_id` null export with `item_id: ""` (UIGF v4 requires the field; consumers fall back to the name).
- The browser receives the JSON from the backend and saves it as `genshintracker-uigf-<date>.json`. The UID is the user's own and stays on their disk.

---

## 10. Pages

### 10.1 Nav

**Wishes** becomes enabled.

### 10.2 Wishes (`/wishes`)

- **Header:** **Import from game** (primary), **Upload file** (.json/.xlsx), **Export UIGF**. The last import shows its time and result ("+37 new · 2 upgraded" or the error). While an import runs: spinner, buttons disabled, polling `GET /api/wishes/import/status` every 2 s.
- **Pity panels** (one per pool with pulls, in order Character, Weapon, Chronicled, Standard, Beginner):
  - 5★ and 4★ pity bars marking soft and hard pity.
  - Next-5★ state.
  - Character: the Radiance estimate.
  - Weapon/Chronicled: the fate point and a chart picker (dropdown of current featured 5★s plus "None"; optimistic save, reverted with an error toast on failure).
- **Pool tabs:** each with headline stats; a 5★ list (icon, name, pity it arrived at, outcome badge, banner short name, date) and a 4★ list (name, pity, date).
- **Charts:** hand-rolled SVG components (no new frontend dependency): pulls per month, 5★ pity histogram, banner timeline. They follow the app's dark theme and CSS variables; each has a text summary for screen readers.
- **History table:** time, item (icon + name), rarity, pool, banner, pity at pull. Filters: pool, rarity, item type, banner; name search; 50 per page. Filter choice stored in `localStorage` (try/catch; defaults when unavailable).
- **Empty state:** the three ways in (game import with the in-game steps, paimon.moe .xlsx, UIGF JSON).
- **Banner data missing or failed:** a notice that outcomes show as Unknown until game data refreshes.

### 10.3 Dashboard

A **Pity** card: one line per pool with pulls, e.g. "Character 42/90 · Guaranteed", "Weapon 12/80 · Fate 1/1". It links to Wishes. Without wishes: "Import your wish history" → Wishes.

### 10.4 Settings

A **Game install path** field (blank = auto-detect) and a status line: "Wish link found (cached 3 h ago)" / "No wish link in the cache" / "Game cache not found". **The URL and authkey are never shown.** Banner-data fetch status and unmapped slugs appear with the other game-data status.

---

## 11. API

| Method & path | Purpose |
|---|---|
| `POST /api/wishes/import/game` | Start a game import (single flight; returns the running import's id if one is active) |
| `POST /api/wishes/import/file` | Multipart upload of `.json` / `.xlsx` (≤20 MB); runs the import |
| `GET /api/wishes/import/status` | Current/last import: state, counts, error |
| `GET /api/wishes/summary` | Per pool: pity, next-5★ state, fate point and chart, Radiance estimate, headline stats, 5★/4★ lists; chart series |
| `GET /api/wishes?pool&rarity&type&banner&q&page` | History page (50 rows) with total count |
| `PUT /api/wishes/chart/{pool}` | `{item_id}` or `{item_id: null}` to clear |
| `GET /api/wishes/export` | UIGF v4 JSON |
| `GET /api/wishes/cache-status` | Settings status line (found / age / not found); no URL |
| `GET /api/dashboard` | Adds `pity` |
| `GET /api/settings`, `PUT /api/settings` | Include `game_install_path` |

---

## 12. Errors

| Situation | Behaviour |
|---|---|
| Game cache not found | "Couldn't find the game's web cache. Set the game install path in Settings." |
| `data_2` locked | "Close Genshin Impact and try again." |
| No wish URL in the cache | "Open Wish History in-game once, then press Import again." |
| Authkey expired/invalid | "Your wish link has expired. Open Wish History in-game once, then press Import again." Nothing changed. |
| UID mismatch (URL or file) | "This wish history belongs to a different account." Nothing changed. |
| Network or API failure mid-import | Transaction rolled back; backup kept; error shown and recorded |
| Bad file | Row errors listed (first 50); nothing imported |
| Banner data never fetched / fetch failed | Pity works; outcomes Unknown; error in Settings |
| Unknown item name | Stored with `item_id = null`; game-data refresh after the import |

---

## 13. Security and data safety

- The authkey and the wish-history URL are never logged, stored (database, files, backups), returned by the API, or exported. Error messages are fixed strings or exception class names with the URL stripped.
- Wish backups and UIGF snapshots live in `data/backups/wishes/` (git-ignored).
- The secret-leakage test is extended: with a fake `data_2` containing a known fake authkey, no API response body and no captured log record during an import contains it, and neither does the `wish_import` table.
- Test fixtures use made-up UIDs and synthetic pulls; the .xlsx fixture is generated by the test helper, not copied from the user's export.

---

## 14. Testing

### Backend (pytest)

- `authkey.py`: URL extraction from a synthetic `data_2` (last URL wins, none present); path resolution from setting and from a fake log file; locked-file message.
- `fetch.py` against a fake gacha API: paging, stop at known id, all six gacha types, expired authkey, rate-limit back-off.
- UID mismatch for game URL, UIGF v3, UIGF v4.
- UIGF v3 and v4 parsing (incl. timezone conversion); v4 export → import round trip adds 0.
- paimon.moe .xlsx parsing from a generated workbook; bad-row reporting; all-or-nothing.
- Merge: duplicate 10-pulls (multiset counting), upgrade of id-less rows, game ids replacing file ids, generated-id recognition, `seq` ordering.
- `banners.js` conversion on a trimmed fixture, converter rejection of unexpected syntax, slug mapping and overrides, parallel banner `order`, time-zone conversion for all three regions.
- Attribution (301/400, null `gacha_type`, unattributed).
- Pity: carry-over across banners, soft/hard flags, Lost→Guaranteed, Unknown propagation, weapon 75/25, fate points with chart set/cleared/expired banner, Chronicled chart, Radiance counter incl. pre-5.0 pulls ignored.
- Stats: win rate exclusions, monthly buckets, histogram.
- Backup rotation (10 database copies + 10 snapshots), separate from sync backups.
- Importer single flight.
- API tests for every endpoint in §11 against a temporary SQLite database.

### Frontend

- `svelte-check` with no errors.
- Vitest: outcome badge text, pity bar marks, chart scaling helpers, history filter state.
- Playwright (seeded wishes): Wishes page shows pity panels → switch to the Weapon tab → set a chart → fate line appears; history filter by 5★ shows only 5★ rows.

### Smoke

`python -m app.smoke --wishes`: live, read-only. Finds the wish link, fetches all gacha types without writing, prints per-pool pull counts and pity. Never prints the URL or authkey.

### First build step: live checks

Against the user's real cache and paimon.moe export (results written to `docs/superpowers/notes/` without UID, URL or authkey):

1. The wish link is found and the fetch returns all pools.
2. The paimon.moe workbook's sheet and column names match the parser mapping.
3. Overlap check: paimon rows inside the game's 6-month window all match game rows by key (expect 0 surplus).
4. The current community model for Capturing Radiance → `RADIANCE_LIKELY_AT`.
5. Real pull ids: confirm none has `9` as its 11th digit (the generated-id marker, §9).

---

## 15. Done when

1. One click on **Import from game** imports the in-game wish history with no manual steps beyond opening Wish History in-game.
2. The user's paimon.moe .xlsx merges in with no duplicates in the overlapping period.
3. Pity for every pool matches a manual count from the in-game history.
4. Exporting UIGF and importing it again adds 0 pulls.
5. All tests pass; the repository contains no UID, authkey, wish URL, nickname, or personal wish data.

---

## 16. Corrections made during planning (2026-11-20)

1. **Banner time zones (§6) were reversed.** paimon.moe's own code treats `timezoneDependent` (start) and `timezoneDependentEnd` (end) times as UTC+8 instants to convert; unmarked times are server-local. `game_banner` gains `timezone_dependent_end`.
2. **UID check for game imports (§4.1)** uses the fetched records' `uid` field, because the wish URL carries no UID.
3. **Merge (§5)** skips an incoming file row whose key matches a stored row that already holds an id, instead of inserting a duplicate.
4. All imports require `GENSHIN_UID` (HoYoLAB connected); without it they fail with "Connect HoYoLAB in Settings first, so imports can be checked against your UID."

## 17. Additions from the live check (2026-11-21)

1. **paimon.moe data backup (`paimon-moe-local-data.json`) is also accepted** by Upload file. Each `wish-counter-*` key maps to a pool; a pull's `code` is its gacha type (301/400 kept apart); items are slugs, matched to game data with the banner slug normalisation for name, type and rarity. An unknown slug fails the whole import with "Refresh game data in Settings". A `wish-uid` that differs from `GENSHIN_UID` is refused. Rows carry no ids, so they merge like the `.xlsx` rows.
2. **The web cache is read with read/write/delete sharing on Windows**, because the running game holds `data_2` with delete access and a plain open fails.
