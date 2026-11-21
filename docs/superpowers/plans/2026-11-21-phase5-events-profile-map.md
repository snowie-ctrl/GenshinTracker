# Phase 5 — Events, Profile, Map Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn on the last three pages — Events (live banners, events with Done ticks and primogem totals, reset countdowns, banner history with the user's pulls), Profile (Battle Chronicle plus a kept history of Abyss/Theater/Stygian runs) and Map (two embedded maps with a fallback) — and complete the Dashboard.

**Architecture:** Three new throttled sync parts (`calendar`, `profile`, `challenges`) call genshin.py from `sync/hoyolab.py`; pure mappers in `sync/chronicle.py` turn genshin.py models into our dataclasses. Current calendar and profile data are stored as JSON snapshots (`hoyolab_snapshot`); challenge cycles go to `challenge_run` (kept forever); Done ticks to `event_done`. Pure view modules `events/` and `profile/` build API payloads; `mapcheck.py` checks once a day whether each map site allows embedding. New SvelteKit pages read only the local API.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2 + Alembic, SQLite, httpx, genshin.py 1.7.32, pytest; SvelteKit (Svelte 5 runes, TypeScript, adapter-static), Vitest, Playwright.

**Spec:** [docs/superpowers/specs/2026-11-21-phase5-events-profile-map-design.md](../specs/2026-11-21-phase5-events-profile-map-design.md)

**Where to work:** a git worktree on branch `phase5-events-profile-map`. Milestones: **M1 Events = Tasks 1–7**, **M2 Profile = Tasks 8–9**, **M3 Map = Tasks 10–11**. After each milestone's last task passes review, push the branch (user preference) after checking nothing sensitive goes with it.

## Global Constraints

- Only `backend/app/sync/hoyolab.py` calls HoYoLAB; `sync/chronicle.py` only maps already-fetched objects. `events/`, `profile/` make no network calls. `mapcheck.py` only requests the two fixed public map URLs, with no cookies.
- Cookie values, UID, nickname, signature, avatar and region are never stored, logged or returned. `UserInfo.nickname`, `server`, `icon`, `in_game_avatar` are dropped in the mapper.
- New sync parts run in this order after `gaps`: `calendar`, `profile`, `challenges`. Throttle: for triggers `auto` and `connect`, a part runs only if its last successful (not skipped) run is more than **60 minutes** old, otherwise it records `{"ok": True, "skipped": "fresh"}`. Trigger `manual` always runs them. Trigger `gaps` never runs them.
- Times inside snapshots and payloads are naive-UTC ISO strings with a `Z` suffix (`app.timeutil.iso`).
- Primogems: a reward counts as primogems when its id is `201` or its name is `Primogem`.
- Reset fallbacks (server time, region offsets from `app.servertime`): daily 04:00; weekly Monday 04:00; Spiral Abyss the **16th** 04:00; Imaginarium Theater the **1st** 04:00; Stygian Onslaught has no fallback (hidden when the calendar has no period).
- `event_done` rows older than **60 days** whose event is not in the calendar snapshot are deleted at startup.
- Map URLs: HoYoLAB `https://act.hoyolab.com/ys/app/interactive-map/index.html`; AppSample `https://genshin-impact-map.appsample.com/`. Embed check cached **24 h** in `game_meta` keys `map_embed_hoyolab` / `map_embed_appsample` as `{"allowed": bool | null, "checked_at": iso}`.
- Setting `default_map`: `"hoyolab"` (default) or `"appsample"`.
- Banner history page size **50**.
- Every new table goes through Alembic migration `0005`; `test_models_match_migrations` stays green.
- Fixtures and the dev seed use made-up data only (UID `800000001`); live-check notes contain no UID, nickname or cookie.
- `localStorage` access always wrapped in try/catch.
- Copy texts (exact): `Sync to load the event calendar`, `N left · X primos unclaimed` (rendered with numbers), `All events done ✓`, `Not attempted this cycle`, `This map doesn't allow embedding`, `Open in new tab`, `Sync to load your profile`.
- Commands (PowerShell, from the worktree root): backend `cd backend; <repo>\.venv\Scripts\python.exe -m pytest -q`; frontend `cd frontend; npm run check; npm test; npm run build`; e2e `$env:PYTHON='<repo>\.venv\Scripts\python.exe'; npm run e2e` (needs `npm run build` first). `<repo>` = `C:\Users\smoki\Documents\Code-Development\GenshinTracker`.

### Refinements made while planning (added to the spec as §13 in Task 11)

1. HoYoLAB's profile has no world level; the header shows AR and days active only.
2. `challenge_run.season` is HoYoLAB's own period id as a string (Abyss `season`, Theater `schedule.id`, Stygian `season.id`) — stable and unique, unlike a formatted date.
3. A part's last success for the throttle is read from `sync_run` (newest run whose part has `ok` and no `skipped`), the same way for all three parts.
4. A live banner's "your pulls" uses the Phase 3 `game_banner` window of the same pool that contains the banner's start and shares a featured 5★; no match → no pull count shown.
5. The HoYoLAB calendar marks events `is_finished`; the spec keeps the manual tick, so this flag is ignored (not stored).

## Review Focus

1. **The calendar has no current Abyss/Theater period (between versions)** → the reset row still shows Abyss/Theater from the fallback rules and hides Stygian, never an error or a past date. Test in Task 4 (`test_resets_fallback_when_calendar_has_no_challenges`).
2. **A manual Sync now right after an auto sync** → calendar/profile/challenges are fetched again; an auto sync within 60 minutes skips them. Test in Task 3 (`test_throttle_skips_fresh_parts_on_auto_but_not_manual`).
3. **Abyss not attempted this cycle (0 battles) or locked** → no `challenge_run` row, Profile shows "Not attempted this cycle", previous cycles stay listed. Tests in Task 2 (`test_abyss_not_attempted_gives_none`) and Task 8 (`test_challenge_views_current_and_past`).
4. **The user ticks an event Done, then the event leaves the calendar** → nothing breaks; the tick is ignored for counts and cleaned up after 60 days. Test in Task 4 (`test_cleanup_event_done`).
5. **The map site is unreachable or the app is offline** → status `allowed: null`, the iframe is tried, Open in new tab still shown; no crash and no repeated fetch inside 24 h. Test in Task 10 (`test_map_status_offline_and_failure`).

---

## File Structure

**Backend — new**

| File | Responsibility |
|---|---|
| `backend/migrations/versions/0005_events_profile.py` | `hoyolab_snapshot`, `challenge_run`, `event_done` |
| `backend/app/sync/chronicle.py` | Dataclasses + pure mappers: calendar, profile, Abyss, Theater, Stygian |
| `backend/app/events/__init__.py`, `backend/app/events/view.py` | Live banners, events, events left, resets, banner history, Done cleanup |
| `backend/app/profile/__init__.py`, `backend/app/profile/view.py` | Profile view, challenge views, profile summary |
| `backend/app/mapcheck.py` | Embed-header parsing, cached embed status |
| `backend/app/api/events.py`, `backend/app/api/profile.py`, `backend/app/api/maps.py` | Endpoints |
| `backend/tests/test_chronicle.py`, `test_sync_chronicle.py`, `test_events_view.py`, `test_api_events.py`, `test_profile_view.py`, `test_api_profile.py`, `test_mapcheck.py`, `test_api_maps.py` | Tests |
| `docs/superpowers/notes/2026-11-21-phase5-chronicle-findings.md` | Live-check findings (Task 2) |

**Backend — modified:** `app/db/models.py`, `app/settings/store.py`, `app/sync/hoyolab.py`, `app/sync/persist.py`, `app/sync/runner.py`, `app/smoke.py`, `app/api/__init__.py`, `app/api/dashboard.py`, `app/api/settings.py`, `app/main.py`, `app/devseed.py`, `tests/fakes.py`, `tests/test_db.py`, `tests/test_sync_runner.py`, `tests/test_api_settings.py`, `tests/test_devseed.py`.

**Frontend — new:** `src/lib/events.ts` (+ `events.test.ts`), `src/lib/maps.ts` (+ `maps.test.ts`), `src/lib/Countdown.svelte`, `src/routes/events/+page.svelte`, `src/routes/profile/+page.svelte`, `src/routes/map/+page.svelte`, `e2e/events.spec.ts`, `e2e/profile.spec.ts`, `e2e/map.spec.ts`.

**Frontend — modified:** `src/lib/types.ts`, `src/lib/api.ts`, `src/routes/+layout.svelte`, `src/routes/+page.svelte`, `src/routes/settings/+page.svelte`. Docs: `README.md`, spec §13.

---

## Milestone 1 — Events

### Task 1: Schema (migration 0005) and the default-map setting

**Files:**
- Create: `backend/migrations/versions/0005_events_profile.py`
- Modify: `backend/app/db/models.py`, `backend/app/settings/store.py`
- Test: `backend/tests/test_db.py`

**Interfaces:**
- Produces: models `HoyolabSnapshot(part, data, fetched_at)`, `ChallengeRun(kind, season, start, end, summary, teams, seen_at, updated_at)`, `EventDone(event_id, done_at)`; setting key `default_map` (default `"hoyolab"`).

- [ ] **Step 1: Write the failing tests** — append to `backend/tests/test_db.py`:

```python
def test_phase5_tables_exist(paths):
    engine = make_engine(paths.db_file)
    migrate(engine)
    names = set(inspect(engine).get_table_names())
    engine.dispose()
    assert {"hoyolab_snapshot", "challenge_run", "event_done"} <= names


def test_default_map_setting(session_factory):
    from app.settings.store import get_setting, set_setting
    with session_factory.begin() as s:
        assert get_setting(s, "default_map") == "hoyolab"
        set_setting(s, "default_map", "appsample")
    with session_factory() as s:
        assert get_setting(s, "default_map") == "appsample"
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd backend; <repo>\.venv\Scripts\python.exe -m pytest tests/test_db.py -q`
Expected: FAIL (tables missing; `KeyError: 'default_map'`).

- [ ] **Step 3: Models** — add to `backend/app/db/models.py` (account data section for the snapshot, user data section for the others):

```python
class HoyolabSnapshot(Base):
    __tablename__ = "hoyolab_snapshot"
    part: Mapped[str] = mapped_column(String, primary_key=True)          # calendar | profile
    data: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)


class ChallengeRun(Base):
    __tablename__ = "challenge_run"
    kind: Mapped[str] = mapped_column(String, primary_key=True)          # abyss | theater | stygian
    season: Mapped[str] = mapped_column(String, primary_key=True)        # HoYoLAB period id
    start: Mapped[str | None] = mapped_column(String, nullable=True)     # iso UTC "...Z"
    end: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[dict] = mapped_column(JSON)
    teams: Mapped[list] = mapped_column(JSON)
    seen_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class EventDone(Base):
    __tablename__ = "event_done"
    event_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    done_at: Mapped[datetime] = mapped_column(DateTime)
```

- [ ] **Step 4: Migration** — `backend/migrations/versions/0005_events_profile.py`:

```python
"""phase 5 events, profile, map

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-21
"""
from alembic import op
import sqlalchemy as sa

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hoyolab_snapshot",
        sa.Column("part", sa.String(), primary_key=True),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "challenge_run",
        sa.Column("kind", sa.String(), primary_key=True),
        sa.Column("season", sa.String(), primary_key=True),
        sa.Column("start", sa.String(), nullable=True),
        sa.Column("end", sa.String(), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("teams", sa.JSON(), nullable=False),
        sa.Column("seen_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
    )
    op.create_table(
        "event_done",
        sa.Column("event_id", sa.Integer(), primary_key=True, autoincrement=False),
        sa.Column("done_at", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("event_done")
    op.drop_table("challenge_run")
    op.drop_table("hoyolab_snapshot")
```

If `test_models_match_migrations` reports an autoincrement difference for `event_done.event_id`, add `autoincrement=False` to the model's `mapped_column` too.

- [ ] **Step 5: Setting** — in `backend/app/settings/store.py` add to `DEFAULTS`: `"default_map": "hoyolab",   # hoyolab | appsample`.

- [ ] **Step 6: Run tests** — `-m pytest tests/test_db.py tests/test_settings_store.py -q` → PASS; then the full suite once.

- [ ] **Step 7: Commit**

```bash
git add backend/migrations/versions/0005_events_profile.py backend/app/db/models.py backend/app/settings/store.py backend/tests/test_db.py
git commit -m "feat(phase5): snapshot, challenge history and event-done tables; default map setting"
```

---

### Task 2: Chronicle mappers, source methods, smoke flags, live check

**Files:**
- Create: `backend/app/sync/chronicle.py`, `backend/tests/test_chronicle.py`, `docs/superpowers/notes/2026-11-21-phase5-chronicle-findings.md`
- Modify: `backend/app/sync/hoyolab.py`, `backend/app/smoke.py`, `backend/tests/fakes.py`

**Interfaces:**
- Produces (`app.sync.chronicle`):
  - dataclasses `BannerItem(id, name, icon, rarity, kind)`, `LiveBanner(id, pool, name, version, start, end, items)`, `Reward(id, name, icon, count, rarity)`, `EventInfo(id, name, description, start, end, rewards)`, `ChallengePeriod(kind, name, start, end)`, `CalendarInfo(banners, events, challenges)`, `Offering(name, level)`, `RegionInfo(id, name, explored, reputation, offerings)`, `ProfileStats(ar, days_active, achievements, characters, chests: dict[str,int], oculi: dict[str,int], waypoints, domains)`, `ProfileInfo(stats, regions)`, `ChallengeRunInfo(kind, season, start, end, summary, teams)`
  - `to_calendar(cal) -> CalendarInfo`, `to_profile(user) -> ProfileInfo`, `to_abyss_run(abyss) -> ChallengeRunInfo | None`, `to_theater_runs(theater) -> list[ChallengeRunInfo]`, `to_stygian_runs(items) -> list[ChallengeRunInfo]`, `to_json(obj) -> dict` (`dataclasses.asdict`), `character_ids(info) -> set[int]` (all character ids in a calendar or list of runs)
  - `HoyolabSource` gains `get_calendar() -> CalendarInfo`, `get_profile() -> ProfileInfo`, `get_challenges() -> list[ChallengeRunInfo]`; `GenshinPySource` implements them; `tests/fakes.FakeSource` implements them (calls recorded as plain strings `"calendar"`, `"profile"`, `"challenges"`).
  - `python -m app.smoke --chronicle`: live, read-only summary of all five calls.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_chronicle.py`:

```python
from datetime import datetime, timezone
from types import SimpleNamespace as NS

from app.sync.chronicle import (
    character_ids, to_abyss_run, to_calendar, to_json, to_profile, to_stygian_runs, to_theater_runs,
)

T0, T1 = 1763870400, 1765166400     # 2025-11-23 04:00Z, 2025-12-08 04:00Z


def utc(ts):
    return datetime.fromtimestamp(ts, timezone.utc)


def banner(id=1, chars=(), weapons=(), start=T0, end=T1, name="Tide"):
    return NS(id=id, version="6.2", name=name, type=1, characters=list(chars), weapons=list(weapons),
              start_timestamp=start, end_timestamp=end)


def char(id, rarity=5, name="Furina"):
    return NS(id=id, icon=f"https://x/{id}.png", name=name, element="Hydro", rarity=rarity)


def event(id=9001, rewards=(), **details):
    base = dict(id=id, name="Fishing Fest", description="<p>Catch <b>fish</b></p>", strategy="", type="ActTypeOther",
                start_timestamp=T0, end_timestamp=T1, status=2, countdown_seconds=10, rewards=list(rewards),
                is_finished=False, abyss_detail=None, theater_detail=None, stygian_detail=None)
    base.update(details)
    return NS(**base)


def reward(id=201, name="Primogem", num=420):
    return NS(id=id, name=name, icon="https://x/r.png", wiki_url="", num=num, rarity=5, homepage_show=True)


def test_calendar_maps_banners_events_and_challenges():
    cal = NS(
        character_banners=[banner(chars=[char(10000089), char(10000032, 4, "Bennett")])],
        weapon_banners=[banner(id=2, weapons=[NS(id=11509, icon="w", rarity=5, name="Mistsplitter", wiki_url="")])],
        chronicled_banners=[],
        events=[event(rewards=[reward(), reward(104003, "Hero's Wit", 10)])],
        challenges=[event(id=1, name="Spiral Abyss", abyss_detail=NS(unlocked=True)),
                    event(id=2, name="Imaginarium Theater", theater_detail=NS(unlocked=True)),
                    event(id=3, name="Stygian Onslaught", stygian_detail=NS(unlocked=True)),
                    event(id=4, name="Something else")],
    )
    info = to_calendar(cal)
    b = info.banners[0]
    assert (b.pool, b.start, b.end) == ("character", "2025-11-23T04:00:00Z", "2025-12-08T04:00:00Z")
    assert [(i.id, i.rarity, i.kind) for i in b.items] == [(10000089, 5, "character"), (10000032, 4, "character")]
    assert info.banners[1].pool == "weapon" and info.banners[1].items[0].kind == "weapon"
    e = info.events[0]
    assert e.description == "Catch fish"
    assert [(r.id, r.count) for r in e.rewards] == [(201, 420), (104003, 10)]
    assert [(c.kind, c.end) for c in info.challenges] == [
        ("abyss", "2025-12-08T04:00:00Z"), ("theater", "2025-12-08T04:00:00Z"), ("stygian", "2025-12-08T04:00:00Z")]
    assert character_ids(info) == {10000089, 10000032}
    assert to_json(info)["events"][0]["rewards"][0]["name"] == "Primogem"


def test_zero_timestamps_become_none_and_traveler_is_canonical():
    cal = NS(character_banners=[banner(chars=[char(10000007, name="Traveler")], start=0, end=0)],
             weapon_banners=[], chronicled_banners=[], events=[], challenges=[])
    b = to_calendar(cal).banners[0]
    assert (b.start, b.end, b.items[0].id) == (None, None, 10000005)


def test_profile_drops_identity_and_maps_regions():
    user = NS(
        info=NS(nickname="SECRET-NICK", server="os_euro", level=60, icon="i", in_game_avatar="a"),
        stats=NS(achievements=900, days_active=1200, characters=95, spiral_abyss="12-3",
                 anemoculi=66, geoculi=131, dendroculi=271, electroculi=181, hydroculi=271, pyroculi=200,
                 lunoculi=0, cryoculi=0, common_chests=3000, exquisite_chests=2000, precious_chests=600,
                 luxurious_chests=200, remarkable_chests=100, unlocked_waypoints=400, unlocked_domains=70,
                 max_friendship_characters=40),
        explorations=[NS(id=1, parent_id=0, name="Mondstadt", raw_explored=1000, type="Reputation", level=8,
                         offerings=[NS(name="Frostbearing Tree", level=12, icon="")]),
                      NS(id=9, parent_id=0, name="Enkanomiya", raw_explored=987, type="Offering", level=0,
                         offerings=[])],
        characters=[], teapot=None,
    )
    p = to_profile(user)
    assert (p.stats.ar, p.stats.days_active, p.stats.achievements) == (60, 1200, 900)
    assert p.stats.oculi["anemoculi"] == 66 and p.stats.chests["luxurious"] == 200
    assert [(r.name, r.explored, r.reputation) for r in p.regions] == [("Mondstadt", 100.0, 8), ("Enkanomiya", 98.7, None)]
    assert "SECRET-NICK" not in str(to_json(p))


def abyss(battles=12, season=101):
    team = [NS(id=10000089), NS(id=10000032)]
    return NS(unlocked=True, season=season, start_time=utc(T0), end_time=utc(T1), total_battles=battles,
              total_wins=battles, max_floor="12-3", total_stars=36,
              floors=[NS(floor=12, stars=9, chambers=[NS(chamber=1, stars=3, battles=[NS(half=1, characters=team)])])])


def test_abyss_run():
    run = to_abyss_run(abyss())
    assert (run.kind, run.season, run.start) == ("abyss", "101", "2025-11-23T04:00:00Z")
    assert run.summary == {"stars": 36, "max_floor": "12-3", "wins": 12, "battles": 12}
    assert run.teams == [[10000089, 10000032]]


def test_abyss_not_attempted_gives_none():
    assert to_abyss_run(abyss(battles=0)) is None
    assert to_abyss_run(NS(unlocked=False, season=1, start_time=utc(T0), end_time=utc(T1), total_battles=0,
                           total_wins=0, max_floor="0-0", total_stars=0, floors=[])) is None


def test_theater_and_stygian_runs():
    act = NS(characters=[NS(id=10000073), NS(id=10000025)])
    theater = NS(unlocked=True, datas=[
        NS(has_data=True, acts=[act, act], stats=NS(difficulty=3, best_record=10, medal_num=8),
           schedule=NS(id=77, start_datetime=utc(T0), end_datetime=utc(T1))),
        NS(has_data=False, acts=[], stats=NS(difficulty=0, best_record=0, medal_num=0),
           schedule=NS(id=76, start_datetime=utc(T0), end_datetime=utc(T1))),
    ])
    runs = to_theater_runs(theater)
    assert [(r.season, r.summary) for r in runs] == [("77", {"act": 10, "difficulty": 3, "medals": 8})]
    assert runs[0].teams == [[10000073, 10000025], [10000073, 10000025]]
    sty = [NS(season=NS(id=5, name="S", start_at=utc(T0), end_at=utc(T1)),
              single_player=NS(has_data=True, best_record=NS(difficulty=4, time_used=95, icon=""),
                               challenges=[NS(team=[NS(id=10000089)])]),
              multi_player=NS(has_data=False, best_record=None, challenges=[]))]
    s = to_stygian_runs(sty)
    assert [(r.kind, r.season, r.summary, r.teams) for r in s] == [
        ("stygian", "5", {"difficulty": 4, "time_used": 95}, [[10000089]])]
    assert to_theater_runs(NS(unlocked=False, datas=[])) == []
```

- [ ] **Step 2: Run to verify they fail**

Run: `-m pytest tests/test_chronicle.py -q` → FAIL (`ModuleNotFoundError: app.sync.chronicle`).

- [ ] **Step 3: Implement** — `backend/app/sync/chronicle.py`:

```python
"""Map genshin.py Battle Chronicle models to our own dataclasses. Pure: no network.
Identity fields (nickname, server, avatars) are dropped here and never leave this module."""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.gamedata.yatta import canonical_id
from app.timeutil import iso

POOLS = (("character_banners", "character"), ("weapon_banners", "weapon"), ("chronicled_banners", "chronicled"))
CHALLENGE_KINDS = (("abyss_detail", "abyss"), ("theater_detail", "theater"), ("stygian_detail", "stygian"))
CHESTS = ("common", "exquisite", "precious", "luxurious", "remarkable")
OCULI = ("anemoculi", "geoculi", "electroculi", "dendroculi", "hydroculi", "pyroculi", "cryoculi", "lunoculi")
TAG = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class BannerItem:
    id: int
    name: str
    icon: str
    rarity: int
    kind: str                       # character | weapon


@dataclass(frozen=True)
class LiveBanner:
    id: int
    pool: str                       # character | weapon | chronicled
    name: str
    version: str
    start: str | None
    end: str | None
    items: list[BannerItem]


@dataclass(frozen=True)
class Reward:
    id: int
    name: str
    icon: str
    count: int
    rarity: int


@dataclass(frozen=True)
class EventInfo:
    id: int
    name: str
    description: str
    start: str | None
    end: str | None
    rewards: list[Reward]


@dataclass(frozen=True)
class ChallengePeriod:
    kind: str                       # abyss | theater | stygian
    name: str
    start: str | None
    end: str | None


@dataclass(frozen=True)
class CalendarInfo:
    banners: list[LiveBanner]
    events: list[EventInfo]
    challenges: list[ChallengePeriod]


@dataclass(frozen=True)
class Offering:
    name: str
    level: int


@dataclass(frozen=True)
class RegionInfo:
    id: int
    name: str
    explored: float                 # percent, one decimal
    reputation: int | None
    offerings: list[Offering]


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


@dataclass(frozen=True)
class ProfileInfo:
    stats: ProfileStats
    regions: list[RegionInfo]


@dataclass(frozen=True)
class ChallengeRunInfo:
    kind: str
    season: str
    start: str | None
    end: str | None
    summary: dict
    teams: list[list[int]] = field(default_factory=list)


def _ts(value: Any) -> str | None:
    ts = int(value or 0)
    return iso(datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None)) if ts > 0 else None


def _dt(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return iso(value)


def _plain(text: str) -> str:
    return " ".join(TAG.sub(" ", text or "").split())


def _banner(b: Any, pool: str) -> LiveBanner:
    items = [BannerItem(canonical_id(c.id), c.name, c.icon, int(c.rarity), "character") for c in b.characters]
    items += [BannerItem(int(w.id), w.name, w.icon, int(w.rarity), "weapon") for w in b.weapons]
    return LiveBanner(int(b.id), pool, b.name, str(b.version or ""), _ts(b.start_timestamp), _ts(b.end_timestamp), items)


def to_calendar(cal: Any) -> CalendarInfo:
    banners = [_banner(b, pool) for attr, pool in POOLS for b in getattr(cal, attr, None) or []]
    events = [EventInfo(int(e.id), e.name, _plain(e.description), _ts(e.start_timestamp), _ts(e.end_timestamp),
                        [Reward(int(r.id), r.name, r.icon, int(r.num), int(r.rarity)) for r in e.rewards])
              for e in cal.events]
    challenges = []
    for e in cal.challenges:
        kind = next((k for attr, k in CHALLENGE_KINDS if getattr(e, attr, None) is not None), None)
        if kind is not None:
            challenges.append(ChallengePeriod(kind, e.name, _ts(e.start_timestamp), _ts(e.end_timestamp)))
    return CalendarInfo(banners, events, challenges)


def to_profile(user: Any) -> ProfileInfo:
    s = user.stats
    stats = ProfileStats(
        ar=int(user.info.level), days_active=int(s.days_active), achievements=int(s.achievements),
        characters=int(s.characters),
        chests={c: int(getattr(s, f"{c}_chests", 0) or 0) for c in CHESTS},
        oculi={o: int(getattr(s, o, 0) or 0) for o in OCULI},
        waypoints=int(s.unlocked_waypoints), domains=int(s.unlocked_domains),
    )
    regions = [RegionInfo(int(e.id), e.name, round(int(e.raw_explored) / 10, 1),
                          int(e.level) if e.type == "Reputation" else None,
                          [Offering(o.name, int(o.level)) for o in e.offerings])
               for e in user.explorations if int(getattr(e, "parent_id", 0) or 0) == 0]
    return ProfileInfo(stats, regions)


def to_abyss_run(a: Any) -> ChallengeRunInfo | None:
    if not a.unlocked or int(a.total_battles) == 0:
        return None
    teams = [[canonical_id(c.id) for c in b.characters]
             for f in a.floors for ch in f.chambers for b in ch.battles]
    return ChallengeRunInfo("abyss", str(a.season), _dt(a.start_time), _dt(a.end_time),
                            {"stars": int(a.total_stars), "max_floor": a.max_floor,
                             "wins": int(a.total_wins), "battles": int(a.total_battles)}, teams)


def to_theater_runs(t: Any) -> list[ChallengeRunInfo]:
    if not t.unlocked:
        return []
    runs = []
    for d in t.datas:
        if not d.has_data:
            continue
        runs.append(ChallengeRunInfo(
            "theater", str(d.schedule.id), _dt(d.schedule.start_datetime), _dt(d.schedule.end_datetime),
            {"act": int(d.stats.best_record), "difficulty": int(d.stats.difficulty), "medals": int(d.stats.medal_num)},
            [[canonical_id(c.id) for c in act.characters] for act in d.acts]))
    return runs


def to_stygian_runs(items: Any) -> list[ChallengeRunInfo]:
    runs = []
    for h in items or []:
        data = h.single_player
        if not data.has_data:
            continue
        summary = ({"difficulty": int(data.best_record.difficulty), "time_used": int(data.best_record.time_used)}
                   if data.best_record is not None else {})
        runs.append(ChallengeRunInfo("stygian", str(h.season.id), _dt(h.season.start_at), _dt(h.season.end_at),
                                     summary, [[canonical_id(c.id) for c in ch.team] for ch in data.challenges]))
    return runs


def to_json(obj: Any) -> dict:
    return asdict(obj)


def character_ids(info: CalendarInfo | list[ChallengeRunInfo]) -> set[int]:
    if isinstance(info, CalendarInfo):
        return {i.id for b in info.banners for i in b.items if i.kind == "character"}
    return {cid for run in info for team in run.teams for cid in team}
```

Then in `backend/app/sync/hoyolab.py`: import the three return types from `app.sync.chronicle`, extend the protocol and implement the calls:

```python
from app.sync.chronicle import (
    CalendarInfo, ChallengeRunInfo, ProfileInfo, to_abyss_run, to_calendar, to_profile, to_stygian_runs,
    to_theater_runs,
)
```

```python
class HoyolabSource(Protocol):
    ...existing methods...
    async def get_calendar(self) -> CalendarInfo: ...
    async def get_profile(self) -> ProfileInfo: ...
    async def get_challenges(self) -> list[ChallengeRunInfo]: ...
```

```python
    # in GenshinPySource
    async def get_calendar(self) -> CalendarInfo:
        return to_calendar(await call_api(self._client.get_genshin_event_calendar, self._uid,
                                          lang="en-us", delays=self._delays))

    async def get_profile(self) -> ProfileInfo:
        return to_profile(await call_api(self._client.get_partial_genshin_user, self._uid,
                                         lang="en-us", delays=self._delays))

    async def get_challenges(self) -> list[ChallengeRunInfo]:
        runs: list[ChallengeRunInfo] = []
        for previous in (False, True):
            run = to_abyss_run(await call_api(self._client.get_genshin_spiral_abyss, self._uid,
                                              previous=previous, delays=self._delays))
            if run is not None:
                runs.append(run)
        runs += to_theater_runs(await call_api(self._client.get_imaginarium_theater, self._uid,
                                               delays=self._delays))
        runs += to_stygian_runs(await call_api(self._client.get_stygian_onslaught, self._uid,
                                               delays=self._delays))
        seen: dict[tuple[str, str], ChallengeRunInfo] = {}
        for r in runs:
            seen[(r.kind, r.season)] = r
        return list(seen.values())
```

(`get_imaginarium_theater` without `previous` returns the current and previous periods in `datas`; the live check in Step 6 confirms this. If it only returns one, add a second call with `previous=True` — the dedupe above already handles overlap.)

In `backend/tests/fakes.py` add to `FakeSource.__init__` parameters `calendar=None, profile=None, challenges=None` stored on self, and these methods (each appends a plain string to `self.calls`, honours `self.fail[<part>]`, and returns the stored value or a small default):

```python
    async def get_calendar(self):
        self.calls.append("calendar")
        if "calendar" in self.fail:
            raise self.fail["calendar"]
        return self.calendar if self.calendar is not None else CalendarInfo([], [], [])

    async def get_profile(self):
        self.calls.append("profile")
        if "profile" in self.fail:
            raise self.fail["profile"]
        return self.profile if self.profile is not None else ProfileInfo(
            ProfileStats(60, 100, 500, 40, {}, {}, 300, 50), [])

    async def get_challenges(self):
        self.calls.append("challenges")
        if "challenges" in self.fail:
            raise self.fail["challenges"]
        return list(self.challenges or [])
```

(import `CalendarInfo, ProfileInfo, ProfileStats` from `app.sync.chronicle` at the top of `fakes.py`).

In `backend/app/smoke.py` add a `--chronicle` mode and document it in the module docstring (`python -m app.smoke --chronicle   read-only calendar/profile/abyss/theater/stygian check`):

```python
async def chronicle(source: GenshinPySource) -> None:
    cal = await source.get_calendar()
    print(f"calendar: {len(cal.banners)} banners, {len(cal.events)} events, challenges "
          f"{[(c.kind, c.end) for c in cal.challenges]}")
    for b in cal.banners:
        print(f"  banner {b.pool} {b.name!r} {b.start}..{b.end} items "
              f"{[(i.id, i.rarity) for i in b.items]}")
    for e in cal.events:
        prim = sum(r.count for r in e.rewards if r.id == 201 or r.name == "Primogem")
        print(f"  event {e.id} {e.name!r} ends {e.end}, rewards {[(r.id, r.name, r.count) for r in e.rewards]}, "
              f"primos {prim}")
    p = await source.get_profile()
    print(f"profile: AR {p.stats.ar}, days {p.stats.days_active}, achievements {p.stats.achievements}, "
          f"regions {[(r.name, r.explored, r.reputation, len(r.offerings)) for r in p.regions]}")
    for r in await source.get_challenges():
        print(f"challenge {r.kind} season {r.season} {r.start}..{r.end} summary {r.summary} teams {len(r.teams)}")
```

wired into the existing argument handling the same way `--gaps` is (read the bottom of `smoke.py` and follow its pattern). It must print no UID, nickname or cookie.

- [ ] **Step 4: Run tests** — `-m pytest tests/test_chronicle.py tests/test_hoyolab.py tests/test_sync_runner.py -q` → PASS (the runner does not call the new methods yet); then the full suite.

- [ ] **Step 5: Commit**

```bash
git add backend/app/sync/chronicle.py backend/app/sync/hoyolab.py backend/app/smoke.py backend/tests/fakes.py backend/tests/test_chronicle.py
git commit -m "feat(phase5): chronicle mappers, calendar/profile/challenge source calls, smoke --chronicle"
```

- [ ] **Step 6: Live check (controller-run checkpoint, read-only)** — copy the main checkout's `.env` into the worktree root, run `cd backend; <repo>\.venv\Scripts\python.exe -m app.smoke --chronicle`, then **delete the copied `.env`**. Write `docs/superpowers/notes/2026-11-21-phase5-chronicle-findings.md` with: banner/event/challenge counts; whether every event's rewards include id 201 when primogems are given; whether event ids repeat between two runs a minute apart; challenge kinds found; Theater periods returned without `previous`; whether Abyss/Theater/Stygian report teams; any mapper error. **No UID, nickname, or cookie in the notes.** If a mapper raised, fix it (with a test reproducing the shape) before committing. Commit:

```bash
git add docs/superpowers/notes/2026-11-21-phase5-chronicle-findings.md
git commit -m "docs(phase5): live chronicle check findings"
```

---

### Task 3: Sync parts with throttle and persistence

**Files:**
- Modify: `backend/app/sync/runner.py`, `backend/app/sync/persist.py`, `backend/tests/test_sync_runner.py`
- Test: `backend/tests/test_sync_chronicle.py`

**Interfaces:**
- Consumes: `get_calendar/get_profile/get_challenges` (Task 2), `to_json`, `character_ids`; models from Task 1.
- Produces: `persist.save_snapshot(s, part: str, data: dict, now) -> None`, `persist.save_challenge_runs(s, runs: list[ChallengeRunInfo], now) -> int`, `persist.unknown_character_ids(s, ids: set[int]) -> set[int]`; `runner.CHRONICLE_PARTS = ("calendar", "profile", "challenges")`, `runner.PARTS` includes them; `runner.FRESH_MINUTES = 60`; `runner.last_part_success(s, part) -> datetime | None`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_sync_chronicle.py`:

```python
from app.db.models import ChallengeRun, HoyolabSnapshot, SyncRun
from app.sync.chronicle import CalendarInfo, ChallengeRunInfo, EventInfo, Reward
from app.sync.hoyolab import HoyolabError
from fakes import Clock, FakeSource
from helpers import seed_game
from test_sync_runner import START, last_run, manager

CAL = CalendarInfo([], [EventInfo(9001, "Fest", "", "2026-11-19T04:00:00Z", "2026-12-01T04:00:00Z",
                                  [Reward(201, "Primogem", "", 420, 5)])], [])
RUN = ChallengeRunInfo("abyss", "101", "2026-11-16T04:00:00Z", "2026-12-16T04:00:00Z",
                       {"stars": 36, "max_floor": "12-3", "wins": 12, "battles": 12}, [[10000089, 10000032]])


async def test_parts_store_snapshots_and_runs(paths, session_factory):
    seed_game(session_factory)
    m = manager(paths, session_factory, FakeSource(calendar=CAL, challenges=[RUN]))
    await m.request("manual")
    await m.wait()
    parts = last_run(session_factory).parts
    assert parts["calendar"] == {"ok": True, "count": 1}
    assert parts["profile"] == {"ok": True}
    assert parts["challenges"] == {"ok": True, "count": 1}
    with session_factory() as s:
        assert s.get(HoyolabSnapshot, "calendar").data["events"][0]["id"] == 9001
        assert s.get(HoyolabSnapshot, "profile").data["stats"]["ar"] == 60
        assert s.get(ChallengeRun, ("abyss", "101")).summary["stars"] == 36


async def test_throttle_skips_fresh_parts_on_auto_but_not_manual(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    source = FakeSource(calendar=CAL)
    m = manager(paths, session_factory, source, clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(minutes=30)                     # the auto sync is due (interval 10 min)
    await m.request("auto")
    await m.wait()
    parts = last_run(session_factory).parts
    assert parts["calendar"] == {"ok": True, "skipped": "fresh"}
    assert parts["profile"] == {"ok": True, "skipped": "fresh"}
    clock.advance(minutes=2)
    await m.request("manual")
    await m.wait()
    assert last_run(session_factory).parts["calendar"] == {"ok": True, "count": 1}
    clock.advance(minutes=61)
    await m.request("auto")
    await m.wait()
    assert last_run(session_factory).parts["calendar"] == {"ok": True, "count": 1}
    assert source.calls.count("calendar") == 3


async def test_failure_keeps_previous_snapshot_and_isolates(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(calendar=CAL), clock=clock)
    await m.request("manual")
    await m.wait()
    clock.advance(minutes=2)
    m2 = manager(paths, session_factory, FakeSource(fail={"calendar": HoyolabError("down")}), clock=clock)
    await m2.request("manual")
    await m2.wait()
    parts = last_run(session_factory).parts
    assert parts["calendar"]["ok"] is False and parts["profile"]["ok"] and parts["challenges"]["ok"]
    with session_factory() as s:
        assert s.get(HoyolabSnapshot, "calendar").data["events"][0]["id"] == 9001


async def test_challenge_runs_upsert_never_delete(paths, session_factory):
    seed_game(session_factory)
    clock = Clock(START)
    m = manager(paths, session_factory, FakeSource(challenges=[RUN]), clock=clock)
    await m.request("manual")
    await m.wait()
    better = ChallengeRunInfo("abyss", "101", RUN.start, RUN.end, {**RUN.summary, "stars": 33}, [])
    clock.advance(minutes=2)
    m2 = manager(paths, session_factory, FakeSource(challenges=[better]), clock=clock)
    await m2.request("manual")
    await m2.wait()
    clock.advance(minutes=2)
    m3 = manager(paths, session_factory, FakeSource(challenges=[]), clock=clock)
    await m3.request("manual")
    await m3.wait()
    with session_factory() as s:
        row = s.get(ChallengeRun, ("abyss", "101"))
        assert row.summary["stars"] == 33 and row.seen_at == START


async def test_gaps_only_run_never_runs_chronicle_parts(paths, session_factory):
    seed_game(session_factory)
    source = FakeSource()
    m = manager(paths, session_factory, source)
    await m.request("manual")
    await m.wait()
    before = source.calls.count("calendar")
    m.start_gaps()
    await m.wait()
    assert source.calls.count("calendar") == before
```

In `backend/tests/test_sync_runner.py::test_full_sync_saves_everything` extend the expected parts dict with `"calendar": {"ok": True, "count": 0}, "profile": {"ok": True}, "challenges": {"ok": True, "count": 0}`.

- [ ] **Step 2: Run to verify they fail** — `-m pytest tests/test_sync_chronicle.py -q` → FAIL (no `calendar` part).

- [ ] **Step 3: Persistence** — add to `backend/app/sync/persist.py`:

```python
from app.db.models import ChallengeRun, GameCharacter, HoyolabSnapshot, OwnedCharacter
from app.sync.chronicle import ChallengeRunInfo


def save_snapshot(session: Session, part: str, data: dict, now: datetime) -> None:
    row = session.get(HoyolabSnapshot, part)
    if row is None:
        session.add(HoyolabSnapshot(part=part, data=data, fetched_at=now))
    else:
        row.data, row.fetched_at = data, now
    session.flush()


def save_challenge_runs(session: Session, runs: list[ChallengeRunInfo], now: datetime) -> int:
    for r in runs:
        row = session.get(ChallengeRun, (r.kind, r.season))
        if row is None:
            row = ChallengeRun(kind=r.kind, season=r.season, seen_at=now)
            session.add(row)
        row.start, row.end, row.summary, row.teams, row.updated_at = r.start, r.end, r.summary, r.teams, now
    session.flush()
    return len(runs)


def unknown_character_ids(session: Session, ids: set[int]) -> set[int]:
    return {i for i in ids if session.get(GameCharacter, i) is None and session.get(OwnedCharacter, i) is None}
```

(merge the imports with the file's existing ones).

- [ ] **Step 4: Runner** — in `backend/app/sync/runner.py`:

```python
from datetime import timedelta
from app.sync.chronicle import character_ids, to_json
from app.sync.persist import save_challenge_runs, save_snapshot, unknown_character_ids

CHRONICLE_PARTS = ("calendar", "profile", "challenges")
PARTS = ("roster", "details", "notes", "gaps", *CHRONICLE_PARTS)
FRESH_MINUTES = 60


def last_part_success(session: Session, part: str) -> datetime | None:
    runs = session.scalars(select(SyncRun).where(SyncRun.finished_at.is_not(None), SyncRun.trigger != "gaps")
                           .order_by(SyncRun.id.desc()).limit(50))
    for run in runs:
        p = (run.parts or {}).get(part) or {}
        if p.get("ok") and "skipped" not in p:
            return run.started_at
    return None
```

In `_run`, keep the current trigger in a local (`trigger = self._run_trigger` at the top) and add after the gaps block, still inside `if not expired:` handling:

```python
            for part in CHRONICLE_PARTS:
                if expired:
                    break
                if trigger != "manual":
                    with self._sf() as s:
                        last = last_part_success(s, part)
                    if last is not None and self._clock() - last < timedelta(minutes=FRESH_MINUTES):
                        parts[part] = {"ok": True, "skipped": "fresh"}
                        continue
                try:
                    parts[part], found = await self._chronicle_part(part, source)
                    unknown |= found
                except AuthExpired:
                    expired = True
                except Exception as e:
                    log.warning("Sync part %s failed: %s", part, type(e).__name__)
                    parts[part] = _failure(e)
```

and the helper method:

```python
    async def _chronicle_part(self, part: str, source: HoyolabSource) -> tuple[dict, set[int]]:
        now = self._clock()
        if part == "calendar":
            cal = await source.get_calendar()
            with self._sf.begin() as s:
                save_snapshot(s, "calendar", to_json(cal), now)
                return {"ok": True, "count": len(cal.events)}, unknown_character_ids(s, character_ids(cal))
        if part == "profile":
            profile = await source.get_profile()
            with self._sf.begin() as s:
                save_snapshot(s, "profile", to_json(profile), now)
            return {"ok": True}, set()
        runs = await source.get_challenges()
        with self._sf.begin() as s:
            count = save_challenge_runs(s, runs, now)
            return {"ok": True, "count": count}, unknown_character_ids(s, character_ids(runs))
```

`_run_trigger` is set in `request()` before the task starts, so read it into the local at the start of `_run`. The existing `for part in PARTS: parts.setdefault(...)` on expiry now also covers the new parts.

- [ ] **Step 5: Run tests** — `-m pytest tests/test_sync_chronicle.py tests/test_sync_runner.py tests/test_api_settings.py -q` → PASS; then the full suite. (`test_api_settings` checks the leak test still counts exactly 2 gaps calls.)

- [ ] **Step 6: Commit**

```bash
git add backend/app/sync/runner.py backend/app/sync/persist.py backend/tests/test_sync_chronicle.py backend/tests/test_sync_runner.py
git commit -m "feat(phase5): throttled calendar, profile and challenges sync parts"
```

---

### Task 4: Events logic (`events/view.py`)

**Files:**
- Create: `backend/app/events/__init__.py` (docstring `"""Events page logic: pure functions over the calendar snapshot, Done ticks and banner data."""`), `backend/app/events/view.py`
- Test: `backend/tests/test_events_view.py`

**Interfaces:**
- Consumes: `server_day`, `week_start`, `offset_hours`, `RESET_HOUR` (`app.servertime`); `PoolResult`, `BannerWindow`, `banner_windows`, `load_names` (`app.wishes.pity`); `server_local_now` (`app.wishes.types`); `iso` (`app.timeutil`); models `EventDone`, `HoyolabSnapshot`, `GameBanner`, `GameCharacter`, `GameWeapon`.
- Produces:
  - `parse_iso(s: str | None) -> datetime | None`
  - `PRIMOGEM_ID = 201`, `primogems(rewards: list[dict]) -> int`
  - `event_rows(calendar: dict, done: set[int], now: datetime) -> list[dict]` — `{"id","name","description","start","end","rewards","primogems","done","ending_soon"}`, only events whose end is in the future (or no end), not-done first by end, done last
  - `events_left(rows: list[dict]) -> dict` — `{"count", "primogems"}`
  - `pulls_by_banner(results: dict[str, PoolResult]) -> dict[str, dict]` — `{banner_key: {"pulls": int, "fives": [name], "fours": [name]}}`
  - `live_banners(calendar: dict, now: datetime, windows: dict[str, list[BannerWindow]], pulls: dict[str, dict], offset: int) -> dict` — `{"current": [banner], "upcoming": [banner]}`, each banner = calendar banner fields + `"pulls": dict | None`
  - `resets(calendar: dict | None, now: datetime, region: str | None) -> list[dict]` — `[{"key","label","at"}]` keys in order `daily, weekly, abyss, theater, stygian` (stygian only when the calendar has it)
  - `banner_history(session, pool: str, q: str, page: int, pulls: dict[str, dict]) -> dict` — `{"total","page","page_size","rows"}`; row = `{"key","name","short_name","start","end","featured_5":[item],"featured_4":[item],"pulls"}`, item = `{"id","name","icon","rarity"}`
  - `cleanup_event_done(session, now: datetime) -> int`

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_events_view.py`:

```python
from datetime import datetime, timedelta

from app.db.models import EventDone, GameBanner, HoyolabSnapshot
from app.events.view import (
    banner_history, cleanup_event_done, event_rows, events_left, live_banners, primogems, resets,
)
from app.wishes.pity import BannerWindow
from helpers import seed_game

NOW = datetime(2026, 11, 21, 12, 0, 0)       # Saturday


def ev(id, end, rewards=(), start="2026-11-10T04:00:00Z"):
    return {"id": id, "name": f"E{id}", "description": "", "start": start, "end": end,
            "rewards": [{"id": r[0], "name": r[1], "icon": "", "count": r[2], "rarity": 5} for r in rewards]}


CAL = {"banners": [], "challenges": [], "events": [
    ev(1, "2026-11-30T04:00:00Z", [(201, "Primogem", 420), (104003, "Hero's Wit", 4)]),
    ev(2, "2026-11-22T04:00:00Z", [(201, "Primogem", 60)]),
    ev(3, "2026-12-05T04:00:00Z"),
    ev(4, "2026-11-20T04:00:00Z", [(201, "Primogem", 999)]),        # already ended
]}


def test_primogems_by_id_or_name():
    assert primogems([{"id": 201, "name": "x", "count": 3}, {"id": 9, "name": "Primogem", "count": 2},
                      {"id": 9, "name": "Mora", "count": 50}]) == 5


def test_event_rows_order_done_and_ending_soon():
    rows = event_rows(CAL, {3}, NOW)
    assert [r["id"] for r in rows] == [2, 1, 3]
    assert rows[0]["ending_soon"] is True and rows[1]["ending_soon"] is False
    assert rows[2]["done"] is True
    assert events_left(rows) == {"count": 2, "primogems": 480}


def test_resets_from_calendar_and_fallback_when_calendar_has_no_challenges():
    cal = {"banners": [], "events": [], "challenges": [
        {"kind": "abyss", "name": "A", "start": None, "end": "2026-12-16T04:00:00Z"},
        {"kind": "stygian", "name": "S", "start": None, "end": "2026-12-01T04:00:00Z"}]}
    got = {r["key"]: r["at"] for r in resets(cal, NOW, "os_euro")}
    assert got["daily"] == "2026-11-22T03:00:00Z"          # 04:00 UTC+1
    assert got["weekly"] == "2026-11-23T03:00:00Z"         # Monday 04:00 UTC+1
    assert got["abyss"] == "2026-12-16T04:00:00Z" and got["stygian"] == "2026-12-01T04:00:00Z"
    assert got["theater"] == "2026-12-01T03:00:00Z"        # fallback: the 1st 04:00 server time


def test_resets_fallback_when_calendar_has_no_challenges():
    got = {r["key"]: r["at"] for r in resets({"banners": [], "events": [], "challenges": []}, NOW, "os_usa")}
    assert got["abyss"] == "2026-12-16T09:00:00Z"          # 16th 04:00 UTC-5
    assert got["theater"] == "2026-12-01T09:00:00Z"
    assert "stygian" not in got
    assert [r["key"] for r in resets(None, NOW, "os_asia")] == ["daily", "weekly", "abyss", "theater"]
    past = {"kind": "abyss", "name": "A", "start": None, "end": "2026-11-16T04:00:00Z"}   # already over
    got = {r["key"]: r["at"] for r in resets({"banners": [], "events": [], "challenges": [past]}, NOW, "os_asia")}
    assert got["abyss"] == "2026-12-15T20:00:00Z"          # fallback 16th 04:00 UTC+8


def test_fallback_on_the_reset_day_itself():
    on_16th = datetime(2026, 11, 16, 1, 0, 0)               # 09:00 UTC+8: the 04:00 reset already passed
    got = {r["key"]: r["at"] for r in resets(None, on_16th, "os_asia")}
    assert got["abyss"] == "2026-12-15T20:00:00Z"


def test_live_banners_with_pulls():
    cal = {"events": [], "challenges": [], "banners": [
        {"id": 1, "pool": "character", "name": "Tide", "version": "6.2", "start": "2026-11-18T03:00:00Z",
         "end": "2026-12-09T03:00:00Z", "items": [{"id": 10000089, "name": "Furina", "icon": "", "rarity": 5,
                                                    "kind": "character"}]},
        {"id": 2, "pool": "weapon", "name": "Next", "version": "6.3", "start": "2026-12-10T03:00:00Z",
         "end": "2026-12-30T03:00:00Z", "items": []}]}
    window = BannerWindow("character|2026-11-18 11:00:00|0", "character", "Tide", "Furina",
                          "2026-11-18 11:00:00", "2026-12-09 10:59:59", 0, (10000089,), ())
    pulls = {window.key: {"pulls": 30, "fives": ["Furina"], "fours": []}}
    out = live_banners(cal, NOW, {"character": [window]}, pulls, 8)
    assert [b["id"] for b in out["current"]] == [1] and [b["id"] for b in out["upcoming"]] == [2]
    assert out["current"][0]["pulls"] == {"pulls": 30, "fives": ["Furina"], "fours": []}
    assert out["upcoming"][0]["pulls"] is None


def test_banner_history_filter_search_page(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        for i in range(55):
            s.add(GameBanner(key=f"character|2020-01-{i:02d}|0", pool="character", name=f"Banner {i}",
                             short_name="Furina" if i == 3 else f"B{i}", start=f"2020-{1 + i // 28:02d}-{1 + i % 28:02d} 10:00:00",
                             end="2020-12-31 10:00:00", timezone_dependent=False, timezone_dependent_end=False,
                             order=0, featured_5=[10000089] if i == 3 else [], featured_4=[10000032], version="1.0"))
        s.add(GameBanner(key="weapon|x|0", pool="weapon", name="W", short_name="W", start="2020-01-01 10:00:00",
                         end="2020-01-20 10:00:00", timezone_dependent=False, timezone_dependent_end=False, order=0,
                         featured_5=[], featured_4=[], version="1.0"))
    with session_factory() as s:
        page1 = banner_history(s, "character", "", 1, {})
        page2 = banner_history(s, "character", "", 2, {})
        found = banner_history(s, "character", "furina", 1, {"character|2020-01-03|0": {"pulls": 7, "fives": [], "fours": []}})
    assert page1["total"] == 55 and len(page1["rows"]) == 50 and len(page2["rows"]) == 5
    assert page1["rows"][0]["start"] >= page1["rows"][1]["start"]          # newest first
    assert [r["key"] for r in found["rows"]] == ["character|2020-01-03|0"]
    assert found["rows"][0]["featured_5"][0]["name"] == "Furina" and found["rows"][0]["pulls"]["pulls"] == 7


def test_cleanup_event_done(session_factory):
    with session_factory.begin() as s:
        s.add(HoyolabSnapshot(part="calendar", data={"banners": [], "challenges": [], "events": [ev(1, None)]},
                              fetched_at=NOW))
        s.add(EventDone(event_id=1, done_at=NOW - timedelta(days=90)))     # still in calendar: kept
        s.add(EventDone(event_id=2, done_at=NOW - timedelta(days=90)))     # gone and old: deleted
        s.add(EventDone(event_id=3, done_at=NOW - timedelta(days=10)))     # gone but recent: kept
    with session_factory.begin() as s:
        assert cleanup_event_done(s, NOW) == 1
    with session_factory() as s:
        assert {r.event_id for r in s.query(EventDone)} == {1, 3}
```

- [ ] **Step 2: Run to verify they fail** — `-m pytest tests/test_events_view.py -q` → FAIL (ImportError).

- [ ] **Step 3: Implement** — `backend/app/events/view.py`:

```python
"""Events page and Dashboard cards: pure functions over the calendar snapshot, Done ticks and banner data."""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.db.models import EventDone, GameBanner, GameCharacter, GameWeapon, HoyolabSnapshot
from app.servertime import RESET_HOUR, offset_hours, server_day, week_start
from app.timeutil import iso
from app.wishes.pity import BannerWindow, PoolResult
from app.wishes.types import server_local_now

PRIMOGEM_ID = 201
ENDING_SOON = timedelta(hours=24)
PAGE_SIZE = 50
KEEP_DONE = timedelta(days=60)
FALLBACK_DAY = {"abyss": 16, "theater": 1}
LABELS = {"daily": "Daily reset", "weekly": "Weekly reset", "abyss": "Spiral Abyss",
          "theater": "Imaginarium Theater", "stygian": "Stygian Onslaught"}


def parse_iso(s: str | None) -> datetime | None:
    return None if not s else datetime.fromisoformat(s.rstrip("Z"))


def primogems(rewards: list[dict]) -> int:
    return sum(int(r["count"]) for r in rewards if r["id"] == PRIMOGEM_ID or r["name"] == "Primogem")


def event_rows(calendar: dict, done: set[int], now: datetime) -> list[dict]:
    rows = []
    for e in calendar.get("events", []):
        end = parse_iso(e.get("end"))
        if end is not None and end <= now:
            continue
        rows.append({**e, "primogems": primogems(e["rewards"]), "done": e["id"] in done,
                     "ending_soon": end is not None and end - now <= ENDING_SOON})
    far = datetime.max
    rows.sort(key=lambda r: (r["done"], parse_iso(r.get("end")) or far, r["id"]))
    return rows


def events_left(rows: list[dict]) -> dict:
    left = [r for r in rows if not r["done"]]
    return {"count": len(left), "primogems": sum(r["primogems"] for r in left)}


def pulls_by_banner(results: dict[str, PoolResult]) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for result in results.values():
        for window in result.banner_at.values():
            if window is not None:
                out.setdefault(window.key, {"pulls": 0, "fives": [], "fours": []})["pulls"] += 1
        for view, bucket in [(v, "fives") for v in result.fives] + [(v, "fours") for v in result.fours]:
            if view.banner_key is not None:
                out.setdefault(view.banner_key, {"pulls": 0, "fives": [], "fours": []})[bucket].append(view.name)
    return out


def _window_for(banner: dict, windows: dict[str, list[BannerWindow]], offset: int) -> BannerWindow | None:
    start = parse_iso(banner.get("start"))
    if start is None:
        return None
    local = server_local_now(start + timedelta(minutes=1), offset)
    fives = {i["id"] for i in banner["items"] if i["rarity"] == 5}
    return next((w for w in windows.get(banner["pool"], [])
                 if w.start <= local <= w.end and (not fives or fives & set(w.featured_5))), None)


def live_banners(calendar: dict, now: datetime, windows: dict[str, list[BannerWindow]],
                 pulls: dict[str, dict], offset: int) -> dict:
    current, upcoming = [], []
    for b in calendar.get("banners", []):
        start, end = parse_iso(b.get("start")), parse_iso(b.get("end"))
        if end is not None and end <= now:
            continue
        window = _window_for(b, windows, offset)
        row = {**b, "pulls": pulls.get(window.key) if window is not None else None}
        (upcoming if start is not None and start > now else current).append(row)
    order = {"character": 0, "weapon": 1, "chronicled": 2}
    current.sort(key=lambda r: (order.get(r["pool"], 9), r["start"] or ""))
    upcoming.sort(key=lambda r: r["start"] or "")
    return {"current": current, "upcoming": upcoming}


def _next_month_day(now: datetime, day: int, offset: int) -> datetime:
    local = now + timedelta(hours=offset)
    year, month = local.year, local.month
    for _ in range(2):
        candidate = datetime(year, month, day, RESET_HOUR)
        if candidate > local:
            return candidate - timedelta(hours=offset)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    raise AssertionError("unreachable")


def resets(calendar: dict | None, now: datetime, region: str | None) -> list[dict]:
    offset = offset_hours(region)
    day = server_day(now, region)
    today_reset = datetime(day.year, day.month, day.day) + timedelta(hours=RESET_HOUR - offset)
    at = {"daily": today_reset + timedelta(days=1), "weekly": week_start(now, region) + timedelta(days=7)}
    periods = {c["kind"]: parse_iso(c.get("end")) for c in (calendar or {}).get("challenges", [])}
    for kind in ("abyss", "theater", "stygian"):
        end = periods.get(kind)
        if end is not None and end > now:
            at[kind] = end
        elif kind in FALLBACK_DAY:
            at[kind] = _next_month_day(now, FALLBACK_DAY[kind], offset)
    return [{"key": k, "label": LABELS[k], "at": iso(at[k])} for k in LABELS if k in at]


def _items(session: Session) -> dict[int, dict]:
    out = {w.id: {"id": w.id, "name": w.name, "icon": w.icon, "rarity": w.rarity}
           for w in session.scalars(select(GameWeapon))}
    out.update({c.id: {"id": c.id, "name": c.name, "icon": c.icon, "rarity": c.rarity}
                for c in session.scalars(select(GameCharacter))})
    return out


def banner_history(session: Session, pool: str, q: str, page: int, pulls: dict[str, dict]) -> dict:
    items = _items(session)
    query = select(GameBanner).where(GameBanner.pool == pool)
    text = q.strip().lower()
    if text:
        ids = [i for i, it in items.items() if text in it["name"].lower()]
        matching = [b.key for b in session.scalars(select(GameBanner).where(GameBanner.pool == pool))
                    if set(b.featured_5 or []) & set(ids) or set(b.featured_4 or []) & set(ids)]
        query = query.where(or_(func.lower(GameBanner.name).contains(text),
                                func.lower(GameBanner.short_name).contains(text), GameBanner.key.in_(matching)))
    total = session.scalar(select(func.count()).select_from(query.subquery())) or 0
    page = max(1, page)
    rows = session.scalars(query.order_by(GameBanner.start.desc(), GameBanner.order)
                           .offset((page - 1) * PAGE_SIZE).limit(PAGE_SIZE))

    def item(i: int) -> dict:
        return items.get(i, {"id": i, "name": f"Item {i}", "icon": None, "rarity": 0})

    return {"total": total, "page": page, "page_size": PAGE_SIZE, "rows": [
        {"key": b.key, "name": b.name, "short_name": b.short_name, "start": b.start, "end": b.end,
         "featured_5": [item(i) for i in b.featured_5 or []], "featured_4": [item(i) for i in b.featured_4 or []],
         "pulls": pulls.get(b.key)} for b in rows]}


def cleanup_event_done(session: Session, now: datetime) -> int:
    snap = session.get(HoyolabSnapshot, "calendar")
    current = {e["id"] for e in (snap.data.get("events", []) if snap is not None else [])}
    stale = [r.event_id for r in session.scalars(select(EventDone).where(EventDone.done_at < now - KEEP_DONE))
             if r.event_id not in current]
    if stale:
        session.execute(delete(EventDone).where(EventDone.event_id.in_(stale)))
    return len(stale)
```

Check the expected values in the tests by hand before changing code: `os_euro` offset +1 → daily 04:00 local = 03:00 UTC; `os_usa` −5 → 04:00 local = 09:00 UTC; `os_asia` +8 → 16th 04:00 local = 15th 20:00 UTC.

- [ ] **Step 4: Run tests** — `-m pytest tests/test_events_view.py -q` → PASS; then the full suite.

- [ ] **Step 5: Commit**

```bash
git add backend/app/events backend/tests/test_events_view.py
git commit -m "feat(phase5): events, primogems, resets and banner history logic"
```

---

### Task 5: Events API, Dashboard data, startup cleanup, seed data, leak test

**Files:**
- Create: `backend/app/api/events.py`, `backend/tests/test_api_events.py`
- Modify: `backend/app/api/__init__.py`, `backend/app/api/dashboard.py`, `backend/app/main.py`, `backend/app/devseed.py`, `backend/tests/test_api_settings.py`, `backend/tests/test_devseed.py`

**Interfaces:**
- Consumes: Task 4 functions; `summarize` (`app.wishes.pity`), `banner_windows`, `region` (`app.api.planner`), `is_connected`.
- Produces:
  - `GET /api/events` → `{"connected", "fetched_at", "error", "banners": {"current","upcoming"}, "events": [...], "events_left": {"count","primogems"}, "resets": [...]}` (`error` = the last `calendar` part error or null)
  - `PUT /api/events/{event_id}/done` body `{"done": bool}` → `{"id", "done"}`
  - `GET /api/banners/history?pool=character&q=&page=1` → Task 4 `banner_history` dict
  - `GET /api/dashboard` adds `"live_banners": [current banners]`, `"events_left": {"count","primogems","next": [3 rows]}`, `"resets": [...]`, `"calendar_fetched_at"`
  - Dev seed: calendar snapshot (one current character banner matching the seeded "Tide of Furina", events 9001 (420 primos), 9002 (60 primos), 9003 (none), challenges abyss/theater ending in the future).

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_api_events.py`:

```python
from datetime import timedelta

from app.db.models import EventDone, HoyolabSnapshot, SyncRun
from app.timeutil import iso, utcnow
from helpers import make_client
from test_api_planner import sf_for


def seed_calendar(sf):
    now = utcnow()
    soon, later = iso(now + timedelta(hours=5)), iso(now + timedelta(days=9))
    data = {"banners": [], "challenges": [{"kind": "abyss", "name": "A", "start": None, "end": later}],
            "events": [{"id": 9001, "name": "Fest", "description": "", "start": None, "end": later,
                        "rewards": [{"id": 201, "name": "Primogem", "icon": "", "count": 420, "rarity": 5}]},
                       {"id": 9002, "name": "Quick", "description": "", "start": None, "end": soon,
                        "rewards": [{"id": 201, "name": "Primogem", "icon": "", "count": 60, "rarity": 5}]}]}
    with sf.begin() as s:
        s.add(HoyolabSnapshot(part="calendar", data=data, fetched_at=now))


def test_events_endpoint_and_done(paths):
    sf = sf_for(paths)
    seed_calendar(sf)
    with make_client(paths) as client:
        body = client.get("/api/events").json()
        assert [e["id"] for e in body["events"]] == [9002, 9001]
        assert body["events_left"] == {"count": 2, "primogems": 480}
        assert {r["key"] for r in body["resets"]} == {"daily", "weekly", "abyss", "theater"}
        assert client.put("/api/events/9002/done", json={"done": True}).json() == {"id": 9002, "done": True}
        body = client.get("/api/events").json()
        assert [e["id"] for e in body["events"]] == [9001, 9002] and body["events_left"]["primogems"] == 420
        dash = client.get("/api/dashboard").json()
        assert dash["events_left"]["count"] == 1 and [e["id"] for e in dash["events_left"]["next"]] == [9001]
        client.put("/api/events/9002/done", json={"done": False})
        assert client.get("/api/events").json()["events_left"]["count"] == 2


def test_events_without_snapshot_and_error(paths):
    sf = sf_for(paths)
    with sf.begin() as s:
        s.add(SyncRun(started_at=utcnow(), finished_at=utcnow(), trigger="manual",
                      parts={"calendar": {"ok": False, "error": "HoyolabError: down"}}))
    with make_client(paths) as client:
        body = client.get("/api/events").json()
        assert body["fetched_at"] is None and body["events"] == [] and body["error"] == "HoyolabError: down"
        assert client.get("/api/dashboard").json()["live_banners"] == []


def test_banner_history_endpoint(paths):
    sf_for(paths)
    with make_client(paths) as client:
        body = client.get("/api/banners/history?pool=character&q=&page=1").json()
        assert body == {"total": 0, "page": 1, "page_size": 50, "rows": []}
        assert client.get("/api/banners/history?pool=nope").status_code == 422


def test_done_validation(paths):
    sf_for(paths)
    with make_client(paths) as client:
        assert client.put("/api/events/abc/done", json={"done": True}).status_code == 422
        assert client.put("/api/events/1/done", json={}).status_code == 422
```

Extend `test_devseed.py`:

```python
def test_devseed_calendar(tmp_path):
    seed(tmp_path)
    with make_client(Paths(tmp_path)) as client:
        body = client.get("/api/events").json()
    assert [e["id"] for e in body["events"]][:2] and body["events_left"]["primogems"] == 480
    assert body["banners"]["current"][0]["name"] == "Tide of Furina"
    assert body["banners"]["current"][0]["pulls"] is not None
```

Extend the leak test in `test_api_settings.py`: add `"/api/events"`, `"/api/banners/history?pool=character"` to the list of GET paths.

- [ ] **Step 2: Run to verify they fail** — `-m pytest tests/test_api_events.py -q` → FAIL (404).

- [ ] **Step 3: Router** — `backend/app/api/events.py`:

```python
from typing import Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.planner import is_connected, region
from app.context import AppContext, get_ctx
from app.db.models import EventDone, GameBanner, HoyolabSnapshot, SyncRun
from app.events.view import banner_history, event_rows, events_left, live_banners, pulls_by_banner, resets
from app.servertime import offset_hours
from app.timeutil import iso, utcnow
from app.wishes.pity import banner_windows, summarize

router = APIRouter()


class DoneIn(BaseModel):
    done: bool


def last_error(session: Session, part: str) -> str | None:
    run = session.scalars(select(SyncRun).where(SyncRun.finished_at.is_not(None), SyncRun.trigger != "gaps")
                          .order_by(SyncRun.id.desc()).limit(1)).first()
    p = ((run.parts or {}) if run is not None else {}).get(part) or {}
    return None if p.get("ok", True) else p.get("error")


def events_payload(ctx: AppContext, s: Session) -> dict:
    now, reg = utcnow(), region(ctx)
    snap = s.get(HoyolabSnapshot, "calendar")
    calendar = snap.data if snap is not None else {"banners": [], "events": [], "challenges": []}
    offset = offset_hours(reg)
    pulls = pulls_by_banner(summarize(s, now, offset))
    windows = banner_windows(list(s.scalars(select(GameBanner))), offset)
    done = set(s.scalars(select(EventDone.event_id)))
    rows = event_rows(calendar, done, now)
    return {"connected": is_connected(ctx, s), "fetched_at": iso(snap.fetched_at) if snap else None,
            "error": last_error(s, "calendar"),
            "banners": live_banners(calendar, now, windows, pulls, offset),
            "events": rows, "events_left": events_left(rows),
            "resets": resets(snap.data if snap is not None else None, now, reg)}


@router.get("/events")
def get_events(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        return events_payload(ctx, s)


@router.put("/events/{event_id}/done")
def set_done(event_id: int, body: DoneIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory.begin() as s:
        row = s.get(EventDone, event_id)
        if body.done and row is None:
            s.add(EventDone(event_id=event_id, done_at=utcnow()))
        elif not body.done and row is not None:
            s.delete(row)
    return {"id": event_id, "done": body.done}


@router.get("/banners/history")
def get_banner_history(pool: Literal["character", "weapon", "chronicled"] = "character",
                       q: str = Query("", max_length=100), page: int = Query(1, ge=1),
                       ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        pulls = pulls_by_banner(summarize(s, utcnow(), offset_hours(region(ctx))))
        return banner_history(s, pool, q, page, pulls)
```

Register it in `app/api/__init__.py` (`events` in the import list and `events.router` in `ROUTERS`).

- [ ] **Step 4: Dashboard** — in `backend/app/api/dashboard.py` import `events_payload` from `app.api.events` and add to the returned dict (compute `ev = events_payload(ctx, s)` inside the session):

```python
            "live_banners": ev["banners"]["current"],
            "events_left": {**ev["events_left"], "next": [e for e in ev["events"] if not e["done"]][:3]},
            "resets": ev["resets"],
            "calendar_fetched_at": ev["fetched_at"],
```

- [ ] **Step 5: Startup cleanup** — in `backend/app/main.py`, right after `session_factory = make_session_factory(engine)`:

```python
    with session_factory.begin() as s:
        cleanup_event_done(s, utcnow())
```

(import `cleanup_event_done` from `app.events.view`).

- [ ] **Step 6: Seed** — at the end of `seed()` in `backend/app/devseed.py` add a calendar snapshot. Read how the seeded "Tide of Furina" banner's `start`/`end` are computed (server-local strings, Asia offset 8) and build the calendar banner's UTC `start`/`end` from the same values minus 8 hours, so the live banner matches the window. The calendar banner is named "Tide of Furina" (pool `character`, items Furina 5★ and Bennett 4★). Events: 9001 "Fishing Festival" ends in 9 days with 420 primogems; 9002 "Quick Trial" ends in 5 hours with 60; 9003 "Photo Event" ends in 3 days, no rewards. Challenges: abyss ends in 20 days, theater in 10 days. `fetched_at = now`. Use `HoyolabSnapshot` and `iso`.

- [ ] **Step 7: Run tests** — `-m pytest tests/test_api_events.py tests/test_devseed.py tests/test_api_settings.py -q` → PASS; then the full suite.

- [ ] **Step 8: Commit**

```bash
git add backend/app/api backend/app/main.py backend/app/devseed.py backend/tests/test_api_events.py backend/tests/test_devseed.py backend/tests/test_api_settings.py
git commit -m "feat(phase5): events and banner history API, dashboard event data, seed calendar"
```

---

### Task 6: Frontend — types, API client, helpers, Events page, nav

**Files:**
- Create: `frontend/src/lib/events.ts`, `frontend/src/lib/events.test.ts`, `frontend/src/lib/Countdown.svelte`, `frontend/src/routes/events/+page.svelte`
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/routes/+layout.svelte`

**Interfaces:**
- Produces (TS): types `BannerItem`, `LiveBanner`, `BannerPulls`, `EventRow`, `EventsLeft`, `ResetRow`, `EventsResponse`, `HistoryBanner`, `BannerHistoryPage`; `api.events()`, `api.setEventDone(id, done)`, `api.bannerHistory(pool, q, page)`; helpers `timeLeft(iso, now)`, `sortEvents(rows)`, `leftTotals(rows)`, `primosLine(left)`; component `Countdown` (props `at: string | null`, `now: number`). Test ids for e2e: `event-<id>`, `events-left`, `resets`, `live-banners`, `banner-history`.

- [ ] **Step 1: Write the failing tests** — `frontend/src/lib/events.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import type { EventRow } from './types';
import { leftTotals, primosLine, sortEvents, timeLeft } from './events';

const NOW = Date.parse('2026-11-21T12:00:00Z');

function row(id: number, end: string | null, done = false, primogems = 0): EventRow {
	return { id, name: `E${id}`, description: '', start: null, end, rewards: [], primogems, done, ending_soon: false };
}

describe('timeLeft', () => {
	it('formats days, hours, minutes', () => {
		expect(timeLeft('2026-11-23T15:30:00Z', NOW)).toBe('2d 3h');
		expect(timeLeft('2026-11-21T15:30:00Z', NOW)).toBe('3h 30m');
		expect(timeLeft('2026-11-21T12:05:00Z', NOW)).toBe('5m');
		expect(timeLeft('2026-11-21T11:00:00Z', NOW)).toBe('ended');
		expect(timeLeft(null, NOW)).toBe('—');
	});
});

describe('events', () => {
	it('sorts not-done by end, done last', () => {
		const rows = [row(1, '2026-11-30T00:00:00Z'), row(2, '2026-11-22T00:00:00Z', true), row(3, '2026-11-25T00:00:00Z'), row(4, null)];
		expect(sortEvents(rows).map((r) => r.id)).toEqual([3, 1, 4, 2]);
	});
	it('totals and line', () => {
		const t = leftTotals([row(1, null, false, 420), row(2, null, true, 60), row(3, null, false, 0)]);
		expect(t).toEqual({ count: 2, primogems: 420 });
		expect(primosLine(t)).toBe('2 left · 420 primos unclaimed');
		expect(primosLine({ count: 0, primogems: 0 })).toBe('All events done ✓');
	});
});
```

- [ ] **Step 2: Run to verify they fail** — `cd frontend; npm test` → FAIL (cannot resolve `./events`).

- [ ] **Step 3: Types** — append to `frontend/src/lib/types.ts` and extend `Dashboard`:

```ts
export interface BannerItem { id: number; name: string; icon: string; rarity: number; kind: 'character' | 'weapon' }
export interface BannerPulls { pulls: number; fives: string[]; fours: string[] }
export interface LiveBanner {
	id: number; pool: 'character' | 'weapon' | 'chronicled'; name: string; version: string;
	start: string | null; end: string | null; items: BannerItem[]; pulls: BannerPulls | null;
}
export interface Reward { id: number; name: string; icon: string; count: number; rarity: number }
export interface EventRow {
	id: number; name: string; description: string; start: string | null; end: string | null;
	rewards: Reward[]; primogems: number; done: boolean; ending_soon: boolean;
}
export interface EventsLeft { count: number; primogems: number }
export interface ResetRow { key: 'daily' | 'weekly' | 'abyss' | 'theater' | 'stygian'; label: string; at: string }
export interface EventsResponse {
	connected: boolean; fetched_at: string | null; error: string | null;
	banners: { current: LiveBanner[]; upcoming: LiveBanner[] };
	events: EventRow[]; events_left: EventsLeft; resets: ResetRow[];
}
export interface HistoryItem { id: number; name: string; icon: string | null; rarity: number }
export interface HistoryBanner {
	key: string; name: string; short_name: string; start: string; end: string;
	featured_5: HistoryItem[]; featured_4: HistoryItem[]; pulls: BannerPulls | null;
}
export interface BannerHistoryPage { total: number; page: number; page_size: number; rows: HistoryBanner[] }
```

and in `Dashboard` add: `live_banners: LiveBanner[]; events_left: EventsLeft & { next: EventRow[] }; resets: ResetRow[]; calendar_fetched_at: string | null;`.

- [ ] **Step 4: API** — add to `api` in `frontend/src/lib/api.ts` (import the new types):

```ts
	events: () => request<EventsResponse>('GET', '/events'),
	setEventDone: (id: number, done: boolean) => request<{ id: number; done: boolean }>('PUT', `/events/${id}/done`, { done }),
	bannerHistory: (pool: string, q: string, page: number) =>
		request<BannerHistoryPage>('GET', `/banners/history?pool=${encodeURIComponent(pool)}&q=${encodeURIComponent(q)}&page=${page}`),
```

- [ ] **Step 5: Helpers** — `frontend/src/lib/events.ts`:

```ts
import type { EventRow, EventsLeft } from './types';

export function timeLeft(iso: string | null, now: number): string {
	if (!iso) return '—';
	const ms = Date.parse(iso) - now;
	if (ms <= 0) return 'ended';
	const mins = Math.floor(ms / 60000);
	const d = Math.floor(mins / 1440);
	const h = Math.floor((mins % 1440) / 60);
	const m = mins % 60;
	if (d > 0) return `${d}d ${h}h`;
	if (h > 0) return `${h}h ${m}m`;
	return `${m}m`;
}

export function sortEvents(rows: EventRow[]): EventRow[] {
	const end = (r: EventRow) => (r.end ? Date.parse(r.end) : Number.MAX_SAFE_INTEGER);
	return [...rows].sort((a, b) => Number(a.done) - Number(b.done) || end(a) - end(b) || a.id - b.id);
}

export function leftTotals(rows: EventRow[]): EventsLeft {
	const left = rows.filter((r) => !r.done);
	return { count: left.length, primogems: left.reduce((n, r) => n + r.primogems, 0) };
}

export function primosLine(left: EventsLeft): string {
	return left.count === 0 ? 'All events done ✓' : `${left.count} left · ${left.primogems} primos unclaimed`;
}
```

`frontend/src/lib/Countdown.svelte`:

```svelte
<script lang="ts">
	import { timeLeft } from './events';
	let { at, now }: { at: string | null; now: number } = $props();
	const soon = $derived(!!at && Date.parse(at) - now < 24 * 3600 * 1000);
</script>

<span class="cd" class:soon title={at ?? ''}>{timeLeft(at, now)}</span>

<style>
	.cd { font-variant-numeric: tabular-nums; }
	.soon { color: var(--warn); }
</style>
```

- [ ] **Step 6: Events page** — `frontend/src/routes/events/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import Countdown from '$lib/Countdown.svelte';
	import { leftTotals, primosLine, sortEvents } from '$lib/events';
	import { imgSrc } from '$lib/img';
	import { sync } from '$lib/sync.svelte';
	import { timeAgo } from '$lib/time';
	import type { BannerHistoryPage, EventRow, EventsResponse } from '$lib/types';

	let data = $state<EventsResponse | null>(null);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let now = $state(Date.now());
	let open = $state<number | null>(null);
	let pool = $state<'character' | 'weapon' | 'chronicled'>('character');
	let q = $state('');
	let page = $state(1);
	let history = $state<BannerHistoryPage | null>(null);
	let timer: ReturnType<typeof setTimeout> | undefined;
	const left = $derived(data ? leftTotals(data.events) : { count: 0, primogems: 0 });

	$effect(() => {
		void sync.version;
		load();
	});

	$effect(() => {
		const p = pool, query = q, pg = page;
		clearTimeout(timer);
		timer = setTimeout(() => loadHistory(p, query, pg), 250);
		return () => clearTimeout(timer);
	});

	onMount(() => {
		const t = setInterval(() => (now = Date.now()), 30_000);
		return () => clearInterval(t);
	});

	async function load() {
		try {
			data = await api.events();
			error = null;
		} catch (e) {
			error = errorMessage(e);
		}
	}

	async function loadHistory(p: string, query: string, pg: number) {
		try {
			history = await api.bannerHistory(p, query, pg);
		} catch (e) {
			toast = `Could not load banner history: ${errorMessage(e)}`;
		}
	}

	async function toggle(ev: EventRow) {
		if (!data) return;
		const before = data.events;
		data = { ...data, events: sortEvents(before.map((r) => (r.id === ev.id ? { ...r, done: !r.done } : r))) };
		try {
			await api.setEventDone(ev.id, !ev.done);
		} catch (e) {
			data = { ...data, events: before };
			toast = `Could not save: ${errorMessage(e)}`;
		}
	}
</script>

<h1>Events</h1>
{#if toast}<div class="toast error">{toast} <button type="button" onclick={() => (toast = null)}>Dismiss</button></div>{/if}
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.fetched_at}
		<p class="muted">as of {timeAgo(data.fetched_at, now)}{#if data.error} · ⚠ last update failed: {data.error}{/if}</p>
	{:else}
		<p class="muted">{data.connected ? 'Sync to load the event calendar' : 'Connect HoYoLAB in Settings to load events'}</p>
	{/if}

	<section class="panel" data-testid="live-banners">
		<h2>Live banners</h2>
		<div class="banners">
			{#each data.banners.current as b (b.id)}
				<div class="banner">
					<div class="title">{b.name} <span class="muted">· {b.pool}</span></div>
					<div class="items">
						{#each b.items as it (it.id)}
							<img class="r{it.rarity}" class:big={it.rarity === 5} src={imgSrc(it.icon)} alt={it.name} title={it.name} />
						{/each}
					</div>
					<div>Ends in <Countdown at={b.end} {now} /></div>
					{#if b.pulls}<div class="muted">You pulled {b.pulls.pulls} here{#if b.pulls.fives.length} · got {b.pulls.fives.join(', ')}{/if}</div>{/if}
				</div>
			{:else}
				<p class="muted">No live banners in the calendar.</p>
			{/each}
		</div>
		{#if data.banners.upcoming.length}
			<h3>Coming up</h3>
			<ul>{#each data.banners.upcoming as b (b.id)}<li>{b.name} · starts in <Countdown at={b.start} {now} /></li>{/each}</ul>
		{/if}
	</section>

	<section class="panel" data-testid="events-left">
		<h2>Events <span class="muted">· {primosLine(left)}</span></h2>
		<ul class="events">
			{#each data.events as ev (ev.id)}
				<li class:done={ev.done} data-testid="event-{ev.id}">
					<label><input type="checkbox" checked={ev.done} onchange={() => toggle(ev)} aria-label="Done: {ev.name}" /></label>
					<button type="button" class="name" onclick={() => (open = open === ev.id ? null : ev.id)}>{ev.name}</button>
					<span class="rewards">
						{#each ev.rewards as r (r.id)}<img src={imgSrc(r.icon)} alt={r.name} title="{r.name} ×{r.count}" />{/each}
						{#if ev.primogems}<strong>{ev.primogems} primos</strong>{/if}
					</span>
					<Countdown at={ev.end} {now} />
					{#if open === ev.id && ev.description}<p class="desc">{ev.description}</p>{/if}
				</li>
			{:else}
				<li class="muted">No current events.</li>
			{/each}
		</ul>
	</section>

	<section class="panel" data-testid="resets">
		<h2>Resets</h2>
		<div class="resets">{#each data.resets as r (r.key)}<span>{r.label}: <Countdown at={r.at} {now} /></span>{/each}</div>
	</section>
{/if}

<section class="panel" data-testid="banner-history">
	<h2>Banner history</h2>
	<div class="filters">
		{#each ['character', 'weapon', 'chronicled'] as p (p)}
			<button type="button" class="chip" class:on={pool === p} onclick={() => { pool = p as typeof pool; page = 1; }}>{p}</button>
		{/each}
		<input placeholder="Search banner or item" bind:value={q} oninput={() => (page = 1)} aria-label="Search banners" />
	</div>
	{#if history}
		<table>
			<tbody>
				{#each history.rows as b (b.key)}
					<tr>
						<td>{b.name}</td>
						<td class="muted">{b.start.slice(0, 10)} – {b.end.slice(0, 10)}</td>
						<td>{#each b.featured_5 as it (it.id)}<img class="r5" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/each}
							{#each b.featured_4 as it (it.id)}<img class="r4 small" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/each}</td>
						<td>{#if b.pulls}{b.pulls.pulls} pulls{#if b.pulls.fives.length} · {b.pulls.fives.join(', ')}{/if}{/if}</td>
					</tr>
				{:else}
					<tr><td class="muted">No banners match.</td></tr>
				{/each}
			</tbody>
		</table>
		{#if history.total > history.page_size}
			<div class="pager">
				<button type="button" disabled={page <= 1} onclick={() => (page -= 1)}>Previous</button>
				<span>Page {history.page} of {Math.ceil(history.total / history.page_size)}</span>
				<button type="button" disabled={page * history.page_size >= history.total} onclick={() => (page += 1)}>Next</button>
			</div>
		{/if}
	{/if}
</section>

<style>
	section { margin-bottom: 12px; }
	.banners { display: flex; flex-wrap: wrap; gap: 12px; }
	.banner { background: var(--panel-2); border-radius: 10px; padding: 10px; min-width: 220px; }
	.items img { width: 40px; height: 40px; border-radius: 6px; }
	.items img.big { width: 64px; height: 64px; }
	.r5 { background: var(--r5); } .r4 { background: var(--r4); }
	.events { list-style: none; padding: 0; margin: 0; }
	.events li { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--line); }
	.events li.done { opacity: 0.5; }
	.name { background: none; border: none; color: var(--text); cursor: pointer; text-align: left; flex: 1; }
	.rewards { display: flex; gap: 4px; align-items: center; }
	.rewards img { width: 24px; height: 24px; }
	.desc { flex-basis: 100%; margin: 4px 0 0 30px; color: var(--muted); }
	.resets { display: flex; flex-wrap: wrap; gap: 16px; }
	td img { width: 32px; height: 32px; border-radius: 6px; }
	td img.small { width: 24px; height: 24px; }
	.filters { display: flex; flex-wrap: wrap; gap: 6px; margin-bottom: 8px; }
	.pager { display: flex; gap: 10px; align-items: center; margin-top: 8px; }
	.toast { margin-bottom: 8px; }
</style>
```

- [ ] **Step 7: Nav** — in `frontend/src/routes/+layout.svelte` change the Events entry to `{ label: 'Events', href: '/events' },`.

- [ ] **Step 8: Check** — `npm run check` (0 errors) and `npm test` (PASS). If an existing test fixture builds a `Dashboard` literal, add the new fields.

- [ ] **Step 9: Commit**

```bash
git add frontend/src
git commit -m "feat(phase5): Events page with banners, Done ticks, resets and banner history"
```

---

### Task 7: Dashboard Events cards and the Events end-to-end test (M1 end)

**Files:**
- Modify: `frontend/src/routes/+page.svelte`
- Create: `frontend/e2e/events.spec.ts`

**Interfaces:**
- Consumes: `Dashboard.live_banners`, `events_left`, `resets`, `calendar_fetched_at`; `Countdown`, `primosLine`, `imgSrc`, `timeAgo`. Test ids: `dash-banners`, `dash-events`, `dash-resets`.

- [ ] **Step 1: Write the e2e test** — `frontend/e2e/events.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('ticking an event Done dims it and lowers the Dashboard count', async ({ page }) => {
	await page.goto('/');
	await expect(page.getByTestId('dash-events')).toContainText('3 events left · 480 primos');
	await page.goto('/events');
	const row = page.getByTestId('event-9002');
	await row.getByRole('checkbox').check();
	await expect(row).toHaveClass(/done/);
	await expect(page.getByTestId('events-left')).toContainText('2 left · 420 primos unclaimed');
	await page.goto('/');
	await expect(page.getByTestId('dash-events')).toContainText('2 events left · 420 primos');
	await expect(page.getByTestId('dash-banners')).toContainText('Tide of Furina');
	await expect(page.getByTestId('dash-resets')).toContainText('Spiral Abyss');
});

test('banner history search narrows the list', async ({ page }) => {
	await page.goto('/events');
	await page.getByLabel('Search banners').fill('Furina');
	await expect(page.getByTestId('banner-history').locator('tbody tr').first()).toContainText('Tide of Furina');
});
```

- [ ] **Step 2: Dashboard cards** — in `frontend/src/routes/+page.svelte` import `Countdown` and `primosLine`, and add after the existing Build teams section:

```svelte
	<section class="panel" data-testid="dash-banners">
		<h2><a href="/events">Live banners</a></h2>
		{#if data.live_banners.length === 0}
			<p class="muted">{data.calendar_fetched_at ? 'No live banners.' : 'Sync to load the event calendar'}</p>
		{:else}
			<div class="tiles-row">
				{#each data.live_banners as b (b.id)}
					<span class="dash-banner">
						{#each b.items.filter((i) => i.rarity === 5) as it (it.id)}<img src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/each}
						<span>{b.name}</span> <Countdown at={b.end} {now} />
					</span>
				{/each}
			</div>
		{/if}
	</section>

	<section class="panel" data-testid="dash-events">
		<h2><a href="/events">Events</a></h2>
		{#if !data.calendar_fetched_at}
			<p class="muted">Sync to load the event calendar</p>
		{:else if data.events_left.count === 0}
			<p>All events done ✓</p>
		{:else}
			<p>{data.events_left.count} events left · {data.events_left.primogems} primos</p>
			<ul>{#each data.events_left.next as e (e.id)}<li>{e.name} · <Countdown at={e.end} {now} /></li>{/each}</ul>
		{/if}
	</section>

	<section class="panel" data-testid="dash-resets">
		<h2>Resets</h2>
		<div class="resets">{#each data.resets as r (r.key)}<span>{r.label}: <Countdown at={r.at} {now} /></span>{/each}</div>
	</section>
```

with styles `.dash-banner { display: inline-flex; gap: 6px; align-items: center; margin-right: 12px; } .dash-banner img { width: 36px; height: 36px; border-radius: 50%; } .resets { display: flex; flex-wrap: wrap; gap: 14px; }` (reuse existing classes if present). The Dashboard already has a `now` state updated by a timer; if not, add one like the Events page.

- [ ] **Step 3: Run everything** — `npm run check`, `npm test`, `npm run build`, then `$env:PYTHON='<repo>\.venv\Scripts\python.exe'; npm run e2e` → all specs PASS (including the existing four and the new events spec). Backend full suite once.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/routes/+page.svelte frontend/e2e/events.spec.ts
git commit -m "feat(phase5): dashboard banners, events and reset cards; events e2e"
```

**Milestone 1 done:** push the branch after the review (check the diff for secrets first).

---

## Milestone 2 — Profile

### Task 8: Profile logic, API, Dashboard summary, seed

**Files:**
- Create: `backend/app/profile/__init__.py` (docstring `"""Profile page: pure functions over the profile snapshot and challenge history."""`), `backend/app/profile/view.py`, `backend/app/api/profile.py`, `backend/tests/test_profile_view.py`, `backend/tests/test_api_profile.py`
- Modify: `backend/app/api/__init__.py`, `backend/app/api/dashboard.py`, `backend/app/devseed.py`, `backend/tests/test_devseed.py`, `backend/tests/test_api_settings.py`

**Interfaces:**
- Consumes: models `HoyolabSnapshot`, `ChallengeRun`, `GameCharacter`, `OwnedCharacter`; `last_error` (`app.api.events`); `parse_iso` (`app.events.view`).
- Produces:
  - `profile_view(data: dict | None) -> dict | None` — `{"ar","days_active","tiles":[{"label","value"}],"chests":[{"label","value"}],"oculi":[{"label","value"}],"regions":[...]}`
  - `challenge_views(session, now) -> dict` — `{"abyss": {"current": run | None, "past": [run]}, "theater": ..., "stygian": ...}`; run = `{"season","start","end","summary","teams":[[{"id","name","icon"}]]}`; "current" = the run whose `end` is in the future
  - `profile_summary(session, now) -> dict` — `{"ar": int | None, "abyss_stars": int | None, "theater_act": int | None}`
  - `GET /api/profile` → `{"connected","fetched_at","error","profile","challenges"}`; `GET /api/dashboard` adds `profile_summary`.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_profile_view.py`:

```python
from datetime import datetime

from app.db.models import ChallengeRun
from app.profile.view import challenge_views, profile_summary, profile_view
from helpers import seed_game

NOW = datetime(2026, 11, 21, 12, 0, 0)
DATA = {"stats": {"ar": 60, "days_active": 1200, "achievements": 900, "characters": 95,
                  "chests": {"common": 3000, "exquisite": 2000, "precious": 600, "luxurious": 200, "remarkable": 100},
                  "oculi": {"anemoculi": 66, "geoculi": 131, "electroculi": 181, "dendroculi": 271,
                            "hydroculi": 271, "pyroculi": 200, "cryoculi": 0, "lunoculi": 0},
                  "waypoints": 400, "domains": 70},
        "regions": [{"id": 1, "name": "Mondstadt", "explored": 100.0, "reputation": 8,
                     "offerings": [{"name": "Frostbearing Tree", "level": 12}]}]}


def add_run(s, kind, season, end, summary, teams=()):
    s.add(ChallengeRun(kind=kind, season=season, start="2026-10-16T04:00:00Z", end=end, summary=summary,
                       teams=[list(t) for t in teams], seen_at=NOW, updated_at=NOW))


def test_profile_view():
    v = profile_view(DATA)
    assert (v["ar"], v["days_active"]) == (60, 1200)
    assert {"label": "Achievements", "value": 900} in v["tiles"]
    assert v["chests"][0] == {"label": "Common", "value": 3000}
    assert {"label": "Cryoculi", "value": 0} not in v["oculi"]          # zero oculi types hidden
    assert v["regions"][0]["name"] == "Mondstadt"
    assert profile_view(None) is None


def test_challenge_views_current_and_past(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        add_run(s, "abyss", "101", "2026-12-16T04:00:00Z", {"stars": 36}, [(10000089, 10000032)])
        add_run(s, "abyss", "100", "2026-11-16T04:00:00Z", {"stars": 30})
        add_run(s, "abyss", "99", "2026-10-16T04:00:00Z", {"stars": 27})
        add_run(s, "theater", "77", "2026-11-01T04:00:00Z", {"act": 8})
    with session_factory() as s:
        v = challenge_views(s, NOW)
        summary = profile_summary(s, NOW)
    assert v["abyss"]["current"]["season"] == "101"
    assert v["abyss"]["current"]["teams"][0][0]["name"] == "Furina"
    assert [r["season"] for r in v["abyss"]["past"]] == ["100", "99"]
    assert v["theater"]["current"] is None and v["theater"]["past"][0]["season"] == "77"
    assert v["stygian"] == {"current": None, "past": []}
    assert summary == {"ar": None, "abyss_stars": 36, "theater_act": None}
```

`backend/tests/test_api_profile.py`:

```python
from app.db.models import HoyolabSnapshot
from app.timeutil import utcnow
from helpers import make_client
from test_api_planner import sf_for
from test_profile_view import DATA


def test_profile_endpoint(paths):
    sf = sf_for(paths)
    with make_client(paths) as client:
        empty = client.get("/api/profile").json()
        assert empty["profile"] is None and empty["fetched_at"] is None
    with sf.begin() as s:
        s.add(HoyolabSnapshot(part="profile", data=DATA, fetched_at=utcnow()))
    with make_client(paths) as client:
        body = client.get("/api/profile").json()
        dash = client.get("/api/dashboard").json()
    assert body["profile"]["ar"] == 60 and set(body["challenges"]) == {"abyss", "theater", "stygian"}
    assert dash["profile_summary"]["ar"] == 60
```

Extend `test_devseed.py` with `test_devseed_profile` asserting `/api/profile` has `ar == 58`, two abyss past runs, and a current abyss run. Add `"/api/profile"` to the leak test's GET list.

- [ ] **Step 2: Run to verify they fail** — `-m pytest tests/test_profile_view.py tests/test_api_profile.py -q` → FAIL.

- [ ] **Step 3: Implement** — `backend/app/profile/view.py`:

```python
"""Profile page: pure functions over the profile snapshot and challenge history."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChallengeRun, GameCharacter, HoyolabSnapshot, OwnedCharacter
from app.events.view import parse_iso

KINDS = ("abyss", "theater", "stygian")
TILES = (("achievements", "Achievements"), ("characters", "Characters"), ("waypoints", "Waypoints"),
         ("domains", "Domains"))


def profile_view(data: dict | None) -> dict | None:
    if data is None:
        return None
    s = data["stats"]
    return {
        "ar": s["ar"], "days_active": s["days_active"],
        "tiles": [{"label": label, "value": s[key]} for key, label in TILES],
        "chests": [{"label": k.capitalize(), "value": v} for k, v in s["chests"].items()],
        "oculi": [{"label": k.capitalize(), "value": v} for k, v in s["oculi"].items() if v],
        "regions": data["regions"],
    }


def _names(session: Session) -> dict[int, dict]:
    out = {c.id: {"id": c.id, "name": c.name, "icon": c.icon} for c in session.scalars(select(GameCharacter))}
    for o in session.scalars(select(OwnedCharacter)):
        out.setdefault(o.character_id, {"id": o.character_id, "name": o.name, "icon": o.icon})
    return out


def _run(r: ChallengeRun, names: dict[int, dict]) -> dict:
    team = lambda ids: [names.get(i, {"id": i, "name": f"Character {i}", "icon": None}) for i in ids]  # noqa: E731
    return {"season": r.season, "start": r.start, "end": r.end, "summary": r.summary,
            "teams": [team(t) for t in r.teams or []]}


def challenge_views(session: Session, now: datetime) -> dict:
    names = _names(session)
    out = {}
    for kind in KINDS:
        rows = sorted(session.scalars(select(ChallengeRun).where(ChallengeRun.kind == kind)),
                      key=lambda r: (r.end or "", r.start or ""), reverse=True)
        current = next((r for r in rows if (parse_iso(r.end) or now) > now), None)
        out[kind] = {"current": _run(current, names) if current is not None else None,
                     "past": [_run(r, names) for r in rows if r is not current]}
    return out


def profile_summary(session: Session, now: datetime) -> dict:
    snap = session.get(HoyolabSnapshot, "profile")
    views = challenge_views(session, now)
    abyss, theater = views["abyss"]["current"], views["theater"]["current"]
    return {"ar": snap.data["stats"]["ar"] if snap is not None else None,
            "abyss_stars": abyss["summary"].get("stars") if abyss else None,
            "theater_act": theater["summary"].get("act") if theater else None}
```

`backend/app/api/profile.py`:

```python
from fastapi import APIRouter, Depends

from app.api.events import last_error
from app.api.planner import is_connected
from app.context import AppContext, get_ctx
from app.db.models import HoyolabSnapshot
from app.profile.view import challenge_views, profile_view
from app.timeutil import iso, utcnow

router = APIRouter()


@router.get("/profile")
def get_profile(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        snap = s.get(HoyolabSnapshot, "profile")
        return {"connected": is_connected(ctx, s), "fetched_at": iso(snap.fetched_at) if snap else None,
                "error": last_error(s, "profile") or last_error(s, "challenges"),
                "profile": profile_view(snap.data if snap else None),
                "challenges": challenge_views(s, utcnow())}
```

Register the router; in `dashboard.py` add `"profile_summary": profile_summary(s, now),`.

- [ ] **Step 4: Seed** — in `devseed.py` add a profile snapshot (AR 58, days 900, made-up counts, regions Mondstadt 100.0/rep 8, Liyue 96.4/rep 7, Inazuma 88.1/rep 6) and `ChallengeRun` rows: abyss season "103" ending in 20 days (36 stars, teams [[furina, bennett, xingqiu, kazuha]]), abyss "102" and "101" ended (30, 27 stars); theater "77" ending in 10 days (act 10, difficulty 3). Use ids from the `CHARACTERS` slug lookup.

- [ ] **Step 5: Run tests** — `-m pytest tests/test_profile_view.py tests/test_api_profile.py tests/test_devseed.py tests/test_api_settings.py -q` → PASS; full suite.

- [ ] **Step 6: Commit**

```bash
git add backend/app/profile backend/app/api backend/app/devseed.py backend/tests
git commit -m "feat(phase5): profile and challenge history API, dashboard profile summary, seed data"
```

---

### Task 9: Profile page, Dashboard card, nav, e2e (M2 end)

**Files:**
- Create: `frontend/src/routes/profile/+page.svelte`, `frontend/e2e/profile.spec.ts`
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/routes/+page.svelte`, `frontend/src/routes/+layout.svelte`

**Interfaces:**
- Produces: types `ProfileResponse`, `ProfileView`, `ChallengeRunView`, `ChallengeViews`; `api.profile()`; `Dashboard.profile_summary: { ar: number | null; abyss_stars: number | null; theater_act: number | null }`. Test ids: `abyss-current`, `abyss-past`, `theater-current`, `dash-profile`.

- [ ] **Step 1: Write the e2e test** — `frontend/e2e/profile.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('profile shows stats, current Abyss and past runs', async ({ page }) => {
	await page.goto('/profile');
	await expect(page.getByText('AR 58')).toBeVisible();
	await expect(page.getByTestId('abyss-current')).toContainText('36');
	await expect(page.getByTestId('abyss-past').locator('tbody tr')).toHaveCount(2);
	await page.goto('/');
	await expect(page.getByTestId('dash-profile')).toContainText('AR 58');
});
```

- [ ] **Step 2: Types and API** — add to `types.ts`:

```ts
export interface StatTile { label: string; value: number }
export interface RegionView { id: number; name: string; explored: number; reputation: number | null; offerings: { name: string; level: number }[] }
export interface ProfileView { ar: number; days_active: number; tiles: StatTile[]; chests: StatTile[]; oculi: StatTile[]; regions: RegionView[] }
export interface TeamChar { id: number; name: string; icon: string | null }
export interface ChallengeRunView { season: string; start: string | null; end: string | null; summary: Record<string, number | string>; teams: TeamChar[][] }
export interface ChallengeViews { abyss: { current: ChallengeRunView | null; past: ChallengeRunView[] }; theater: { current: ChallengeRunView | null; past: ChallengeRunView[] }; stygian: { current: ChallengeRunView | null; past: ChallengeRunView[] } }
export interface ProfileResponse { connected: boolean; fetched_at: string | null; error: string | null; profile: ProfileView | null; challenges: ChallengeViews }
```

`Dashboard` gains `profile_summary: { ar: number | null; abyss_stars: number | null; theater_act: number | null };`. `api.profile: () => request<ProfileResponse>('GET', '/profile')`.

- [ ] **Step 3: Profile page** — `frontend/src/routes/profile/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import Countdown from '$lib/Countdown.svelte';
	import { imgSrc } from '$lib/img';
	import { sync } from '$lib/sync.svelte';
	import { timeAgo } from '$lib/time';
	import type { ChallengeRunView, ProfileResponse } from '$lib/types';

	let data = $state<ProfileResponse | null>(null);
	let error = $state<string | null>(null);
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

	function result(kind: string, r: ChallengeRunView): string {
		const s = r.summary;
		if (kind === 'abyss') return `${s.stars ?? '—'}★ · floor ${s.max_floor ?? '—'} · ${s.wins ?? 0}/${s.battles ?? 0} wins`;
		if (kind === 'theater') return `Act ${s.act ?? '—'} · difficulty ${s.difficulty ?? '—'} · ${s.medals ?? 0} medals`;
		return `Difficulty ${s.difficulty ?? '—'}${s.time_used ? ` · ${s.time_used}s` : ''}`;
	}
</script>

<h1>Profile</h1>
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.profile}
		<p class="muted">as of {data.fetched_at ? timeAgo(data.fetched_at, now) : '—'}{#if data.error} · ⚠ last update failed: {data.error}{/if}</p>
		<section class="panel">
			<h2>AR {data.profile.ar} <span class="muted">· {data.profile.days_active} days active</span></h2>
			<div class="tiles">
				{#each [...data.profile.tiles, ...data.profile.chests, ...data.profile.oculi] as t (t.label)}
					<div class="tile"><div class="big">{t.value}</div><div class="muted">{t.label}</div></div>
				{/each}
			</div>
		</section>
		<section class="panel">
			<h2>Exploration</h2>
			<div class="regions">
				{#each data.profile.regions as r (r.id)}
					<div class="region">
						<div class="title">{r.name}</div>
						<div class="big">{r.explored}%</div>
						{#if r.reputation !== null}<div class="muted">Reputation {r.reputation}</div>{/if}
						{#each r.offerings as o (o.name)}<div class="muted">{o.name} {o.level}</div>{/each}
					</div>
				{/each}
			</div>
		</section>
	{:else}
		<p class="muted">{data.connected ? 'Sync to load your profile' : 'Connect HoYoLAB in Settings to load your profile'}</p>
	{/if}

	{#each KINDS as k (k.key)}
		{@const view = data.challenges[k.key]}
		<section class="panel">
			<h2>{k.title}</h2>
			<div data-testid="{k.key}-current">
				{#if view.current}
					<p>{result(k.key, view.current)} · ends in <Countdown at={view.current.end} {now} /></p>
					{#each view.current.teams as team, i (i)}
						<div class="team">{#each team as c (c.id)}<img src={imgSrc(c.icon)} alt={c.name} title={c.name} />{/each}</div>
					{/each}
				{:else}
					<p class="muted">Not attempted this cycle</p>
				{/if}
			</div>
			{#if view.past.length}
				<h3>Past runs</h3>
				<table data-testid="{k.key}-past">
					<tbody>
						{#each view.past as r (r.season)}
							<tr><td>{r.start?.slice(0, 10) ?? r.season}</td><td>{result(k.key, r)}</td></tr>
						{/each}
					</tbody>
				</table>
			{/if}
		</section>
	{/each}
{/if}

<style>
	section { margin-bottom: 12px; }
	.tiles, .regions { display: flex; flex-wrap: wrap; gap: 10px; }
	.tile, .region { background: var(--panel-2); border-radius: 10px; padding: 8px 12px; min-width: 110px; }
	.big { font-size: 20px; font-weight: 600; }
	.team img { width: 36px; height: 36px; border-radius: 50%; }
	.team { display: flex; gap: 4px; margin: 4px 0; }
</style>
```

- [ ] **Step 4: Dashboard card and nav** — on the Dashboard add after the Resets card:

```svelte
	<section class="panel" data-testid="dash-profile">
		<h2><a href="/profile">Profile</a></h2>
		{#if data.profile_summary.ar === null}
			<p class="muted">Sync to load your profile</p>
		{:else}
			<p>AR {data.profile_summary.ar} · Abyss {data.profile_summary.abyss_stars ?? '—'}★ · Theater act {data.profile_summary.theater_act ?? '—'}</p>
		{/if}
	</section>
```

Nav: `{ label: 'Profile', href: '/profile' },`.

- [ ] **Step 5: Run everything** — check, test, build, e2e (all specs) PASS; backend suite once.

- [ ] **Step 6: Commit**

```bash
git add frontend/src frontend/e2e/profile.spec.ts
git commit -m "feat(phase5): Profile page, dashboard profile card, profile e2e"
```

**Milestone 2 done:** push the branch after the review.

---

## Milestone 3 — Map

### Task 10: Embed check, map API, default-map setting

**Files:**
- Create: `backend/app/mapcheck.py`, `backend/app/api/maps.py`, `backend/tests/test_mapcheck.py`, `backend/tests/test_api_maps.py`
- Modify: `backend/app/api/__init__.py`, `backend/app/api/settings.py`, `backend/app/devseed.py`, `backend/tests/test_api_settings.py`

**Interfaces:**
- Consumes: `GameMeta` model; `ctx.http` (httpx.AsyncClient), `ctx.offline`; `get_setting`, `set_setting`.
- Produces:
  - `MAPS: dict[str, tuple[str, str]]` = `{"hoyolab": ("HoYoLAB Interactive Map", <url>), "appsample": ("AppSample", <url>)}`
  - `frame_allowed(headers: Mapping[str, str], origin: str) -> bool`
  - `async check(http, url) -> bool | None`
  - `async map_status(session_factory, http, now, offline: bool, origin: str) -> list[dict]` — `[{"key","name","url","allowed"}]`, cached 24 h in `game_meta`
  - `GET /api/map` → `{"maps": [...], "default_map": "hoyolab" | "appsample"}`; `PUT /api/settings` accepts `default_map`; `GET /api/settings` returns it.

- [ ] **Step 1: Write the failing tests** — `backend/tests/test_mapcheck.py`:

```python
from datetime import datetime, timedelta

import httpx

from app.db.models import GameMeta
from app.mapcheck import MAPS, check, frame_allowed, map_status

ORIGIN = "http://127.0.0.1:8765"
NOW = datetime(2026, 11, 21, 12, 0, 0)


def test_frame_allowed_headers():
    assert frame_allowed({}, ORIGIN) is True
    assert frame_allowed({"X-Frame-Options": "DENY"}, ORIGIN) is False
    assert frame_allowed({"x-frame-options": "sameorigin"}, ORIGIN) is False
    assert frame_allowed({"Content-Security-Policy": "default-src 'self'; frame-ancestors 'none'"}, ORIGIN) is False
    assert frame_allowed({"Content-Security-Policy": "frame-ancestors 'self' https://a.com"}, ORIGIN) is False
    assert frame_allowed({"Content-Security-Policy": "frame-ancestors *"}, ORIGIN) is True
    assert frame_allowed({"Content-Security-Policy": f"frame-ancestors {ORIGIN}"}, ORIGIN) is True
    assert frame_allowed({"Content-Security-Policy": "default-src 'self'"}, ORIGIN) is True


async def test_check_and_failure():
    def handler(request):
        if "hoyolab" in str(request.url):
            return httpx.Response(200, headers={"X-Frame-Options": "SAMEORIGIN"})
        return httpx.Response(200)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        assert await check(http, MAPS["hoyolab"][1]) is False
        assert await check(http, MAPS["appsample"][1]) is True

    def boom(request):
        raise httpx.ConnectError("down")
    async with httpx.AsyncClient(transport=httpx.MockTransport(boom)) as http:
        assert await check(http, MAPS["appsample"][1]) is None


async def test_map_status_offline_and_failure(session_factory):
    calls = []

    def handler(request):
        calls.append(str(request.url))
        raise httpx.ConnectError("down")
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        offline = await map_status(session_factory, http, NOW, True, ORIGIN)
        assert [m["allowed"] for m in offline] == [None, None] and calls == []
        first = await map_status(session_factory, http, NOW, False, ORIGIN)
        assert [m["allowed"] for m in first] == [None, None] and len(calls) == 2
        await map_status(session_factory, http, NOW + timedelta(hours=1), False, ORIGIN)
        assert len(calls) == 2                       # cached for 24 h, even after a failure
        await map_status(session_factory, http, NOW + timedelta(hours=25), False, ORIGIN)
        assert len(calls) == 4


async def test_cached_value_used_offline(session_factory):
    with session_factory.begin() as s:
        s.add(GameMeta(key="map_embed_hoyolab", value={"allowed": False, "checked_at": "2026-11-21T11:00:00Z"}))
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200))) as http:
        got = {m["key"]: m["allowed"] for m in await map_status(session_factory, http, NOW, True, ORIGIN)}
    assert got == {"hoyolab": False, "appsample": None}
```

`backend/tests/test_api_maps.py`:

```python
from helpers import make_client


def test_map_endpoint_and_default_setting(paths):
    with make_client(paths) as client:
        body = client.get("/api/map").json()
        assert [m["key"] for m in body["maps"]] == ["hoyolab", "appsample"] and body["default_map"] == "hoyolab"
        assert client.put("/api/settings", json={"default_map": "appsample"}).json()["default_map"] == "appsample"
        assert client.get("/api/map").json()["default_map"] == "appsample"
        assert client.put("/api/settings", json={"default_map": "google"}).status_code == 422
```

(`make_client` runs with `offline=True`, so no network is touched.) Add `"/api/map"` to the leak test's GET list.

- [ ] **Step 2: Run to verify they fail** — `-m pytest tests/test_mapcheck.py tests/test_api_maps.py -q` → FAIL.

- [ ] **Step 3: Implement** — `backend/app/mapcheck.py`:

```python
"""Does each map site allow being shown in an iframe? One unauthenticated request per site per day."""
from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import sessionmaker

from app.db.models import GameMeta
from app.timeutil import iso

MAPS: dict[str, tuple[str, str]] = {
    "hoyolab": ("HoYoLAB Interactive Map", "https://act.hoyolab.com/ys/app/interactive-map/index.html"),
    "appsample": ("AppSample", "https://genshin-impact-map.appsample.com/"),
}
CACHE = timedelta(hours=24)
TIMEOUT = 8.0


def frame_allowed(headers: Mapping[str, str], origin: str) -> bool:
    lower = {k.lower(): v for k, v in headers.items()}
    xfo = lower.get("x-frame-options", "").strip().lower()
    if xfo in ("deny", "sameorigin"):
        return False
    for directive in lower.get("content-security-policy", "").split(";"):
        parts = directive.split()
        if parts and parts[0].lower() == "frame-ancestors":
            sources = [p.strip() for p in parts[1:]]
            return "*" in sources or origin in sources
    return True


async def check(http: httpx.AsyncClient, url: str, origin: str = "http://127.0.0.1") -> bool | None:
    try:
        response = await http.get(url, timeout=TIMEOUT, follow_redirects=True)
    except httpx.HTTPError:
        return None
    return frame_allowed(response.headers, origin)


async def map_status(session_factory: sessionmaker, http: httpx.AsyncClient, now: datetime, offline: bool,
                     origin: str) -> list[dict]:
    out = []
    for key, (name, url) in MAPS.items():
        meta_key = f"map_embed_{key}"
        with session_factory() as s:
            row = s.get(GameMeta, meta_key)
            cached = row.value if row is not None else None
        fresh = cached is not None and now - datetime.fromisoformat(cached["checked_at"].rstrip("Z")) < CACHE
        if fresh or offline:
            allowed = cached["allowed"] if cached is not None else None
        else:
            allowed = await check(http, url, origin)
            with session_factory.begin() as s:
                s.merge(GameMeta(key=meta_key, value={"allowed": allowed, "checked_at": iso(now)}))
        out.append({"key": key, "name": name, "url": url, "allowed": allowed})
    return out
```

`backend/app/api/maps.py`:

```python
from fastapi import APIRouter, Depends

from app.context import AppContext, get_ctx
from app.mapcheck import map_status
from app.settings.store import get_setting
from app.timeutil import utcnow

router = APIRouter()


@router.get("/map")
async def get_maps(ctx: AppContext = Depends(get_ctx)) -> dict:
    maps = await map_status(ctx.session_factory, ctx.http, utcnow(), ctx.offline, "http://127.0.0.1")
    with ctx.session_factory() as s:
        return {"maps": maps, "default_map": get_setting(s, "default_map")}
```

Register it. In `api/settings.py`: `SettingsIn` gains `default_map: Literal["hoyolab", "appsample"] | None = None`; `put_settings` sets it when given; `settings_payload` returns `"default_map": get_setting(s, "default_map")`.

- [ ] **Step 4: Seed** — in `devseed.py` add `GameMeta(key="map_embed_hoyolab", value={"allowed": False, "checked_at": iso(now)})` and `GameMeta(key="map_embed_appsample", value={"allowed": True, "checked_at": iso(now)})`.

- [ ] **Step 5: Run tests** — `-m pytest tests/test_mapcheck.py tests/test_api_maps.py tests/test_api_settings.py tests/test_devseed.py -q` → PASS; full suite.

- [ ] **Step 6: Commit**

```bash
git add backend/app/mapcheck.py backend/app/api backend/app/devseed.py backend/tests
git commit -m "feat(phase5): map embed check, map API and default map setting"
```

---

### Task 11: Map page, Settings choice, nav, e2e, README, spec refinements, final checks (M3 end)

**Files:**
- Create: `frontend/src/lib/maps.ts`, `frontend/src/lib/maps.test.ts`, `frontend/src/routes/map/+page.svelte`, `frontend/e2e/map.spec.ts`
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/routes/settings/+page.svelte`, `frontend/src/routes/+layout.svelte`, `README.md`, `docs/superpowers/specs/2026-11-21-phase5-events-profile-map-design.md`

**Interfaces:**
- Produces: types `MapKey = 'hoyolab' | 'appsample'`, `MapInfo { key; name; url; allowed: boolean | null }`, `MapsResponse { maps; default_map }`; `Settings.default_map: MapKey`; `api.maps()`; `saveSettings` accepts `default_map`; helpers `initialTab(stored: string | null, fallback: MapKey): MapKey`, `loadLastMap()`, `saveLastMap(key)`. Test ids: `map-tab-<key>`, `map-fallback`, `map-frame`.

- [ ] **Step 1: Write the failing tests** — `frontend/src/lib/maps.test.ts`:

```ts
import { describe, expect, it } from 'vitest';
import { initialTab } from './maps';

describe('initialTab', () => {
	it('uses the stored tab when valid, otherwise the default', () => {
		expect(initialTab('appsample', 'hoyolab')).toBe('appsample');
		expect(initialTab(null, 'appsample')).toBe('appsample');
		expect(initialTab('google', 'hoyolab')).toBe('hoyolab');
	});
});
```

`frontend/e2e/map.spec.ts`:

```ts
import { expect, test } from '@playwright/test';

test('a map that refuses embedding shows the fallback card; the other embeds', async ({ page }) => {
	await page.goto('/map');
	await page.getByTestId('map-tab-hoyolab').click();
	const fallback = page.getByTestId('map-fallback');
	await expect(fallback).toContainText("This map doesn't allow embedding");
	await expect(fallback.getByRole('link', { name: 'Open in new tab' })).toHaveAttribute('href', /act\.hoyolab\.com/);
	await page.getByTestId('map-tab-appsample').click();
	await expect(page.getByTestId('map-frame')).toHaveAttribute('src', /appsample/);
});
```

- [ ] **Step 2: Run to verify the unit test fails** — `npm test` → FAIL.

- [ ] **Step 3: Helpers, types, API** — `frontend/src/lib/maps.ts`:

```ts
import type { MapKey } from './types';

const KEY = 'gt.lastMap';
const KEYS: MapKey[] = ['hoyolab', 'appsample'];

export function initialTab(stored: string | null, fallback: MapKey): MapKey {
	return KEYS.includes(stored as MapKey) ? (stored as MapKey) : fallback;
}

export function loadLastMap(): string | null {
	try {
		return localStorage.getItem(KEY);
	} catch {
		return null;
	}
}

export function saveLastMap(key: MapKey): void {
	try {
		localStorage.setItem(KEY, key);
	} catch {
		/* ignore */
	}
}
```

Types: `export type MapKey = 'hoyolab' | 'appsample'; export interface MapInfo { key: MapKey; name: string; url: string; allowed: boolean | null } export interface MapsResponse { maps: MapInfo[]; default_map: MapKey }`; `Settings` gains `default_map: MapKey`. API: `maps: () => request<MapsResponse>('GET', '/map')`, and add `default_map?: MapKey` to `saveSettings`'s body type.

- [ ] **Step 4: Map page** — `frontend/src/routes/map/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import { initialTab, loadLastMap, saveLastMap } from '$lib/maps';
	import type { MapKey, MapsResponse } from '$lib/types';

	let data = $state<MapsResponse | null>(null);
	let tab = $state<MapKey>('hoyolab');
	let error = $state<string | null>(null);
	const current = $derived(data?.maps.find((m) => m.key === tab) ?? null);

	onMount(async () => {
		try {
			data = await api.maps();
			tab = initialTab(loadLastMap(), data.default_map);
		} catch (e) {
			error = errorMessage(e);
		}
	});

	function choose(key: MapKey) {
		tab = key;
		saveLastMap(key);
	}
</script>

<h1>Map</h1>
{#if error}<p class="error">{error}</p>{/if}
{#if data}
	<div class="tabs" role="tablist">
		{#each data.maps as m (m.key)}
			<button type="button" role="tab" class="chip" class:on={tab === m.key} aria-selected={tab === m.key}
				data-testid="map-tab-{m.key}" onclick={() => choose(m.key)}>{m.name}</button>
		{/each}
	</div>
	{#if current}
		<div class="bar">
			<span>{current.name}</span>
			<a href={current.url} target="_blank" rel="noopener noreferrer">Open in new tab</a>
		</div>
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
	{/if}
{/if}

<style>
	.tabs { display: flex; gap: 6px; margin-bottom: 8px; }
	.bar { display: flex; justify-content: space-between; align-items: center; padding: 6px 10px;
		background: var(--panel-2); border-radius: 8px 8px 0 0; }
	iframe { width: 100%; height: calc(100vh - 220px); min-height: 480px; border: none; border-radius: 0 0 8px 8px; }
	.fallback { text-align: center; padding: 40px; }
	.big { display: inline-block; margin-top: 10px; padding: 10px 18px; border-radius: 8px; background: var(--accent);
		color: #111; font-weight: 600; text-decoration: none; }
</style>
```

- [ ] **Step 5: Settings and nav** — in `frontend/src/routes/settings/+page.svelte` add a **Default map** select (options HoYoLAB Interactive Map / AppSample) bound to the loaded settings' `default_map`, saved through `api.saveSettings({ default_map })` the same way the page saves its other fields (read the page and follow its pattern). Nav: `{ label: 'Map', href: '/map' },`. No `phase` entries remain in `NAV`; remove the now-unused disabled-entry markup only if `svelte-check` reports it unused.

- [ ] **Step 6: README** — add a section after Teams:

```markdown
## Events, Profile and Map

**Events** shows the live banners (with your pulls on each), current in-game events with their rewards — tick **Done** to track what's left and how many primogems are still unclaimed — countdowns to the daily, weekly, Abyss, Theater and Stygian resets, and every past banner with your pulls. **Profile** shows your Battle Chronicle: account stats, exploration per region, and Spiral Abyss, Imaginarium Theater and Stygian Onslaught results. Each cycle is kept, so past runs stay listed after HoYoLAB stops showing them. **Map** embeds the HoYoLAB and AppSample maps (choose the default in Settings); if a site refuses embedding, use **Open in new tab**.

Calendar, profile and challenge data refresh with the normal sync at most once an hour; **Sync now** always fetches them.
```

- [ ] **Step 7: Spec refinements** — append to the spec:

```markdown
---

## 13. Refinements made during planning (2026-11-21)

1. HoYoLAB's profile has no world level; the header shows AR and days active only.
2. `challenge_run.season` is HoYoLAB's own period id as a string (Abyss `season`, Theater `schedule.id`, Stygian `season.id`).
3. A part's last success for the throttle is read from `sync_run` (newest run whose part has `ok` and no `skipped`), the same way for all three parts.
4. A live banner's "your pulls" uses the Phase 3 `game_banner` window of the same pool that contains the banner's start and shares a featured 5★; no match → no pull count shown.
5. The calendar's `is_finished` event flag is ignored; Done stays manual.
```

- [ ] **Step 8: Full verification** — backend full suite; frontend `npm run check`, `npm test`, `npm run build`, e2e (all specs, including events, profile, map). Secret check against the branch's base commit:

```powershell
git diff <base> | Select-String -Pattern 'ltoken|ltuid|cookie_token|authkey=|@gmail|GENSHIN_UID=\d'
```

Expected: no matches; `git status --short` shows no `.env`, `data/` or `.e2e-data/`.

- [ ] **Step 9: Commit**

```bash
git add frontend README.md docs/superpowers/specs/2026-11-21-phase5-events-profile-map-design.md
git commit -m "feat(phase5): Map page, default map setting, map e2e; README; spec planning refinements"
```

**Milestone 3 done:** push the branch after the review; all nine pages are live.
