# Ad Astra Sub-project 9 — Build Recommendations and Guides

**Date:** 2026-11-24
**Status:** Approved by the user 2026-11-24 (plan-time amendment in section 6.2 marked "Amended while planning"; ORM class named `CharacterStatRecommendation`)
**Frame:** `2026-11-22-ad-astra-revision-overview-design.md` (sub-project 9 of 10). Fills the two slots left by Character detail (`2026-11-23-ad-astra-character-detail-design.md`: Build "Suggestions" `build-suggestions-slot`, Guide "How to play" `guide-howto-slot`) and builds on Artifact planning (`2026-11-24-ad-astra-artifact-planning-design.md`: `character_goal.artifact_target`).
**Scope:** The source decision, then official HoYoLAB artifact-stat recommendations (stored at sync, used to prefill new Build artifact targets and shown on Build with Apply) and a community-guide link on the Guide. Talent priority, artifact sets, teams, rotations and roles are omitted: no usable source has them.

---

## 1. Decisions made with the user

| Topic | Decision |
|---|---|
| Source | The user first chose the community build spreadsheet. The probe (section 2) found it frozen and its successor explicitly "all rights reserved", so it is not used. The user does not want to hand-curate builds or maintain them each patch: "if there really is no way to get that data from another source, then just omit the recommendations all together" |
| What is kept | The one real source found: HoYoLAB's own per-character recommended artifact main stats and substats, which arrive in the character-detail response the sync already fetches |
| Use of it | **Prefill + suggest**: a character entering Build with no artifact target gets the recommendation as its main-stat and substat target; the Build tab shows the recommendation with an Apply button |
| Guide "How to play" | A link card to the character's page on the community build site. No content is copied |
| Omitted | Talent priority and talent targets (`build_defaults()` keeps the baseline), set recommendations, teams, rotations, roles |

---

## 2. Feasibility (probed 2026-11-24, public hosts only, no cookie/UID/email)

| Candidate | Finding | Verdict |
|---|---|---|
| HoYoWiki entry pages (`sg-wiki-api-static.hoyolab.com … entry_page`) | Modules: Attributes, Ascend, Gallery, Talents, Constellation, Video Collection, Description, Voice-Over, Lore, Media. No build or recommendation module | No builds |
| genshin-db, Yatta | No build data (as the overview noted) | No builds |
| GitHub search for an open build dataset | Nothing maintained and licensed; the only MIT repo is a 2-star optimizer | None |
| Community build spreadsheet (Genshin Impact Helper Team, Google Sheets) | Public CSV export works, one tab per element. First row "Discontinued … (Migrating to a new site)"; changelog 2026-06-24 (v6.6): "No additional updates will be made to the Google Sheet going forward" | Frozen; new characters missing |
| Its successor, `github.com/Genshin-Impact-Helper-Team/genshin-builds` (site `genshin-impact-helper-team.github.io/genshin-builds/`) | 129 characters as clean JSON per build (weapons, sets, main stats, substats, talents, notes); active. `LICENSE.md`: "All rights reserved … does not grant permission to copy, mirror, rehost, redistribute … its build recommendations, rankings, notes"; cloning only to inspect, report issues or open PRs | **Not usable** without the maintainers' written permission. Deep links are fine: `/genshin-builds/en/<slug>` |
| **HoYoLAB character detail** (`game_record/genshin/api/character/detail`, already called by sync via `get_genshin_detailed_characters`) | Each `list[]` entry carries `recommend_relic_property`: `recommend_properties` = `sand_main_property_list`, `goblet_main_property_list`, `circlet_main_property_list`, `sub_property_list` (lists of property-type ids), plus `custom_properties` and `has_set_recommend_prop`. genshin.py 1.0.0 does not model it (ignored on parse). Read by Snap.Hutao, TeyvatGuide and other clients | **Available** for owned characters; official, updated by HoYoverse |

Not yet seen in the user's own sync response; the build reads it defensively (section 3.2) and the UI has an empty state.

---

## 3. Data

### 3.1 Migration 0013

New table `stat_recommendation`:

| Column | Type | Meaning |
|---|---|---|
| `character_id` | integer PK (not autoincrement) | our id (each Traveler element its own id, from `canonical_id`) |
| `data` | JSON | `{"main": {"sands": [...], "goblet": [...], "circlet": [...]}, "subs": [...]}` in our stat keys |
| `synced_at` | datetime | when it was last written |

Downgrade drops the table. Revision `"0013"`, down-revision `"0012"`. The real database is at 0009; 0010–0013 run at the next app start.

### 3.2 Sync (`backend/app/sync/`)

Unofficial-API code stays in `sync/`.

- `GenshinPySource.get_details` calls `get_genshin_detailed_characters(..., return_raw_data=True)`, takes the recommendation from each raw `list[]` entry **before** building `genshin.models.GenshinDetailCharacters(**raw)` from a copy (its validator mutates the dict), and maps characters exactly as today.
- `DetailEntry` gains `recommendation: StatRecommendation | None` (a frozen dataclass: `main: dict[str, list[str]]`, `subs: list[str]`).
- `parse_recommendation(raw_entry) -> StatRecommendation | None` (pure, in a new `sync/recommend.py`):
  - reads `recommend_relic_property.recommend_properties`; `custom_properties` (the player's own HoYoLAB choices) and `has_set_recommend_prop` are ignored;
  - maps each property-type id through `PROPERTY_KEYS` (below); unknown ids are dropped; within a list, order is kept and duplicates removed;
  - main-stat keys not allowed for that slot (`SLOT_OPTIONS` in `artifacts/stats.py`) and substat keys not in `SUB_KEYS` are dropped;
  - returns `None` when the block is missing, not a dict, or every list ends up empty. Never raises.
- `PROPERTY_KEYS` (game fight-property ids): `2 hp`, `3 hp%`, `5 atk`, `6 atk%`, `8 def`, `9 def%`, `20 crit_rate`, `22 crit_dmg`, `23 er`, `26 heal`, `28 em`, `30 phys`, `40 pyro`, `41 electro`, `42 hydro`, `43 dendro`, `44 anemo`, `45 geo`, `46 cryo`. A test pins this table; if the user's first real sync shows other ids, the table is corrected then.
- `persist.save_details` upserts a `stat_recommendation` row for each detail entry whose `recommendation` is not `None` (`synced_at` = sync time). `None` leaves any existing row untouched. Rows are never deleted (a character no longer owned keeps its last recommendation; it is game guidance, not account data).

### 3.3 `build_defaults()` unchanged

No source has talent recommendations, so `build_defaults()` keeps the baseline (level 90, normal 6, skill 9, burst 9, weapon 90). The character-detail spec's note "Sub-project 9 changes its body" is superseded by this spec.

---

## 4. Prefill on entering Build

- New helper in `backend/app/targets.py`: `prefill_artifact_target(s, row) -> None`. When `row.goal == "build"`, `row.artifact_target is None` and a `stat_recommendation` row exists for `row.character_id`, it sets `row.artifact_target = {"sets": [], "main": rec.main, "subs": rec.subs}`. Otherwise it does nothing.
- Called after `apply_goal` in both places a character enters Build: `api/characters.py` `set_goal` and `teams/goals.py` `raise_to_build`. In `set_goal` it runs before the body's own `artifact_target` is applied, so an explicit target in the same request wins.
- An existing target (even one with only sets) is never overwritten. Characters already on Build are not changed when a recommendation first arrives; the Build tab offers Apply instead.
- The prefilled value has the `ArtifactTargetIn` shape, so the Build editor and the artifact check (sub-project 8) need no change. Main-stat prefills feed the Dashboard only through the existing rules (a target with no sets is never counted).

---

## 5. API

- `GET /api/characters/{slug}` adds `stat_recommendation: {"main": {...}, "subs": [...], "synced_at": iso} | null`.
- No new endpoints. Apply uses the existing `PUT /api/characters/{id}/goal` with `artifact_target`.

---

## 6. Front end

### 6.1 Build tab: `BuildSuggestions.svelte` (replaces `build-suggestions-slot`)

- Title "Suggestions"; subtitle "HoYoLAB recommends" and the sync date.
- Rows Sands / Goblet / Circlet with the recommended main-stat pills, then "Substats" with the ordered pills. Same `StatPills` look and labels as `BuildArtifacts`.
- **Apply** (goal Build only): sends `artifact_target` = the current target with `main` and `subs` replaced by the recommendation and `sets` kept (or `[]` when there is no target). Saves through the layout's `saveGoal` and reloads; disabled while saving.
- When the current target's `main` and `subs` already equal the recommendation (order-sensitive for subs, order-insensitive within each main slot), the button is replaced by "Your target matches".
- Goal not Build: the recommendation is shown read-only, no Apply.
- No recommendation: "No HoYoLAB recommendation yet. It arrives with the next sync of an owned character." (`data-testid="suggestions-empty"`).
- A footnote: "Talent, set and team suggestions are not available from any open source."
- Pure helpers in `lib/recommend.ts`: `applyRecommendation(target, rec)`, `matchesRecommendation(target, rec)`.

### 6.2 Guide tab: `GuideLink.svelte` (replaces `guide-howto-slot`)

- A small card, "How to play", with "Community build guide ↗" linking to `communityGuideUrl(slug, element)` in a new tab with `rel="noopener noreferrer"`.
- Note under it: "Third-party guide by the Genshin Impact Helper Team (all rights reserved), not affiliated with Ad Astra."
- `lib/guides.ts` (pure): `communityGuideUrl(slug)` → `https://genshin-impact-helper-team.github.io/genshin-builds/en/<their-slug>`, where `<their-slug>` is our slug except a small exceptions map. Amended while planning: a full comparison of our 129 slugs with the site's list found one exception (`raiden-shogun → shogun-raiden`); our Traveler slugs (`anemo-traveler` …) already match the site's URLs, so no Traveler parameter. Characters the site lacks still get a link (their 404 page is acceptable).

### 6.3 New pieces

- Components: `BuildSuggestions`, `GuideLink`.
- `lib/recommend.ts`, `lib/guides.ts`; type `StatRecommendation`; `Character` gains `stat_recommendation`.

---

## 7. Errors and empty states

| Case | Behaviour |
|---|---|
| HoYoLAB omits or changes the field | `parse_recommendation` returns `None`; existing rows stay; sync never fails because of it |
| Unknown property ids | Dropped; a list may end up empty (shown as "no preference") |
| No recommendation for a character | Suggestions empty state; prefill does nothing |
| Apply save fails | The layout's existing inline save error; values reload |
| Community page missing for a character | The link still opens their site's 404; no check from our side |

---

## 8. Security, data safety and licence

- No new requests: the recommendation is part of the character-detail response the sync already fetches with the same cookies. Nothing new is sent anywhere.
- Only property ids → stat keys are stored. Nickname, server, avatars and UID are still dropped at sync; `custom_properties` (the player's own choices) is not stored.
- The community site is only linked, never fetched or copied. No game art is added.
- Licence: HoYoLAB-derived recommendations carry the same risk as the rest of the HoYoLAB data for a public site (unofficial API, HoYoverse terms). The community build data is "all rights reserved"; using it would need the maintainers' written permission.
- Test fixtures are trimmed made-up detail entries with UID 800000001 where a UID is needed.

---

## 9. Testing

**Backend (pytest)**

- `parse_recommendation`: full block; missing block; non-dict; unknown ids dropped; slot-invalid main stats dropped; duplicates removed; all-empty → `None`.
- `PROPERTY_KEYS` pinned.
- `get_details` with a fake client returning raw data: recommendation attached to the right canonical id (including a Traveler body id); existing detail mapping unchanged.
- `save_details`: insert, update, `None` keeps the old row.
- Prefill: goal switch to Build fills an empty target; an existing target is kept; no recommendation → nothing; explicit `artifact_target` in the same request wins; Teams Build prefills too; leaving and re-entering Build keeps the stored target.
- `GET /api/characters/{slug}` includes `stat_recommendation`.
- Migration 0013: table created and dropped.

**Frontend**

- Vitest: `applyRecommendation` (keeps sets, null target), `matchesRecommendation` (main order-insensitive, subs order-sensitive), `communityGuideUrl` (plain slug, exceptions, each Traveler element).
- Playwright (workers 1; restore what a test changes): Build shows the seeded recommendation; Apply changes the target and the test restores it; "Your target matches" after Apply; empty state for a character without one; Guide link href and `target="_blank"`.
- Devseed stores recommendations for Bennett and Furina (made-up but plausible stat lists), none for one other seeded character.

---

## 10. Out of scope

- Talent priority and recommended talent levels; artifact set recommendations; weapon recommendations; teams, rotations, roles.
- Fetching, mirroring or parsing the community build site or the frozen spreadsheet.
- Using `custom_properties` or `has_set_recommend_prop`.
- Recommendations for characters never synced as owned.

---

## 11. Done when

- A sync stores HoYoLAB's recommended main stats and substats per owned character.
- Putting a character with no artifact target on Build (goal switch or Teams) prefills its main-stat and substat target.
- Build shows "HoYoLAB recommends" with Apply, the match state and the empty state; the slot is gone.
- Guide shows the community-guide link card; the slot is gone.
- pytest, svelte-check, vitest, build and Playwright pass.

---

## 12. Hard constraints (unchanged)

- Cookie values only in the git-ignored `.env`; never logged, returned or committed.
- Unofficial API code in `backend/app/sync/` and `wishes/`; public game-data code in `backend/app/gamedata/`.
- Made-up UIDs (800000001) in fixtures; no personal data or game art committed; images through `/api/img`.
- No user name, email, Windows user name or absolute user path in committed files.
