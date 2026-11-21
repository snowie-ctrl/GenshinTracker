"""paimon.moe's banners.js (MIT, github.com/MadeBaruna/paimon-moe) → GameBanner rows.
The converter is deliberately strict: anything unexpected raises and the cached banners stay."""
from __future__ import annotations

import json
import re
from collections import defaultdict
from dataclasses import dataclass

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import BANNERS_URL
from app.db.models import GameCharacter, GameWeapon
from app.wishes.types import normalize_time

POOL_BY_KEY = {"beginners": "beginner", "standard": "standard", "characters": "character",
               "weapons": "weapon", "chronicled": "chronicled"}
# paimon.moe slug -> our name_slug, for the few names that do not normalise to the same slug.
SLUG_OVERRIDES: dict[str, str] = {}
ESCAPES = {"n": "\n", "t": "\t", "r": "\r"}


class BannerParseError(ValueError):
    pass


def js_to_json(text: str) -> str:
    try:
        start, end = text.index("{"), text.rindex("}")
    except ValueError:
        raise BannerParseError("no object literal found") from None
    src, out, i, n = text[start:end + 1], [], 0, end + 1 - start
    while i < n:
        c = src[i]
        if c in "'\"":
            j, buf = i + 1, []
            while True:
                if j >= n:
                    raise BannerParseError("unterminated string")
                d = src[j]
                if d == "\\" and j + 1 < n:
                    buf.append(ESCAPES.get(src[j + 1], src[j + 1]))
                    j += 2
                    continue
                if d == c:
                    break
                buf.append(d)
                j += 1
            out.append(json.dumps("".join(buf)))
            i = j + 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            i = n if j < 0 else j
        elif src.startswith("/*", i):
            j = src.find("*/", i)
            if j < 0:
                raise BannerParseError("unterminated comment")
            i = j + 2
        elif c.isalpha() or c in "_$":
            j = i
            while j < n and (src[j].isalnum() or src[j] in "_$"):
                j += 1
            word = src[i:j]
            k = j
            while k < n and src[k].isspace():
                k += 1
            if word in ("true", "false", "null"):
                out.append(word)
            elif k < n and src[k] == ":":
                out.append(json.dumps(word))
            else:
                raise BannerParseError(f"unexpected identifier {word!r}")
            i = j
        elif c in "]}":
            if out and out[-1] == ",":
                out.pop()                      # trailing comma
            out.append(c)
            i += 1
        elif c in "{[:,":
            out.append(c)
            i += 1
        elif c.isspace():
            i += 1
        elif c.isdigit() or c == "-":
            j = i + 1
            while j < n and (src[j].isdigit() or src[j] in ".eE+-"):
                j += 1
            out.append(src[i:j])
            i = j
        else:
            raise BannerParseError(f"unexpected character {c!r}")
    return "".join(out)


def parse_banners(text: str) -> dict[str, list[dict]]:
    try:
        data = json.loads(js_to_json(text))
    except json.JSONDecodeError as e:
        raise BannerParseError(f"invalid JSON after conversion: {e.msg}") from None
    if not isinstance(data, dict) or not set(POOL_BY_KEY) & set(data):
        raise BannerParseError("no banner lists found")
    return {k: v for k, v in data.items() if k in POOL_BY_KEY and isinstance(v, list)}


def name_slug(name: str) -> str:
    cleaned = re.sub(r"['’\"]", "", name.lower())
    return re.sub(r"[^a-z0-9]+", "_", cleaned).strip("_")


def slug_index(session: Session) -> dict[str, int]:
    out = {name_slug(n): i for i, n in session.execute(select(GameWeapon.id, GameWeapon.name))}
    out.update({name_slug(n): i for i, n in session.execute(select(GameCharacter.id, GameCharacter.name))})
    return out


@dataclass(frozen=True)
class BannerData:
    key: str
    pool: str
    name: str
    short_name: str
    start: str
    end: str
    timezone_dependent: bool
    timezone_dependent_end: bool
    order: int
    featured_5: list[int]
    featured_4: list[int]
    version: str | None


def build_banners(parsed: dict, slugs: dict[str, int],
                  overrides: dict[str, str] = SLUG_OVERRIDES) -> tuple[list[BannerData], set[str]]:
    unmapped: set[str] = set()

    def ids(values) -> tuple[list[int], bool]:
        out, missing = [], False
        for slug in values or []:
            if not isinstance(slug, str):
                raise BannerParseError("non-string slug in a featured list")
            item = slugs.get(overrides.get(slug) or name_slug(slug))
            if item is None:
                unmapped.add(slug)
                missing = True
            else:
                out.append(item)
        return out, missing

    banners: dict[str, BannerData] = {}
    for key, pool in POOL_BY_KEY.items():
        seen_starts: dict[str, int] = defaultdict(int)
        for b in parsed.get(key, []):
            try:
                start = normalize_time(b["start"])
                end = normalize_time(b["end"])
                order = seen_starts[start] if pool == "character" else 0
                seen_starts[start] += 1
                f5, f5_missing = ids(b.get("featured"))
                f4, _ = ids(b.get("featuredRare"))
                data = BannerData(
                    key=f"{pool}|{start}|{order}", pool=pool, name=str(b["name"]),
                    short_name=str(b.get("shortName") or b["name"]), start=start, end=end,
                    timezone_dependent=bool(b.get("timezoneDependent", False)),
                    timezone_dependent_end=bool(b.get("timezoneDependentEnd", False)), order=order,
                    # A partly mapped 5★ list would make a missing featured item look Lost, so it is
                    # stored empty (outcomes become Unknown); the slugs still appear in `unmapped`.
                    featured_5=[] if f5_missing else f5, featured_4=f4,
                    version=str(b["version"]) if b.get("version") is not None else None)
            except (KeyError, TypeError, AttributeError, ValueError) as e:
                raise BannerParseError(f"malformed banner entry in {key!r} ({type(e).__name__})") from None
            banners[data.key] = data
    return list(banners.values()), unmapped


async def fetch_banners_js(http: httpx.AsyncClient) -> str:
    r = await http.get(BANNERS_URL, timeout=30)
    r.raise_for_status()
    return r.text
