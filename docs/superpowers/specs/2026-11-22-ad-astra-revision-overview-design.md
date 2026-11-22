# Ad Astra — Design Revision Overview

**Date:** 2026-11-22
**Status:** Breakdown agreed with the user 2026-11-22
**Scope:** The frame for the whole-app design revision that renames GenshinTracker to **Ad Astra** ("Ad Astra Abyssosque"; "to the stars"). It splits the user's page-by-page notes into sub-projects with a build order and records which new data the app can and cannot get. Each sub-project gets its own spec → plan → build → review and leaves the app usable.

The 2026-11-19 overview design still holds (architecture, data model, cookie and art rules) except where a sub-project spec says otherwise.

---

## 1. Goals (from the user's notes)

- A distinct look shared by every page: a left icon sidebar, an animated "astral space dust" background (with an on/off setting, on by default), and dark frosted-glass containers.
- Images first, with text to supplement, so what the app shows matches what the player sees in game.
- Efficient use of the full page width.
- Each page reworked around what the player needs first (details per sub-project).

Hard constraints carried over: cookie values only in the git-ignored `.env`; unofficial API code only in `backend/app/sync/` and `wishes/`; test fixtures use made-up UIDs (800000001); no personal data or game art committed (images load at runtime through `/api/img`); the user's email is never sent to external services.

---

## 2. Data feasibility (probed 2026-11-22)

| Need | Source | Verdict |
|---|---|---|
| Talent and constellation descriptions | Yatta `avatar/<id>` (`talent`, `constellation`) | Available |
| Which domain drops which artifact set | genshin-db API v5 `domains` (MIT): `rewardPreview`, `regionName`, `entranceName` | Available. Yatta `reliquary/<id>` only says "Mystic Offering" |
| Average pity | The user's own wish history | Computed locally |
| Teapot wood and furnishing materials | Yatta `material` catalogue (e.g. Birch Wood); Yatta `furniture` endpoint | Catalogue available; counts only via GOOD import; a "needed" amount requires the user to pick furnishings |
| Domain images | genshin-db `images.filename_image` (e.g. `UI_DungeonPic_Cubic_Normal_3`) | Unresolved: enka.network and Yatta both return 404 for these names; no API has in-world location shots. Needs a spike |
| Expedition rewards | HoYoLAB notes | Not available (character and time left only) |
| Forge and cooking timers | none | Not available; only user-set manual timers. Notes do give resin, realm currency, expeditions, parametric transformer |
| Build recommendations and guides (roles, comps, rotations, talent priority, sets, stats) | no game-data source | Needs a decision: a community build spreadsheet (licence unclear for monetized use) or hand-curated repo data |
| Element icons | `/api/img` named `UI_Buff_Element_Fire` etc. | Available |
| Game menu icons (backpack, wish) | enka.network / Yatta | Not hosted; Ad Astra draws original single-colour icons instead |

---

## 3. Sub-projects and build order

| # | Sub-project | Delivers | Depends on |
|---|---|---|---|
| 1 | **Foundation: shell, theme, rename** | Ad Astra name and icon, left icon sidebar with sync, drifting-dust background with setting, medium glass, theme tokens, `Icon` and `FilterPill`, wider page cap, full-size Map, tidied Settings | — |
| 2 | **Traveler and Manekin per element** | Split the single Traveler (and Manekin) into one plannable character per element ("Anemo Traveler", …) across game data, sync, goals and the planner | 1 |
| 3 | **Dashboard** | Centre column plus side column; greeting; resin/commissions/realm/expeditions bubbles; domain day picker; weekly bosses; user-set character priority with counts allocated by priority; completed builds; side column with timers, live banners with pity, events (raised when ending soon) | 1, 2 |
| 4 | **Characters overview and Teams** | Small/large tiles, sort toggles, coloured filters; diagonal team ribbons, popup editor, coloured default tags, team→character Build propagation, greyed-out unowned characters | 1, 2 |
| 5 | **Character detail** | Banner header, Current / Build / Guide sub-pages, element theming; per-character build targets (removes the global default targets); Guide starts with talent and constellation text | 1 |
| 6 | **Inventory and Events** | "To farm" strip above real counts; paimon.moe-style event timeline with popups; timers beside it; banner history below | 1 |
| 7 | **Wishes and Profile** | Data-analysis Wishes (average-pity line, guarantee arrow, charts); enka.network-style Profile | 1 |
| 8 | **Artifact planning** | Artifact domains from genshin-db, artifact set and main/sub stat targets in Build, Dashboard artifact section, domain-image spike | 3, 5 |
| 9 | **Build recommendations and guides** | Source decision, then Build suggestions and Guide content (teams, rotations, role, talent priority) | 5 |
| 10 | **Teapot materials** | Wood and furnishing materials in Inventory | 6 |

Sub-projects 3 and 5 leave clear slots for the data that 8 and 9 add later.

Hosting, accounts and monetization stay out of scope for this revision; licence risk is noted wherever a data source would matter for a public site.
