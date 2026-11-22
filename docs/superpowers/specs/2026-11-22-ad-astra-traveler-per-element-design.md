# Ad Astra sub-project 2: Traveler per element

**Date:** 2026-11-22
**Status:** Approved by the user 2026-11-22
**Depends on:** sub-project 1 (Foundation), merged at e80061f
**Parent:** `2026-11-22-ad-astra-revision-overview-design.md` (sub-project 2)

## 1. Goal

Today the Traveler is one character (ids 10000005 and 10000007 folded into 10000005), and the planner skips it ("not planned: Traveler"). The Manekin (10000117 and 10000118, folded into 10000117) is handled the same way.

After this sub-project:

- The Traveler becomes **one plannable character per element**: "Anemo Traveler", "Geo Traveler", "Electro Traveler", "Dendro Traveler", "Hydro Traveler", "Pyro Traveler" and "Cryo Traveler". Each element has its own talents, constellation, Build goal and material plan.
- The **Manekin is removed** as a character (user decision).

Success means:
- A Build goal on any Traveler element produces a correct material gap: that element's talent books and weekly-boss drop.
- The shared level and weapon are counted once, however many elements have goals.
- Existing goals and teams on the old Traveler survive the migration.

## 2. Data sources (probed 2026-11-22)

| Fact | Source | Finding |
|---|---|---|
| Which elements exist | Yatta `api/v2/en/avatar` | 7 variants per body: `10000005-anemo`, `-geo`, `-electro`, `-dendro`, `-hydro`, `-pyro`, `-cryo` (and `10000007-*`). Cryo was released 2026-08. Each variant has name "Traveler", an element and icon `UI_AvatarIcon_PlayerBoy` or `PlayerGirl`. |
| Per-element talents, constellations, costs | Yatta `avatar/10000005-<element>` | Talents, constellations and talent costs differ per element (e.g. weekly drop 113005 for Anemo, 113075 for Cryo). Ascension (level) materials are the same for every element. |
| Current element and talents | HoYoLAB character list and detailed characters (genshin.py 1.7.32) | One Traveler row with the raw body id. `element` is the **current** element only. The detail call returns only the current element's skills and levels. Constellation is the current element's. |
| Calculator | HoYoLAB `avatarSkill/list`, `batch_compute` | The Traveler **requires** `element_attr_id` (1 Pyro, 2 Anemo, 3 Geo, 4 Dendro, 5 Electro, 6 Hydro, 7 Cryo, matching genshin.py `CALCULATOR_ELEMENTS`). Without it the calls fail (-400005 or -500001). With it they work. Skill group ids differ per element and per body (normal attack 730 for the boy, 731 for the girl). The results gave Freedom books for Anemo, Prosperity for Geo and Charity for Cryo. |
| Challenge teams | genshin.py `BaseCharacter` (abyss, theater) | Each character carries an `element` field. |
| Manekin | Yatta, HoYoLAB | One kit whatever the element; it has its own talent materials and no constellations. The calculator rejects it for every request. Dropped (see 1). |

Game rules: **shared** across elements are level/ascension, weapon, friendship and artifacts. **Per element** are talents and constellation.

The live probes were throwaway scripts that read the existing `.env` and printed only structure. Nothing new was sent anywhere.

## 3. Ids and game data

- **Element ids:** `traveler_id(element) = 10000005 * 100 + calc_element`, where `calc_element` is the calculator number above. That gives Pyro 1000000501, Anemo 1000000502, Geo 1000000503, Dendro 1000000504, Electro 1000000505, Hydro 1000000506 and Cryo 1000000507. These ids are never sent to HoYoLAB. They exist only inside Ad Astra.
- New module `backend/app/gamedata/traveler.py` holds:
  - `TRAVELER_ELEMENTS`: element name to calculator number.
  - `traveler_id(element)`, `element_of(cid)` and `is_traveler(cid)`.
  - `BODY_IDS = {"boy": 10000005, "girl": 10000007}`.
- **Yatta import** (`yatta.py`):
  - Each `10000005-<element>` item becomes a `CharacterData` with the element id, name "{Element} Traveler" and slug `{element}-traveler`. Its icon is PlayerBoy or PlayerGirl according to the `traveler_body` setting.
  - The `10000007-*` items are skipped, since they duplicate the boy's.
  - Items `10000117` and `10000118` (Manekin) are skipped.
  - `_ALIASES`, `_FIXED_NAMES` and the Manekin constants go away.
  - Any newly released element appears automatically as long as its name is in `ELEMENTS` and `TRAVELER_ELEMENTS`.
- **`canonical_id(raw, element=None)`:**
  - For 10000005 or 10000007, it returns the element id for `element`. When no element is given, it uses the current element, read from the setting `traveler_current_element`.
  - For 10000117 or 10000118, it returns `None`. Callers drop `None`.
  - Every other id is returned unchanged.
- **Settings** (in the existing `setting` table, written by sync):
  - `traveler_body`: `"boy"` or `"girl"`, from the raw roster id. Defaults to `"girl"` until the first sync.
  - `traveler_current_element`: for example `"Cryo"`.
  - When `traveler_body` changes, game data is refreshed so the icons follow, and the cached talent ids for Traveler elements are cleared.

## 4. Traveler element state (new user-data table)

`traveler_element`:

| Column | Type | Notes |
|---|---|---|
| `element_id` | int PK | 1000000501–1000000507 |
| `seen` | bool | set when a sync has reported this element as current |
| `unlocked` | bool | set by the user |
| `talent_normal`, `talent_skill`, `talent_burst` | int, default 1 | |
| `constellation` | int, default 0 | |
| `source` | str | `sync` or `manual`: who last wrote the talents and constellation |
| `updated_at` | datetime | |

- An element is **owned** when `seen or unlocked` (user decision: "seen or marked unlocked").
- Sync writes a row only for the current element: it sets `seen`, copies talents and constellation, and sets `source=sync`. Rows for other elements are never touched by sync.
- The user can edit talents and constellation for any element except the current one. When the user next switches to an edited element in game and syncs, the synced values replace the manual ones, because they are the real game data.

## 5. Sync

`backend/app/sync/` stays the only HoYoLAB code. Changes:

- **Roster** (`to_roster_entry`, `save_roster`):
  - The Traveler entry resolves to `traveler_id(current element)`. Sync records `traveler_body` and `traveler_current_element`, and upserts that element's `traveler_element` row.
  - Manekin entries are dropped.
  - **Fan-out:** every other owned element gets an `owned_character` row. It takes the shared fields from the synced Traveler: level, friendship, weapon, `stats` and artifacts (copied when details are saved). It takes talents and constellation from `traveler_element`.
  - Those element ids are added to `seen`, so the delete of characters no longer owned keeps them.
  - Removing an owned element (unticking "unlocked" on a never-seen element) deletes its `owned_character` row straight away.
- **Details:**
  - Details are requested with the raw body id, as today.
  - The result maps to the current element.
  - Artifacts and stats are then copied to the other owned element rows.
- **Challenge teams** (`chronicle.py`): a Traveler maps through `canonical_id(raw, c.element or None)`. Manekin members are dropped from the team list.
- **Banners and wishes:** no change, since the Traveler and the Manekin are never wished for.

## 6. Planner

- **Talent ids:**
  - `get_talent_ids` gains an optional `element` argument.
  - For a Traveler element id it calls `avatarSkill/list` with `avatar_id` = the body id and `element_attr_id`.
  - The results are cached under the element id, as now.
- **Calculator request:**
  - `GapCharacter` gains `element_attr_id: int | None`.
  - `build_batch_body` sends `avatar_id` = the body id plus `element_attr_id` for Traveler elements.
  - `to_gap_result` still maps the results back by position to Ad Astra's ids.
- **Shared level and weapon counted once** (`requests.py`):
  - Among the Traveler element Build goals that have work, one **carrier** is chosen: the current element if it has a goal, else the lowest element id.
  - The carrier sends the **highest** target level across those goals.
  - The carrier also sends the weapon. That is the carrier's own planned weapon if it has one, else the first planned weapon among the other elements, else the equipped one. The weapon target level is the highest across those goals.
  - The other elements send only their talents: `avatar_level_target` equals the current level, and they send no weapon.
  - An element whose only work was level or weapon sends nothing.
- `UNSUPPORTED` is removed. The skipped list no longer names the Traveler, and the frontend test strings that use "Traveler" as the example are updated.
- The "has work" and snapshot logic are unchanged.

## 7. GOOD import

`KeyIndex.character`:

- The keys `TravelerAnemo`, `TravelerGeo`, `TravelerElectro`, `TravelerDendro`, `TravelerHydro`, `TravelerPyro` and `TravelerCryo` map to their element ids.
- A bare `Traveler` key maps to the current element.
- `Manekin` and `Manekina` return `None`. The weapon or artifact is kept as unequipped, and the key is added to `unmatched` as today.

## 8. Migration (Alembic `0007_traveler_elements`)

1. Create `traveler_element`.
2. Determine the current element from `owned_character` row 10000005's `element`. If there is no such row, or its element is not a Traveler element, use Anemo. Call the result `E`.
3. Seed `traveler_element` for `E` with `seen=1`, `unlocked=0`, `source=sync`, and talents and constellation from the old row (defaults when the row is absent). Write the `traveler_current_element` setting. Write `traveler_body` from the old row's `icon`: `UI_AvatarIcon_PlayerBoy` means boy, anything else means girl.
4. Re-point 10000005 to `traveler_id(E)` in:
   - `character_goal`
   - `team_member` (no duplicate is possible, since a team held only one Traveler)
   - `good_weapon.character_id` and `good_artifact.character_id`
   - the id lists in `challenge_run.teams` (JSON)
5. Delete the Manekin (10000117) from:
   - `character_goal`
   - `team_member` (then close the gaps so the remaining slots stay contiguous from 0)
   - `owned_character`, `owned_artifact` and `material_gap`
   - `good_weapon` and `good_artifact`: set `character_id` to null and keep the rows
   - `challenge_run.teams`
6. Delete the old 10000005 rows from `owned_character`, `owned_artifact` and `material_gap`, and delete the `game_character` rows 10000005 and 10000117. Clear the cached talent ids for 10000005 and the game-data fetched marker, so the next start refreshes the character list. The next sync rebuilds the owned Traveler rows.
7. Downgrade: map every element id back to 10000005, keeping the current element's goal when several exist, and drop `traveler_element`. Manekin data is not restored. The downgrade docstring says so.

Before migrating, the existing startup backup (`backups/`) covers recovery.

## 9. UI (minimal; sub-projects 4 and 5 restyle)

- **Characters list:** the seven Traveler elements behave like any character. Unowned elements follow the existing rule for unowned characters, and sub-project 4 later greys them out.
- **Character detail** for a Traveler element gains a small "Traveler element" card with:
  - an **Unlocked** toggle, shown checked and disabled when the element has been seen by sync;
  - number inputs for normal, skill and burst talents (1–10) and for constellation (0–6). They are disabled for the current element, with the hint "From HoYoLAB: current element".
  - Saving calls the new endpoint `PUT /api/traveler/{element_id}`, which validates the ranges and rejects the current element with 409. The change then refreshes owned rows and the gap like any goal change does.
- No other pages change. The team picker and goals already work with whatever character ids the API returns.

## 10. Error handling

- An unknown Traveler element from HoYoLAB (a future element not yet in `TRAVELER_ELEMENTS`): sync logs the element name, keeps the previous current element, and skips the Traveler for that run. The rest of the sync carries on.
- A calculator error for a Traveler element is reported like any other character's gap failure.
- `PUT /api/traveler/{id}` on a non-Traveler id returns 404. Out-of-range values return 422.

## 11. Testing

Fixtures use only the made-up UID 800000001 and a synthetic roster.

- Unit tests:
  - `traveler_id`, `element_of` and `canonical_id`, with and without an element, and for Manekin ids.
  - Yatta parsing of a trimmed fixture: 7 elements, no Manekin, body icon.
  - `save_roster` fan-out: shared fields copied, per-element talents kept, manual values overwritten only for the current element.
  - Planner carrier logic: level counted once and taken as the highest target, weapon sent once, an element with only level work dropped.
  - `build_batch_body` includes `element_attr_id` and the body id.
  - GOOD keys.
- Migration test: seed a database at 0006 with a Traveler goal, a team, GOOD rows, a challenge run and Manekin rows. Upgrade, then assert the remapped ids and the contiguous slots.
- API tests for `PUT /api/traveler/{id}`.
- Playwright: open the Cryo Traveler and toggle Unlocked on another element. It then appears as owned. `devseed.py` has no Traveler today. It gains a Cryo Traveler owned row and a `traveler_element` row.
- About 11 existing backend test files and the Yatta fixture assume the folded ids 10000005 and 10000117. They are updated to the element ids, or the Manekin is removed from them.
- The ids fit in a 32-bit integer (the largest is 1000000507), so SQLite, JSON and TypeScript `number` all handle them.

## 12. Out of scope

- Planning the Manekin.
- Per-element artifact builds (artifacts stay shared, as in game).
- Element theming and the visual rework of the Character page (sub-project 5) and of the Characters overview (sub-project 4).
