# Ad Astra Sub-project 7 — Wishes and Profile Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Wishes into a data-analysis page (pity tiles with soft/average marks and a guarantee arrow, one banner filter driving charts and the 5★ list) and Profile into an enka.network-style page built only from HoYoLAB data the app already fetches.

**Architecture:** A new pure module `backend/app/wishes/analysis.py` computes one analysis block per banner filter from the existing `summarize()` results; `/wishes/summary` returns it. The HoYoLAB profile snapshot keeps more fields (identity still dropped); `backend/app/profile/` gains tiles, roster and a showcase stored in the `setting` table. The frontend draws everything with hand-rolled SVG components; no chart library, no migration.

**Tech Stack:** FastAPI, SQLAlchemy 2, pytest (backend); SvelteKit with Svelte 5 runes, TypeScript, vitest, Playwright (frontend).

**Spec:** `docs/superpowers/specs/2026-11-23-ad-astra-wishes-profile-design.md`

## Global Constraints

- Cookie values only in the git-ignored `.env`; never logged, returned or committed.
- Unofficial API code stays in `backend/app/sync/` and `backend/app/wishes/`.
- Identity fields (nickname, server, avatars, UID) are dropped at sync and never stored, logged or returned. The Profile header name is the `display_name` setting, or "Traveler" when blank.
- No new external host; images only through `/api/img/<name>` and `/api/img/remote` (existing allow-list).
- Test fixtures use made-up UID 800000001 and made-up data; no game art or personal data committed; no user name, email, Windows user name or absolute user path in any committed file.
- No chart library; charts are hand-rolled SVG.
- No database migration (showcase = `setting` row `profile_showcase`; profile snapshot is JSON).
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

**Commands** (`PY` = the project venv python, `.venv/Scripts/python.exe` in the main checkout):
- Backend, from `backend/`: `PY -m pytest -q` (615 passing at start).
- Frontend, from `frontend/` (run `npm ci` first in a new worktree): `npm run check`, `npx vitest run` (163 at start), `npm run build`, `PYTHON=PY npx playwright test` (60 at start; workers 1, one shared seeded server: any test that changes state restores it).

## Review Focus

1. **Banner-less pulls** (no `game_banner` rows yet, or pulls older than the first known phase): every chart except Rotation must still render; Rotation shows "No pulls are matched to banners yet." — pinned in Task 2 (`test_analyze_without_phases`).
2. **A filter with pulls but no 5★** (e.g. Weapon Event with only 3★/4★): no light-blue mark, Luck says "No 5★ yet", histogram empty, spiders show 4★ only — pinned in Task 1 (`test_luck_without_fives`) and Task 5 e2e (weapon tile has no avg mark).
3. **Old profile snapshot** (saved before this change, no `teapot`, `areas`, `bosses`, `max_friendship`, `abyss` keys): page must render without errors and hide the missing parts — pinned in Task 7 (`test_profile_view_old_snapshot`).
4. **Showcase id no longer owned / Traveler element ids** (custom list contains a character since removed, or the Traveler's element id): skipped silently, Traveler resolves to its element entry — pinned in Task 8 (`test_showcase_skips_unowned`, Traveler in default order test).
5. **Sub-area percentages above 100 %** (genshin.py notes area exploration can exceed 100 %): display clamps to 100 — pinned in Task 6 (`test_profile_keeps_areas_bosses_teapot` clamps 1012 → 100.0).

---

## File Structure

**Backend**
- Create `backend/app/gamedata/kinds.py` — `ELEMENTS`, `WEAPON_TYPES` tuples (shared by wishes and profile).
- Create `backend/app/wishes/analysis.py` — item lookup, expected pity, luck, spider counts, phases, rotations, primogem series, `analyze()`.
- Modify `backend/app/wishes/pity.py` — `BannerWindow.version` (optional field).
- Modify `backend/app/api/wishes.py` — summary returns `analysis` and `banners`; pool payload `avg_pity`.
- Modify `backend/app/sync/chronicle.py` — wider profile dataclasses and `to_profile`.
- Modify `backend/app/profile/view.py` — header, icon tiles, regions with areas, teapot, bosses, `roster_view`.
- Create `backend/app/profile/showcase.py` — default order, entries, crit value, set summary, id validation.
- Modify `backend/app/settings/store.py` — `profile_showcase` default.
- Modify `backend/app/api/profile.py` — new keys, `PUT /profile/showcase`.
- Modify `backend/app/devseed.py` — teapot, bosses, areas, max friendship, abyss in the demo profile.
- Tests: create `backend/tests/test_wish_analysis.py`, `backend/tests/test_profile_showcase.py`; modify `test_api_wishes.py`, `test_chronicle.py`, `test_profile_view.py`, `test_api_profile.py`.

**Frontend**
- Create `frontend/src/lib/charts.ts` (+ `charts.test.ts`) — SVG geometry.
- Create `RadarChart.svelte`, `Histogram.svelte`, `LineChart.svelte` in `frontend/src/lib/`.
- Modify `frontend/src/lib/wishes.ts` (+ test), `types.ts`, `PityPanel.svelte`, `routes/wishes/+page.svelte`, `e2e/wishes.spec.ts`.
- Create `frontend/src/lib/profile.ts` (+ `profile.test.ts`) — showcase editing and display helpers.
- Modify `frontend/src/lib/icons.ts` (+ test) — 8 new stat icons.
- Create `ProfileHeader.svelte`, `Showcase.svelte`, `ShowcasePanel.svelte`, `ShowcaseEditor.svelte`, `RegionCard.svelte` in `frontend/src/lib/`.
- Modify `frontend/src/lib/api.ts`, `routes/profile/+page.svelte`, `e2e/profile.spec.ts`.

---

# Half 1 — Wishes

### Task 1: Analysis building blocks (expected pity, luck, spider counts)

**Files:**
- Create: `backend/app/gamedata/kinds.py`
- Create: `backend/app/wishes/analysis.py`
- Test: `backend/tests/test_wish_analysis.py`

**Interfaces:**
- Consumes: `app.wishes.types.PITY`, `PityRule(hard, soft, four)`; `app.wishes.pity.PullView`; models `GameCharacter`, `GameWeapon`.
- Produces:
  - `app.gamedata.kinds.ELEMENTS: tuple[str, ...]` = ("Pyro","Hydro","Anemo","Electro","Dendro","Cryo","Geo"); `WEAPON_TYPES` = ("Sword","Claymore","Polearm","Bow","Catalyst").
  - `ItemInfo(name: str, icon: str, rarity: int, element: str | None, weapon_type: str)` (frozen dataclass).
  - `load_items(session) -> dict[int, ItemInfo]`.
  - `expected_for(rule: PityRule, base: float, step: float) -> float`; `expected_pity(pool: str) -> float`.
  - `luck(fives: list[PullView], judged: list[PullView], expected: float, label: str | None) -> dict` with keys `avg_pity, expected, verdict, won, lost, rate, judged_label`.
  - `spiders(pulls: list[PullView], items: dict[int, ItemInfo]) -> tuple[dict, dict, int]` → `(elements, weapon_types, unknown)`; each dict is `{"five": {name: n}, "four": {name: n}}`, zero-filled.

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_wish_analysis.py
from app.wishes.analysis import ItemInfo, expected_for, expected_pity, luck, spiders
from app.wishes.pity import PullView
from app.wishes.types import PityRule

FURINA, NAHIDA, MIST, FAV = 10000089, 10000073, 11509, 11401
ITEMS = {FURINA: ItemInfo("Furina", "UI_AvatarIcon_Furina", 5, "Hydro", "Sword"),
         NAHIDA: ItemInfo("Nahida", "UI_AvatarIcon_Nahida", 5, "Dendro", "Catalyst"),
         MIST: ItemInfo("Mistsplitter Reforged", "UI_EquipIcon_Sword_Narukami", 5, None, "Sword"),
         FAV: ItemInfo("Favonius Sword", "UI_EquipIcon_Sword_Zephyrus", 4, None, "Sword")}


def pv(pity, outcome=None, item_id=FURINA, rarity=5, time="2024-01-15 10:00:00", pk=1):
    return PullView(pk, "x", item_id, "character", rarity, time, pity, outcome, None, None)


def test_expected_for_small_rule_and_real_pools():
    assert expected_for(PityRule(2, None, 10), 0.5, 0.0) == 1.5
    assert expected_pity("character") == 62.3
    assert expected_pity("standard") == 62.3
    assert expected_pity("weapon") == 53.3


def test_luck_verdicts_and_record():
    judged = [pv(80, "lost"), pv(10, "guaranteed"), pv(60, "won"), pv(70, "unknown")]
    out = luck(judged, judged, 62.3, "50/50")
    assert out == {"avg_pity": 55.0, "expected": 62.3, "verdict": "luckier", "won": 1, "lost": 1, "rate": 0.5,
                   "judged_label": "50/50"}
    assert luck([pv(62)], [], 62.3, None)["verdict"] == "average"
    assert luck([pv(65)], [], 62.0, None)["verdict"] == "average"            # exactly +3 is still average
    assert luck([pv(66)], [], 62.3, None)["verdict"] == "unluckier"
    assert luck([pv(59)], [], 62.0, None)["verdict"] == "average"            # exactly −3 is still average
    std = luck([pv(66)], [], 62.3, None)
    assert (std["won"], std["lost"], std["rate"], std["judged_label"]) == (None, None, None, None)


def test_luck_without_fives():
    out = luck([], [], 53.3, "75/25")
    assert out == {"avg_pity": None, "expected": 53.3, "verdict": None, "won": 0, "lost": 0, "rate": None,
                   "judged_label": "75/25"}


def test_spiders_counts_zero_fill_and_unknown():
    pulls = [pv(70, item_id=FURINA), pv(50, item_id=NAHIDA), pv(40, item_id=MIST), pv(9, item_id=FAV, rarity=4),
             pv(9, item_id=999999, rarity=4), pv(1, item_id=None, rarity=3)]
    elements, weapons, unknown = spiders(pulls, ITEMS)
    assert elements["five"] == {"Pyro": 0, "Hydro": 1, "Anemo": 0, "Electro": 0, "Dendro": 1, "Cryo": 0, "Geo": 0}
    assert sum(elements["four"].values()) == 0                        # weapons have no element
    assert weapons["five"] == {"Sword": 2, "Claymore": 0, "Polearm": 0, "Bow": 0, "Catalyst": 1}
    assert weapons["four"]["Sword"] == 1
    assert unknown == 1                                                # 3★ never counted, unknown 4★ is
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `backend/`): `PY -m pytest tests/test_wish_analysis.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.wishes.analysis'`.

- [ ] **Step 3: Write the implementation**

```python
# backend/app/gamedata/kinds.py
"""Element and weapon-type names as game data stores them (Yatta), in display order."""
ELEMENTS = ("Pyro", "Hydro", "Anemo", "Electro", "Dendro", "Cryo", "Geo")
WEAPON_TYPES = ("Sword", "Claymore", "Polearm", "Bow", "Catalyst")
```

```python
# backend/app/wishes/analysis.py
"""Wish analysis per banner filter (Ad Astra sub-project 7).
Pure functions over pity results, Wish rows and an item lookup; only load_items queries."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, GameWeapon
from app.gamedata.kinds import ELEMENTS, WEAPON_TYPES
from app.wishes.pity import PullView
from app.wishes.types import PITY, PityRule

AVERAGE_BAND = 3.0                       # ±3 pulls around the expected value counts as "average"
RATES = {"weapon": (0.007, 0.07)}        # (base 5★ rate, rise per pull from soft pity) — community model
DEFAULT_RATES = (0.006, 0.06)


@dataclass(frozen=True)
class ItemInfo:
    name: str
    icon: str
    rarity: int
    element: str | None          # characters only
    weapon_type: str


def load_items(session: Session) -> dict[int, ItemInfo]:
    items = {w.id: ItemInfo(w.name, w.icon, w.rarity, None, w.weapon_type) for w in session.scalars(select(GameWeapon))}
    items.update({c.id: ItemInfo(c.name, c.icon, c.rarity, c.element, c.weapon_type)
                  for c in session.scalars(select(GameCharacter))})
    return items


def expected_for(rule: PityRule, base: float, step: float) -> float:
    """Expected pull number of the first 5★: Σ n · P(first 5★ at n)."""
    none, total = 1.0, 0.0
    for n in range(1, rule.hard + 1):
        if n == rule.hard:
            rate = 1.0
        elif rule.soft is None or n < rule.soft:
            rate = base
        else:
            rate = min(1.0, base + step * (n - rule.soft + 1))
        total += n * none * rate
        none *= 1 - rate
    return round(total, 1)


def expected_pity(pool: str) -> float:
    base, step = RATES.get(pool, DEFAULT_RATES)
    return expected_for(PITY[pool], base, step)


def luck(fives: list[PullView], judged: list[PullView], expected: float, label: str | None) -> dict:
    avg = round(sum(p.pity for p in fives) / len(fives), 1) if fives else None
    verdict = None
    if avg is not None:
        verdict = ("luckier" if avg < expected - AVERAGE_BAND
                   else "unluckier" if avg > expected + AVERAGE_BAND else "average")
    out = {"avg_pity": avg, "expected": expected, "verdict": verdict,
           "won": None, "lost": None, "rate": None, "judged_label": label}
    if label is not None:
        won = sum(1 for p in judged if p.outcome == "won")
        lost = sum(1 for p in judged if p.outcome == "lost")
        out.update(won=won, lost=lost, rate=round(won / (won + lost), 3) if won + lost else None)
    return out


def spiders(pulls: list[PullView], items: dict[int, ItemInfo]) -> tuple[dict, dict, int]:
    elements = {"five": dict.fromkeys(ELEMENTS, 0), "four": dict.fromkeys(ELEMENTS, 0)}
    weapons = {"five": dict.fromkeys(WEAPON_TYPES, 0), "four": dict.fromkeys(WEAPON_TYPES, 0)}
    unknown = 0
    for p in pulls:
        if p.rarity not in (4, 5):
            continue
        info = items.get(p.item_id) if p.item_id is not None else None
        if info is None:
            unknown += 1
            continue
        tier = "five" if p.rarity == 5 else "four"
        if info.element in elements[tier]:
            elements[tier][info.element] += 1
        if info.weapon_type in weapons[tier]:
            weapons[tier][info.weapon_type] += 1
    return elements, weapons, unknown
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_wish_analysis.py -q`
Expected: 4 passed. (If `expected_pity("character")` is off by 0.1, the rate model was typed wrong: soft pity pull 74 must have rate 0.006 + 0.06 = 0.066.)

- [ ] **Step 5: Commit**

```bash
git add backend/app/gamedata/kinds.py backend/app/wishes/analysis.py backend/tests/test_wish_analysis.py
git commit -m "feat(wishes): expected pity, luck and spider counts for the analysis page"
```

---

### Task 2: Time series, `analyze()` and the summary API

**Files:**
- Modify: `backend/app/wishes/pity.py` (BannerWindow, banner_windows)
- Modify: `backend/app/wishes/analysis.py`
- Modify: `backend/app/api/wishes.py`
- Test: `backend/tests/test_wish_analysis.py`, `backend/tests/test_api_wishes.py`

**Interfaces:**
- Consumes: Task 1 (`ItemInfo`, `load_items`, `expected_pity`, `luck`, `spiders`); `pity.summarize`, `PoolResult` (`fives`, `fours`, `total`, `pity_at`), `stats.monthly(rows)`, `stats.pity_histogram(results)`, `stats.PRIMOGEMS_PER_PULL`, `types.POOLS`.
- Produces:
  - `BannerWindow.version: str | None = None` (new last field; `banner_windows` fills it from `GameBanner.version`).
  - `Phase(label: str, version: str, start: str)`; `load_phases(windows: list[BannerWindow]) -> list[Phase]` (character windows with a version; one phase per (version, start day); label `"7.1 ph2"`).
  - `rotations(rows: list[Wish], phases: list[Phase], items) -> list[dict]` with `{label, version, start, pool_counts, pulls, fives: [{name, icon}]}`.
  - `primogem_series(rows: list[Wish], items) -> {"points": [{date, total}], "fives": [{date, name, icon, total}]}`.
  - `analyze(results: dict[str, PoolResult], rows: list[Wish], phases: list[Phase], items) -> dict[str, dict]` keyed by `all` and each of `character`, `weapon`, `chronicled`, `standard` that has pulls. Block keys: `months, rotations, elements, weapon_types, unknown_items, pity_hist {buckets, soft, avg}, primogems, luck, fives, fours`. Pull dicts: `{name, item_id, icon, item_type, rarity, time, pity, outcome, banner, pool}`, newest first.
  - `GET /api/wishes/summary` → `{pools, overall, analysis, banners, banners_available, import}`; each pool gains `avg_pity`. `charts` is gone; `banners` is the old `charts.banners` list.

- [ ] **Step 1: Write the failing tests** (append to `backend/tests/test_wish_analysis.py`; move the new imports to the top of the file with the others)

```python
from datetime import datetime

from app.db.models import GameBanner, Wish
from app.wishes.analysis import Phase, analyze, load_phases, primogem_series, rotations
from app.wishes.pity import BannerWindow, banner_windows, summarize_pool


def wish(pk, pool, time, rarity=3, item_id=None, name="Filler"):
    return Wish(pk=pk, id=None, pool=pool, gacha_type={"character": "301", "weapon": "302", "standard": "200"}[pool],
                time=time, seq=0, name=name, item_id=item_id, item_type="character", rarity=rarity, source="game",
                imported_at=datetime(2024, 1, 1))


def window(start, version, pool="character", order=0):
    return BannerWindow(f"{pool}|{start}|{order}", pool, "B", "B", start, "2099-01-01 00:00:00", order, (FURINA,), (),
                        version)


def test_load_phases_labels_and_dedupes():
    ws = [window("2024-01-10 06:00:00", "4.3"), window("2024-01-10 06:00:00", "4.3", order=1),
          window("2024-01-31 18:00:00", "4.3"), window("2024-02-20 06:00:00", "4.4"),
          window("2024-01-01 00:00:00", None), window("2024-01-12 00:00:00", "4.3", pool="weapon")]
    assert load_phases(ws) == [Phase("4.3 ph1", "4.3", "2024-01-10 06:00:00"),
                               Phase("4.3 ph2", "4.3", "2024-01-31 18:00:00"),
                               Phase("4.4 ph1", "4.4", "2024-02-20 06:00:00")]


def test_rotations_bucket_every_pool_and_skip_early_pulls():
    phases = [Phase("4.3 ph1", "4.3", "2024-01-10 06:00:00"), Phase("4.3 ph2", "4.3", "2024-01-31 18:00:00")]
    rows = [wish(1, "standard", "2024-01-09 10:00:00"),                       # before the first phase: left out
            wish(2, "character", "2024-01-11 10:00:00", 5, FURINA, "Furina"),
            wish(3, "standard", "2024-01-20 10:00:00"),
            wish(4, "weapon", "2024-02-01 10:00:00")]
    out = rotations(rows, phases, ITEMS)
    assert out == [
        {"label": "4.3 ph1", "version": "4.3", "start": "2024-01-10 06:00:00",
         "pool_counts": {"character": 1, "standard": 1}, "pulls": 2,
         "fives": [{"name": "Furina", "icon": "UI_AvatarIcon_Furina"}]},
        {"label": "4.3 ph2", "version": "4.3", "start": "2024-01-31 18:00:00",
         "pool_counts": {"weapon": 1}, "pulls": 1, "fives": []}]


def test_primogem_series_one_point_per_day_with_five_marks():
    rows = [wish(1, "character", "2024-01-11 10:00:00"), wish(2, "character", "2024-01-11 11:00:00", 5, FURINA, "Furina"),
            wish(3, "standard", "2024-01-13 09:00:00")]
    assert primogem_series(rows, ITEMS) == {
        "points": [{"date": "2024-01-11", "total": 320}, {"date": "2024-01-13", "total": 480}],
        "fives": [{"date": "2024-01-11", "name": "Furina", "icon": "UI_AvatarIcon_Furina", "total": 320}]}


def run_summary(rows, windows):
    by_pool = {}
    for w in rows:
        by_pool.setdefault(w.pool, []).append(w)
    names = {FURINA: "Furina", NAHIDA: "Nahida", MIST: "Mistsplitter Reforged"}
    from app.wishes.types import POOLS
    return {p: summarize_pool(p, by_pool.get(p, []), [w for w in windows if w.pool == p], None,
                              "2024-02-01 00:00:00", 8, names) for p in POOLS}


def test_analyze_filters_and_blocks():
    windows = [window("2024-01-10 06:00:00", "4.3")]
    rows = ([wish(i, "character", f"2024-01-11 10:{i:02d}:00") for i in range(1, 10)]
            + [wish(10, "character", "2024-01-11 10:10:00", 5, NAHIDA, "Nahida")]                 # lost, pity 10
            + [wish(11, "weapon", "2024-01-12 10:00:00", 4, FAV, "Favonius Sword")]
            + [wish(12, "standard", "2024-01-13 10:00:00")])
    results = run_summary(rows, windows)
    out = analyze(results, rows, load_phases(windows), ITEMS)
    assert set(out) == {"all", "character", "weapon", "standard"}                # chronicled has no pulls
    ch = out["character"]
    assert ch["luck"]["avg_pity"] == 10.0 and ch["luck"]["lost"] == 1 and ch["luck"]["judged_label"] == "50/50"
    assert ch["pity_hist"] == {"buckets": ch["pity_hist"]["buckets"], "soft": 74, "avg": 10.0}
    assert ch["pity_hist"]["buckets"][0] == {"bucket": "1-10", "count": 1}
    assert ch["fives"][0]["name"] == "Nahida" and ch["fives"][0]["pool"] == "character"
    assert ch["fives"][0]["icon"] == "UI_AvatarIcon_Nahida" and ch["fives"][0]["outcome"] == "lost"
    assert ch["elements"]["five"]["Dendro"] == 1 and ch["months"][0]["character"] == 10
    assert out["weapon"]["luck"]["avg_pity"] is None and out["weapon"]["fours"][0]["name"] == "Favonius Sword"
    assert out["standard"]["luck"]["judged_label"] is None
    a = out["all"]
    assert a["luck"]["judged_label"] == "50/50 + 75/25" and a["pity_hist"]["soft"] is None
    assert a["primogems"]["points"][-1]["total"] == 12 * 160
    assert [r["pulls"] for r in a["rotations"]] == [12]
    # pull-weighted expectation: (10 * 62.3 + 1 * 53.3 + 1 * 62.3) / 12 = 61.55 → 61.5 or 61.6
    assert abs(a["luck"]["expected"] - 61.55) <= 0.051


def test_analyze_without_phases():
    rows = [wish(1, "standard", "2024-01-13 10:00:00")]
    out = analyze(run_summary(rows, []), rows, [], ITEMS)
    assert out["standard"]["rotations"] == [] and out["standard"]["months"][0]["standard"] == 1


def test_banner_windows_carry_version():
    b = GameBanner(key="character|2024-01-10 06:00:00|0", pool="character", name="B", short_name="B",
                   start="2024-01-10 06:00:00", end="2024-01-30 17:59:00", timezone_dependent=False,
                   timezone_dependent_end=False, order=0, featured_5=[], featured_4=[], version="4.3")
    assert banner_windows([b], 8)["character"][0].version == "4.3"
```

In `backend/tests/test_api_wishes.py`, inside `test_game_import_summary_history_and_dashboard`, after the line `assert summary["overall"]["pulls"] == 61 and summary["banners_available"] is False` add:

```python
        assert "charts" not in summary and summary["banners"] == []
        assert set(summary["analysis"]) == {"all", "character", "standard"}
        assert summary["analysis"]["character"]["fives"][0]["name"] == "Furina"
        assert summary["analysis"]["character"]["rotations"] == []                # no banner data
        assert pools["character"]["avg_pity"] == 1.0 and pools["standard"]["avg_pity"] is None
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_wish_analysis.py tests/test_api_wishes.py -q`
Expected: FAIL (`ImportError: cannot import name 'Phase'`; `BannerWindow` takes 9 positional arguments).

- [ ] **Step 3: Add `version` to `BannerWindow`**

In `backend/app/wishes/pity.py`, add a last field to `BannerWindow`:

```python
    featured_5: tuple[int, ...]
    featured_4: tuple[int, ...]
    version: str | None = None
```

and in `banner_windows` pass it:

```python
        out.setdefault(b.pool, []).append(BannerWindow(b.key, b.pool, b.name, b.short_name, start, end, b.order,
                                                       tuple(b.featured_5), tuple(b.featured_4), b.version))
```

- [ ] **Step 4: Add the series and `analyze()` to `analysis.py`**

Add these imports at the top of `backend/app/wishes/analysis.py` (merge with the existing ones):

```python
from bisect import bisect_right
from collections import Counter

from app.db.models import GameCharacter, GameWeapon, Wish
from app.wishes.pity import BannerWindow, PoolResult, PullView
from app.wishes.stats import PRIMOGEMS_PER_PULL, monthly, pity_histogram
from app.wishes.types import PITY, POOLS, PityRule
```

Append:

```python
FILTER_POOLS = ("character", "weapon", "chronicled", "standard")
JUDGED = {"character": "50/50", "weapon": "75/25"}


@dataclass(frozen=True)
class Phase:
    label: str          # e.g. "7.1 ph2"
    version: str
    start: str          # server-local "YYYY-MM-DD HH:MM:SS" (already shifted by banner_windows)


def load_phases(windows: list[BannerWindow]) -> list[Phase]:
    """Banner phases from the character windows: one per (version, start day), earliest start wins."""
    starts: dict[tuple[str, str], str] = {}
    for w in windows:
        if w.pool != "character" or not w.version:
            continue
        key = (w.version, w.start[:10])
        starts[key] = min(starts.get(key, w.start), w.start)
    count: Counter = Counter()
    out = []
    for (version, _day), start in sorted(starts.items(), key=lambda kv: kv[1]):
        count[version] += 1
        out.append(Phase(f"{version} ph{count[version]}", version, start))
    return out


def _icon(items: dict[int, ItemInfo], item_id: int | None) -> str | None:
    info = items.get(item_id) if item_id is not None else None
    return info.icon if info else None


def rotations(rows: list[Wish], phases: list[Phase], items: dict[int, ItemInfo]) -> list[dict]:
    """Pulls per phase. A pull belongs to the last phase that started at or before it; earlier pulls are left out."""
    starts = [p.start for p in phases]
    out: dict[int, dict] = {}
    for w in rows:
        i = bisect_right(starts, w.time) - 1
        if i < 0:
            continue
        e = out.setdefault(i, {"label": phases[i].label, "version": phases[i].version, "start": phases[i].start,
                               "pool_counts": Counter(), "pulls": 0, "fives": []})
        e["pool_counts"][w.pool] += 1
        e["pulls"] += 1
        if w.rarity == 5:
            e["fives"].append({"name": w.name, "icon": _icon(items, w.item_id)})
    return [{**e, "pool_counts": dict(e["pool_counts"])} for _i, e in sorted(out.items())]


def primogem_series(rows: list[Wish], items: dict[int, ItemInfo]) -> dict:
    points: list[dict] = []
    fives: list[dict] = []
    total = 0
    for w in rows:
        total += PRIMOGEMS_PER_PULL
        day = w.time[:10]
        if points and points[-1]["date"] == day:
            points[-1]["total"] = total
        else:
            points.append({"date": day, "total": total})
        if w.rarity == 5:
            fives.append({"date": day, "name": w.name, "icon": _icon(items, w.item_id), "total": total})
    return {"points": points, "fives": fives}


def _pull(p: PullView, pool: str, items: dict[int, ItemInfo]) -> dict:
    return {"name": p.name, "item_id": p.item_id, "icon": _icon(items, p.item_id), "item_type": p.item_type,
            "rarity": p.rarity, "time": p.time, "pity": p.pity, "outcome": p.outcome, "banner": p.banner,
            "pool": pool}


def _expected(pools: list[str], results: dict[str, PoolResult]) -> float:
    if len(pools) == 1:
        return expected_pity(pools[0])
    weights = {p: results[p].total for p in pools if results[p].total}
    total = sum(weights.values())
    return round(sum(expected_pity(p) * n for p, n in weights.items()) / total, 1) if total else expected_pity("character")


def _block(pools: list[str], results: dict[str, PoolResult], rows: list[Wish], phases: list[Phase],
           items: dict[int, ItemInfo]) -> dict:
    sub = [w for w in rows if w.pool in pools]
    fives = sorted(((p, pool) for pool in pools for p in results[pool].fives), key=lambda t: t[0].time, reverse=True)
    fours = sorted(((p, pool) for pool in pools for p in results[pool].fours), key=lambda t: t[0].time, reverse=True)
    judged = [p for pool in pools if pool in JUDGED for p in results[pool].fives]
    label = " + ".join(JUDGED[p] for p in ("character", "weapon") if p in pools) or None
    elements, weapon_types, unknown = spiders([p for p, _ in fives + fours], items)
    lk = luck([p for p, _ in fives], judged, _expected(pools, results), label)
    return {
        "months": monthly(sub),
        "rotations": rotations(sub, phases, items),
        "elements": elements, "weapon_types": weapon_types, "unknown_items": unknown,
        "pity_hist": {"buckets": pity_histogram({p: results[p] for p in pools}),
                      "soft": PITY[pools[0]].soft if len(pools) == 1 else None, "avg": lk["avg_pity"]},
        "primogems": primogem_series(sub, items),
        "luck": lk,
        "fives": [_pull(p, pool, items) for p, pool in fives],
        "fours": [_pull(p, pool, items) for p, pool in fours],
    }


def analyze(results: dict[str, PoolResult], rows: list[Wish], phases: list[Phase],
            items: dict[int, ItemInfo]) -> dict[str, dict]:
    rows = sorted(rows, key=lambda w: (w.time, w.seq, w.pk))
    present = [p for p in POOLS if p in results and results[p].total]
    if not present:
        return {}
    filters: dict[str, list[str]] = {"all": present}
    filters.update({p: [p] for p in FILTER_POOLS if p in present})
    return {f: _block(pools, results, rows, phases, items) for f, pools in filters.items()}
```

- [ ] **Step 5: Update the summary endpoint**

In `backend/app/api/wishes.py`:
- imports: replace `from app.wishes.stats import banner_timeline, monthly, overall_stats, pity_histogram, pool_stats` with
  ```python
  from app.wishes.analysis import analyze, load_items, load_phases
  from app.wishes.pity import PoolResult, PullView, banner_windows, summarize
  from app.wishes.stats import banner_timeline, overall_stats, pool_stats
  ```
  (and drop the old `from app.wishes.pity import PoolResult, PullView, summarize` line).
- in `pool_payload`, add `"avg_pity": pool_stats(r)["avg_five_pity"],` after `"stats": pool_stats(r),`.
- replace the body of `summary()` with:

```python
@router.get("/wishes/summary")
def summary(ctx: AppContext = Depends(get_ctx)) -> dict:
    offset = _offset(ctx)
    with ctx.session_factory() as s:
        results = summarize(s, utcnow(), offset)
        icons = _icons(s)
        rows = list(s.scalars(select(Wish)))
        game_banners = list(s.scalars(select(GameBanner)))
        items = load_items(s)
    phases = load_phases(banner_windows(game_banners, offset).get("character", []))
    return {
        "pools": [pool_payload(results[p], icons) for p in POOLS if results[p].total],
        "overall": overall_stats(results),
        "analysis": analyze(results, rows, phases, items),
        "banners": banner_timeline(results),
        "banners_available": bool(game_banners),
        "import": ctx.wishes.status(),
    }
```

Remove the now-unused `func` import from `sqlalchemy` if nothing else in the file uses it.

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_wish_analysis.py tests/test_api_wishes.py tests/test_wish_stats.py tests/test_wish_pity.py -q`
Expected: all pass.

- [ ] **Step 7: Run the whole backend suite**

Run: `PY -m pytest -q`
Expected: 615 + 10 new = 625 passed (number may differ by the tests you added; no failures).

- [ ] **Step 8: Commit**

```bash
git add backend/app/wishes/pity.py backend/app/wishes/analysis.py backend/app/api/wishes.py backend/tests/test_wish_analysis.py backend/tests/test_api_wishes.py
git commit -m "feat(wishes): per-filter analysis blocks in the wish summary"
```

---

### Task 3: Frontend types, chart geometry and filter helpers

**Files:**
- Modify: `frontend/src/lib/types.ts`
- Create: `frontend/src/lib/charts.ts`, `frontend/src/lib/charts.test.ts`
- Modify: `frontend/src/lib/wishes.ts`, `frontend/src/lib/wishes.test.ts`

**Interfaces:**
- Consumes: Task 2 JSON shapes.
- Produces (TypeScript):
  - types: `WishFilter`, `AnalysisPull`, `Rotation`, `TierCounts`, `Luck`, `AnalysisBlock`; `PoolSummary.avg_pity`; `WishSummary` with `analysis` and `banners` (no `charts`).
  - `charts.ts`: `ELEMENTS`, `WEAPON_TYPES`, `axisPoint(i, n, r, cx, cy)`, `radarPoints(values, max, r, cx, cy)`, `dayIndex(date)`, `lineScale(dates, maxY, width, height)`, `linePath(points, width, height)`, `pityX(pity, width, maxPity = 90)`.
  - `wishes.ts`: `FILTER_ORDER`, `FILTER_LABEL`, `availableFilters(analysis)`, `pickFilter(saved, available)`, `toFilter(pool)`, `loadWishFilter()`, `saveWishFilter(f)`, `rotationBars(rows)`, `spiderSeries(t, axes)`, `verdictLabel(v)`; `pityBar(pity, hard, soft, avg = null)` now returns `{ fill, soft, avg }`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/charts.test.ts
import { describe, expect, it } from 'vitest';
import { axisPoint, dayIndex, linePath, pityX, radarPoints } from './charts';

describe('charts', () => {
	it('places radar axes clockwise from the top', () => {
		expect(axisPoint(0, 4, 10, 50, 50)).toEqual({ x: 50, y: 40 });
		expect(axisPoint(1, 4, 10, 50, 50)).toEqual({ x: 60, y: 50 });
		expect(axisPoint(2, 4, 10, 50, 50)).toEqual({ x: 50, y: 60 });
	});
	it('scales radar values to the max and clamps', () => {
		expect(radarPoints([1, 0, 1, 0], 1, 10, 50, 50)).toBe('50,40 50,50 50,60 50,50');
		expect(radarPoints([5, 0, 0, 0], 2, 10, 50, 50)).toBe('50,40 50,50 50,50 50,50');
		expect(radarPoints([0, 0, 0], 0, 10, 50, 50)).toBe('50,50 50,50 50,50');
	});
	it('builds a line path on a day scale', () => {
		expect(dayIndex('1970-01-02')).toBe(1);
		expect(linePath([{ date: '2026-01-01', total: 160 }, { date: '2026-01-03', total: 320 }], 100, 50))
			.toBe('M0,25 L100,0');
		expect(linePath([{ date: '2026-01-01', total: 160 }], 100, 50)).toBe('M0,0');
		expect(linePath([], 100, 50)).toBe('');
	});
	it('maps pity to an x position', () => {
		expect(pityX(45, 180)).toBe(90);
		expect(pityX(120, 180)).toBe(180);
	});
});
```

In `frontend/src/lib/wishes.test.ts`:
- change the import list to also import `availableFilters, pickFilter, rotationBars, spiderSeries, toFilter, verdictLabel`;
- replace the two `pityBar` expectations with:

```ts
		expect(pityBar(45, 90, 74)).toEqual({ fill: 50, soft: 82.2, avg: null });
		expect(pityBar(120, 90, null)).toEqual({ fill: 100, soft: null, avg: null });
		expect(pityBar(10, 90, 74, 62.3)).toEqual({ fill: 11.1, soft: 82.2, avg: 69.2 });
```

- append:

```ts
describe('wish filters and analysis helpers', () => {
	it('lists filters in a fixed order and picks a sensible default', () => {
		const avail = availableFilters({ standard: {}, all: {}, character: {} });
		expect(avail).toEqual(['all', 'character', 'standard']);
		expect(pickFilter(null, avail)).toBe('character');
		expect(pickFilter('standard', avail)).toBe('standard');
		expect(pickFilter('weapon', avail)).toBe('character');          // remembered filter without pulls
		expect(pickFilter(null, ['all', 'standard'])).toBe('standard');
		expect(pickFilter(null, [])).toBe('all');
		expect(toFilter('beginner')).toBe('all');
		expect(toFilter('weapon')).toBe('weapon');
	});
	it('stacks rotation bars by pool', () => {
		const [bar] = rotationBars([{ label: '4.3 ph1', version: '4.3', start: '2024-01-10 06:00:00',
			pool_counts: { character: 3, standard: 1 }, pulls: 4, fives: [] }]);
		expect(bar.label).toBe('4.3 ph1');
		expect(bar.segments.find((s) => s.name === 'Character Event')?.value).toBe(3);
		expect(bar.segments.find((s) => s.name === 'Weapon Event')?.value).toBe(0);
	});
	it('reads spider series in axis order and labels verdicts', () => {
		expect(spiderSeries({ five: { Hydro: 2 }, four: { Pyro: 1 } }, ['Pyro', 'Hydro']))
			.toEqual({ five: [0, 2], four: [1, 0] });
		expect(verdictLabel('luckier')).toBe('Luckier than average');
		expect(verdictLabel(null)).toBe('');
	});
});
```

- [ ] **Step 2: Run the tests to verify they fail**

Run (from `frontend/`): `npx vitest run src/lib/charts.test.ts src/lib/wishes.test.ts`
Expected: FAIL (`Failed to resolve import "./charts"`; missing exports).

- [ ] **Step 3: Update `types.ts`**

Replace the `PoolSummary` and `WishSummary` interfaces and add the new types (keep `MonthRow`, `BannerRow` as they are):

```ts
export interface PoolSummary {
	pool: Pool; total: number; pity5: number; pity4: number; hard: number; soft: number | null; in_soft: boolean;
	next_state: string | null; fate: Fate | null; radiance: Radiance | null; stats: WishStats;
	avg_pity: number | null; fives: WishPull[]; fours: WishPull[];
}
export type WishFilter = 'all' | 'character' | 'weapon' | 'chronicled' | 'standard';
export interface AnalysisPull extends WishPull { pool: Pool }
export interface Rotation {
	label: string; version: string; start: string; pool_counts: Partial<Record<Pool, number>>; pulls: number;
	fives: { name: string; icon: string | null }[];
}
export interface TierCounts { five: Record<string, number>; four: Record<string, number> }
export interface Luck {
	avg_pity: number | null; expected: number; verdict: 'luckier' | 'average' | 'unluckier' | null;
	won: number | null; lost: number | null; rate: number | null; judged_label: string | null;
}
export interface AnalysisBlock {
	months: MonthRow[]; rotations: Rotation[]; elements: TierCounts; weapon_types: TierCounts; unknown_items: number;
	pity_hist: { buckets: { bucket: string; count: number }[]; soft: number | null; avg: number | null };
	primogems: { points: { date: string; total: number }[]; fives: { date: string; name: string; icon: string | null; total: number }[] };
	luck: Luck; fives: AnalysisPull[]; fours: AnalysisPull[];
}
export interface WishSummary {
	pools: PoolSummary[]; overall: WishStats; analysis: Partial<Record<WishFilter, AnalysisBlock>>;
	banners: BannerRow[]; banners_available: boolean; import: ImportStatus;
}
```

- [ ] **Step 4: Create `charts.ts`**

```ts
// frontend/src/lib/charts.ts
/** Pure SVG geometry for the hand-drawn charts (Wishes, Profile). */
export const ELEMENTS = ['Pyro', 'Hydro', 'Anemo', 'Electro', 'Dendro', 'Cryo', 'Geo'] as const;
export const WEAPON_TYPES = ['Sword', 'Claymore', 'Polearm', 'Bow', 'Catalyst'] as const;

const r1 = (n: number) => Math.round(n * 10) / 10 + 0;   // + 0 turns -0 into 0

export function axisPoint(i: number, n: number, r: number, cx: number, cy: number): { x: number; y: number } {
	const a = -Math.PI / 2 + (2 * Math.PI * i) / n;
	return { x: r1(cx + r * Math.cos(a)), y: r1(cy + r * Math.sin(a)) };
}

export function radarPoints(values: number[], max: number, r: number, cx: number, cy: number): string {
	return values
		.map((v, i) => {
			const p = axisPoint(i, values.length, max > 0 ? (Math.min(v, max) / max) * r : 0, cx, cy);
			return `${p.x},${p.y}`;
		})
		.join(' ');
}

export function dayIndex(date: string): number {
	return Math.round(Date.parse(`${date}T00:00:00Z`) / 86_400_000);
}

export function lineScale(dates: string[], maxY: number, width: number, height: number) {
	const days = dates.map(dayIndex);
	const lo = Math.min(...days);
	const span = Math.max(...days) - lo || 1;
	return {
		x: (date: string) => r1(((dayIndex(date) - lo) / span) * width),
		y: (v: number) => r1(height - (maxY > 0 ? (v / maxY) * height : 0))
	};
}

export function linePath(points: { date: string; total: number }[], width: number, height: number): string {
	if (points.length === 0) return '';
	const s = lineScale(points.map((p) => p.date), Math.max(...points.map((p) => p.total)), width, height);
	return points.map((p, i) => `${i ? 'L' : 'M'}${s.x(p.date)},${s.y(p.total)}`).join(' ');
}

export function pityX(pity: number, width: number, maxPity = 90): number {
	return r1((Math.min(pity, maxPity) / maxPity) * width);
}
```

- [ ] **Step 5: Add the helpers to `wishes.ts`**

Change the type import line to:

```ts
import type { CacheStatus, Fate, HistoryFilters, Luck, MonthRow, Outcome, PityLine, Pool, Radiance, Rotation, TierCounts, WishFilter, WishImport } from './types';
```

Replace `pityBar` with:

```ts
export function pityBar(pity: number, hard: number, soft: number | null, avg: number | null = null):
	{ fill: number; soft: number | null; avg: number | null } {
	const pct = (n: number) => Math.round((n / hard) * 1000) / 10;
	return {
		fill: Math.min(100, Math.max(0, pct(pity))), soft: soft === null ? null : pct(soft),
		avg: avg === null ? null : Math.min(100, pct(avg))
	};
}
```

Append:

```ts
export const FILTER_ORDER: WishFilter[] = ['all', 'character', 'weapon', 'chronicled', 'standard'];
export const FILTER_LABEL: Record<WishFilter, string> = {
	all: 'All banners', character: 'Character Event', weapon: 'Weapon Event', chronicled: 'Chronicled Wish',
	standard: 'Standard'
};

export function availableFilters(analysis: Partial<Record<WishFilter, unknown>>): WishFilter[] {
	return FILTER_ORDER.filter((f) => f in analysis);
}

export function pickFilter(saved: string | null, available: WishFilter[]): WishFilter {
	if (saved && (available as string[]).includes(saved)) return saved as WishFilter;
	if (available.includes('character')) return 'character';
	return available.find((f) => f !== 'all') ?? 'all';
}

export function toFilter(pool: Pool): WishFilter {
	return pool === 'beginner' ? 'all' : pool;
}

const WISH_FILTER_KEY = 'wishes.filter';

export function loadWishFilter(): string | null {
	try {
		return localStorage.getItem(WISH_FILTER_KEY);
	} catch {
		return null;
	}
}

export function saveWishFilter(f: WishFilter): void {
	try {
		localStorage.setItem(WISH_FILTER_KEY, f);
	} catch {
		/* storage unavailable: the filter just is not remembered */
	}
}

export function rotationBars(rows: Rotation[]): Bar[] {
	return rows.map((r) => ({
		label: r.label,
		segments: POOLS.map((p) => ({ name: POOL_LABEL[p], value: r.pool_counts[p] ?? 0, color: POOL_COLOR[p] }))
	}));
}

export function spiderSeries(t: TierCounts, axes: readonly string[]): { five: number[]; four: number[] } {
	return { five: axes.map((a) => t.five[a] ?? 0), four: axes.map((a) => t.four[a] ?? 0) };
}

export function verdictLabel(v: Luck['verdict']): string {
	if (v === 'luckier') return 'Luckier than average';
	if (v === 'unluckier') return 'Unluckier than average';
	if (v === 'average') return 'About average';
	return '';
}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `npx vitest run src/lib/charts.test.ts src/lib/wishes.test.ts`
Expected: PASS. (`npm run check` will still fail on `routes/wishes/+page.svelte` using `data.charts`; Task 5 replaces that page.)

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/charts.ts frontend/src/lib/charts.test.ts frontend/src/lib/wishes.ts frontend/src/lib/wishes.test.ts
git commit -m "feat(wishes): analysis types, chart geometry and filter helpers"
```

---

### Task 4: Chart components (RadarChart, Histogram, LineChart)

**Files:**
- Create: `frontend/src/lib/RadarChart.svelte`, `frontend/src/lib/Histogram.svelte`, `frontend/src/lib/LineChart.svelte`

**Interfaces:**
- Consumes: Task 3 `charts.ts`, `niceMax` from `wishes.ts`, `imgSrc` from `img.ts`.
- Produces (props):
  - `RadarChart { title: string; axes: { label: string; icon?: string | null }[]; series: { name: string; values: number[]; color: string }[]; size?: number; testid?: string }`
  - `Histogram { buckets: { bucket: string; count: number }[]; soft: number | null; avg: number | null }` (root `data-testid="pity-hist"`)
  - `LineChart { points: { date: string; total: number }[]; marks: { date: string; total: number; name: string; icon: string | null }[] }` (root `data-testid="primogems"`)

These are drawn by Task 5's page and checked by its e2e; this task's gate is `npm run check` on the three files.

- [ ] **Step 1: Create `RadarChart.svelte`**

```svelte
<!-- frontend/src/lib/RadarChart.svelte -->
<script lang="ts">
	import { axisPoint, radarPoints } from './charts';
	import { imgSrc } from './img';

	type Series = { name: string; values: number[]; color: string };
	let { title, axes, series, size = 200, testid }: {
		title: string; axes: { label: string; icon?: string | null }[]; series: Series[]; size?: number; testid?: string;
	} = $props();

	const c = $derived(size / 2);
	const R = $derived(size / 2 - 26);
	const max = $derived(Math.max(1, ...series.flatMap((s) => s.values)));
	const summary = $derived(
		series.map((s) => `${s.name}: ${axes.map((a, i) => `${a.label} ${s.values[i] ?? 0}`).join(', ')}`).join('; ')
	);
</script>

<figure data-testid={testid}>
	<figcaption>{title}</figcaption>
	<svg viewBox="0 0 {size} {size}" width="100%" style="max-width: {size}px" role="img" aria-label="{title}: {summary}">
		{#each [0.25, 0.5, 0.75, 1] as k (k)}
			<polygon class="ring" points={radarPoints(axes.map(() => k), 1, R, c, c)} />
		{/each}
		{#each axes as a, i (a.label)}
			{@const end = axisPoint(i, axes.length, R, c, c)}
			{@const at = axisPoint(i, axes.length, R + 14, c, c)}
			<line class="spoke" x1={c} y1={c} x2={end.x} y2={end.y} />
			{#if a.icon && imgSrc(a.icon)}
				<image href={imgSrc(a.icon)} x={at.x - 8} y={at.y - 8} width="16" height="16"><title>{a.label}</title></image>
			{:else}
				<text x={at.x} y={at.y + 3} text-anchor="middle">{a.label}</text>
			{/if}
		{/each}
		{#each series as s (s.name)}
			<polygon points={radarPoints(s.values, max, R, c, c)} fill={s.color} fill-opacity="0.3" stroke={s.color}
				stroke-width="1.5"><title>{s.name}</title></polygon>
		{/each}
	</svg>
	{#if series.length > 1}
		<div class="legend">
			{#each series as s (s.name)}<span><i style="background: {s.color}"></i>{s.name}</span>{/each}
		</div>
	{/if}
</figure>

<style>
	figure { margin: 0; display: flex; flex-direction: column; align-items: center; }
	figcaption { align-self: flex-start; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
	.ring { fill: none; stroke: var(--line); }
	.spoke { stroke: var(--line); }
	text { font-size: 9px; fill: var(--muted); }
	.legend { display: flex; gap: 12px; font-size: 11px; color: var(--muted); }
	.legend i { display: inline-block; width: 8px; height: 8px; border-radius: 2px; margin-right: 4px; }
</style>
```

- [ ] **Step 2: Create `Histogram.svelte`**

```svelte
<!-- frontend/src/lib/Histogram.svelte -->
<script lang="ts">
	import { pityX } from './charts';
	import { niceMax } from './wishes';

	let { buckets, soft, avg }: { buckets: { bucket: string; count: number }[]; soft: number | null; avg: number | null } = $props();
	const W = 270;
	const H = 110;
	const LABEL = 16;
	const max = $derived(niceMax(Math.max(0, ...buckets.map((b) => b.count))));
	const bw = $derived(W / Math.max(1, buckets.length));
	const h = (n: number) => (max ? (n / max) * H : 0);
	const summary = $derived(buckets.map((b) => `${b.bucket}: ${b.count}`).join(', '));
</script>

<figure data-testid="pity-hist">
	<figcaption>Where your 5★s landed</figcaption>
	{#if buckets.every((b) => b.count === 0)}
		<p class="muted">No 5★ yet.</p>
	{:else}
		<svg viewBox="0 0 {W} {H + LABEL}" width="100%" role="img" aria-label="5★ pity: {summary}">
			{#each buckets as b, i (b.bucket)}
				{#if b.count > 0}
					<rect class="bar" x={i * bw + 2} width={bw - 4} y={H - h(b.count)} height={h(b.count)}>
						<title>{b.bucket}: {b.count}</title>
					</rect>
				{/if}
				<text x={i * bw + bw / 2} y={H + 12} text-anchor="middle">{b.bucket}</text>
			{/each}
			{#if soft !== null}
				<line class="soft" x1={pityX(soft, W)} x2={pityX(soft, W)} y1="0" y2={H}><title>Soft pity from {soft}</title></line>
			{/if}
			{#if avg !== null}
				<line class="avg" x1={pityX(avg, W)} x2={pityX(avg, W)} y1="0" y2={H}><title>Your average 5★ pity: {avg}</title></line>
			{/if}
		</svg>
	{/if}
</figure>

<style>
	figure { margin: 0; }
	figcaption { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
	.bar { fill: var(--rarity-5); }
	.soft { stroke: var(--warn); stroke-width: 2; }
	.avg { stroke: var(--avg-pity); stroke-width: 2; }
	text { font-size: 8px; fill: var(--muted); }
</style>
```

- [ ] **Step 3: Create `LineChart.svelte`**

```svelte
<!-- frontend/src/lib/LineChart.svelte -->
<script lang="ts">
	import { linePath, lineScale } from './charts';

	type Point = { date: string; total: number };
	let { points, marks }: { points: Point[]; marks: (Point & { name: string; icon: string | null })[] } = $props();
	const W = 800;
	const H = 120;
	const top = $derived(Math.max(0, ...points.map((p) => p.total)));
	const scale = $derived(points.length ? lineScale(points.map((p) => p.date), top, W, H) : null);
</script>

<figure data-testid="primogems">
	<figcaption>Primogems spent{#if points.length} · <strong>{top.toLocaleString()}</strong>{/if}</figcaption>
	{#if !scale}
		<p class="muted">No pulls yet.</p>
	{:else}
		<svg viewBox="-8 -8 {W + 16} {H + 28}" width="100%" role="img"
			aria-label="Primogems spent: {top.toLocaleString()} from {points[0].date} to {points[points.length - 1].date}">
			<path class="line" d={linePath(points, W, H)} />
			{#each marks as m, i (i)}
				<circle class="mark" cx={scale.x(m.date)} cy={scale.y(m.total)} r="5"><title>{m.name} · {m.date}</title></circle>
			{/each}
			<text x="0" y={H + 18}>{points[0].date}</text>
			<text x={W} y={H + 18} text-anchor="end">{points[points.length - 1].date}</text>
		</svg>
	{/if}
</figure>

<style>
	figure { margin: 0; }
	figcaption { font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); margin-bottom: 6px; }
	figcaption strong { color: var(--cream); letter-spacing: 0; }
	.line { fill: none; stroke: var(--avg-pity); stroke-width: 2; }
	.mark { fill: var(--rarity-5); stroke: var(--bg, #070a14); stroke-width: 1.5; }
	text { font-size: 11px; fill: var(--muted); }
</style>
```

- [ ] **Step 4: Add the `--avg-pity` theme token**

Find the file that defines `--warn` on `:root` (run `grep -rn -- "--warn:" frontend/src`), and add next to it:

```css
	--avg-pity: #7cc8ff;   /* light blue: the user's average 5★ pity (sub-project 7) */
```

- [ ] **Step 5: Type-check the new files**

Run: `npm run check 2>&1 | grep -E "RadarChart|Histogram|LineChart" ; echo done`
Expected: no lines mentioning the three new files (errors in `routes/wishes/+page.svelte` about `charts` are expected until Task 5).

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/RadarChart.svelte frontend/src/lib/Histogram.svelte frontend/src/lib/LineChart.svelte <the theme file from Step 4>
git commit -m "feat(wishes): radar, histogram and line chart components"
```

---

### Task 5: Wishes page and pity tiles

**Files:**
- Modify: `frontend/src/lib/PityPanel.svelte`
- Modify: `frontend/src/routes/wishes/+page.svelte`
- Modify: `frontend/e2e/wishes.spec.ts`

**Interfaces:**
- Consumes: Tasks 2–4.
- Produces: `PityPanel` props `{ pool: PoolSummary; selected: boolean; onselect: () => void; onChart: (itemId: number | null) => void }`; test ids `pity-<pool>`, `guaranteed`, `avg-mark`, `filters`, `pulls-chart`, `luck`, `elements-radar`, `weapons-radar`, `pity-hist`, `primogems`, `five-list`, `four-list`.

- [ ] **Step 1: Write the failing e2e test**

Replace the first test in `frontend/e2e/wishes.spec.ts` with these two (keep the other tests):

```ts
test('wishes page shows pity tiles and tracks a weapon chart', async ({ page }) => {
	await page.goto('/wishes');
	const character = page.getByTestId('pity-character');
	await expect(character).toContainText('2 / 90');
	await expect(character.getByTestId('guaranteed')).toHaveCount(0);            // next 5★ is a 50/50
	await expect(character.getByTestId('avg-mark')).toHaveAttribute('title', 'Your average 5★ pity: 14');
	await expect(page.getByTestId('pity-weapon').getByTestId('avg-mark')).toHaveCount(0);   // no 5★ there
	const weapon = page.getByTestId('pity-weapon');
	await weapon.getByLabel('Charted weapon').selectOption({ label: 'Mistsplitter Reforged' });
	await expect(weapon.getByTestId('fate')).toContainText('Fate point 0/1');
	await page.reload();
	await expect(page.getByTestId('pity-weapon').getByTestId('fate')).toContainText('charted Mistsplitter Reforged');
});

test('banner filter drives the charts and the 5★ list', async ({ page }) => {
	await page.goto('/wishes');
	const filters = page.getByTestId('filters');
	await expect(filters.getByRole('button', { name: 'Character Event', pressed: true })).toBeVisible();
	await expect(page.getByTestId('five-list')).toContainText('Furina');
	await expect(page.getByTestId('luck')).toContainText('14');
	await expect(page.getByTestId('elements-radar')).toBeVisible();
	await expect(page.getByTestId('pity-hist')).toBeVisible();
	await expect(page.getByTestId('primogems')).toContainText('4,800');            // 30 character pulls × 160
	await page.getByTestId('pulls-chart').getByRole('button', { name: 'Rotation' }).click();
	await expect(page.getByTestId('pulls-chart')).toContainText('9.9 ph1');
	await filters.getByRole('button', { name: 'Standard' }).click();
	await expect(page.getByTestId('five-list')).toContainText('Kaedehara Kazuha');
	await expect(page.getByTestId('five-list')).not.toContainText('Furina');
	await page.reload();
	await expect(filters.getByRole('button', { name: 'Standard', pressed: true })).toBeVisible();  // remembered
	await page.getByTestId('pity-character').getByRole('button', { name: 'Character Event' }).click();
	await expect(filters.getByRole('button', { name: 'Character Event', pressed: true })).toBeVisible();
});
```

(The last line restores the default filter for later tests; the shared server is unaffected because the filter lives in the browser's `localStorage`.)

- [ ] **Step 2: Update `PityPanel.svelte`**

Replace the `<script>` block and the markup down to (not including) `{#if pool.radiance}` with:

```svelte
<script lang="ts">
	import type { PoolSummary } from './types';
	import { POOL_LABEL, fateLine, pityBar, radianceLine } from './wishes';

	let { pool, selected, onselect, onChart }: {
		pool: PoolSummary; selected: boolean; onselect: () => void; onChart: (itemId: number | null) => void;
	} = $props();
	const bar = $derived(pityBar(pool.pity5, pool.hard, pool.soft, pool.avg_pity));

	function change(e: Event) {
		const v = (e.currentTarget as HTMLSelectElement).value;
		onChart(v === '' ? null : Number(v));
	}
</script>

<section class="panel pity" class:selected data-testid="pity-{pool.pool}">
	<h2>
		<button type="button" class="title" aria-pressed={selected} onclick={onselect}>{POOL_LABEL[pool.pool]}</button>
		{#if pool.next_state === 'guaranteed'}
			<span class="up" data-testid="guaranteed" title="Next 5★ is guaranteed" aria-label="Next 5★ is guaranteed">▲</span>
		{/if}
	</h2>
	<div class="big">{pool.pity5}<span class="muted">&nbsp;/ {pool.hard}</span></div>
	<div class="bar" role="progressbar" aria-label="5★ pity" aria-valuenow={pool.pity5} aria-valuemin={0}
		aria-valuemax={pool.hard}>
		<span class="fill" class:soft={pool.in_soft} style="width: {bar.fill}%"></span>
		{#if bar.soft !== null}<span class="mark" style="left: {bar.soft}%" title="Soft pity from {pool.soft}"></span>{/if}
		{#if bar.avg !== null}
			<span class="mark avg" data-testid="avg-mark" style="left: {bar.avg}%" title="Your average 5★ pity: {pool.avg_pity}"></span>
		{/if}
	</div>
	<div class="muted small">4★ pity {pool.pity4} / 10{pool.in_soft ? ' · in soft pity' : ''}{pool.avg_pity !== null ? ` · avg 5★ at ${pool.avg_pity}` : ''}</div>
	<div class="bar bar4" role="progressbar" aria-label="4★ pity" aria-valuenow={pool.pity4} aria-valuemin={0}
		aria-valuemax={10}>
		<span class="fill four" style="width: {Math.min(100, (pool.pity4 / 10) * 100)}%"></span>
	</div>
```

(The old `{#if pool.next_state}<div class="state">…</div>{/if}` line is removed: the ▲ replaces it.) In `<style>`, replace `.state { font-weight: 600; }` with:

```css
	.pity.selected { border-color: var(--avg-pity); }
	h2 { display: flex; align-items: center; gap: 6px; margin: 0; }
	.title { all: unset; cursor: pointer; font: inherit; }
	.title:focus-visible { outline: 2px solid var(--avg-pity); outline-offset: 2px; border-radius: 4px; }
	.up { color: var(--rarity-5); font-size: 15px; line-height: 1; }
	.mark.avg { background: var(--avg-pity); }
```

Remove the now-unused `nextStateLabel` import (it stays exported from `wishes.ts`; the Dashboard may use it — check with `grep -rn nextStateLabel frontend/src` and leave the export).

- [ ] **Step 3: Replace the Wishes page**

Replace `frontend/src/routes/wishes/+page.svelte` entirely. The script keeps today's import/upload/export/poll/chart functions unchanged; only the imports, state, `load()` and markup change:

```svelte
<!-- frontend/src/routes/wishes/+page.svelte -->
<script lang="ts">
	import { onMount } from 'svelte';
	import BarChart from '$lib/BarChart.svelte';
	import FilterPill from '$lib/FilterPill.svelte';
	import Histogram from '$lib/Histogram.svelte';
	import LineChart from '$lib/LineChart.svelte';
	import PityPanel from '$lib/PityPanel.svelte';
	import RadarChart from '$lib/RadarChart.svelte';
	import WishHistory from '$lib/WishHistory.svelte';
	import { api, errorMessage } from '$lib/api';
	import { ELEMENTS, WEAPON_TYPES } from '$lib/charts';
	import { ELEMENT_STYLE } from '$lib/elements';
	import { imgSrc } from '$lib/img';
	import { timeAgo } from '$lib/time';
	import type { ImportStatus, Pool, WishFilter, WishSummary } from '$lib/types';
	import {
		FILTER_LABEL, POOL_LABEL, availableFilters, importResultLine, loadWishFilter, outcomeLabel, pickFilter,
		rotationBars, saveWishFilter, spiderSeries, stackedMonths, toFilter, verdictLabel
	} from '$lib/wishes';

	let data = $state<WishSummary | null>(null);
	let status = $state<ImportStatus | null>(null);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let filter = $state<WishFilter>('character');
	let byRotation = $state(false);
	let version = $state(0);
	let now = $state(Date.now());
	const running = $derived(status?.running ?? false);
	const filters = $derived(data ? availableFilters(data.analysis) : []);
	const block = $derived(data?.analysis[filter] ?? null);
	const elementAxes = ELEMENTS.map((e) => ({ label: e, icon: ELEMENT_STYLE[e].icon }));
	const weaponAxes = WEAPON_TYPES.map((w) => ({ label: w }));
	const pct = (n: number | null) => (n === null ? '—' : `${Math.round(n * 100)}%`);

	function radar(counts: { five: Record<string, number>; four: Record<string, number> }, axes: readonly string[]) {
		const s = spiderSeries(counts, axes);
		return [
			{ name: '5★', values: s.five, color: 'var(--rarity-5)' },
			{ name: '4★', values: s.four, color: 'var(--rarity-4)' }
		];
	}

	function choose(f: WishFilter) {
		filter = f;
		saveWishFilter(f);
	}

	async function load() {
		try {
			data = await api.wishSummary();
			status = data.import;
			filter = pickFilter(loadWishFilter(), availableFilters(data.analysis));
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	// onMount, poll, importGame, upload, exportUigf and setChart: copy unchanged from the current file.
</script>
```

Then copy the current file's `onMount(...)`, `poll()`, `importGame()`, `upload()`, `exportUigf()` and `setChart()` verbatim into that script in place of the comment (they do not reference `charts`). The markup after `</script>`:

```svelte
<h1>Wishes</h1>
{#if error}<p class="error">{error}</p>{/if}
{#if toast}<p class="error" role="alert">{toast}</p>{/if}

<section class="panel header">
	<button type="button" class="primary" onclick={importGame} disabled={running}>
		{running ? 'Importing…' : 'Import from game'}
	</button>
	<label class="upload">
		<span>Upload file</span>
		<input type="file" accept=".json,.xlsx" onchange={upload} disabled={running} />
	</label>
	<button type="button" onclick={exportUigf} disabled={running}>Export UIGF</button>
	<span class="muted" data-testid="import-result">
		{#if running}<span class="spinner" aria-hidden="true"></span> Importing…
		{:else if status?.last}
			{importResultLine(status.last)}{status.last.finished_at ? ` · ${timeAgo(status.last.finished_at, now)}` : ''}
		{:else}No imports yet{/if}
	</span>
</section>

{#if data}
	{#if !data.banners_available && data.pools.length}
		<p class="muted">Banner data isn't downloaded yet, so 50/50 results show as Unknown until game data refreshes.</p>
	{/if}
	{#if data.pools.length === 0}
		<section class="panel empty">
			<h2>No wishes yet</h2>
			<ol>
				<li><strong>From the game:</strong> open Wish History in-game once (any banner), then press <em>Import from game</em>. Close the game first if the import says the cache is locked.</li>
				<li><strong>From paimon.moe:</strong> Settings → Export data (the .json backup) or Export to Excel (.xlsx), then <em>Upload file</em>.</li>
				<li><strong>From another tracker:</strong> export UIGF JSON, then <em>Upload file</em>.</li>
			</ol>
		</section>
	{:else}
		<div class="tiles">
			{#each data.pools as pool (pool.pool)}
				<PityPanel {pool} selected={filter === pool.pool} onselect={() => choose(toFilter(pool.pool))}
					onChart={(id) => setChart(pool.pool, id)} />
			{/each}
		</div>

		<div class="pills" data-testid="filters" role="group" aria-label="Banner filter">
			{#each filters as f (f)}
				<FilterPill label={FILTER_LABEL[f]} on={filter === f} onclick={() => choose(f)} color="var(--avg-pity)" />
			{/each}
		</div>

		{#if block}
			<div class="row two">
				<section class="panel" data-testid="pulls-chart">
					<div class="head">
						<h2>Pulls per {byRotation ? 'rotation' : 'month'}</h2>
						<div class="toggle" role="group" aria-label="Group pulls by">
							<button type="button" aria-pressed={!byRotation} onclick={() => (byRotation = false)}>Month</button>
							<button type="button" aria-pressed={byRotation} onclick={() => (byRotation = true)}>Rotation</button>
						</div>
					</div>
					{#if byRotation && block.rotations.length === 0}
						<p class="muted">No pulls are matched to banners yet.</p>
					{:else}
						<BarChart title="" bars={byRotation ? rotationBars(block.rotations) : stackedMonths(block.months)} />
					{/if}
					{#if byRotation}
						<div class="rot-fives">
							{#each block.rotations.filter((r) => r.fives.length) as r (r.label)}
								<span class="muted">{r.label}</span>
								{#each r.fives as f, i (i)}{#if imgSrc(f.icon)}<img src={imgSrc(f.icon)} alt={f.name} title={f.name} />{/if}{/each}
							{/each}
						</div>
					{/if}
				</section>
				<section class="panel luck" data-testid="luck">
					<h2>Luck</h2>
					{#if block.luck.avg_pity === null}
						<p class="muted">No 5★ yet.</p>
					{:else}
						<div class="big">{block.luck.avg_pity}<span class="muted"> avg 5★ pity</span></div>
						<div class="muted">expected ≈ {block.luck.expected} (estimate) · <strong>{verdictLabel(block.luck.verdict)}</strong></div>
					{/if}
					{#if block.luck.judged_label}
						<div class="big">{pct(block.luck.rate)}<span class="muted"> {block.luck.judged_label} won ({block.luck.won} of {(block.luck.won ?? 0) + (block.luck.lost ?? 0)})</span></div>
					{/if}
				</section>
			</div>

			<div class="row three">
				<section class="panel">
					<RadarChart testid="elements-radar" title="Elements pulled" axes={elementAxes} series={radar(block.elements, ELEMENTS)} />
					{#if block.unknown_items}<p class="muted small">{block.unknown_items} pull(s) not in game data yet are left out.</p>{/if}
				</section>
				<section class="panel">
					<RadarChart testid="weapons-radar" title="Weapon types" axes={weaponAxes} series={radar(block.weapon_types, WEAPON_TYPES)} />
				</section>
				<section class="panel">
					<Histogram buckets={block.pity_hist.buckets} soft={block.pity_hist.soft} avg={block.pity_hist.avg} />
				</section>
			</div>

			<section class="panel">
				<LineChart points={block.primogems.points} marks={block.primogems.fives} />
			</section>

			<section class="panel">
				<h2>5★ pulled · {FILTER_LABEL[filter]}</h2>
				{#if block.fives.length === 0}<p class="muted">No 5★ yet.</p>{/if}
				<ul class="pulls" data-testid="five-list">
					{#each block.fives as p, i (`${p.time}-${i}`)}
						<li class="r5">
							{#if imgSrc(p.icon)}<img src={imgSrc(p.icon)} alt="" />{/if}
							<span class="name">{p.name}</span>
							<span class="pity">{p.pity}</span>
							{#if p.outcome}<span class="badge {p.outcome}">{outcomeLabel(p.outcome)}</span>{/if}
							{#if filter === 'all'}<span class="badge">{POOL_LABEL[p.pool as Pool]}</span>{/if}
							<span class="muted">{p.banner ?? ''} · {p.time.slice(0, 10)}</span>
						</li>
					{/each}
				</ul>
				<h2>4★</h2>
				{#if block.fours.length === 0}<p class="muted">No 4★ yet.</p>{/if}
				<ul class="pulls compact" data-testid="four-list">
					{#each block.fours as p, i (`${p.time}-${i}`)}
						<li><span class="name">{p.name}</span><span class="pity">{p.pity}</span>
							<span class="muted">{p.time.slice(0, 10)}</span></li>
					{/each}
				</ul>
			</section>
		{/if}

		<WishHistory banners={data.banners} {version} />
	{/if}
{/if}

<style>
	.header { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; }
	.upload { display: inline-flex; align-items: center; gap: 6px; cursor: pointer; }
	.upload input { max-width: 220px; }
	.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(230px, 1fr)); gap: 12px; margin: 12px 0; }
	.pills { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 12px; }
	.row { display: grid; gap: 12px; margin-bottom: 12px; }
	.row.two { grid-template-columns: 2fr 1fr; }
	.row.three { grid-template-columns: 1fr 1fr 1.3fr; }
	@media (max-width: 900px) { .row.two, .row.three { grid-template-columns: 1fr; } }
	section.panel { margin-top: 0; margin-bottom: 12px; }
	.row section.panel { margin-bottom: 0; }
	.head { display: flex; align-items: center; justify-content: space-between; gap: 8px; }
	.toggle { display: inline-flex; gap: 4px; }
	.toggle button[aria-pressed='true'] { border-color: var(--avg-pity); color: var(--avg-pity); }
	.rot-fives { display: flex; flex-wrap: wrap; align-items: center; gap: 4px; margin-top: 6px; font-size: 11px; }
	.rot-fives img { width: 22px; height: 22px; border-radius: 50%; }
	.luck .big { font-size: 24px; font-weight: 700; margin-top: 4px; }
	.luck .big .muted { font-size: 13px; font-weight: 400; }
	.small { font-size: 11px; }
	.empty ol { margin: 0; padding-left: 20px; display: grid; gap: 6px; }
	.spinner { display: inline-block; width: 10px; height: 10px; border: 2px solid var(--muted);
		border-top-color: transparent; border-radius: 50%; animation: spin 0.8s linear infinite; }
	@keyframes spin { to { transform: rotate(360deg); } }
	.pulls { list-style: none; padding: 0; margin: 0 0 12px; display: grid; gap: 6px; }
	.pulls li { display: flex; align-items: center; gap: 10px; }
	.pulls img { width: 32px; height: 32px; border-radius: 6px; background: var(--r5); }
	.pulls .name { min-width: 180px; font-weight: 600; }
	.pulls .pity { min-width: 28px; text-align: right; font-variant-numeric: tabular-nums; }
	.pulls.compact { grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); }
	.pulls.compact .name { min-width: 150px; font-weight: 400; }
	.badge { font-size: 11px; padding: 1px 6px; border-radius: 8px; background: var(--panel-2); border: 1px solid var(--line); }
	.badge.won, .badge.charted { color: var(--building); border-color: var(--building); }
	.badge.lost, .badge.not_charted { color: var(--error); border-color: var(--error); }
	.badge.guaranteed { color: var(--wanted); border-color: var(--wanted); }
</style>
```

`BarChart` prints its `title` as a figcaption; with `title=""` the panel's own `<h2>` is the heading. If `BarChart` renders an empty `<figcaption>`, that is acceptable.

- [ ] **Step 4: Check, unit tests and build**

Run (from `frontend/`): `npm run check && npx vitest run && npm run build`
Expected: 0 errors, 0 warnings; vitest all pass; build ok.

- [ ] **Step 5: Run the Wishes e2e**

Run: `PYTHON=PY npx playwright test e2e/wishes.spec.ts`
Expected: 4 passed. If the luck card shows `14.0` instead of `14`, the backend `round()` result is fine (JSON `14.0` parses to `14`); look elsewhere.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/PityPanel.svelte frontend/src/routes/wishes/+page.svelte frontend/e2e/wishes.spec.ts
git commit -m "feat(wishes): data-analysis page with banner filter, charts and guarantee arrow"
```

---

# Half 2 — Profile

### Task 6: Wider profile snapshot (identity still dropped)

**Files:**
- Modify: `backend/app/sync/chronicle.py` (profile dataclasses, `to_profile`)
- Test: `backend/tests/test_chronicle.py`

**Interfaces:**
- Consumes: genshin.py `PartialGenshinUserStats` attributes: `stats.max_friendship_characters`, `stats.spiral_abyss`, each exploration's `icon`, `area_exploration_list[].name/raw_explored`, `boss_list[].name/kills`, `offerings[].icon`, and `teapot` (`level, comfort, comfort_name, comfort_icon, items, visitors, realms[].name/icon`) or `None`.
- Produces (JSON via `to_json`, stored as the `profile` snapshot):
  - `stats` gains `max_friendship: int`, `abyss: str` ("" when absent).
  - each region gains `icon: str`, `areas: [{name, explored}]` (percent, one decimal, clamped to 100), `bosses: [{name, kills}]`; each offering gains `icon: str`.
  - top level gains `teapot: {level, comfort, comfort_name, comfort_icon, items, visitors, realms: [{name, icon}]} | null`.
  - No `nickname`, `server`, `icon`/`in_game_avatar` of the account anywhere.

- [ ] **Step 1: Write the failing test** (append to `backend/tests/test_chronicle.py`)

```python
def _user(**extra):
    stats = NS(achievements=900, days_active=1200, characters=95, spiral_abyss="12-3",
               anemoculi=66, geoculi=131, dendroculi=271, electroculi=181, hydroculi=271, pyroculi=200,
               lunoculi=0, cryoculi=0, common_chests=3000, exquisite_chests=2000, precious_chests=600,
               luxurious_chests=200, remarkable_chests=100, unlocked_waypoints=400, unlocked_domains=70,
               max_friendship_characters=40)
    base = dict(info=NS(nickname="SECRET-NICK", server="os_euro", level=60, icon="https://x.test/me.png",
                        in_game_avatar="https://x.test/avatar.png"),
                stats=stats, characters=[], teapot=None, explorations=[])
    return NS(**{**base, **extra})


def test_profile_keeps_areas_bosses_teapot():
    region = NS(id=1, parent_id=0, name="Mondstadt", raw_explored=1000, type="Reputation", level=8,
                icon="https://act-upload.hoyoverse.com/m.png",
                offerings=[NS(name="Frostbearing Tree", level=12, icon="https://act-upload.hoyoverse.com/t.png")],
                area_exploration_list=[NS(name="Starfell Valley", raw_explored=1012),
                                       NS(name="Galesong Hill", raw_explored=955)],
                boss_list=[NS(name="Stormterror", kills=12)])
    teapot = NS(level=10, comfort=21400, comfort_name="Exquisite", comfort_icon="https://act-upload.hoyoverse.com/c.png",
                items=312, visitors=40, realms=[NS(name="Emerald Peak", icon="https://act-upload.hoyoverse.com/r.png")])
    p = to_profile(_user(explorations=[region], teapot=teapot))
    assert (p.stats.max_friendship, p.stats.abyss) == (40, "12-3")
    r = p.regions[0]
    assert r.icon.endswith("/m.png") and r.offerings[0].icon.endswith("/t.png")
    assert [(a.name, a.explored) for a in r.areas] == [("Starfell Valley", 100.0), ("Galesong Hill", 95.5)]
    assert [(b.name, b.kills) for b in r.bosses] == [("Stormterror", 12)]
    assert p.teapot.level == 10 and p.teapot.comfort == 21400 and p.teapot.realms[0].name == "Emerald Peak"
    blob = str(to_json(p))
    for secret in ("SECRET-NICK", "os_euro", "me.png", "avatar.png"):
        assert secret not in blob


def test_profile_tolerates_missing_new_fields():
    region = NS(id=2, parent_id=0, name="Liyue", raw_explored=900, type="Offering", level=0, offerings=[])
    p = to_profile(_user(explorations=[region]))
    assert p.teapot is None and p.regions[0].areas == [] and p.regions[0].bosses == [] and p.regions[0].icon == ""
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_chronicle.py -q`
Expected: FAIL (`AttributeError: 'ProfileStats' object has no attribute 'max_friendship'`).

- [ ] **Step 3: Widen the dataclasses**

In `backend/app/sync/chronicle.py` replace the `Offering`, `RegionInfo`, `ProfileStats` and `ProfileInfo` dataclasses with:

```python
@dataclass(frozen=True)
class Offering:
    name: str
    level: int
    icon: str = ""


@dataclass(frozen=True)
class AreaInfo:
    name: str
    explored: float                 # percent, one decimal, clamped to 100


@dataclass(frozen=True)
class BossInfo:
    name: str
    kills: int


@dataclass(frozen=True)
class RegionInfo:
    id: int
    name: str
    explored: float                 # percent, one decimal
    reputation: int | None
    offerings: list[Offering]
    icon: str = ""
    areas: list[AreaInfo] = field(default_factory=list)
    bosses: list[BossInfo] = field(default_factory=list)


@dataclass(frozen=True)
class ProfileStats:
    ar: int
    days_active: int
    achievements: int
    characters: int
    chests: dict[str, int]
    oculi: dict[str, int]
    waypoints: int
    domains: int
    max_friendship: int = 0
    abyss: str = ""


@dataclass(frozen=True)
class TeapotRealm:
    name: str
    icon: str


@dataclass(frozen=True)
class TeapotInfo:
    level: int
    comfort: int
    comfort_name: str
    comfort_icon: str
    items: int
    visitors: int
    realms: list[TeapotRealm]


@dataclass(frozen=True)
class ProfileInfo:
    stats: ProfileStats
    regions: list[RegionInfo]
    teapot: TeapotInfo | None = None
```

- [ ] **Step 4: Widen `to_profile`**

Replace `to_profile` with:

```python
def _area_pct(raw: Any) -> float:
    return min(100.0, round(int(raw) / 10, 1))


def _teapot(t: Any) -> TeapotInfo | None:
    if t is None:
        return None
    return TeapotInfo(int(t.level), int(t.comfort), str(getattr(t, "comfort_name", "") or ""),
                      str(getattr(t, "comfort_icon", "") or ""), int(t.items), int(t.visitors),
                      [TeapotRealm(r.name, getattr(r, "icon", "") or "") for r in getattr(t, "realms", None) or []])


def to_profile(user: Any) -> ProfileInfo:
    """Identity fields (user.info nickname, server, icons) are not read here on purpose."""
    s = user.stats
    stats = ProfileStats(
        ar=int(user.info.level), days_active=int(s.days_active), achievements=int(s.achievements),
        characters=int(s.characters),
        chests={c: int(getattr(s, f"{c}_chests", 0) or 0) for c in CHESTS},
        oculi={o: int(getattr(s, o, 0) or 0) for o in OCULI},
        waypoints=int(s.unlocked_waypoints), domains=int(s.unlocked_domains),
        max_friendship=int(getattr(s, "max_friendship_characters", 0) or 0),
        abyss=str(getattr(s, "spiral_abyss", "") or ""),
    )
    regions = [RegionInfo(int(e.id), e.name, round(int(e.raw_explored) / 10, 1),
                          int(e.level) if e.type == "Reputation" else None,
                          [Offering(o.name, int(o.level), getattr(o, "icon", "") or "") for o in e.offerings],
                          getattr(e, "icon", "") or "",
                          [AreaInfo(a.name, _area_pct(a.raw_explored))
                           for a in getattr(e, "area_exploration_list", None) or []],
                          [BossInfo(b.name, int(b.kills)) for b in getattr(e, "boss_list", None) or []])
               for e in user.explorations if int(getattr(e, "parent_id", 0) or 0) == 0]
    return ProfileInfo(stats, regions, _teapot(getattr(user, "teapot", None)))
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_chronicle.py tests/test_sync_chronicle.py tests/test_sync_runner.py -q`
Expected: PASS (the existing `test_profile_drops_identity_and_maps_regions` keeps passing).

- [ ] **Step 6: Commit**

```bash
git add backend/app/sync/chronicle.py backend/tests/test_chronicle.py
git commit -m "feat(profile): keep sub-areas, boss kills, teapot, max friendship and Abyss floor at sync"
```

---

### Task 7: Profile view (header, icon tiles, regions, teapot, bosses, roster) and demo data

**Files:**
- Modify: `backend/app/profile/view.py`
- Modify: `backend/app/api/profile.py`
- Modify: `backend/app/devseed.py` (demo profile dict)
- Test: `backend/tests/test_profile_view.py`, `backend/tests/test_api_profile.py`

**Interfaces:**
- Consumes: Task 6 snapshot JSON; `app.gamedata.kinds` (Task 1); `get_setting(session, "display_name")`.
- Produces:
  - `profile_view(data: dict | None, name: str = "") -> dict | None` → `{header: {name, ar, days_active, achievements}, tiles: [{key, label, value, detail?}], regions: [{id, name, explored, reputation, icon, offerings: [{name, level, icon}], areas: [{name, explored}]}], teapot: dict | None, bosses: [{name, kills}]}`. Tile keys: `characters, friendship, waypoint, domain, abyss, chest, oculus` (a tile whose value is missing in an older snapshot is left out).
  - `roster_view(session) -> {total, elements: {el: n}, weapon_types: {type: n}, rarity: {"5": n, "4": n}, constellations, c6}`.
  - `GET /api/profile` → `profile.header`, `roster`.

- [ ] **Step 1: Write the failing tests**

In `backend/tests/test_profile_view.py` replace `test_profile_view` with the tests below and add the import `from app.db.models import ChallengeRun, OwnedCharacter` and `from app.profile.view import challenge_views, profile_view, roster_view`:

```python
NEW = {**DATA,
       "stats": {**DATA["stats"], "max_friendship": 40, "abyss": "12-3"},
       "regions": [{"id": 1, "name": "Mondstadt", "explored": 100.0, "reputation": 8, "icon": "https://x.test/m.png",
                    "offerings": [{"name": "Frostbearing Tree", "level": 12, "icon": "https://x.test/t.png"}],
                    "areas": [{"name": "Starfell Valley", "explored": 100.0}],
                    "bosses": [{"name": "Stormterror", "kills": 12}, {"name": "Anemo Hypostasis", "kills": 30}]},
                   {"id": 2, "name": "Liyue", "explored": 90.0, "reputation": 7, "offerings": [],
                    "bosses": [{"name": "Stormterror", "kills": 1}, {"name": "Azhdaha", "kills": 20}]}],
       "teapot": {"level": 10, "comfort": 21400, "comfort_name": "Exquisite", "comfort_icon": "", "items": 312,
                  "visitors": 40, "realms": []}}


def test_profile_view():
    v = profile_view(NEW, "  Lumine  ")
    assert v["header"] == {"name": "Lumine", "ar": 60, "days_active": 1200, "achievements": 900}
    tiles = {t["key"]: t for t in v["tiles"]}
    assert list(tiles) == ["characters", "friendship", "waypoint", "domain", "abyss", "chest", "oculus"]
    assert tiles["friendship"]["value"] == 40 and tiles["abyss"]["value"] == "12-3"
    assert tiles["chest"]["value"] == 5900 and tiles["chest"]["detail"][0] == {"label": "Common", "value": 3000}
    assert {"label": "Cryoculi", "value": 0} not in tiles["oculus"]["detail"]        # zero oculi types hidden
    assert tiles["oculus"]["value"] == 1120
    r = v["regions"][0]
    assert r["icon"] == "https://x.test/m.png" and r["offerings"][0]["icon"] == "https://x.test/t.png"
    assert r["areas"] == [{"name": "Starfell Valley", "explored": 100.0}]
    assert v["regions"][1]["icon"] is None and v["regions"][1]["areas"] == []
    assert v["bosses"] == [{"name": "Anemo Hypostasis", "kills": 30}, {"name": "Azhdaha", "kills": 20},
                           {"name": "Stormterror", "kills": 13}]
    assert v["teapot"]["level"] == 10
    assert profile_view(None) is None


def test_profile_view_old_snapshot():
    v = profile_view(DATA)
    assert v["header"]["name"] == "Traveler"
    assert [t["key"] for t in v["tiles"]] == ["characters", "waypoint", "domain", "chest", "oculus"]
    assert v["teapot"] is None and v["bosses"] == []
    assert v["regions"][0]["areas"] == [] and v["regions"][0]["offerings"][0]["icon"] is None


def own(s, cid, name, level=90, cons=0, element=None):
    from datetime import datetime
    s.add(OwnedCharacter(character_id=cid, name=name, element=element, icon=None, level=level, constellation=cons,
                         friendship=10, weapon_name="W", weapon_icon="", weapon_rarity=4, weapon_level=90,
                         weapon_refinement=1, stats=[], synced_at=datetime(2026, 11, 1)))


def test_roster_view(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        own(s, 10000089, "Furina", cons=6)
        own(s, 10000032, "Bennett", cons=2)
        own(s, 1000000507, "Cryo Traveler", element="Cryo")
        own(s, 424242, "Not In Game Data", element="Geo")
    with session_factory() as s:
        r = roster_view(s)
    assert r["total"] == 4 and r["constellations"] == 8 and r["c6"] == 1
    assert r["elements"]["Hydro"] == 1 and r["elements"]["Pyro"] == 1 and r["elements"]["Cryo"] == 1
    assert r["elements"]["Geo"] == 1                                   # owned row's own element still counts
    assert r["weapon_types"]["Sword"] == 3 and r["rarity"] == {"5": 2, "4": 1}
```

In `backend/tests/test_api_profile.py`, change `assert body["profile"]["ar"] == 60 and …` to:

```python
    assert body["profile"]["header"]["ar"] == 60 and body["profile"]["header"]["name"] == "Traveler"
    assert set(body["challenges"]) == {"abyss", "theater", "stygian"}
    assert body["roster"]["total"] == 0
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_profile_view.py tests/test_api_profile.py -q`
Expected: FAIL (`ImportError: cannot import name 'roster_view'`).

- [ ] **Step 3: Rewrite `profile_view` and add `roster_view`**

In `backend/app/profile/view.py` replace `TILES`, `_region` and `profile_view` with the code below and add the imports `from collections import Counter`, `from app.gamedata.kinds import ELEMENTS, WEAPON_TYPES` (keep `KINDS`, `_names`, `_run`, `challenge_views`):

```python
def _region(r: dict) -> dict:
    rep = r.get("reputation")
    return {"id": r["id"], "name": r["name"], "explored": r["explored"],
            "reputation": rep if rep is not None and rep > 0 else None, "icon": r.get("icon") or None,
            "offerings": [{"name": o["name"], "level": o["level"], "icon": o.get("icon") or None}
                          for o in r.get("offerings") or []],
            "areas": [dict(a) for a in r.get("areas") or []]}


def _bosses(regions: list[dict]) -> list[dict]:
    kills: Counter = Counter()
    for r in regions:
        for b in r.get("bosses") or []:
            kills[b["name"]] += b["kills"]
    return [{"name": n, "kills": k} for n, k in sorted(kills.items(), key=lambda kv: (-kv[1], kv[0]))]


def profile_view(data: dict | None, name: str = "") -> dict | None:
    if data is None:
        return None
    s = data["stats"]
    chests = [{"label": k.capitalize(), "value": v} for k, v in s["chests"].items()]
    oculi = [{"label": k.capitalize(), "value": v} for k, v in s["oculi"].items() if v]
    tiles = [
        {"key": "characters", "label": "Characters", "value": s["characters"]},
        {"key": "friendship", "label": "Max friendship", "value": s.get("max_friendship")},
        {"key": "waypoint", "label": "Waypoints", "value": s["waypoints"]},
        {"key": "domain", "label": "Domains", "value": s["domains"]},
        {"key": "abyss", "label": "Spiral Abyss", "value": s.get("abyss") or None},
        {"key": "chest", "label": "Chests", "value": sum(c["value"] for c in chests), "detail": chests},
        {"key": "oculus", "label": "Oculi", "value": sum(o["value"] for o in oculi), "detail": oculi},
    ]
    return {
        "header": {"name": name.strip() or "Traveler", "ar": s["ar"], "days_active": s["days_active"],
                   "achievements": s["achievements"]},
        "tiles": [t for t in tiles if t["value"] is not None],
        "regions": [_region(r) for r in sorted(data["regions"], key=lambda r: r["id"])],
        "teapot": data.get("teapot"),
        "bosses": _bosses(data["regions"]),
    }


def roster_view(session: Session) -> dict:
    game = {c.id: c for c in session.scalars(select(GameCharacter))}
    owned = list(session.scalars(select(OwnedCharacter)))
    elements = dict.fromkeys(ELEMENTS, 0)
    weapons = dict.fromkeys(WEAPON_TYPES, 0)
    rarity = {"5": 0, "4": 0}
    for o in owned:
        g = game.get(o.character_id)
        element = o.element or (g.element if g else None)
        if element in elements:
            elements[element] += 1
        if g is not None and g.weapon_type in weapons:
            weapons[g.weapon_type] += 1
        if g is not None and str(g.rarity) in rarity:
            rarity[str(g.rarity)] += 1
    return {"total": len(owned), "elements": elements, "weapon_types": weapons, "rarity": rarity,
            "constellations": sum(o.constellation for o in owned),
            "c6": sum(1 for o in owned if o.constellation >= 6)}
```

- [ ] **Step 4: Pass the display name and roster through the API**

In `backend/app/api/profile.py` import `from app.profile.view import challenge_views, profile_view, roster_view` and `from app.settings.store import get_setting`, and build the response as:

```python
        return {"connected": is_connected(ctx, s), "fetched_at": iso(snap.fetched_at) if snap else None,
                "error": last_error(s, "profile") or last_error(s, "challenges"),
                "profile": profile_view(snap.data if snap else None, str(get_setting(s, "display_name") or "")),
                "roster": roster_view(s),
                "challenges": challenge_views(s, utcnow())}
```

- [ ] **Step 5: Extend the demo profile**

In `backend/app/devseed.py`, in the `profile = {…}` dict: add `"max_friendship": 12, "abyss": "12-3"` to `"stats"`; give Mondstadt `"areas": [{"name": "Starfell Valley", "explored": 100.0}, {"name": "Galesong Hill", "explored": 95.5}]` and `"bosses": [{"name": "Anemo Hypostasis", "kills": 30}, {"name": "Stormterror", "kills": 12}]`; give Liyue `"bosses": [{"name": "Azhdaha", "kills": 20}]`; and add a top-level key:

```python
            "teapot": {"level": 10, "comfort": 21400, "comfort_name": "Exquisite", "comfort_icon": "",
                       "items": 312, "visitors": 40, "realms": [{"name": "Emerald Peak", "icon": ""}]},
```

(Icons stay empty strings: the e2e server is offline.)

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_profile_view.py tests/test_api_profile.py tests/test_devseed.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/app/profile/view.py backend/app/api/profile.py backend/app/devseed.py backend/tests/test_profile_view.py backend/tests/test_api_profile.py
git commit -m "feat(profile): header, icon tiles, regions, teapot, boss kills and roster view"
```

---

### Task 8: Showcase (default order, entries, editing API)

**Files:**
- Create: `backend/app/profile/showcase.py`
- Modify: `backend/app/settings/store.py` (`DEFAULTS`)
- Modify: `backend/app/api/profile.py`
- Test: `backend/tests/test_profile_showcase.py`, `backend/tests/test_api_profile.py`

**Interfaces:**
- Consumes: `OwnedCharacter`, `OwnedArtifact`, `GameCharacter`; `get_setting` / `set_setting`.
- Produces:
  - `SHOWCASE_MAX = 8`; `crit_value(artifacts) -> float`; `set_summary(artifacts) -> str`; `default_ids(owned, game) -> list[int]`; `showcase_view(session) -> {"mode": "auto" | "custom", "entries": [entry]}`; `owned_options(session) -> [{id, name, icon}]` sorted by name; `validate_ids(session, ids) -> str | None`.
  - entry: `{id, slug, name, rarity, element, icon, level, constellation, friendship, talents: {normal, skill, burst}, weapon: {name, icon, level, refinement, rarity}, stats: [{name, value}], artifacts: [{slot, set_name, icon, rarity, level, main_stat, substats}], sets, crit_value}`.
  - `GET /api/profile` adds `showcase`, `showcase_mode`, `owned`; `PUT /api/profile/showcase {ids}` → `{showcase, showcase_mode}` or 400 `{"detail": message}`.
  - setting `profile_showcase` (default `[]` = automatic).

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_profile_showcase.py
from datetime import datetime

from app.db.models import OwnedArtifact, OwnedCharacter
from app.profile.showcase import crit_value, owned_options, set_summary, showcase_view, validate_ids
from app.settings.store import set_setting
from helpers import seed_game

T = datetime(2026, 11, 1)


def own(s, cid, name, level=90, cons=0, element=None, stats=()):
    s.add(OwnedCharacter(character_id=cid, name=name, element=element, icon=None, level=level, constellation=cons,
                         friendship=10, talent_normal=6, talent_skill=10, talent_burst=None,
                         weapon_name="Favonius Sword", weapon_icon="https://x.test/w.png", weapon_rarity=4,
                         weapon_level=90, weapon_refinement=3, stats=list(stats), synced_at=T))


def art(cid, slot, set_name, subs):
    return OwnedArtifact(character_id=cid, slot=slot, set_name=set_name, rarity=5, level=20, main_stat="HP 4780",
                         substats=list(subs), icon="https://x.test/a.png")


def test_default_order_level_cons_rarity_name(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        own(s, 10000089, "Furina", cons=2)
        own(s, 10000073, "Nahida")
        own(s, 10000032, "Bennett", cons=6)
        own(s, 10000023, "Xiangling", level=80)
        own(s, 1000000507, "Cryo Traveler", element="Cryo")
    with session_factory() as s:
        v = showcase_view(s)
    assert v["mode"] == "auto"
    assert [e["id"] for e in v["entries"]] == [10000032, 10000089, 1000000507, 10000073, 10000023]
    traveler = v["entries"][2]
    assert traveler["slug"] == "cryo-traveler" and traveler["element"] == "Cryo"
    assert traveler["icon"] == "UI_AvatarIcon_PlayerGirl"                 # owned icon empty → game icon


def test_default_order_caps_at_eight(session_factory):
    with session_factory.begin() as s:
        for i in range(1, 10):
            own(s, 500 + i, f"C{i}", level=80 + i)
    with session_factory() as s:
        assert len(showcase_view(s)["entries"]) == 8


def test_showcase_skips_unowned(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        own(s, 10000073, "Nahida")
        own(s, 10000089, "Furina")
        set_setting(s, "profile_showcase", [999, 10000073])
    with session_factory() as s:
        v = showcase_view(s)
    assert v["mode"] == "custom" and [e["id"] for e in v["entries"]] == [10000073]


def test_entry_stats_artifacts_sets_and_crit(session_factory):
    seed_game(session_factory)
    stats = [{"name": "Max HP", "value": "38412"}, {"name": "Max Stamina", "value": "240"},
             {"name": "CRIT Rate", "value": "72.4%"}, {"name": "Healing Bonus", "value": "0.0%"}]
    with session_factory.begin() as s:
        own(s, 10000089, "Furina", stats=stats)
        for slot in (1, 2, 3, 4):
            s.add(art(10000089, slot, "Golden Troupe", ["CRIT Rate 3.5%", "ATK 14"]))
        s.add(art(10000089, 5, "Noblesse Oblige", ["CRIT DMG 7.8%", "HP 5.8%"]))
    with session_factory() as s:
        e = showcase_view(s)["entries"][0]
    assert e["stats"] == [{"name": "Max HP", "value": "38412"}, {"name": "CRIT Rate", "value": "72.4%"}]
    assert [a["slot"] for a in e["artifacts"]] == [1, 2, 3, 4, 5]
    assert e["sets"] == "Golden Troupe 4" and e["crit_value"] == 35.8              # 4 × 2 × 3.5 + 7.8
    assert e["talents"] == {"normal": 6, "skill": 10, "burst": None}
    assert e["weapon"] == {"name": "Favonius Sword", "icon": "https://x.test/w.png", "level": 90, "refinement": 3,
                           "rarity": 4}


def test_set_summary_and_crit_value_edge_cases():
    two_two = [art(1, 1, "B Set", []), art(1, 2, "A Set", []), art(1, 3, "B Set", []), art(1, 4, "A Set", []),
               art(1, 5, "C Set", [])]
    assert set_summary(two_two) == "A Set 2 · B Set 2"
    assert set_summary([art(1, 1, "A Set", [])]) == ""
    assert crit_value([art(1, 1, "A", ["CRIT Rate 3.9%", "CRIT DMG 21.0%", "CRIT Rate 3"])]) == 28.8   # flat ignored


def test_validate_ids_and_owned_options(session_factory):
    with session_factory.begin() as s:
        own(s, 10000089, "Furina")
        own(s, 10000032, "Bennett")
    with session_factory() as s:
        assert validate_ids(s, [10000089, 10000032]) is None
        assert validate_ids(s, []) is None
        assert validate_ids(s, list(range(9))) == "Pick at most 8 characters."
        assert validate_ids(s, [10000089, 10000089]) == "Each character can be shown once."
        assert validate_ids(s, [123]) == "Only characters you own can be shown."
        assert [o["name"] for o in owned_options(s)] == ["Bennett", "Furina"]
```

Append to `backend/tests/test_api_profile.py`:

```python
def test_showcase_endpoint(paths):
    from datetime import datetime

    from app.db.models import OwnedCharacter
    sf = sf_for(paths)
    with sf.begin() as s:
        for cid, name in ((10000089, "Furina"), (10000032, "Bennett")):
            s.add(OwnedCharacter(character_id=cid, name=name, element=None, icon=None, level=90, constellation=0,
                                 friendship=10, weapon_name="W", weapon_icon="", weapon_rarity=4, weapon_level=90,
                                 weapon_refinement=1, stats=[], synced_at=datetime(2026, 11, 1)))
    with make_client(paths) as client:
        body = client.get("/api/profile").json()
        assert body["showcase_mode"] == "auto" and [e["name"] for e in body["showcase"]] == ["Bennett", "Furina"]
        assert [o["name"] for o in body["owned"]] == ["Bennett", "Furina"]
        bad = client.put("/api/profile/showcase", json={"ids": [42]})
        assert bad.status_code == 400 and bad.json()["detail"] == "Only characters you own can be shown."
        ok = client.put("/api/profile/showcase", json={"ids": [10000089]}).json()
        assert ok["showcase_mode"] == "custom" and [e["id"] for e in ok["showcase"]] == [10000089]
        assert client.get("/api/profile").json()["showcase_mode"] == "custom"
        reset = client.put("/api/profile/showcase", json={"ids": []}).json()
        assert reset["showcase_mode"] == "auto" and len(reset["showcase"]) == 2
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `PY -m pytest tests/test_profile_showcase.py tests/test_api_profile.py -q`
Expected: FAIL (`ModuleNotFoundError: No module named 'app.profile.showcase'`).

- [ ] **Step 3: Add the setting default**

In `backend/app/settings/store.py` add to `DEFAULTS`:

```python
    "profile_showcase": [],              # Profile showcase character ids, in order; [] = automatic (sub-project 7)
```

- [ ] **Step 4: Create `showcase.py`**

```python
# backend/app/profile/showcase.py
"""Profile showcase (sub-project 7): up to 8 owned characters with their build, from synced data only."""
from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, OwnedArtifact, OwnedCharacter
from app.settings.store import get_setting

SHOWCASE_MAX = 8
HIDDEN_STATS = {"Max Stamina"}
ZERO = re.compile(r"^-?0+(\.0+)?%?$")
PERCENT_SUB = re.compile(r"^(?P<name>.+?)\s+(?P<value>-?\d+(?:\.\d+)?)%$")


def crit_value(artifacts: list[OwnedArtifact]) -> float:
    """CRIT Rate × 2 + CRIT DMG over artifact substats (percent substats only)."""
    total = 0.0
    for a in artifacts:
        for sub in a.substats or []:
            m = PERCENT_SUB.match(sub.strip())
            if m is None:
                continue
            if m["name"] == "CRIT Rate":
                total += 2 * float(m["value"])
            elif m["name"] == "CRIT DMG":
                total += float(m["value"])
    return round(total, 1)


def set_summary(artifacts: list[OwnedArtifact]) -> str:
    counts = Counter(a.set_name for a in artifacts)
    four = sorted(n for n, c in counts.items() if c >= 4)
    if four:
        return f"{four[0]} 4"
    return " · ".join(f"{n} 2" for n in sorted(n for n, c in counts.items() if c >= 2))


def default_ids(owned: list[OwnedCharacter], game: dict[int, GameCharacter]) -> list[int]:
    def key(o: OwnedCharacter) -> tuple:
        g = game.get(o.character_id)
        return (-o.level, -o.constellation, -(g.rarity if g else 0), o.name)
    return [o.character_id for o in sorted(owned, key=key)][:SHOWCASE_MAX]


def _entry(o: OwnedCharacter, g: GameCharacter | None, arts: list[OwnedArtifact]) -> dict:
    return {
        "id": o.character_id, "slug": g.slug if g else None, "name": o.name, "rarity": g.rarity if g else None,
        "element": o.element or (g.element if g else None), "icon": o.icon or (g.icon if g else None),
        "level": o.level, "constellation": o.constellation, "friendship": o.friendship,
        "talents": {"normal": o.talent_normal, "skill": o.talent_skill, "burst": o.talent_burst},
        "weapon": {"name": o.weapon_name, "icon": o.weapon_icon, "level": o.weapon_level,
                   "refinement": o.weapon_refinement, "rarity": o.weapon_rarity},
        "stats": [s for s in o.stats or [] if s.get("name") not in HIDDEN_STATS
                  and not ZERO.match(str(s.get("value", "")).strip())],
        "artifacts": [{"slot": a.slot, "set_name": a.set_name, "icon": a.icon, "rarity": a.rarity, "level": a.level,
                       "main_stat": a.main_stat, "substats": list(a.substats or [])}
                      for a in sorted(arts, key=lambda a: a.slot)],
        "sets": set_summary(arts), "crit_value": crit_value(arts),
    }


def showcase_view(session: Session) -> dict:
    owned = {o.character_id: o for o in session.scalars(select(OwnedCharacter))}
    game = {g.id: g for g in session.scalars(select(GameCharacter))}
    arts: dict[int, list[OwnedArtifact]] = {}
    for a in session.scalars(select(OwnedArtifact)):
        arts.setdefault(a.character_id, []).append(a)
    saved = [i for i in get_setting(session, "profile_showcase") or [] if isinstance(i, int)]
    ids = [i for i in saved if i in owned][:SHOWCASE_MAX] if saved else default_ids(list(owned.values()), game)
    return {"mode": "custom" if saved else "auto",
            "entries": [_entry(owned[i], game.get(i), arts.get(i, [])) for i in ids]}


def owned_options(session: Session) -> list[dict]:
    game = {g.id: g for g in session.scalars(select(GameCharacter))}
    rows = sorted(session.scalars(select(OwnedCharacter)), key=lambda o: o.name)
    return [{"id": o.character_id, "name": o.name,
             "icon": o.icon or (game[o.character_id].icon if o.character_id in game else None)} for o in rows]


def validate_ids(session: Session, ids: list[int]) -> str | None:
    if len(ids) > SHOWCASE_MAX:
        return f"Pick at most {SHOWCASE_MAX} characters."
    if len(set(ids)) != len(ids):
        return "Each character can be shown once."
    owned = set(session.scalars(select(OwnedCharacter.character_id)))
    if any(i not in owned for i in ids):
        return "Only characters you own can be shown."
    return None
```

- [ ] **Step 5: Wire the API**

In `backend/app/api/profile.py`: add imports

```python
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.profile.showcase import owned_options, showcase_view, validate_ids
from app.settings.store import get_setting, set_setting
```

add to the `get_profile` response dict (compute `show = showcase_view(s)` first, inside the session):

```python
                "showcase": show["entries"], "showcase_mode": show["mode"], "owned": owned_options(s),
```

and append:

```python
class ShowcaseIn(BaseModel):
    ids: list[int]


@router.put("/profile/showcase")
def put_showcase(body: ShowcaseIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory.begin() as s:
        message = validate_ids(s, body.ids)
        if message is not None:
            raise HTTPException(400, message)
        set_setting(s, "profile_showcase", list(body.ids))
        show = showcase_view(s)
    return {"showcase": show["entries"], "showcase_mode": show["mode"]}
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `PY -m pytest tests/test_profile_showcase.py tests/test_api_profile.py tests/test_settings_store.py tests/test_api_settings.py -q`
Expected: PASS. (If a settings test asserts the exact `DEFAULTS` keys, add `"profile_showcase"` to its expectation.)

- [ ] **Step 7: Run the whole backend suite and commit**

Run: `PY -m pytest -q` — expected: no failures.

```bash
git add backend/app/profile/showcase.py backend/app/settings/store.py backend/app/api/profile.py backend/tests/test_profile_showcase.py backend/tests/test_api_profile.py
git commit -m "feat(profile): editable character showcase with build details"
```

---

### Task 9: Profile frontend types, API, icons and helpers

**Files:**
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`
- Modify: `frontend/src/lib/icons.ts`, `frontend/src/lib/icons.test.ts`
- Create: `frontend/src/lib/profile.ts`, `frontend/src/lib/profile.test.ts`

**Interfaces:**
- Consumes: Tasks 7–8 JSON.
- Produces:
  - types `StatTile` (now `{ key; label; value: number | string; detail? }`), `RegionView`, `TeapotView`, `ProfileHeaderView`, `ProfileView`, `RosterView`, `ShowcaseArtifact`, `ShowcaseEntry`, `OwnedOption`; `ProfileResponse` gains `roster`, `showcase`, `showcase_mode`, `owned`.
  - `api.setShowcase(ids: number[]) => Promise<{ showcase: ShowcaseEntry[]; showcase_mode: 'auto' | 'custom' }>`.
  - icon names `friendship, waypoint, domain, abyss, chest, oculus, teapot, boss`.
  - `profile.ts`: `SHOWCASE_MAX`, `TILE_ICON`, `toggleId`, `moveId`, `ringDash`, `tileTitle`, `talentLine`, `topBosses`.

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/lib/profile.test.ts
import { describe, expect, it } from 'vitest';
import { moveId, ringDash, talentLine, tileTitle, toggleId, topBosses } from './profile';

describe('profile helpers', () => {
	it('toggles ids with a cap', () => {
		expect(toggleId([1, 2], 2)).toEqual([1]);
		expect(toggleId([1], 2)).toEqual([1, 2]);
		expect(toggleId([1, 2, 3, 4, 5, 6, 7, 8], 9)).toEqual([1, 2, 3, 4, 5, 6, 7, 8]);
	});
	it('moves ids up and down within bounds', () => {
		expect(moveId([1, 2, 3], 1, -1)).toEqual([2, 1, 3]);
		expect(moveId([1, 2, 3], 2, 1)).toEqual([1, 2, 3]);
		expect(moveId([1, 2, 3], 0, -1)).toEqual([1, 2, 3]);
	});
	it('draws a ring dash for a percentage', () => {
		expect(ringDash(50)).toBe('47.1 94.2');
		expect(ringDash(150)).toBe('94.2 94.2');
		expect(ringDash(-5)).toBe('0.0 94.2');
	});
	it('formats tiles, talents and bosses', () => {
		expect(tileTitle({ key: 'chest', label: 'Chests', value: 3, detail: [{ label: 'Common', value: 2 }, { label: 'Rare', value: 1 }] }))
			.toBe('Common 2 · Rare 1');
		expect(tileTitle({ key: 'domain', label: 'Domains', value: 3 })).toBe('');
		expect(talentLine({ normal: 6, skill: 10, burst: null })).toBe('6 / 10 / —');
		const bosses = Array.from({ length: 8 }, (_, i) => ({ name: `B${i}`, kills: 8 - i }));
		expect(topBosses(bosses, false)).toHaveLength(6);
		expect(topBosses(bosses, true)).toHaveLength(8);
	});
});
```

In `frontend/src/lib/icons.test.ts` change `expect(ICON_NAMES).toHaveLength(13);` to `expect(ICON_NAMES).toHaveLength(21);`.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npx vitest run src/lib/profile.test.ts src/lib/icons.test.ts`
Expected: FAIL (missing `./profile`; icon count 13).

- [ ] **Step 3: Update the types**

In `frontend/src/lib/types.ts` replace `StatTile`, `RegionView`, `ProfileView` and `ProfileResponse` with:

```ts
export interface StatTile { key: string; label: string; value: number | string; detail?: { label: string; value: number }[] }
export interface RegionView {
	id: number; name: string; explored: number; reputation: number | null; icon: string | null;
	offerings: { name: string; level: number; icon: string | null }[]; areas: { name: string; explored: number }[];
}
export interface TeapotView {
	level: number; comfort: number; comfort_name: string; comfort_icon: string; items: number; visitors: number;
	realms: { name: string; icon: string }[];
}
export interface ProfileHeaderView { name: string; ar: number; days_active: number; achievements: number }
export interface ProfileView {
	header: ProfileHeaderView; tiles: StatTile[]; regions: RegionView[]; teapot: TeapotView | null;
	bosses: { name: string; kills: number }[];
}
export interface RosterView {
	total: number; elements: Record<string, number>; weapon_types: Record<string, number>;
	rarity: { '5': number; '4': number }; constellations: number; c6: number;
}
export interface ShowcaseArtifact {
	slot: number; set_name: string; icon: string; rarity: number; level: number; main_stat: string; substats: string[];
}
export interface ShowcaseEntry {
	id: number; slug: string | null; name: string; rarity: number | null; element: string | null; icon: string | null;
	level: number; constellation: number; friendship: number;
	talents: { normal: number | null; skill: number | null; burst: number | null };
	weapon: { name: string; icon: string; level: number; refinement: number; rarity: number };
	stats: { name: string; value: string }[]; artifacts: ShowcaseArtifact[]; sets: string; crit_value: number;
}
export interface OwnedOption { id: number; name: string; icon: string | null }
export interface ProfileResponse {
	connected: boolean; fetched_at: string | null; error: string | null; profile: ProfileView | null;
	roster: RosterView; showcase: ShowcaseEntry[]; showcase_mode: 'auto' | 'custom'; owned: OwnedOption[];
	challenges: ChallengeViews;
}
```

Check nothing else uses the old fields: `grep -rn "StatTile\|RegionView\|ProfileView" frontend/src --include=*.svelte --include=*.ts` should only list `types.ts` and `routes/profile/+page.svelte` (rewritten in Task 11).

- [ ] **Step 4: Add the API call**

In `frontend/src/lib/api.ts`, next to `profile: …`, add (and import `ShowcaseEntry` from `./types`):

```ts
	setShowcase: (ids: number[]) =>
		request<{ showcase: ShowcaseEntry[]; showcase_mode: 'auto' | 'custom' }>('PUT', '/profile/showcase', { ids }),
```

- [ ] **Step 5: Add the icons**

In `frontend/src/lib/icons.ts` extend `ICON_NAMES`:

```ts
export const ICON_NAMES = [
	'dashboard', 'characters', 'teams', 'inventory', 'map', 'events', 'wishes', 'sync', 'profile', 'settings', 'external',
	'commission', 'expedition', 'friendship', 'waypoint', 'domain', 'abyss', 'chest', 'oculus', 'teapot', 'boss'
] as const;
```

and add these entries to `ICONS` (original single-colour shapes):

```ts
	friendship: [{ d: 'M12 21l-1.5-1.3C5 15 2 12.2 2 8.5 2 5.4 4.4 3 7.5 3c1.7 0 3.4.8 4.5 2.1C13.1 3.8 14.8 3 16.5 3 19.6 3 22 5.4 22 8.5c0 3.7-3 6.5-8.5 11.2z' }],
	waypoint: [{ d: 'M12 1l5 8-5 14-5-14zm0 4.5L9.8 9 12 15l2.2-6z', evenodd: true }],
	domain: [{ d: 'M3 21V9l9-6 9 6v12h-6v-6a3 3 0 0 0-6 0v6z' }],
	abyss: [{ d: 'M12 2l2.6 6.9L22 9.3l-5.6 4.6L18.2 21 12 17.3 5.8 21l1.8-7.1L2 9.3l7.4-.4z' }],
	chest: [{ d: 'M4 8a4 4 0 0 1 4-4h8a4 4 0 0 1 4 4v2H4zM4 12h7v2h2v-2h7v8H4z' }],
	oculus: [{ d: 'M12 3a9 9 0 1 0 0 18a9 9 0 1 0 0-18zm0 4l1.5 3.5L17 12l-3.5 1.5L12 17l-1.5-3.5L7 12l3.5-1.5z', evenodd: true }],
	teapot: [{ d: 'M8 4h8v2h-1v2h3a3 3 0 0 1 3 3v1a3 3 0 0 1-3 3h-.4A7 7 0 0 1 5 15H3l2-5V8h4V6H8zm11 6v3a1 1 0 0 0 1-1v-1a1 1 0 0 0-1-1z', evenodd: true }],
	boss: [{ d: 'M12 2c4.4 0 8 3.4 8 7.6 0 2.6-1.3 4.8-3.3 6.2V20H7.3v-4.2C5.3 14.4 4 12.2 4 9.6 4 5.4 7.6 2 12 2zm-3 7a2 2 0 1 0 0 4 2 2 0 0 0 0-4zm6 0a2 2 0 1 0 0 4 2 2 0 0 0 0-4z', evenodd: true }],
```

- [ ] **Step 6: Create `profile.ts`**

```ts
// frontend/src/lib/profile.ts
import type { IconName } from './icons';
import type { ShowcaseEntry, StatTile } from './types';

export const SHOWCASE_MAX = 8;
export const BOSSES_SHOWN = 6;

export const TILE_ICON: Record<string, IconName> = {
	characters: 'characters', friendship: 'friendship', waypoint: 'waypoint', domain: 'domain', abyss: 'abyss',
	chest: 'chest', oculus: 'oculus'
};

export function toggleId(ids: number[], id: number, max = SHOWCASE_MAX): number[] {
	if (ids.includes(id)) return ids.filter((i) => i !== id);
	return ids.length >= max ? ids : [...ids, id];
}

export function moveId(ids: number[], index: number, delta: -1 | 1): number[] {
	const j = index + delta;
	if (j < 0 || j >= ids.length) return ids;
	const out = [...ids];
	[out[index], out[j]] = [out[j], out[index]];
	return out;
}

export function ringDash(pct: number, r = 15): string {
	const c = 2 * Math.PI * r;
	return `${((Math.max(0, Math.min(100, pct)) / 100) * c).toFixed(1)} ${c.toFixed(1)}`;
}

export function tileTitle(t: StatTile): string {
	return t.detail?.map((d) => `${d.label} ${d.value}`).join(' · ') ?? '';
}

export function talentLine(t: ShowcaseEntry['talents']): string {
	return [t.normal, t.skill, t.burst].map((v) => v ?? '—').join(' / ');
}

export function topBosses<T>(bosses: T[], all: boolean): T[] {
	return all ? bosses : bosses.slice(0, BOSSES_SHOWN);
}
```

- [ ] **Step 7: Run the tests to verify they pass**

Run: `npx vitest run src/lib/profile.test.ts src/lib/icons.test.ts`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/lib/types.ts frontend/src/lib/api.ts frontend/src/lib/icons.ts frontend/src/lib/icons.test.ts frontend/src/lib/profile.ts frontend/src/lib/profile.test.ts
git commit -m "feat(profile): frontend types, showcase API call, stat icons and helpers"
```

---

### Task 10: Profile components (header, showcase, panel, editor, region card)

**Files:**
- Create: `frontend/src/lib/ProfileHeader.svelte`, `Showcase.svelte`, `ShowcasePanel.svelte`, `ShowcaseEditor.svelte`, `RegionCard.svelte` (all in `frontend/src/lib/`)

**Interfaces:**
- Consumes: Task 9 types and helpers; `elementStyle`, `RARITY_STYLE` from `elements.ts`; `imgSrc`; `timeAgo`.
- Produces (props and test ids):
  - `ProfileHeader { header: ProfileHeaderView; portrait: string | null; fetchedAt: string | null; error: string | null; now: number }` — `data-testid="profile-header"`.
  - `Showcase { entries: ShowcaseEntry[]; mode: 'auto' | 'custom'; owned: OwnedOption[]; onsave: (ids: number[]) => Promise<void> }` — `showcase`, `showcase-card` (buttons), button "Edit showcase".
  - `ShowcasePanel { entry: ShowcaseEntry }` — `showcase-panel`.
  - `ShowcaseEditor { owned: OwnedOption[]; initial: number[]; onsave: (ids: number[]) => Promise<void>; onclose: () => void }` — `showcase-editor` dialog; buttons: each owned name (aria-pressed), "Move <name> up/down", "Remove <name>", "Clear", "Reset to automatic", "Cancel", "Save".
  - `RegionCard { region: RegionView }` — `region-card`; button "Show N areas".

Checked by Task 11's e2e; this task's gate is `npm run check` on these files.

- [ ] **Step 1: Create `ProfileHeader.svelte`**

```svelte
<!-- frontend/src/lib/ProfileHeader.svelte -->
<script lang="ts">
	import { imgSrc } from './img';
	import { timeAgo } from './time';
	import type { ProfileHeaderView } from './types';

	let { header, portrait, fetchedAt, error, now }: {
		header: ProfileHeaderView; portrait: string | null; fetchedAt: string | null; error: string | null; now: number;
	} = $props();
</script>

<section class="panel hero" data-testid="profile-header">
	{#if imgSrc(portrait)}
		<img class="avatar" src={imgSrc(portrait)} alt="" />
	{:else}
		<span class="avatar initial" aria-hidden="true">{header.name.slice(0, 1)}</span>
	{/if}
	<div>
		<h1>{header.name} <span class="ar">AR {header.ar}</span></h1>
		<div class="muted">{header.days_active.toLocaleString()} days active · {header.achievements.toLocaleString()} achievements</div>
		<div class="muted small">as of {fetchedAt ? timeAgo(fetchedAt, now) : '—'}{#if error} · ⚠ last update failed: {error}{/if}</div>
	</div>
</section>

<style>
	.hero { display: flex; align-items: center; gap: 16px; margin-bottom: 12px;
		background: linear-gradient(90deg, color-mix(in srgb, var(--rarity-4) 35%, transparent), transparent); }
	.avatar { width: 72px; height: 72px; border-radius: 50%; border: 2px solid var(--rarity-5); object-fit: cover;
		background: var(--panel-2); }
	.initial { display: inline-flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 700; }
	h1 { margin: 0; display: flex; align-items: center; gap: 8px; }
	.ar { background: var(--rarity-5); color: #17130b; border-radius: 999px; padding: 1px 10px; font-size: 13px; font-weight: 700; }
	.small { font-size: 12px; }
</style>
```

- [ ] **Step 2: Create `ShowcasePanel.svelte`**

```svelte
<!-- frontend/src/lib/ShowcasePanel.svelte -->
<script lang="ts">
	import { elementStyle } from './elements';
	import { imgSrc } from './img';
	import { talentLine } from './profile';
	import type { ShowcaseEntry } from './types';

	let { entry }: { entry: ShowcaseEntry } = $props();
	const SLOTS = ['Flower', 'Plume', 'Sands', 'Goblet', 'Circlet'];
	const tint = $derived(elementStyle(entry.element).color);
</script>

<div class="detail" style="--tint: {tint}" data-testid="showcase-panel" aria-live="polite">
	<div class="who">
		{#if imgSrc(entry.icon)}<img class="portrait" src={imgSrc(entry.icon)} alt="" />{/if}
		<h3>{entry.name}</h3>
		<div class="muted">Lv {entry.level} · C{entry.constellation} · ♥ {entry.friendship}</div>
		<div class="talents" title="Normal attack / Skill / Burst">Talents {talentLine(entry.talents)}</div>
		<div class="weapon">
			{#if imgSrc(entry.weapon.icon)}<img src={imgSrc(entry.weapon.icon)} alt="" />{/if}
			<span>{entry.weapon.name}<br /><span class="muted">Lv {entry.weapon.level} · R{entry.weapon.refinement}</span></span>
		</div>
		{#if entry.slug}<a href="/characters/{entry.slug}">Open character</a>{/if}
	</div>
	<dl class="stats">
		{#each entry.stats as s (s.name)}<dt>{s.name}</dt><dd>{s.value}</dd>{/each}
	</dl>
	<div class="arts">
		{#if entry.artifacts.length === 0}
			<p class="muted">No artifacts synced.</p>
		{:else}
			<div class="muted small">{entry.sets || 'Mixed sets'} · CV {entry.crit_value}</div>
			<div class="grid">
				{#each entry.artifacts as a (a.slot)}
					<div class="art">
						{#if imgSrc(a.icon)}<img src={imgSrc(a.icon)} alt="" />{/if}
						<div class="muted small">{SLOTS[a.slot - 1] ?? `Slot ${a.slot}`} · +{a.level}</div>
						<strong>{a.main_stat}</strong>
						{#each a.substats as sub, i (i)}<div class="small">{sub}</div>{/each}
					</div>
				{/each}
			</div>
		{/if}
	</div>
</div>

<style>
	.detail { display: grid; grid-template-columns: 180px 1fr 2fr; gap: 16px; margin-top: 12px; padding: 12px;
		border-radius: 12px; border: 1px solid color-mix(in srgb, var(--tint) 50%, transparent);
		background: linear-gradient(90deg, color-mix(in srgb, var(--tint) 22%, transparent), transparent); }
	@media (max-width: 900px) { .detail { grid-template-columns: 1fr; } }
	.portrait { width: 96px; height: 96px; border-radius: 12px; }
	h3 { margin: 6px 0 2px; }
	.talents { margin: 6px 0; font-size: 12px; }
	.weapon { display: flex; align-items: center; gap: 6px; font-size: 12px; margin-bottom: 6px; }
	.weapon img { width: 32px; height: 32px; }
	.stats { display: grid; grid-template-columns: 1fr auto; gap: 2px 12px; margin: 0; font-size: 13px; align-content: start; }
	.stats dt { color: var(--muted); }
	.stats dd { margin: 0; font-weight: 600; text-align: right; font-variant-numeric: tabular-nums; }
	.grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(120px, 1fr)); gap: 6px; margin-top: 6px; }
	.art { background: var(--panel-2); border-radius: 8px; padding: 6px; font-size: 12px; }
	.art img { width: 32px; height: 32px; float: right; }
	.small { font-size: 11px; }
</style>
```

- [ ] **Step 3: Create `ShowcaseEditor.svelte`**

```svelte
<!-- frontend/src/lib/ShowcaseEditor.svelte -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { imgSrc } from './img';
	import { SHOWCASE_MAX, moveId, toggleId } from './profile';
	import type { OwnedOption } from './types';

	let { owned, initial, onsave, onclose }: {
		owned: OwnedOption[]; initial: number[]; onsave: (ids: number[]) => Promise<void>; onclose: () => void;
	} = $props();
	let ids = $state<number[]>([...initial]);
	let busy = $state(false);
	let dialog: HTMLDialogElement;
	const byId = $derived(new Map(owned.map((o) => [o.id, o])));

	onMount(() => dialog.showModal());

	async function save(next: number[]) {
		busy = true;
		try {
			await onsave(next);
		} finally {
			busy = false;
		}
	}
</script>

<dialog bind:this={dialog} {onclose} aria-labelledby="showcase-editor-title" data-testid="showcase-editor">
	<h2 id="showcase-editor-title">Edit showcase</h2>
	<p class="muted small">Pick up to {SHOWCASE_MAX} characters ({ids.length}/{SHOWCASE_MAX}). The order here is the order on the page.</p>
	<ol class="chosen">
		{#each ids as id, i (id)}
			{@const name = byId.get(id)?.name ?? String(id)}
			<li>
				<span>{name}</span>
				<button type="button" aria-label="Move {name} up" disabled={i === 0} onclick={() => (ids = moveId(ids, i, -1))}>↑</button>
				<button type="button" aria-label="Move {name} down" disabled={i === ids.length - 1} onclick={() => (ids = moveId(ids, i, 1))}>↓</button>
				<button type="button" aria-label="Remove {name}" onclick={() => (ids = toggleId(ids, id))}>×</button>
			</li>
		{/each}
	</ol>
	<div class="pick">
		{#each owned as o (o.id)}
			<button type="button" class="opt" aria-pressed={ids.includes(o.id)}
				disabled={!ids.includes(o.id) && ids.length >= SHOWCASE_MAX} onclick={() => (ids = toggleId(ids, o.id))}>
				{#if imgSrc(o.icon)}<img src={imgSrc(o.icon)} alt="" />{/if}{o.name}
			</button>
		{/each}
	</div>
	<div class="actions">
		<button type="button" onclick={() => (ids = [])}>Clear</button>
		<button type="button" onclick={() => save([])} disabled={busy}>Reset to automatic</button>
		<span class="spacer"></span>
		<button type="button" onclick={() => dialog.close()}>Cancel</button>
		<button type="button" class="primary" onclick={() => save(ids)} disabled={busy || ids.length === 0}>Save</button>
	</div>
</dialog>

<style>
	dialog { max-width: 720px; width: 92vw; }
	.chosen { display: grid; gap: 4px; padding-left: 20px; }
	.chosen li span { display: inline-block; min-width: 160px; }
	.pick { display: flex; flex-wrap: wrap; gap: 6px; margin: 10px 0; max-height: 300px; overflow: auto; }
	.opt { display: inline-flex; align-items: center; gap: 6px; }
	.opt[aria-pressed='true'] { border-color: var(--avg-pity); color: var(--avg-pity); }
	.opt img { width: 22px; height: 22px; border-radius: 50%; }
	.actions { display: flex; gap: 8px; align-items: center; }
	.spacer { flex: 1; }
	.small { font-size: 12px; }
</style>
```

- [ ] **Step 4: Create `Showcase.svelte`**

```svelte
<!-- frontend/src/lib/Showcase.svelte -->
<script lang="ts">
	import { RARITY_STYLE, elementStyle } from './elements';
	import { imgSrc } from './img';
	import ShowcaseEditor from './ShowcaseEditor.svelte';
	import ShowcasePanel from './ShowcasePanel.svelte';
	import type { OwnedOption, ShowcaseEntry } from './types';

	let { entries, mode, owned, onsave }: {
		entries: ShowcaseEntry[]; mode: 'auto' | 'custom'; owned: OwnedOption[]; onsave: (ids: number[]) => Promise<void>;
	} = $props();
	let openId = $state<number | null>(null);
	let editing = $state(false);
	const current = $derived(entries.find((e) => e.id === openId) ?? entries[0] ?? null);

	async function save(ids: number[]) {
		await onsave(ids);
		editing = false;
	}
</script>

<section class="panel" data-testid="showcase">
	<div class="head">
		<h2>Showcase <span class="muted small">{mode === 'auto' ? 'automatic' : 'your pick'}</span></h2>
		<button type="button" onclick={() => (editing = true)}>Edit showcase</button>
	</div>
	<div class="row">
		{#each entries as e (e.id)}
			{@const el = elementStyle(e.element)}
			<button type="button" class="card" data-testid="showcase-card" aria-pressed={current?.id === e.id}
				style="--rar: {RARITY_STYLE[e.rarity ?? 0]?.color ?? 'var(--pill-neutral)'}" onclick={() => (openId = e.id)}>
				{#if imgSrc(e.icon)}<img class="face" src={imgSrc(e.icon)} alt="" />{:else}<span class="face initial">{e.name.slice(0, 1)}</span>{/if}
				{#if el.icon && imgSrc(el.icon)}<img class="el" src={imgSrc(el.icon)} alt={e.element ?? ''} />{/if}
				<strong>{e.name}</strong>
				<span class="muted small">Lv {e.level} · C{e.constellation}</span>
			</button>
		{/each}
	</div>
	{#if current}<ShowcasePanel entry={current} />{/if}
</section>

{#if editing}
	<ShowcaseEditor {owned} initial={entries.map((e) => e.id)} onsave={save} onclose={() => (editing = false)} />
{/if}

<style>
	.head { display: flex; align-items: center; justify-content: space-between; }
	.row { display: grid; grid-template-columns: repeat(8, minmax(0, 1fr)); gap: 8px; }
	@media (max-width: 900px) { .row { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
	.card { all: unset; cursor: pointer; position: relative; display: flex; flex-direction: column; align-items: center;
		text-align: center; border-radius: 10px; overflow: hidden; padding-bottom: 6px; font-size: 12px;
		background: linear-gradient(180deg, color-mix(in srgb, var(--rar) 60%, transparent), var(--panel-2)); }
	.card[aria-pressed='true'] { outline: 2px solid var(--avg-pity); }
	.card:focus-visible { outline: 2px solid var(--avg-pity); }
	.face { width: 100%; aspect-ratio: 1; object-fit: cover; }
	.initial { display: flex; align-items: center; justify-content: center; font-size: 28px; font-weight: 700; }
	.el { position: absolute; top: 4px; right: 4px; width: 18px; height: 18px; }
	.small { font-size: 11px; }
</style>
```

- [ ] **Step 5: Create `RegionCard.svelte`**

```svelte
<!-- frontend/src/lib/RegionCard.svelte -->
<script lang="ts">
	import { imgSrc } from './img';
	import { ringDash } from './profile';
	import type { RegionView } from './types';

	let { region }: { region: RegionView } = $props();
	let open = $state(false);
</script>

<div class="region" data-testid="region-card">
	<div class="top">
		<svg viewBox="0 0 36 36" class="ring" role="img" aria-label="{region.name}: {region.explored}% explored">
			<circle cx="18" cy="18" r="15" class="track" />
			<circle cx="18" cy="18" r="15" class="fill" stroke-dasharray={ringDash(region.explored)} transform="rotate(-90 18 18)" />
			{#if imgSrc(region.icon)}<image href={imgSrc(region.icon)} x="10" y="10" width="16" height="16" />{/if}
		</svg>
		<div>
			<div class="name">{region.name}</div>
			<div class="big">{region.explored}%</div>
			{#if region.reputation !== null}<div class="muted small">Reputation {region.reputation}</div>{/if}
			{#each region.offerings as o, j (j)}
				<div class="muted small offering">{#if imgSrc(o.icon)}<img src={imgSrc(o.icon)} alt="" />{/if}{o.name} {o.level}</div>
			{/each}
		</div>
	</div>
	{#if region.areas.length}
		<button type="button" class="more" aria-expanded={open} onclick={() => (open = !open)}>
			{open ? 'Hide' : 'Show'} {region.areas.length} areas
		</button>
		{#if open}
			<ul class="areas">
				{#each region.areas as a, i (i)}
					<li><span>{a.name}</span><span class="track-bar"><span style="width: {Math.min(100, a.explored)}%"></span></span>
						<span class="muted">{a.explored}%</span></li>
				{/each}
			</ul>
		{/if}
	{/if}
</div>

<style>
	.region { background: var(--panel-2); border-radius: 10px; padding: 10px 12px; }
	.top { display: flex; gap: 10px; align-items: center; }
	.ring { width: 56px; height: 56px; flex: none; }
	.track { fill: none; stroke: var(--line); stroke-width: 4; }
	.fill { fill: none; stroke: var(--anemo); stroke-width: 4; stroke-linecap: round; }
	.name { font-weight: 600; }
	.big { font-size: 18px; font-weight: 700; }
	.small { font-size: 12px; }
	.offering img { width: 16px; height: 16px; vertical-align: -3px; margin-right: 4px; }
	.more { margin-top: 6px; font-size: 12px; }
	.areas { list-style: none; padding: 0; margin: 6px 0 0; display: grid; gap: 4px; font-size: 12px; }
	.areas li { display: grid; grid-template-columns: 1fr 80px 46px; gap: 6px; align-items: center; }
	.track-bar { height: 6px; background: var(--line); border-radius: 3px; overflow: hidden; }
	.track-bar span { display: block; height: 100%; background: var(--anemo); }
</style>
```

- [ ] **Step 6: Type-check the new files**

Run: `npm run check 2>&1 | grep -E "ProfileHeader|Showcase|RegionCard" ; echo done`
Expected: no lines mentioning the new files (errors in `routes/profile/+page.svelte` are expected until Task 11).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/ProfileHeader.svelte frontend/src/lib/Showcase.svelte frontend/src/lib/ShowcasePanel.svelte frontend/src/lib/ShowcaseEditor.svelte frontend/src/lib/RegionCard.svelte
git commit -m "feat(profile): header, showcase, showcase editor and region card components"
```

---

### Task 11: Profile page and e2e

**Files:**
- Modify: `frontend/src/routes/profile/+page.svelte`
- Modify: `frontend/e2e/profile.spec.ts`

**Interfaces:**
- Consumes: Tasks 9–10; `Icon`, `RadarChart`, `Countdown`, `api.profile`, `api.setShowcase`.
- Produces: test ids `stat-tiles`, `roster`, `teapot`, `bosses`, plus today's `<kind>-current` / `<kind>-past`.

- [ ] **Step 1: Write the failing e2e tests**

Replace `frontend/e2e/profile.spec.ts` with:

```ts
import { expect, test } from '@playwright/test';

test('profile shows header, stats, exploration, roster, teapot, bosses and challenges', async ({ page }) => {
	await page.goto('/profile');
	await expect(page.getByText('AR 58')).toBeVisible();
	await expect(page.getByTestId('profile-header')).toContainText('Traveler');
	await expect(page.getByTestId('profile-header')).toContainText('900 days active');
	await expect(page.getByTestId('stat-tiles')).toContainText('Spiral Abyss');
	await expect(page.getByTestId('stat-tiles')).toContainText('12-3');
	await expect(page.getByTestId('region-card')).toHaveCount(3);
	await page.getByRole('button', { name: 'Show 2 areas' }).click();
	await expect(page.getByTestId('region-card').first()).toContainText('Galesong Hill');
	await expect(page.getByTestId('roster')).toContainText('5 characters');
	await expect(page.getByTestId('teapot')).toContainText('Lv 10');
	await expect(page.getByTestId('bosses').locator('li').first()).toContainText('Anemo Hypostasis');
	await expect(page.getByTestId('abyss-current')).toContainText('36');
	await expect(page.getByTestId('abyss-past').locator('tbody tr')).toHaveCount(2);
	await expect(page.getByTestId('abyss-past').getByRole('columnheader')).toHaveText(['Started', 'Result']);
});

test('showcase opens a detail panel and can be edited, then reset', async ({ page }) => {
	await page.goto('/profile');
	const cards = page.getByTestId('showcase-card');
	await expect(cards).toHaveCount(5);
	await expect(cards.first()).toContainText('Cryo Traveler');                 // automatic order
	await expect(page.getByTestId('showcase-panel')).toContainText('Favonius Sword');
	await cards.nth(1).click();
	await expect(page.getByTestId('showcase-panel')).toContainText('Furina');

	await page.getByRole('button', { name: 'Edit showcase' }).click();
	const editor = page.getByTestId('showcase-editor');
	await editor.getByRole('button', { name: 'Clear' }).click();
	await editor.getByRole('button', { name: 'Furina', exact: true }).click();
	await editor.getByRole('button', { name: 'Bennett', exact: true }).click();
	await editor.getByRole('button', { name: 'Move Bennett up' }).click();
	await editor.getByRole('button', { name: 'Save' }).click();
	await expect(cards).toHaveCount(2);
	await expect(cards.first()).toContainText('Bennett');
	await page.reload();
	await expect(page.getByTestId('showcase-card').first()).toContainText('Bennett');    // stored

	await page.getByRole('button', { name: 'Edit showcase' }).click();                    // restore shared state
	await page.getByTestId('showcase-editor').getByRole('button', { name: 'Reset to automatic' }).click();
	await expect(page.getByTestId('showcase-card')).toHaveCount(5);
});
```

- [ ] **Step 2: Replace the Profile page**

```svelte
<!-- frontend/src/routes/profile/+page.svelte -->
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { WEAPON_TYPES } from '$lib/charts';
	import Countdown from '$lib/Countdown.svelte';
	import { ELEMENT_STYLE } from '$lib/elements';
	import Icon from '$lib/Icon.svelte';
	import { imgSrc } from '$lib/img';
	import ProfileHeader from '$lib/ProfileHeader.svelte';
	import { TILE_ICON, tileTitle, topBosses } from '$lib/profile';
	import RadarChart from '$lib/RadarChart.svelte';
	import RegionCard from '$lib/RegionCard.svelte';
	import Showcase from '$lib/Showcase.svelte';
	import { sync } from '$lib/sync.svelte';
	import type { ChallengeRunView, ProfileResponse } from '$lib/types';

	let data = $state<ProfileResponse | null>(null);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let allBosses = $state(false);
	let now = $state(Date.now());
	const KINDS = [
		{ key: 'abyss', title: 'Spiral Abyss' },
		{ key: 'theater', title: 'Imaginarium Theater' },
		{ key: 'stygian', title: 'Stygian Onslaught' }
	] as const;

	$effect(() => {
		void sync.version;
		api.profile().then((d) => { data = d; error = null; }).catch((e) => (error = errorMessage(e)));
	});

	onMount(() => {
		const t = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(t);
	});

	async function saveShowcase(ids: number[]) {
		if (!data) return;
		try {
			const r = await api.setShowcase(ids);
			data = { ...data, showcase: r.showcase, showcase_mode: r.showcase_mode };
			toast = null;
		} catch (e) {
			toast = errorMessage(e);
		}
	}

	function result(kind: string, r: ChallengeRunView): string {
		const s = r.summary;
		if (kind === 'abyss') return `${s.stars ?? '—'}★ · floor ${s.max_floor ?? '—'} · ${s.wins ?? 0}/${s.battles ?? 0} wins`;
		if (kind === 'theater') return `Act ${s.act ?? '—'} · difficulty ${s.difficulty ?? '—'} · ${s.medals ?? 0} medals`;
		return `Difficulty ${s.difficulty ?? '—'}${s.time_used ? ` · ${s.time_used}s` : ''}`;
	}
</script>

{#if error}<p class="error">{error}</p>{/if}
{#if toast}<p class="error" role="alert">{toast}</p>{/if}

{#if data}
	{#if data.profile}
		<ProfileHeader header={data.profile.header} portrait={data.showcase[0]?.icon ?? null}
			fetchedAt={data.fetched_at} error={data.error} {now} />
	{:else}
		<h1>Profile</h1>
		<p class="muted">{data.connected ? 'Sync to load your profile' : 'Connect HoYoLAB in Settings to load your profile'}</p>
	{/if}

	{#if data.owned.length}
		<Showcase entries={data.showcase} mode={data.showcase_mode} owned={data.owned} onsave={saveShowcase} />
	{/if}

	{#if data.profile}
		<section class="panel tiles" data-testid="stat-tiles">
			{#each data.profile.tiles as t (t.key)}
				<div class="tile" title={tileTitle(t) || undefined}>
					<span class="ic"><Icon name={TILE_ICON[t.key] ?? 'profile'} size={20} /></span>
					<span class="v">{typeof t.value === 'number' ? t.value.toLocaleString() : t.value}</span>
					<span class="muted small">{t.label}</span>
				</div>
			{/each}
		</section>

		<section class="panel">
			<h2>Exploration</h2>
			<div class="regions">
				{#each data.profile.regions as r (r.id)}<RegionCard region={r} />{/each}
			</div>
		</section>
	{/if}

	<div class="three">
		<section class="panel" data-testid="roster">
			<h2>Roster <span class="muted small">{data.roster.total} characters</span></h2>
			<ul class="bars">
				{#each Object.entries(data.roster.elements) as [el, n] (el)}
					<li><span>{el}</span><span class="bar"><span style="width: {data.roster.total ? (n / data.roster.total) * 100 : 0}%; background: {ELEMENT_STYLE[el]?.color ?? 'var(--muted)'}"></span></span><span>{n}</span></li>
				{/each}
			</ul>
			<RadarChart title="Weapon types" size={160} axes={WEAPON_TYPES.map((w) => ({ label: w }))}
				series={[{ name: 'Owned', values: WEAPON_TYPES.map((w) => data?.roster.weapon_types[w] ?? 0), color: 'var(--avg-pity)' }]} />
			<div class="muted small">5★ {data.roster.rarity['5']} · 4★ {data.roster.rarity['4']} · {data.roster.constellations} constellations · {data.roster.c6} at C6</div>
		</section>

		{#if data.profile?.teapot}
			{@const tp = data.profile.teapot}
			<section class="panel" data-testid="teapot">
				<h2><Icon name="teapot" size={18} /> Serenitea Pot</h2>
				<div class="big">Lv {tp.level}</div>
				<div>{#if imgSrc(tp.comfort_icon)}<img class="sm" src={imgSrc(tp.comfort_icon)} alt="" />{/if}{tp.comfort.toLocaleString()} comfort · {tp.comfort_name}</div>
				<div class="muted small">{tp.items.toLocaleString()} furnishings · {tp.visitors} visitors</div>
				<div class="realms">{#each tp.realms as r, i (i)}{#if imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt={r.name} title={r.name} />{:else}<span class="muted small">{r.name}</span>{/if}{/each}</div>
			</section>
		{/if}

		{#if data.profile?.bosses.length}
			<section class="panel" data-testid="bosses">
				<h2><Icon name="boss" size={18} /> Boss kills</h2>
				<ol class="bosses">
					{#each topBosses(data.profile.bosses, allBosses) as b (b.name)}<li><span>{b.name}</span><strong>{b.kills}</strong></li>{/each}
				</ol>
				{#if data.profile.bosses.length > 6}
					<button type="button" onclick={() => (allBosses = !allBosses)}>{allBosses ? 'Show fewer' : `Show all ${data.profile.bosses.length}`}</button>
				{/if}
			</section>
		{/if}
	</div>

	<div class="three">
		{#each KINDS as k (k.key)}
			{@const view = data.challenges[k.key]}
			<section class="panel">
				<h2>{k.title}</h2>
				<div data-testid="{k.key}-current">
					{#if view.current}
						<p>{result(k.key, view.current)} · ends in <Countdown at={view.current.end} {now} /></p>
						{#each view.current.teams as team, i (i)}
							<div class="team">{#each team as c (c.id)}{#if imgSrc(c.icon)}<img src={imgSrc(c.icon)} alt={c.name} title={c.name} />{:else}<span class="initial" title={c.name}>{c.name.slice(0, 1)}</span>{/if}{/each}</div>
						{/each}
					{:else}
						<p class="muted">Not attempted this cycle</p>
					{/if}
				</div>
				{#if view.past.length}
					<h3>Past runs</h3>
					<table data-testid="{k.key}-past">
						<thead><tr><th>Started</th><th>Result</th></tr></thead>
						<tbody>
							{#each view.past as r (r.season)}
								<tr><td>{r.start?.slice(0, 10) ?? r.season}</td><td>{result(k.key, r)}</td></tr>
							{/each}
						</tbody>
					</table>
				{/if}
			</section>
		{/each}
	</div>
{/if}

<style>
	section.panel { margin-bottom: 12px; }
	.tiles { display: grid; grid-template-columns: repeat(auto-fill, minmax(130px, 1fr)); gap: 10px; }
	.tile { background: var(--panel-2); border-radius: 10px; padding: 8px 12px; display: grid; grid-template-columns: auto 1fr; column-gap: 8px; align-items: center; }
	.tile .ic { grid-row: span 2; color: var(--avg-pity); }
	.tile .v { font-size: 18px; font-weight: 700; }
	.regions { display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 10px; }
	.three { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; }
	@media (max-width: 900px) { .three { grid-template-columns: 1fr; } }
	.three section.panel { margin-bottom: 0; }
	.three + .three { margin-top: 12px; }
	h2 { display: flex; align-items: center; gap: 6px; }
	.bars { list-style: none; padding: 0; margin: 0 0 8px; display: grid; gap: 3px; font-size: 12px; }
	.bars li { display: grid; grid-template-columns: 64px 1fr 24px; gap: 6px; align-items: center; }
	.bar { height: 7px; background: var(--line); border-radius: 4px; overflow: hidden; }
	.bar span { display: block; height: 100%; }
	.big { font-size: 22px; font-weight: 700; }
	.sm { width: 18px; height: 18px; vertical-align: -4px; margin-right: 4px; }
	.realms { display: flex; gap: 4px; margin-top: 6px; }
	.realms img { width: 28px; height: 28px; border-radius: 6px; }
	.bosses { padding-left: 18px; margin: 0 0 6px; display: grid; gap: 2px; font-size: 13px; }
	.bosses li span { display: inline-block; min-width: 70%; }
	.small { font-size: 12px; }
	.team img { width: 36px; height: 36px; border-radius: 50%; }
	.initial { width: 36px; height: 36px; border-radius: 50%; background: var(--panel-2); display: inline-flex;
		align-items: center; justify-content: center; font-weight: 600; }
	.team { display: flex; gap: 4px; margin: 4px 0; }
	th { text-align: left; font-size: 12px; color: var(--muted); font-weight: 500; padding-right: 14px; }
</style>
```

- [ ] **Step 3: Check, unit tests and build**

Run (from `frontend/`): `npm run check && npx vitest run && npm run build`
Expected: 0 errors, 0 warnings; all vitest pass; build ok.

- [ ] **Step 4: Run the Profile e2e**

Run: `PYTHON=PY npx playwright test e2e/profile.spec.ts`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/routes/profile/+page.svelte frontend/e2e/profile.spec.ts
git commit -m "feat(profile): enka-style Profile page with showcase, tiles, exploration, roster, teapot and bosses"
```

---

### Task 12: Final verification

**Files:** none new (fixes only if something fails).

- [ ] **Step 1: Full backend suite** — from `backend/`: `PY -m pytest -q`. Expected: all pass (615 at start plus the new tests), no new warnings.
- [ ] **Step 2: Full frontend checks** — from `frontend/`: `npm run check` (0 errors, 0 warnings), `npx vitest run` (all pass), `npm run build` (ok).
- [ ] **Step 3: Full e2e** — `PYTHON=PY npx playwright test`. Expected: all pass (60 at start; Wishes +1, Profile +1 → 62). Re-run once if a test that never touched this work flakes; report it if it fails twice.
- [ ] **Step 4: Privacy check of the branch diff** — `git diff origin/main --stat` and `git diff origin/main | grep -n -i -E "nickname|in_game_avatar|cookie|ltoken|authkey=|@gmail|C:\\\\Users|/Users/"`. Expected: only the existing `SECRET-NICK` test fixtures and test assertions that identity is absent; no real names, paths or tokens. Also confirm no new host appears: `git diff origin/main | grep -n -E "https?://" | grep -v -E "x\.test|act-upload\.hoyoverse\.com|enka\.network|example"` → nothing in app code.
- [ ] **Step 5: Look at both pages in the dev app** — start the seeded app as the e2e config does (or `python run.py` on a copy of real data, never the real DB without a backup) and check at 1400 px and 900 px wide: Wishes tiles, pills, the four chart rows, the 5★ list; Profile header, showcase panel and editor, tiles, region rings, the three-card rows. Fix any overflow.
- [ ] **Step 6: Note for the user** — sub-area percentages assume genshin.py's per-mille scale (as for regions). On the next real sync, compare one region's sub-areas with the game; if they read 10× too small or too large, adjust `_area_pct` in `backend/app/sync/chronicle.py` and its test.
- [ ] **Step 7: Commit any fixes** with a message naming what was fixed.
