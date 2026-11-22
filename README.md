# GenshinTracker

A personal, locally run Genshin Impact tracker: your roster syncs from HoYoLAB automatically,
grouped by what you're building, own, want, or don't have yet.

> Fan project. Not affiliated with or endorsed by HoYoverse. Game data comes from community
> sources (Yatta, Enka) and is downloaded at runtime; no game assets are stored in this repo.

## Requirements

- Python 3.12+
- Node.js LTS (to build the web pages)

## Setup (Windows PowerShell)

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -e "backend[dev]"
python run.py
```

Open http://127.0.0.1:8765. The first `python run.py` builds the frontend (needs `npm`).

After a `git pull`, just run `python run.py` again: it installs any new Python packages and rebuilds the
frontend when its files changed. `--no-install` and `--no-build` skip those steps.

## Connect HoYoLAB

1. Log in at hoyolab.com in your browser.
2. Press F12 → Application (Firefox: Storage) → Cookies → `https://www.hoyolab.com`.
3. In the app, open **Settings → Connect HoYoLAB** and paste `ltuid_v2`, `ltoken_v2`, `ltmid_v2`
   (and the optional ones if present).

The values are tested first, then saved only to your local `.env`, which is git-ignored.
Treat them like a password.

## Planner (phase 2)

Set characters to **Build** on the Characters page and pick targets. After each sync — and a few seconds after any
target change — the app asks HoYoLAB's calculator what is still missing:

- **Inventory** shows every upgrade material like the in-game backpack. Red `−N` = still to farm; `craft N` = you can
  craft it from spare lower tiers; `✓` = you have enough. Without a scanner import the app only knows counts for
  materials a Build character needs, so other tiles show no number.
- **Dashboard** shows domains open today (server time, reset 04:00), weekly bosses (tick them when done; they reset
  Monday 04:00 server time) and what each Build character still needs.
- **Planned weapon**: on a character's page you can plan for a weapon other than the equipped one; it is planned from
  level 1 because HoYoLAB only reports equipped weapons.

Known limits: Traveler and Manekin are not planned yet. HoYoLAB doesn't report ascension, so a character sitting
exactly at a level cap (20/40/50/60/70/80) is counted as not yet ascended — if you've already ascended them, the
next ascension's materials show as still needed until they level up.

Live check of the calculator against your account: `cd backend; ..\.venv\Scripts\python -m app.smoke --gaps`.

## Wishes

- **Import from game:** open Wish History in-game once (any banner), then press **Import from game** on the Wishes page. The link the game caches is valid for about a day; if the import says it expired, open Wish History again. If it says the cache is locked, close the game and retry. If the game cache isn't found, set the game install path in Settings.
- **Older history:** from paimon.moe, upload either its data backup (Settings → *Export data*, `paimon-moe-local-data.json`) or its *Export to Excel* `.xlsx` with **Upload file**. Backup items are matched by name to game data, so refresh game data first if the upload lists unknown items. UIGF JSON (v3/v4) from other trackers works the same way. Pulls are de-duplicated, so importing overlapping files is safe.
- **Export:** **Export UIGF** downloads your whole history as UIGF v4 JSON.
- **Backups:** before every import the database is copied to `data/backups/wishes/`, and after every import a UIGF snapshot is written there (10 of each are kept). Sync backups in `data/backups/` are separate.
- **Privacy:** the wish link's authkey is read from the game cache into memory only; it is never stored, logged, or shown.
- **Estimates:** the Capturing Radiance counter is a community estimate. Pity and the 50/50 guarantee are exact once banner data has been downloaded (Settings → Game data). Banner data comes from paimon.moe's open-source banner list (MIT).

## Teams

Group up to four characters into a team and label it with tags (for example *abyss*, *exploration*, *main*, or none for fun teams). Tags are yours to create, rename, recolour and delete under **Teams → Manage tags**.

**Build** is a built-in tag. Adding it to a team sets every member to Build, so the planner starts farming for them; adding a member to a Build team does the same for that member. Removing the tag, a member or a team never lowers a goal. If you later set a member back to Want or None, the team marks them **Not building** with a **Build again** button.

Each team with Build members shows what is still left to farm **to finish just that team**, as if it got your whole bag first. Materials other Build characters also need are marked *shared*. Build teams also appear on the Dashboard, and the Characters page can filter by team tag.

## Events, Profile and Map

**Events** shows the live banners (with your pulls on each), current in-game events with their rewards — tick **Done** to track what's left and how many primogems are still unclaimed — countdowns to the daily, weekly, Abyss, Theater and Stygian resets, and every past banner with your pulls. **Profile** shows your Battle Chronicle: account stats, exploration per region, and Spiral Abyss, Imaginarium Theater and Stygian Onslaught results. Each cycle is kept, so past runs stay listed after HoYoLAB stops showing them. **Map** embeds the HoYoLAB and AppSample maps (choose the default in Settings); if a site refuses embedding, use **Open in new tab**.

Calendar, profile and challenge data refresh with the normal sync at most once an hour; **Sync now** always fetches them.

## Development

```powershell
# backend tests (from backend/)
python -m pytest
# live check against your account (from backend/, after connecting)
python -m app.smoke
# frontend (from frontend/)
npm run dev      # http://localhost:5173, proxies /api to the backend on 8765
npm run check
npm test
npm run e2e      # needs the venv active; builds nothing, run `npm run build` first
```

Your data lives in `data/` (database, backups, image cache). Delete `data/` to start fresh.
