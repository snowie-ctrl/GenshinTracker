# Ad Astra Sub-project 1 — Foundation (Shell, Theme, Rename)

**Date:** 2026-11-22
**Status:** Design approved in chat 2026-11-22; awaiting written-spec review
**Frame:** `2026-11-22-ad-astra-revision-overview-design.md` (sub-project 1 of 10)
**Scope:** Rename the app to Ad Astra; replace the top bar with a left icon sidebar; add the animated astral background and its setting; restyle every container as frosted glass; add theme tokens and the two shared components later sub-projects reuse; widen pages; make Map's embed fill the window; tidy Settings. No page gets its own redesign here.

---

## 1. Decisions made with the user

| Topic | Decision |
|---|---|
| Sidebar style | Icons with small labels under them, about 76px wide (mockup option B) |
| Icon style | Solid single-colour icons, warm cream; the active page turns gold with a soft glow and a gold bar |
| Icon source | Original SVGs drawn in the spirit of the game's menu icons, committed to the repo. The game's own menu icons are not hosted by enka.network or Yatta (probed: every name tried returned 404) |
| Background | Three layers of dust drifting slowly at different speeds over a faint, still purple/blue nebula (mockup option A) |
| Background technique | CSS star layers moved by CSS transforms (approach A); not canvas, not video |
| Glass strength | Medium: `rgba(18,22,38,.52)`, 14px blur, faint white border, top-edge highlight |
| Rename scope | Name and code, not folders |
| Page width | Shell full width; pages not yet redesigned capped at about 1600px; Map full width now |
| Settings | Grouped sections as glass cards with a sticky in-page index |

---

## 2. Shell

### 2.1 Layout

- `+layout.svelte` renders three layers: the background (fixed, behind everything), the sidebar (fixed, left, full height, 76px), and the content area (the rest of the width).
- The current top bar (`.topnav`) is removed.
- The HoYoLAB connection banners ("login expired" / "not connected") move to the top of the content area, keeping their text, links and conditions.

### 2.2 Sidebar

Top to bottom:

1. Ad Astra logo (the committed SVG, about 40px). Not a link; `aria-label="Ad Astra"`.
2. Dashboard `/`, Characters `/characters`, Teams `/teams`, Inventory `/inventory`, Map `/map`, Events `/events`, Wishes `/wishes`. Each is an `<a>` with an icon and a label under it.
3. A flexible spacer that pushes the rest to the bottom.
4. Sync item (see 2.3).
5. Profile `/profile`, Settings `/settings`.

Active-page rule is unchanged from today (`/` matches exactly; other links match by path prefix). The active link gets `aria-current="page"`, gold colour, a glow on the icon and a 3px gold bar on its left edge. Inactive links are cream at reduced brightness and brighten on hover and keyboard focus (visible focus ring).

The sidebar is a glass surface (same tokens as panels, slightly darker) with a 1px right border.

### 2.3 Sync item

- Shows the sync icon with a short label under it: the relative time from the current `syncLabel` helper, shortened to fit (e.g. "3m ago", "Syncing…", "Never").
- A coloured status dot on the icon: green when the last sync's parts all succeeded, amber when any part failed, none when there has been no sync. The icon spins while a sync runs, unless reduced motion is in effect.
- Clicking it toggles the existing details popover, now opening to the right of the sidebar. The popover gains the "Sync now" button (same enable rule as today: disabled while running or when not connected). The sync error text shows inside the popover.
- `data-testid="sync-label"` stays on the clickable element so existing tests keep their hook.
- A pure helper `syncBadge(status) → { tone: 'ok' | 'warn' | 'none', short: string }` drives the dot and label so it can be unit-tested.

### 2.4 Icons

- `frontend/src/lib/icons/` holds the original SVG paths; `Icon.svelte` renders one by name (`dashboard`, `characters`, `teams`, `inventory`, `map`, `events`, `wishes`, `sync`, `profile`, `settings`, `external`, `close`) at a given size, filled with `currentColor`.
- Shapes: a four-tile grid (Dashboard), a bust (Characters), a group of figures (Teams), a backpack (Inventory), a folded map (Map), a calendar (Events), a four-point wish star with sparkles (Wishes), circular arrows (Sync), an ID card (Profile), a gear (Settings).
- Icons are decorative next to their visible labels (`aria-hidden="true"`).

### 2.5 Logo and favicon

- The user's `adAstraIcon.svg` (their own design, not game art) is copied to `frontend/static/ad-astra.svg` and used for the sidebar logo and as the favicon (`<link rel="icon" type="image/svg+xml">` in `app.html`).
- `frontend/static/` is new; adapter-static copies it into the build.

---

## 3. Background

### 3.1 Scene

- Base colour: deep navy (`#070a14`).
- Nebula: two soft radial gradients (purple top-right, blue bottom-left) at low opacity. Never moves.
- Dust: three layers of small dots. Far layer: many tiny, dim white dots. Middle layer: fewer, slightly larger, cool blue-white. Near layer: few, largest, warm cream.
- Dot positions come from a seeded random generator so the scene looks the same on every load. Each layer is one element whose `box-shadow` list draws its dots over a fixed tile (e.g. 1400×900px). The tile pattern is drawn twice, offset by one tile, so the drift loops without a visible seam.

### 3.2 Motion

- Each layer moves diagonally (up-left) by exactly one tile size with a CSS `transform` animation, linear and infinite. Durations are roughly 90s (far), 55s (middle) and 35s (near), so the near dust moves fastest and gives depth.
- No JavaScript runs per frame.
- The background is `position: fixed`, `pointer-events: none` and sits behind all content.

### 3.3 Still mode

The animation pauses (`animation-play-state: paused`), leaving the same scene still, when either:

- the `background_animated` setting is `false`, or
- the operating system asks for reduced motion (`prefers-reduced-motion: reduce`).

A pure helper `backgroundAnimated(setting: boolean, reducedMotion: boolean): boolean` returns `setting && !reducedMotion`.

### 3.4 Setting

- New backend setting `background_animated`, default `true`, in `app/settings/store.py` `DEFAULTS`.
- `SettingsIn` gains `background_animated: bool | None`; `settings_payload` returns it; `PUT /api/settings` saves it. No migration is needed (settings are key/value rows).
- The layout loads it once on start through the existing settings API and keeps it in a small shared store so the Settings page can update it live without a reload. If the request fails, the background animates (the default).

---

## 4. Theme

### 4.1 Tokens (`app.css`)

- **Surfaces:** `--glass-bg: rgba(18,22,38,.52)`, `--glass-bg-strong` (sidebar, popovers; darker), `--glass-border: rgba(255,255,255,.12)`, `--glass-highlight` (inset top-edge line), `--glass-blur: 14px`.
- **Accents from the icon:** `--cream: #e9dcc0`, `--cream-dim`, `--gold: #e8cf9c`, `--gold-strong: #d9b672`.
- **Elements:** `--pyro`, `--hydro`, `--anemo`, `--electro`, `--dendro`, `--cryo`, `--geo` (orange-red, blue, teal, violet, green, ice blue, amber).
- **Rarity:** `--rarity-5` gold, `--rarity-4` purple. The existing `--r5…--r0` card gradients stay.
- **Kept:** the four status colours (`--building`, `--obtained`, `--wanted`, `--unobtained`), `--warn`, `--error`, `--text`, `--muted`.
- `--accent` becomes gold (it is used for links and the active state today).

### 4.2 Global restyle

- `body` background becomes transparent over the fixed background; the old `--bg` stays as the fallback colour.
- `.panel` becomes medium glass: `--glass-bg`, `backdrop-filter: blur(var(--glass-blur))`, `--glass-border`, top-edge highlight, 12px radius. Every existing page picks this up unchanged.
- Buttons, inputs and selects: translucent dark fill, glass border, cream text, gold focus ring. `button.primary` becomes gold with dark text.
- `.chip` keeps working for places not yet moved to `FilterPill`.
- `main` max width rises from 1280px to 1600px with 24px gutters. A page can opt out of the cap (Map does; redesigned pages will).

### 4.3 FilterPill

- `FilterPill.svelte` props: `label`, `on`, `color` (a CSS colour or token; defaults to grey), optional `image` (an icon name passed to `imgSrc`), `onclick`.
- Off: transparent fill, 1px outline in `color`, cream text. On: filled with `color`, dark text if the colour is light, otherwise white. `aria-pressed` reflects `on`.
- The optional image renders at 16px before the label; a failed image is hidden and the label still shows.
- Foundation uses it on the Characters page for the element (element colour plus `UI_Buff_Element_*` icon), weapon (grey) and rarity (5★ gold, 4★ purple) filters. The team-tag filter row there keeps `TagChip` (Teams is redesigned in sub-project 4).
- Mapping element → colour token and icon name lives in one helper (`elements.ts`) so later pages reuse it.

---

## 5. Pages touched

### 5.1 Map

- The page opts out of the width cap.
- The map tabs, the current map's name and "Open in new tab" become one slim glass bar.
- The embed fills the remaining window height: `height: calc(100vh - <bar and gutters>)` with a 600px minimum, full width, rounded corners.
- The "doesn't allow embedding" fallback keeps its behaviour, restyled as glass.

### 5.2 Settings

- The seven current panels are grouped into sections, each a glass card with a heading:
  - **Account:** HoYoLAB.
  - **Sync & data:** Sync, Game data, Inventory import (GOOD).
  - **Appearance (new):** "Animated background" toggle, with a note that the system's reduce-motion setting also keeps it still.
  - **Planner:** Default build targets (removed later by sub-project 5).
  - **Wishes.**
  - **Map.**
- A sticky index on the left lists the sections, jumps to each on click, and highlights the section currently in view. Below about 900px wide, the index sits above the sections instead.
- Every existing control, `data-testid` and behaviour is kept; only grouping and styling change.

### 5.3 Characters

- Only the filter pills change (4.3). The grid, cards and everything else wait for sub-project 4.

### 5.4 Everything else

- Dashboard, Teams, Inventory, Events, Wishes, Profile and character detail get the glass, colours and controls through the global styles only.

---

## 6. Rename (name and code, not folders)

| Where | From | To |
|---|---|---|
| `frontend/src/app.html` `<title>` | GenshinTracker | Ad Astra |
| Sidebar logo accessible name | (brand text) | Ad Astra |
| `frontend/package.json` `name` | genshintracker-frontend | ad-astra-frontend (lockfile updated to match) |
| `backend/app/main.py` FastAPI title | GenshinTracker | Ad Astra |
| `backend/app/main.py` `USER_AGENT` | GenshinTracker/0.1 (local personal tool) | AdAstra/0.2 (local personal tool) |
| `backend/app/wishes/uigf.py` `export_app` | GenshinTracker | AdAstra |
| `run.py` docstring and startup message | GenshinTracker | Ad Astra |
| `README.md` title and intro | GenshinTracker | Ad Astra (one line noting it was formerly GenshinTracker) |

Unchanged: the repository folder, `data/` and the database file name, environment variable names, and earlier specs and plans (they are history). Tests that assert the old strings are updated. Renaming the GitHub repository is left to the user (GitHub redirects the old name).

UIGF files exported under the old name keep importing: the importer does not check `export_app`. A test pins this by importing a fixture with `export_app: "GenshinTracker"`.

---

## 7. Error handling

- An element icon or the logo fails to load: the image is hidden and the text label remains; layout does not shift.
- The settings request fails at start: the background animates (default) and the rest of the shell works.
- Saving the background toggle fails: the toggle reverts and the Settings page shows its usual save error.
- `backdrop-filter` unsupported: glass falls back to the solid `--glass-bg-strong` colour, which stays readable.

---

## 8. Testing

- **Backend (pytest):** `background_animated` defaults to `true`, saves `false`, returns 422 for a value that is not a boolean (e.g. a list); the UIGF export uses `AdAstra`; a UIGF file with `export_app: "GenshinTracker"` still imports.
- **Vitest:** `syncBadge` (no sync, running, all ok, a failed part); `backgroundAnimated` (all four combinations); `elements.ts` mapping covers all seven elements.
- **Playwright:**
  - The sidebar reaches all nine pages and marks only the current one with `aria-current="page"`.
  - The sync item opens the details popover, which contains "Sync now".
  - Turning "Animated background" off in Settings pauses the background, and the choice survives a reload.
  - Map's embed fills most of the window height.
  - Characters element pills toggle filtering as before.
- Existing suites stay green; tests that relied on the top bar or old names are updated. Commands: backend `.venv` `python -m pytest -q`; frontend `npm run check`, `npx vitest run`, `npm run build`, `PYTHON=<venv python> npx playwright test`.

---

## 9. Out of scope

- Each page's own redesign (sub-projects 3–7), including fully fluid page widths.
- Image-plus-label tiles, element-themed pages, and charts (added with the pages that need them).
- Removing the default build targets setting (sub-project 5).
- Game-art menu icons (no source hosts them).
- A phone layout: below about 900px the sidebar stays as is.
- Renaming folders, the database file or the GitHub repository.
