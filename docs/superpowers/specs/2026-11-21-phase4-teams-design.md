# Phase 4 — Teams: Design

**Date:** 2026-11-21
**Status:** Approved 2026-11-21
**Parent:** [Overview design](2026-11-19-genshintracker-overview-design.md). Builds on [Phase 1 — Foundation](2026-11-19-phase1-foundation-design.md), [Phase 2 — Planner](2026-11-19-phase2-planner-design.md) and [Phase 3 — Wishes](2026-11-20-phase3-wishes-design.md); stays within the overview's architecture, data model and rules (§3, §4.3, §4.5, §7).

---

## 1. Goal

Teams are a general way to group up to four characters and label the group with **tags**: some teams are being built for the Abyss (tags *abyss* + *Build*), some are exploration or main teams (*exploration* + *main*), some are just for fun (no tags). Tagging a team **Build** adds its members to the planner, and the team then shows **what is still left to farm to finish it**, with no manual entry.

### Agreed decisions

| Topic | Decision |
|---|---|
| What teams are | General groups of characters with **free-form user tags**; no fixed purpose. |
| Building | **Build is a built-in tag** (cannot be renamed or deleted). It replaces the overview's separate `building` flag. Adding it raises members to goal `build`; removing it changes no goals. |
| Members | **Any released character, owned or not; 1–4 per team; the same character may be in many teams.** |
| Team shortfall | **"As if this team goes first"**: what is still to farm to finish just this team using the whole bag, with a *shared* mark for materials other Build characters also need. |
| Goal drift | If a Build team's member is later set to Want/None elsewhere, the change sticks; the team flags the member **Not building** with a one-click **Build again**. |
| Member slot | Level and talents, progress, equipped weapon, artifact sets, and a **role note** per slot. |
| Elsewhere | Character detail **In teams** panel; Dashboard **Build teams** card; Characters grid **Team tag** filter. |
| Approach | New database-only `teams/` module with proper tag tables; team shortfall computed from the existing planner rows; **no new HoYoLAB calls**. |

### In scope

- `backend/app/teams/`: goal raising, team shortfall, team view payloads.
- Pages: **Teams** (new), **Team editor** (new), **Dashboard** Build teams card, **Characters** tag filter, **Character detail** In teams panel.

### Out of scope

- Build, artifact, or team recommendations (overview §10).
- Element resonance and other derived team stats.
- Spiral Abyss half pairing and Imaginarium Theater rosters (tags cover the labelling need).
- Per-team weapon or artifact plans (the planned weapon stays per character, Phase 2).
- Priorities between teams in the planner (the Inventory page keeps its combined view).
- Importing or sharing teams.

---

## 2. Architecture

`backend/app/teams/` is pure code over database rows, like `planner/`. It makes no network calls; HoYoLAB access stays in `sync/` and `wishes/`.

| File | Responsibility |
|---|---|
| `goals.py` | `raise_to_build(session, character_ids) -> list[int]` (§4). The only place teams change goals. |
| `shortfall.py` | Team-first shortfall and team progress from `PlannerData` (§5). |
| `artifacts.py` | Artifact set line for a member from `owned_artifact` (§6). |
| `view.py` | Team payloads for the API: members, badges, tags, shortfall (§6). |
| `store.py` | Create/replace/delete teams and tags; slot compaction; validation; one transaction per write. |

`api/teams.py` exposes the endpoints in §8. After a write that raised any goal, the API calls the existing `ctx.sync.schedule_gaps()` (Phase 2 §5.2 debounce: 3 s, coalesced, queued behind a running sync).

---

## 3. Data model (one Alembic migration, `0004_teams`)

All of this is **user data**: sync never writes it.

| Table | Columns |
|---|---|
| `team` | `id` PK, `name` (1–60 chars, required, not unique), `notes` (text, may be empty), `sort_order` (int), `created_at`, `updated_at` (UTC) |
| `team_member` | `team_id` + `slot` (0–3) PK, `character_id` (canonical id: Traveler and Manekin collapse as in Phase 1 §5), `role` (≤40 chars, may be empty). Unique `(team_id, character_id)`. |
| `tag` | `id` PK, `name` (1–30 chars, unique case-insensitively, stored as typed), `color` (a palette token from a fixed list; assigned in turn on creation, changeable), `builtin` (bool) |
| `team_tag` | `team_id` + `tag_id` PK |

Rules:

- The migration creates the built-in tag **Build** (`builtin = true`). It cannot be renamed or deleted; its colour can change.
- Deleting a team deletes its members and tag links (`ON DELETE CASCADE`). Deleting a tag removes it from every team. **Neither changes any goal.**
- A team has 1–4 members. Slots are contiguous from 0: removing a member shifts later ones up. Members can be reordered.
- New teams get the lowest `sort_order` (shown first). The Teams page reorders by drag.
- A member whose `character_id` is unknown to the game data (e.g. after a patch) keeps its row and renders as a placeholder card, as on the Characters page.

---

## 4. Goal rules

`raise_to_build(session, character_ids)`:

- For each id whose goal is `none` (no `character_goal` row counts as `none`) or `want`: set goal `build`. Targets are filled exactly as the Characters page does when `build` is chosen (Phase 1 §7): stored targets are restored; otherwise `default_targets`.
- Goals already `build` are untouched. **Goals are never lowered.**
- Returns the ids it changed.

It is called, inside the same transaction as the team write:

1. When a team **gains the Build tag** → all its members.
2. When a team that has the Build tag **gains a member** → that member.

Removing the Build tag, removing a member, deleting a team, and deleting a tag change no goals. Setting a member's goal elsewhere is always allowed; the team then shows the member as **Not building** (§6).

If any goal changed, the API schedules a gaps-only recalculation and returns `raised: [ids]` so the frontend can show "Raised N characters to Build".

---

## 5. Team shortfall ("as if this team goes first")

Computed in `shortfall.py` from one `PlannerData` read (Phase 2 §6); no HoYoLAB calls.

Only members whose goal is `build` count ("Build members"). Per material `m`:

```
team_need[m]  = Σ need of m over Build members (from material_gap)
have[m]       = total.need − total.short + total.spare   (material_total; exact when short, a lower bound otherwise)
team_short[m] = max(0, team_need[m] − have[m])
team_spare[m] = max(0, have[m] − team_need[m])
```

The existing crafting rollup (`planner/crafting.rollup`) then runs over a copy of `PlannerData` whose `totals` are the team's `(team_need, team_short, team_spare)`, giving `craftable` and `to_farm` per material. It follows the same `LACK_INCLUDES_CRAFTING` mode as the Inventory page.

- A material is **shared** when a Build character outside the team also needs it (`need > 0` in their `material_gap`).
- **Team progress** = average of the Phase 1 progress over Build members; none when the team has no Build members.
- Build members the planner skipped (`planner/requests.UNSUPPORTED`, e.g. Traveler) or not yet calculated are listed as **Not calculated** and contribute nothing.
- Status fields reuse Phase 2's: `computed_at`, `gaps_stale`, last gaps error.

---

## 6. Team payload

Per team: `id`, `name`, `notes`, `sort_order`, `tags` (`id`, `name`, `color`, `builtin`), `has_build_tag`, `members`, `shortfall` (or null when no member is Build), `progress`, plus gap-run status.

Per member (in slot order):

- Character: `id`, `name`, `slug`, `icon`, `element`, `rarity`, derived `status` (Phase 1 §7) and `prefarming`.
- If owned: `level`, talents `normal/skill/burst`, equipped weapon (`icon`, `name`, `level`, `refinement`), **artifact set line**.
- If Build: `progress`.
- `role` note.
- Badges: **Not building** — on a member of a Build-tagged team whose goal is not `build`; **Not calculated** — see §5.

**Artifact set line** (`artifacts.py`, from `owned_artifact.set_name`): count pieces per set; a set with ≥4 → `4pc <set>`; otherwise every set with ≥2, highest first → `2pc <A> + 2pc <B>` (or `2pc <A>`); nothing qualifying or no artifacts → empty.

Shortfall rows have the shape of the Inventory tiles: material `id`, `name`, `icon`, `rarity`, `category`, `need`, `short`, `craftable`, `to_farm`, `shared`, ordered by category and tier like Inventory.

---

## 7. Pages

### 7.1 Nav

**Teams** becomes enabled.

### 7.2 Teams (`/teams`)

- **Header:** **New team**, **Manage tags**, tag filter chips *All · <each tag> · Untagged*. Selecting several tags shows teams that have **all** of them. The choice is stored in `localStorage` (try/catch; default *All* when unavailable).
- **Team cards** in `sort_order`, reorderable by dragging the card handle (optimistic; reverted with an error toast on failure). Each card:
  - Name, tag chips, **Edit** link.
  - Four member slots (empty slots dashed): icon on rarity background, name, status badge, `Lv 80 · 6/8/8`, progress bar for Build members, weapon icon with `Lv 90 R1`, artifact set line, role note, and the **Not building** badge with **Build again** (calls the existing goal endpoint).
  - Notes, collapsed after two lines.
  - **Team shortfall panel**, only when at least one member is Build: "To finish this team" with `MaterialTile`s (to farm, craft hint, shared mark); "Everything in the bag ✓" when nothing is short; "Updating…" while `gaps_stale`; "as of <time>" with a warning when the last gaps run failed; "Shortfall appears after the next sync" when gaps were never computed; "Connect HoYoLAB to calculate" when not connected.
- **Empty state:** "Make your first team", with one line explaining that the Build tag adds members to the planner.

### 7.3 Team editor (`/teams/new`, `/teams/[id]`)

- Fields: name, notes, tag picker (choose existing tags or type a new name to create it on save), four slots each with a role note field and ×.
- Below: the character art grid (`CharacterCard`, owned and unowned together) with the Characters page's element, weapon type, rarity and name filters. Clicking a card puts it in the first free slot; members already in the team are marked and not addable; with four members the grid is disabled with a hint. Slots reorder by drag, with up/down buttons for keyboard use.
- When the team has the Build tag, a line under the slots previews the raise: "Saving raises Xiangling, Bennett to Build".
- **Save** (one `POST`/`PUT`; on success a toast "Saved" plus "Raised N characters to Build" when `raised` is non-empty, then back to `/teams`) and **Delete** (confirmation; goals unchanged).
- Unsaved changes: a leave-page warning. Errors appear next to the field (validation) or as a toast (other), and the form keeps its contents.

### 7.4 Manage tags

A panel on the Teams page: list of tags with colour swatch, name and team count; rename inline, recolour from the palette, delete (confirmation names the number of teams that lose it), create. **Build** shows a lock icon and only its colour can change.

### 7.5 Dashboard

A **Build teams** card: one row per Build-tagged team, in `sort_order`: name, member icons, team progress, and the top 5 materials by `to_farm` (most missing first) as small tiles, with "+N more" linking to the team on `/teams`. With no Build-tagged team: "Tag a team Build to plan it here" → Teams.

### 7.6 Characters (`/characters`)

A **Team tag** chip row joins the existing filters: shows characters in any team that has the selected tag(s) (a character matches when one of its teams has all selected tags). Applied within every section; stored with the other filters.

### 7.7 Character detail (`/characters/<slug>`)

An **In teams** panel: each team's name, tag chips and a link to it on `/teams`; "Not in any team" otherwise.

---

## 8. API

| Method & path | Purpose |
|---|---|
| `GET /api/teams` | All teams with the §6 payload (tag filtering happens in the page) |
| `GET /api/teams/{id}` | One team |
| `POST /api/teams` | Create `{name, notes, members: [{character_id, role}], tag_ids, new_tags: [name]}` → team + `raised` |
| `PUT /api/teams/{id}` | Replace name, notes, members (in slot order), and tags as a whole → team + `raised` |
| `DELETE /api/teams/{id}` | Delete; goals unchanged |
| `PUT /api/teams/order` | `{ids: [...]}` (must list every team exactly once) |
| `GET /api/tags` | Tags with team counts |
| `POST /api/tags` | Create `{name, color?}` |
| `PUT /api/tags/{id}` | Rename and/or recolour; renaming Build → `409` |
| `DELETE /api/tags/{id}` | Delete; Build → `409` |
| `GET /api/characters` | Adds `team_tags` per character: one list of tag ids per team the character is in |
| `GET /api/characters/{slug}` | Adds `teams: [{id, name, tags}]` |
| `GET /api/dashboard` | Adds `build_teams` |

---

## 9. Errors

| Situation | Behaviour |
|---|---|
| 0 or more than 4 members, duplicate member, empty or over-long name/role, unknown character or tag id | `422` with a field message; nothing changed |
| Tag name already taken (case-insensitive) | `409` "A tag with that name exists" |
| Rename or delete Build | `409` "Build is a built-in tag" |
| Team or tag not found | `404`; the editor shows "This team no longer exists" with a link back |
| Save fails for any reason | One transaction: team, members, tags, new tags and goal raises apply together or not at all; the editor keeps its contents and shows an error toast |
| Order update lists a missing/extra id | `422`; the page reverts the drag |
| Gaps never computed / last gaps run failed / stale | Panel messages as in §7.2; last-known data shown |
| Not connected | Teams fully usable; shortfall panel says "Connect HoYoLAB to calculate" |
| Unknown member character id after a patch | Placeholder member card; a game-data refresh is triggered as on the Characters page |

---

## 10. Security and data safety

- No new network access and no new secrets. Teams contain only user-entered names, notes, roles and tags.
- The Phase 1 secret-leakage test is extended to the teams and tags endpoints.
- Test fixtures and the dev seed use made-up data only (UID 800000001). The dev seed gains two demo teams: one tagged *Build* + *abyss*, one untagged.
- Teams are included in the existing pre-sync database backups; no extra backup is needed (they are not irreplaceable like wish history).

---

## 11. Testing

### Backend (pytest)

- `raise_to_build`: none → build, want → build, build untouched, never lowers, stored targets restored before defaults, returns changed ids.
- Triggers: adding Build raises all members; adding a member to a Build team raises only that member; removing the tag, a member, a team, and deleting a tag change nothing; a gaps run is scheduled only when something was raised.
- Team shortfall: material shared with an outside Build character (team short < combined short); material not short overall (team short 0); non-Build members excluded; crafting across tiers using the team's spare; `LACK_INCLUDES_CRAFTING` mode; shared mark; team progress; Not calculated members.
- Artifact set line: 4pc, 4+1, 2+2, 2+2+1, none.
- Slot compaction and reorder; one-character-per-team uniqueness; 1–4 members.
- Tags: Build created by the migration, protected from rename/delete, case-insensitive uniqueness, cascade on team and tag delete, `new_tags` creation in the same transaction.
- Transaction rollback: a failing write leaves teams, tags and goals unchanged.
- API tests for every endpoint in §8 against a temporary SQLite database, including the characters and dashboard additions.

### Frontend

- `svelte-check` with no errors.
- Vitest: tag filter (AND, Untagged), "will raise" preview, artifact line text, slot editing helpers (add to first free slot, remove and compact, reorder).
- Playwright (seeded data): create a team from the grid → add the Build tag → save → raise toast → the member appears under *Actively building* on Characters → the Teams card shows the shortfall panel → filter Teams by tag.

---

## 12. Done when

1. Tagging a team **Build** adds its members to the planner, and the team's to-farm list appears within a few seconds.
2. Teams can carry any tags or none, and Teams and Characters can be filtered by them.
3. Teams only ever raise goals; nothing a team does lowers one.
4. Dashboard shows Build teams with their top materials; character pages list their teams.
5. All tests pass; the repository contains no cookie values, UID, nickname, or personal data.

---

## 13. Refinements made during planning (2026-11-21)

1. Tags get a `name_key` column (lower-cased name, unique) to enforce case-insensitive uniqueness.
2. Notes are capped at 2000 characters.
3. A typed new tag that matches an existing tag case-insensitively reuses that tag instead of failing.
4. Member ids are validated on save, so an unknown member can only appear if the catalogue later drops a character; it renders as a placeholder and no extra game-data refresh is triggered.
5. `GET /api/teams` returns `{gaps, connected, teams}` and `GET /api/teams/{id}` returns `{gaps, connected, team}`; tag filtering happens in the page.
6. The Characters page filters are not persisted, so the Team tag filter is not persisted either.
