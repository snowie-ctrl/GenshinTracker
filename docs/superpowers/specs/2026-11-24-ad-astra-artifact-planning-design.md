# Ad Astra Sub-project 8 — Artifact Planning

**Date:** 2026-11-24
**Status:** Approved by the user 2026-11-24 (plan-time amendments in sections 5, 3.2, 6.4 and 9 marked "amended while planning")
**Frame:** `2026-11-22-ad-astra-revision-overview-design.md` (sub-project 8 of 10). Fills the slots left by Dashboard (`2026-11-22-ad-astra-dashboard-design.md`, section 3.1 item 6) and Character detail (`2026-11-23-ad-astra-character-detail-design.md`, `BuildArtifacts.svelte`).
**Scope:** Artifact domains from genshin-db, per-character artifact targets (sets, main stats, substat priority) on the Build tab with a check against equipped gear, an Artifact domains section on the Dashboard, and the domain-image spike result.

---

## 1. Decisions made with the user

| Topic | Decision |
|---|---|
| Who the Dashboard counts | Build characters with a set target whose equipped gear does not yet match it (auto check), unless the user ticked **Artifacts done** on Build. Substats never auto-complete |
| Target depth | One 4-piece set **or** two 2-piece sets; one or more allowed main stats for each of Sands, Goblet, Circlet; an ordered substat priority list. Flower and Plume are fixed |
| Domain card art | The domain's two 5★ set icons side by side, the needed set lit, the other dimmed |
| Storage | Approach 1: the target is one JSON value on `character_goal`, plus a new `game_artifact_domain` table refreshed from genshin-db |

---

## 2. Feasibility and the domain-image spike (probed 2026-11-24, public hosts only, no cookie/UID/email)

| Need | Finding | Verdict |
|---|---|---|
| Artifact domains | genshin-db API v5 `GET https://genshin-db-api.vercel.app/api/v5/domains?query=names&matchCategories=true&verboseCategories=true` returns all 284 domains in one response (~370 KB). `domainType == "UI_ABYSSUS_RELIC"` marks the 92 artifact domain tiers, which group into **22 domains** by name without the trailing roman numeral | Available |
| Fields per tier | `id`, `name`, `regionName`, `entranceName`, `recommendedLevel`, `recommendedElements` (e.g. `["Pyro"]`), `rewardPreview` (items with `name` and `rarity`; artifact items carry the **set name**), `images.filename_image` | Available. The 5★ sets come from the highest tier's `rewardPreview` entries with `rarity == 5` (always two sets) |
| Set ids | `rewardPreview` artifact ids (e.g. 400108) are item ids, not Yatta set ids. Set **names** match `game_artifact_set.name` (Yatta) | Map by name |
| Source quirks | `regionName` is wrong for at least one domain (Ridge Watch is listed as Mondstadt; it is in Liyue) | Shown as given; no hand patches |
| Sets not from domains | Gladiator's Finale, Wanderer's Troupe and others drop from bosses or the Strongbox; no domain lists them | Labelled "Not from a domain" |
| Set bonus text | Yatta `reliquary/<id>` → `affixList` (2-piece / 4-piece text) | Available but out of scope (section 10) |
| **Domain location images (spike)** | `UI_DungeonPic_*` names (e.g. `UI_DungeonPic_Cubic_Normal_1`, `UI_DungeonPic_FDRelic01`) return 404 on `enka.network/ui/`, `gi.yatta.moe/assets/UI/` (and its `dungeon/`, `reliquary/` paths); Yatta has no `dungeon` endpoint; the HoYoWiki API (`sg-wiki-api-static.hoyolab.com … get_menus`) has no Domains category; honeyhunterworld refuses (403); ambr, hakush.in and homdgcat did not answer. Nation emblems `UI_ChapterIcon_<Nation>` exist on enka for Mengde, Liyue, Inazuma and Sumeru only | **No source.** Cards use the two set icons instead (decision above). The spike is closed |
| Equipped artifacts | `owned_artifact` (from sync): `set_name`, `slot` 1–5 (flower, plume, sands, goblet, circlet), `main_stat` as `"<name> <value>"` (e.g. `"ATK 46.6%"`, `"Pyro DMG Bonus 46.6%"`, `"Elemental Mastery 187"`), `substats` | Available for the check |

---

## 3. Data

### 3.1 Migration 0012

- `character_goal` gains `artifact_target` (JSON, nullable) and `artifacts_done` (boolean, not null, default false).
- New table `game_artifact_domain`:

| Column | Type | Meaning |
|---|---|---|
| `id` | integer PK (not autoincrement) | the lowest genshin-db tier id of the domain |
| `name` | string | base name, e.g. `"Domain of Blessing: Fires of Purification"` |
| `entrance` | string | `entranceName`, e.g. `"Midsummer Courtyard"` |
| `region` | string \| null | `regionName` as given |
| `elements` | JSON | `recommendedElements` of the highest tier |
| `set_ids` | JSON | the two 5★ set ids, in `rewardPreview` order |

- Downgrade drops the table and the two columns.

### 3.2 Target shape (`artifact_target`)

```text
{
  "sets": [{"set_id": 15007, "pieces": 4}]                                # one 4-piece
        | [{"set_id": 15001, "pieces": 2}, {"set_id": 15007, "pieces": 2}],  # or two 2-piece (different ids)
  "main": {"sands": ["atk%", "er"], "goblet": ["pyro"], "circlet": ["crit_rate", "crit_dmg"]},
  "subs": ["crit_rate", "crit_dmg", "er", "atk%"]                          # ordered, no duplicates
}
```

- `sets` may be empty (only stats targeted). A target with no sets is never counted on the Dashboard.
- `sets` may also hold a single 2-piece entry: the "2 + 2" mode before the second set is chosen (amended while planning).
- Each `main` list may be empty (no preference for that slot).
- **Stat keys** (`backend/app/artifacts/stats.py`):
  - Main: `hp%`, `atk%`, `def%`, `em`, `er`, `crit_rate`, `crit_dmg`, `heal`, `pyro`, `hydro`, `electro`, `cryo`, `anemo`, `geo`, `dendro`, `phys`.
  - Allowed per slot: sands `hp% atk% def% em er`; goblet `hp% atk% def% em` + the seven elements + `phys`; circlet `hp% atk% def% em crit_rate crit_dmg heal`.
  - Substats: `hp`, `atk`, `def`, `hp%`, `atk%`, `def%`, `em`, `er`, `crit_rate`, `crit_dmg`.
- Validated by a Pydantic model `ArtifactTargetIn` on `PUT /goal`: unknown keys, a stat not allowed for its slot, more than two sets, two 2-piece entries with the same id, a 4-piece entry alongside another entry, an unknown set id, or duplicate substats → 422.
- Stored like the other targets: kept when the goal leaves Build. Leaving Build sets `artifacts_done` to false, so a character re-entering Build starts unticked. This goes through the shared goal helper used by `api/characters.py` and `teams/goals.py`.

### 3.3 Domain refresh (`backend/app/gamedata/genshindb.py`)

genshin-db code stays in `gamedata/`.

- `async fetch_domains(http) -> list` — GET the URL in section 2 (30 s timeout, raise on HTTP error).
- `parse_artifact_domains(payload, set_ids_by_name) -> (list[ArtifactDomainData], unmatched: list[str])` (pure):
  - keep `domainType == "UI_ABYSSUS_RELIC"`; group by `name` with a trailing ` I`…` X` roman numeral removed;
  - per group: `id` = lowest tier id; `entrance`, `region`, `elements` from the highest `recommendedLevel` tier; `set_ids` = that tier's `rarity == 5` reward names, de-duplicated in order, mapped through `set_ids_by_name`;
  - names not in `set_ids_by_name` go to `unmatched`; a group with no matched set is dropped;
  - malformed entries are skipped, not fatal.
- `service.refresh_artifact_domains(...)` follows `refresh_artifact_sets`: 7-day staleness (`GAMEDATA_MAX_AGE_DAYS`) or an empty table; `GameMeta` keys `artifact_domains_fetched_at`, `artifact_domains_last_error`, `artifact_domains_unmatched`. On failure the stored rows are kept. On success the table is replaced.
- `refresh_all` calls it **after** `refresh_artifact_sets` (it needs set names) and also forces it when the sets were just refreshed.
- `gamedata_status` gains `artifact_domains: {fetched_at, last_error, count, unmatched}`; Settings shows it as another line in the game-data status block.
- The request carries no cookie, UID or email.

---

## 4. Artifact check (`backend/app/artifacts/check.py`, pure)

### 4.1 Main-stat parsing

`main_key(text) -> str | None` parses an `owned_artifact.main_stat` string:

- Split on the last space into name and value; `%` at the end of the value marks a percentage.
- Names: `HP` / `ATK` / `DEF` with `%` → `hp%` / `atk%` / `def%` (without `%` → flat `hp` / `atk` / `def`); `Elemental Mastery` → `em`; `Energy Recharge` → `er`; `CRIT Rate` → `crit_rate`; `CRIT DMG` → `crit_dmg`; `Healing Bonus` → `heal`; `<Element> DMG Bonus` → element key; `Physical DMG Bonus` → `phys`.
- Anything else → `None`.

### 4.2 Check

`check(target, equipped: list[OwnedArtifactLike], sets_by_id) -> ArtifactCheck`:

```text
ArtifactCheck
  status:  "none" | "met" | "missing"
  sets:    [{set_id, name, icon, pieces, equipped}]     # equipped = pieces of that set worn
  slots:   [{slot, set_name, icon, main_stat, key, ok}] # one per equipped piece; ok is null for flower/plume
                                                         # and for slots with no main preference
  missing: [str]                                        # e.g. "4pc Emblem of Severed Fate (2/4)", "Goblet"
```

- `status = "none"` when there is no target or the target has no sets and no main preferences.
- **Sets met**: every target entry has `equipped >= pieces` (matched by set name, since `owned_artifact` stores names).
- **Mains met**: every sands/goblet/circlet piece that is equipped has a `key` in that slot's allowed list (or the list is empty). A slot with no piece equipped counts as missing ("Sands"). A `None` key never matches.
- `status = "met"` when both hold, else `"missing"`. With no artifacts equipped: `"missing"`, `missing = ["No artifacts equipped"]`.
- Substats are not checked.

### 4.3 Which gear is checked

- Normal characters: their `owned_artifact` rows.
- Traveler elements: the rows stored under whichever Traveler element id has them (the sync stores gear only for the synced element; all elements share it in game).
- Not owned: no rows → `"missing"` with "No artifacts equipped".

---

## 5. API

- `GET /api/characters/{slug}` adds:
  - `artifact_target` — the stored target or `null` (top level, not inside `targets`; amended while planning: `TargetsIn` requires every level field and feeds the material planner, so artifacts stay separate);
  - `artifacts_done` — boolean;
  - `artifact_check` — section 4.2, always present (status `"none"` without a target).
  `artifact_target` and `artifacts_done` are also in the `GET /api/characters` list rows.
- `PUT /api/characters/{id}/goal` accepts top-level `artifact_target` (`ArtifactTargetIn` or `null` to clear) and `artifacts_done`. Omitting either keeps the stored value. `artifacts_done` is only stored while the goal is Build.
- `GET /api/artifact-sets` (new) → `[{id, name, icon, domain: {id, name, entrance, region} | null}]`, sorted by name; for the Build picker.
- `GET /api/dashboard` adds `artifact_domains` (section 6.2).

---

## 6. Front end

### 6.1 Build tab: `BuildArtifacts.svelte`

Replaces the dashed slot; still spans two grid columns.

- **Sets.** A two-way toggle "4-piece" / "2 + 2", then one or two `ArtifactSetPicker`s (searchable list of sets with icons from `/api/artifact-sets`). Each chosen set shows icon, name and its source: the domain entrance ("Midsummer Courtyard") or "Not from a domain". A picker has a clear (✕) button.
- **Main stats.** Three rows (Sands, Goblet, Circlet), each a multi-select group of `FilterPill`s with the slot's allowed stats. Flower "HP" and Plume "ATK" are shown fixed.
- **Substats.** Ordered chips with up/down buttons and a remove ✕; an "Add substat" menu lists the stats not yet chosen. Position = priority (shown as 1, 2, 3…).
- **Equipped check.** A row of the equipped pieces (set icon, slot name, main stat) with ✓ / ✗ per sands/goblet/circlet (none for flower/plume or slots without a preference), the set counts ("Emblem 2/4") and a status line: "Matches target", "Missing: …", or "No artifacts equipped".
- **Artifacts done** tick beside the status line.
- Every change saves at once through `PUT /goal` and reloads (the Build tab pattern). While a save is in flight the controls are disabled. When the goal is not Build the card is read-only, like the rest of the tab.
- Labels for stat keys come from `lib/artifacts.ts`.

### 6.2 Dashboard: `ArtifactDomains.svelte`

Rendered in the centre column between Weekly bosses and Building (the reserved position).

Backend (`backend/app/dashboard/artifacts.py`, pure over rows) builds:

```text
artifact_domains: {
  domains: [{id, name, entrance, region, elements,
             sets: [{id, name, icon, needed: bool,
                     characters: [{id, name, slug, icon, pieces, equipped}]}]}],
  other:   [{id, name, icon, characters: [...]}],   # wanted sets no domain drops
  hint:    str | null
}
```

- **Counted characters**: Build characters with at least one target set, `artifacts_done` false and check status `"missing"`. A character whose sets are met but main stats are not is still counted under its sets (it still needs pieces).
- A domain is listed when at least one of its sets is wanted by a counted character. Characters per set follow Build priority; domains are ordered by best priority among their characters, then by name (the `planner/today.py` rule).
- `other` holds wanted sets with no domain, same ordering.
- `hint`: when there are Build characters but none has a target set → "Set artifact targets on a character's Build tab to plan domains here". Otherwise `null`.
- The section is hidden when `domains` and `other` are empty and `hint` is null.

Card layout:

- Art: the two set icons (`/api/img`), large, side by side; a set with `needed: false` is dimmed.
- Entrance name as the title, region below it, recommended element icons.
- Per needed set: set name, then character portraits (linking to `/characters/<slug>/build`) with "4pc · 2/4" style hints.
- "Other sources" card: same set rows, titled "Not from a domain (bosses / Strongbox)".
- No day picker: artifact domains are open every day.

### 6.3 New pieces

- Components: `BuildArtifacts` (rewritten), `ArtifactSetPicker`, `StatPills`, `SubstatOrder`, `ArtifactDomains`.
- `lib/artifacts.ts` (pure, vitest): `STAT_LABELS`, `SLOT_OPTIONS`, `moveSub(order, from, to)`, `setsFor(mode, current)` (switching 4-piece ↔ 2 + 2 keeps the first set).
- `api.artifactSets()`, types `ArtifactTarget`, `ArtifactCheck`, `ArtifactSetOption`, `ArtifactDomainsView`; `Character` gains `artifact_target` and `artifacts_done`, `CharacterDetail` gains `artifact_check`.

### 6.4 Correction to the Dashboard spec

The Dashboard spec said talent domain cards keep "an empty image slot" for this spike. `DomainDays.svelte` has that slot (an empty `.image` div); it is removed, since the spike found no source (amended while planning; an earlier draft of this section wrongly said the slot did not exist).

---

## 7. Errors and empty states

| Situation | Behaviour |
|---|---|
| genshin-db fetch fails | Stored domains kept; error stored in `artifact_domains_last_error` and shown on Settings. With no domains stored, every set reads "Drop source unknown" on Build and appears under Other sources on the Dashboard |
| Set name from genshin-db not in `game_artifact_set` | Skipped, listed in `artifact_domains_unmatched`; retried at the next refresh |
| No equipped artifacts | Status `missing`, "No artifacts equipped" |
| Unparseable main stat | That slot does not match; Build shows the raw text with ✗ |
| Invalid target | 422; the Build card shows the inline save error and reloads |
| Target save fails (network) | Inline error under the banner, values reload (existing Build behaviour) |

---

## 8. Security and data safety

- The domain request goes to genshin-db-api.vercel.app only, with no cookie, UID or email. The image proxy allow-list is unchanged (set icons already load from enka.network / Yatta).
- genshin-db data is MIT-licensed public game data; only parsed fields are stored.
- No game art is committed; set icons load at runtime through `/api/img`.
- Test fixtures are a trimmed genshin-db response (public game data) and keep the made-up UID 800000001 where a UID is needed.

---

## 9. Testing

**Backend (pytest)**

- `parse_artifact_domains` on a trimmed fixture (three domains with several tiers, one unknown set name, one malformed entry): grouping, top-tier 5★ sets, name mapping, unmatched list, skipping.
- `refresh_artifact_domains` with fake HTTP: fresh skip, stale refetch, failure keeps rows and stores the error, ordering after the set refresh in `refresh_all`; `gamedata_status` shape.
- `main_key` for every stat family, flat vs percent, unknown text.
- `check`: 4-piece met, 2 + 2 met, partial set, wrong main, slot with no preference, missing slot, no gear, `None` key, Traveler element using the synced element's gear.
- `ArtifactTargetIn` validation (each 422 case in 3.2).
- Goal round-trip: set, omit keeps, `null` clears; `artifacts_done` set and cleared on leaving Build, from both the Characters endpoint and Teams propagation.
- Migration 0012 upgrade and downgrade.
- `/api/artifact-sets` shape and domain join; `/api/characters/{slug}` new fields.
- Dashboard `artifact_domains`: counting rule (met, done, no sets), priority ordering of characters and domains, `needed` flags, `other`, `hint`, hidden state.

**Dev seed:** stores the trimmed domain list (with a current `artifact_domains_fetched_at`) so Playwright never calls genshin-db; gives Bennett a target ticked Artifacts done (amended while planning: done by the tick rather than by gear, so the shared seed gear used by Teams and Profile stays unchanged; pytest covers `met` by gear), Furina a 2 + 2 target (Noblesse from Stone Chamber, Gladiator from no domain) that is `missing`, and Neuvillette a 4-piece Bloodstained Chivalry target from the same domain.

**Frontend**

- Vitest: `lib/artifacts.ts` helpers.
- Playwright `e2e/artifacts.spec.ts` (workers 1; restores what it changes): set a 4-piece target and main stats on Build, check status updates; the Dashboard section shows the domain card with the lit set and the character; ticking Artifacts done removes the character; the target is restored at the end.
- `characters.spec.ts`: the dashed-slot assertion is replaced by a check that the Artifacts card renders.

Gates: pytest, `npm run check`, `npx vitest run`, `npm run build`, Playwright.

---

## 10. Out of scope

- Set bonus text (2-piece / 4-piece) in the picker.
- Suggesting owned artifacts from the GOOD import inventory.
- Substat scoring or a per-piece rating.
- Recommended artifact targets (sub-project 9).
- Domain location images (spike closed: no source).
- Resin or run-count estimates.

---

## 11. Done when

- Settings' game-data status lists artifact domains, refreshed weekly from genshin-db.
- A Build character can be given sets (4-piece or 2 + 2), main stats per slot and an ordered substat list; the Build tab shows whether the equipped gear matches, and an Artifacts done tick.
- The Dashboard shows an Artifact domains section between Weekly bosses and Building, with set-icon art, characters in priority order, and an Other sources card; characters leave it when their gear matches or they are ticked done.
- pytest, svelte-check, vitest, build and Playwright pass.

## 12. Hard constraints (unchanged)

- Cookie values live only in the git-ignored `.env` and are never logged, returned or committed.
- Unofficial API code stays in `backend/app/sync/` and `wishes/`; public game-data code stays in `gamedata/`.
- Test fixtures use only made-up UIDs (800000001).
- No personal data or game art is committed; images load at runtime through `/api/img`.
- The user's email is never sent to external services.
