# Phase 5 — Events, Profile, Map: Design

**Date:** 2026-11-21
**Status:** Approved 2026-11-21
**Parent:** [Overview design](2026-11-19-genshintracker-overview-design.md). Builds on [Phase 1](2026-11-19-phase1-foundation-design.md), [Phase 2](2026-11-19-phase2-planner-design.md), [Phase 3](2026-11-20-phase3-wishes-design.md) and [Phase 4](2026-11-21-phase4-teams-design.md); stays within the overview's architecture, data model and rules (§3, §4, §6, §7).

---

## 1. Goal

The last three pages go live and the Dashboard is completed. **Events** shows what is happening in the game now (banners, events with their rewards, challenge resets) and every past banner with the user's own pulls; **Profile** shows the Battle Chronicle (account stats, exploration, Spiral Abyss, Imaginarium Theater, Stygian Onslaught) and keeps a history of challenge runs that HoYoLAB itself forgets; **Map** embeds the two community maps with a fallback when a site refuses embedding. All of it comes from data already reachable with the user's HoYoLAB connection, with no manual entry beyond ticking events done.

### Agreed decisions

| Topic | Decision |
|---|---|
| Scope | **One spec, built in three milestones**: Events → Profile → Map. Each milestone is usable on its own and pushed when done. |
| Events page | Live and upcoming banners (featured 5★/4★, time left); in-game events with reward and primogem totals; Spiral Abyss / Imaginarium Theater / Stygian Onslaught reset countdowns; searchable banner history with the user's pulls. |
| Event progress | A **manual Done tick** per event; done events dim and sort last; the Dashboard shows "N events left · X primos". |
| Dashboard | New cards: **Live banners**, **Events left**, **Resets**, **Profile summary**. |
| Profile | **Account stats**, **exploration per region**, **Abyss / Theater / Stygian this cycle**. No Serenitea Pot. |
| History | **Challenge runs are kept** (one row per challenge cycle once seen); account stats stay current-only. |
| Map | **Two tabs** (HoYoLAB Interactive Map, AppSample), **default from Settings**, then last used; **Open in new tab** always available, and a fallback card when a site refuses embedding. |
| Refresh | New HoYoLAB parts run **with the normal sync, throttled to once per 60 minutes**; a manual **Sync now** always fetches them. |
| Storage | **Approach A**: current calendar and profile as JSON snapshots; challenge history and Done ticks in their own tables. |

### In scope

- `sync/`: three new sync parts (`calendar`, `profile`, `challenges`) behind the existing `SyncManager`, with a per-part throttle.
- `events/` (new, pure): event and banner views, primogem totals, reset times, banner history with pulls.
- `profile/` (new, pure): profile and challenge views.
- `mapcheck.py` (new): daily embeddability check of the two public map URLs.
- Pages: **Events**, **Profile**, **Map** (new); **Dashboard** cards; **Settings** default map and new part timestamps.

### Out of scope

- Serenitea Pot, daily snapshots of account stats, achievement lists.
- Notifications or reminders for events ending.
- Own map or marker data (overview §10).
- Automatic detection of event completion (HoYoLAB does not report it reliably).
- Gacha calendars or events of other games.

---

## 2. Data sources

All through genshin.py 1.7.32 (the pinned version), called only from `backend/app/sync/hoyolab.py`.

| Part | Call | Notes |
|---|---|---|
| `calendar` | `get_genshin_event_calendar(uid)` → `character_banners`, `weapon_banners`, `chronicled_banners`, `events`, `challenges` | Verified reachable by the 2026-11-19 probe. |
| `profile` | `get_partial_genshin_user(uid)` → `info`, `stats`, `explorations` (`characters`, `teapot` ignored) | Not yet probed. |
| `challenges` | `get_genshin_spiral_abyss(uid)` and `(previous=True)`; `get_imaginarium_theater(uid)` and `(previous=True)`; `get_stygian_onslaught(uid)` | Not yet probed. |

Banner history uses Phase 3's `game_banner` table and its pull attribution (`wishes/pity.attribute`); nothing new is fetched for it.

### 2.1 First build step: live check

As in Phase 3 §14, the first step of Milestone 1 runs `python -m app.smoke --calendar --profile --challenges` (live, read-only) against the user's account and writes anonymised findings to `docs/superpowers/notes/` (no UID, nickname, signature, or cookie). It confirms, before the parsers are written:

1. The calendar's banner, event and challenge field names; where an event's rewards and primogem counts live; whether event ids are stable across calls.
2. Whether challenge entries give the current Abyss/Theater/Stygian period start and end.
3. The profile's stat and exploration field names (including offerings and reputation).
4. Whether Abyss, Theater and Stygian results include the teams used, and the shape of each result's summary (stars, floor/chamber, act, difficulty).

Each check has a fallback: a field that is missing is shown as "—", and the related display is dropped from the page rather than guessed.

---

## 3. Sync

### 3.1 Parts and order

The new parts run after `roster`, `details`, `notes`, `gaps`, in the order `calendar`, `profile`, `challenges`. Each catches its own errors and records `{ok, error, count}` in `sync_run.parts` like the existing parts; a failure never stops the others. Gaps-only runs (trigger `gaps`) never run them.

### 3.2 Throttle

For triggers `auto` and `connect`, a new part runs only when its last successful run is more than **60 minutes** old; otherwise it is recorded as `{ok: true, skipped: "fresh"}`. Trigger `manual` always runs them. The last-success time per part is read from `hoyolab_snapshot.fetched_at` (calendar, profile) and from the newest successful `challenges` part in `sync_run` (challenges).

### 3.3 Boundary

`sync/hoyolab.py` converts every result to our own dataclasses, as the other parts do. The UID, nickname, signature and avatar of the account are dropped at the boundary and never stored, logged or returned. Character ids in banners and teams are mapped through `canonical_id`.

### 3.4 Storage

- `calendar` and `profile` replace their `hoyolab_snapshot` row as a whole after a successful fetch; on failure the previous row stays.
- `challenges` upserts one `challenge_run` row per (kind, season) it sees with data; cycles with nothing attempted (or locked) write nothing. Rows are never deleted by sync.
- An unknown character id in a banner or team triggers the existing game-data refresh after the run.

---

## 4. Data model (one Alembic migration, `0005`)

| Table | Category | Columns |
|---|---|---|
| `hoyolab_snapshot` | Account (overwritten by sync) | `part` PK (`calendar` / `profile`), `data` JSON (our dataclasses, serialised), `fetched_at` (UTC) |
| `challenge_run` | User history (sync upserts, never deletes) | `kind` (`abyss` / `theater` / `stygian`) + `season` (period start, server-local date string) PK, `start`, `end` (UTC), `summary` JSON (per kind: Abyss stars, max floor-chamber, wins/battles; Theater act reached, stars/medals, difficulty; Stygian difficulty cleared and best time where reported), `teams` JSON (list of character-id lists, empty when not reported), `seen_at`, `updated_at` |
| `event_done` | User (sync never writes) | `event_id` PK (HoYoLAB event id), `done_at` (UTC) |

`setting` gains `default_map`: `hoyolab` (default) or `appsample`.

Rules:

- `event_done` rows whose event is no longer in the calendar snapshot are deleted on startup once they are older than 60 days.
- The map embed check cache lives in `game_meta` (`map_embed_<site>`: `{allowed: bool | null, checked_at}`).

---

## 5. Logic (pure modules)

### 5.1 `events/`

- **`live_banners(snapshot, now)`** — current banners per pool with featured 5★/4★ (ids, names, icons via the catalogue), start, end, and `pulls` (count of the user's wishes attributed to the matching `game_banner` window, plus the 5★/4★ items obtained); upcoming banners (start in the future) separately.
- **`events(snapshot, done_ids, now)`** — each event with name, description (plain text), start, end, rewards (item, count), `primogems` (sum of reward items that are Primogems), `done`, `ending_soon` (ends within 24 h). Order: not done first, then by end time; done last.
- **`events_left(...)`** — count and primogem total of not-done events still running.
- **`resets(snapshot, now, region)`** — next daily (04:00 server) and weekly (Monday 04:00 server) reset from the existing `servertime` helpers; Spiral Abyss, Imaginarium Theater and Stygian Onslaught period ends from the calendar's challenge entries. Fallback when an entry is missing: Abyss on the **16th** at 04:00 server time, Theater on the **1st** at 04:00 server time; Stygian has no fallback and is hidden.
- **`banner_history(session, pool, q, page)`** — `game_banner` rows newest first, filtered by pool and a case-insensitive search on banner name or featured item name, 50 per page, each with the user's pull count and 5★/4★ obtained on it.

### 5.2 `profile/`

- **`profile_view(snapshot)`** — header (AR, world level, days active), stat tiles (achievements, characters, chests by type, oculi by type, waypoints, domains), regions (name, exploration %, reputation level, offering name and level) in game order.
- **`challenge_views(session, now)`** — per kind: the current cycle (if any), and past runs newest first.

### 5.3 `mapcheck.py`

`embeddable(url)` — one GET (no cookies, short timeout, redirects followed) to the public map URL; returns `False` when `X-Frame-Options` is `DENY` or `SAMEORIGIN`, or when CSP `frame-ancestors` does not allow any origin (`'none'` or a list without `*` and without `http://127.0.0.1:<port>`), `True` otherwise, `None` on network failure. Cached for 24 h in `game_meta`. Map URLs:

- HoYoLAB: `https://act.hoyolab.com/ys/app/interactive-map/index.html`
- AppSample: `https://genshin-impact-map.appsample.com/`

---

## 6. Pages

### 6.1 Nav

**Events**, **Profile** and **Map** become enabled as their milestones land.

### 6.2 Events (`/events`)

1. **Live banners** — one card per current character, weapon and chronicled banner: featured 5★ art, 4★ icons, a live countdown, and "You pulled N here · got X". **Coming up** lists upcoming banners when the calendar has them.
2. **Events** — header "N left · X primos unclaimed". One row per event: name, time left (warning colour within 24 h), reward icons with the primogem total, and a **Done** checkbox (optimistic save, reverted with an error toast on failure). Done rows dim and sort last. Clicking a row shows the description.
3. **Resets** — one row of countdowns: Daily, Weekly, Spiral Abyss, Imaginarium Theater, Stygian Onslaught.
4. **Banner history** — pool tabs (Character, Weapon, Chronicled), search box, 50 per page, newest first; each row: banner name, dates, featured 5★/4★ icons, and the user's pulls on it.

Header: "as of <calendar age>", with a warning when the last `calendar` part failed. Without any snapshot: "Sync to load the event calendar" (or the Connect banner when not connected). Banner history works without a connection.

### 6.3 Dashboard

Added below the existing cards, in this order:

1. **Live banners** — featured 5★ icons with time left; links to Events.
2. **Events left** — "N events left · X primos", then the three not-done events ending soonest with time left; links to Events. When all are done: "All events done ✓".
3. **Resets** — the compact countdown row.
4. **Profile summary** (Milestone 2) — AR, this cycle's Abyss stars and Theater act; links to Profile.

Each shows "as of <age>"; without data each points to Sync or Settings.

### 6.4 Profile (`/profile`)

- Header: AR, world level, days active ("as of <profile age>").
- Stat tiles (§5.2).
- **Exploration** — one card per region: exploration %, reputation level, offering level.
- **Spiral Abyss**, **Imaginarium Theater**, **Stygian Onslaught** — each a panel with the current cycle (stars or act or difficulty, wins/battles, teams as character icons when reported, period end countdown) or "Not attempted this cycle"; below it a **Past runs** table from `challenge_run`, newest first.

### 6.5 Map (`/map`)

- Tabs **HoYoLAB Interactive Map** and **AppSample**. Initial tab: the last-used tab from `localStorage` (try/catch), otherwise `default_map`.
- Each tab: a full-height iframe and a slim bar with the map name and **Open in new tab**.
- When the cached check says embedding is refused (`allowed: false`), the tab shows a card "This map doesn't allow embedding" with a large **Open in new tab** button instead of the iframe. When unknown (`null`), the iframe is tried; the bar's button is always there.

### 6.6 Settings

- **Default map** choice.
- The sync runs table shows the new parts (including `skipped: fresh`).

---

## 7. API

| Method & path | Purpose |
|---|---|
| `GET /api/events` | Live and upcoming banners, events (with `done`), events-left totals, resets, snapshot age and last error |
| `PUT /api/events/{event_id}/done` | `{done: bool}` |
| `GET /api/banners/history?pool&q&page` | Banner history page (50) with total and pulls |
| `GET /api/profile` | Profile view, challenge views (current + past), snapshot age and last error |
| `GET /api/map` | Both maps: name, URL, `allowed` (`true` / `false` / `null`), plus `default_map` |
| `GET /api/dashboard` | Adds `live_banners`, `events_left`, `resets`, `profile_summary` |
| `GET /api/settings`, `PUT /api/settings` | Include `default_map` |
| `GET /api/sync/status` | Includes the new parts |

---

## 8. Errors

| Situation | Behaviour |
|---|---|
| A new part fails (network, rate limit, unexpected shape) | Recorded in `sync_run.parts`; other parts continue; pages show last-known data with "as of" and a warning |
| Cookie expired | Existing behaviour: run stops, Reconnect banner |
| Challenge locked or not attempted this cycle | "Not attempted this cycle"; no `challenge_run` row |
| Event without rewards or primogems | Primogem total 0; event still listed |
| Done tick on an event that later disappears | No effect; row cleaned up after 60 days |
| Unknown character id in a banner or team | Placeholder icon; game-data refresh after the run |
| Map site unreachable / check fails | `allowed: null`; iframe tried; Open in new tab always visible |
| Calendar missing a challenge entry | Fallback reset rules (§5.1); Stygian hidden |

---

## 9. Security and data safety

- Cookie values, UID, nickname, signature and region are never logged or returned; the profile's identity fields are dropped at the sync boundary.
- The map check sends only an unauthenticated request to the two fixed public URLs; no user data, no cookies.
- The secret-leakage test is extended to the new parts (with fake profile identity fields that must never appear) and to every endpoint in §7.
- Fixtures are synthetic or anonymised, with UID 800000001; the live-check notes contain no identifiers.
- `challenge_run` is user data and goes into the existing pre-sync database backups.

---

## 10. Testing

### Backend (pytest)

- Parsers for `calendar`, `profile`, Abyss, Theater and Stygian from anonymised fixtures shaped by the live check.
- Throttle: skipped under 60 minutes for `auto`/`connect`, always run for `manual`, never run for `gaps`; `skipped: fresh` recorded.
- Part isolation: one new part failing leaves the others and the snapshots intact.
- `challenge_run` upsert: current and previous cycles, re-seen cycle updated, empty cycle skipped, never deleted.
- Events: primogem totals, ordering (not done, by end; done last), ending soon, events left.
- Resets: daily/weekly for all three server regions; challenge ends from the calendar; Abyss/Theater fallbacks around the 1st and 16th at 04:00.
- Banner history: pool filter, search, paging, pulls per banner.
- `event_done`: set/clear, 60-day cleanup.
- `mapcheck`: X-Frame-Options DENY/SAMEORIGIN, CSP `frame-ancestors` variants, allowed, network failure → `None`, 24-hour cache.
- API tests for every endpoint in §7 against a temporary SQLite database; extended leak test.

### Frontend

- `svelte-check` with no errors.
- Vitest: countdown text, event sorting and primogem sums, map initial-tab choice.
- Playwright (seeded data), one per milestone: Events — tick an event Done → it dims and the Dashboard "events left" count drops; Profile — Abyss past runs listed; Map — the seeded refused check shows the fallback card with Open in new tab.

### Smoke

`python -m app.smoke --calendar --profile --challenges`: live, read-only; prints counts and field summaries without identifiers. Used for §2.1.

---

## 11. Milestones

1. **Events** — live check (§2.1); calendar parsing and `calendar` part with throttle; `hoyolab_snapshot`, `event_done`; `events/` logic; Events page; Dashboard Live banners, Events left and Resets cards; Events nav.
2. **Profile** — `profile` and `challenges` parts; `challenge_run`; `profile/` logic; Profile page; Dashboard Profile summary; Profile nav.
3. **Map** — `mapcheck.py`; `GET /api/map`; Map page; Default map setting; Map nav.

Each milestone ends with all tests passing and is pushed when done.

---

## 12. Done when

1. All nine pages are live.
2. The Events page lists the same events and banner end times as the game, and ticking an event Done updates the Dashboard count.
3. The Profile matches the in-game Battle Chronicle, and a past Abyss cycle stays listed after HoYoLAB stops reporting it.
4. Each map either embeds or shows the fallback card, and Open in new tab always works.
5. All tests pass; the repository contains no cookie values, UID, nickname, or personal data.

---

## 13. Refinements made during planning (2026-11-21)

1. HoYoLAB's profile has no world level; the header shows AR and days active only.
2. `challenge_run.season` is HoYoLAB's own period id as a string (Abyss `season`, Theater `schedule.id`, Stygian `season.id`).
3. A part's last success for the throttle is read from `sync_run` (newest run whose part has `ok` and no `skipped`), the same way for all three parts.
4. A live banner's "your pulls" uses the Phase 3 `game_banner` window of the same pool that contains the banner's start and shares a featured 5★; no match → no pull count shown.
5. The calendar's `is_finished` event flag is ignored; Done stays manual.
6. From the live check: Stygian's reset countdown falls back to the current Stygian run's period end (the calendar lists only Abyss and Theater); reputation is shown only when above 0; regions are ordered by HoYoLAB id; a connect sync always fetches the calendar, profile and challenges.
