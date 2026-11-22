# Phase 5 — Live Battle Chronicle check (2026-11-21)

`python -m app.smoke --chronicle` against the user's account (read-only; the app's `.env` was read in place, no copy; no UID, nickname or cookie recorded here). genshin.py 1.7.32. Every mapper ran without error.

## Calendar (`get_genshin_event_calendar`)

- 3 live banners (two character banners, one weapon banner), 7 events, 2 challenge periods.
- **Banner names are generic** ("Character Event Wish", "Character Event Wish 2", "Weapon Event Wish"); the featured 5★ ids identify them. Banner times map to the Phase 3 windows (e.g. `…T23:00:00Z` start, `…T22:59:00Z` end).
- **Rewards:** primogems always appear as reward id `201`, name `Primogem` (420 / 450 / 920 on the three events that give them). Some rewards have `num = 0` (Hero's Wit, Mora, Mystic Enhancement Ore) — amounts not shown in the calendar. One reward has id `0`, name `Characters`.
- **Events without an end time** exist (`end = None`, e.g. Ley Line Overflow) — kept, sorted last among not-done events.
- **Challenge periods:** only `abyss` and `theater` appear in `challenges`. **Stygian Onslaught appears as an ordinary event**, not as a challenge entry; its current period end is available from `get_stygian_onslaught` (season `end_at`).
- Event ids are small integers (464–470); stable across two calls is assumed (only one run was made).

## Profile (`get_partial_genshin_user`)

- AR, days active and achievements map as expected; no world level in the response (spec §13.1).
- 16 exploration entries with `parent_id == 0`, **including sub-areas** (Dragonspine, The Chasm, Enkanomiya, Chenyu Vale, Sea of Bygone Eras, …) and the regions **in no useful order**.
- Regions without a reputation system report `type == "Reputation"` with **level 0** (Snezhnaya, Nod-Krai, Natlan); Natlan has a separate `natlan_reputation` structure (not mapped).

## Challenges

- **Spiral Abyss:** current cycle not attempted → no run (correct); previous cycle returned with summary and 18 team lineups.
- **Imaginarium Theater:** no runs returned (not attempted / no data on this account), so whether one call returns both periods is still unconfirmed; the `(kind, season)` dedupe covers either case.
- **Stygian Onslaught:** two seasons returned (current and previous), each with difficulty, time used and 3 team lineups. Season ids are large integers (7 digits).

## Consequences for the build

1. Stygian's reset countdown uses the current Stygian `challenge_run` period end when the calendar has no Stygian challenge entry.
2. The Profile shows a reputation level only when it is above 0.
3. Profile regions are ordered by their HoYoLAB id.
