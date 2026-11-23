# Ad Astra Sub-project 5 — Character Detail

**Date:** 2026-11-23
**Status:** Approved 2026-11-23
**Frame:** `2026-11-22-ad-astra-revision-overview-design.md` (sub-project 5 of 10). Builds on Foundation (`2026-11-22-ad-astra-foundation-design.md`), Traveler per element (`2026-11-22-ad-astra-traveler-per-element-design.md`), Dashboard (`2026-11-22-ad-astra-dashboard-design.md`) and Characters overview and Teams (`2026-11-23-ad-astra-characters-teams-design.md`). Replaces the character detail page and the global default build targets setting.
**Scope:** A banner header with Current / Build / Guide sub-pages, element theming, per-character build targets (with target constellation and refinement), and a Guide that starts with talent, passive and constellation text from Yatta. Leaves marked slots for sub-project 8 (artifact targets) and sub-project 9 (recommendations and guide content).

---

## 1. Decisions made with the user

| Topic | Decision |
|---|---|
| Starting targets | A built-in baseline replaces the global setting: character level 90, weapon level 90, talents normal 6 / skill 9 / burst 9, each raised to the current value when already higher. No setting. Sub-project 9 later replaces the baseline with per-character recommendations through the same function |
| Build scope | Build also stores a **target constellation** and **target weapon refinement**. They are shown beside Current ("C2 → C6", "R1 → R5") and ignored by the material planner |
| Guide talent depth | Icon, name, description, plus a compact table of the talent's numbers at the current level, the Build target level and the max level. Constellations: icon, name, text, lit when owned |
| Banner | Layout B: a ~300px banner of the cropped splash, dark fade on the left, name in the element colour, rarity, element, weapon type, goal pills; the Current / Build / Guide tabs sit inside its bottom edge |
| Current / Build | One shared grid. Current is read-only; Build shows each value as "now → target" with a picker. No materials on this page |
| Guide layout | Two columns (A): talents and passives on the left, constellations on the right; one column when narrow. A "How to play" slot on top |
| Kit data source | Fetched from Yatta on first open of a character, cached in the database, refreshed after 7 days (approach 1) |

Visual-companion mockups (git-ignored): `.superpowers/brainstorm/15295-1795457216/content/` (`banner.html`, `current-build.html`, `guide.html`).

---

## 2. Feasibility (probed 2026-11-23, public hosts only)

| Need | Finding | Verdict |
|---|---|---|
| Talent text | Yatta `api/v2/en/avatar/<id>` → `data.talent`, a dict keyed `"0"`, `"1"`, … Each entry: `name`, `description`, `icon`, `type`, `cooldown`, `cost`, and for active talents `promote` (per level `"1"`…`"15"`: `description` row templates such as `Skill DMG|{param1:F1P} Max HP`, and `params` floats) | Available |
| Talent roles | `type` 0 = normal attack and skill, plus an alternate sprint for some characters (Ayaka, Mona: key `"2"`, no cooldown); `type` 1 = burst; `type` 2 = passives (3 or 4, e.g. Mona 4, Mavuika 4) | Normal = first type-0 entry; skill = the type-0 entry with a cooldown; burst = type 1; other type-0 entries = `other` |
| Constellation text | `data.constellation` `"0"`…`"5"`: `name`, `description`, `icon`, `extraData.addTalentExtraLevel` (`talentIndex`, `extraLevel` 3) for C3/C5 | Available |
| Text markup | `<color=#RRGGBBAA>…</color>`, `<i>…</i>`, `{LINK#N…}…{/LINK}`, literal `\n` | Needs a small parser to safe segments |
| Icons | `Skill_A_01`, `Skill_A_Catalyst_MD`, `Skill_S_<X>_01`, `Skill_E_<X>_01`, `UI_Talent_S_<X>_NN`, `UI_Talent_U_<X>_NN`: 200 on enka.network and gi.yatta.moe | Load through `/api/img` |
| Traveler | Yatta keys `10000005-<element>` (boy) and `10000007-<element>` (girl), e.g. `Skill_S_PlayerWind_01` | Per-element kits available |
| Banner art | `UI_Gacha_AvatarImg_<X>` 2048×1024 on both hosts (already `splash` in the payload) | Available |

---

## 3. Build targets (backend)

### 3.1 Baseline

A new function in `backend/app/domain.py`:

```python
@dataclass(frozen=True)
class Current:            # existing, extended
    level: int
    normal: int | None
    skill: int | None
    burst: int | None
    constellation: int = 0
    weapon_level: int | None = None
    refinement: int | None = None

def build_defaults(current: Current | None) -> Targets
```

- Baseline: level 90, normal 6, skill 9, burst 9, weapon level 90.
- Each baseline value is raised to the current value when the current value is higher (`max(baseline, current)`).
- `constellation` target = current constellation; `refinement` target = current refinement (1 when no weapon). A new Build plans nothing from wishes until the user raises it.
- Not owned (`current is None`): level 1, talents 1, C0, R1 as current, so the baseline as above.
- This is the only source of starting targets. Sub-project 9 changes its body, not its callers.

### 3.2 Targets

`Targets` gains `constellation: int | None = None` (0–6) and `refinement: int | None = None` (1–5), stored in the new nullable columns. `Targets.from_dict` accepts dicts without them (old rows and tests). `build_defaults` always fills both; a stored `None` (a row from before this sub-project) is shown on Build as "same as current". `TargetsIn` gets optional `constellation: int | None = Field(None, ge=0, le=6)` and `refinement: int | None = Field(None, ge=1, le=5)`; when a client omits them the stored values are kept.

`resolve_targets(goal, stored, defaults)` keeps its rule (defaults only when going to Build with nothing stored; stored targets survive goal changes). Its callers pass `build_defaults(current)` instead of the setting.

### 3.3 Callers

- `api/characters.py` `set_goal`: builds `Current` from the owned row (Traveler: see 3.5) and passes `build_defaults(current)`.
- `teams/goals.py` `raise_to_build(session, character_ids)`: drops the `defaults` parameter and looks up each character's current values itself (a helper `current_for(session, character_id) -> Current | None`, in `planner` or `domain`-adjacent code, shared with `set_goal`). `teams/store.py` stops importing `default_targets`.
- The material planner ignores `target_constellation` and `target_refinement`.

### 3.4 Data: migration 0010

- `character_goal` gains nullable `target_constellation` and `target_refinement` (integers).
- The `setting` row with key `default_targets` is deleted. Downgrade drops the new columns and table only; the setting row is not restored (older code falls back to its built-in default).
- The same migration creates `game_character_kit` (section 4.2).

Stored targets are not rewritten: characters already on Build keep what they have, including values that came from the old 8/8/8 default.

### 3.5 Traveler

Current values for a Traveler element come from the same place the detail payload already uses: the owned row for the synced element, `traveler_element` (talents, constellation) for the others. No change to Traveler storage.

### 3.6 Removed

- `default_targets` from `settings/store.py` `DEFAULTS` and the `default_targets()` helper.
- `DEFAULT_TARGETS` from `config.py`.
- `default_targets` from `api/settings.py` (GET payload and PUT body), `frontend/src/lib/api.ts` `saveSettings`, `types.ts` `Settings`.
- The "Default build targets" block on the Settings page.
- `TargetsEditor.svelte` (replaced by the Build tab pickers; its only users are the Settings block above and the old detail page).

### 3.7 Edge cases

- A target below the current value (the character was levelled in game) shows as reached on Build; the planner already treats it as no cost.
- Weapon target level and refinement apply to the planned weapon if set, else the equipped one.

---

## 4. Talent kit (backend)

### 4.1 `backend/app/gamedata/kit.py`

Yatta code stays in `gamedata/`.

- `yatta_key(character_id, traveler_body) -> str`: the id as a string; for a Traveler element id, `"10000005-<element>"` (boy) or `"10000007-<element>"` (girl) from the `traveler_body` setting, element in lower case (`anemo`, `geo`, …).
- `async fetch_kit(http, key) -> dict`: GET `https://gi.yatta.moe/api/v2/en/avatar/<key>` (30s timeout, raise on HTTP error).
- `parse_kit(payload) -> Kit` (pure):

```text
Kit
  v:              int              shape version (KIT_VERSION = 1); a cached kit with another v is refetched
  talents:        [ActiveTalent]   role: normal | skill | burst | other
      name, icon, role, cooldown (float|None), cost (int|None)
      description: [[Segment]]       lines of segments
      scaling: [ScaleRow]            label, values: [str] for levels 1..15 (shorter if Yatta has fewer)
  passives:       [Passive]        name, icon, description
  constellations: [Constellation]  index 1..6, name, icon, description,
                                   raises: normal | skill | burst | None
Segment = {text: str, color: str | None, italic: bool}
```

- Role rule: first type-0 entry = `normal`; the type-0 entry with a cooldown = `skill`; type 1 = `burst`; any other type-0 entry = `other` (shown on the Guide, no scaling column on Build).
- `raises`: `extraData.addTalentExtraLevel.talentIndex` matched to the active talent with that index in Yatta's talent list (skill or burst).
- Template formatting: `{paramN:F1P}` → `round(v*100, 1)%`; `F2P` → 2 decimals %; `P` → 0 decimals %; `F1`/`F2` → 1/2 decimals; `I` → integer. A row may hold several placeholders and plain text (`{param1:F1P}+{param2:F1P}`, `{param3:F1}s`). Unknown formats print the raw number. Rows split on the first `|` into label and value.
- Markup: `<color=#RRGGBBAA>` → segment colour `#RRGGBB`; `<i>` → italic; `{LINK#…}` / `{/LINK}` dropped, inner text kept; `\n` (literal and real) → new line; any other `<…>` tag dropped. Output is plain text only.
- A talent with no `promote` gets `scaling: []`; a missing icon is `None`. Malformed entries are skipped, not fatal.

### 4.2 Storage

Table `game_character_kit`: `character_id` integer PK, `data` JSON (the parsed `Kit`, not the raw payload), `fetched_at` datetime. Created in migration 0010.

### 4.3 Endpoint

`GET /api/characters/{slug}/kit` → `{"state": "fresh" | "stale" | "unavailable", "kit": Kit | null}`.

- Fresh (fetched within `GAMEDATA_MAX_AGE_DAYS`): served from the database.
- Missing or older: fetched from Yatta, parsed, stored, served as `fresh`. A per-character `asyncio.Lock` (held on the app context) stops two opens fetching at once.
- Fetch fails (`FETCH_ERRORS`): the stored kit is served as `stale`; with none, `unavailable` and `kit: null` (HTTP 200).
- Unknown slug: 404.
- The request carries no cookie, UID or email (same public request style as the catalogue refresh).

### 4.4 Effective talent levels

HoYoLAB reports base talent levels. The in-game level adds 3 for each owned constellation that raises that talent. Shown as base with a "+3" mark; the Guide table's columns use effective levels:

- now = base + 3 if the raising constellation is owned;
- target = target base + 3 if the raising constellation is owned or within the target constellation;
- max = 10, or 13 when the raising constellation is owned or targeted.

---

## 5. API changes

- `GET /api/characters/{slug}` adds `priority` (from `character_goal.priority`) and `targets.constellation`, `targets.refinement`. Its `shortfall` field stays (existing planner tests use it), but the page no longer shows it.
- `PUT /api/characters/{id}/goal` accepts `targets.constellation` and `targets.refinement`.
- `GET /api/characters/{slug}/kit` (new, 4.3).
- `GET/PUT /api/settings` lose `default_targets`.

---

## 6. Frontend

### 6.1 Routes

Under `frontend/src/routes/characters/[slug]/`:

- `+layout.svelte`: loads `api.character(slug)` (reloads on `sync.version`), renders `CharacterBanner`, sets `--el` to the element colour on its root, sets the dust tint (6.3), and provides a small context object (`character`, `reload()`, `saveGoal(body)`, `saveError`) to the tabs.
- `+page.svelte` — Current; `build/+page.svelte` — Build; `guide/+page.svelte` — Guide.
- Tabs are links: `/characters/<slug>`, `/characters/<slug>/build`, `/characters/<slug>/guide`.
- `isWide` in `lib/nav.ts` also matches `/characters/<slug>` and its sub-paths (not only exact `WIDE_ROUTES`).
- The kit (`api.characterKit(slug)`) is loaded by the Build and Guide tabs (and Current for talent/constellation icons). A missing kit never blocks Current or Build: they fall back to text labels without icons.
- The old 2-second shortfall polling goes away with the shortfall section.

### 6.2 Banner: `CharacterBanner.svelte`

- About 300px tall, glass border, the splash (`imgSrc(splash)`) with `object-fit: cover; object-position: 62% 25%`, a left-to-right dark fade.
- Left: name (element colour, large), rarity stars, element icon + element, weapon type, goal pills (None / Want / Build, the existing `GoalSwitch`), "Pre-farming" when set, and when the goal is Build a read-only "Priority #n" linking to `/` (Dashboard). Save errors show below the banner.
- Bottom edge: the three tabs on a dark gradient; active tab in the element colour with an underline.
- Narrow screens: banner height drops to ~220px and the fade covers more of the art so text stays readable.

### 6.3 Element theming

- `lib/elements.ts` gains `ELEMENT_HEX` (same values as the `--pyro` … `--geo` tokens).
- `appearance` gains `tint: string | null`. The character layout sets it on mount (and when the element changes) and clears it on destroy.
- `Starfield` repaints the two larger dust layers and the nebula gradients in the tint colour when set; the fine white layer stays white. With no tint it looks as today.
- `--el` drives the name, active tab, card headings and target values on the three tabs.
- Characters with no element (should not happen after sub-project 2) use the default gold.

### 6.4 Current tab

Grid (three columns wide, one narrow):

- **Level & constellations**: level / 90 (with friendship), "C n", `ConstellationRow` (six icons, lit when owned).
- **Talents**: three `TalentBadge`s (icon, level, gold when 10 base, "+3" when boosted).
- **Weapon**: icon, name, rarity, level, refinement. Below it **In teams** (existing list with tag chips).
- **Artifacts** (two columns wide): five pieces with set icon, slot, level, main stat, substats.
- **Stats**: the existing stat table.
- Traveler: `TravelerElementCard` sits at the top of Current.
- Not owned: "Not obtained yet" card plus In teams.

### 6.5 Build tab

The same grid, each value "now → target" with a picker:

- Level (level caps from settings), target constellation (C0–C6; constellation icons beyond the current one get a dashed outline when targeted), three talent pickers (1–10), weapon: planned weapon select (existing options), target weapon level, target refinement (R1–R5).
- **Artifacts** card: `BuildArtifacts.svelte`, a dashed slot — "Target sets and main/sub stats arrive with sub-project 8."
- **Suggestions** card: a dashed slot — "Recommended targets arrive with sub-project 9."
- When the goal is not Build, the tab shows the targets read-only with a "Set to Build to plan this character" button (same as choosing Build in the banner, which fills the baseline).
- Every change saves at once through `PUT /goal` and reloads.

### 6.6 Guide tab

- Top: "How to play" dashed slot — "Role, team comps, rotations and talent priority arrive with sub-project 9."
- Left column: **Talents** (each: icon, name, kind and cooldown/energy, `KitText` description, `ScalingTable` with columns now / target / max using effective levels; target column only when the goal is Build) and **Passives** (icon, name, description).
- Right column: **Constellations · C n**: six rows, icon lit when owned, name, description.
- One column below ~1100px.
- `state: "stale"` shows a small "Talent data may be out of date" note; `unavailable` shows "Talent data unavailable" with Retry.

### 6.7 New pieces

- Components: `CharacterBanner`, `TalentBadge`, `ConstellationRow`, `KitText` (renders segments as `<span>`s with inline colour and italics; no `{@html}`), `ScalingTable`, `BuildArtifacts`.
- `lib/kit.ts` (pure): `effectiveLevel`, `maxLevel`, `raisedBy` (which constellation raises a talent), `scalingColumns(kit, current, targets, constellation)`.
- `api.characterKit(slug)`, types `Kit`, `KitResponse`; `Targets` gains `constellation` and `refinement`.

---

## 7. Errors

| Case | Behaviour |
|---|---|
| Kit unavailable | Guide shows a notice with Retry; Current and Build drop only the icons |
| Kit stale | Guide shows a small out-of-date note |
| Goal or target save fails | Inline error under the banner, values reload |
| Unknown slug | "Unknown character" text (as today) |
| Odd Yatta data | Entries skipped; unknown template formats print the raw number |

---

## 8. Security and data safety

- The kit request goes to gi.yatta.moe only, with no cookie, UID or email.
- Kit text is parsed to plain segments on the server and rendered as text; no HTML from Yatta reaches the DOM.
- No game art is committed; talent and constellation icons load at runtime through `/api/img` (enka.network then Yatta).
- Test fixtures are trimmed Yatta JSON (public game data, no personal data) and keep the made-up UID 800000001 where a UID is needed.

---

## 9. Testing

**Backend (pytest)**

- `parse_kit` on trimmed fixtures — Furina (roles, scaling templates, C3/C5 `raises`), Ayaka (alternate sprint as `other`), Anemo Traveler (`{LINK}` markup): roles, formats `F1P`/`F2P`/`P`/`F1`/`I`/multi-param, markup segments, skipped malformed entries.
- `yatta_key` for normal ids and Traveler elements per body.
- Kit endpoint with fake HTTP: fresh cache, stale refetch, failure with and without a cache, one fetch for two concurrent requests, 404.
- `build_defaults`: baseline, never below current, unowned, constellation/refinement from current.
- `set_goal` and `raise_to_build` use the baseline without the setting; targets round-trip `constellation` and `refinement`; omitting them keeps stored values.
- Migration 0010: columns added, `default_targets` row removed, `game_character_kit` created.
- Settings tests: `default_targets` gone from GET and rejected/ignored in PUT.

**Frontend**

- Vitest: `lib/kit.ts` helpers; `ELEMENT_HEX`; Starfield tint colour choice; `isWide` for sub-paths.
- Playwright (`characters.spec.ts` rewritten; workers 1; restore what a test changes): banner shows name and tabs; tab links switch pages; Build pickers save and are restored; Guide shows talents, passives and constellations from the seeded kit; dust tint set on the page and cleared after leaving. `settings.spec.ts`: the targets block is gone.
- Devseed stores a kit (with a current `fetched_at`) for each seeded character so Playwright never calls Yatta.

---

## 10. Out of scope

- Artifact set and main/sub stat targets (sub-project 8).
- Recommendations, role, comps, rotations, talent priority (sub-project 9).
- A full Lv 1–15 scaling table, weapon passive and refinement text.
- Any change to how the planner prices targets.
- Material shortfall on this page (removed; Dashboard and Inventory keep theirs).

---

## 11. Done when

- `/characters/<slug>` shows the banner with Current / Build / Guide tabs, themed in the character's element colour, and the dust tint clears on leaving.
- Build edits level, talents, constellation, weapon, weapon level and refinement per character; a new Build starts from the baseline.
- The global default targets setting is gone from Settings, the API and the database, and goal raising (goal switch, Teams Build) still works.
- The Guide shows talents with now / target / max numbers, passives and constellations for every character, including each Traveler element.
- Slots for sub-projects 8 and 9 are visible.
- pytest, svelte-check, vitest, build and Playwright pass.
