import copy
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


def test_malformed_items_are_skipped_not_fatal():
    feed = copy.deepcopy(LIST)
    event_group = next(g for g in feed["data"]["list"] if g["type_id"] == 1)
    event_group["list"].append({"title": "No ann_id", "subtitle": "No id", "banner": "", "type": 1,
                                "start_time": "2026-11-18 05:00:00", "end_time": "2026-11-30 03:59:59"})
    event_group["list"].append({"ann_id": 299, "title": "Bad start", "subtitle": "Bad start", "banner": "",
                                "start_time": "not a date", "end_time": "2026-11-30 03:59:59", "type": 1})
    assert sorted(a.ann_id for a in parse(feed, CONTENT, -5)) == [201, 202, 204, 205, 206]
    content = copy.deepcopy(CONTENT)
    content["data"]["list"].append({"banner": "", "content": "<p>orphan, no ann_id</p>"})
    content["data"]["list"].append({"ann_id": "abc", "banner": "", "content": "<p>orphan, bad ann_id</p>"})
    assert sorted(a.ann_id for a in parse(LIST, content, -5)) == [201, 202, 204, 205, 206]


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
