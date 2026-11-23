# Ad Astra Sub-project 4 — Characters Overview and Teams

**Date:** 2026-11-23
**Status:** Approved 2026-11-23
**Frame:** `2026-11-22-ad-astra-revision-overview-design.md` (sub-project 4 of 10). Builds on Foundation (`2026-11-22-ad-astra-foundation-design.md`), Traveler per element (`2026-11-22-ad-astra-traveler-per-element-design.md`) and Dashboard (`2026-11-22-ad-astra-dashboard-design.md`). Replaces the page parts of Phase 4 Teams (`2026-11-21-phase4-teams-design.md` §7.2–7.4) and changes its goal rule (§4: teams now also lower goals).
**Scope:** Restyle the Characters overview (small/large tiles, sort toggles, greyed unowned characters, full width) and redesign Teams (slanted character ribbons with splash art, team info section, popup editor, coloured default tags, Build switch that both raises and lowers members' goals, shortfall drawer).

---

## 1. Decisions made with the user

| Topic | Decision |
|---|---|
| Build switch off | Every member still on Build goes to **None**, except members also in another team that still has Build ("skip shared"). Characters the user set to Build by hand are un-built too |
| Delete / remove member | Deleting a Build team, or removing a member from it, un-builds under the same rule |
| Unowned characters | Grey unless owned, everywhere: Wanted and Unobtained alike. Owned tiles show level, constellation and talents |
| Ribbon angle | 18° from vertical (mockup option B), not 30° |
| Ribbon art | The full wish splash (`UI_Gacha_AvatarImg_*`) cropped to the ribbon, scaled to its height (crop A). The thin `UI_Gacha_AvatarIcon_*` strip did not fill the ribbon |
| Clipping | Text and icons must not touch or cross a ribbon's slanted edge; the team info section must not sit under the fourth ribbon |
| Small tile | Rarity background (gold / purple), element icon in the corner |
| Large tile | Wide card: big icon on the rarity background, details beside it |
| Default tags | Abyss, Theater, Nuke, AoE, Boss, Exploration, Main, Fun, coloured (plus the existing Build) |
| Team shortfall | A drawer under the team row, opened from the info section |
| Team editor | A popup over Teams; stacked layout (team on top, picker below) |
| Sorting | Three combinable toggles (A–Z, Rarity, Level) as stacked sort keys |
| Build storage | Approach A: Build stays the built-in tag; the switch is its face. No schema change for Build |

---

## 2. Feasibility (probed 2026-11-23, public hosts only)

| Need | Finding |
|---|---|
| Rarity background baked into icons? | No. `UI_AvatarIcon_*` from enka.network is 256×256 with a transparent background; the app tries enka first. Backgrounds can be drawn behind icons |
| Splash art | `UI_Gacha_AvatarImg_*` (2048×1024, transparent around the effects) resolves on enka.network for all 124 distinct character icons in the catalogue, including `PlayerGirl`/`PlayerBoy` for the Traveler. `game_character.splash` already stores the name and the characters payload already returns it |
| Artifact set icons | `game_artifact_set.icon` = `UI_RelicIcon_<setid>_4` (63 sets), resolves on enka.network. The game has one icon per set; there is no separate 2pc/4pc art, so piece counts are shown as a badge |
| Crowned talents | Talent levels come from the calculator's `level_current` (base level), so crowned = 10 |
| Weapon, level, constellation | Already in `owned_character` and the characters payload |

---

## 3. Goal rules for teams (backend)

All rules live in `backend/app/teams/goals.py`, the only place teams change goals. Every change goes through `app.planner.order.apply_goal`, so Build priority stays right (entering Build appends to the order; leaving Build clears the number).

| Event | Effect |
|---|---|
| A team gains Build (popup save or the row switch) | `raise_to_build` on all members (unchanged: None/Want → Build; stored targets restored, else defaults) |
| A member is added to a team that has Build | `raise_to_build` on that member (unchanged) |
| A team loses Build | `lower_from_build` on all members |
| A member is removed from a team that keeps Build | `lower_from_build` on that member |
| A team that has Build is deleted | `lower_from_build` on all its members |
| A goal changes on Characters or the Dashboard | No team changes; a Build team flags that member **Not building** with **Build again** (unchanged) |

`lower_from_build(session, character_ids, exclude_team_id) -> list[int]`:

- For each id whose goal is `build`: if any team **other than** `exclude_team_id` that has the Build tag still lists the character, keep it. Otherwise `apply_goal(row, "none")`.
- Goals already `none` or `want` are untouched. Stored targets are kept, so a later raise restores them.
- Returns the ids it changed. Runs after the team write in the same transaction, so "other teams" reflects the saved state.

One save may both raise and lower (for example swapping a member of a Build team). Both lists come back from the API: `raised: [ids]`, `lowered: [ids]`. When either is non-empty the API schedules the existing debounced gaps-only recalculation.

---

## 4. API

| Method & path | Change |
|---|---|
| `GET /api/characters` | Each character gains `release_at` (ISO date; `null` for a character missing from the game data, which sorts last) for the newest-first order |
| `GET /api/teams`, `GET /api/teams/{id}` | Each member gains `constellation`, `splash`, and `artifact_sets: [{name, icon, pieces}]`. `artifact_line` stays (used as tooltip text) |
| `POST /api/teams`, `PUT /api/teams/{id}` | Response gains `lowered` next to `raised` |
| `DELETE /api/teams/{id}` | Response gains `lowered: [ids]` next to its current fields, and schedules the gaps recalculation when it is non-empty |
| `PUT /api/teams/{id}/build` | **New.** Body `{on: bool}`. Adds or removes the Build tag and applies §3. Returns the team plus `raised` and `lowered`. Setting the state the team already has changes nothing and returns empty lists. Unknown team → `404` |
| `POST /api/tags`, `PUT /api/tags/{id}` | Accept the two new palette colours (§7) |

`artifact_sets` (in `teams/artifacts.py`, next to `set_line`): count pieces per set name from `owned_artifact`. A set with 4 or more pieces → one entry with `pieces: 4`. Otherwise every set with 2 or more pieces, most pieces first, then by name → entries with `pieces: 2`. `icon` comes from `game_artifact_set.icon` matched by exact name; no match → `icon: null` (the name still shows as a tooltip). Same thresholds as `set_line`, so the two never disagree.

---

## 5. Characters page (`/characters`)

### 5.1 Layout

- The page opts out of the 1600px cap and uses the full content width with 24px gutters.
- The four collapsible sections stay: Actively building, Obtained, Wanted, Unobtained.
- Under the toolbar, the Team tag row stays (TagChip, now in the new tag colours).

### 5.2 Toolbar: `CharacterFilterBar`

A shared component, also used by the team editor's picker:

- Search box; element pills (element colour plus `UI_Buff_Element_*` icon); weapon pills (grey); rarity pills (5★ gold, 4★ purple). Foundation's `FilterPill` behaviour is unchanged: outlined in its colour when off, filled when on.
- Sort toggles **A–Z · Rarity · Level** (gold `FilterPill`s).
- On the Characters page only: a **Small / Large** tile switch.
- Props: the filters object, the sort object, and optionally the tile size. Each is bound, so the parent owns the state.

### 5.3 Sorting

Pure helper `sortCharacters(chars, {az, rarity, level})` in `status.ts`:

1. Rarity on: higher rarity first.
2. Level on: higher level first; unowned characters count as level 0.
3. A–Z on: name ascending. A–Z off: newest `release_at` first, then name.

- The same order applies in every section. Building no longer sorts by progress, since the Dashboard owns Build priority.
- Default: A–Z and Rarity on, Level off; small tiles.
- Sort and tile size are stored in `localStorage` under `aa.characterView`. Every read and write is wrapped in try/catch, and the defaults apply when storage is blocked or the data is corrupt.

### 5.4 Tiles: `CharacterTile` (replaces `CharacterCard`)

Prop `size: 'small' | 'large'`.

- **Small (104px wide):**
  - Icon on the rarity gradient (`--r5` / `--r4` / `--r0`), with the element icon at 18px in the top-left corner.
  - Below: the name, then one line. Building: the progress bar (with the existing tooltip). Otherwise owned: "Lv 90 · C1". Otherwise: "Not owned".
- **Large (about 330×150):**
  - A 150px icon on the rarity gradient.
  - Beside it: element icon and name; stars; "Lv 90 · C1"; "Talents 10/9/10" with level-10 values in gold; weapon icon with "Lv 90 R1"; the progress bar when building.
  - Unowned: "Not owned", plus "· Wanted" when the goal is Want.
- **Unowned (Wanted or Unobtained), both sizes:**
  - Grey background, greyscale art at 50% opacity, greyscale element icon.
- **Both sizes:**
  - Hovering or focusing shows the goal switch (unchanged).
  - Building tiles keep the gold outline.
  - The tile links to `/characters/<slug>`.
- Helper `talentParts(talents) -> [{value, crowned}]` (crowned when value ≥ 10) is shared with the team ribbons.

---

## 6. Teams page (`/teams`)

### 6.1 Header

**New team**, **Manage tags** (existing panel, new palette), and the tag filter chips All · each tag · Untagged (unchanged, still stored in `localStorage`). The page uses the full width.

### 6.2 Team row: `TeamRow`

A glass panel about 330px tall. A CSS grid of four ribbon columns followed by the info section (`repeat(4, 1fr) 1.15fr`).

### 6.3 Ribbon: `TeamRibbon`

- **Shape:** a parallelogram slanted 18° from vertical, top leaning right. The outer element uses `skewX(-18deg)`; its contents are counter-skewed so art and text stand upright.
- **Art:** the member's `splash`, as a background image on a counter-skewed layer wider than the ribbon. Sized `auto 125%` (scaled to the ribbon height), positioned `center 20%`. Behind it sits a gradient tinted with the element colour, so a missing image (the `/api/img` transparent placeholder) still looks intentional.
- **Info at the bottom,** on a dark fade:
  - element icon, name and "C1"
  - "Lv 90 · 10/9/10", crowned values in gold
  - weapon icon with "Lv 90 R1"
  - artifact set icons (24px), each with a piece badge (4 or 2)
  - the role note in italics
  - the **Not building** badge with **Build again**, or **Not calculated**, when they apply
- **No clipping:** the info block's left padding is at least `tan(18°) × block height` plus 10px. Pure helper `slantInset(heightPx, deg = 18)` returns it, and the block's height is fixed so the inset is known. Nothing in the block may extend past that inset or the right edge.
- **Unowned member:** greyscale, darkened art; greyscale element icon; a "Not owned" badge; no level, talents, weapon or artifacts.
- **Placeholder member** (unknown id after a patch): no art, "Unknown character <id>".
- **Empty slot:** a dashed slanted outline with "+". Clicking it opens the editor.

### 6.4 Info section: `TeamInfo`

- **Left padding:** at least `slantInset(row height)` (about 0.33 × row height) plus 12px, so nothing sits under the fourth ribbon's slant.
- **Contents:**
  - the team name
  - a **Build switch** (`role="switch"`, `aria-checked`)
  - tag chips
  - notes, clamped to 3 lines
  - the shortfall summary, which reads:
    - "**N materials short ▸**" (team progress % beside it)
    - "Ready ✓" when nothing is short and all Build members are calculated
    - "Updating…" while gaps are stale or pending
    - "Shortfall appears after the next sync" when gaps were never computed
    - "Connect HoYoLAB to calculate" when not connected
    - nothing when the team has no Build members
- **The Build switch:**
  - Switching **on** calls `PUT /api/teams/{id}/build {on: true}` straight away.
  - Switching **off** first computes `willLower` (§6.6). If anyone would be moved off, it asks "Turn off Build? This moves X, Y off Build." Then it calls the endpoint.
  - The switch updates at once and reverts with an error toast on failure.
  - A success toast reads "Raised N to Build" or "Moved N off Build", and the list reloads.

### 6.5 Interaction

- Clicking the row (ribbons or info section) opens the editor for that team. The switch, the shortfall link, the arrows and Build again do their own action and do not open it.
- **Reordering:** ▲ and ▼ buttons appear at the row's right edge on hover and on keyboard focus within the row. Drag-to-reorder is removed. Reordering is off while a tag filter is active, with the existing hint.
- **Shortfall drawer:** "N materials short ▸" toggles a section under the row with the existing `MaterialTile`s (to farm, craft hint, shared mark) and status messages. Open/closed is per team and not stored.
- **Narrow windows:** below about 1100px wide the info section moves under the four ribbons (single column) and its slant padding no longer applies.
- **Anchors:** each row keeps `id="team-<id>"`, so the character detail page's "In teams" links still land on the row.

### 6.6 Preview helper

Pure helper `willLower(teams, teamId, draft: {memberIds, hasBuild} | null) -> names` in `teams.ts` mirrors §3.

- `draft = null` means delete.
- It returns the members that would leave Build: currently Build, no longer covered by this team (it lost Build, they were removed, or it was deleted), and not in another team that has Build.
- It sits beside the existing `willRaise`.

---

## 7. Popup team editor: `TeamEditorModal`

### 7.1 Opening

- **New team** opens `/teams?edit=new`; clicking a row opens `/teams?edit=<id>`. The modal follows the query parameter, so back closes it and a reload reopens it.
- `/teams/new` and `/teams/[id]` become redirects to those URLs.
- The modal covers about 90% of the window over a dimmed page. Focus is trapped inside it and returns to the row on close.

### 7.2 Layout (stacked)

1. **Name** field, **Build switch**, and ✕.
2. **Tags:** every tag as a clickable `TagChip` (outlined when off, filled when on); "+ new tag" adds a typed name, and a case-insensitive match reuses the existing tag. Beside them, **Notes** (up to 2000 characters).
3. **Four slots:**
   - Each slot shows the member's splash (same crop as the ribbon, unslanted; greyed and marked "Not owned" if unowned), the name, a role field (up to 40 characters) and ✕.
   - Slots reorder by drag, with ◀ ▶ buttons for keyboard use. Empty slots are dashed.
4. **Previews:** "Saving raises A, B to Build" (`willRaise`) and "Saving moves C off Build" (`willLower`, using the teams list the page already has).
5. **Picker:**
   - `CharacterFilterBar` (no tile-size switch) and small `CharacterTile`s.
   - Owned characters in colour, others grey. Current members are outlined in gold and cannot be added again.
   - Clicking a tile fills the first free slot. With four members the picker is disabled, with a hint.
   - The picker's sort starts from the Characters page's saved sort.
6. **Footer:** **Delete team** (existing teams only), **Cancel**, **Save**.

### 7.3 Behaviour

- **Save:** one `POST`/`PUT`. On success the modal closes, the list reloads, and a toast reads "Saved", plus "· Raised N to Build" and/or "· Moved N off Build".
- **Delete:** a confirmation that names anyone moving off Build. On success the modal closes, the list reloads, and a toast appears.
- **Errors:**
  - Validation errors show next to their field (existing `teamErrorField` mapping); other errors show as a toast. The form keeps its contents.
  - A 404 on open shows "This team no longer exists" with Close.
- **Unsaved changes:** Cancel, ✕, Esc, a click on the backdrop, or navigating away asks "Discard changes?" when the form is dirty.
- The existing `TeamEditor.svelte` logic (load, validation, dirty tracking, slot helpers) moves into the modal; the field rules and messages are unchanged.

---

## 8. Tags

- **Palette:** gains `navy` (`#2a3f8f`) and `gold` (`#a9842c`). Updated in `store.TAG_COLORS`, `teams.ts` `TAG_COLORS`/`TAG_HEX` and the Manage tags colour picker. Auto-assigned colours for new tags keep cycling through the palette.
- **Migration `0009_default_tags`** adds, when no tag with the same name exists (case-insensitive on `name_key`):

  | Tag | Colour |
  |---|---|
  | Abyss | navy |
  | Theater | purple |
  | Nuke | red |
  | AoE | yellow |
  | Boss | gold |
  | Exploration | green |
  | Main | teal |
  | Fun | pink |

  - Existing tags with these names are left as they are, colour included.
  - The defaults are ordinary tags (`builtin = false`), so they can be renamed, recoloured or deleted.
  - **Downgrade:** deletes only default-named tags that are on no team.
- **Dev seed:** stops inserting tag id 2 "abyss" and links its demo team to the migration's **Abyss** tag looked up by name. Dev-seed teams use made-up data only.

---

## 9. Errors

| Situation | Behaviour |
|---|---|
| Validation (members, names, roles, notes, unknown ids) | `422` with a field message (unchanged) |
| Tag name taken; rename or delete Build | `409` (unchanged) |
| Team or tag not found | `404`; the modal shows "This team no longer exists" |
| Build switch on an unknown team | `404`; the switch reverts with a toast |
| Build switch to the state it already has | No change; empty `raised` and `lowered` |
| Any write fails | One transaction: members, tags, new tags, raises and lowerings apply together or not at all |
| Reorder lists a missing or extra id | `422`; the page reverts (unchanged) |
| Splash or set icon missing | Element gradient behind the art; the set's name as a tooltip |
| Not connected / gaps never computed / stale | Shortfall summary messages as in §6.4 |

---

## 10. Security and data safety

- No new network access and no new secrets. Images still load at runtime through `/api/img` from enka.network and Yatta; nothing is committed.
- The secret-leakage test covers `PUT /api/teams/{id}/build`.
- Fixtures and the dev seed use made-up data only (UID 800000001).
- The planning mockups live in the git-ignored `.superpowers/` folder.

---

## 11. Testing

### Backend (pytest)

- `lower_from_build`:
  - Build → None.
  - Kept when another Build team lists the member; not kept by a team without Build.
  - Want and None untouched.
  - Priority cleared.
  - Targets kept and restored by a later raise.
  - Returns the changed ids.
- Triggers:
  - Build off un-builds members; removing a member from a Build team un-builds that member; deleting a Build team un-builds its members.
  - A swap both raises and lowers.
  - Teams without Build never lower anything.
  - Gaps are scheduled only when something changed.
- `PUT /api/teams/{id}/build`: on, off, no-op, 404, and `raised`/`lowered` in the response.
- `artifact_sets`: 4pc, 4+1, 2+2, 2+2+1, none, unknown set name (null icon), and agreement with `set_line`.
- Payloads: members include `constellation` and `splash`; characters include `release_at`; `DELETE` returns `lowered`.
- Migration 0009: adds the defaults; skips existing names case-insensitively and keeps their colours; the downgrade keeps in-use tags.
- Palette: `navy` and `gold` accepted on create and update.
- Secret-leakage test extended.

### Frontend

- `svelte-check` with no errors.
- **Vitest:**
  - `sortCharacters`: every toggle combination, unowned as level 0, newest first when A–Z is off.
  - `willLower`: toggle off, remove, delete, shared-team exception, no Build.
  - Existing `willRaise` still passes.
  - `talentParts`, `slantInset`.
  - View-preference load/save, including blocked storage.
- **Playwright** (seeded server; each spec restores what it changes):
  - `teams.spec.ts`, rewritten for the popup:
    - Create a team from the picker, switch Build on, and see the raise toast; the member appears under Actively building on Characters.
    - Switch Build off from the row, confirm, see the moved-off toast, and the member leaves Actively building.
    - Open the shortfall drawer.
    - Reorder with the hover arrows.
    - Filter by tag.
    - `/teams/new` redirects to the popup.
    - An unowned member renders greyed with "Not owned".
  - `characters.spec.ts`: switch to large tiles; the sort toggles change the order; an unowned tile is greyed; the choice survives a reload.
  - `shell.spec.ts`: references to the old editor routes are updated.

---

## 12. Out of scope

- Team, rotation and role recommendations (sub-project 9).
- The character detail page (sub-project 5).
- Per-character splash offsets. Add them only if real characters crop badly in use.
- Drag-to-reorder for teams (replaced by the hover arrows).
- Element resonance or other derived team stats.

---

## 13. Done when

1. The Characters page switches between small and large tiles, sorts with the three toggles, greys every unowned character, and uses the full width.
2. Teams show as rows of 18° splash ribbons with level, talents, weapon, artifact set icons and role, plus an info section that never sits under a ribbon.
3. Turning a team's Build switch on raises its members. Turning it off, removing a member, or deleting the team moves members off Build, unless another Build team still has them.
4. Teams are created and edited in a popup; the old editor URLs redirect to it.
5. The default tags exist in their colours; the shortfall opens as a drawer under its team.
6. All tests pass; the repository contains no cookie values, UID, nickname, game art or personal data.
