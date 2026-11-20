# Phase 2 — Planner: Design

**Date:** 2026-11-19
**Status:** Draft for review
**Parent:** [Overview design](2026-11-19-genshintracker-overview-design.md). Builds on [Phase 1 — Foundation](2026-11-19-phase1-foundation-design.md); stays within the overview's architecture, data model, and rules.

---

## 1. Goal

For every character with goal `build` (owned or pre-farming), the app shows **what is still left to farm**, automatically, with no manual entry. The user never compares "need" against "have" and never reads a total where a remainder is meant.

### Agreed decisions

| Topic | Decision |
|---|---|
| GOOD inventory import | **Not in phase 2.** Deferred to a later phase. |
| Recalculation after edits | Goal/target/planned-weapon edits trigger a **debounced, gaps-only** recalculation; every normal sync also refreshes gaps. |
| Weapon materials | Included, for a **planned weapon**: the equipped one by default, or any weapon of the character's type chosen by the user. |
| Inventory page | A **backpack-style grid of all upgrade materials** (database feel), grouped by category, showing what is known per tile. |
| Crafting | Counted in "still to farm": short items coverable by crafting from spare lower tiers are shown as "craft N", not as farming. |
| Dashboard | **Active today** domains, **Weekly bosses** with a manual "done this week" toggle plus HoYoLAB's discounted-runs counter, and **Building** cards listing only what each character still needs. |
| Shared materials | Inventory and Farm today use the **combined** shortfall; character views show the character's own shortfall with a "shared" mark. |

### In scope

- Material, domain, and weapon game data from Yatta.
- Calculator gap sync (`gaps` sync part) and gaps-only runs.
- Planner module: inventory states, crafting rollup, farm today, weekly bosses, per-character shortfall.
- Pages: **Inventory** (new), **Dashboard** sections, **Character detail** shortfall panel and planned-weapon picker.

### Out of scope (deferred)

- GOOD-format import (exact counts for every tile).
- Artifact planning.
- Weapon inventory (weapons not equipped by anyone; HoYoLAB reports only equipped weapons).
- Manual count entry.

---

## 2. What "have" means without an import

The calculator reports, per material, `need` and `short` only for materials some Build character needs. Each tile therefore has one of three states:

| State | Condition | Known | Tile shows |
|---|---|---|---|
| `short` | combined `short > 0` | exact have = need − short | `have/need`, red **−N to farm**, craft hint |
| `met` | needed, `short = 0` | have ≥ need | green "✓ need" |
| `unneeded` | no Build character needs it | nothing | dimmed, no number |

---

## 3. Game data

Source: Yatta (`https://gi.yatta.moe/api/v2/en/...`), verified reachable 2026-11-19:

- `/material` — 832 items with `type`, `rank`, `recipe` (craftable flag), `icon`.
- `/material/{id}` — detail incl. `source` (e.g. domain or boss name) and `additions.requiredBy`.
- `/dailyDungeon` — per weekday (`monday` … `sunday`), each open domain with `id`, `name`, `reward` (material ids), `city`.
- `/weapon` — 279 weapons with `id`, `rank`, `type` (`WEAPON_*`), `name`, `icon`.

Refresh triggers are the same as phase 1's character data: first run, data older than 7 days at startup, an unknown id seen in a sync, and "Refresh game data" in Settings. Per-material detail calls are made only for materials in the eight categories below (about 300) and cached; later refreshes fetch details only for new ids. On failure: keep cached data, store the error in `game_meta`, show it in Settings.

### Categories (Inventory section order)

1. Character EXP and weapon enhancement (EXP books, enhancement ore, Mora)
2. Character ascension: elemental gems and boss drops
3. Local specialties, by region
4. Talent books
5. Weapon ascension materials
6. Common enemy drops
7. Weekly boss drops
8. Crowns and other special materials

Quest items, food, potions, gadgets, currencies, and similar types are excluded. The mapping from Yatta `type` (+ `rank` and `source` where a type spans categories) to our category lives in one function in `gamedata/` with unit tests.

Materials whose ids are unknown to the catalogue are shown in an **Other** section as placeholder tiles and trigger a game-data refresh.

---

## 4. Data model (phase 2 additions)

One Alembic migration adds the following.

### Game data

| Table | Columns (key ones) |
|---|---|
| `game_material` | `id` PK, `name`, `icon`, `rarity`, `yatta_type`, `category`, `family` (groups the tiers of one material line), `craft_from` (id of the next-lower tier or null), `sources` (JSON), `sort_order` |
| `game_domain` | `id` PK, `name`, `kind` (`talent`/`weapon`), `city`, `weekdays` (JSON list, 0 = Monday), `material_ids` (JSON) |
| `game_weapon` | `id` PK, `name`, `icon`, `rarity`, `weapon_type` |

### Account data (overwritten by sync)

| Table / column | Contents |
|---|---|
| `owned_character.weapon_id` | equipped weapon id from the roster (new column) |
| `live_notes.weekly_discounts_left`, `live_notes.weekly_discounts_max` | from `remaining_resin_discounts` / `max_resin_discounts` (new columns) |
| `material_gap` | `character_id`, `material_id` (PK pair), `need`, `short` — the character's own result |
| `material_total` | `material_id` PK, `need`, `short`, `spare` (from `available_material`, 0 if absent) — combined across all Build characters |
| `gap_run` | single row: `computed_at`, `snapshot` (JSON of goals/targets/planned weapons used), `ok`, `error` |

### User data

| Table / column | Contents |
|---|---|
| `character_goal.planned_weapon_id` | null = equipped weapon (owned) / no weapon (not owned) |
| `weekly_boss_done` | `boss` (name), `week_start` (datetime of the Monday 04:00 server-time reset), PK pair |

Rules:

- Sync replaces `material_gap` and `material_total` as a whole after a successful gaps part; on failure the previous rows stay.
- `weekly_boss_done` rows for earlier weeks count as not done; nothing has to be cleared. Rows older than 8 weeks may be deleted on startup.
- Sync never writes `character_goal` or `weekly_boss_done`.

### Server time

Region offset from `GENSHIN_REGION`: America UTC−5, Europe UTC+1, Asia and TW/HK/MO UTC+8. Daily reset 04:00 server time; weekly reset Monday 04:00 server time. All reset logic takes the clock as a parameter.

---

## 5. Gap sync

### 5.1 Gaps part

Runs as the fourth sync part, after roster, details, and notes (it needs current levels, talents, and weapon ids). It is skipped with `"skipped: roster failed"` when roster failed, and with `{ok: true, count: 0}` when there are no Build characters (`material_gap` and `material_total` are then emptied).

One `batch_compute` request (genshin.py `batch_calculator()`); the `sync/hoyolab.py` wrapper adds the account `uid` and `region` to the request body. Per Build character:

- **Character level:** current → `target_level`.
- **Talents:** normal, skill, burst: current → targets.
- **Weapon:** the planned weapon (`planned_weapon_id`, else the equipped `weapon_id`) from its current level → `target_weapon_level`. A planned weapon that is not the equipped one starts at level 1. A character with no weapon (pre-farming, none planned) gets no weapon entry.
- **Owned** characters use synced levels and talents. **Pre-farming** characters start at level 1, talents 1/1/1; their talent ids come from HoYoLAB's calculator character data (genshin.py `get_character_talents`), cached in `game_meta`.

Mapping:

- `single_role_result` → `material_gap` (per character).
- `overall_consume` → `material_total.need/short`.
- `available_material` → `material_total.spare`.
- `has_user_info = false` → the part **fails** with "HoYoLAB returned no inventory data"; nothing is stored.

The `sync/hoyolab.py` boundary converts the result to our own dataclasses, like the other parts.

### 5.2 Gaps-only runs

- Any change to a goal, target, or planned weapon schedules a gaps-only run **3 s** later; further changes within that window restart the timer.
- It goes through `SyncManager` with trigger `gaps` and runs only the gaps part (no backup copy).
- If any run is in progress, the gaps run is queued and starts when that run finishes; at most one is queued.
- Exempt from the 60 s manual limit; still single-flight. It does not count as a "successful sync" for the auto-sync interval.
- `gap_run.snapshot` records the inputs used. The API reports `gaps_stale = true` while the current goals/targets differ from the snapshot; the UI shows **"Updating…"** then.

### 5.3 Crafting rollup

Per material family, from the lowest tier upward (3 of tier *k−1* craft 1 of tier *k*):

```
carry = 0
for tier in family (lowest first):
    available_lower = carry                       # spare lower-tier items, in units of this tier
    craftable[tier] = min(short[tier], available_lower)
    to_farm[tier]   = short[tier] - craftable[tier]
    carry = (spare[tier] + (available_lower - craftable[tier])) // 3
```

`spare` comes from `material_total.spare`. Mora cost of crafting is ignored. Inventory and Farm today use `to_farm`; tiles show "craft N" when `craftable > 0`.

### 5.4 Verification in the first build step

Checked against the user's live account with the smoke command before the rest is built; each has a fallback:

1. **Does `lack_num` already account for crafting?** If yes, the rollup only produces the "craft N" hint and does not subtract again.
2. **Is there a per-request character limit in `batch_compute`?** If yes, stop and amend this spec before continuing.
3. **Are weapon materials returned with correct shortfalls?** If not, drop the planned-weapon feature from phase 2 (weapon materials deferred).
4. **Ascension at level caps.** HoYoLAB does not report whether a character at a cap (e.g. 80) is ascended; record what the calculator assumes and document it in the README.
5. **Shape of `available_material`.** Confirm it lists spare counts per item; if not, `spare` is 0 and crafting hints are not shown.

### 5.5 Failure

The gaps part fails on its own like other parts (recorded in `sync_run.parts`). Pages keep showing last-known gaps with "as of <time>" and a warning.

---

## 6. Planner (`backend/app/planner/`)

Pure functions over database rows; no HoYoLAB access.

- **`inventory()`** — every catalogue material in the eight categories with its state (§2), `need`, `short`, `craftable`, `to_farm`, sources, and the characters needing it (from `material_gap`, with each one's need). Ordered by category, family, tier.
- **`farm_today(now, region)`** — server weekday after the 04:00 reset; today's open domains (all on Sunday) that drop a material with `to_farm > 0`, each with those materials and the characters needing them. Domains with nothing to farm are omitted.
- **`weekly_bosses(now, region)`** — bosses whose drops have `to_farm > 0`, with materials, characters, and `done_this_week`; done bosses last. Bosses are identified from the `sources` of category-7 materials. Header values: discounted runs left/max from `live_notes`.
- **`character_shortfall(character_id)`** — the character's materials with their own `short` (from `material_gap`). A material is marked **shared** when another Build character also needs it and the combined `short` is larger than this character's.
- **`building_cards()`** — per Build character: progress (phase 1 formula) plus their materials with own `short > 0`.

---

## 7. Pages

### 7.1 Nav

Inventory becomes enabled.

### 7.2 Inventory (`/inventory`)

- Eight category sections (§3) plus **Other** when needed; each a grid of backpack-style tiles: icon on rarity background, name below.
- Tiles by state (§2). Hover or focus → popover with full name, sources (domain + weekdays, boss, or region), characters needing it with each one's need, and the shared note.
- Filter chips **All · Needed · To farm** and a name search. Default **All**. Choice stored in `localStorage` (try/catch; default applies if unavailable).
- Header: "Calculated <age> ago", "Updating…" while `gaps_stale`, warning if the last gaps part failed.
- No Build characters: the grid shows all tiles dimmed with "Set characters to Build to plan farming".

### 7.3 Dashboard (`/`)

Existing tiles stay at the top. Below them:

1. **Active today** — one card per open domain with something to farm: domain name, open weekdays, material tiles with to-farm counts, avatars of characters needing them. Empty: "Nothing to farm in domains today ✓".
2. **Weekly bosses** — header "Discounted runs left N/M". One card per boss with something to farm: material tiles, character avatars, **Done this week** checkbox (optimistic save, reverted with an error toast on failure). Done cards dim and sort last.
3. **Building** — one card per Build character: icon, name, progress bar, and **only** materials still short for them (small tiles with counts and shared marks). Fully covered: "Everything in the bag ✓". Click → detail page.

### 7.4 Character detail (`/characters/<slug>`)

- The phase 1 placeholder becomes **Material shortfall**: tiles grouped by category with need, short, craft hint, and shared mark; "Updating…" while `gaps_stale`.
- **Planned weapon** in the targets editor: dropdown of weapons of the character's type. Default "Equipped: <name>" (owned) or "None" (not owned). Saving schedules a gaps-only run.

---

## 8. API (new or changed)

| Method & path | Purpose |
|---|---|
| `GET /api/inventory` | Categories → materials with state, need/short/craftable/to_farm, sources, characters; gap-run status (`computed_at`, `gaps_stale`, last error) |
| `GET /api/dashboard` | Adds `farm_today`, `weekly_bosses` (with discounts left/max), `building_cards` |
| `GET /api/characters/{slug}` | Adds `shortfall`, `planned_weapon` |
| `PUT /api/characters/{id}/goal` | Also accepts `planned_weapon_id`; any change schedules a gaps-only run |
| `GET /api/weapons?type=<weapon type>` | Weapon list for the picker |
| `PUT /api/weekly-bosses/{boss}` | `{done: bool}` for the current week |
| `GET /api/sync/status` | Includes the `gaps` part and gaps-only runs |

---

## 9. Errors

| Situation | Behaviour |
|---|---|
| Gaps part fails / `has_user_info = false` | Last-known gaps kept; "as of <time>" plus warning |
| Yatta material, weapon, or domain fetch fails | Cached data kept; error in Settings |
| Unknown material id in calculator result | Placeholder tile in **Other**; game-data refresh after the run |
| No Build characters | Inventory dimmed with hint; Dashboard sections show "Set characters to Build to plan farming" |
| Not connected | Catalogue only; the usual Connect banner |

Cookie values, UID, and region are never logged or returned. The phase 1 secret-leakage test is extended to the new endpoints and to log records captured during a gaps run.

---

## 10. Testing

### Backend (pytest)

- Yatta parsing: material categories, families and craft chains, domain schedule, weapons (trimmed public fixtures).
- Calculator mapping from an anonymized `batch_compute` fixture, incl. `has_user_info = false`, pre-farming characters, and planned vs. equipped weapon.
- Crafting rollup: multi-tier chain, leftovers carried upward, nothing spare, `lack_num`-already-netted mode.
- `farm_today` around 04:00 and on Sunday, for all three region offsets.
- Weekly reset for boss toggles (Monday 04:00 server time).
- Shared-material flag.
- Gaps-only runs: debounce, coalescing, queued behind a running sync, exemption from the manual limit, not counted for the auto interval.
- API tests for every endpoint in §8 against a temporary SQLite database.

### Frontend

- `svelte-check` with no errors.
- Vitest: tile state and badge text, filter logic, Building cards show only short materials.
- Playwright (seeded data): Dashboard shows Active today and a boss card → tick Done → card dims; Inventory "To farm" filter shows only short tiles.

### Smoke

`python -m app.smoke` also runs the gaps part and prints per-material need/short/spare counts; used for the checks in §5.4.

---

## 11. Done when

1. With characters set to Build, Inventory, Dashboard, and detail pages show still-to-farm per material with no manual entry.
2. Editing a target updates the shortfall within a few seconds.
3. Active today matches the in-game open domains for the server day.
4. Weekly boss toggles reset on Monday 04:00 server time.
5. All tests pass; the repository contains no cookie values, UID, nickname, or game art.
