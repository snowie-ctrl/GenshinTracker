# Ad Astra Sub-project 6 — Inventory and Events Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn Events into an art timeline (popup, Timers, Done checklist, version-grouped banner history) fed by HoYoverse's public announcement feed merged with the HoYoLAB calendar, and turn Inventory's Materials tab into a "To farm" strip above plain best-known counts.

**Architecture:** A new `app/sync/announcements.py` fetches and parses the public feed inside the calendar part of every sync (through a new `HoyolabSource.get_announcements()`); `app/events/log.py` matches announcements to calendar events and keeps them in a new `event_log` table (migration 0011); `app/events/view.py` merges log + calendar into `timeline` rows and regroups banner history by version and phase. The frontend gets `lib/timeline.ts` (pure maths), `EventTimeline`, `EventModal`, `BannerHistory` components and new tile helpers in `materials.ts`.

**Tech Stack:** FastAPI, SQLAlchemy 2, Alembic, SQLite, httpx (backend); SvelteKit with Svelte 5 runes, TypeScript, Vitest, Playwright (frontend).

**Spec:** `docs/superpowers/specs/2026-11-23-ad-astra-inventory-events-design.md`

## Global Constraints

- Python: the repo venv's `.venv/Scripts/python.exe` (in the main checkout, one level above `.claude/worktrees/`); backend tests run from `backend/` with `<python> -m pytest -q`.
- Frontend checks from `frontend/`: `npm run check`, `npx vitest run`, `npm run build`, `PYTHON=<python> npx playwright test` (workers 1; one shared seeded server; every test restores any state it changes).
- The feed request sends only fixed parameters plus the server region: `game=hk4e&game_biz=hk4e_global&lang=en&bundle_id=hk4e_global&platform=pc&region=<server>&level=60`. No cookie, no UID, no nickname, no email.
- Unofficial API code lives only in `backend/app/sync/` (and `wishes/`).
- No game art or personal data committed; fixtures use placeholder image URLs on `sdk.hoyoverse.com` and made-up text; test UIDs are 800000001.
- Never put the user's name or email (or any part of it) in a committed file, including grep patterns.
- Descriptions reach the frontend as plain text only; no `{@html}`.
- Timeline rows: gameplay events and event wishes only; anything mentioning "Genius Invokation" is dropped; only the `type_id == 1` (Event) group is read.
- `event_log` rows ended more than 90 days ago are pruned; the timeline shows rows ending at or after `now − 21 days`.
- Teapot materials are out of scope.
- Commit messages end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **A feed outage must not cost the calendar.** If `getAnnList` fails, the calendar snapshot still saves, the part stays `ok`, and the page shows "⚠ event art update failed" while the timeline draws from what is stored. (Task 3 test `test_feed_failure_keeps_calendar`.)
2. **Year-long events and events with no start.** A "Hunt Begins!"-style event ending months away must not stretch the axis to a year, and a calendar event with `start: null` must still get a bar. (Task 6 tests `clamps far ends` and `missing start uses axis start`.)
3. **Two character wishes in one phase.** Both must find the single paimon.moe row and show its items; neither may vanish. (Task 2 test `test_both_character_wishes_match_one_row`.)
4. **Stored filter from before the change.** A browser that remembered `needed` or `farm` must open on "All", not an empty grid. (Task 9 test `readFilter falls back`.)
5. **Search during the To-farm strip.** Typing in search must hide the strip and leave matching backpack tiles visible, so a material is never shown twice with different numbers. (Task 9 e2e.)

---

## File Structure

Backend:
- Create `backend/app/sync/announcements.py` — fetch + pure parse of the public feed (`Announcement`, `parse`, `fetch_announcements`, `AnnouncementError`).
- Create `backend/app/events/log.py` — `normalise`, `match_calendar`, `wish_pool`, `match_banner`, `record` (upsert/prune `event_log`).
- Modify `backend/app/db/models.py` — `EventLog` model.
- Create `backend/migrations/versions/0011_event_log.py`.
- Modify `backend/app/sync/hoyolab.py` — `get_announcements` on the protocol and `GenshinPySource`.
- Modify `backend/app/sync/runner.py` — calendar part calls the feed and `record`.
- Modify `backend/app/events/view.py` — `timeline_rows`, `ending_soon_list`, new `banner_history`.
- Modify `backend/app/api/events.py` — new payload fields, new history endpoint shape.
- Modify `backend/app/devseed.py` — demo `event_log` rows.
- Tests: `backend/tests/fixtures/ann_list.json`, `backend/tests/fixtures/ann_content.json`, `backend/tests/test_announcements.py`, `backend/tests/test_event_log.py`, `backend/tests/test_migration_0011.py`, updates to `tests/fakes.py`, `tests/test_sync_chronicle.py`, `tests/test_events_view.py`, `tests/test_api_events.py`.

Frontend:
- Modify `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`.
- Create `frontend/src/lib/timeline.ts` + `timeline.test.ts`.
- Create `frontend/src/lib/EventTimeline.svelte`, `EventModal.svelte`, `BannerHistory.svelte`.
- Rewrite `frontend/src/routes/events/+page.svelte`.
- Modify `frontend/src/lib/materials.ts` + `materials.test.ts`, `frontend/src/lib/MaterialTile.svelte`, `frontend/src/routes/inventory/+page.svelte`.
- E2E: `frontend/e2e/events.spec.ts`, `frontend/e2e/planner.spec.ts`, `frontend/e2e/good.spec.ts`.

---

### Task 1: Announcement feed parser

**Files:**
- Create: `backend/app/sync/announcements.py`
- Create: `backend/tests/fixtures/ann_list.json`, `backend/tests/fixtures/ann_content.json`
- Test: `backend/tests/test_announcements.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) class Announcement: ann_id: int; kind: str  # "event" | "wish"; name: str; title: str; start: str | None; end: str | None; window_start: str | None; window_end: str | None; image: str | None; description: str`
  - `def parse(ann_list: dict, ann_content: dict, offset_hours: int) -> list[Announcement]` (all times naive-UTC ISO strings via `app.timeutil.iso`, ending in `Z`)
  - `class AnnouncementError(Exception)`
  - `async def fetch_announcements(http: httpx.AsyncClient, region: str) -> list[Announcement]`
  - `FEED_BASE = "https://sg-hk4e-api.hoyoverse.com/common/hk4e_global/announcement/api"`

- [ ] **Step 1: Write the fixtures** (made-up text, placeholder image URLs, same shape as the real feed: the time tags are HTML-escaped inside the content)

`backend/tests/fixtures/ann_list.json`:

```json
{"retcode": 0, "message": "OK", "data": {"timezone": -5, "list": [
  {"type_id": 2, "type_label": "Game", "list": [
    {"ann_id": 100, "title": "Update Details", "subtitle": "Update Details", "banner": "https://sdk.hoyoverse.com/upload/ann/test/game.png",
     "start_time": "2026-11-04 00:00:00", "end_time": "2026-12-15 23:00:00", "type": 2}]},
  {"type_id": 1, "type_label": "Event", "list": [
    {"ann_id": 201, "title": "\"Digging Days\" Event: Dig and Win", "subtitle": "Digging Days", "banner": "https://sdk.hoyoverse.com/upload/ann/test/dig.png",
     "start_time": "2026-11-18 05:00:00", "end_time": "2026-11-30 03:59:59", "type": 1},
    {"ann_id": 202, "title": "Event Wish \"Test Abundance\" - Boosted Drop Rate", "subtitle": "Event Wish \"Test Abundance\"", "banner": "",
     "start_time": "2026-11-19 09:00:00", "end_time": "2026-12-15 14:59:59", "type": 1},
    {"ann_id": 203, "title": "\"Genius Invokation TCG\" Test Mode", "subtitle": "Genius Invokation TCG - Test Mode", "banner": "https://sdk.hoyoverse.com/upload/ann/test/tcg.png",
     "start_time": "2026-11-19 05:00:00", "end_time": "2026-12-07 03:59:59", "type": 1},
    {"ann_id": 204, "title": "\"Grand Test\" Event: Participate", "subtitle": "Grand Test", "banner": "https://sdk.hoyoverse.com/upload/ann/test/grand.png",
     "start_time": "2026-11-02 05:00:00", "end_time": "2026-12-16 00:00:00", "type": 1},
    {"ann_id": 205, "title": "Login Gift: Test Rewards", "subtitle": "Test Rewards", "banner": "https://sdk.hoyoverse.com/upload/ann/test/login.png",
     "start_time": "2026-11-02 05:00:00", "end_time": "2026-12-14 03:59:59", "type": 1},
    {"ann_id": 206, "title": "Event Wish \"Test Invocation\" - Epitome Invocation", "subtitle": "Event Wish - Test Invocation", "banner": "https://sdk.hoyoverse.com/upload/ann/test/weapon.png",
     "start_time": "2026-11-19 09:00:00", "end_time": "2026-12-15 14:59:59", "type": 1}]},
  {"type_id": 26, "type_label": "Miliastra Wonderland", "list": [
    {"ann_id": 300, "title": "Season Opening", "subtitle": "Season", "banner": "https://sdk.hoyoverse.com/upload/ann/test/mw.png",
     "start_time": "2026-11-02 05:00:00", "end_time": "2026-12-16 00:00:00", "type": 26}]}
]}}
```

`backend/tests/fixtures/ann_content.json`:

```json
{"retcode": 0, "message": "OK", "data": {"list": [
  {"ann_id": 201, "banner": "", "content": "<p><span>〓Event Duration〓</span></p><p><span>&lt;t class=\"t_lc\" contenteditable=\"false\"&gt;2026/11/20 10:00&lt;/t&gt; – &lt;t class=\"t_lc\" contenteditable=\"false\"&gt;2026/11/30 03:59&lt;/t&gt;</span></p><p><span>Dig up &amp; smash test blocks.</span></p><p><img src=\"https://sdk.hoyoverse.com/upload/ann/test/inline.png\"></p>"},
  {"ann_id": 202, "banner": "https://sdk.hoyoverse.com/upload/ann/test/wish.png", "content": "<p>〓Wish Duration〓</p><p>&lt;t class=\"t_lc\" contenteditable=\"false\"&gt;2026/11/24 18:00&lt;/t&gt; – &lt;t class=\"t_lc\" contenteditable=\"false\"&gt;2026/12/15 14:59&lt;/t&gt;</p><p>Test character featured.</p>"},
  {"ann_id": 203, "banner": "", "content": "<p>TCG text</p>"},
  {"ann_id": 204, "banner": "", "content": "<p>〓Event Duration〓</p><p>Available throughout the entirety of Version 9.9</p><p>Defend the test.</p>"},
  {"ann_id": 205, "banner": "", "content": "<p>〓Event Duration〓</p><p>After the update – &lt;t class=\"t_gl\" contenteditable=\"false\"&gt;2026/12/14 03:59&lt;/t&gt;</p><p>Log in.</p>"},
  {"ann_id": 206, "banner": "", "content": "<p>&lt;t class=\"t_lc\" contenteditable=\"false\"&gt;2026/11/24 18:00&lt;/t&gt; – &lt;t class=\"t_lc\" contenteditable=\"false\"&gt;2026/12/15 14:59&lt;/t&gt;</p>"}
]}}
```

- [ ] **Step 2: Write the failing tests** — `backend/tests/test_announcements.py`

```python
import json
from pathlib import Path

import httpx
import pytest

from app.sync.announcements import AnnouncementError, FEED_BASE, fetch_announcements, parse

FIX = Path(__file__).parent / "fixtures"
LIST = json.loads((FIX / "ann_list.json").read_text(encoding="utf-8"))
CONTENT = json.loads((FIX / "ann_content.json").read_text(encoding="utf-8"))


def by_id(rows):
    return {a.ann_id: a for a in rows}


def test_only_event_group_and_no_tcg():
    rows = by_id(parse(LIST, CONTENT, -5))
    assert sorted(rows) == [201, 202, 204, 205, 206]


def test_event_times_from_local_tags_shifted_to_utc():
    a = by_id(parse(LIST, CONTENT, -5))[201]
    assert a.kind == "event" and a.name == "Digging Days"
    assert (a.start, a.end) == ("2026-11-20T15:00:00Z", "2026-11-30T08:59:00Z")
    assert (a.window_start, a.window_end) == ("2026-11-18T10:00:00Z", "2026-11-30T08:59:59Z")
    assert a.image == "https://sdk.hoyoverse.com/upload/ann/test/dig.png"


def test_wish_name_cleaned_and_image_from_content():
    rows = by_id(parse(LIST, CONTENT, 8))
    assert rows[202].kind == "wish" and rows[202].name == "Test Abundance"
    assert rows[202].image == "https://sdk.hoyoverse.com/upload/ann/test/wish.png"
    assert rows[202].start == "2026-11-24T10:00:00Z"
    assert rows[206].kind == "wish" and rows[206].name == "Test Invocation"


def test_no_tags_leaves_times_empty_one_global_tag_is_end_at_utc8():
    rows = by_id(parse(LIST, CONTENT, -5))
    assert (rows[204].start, rows[204].end) == (None, None)
    assert rows[205].start is None and rows[205].end == "2026-12-13T19:59:00Z"


def test_description_is_plain_paragraphs():
    d = by_id(parse(LIST, CONTENT, -5))[201].description
    assert "<" not in d and "&amp;" not in d
    assert d.split("\n\n") == ["〓Event Duration〓", "2026/11/20 10:00 – 2026/11/30 03:59", "Dig up & smash test blocks."]


async def test_fetch_sends_only_fixed_params_and_region():
    seen = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        body = LIST if request.url.path.endswith("getAnnList") else CONTENT
        return httpx.Response(200, json=body)

    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as http:
        rows = await fetch_announcements(http, "os_usa")
    assert len(rows) == 5
    for r in seen:
        assert str(r.url).startswith(FEED_BASE)
        assert dict(r.url.params) == {"game": "hk4e", "game_biz": "hk4e_global", "lang": "en",
                                      "bundle_id": "hk4e_global", "platform": "pc", "region": "os_usa", "level": "60"}
        assert "cookie" not in {k.lower() for k in r.headers}


async def test_fetch_raises_on_bad_retcode():
    transport = httpx.MockTransport(lambda r: httpx.Response(200, json={"retcode": -1, "message": "x", "data": None}))
    async with httpx.AsyncClient(transport=transport) as http:
        with pytest.raises(AnnouncementError):
            await fetch_announcements(http, "os_euro")
```

- [ ] **Step 3: Run to verify failure**

Run (from `backend/`): `<python> -m pytest tests/test_announcements.py -q`
Expected: FAIL, `ModuleNotFoundError: No module named 'app.sync.announcements'`.

- [ ] **Step 4: Implement** — `backend/app/sync/announcements.py`

```python
"""HoYoverse's public in-game announcement feed (no cookie, no UID): event art, text and true times.
Unofficial API, so it lives in sync/. Everything else talks to our own Announcement dataclass."""
from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timedelta

import httpx

from app.servertime import REGION_OFFSETS
from app.timeutil import iso

FEED_BASE = "https://sg-hk4e-api.hoyoverse.com/common/hk4e_global/announcement/api"
EVENT_TYPE_ID = 1
GLOBAL_OFFSET = 8                      # t_gl tags are UTC+8
TAG = re.compile(r'<t class="(t_lc|t_gl)"[^>]*>\s*(\d{4}/\d{2}/\d{2} \d{2}:\d{2})(?::\d{2})?\s*</t>')
BLOCK = re.compile(r"</?(p|div|br|li|h\d)[^>]*>", re.I)
ANY_TAG = re.compile(r"<[^>]+>")
WISH_PREFIX = re.compile(r'^\s*event wish\s*[-–:]?\s*', re.I)


class AnnouncementError(Exception):
    pass


@dataclass(frozen=True)
class Announcement:
    ann_id: int
    kind: str                 # event | wish
    name: str
    title: str
    start: str | None
    end: str | None
    window_start: str | None  # the announcement's display window, used only as a fallback
    window_end: str | None
    image: str | None
    description: str


def params(region: str) -> dict[str, str]:
    return {"game": "hk4e", "game_biz": "hk4e_global", "lang": "en", "bundle_id": "hk4e_global",
            "platform": "pc", "region": region, "level": "60"}


def _utc(local: str, fmt: str, offset_hours: int) -> str:
    return iso(datetime.strptime(local, fmt) - timedelta(hours=offset_hours))


def _times(content: str, offset_hours: int) -> tuple[str | None, str | None]:
    found = TAG.findall(html.unescape(content))
    stamps = [_utc(t, "%Y/%m/%d %H:%M", offset_hours if kind == "t_lc" else GLOBAL_OFFSET) for kind, t in found[:2]]
    if len(stamps) >= 2:
        return stamps[0], stamps[1]
    if len(stamps) == 1:
        return None, stamps[0]
    return None, None


def plain_text(content: str) -> str:
    text = html.unescape(content)
    text = TAG.sub(lambda m: m.group(2), text)
    text = BLOCK.sub("\n\n", text)
    text = html.unescape(ANY_TAG.sub("", text))
    paras = [" ".join(p.split()) for p in text.split("\n\n")]
    return "\n\n".join(p for p in paras if p)


def _name(item: dict) -> str:
    sub = (item.get("subtitle") or "").replace("\n", " ").strip()
    sub = WISH_PREFIX.sub("", sub).strip().strip('"“”').strip()
    return sub or (item.get("title") or "").strip()


def parse(ann_list: dict, ann_content: dict, offset_hours: int) -> list[Announcement]:
    content = {int(c["ann_id"]): c for c in (ann_content.get("data") or {}).get("list", [])}
    out: list[Announcement] = []
    for group in (ann_list.get("data") or {}).get("list", []):
        if int(group.get("type_id", 0)) != EVENT_TYPE_ID:
            continue
        for item in group.get("list", []):
            title, sub = item.get("title") or "", item.get("subtitle") or ""
            if "genius invokation" in f"{title} {sub}".lower():
                continue
            ann_id = int(item["ann_id"])
            body = content.get(ann_id, {})
            start, end = _times(body.get("content") or "", offset_hours)
            out.append(Announcement(
                ann_id=ann_id,
                kind="wish" if title.lower().startswith("event wish") else "event",
                name=_name(item), title=title, start=start, end=end,
                window_start=_utc(item["start_time"], "%Y-%m-%d %H:%M:%S", offset_hours) if item.get("start_time") else None,
                window_end=_utc(item["end_time"], "%Y-%m-%d %H:%M:%S", offset_hours) if item.get("end_time") else None,
                image=item.get("banner") or body.get("banner") or None,
                description=plain_text(body.get("content") or ""),
            ))
    return out


async def _get(http: httpx.AsyncClient, path: str, region: str) -> dict:
    try:
        r = await http.get(f"{FEED_BASE}/{path}", params=params(region), timeout=20)
        body = r.json()
    except (httpx.HTTPError, ValueError) as e:
        raise AnnouncementError(f"{path}: {type(e).__name__}") from None
    if r.status_code != 200 or not isinstance(body, dict) or body.get("retcode") != 0 or not body.get("data"):
        raise AnnouncementError(f"{path}: retcode {body.get('retcode') if isinstance(body, dict) else '?'}")
    return body


async def fetch_announcements(http: httpx.AsyncClient, region: str) -> list[Announcement]:
    ann_list = await _get(http, "getAnnList", region)
    ann_content = await _get(http, "getAnnContent", region)
    return parse(ann_list, ann_content, REGION_OFFSETS.get(region, 8))
```

`app.timeutil.iso` returns `YYYY-MM-DDTHH:MM:SSZ` (naive UTC, microseconds dropped), which the tests expect.

- [ ] **Step 5: Run to verify pass**

Run: `<python> -m pytest tests/test_announcements.py -q`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add backend/app/sync/announcements.py backend/tests/test_announcements.py backend/tests/fixtures/ann_list.json backend/tests/fixtures/ann_content.json
git commit -m "feat(events): parse the public announcement feed"
```

---

### Task 2: `event_log` table, matching and recording

**Files:**
- Modify: `backend/app/db/models.py` (add `EventLog` after `EventDone`)
- Create: `backend/migrations/versions/0011_event_log.py`
- Create: `backend/app/events/log.py`
- Test: `backend/tests/test_migration_0011.py`, `backend/tests/test_event_log.py`

**Interfaces:**
- Consumes: `Announcement` (Task 1).
- Produces:
  - `class EventLog(Base)`: `key: str` PK, `kind: str`, `name: str`, `start: str | None`, `end: str | None`, `image: str | None`, `description: str`, `calendar_id: int | None`, `first_seen: datetime`, `last_seen: datetime`.
  - `def normalise(name: str) -> str`
  - `def match_calendar(ann: Announcement, events: list[dict]) -> dict | None` (calendar event dicts as stored in the snapshot)
  - `def wish_pool(title: str) -> str` (`weapon` | `chronicled` | `character`)
  - `def match_banner(pool: str, start: str | None, banners: list[GameBanner]) -> GameBanner | None`
  - `def record(session: Session, anns: list[Announcement], calendar: dict, now: datetime) -> int` (returns rows written)
  - `KEEP = timedelta(days=90)`
  - Stored `kind` is `event` or `wish:<pool>` (`wish:character`, `wish:weapon`, `wish:chronicled`), so readers know a wish's pool without the announcement title.

- [ ] **Step 1: Write the failing migration test** — `backend/tests/test_migration_0011.py`

```python
from sqlalchemy import inspect

from app.db.engine import make_engine
from test_migration_0007 import downgrade, upgrade


def test_0011_creates_event_log(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0011")
    cols = {c["name"] for c in inspect(engine).get_columns("event_log")}
    assert cols == {"key", "kind", "name", "start", "end", "image", "description", "calendar_id",
                    "first_seen", "last_seen"}
    engine.dispose()


def test_0011_downgrade(paths):
    engine = make_engine(paths.db_file)
    upgrade(engine, "0011")
    downgrade(engine, "0010")
    assert "event_log" not in inspect(engine).get_table_names()
    engine.dispose()
```

- [ ] **Step 2: Write the failing log tests** — `backend/tests/test_event_log.py`

```python
from datetime import datetime, timedelta

from app.db.models import EventLog, GameBanner
from app.events.log import match_banner, match_calendar, normalise, record, wish_pool
from app.sync.announcements import Announcement

NOW = datetime(2026, 11, 23, 12, 0, 0)


def ann(ann_id, name, kind="event", start="2026-11-20T15:00:00Z", end="2026-11-30T08:59:00Z", title=None):
    return Announcement(ann_id, kind, name, title or name, start, end, None, None,
                        "https://sdk.hoyoverse.com/upload/ann/test/x.png", "Text.")


def cal_event(id, name, start="2026-11-20T15:00:00Z", end="2026-11-30T08:59:59Z"):
    return {"id": id, "name": name, "description": "", "start": start, "end": end, "rewards": []}


def banner(pool, start, key=None):
    return GameBanner(key=key or f"{pool}|{start}|0", pool=pool, name="B", short_name="B", start=start, end=start,
                      timezone_dependent=True, timezone_dependent_end=False, order=0, featured_5=[], featured_4=[],
                      version="9.9")


def test_normalise():
    assert normalise('"Stress Block" Smashing: Project!') == "stress block smashing project"


def test_match_calendar_containment_both_ways_and_closest_end():
    events = [cal_event(1, "Stygian Onslaught", end="2026-12-15T08:59:59Z"),
              cal_event(2, "Digging", end="2026-11-30T08:59:59Z"),
              cal_event(3, "Digging", end="2027-01-30T08:59:59Z")]
    assert match_calendar(ann(9, "Stygian Onslaught Event: Ley Line"), events)["id"] == 1
    assert match_calendar(ann(9, "Digging Days"), events)["id"] == 2
    assert match_calendar(ann(9, "Unrelated"), events) is None
    assert match_calendar(ann(9, "Digging Days", kind="wish"), events) is None


def test_wish_pool():
    assert wish_pool('Event Wish "X" - Epitome Invocation') == "weapon"
    assert wish_pool('Event Wish "Y" - Chronicled Wish Now Available') == "chronicled"
    assert wish_pool('Event Wish "Z" - Boosted Drop Rate') == "character"


def test_both_character_wishes_match_one_row():
    rows = [banner("character", "2026-11-25 02:00:00"), banner("weapon", "2026-11-25 02:00:00"),
            banner("character", "2026-11-04 06:00:00")]
    first = match_banner("character", "2026-11-24T23:00:00Z", rows)
    second = match_banner("character", "2026-11-24T23:00:00Z", rows)
    assert first is rows[0] and second is rows[0]
    assert match_banner("character", "2026-12-20T00:00:00Z", rows) is None
    assert match_banner("character", None, rows) is None


def test_record_upserts_adds_cal_rows_replaces_them_and_prunes(session_factory):
    calendar = {"banners": [], "challenges": [], "events": [
        cal_event(1, "Digging"), cal_event(2, "Calendar Only"), cal_event(3, "No Dates", start=None, end=None)]}
    with session_factory.begin() as s:
        s.add(EventLog(key="ann:1", kind="event", name="Ancient", start=None, end="2026-08-01T00:00:00Z",
                       image=None, description="", calendar_id=None, first_seen=NOW, last_seen=NOW))
        record(s, [ann(10, "Digging Days")], calendar, NOW)
    with session_factory() as s:
        keys = {r.key: r for r in s.query(EventLog)}
    assert set(keys) == {"ann:10", "cal:2"}                    # ancient pruned, no-dates calendar row skipped
    assert keys["ann:10"].calendar_id == 1
    later = NOW + timedelta(hours=1)
    with session_factory.begin() as s:
        record(s, [ann(10, "Digging Days", end="2026-12-01T00:00:00Z"), ann(11, "Calendar Only")], calendar, later)
    with session_factory() as s:
        keys = {r.key: r for r in s.query(EventLog)}
    assert set(keys) == {"ann:10", "ann:11"}                   # cal:2 replaced by the announcement
    assert keys["ann:10"].end == "2026-12-01T00:00:00Z" and keys["ann:10"].first_seen == NOW
    assert keys["ann:10"].last_seen == later


def test_record_stores_wish_pool(session_factory):
    with session_factory.begin() as s:
        record(s, [ann(30, "Test Invocation", kind="wish", title='Event Wish "Test Invocation" - Epitome Invocation')],
               {"events": []}, NOW)
    with session_factory() as s:
        assert s.get(EventLog, "ann:30").kind == "wish:weapon"


def test_record_keeps_rows_missing_from_feed_and_fills_times(session_factory):
    calendar = {"banners": [], "challenges": [], "events": [cal_event(1, "Grand Test")]}
    with session_factory.begin() as s:
        record(s, [ann(20, "Grand Test", start=None, end=None), ann(21, "Window Only", start=None, end=None)],
               calendar, NOW)
    with session_factory.begin() as s:
        record(s, [], calendar, NOW + timedelta(hours=1))
    with session_factory() as s:
        rows = {r.key: r for r in s.query(EventLog)}
    assert rows["ann:20"].start == "2026-11-20T15:00:00Z"      # from the matched calendar event
    assert "ann:21" not in rows                                 # no times and no fallback window: skipped
```

- [ ] **Step 3: Run to verify failure**

Run: `<python> -m pytest tests/test_migration_0011.py tests/test_event_log.py -q`
Expected: FAIL (`ImportError: cannot import name 'EventLog'`).

- [ ] **Step 4: Add the model** — in `backend/app/db/models.py` after `class EventDone` (add `Text` to the existing `from sqlalchemy import ...` line; it is not imported yet):

```python
class EventLog(Base):
    """Every event and event wish the announcement feed (or calendar) has shown; pruned 90 days after its end."""
    __tablename__ = "event_log"
    key: Mapped[str] = mapped_column(String, primary_key=True)          # ann:<ann_id> | cal:<calendar id>
    kind: Mapped[str] = mapped_column(String)                           # event | wish
    name: Mapped[str] = mapped_column(String)
    start: Mapped[str | None] = mapped_column(String, nullable=True)    # UTC ISO
    end: Mapped[str | None] = mapped_column(String, nullable=True)
    image: Mapped[str | None] = mapped_column(String, nullable=True)
    description: Mapped[str] = mapped_column(Text, default="")
    calendar_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime)
    last_seen: Mapped[datetime] = mapped_column(DateTime)
```

- [ ] **Step 5: Add the migration** — `backend/migrations/versions/0011_event_log.py`

```python
"""Ad Astra sub-project 6: event_log for the Events timeline

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-23
"""
import sqlalchemy as sa
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "event_log",
        sa.Column("key", sa.String(), primary_key=True),
        sa.Column("kind", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("start", sa.String(), nullable=True),
        sa.Column("end", sa.String(), nullable=True),
        sa.Column("image", sa.String(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("calendar_id", sa.Integer(), nullable=True),
        sa.Column("first_seen", sa.DateTime(), nullable=False),
        sa.Column("last_seen", sa.DateTime(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("event_log")
```

- [ ] **Step 6: Implement** — `backend/app/events/log.py`

```python
"""Keeps every announced event and wish in event_log, matched to HoYoLAB calendar events by name."""
from __future__ import annotations

import re
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import EventLog, GameBanner
from app.sync.announcements import Announcement

KEEP = timedelta(days=90)
WISH_MATCH = timedelta(days=1)
_PUNCT = re.compile(r"[^\w\s]")


def _dt(s: str | None) -> datetime | None:
    if not s:
        return None
    return datetime.fromisoformat(s.rstrip("Z").replace(" ", "T"))


def normalise(name: str) -> str:
    return " ".join(_PUNCT.sub(" ", name.lower()).split())


def match_calendar(ann: Announcement, events: list[dict]) -> dict | None:
    if ann.kind != "event":
        return None
    a = normalise(ann.name)
    hits = [e for e in events if (c := normalise(e.get("name") or "")) and (c in a or a in c)]
    if not hits:
        return None
    end = _dt(ann.end) or _dt(ann.window_end)
    if end is None:
        return hits[0]
    far = timedelta(days=36500)
    return min(hits, key=lambda e: abs((_dt(e.get("end")) or end + far) - end))


def wish_pool(title: str) -> str:
    t = title.lower()
    if "epitome invocation" in t:
        return "weapon"
    if "chronicled" in t:
        return "chronicled"
    return "character"


def match_banner(pool: str, start: str | None, banners: list[GameBanner]) -> GameBanner | None:
    at = _dt(start)
    if at is None:
        return None
    hits = [b for b in banners if b.pool == pool and abs(_dt(b.start) - at) <= WISH_MATCH]
    return min(hits, key=lambda b: abs(_dt(b.start) - at)) if hits else None


def _upsert(session: Session, key: str, now: datetime, **values) -> None:
    row = session.get(EventLog, key)
    if row is None:
        session.add(EventLog(key=key, first_seen=now, last_seen=now, **values))
    else:
        for k, v in values.items():
            setattr(row, k, v)
        row.last_seen = now


def record(session: Session, anns: list[Announcement], calendar: dict, now: datetime) -> int:
    events = [e for e in calendar.get("events", []) if isinstance(e, dict)]
    matched: set[int] = set()
    written = 0
    for a in anns:
        cal = match_calendar(a, events)
        start = a.start or (cal or {}).get("start") or a.window_start
        end = a.end or (cal or {}).get("end") or a.window_end
        if start is None and end is None:
            continue
        if cal is not None:
            matched.add(cal["id"])
            session.execute(delete(EventLog).where(EventLog.key == f"cal:{cal['id']}"))
        kind = f"wish:{wish_pool(a.title)}" if a.kind == "wish" else "event"
        _upsert(session, f"ann:{a.ann_id}", now, kind=kind, name=a.name, start=start, end=end, image=a.image,
                description=a.description, calendar_id=cal["id"] if cal else None)
        written += 1
    known = {r for (r,) in session.execute(select(EventLog.calendar_id).where(EventLog.calendar_id.is_not(None)))}
    for e in events:
        if e["id"] in matched or e["id"] in known or not e.get("start") or not e.get("end"):
            continue
        _upsert(session, f"cal:{e['id']}", now, kind="event", name=e["name"], start=e["start"], end=e["end"],
                image=None, description=e.get("description") or "", calendar_id=e["id"])
        written += 1
    session.flush()
    cutoff = now - KEEP
    stale = [r.key for r in session.scalars(select(EventLog)) if (end := _dt(r.end)) is not None and end < cutoff]
    if stale:
        session.execute(delete(EventLog).where(EventLog.key.in_(stale)))
    return written
```

Note: a `cal:` row whose calendar id is already the `calendar_id` of an `ann:` row is never re-added (the `known` set), so a later sync without the announcement keeps the announcement row instead.

- [ ] **Step 7: Run to verify pass**

Run: `<python> -m pytest tests/test_migration_0011.py tests/test_event_log.py -q`
Expected: all pass. Then the full suite: `<python> -m pytest -q` (588 + new, all pass).

- [ ] **Step 8: Commit**

```bash
git add backend/app/db/models.py backend/migrations/versions/0011_event_log.py backend/app/events/log.py backend/tests/test_migration_0011.py backend/tests/test_event_log.py
git commit -m "feat(events): event_log table with calendar and banner matching"
```

---

### Task 3: Fetch the feed during the calendar sync part

**Files:**
- Modify: `backend/app/sync/hoyolab.py` (protocol + `GenshinPySource.get_announcements`)
- Modify: `backend/app/sync/runner.py:188-194` (calendar branch of `_chronicle_part`)
- Modify: `backend/tests/fakes.py` (`FakeSource`)
- Test: `backend/tests/test_sync_chronicle.py`

**Interfaces:**
- Consumes: `fetch_announcements`, `Announcement` (Task 1); `record` (Task 2).
- Produces:
  - `HoyolabSource.get_announcements(self) -> list[Announcement]`
  - Calendar part result: `{"ok": True, "count": n}` on success; `{"ok": True, "count": n, "announcements_error": "<Type>: <msg>"}` when the feed failed. The key is absent on success so existing assertions stay valid.
  - `FakeSource(announcements=[...])`; `fail={"announcements": Exception}` raises from `get_announcements`.

- [ ] **Step 1: Extend `FakeSource`** — in `backend/tests/fakes.py` add an `announcements=None` keyword to `__init__` (store `self.announcements = announcements`) and the method:

```python
    async def get_announcements(self):
        self.calls.append("announcements")
        if "announcements" in self.fail:
            raise self.fail["announcements"]
        return list(self.announcements or [])
```

- [ ] **Step 2: Write the failing tests** — append to `backend/tests/test_sync_chronicle.py`

```python
from app.db.models import EventLog
from app.sync.announcements import Announcement, AnnouncementError

ANN = Announcement(501, "event", "Fest", "Fest", "2026-11-19T04:00:00Z", "2026-12-01T04:00:00Z", None, None,
                   "https://sdk.hoyoverse.com/upload/ann/test/fest.png", "About the fest.")


async def test_calendar_part_records_announcements(paths, session_factory):
    seed_game(session_factory)
    m = manager(paths, session_factory, FakeSource(calendar=CAL, announcements=[ANN]))
    await m.request("manual")
    await m.wait()
    assert last_run(session_factory).parts["calendar"] == {"ok": True, "count": 1}
    with session_factory() as s:
        row = s.get(EventLog, "ann:501")
        assert row.calendar_id == 9001 and row.image.endswith("fest.png")


async def test_feed_failure_keeps_calendar(paths, session_factory):
    seed_game(session_factory)
    m = manager(paths, session_factory,
                FakeSource(calendar=CAL, fail={"announcements": AnnouncementError("getAnnList: retcode -1")}))
    await m.request("manual")
    await m.wait()
    part = last_run(session_factory).parts["calendar"]
    assert part["ok"] is True and part["count"] == 1
    assert part["announcements_error"] == "AnnouncementError: getAnnList: retcode -1"
    with session_factory() as s:
        assert s.get(HoyolabSnapshot, "calendar").data["events"][0]["id"] == 9001
        assert s.get(EventLog, "cal:9001") is not None          # the calendar event still gets a bar
```

- [ ] **Step 3: Run to verify failure**

Run: `<python> -m pytest tests/test_sync_chronicle.py -q`
Expected: the two new tests FAIL (no `EventLog` rows / no `announcements_error`).

- [ ] **Step 4: Protocol and real source** — in `backend/app/sync/hoyolab.py`:

Add to the imports: `import httpx` and `from app.sync.announcements import Announcement, fetch_announcements`.

Add to `class HoyolabSource(Protocol)`:

```python
    async def get_announcements(self) -> list[Announcement]: ...
```

Add to `GenshinPySource`:

```python
    async def get_announcements(self) -> list[Announcement]:
        """Public feed: no cookie and no UID, only the server region."""
        async with httpx.AsyncClient() as http:
            return await fetch_announcements(http, self._region)
```

- [ ] **Step 5: Runner** — replace the calendar branch in `_chronicle_part` (`backend/app/sync/runner.py`) with:

```python
        if part == "calendar":
            cal = await source.get_calendar()
            result: dict = {"ok": True, "count": len(cal.events)}
            try:
                anns = await source.get_announcements()
            except AuthExpired:
                raise
            except Exception as e:  # the feed is extra: its failure never costs the calendar
                log.warning("Announcement feed failed: %s", type(e).__name__)
                anns, result["announcements_error"] = [], _failure(e)["error"]
            with self._sf.begin() as s:
                data = to_json(cal)
                save_snapshot(s, "calendar", data, now)
                record(s, anns, data, now)
                return result, unknown_character_ids(s, character_ids(cal))
```

and add `from app.events.log import record` to the runner's imports.

- [ ] **Step 6: Run to verify pass**

Run: `<python> -m pytest tests/test_sync_chronicle.py tests/test_sync_runner.py tests/test_hoyolab.py -q`
Expected: all pass. Then `<python> -m pytest -q`.

- [ ] **Step 7: Commit**

```bash
git add backend/app/sync/hoyolab.py backend/app/sync/runner.py backend/tests/fakes.py backend/tests/test_sync_chronicle.py
git commit -m "feat(events): fetch announcements with the calendar sync part"
```

---

### Task 4: Merged timeline in the events payload, plus dev seed

**Files:**
- Modify: `backend/app/events/view.py` (add `timeline_rows`, `ending_soon_list`)
- Modify: `backend/app/api/events.py` (`events_payload` gains `timeline`, `ending_soon`, `announcements_error`)
- Modify: `backend/app/devseed.py` (demo `event_log` rows)
- Test: `backend/tests/test_events_view.py`, `backend/tests/test_api_events.py`, `backend/tests/test_devseed.py`

**Interfaces:**
- Consumes: `EventLog`, `match_banner`, `wish_pool` (Task 2); calendar part `announcements_error` (Task 3).
- Produces:
  - `TIMELINE_BACK = timedelta(days=21)`, `ENDING_LIST = timedelta(days=3)`, `ENDING_LIST_MAX = 5`
  - `def timeline_rows(log_rows: list[EventLog], calendar: dict, done: set[int], banners: list[GameBanner], items: dict[int, dict], pulls: dict[str, dict], now: datetime) -> list[dict]` — each row `{key, kind, name, start, end, image, description, calendar_id, rewards, primogems, finished, done, ending_soon, items, pulls}`; `items` is `{"featured_5": [item], "featured_4": [item]}` or `None`.
  - `def ending_soon_list(rows: list[dict], now: datetime) -> list[dict]` — `[{key, kind, name, end}]`.
  - `def history_items(session) -> dict[int, dict]` (rename of today's private `_items`, now public).
  - `/api/events` payload adds `"timeline"`, `"ending_soon"`, `"announcements_error"`.
  - Rows carry `kind: "event" | "wish"` and `pool` (from the stored `wish:<pool>` kind, Task 2; `null` for events).

- [ ] **Step 1: Write the failing view tests** — append to `backend/tests/test_events_view.py` (and add `EventLog` to its model import, `timeline_rows, ending_soon_list, history_items` to the view import):

```python
def log(key, name, start, end, kind="event", calendar_id=None, image=None):
    return EventLog(key=key, kind=kind, name=name, start=start, end=end, image=image, description="Text",
                    calendar_id=calendar_id, first_seen=NOW, last_seen=NOW)


def test_timeline_window_calendar_override_and_done():
    rows = [log("ann:1", "Long", "2026-11-01T00:00:00Z", "2026-12-30T00:00:00Z", calendar_id=1),
            log("ann:2", "Old", "2026-10-01T00:00:00Z", "2026-10-20T00:00:00Z"),          # ended > 21 days ago
            log("ann:3", "Recent", "2026-11-01T00:00:00Z", "2026-11-10T00:00:00Z"),       # ended 11 days ago
            log("ann:4", "Ticked", "2026-11-10T00:00:00Z", "2026-11-21T20:00:00Z", calendar_id=2)]
    out = timeline_rows(rows, CAL, {2}, [], {}, {}, NOW)
    by = {r["key"]: r for r in out}
    assert set(by) == {"ann:1", "ann:3", "ann:4"}
    assert by["ann:1"]["end"] == "2026-11-30T04:00:00Z"                 # calendar's end wins
    assert by["ann:1"]["primogems"] == 420 and by["ann:1"]["done"] is False
    assert by["ann:4"]["done"] is True and by["ann:4"]["ending_soon"] is False   # done rows never warn
    assert by["ann:3"]["rewards"] == [] and by["ann:3"]["calendar_id"] is None
    # starts after the calendar override: ann:3 Nov 1; ann:4 and ann:1 both Nov 10 (calendar), ann:4 ends first
    assert [r["key"] for r in out] == ["ann:3", "ann:4", "ann:1"]


def test_timeline_wish_items_and_pulls(session_factory):
    seed_game(session_factory)
    b = GameBanner(key="character|2026-11-21 18:00:00|0", pool="character", name="B", short_name="B",
                   start="2026-11-21 18:00:00", end="2026-12-12 14:59:00", timezone_dependent=True,
                   timezone_dependent_end=False, order=0, featured_5=[10000089], featured_4=[10000032], version="9.9")
    with session_factory() as s:
        items = history_items(s)
    rows = [log("ann:7", "Wish A", "2026-11-21T10:00:00Z", "2026-12-12T06:59:00Z", kind="wish:character"),
            log("ann:8", "Wish B", "2026-12-20T10:00:00Z", "2027-01-12T06:59:00Z", kind="wish:character")]
    out = {r["key"]: r for r in timeline_rows(rows, CAL, set(), [b], items, {b.key: {"pulls": 3, "fives": [], "fours": []}}, NOW)}
    assert out["ann:7"]["kind"] == "wish" and out["ann:7"]["pool"] == "character"
    assert out["ann:7"]["items"]["featured_5"][0]["name"] == "Furina"
    assert out["ann:7"]["pulls"]["pulls"] == 3 and out["ann:7"]["done"] is False
    assert out["ann:8"]["items"] is None and out["ann:8"]["pulls"] is None


def test_ending_soon_list():
    rows = [{"key": "a", "kind": "event", "name": "A", "end": "2026-11-22T00:00:00Z", "done": False},
            {"key": "b", "kind": "event", "name": "B", "end": "2026-11-22T00:00:00Z", "done": True},
            {"key": "c", "kind": "wish", "name": "C", "end": "2026-11-21T18:00:00Z", "done": False},
            {"key": "d", "kind": "event", "name": "D", "end": "2026-11-29T00:00:00Z", "done": False},
            {"key": "e", "kind": "event", "name": "E", "end": "2026-11-20T00:00:00Z", "done": False}]
    assert [r["key"] for r in ending_soon_list(rows, NOW)] == ["c", "a"]
    assert set(ending_soon_list(rows, NOW)[0]) == {"key", "kind", "name", "end"}
```

(`CAL` and `NOW` are the module's existing constants: `NOW` is 2026-11-21 12:00; every `CAL` event starts `2026-11-10T04:00:00Z`; event 1 ends `2026-11-30T04:00:00Z` with 420 primos; event 2 ends `2026-11-22T04:00:00Z` with 60 primos.)

Append to `backend/tests/test_api_events.py`:

```python
def test_events_payload_has_timeline_and_feed_error(paths):
    sf = sf_for(paths)
    now = utcnow()
    with sf.begin() as s:
        s.add(HoyolabSnapshot(part="calendar", data={"banners": [], "events": [], "challenges": []}, fetched_at=now))
        s.add(EventLog(key="ann:1", kind="event", name="Fest", start=iso(now - timedelta(days=1)),
                       end=iso(now + timedelta(hours=10)), image=None, description="", calendar_id=None,
                       first_seen=now, last_seen=now))
        s.add(SyncRun(trigger="manual", started_at=now, finished_at=now,
                      parts={"calendar": {"ok": True, "count": 0, "announcements_error": "AnnouncementError: x"}}))
    with make_client(paths) as client:
        body = client.get("/api/events").json()
    assert [r["key"] for r in body["timeline"]] == ["ann:1"]
    assert body["ending_soon"] == [{"key": "ann:1", "kind": "event", "name": "Fest", "end": body["timeline"][0]["end"]}]
    assert body["announcements_error"] == "AnnouncementError: x"
    assert "banners" in body and "events" in body                 # Dashboard fields kept
```

(`SyncRun` columns are `id`, `started_at`, `finished_at`, `trigger`, `parts`; nothing else is required.)

- [ ] **Step 2: Run to verify failure**

Run: `<python> -m pytest tests/test_events_view.py tests/test_api_events.py tests/-q`
Expected: FAIL (`ImportError: cannot import name 'timeline_rows'`).

- [ ] **Step 3: Implement the view** — in `backend/app/events/view.py`: rename `_items` to `history_items` (update its one caller in `banner_history`), import `EventLog` and `from app.events.log import match_banner`, and add:

```python
TIMELINE_BACK = timedelta(days=21)
ENDING_LIST = timedelta(days=3)
ENDING_LIST_MAX = 5


def _featured(b: GameBanner, items: dict[int, dict]) -> dict:
    def item(i: int) -> dict:
        return items.get(i, {"id": i, "name": f"Item {i}", "icon": None, "rarity": 0})
    return {"featured_5": [item(i) for i in b.featured_5 or []], "featured_4": [item(i) for i in b.featured_4 or []]}


def timeline_rows(log_rows: list[EventLog], calendar: dict, done: set[int], banners: list[GameBanner],
                  items: dict[int, dict], pulls: dict[str, dict], now: datetime) -> list[dict]:
    cal = {e["id"]: e for e in calendar.get("events", [])}
    cutoff = now - TIMELINE_BACK
    out = []
    for r in log_rows:
        c = cal.get(r.calendar_id) if r.calendar_id is not None else None
        start = (c or {}).get("start") or r.start
        end = (c or {}).get("end") or r.end
        end_dt = parse_iso(end)
        if end_dt is not None and end_dt < cutoff:
            continue
        wish = r.kind.startswith("wish")
        pool = r.kind.split(":", 1)[1] if wish and ":" in r.kind else None
        finished = bool((c or {}).get("finished", False))
        row = {"key": r.key, "kind": "wish" if wish else "event", "pool": pool, "name": r.name,
               "start": start, "end": end, "image": r.image, "description": r.description,
               "calendar_id": r.calendar_id if c is not None else None,
               "rewards": (c or {}).get("rewards", []), "primogems": primogems((c or {}).get("rewards", [])),
               "finished": finished, "done": (not wish) and c is not None and (finished or c["id"] in done),
               "ending_soon": False, "items": None, "pulls": None}
        row["ending_soon"] = (not row["done"]) and end_dt is not None and now < end_dt <= now + ENDING_SOON
        if wish and pool is not None:
            b = match_banner(pool, start, banners)
            if b is not None:
                row["items"], row["pulls"] = _featured(b, items), pulls.get(b.key)
        out.append(row)
    far = "9999"
    out.sort(key=lambda r: (r["start"] or "", r["end"] or far, r["name"]))
    return out


def ending_soon_list(rows: list[dict], now: datetime) -> list[dict]:
    soon = [r for r in rows if not r["done"] and (e := parse_iso(r.get("end"))) is not None and now < e <= now + ENDING_LIST]
    soon.sort(key=lambda r: r["end"])
    return [{"key": r["key"], "kind": r["kind"], "name": r["name"], "end": r["end"]} for r in soon[:ENDING_LIST_MAX]]
```

`row["calendar_id"]` is the calendar event id only while that event is still in the calendar snapshot (so the Done button only appears when the toggle can work). Rewrite `banner_history`'s internal `item()` to use `_featured` where it builds `featured_5`/`featured_4`, keeping behaviour.

- [ ] **Step 4: Payload** — in `backend/app/api/events.py` `events_payload`, after `rows = event_rows(...)`:

```python
    log_rows = list(s.scalars(select(EventLog)))
    banners = list(s.scalars(select(GameBanner)))
    timeline = timeline_rows(log_rows, calendar, done, banners, history_items(s), pulls, now)
```

and add to the returned dict:

```python
            "timeline": timeline, "ending_soon": ending_soon_list(timeline, now),
            "announcements_error": announcements_error(s),
```

with this helper next to `last_error`:

```python
def announcements_error(session: Session) -> str | None:
    run = session.scalars(select(SyncRun).where(SyncRun.finished_at.is_not(None), SyncRun.trigger != "gaps")
                          .order_by(SyncRun.id.desc()).limit(1)).first()
    return ((run.parts or {}).get("calendar") or {}).get("announcements_error") if run is not None else None
```

Reuse the existing `banner_windows(list(s.scalars(select(GameBanner))), offset)` input: pass the same `banners` list to it instead of a second query. Imports: `EventLog` from models; `timeline_rows, ending_soon_list, history_items` from the view.

- [ ] **Step 5: Dev seed** — in `backend/app/devseed.py`, in the same `with sf.begin() as s:` block that adds the calendar snapshot, after it:

```python
        art = "https://sdk.hoyoverse.com/upload/ann/demo/{}.png"
        demo_log = [
            ("ann:9001", "event", "Fishing Festival", now - timedelta(days=6), now + timedelta(days=9), "fish", 9001),
            ("ann:9002", "event", "Quick Trial", now - timedelta(days=2), now + timedelta(hours=5), "trial", 9002),
            ("cal:9003", "event", "Photo Event", now - timedelta(days=4), now + timedelta(days=2), None, 9003),
            ("ann:9100", "wish:character", "Tide of Furina", b_start, b_end, "wish", None),
            ("ann:9101", "wish:character", "Next Phase Wish", b_end + timedelta(minutes=1), b_end + timedelta(days=21), "next", None),
            ("ann:9102", "event", "Ended Carnival", now - timedelta(days=20), now - timedelta(days=5), "carnival", None),
        ]
        for key, kind, name, start_at, end_at, img, cal_id in demo_log:
            s.add(EventLog(key=key, kind=kind, name=name, start=iso(start_at), end=iso(end_at),
                           image=art.format(img) if img else None,
                           description=f"Demo text for {name}.\n\nSecond paragraph.", calendar_id=cal_id,
                           first_seen=now, last_seen=now))
```

Give events 9001–9003 in the demo calendar a `start` of `iso(now - timedelta(days=6))`, `iso(now - timedelta(days=2))`, `iso(now - timedelta(days=4))` instead of `None`, so bars have a start. Import `EventLog`. Add to `backend/tests/test_devseed.py`'s existing seeding test: `assert s.query(EventLog).count() == 6`.

- [ ] **Step 6: Run to verify pass**

Run: `<python> -m pytest -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add backend/app/events/view.py backend/app/api/events.py backend/app/devseed.py backend/tests/test_events_view.py backend/tests/test_api_events.py backend/tests/test_devseed.py
git commit -m "feat(events): merged timeline, ending-soon list and feed error in the events payload"
```

---

### Task 5: Banner history by version and phase

**Files:**
- Modify: `backend/app/events/view.py` (`banner_history` replaced)
- Modify: `backend/app/api/events.py` (`get_banner_history` drops `pool`)
- Test: `backend/tests/test_events_view.py` (replace `test_banner_history_filter_search_page`), `backend/tests/test_api_events.py` (replace `test_banner_history_endpoint`, `test_banner_history_wildcards_are_literal`)

**Interfaces:**
- Consumes: `history_items`, `_featured` (Task 4); `EventLog`, `match_banner` (Task 2).
- Produces: `HISTORY_PAGE = 6`; `def banner_history(session, q: str, page: int, pulls: dict[str, dict]) -> dict` returning

```
{"total_versions": int, "page": int, "page_size": 6,
 "versions": [{"version": str, "phases": [{"start": str, "end": str, "upcoming": bool, "image": str | None,
               "banners": [{"key", "pool", "name", "featured_5", "featured_4", "pulls"}]}]}]}
```

Phases within a version are ordered oldest first (so "Phase 1" is first); versions newest first.

- [ ] **Step 1: Write the failing tests** — replace `test_banner_history_filter_search_page` in `backend/tests/test_events_view.py`:

```python
def gb(pool, start, version, name="B", f5=(), f4=(), order=0):
    return GameBanner(key=f"{pool}|{start}|{order}", pool=pool, name=name, short_name=name, start=start,
                      end=start, timezone_dependent=True, timezone_dependent_end=False, order=order,
                      featured_5=list(f5), featured_4=list(f4), version=version)


def test_banner_history_versions_phases_search_and_paging(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        s.add(gb("character", "2026-11-04 06:00:00", "9.9", "Tide of Furina", [10000089], [10000032]))
        s.add(gb("weapon", "2026-11-04 06:00:00", "9.9", "Epitome Invocation"))
        s.add(gb("chronicled", "2026-11-04 06:00:00", "9.9", "Chronicle"))
        s.add(gb("character", "2026-10-14 18:00:00", "9.8", "Older"))
        s.add(gb("standard", "2000-01-01 00:00:00", None, "Wanderlust"))
        s.add(gb("standard", "2000-01-02 00:00:00", "9.9", "Wanderlust 9.9"))   # standard pool never shown
        for i in range(8):
            s.add(gb("character", f"2020-{i + 1:02d}-01 06:00:00", f"1.{i}", f"Old {i}"))
    with session_factory() as s:
        page1 = banner_history(s, "", 1, {"character|2026-11-04 06:00:00|0": {"pulls": 7, "fives": ["Furina"], "fours": []}})
        page2 = banner_history(s, "", 2, {})
        found = banner_history(s, "furina", 1, {})
    assert page1["total_versions"] == 10 and page1["page_size"] == 6
    assert [v["version"] for v in page1["versions"]] == ["9.9", "9.8", "1.7", "1.6", "1.5", "1.4"]
    assert len(page2["versions"]) == 4
    top = page1["versions"][0]["phases"][0]
    assert [b["pool"] for b in top["banners"]] == ["character", "weapon", "chronicled"]
    assert top["banners"][0]["featured_5"][0]["name"] == "Furina" and top["banners"][0]["pulls"]["pulls"] == 7
    assert top["upcoming"] is False
    assert [v["version"] for v in found["versions"]] == ["9.9"]
    assert [b["name"] for b in found["versions"][0]["phases"][0]["banners"]] == ["Tide of Furina"]


def test_banner_history_upcoming_phase_from_log(session_factory):
    seed_game(session_factory)
    with session_factory.begin() as s:
        s.add(gb("character", "2026-11-04 06:00:00", "9.9", "Tide of Furina"))
        s.add(EventLog(key="ann:5", kind="wish:character", name="Next Wish", start="2026-11-24T10:00:00Z",
                       end="2026-12-15T06:59:00Z", image="https://sdk.hoyoverse.com/upload/ann/test/n.png",
                       description="", calendar_id=None, first_seen=NOW, last_seen=NOW))
        s.add(EventLog(key="ann:6", kind="wish:character", name="Matched Wish", start="2026-11-03T22:00:00Z",
                       end="2026-11-24T06:59:00Z", image=None, description="", calendar_id=None,
                       first_seen=NOW, last_seen=NOW))
    with session_factory() as s:
        out = banner_history(s, "", 1, {})
    phases = out["versions"][0]["phases"]
    assert [p["upcoming"] for p in phases] == [False, True]
    assert phases[1]["image"].endswith("n.png") and phases[1]["banners"][0]["name"] == "Next Wish"
    assert phases[1]["banners"][0]["featured_5"] == []
```

Replace the two history tests in `backend/tests/test_api_events.py`:

```python
def test_banner_history_endpoint(paths):
    sf_for(paths)
    with make_client(paths) as client:
        body = client.get("/api/banners/history?q=&page=1").json()
        assert body == {"total_versions": 0, "page": 1, "page_size": 6, "versions": []}
        assert client.get("/api/banners/history?page=0").status_code == 422


def test_banner_history_wildcards_are_literal(paths):
    sf = sf_for(paths)
    with sf.begin() as s:
        s.add(GameBanner(key="character|2024-01-01 00:00:00|0", pool="character", name="Plain Banner",
                         short_name="Plain", start="2024-01-01 00:00:00", end="2024-01-20 00:00:00",
                         timezone_dependent=False, timezone_dependent_end=False, order=0,
                         featured_5=[], featured_4=[], version="1.0"))
    with make_client(paths) as client:
        assert client.get("/api/banners/history?q=%25").json()["total_versions"] == 0
        assert client.get("/api/banners/history?q=_").json()["total_versions"] == 0
        assert client.get("/api/banners/history?q=plain").json()["total_versions"] == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `<python> -m pytest tests/test_events_view.py tests/test_api_events.py -q`
Expected: FAIL (signature mismatch / old response shape).

- [ ] **Step 3: Implement** — replace `banner_history` in `backend/app/events/view.py` (remove `PAGE_SIZE` if unused afterwards; keep `func`/`or_` imports only if still used):

```python
HISTORY_PAGE = 6
POOL_ORDER = {"character": 0, "weapon": 1, "chronicled": 2}


def _banner_dict(b: GameBanner, items: dict[int, dict], pulls: dict[str, dict]) -> dict:
    return {"key": b.key, "pool": b.pool, "name": b.name, **_featured(b, items), "pulls": pulls.get(b.key)}


def banner_history(session: Session, q: str, page: int, pulls: dict[str, dict]) -> dict:
    items = history_items(session)
    banners = [b for b in session.scalars(select(GameBanner)) if b.version and b.pool in POOL_ORDER]  # no standard/beginner
    text = q.strip().lower()

    def matches(b: GameBanner) -> bool:
        if not text:
            return True
        names = [items.get(i, {}).get("name", "") for i in (b.featured_5 or []) + (b.featured_4 or [])]
        return any(text in n.lower() for n in [b.name, b.short_name, *names])

    phases: dict[tuple[str, str], list[GameBanner]] = {}
    for b in banners:
        phases.setdefault((b.version, b.start[:10]), []).append(b)
    versions: dict[str, list[dict]] = {}
    for (version, _day), group in phases.items():
        shown = [b for b in group if matches(b)]
        if not shown:
            continue
        shown.sort(key=lambda b: (POOL_ORDER.get(b.pool, 9), b.order))
        versions.setdefault(version, []).append({
            "start": min(b.start for b in group), "end": max(b.end for b in group), "upcoming": False, "image": None,
            "banners": [_banner_dict(b, items, pulls) for b in shown]})

    if banners:
        newest = max(banners, key=lambda b: b.start)
        newest_at = datetime.fromisoformat(newest.start.replace(" ", "T"))
        upcoming: dict[str, list[EventLog]] = {}
        for r in session.scalars(select(EventLog).where(EventLog.kind.like("wish%"))):
            pool = r.kind.split(":", 1)[1] if ":" in r.kind else "character"
            start = parse_iso(r.start)
            if start is None or start <= newest_at or match_banner(pool, r.start, banners) is not None:
                continue
            if text and text not in r.name.lower():
                continue
            upcoming.setdefault(r.start[:10], []).append(r)
        for _day, group in sorted(upcoming.items()):
            versions.setdefault(newest.version, []).append({
                "start": min(r.start for r in group), "end": max(r.end or r.start for r in group), "upcoming": True,
                "image": next((r.image for r in group if r.image), None),
                "banners": [{"key": r.key, "pool": r.kind.split(":", 1)[-1], "name": r.name, "featured_5": [],
                             "featured_4": [], "pulls": None} for r in group]})

    ordered = sorted(versions.items(), key=lambda kv: max(p["start"] for p in kv[1]), reverse=True)
    page = max(1, page)
    chunk = ordered[(page - 1) * HISTORY_PAGE: page * HISTORY_PAGE]
    return {"total_versions": len(ordered), "page": page, "page_size": HISTORY_PAGE,
            "versions": [{"version": v, "phases": sorted(ps, key=lambda p: p["start"])} for v, ps in chunk]}
```

Note: paimon.moe `start` values are `"YYYY-MM-DD HH:MM:SS"` and upcoming starts are `"...Z"` ISO strings; both sort correctly as strings for the phase order within a version, because they share the `YYYY-MM-DD` prefix. `parse_iso` already strips a trailing `Z`.

Endpoint — replace `get_banner_history` in `backend/app/api/events.py`:

```python
@router.get("/banners/history")
def get_banner_history(q: str = Query("", max_length=100), page: int = Query(1, ge=1),
                       ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        pulls = pulls_by_banner(summarize(s, utcnow(), offset_hours(region(ctx))))
        return banner_history(s, q, page, pulls)
```

Remove the now-unused `Literal` import if nothing else uses it.

- [ ] **Step 4: Run to verify pass**

Run: `<python> -m pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add backend/app/events/view.py backend/app/api/events.py backend/tests/test_events_view.py backend/tests/test_api_events.py
git commit -m "feat(events): banner history grouped by version and phase"
```

---

### Task 6: Frontend types, API and timeline maths

**Files:**
- Modify: `frontend/src/lib/types.ts`, `frontend/src/lib/api.ts`
- Create: `frontend/src/lib/timeline.ts`, `frontend/src/lib/timeline.test.ts`

**Interfaces:**
- Consumes: `/api/events` fields from Task 4, `/api/banners/history` from Task 5.
- Produces (types.ts):

```ts
export interface HistoryItem { id: number; name: string; icon: string | null; rarity: number }
export interface TimelineRow {
	key: string; kind: 'event' | 'wish'; pool: 'character' | 'weapon' | 'chronicled' | null; name: string;
	start: string | null; end: string | null; image: string | null; description: string; calendar_id: number | null;
	rewards: Reward[]; primogems: number; finished: boolean; done: boolean; ending_soon: boolean;
	items: { featured_5: HistoryItem[]; featured_4: HistoryItem[] } | null; pulls: BannerPulls | null;
}
export interface EndingSoon { key: string; kind: 'event' | 'wish'; name: string; end: string }
// EventsResponse gains: timeline: TimelineRow[]; ending_soon: EndingSoon[]; announcements_error: string | null;
export interface HistoryBanner {
	key: string; pool: 'character' | 'weapon' | 'chronicled'; name: string;
	featured_5: HistoryItem[]; featured_4: HistoryItem[]; pulls: BannerPulls | null;
}
export interface HistoryPhase { start: string; end: string; upcoming: boolean; image: string | null; banners: HistoryBanner[] }
export interface HistoryVersion { version: string; phases: HistoryPhase[] }
export interface BannerHistoryPage { total_versions: number; page: number; page_size: number; versions: HistoryVersion[] }
```

- `api.bannerHistory(q: string, page: number): Promise<BannerHistoryPage>`
- timeline.ts:

```ts
export const DAY = 86_400_000;
export const BACK_DAYS = 21;
export const MIN_AHEAD_DAYS = 14;
export const MAX_AHEAD_DAYS = 60;
export interface Axis { start: number; end: number; days: number }
export interface Placed<T> { row: T; lane: number; left: number; width: number; clampedEnd: boolean; from: number; to: number }
export function dayStart(ms: number): number;   // local midnight
export function buildAxis(rows: { start: string | null; end: string | null }[], now: number): Axis;
export function placeBars<T extends { start: string | null; end: string | null }>(rows: T[], axis: Axis): Placed<T>[];
export function todayOffset(axis: Axis, now: number): number;   // 0..1
export function dayTicks(axis: Axis): { ms: number; label: string; monthStart: boolean }[];
```

- [ ] **Step 1: Write the failing tests** — `frontend/src/lib/timeline.test.ts`

```ts
import { describe, expect, it } from 'vitest';
import { buildAxis, DAY, dayStart, dayTicks, placeBars, todayOffset } from './timeline';

const now = new Date(2026, 10, 23, 12, 0, 0).getTime();
const iso = (days: number) => new Date(now + days * DAY).toISOString();

describe('buildAxis', () => {
	it('runs from 21 days back to at least 14 days ahead', () => {
		const a = buildAxis([], now);
		expect(a.start).toBe(dayStart(now) - 21 * DAY);
		expect(a.days).toBe(21 + 14 + 1);
	});
	it('extends to the latest end but clamps far ends to 60 days', () => {
		expect(buildAxis([{ start: iso(-1), end: iso(30) }], now).days).toBe(21 + 31 + 1);
		expect(buildAxis([{ start: iso(-1), end: iso(300) }], now).days).toBe(21 + 60 + 1);
	});
});

describe('placeBars', () => {
	const axis = buildAxis([], now);
	it('packs non-overlapping bars into one lane and overlapping ones into new lanes', () => {
		const rows = [
			{ id: 'a', start: iso(-10), end: iso(-5) },
			{ id: 'b', start: iso(-4), end: iso(2) },
			{ id: 'c', start: iso(-3), end: iso(1) }
		];
		const placed = placeBars(rows, axis);
		expect(placed.map((p) => [p.row.id, p.lane])).toEqual([['a', 0], ['b', 0], ['c', 1]]);
	});
	it('clamps far ends and marks them', () => {
		const [p] = placeBars([{ start: iso(-1), end: iso(300) }], axis);
		expect(p.clampedEnd).toBe(true);
		expect(p.left + p.width).toBeCloseTo(1, 5);
	});
	it('missing start uses axis start', () => {
		const [p] = placeBars([{ start: null, end: iso(3) }], axis);
		expect(p.left).toBe(0);
		expect(p.width).toBeGreaterThan(0);
	});
	it('drops rows without an end and rows wholly before the axis', () => {
		expect(placeBars([{ start: iso(-1), end: null }, { start: iso(-60), end: iso(-30) }], axis)).toEqual([]);
	});
});

describe('todayOffset and ticks', () => {
	it('puts today 21.5 days into a 36-day axis', () => {
		const a = buildAxis([], now);
		expect(todayOffset(a, now)).toBeCloseTo(21.5 / 36, 5);
	});
	it('labels month starts with the month name', () => {
		const ticks = dayTicks(buildAxis([], now));
		expect(ticks).toHaveLength(36);
		const dec = ticks.find((t) => t.monthStart);
		expect(dec?.label).toBe('Dec');
	});
});
```

- [ ] **Step 2: Run to verify failure**

Run (from `frontend/`): `npx vitest run src/lib/timeline.test.ts`
Expected: FAIL (cannot resolve `./timeline`).

- [ ] **Step 3: Implement** — `frontend/src/lib/timeline.ts`

```ts
/** Pure maths for the Events timeline: a day axis, bar positions (0..1 of the axis) and lane packing. */
export const DAY = 86_400_000;
export const BACK_DAYS = 21;
export const MIN_AHEAD_DAYS = 14;
export const MAX_AHEAD_DAYS = 60;

export interface Axis { start: number; end: number; days: number }
export interface Placed<T> { row: T; lane: number; left: number; width: number; clampedEnd: boolean; from: number; to: number }

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];

export function dayStart(ms: number): number {
	const d = new Date(ms);
	return new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
}

function ms(s: string | null): number | null {
	if (!s) return null;
	const v = Date.parse(s);
	return Number.isNaN(v) ? null : v;
}

export function buildAxis(rows: { start: string | null; end: string | null }[], now: number): Axis {
	const today = dayStart(now);
	const start = today - BACK_DAYS * DAY;
	const min = today + (MIN_AHEAD_DAYS + 1) * DAY;
	const max = today + (MAX_AHEAD_DAYS + 1) * DAY;
	let end = min;
	for (const r of rows) {
		const e = ms(r.end);
		if (e !== null) end = Math.max(end, dayStart(e) + DAY);
	}
	end = Math.min(end, max);
	return { start, end, days: Math.round((end - start) / DAY) };
}

export function placeBars<T extends { start: string | null; end: string | null }>(rows: T[], axis: Axis): Placed<T>[] {
	const span = axis.end - axis.start;
	const items = rows
		.map((row) => {
			const e = ms(row.end);
			if (e === null || e <= axis.start) return null;
			const s = Math.max(ms(row.start) ?? axis.start, axis.start);
			const clampedEnd = e > axis.end;
			const to = Math.min(e, axis.end);
			return { row, from: s, to, clampedEnd };
		})
		.filter((x): x is { row: T; from: number; to: number; clampedEnd: boolean } => x !== null && x.to > x.from)
		.sort((a, b) => a.from - b.from || a.to - b.to);
	const laneEnds: number[] = [];
	return items.map((it) => {
		let lane = laneEnds.findIndex((end) => end <= it.from);
		if (lane === -1) {
			lane = laneEnds.length;
			laneEnds.push(it.to);
		} else laneEnds[lane] = it.to;
		return { ...it, lane, left: (it.from - axis.start) / span, width: (it.to - it.from) / span };
	});
}

export function todayOffset(axis: Axis, now: number): number {
	return Math.min(1, Math.max(0, (now - axis.start) / (axis.end - axis.start)));
}

export function dayTicks(axis: Axis): { ms: number; label: string; monthStart: boolean }[] {
	const out = [];
	for (let i = 0; i < axis.days; i++) {
		const d = new Date(axis.start + i * DAY + DAY / 2);
		const at = dayStart(d.getTime());
		const monthStart = d.getDate() === 1;
		out.push({ ms: at, label: monthStart ? MONTHS[d.getMonth()] : String(d.getDate()), monthStart });
	}
	return out;
}
```

Note: the "today 21.5 / 36" test holds because `now` is local noon; `dayTicks` uses midday of each day so daylight-saving shifts never skip or repeat a date.

- [ ] **Step 4: Types and API** — edit `frontend/src/lib/types.ts`: add `TimelineRow`, `EndingSoon`, `HistoryPhase`, `HistoryVersion`; replace `HistoryBanner` and `BannerHistoryPage` with the definitions above; add `timeline: TimelineRow[]; ending_soon: EndingSoon[]; announcements_error: string | null;` to `EventsResponse`. Edit `frontend/src/lib/api.ts`:

```ts
	bannerHistory: (q: string, page: number) =>
		request<BannerHistoryPage>('GET', `/banners/history?q=${encodeURIComponent(q)}&page=${page}`)
```

- [ ] **Step 5: Run to verify pass**

Run: `npx vitest run src/lib/timeline.test.ts` → PASS. `npm run check` will still report errors in `routes/events/+page.svelte` (old history shape); those are fixed in Task 7/8 — note them, do not patch the old page.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/timeline.ts frontend/src/lib/timeline.test.ts frontend/src/lib/types.ts frontend/src/lib/api.ts
git commit -m "feat(events): timeline maths and new event/history types"
```

---

### Task 7: Events page — timeline, popup, Timers, Done checklist

**Files:**
- Create: `frontend/src/lib/EventTimeline.svelte`, `frontend/src/lib/EventModal.svelte`
- Rewrite: `frontend/src/routes/events/+page.svelte` (history section becomes `<BannerHistory />` in Task 8; in this task leave a `<section class="panel" data-testid="banner-history"></section>` placeholder)
- Test: `frontend/e2e/events.spec.ts`

**Interfaces:**
- Consumes: `TimelineRow`, `EndingSoon`, `EventsResponse` (Task 6); `buildAxis`, `placeBars`, `todayOffset`, `dayTicks`, `DAY` (Task 6); existing `Countdown`, `imgSrc`, `setDone`, `leftTotals`, `primosLine`, `timeAgo`, `api.setEventDone`.
- Produces:
  - `EventTimeline.svelte` props `{ rows: TimelineRow[]; now: number; onopen: (key: string) => void }`; each bar `data-testid="bar-<key>"`, class `wish` / `done` / `noart`; today line `data-testid="today-line"`.
  - `EventModal.svelte` props `{ row: TimelineRow; now: number; onclose: () => void; ontoggle: (row: TimelineRow) => void }`; dialog `data-testid="event-modal"`.

- [ ] **Step 1: Write the failing e2e test** — replace the first test in `frontend/e2e/events.spec.ts`:

```ts
test('timeline bars open a popup that ticks Done, shown on the Dashboard', async ({ page }) => {
	await page.goto('/events');
	await expect(page.getByTestId('today-line')).toBeVisible();
	await expect(page.getByTestId('bar-ann:9001')).not.toHaveClass(/noart/);
	await expect(page.getByTestId('bar-cal:9003')).toHaveClass(/noart/);
	await expect(page.getByTestId('bar-ann:9100')).toHaveClass(/wish/);
	await expect(page.getByTestId('bar-ann:9102')).toHaveClass(/done|ended/);

	await page.getByTestId('bar-ann:9002').click();
	const modal = page.getByTestId('event-modal');
	await expect(modal).toBeVisible();
	await expect(modal).toContainText('Quick Trial');
	await expect(modal).toContainText('60 primos');
	await modal.getByRole('button', { name: 'Mark done' }).click();
	await expect(page.getByTestId('event-9002')).toHaveClass(/done/);
	await expect(page.getByTestId('events-left')).toContainText('2 events left · 420 primos unclaimed');
	await page.keyboard.press('Escape');
	await expect(modal).toBeHidden();
	await expect(page.getByTestId('bar-ann:9002')).toBeFocused();

	await page.goto('/');
	await expect(page.getByTestId('dash-event-9002')).toHaveClass(/done/);
	await expect(page.getByTestId('dash-banners')).toContainText('Tide of Furina');
	await page.goto('/events');
	await page.getByTestId('event-9002').getByRole('checkbox').uncheck();
	await expect(page.getByTestId('event-9002')).not.toHaveClass(/done/);
});

test('wish popup shows featured items; timers list resets and ending soon', async ({ page }) => {
	await page.goto('/events');
	const timers = page.getByTestId('timers');
	await expect(timers).toContainText('Spiral Abyss');
	await expect(timers.getByTestId('ending-soon')).toContainText('Quick Trial');
	await page.getByTestId('bar-ann:9100').click();
	const modal = page.getByTestId('event-modal');
	await expect(modal.getByRole('img', { name: 'Furina' })).toBeVisible();
	await expect(modal.getByRole('button', { name: 'Mark done' })).toHaveCount(0);
	await modal.getByRole('button', { name: 'Close' }).click();
	await expect(modal).toBeHidden();
});
```

(The seeded "Tide of Furina" `game_banner` row is matched to wish `ann:9100` because the seed uses the banner's own start; check `devseed.py` keeps `b_start` in UTC so `match_banner` finds it within a day.)

- [ ] **Step 2: Run to verify failure**

Run: `PYTHON=<python> npx playwright test e2e/events.spec.ts`
Expected: FAIL (no `today-line`).

- [ ] **Step 3: `EventTimeline.svelte`**

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { timeLeft } from './events';
	import { imgSrc } from './img';
	import { buildAxis, dayTicks, placeBars, todayOffset } from './timeline';
	import type { TimelineRow } from './types';

	let { rows, now, onopen }: { rows: TimelineRow[]; now: number; onopen: (key: string) => void } = $props();

	const DAY_PX = 34;
	const LANE_PX = 36;
	const axis = $derived(buildAxis(rows, now));
	const placed = $derived(placeBars(rows, axis));
	const ticks = $derived(dayTicks(axis));
	const lanes = $derived(Math.max(1, ...placed.map((p) => p.lane + 1)));
	const width = $derived(axis.days * DAY_PX);
	const today = $derived(todayOffset(axis, now));
	let scroller: HTMLDivElement;

	onMount(() => {
		scroller.scrollLeft = Math.max(0, today * width - scroller.clientWidth / 3);
	});

	function label(p: (typeof placed)[number]): string {
		const s = p.row.start ? new Date(p.row.start).toLocaleString() : 'already running';
		const e = p.row.end ? new Date(p.row.end).toLocaleString() : '?';
		return `${p.row.name}, ${s} to ${e}`;
	}

	function right(p: (typeof placed)[number]): string {
		if (p.row.start && Date.parse(p.row.start) > now) return `starts in ${timeLeft(p.row.start, now)}`;
		return timeLeft(p.row.end, now);
	}

	function move(e: KeyboardEvent, i: number) {
		if (e.key !== 'ArrowRight' && e.key !== 'ArrowLeft') return;
		e.preventDefault();
		const next = scroller.querySelectorAll<HTMLButtonElement>('button.bar')[i + (e.key === 'ArrowRight' ? 1 : -1)];
		next?.focus();
	}
</script>

<div class="scroller" bind:this={scroller}>
	<div class="track" style="width:{width}px">
		<div class="days" style="grid-template-columns:repeat({axis.days},{DAY_PX}px)">
			{#each ticks as t (t.ms)}<span class:month={t.monthStart}>{t.label}</span>{/each}
		</div>
		<div class="lanes" style="height:{lanes * LANE_PX}px">
			<div class="today" data-testid="today-line" style="left:{today * 100}%"><span>today</span></div>
			{#each placed as p, i (p.row.key)}
				{@const ended = !!p.row.end && Date.parse(p.row.end) <= now}
				{@const src = imgSrc(p.row.image)}
				<button type="button" class="bar" data-testid="bar-{p.row.key}" aria-label={label(p)}
					class:wish={p.row.kind === 'wish'} class:done={p.row.done} class:ended class:noart={!src}
					style="left:{p.left * 100}%;width:{p.width * 100}%;top:{p.lane * LANE_PX}px;{src ? `background-image:url('${src}')` : ''}"
					onclick={() => onopen(p.row.key)} onkeydown={(e) => move(e, i)}>
					<b>{p.row.name}</b>
					<i class:soon={p.row.ending_soon}>{right(p)}{p.clampedEnd ? ' →' : ''}</i>
				</button>
			{/each}
		</div>
	</div>
</div>

<style>
	.scroller { overflow-x: auto; padding-top: 18px; }
	.track { position: relative; }
	.days { display: grid; font-size: 10px; color: var(--muted); border-bottom: 1px solid var(--line); margin-bottom: 6px; }
	.days span { padding-left: 3px; border-left: 1px solid var(--line); }
	.days span.month { color: var(--text); font-weight: 600; }
	.lanes { position: relative; }
	.today { position: absolute; top: -26px; bottom: 0; width: 2px; background: #e8cf9c; box-shadow: 0 0 8px #e8cf9c; z-index: 3; pointer-events: none; }
	.today span { position: absolute; top: -2px; left: 5px; font-size: 10px; color: #e8cf9c; }
	.bar { position: absolute; height: 30px; border-radius: 7px; border: none; padding: 0; overflow: hidden; cursor: pointer;
		background: linear-gradient(120deg, rgba(120, 130, 180, 0.35), rgba(60, 70, 110, 0.35)) center 30% / cover;
		color: #fff; text-align: left; }
	.bar::after { content: ''; position: absolute; inset: 0; background: linear-gradient(90deg, rgba(7, 10, 20, 0.85), rgba(7, 10, 20, 0.35) 55%, rgba(7, 10, 20, 0.1)); }
	.bar b { position: absolute; left: 8px; top: 7px; z-index: 1; font-size: 12px; white-space: nowrap; text-shadow: 0 1px 2px #000; }
	.bar i { position: absolute; right: 8px; top: 8px; z-index: 1; font-style: normal; font-size: 11px; color: #e8cf9c; text-shadow: 0 1px 2px #000; }
	.bar i.soon { color: var(--warn); }
	.bar.wish { outline: 1px solid rgba(232, 207, 156, 0.6); }
	.bar.done, .bar.ended { filter: grayscale(0.85) brightness(0.6); }
	.bar:focus-visible { outline: 2px solid var(--accent); outline-offset: 2px; }
</style>
```

If the art fails to load the bar keeps its gradient (it is drawn underneath via the shorthand fallback only when `src` is null; a failing remote image is served as a placeholder PNG by the backend, so no client error handling is needed).

- [ ] **Step 4: `EventModal.svelte`**

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import Countdown from './Countdown.svelte';
	import { imgSrc } from './img';
	import type { TimelineRow } from './types';

	let { row, now, onclose, ontoggle }: {
		row: TimelineRow; now: number; onclose: () => void; ontoggle: (row: TimelineRow) => void;
	} = $props();
	let dialog: HTMLDialogElement;
	const hero = $derived(imgSrc(row.image));
	const fmt = (s: string | null) =>
		s ? new Date(s).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '…';

	onMount(() => dialog.showModal());
</script>

<dialog bind:this={dialog} class="modal" data-testid="event-modal" aria-label={row.name}
	onclose={onclose} onclick={(e) => { if (e.target === dialog) dialog.close(); }}>
	<div class="hero" class:noart={!hero} style={hero ? `background-image:url('${hero}')` : ''}>
		<button type="button" class="x" aria-label="Close" onclick={() => dialog.close()}>✕</button>
		<h3>{row.name}</h3>
	</div>
	<div class="body">
		<div class="pills">
			<span class="pill">{fmt(row.start)} → {fmt(row.end)}</span>
			<span class="pill">{#if row.start && Date.parse(row.start) > now}starts in <Countdown at={row.start} {now} />{:else}<Countdown at={row.end} {now} warn={!row.done} />{/if}</span>
			{#if row.primogems > 0}<span class="pill">{row.primogems} primos</span>{/if}
		</div>
		{#if row.rewards.length}
			<h4>Rewards</h4>
			<div class="rewards">
				{#each row.rewards as r, i (i)}
					<div class="reward">{#if imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt={r.name} title={r.name} />{/if}<span>{r.count || ''}</span></div>
				{/each}
			</div>
		{/if}
		{#if row.items}
			<h4>Featured</h4>
			<div class="featured">
				{#each row.items.featured_5 as it (it.id)}{#if imgSrc(it.icon)}<img class="r5" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/if}{/each}
				{#each row.items.featured_4 as it (it.id)}{#if imgSrc(it.icon)}<img class="r4 small" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/if}{/each}
			</div>
			{#if row.pulls}<p class="muted">You pulled {row.pulls.pulls} here{#if row.pulls.fives.length} · got {row.pulls.fives.join(', ')}{/if}</p>{/if}
		{/if}
		{#if row.description}
			<h4>About</h4>
			<div class="desc">{#each row.description.split('\n\n') as p, i (i)}<p>{p}</p>{/each}</div>
		{/if}
		{#if row.kind === 'event' && row.calendar_id !== null}
			<div class="foot">
				{#if row.finished}
					<button type="button" disabled>Completed in game</button>
				{:else}
					<button type="button" class="primary" onclick={() => ontoggle(row)}>{row.done ? 'Undo' : 'Mark done'}</button>
				{/if}
			</div>
		{/if}
	</div>
</dialog>

<style>
	.modal { width: min(460px, calc(100vw - 32px)); padding: 0; border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
		background: var(--glass-bg-strong); backdrop-filter: blur(var(--glass-blur)); color: var(--text); }
	.modal::backdrop { background: rgba(0, 0, 0, 0.55); }
	.hero { position: relative; height: 150px; background: linear-gradient(120deg, rgba(120, 130, 180, 0.4), rgba(60, 70, 110, 0.4)) center / cover; }
	.hero::after { content: ''; position: absolute; inset: 0; background: linear-gradient(180deg, transparent 40%, var(--glass-bg-strong)); }
	.hero h3 { position: absolute; left: 14px; bottom: 8px; margin: 0; z-index: 1; font-size: 18px; text-shadow: 0 1px 3px #000; }
	.x { position: absolute; right: 10px; top: 8px; z-index: 2; width: 28px; height: 28px; border-radius: 50%; border: none; background: rgba(0, 0, 0, 0.5); color: #fff; cursor: pointer; }
	.body { padding: 12px 14px 14px; max-height: 60vh; overflow-y: auto; }
	.pills { display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 8px; }
	.pill { padding: 2px 10px; border-radius: 999px; background: rgba(255, 255, 255, 0.08); font-size: 12px; }
	h4 { margin: 10px 0 6px; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
	.rewards, .featured { display: flex; flex-wrap: wrap; gap: 6px; }
	.reward { width: 42px; text-align: center; font-size: 11px; }
	.reward img, .featured img { width: 40px; height: 40px; border-radius: 6px; }
	.featured img.small { width: 28px; height: 28px; }
	.r5 { background: var(--r5); } .r4 { background: var(--r4); }
	.desc p { margin: 0 0 8px; line-height: 1.5; color: var(--muted); }
	.foot { margin-top: 10px; padding-top: 10px; border-top: 1px solid var(--line); }
</style>
```

Native `<dialog>` returns focus to the element focused before `showModal()` when it closes, so clicking a bar and pressing Esc refocuses that bar.

- [ ] **Step 5: Page** — rewrite `frontend/src/routes/events/+page.svelte`:

```svelte
<script lang="ts">
	import { onMount } from 'svelte';
	import { api, errorMessage } from '$lib/api';
	import Countdown from '$lib/Countdown.svelte';
	import EventModal from '$lib/EventModal.svelte';
	import EventTimeline from '$lib/EventTimeline.svelte';
	import { leftTotals, primosLine, setDone } from '$lib/events';
	import { imgSrc } from '$lib/img';
	import { sync } from '$lib/sync.svelte';
	import { timeAgo } from '$lib/time';
	import type { EventRow, EventsResponse, TimelineRow } from '$lib/types';

	let data = $state<EventsResponse | null>(null);
	let error = $state<string | null>(null);
	let toast = $state<string | null>(null);
	let now = $state(Date.now());
	let openKey = $state<string | null>(null);
	const left = $derived(data ? leftTotals(data.events) : { count: 0, primogems: 0 });
	const openRow = $derived(data?.timeline.find((r) => r.key === openKey) ?? null);

	$effect(() => {
		void sync.version;
		load();
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

	/** Done lives on calendar ids; keep the checklist and every timeline row of that id in step. */
	function applyDone(id: number, done: boolean) {
		if (!data) return;
		data = {
			...data,
			events: setDone(data.events, id, done),
			timeline: data.timeline.map((r) => (r.calendar_id === id && !r.finished ? { ...r, done } : r))
		};
	}

	async function toggle(id: number, done: boolean) {
		applyDone(id, done);
		try {
			await api.setEventDone(id, done);
		} catch (e) {
			applyDone(id, !done);
			toast = `Could not save: ${errorMessage(e)}`;
		}
	}

	const toggleRow = (r: TimelineRow) => r.calendar_id !== null && toggle(r.calendar_id, !r.done);
	const toggleEvent = (ev: EventRow) => toggle(ev.id, !ev.done);
</script>

<h1>Events</h1>
{#if toast}<div class="toast error">{toast} <button type="button" onclick={() => (toast = null)}>Dismiss</button></div>{/if}
{#if error}<p class="error">{error}</p>{/if}

{#if data}
	{#if data.fetched_at}
		<p class="muted">as of {timeAgo(data.fetched_at, now)}{#if data.error} · ⚠ last update failed: {data.error}{/if}{#if data.announcements_error} · ⚠ event art update failed: {data.announcements_error}{/if}</p>
	{:else}
		<p class="muted">{data.connected ? 'Sync to load the event calendar' : 'Connect HoYoLAB in Settings to load events'}{#if data.error}<br />⚠ last update failed: {data.error}{/if}</p>
	{/if}

	<div class="top">
		<section class="panel" data-testid="timeline">
			<h2>Timeline</h2>
			{#if data.timeline.length}
				<EventTimeline rows={data.timeline} {now} onopen={(k) => (openKey = k)} />
			{:else}
				<p class="muted">No events yet.</p>
			{/if}
		</section>
		<section class="panel timers" data-testid="timers">
			<h2>Timers</h2>
			{#each data.resets as r (r.key)}<div class="t"><span>{r.label}</span><Countdown at={r.at} {now} /></div>{/each}
			{#if data.ending_soon.length}
				<h3>Ending soon</h3>
				<div data-testid="ending-soon">
					{#each data.ending_soon as e (e.key)}
						<button type="button" class="t link" onclick={() => (openKey = e.key)}><span>{e.name}</span><Countdown at={e.end} {now} warn /></button>
					{/each}
				</div>
			{/if}
		</section>
	</div>

	<section class="panel" data-testid="events-left">
		<h2>Done <span class="muted">· {primosLine(left)}</span></h2>
		<ul class="events">
			{#each data.events as ev (ev.id)}
				<li class:done={ev.done} data-testid="event-{ev.id}">
					<label title={ev.finished ? 'Completed in game' : undefined}><input type="checkbox" checked={ev.done} disabled={ev.finished} onchange={() => toggleEvent(ev)} aria-label="Done: {ev.name}" /></label>
					<span class="name">{ev.name}</span>
					{#if ev.finished}<span class="auto">auto</span>{/if}
					<span class="rewards">
						{#each ev.rewards as r, i (i)}{#if imgSrc(r.icon)}<img src={imgSrc(r.icon)} alt={r.name} title={r.count > 0 ? `${r.name} ×${r.count}` : r.name} />{/if}{/each}
						{#if ev.primogems}<strong>{ev.primogems} primos</strong>{/if}
					</span>
					<Countdown at={ev.end} {now} warn={!ev.done} />
				</li>
			{:else}
				<li class="muted">No current events.</li>
			{/each}
		</ul>
	</section>
{/if}

<section class="panel" data-testid="banner-history"></section>

{#if openRow}
	<EventModal row={openRow} {now} onclose={() => (openKey = null)} ontoggle={toggleRow} />
{/if}

<style>
	section { margin-bottom: 12px; }
	.top { display: grid; grid-template-columns: minmax(0, 1fr) 240px; gap: 12px; }
	@media (max-width: 1100px) { .top { grid-template-columns: minmax(0, 1fr); } }
	.timers .t { display: flex; justify-content: space-between; gap: 8px; padding: 5px 0; border-bottom: 1px solid var(--line); width: 100%; }
	.timers h3 { margin: 12px 0 4px; font-size: 11px; letter-spacing: 0.08em; text-transform: uppercase; color: var(--muted); }
	.link { background: none; border: none; color: var(--text); cursor: pointer; text-align: left; font: inherit; }
	.events { list-style: none; padding: 0; margin: 0; }
	.events li { display: flex; flex-wrap: wrap; align-items: center; gap: 10px; padding: 6px 0; border-bottom: 1px solid var(--line); }
	.events li.done { opacity: 0.5; }
	.name { flex: 1; }
	.auto { font-size: 10px; padding: 1px 6px; border-radius: 999px; background: var(--panel-2); }
	.rewards { display: flex; gap: 4px; align-items: center; }
	.rewards img { width: 24px; height: 24px; }
	.toast { margin-bottom: 8px; }
</style>
```

- [ ] **Step 6: Run to verify pass**

Run: `npm run check` (0 errors), `npx vitest run`, then `PYTHON=<python> npx playwright test e2e/events.spec.ts e2e/dashboard.spec.ts`
Expected: the two new events tests pass; the old "banner history search" test fails until Task 8 (expected). Dashboard specs pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/EventTimeline.svelte frontend/src/lib/EventModal.svelte frontend/src/routes/events/+page.svelte frontend/e2e/events.spec.ts
git commit -m "feat(events): art timeline with popup, Timers and Done checklist"
```

---

### Task 8: Banner history by version and phase (frontend)

**Files:**
- Create: `frontend/src/lib/BannerHistory.svelte`
- Modify: `frontend/src/routes/events/+page.svelte` (replace the placeholder section with `<BannerHistory />`)
- Modify: `backend/app/devseed.py` (enough versions for a second page)
- Test: `frontend/e2e/events.spec.ts` (replace the search test)

**Interfaces:**
- Consumes: `api.bannerHistory(q, page)`, `BannerHistoryPage`, `HistoryVersion`, `HistoryPhase` (Task 6).
- Produces: `BannerHistory.svelte` (no props), root `<section class="panel" data-testid="banner-history">`; each version row `data-testid="version-<version>"`; phase cards `data-testid="phase"`; upcoming phase has class `upcoming`; "Load more" button.

- [ ] **Step 1: Seed more versions** — in `backend/app/devseed.py`, after the existing `GameBanner` seeding loop, add eight older character banners so history has two pages:

```python
        for i in range(8):
            day = f"2020-{i + 1:02d}-01 06:00:00"
            s.add(GameBanner(key=f"character|{day}|0", pool="character", name=f"Archive Banner {i}",
                             short_name=f"Archive {i}", start=day, end=f"2020-{i + 1:02d}-20 17:59:00",
                             timezone_dependent=True, timezone_dependent_end=False, order=0,
                             featured_5=[10000089], featured_4=[10000032], version=f"1.{i}"))
```

Run `<python> -m pytest tests/test_devseed.py -q` and fix any count it asserts on `GameBanner`.

- [ ] **Step 2: Write the failing e2e test** — replace `banner history search narrows the list` in `frontend/e2e/events.spec.ts`:

```ts
test('banner history groups by version, pages on scroll and searches', async ({ page }) => {
	await page.goto('/events');
	const history = page.getByTestId('banner-history');
	const top = history.getByTestId('version-9.9');
	await expect(top).toContainText('Tide of Furina');
	await expect(top.getByTestId('phase').first()).toContainText('Phase 1');
	await expect(top.locator('.phase.upcoming')).toContainText('Next Phase Wish');
	await expect(history.getByTestId('version-1.0')).toHaveCount(0);
	await history.getByRole('button', { name: 'Load more' }).scrollIntoViewIfNeeded();
	await expect(history.getByTestId('version-1.0')).toBeVisible();
	await page.getByLabel('Search banners').fill('Epitome');
	await expect(history.getByTestId('version-9.9')).toContainText('Epitome Invocation');
	await expect(history.getByTestId('version-9.9')).not.toContainText('Tide of Furina');
	await expect(history.getByTestId('version-1.0')).toHaveCount(0);
	await page.getByLabel('Search banners').fill('');
});
```

(Check the seeded version string with `grep -n 'version="' backend/app/devseed.py`; the existing seed uses `"9.9"`.)

- [ ] **Step 3: Run to verify failure**

Run: `PYTHON=<python> npx playwright test e2e/events.spec.ts -g "banner history"`
Expected: FAIL (empty section).

- [ ] **Step 4: Implement** — `frontend/src/lib/BannerHistory.svelte`

```svelte
<script lang="ts">
	import { api, errorMessage } from './api';
	import { imgSrc } from './img';
	import type { HistoryPhase, HistoryVersion } from './types';

	let q = $state('');
	let query = $state('');
	let versions = $state<HistoryVersion[]>([]);
	let page = $state(0);
	let total = $state(0);
	let loading = $state(false);
	let toast = $state<string | null>(null);
	let sentinel = $state<HTMLDivElement>();
	let request = 0;
	const more = $derived(versions.length < total);

	$effect(() => {
		const typed = q;
		const timer = setTimeout(() => { if (typed !== query) query = typed; }, 250);
		return () => clearTimeout(timer);
	});

	$effect(() => {
		void query;
		versions = [];
		page = 0;
		total = 0;
		loadNext(query);
	});

	$effect(() => {
		if (!sentinel) return;
		const io = new IntersectionObserver((entries) => {
			if (entries.some((e) => e.isIntersecting) && more && !loading) loadNext(query);
		}, { rootMargin: '200px' });
		io.observe(sentinel);
		return () => io.disconnect();
	});

	async function loadNext(forQuery: string) {
		const mine = ++request;
		loading = true;
		try {
			const res = await api.bannerHistory(forQuery, page + 1);
			if (mine !== request) return;
			versions = [...versions, ...res.versions];
			page = res.page;
			total = res.total_versions;
		} catch (e) {
			if (mine === request) toast = `Could not load banner history: ${errorMessage(e)}`;
		} finally {
			if (mine === request) loading = false;
		}
	}

	const day = (s: string) => new Date(s.replace(' ', 'T')).toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
	const got = (p: HistoryPhase) => p.banners.flatMap((b) => b.pulls?.fives ?? []);
	const pulls = (p: HistoryPhase) => p.banners.reduce((n, b) => n + (b.pulls?.pulls ?? 0), 0);
</script>

<section class="panel" data-testid="banner-history">
	<h2>Banner history</h2>
	{#if toast}<div class="toast error">{toast} <button type="button" onclick={() => (toast = null)}>Dismiss</button></div>{/if}
	<input class="search" placeholder="Search banner or item" bind:value={q} aria-label="Search banners" />
	{#each versions as v (v.version)}
		<div class="version" data-testid="version-{v.version}">
			<div class="vlabel">{v.version}</div>
			<div class="phases">
				{#each v.phases as p, i (p.start)}
					<div class="phase" class:upcoming={p.upcoming} data-testid="phase">
						<h5>Phase {i + 1} · {day(p.start)} – {day(p.end)}{#if p.upcoming} <span class="tag">upcoming</span>{/if}</h5>
						{#if p.upcoming}
							{#if imgSrc(p.image)}<div class="strip" style="background-image:url('{imgSrc(p.image)}')"></div>{/if}
							<div class="muted">{p.banners.map((b) => b.name).join(' · ')}</div>
						{:else}
							<div class="names muted">{p.banners.map((b) => b.name).join(' · ')}</div>
							<div class="five">
								{#each p.banners.filter((b) => b.pool !== 'weapon') as b (b.key)}
									{#each b.featured_5 as it (it.id)}{#if imgSrc(it.icon)}<img class="c r5" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/if}{/each}
								{/each}
								<span class="sep"></span>
								{#each p.banners.filter((b) => b.pool === 'weapon') as b (b.key)}
									{#each b.featured_5 as it (it.id)}{#if imgSrc(it.icon)}<img class="w r5" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/if}{/each}
								{/each}
							</div>
							<div class="four">
								{#each p.banners as b (b.key)}
									{#each b.featured_4 as it (it.id)}{#if imgSrc(it.icon)}<img class="r4" src={imgSrc(it.icon)} alt={it.name} title={it.name} />{/if}{/each}
								{/each}
							</div>
							{#if p.banners.some((b) => b.pool === 'chronicled')}<span class="tag">Chronicled</span>{/if}
							{#if pulls(p) > 0}<span class="you" class:got={got(p).length > 0}>{pulls(p)} pulls{#if got(p).length} · got {got(p).join(', ')}{/if}</span>{/if}
						{/if}
					</div>
				{/each}
			</div>
		</div>
	{:else}
		{#if !loading}<p class="muted">No banners match.</p>{/if}
	{/each}
	{#if more}
		<div bind:this={sentinel}></div>
		<button type="button" disabled={loading} onclick={() => loadNext(query)}>Load more</button>
	{/if}
</section>

<style>
	.search { margin-bottom: 10px; }
	.version { display: grid; grid-template-columns: 56px minmax(0, 1fr); gap: 10px; margin-bottom: 10px; }
	.vlabel { font-size: 20px; font-weight: 700; color: #e8cf9c; display: flex; align-items: center; justify-content: center; border-right: 1px solid var(--line); }
	.phases { display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; }
	.phase { background: var(--panel-2); border-radius: 10px; padding: 8px 10px; }
	.phase h5 { margin: 0 0 4px; font-size: 11px; letter-spacing: 0.06em; text-transform: uppercase; color: var(--muted); font-weight: 600; }
	.names { font-size: 12px; margin-bottom: 6px; }
	.five { display: flex; gap: 6px; align-items: flex-end; }
	.five img.c { width: 54px; height: 54px; border-radius: 8px; }
	.five img.w { width: 40px; height: 40px; border-radius: 8px; }
	.sep { width: 1px; align-self: stretch; background: var(--line); margin: 0 4px; }
	.four { display: flex; gap: 3px; margin-top: 5px; }
	.four img { width: 24px; height: 24px; border-radius: 5px; }
	.r5 { background: var(--r5); } .r4 { background: var(--r4); }
	.tag { font-size: 10px; padding: 1px 6px; border-radius: 999px; background: var(--panel); margin-right: 6px; }
	.you { display: inline-block; margin-top: 6px; padding: 1px 8px; border-radius: 999px; background: rgba(142, 197, 255, 0.18); font-size: 11px; }
	.you.got { background: rgba(232, 207, 156, 0.25); color: #f3d9a6; }
	.strip { height: 60px; border-radius: 8px; background-size: cover; background-position: center; margin-bottom: 6px; }
</style>
```

In `frontend/src/routes/events/+page.svelte` replace `<section class="panel" data-testid="banner-history"></section>` with `<BannerHistory />` and add `import BannerHistory from '$lib/BannerHistory.svelte';`.

- [ ] **Step 5: Run to verify pass**

Run: `npm run check`, `npx vitest run`, `PYTHON=<python> npx playwright test e2e/events.spec.ts`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/lib/BannerHistory.svelte frontend/src/routes/events/+page.svelte frontend/e2e/events.spec.ts backend/app/devseed.py backend/tests/test_devseed.py
git commit -m "feat(events): banner history by version and phase with infinite scroll"
```

---

### Task 9: Inventory — "To farm" strip and plain best-known counts

**Files:**
- Modify: `frontend/src/lib/materials.ts`, `frontend/src/lib/materials.test.ts`
- Modify: `frontend/src/lib/MaterialTile.svelte` (second pill)
- Modify: `frontend/src/routes/inventory/+page.svelte`
- Test: `frontend/e2e/planner.spec.ts`, `frontend/e2e/good.spec.ts`

**Interfaces:**
- Consumes: `Material`, `Inventory` (existing types).
- Produces:
  - `TileView` gains `craft: string | null` (amber pill). `tileView` and `charTileView` return `craft: null` (Dashboard unchanged visually).
  - `export function bestKnownCount(m: Material): number | null`
  - `export function backpackView(m: Material): TileView`
  - `export function farmView(m: Material): TileView`
  - `export function backpackDim(m: Material): boolean`
  - `export type InventoryFilter = 'all' | 'owned'`
  - `export function readInventoryFilter(stored: string | null): InventoryFilter`
  - `filterMaterials(ms, filter, query)` keeps its signature with the narrower filter.
  - Strip tiles `data-testid="farm-<id>"` inside `section.panel[data-testid="to-farm"]`; backpack tiles stay `tile-<id>`.

- [ ] **Step 1: Write the failing unit tests** — append to `frontend/src/lib/materials.test.ts` (keep a `mat()` builder if the file has one; otherwise add this one):

```ts
import { backpackDim, backpackView, bestKnownCount, farmView, readInventoryFilter } from './materials';
import type { Material } from './types';

const mat = (over: Partial<Material> = {}): Material => ({
	id: 1, name: 'Guide', icon: 'x', rarity: 3, category: 'talent', state: 'unneeded', need: 0, short: 0,
	have: null, craftable: 0, to_farm: 0, sources: [], characters: [], scan: null, ...over
});

describe('bestKnownCount', () => {
	it('prefers the live count when short, then the scan, else null', () => {
		expect(bestKnownCount(mat({ state: 'short', have: 8, scan: 2 }))).toBe(8);
		expect(bestKnownCount(mat({ state: 'met', need: 20, scan: 120 }))).toBe(120);
		expect(bestKnownCount(mat({ state: 'met', need: 20 }))).toBeNull();
		expect(bestKnownCount(mat({ scan: 0 }))).toBe(0);
	});
});

describe('backpackView', () => {
	it('shows only the count, no badge, no tone', () => {
		expect(backpackView(mat({ state: 'short', have: 8, need: 15, short: 7, to_farm: 7 }))).toEqual(
			{ main: '8', badge: null, craft: null, hint: null, tone: 'none' });
		expect(backpackView(mat()).main).toBe('—');
	});
	it('dims zero and unknown counts only', () => {
		expect(backpackDim(mat())).toBe(true);
		expect(backpackDim(mat({ scan: 0 }))).toBe(true);
		expect(backpackDim(mat({ scan: 3 }))).toBe(false);
	});
});

describe('farmView', () => {
	it('red to-farm pill, amber craft pill, best-known count', () => {
		expect(farmView(mat({ state: 'short', have: 7, need: 25, short: 18, craftable: 4, to_farm: 14 }))).toEqual(
			{ main: '7', badge: '−14', craft: '+4', hint: null, tone: 'none' });
	});
});

describe('readInventoryFilter falls back', () => {
	it('maps removed filters to all', () => {
		expect(readInventoryFilter('needed')).toBe('all');
		expect(readInventoryFilter('farm')).toBe('all');
		expect(readInventoryFilter('owned')).toBe('owned');
		expect(readInventoryFilter(null)).toBe('all');
	});
});
```

Update existing tests in `materials.test.ts` that call `filterMaterials` with `'needed'` or `'farm'`: delete those cases (the filters no longer exist) and add `craft: null` to any `tileView`/`charTileView` `toEqual` expectations.

- [ ] **Step 2: Run to verify failure**

Run: `npx vitest run src/lib/materials.test.ts`
Expected: FAIL (missing exports).

- [ ] **Step 3: Implement** — in `frontend/src/lib/materials.ts`:

```ts
export type InventoryFilter = 'all' | 'owned';
export interface TileView { main: string; badge: string | null; craft: string | null; hint: string | null; tone: Tone }
```

Add `craft: null` to every object `tileView` and `charTileView` return. Replace `filterMaterials`:

```ts
export function filterMaterials(ms: Material[], filter: InventoryFilter, query: string): Material[] {
	const q = query.trim().toLowerCase();
	return ms.filter((m) => (filter === 'all' || (m.scan ?? 0) > 0) && (!q || m.name.toLowerCase().includes(q)));
}

export function readInventoryFilter(stored: string | null): InventoryFilter {
	return stored === 'owned' ? 'owned' : 'all';
}

/** Live HoYoLAB count when short (newest), else the GOOD scan, else unknown. */
export function bestKnownCount(m: Material): number | null {
	if (m.state === 'short' && m.have != null) return m.have;
	return m.scan ?? null;
}

export function backpackView(m: Material): TileView {
	const n = bestKnownCount(m);
	return { main: n === null ? '—' : String(n), badge: null, craft: null, hint: null, tone: 'none' };
}

export function backpackDim(m: Material): boolean {
	return !bestKnownCount(m);
}

export function farmView(m: Material): TileView {
	const n = bestKnownCount(m);
	return {
		main: n === null ? '—' : String(n),
		badge: m.to_farm > 0 ? `−${m.to_farm}` : null,
		craft: m.craftable > 0 ? `+${m.craftable}` : null,
		hint: null,
		tone: 'none'
	};
}
```

`MaterialTile.svelte`: inside `.face`, after the badge, add `{#if view.craft}<span class="craft">{view.craft}</span>{/if}` and style:

```css
	.craft { position: absolute; bottom: -6px; right: -6px; background: #b7892f; color: #fff;
		border-radius: 10px; padding: 1px 6px; font-weight: 700; font-size: 11px; }
```

- [ ] **Step 4: Page** — in `frontend/src/routes/inventory/+page.svelte`:
  - Replace `BASE_FILTERS` with `[{ key: 'all', label: 'All' }]` and `readFilter()` with `try { return readInventoryFilter(localStorage.getItem(FILTER_KEY)); } catch { return 'all'; }`.
  - Import `backpackView, backpackDim, farmView, gapsSettled, readInventoryFilter` (drop `tileView`, `tileDim`).
  - Add derived values:

```ts
	const farm = $derived((data?.categories ?? []).flatMap((c) => c.materials.filter((m) => m.to_farm > 0)));
	const searching = $derived(query.trim().length > 0);
```

  - Remove the `anyNeeded` derived value and its "Set characters to Build" line, and add above the category loop (inside `{#if activeTab === 'materials'}`, after the skipped-planning note):

```svelte
		{#if !data.good}<p class="muted" data-testid="scan-hint">Import a GOOD scan to see every count.</p>{/if}
		{#if !searching}
			<section class="panel" data-testid="to-farm">
				<h2>To farm{#if farm.length} · {farm.length} material{farm.length === 1 ? '' : 's'}{/if}</h2>
				{#if farm.length}
					<div class="grid">
						{#each farm as m (m.id)}
							<MaterialTile name={m.name} icon={m.icon} rarity={m.rarity} view={farmView(m)} testid="farm-{m.id}">
								{#snippet popover()}<MaterialPopover material={m} scannedAt={data?.good?.imported_at ?? null} />{/snippet}
							</MaterialTile>
						{/each}
					</div>
				{:else if gapsSettled(data.gaps)}
					<p class="muted">Nothing to farm ✓</p>
				{:else}
					<p class="muted">{gapLabel(data.gaps, now)}</p>
				{/if}
			</section>
		{/if}
```

  - In the category loop use `view={backpackView(m)}` and `dim={backpackDim(m)}`.

- [ ] **Step 5: Update the e2e specs**

`frontend/e2e/planner.spec.ts` — replace `inventory To farm filter shows only short tiles`:

```ts
test('inventory To farm strip lists short materials; backpack shows plain counts', async ({ page }) => {
	await page.goto('/inventory');
	const strip = page.getByTestId('to-farm');
	await expect(strip.getByTestId('farm-104302')).toBeVisible();          // Guide to Freedom, short
	await expect(strip.getByTestId('farm-104302')).toContainText('−');
	await expect(strip.getByTestId('farm-104003')).toHaveCount(0);         // Hero's Wit, met
	await expect(page.getByTestId('tile-104302')).toContainText('8');
	await expect(page.getByTestId('tile-104302')).not.toContainText('/');
	await expect(page.getByTestId('tile-104003')).toContainText('—');      // met, no scan: unknown
	await expect(page.getByTestId('tile-104003')).toHaveClass(/dim/);
	await expect(page.getByTestId('scan-hint')).toBeVisible();
	await expect(page.getByRole('button', { name: 'To farm' })).toHaveCount(0);
	await page.getByLabel('Search materials').fill('Freedom');
	await expect(strip).toHaveCount(0);
	await expect(page.getByTestId('tile-104302')).toBeVisible();
	await page.getByLabel('Search materials').fill('');
});

test('a stored Needed filter opens on All', async ({ page }) => {
	await page.goto('/inventory');
	await page.evaluate(() => localStorage.setItem('gt.inventory.filter', 'needed'));
	await page.reload();
	await expect(page.getByRole('button', { name: 'All', exact: true })).toHaveClass(/on/);
	await expect(page.getByTestId('tile-100055')).toBeVisible();           // unneeded tile still listed
	await page.evaluate(() => localStorage.removeItem('gt.inventory.filter'));
});
```

(Confirm the seeded live count of Guide to Freedom with the existing good.spec comment "`8/15`": the short material has `have = 8`.)

`frontend/e2e/good.spec.ts` — change the two count assertions:

```ts
	await expect(page.getByTestId('tile-104003')).toContainText('120');      // met: scan count
	await expect(page.getByTestId('tile-104003')).not.toContainText('✓');
	await expect(page.getByTestId('tile-104302')).toContainText('8');        // short: live wins over scan 2
	await expect(page.getByTestId('tile-104302')).not.toContainText('/');
```

- [ ] **Step 6: Run to verify pass**

Run: `npx vitest run`, `npm run check`, `PYTHON=<python> npx playwright test e2e/planner.spec.ts e2e/good.spec.ts e2e/popover.spec.ts e2e/dashboard.spec.ts`
Expected: all pass (the popover spec covers strip tiles too: the strip is a `.panel`).

- [ ] **Step 7: Commit**

```bash
git add frontend/src/lib/materials.ts frontend/src/lib/materials.test.ts frontend/src/lib/MaterialTile.svelte frontend/src/routes/inventory/+page.svelte frontend/e2e/planner.spec.ts frontend/e2e/good.spec.ts
git commit -m "feat(inventory): To farm strip above plain best-known counts"
```

---

### Task 10: Full verification

**Files:** none new (fixes only, if a check fails).

- [ ] **Step 1: Backend** — from `backend/`: `<python> -m pytest -q` → all pass (588 before this work plus the new tests).
- [ ] **Step 2: Frontend** — from `frontend/`: `npm run check` (0 errors, 0 warnings), `npx vitest run` (all pass), `npm run build` (succeeds), `PYTHON=<python> npx playwright test` (all pass, workers 1).
- [ ] **Step 3: Migration on a copy of the real database** —

```bash
cp ../data/tracker.db "$SCRATCH/tracker-copy.db"
```

then run Alembic `upgrade head` against the copy (see `backend/tests/test_migration_0007.py` `upgrade()` helper for how the tests point Alembic at a file; reuse it from a one-off `<python> -I -c` call that imports it with `sys.path` set to `backend/` and `backend/tests/`). Expected: reaches `0011` without error; `event_log` exists. Never touch `../data/tracker.db` itself. (`$SCRATCH` = the session scratchpad directory.)
- [ ] **Step 4: Privacy check of the branch** — `git diff origin/main --stat` and `git grep -n -i -e "cookie" -e "ltoken" -- backend/app/sync/announcements.py backend/tests/fixtures/ann_*.json` → no cookie values; fixtures contain only placeholder `sdk.hoyoverse.com/upload/ann/test/...` URLs and made-up text.
- [ ] **Step 5: Commit any fixes** with `fix(...)` messages; report the counts.
