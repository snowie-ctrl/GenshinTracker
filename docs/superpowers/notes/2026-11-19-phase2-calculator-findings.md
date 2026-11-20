# Phase 2 — live calculator findings

**Run:** 2026-11-20, `python -m app.smoke --gaps` plus one full phase 2 sync, against the user's real account using a copy of `.env` and `data/tracker.db` inside the phase 2 worktree (the main checkout was not touched). This note records counts and material names only; it holds no UID, nickname or cookie data.

**Inputs:** 6 Build characters. Traveler was skipped by design, and one was already at every target. That left 4 with work: 2 owned at level 80 (one with its equipped weapon going 80→90, one with a planned 4★ catalyst going 1→90) and 2 not owned (pre-farming, 1→90).

## Checks

0. **Talent ids** — `avatarSkill/list` works. The normal/skill/burst group ids were returned for all 4 characters, e.g. `(14031, 14032, 14039)`.
1. **Crafting in `lack_num`: not netted.** Guide to Gold showed short 11 while 47 Teachings of Gold were spare (enough to craft 15 Guides). HoYoLAB's short does not account for crafting, so `LACK_INCLUDES_CRAFTING = False` stays. The planner's rollup then gives Guide to Gold craft 11 / farm 0, and Philosophies of Gold craft 1 / farm 22.
2. **Character limit** — 4 characters in one request returned 4 per-character results. No limit was hit at this size.
3. **Weapons work.** The planned Favonius Codex (1→90) produced the Decarabian chain (Tile 3, Debris 9, Fragment 9, Scattered Piece 4). The equipped 5★ sword (80→90) produced Sacred Dewdrop materials. Planned weapons stay in phase 2.
4. **Ascension at caps: counted as not ascended.** Both level-80 characters' needs include the 80→90 ascension (6 gemstones each). A character that is already ascended at 80 is over-counted by one ascension phase. This is documented in the README.
5. **`available_material`** lists spare counts per item (`num`), e.g. Shivada Jade Sliver 82, Teachings of Gold 47. These feed `material_total.spare` as designed.
6. **Order** — per-character results match the request order. Each character's first materials fit that character, and the two pre-farming characters have identical level-1→90 needs.

**Request body:** top-level `uid` and `region` (no per-item copies) produced `has_user_info = true`.

**Catalogue:** all 49 material ids in the totals exist in the Yatta catalogue (523 materials downloaded).
