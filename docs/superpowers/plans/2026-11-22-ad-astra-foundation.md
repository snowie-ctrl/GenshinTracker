# Ad Astra Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rename GenshinTracker to Ad Astra and give every page the new shell: left icon sidebar with sync, drifting-dust background with an on/off setting, medium frosted glass, theme tokens, coloured filter pills, a full-size Map and a tidied Settings page.

**Architecture:** Frontend-heavy. One new backend key/value setting (`background_animated`). The shell lives in `+layout.svelte`, split into `Starfield.svelte` (background), `Sidebar.svelte` and `SyncItem.svelte`. Pure helpers (`starfield.ts`, `nav.ts`, `elements.ts`, `syncBadge` in `syncLabel.ts`) carry the logic and are unit-tested; components stay thin. The background is CSS: three oversized layers with a repeating SVG star tile, moved by a CSS transform animation.

**Tech Stack:** FastAPI + Pydantic + SQLAlchemy (backend settings), SvelteKit 2 / Svelte 5 runes / TypeScript, adapter-static, Vitest, Playwright, pytest.

**Spec:** `docs/superpowers/specs/2026-11-22-ad-astra-foundation-design.md` (frame: `2026-11-22-ad-astra-revision-overview-design.md`).

## Global Constraints

- Cookie values live only in the git-ignored `.env`; never logged, returned by the API, or committed.
- Unofficial API code stays in `backend/app/sync/` and `backend/app/wishes/`.
- Test fixtures use only made-up UIDs (800000001).
- No game art committed. Element icons load at runtime through `/api/img/<UI_name>` via `imgSrc()` in `frontend/src/lib/img.ts`. The Ad Astra logo is the user's own design and is committed.
- Glass: `rgba(18,22,38,.52)`, 14px blur, faint white border, top-edge highlight.
- Sidebar: about 76px wide, icons with labels under them, cream icons, active page gold with a glow and a 3px gold bar.
- Background: three drifting dust layers (≈90s / 55s / 35s), still nebula, no per-frame JavaScript; still when `background_animated` is false or `prefers-reduced-motion: reduce`.
- Pages capped at 1600px with 24px gutters; Map uncapped.
- Rename: "Ad Astra" for people, `AdAstra` in machine strings (`AdAstra/0.2 (local personal tool)`, UIGF `export_app: "AdAstra"`), `ad-astra-frontend` package name. Folders, `data/`, DB file, env var names and old docs unchanged.
- Python for tests: `C:/Users/smoki/Documents/Code-Development/GenshinTracker/.venv/Scripts/python.exe`. Backend tests run from `backend/`: `<python> -m pytest -q`. Frontend from `frontend/`: `npm run check`, `npx vitest run`, `npm run build`, `PYTHON=<python> npx playwright test`.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

### Spec amendments made while planning

- The `close` icon is dropped (nothing in Foundation uses it); the icon set is `dashboard, characters, teams, inventory, map, events, wishes, sync, profile, settings, external`.
- Star tiles are drawn as a repeating SVG `background-image` instead of a `box-shadow` list: the browser repeats the tile natively, so any window size is covered without duplicating stars. Behaviour is the same as spec §3.1–3.2.
- Element icon names verified 2026-11-22: `UI_Buff_Element_Fire, _Water, _Wind, _Electric, _Grass, _Ice, _Rock` (`_Ice` only on Yatta; the image cache already falls back from enka.network to Yatta).

## Review Focus

1. **Reduced motion with the setting on** → the background must be still. Pinned in Task 9 (Playwright `emulateMedia({ reducedMotion: 'reduce' })`) and Task 5 (`backgroundAnimated` unit test).
2. **Settings request fails at start** → background animates (default) and the sidebar still works. Pinned in Task 5 (store unit test with a rejecting loader).
3. **Saving the background toggle fails** → the checkbox snaps back and the error shows. Pinned in Task 9 (Playwright with a 500 route).
4. **Element icon fails to load** → the pill still shows its label and keeps filtering. Pinned in Task 7 (Playwright with the image route returning 404).
5. **Nested and root paths** → `/characters/xiangling` marks only Characters active; `/` marks only Dashboard. Pinned in Task 6 (`isActive` unit tests) and the Task 6 Playwright test.

---

## File Map

| File | Status | Responsibility |
|---|---|---|
| `backend/app/settings/store.py` | modify | `background_animated` default |
| `backend/app/api/settings.py` | modify | accept, save and return `background_animated` |
| `backend/tests/test_api_settings.py` | modify | setting tests |
| `backend/app/main.py`, `backend/app/wishes/uigf.py`, `run.py`, `README.md` | modify | rename strings |
| `backend/tests/test_wish_uigf.py` | modify | export name; old export still imports |
| `frontend/package.json`, `frontend/package-lock.json`, `frontend/src/app.html` | modify | rename, favicon |
| `frontend/static/ad-astra.svg` | create | logo + favicon (copied from the user's file) |
| `frontend/src/app.css` | modify | tokens and global glass restyle |
| `frontend/src/lib/icons.ts`, `frontend/src/lib/Icon.svelte`, `frontend/src/lib/icons.test.ts` | create | original icon set |
| `frontend/src/lib/starfield.ts`, `frontend/src/lib/starfield.test.ts` | create | seeded stars, SVG tile, still-mode rule |
| `frontend/src/lib/appearance.svelte.ts`, `frontend/src/lib/appearance.test.ts` | create | shared background setting store |
| `frontend/src/lib/Starfield.svelte` | create | background layers |
| `frontend/src/lib/nav.ts`, `frontend/src/lib/nav.test.ts` | create | nav items and active rule |
| `frontend/src/lib/syncLabel.ts`, `frontend/src/lib/syncLabel.test.ts` | modify | `syncBadge` |
| `frontend/src/lib/Sidebar.svelte`, `frontend/src/lib/SyncItem.svelte` | create | sidebar and sync item with popover |
| `frontend/src/routes/+layout.svelte` | modify | new shell |
| `frontend/src/lib/elements.ts`, `frontend/src/lib/elements.test.ts`, `frontend/src/lib/FilterPill.svelte` | create | element colours/icons, pill |
| `frontend/src/routes/characters/+page.svelte` | modify | pills on filters |
| `frontend/src/routes/map/+page.svelte` | modify | full-size embed |
| `frontend/src/lib/SettingsIndex.svelte` | create | sticky section index |
| `frontend/src/routes/settings/+page.svelte` | modify | grouped sections, Appearance toggle |
| `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts` | modify | `background_animated` |
| `frontend/e2e/shell.spec.ts` | create | sidebar, sync popover |
| `frontend/e2e/characters.spec.ts`, `map.spec.ts`, `settings.spec.ts` | modify | new e2e cases |

---

### Task 1: `background_animated` setting (backend + API types)

**Files:**
- Modify: `backend/app/settings/store.py` (DEFAULTS)
- Modify: `backend/app/api/settings.py` (`SettingsIn`, `settings_payload`, `put_settings`)
- Modify: `frontend/src/lib/types.ts` (`Settings`), `frontend/src/lib/api.ts` (`saveSettings` body)
- Test: `backend/tests/test_api_settings.py`

**Interfaces:**
- Produces: `GET/PUT /api/settings` field `background_animated: bool` (default `true`). TS: `Settings.background_animated: boolean`; `api.saveSettings({ background_animated?: boolean })`.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_api_settings.py`)

```python
def test_background_animated_defaults_on_and_saves(paths):
    with make_client(paths) as client:
        assert client.get("/api/settings").json()["background_animated"] is True
        body = client.put("/api/settings", json={"background_animated": False}).json()
        assert body["background_animated"] is False
        assert client.get("/api/settings").json()["background_animated"] is False


def test_background_animated_rejects_non_boolean(paths):
    with make_client(paths) as client:
        assert client.put("/api/settings", json={"background_animated": [1]}).status_code == 422
        assert client.get("/api/settings").json()["background_animated"] is True
```

- [ ] **Step 2: Run them to verify they fail**

Run (from `backend/`): `<python> -m pytest tests/test_api_settings.py -q -k background`
Expected: FAIL with `KeyError: 'background_animated'`.

- [ ] **Step 3: Implement**

`backend/app/settings/store.py` — add to `DEFAULTS` after `good_import_enabled`:

```python
    "background_animated": True,    # Ad Astra drifting-dust background (Foundation)
```

`backend/app/api/settings.py` — in `SettingsIn` add `background_animated: bool | None = None`; in `settings_payload` add `"background_animated": bool(get_setting(s, "background_animated")),`; in `put_settings` before the `return`:

```python
        if body.background_animated is not None:
            set_setting(s, "background_animated", body.background_animated)
```

`frontend/src/lib/types.ts` — in `interface Settings` add `background_animated: boolean;` after `good_import_enabled`.

`frontend/src/lib/api.ts` — extend the `saveSettings` body type with `background_animated?: boolean`.

- [ ] **Step 4: Run tests**

Run: `<python> -m pytest -q` (from `backend/`), then `npm run check` (from `frontend/`).
Expected: all pass; svelte-check 0 errors.

- [ ] **Step 5: Commit**

```bash
git add backend/app/settings/store.py backend/app/api/settings.py backend/tests/test_api_settings.py frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat(foundation): background_animated setting"
```

---

### Task 2: Rename to Ad Astra, logo and favicon

**Files:**
- Modify: `backend/app/main.py:30,85`, `backend/app/wishes/uigf.py:111`, `run.py:1,115`, `README.md:1-4`
- Modify: `frontend/package.json` (`name`), `frontend/package-lock.json` (top-level `name` and `packages[""].name`), `frontend/src/app.html`
- Create: `frontend/static/ad-astra.svg`
- Test: `backend/tests/test_wish_uigf.py`

**Interfaces:**
- Produces: `/ad-astra.svg` served from the build (used by Task 6's sidebar logo).

- [ ] **Step 1: Write the failing tests** (in `backend/tests/test_wish_uigf.py`)

Change the assertion in `test_build_v4` to `out["info"]["export_app"] == "AdAstra"`, and add:

```python
def test_exports_from_the_old_app_name_still_import():
    data = v4([rec("1704096000000000001", "301", "2024-01-01 09:00:00", "Slingshot", 3)])
    data["info"]["export_app"] = "GenshinTracker"
    rows = parse_uigf(data, UID, 1)
    assert [r.name for r in rows] == ["Slingshot"]
```

- [ ] **Step 2: Run to verify**

Run: `<python> -m pytest tests/test_wish_uigf.py -q`
Expected: `test_build_v4` FAILS (`'GenshinTracker' == 'AdAstra'`); the old-name test PASSES already (it pins existing behaviour).

- [ ] **Step 3: Implement the rename**

- `backend/app/main.py`: `USER_AGENT = "AdAstra/0.2 (local personal tool)"`; `FastAPI(title="Ad Astra", lifespan=lifespan)`.
- `backend/app/wishes/uigf.py`: `"export_app": "AdAstra"`.
- `run.py`: docstring `"""Start Ad Astra on http://127.0.0.1:<port>. ...` (keep the rest); `print(f"Ad Astra running at http://127.0.0.1:{port}")`.
- `README.md`: title `# Ad Astra`; first paragraph becomes `A personal, locally run Genshin Impact tracker (formerly GenshinTracker): your roster syncs from HoYoLAB automatically, grouped by what you're building, own, want, or don't have yet.` Leave everything else.
- `frontend/package.json`: `"name": "ad-astra-frontend"`. In `frontend/package-lock.json` change the two `"name": "genshintracker-frontend"` occurrences (top level and under `"packages": { "": {`) to `ad-astra-frontend`.
- Copy the logo: `Copy-Item "C:\Users\smoki\Documents\Code-Development\- Resources -\images\appIcons\adAstraIcon.svg" frontend\static\ad-astra.svg` (create `frontend/static/` first). Open the copy and confirm it is the compass-and-star SVG with no external references.
- `frontend/src/app.html`: `<title>Ad Astra</title>` and, before `%sveltekit.head%`, `<link rel="icon" type="image/svg+xml" href="/ad-astra.svg" />`.

- [ ] **Step 4: Run tests and build**

Run: `<python> -m pytest -q`; `npm run build`; then check `frontend/build/ad-astra.svg` exists.
Expected: all pass, file present. `grep -rn "GenshinTracker" backend/app frontend/src run.py` returns nothing.

- [ ] **Step 5: Commit**

```bash
git add backend/app/main.py backend/app/wishes/uigf.py run.py README.md backend/tests/test_wish_uigf.py frontend/package.json frontend/package-lock.json frontend/src/app.html frontend/static/ad-astra.svg
git commit -m "feat(foundation): rename to Ad Astra, logo and favicon"
```

---

### Task 3: Theme tokens and global glass

**Files:**
- Modify: `frontend/src/app.css` (replace whole file)

**Interfaces:**
- Produces CSS custom properties used by later tasks: `--glass-bg`, `--glass-bg-strong`, `--glass-border`, `--glass-highlight`, `--glass-blur`, `--cream`, `--cream-dim`, `--gold`, `--gold-strong`, `--pyro`, `--hydro`, `--anemo`, `--electro`, `--dendro`, `--cryo`, `--geo`, `--rarity-5`, `--rarity-4`, `--pill-neutral`, `--sidebar-w`, `--gutter`. Class `.glass` (same look as `.panel`, no padding).

- [ ] **Step 1: Replace `frontend/src/app.css`**

```css
:root {
	--bg: #070a14;
	--panel: rgba(18, 22, 38, 0.52);
	--panel-2: rgba(30, 36, 58, 0.6);
	--line: rgba(255, 255, 255, 0.12);
	--text: #e8e6ef;
	--muted: #a19fb2;
	--cream: #e9dcc0;
	--cream-dim: #a9a294;
	--gold: #e8cf9c;
	--gold-strong: #d9b672;
	--accent: var(--gold);
	--glass-bg: rgba(18, 22, 38, 0.52);
	--glass-bg-strong: rgba(12, 15, 28, 0.82);
	--glass-border: rgba(255, 255, 255, 0.12);
	--glass-highlight: inset 0 1px 0 rgba(255, 255, 255, 0.08);
	--glass-blur: 14px;
	--pyro: #ef7a4a;
	--hydro: #4cc2f1;
	--anemo: #5fd3b8;
	--electro: #b38cf0;
	--dendro: #9bd25a;
	--cryo: #9fe0ef;
	--geo: #f0c45a;
	--rarity-5: #e8b45a;
	--rarity-4: #a283d6;
	--pill-neutral: #8a8aa0;
	--building: #4fd1a5;
	--obtained: #8fa3ff;
	--wanted: #e8c15a;
	--unobtained: #6b6b7d;
	--warn: #f0a04b;
	--error: #ef6b6b;
	--r5: linear-gradient(160deg, #9b6a3c, #d6a253);
	--r4: linear-gradient(160deg, #5c4a8a, #9a78c9);
	--r3: linear-gradient(160deg, #3d5a8a, #5c86c6);
	--r2: linear-gradient(160deg, #3d6b52, #5a9b74);
	--r1: linear-gradient(160deg, #55555f, #77778a);
	--r0: linear-gradient(160deg, #3a3a48, #50505f);
	--sidebar-w: 76px;
	--gutter: 24px;
	color-scheme: dark;
}
* { box-sizing: border-box; }
html { background: var(--bg); }
body {
	margin: 0;
	background: transparent;
	color: var(--text);
	font: 14px/1.45 system-ui, -apple-system, 'Segoe UI', sans-serif;
}
a { color: var(--gold); }
h1 { font-size: 22px; margin: 4px 0 16px; color: var(--cream); }
h2 { font-size: 15px; text-transform: uppercase; letter-spacing: 0.06em; color: var(--muted); }
button, input, select, textarea {
	font: inherit;
	color: var(--text);
	background: rgba(255, 255, 255, 0.05);
	border: 1px solid var(--glass-border);
	border-radius: 8px;
	padding: 4px 10px;
}
button { cursor: pointer; }
button:hover:not(:disabled) { background: rgba(255, 255, 255, 0.09); }
button:disabled { opacity: 0.5; cursor: default; }
:focus-visible { outline: 2px solid var(--gold); outline-offset: 2px; }
button.primary { background: var(--gold); color: #17130b; border-color: var(--gold); font-weight: 600; }
button.primary:hover:not(:disabled) { background: var(--gold-strong); }
.panel, .glass {
	background: var(--glass-bg);
	border: 1px solid var(--glass-border);
	border-radius: 12px;
	box-shadow: var(--glass-highlight);
	-webkit-backdrop-filter: blur(var(--glass-blur)) saturate(1.2);
	backdrop-filter: blur(var(--glass-blur)) saturate(1.2);
}
.panel { padding: 14px; }
@supports not ((backdrop-filter: blur(1px)) or (-webkit-backdrop-filter: blur(1px))) {
	.panel, .glass { background: var(--glass-bg-strong); }
}
.muted { color: var(--muted); }
.error { color: var(--error); }
.chip { border-radius: 999px; padding: 2px 10px; font-size: 12px; }
.chip.on { background: var(--gold); color: #17130b; border-color: var(--gold); }
```

(`main` layout rules move to `+layout.svelte` in Task 6.)

- [ ] **Step 2: Verify**

Run: `npm run check`, `npx vitest run`, `npm run build`, `PYTHON=<python> npx playwright test`.
Expected: all pass (style-only change). Open `python run.py` and eyeball one page: panels are translucent with blur.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/app.css
git commit -m "feat(foundation): theme tokens and global frosted glass"
```

---

### Task 4: Original icon set

**Files:**
- Create: `frontend/src/lib/icons.ts`, `frontend/src/lib/Icon.svelte`
- Test: `frontend/src/lib/icons.test.ts`

**Interfaces:**
- Produces: `type IconName = 'dashboard' | 'characters' | 'teams' | 'inventory' | 'map' | 'events' | 'wishes' | 'sync' | 'profile' | 'settings' | 'external'`; `ICONS: Record<IconName, IconPath[]>` where `IconPath = { d: string; evenodd?: boolean }`; component `<Icon name={IconName} size?={number} />` (default 22, `fill="currentColor"`, `aria-hidden="true"`).

- [ ] **Step 1: Write the failing test** (`frontend/src/lib/icons.test.ts`)

```ts
import { describe, expect, it } from 'vitest';
import { ICON_NAMES, ICONS } from './icons';

describe('icons', () => {
	it('has at least one path, starting with a move, for every name', () => {
		expect(ICON_NAMES).toHaveLength(11);
		for (const name of ICON_NAMES) {
			expect(ICONS[name].length).toBeGreaterThan(0);
			for (const p of ICONS[name]) expect(p.d).toMatch(/^M/);
		}
	});
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `npx vitest run src/lib/icons.test.ts` → FAIL (module not found).

- [ ] **Step 3: Implement**

`frontend/src/lib/icons.ts`:

```ts
/** Original single-colour icons (24×24), drawn for Ad Astra in the spirit of the game's menu. Not game art. */
export interface IconPath { d: string; evenodd?: boolean }

export const ICON_NAMES = [
	'dashboard', 'characters', 'teams', 'inventory', 'map', 'events', 'wishes', 'sync', 'profile', 'settings', 'external'
] as const;
export type IconName = (typeof ICON_NAMES)[number];

export const ICONS: Record<IconName, IconPath[]> = {
	dashboard: [{ d: 'M3 3h8v10H3zM13 3h8v6h-8zM13 11h8v10h-8zM3 15h8v6H3z' }],
	characters: [
		{ d: 'M7.5 7.5a4.5 4.5 0 1 0 9 0a4.5 4.5 0 1 0-9 0z' },
		{ d: 'M3 22c0-5 4-8.5 9-8.5s9 3.5 9 8.5z' }
	],
	teams: [
		{ d: 'M4 8a3 3 0 1 0 6 0a3 3 0 1 0-6 0z' },
		{ d: 'M14 8a3 3 0 1 0 6 0a3 3 0 1 0-6 0z' },
		{ d: 'M8.6 6a3.4 3.4 0 1 0 6.8 0a3.4 3.4 0 1 0-6.8 0z' },
		{ d: 'M1 20c0-3.5 2.6-6 6-6 1.2 0 2.3.3 3.2.9A7 7 0 0 0 7.5 20z' },
		{ d: 'M23 20c0-3.5-2.6-6-6-6-1.2 0-2.3.3-3.2.9a7 7 0 0 1 2.7 5.1z' },
		{ d: 'M5.5 21c0-4 2.9-7 6.5-7s6.5 3 6.5 7z' }
	],
	inventory: [
		{ d: 'M9 2h6a2 2 0 0 1 2 2v2h-2V4H9v2H7V4a2 2 0 0 1 2-2z' },
		{ d: 'M5 6h14a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2zm3 7v2h8v-2z', evenodd: true }
	],
	map: [{ d: 'M2 5l6-2 8 3 6-2v16l-6 2-8-3-6 2zm7 0v13l6 2.2V7.2z', evenodd: true }],
	events: [{ d: 'M7 1h2v3h6V1h2v3h3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h3zM4 9v11h16V9zm2 2h4v4H6z', evenodd: true }],
	wishes: [
		{ d: 'M12 1c1 6 3 9 9.5 11C15 14 13 17 12 23c-1-6-3-9-9.5-11C9 10 11 7 12 1z' },
		{ d: 'M18.4 4a1.6 1.6 0 1 0 3.2 0a1.6 1.6 0 1 0-3.2 0z' },
		{ d: 'M3.3 19.5a1.2 1.2 0 1 0 2.4 0a1.2 1.2 0 1 0-2.4 0z' }
	],
	sync: [{ d: 'M12 3a9 9 0 0 1 8.5 6H23l-4 5-4-5h2.3A6 6 0 0 0 6.2 9.5L3.6 8A9 9 0 0 1 12 3zM12 21a9 9 0 0 1-8.5-6H1l4-5 4 5H6.7a6 6 0 0 0 11.1.5l2.6 1.5A9 9 0 0 1 12 21z' }],
	profile: [{ d: 'M3 4h18a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2zm5 3a3 3 0 1 0 0 6 3 3 0 0 0 0-6zm-4.5 10h9c0-2.5-2-4-4.5-4s-4.5 1.5-4.5 4zM14 8v2h6V8zm0 4v2h5v-2z', evenodd: true }],
	settings: [{ d: 'M10 1h4l.6 3a8 8 0 0 1 2.2 1.3l2.9-1 2 3.4-2.3 2a8 8 0 0 1 0 2.6l2.3 2-2 3.4-2.9-1A8 8 0 0 1 14.6 20l-.6 3h-4l-.6-3a8 8 0 0 1-2.2-1.3l-2.9 1-2-3.4 2.3-2a8 8 0 0 1 0-2.6l-2.3-2 2-3.4 2.9 1A8 8 0 0 1 9.4 4zm2 7a4 4 0 1 0 0 8 4 4 0 0 0 0-8z', evenodd: true }],
	external: [{ d: 'M14 3h7v7h-2V6.4l-8.3 8.3-1.4-1.4L17.6 5H14zM5 5h6v2H5v12h12v-6h2v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2z' }]
};
```

`frontend/src/lib/Icon.svelte`:

```svelte
<script lang="ts">
	import { ICONS, type IconName } from './icons';

	let { name, size = 22 }: { name: IconName; size?: number } = $props();
</script>

<svg width={size} height={size} viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false">
	{#each ICONS[name] as p, i (i)}
		<path d={p.d} fill-rule={p.evenodd ? 'evenodd' : undefined} />
	{/each}
</svg>
```

- [ ] **Step 4: Run**

Run: `npx vitest run src/lib/icons.test.ts` → PASS; `npm run check` → 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/icons.ts frontend/src/lib/Icon.svelte frontend/src/lib/icons.test.ts
git commit -m "feat(foundation): original single-colour icon set"
```

---

### Task 5: Starfield background and appearance store

**Files:**
- Create: `frontend/src/lib/starfield.ts`, `frontend/src/lib/Starfield.svelte`, `frontend/src/lib/appearance.svelte.ts`
- Test: `frontend/src/lib/starfield.test.ts`, `frontend/src/lib/appearance.test.ts`

**Interfaces:**
- Consumes: `api.settings()`, `api.saveSettings({ background_animated })` (Task 1).
- Produces:
  - `starfield.ts`: `TILE = { w: 1400, h: 900 }`; `interface Star { x: number; y: number; r: number; o: number }`; `makeStars(seed: number, count: number, rMin: number, rMax: number): Star[]`; `starTile(stars: Star[], color: string): string` (a CSS `url("data:image/svg+xml,...")`); `backgroundAnimated(setting: boolean, reducedMotion: boolean): boolean`; `LAYERS: { seed: number; count: number; r: [number, number]; color: string; seconds: number }[]`.
  - `appearance.svelte.ts`: `class AppearanceStore { backgroundAnimated: boolean (reactive, default true); load(): Promise<void>; setBackgroundAnimated(on: boolean): Promise<void> /* throws after reverting on failure */ }`; `createAppearance(loader, saver)`; singleton `appearance`.
  - `Starfield.svelte`: `<Starfield animated={boolean} />`, renders `data-testid="starfield"` with `data-animated="true|false"` (the effective value after reduced motion).

- [ ] **Step 1: Write the failing tests**

`frontend/src/lib/starfield.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { LAYERS, TILE, backgroundAnimated, makeStars, starTile } from './starfield';

describe('makeStars', () => {
	it('is deterministic for a seed and differs between seeds', () => {
		expect(makeStars(7, 50, 0.4, 1)).toEqual(makeStars(7, 50, 0.4, 1));
		expect(makeStars(7, 50, 0.4, 1)).not.toEqual(makeStars(8, 50, 0.4, 1));
	});
	it('keeps every star inside the tile, away from the edge, within the radius range', () => {
		const stars = makeStars(3, 400, 0.5, 1.5);
		expect(stars).toHaveLength(400);
		for (const s of stars) {
			expect(s.x).toBeGreaterThanOrEqual(2);
			expect(s.x).toBeLessThanOrEqual(TILE.w - 2);
			expect(s.y).toBeGreaterThanOrEqual(2);
			expect(s.y).toBeLessThanOrEqual(TILE.h - 2);
			expect(s.r).toBeGreaterThanOrEqual(0.5);
			expect(s.r).toBeLessThanOrEqual(1.5);
			expect(s.o).toBeGreaterThan(0);
			expect(s.o).toBeLessThanOrEqual(1);
		}
	});
});

describe('starTile', () => {
	it('returns an encoded SVG data URL sized to the tile with one circle per star', () => {
		const css = starTile(makeStars(1, 3, 1, 1), '#ffeccc');
		expect(css.startsWith('url("data:image/svg+xml,')).toBe(true);
		const svg = decodeURIComponent(css.slice('url("data:image/svg+xml,'.length, -2));
		expect(svg).toContain(`width="${TILE.w}"`);
		expect(svg).toContain(`height="${TILE.h}"`);
		expect(svg.match(/<circle/g)).toHaveLength(3);
		expect(svg).toContain('#ffeccc');
	});
});

describe('backgroundAnimated', () => {
	it('animates only when the setting is on and reduced motion is off', () => {
		expect(backgroundAnimated(true, false)).toBe(true);
		expect(backgroundAnimated(true, true)).toBe(false);
		expect(backgroundAnimated(false, false)).toBe(false);
		expect(backgroundAnimated(false, true)).toBe(false);
	});
});

describe('LAYERS', () => {
	it('has three layers, nearer ones faster', () => {
		expect(LAYERS.map((l) => l.seconds)).toEqual([90, 55, 35]);
	});
});
```

`frontend/src/lib/appearance.test.ts`:

```ts
import { describe, expect, it, vi } from 'vitest';
import { createAppearance } from './appearance.svelte';

describe('appearance store', () => {
	it('defaults to animated and keeps it when loading fails', async () => {
		const a = createAppearance(() => Promise.reject(new Error('down')), vi.fn());
		await a.load();
		expect(a.backgroundAnimated).toBe(true);
	});
	it('takes the saved value on load', async () => {
		const a = createAppearance(async () => ({ background_animated: false }), vi.fn());
		await a.load();
		expect(a.backgroundAnimated).toBe(false);
	});
	it('reverts and rethrows when saving fails', async () => {
		const a = createAppearance(async () => ({ background_animated: true }), () => Promise.reject(new Error('Save failed')));
		await a.load();
		await expect(a.setBackgroundAnimated(false)).rejects.toThrow('Save failed');
		expect(a.backgroundAnimated).toBe(true);
	});
	it('keeps the new value when saving works', async () => {
		const save = vi.fn().mockResolvedValue({});
		const a = createAppearance(async () => ({ background_animated: true }), save);
		await a.setBackgroundAnimated(false);
		expect(save).toHaveBeenCalledWith(false);
		expect(a.backgroundAnimated).toBe(false);
	});
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `npx vitest run src/lib/starfield.test.ts src/lib/appearance.test.ts` → FAIL (modules not found).

- [ ] **Step 3: Implement**

`frontend/src/lib/starfield.ts`:

```ts
/** Seeded star tiles for the drifting-dust background. Pure: no DOM. */
export const TILE = { w: 1400, h: 900 } as const;

export interface Star { x: number; y: number; r: number; o: number }

/** mulberry32: small, fast, deterministic PRNG returning [0, 1). */
function rng(seed: number): () => number {
	let a = seed >>> 0;
	return () => {
		a = (a + 0x6d2b79f5) >>> 0;
		let t = a;
		t = Math.imul(t ^ (t >>> 15), t | 1);
		t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
		return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
	};
}

const round = (n: number) => Math.round(n * 100) / 100;

export function makeStars(seed: number, count: number, rMin: number, rMax: number): Star[] {
	const next = rng(seed);
	return Array.from({ length: count }, () => ({
		x: round(2 + next() * (TILE.w - 4)),
		y: round(2 + next() * (TILE.h - 4)),
		r: round(rMin + next() * (rMax - rMin)),
		o: round(0.35 + next() * 0.65)
	}));
}

export function starTile(stars: Star[], color: string): string {
	const circles = stars.map((s) => `<circle cx="${s.x}" cy="${s.y}" r="${s.r}" fill-opacity="${s.o}"/>`).join('');
	const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${TILE.w}" height="${TILE.h}"><g fill="${color}">${circles}</g></svg>`;
	return `url("data:image/svg+xml,${encodeURIComponent(svg)}")`;
}

export function backgroundAnimated(setting: boolean, reducedMotion: boolean): boolean {
	return setting && !reducedMotion;
}

/** Far → near: more, smaller, dimmer, slower at the back. */
export const LAYERS: { seed: number; count: number; r: [number, number]; color: string; seconds: number }[] = [
	{ seed: 11, count: 260, r: [0.4, 0.8], color: '#ffffff', seconds: 90 },
	{ seed: 23, count: 110, r: [0.7, 1.1], color: '#dbe7ff', seconds: 55 },
	{ seed: 37, count: 40, r: [1.1, 1.6], color: '#ffeccc', seconds: 35 }
];
```

`frontend/src/lib/appearance.svelte.ts`:

```ts
import { api } from './api';

type Loader = () => Promise<{ background_animated: boolean }>;
type Saver = (on: boolean) => Promise<unknown>;

export class AppearanceStore {
	backgroundAnimated = $state(true);
	#load: Loader;
	#save: Saver;

	constructor(load: Loader, save: Saver) {
		this.#load = load;
		this.#save = save;
	}

	async load(): Promise<void> {
		try {
			this.backgroundAnimated = (await this.#load()).background_animated;
		} catch {
			/* keep the default: animated */
		}
	}

	async setBackgroundAnimated(on: boolean): Promise<void> {
		const before = this.backgroundAnimated;
		this.backgroundAnimated = on;
		try {
			await this.#save(on);
		} catch (e) {
			this.backgroundAnimated = before;
			throw e;
		}
	}
}

export function createAppearance(load: Loader, save: Saver): AppearanceStore {
	return new AppearanceStore(load, save);
}

export const appearance = createAppearance(
	() => api.settings(),
	(on) => api.saveSettings({ background_animated: on })
);
```

`frontend/src/lib/Starfield.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { LAYERS, TILE, backgroundAnimated, makeStars, starTile } from './starfield';

	let { animated }: { animated: boolean } = $props();

	let reducedMotion = $state(false);
	const moving = $derived(backgroundAnimated(animated, reducedMotion));
	const tiles = LAYERS.map((l) => ({ ...l, image: starTile(makeStars(l.seed, l.count, l.r[0], l.r[1]), l.color) }));

	onMount(() => {
		const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
		reducedMotion = mq.matches;
		const onChange = (e: MediaQueryListEvent) => (reducedMotion = e.matches);
		mq.addEventListener('change', onChange);
		return () => mq.removeEventListener('change', onChange);
	});
</script>

<div class="starfield" class:paused={!moving} data-testid="starfield" data-animated={String(moving)} aria-hidden="true"
	style="--tile-w: {TILE.w}px; --tile-h: {TILE.h}px">
	<div class="nebula"></div>
	{#each tiles as t (t.seed)}
		<div class="dust" style="background-image: {t.image}; animation-duration: {t.seconds}s"></div>
	{/each}
</div>

<style>
	.starfield { position: fixed; inset: 0; z-index: -1; overflow: hidden; pointer-events: none; background: var(--bg); }
	.nebula {
		position: absolute; inset: -20%;
		background:
			radial-gradient(ellipse 50% 35% at 70% 30%, rgba(59, 47, 107, 0.25), transparent 70%),
			radial-gradient(ellipse 45% 45% at 20% 75%, rgba(29, 74, 107, 0.25), transparent 70%);
	}
	.dust {
		position: absolute; top: 0; left: 0;
		width: calc(100% + var(--tile-w)); height: calc(100% + var(--tile-h));
		background-repeat: repeat;
		will-change: transform;
		animation-name: drift; animation-timing-function: linear; animation-iteration-count: infinite;
	}
	.paused .dust { animation-play-state: paused; }
	@media (prefers-reduced-motion: reduce) { .dust { animation: none; } }
	@keyframes drift {
		from { transform: translate3d(0, 0, 0); }
		to { transform: translate3d(calc(-1 * var(--tile-w)), calc(-1 * var(--tile-h)), 0); }
	}
</style>
```

- [ ] **Step 4: Run**

Run: `npx vitest run src/lib/starfield.test.ts src/lib/appearance.test.ts` → PASS; `npm run check` → 0 errors.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/starfield.ts frontend/src/lib/starfield.test.ts frontend/src/lib/Starfield.svelte frontend/src/lib/appearance.svelte.ts frontend/src/lib/appearance.test.ts
git commit -m "feat(foundation): drifting-dust background and appearance store"
```

---

### Task 6: Sidebar shell with sync item

**Files:**
- Create: `frontend/src/lib/nav.ts`, `frontend/src/lib/nav.test.ts`, `frontend/src/lib/Sidebar.svelte`, `frontend/src/lib/SyncItem.svelte`, `frontend/e2e/shell.spec.ts`
- Modify: `frontend/src/lib/syncLabel.ts`, `frontend/src/lib/syncLabel.test.ts`, `frontend/src/routes/+layout.svelte` (replace whole file)

**Interfaces:**
- Consumes: `Icon` (Task 4), `Starfield`, `appearance` (Task 5), `/ad-astra.svg` (Task 2), existing `sync` store and `lastFinished`, `failedParts`, `skippedNote`, `syncLabel`.
- Produces:
  - `nav.ts`: `interface NavItem { label: string; href: string; icon: IconName }`; `MAIN_NAV: NavItem[]` (Dashboard, Characters, Teams, Inventory, Map, Events, Wishes); `BOTTOM_NAV: NavItem[]` (Profile, Settings); `isActive(href: string, pathname: string): boolean`; `FLUID_ROUTES = ['/map']`; `isFluid(pathname: string): boolean`.
  - `syncLabel.ts`: `type SyncTone = 'ok' | 'warn' | 'none'`; `syncBadge(s: SyncStatus | null, now: number): { tone: SyncTone; short: string; running: boolean }`.
  - Layout: `<main class:fluid>`; fluid routes get no width cap and a full-height flex column (Task 8 relies on this).

- [ ] **Step 1: Write the failing unit tests**

`frontend/src/lib/nav.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { BOTTOM_NAV, MAIN_NAV, isActive, isFluid } from './nav';

describe('nav', () => {
	it('lists the pages in the agreed order', () => {
		expect(MAIN_NAV.map((n) => n.label)).toEqual(['Dashboard', 'Characters', 'Teams', 'Inventory', 'Map', 'Events', 'Wishes']);
		expect(BOTTOM_NAV.map((n) => n.label)).toEqual(['Profile', 'Settings']);
	});
	it('matches the dashboard only at the root', () => {
		expect(isActive('/', '/')).toBe(true);
		expect(isActive('/', '/characters')).toBe(false);
	});
	it('matches other pages by path prefix, including nested routes', () => {
		expect(isActive('/characters', '/characters/xiangling')).toBe(true);
		expect(isActive('/teams', '/teams/3')).toBe(true);
		expect(isActive('/teams', '/characters')).toBe(false);
	});
	it('does not match a page that only shares a prefix of the name', () => {
		expect(isActive('/map', '/maps-legacy')).toBe(false);
	});
	it('treats Map as a fluid page', () => {
		expect(isFluid('/map')).toBe(true);
		expect(isFluid('/settings')).toBe(false);
	});
});
```

Append to `frontend/src/lib/syncLabel.test.ts` (keep existing tests; add `syncBadge` to the existing import from `./syncLabel`):

```ts
describe('syncBadge', () => {
	const now = Date.parse('2026-11-22T12:00:00Z');
	const run = (parts: Record<string, { ok: boolean; error?: string }>, finished = '2026-11-22T11:57:00Z') =>
		({ id: 1, trigger: 'manual', started_at: finished, finished_at: finished, parts });

	it('shows nothing yet before the first status arrives', () => {
		expect(syncBadge(null, now)).toEqual({ tone: 'none', short: '…', running: false });
	});
	it('says Never when nothing has synced', () => {
		expect(syncBadge({ running: false, runs: [] } as never, now)).toEqual({ tone: 'none', short: 'Never', running: false });
	});
	it('is ok with a short age when every part succeeded', () => {
		expect(syncBadge({ running: false, runs: [run({ roster: { ok: true } })] } as never, now))
			.toEqual({ tone: 'ok', short: '3m ago', running: false });
	});
	it('warns with a count when a part failed', () => {
		expect(syncBadge({ running: false, runs: [run({ roster: { ok: true }, notes: { ok: false, error: 'x' } })] } as never, now))
			.toEqual({ tone: 'warn', short: '1 failed', running: false });
	});
	it('says Syncing while running and keeps the last tone', () => {
		expect(syncBadge({ running: true, runs: [run({ roster: { ok: true } })] } as never, now))
			.toEqual({ tone: 'ok', short: 'Syncing…', running: true });
	});
	it('uses hours and days for older syncs', () => {
		expect(syncBadge({ running: false, runs: [run({ roster: { ok: true } }, '2026-11-22T09:00:00Z')] } as never, now).short).toBe('3h ago');
		expect(syncBadge({ running: false, runs: [run({ roster: { ok: true } }, '2026-11-20T12:00:00Z')] } as never, now).short).toBe('2d ago');
		expect(syncBadge({ running: false, runs: [run({ roster: { ok: true } }, '2026-11-22T11:59:40Z')] } as never, now).short).toBe('now');
	});
});
```

(Check `SyncStatus`/`SyncRun` in `types.ts`; if the run objects need more fields to typecheck, add them with neutral values — the `as never` casts keep the test focused.)

- [ ] **Step 2: Run to verify they fail**

Run: `npx vitest run src/lib/nav.test.ts src/lib/syncLabel.test.ts` → FAIL (`nav` missing, `syncBadge` not exported).

- [ ] **Step 3: Implement helpers**

`frontend/src/lib/nav.ts`:

```ts
import type { IconName } from './icons';

export interface NavItem { label: string; href: string; icon: IconName }

export const MAIN_NAV: NavItem[] = [
	{ label: 'Dashboard', href: '/', icon: 'dashboard' },
	{ label: 'Characters', href: '/characters', icon: 'characters' },
	{ label: 'Teams', href: '/teams', icon: 'teams' },
	{ label: 'Inventory', href: '/inventory', icon: 'inventory' },
	{ label: 'Map', href: '/map', icon: 'map' },
	{ label: 'Events', href: '/events', icon: 'events' },
	{ label: 'Wishes', href: '/wishes', icon: 'wishes' }
];

export const BOTTOM_NAV: NavItem[] = [
	{ label: 'Profile', href: '/profile', icon: 'profile' },
	{ label: 'Settings', href: '/settings', icon: 'settings' }
];

export function isActive(href: string, pathname: string): boolean {
	if (href === '/') return pathname === '/';
	return pathname === href || pathname.startsWith(href + '/');
}

/** Pages that opt out of the 1600px cap and fill the window height. */
export const FLUID_ROUTES = ['/map'];

export function isFluid(pathname: string): boolean {
	return FLUID_ROUTES.some((r) => isActive(r, pathname));
}
```

Add to `frontend/src/lib/syncLabel.ts`:

```ts
export type SyncTone = 'ok' | 'warn' | 'none';

function shortAgo(iso: string, now: number): string {
	const m = Math.floor((now - Date.parse(iso)) / 60_000);
	if (m < 1) return 'now';
	if (m < 60) return `${m}m ago`;
	const h = Math.floor(m / 60);
	if (h < 24) return `${h}h ago`;
	return `${Math.floor(h / 24)}d ago`;
}

/** Sidebar sync item: a status dot tone and a label short enough for 76px. */
export function syncBadge(s: SyncStatus | null, now: number): { tone: SyncTone; short: string; running: boolean } {
	if (!s) return { tone: 'none', short: '…', running: false };
	const last = lastFinished(s);
	const failed = last ? failedParts(last).length : 0;
	const tone: SyncTone = !last ? 'none' : failed ? 'warn' : 'ok';
	if (s.running) return { tone, short: 'Syncing…', running: true };
	if (!last) return { tone, short: 'Never', running: false };
	return { tone, short: failed ? `${failed} failed` : shortAgo(last.finished_at!, now), running: false };
}
```

- [ ] **Step 4: Run unit tests** → `npx vitest run src/lib/nav.test.ts src/lib/syncLabel.test.ts` PASS.

- [ ] **Step 5: Write the failing Playwright test** (`frontend/e2e/shell.spec.ts`)

```ts
import { expect, test } from '@playwright/test';

const PAGES = [
	['Dashboard', '/'], ['Characters', '/characters'], ['Teams', '/teams'], ['Inventory', '/inventory'],
	['Map', '/map'], ['Events', '/events'], ['Wishes', '/wishes'], ['Profile', '/profile'], ['Settings', '/settings']
] as const;

test('the sidebar reaches every page and marks only the current one', async ({ page }) => {
	await page.goto('/');
	const nav = page.getByRole('navigation', { name: 'Main' });
	await expect(nav.getByRole('img', { name: 'Ad Astra' })).toBeVisible();
	for (const [label, path] of PAGES) {
		await nav.getByRole('link', { name: label, exact: true }).click();
		await expect(page).toHaveURL(new RegExp(`${path === '/' ? '/$' : path + '$'}`));
		await expect(nav.locator('[aria-current="page"]')).toHaveCount(1);
		await expect(nav.getByRole('link', { name: label, exact: true })).toHaveAttribute('aria-current', 'page');
	}
});

test('a nested character page keeps Characters active', async ({ page }) => {
	await page.goto('/characters/xiangling');
	const nav = page.getByRole('navigation', { name: 'Main' });
	await expect(nav.getByRole('link', { name: 'Characters', exact: true })).toHaveAttribute('aria-current', 'page');
	await expect(nav.getByRole('link', { name: 'Dashboard', exact: true })).not.toHaveAttribute('aria-current', 'page');
});

test('the sync item opens details with a Sync now button', async ({ page }) => {
	await page.goto('/');
	await page.getByTestId('sync-label').click();
	await expect(page.getByTestId('sync-popover')).toBeVisible();
	await expect(page.getByTestId('sync-popover').getByRole('button', { name: 'Sync now' })).toBeVisible();
	await page.getByTestId('sync-label').click();
	await expect(page.getByTestId('sync-popover')).toHaveCount(0);
});
```

Run: `PYTHON=<python> npx playwright test e2e/shell.spec.ts` → FAIL (no "Main" navigation).

- [ ] **Step 6: Implement components and layout**

`frontend/src/lib/SyncItem.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import Icon from './Icon.svelte';
	import { sync } from './sync.svelte';
	import { lastFinished, skippedNote, syncBadge, syncLabel } from './syncLabel';

	let now = $state(Date.now());
	let open = $state(false);
	const badge = $derived(syncBadge(sync.status, now));
	const last = $derived(lastFinished(sync.status));

	onMount(() => {
		const t = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(t);
	});
</script>

<div class="sync">
	<button type="button" class="item" data-testid="sync-label" aria-expanded={open}
		title={syncLabel(sync.status, now)} onclick={() => (open = !open)}>
		<span class="icon" class:spin={badge.running}><Icon name="sync" /></span>
		{#if badge.tone !== 'none'}<span class="dot {badge.tone}" aria-hidden="true"></span>{/if}
		<span class="label">{badge.short}</span>
	</button>
	{#if open}
		<div class="popover" data-testid="sync-popover">
			<div class="row">
				<b>{syncLabel(sync.status, now)}</b>
				<button type="button" class="primary" onclick={() => sync.start('manual')}
					disabled={sync.status?.running || sync.connection?.status !== 'connected'}>Sync now</button>
			</div>
			{#if last}
				<div class="muted">Last sync ({last.trigger})</div>
				{#each Object.entries(last.parts) as [name, part] (name)}
					<div>
						<b>{name}</b>:
						{#if part.ok}ok{#if skippedNote(part)} ({skippedNote(part)}){/if}{#if part.count !== undefined} ({part.count}){/if}{:else}<span class="error">{part.error}</span>{/if}
					</div>
				{/each}
			{/if}
			{#if sync.error}<div class="error">{sync.error}</div>{/if}
		</div>
	{/if}
</div>

<style>
	.sync { position: relative; width: 100%; }
	.item {
		position: relative; width: 100%; display: flex; flex-direction: column; align-items: center; gap: 3px;
		padding: 7px 0; background: none; border: none; border-radius: 0; color: var(--cream-dim); font-size: 10.5px;
	}
	.item:hover { color: var(--cream); background: none; }
	.label { max-width: 70px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
	.dot { position: absolute; top: 6px; right: 22px; width: 7px; height: 7px; border-radius: 50%; }
	.dot.ok { background: var(--building); }
	.dot.warn { background: var(--warn); }
	.spin { display: inline-flex; animation: spin 1.2s linear infinite; }
	@media (prefers-reduced-motion: reduce) { .spin { animation: none; } }
	@keyframes spin { to { transform: rotate(360deg); } }
	.popover {
		position: absolute; left: calc(100% + 10px); bottom: 0; z-index: 50; min-width: 280px; padding: 12px;
		font-size: 12px; background: var(--glass-bg-strong); border: 1px solid var(--glass-border); border-radius: 12px;
		box-shadow: 0 8px 24px rgba(0, 0, 0, 0.5); backdrop-filter: blur(var(--glass-blur));
	}
	.row { display: flex; justify-content: space-between; align-items: center; gap: 10px; margin-bottom: 8px; }
</style>
```

`frontend/src/lib/Sidebar.svelte`:

```svelte
<script lang="ts">
	import { page } from '$app/state';
	import Icon from './Icon.svelte';
	import SyncItem from './SyncItem.svelte';
	import { BOTTOM_NAV, MAIN_NAV, isActive, type NavItem } from './nav';
</script>

{#snippet link(item: NavItem)}
	{@const active = isActive(item.href, page.url.pathname)}
	<a href={item.href} class="item" class:active aria-current={active ? 'page' : undefined}>
		<Icon name={item.icon} />
		<span>{item.label}</span>
	</a>
{/snippet}

<nav class="sidebar" aria-label="Main">
	<img class="logo" src="/ad-astra.svg" alt="Ad Astra" width="40" height="40" />
	{#each MAIN_NAV as item (item.href)}{@render link(item)}{/each}
	<div class="spacer"></div>
	<SyncItem />
	{#each BOTTOM_NAV as item (item.href)}{@render link(item)}{/each}
</nav>

<style>
	.sidebar {
		position: fixed; top: 0; left: 0; bottom: 0; width: var(--sidebar-w); z-index: 20;
		display: flex; flex-direction: column; align-items: center; padding: 12px 0;
		background: rgba(12, 15, 28, 0.6); border-right: 1px solid var(--glass-border);
		backdrop-filter: blur(var(--glass-blur));
	}
	.logo { margin-bottom: 12px; }
	.spacer { flex: 1; }
	.item {
		position: relative; width: 100%; display: flex; flex-direction: column; align-items: center; gap: 3px;
		padding: 7px 0; color: var(--cream-dim); text-decoration: none; font-size: 10.5px;
	}
	.item:hover, .item:focus-visible { color: var(--cream); }
	.item.active { color: var(--gold); }
	.item.active :global(svg) { filter: drop-shadow(0 0 6px rgba(232, 207, 156, 0.65)); }
	.item.active::before {
		content: ''; position: absolute; left: 0; top: 8px; bottom: 8px; width: 3px; border-radius: 2px; background: var(--gold);
	}
</style>
```

`frontend/src/routes/+layout.svelte` (replace the file):

```svelte
<script lang="ts">
	import '../app.css';
	import { onMount } from 'svelte';
	import { afterNavigate } from '$app/navigation';
	import { page } from '$app/state';
	import { appearance } from '$lib/appearance.svelte';
	import { isFluid } from '$lib/nav';
	import Sidebar from '$lib/Sidebar.svelte';
	import Starfield from '$lib/Starfield.svelte';
	import { sync } from '$lib/sync.svelte';

	let { children } = $props();
	const fluid = $derived(isFluid(page.url.pathname));

	onMount(() => {
		sync.loadConnection();
		appearance.load();
	});

	// "Sync on page load": every navigation asks for an auto sync; the backend decides if it's due.
	afterNavigate(() => {
		sync.start('auto');
	});
</script>

<Starfield animated={appearance.backgroundAnimated} />
<Sidebar />

<div class="content" class:fluid>
	{#if sync.connection?.status === 'expired'}
		<div class="banner warn">Your HoYoLAB login expired. <a href="/settings">Reconnect HoYoLAB</a></div>
	{:else if sync.connection?.status === 'missing'}
		<div class="banner">Not connected to HoYoLAB yet. <a href="/settings">Connect HoYoLAB</a></div>
	{/if}
	<main class:fluid>{@render children()}</main>
</div>

<style>
	.content { margin-left: var(--sidebar-w); min-height: 100vh; display: flex; flex-direction: column; }
	.content.fluid { height: 100vh; }
	main { flex: 1; width: 100%; max-width: 1600px; margin: 0 auto; padding: var(--gutter); }
	main.fluid { max-width: none; min-height: 0; display: flex; flex-direction: column; }
	.banner {
		margin: 12px var(--gutter) 0; padding: 8px 14px; border-radius: 10px;
		background: var(--glass-bg); border: 1px solid var(--glass-border);
	}
	.banner.warn { background: rgba(90, 60, 20, 0.6); border-color: rgba(240, 160, 75, 0.4); }
</style>
```

- [ ] **Step 7: Run everything**

Run: `npm run check`, `npx vitest run`, `npm run build`, `PYTHON=<python> npx playwright test`.
Expected: all pass. If an existing e2e test located something through the removed top bar, update it to use `page.getByRole('navigation', { name: 'Main' })`.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/nav.ts frontend/src/lib/nav.test.ts frontend/src/lib/syncLabel.ts frontend/src/lib/syncLabel.test.ts frontend/src/lib/Sidebar.svelte frontend/src/lib/SyncItem.svelte frontend/src/routes/+layout.svelte frontend/e2e/shell.spec.ts
git commit -m "feat(foundation): left icon sidebar shell with sync item"
```

---

### Task 7: FilterPill and element styles on Characters

**Files:**
- Create: `frontend/src/lib/elements.ts`, `frontend/src/lib/elements.test.ts`, `frontend/src/lib/FilterPill.svelte`
- Modify: `frontend/src/routes/characters/+page.svelte:68-82`, `frontend/e2e/characters.spec.ts`

**Interfaces:**
- Consumes: `ELEMENTS`, `WEAPON_TYPES` from `status.ts`; `imgSrc` from `img.ts`; tokens from Task 3.
- Produces:
  - `elements.ts`: `ELEMENT_STYLE: Record<string, { color: string; icon: string }>` (color is a `var(--pyro)`-style token); `elementStyle(name: string | null | undefined): { color: string; icon: string | null }` (unknown → neutral, `icon: null`); `RARITY_STYLE: Record<number, { color: string; ink: string }>`.
  - `<FilterPill label on color? ink? image? onclick />` → a `<button aria-pressed>`.

- [ ] **Step 1: Write the failing unit test** (`frontend/src/lib/elements.test.ts`)

```ts
import { describe, expect, it } from 'vitest';
import { ELEMENTS } from './status';
import { ELEMENT_STYLE, RARITY_STYLE, elementStyle } from './elements';

describe('elements', () => {
	it('styles every element with a colour token and its icon', () => {
		for (const el of ELEMENTS) {
			expect(ELEMENT_STYLE[el].color).toBe(`var(--${el.toLowerCase()})`);
			expect(ELEMENT_STYLE[el].icon).toMatch(/^UI_Buff_Element_/);
		}
		expect(ELEMENT_STYLE.Electro.icon).toBe('UI_Buff_Element_Electric');
		expect(ELEMENT_STYLE.Cryo.icon).toBe('UI_Buff_Element_Ice');
	});
	it('falls back to neutral for unknown or missing elements', () => {
		expect(elementStyle('Physical')).toEqual({ color: 'var(--pill-neutral)', icon: null });
		expect(elementStyle(null)).toEqual({ color: 'var(--pill-neutral)', icon: null });
	});
	it('gives 5★ gold with dark text and 4★ purple with white text', () => {
		expect(RARITY_STYLE[5]).toEqual({ color: 'var(--rarity-5)', ink: '#17130b' });
		expect(RARITY_STYLE[4]).toEqual({ color: 'var(--rarity-4)', ink: '#ffffff' });
	});
});
```

- [ ] **Step 2: Run to verify it fails** → `npx vitest run src/lib/elements.test.ts` FAIL.

- [ ] **Step 3: Implement**

`frontend/src/lib/elements.ts`:

```ts
/** Element and rarity look, shared by every page that shows them. Icons load at runtime through /api/img. */
export const ELEMENT_STYLE: Record<string, { color: string; icon: string }> = {
	Pyro: { color: 'var(--pyro)', icon: 'UI_Buff_Element_Fire' },
	Hydro: { color: 'var(--hydro)', icon: 'UI_Buff_Element_Water' },
	Anemo: { color: 'var(--anemo)', icon: 'UI_Buff_Element_Wind' },
	Electro: { color: 'var(--electro)', icon: 'UI_Buff_Element_Electric' },
	Dendro: { color: 'var(--dendro)', icon: 'UI_Buff_Element_Grass' },
	Cryo: { color: 'var(--cryo)', icon: 'UI_Buff_Element_Ice' },
	Geo: { color: 'var(--geo)', icon: 'UI_Buff_Element_Rock' }
};

export function elementStyle(name: string | null | undefined): { color: string; icon: string | null } {
	return (name && ELEMENT_STYLE[name]) || { color: 'var(--pill-neutral)', icon: null };
}

export const RARITY_STYLE: Record<number, { color: string; ink: string }> = {
	5: { color: 'var(--rarity-5)', ink: '#17130b' },
	4: { color: 'var(--rarity-4)', ink: '#ffffff' }
};
```

`frontend/src/lib/FilterPill.svelte`:

```svelte
<script lang="ts">
	import { imgSrc } from './img';

	let {
		label, on, onclick, color = 'var(--pill-neutral)', ink = '#10131f', image = null
	}: { label: string; on: boolean; onclick: () => void; color?: string; ink?: string; image?: string | null } = $props();

	let broken = $state(false);
	const src = $derived(image && !broken ? imgSrc(image) : null);
</script>

<button type="button" class="pill" class:on aria-pressed={on} style="--pill: {color}; --pill-ink: {ink}" {onclick}>
	{#if src}<img {src} alt="" width="16" height="16" onerror={() => (broken = true)} />{/if}
	{label}
</button>

<style>
	.pill {
		display: inline-flex; align-items: center; gap: 5px; border-radius: 999px; padding: 3px 11px; font-size: 12px;
		background: transparent; border: 1px solid var(--pill); color: var(--cream);
	}
	.pill:hover:not(.on) { background: color-mix(in srgb, var(--pill) 18%, transparent); }
	.pill.on { background: var(--pill); color: var(--pill-ink); font-weight: 600; }
	img { display: block; }
</style>
```

In `frontend/src/routes/characters/+page.svelte` add imports `import FilterPill from '$lib/FilterPill.svelte';` and `import { RARITY_STYLE, elementStyle } from '$lib/elements';`, then replace the three `{#each}` blocks inside `<div class="filters">` with:

```svelte
	{#each ELEMENTS as el (el)}
		<FilterPill label={el} on={filters.elements.includes(el)} color={elementStyle(el).color}
			image={elementStyle(el).icon} onclick={() => (filters.elements = toggle(filters.elements, el))} />
	{/each}
	{#each WEAPON_TYPES as w (w)}
		<FilterPill label={w} on={filters.weapons.includes(w)} onclick={() => (filters.weapons = toggle(filters.weapons, w))} />
	{/each}
	{#each [5, 4] as r (r)}
		<FilterPill label="{r}★" on={filters.rarities.includes(r)} color={RARITY_STYLE[r].color} ink={RARITY_STYLE[r].ink}
			onclick={() => (filters.rarities = toggle(filters.rarities, r))} />
	{/each}
```

- [ ] **Step 4: Add the Playwright tests** (append to `frontend/e2e/characters.spec.ts`)

```ts
test('element pills filter and report their state', async ({ page }) => {
	await page.goto('/characters');
	const pyro = page.getByRole('button', { name: 'Pyro', exact: true });
	await expect(pyro).toHaveAttribute('aria-pressed', 'false');
	await pyro.click();
	await expect(pyro).toHaveAttribute('aria-pressed', 'true');
	// dev seed: Xiangling (Pyro, obtained), Bennett (Pyro, building), Nahida (Dendro, obtained), Furina (Hydro, building)
	await expect(page.getByTestId('card-xiangling')).toBeVisible();
	await expect(page.getByTestId('card-bennett')).toBeVisible();
	await expect(page.getByTestId('card-nahida')).toHaveCount(0);
	await expect(page.getByTestId('card-furina')).toHaveCount(0);
	await pyro.click();
	await expect(pyro).toHaveAttribute('aria-pressed', 'false');
	await expect(page.getByTestId('card-nahida')).toBeVisible();
});

test('a pill whose element icon fails to load still shows its label and filters', async ({ page }) => {
	await page.route('**/api/img/UI_Buff_Element_*', (route) => route.fulfill({ status: 404, body: '' }));
	await page.goto('/characters');
	const pyro = page.getByRole('button', { name: 'Pyro', exact: true });
	await expect(pyro).toBeVisible();
	await expect(pyro.locator('img')).toHaveCount(0);
	await pyro.click();
	await expect(page.getByTestId('card-xiangling')).toBeVisible();
});
```

- [ ] **Step 5: Run**

Run: `npx vitest run`, `npm run check`, `PYTHON=<python> npx playwright test e2e/characters.spec.ts` → all PASS.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/elements.ts frontend/src/lib/elements.test.ts frontend/src/lib/FilterPill.svelte frontend/src/routes/characters/+page.svelte frontend/e2e/characters.spec.ts
git commit -m "feat(foundation): coloured filter pills with element icons on Characters"
```

---

### Task 8: Full-size Map

**Files:**
- Modify: `frontend/src/routes/map/+page.svelte` (markup from `<h1>` down and the `<style>` block), `frontend/e2e/map.spec.ts`

**Interfaces:**
- Consumes: layout `main.fluid` full-height flex column (Task 6); `Icon` name `external` (Task 4).

- [ ] **Step 1: Write the failing Playwright test** (append to `frontend/e2e/map.spec.ts`)

```ts
test('the embedded map fills most of the window', async ({ page }) => {
	await page.setViewportSize({ width: 1400, height: 900 });
	await page.goto('/map');
	await page.getByTestId('map-tab-appsample').click();
	const box = await page.getByTestId('map-frame').boundingBox();
	expect(box).not.toBeNull();
	expect(box!.height).toBeGreaterThan(900 * 0.8);
	expect(box!.width).toBeGreaterThan((1400 - 76) * 0.9);
});
```

Run: `PYTHON=<python> npx playwright test e2e/map.spec.ts` → the new test FAILS on the height check (today the frame is `100vh - 220px` = 680px, under 720px).

- [ ] **Step 2: Implement**

Keep the `<script>` unchanged except adding `import Icon from '$lib/Icon.svelte';`. Replace the markup and styles:

```svelte
<div class="map-page">
	{#if error}<p class="error">{error}</p>{/if}
	{#if data}
		<div class="bar glass">
			<h1>Map</h1>
			<div class="tabs" role="tablist" aria-label="Maps">
				{#each data.maps as m (m.key)}
					<button type="button" role="tab" class="chip" class:on={tab === m.key} aria-selected={tab === m.key}
						id="map-tab-{m.key}" aria-controls="map-panel" tabindex={tab === m.key ? 0 : -1} onkeydown={keydown}
						data-testid="map-tab-{m.key}" onclick={() => choose(m.key)}>{m.name}</button>
				{/each}
			</div>
			{#if current}
				<a class="open" href={current.url} target="_blank" rel="noopener noreferrer">
					Open in new tab <Icon name="external" size={14} />
				</a>
			{/if}
		</div>
		{#if current}
			<div class="panel-area" role="tabpanel" id="map-panel" aria-labelledby="map-tab-{current.key}">
				{#if current.allowed === false}
					<section class="panel fallback" data-testid="map-fallback">
						<p>This map doesn't allow embedding</p>
						<a class="big" href={current.url} target="_blank" rel="noopener noreferrer">Open in new tab</a>
					</section>
				{:else}
					{#key current.key}
						<iframe data-testid="map-frame" title={current.name} src={current.url}
							referrerpolicy="no-referrer" allow="fullscreen"></iframe>
					{/key}
				{/if}
			</div>
		{/if}
	{/if}
</div>

<style>
	.map-page { flex: 1; min-height: 600px; display: flex; flex-direction: column; gap: 10px; }
	.bar { display: flex; align-items: center; gap: 14px; padding: 8px 14px; }
	.bar h1 { margin: 0; font-size: 18px; }
	.tabs { display: flex; gap: 6px; }
	.open { margin-left: auto; display: inline-flex; align-items: center; gap: 6px; }
	.panel-area { flex: 1; min-height: 0; display: flex; flex-direction: column; }
	iframe { flex: 1; width: 100%; min-height: 540px; border: 1px solid var(--glass-border); border-radius: 12px; background: var(--glass-bg-strong); }
	.fallback { text-align: center; padding: 40px; }
	.big { display: inline-block; margin-top: 10px; padding: 10px 18px; border-radius: 8px; background: var(--gold);
		color: #17130b; font-weight: 600; text-decoration: none; }
</style>
```

The fallback's "Open in new tab" link stays inside `map-fallback`, so the existing test that scopes to it still passes; the bar link has the same accessible name but is outside that scope.

- [ ] **Step 3: Run** `PYTHON=<python> npx playwright test e2e/map.spec.ts` → all 4 PASS; `npm run check` → 0 errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/map/+page.svelte frontend/e2e/map.spec.ts
git commit -m "feat(foundation): full-size map embed"
```

---

### Task 9: Settings sections, sticky index and Appearance toggle

**Files:**
- Create: `frontend/src/lib/SettingsIndex.svelte`
- Modify: `frontend/src/routes/settings/+page.svelte` (markup and style; script gains the appearance handler), `frontend/e2e/settings.spec.ts`

**Interfaces:**
- Consumes: `appearance` store (Task 5), existing settings page state and handlers (unchanged).
- Produces: `<SettingsIndex sections={{ id: string; label: string }[]} />`; section ids `account`, `sync-data`, `appearance`, `planner`, `wishes`, `map`.

- [ ] **Step 1: Write the failing Playwright tests** (append to `frontend/e2e/settings.spec.ts`)

```ts
test('settings are grouped with an index that jumps to each section', async ({ page }) => {
	await page.goto('/settings');
	const index = page.getByRole('navigation', { name: 'Settings sections' });
	for (const label of ['Account', 'Sync & data', 'Appearance', 'Planner', 'Wishes', 'Map']) {
		await expect(index.getByRole('link', { name: label })).toBeVisible();
		await expect(page.getByRole('heading', { level: 2, name: label })).toBeVisible();
	}
	await index.getByRole('link', { name: 'Map' }).click();
	await expect(page).toHaveURL(/#map$/);
	await expect(page.getByLabel('Default map')).toBeInViewport();
});

test('turning the animated background off is remembered across reloads', async ({ page }) => {
	await page.goto('/settings');
	const toggle = page.getByLabel('Animated background');
	await expect(toggle).toBeChecked();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'true');
	await toggle.uncheck();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'false');
	await page.reload();
	await expect(page.getByLabel('Animated background')).not.toBeChecked();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'false');
	await page.getByLabel('Animated background').check();   // leave the seed as we found it
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'true');
});

test('reduced motion keeps the background still even with the setting on', async ({ page }) => {
	await page.emulateMedia({ reducedMotion: 'reduce' });
	await page.goto('/settings');
	await expect(page.getByLabel('Animated background')).toBeChecked();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'false');
});

test('a failed background save snaps the toggle back and shows the error', async ({ page }) => {
	await page.goto('/settings');
	await page.route('**/api/settings', (route) =>
		route.request().method() === 'GET'
			? route.continue()
			: route.fulfill({ status: 500, contentType: 'application/json', body: JSON.stringify({ detail: 'Save failed' }) })
	);
	const toggle = page.getByLabel('Animated background');
	await toggle.uncheck();
	await expect(page.getByTestId('appearance-note')).toHaveText('Save failed');
	await expect(toggle).toBeChecked();
	await expect(page.getByTestId('starfield')).toHaveAttribute('data-animated', 'true');
});
```

Run: `PYTHON=<python> npx playwright test e2e/settings.spec.ts` → the new tests FAIL.

Note: Playwright runs test files in parallel workers against one seeded server; the toggle test restores the setting at its end, and no other spec reads `data-animated`. If parallel runs still interfere, add `test.describe.configure({ mode: 'serial' })` around the appearance tests.

- [ ] **Step 2: Implement `SettingsIndex.svelte`**

```svelte
<script lang="ts">
	import { onMount } from 'svelte';

	let { sections }: { sections: { id: string; label: string }[] } = $props();
	let current = $state(sections[0]?.id ?? '');

	onMount(() => {
		const observer = new IntersectionObserver(
			(entries) => {
				const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top);
				if (visible[0]) current = visible[0].target.id;
			},
			{ rootMargin: '0px 0px -60% 0px' }
		);
		for (const s of sections) {
			const el = document.getElementById(s.id);
			if (el) observer.observe(el);
		}
		return () => observer.disconnect();
	});
</script>

<nav class="index glass" aria-label="Settings sections">
	{#each sections as s (s.id)}
		<a href="#{s.id}" class:current={current === s.id} aria-current={current === s.id ? 'true' : undefined}>{s.label}</a>
	{/each}
</nav>

<style>
	.index { position: sticky; top: var(--gutter); display: flex; flex-direction: column; padding: 8px; gap: 2px; }
	a { padding: 6px 12px; border-radius: 8px; color: var(--cream-dim); text-decoration: none; font-size: 13px; }
	a:hover { color: var(--cream); }
	a.current { color: var(--gold); background: rgba(232, 207, 156, 0.1); }
	@media (max-width: 900px) {
		.index { position: static; flex-direction: row; flex-wrap: wrap; }
	}
</style>
```

- [ ] **Step 3: Restructure the Settings page**

Script additions:

```ts
	import { appearance } from '$lib/appearance.svelte';
	import SettingsIndex from '$lib/SettingsIndex.svelte';

	const SECTIONS = [
		{ id: 'account', label: 'Account' },
		{ id: 'sync-data', label: 'Sync & data' },
		{ id: 'appearance', label: 'Appearance' },
		{ id: 'planner', label: 'Planner' },
		{ id: 'wishes', label: 'Wishes' },
		{ id: 'map', label: 'Map' }
	];
	let appearanceNote = $state<string | null>(null);

	async function setBackground(input: HTMLInputElement) {
		appearanceNote = null;
		try {
			await appearance.setBackgroundAnimated(input.checked);
		} catch (e) {
			input.checked = appearance.backgroundAnimated;
			appearanceNote = errorMessage(e);
		}
	}
```

Markup: keep `<h1>Settings</h1>` and the error line. Inside `{#if settings}`, wrap everything in a two-column grid and regroup the existing panels. Each old `<section class="panel">` becomes a `<div class="sub">` with its old `<h2>` turned into `<h3>`, inside a new group `<section class="panel group" id=... aria-labelledby=...>`. The GOOD block keeps `data-testid="good-settings"` on its `<div class="sub">`. Order:

```svelte
	<div class="layout">
		<SettingsIndex sections={SECTIONS} />
		<div class="groups">
			<section class="panel group" id="account" aria-labelledby="h-account">
				<h2 id="h-account">Account</h2>
				<div class="sub"><h3>HoYoLAB</h3> …existing HoYoLAB content unchanged… </div>
			</section>
			<section class="panel group" id="sync-data" aria-labelledby="h-sync-data">
				<h2 id="h-sync-data">Sync &amp; data</h2>
				<div class="sub"><h3>Sync</h3> …existing Sync content… </div>
				<div class="sub"><h3>Game data</h3> …existing Game data content… </div>
				<div class="sub" data-testid="good-settings"><h3>Inventory import (GOOD)</h3> …existing GOOD content… </div>
			</section>
			<section class="panel group" id="appearance" aria-labelledby="h-appearance">
				<h2 id="h-appearance">Appearance</h2>
				<div class="sub">
					<label class="inline">
						<input type="checkbox" checked={appearance.backgroundAnimated}
							onchange={(e) => setBackground(e.currentTarget)} />
						Animated background
					</label>
					<p class="muted">Drifting space dust behind every page. It also stays still when your system's reduce-motion setting is on.</p>
					{#if appearanceNote}<span class="error" data-testid="appearance-note">{appearanceNote}</span>{/if}
				</div>
			</section>
			<section class="panel group" id="planner" aria-labelledby="h-planner">
				<h2 id="h-planner">Planner</h2>
				<div class="sub"><h3>Default build targets</h3> …existing content… </div>
			</section>
			<section class="panel group" id="wishes" aria-labelledby="h-wishes">
				<h2 id="h-wishes">Wishes</h2>
				<div class="sub"> …existing Wishes content (no inner heading)… </div>
			</section>
			<section class="panel group" id="map" aria-labelledby="h-map">
				<h2 id="h-map">Map</h2>
				<div class="sub"> …existing Map content… </div>
			</section>
		</div>
	</div>
```

"…existing … content…" means: move the exact existing markup of that panel (everything between its `<h2>` and `</section>`) into the `<div class="sub">` without changing it. Do not leave the ellipsis text in the file.

Add to the `<style>` block (keep the existing rules):

```css
	.layout { display: grid; grid-template-columns: 200px minmax(0, 1fr); gap: 20px; align-items: start; }
	.groups { display: flex; flex-direction: column; gap: 16px; }
	.group { scroll-margin-top: var(--gutter); margin-bottom: 0; }
	.group > h2 { margin-top: 0; color: var(--cream); }
	.sub + .sub { margin-top: 14px; padding-top: 14px; border-top: 1px solid var(--glass-border); }
	h3 { font-size: 13px; margin: 0 0 8px; color: var(--muted); text-transform: uppercase; letter-spacing: 0.05em; }
	@media (max-width: 900px) { .layout { grid-template-columns: 1fr; } }
```

and change the existing `section { margin-bottom: 14px; }` rule to `section.group { margin-bottom: 0; }` (the gap handles spacing).

Check other specs for headings they rely on: `grep -rn "heading" frontend/e2e` — the GOOD spec may look for the "Inventory import (GOOD)" heading at level 2; if so, change it to level 3.

- [ ] **Step 4: Run everything**

Run: `npm run check`, `npx vitest run`, `npm run build`, `PYTHON=<python> npx playwright test`, and from `backend/` `<python> -m pytest -q`.
Expected: all pass (backend ~475, vitest all, Playwright all including the new ones).

- [ ] **Step 5: Commit**

```bash
git add frontend/src/lib/SettingsIndex.svelte frontend/src/routes/settings/+page.svelte frontend/e2e/settings.spec.ts
git commit -m "feat(foundation): grouped Settings with section index and Appearance toggle"
```

---

## Final check (controller)

- Full suite: backend pytest, `npm run check`, `npx vitest run`, `npm run build`, Playwright.
- `python run.py` and look at every page: sidebar, drifting dust, glass panels readable, Map fills the window, Settings index highlights while scrolling, toggle off stops the dust.
- `grep -rn "GenshinTracker" backend/app frontend/src run.py` returns nothing.
