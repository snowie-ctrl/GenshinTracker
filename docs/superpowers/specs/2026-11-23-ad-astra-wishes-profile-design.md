# Ad Astra Sub-project 7 — Wishes and Profile

**Date:** 2026-11-23
**Status:** Draft, awaiting user review
**Frame:** `2026-11-22-ad-astra-revision-overview-design.md` (sub-project 7 of 10). Builds on Foundation (`2026-11-22-ad-astra-foundation-design.md`) for the glass look, icons and pills; replaces the Wishes page layout from Phase 3 (`2026-11-20-phase3-wishes-design.md`) and the Profile page from Phase 5 (`2026-11-21-phase5-events-profile-map-design.md`).
**Scope:** Wishes becomes a data-analysis page: pity tiles with a soft-pity mark, an average-pity mark and a guarantee arrow, then one banner filter that drives a set of charts (pulls over time, luck, element and weapon-type spiders, pity histogram, primogems spent) and the 5★ list. Profile becomes an enka.network-style page built only from HoYoLAB data the app already fetches: a hero header, a user-chosen showcase of up to 8 characters with a detail panel, icon stat tiles, exploration rings, roster charts, teapot, boss kills and the challenge cards. No new external service; no migration.

---

## 1. Decisions made with the user

| Topic | Decision |
|---|---|
| enka.network API | Not used. HoYoLAB data only, so the UID goes nowhere new. Signature, world level, namecard and enka's showcase order are therefore out of scope |
| Wishes charts | All four: pulls over time (month or rotation), element + weapon-type spiders, pity distribution + luck, primogems spent |
| Profile additions | All four: character showcase, roster charts, teapot + boss kills, exploration detail |
| Showcase selection | User picks and orders up to 8; default is automatic top 8 |
| Size | One spec and one plan, built in two testable halves (Wishes, then Profile), one merge |
| Wishes layout | B: one banner filter (pills) drives every chart, the luck card and the 5★ list |
| Profile layout | A: enka-style, header and full-width showcase first, then full-width rows |
| Showcase card | A: compact portrait row; clicking a card opens a wide detail panel beneath it |
| Approach | 1: backend computes the analysis in pure Python; frontend draws hand-rolled SVG (no chart library) |

Mockups: `.superpowers/brainstorm/19933-1795489705/content` (git-ignored).

---

## 2. Feasibility (checked 2026-11-23)

- **Wish rows** hold pool, gacha_type, server-local time, seq, name, item_id, item_type and rarity. Element, weapon type and rarity come from joining `item_id` to `game_character` / `game_weapon`. The real history has an item_id on every row.
- **Already computed** in `wishes/pity.py` and `wishes/stats.py`: pity per pull, 5★ outcome (won / lost / guaranteed / unknown), next state, average 5★ pity, monthly counts, pity histogram and per-banner pull counts. Banner attribution uses `game_banner` windows (paimon.moe) with a `version` column.
- **HoYoLAB profile**: the sync already calls genshin.py `get_partial_genshin_user`. `to_profile` keeps only AR, days active, achievements, characters, chests, oculi, waypoints, domains and top-level regions. The same response also carries nickname, server, in-game avatar, `max_friendship_characters`, the `spiral_abyss` string, per-region icon, sub-areas, boss kills and offering icons, and the teapot (level, comfort, tier name/icon, furnishings, visitors, realms).
- **Owned characters** already hold level, constellation, friendship, talents, weapon and final stats (HP, ATK, DEF, EM, CRIT Rate, CRIT DMG, ER, healing, element bonuses); `owned_artifact` holds slot, set, rarity, level, main stat and substats.
- **enka.network** was probed only with its documentation sample UID. Beyond HoYoLAB it would add signature, world level, namecard, profile picture and showcase order; the user declined it.

---

## 3. Wishes (backend)

### 3.1 `wishes/analysis.py` (new, pure)

Input: the `PoolResult`s from `summarize()`, the `Wish` rows, `game_banner` windows and an id → game-data lookup (element, weapon type, rarity, icon, name). Output: `{filter: AnalysisBlock}` where the filters are `all` plus every pool with pulls among `character`, `weapon`, `standard`, `chronicled`. `beginner` pulls count only in `all`.

An `AnalysisBlock` has:

| Key | Content |
|---|---|
| `months` | `[{month: "YYYY-MM", <pool>: count, …}]` sorted by month; one key per pool present in the filter |
| `rotations` | `[{label, version, start, pool_counts: {pool: n}, pulls, fives: [{name, icon}]}]`, one entry per banner phase (version + phase start day, grouped as the Events banner history groups them). Pulls with no banner are left out of this series only |
| `elements` | `{five: {element: n}, four: {element: n}}` over pulled characters; the 7 elements always present (zero-filled) |
| `weapon_types` | `{five: {type: n}, four: {type: n}}` over pulled characters (their weapon type) and weapons; the 5 types always present |
| `unknown_items` | count of 4★/5★ pulls whose item_id is not in game data (left out of the spiders) |
| `pity_hist` | 5★ pity in 10-pull buckets, as today's histogram, plus `soft` and `avg` for the marker lines |
| `primogems` | cumulative series, one point per day with pulls: `{date, total}` at 160 per pull, plus `fives: [{date, name, icon, total}]` markers |
| `luck` | `{avg_pity, expected, verdict, won, lost, rate, judged_label}`; see 3.2 |
| `fives` | the filter's 5★ pulls, newest first, as today's pull view (icon, name, pity, outcome, banner, date); under `all` all pools merged by time, each with its pool |
| `fours` | the filter's 4★ pulls, newest first (compact) |

### 3.2 Luck

- `avg_pity`: mean pity of the filter's 5★ pulls; `null` with no 5★.
- `expected`: expected 5★ pity from the pool's pity rule (`wishes/types.PITY`), computed, not hard-coded: per-pull rate is the base rate (0.6 % character-like pools, 0.7 % weapon) until soft pity, then rises by 6 % (character-like) or 7 % (weapon) per pull, capped at 100 % at hard pity; expected value = Σ n · P(first 5★ at n). Labelled "estimate" in the UI. Under `all`, `expected` is the pull-weighted mean of the pools' expectations.
- `verdict`: `luckier` if `avg_pity < expected − 3`, `unluckier` if `> expected + 3`, else `average`; `null` with no 5★.
- `won` / `lost` / `rate`: 50/50 results for `character`, 75/25 for `weapon`, both for `all` (as `overall_stats` does today); unknown outcomes are left out; `judged_label` is "50/50", "75/25" or "50/50 + 75/25". Absent for standard and chronicled.

### 3.3 Pool payload and API

- Each pool payload gains `avg_pity` (same as `stats.avg_five_pity`, exposed for the tile marker).
- `GET /wishes/summary` returns `pools`, `overall`, `analysis`, `banners`, `banners_available`, `import`. `analysis` replaces `charts`. `banners` keeps today's `banner_timeline` list because the history table's banner filter uses its keys; the page no longer draws it.
- `analysis.py` reuses `stats.monthly` and `stats.pity_histogram` (applied to each filter's rows); the summary no longer returns them on their own.

---

## 4. Wishes page (frontend)

Top to bottom:

1. **Import bar**: unchanged.
2. **Pity tiles** (one per pool with pulls, grid of 4 on wide screens). Each: pool title with a gold **▲** after it when `next_state == "guaranteed"` (title text "Next 5★ is guaranteed"); big `pity5 / hard`; the 5★ bar with the orange soft-pity mark and a light-blue mark at `avg_pity` (hidden when null; title "Your average 5★ pity: N"); 4★ pity bar; Fate line and chart selector on Weapon and Chronicled; radiance line on Character. The old "next pull is guaranteed / 50/50" text line is removed. Clicking a tile selects its filter; the selected tile has a light-blue border.
3. **Filter pills** (`FilterPill`): All banners · Character Event · Weapon Event · Standard · Chronicled, only those with pulls. Default Character Event (else the first pool with pulls). The choice is remembered in `localStorage` (try/catch); a remembered filter with no pulls falls back to the default.
4. **Row: pulls over time (2/3) + Luck (1/3).** `BarChart` gains stacking; a Month / Rotation toggle; under All, bars stack by pool in pool colours with a legend; rotation labels are `version phase` with the phase's 5★ icons under the bar. Luck card: big average pity, "expected ≈ N (estimate)", verdict word, and the won/lost record with rate, or "No 5★ yet".
5. **Row: Elements spider · Weapon-types spider · Where your 5★s landed.** `RadarChart` draws 5★ and 4★ as two overlaid shapes (gold, purple) with element / weapon icons at the axis ends; a small note when `unknown_items > 0`. `Histogram` draws the buckets with the orange soft and light-blue average lines.
6. **Primogems spent**: `LineChart`, full width, cumulative line with gold dots at each 5★ (title shows name and date) and the total at the end.
7. **5★ pulled**: the filter's 5★ list as today (icon, name, pity, outcome badge, banner, date; pool tag under All), then the compact 4★ list.
8. **Wish history** table: unchanged.

New components in `src/lib/`: `RadarChart.svelte`, `Histogram.svelte`, `LineChart.svelte`, `WishFilters` logic in `wishes.ts`; geometry helpers (radar points, stacked bars, histogram scale, line path) live in a pure `charts.ts`. The empty state ("No wishes yet") is unchanged.

---

## 5. Profile (backend)

### 5.1 Wider snapshot (`sync/chronicle.py`)

`ProfileInfo` gains, all optional so older snapshots still load:

- `player`: `{nickname, server, avatar}` from `user.info` (`in_game_avatar`, falling back to `icon`).
- `stats.max_friendship`, `stats.abyss` (the `spiral_abyss` string, e.g. "12-3").
- per region: `icon`, `areas: [{name, explored}]`, `bosses: [{name, kills}]`, offering `icon`.
- `teapot`: `{level, comfort, comfort_name, comfort_icon, items, visitors, realms: [{name, icon}]}`, or `null` when the teapot is locked.

Icons are HoYoLAB CDN URLs and go through the existing `/api/img/remote` allow-list.

### 5.2 `profile/view.py`

`profile_view` returns:

- `header`: nickname, AR, server, avatar, days active, achievements.
- `tiles`: `[{key, label, value, detail?}]` for characters, max friendship, waypoints, domains, Spiral Abyss, chests (total; per-tier `detail`), oculi (total; per-element `detail`). Each `key` maps to an `Icon`.
- `regions`: as today plus icon, areas, offering icon.
- `teapot` (or `null`) and `bosses` (all regions merged, sorted by kills descending).

Sections missing from an older snapshot come back `null`/empty and the page hides them.

New `roster_view(session)` (from `owned_character` + `game_character`): counts by element, weapon type and rarity, total constellations and C6 count.

### 5.3 Showcase

- Stored in `setting` under `profile_showcase` as a JSON list of up to 8 character ids. Unset = automatic: top 8 owned characters by level, then constellation, then rarity, then name.
- Ids no longer owned are skipped (the stored list is left as is).
- Each entry: id, name, rarity, element, portrait/icon, level, constellation, friendship, talents (normal, skill, burst), weapon `{name, icon, level, refinement, rarity}`, `stats` from `owned_character.stats` (in display order, zero bonuses left out), `artifacts` (5 slots from `owned_artifact`: set, icon, rarity, level, main stat, substats), `sets` (bonus summary, e.g. "Golden Troupe 4" or "A 2 · B 2") and `crit_value` (CRIT Rate × 2 + CRIT DMG over artifact substats).
- `showcase_mode`: `auto` or `custom`.

### 5.4 API

- `GET /profile` adds `roster`, `showcase`, `showcase_mode` to today's keys.
- `PUT /profile/showcase {ids: int[]}`: 400 if more than 8, duplicates, or any id not owned; `[]` clears the setting (back to automatic). Returns the new `showcase` and `showcase_mode`.

---

## 6. Profile page (frontend)

Top to bottom:

1. **Hero header**: in-game avatar in a gold ring, nickname, AR pill, small line "server · N days active · N achievements", "as of …" and the last-error line as today.
2. **Showcase**: a row of 8 portrait cards (rarity-tinted background, element badge, name, Lv · C). Clicking a card opens a full-width panel beneath the row, tinted with that character's element: portrait, friendship, talent pills and weapon on the left; the stats list in the middle; the set summary, crit value and 5 artifact cards (slot, main stat, substats) on the right; "Open character" link to the character page. The first card is open by default. **Edit** opens a dialog: owned characters as tickable tiles (max 8), the chosen list with ↑↓ and ×, Save, and "Reset to automatic". Hidden when no characters are owned; "No artifacts synced" when a character has none.
3. **Stat tiles**: a row of icon tiles (original single-colour icons in the sidebar style); chests and oculi show their breakdown on hover/focus.
4. **Exploration**: one card per region with a progress ring, region icon, %, reputation, offering icon + level; sub-area bars expand on click.
5. **Row of three**: Roster (element bars in element colours, weapon-type mini `RadarChart`, rarity split, C6 count) · Teapot (comfort tier icon, level, comfort, furnishings, visitors, realm icons; hidden when null) · Boss kills (top 6, "show all" expands).
6. **Challenges**: Spiral Abyss, Imaginarium Theater, Stygian Onslaught as one row of three glass cards with today's content (result, countdown, team icons, past runs).

Empty states unchanged ("Connect HoYoLAB in Settings…" / "Sync to load your profile").

New components: `ProfileHeader.svelte`, `Showcase.svelte`, `ShowcasePanel.svelte`, `ShowcaseEditor.svelte`, `RegionCard.svelte`; `RadarChart` is shared with Wishes.

---

## 7. Errors and edge cases

- Pulls with no banner: counted everywhere except `rotations`.
- Pool with no 5★: no light-blue mark; Luck shows "No 5★ yet".
- No banner data: outcomes unknown, left out of the won/lost rate; the existing notice stays.
- Item id not in game data: left out of the spiders, counted in `unknown_items`.
- Older profile snapshot: new sections hidden until the next sync.
- Teapot locked: card hidden.
- Bad showcase `PUT`: 400 with a plain message; the page shows it as a toast and keeps the old showcase.

## 8. Security and data safety

- No new external host; no cookie, UID or email goes anywhere new. Icons use the existing `/api/img` and `/api/img/remote` allow-list.
- Test fixtures use made-up UID 800000001 and made-up names; no game art committed.
- No migration: the showcase is a `setting` row; the profile snapshot is JSON.

## 9. Testing

- **pytest**: `analysis.py` (months, rotations incl. unattributed pulls, element/weapon counts incl. unknown ids, histogram, primogem series, luck with a hand-computed expected pity for a small rule and the verdict thresholds, won/lost per filter); pool `avg_pity`; wider `to_profile` on a fake genshin.py object (old and new shapes; teapot null); `profile_view` on an old and a new snapshot; `roster_view`; default showcase order; showcase skips unowned ids; `PUT /profile/showcase` validation; `/wishes/summary` and `/profile` shapes.
- **vitest**: `charts.ts` geometry (radar points, stacked bars, histogram scale, line path); filter default and fallback; showcase editor ordering helpers.
- **Playwright**: Wishes — tiles show the average mark and ▲ when guaranteed, filter pills switch charts and the 5★ list, Month/Rotation toggle, tile click selects the filter. Profile — header, showcase panel opens on click, editing the showcase (the test restores it afterwards: one shared seeded server), teapot and boss cards. Devseed gains made-up teapot, boss, sub-area and player data.
- Full suite at the end: pytest, `npm run check`, vitest, `npm run build`, Playwright.

## 10. Build order

One plan, two halves, each leaving the app working:

1. **Wishes**: `analysis.py` + tests → API → `charts.ts` + chart components → page + e2e.
2. **Profile**: snapshot widening → `profile/view.py` + roster + showcase + API → showcase components → page + e2e.
3. Final verification.

## 11. Out of scope

- enka.network (signature, world level, namecard, profile picture, other UIDs).
- Wish history table changes; import/export changes.
- Hover tooltips beyond SVG `<title>`; chart animation.
- Exact pity probabilities beyond the documented community model (the expected value is an estimate).

## 12. Done when

- Wishes shows the tiles with soft and average marks and the ▲, the filter drives all charts and the 5★ list, and the four chart groups render from real data.
- Profile shows the header, an editable showcase with a detail panel, icon tiles, exploration rings with sub-areas, roster, teapot, boss kills and the challenge cards, all from HoYoLAB data.
- All test suites pass; nothing new is sent to any external service.
