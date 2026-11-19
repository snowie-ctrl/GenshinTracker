# Phase 1 — Foundation: Design

**Date:** 2026-11-19
**Status:** Draft for review
**Parent:** [Overview design](2026-11-19-genshintracker-overview-design.md) — this spec must stay within its architecture, data model, and rules.

---

## 1. Goal

Opening the app shows the user's full roster, grouped by status, with **no manual entry**, plus live resin/commission data. Goals and build targets can be set per character.

### In scope

- One-command run (`python run.py`) serving the built frontend on `127.0.0.1`.
- Game data and art cache (characters only).
- HoYoLAB connect flow in Settings; background sync of roster, details, and live notes.
- Pages: **Characters** (grid + detail page), **Settings**, basic **Dashboard**.
- Top navigation with later pages shown disabled.

### Out of scope (later phases)

Material shortfalls and calculator sync, Inventory, GOOD import (phase 2); wishes (3); teams (4); events, calendar, profile, map (5); weapon and material game data (phase 2).

---

## 2. Technology

| Layer | Choice |
|---|---|
| Backend | Python 3.12, FastAPI, uvicorn |
| HoYoLAB | `genshin` (genshin.py) pinned to `1.0.0` (the version verified by the probe) |
| HTTP | `httpx` (game data and images) |
| Database | SQLite via SQLAlchemy 2.x; schema managed by **Alembic** migrations, applied automatically at startup |
| Config | `.env` (cookie, UID, region) via `python-dotenv`; other settings in the database |
| Frontend | SvelteKit + TypeScript, `adapter-static`, SSR disabled; plain CSS with CSS variables; dark theme |
| Tests | pytest, FastAPI TestClient, svelte-check, Vitest, Playwright |

---

## 3. Repository layout (phase 1)

```
run.py                          build check + start uvicorn on 127.0.0.1:<port>
.env.example                    empty cookie/UID fields with comments
README.md                       setup, run, connect steps, fan-project disclaimer
backend/
  pyproject.toml
  alembic.ini, migrations/
  app/
    main.py                     app factory; routers; static frontend; startup migrations
    config.py                   paths (data/, .env), port, defaults
    db/                         engine, session, models
    gamedata/                   Yatta client, roster filtering, image cache
    sync/                       HoYoLAB client wrapper, sync runner, parts
    settings/                   .env read/write, settings table, connection status
    api/                        characters.py, settings.py, dashboard.py, sync.py, img.py
    smoke.py                    `python -m app.smoke`: one live sync, printed summary
  tests/
    fixtures/                   anonymized recorded responses
frontend/
  src/lib/                      api client, stores, components (CharacterCard, GoalSwitch, ...)
  src/routes/                   +layout (nav), / (dashboard), characters/, characters/[slug]/, settings/
```

Port: `8765` by default, configurable in `.env` (`PORT`).

---

## 4. Data model (phase 1 tables)

All tables are created by the first Alembic migration.

| Table | Columns (key ones) | Category |
|---|---|---|
| `game_character` | `id` PK, `name`, `slug`, `rarity`, `element`, `weapon_type`, `region`, `icon`, `splash`, `release_at` | Game |
| `game_meta` | `key` PK, `value` (e.g. `characters_fetched_at`, last error) | Game |
| `owned_character` | `character_id` PK, `level`, `ascension`, `constellation`, `friendship`, `talent_normal`, `talent_skill`, `talent_burst`, `weapon_name`, `weapon_icon`, `weapon_rarity`, `weapon_level`, `weapon_refinement`, `stats` (JSON), `synced_at` | Account |
| `owned_artifact` | `character_id`, `slot` (PK pair), `set_name`, `rarity`, `level`, `main_stat`, `substats` (JSON), `icon` | Account |
| `live_notes` | single row: `resin`, `resin_max`, `resin_full_at`, `commissions_done`, `commissions_max`, `expeditions` (JSON), `realm_currency`, `realm_currency_max`, `fetched_at` | Account |
| `sync_run` | `id`, `started_at`, `finished_at`, `trigger` (`auto`/`manual`/`connect`), `parts` (JSON: per part `ok`, `error`, `count`) | Account |
| `character_goal` | `character_id` PK, `goal` (`none`/`want`/`build`), `target_level`, `target_normal`, `target_skill`, `target_burst`, `target_weapon_level`, `updated_at` | User |
| `setting` | `key` PK, `value` (JSON) | User |

Rules:

- A character with no `character_goal` row has goal `none`.
- Sync replaces `owned_character`, `owned_artifact`, and `live_notes` contents; it never writes `character_goal` or `setting`.
- A character absent from the latest successful roster sync is removed from `owned_character` (ownership is whatever HoYoLAB last reported).

### Settings keys and defaults

| Key | Default |
|---|---|
| `sync_interval_minutes` | 10 |
| `default_targets` | level 90, talents 8/8/8, weapon 90 |

---

## 5. Game data

- **Source:** `https://gi.yatta.moe/api/v2/en/avatar` (list: id, rarity, name, element, weaponType, region, icon, release). Art from `https://enka.network/ui/<icon>.png` (icon, e.g. `UI_AvatarIcon_Shougun`) and `UI_Gacha_AvatarImg_<icon suffix>.png` (splash, e.g. `UI_Gacha_AvatarImg_Shougun` — the internal name, not the display name), with Yatta's `/assets/UI/` as fallback. Both confirmed reachable on 2026-11-19.
- **Roster filtering:**
  - All Traveler entries collapse into one `game_character` named "Traveler"; on sync it takes whichever Traveler id/element HoYoLAB reports. Same for Manekin/Manekina ("Manekin").
  - Entries with `release_at` in the future are hidden.
- **Refresh triggers:** first run; data older than 7 days at startup; a sync returning an unknown character id; "Refresh game data" in Settings.
- **Image cache:** `/api/img/<name>` serves from `data/cache/img/`, downloading on first request. On download failure it returns a placeholder image and retries on a later request.
- **Failure:** keep cached data; store the error in `game_meta`; Settings displays it.

---

## 6. HoYoLAB connect and sync

### 6.1 Connect

1. `POST /api/settings/hoyolab` with cookie fields (`ltuid_v2`, `ltoken_v2`, `ltmid_v2`, optional `account_id_v2`, `account_mid_v2`, `cookie_token_v2`).
2. Backend builds a client with these values in memory and calls `get_game_accounts()`.
3. Failure → `400` with HoYoLAB's message; nothing written.
4. Exactly one Genshin account → save cookie values, `GENSHIN_UID`, and `GENSHIN_REGION` to `.env`. Several → respond with the list (UID, server, nickname, AR); the frontend asks the user to choose, then posts again with the chosen UID.
5. A sync with trigger `connect` starts immediately.

`.env` writes preserve unrelated lines. The API only ever returns `{status: connected | expired | missing, uid}` — never cookie values.

### 6.2 Triggers and limits

- **Auto:** the frontend calls `POST /api/sync?trigger=auto` on each page load; the backend starts a sync only if the last successful sync is older than `sync_interval_minutes`.
- **Manual:** nav **Sync** button → `trigger=manual`; refused with `429` if a sync started less than 60 s ago.
- **Single flight:** if a sync is running, the request returns the running sync's id instead of starting another.
- **Status:** `GET /api/sync/status` → current/last run with per-part results. The frontend polls every 2 s while a run is active, then refetches page data.

### 6.3 Parts (in order, each independent)

1. **Roster** — `get_genshin_characters(uid)` → upsert `owned_character` base fields; delete characters no longer present.
2. **Details** — `get_genshin_detailed_characters(uid, characters=[...])` in batches → talents, artifacts, stats.
3. **Live notes** — `get_genshin_notes(uid)` → `live_notes`.

Before part 1, the database file is copied to `data/backups/tracker-<timestamp>.db`; only the 5 newest are kept.

Each part catches its own exceptions and records `{ok: false, error}` in `sync_run.parts`; later parts still run (details is skipped if roster failed on the first-ever sync, as there is nothing to detail).

### 6.4 Errors

- **Auth rejected** (genshin.py `InvalidCookies` or equivalent) → set connection status `expired`, stop the run, show a "Reconnect HoYoLAB" banner on every page.
- **Rate limited** → wait and retry the call up to 3 times with increasing delay, then fail that part.
- **Unknown character id** → trigger a game-data refresh after the run; render the character with a placeholder until known.
- **Logging:** request errors are logged without headers or cookie values.

---

## 7. Status and progress logic

Shared by backend (API returns derived fields) and frontend (display).

- **Status** = f(owned, goal): `none`+not owned → `unobtained`; `none`/`want`+owned → `obtained`; `want`+not owned → `wanted`; `build`+not owned → `wanted` with `prefarming=true`; `build`+owned → `building`.
- **Choosing `build`** with no existing targets fills `default_targets`. Switching away from `build` keeps the stored targets (restored if `build` is chosen again).
- **Progress** (building only) = average over level, normal, skill, burst of `min(current, target) / target`, where `target` is the stored target; a component whose target is at or below its current value counts as 1. Weapon level is shown but excluded from progress in phase 1.

---

## 8. Frontend pages

### 8.1 Layout

Top navigation: Dashboard · Characters · Teams · Inventory · Events · Map · Wishes · Profile · Settings, with Teams–Profile disabled and labelled with their phase. Right side: sync status ("Syncing…", "Synced 3 min ago", "⚠ 1 part failed" → popover with details) and the **Sync** button. A "Reconnect HoYoLAB" banner appears below the nav when status is `expired`; "Connect HoYoLAB" when `missing`.

### 8.2 Characters (`/characters`)

- Filters: element, weapon type, rarity (multi-select chips), name search. Applied within all sections.
- Sections in order: **Actively building**, **Obtained**, **Wanted**, **Unobtained**, each with a count and collapse toggle. Unobtained collapsed by default. Collapse state stored in `localStorage` (wrapped in try/catch; defaults apply if unavailable).
- Sort: Building by progress ascending; others by rarity desc, element, name.
- **Card:** icon on rarity background, name, one status line:
  - Building — progress bar; tooltip with `Lv 80→90 · 6/8/8 → 8/8/8`.
  - Obtained — `Lv 80 · C2`.
  - Wanted — `Wanted` or `Pre-farming`.
  - Unobtained — dimmed card, no line.
- **Hover (or focus) → goal switch** `None / Want / Build`; saves via `PUT /api/characters/<id>/goal`; card moves sections immediately (optimistic update, reverted with an error toast on failure). Clicking the card body opens the detail page.

### 8.3 Character detail (`/characters/<slug>`)

- Header: splash art, name, element, weapon type, rarity, "← Characters".
- Goal switch; when `build`, editors for target level (dropdown of level caps 20, 40, 50, 60, 70, 80, 90, plus any higher caps the game currently allows), three talent targets (1–10), weapon target level. Saved on change.
- If owned: level/ascension/constellation/friendship; talents as current → target; weapon card (icon, name, level, refinement); five artifact cards (set, slot, main stat, substats); stats table.
- If not owned: game info, goal, and targets only.
- Placeholder panel: "Material shortfall — arrives in phase 2".

### 8.4 Settings (`/settings`)

- **HoYoLAB:** status line; connect/reconnect form with the F12 steps; account chooser when several accounts exist.
- **Sync:** interval input; table of the last 10 runs with per-part results.
- **Defaults:** default targets editor.
- **Game data:** last fetched time, last error, "Refresh game data" button.

### 8.5 Dashboard (`/`)

- Resin `current/max` with time-until-full counting down in the browser from `resin_full_at`; commissions; expeditions with return times; realm currency. Each shows "as of <sync age>".
- Building summary: "N characters building · average X% to target" linking to Characters.
- When not connected: a card pointing to Settings.

---

## 9. API (phase 1)

| Method & path | Purpose |
|---|---|
| `GET /api/characters` | All visible characters with game info, owned data summary, goal, targets, derived status, progress |
| `GET /api/characters/{slug}` | Full detail incl. artifacts and stats |
| `PUT /api/characters/{id}/goal` | Set goal and/or targets |
| `GET /api/dashboard` | Live notes, building summary, connection and sync status |
| `POST /api/sync?trigger=auto\|manual` | Start or join a sync; returns run id or `429` |
| `GET /api/sync/status` | Current/last run and recent runs |
| `GET /api/settings` | Settings, connection status (no secrets), game-data status |
| `PUT /api/settings` | Update interval and default targets |
| `POST /api/settings/hoyolab` | Connect flow (§6.1) |
| `POST /api/gamedata/refresh` | Refresh game data |
| `GET /api/img/{name}` | Cached art |

---

## 10. Testing

### Backend (pytest)

- **Fixtures:** one recorded response each for game accounts, roster, detailed characters, notes, and the Yatta list, with UID, nickname, and other identifiers replaced by fake values before commit. Sync tests run against fixtures with the HoYoLAB client mocked; no network.
- **Unit tests:** status derivation (all six combinations); `build` default-target fill and target retention; progress formula including targets at/below current; Traveler/Manekin collapse and unreleased filtering; auto-sync interval check; manual 60 s limit; single flight; partial-failure isolation; expired cookie → `expired` status and stopped run; connect writes `.env` only after a successful test and preserves other lines; backup rotation keeps 5.
- **Secret leakage test:** with known fake cookie values configured, no API response body and no captured log record contains them.
- **API tests:** TestClient against a temporary SQLite file with migrations applied from empty.
- **Smoke:** `python -m app.smoke` — manual, live, prints counts per part; not run in CI.

### Frontend

- `svelte-check` with no errors.
- Vitest: status line text, progress display, section grouping and sort.
- Playwright (backend running on fixture data): Characters → hover a card → Build → card appears under Actively building with a progress bar → open detail → target editors visible.

---

## 11. Done when

1. Fresh clone → copy `.env.example` → follow README → `python run.py` → site loads on `127.0.0.1:8765`.
2. Connecting via Settings shows the full roster in the correct sections with no manual entry.
3. Goals and targets persist across restarts and syncs.
4. Dashboard shows resin, commissions, expeditions, and realm currency.
5. All tests pass; repository contains no cookie values, UID, nickname, or game art.
