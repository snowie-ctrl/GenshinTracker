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
    content: dict[int, dict] = {}
    for c in (ann_content.get("data") or {}).get("list", []):
        try:
            content[int(c["ann_id"])] = c
        except (KeyError, TypeError, ValueError):
            continue  # a malformed content entry is ignored, like a malformed item
    out: list[Announcement] = []
    for group in (ann_list.get("data") or {}).get("list", []):
        if int(group.get("type_id", 0)) != EVENT_TYPE_ID:
            continue
        for item in group.get("list", []):
            title, sub = item.get("title") or "", item.get("subtitle") or ""
            if "genius invokation" in f"{title} {sub}".lower():
                continue
            try:
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
            except (KeyError, TypeError, ValueError):
                continue  # one malformed item is skipped; the rest of the feed still parses
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
