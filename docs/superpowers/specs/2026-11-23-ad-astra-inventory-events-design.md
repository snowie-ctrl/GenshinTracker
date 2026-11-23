# Ad Astra Sub-project 6 — Inventory and Events

**Date:** 2026-11-23
**Status:** Written 2026-11-23, awaiting user review
**Frame:** `2026-11-22-ad-astra-revision-overview-design.md` (sub-project 6 of 10). Builds on Foundation (`2026-11-22-ad-astra-foundation-design.md`) and Dashboard (`2026-11-22-ad-astra-dashboard-design.md`); replaces the Events page from Phase 5 (`2026-11-21-phase5-events-profile-map-design.md`) and the Materials tab layout from Phase 2/6.
**Scope:** Inventory gets a "To farm" strip above a backpack of plain counts. Events becomes a paimon.moe-style timeline with art and a popup, Timers beside it, the Done checklist under it and banner history (by version and phase) at the bottom. A new public announcement feed supplies event art, text, true times and upcoming event wishes. Teapot materials stay in sub-project 10.

---

## 1. Decisions made with the user

| Topic | Decision |
|---|---|
| Backpack tiles without a GOOD scan | Show the best-known count: GOOD scan count when a scan exists; otherwise `need − short` for materials you are short on; otherwise "—". Faded at 0 or "—". A hint says a GOOD import fills every count |
| Event data | Both sources merged: HoYoverse's public announcement feed (art, text, times, upcoming wishes) plus the HoYoLAB calendar (rewards, finished flag, accurate times). Calendar-only events still get a bar |
| Timeline rows | Gameplay events and event wishes. Genius Invokation TCG and Miliastra Wonderland items are left out |
| Timers column | Resets (daily, weekly, Abyss, Theater, Stygian) plus an "Ending soon" list. Personal timers (resin etc.) stay on the Dashboard |
| Past events | Kept in the database from now on; the timeline shows about 3 weeks back; rows ended over 90 days ago are pruned |
| Events layout | A: timeline and Timers side by side; Done checklist and banner history full width below |
| Bar popup | A: centred modal (native `<dialog>`) with the art as a hero image |
| Banner history | A: grouped by version and phase, character and weapon banners together, your pulls per banner |
| To-farm strip | A: one flat strip, category order |
| Feed approach | 1: fetched inside the calendar part of every sync, stored in a new `event_log` table, merged in `events/view.py` |

Visual-companion mockups (git-ignored): `.superpowers/brainstorm/17327-1795471595/content/` (`events-layout.html`, `event-popup.html`, `banner-history.html`, `inventory.html`).

---

## 2. Feasibility (probed 2026-11-23, public hosts only, no cookie, no UID)

| Need | Finding | Verdict |
|---|---|---|
| Real count of every material | Only the GOOD scan has it. The HoYoLAB calculator reveals `have = need − short` only when short | Best-known count, as decided |
| Event times, rewards, completion | HoYoLAB calendar snapshot (already stored): current events only (7 in the real DB; two had no start/end), `desc` plain text, `reward_list`, `is_finished` | Have it. No images, nothing past or upcoming |
| Event art, text, upcoming wishes | `https://sg-hk4e-api.hoyoverse.com/common/hk4e_global/announcement/api/getAnnList` and `.../getAnnContent` with `game=hk4e&game_biz=hk4e_global&lang=en&bundle_id=hk4e_global&platform=pc&region=<server>&level=60`. Works without `uid`. `getAnnList` groups items by `type_id` (1 = Event, 2 = Game, 26 = Miliastra Wonderland); each item has `ann_id`, `title`, `subtitle`, `banner` (image on `sdk.hoyoverse.com`), `start_time`/`end_time` (the *display* window, not the event's), and `timezone` (server offset, −5 for `os_usa`). `getAnnContent` gives `content` HTML | Available |
| True event times in the feed | The content HTML carries timestamps as `<t class="t_lc">2026/11/24 18:00</t>` (server local time); the first two are start and end. Some events say only "after the Version update" and have one or no tag | Parse; fall back as in §3.2 |
| paimon.moe timeline data | `src/data/timeline.js`: hand-curated, behind (still listing events that ended 2026-11-03), images on paimon.moe | Not used |
| Banner history | `game_banner` from paimon.moe: 108 character, 107 weapon, 7 chronicled; latest start 2026-11-04 (7.2 phase 2 not listed yet). Two character banners of a phase are one row. No banner art | Have it |
| Image proxy | `/api/img/remote` already allows `*.hoyoverse.com` | No change |

---

## 3. Announcement feed (backend)

### 3.1 `backend/app/sync/announcements.py`

The feed is an unofficial API, so it lives in `sync/`.

- `async def fetch_announcements(http, region) -> list[Announcement]`: one `getAnnList` and one `getAnnContent` call with the parameters in §2 and `region` set to the account's server (`os_usa`, `os_euro`, `os_asia`, `os_cht`). Sends no cookie and no UID. Raises `AnnouncementError` on a non-zero `retcode` or a malformed body.
- `parse(ann_list: dict, ann_content: dict, offset_hours: int) -> list[Announcement]` (pure, tested with fixtures):
  - Keep only items in the `type_id == 1` (Event) group.
  - Drop items whose title or subtitle contains "Genius Invokation" (TCG).
  - `kind = "wish"` when the title starts with `Event Wish`, else `"event"`.
  - `name`: the subtitle with surrounding quotes and an `Event Wish` / `Event Wish -` prefix removed (e.g. `Harmonious Abundance`); the title when the subtitle is empty.
  - `start`/`end` (UTC ISO): from the first two `t_lc` tags in the content, read as server-local time and shifted by `offset_hours`. One tag only → it is the end; start comes from the fallback.
  - `image`: the list item's `banner`, else the content item's `banner`, else none.
  - `description`: the content HTML turned into plain paragraphs (block tags become paragraph breaks, other tags dropped, entities decoded, whitespace collapsed). No HTML reaches the frontend.
- `Announcement` dataclass: `ann_id, kind, name, start, end, image, description`.

### 3.2 Times fallback

For an announcement missing a start or end after parsing:

1. Take the missing value from the matched calendar event (§3.4), if any.
2. Otherwise use the announcement's display window (`start_time`/`end_time`, server local, shifted to UTC).

### 3.3 Storage: migration 0011, table `event_log`

| Column | Type | Notes |
|---|---|---|
| `key` | str, PK | `ann:<ann_id>` or `cal:<calendar id>` |
| `kind` | str | `event` or `wish` |
| `name` | str | |
| `start`, `end` | str, nullable | UTC ISO |
| `image` | str, nullable | remote URL |
| `description` | text | plain paragraphs separated by `\n\n` |
| `calendar_id` | int, nullable | matched HoYoLAB calendar event id |
| `first_seen`, `last_seen` | datetime | |

The calendar part of a sync, after saving the calendar snapshot:

1. Calls `fetch_announcements`. A failure is recorded as the run's `calendar.announcements` error (beside the calendar part's own result), and the calendar part still counts as successful.
2. Upserts one row per announcement (`ann:<id>`), with `calendar_id` set from the match in §3.4.
3. Upserts a `cal:<id>` row for each calendar event that has start and end and matched no announcement, so it keeps a past bar after it leaves the calendar. Such a row is deleted when a later announcement matches the same calendar id.
4. Deletes rows whose `end` is more than 90 days before now.

Rows not seen in the latest feed are kept (that is the history).

### 3.4 Matching announcements to the calendar

`normalise(name)`: lowercase, drop quotes and punctuation, collapse spaces. An announcement matches a calendar event when one normalised name contains the other (calendar names are often shorter, e.g. "Stygian Onslaught"). When several match, the one with the closest end time wins. Only `kind="event"` rows match calendar events.

Wishes match `game_banner` rows instead (calendar banner names are generic, e.g. "Character Event Wish"): the wish's pool is `weapon` when the title mentions "Epitome Invocation", `chronicled` when it mentions "Chronicled", else `character`; it matches the `game_banner` row of that pool whose start is within one day of the wish's start (paimon.moe stores both character banners of a phase as one row, so both character wishes of a phase match it). The match only supplies featured items and your pulls.

### 3.5 Merged timeline: `events/view.py`

`timeline_rows(log_rows, calendar, done, banners, pulls, now) -> list[dict]` (`banners`: `game_banner` rows; `pulls`: `pulls_by_banner` keyed by banner key) returns every `event_log` row whose `end` is at or after `now − 21 days` (or which has no end), each as:

`{key, kind, name, start, end, image, description, calendar_id, rewards, primogems, finished, done, ending_soon, items, pulls}`

- For a matched event, the calendar's `start`/`end` override the stored ones, and `rewards`, `primogems`, `finished` come from the calendar; `done = finished or event id ticked in EventDone` (today's rule). Unmatched events have `rewards = []`, `done = false` and no checkbox.
- `ending_soon`: not done and ends within 24 hours (today's rule).
- Wishes: `done` is always false; `items` is the matched `game_banner` row's featured 5★ and 4★ items (as in banner history), `pulls` that banner's entry in `pulls_by_banner`; both `null` when unmatched (e.g. a phase paimon.moe has not listed yet).
- Sorted by start, then end, then name.

`ending_soon_list(rows, now)`: not-done events and all wishes ending within 3 days, soonest first, at most 5.

### 3.6 API changes

`GET /api/events` keeps every current field (the Dashboard still uses `events` and `banners`) and adds:

- `timeline`: the rows from §3.5.
- `ending_soon`: the list from §3.5, each `{key, kind, name, end}`.
- `announcements_error`: the latest run's `calendar.announcements` error or `null`.

`PUT /api/events/{id}/done` is unchanged (calendar event ids).

`GET /api/banners/history?q=&page=` changes shape (the `pool` parameter is removed):

```
{ total_versions, page, page_size: 6,
  versions: [ { version: "7.2",
                phases: [ { start, end, upcoming: bool,
                            banners: [ { key, pool, name, featured_5: [item], featured_4: [item], pulls } ],
                            image: str|null } ] } ] }
```

- Versions sorted newest first. A phase is the set of `game_banner` rows of one version sharing a start date (character, weapon and chronicled together; chronicled banners keep `pool: "chronicled"` so the frontend tags them).
- Banners with no version (standard, beginner) are left out.
- An upcoming phase: `event_log` wish rows that match no `game_banner` row (§3.4) and start after the newest `game_banner` start, grouped by start date, each group becoming a phase with `upcoming: true`, no featured items (paimon.moe has not listed it), and the wish art as `image`. It belongs to the newest version.
- `q` keeps today's behaviour: matches banner name, short name, or a featured item's name; versions with no matching banner are left out, and matching versions show only their matching phases.

---

## 4. Events page (frontend)

### 4.1 Layout

`routes/events/+page.svelte`, top to bottom:

1. Title row with the "as of …" line and any `error` / `announcements_error` warning, as today.
2. A grid: **timeline card** (`1fr`) and **Timers card** (~240px). Below ~1100px viewport width the Timers card moves under the timeline.
3. **Done checklist**, full width.
4. **Banner history**, full width.

The old Live banners panel and Resets panel are removed from this page (wishes are on the timeline; resets move into Timers). The Dashboard is unchanged.

### 4.2 `EventTimeline.svelte` and `lib/timeline.ts`

- Axis: one column per day from `today − 21 days` to the latest known end (at least `today + 14 days`), with day numbers and month names at month starts. Ends far in the future (e.g. a year-long event) are clamped to `today + 60 days` and the bar shows a "→" at its right edge.
- On mount the scroll position puts "today" about a third of the way across. The card scrolls horizontally.
- Lane packing (`packLanes` in `timeline.ts`): rows sorted by start, each placed in the first lane whose last bar ended before it starts; wishes and events share lanes.
- Bar: positioned by start/end; background is the art through `/api/img/remote` with a dark left-to-right fade; name in white; time left on the right in gold, orange under 24 hours; "starts in …" for future bars. Wishes have a thin gold outline. Done or ended bars are greyscale and dimmed. No art (or the image fails to load): a neutral glass gradient.
- Today line: a gold vertical line with a soft glow and a "today" label.
- Each bar is a `<button>` labelled "<name>, <start> to <end>"; Left/Right arrows move focus between bars in time order. Clicking opens the popup.

### 4.3 `EventModal.svelte`

A native `<dialog>` opened with `showModal()`, closed by ✕, Esc or a backdrop click; focus returns to the bar (same pattern as `TeamEditorModal`).

- Hero: the art (~150px tall, cover) with a bottom fade and the name over it; ✕ top right. No art: a gradient hero.
- Pills: "Nov 20 10:00 → Nov 30 03:59" in the browser's local time, a countdown (`Countdown`, warn colour under 24h), and "N primos" when > 0.
- Rewards: icon tiles with counts (calendar rewards), hidden when there are none.
- Wish popup: featured 5★ and 4★ icons, and "You pulled N here · got X" when `pulls` is known.
- Description paragraphs, scrolling inside the dialog when long.
- Footer: "Mark done" / "Undo" for matched events (same optimistic toggle and revert as today); disabled with "Completed in game" when `finished`; absent for wishes and unmatched events.

### 4.4 Timers card

Resets from `resets` (daily, weekly, Abyss, Theater, Stygian) as label + `Countdown`, then an "Ending soon" heading with `ending_soon` entries (countdown in the warn colour); clicking one opens its popup. Empty list: the heading is hidden.

### 4.5 Done checklist

Today's list restyled as a glass card: checkbox, name, an "auto" tag when `finished`, reward icons, primogems, countdown. Header "Done · N left · X primos". Lists the current calendar events (today's `events` field); ended events drop out of the list but stay on the timeline.

### 4.6 `BannerHistory.svelte`

- A search box (debounced 250ms as today).
- Version rows: a gold version label on the left, then one card per phase (two per row; wraps when narrow).
- Phase card: heading "Phase N · Nov 4 – Nov 24" (phase number by start order within the version; "upcoming" tag when `upcoming`). 5★ characters at 54px, a divider, 5★ weapons at 40px, 4★ items at 24px underneath; a small "Chronicled" tag row when a chronicled banner is present. Your pulls: "N pulls" pill, or a gold "N pulls · got X" pill when you pulled a 5★ there. An upcoming phase shows its art as a short image strip instead of icons.
- Loading: the first page on mount; the next page when a sentinel near the bottom scrolls into view (`IntersectionObserver`), with a "Load more" button as fallback. A new search resets to page 1.

---

## 5. Inventory (frontend only)

### 5.1 "To farm" strip

A glass card at the top of the Materials tab titled "To farm · N materials":

- Every material with `to_farm > 0`, in category order (`categories` order) then the server's order within a category.
- Tile: icon, red "−N" pill (`to_farm`), amber "+N" pill when `craftable > 0`, the best-known count (§5.2) underneath, name, and the existing `MaterialPopover` on hover.
- No material short and a successful calculation exists: "Nothing to farm ✓". No calculation yet: the calculation status line instead.
- Hidden while the search box has text (the backpack below shows the matches).

### 5.2 Backpack

Category cards below the strip. Each tile shows one number, the best-known count:

1. `scan` when a GOOD scan is active;
2. otherwise `have` (`need − short`) when the material is short;
3. otherwise "—".

Tiles showing 0 or "—" are faded (~35% opacity). No red, no ✓, no `have/need` text; the popover still lists who needs it and the sources. Without a GOOD scan, a one-line hint under the filter bar reads "Import a GOOD scan to see every count" (the import button is already in the bar when the feature is enabled).

### 5.3 Filters

The chips become "All" and (with a scan) "Owned". "Needed" and "To farm" are removed: the strip replaces them. A stored `gt.inventory.filter` of `needed` or `farm` reads as "All". Search, the calculation status, the Weapons and Artifacts tabs and polling are unchanged.

### 5.4 Code

`materials.ts` gains `backpackView(m)` and `farmView(m)` (both return `TileView`) and `bestKnownCount(m)`; `InventoryFilter` becomes `'all' | 'owned'`. `tileView` stays for the Dashboard's domain and boss cards. `MaterialTile` gets an optional second pill (craft) through `TileView`.

---

## 6. Errors

| Situation | Behaviour |
|---|---|
| Announcement fetch fails (network, `retcode ≠ 0`, bad JSON) | Logged without parameters beyond the endpoint name; stored as `calendar.announcements` error; page shows "⚠ event art update failed: …"; timeline draws from `event_log` and the calendar |
| An announcement has no parseable time and no fallback | Skipped (not stored) |
| Art fails to load | Gradient bar / hero |
| Not connected to HoYoLAB | No sync runs, so no feed; the page shows whatever `event_log` holds, with today's "Connect HoYoLAB" note when empty |
| Region unknown | Feed step skipped |
| Banner history page fails | Toast "Could not load banner history: …" (as today); already loaded versions stay |

---

## 7. Security and data safety

- The feed request carries only fixed parameters plus the server region; no cookie, UID, nickname or email.
- Feed code lives in `backend/app/sync/`.
- Descriptions are converted to plain text on the server; the frontend renders text only (no `{@html}`).
- Art loads at runtime through `/api/img/remote`; test fixtures use placeholder image URLs and trimmed, made-up announcement text. No game art or personal data is committed.
- `event_log` holds only public announcement data and calendar ids.

---

## 8. Testing

Backend (pytest):

- `parse` with trimmed fixtures: event with two time tags; wish (name cleaned, `kind="wish"`); TCG item dropped; Game and Miliastra groups ignored; one tag only; no tags (display-window fallback); entities and block tags in the description.
- Server-time → UTC for each region offset.
- `normalise` and matching (containment both ways, closest end wins, wishes never match events; wish → `game_banner` by pool and start within a day, both character wishes of a phase matching the one row).
- `event_log` upsert, `cal:` row added and later replaced by a matching announcement, 90-day pruning.
- Sync: feed failure leaves the calendar saved and records `calendar.announcements`.
- `timeline_rows` (21-day window, calendar override, done rules, wish items/pulls) and `ending_soon_list`.
- Banner history grouping (phases by start, chronicled kept, no-version banners dropped), upcoming phase from `event_log`, search, paging.
- Migration 0011 up/down.

Frontend (Vitest): `timeline.ts` (axis range, clamping, lane packing, today offset), `bestKnownCount`, `backpackView`, `farmView`, filter fallback.

Playwright (seeded server, workers 1, restoring any state changed):

- Events: bars render (an art bar and a gradient bar), today line present, clicking a bar opens the modal, Mark done toggles and is undone, Esc closes and focus returns, Timers lists resets and ending soon, banner history shows version rows and loads the next page.
- Inventory: strip lists short materials with pills; backpack shows plain counts and "—" without a scan; with a scan shows scan counts; old stored filter falls back to All.

Dev seed (`devseed.py`): demo `event_log` rows (events and a wish, one upcoming, one ended), with placeholder art URLs.

---

## 9. Out of scope

- Teapot wood and furnishing materials (sub-project 10).
- TCG and Miliastra Wonderland items on the timeline.
- Personal timers on the Events page (they stay on the Dashboard); manual timers.
- Banner art for past banners (no source).
- Event history before this feature ships.
- Exploration percentage and double-reward counters from the calendar.
- Any Dashboard change.

---

## 10. Done when

- The Events page shows the art timeline with popups, Timers beside it, the Done checklist and version-grouped banner history, from the merged feed and calendar.
- The Inventory Materials tab shows the "To farm" strip above plain best-known counts, with the two remaining filters.
- Migration 0011 applies cleanly to a copy of the real database.
- pytest, `npm run check`, Vitest, `npm run build` and Playwright all pass.
