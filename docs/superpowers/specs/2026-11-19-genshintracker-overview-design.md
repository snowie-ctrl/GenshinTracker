# GenshinTracker — Overview Design

**Date:** 2026-11-19
**Status:** Draft for review
**Scope:** Whole-project architecture, shared data model, page list, cross-cutting rules, and phase order. Each phase gets its own detailed spec and plan; this document is the frame they must fit.

---

## 1. Purpose

A single local web app that tells one player everything going on with their Genshin Impact account and the game, replacing a mix of sites (genshintrack.com, wish trackers, event calendars, map sites).

### Problems it solves (from current use of genshintrack.com)

1. **Manual upkeep.** Character levels, talents, and materials must be updated by hand; inventory import is a chore repeated every visit.
2. **Have-vs-need is not shown directly.** The user ends up comparing "what I need" against "what I have" themselves.
3. **Statuses blur together.** Hard to tell unobtained, wanted, obtained, and actively-building characters apart at a glance.

### Success criteria

- Opening the app shows current data **with no manual entry**: roster, talents, weapons, artifacts, material shortfalls, resin.
- Material views show **need, have, and still-to-farm** together; the user never compares two lists.
- The four character statuses are visually distinct and filterable.
- Wish history imports with **one button**, like existing wish trackers.
- The app covers the whole game: banners/events, wishes, teams, map, profile — not only farming.

### Constraints

- **Personal use, local only.** Runs on the user's dev machine; no hosting, no accounts.
- **Public GitHub repository.** No secrets, personal data, or game art may be committed.
- Unofficial HoYoLAB endpoints are acceptable for personal use, but must be isolated so breakage is contained.

---

## 2. Data sources (verified)

A throwaway probe (2026-11-19, `genshin.py` 1.0.0) confirmed the following against a real account:

| Need | Source | Verified result |
|---|---|---|
| Full roster: level, constellation, friendship, weapon (level, refinement), element, rarity | HoYoLAB Battle Chronicle via `genshin.py` `get_genshin_characters` | All owned characters returned (not limited to the showcase) |
| Talent levels, artifacts, stats | `get_genshin_detailed_characters` | Skills with levels, 5 artifacts, base/element/extra properties |
| Material shortfall vs. owned | HoYoLAB calculator `batch_compute` (api v3) | Returns per-material `num` (need) and `lack_num` (short) **only when the request includes the account `uid` and `region`**; without them `has_user_info=false` and everything reads as fully lacking. Also returns `available_material` (lower-tier items usable via crafting). |
| Resin, commissions, expeditions, realm currency | `get_genshin_notes` | Live values |
| Current banners, events, Abyss/Theater | `get_genshin_event_calendar` | Character/weapon/chronicled banners, events, challenges |
| Static game data + art | Yatta (gi.yatta.moe) / Enka asset URLs | Not probed; widely used community sources |
| Banner history | Community banner data (e.g. paimon.moe's open-source banner list) | Not probed |
| Wish history | Game web cache → wish-history URL with authkey (~24 h) → gacha log API | Not probed; well-established method |

**Known limit:** the calculator reports shortfalls, not a full inventory. When `lack_num = 0` we know only `have ≥ need`, not the exact count. A full owned-items list requires an optional GOOD-format import (scanner export, e.g. Inventory Kamera / Irminsul).

**Not built:** an interactive map (embedded instead) and build recommendations (no reliable machine-readable source; the user sets targets).

---

## 3. Architecture

**Chosen approach:** Python FastAPI backend + SvelteKit (TypeScript, static/SPA build) frontend + SQLite. Rejected: Flask + Jinja + HTMX (rich pages like the team builder get clunky) and Qt/QML desktop (user wants web pages; map embedding and public-repo usability are worse).

### Repo layout

```
GenshinTracker/
├─ run.py                     one command: start backend, which serves the built frontend
├─ backend/
│  ├─ app/
│  │  ├─ main.py              FastAPI app; mounts API routers and frontend static files
│  │  ├─ api/                 one router module per page area
│  │  ├─ sync/                ONLY module that calls HoYoLAB (wraps genshin.py)
│  │  ├─ gamedata/            fetch + cache static game data and art
│  │  ├─ wishes/              wish-history import, UIGF import/export, pity logic
│  │  ├─ planner/             have-vs-need aggregation, "farm today"
│  │  └─ db/                  SQLite schema and access
│  └─ tests/
├─ frontend/                  SvelteKit, adapter-static, SSR off
│  └─ src/routes/             dashboard, characters, teams, inventory, events, map, wishes, profile, settings
├─ data/          (ignored)   tracker.db, backups/, image + game-data cache
├─ .env           (ignored)   HoYoLAB cookie values, UID
├─ .env.example               committed template with empty values
└─ docs/superpowers/specs/
```

### Rules

- **The browser talks only to the local backend.** It never contacts HoYoLAB; the cookie never reaches the frontend.
- **Unofficial-API code lives only in `sync/` and `wishes/`.** Every other module works from the database, so an endpoint change breaks one module and the app keeps serving last-known data.
- **Images** are downloaded once by the backend and served from `data/`; no art is committed.
- **Sync triggers:** on page load if the last successful sync is older than the configured interval (default 10 minutes), and a manual "Sync now" button. Scheduled background sync is out of scope for now.
- **Run modes:** `python run.py` for normal use (backend serves `frontend/build`). During development the Vite dev server runs alongside and proxies `/api` to the backend.
- **Network binding:** backend listens on `127.0.0.1` only.

---

## 4. Data model

Three categories, kept separate so a sync never overwrites a user decision.

### 4.1 Game data — refreshed per patch from community sources

- Characters, weapons, materials, artifact sets: IDs, names, rarity, element, weapon type, art URLs, ascension and talent material lists, farmable weekdays for domain materials.
- Banner history: each past banner with dates and featured 5★/4★ items (for attributing pulls).

### 4.2 Account data — overwritten on every sync

- Owned characters: level, constellation, friendship, talent levels, weapon (id, level, refinement), artifacts.
- Material gaps: for current build targets, per material `need` and `lack`.
- Live notes: resin, commissions, expeditions, realm currency, with fetch timestamp.
- Sync log: per-part timestamp and success/failure.

### 4.3 User data — changed only by the user

- **Per-character goal:** `none | want | build`, plus build targets when `build` (character level, three talent levels, weapon level). Default targets come from Settings (initial default: level 90, talents 8/8/8).
- Teams: name, up to 4 members, notes, `building` flag.
- Wish history: every pull (pull id, banner type, banner, item, rarity, time). Stored permanently.
- Optional GOOD inventory import.
- Settings: default targets, sync interval, default map, game install path.

### 4.4 Displayed status (derived)

Ownership comes from sync; intent comes from the goal.

| Goal | Not owned | Owned |
|---|---|---|
| `none` | Unobtained | Obtained |
| `want` | Wanted | Obtained |
| `build` | Wanted (pre-farming) | Actively building |

- "Obtained" is never set by hand; it appears when a sync sees the character.
- Any character with goal `build` — owned or not — is included in planner calculations (the calculator accepts unowned characters).

### 4.5 Teams → goals

- Turning a team's `building` flag **on** sets each member whose goal is `none` (or `want`) to `build`. It never lowers a goal.
- Turning it **off** changes no goals.

---

## 5. Pages

Detailed layouts belong in each phase spec.

| Page | Contents |
|---|---|
| Dashboard | Resin, commissions, expeditions; **Farm today** (short materials whose domain is open today, and which characters need them); live banners/events with countdowns; pity summary; last sync time and status |
| Characters | Art grid; distinct visual treatment per status; filters (status, element, weapon, rarity); one-click goal change; detail view with stats, talents, weapon, artifacts, targets, per-character shortfall |
| Teams | Team builder from the art grid; `building` toggle; combined team shortfall; member status badges |
| Inventory | Need / have / still-to-farm for every material across all `build` characters, grouped by source (weekly boss, domain, local specialty, enemy drop), with location and farm days; full owned list only when a GOOD import exists |
| Events | Current and upcoming banners and events as a timeline; Abyss/Theater resets; searchable banner history |
| Map | Embedded map with a HoYoLAB / AppSample switch; "open in new tab" fallback when a site refuses embedding |
| Wishes | One-button import (backend reads the wish URL from the local game cache); pity per banner type; 50/50 and guarantee state; history; stats; UIGF import/export |
| Profile | AR, days active, achievements, exploration, Abyss/Theater progress |
| Settings | Cookie status (connected / expired — value never shown), sync interval, default targets, default map, game install path, refresh game data |

---

## 6. Failure handling

- **Independent sync parts** (roster, details, gaps, notes, calendar): one failing does not stop the others; failures are recorded in the sync log and shown in the UI. The app always renders last-known data.
- **Expired/invalid cookie:** "Reconnect HoYoLAB" banner linking to Settings instructions.
- **Rate limiting:** batch requests, back off and retry on rate-limit responses, enforce the auto-sync interval, and limit manual sync to once per minute.
- **Unknown IDs after a patch:** trigger a game-data refresh; render a placeholder card meanwhile.
- **Game-data source unavailable:** keep using cached data.
- **Wish import with expired authkey:** tell the user to open Wish History in-game once, then retry. Imports are incremental and de-duplicated by pull id.

---

## 7. Security and data safety

- Cookie stored only in `.env`; never sent to the browser, logged, or exported.
- Backend bound to `127.0.0.1`; no LAN exposure.
- `.gitignore` covers `.env*` (except `.env.example`) and `data/` from the first commit. Every push is checked for secrets and personal data first.
- Test fixtures derived from real responses must have UID, nickname, and other identifiers removed.
- **Wish history is irreplaceable** (the game shows only 6 months): UIGF export/import for portability and importing older history from other trackers; automatic SQLite backups to `data/backups/` before each sync or import, keeping the most recent copies.

---

## 8. Testing

- **Backend (pytest):**
  - Sync code tested against recorded, anonymized HoYoLAB responses; no live calls in the test suite.
  - A separate manual `smoke` command performs a real sync.
  - Unit tests for: status derivation, team → goal rules, have-vs-need aggregation, farm-today weekday matching, pity and 50/50 state, UIGF round-trip.
  - API tests with FastAPI's test client against a temporary SQLite database.
- **Frontend:** `svelte-check` type checks; Vitest for page logic; one Playwright test per phase covering its main flow.

---

## 9. Phases

Each phase: own spec → plan → build → review, and leaves the app usable.

| Phase | Delivers | Done when |
|---|---|---|
| 1. Foundation | Repo skeleton, `run.py`, game-data + art cache, HoYoLAB sync (roster, details, notes), Characters page with goals/statuses, Settings, basic Dashboard (resin, last sync) | Opening the app shows the full roster grouped by status with no manual entry |
| 2. Planner | Calculator gap sync, Inventory page, Farm today, per-character shortfall, optional GOOD import | Need / have / still-to-farm shown for every `build` character |
| 3. Wishes | One-button import, UIGF import/export, pity and 50/50, history and stats | Wish history imported and pity correct against in-game counters |
| 4. Teams | Team builder, `building` toggle feeding goals | Marking a team as building adds its members to the planner |
| 5. Events, Profile, Map | Banner/event timeline and countdowns, Profile page, map embeds with switch, complete Dashboard | All nine pages live |

---

## 10. Out of scope

- Hosting, multi-user accounts, or public deployment.
- Building an own interactive map or marker data.
- Build/artifact recommendations.
- Scheduled background sync (may be revisited after phase 2).
- Writing an inventory scanner (GOOD files from existing tools are imported instead).
