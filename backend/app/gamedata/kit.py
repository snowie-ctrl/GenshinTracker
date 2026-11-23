"""Talents, passives and constellations per character from Yatta (gi.yatta.moe avatar/<id>), parsed to plain
text segments and pre-formatted scaling values (sub-project 5)."""
from __future__ import annotations

import asyncio
import logging
import re
from datetime import datetime, timedelta

import httpx
from sqlalchemy.orm import sessionmaker

from app.config import GAMEDATA_MAX_AGE_DAYS
from app.db.models import GameCharacterKit
from app.gamedata.traveler import BODY_IDS, element_of, is_traveler

KIT_VERSION = 1                      # bump when the parsed Kit shape changes; older cached copies are refetched
log = logging.getLogger(__name__)

YATTA_AVATAR_DETAIL_URL = "https://gi.yatta.moe/api/v2/en/avatar/{key}"

_PARAM = re.compile(r"\{param(\d+):([A-Za-z0-9]+)\}")
_TOKEN = re.compile(
    r"<color=#([0-9A-Fa-f]{6})[0-9A-Fa-f]{0,2}>|(</color>)|(<i>)|(</i>)|\{[A-Z_]+#[^}]*\}|\{/[A-Z_]+\}|<[^>]*>")


def yatta_key(character_id: int, traveler_body: str) -> str:
    if not is_traveler(character_id):
        return str(character_id)
    body = BODY_IDS.get(traveler_body, BODY_IDS["girl"])
    return f"{body}-{element_of(character_id).lower()}"


def _fmt(v: float, spec: str) -> str:
    pct = spec.endswith("P")
    core = spec[:-1] if pct else spec
    if core == "I":
        return str(int(round(v)))
    if core == "":
        digits = 0
    elif core.startswith("F") and core[1:].isdigit():
        digits = int(core[1:])
    else:
        return str(v)
    x = v * 100 if pct else v
    return f"{x:.{digits}f}" + ("%" if pct else "")


def fill(template: str, params: list[float]) -> str:
    def one(m: re.Match) -> str:
        i = int(m.group(1)) - 1
        if i < 0 or i >= len(params):
            return "?"
        return _fmt(float(params[i]), m.group(2))
    return _PARAM.sub(one, template)


def segments(text: str) -> list[list[dict]]:
    """Yatta markup -> lines of {text, color, italic}. Plain text only; unknown tags are dropped."""
    text = (text or "").replace("\\n", "\n")
    lines: list[list[dict]] = [[]]
    color: str | None = None
    italic = False

    def emit(chunk: str) -> None:
        for n, part in enumerate(chunk.split("\n")):
            if n:
                lines.append([])
            if part:
                lines[-1].append({"text": part, "color": color, "italic": italic})

    pos = 0
    for m in _TOKEN.finditer(text):
        emit(text[pos:m.start()])
        if m.group(1):
            color = "#" + m.group(1).upper()
        elif m.group(2):
            color = None
        elif m.group(3):
            italic = True
        elif m.group(4):
            italic = False
        pos = m.end()
    emit(text[pos:])
    return lines


def _num(v) -> float | None:
    try:
        return None if v in (None, "", "None") else float(v)
    except (TypeError, ValueError):
        return None


def _scaling(promote: dict | None) -> list[dict]:
    if not promote:
        return []
    levels = sorted(promote, key=int)
    first = promote[levels[0]].get("description") or []
    rows = []
    for i, template in enumerate(first):
        if not template or "|" not in template:
            continue
        label = template.split("|", 1)[0]
        values = []
        for lv in levels:
            desc = promote[lv].get("description") or []
            line = desc[i] if i < len(desc) else ""
            values.append(fill(line.split("|", 1)[1], promote[lv].get("params") or []) if "|" in line else "")
        rows.append({"label": label, "values": values})
    return rows


def _entries(d: dict | None) -> list[dict]:
    out = []
    for k in sorted((d or {}), key=lambda x: int(x) if str(x).isdigit() else 10**6):
        v = d[k]
        if isinstance(v, dict) and v.get("name"):
            out.append(v)
    return out


def _plain_lines(lines: list[list[dict]]) -> str:
    return "".join(s["text"] for line in lines for s in line)


def parse_kit(payload: dict) -> dict:
    data = payload["data"]
    talents, passives = [], []
    normal_seen = skill_seen = burst_seen = False
    raw_active: list[tuple[dict, dict]] = []
    for t in _entries(data.get("talent")):
        kind = int(t.get("type", -1)) if str(t.get("type", "")).lstrip("-").isdigit() else -1
        if kind == 2:
            passives.append({"name": t["name"], "icon": t.get("icon") or None,
                             "description": segments(t.get("description", ""))})
            continue
        if kind not in (0, 1):
            continue
        cooldown = _num(t.get("cooldown"))
        if kind == 1 and not burst_seen:
            role, burst_seen = "burst", True
        elif kind == 0 and not normal_seen:
            role, normal_seen = "normal", True
        elif kind == 0 and cooldown is not None and not skill_seen:
            role, skill_seen = "skill", True
        else:
            role = "other"
        cost = _num(t.get("cost"))
        item = {"name": t["name"], "icon": t.get("icon") or None, "role": role, "cooldown": cooldown,
                "cost": int(cost) if cost is not None else None,
                "description": segments(t.get("description", "")), "scaling": _scaling(t.get("promote"))}
        talents.append(item)
        raw_active.append((t, item))

    raises: dict[int, str] = {}
    for t, item in raw_active:
        if item["role"] not in ("skill", "burst"):
            continue
        linked = t.get("linkedConstellations") or {}
        for p in (linked.get("prop") or []) if isinstance(linked, dict) else []:
            if p.get("type") == "level":
                raises[int(p["id"]) + 1] = item["role"]

    constellations = []
    for n, c in enumerate(_entries(data.get("constellation")), start=1):
        if n > 6:
            break
        constellations.append({"index": n, "name": c["name"], "icon": c.get("icon") or None,
                               "description": segments(c.get("description", "")), "raises": raises.get(n)})
    for c in constellations:                                   # no link data (e.g. Mona): match the text
        if c["raises"] is None and c["index"] in (3, 5):
            text = _plain_lines(c["description"])
            for t, item in raw_active:
                if item["role"] in ("skill", "burst") and f"Increases the Level of {item['name']}" in text:
                    c["raises"] = item["role"]
    return {"v": KIT_VERSION, "talents": talents, "passives": passives, "constellations": constellations}


FETCH_ERRORS = (httpx.HTTPError, KeyError, ValueError, TypeError, AttributeError)


async def fetch_kit(http: httpx.AsyncClient, key: str) -> dict:
    response = await http.get(YATTA_AVATAR_DETAIL_URL.format(key=key), timeout=30)
    response.raise_for_status()
    return response.json()


async def load_kit(session_factory: sessionmaker, http: httpx.AsyncClient, character_id: int, key: str,
                   offline: bool, lock: asyncio.Lock, now: datetime) -> dict:
    """Cached kit if fresh; else fetch (never when offline). Fetch failure falls back to the stale copy."""
    async with lock:
        with session_factory() as s:
            row = s.get(GameCharacterKit, character_id)
            cached = (row.data, row.fetched_at) if row is not None else None
        if (cached is not None and cached[0].get("v") == KIT_VERSION
                and now - cached[1] <= timedelta(days=GAMEDATA_MAX_AGE_DAYS)):
            return {"state": "fresh", "kit": cached[0]}
        if not offline:
            kit = None
            try:
                kit = parse_kit(await fetch_kit(http, key))
                if not kit["talents"]:
                    raise ValueError("kit has no talents")
            except FETCH_ERRORS as e:
                log.warning("kit fetch/parse failed for yatta key %s: %s", key, type(e).__name__)
                kit = None
            if kit is not None:
                with session_factory.begin() as s:
                    s.merge(GameCharacterKit(character_id=character_id, data=kit, fetched_at=now))
                return {"state": "fresh", "kit": kit}
        if cached is not None:
            return {"state": "stale", "kit": cached[0]}
        return {"state": "unavailable", "kit": None}
