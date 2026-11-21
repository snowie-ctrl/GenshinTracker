# Phase 3 — live wish findings

**Run:** 2026-11-20 (research), 2026-11-21 (live run with the user's game, on a copy of their data).

1. Wish link found / records fetched / UID matches .env: yes / 1478 / yes. While the game runs, the cache must be read with delete sharing (fixed in 0d2f666).
2. 400-type records returned by the 301/400 queries: yes (301: 474, 400: 730).
3. paimon.moe workbook sheet names, header rows, data rows: not checked. The user had paimon.moe's data backup (.json), so backup import was added (5f3f8fc); all 1478 backup pulls mapped to game data.
4. Per-pool pity vs. the user's in-game count: the app matches the check script (character 38, weapon 0, standard 47, beginner 20); the user's in-game confirmation is pending.
5. Id format (19 digits; `9` as 11th digit count): all 19 digits; 0 with `9` as the 11th digit.
6. Capturing Radiance: RADIANCE_LIKELY_AT = None, sources:
   - https://news.bittopup.com/news/capturing-radiance-50-50-22.5-double-loss-explained
   - https://buffget.com/news/genshin-impact-60-capturing-radiance-5050-guide
   - https://genshintactics.com/wish-simulator/
   - https://sportskeeda.com/esports/genshin-impact-capturing-radiance-guide-boosted-5-star-drop-rate-characters-explained

   Summary: all sources agree the mechanic lifts the overall featured rate to about 55% and that a long enough streak of lost 50/50s guarantees a win. They disagree on when the guarantee applies (after 2 or after 3 consecutive losses) and on the intermediate chances (about 10%, 33%, 55% or 75%), and none cites a datamine or official figure beyond the guarantee. Because the threshold is not settled, no single integer can be chosen, so the value stays None.
7. Round trip: game import added 1478; backup upload added 0 (1478 skipped); UIGF export (1478 pulls, v4.0) re-imported added 0; a second game import added 0. Banner refresh: 224 banners, 0 unmatched items. No 5★ outcome is Unknown.
