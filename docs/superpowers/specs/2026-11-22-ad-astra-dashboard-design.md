# Ad Astra sub-project 3: Dashboard

**Date:** 2026-11-22
**Status:** Design approved in chat 2026-11-22; written spec awaiting the user's review
**Depends on:** sub-project 1 (Foundation) and sub-project 2 (Traveler per element), both merged (main at bd3d1ed)
**Parent:** `2026-11-22-ad-astra-revision-overview-design.md` (sub-project 3)

## 1. Goal

The Dashboard is a quick look at what the player should do right now, as if they had just opened the game. Everything on it is ordered by how urgent it is. The current page is a grid of equal panels that mixes daily needs (resin, domains) with things that are not daily (pity, profile, resets).

After this sub-project:

- The page is a **wide centre column** (daily, in order of urgency) plus a **side column** (useful but not urgent).
- Build characters have a **user-set priority**. Material counts are **allocated to the highest priority first**. For example, with 14 held, a P1 character needing 20 and a P2 character needing 30 read 14/20 and 0/30. With 32 held they read 20/20 and 12/30.
- Build characters with nothing left to level are listed separately as **completed**, so they are not lost.
- Events the user has not finished are **raised** to the centre column when they end within 3 days.

Success means:
- Opening the page answers, top to bottom: "how much resin and what else is waiting", "is any event about to end", "which domains today and for whom", "which bosses", "who am I building, in what order, and what do they still need".
- Allocation is deterministic and matches the two examples above.
- Every number on the page comes from data the app already fetches. Nothing is a user-entered timer.

## 2. Data sources (checked 2026-11-22)

No live probe was needed. Everything comes from responses the app already fetches, or from the installed genshin.py 1.7.32 models.

| Piece | Source | Status |
|---|---|---|
| Resin, commissions, realm currency, weekly boss discounts | HoYoLAB notes (stored in `live_notes`) | Stored today |
| Commission bonus claimed, realm currency recovery time, max expeditions | genshin.py `Notes.claimed_commission_reward`, `remaining_realm_currency_recovery_time`, `max_expeditions` | In the same notes response; stored by this sub-project |
| Parametric Transformer | genshin.py `Notes.remaining_transformer_recovery_time` (optional) | In the same notes response; stored by this sub-project |
| Expeditions | notes: `character_icon`, `status`, `remaining_time` | Stored today. **No reward or resource information exists** in any API |
| Forge, cooking and other timers | none | **Not available.** The user decided not to add manual timers |
| Greeting name | new local `display_name` setting | The HoYoLAB nickname is deliberately never stored (identity fields are dropped at sync), and that rule stays. The user decided on a Settings field instead |
| Domains for any weekday | `planner.today.farm_today(data, weekday, index)` | Exists; called once per day |
| Weekly bosses | planner index (category `weekly`) + `weekly_boss_done` | Exists |
| Held counts for allocation | `material_total`: held = need − short + spare (the rule `teams/shortfall.py` already uses) | Exact while short overall; a lower bound when not short, in which case every character is covered anyway |
| Per-character need | `material_gap.need` | Exists |
| Completed builds | `PlannerData.calculated` and no gap rows | Exists |
| Weapon materials | already in the calculator request when a target weapon level is set | Exists |
| Live banners and pity | calendar snapshot banners + wish history (`pulls_by_banner`, `pity_lines`) | Exists |
| Events, end times, done flags | calendar snapshot + `event_done` | Exists |
| Event finished in game | genshin.py calendar `Event.is_finished` | In the calendar response; stored by this sub-project |
| Banner and event artwork | none: the calendar models have no banner or event image | **Not available.** Banners use the featured 5★ item icon. Events use the icon of their top reward |
| Domain location images | genshin-db `filename_image` names return 404 on enka.network and Yatta | **Unresolved.** The spike belongs to sub-project 8; domain cards keep an empty image slot |
| Artifact domains | genshin-db (sub-project 8) | Out of scope; the section's position is reserved |

## 3. Layout

The page has two columns across the full width: a centre column (about 2/3) and a side column (about 1/3). Below about 1100px the side column moves under the centre column. Every block is a Foundation glass panel.

### 3.1 Centre column (top to bottom)

1. **Greeting.**
   - The text is "Good morning", "Good afternoon" or "Good evening", followed by the `display_name` setting, or by "Traveler" when that setting is blank.
   - The time of day is the browser's local time: morning is 05:00–11:59, afternoon 12:00–17:59, evening 18:00–04:59.
2. **Bubbles.** There are four. Each has an icon (a game item icon through `/api/img`, with an original Foundation `Icon` where no game icon name resolves):
   - **Original Resin:** `n/max`, plus "Full in 3h 20m" or "Full".
   - **Commissions:** `n/max`, plus "Bonus claimed" or "Bonus not claimed".
   - **Realm Currency:** `n/max`, plus "Full in …" or "Full".
   - **Expeditions:** for example "3/5 ready". It shows each running expedition's character side icon, dimmed until that expedition has returned. The total is `expeditions_max` when known, otherwise the number of expeditions.
   - When HoYoLAB is not connected, one panel ("Connect HoYoLAB in Settings") replaces the bubbles. When notes have never been fetched, each value shows "—".
3. **Ending soon.** This lists events that are not done and end within 3 days. The 3-day window is a new dashboard constant. The existing 24-hour `ending_soon` flag on event rows, which drives the red styling, is unchanged.
   - Each row shows the top-reward icon, the name and the time left. The time left is red under 1 day.
   - The strip is hidden when no event matches. These events stay in the side column's event list as well.
4. **Domains.**
   - A day picker has Mon–Sun buttons plus a "Today" button. The **day being viewed** and the **actual server day** get two distinct styles; when they are the same day, the viewed style wins.
   - The page opens on the server day.
   - Each domain card shows the domain name, an empty image slot, the materials still to farm (`MaterialTile`, with the popover) and the characters who need them, in priority order.
   - Cards are ordered by the best (lowest) priority among the characters that need their materials, then by name.
   - On Sunday every domain is open. A day with nothing to farm shows "Nothing to farm on ‹day›".
5. **Weekly bosses.**
   - The header shows "Discounts n/max left" when known.
   - Each boss card shows its drops still to farm, the characters who need them in priority order, and the existing done tick. Bosses ticked done sink to the bottom.
   - The cards are ordered like the domain cards.
6. **Artifact domains.** This section is **not rendered** in this sub-project. Sub-project 8 adds it here, between Weekly bosses and Building.
7. **Building**, in priority order.
   - Each card shows a "P1", "P2", … badge, a drag handle and up/down buttons, plus the portrait, name and progress.
   - The card lists **every** material the character still needs to level as `have/need`:
     - `have` is the allocated amount;
     - a `+N craft` hint appears where leftover lower tiers cover part of the gap;
     - items fully covered (have + craft ≥ need) are dimmed with a tick.
   - When every material is covered, the card says "Ready to level up".
   - Characters not yet calculated keep today's "not calculated" label and list no materials.
   - With no Build characters, the section reads "Mark characters as Build on Characters to plan here".
8. **Completed builds.** These are Build characters that are calculated and have no gap rows. They appear as a compact row of portraits, each linking to its character page. The section is hidden when empty.

### 3.2 Side column (top to bottom)

1. **Timers.** Timers come only from HoYoLAB; there are no manual timers. They are sorted by `ready_at`, and "Ready" shows in green when the time has passed. The rows are:
   - Resin full.
   - Realm currency full.
   - Parametric Transformer. This row is hidden when the account does not report one.
   - One row per expedition, with the character's side icon.

   When nothing is stored, the panel reads "Sync to load timers".
2. **Live banners.**
   - Each banner row shows the featured 5★ item icon, the banner name and its end countdown.
   - It also shows the user's pity on that banner pool, for example "62 · guaranteed" (from `pity_lines`).
   - The pity part is omitted when there is no wish history for the pool. When the calendar has never been fetched, the panel reads "Sync to load events".
3. **Events.**
   - Each row shows the top-reward icon, the name and the time left: "4d 6h", or "5h 12m" in red under 1 day.
   - Each event has the existing done toggle. An event finished in game shows as done and its toggle is locked.
   - The abyss, theater and stygian **resets** appear in the same list as rows without a done toggle.
   - Rows sort by done (not-done first), then by end time.

### 3.3 Removed from the Dashboard

These are removed:
- the profile summary;
- the "Building" count/average tile;
- the standalone Pity card (pity moves onto the live banners);
- the separate Resets card (resets move into Events);
- the "Build teams" card (team build views stay on Teams; see sub-project 4).

## 4. Data model (migration 0008)

**`character_goal.priority`**, a nullable integer.
- Effective order of Build characters: `(priority is null, priority, updated_at, character_id)`. Characters without a number come last, in the order they were marked Build.
- Leaving Build clears `priority`, so marking a character Build again puts it at the end.
- Goal changes go through **one shared helper**, which both the Characters goal endpoint (`api/characters.py`) and the Teams Build propagation (`teams/goals.py`) call. That way the rule is applied everywhere.
- Each Traveler element (`10000005*100+element`) has its own goal row, so each element has its own priority.

**`live_notes`** gains four nullable columns:
- `commission_bonus_claimed` (bool);
- `realm_currency_full_at` (datetime; `fetched_at` + recovery time);
- `transformer_ready_at` (datetime). It is null when the account has no transformer; at or before `fetched_at` means ready;
- `expeditions_max` (int).

`sync/hoyolab.py` (`NotesInfo`, `to_notes`) and `sync/persist.py` fill these from the notes response the sync already makes. Unofficial API code stays in `sync/`.

**Calendar snapshot.** `EventInfo` gains `finished: bool`, from `Event.is_finished`. Older snapshots without the field read it as false.
- An event is **done** when it is in `event_done` (ticked by the user) or `finished` is true.
- `PUT /api/events/{id}/done` keeps working for manual ticks. A finished event reports `done: true` whatever its manual flag is.

The migration only adds nullable columns, and its downgrade drops them.

**Setting `display_name`.**
- A string, default `""`, stored in the existing settings store (the local DB only; it is never sent anywhere).
- `GET`/`PUT /api/settings` gain the field. A value is trimmed and capped at 40 characters.
- Settings shows it as a "Display name" text field in the Appearance section.

## 5. Allocation (`backend/app/planner/priority.py`)

These are pure functions over `PlannerData` and a priority-ordered list of Build character ids.

1. **Held counts.** For each material, `held = need − short + spare` from `material_total`.
2. **Exact pass.** Walk the characters in priority order. For each material a character needs (`material_gap.need`), allocate `min(need, remaining)` and subtract it from `remaining`.
3. **Craft pass** (skipped when `LACK_INCLUDES_CRAFTING` is true, in which case `craft` is 0).
   - Walk the characters in priority order again.
   - For each unmet material in a crafting chain (`planner.crafting.chains`), convert leftover lower tiers (3 → 1, tier by tier) to cover the gap.
   - The amount covered becomes `craft` for that character and material, and the lower tiers used are taken out of `remaining`.
4. **Results per character.** Each character gets `materials: [{id, name, icon, rarity, category, need, have, craft}]`. The materials are sorted like `character_shortfall`, by category order, then sort order, then id.
   - `ready = all(have + craft >= need)`.
   - Characters not yet calculated get no materials and `ready = false`.
5. **Completed** means calculated with no gap rows. These characters are not in the build list.

Domain and boss cards keep showing **total** left to farm (`to_farm` from the index), because farming totals do not depend on order. Only the order of the characters shown on them follows priority.

## 6. API

### 6.1 `GET /api/dashboard` (reshaped)

```
{
  connection,                       # as today
  display_name: str,                # the setting; "" when blank
  notes: {resin, resin_max, resin_full_at, commissions_done, commissions_max,
          commission_bonus_claimed, realm_currency, realm_currency_max, realm_currency_full_at,
          expeditions: [{icon, finished, return_at}], expeditions_max, fetched_at} | null,
  timers: [{kind: "resin"|"realm"|"transformer"|"expedition", label, icon, ready_at}],   # sorted by ready_at
  ending_soon: [event row],         # not done, ends within 3 days
  server_weekday: 0..6,
  domains_by_day: {"0": farm_today(...), ..., "6": ...},   # characters in priority order, cards ordered by priority
  weekly_bosses: {discounts_left, discounts_max, bosses},  # characters in priority order
  builds: [{character, priority, progress, calculated, ready, materials}],
  completed: [character],
  live_banners: [banner row + pity],
  events: [event row | reset row],  # reset rows have kind "reset" and no done flag
  calendar_fetched_at,
  gaps                              # as today, for the "calculating…" state and polling
}
```

These fields are dropped: `building`, `build_teams`, `profile_summary`, `pity`, `resets` (merged into `events`), `events_left` and `farm_today` (replaced by `domains_by_day`). Tests that read them are updated.

### 6.2 `PUT /api/priority`

- **Body:** `{"order": [character_id, ...]}`.
- **Errors:** 400 if any id is not currently Build, or if an id appears twice.
- **Behaviour:** the listed ids get priorities 1…n. Build characters not listed follow in their existing effective order (n+1…).
- **Response:** `{builds, completed}`, computed exactly as in the dashboard payload.

## 7. Front end

`frontend/src/routes/+page.svelte` becomes a thin two-column shell. Components live in `frontend/src/lib/dashboard/`:

| Component | Shows |
|---|---|
| `Greeting.svelte` | greeting line |
| `NoteBubbles.svelte` | the four bubbles or the connect panel |
| `EndingSoon.svelte` | the ending-soon strip |
| `DomainDays.svelte` | day picker + domain cards |
| `WeeklyBosses.svelte` | boss cards with the done tick |
| `BuildList.svelte` / `BuildCard.svelte` | priority list, drag/buttons, have/need tiles |
| `CompletedBuilds.svelte` | completed portraits |
| `TimerList.svelte` | side timers |
| `LiveBanners.svelte` | banners with pity |
| `EventList.svelte` | events and resets |

Pure helpers live in `frontend/src/lib/dashboard.ts`, with vitest tests:
- `greetingFor(hour)`;
- `timeLeft(ms)` (format and an "urgent" flag under 24h);
- `dayButtons(viewed, today)` (the two highlight states);
- `moveItem(order, from, to)`.

Existing pieces are reused: `MaterialTile`, `MaterialPopover`, `Countdown`, the 1-second clock, the `sync.version` reload, gap polling (`shouldPoll`), `FilterPill` styling for the day buttons, and `Icon`.

**Reordering:**
- It uses the native HTML5 drag-and-drop API plus up/down buttons for keyboard and touch. No new dependency is added.
- The list reorders optimistically and then calls `PUT /api/priority`. Its response replaces `builds` and `completed`.
- On failure the previous order is restored and a toast shows the error.
- While a save is in flight, the handles and buttons are disabled (the pattern used by the Traveler card).

## 8. Errors and empty states

| Situation | Shown |
|---|---|
| HoYoLAB not connected | Connect panel instead of bubbles; timers show only stored data |
| Notes never fetched | Bubbles show "—"; Timers panel reads "Sync to load timers" |
| Calendar never fetched | Ending soon hidden; Banners and Events read "Sync to load events" |
| No wish history for a pool | Banner row without pity |
| No Build characters | "Mark characters as Build on Characters to plan here"; Completed hidden |
| Gaps calculating / failed | Existing gap status line and polling |
| Day with nothing to farm | "Nothing to farm on ‹day›" |
| Priority save fails | Order rolls back, toast with the error |

## 9. Testing

**Backend (pytest):**
- `priority.py`:
  - The user's examples: with 14 held, P1 gets 14/20 and P2 gets 0/30. With 32 held, P1 gets 20/20 and P2 gets 12/30.
  - Leftover lower tiers craft for P1 before P2.
  - Netted mode gives `craft` = 0.
  - A not-calculated character gets no materials.
  - Two Traveler elements are allocated as separate entries.
- **Priority order:** null priorities last by `updated_at`; leaving Build clears the number through the Characters endpoint and through Teams propagation.
- **Migration 0008:** upgrade and downgrade, with existing rows keeping null values.
- **Notes parsing:** the new fields, including a missing transformer, and persistence of `realm_currency_full_at` and `transformer_ready_at`.
- **Calendar:** `finished` is parsed; an old snapshot without it reads as false; a finished event counts as done and drops out of `ending_soon`.
- **`/api/dashboard`:** the new shape; `domains_by_day` has 7 days with Sunday showing all domains; cards follow priority order; `timers` are sorted.
- **`PUT /api/priority`:** renumbering, 400 for non-Build and duplicate ids, unlisted ids appended, and the response shape.
- **`display_name`:** default blank, trimmed on save, capped at 40 characters.
- Existing tests that read the dropped dashboard fields are updated.

**Dev seed:** add priorities, the new notes fields, a transformer timer, one finished event, one event ending within 3 days, and a material shared by two Build characters, so allocation is visible.

**Frontend:**
- vitest for the `dashboard.ts` helpers.
- New Playwright test `e2e/dashboard.spec.ts`:
  - all sections are present;
  - the day picker switches cards and shows the two highlights;
  - moving a character up with the buttons changes the have/need counts;
  - the ending-soon strip appears;
  - toggling a weekly boss.
- The dashboard checks in `planner.spec.ts` and `wishes.spec.ts` are updated.

The usual gates must pass: pytest, `npm run check`, `npx vitest run`, `npm run build` and Playwright.

## 10. Out of scope

- Artifact domains and domain location images (sub-project 8).
- Banner and event artwork (no API source).
- Manual timers: forge, cooking and the like (user decision: API data only).
- Team build views on the Dashboard (sub-project 4 handles Teams).
- Build recommendations (sub-project 9).

## 11. Hard constraints (unchanged)

- Cookie values live only in the git-ignored `.env` and are never logged, returned or committed.
- Unofficial API code stays in `backend/app/sync/` and `wishes/`.
- Test fixtures use only made-up UIDs (800000001).
- No personal data or game art is committed; images load at runtime through `/api/img`.
- The user's email is never sent to external services.
