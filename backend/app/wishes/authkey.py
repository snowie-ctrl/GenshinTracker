"""Find the wish-history link in the game's web cache. Read-only; the authkey stays in memory.
genshin.py's get_authkey() is deliberately not used: it writes the authkey to a temp file."""
from __future__ import annotations

import re
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from app.wishes.types import ImportFailed

CACHE_NOT_FOUND = "Couldn't find the game's web cache. Set the game install path in Settings."
CACHE_LOCKED = "Close Genshin Impact and try again."
NO_WISH_LINK = "Open Wish History in-game once, then press Import again."

DATA_DIR_NAMES = ("GenshinImpact_Data", "YuanShen_Data")
LOG_DIRS = [(company, game) for company in ("miHoYo", "HoYoverse", "Cognosphere")
            for game in ("Genshin Impact", "原神")]
LOG_NAMES = ("output_log.txt", "Player.log")
LOG_DATA_RE = re.compile(r"([A-Za-z]:/[^\n\r]*?/(?:GenshinImpact|YuanShen)_Data)")
URL_RE = re.compile(rb"https://[^\x00\s\"'<>]+")
AUTHKEY_RE = re.compile(r"[?&]authkey=([^&#]+)")
REGION_RE = re.compile(r"[?&]region=([^&#]+)")


@dataclass(frozen=True, repr=False)
class WishLink:
    authkey: str = field(repr=False)
    region: str | None
    cached_at: datetime

    def __repr__(self) -> str:
        return f"WishLink(region={self.region!r}, cached_at={self.cached_at!r})"


def default_locallow() -> Path:
    return Path.home() / "AppData" / "LocalLow"


def _version_key(p: Path) -> tuple[int, ...]:
    try:
        return tuple(int(x) for x in p.name.split("."))
    except ValueError:
        return (-1,)


def _data_2_in(data_dir: Path) -> Path | None:
    caches = data_dir / "webCaches"
    if not caches.is_dir():
        return None
    versions = sorted((d for d in caches.iterdir() if d.is_dir()), key=_version_key, reverse=True)
    for v in versions:
        f = v / "Cache" / "Cache_Data" / "data_2"
        if f.is_file():
            return f
    return None


def _data_dirs_under(game_path: Path) -> list[Path]:
    if game_path.name in DATA_DIR_NAMES:
        return [game_path]
    out = []
    for base in (game_path, game_path / "Genshin Impact game"):
        out += [base / n for n in DATA_DIR_NAMES]
    return out


def _data_dirs_from_log(locallow: Path) -> list[Path]:
    for company, game in LOG_DIRS:
        for name in LOG_NAMES:
            log = locallow / company / game / name
            if log.is_file():
                try:
                    text = log.read_text(encoding="utf-8", errors="replace")
                except OSError:
                    continue
                return [Path(m) for m in dict.fromkeys(LOG_DATA_RE.findall(text))]
    return []


def find_data_2(game_path: str, locallow: Path) -> Path:
    candidates = _data_dirs_under(Path(game_path)) if game_path.strip() else _data_dirs_from_log(locallow)
    for d in candidates:
        found = _data_2_in(d)
        if found is not None:
            return found
    raise ImportFailed(CACHE_NOT_FOUND)


def read_wish_link(data_2: Path) -> WishLink:
    try:
        raw = data_2.read_bytes()
        mtime = data_2.stat().st_mtime
    except PermissionError:
        raise ImportFailed(CACHE_LOCKED) from None
    except OSError:
        raise ImportFailed(CACHE_NOT_FOUND) from None
    last: str | None = None
    for m in URL_RE.finditer(raw):
        url = m.group(0).decode("utf-8", errors="replace")
        if "authkey=" in url and ("gacha" in url or "getGachaLog" in url):
            last = url
    if last is None:
        raise ImportFailed(NO_WISH_LINK)
    key = AUTHKEY_RE.search(last)
    if key is None:
        raise ImportFailed(NO_WISH_LINK)
    region = REGION_RE.search(last)
    return WishLink(authkey=urllib.parse.unquote(key.group(1)),
                    region=region.group(1) if region else None,
                    cached_at=datetime.fromtimestamp(mtime, timezone.utc).replace(tzinfo=None))


def load_wish_link(game_path: str, locallow: Path) -> WishLink:
    return read_wish_link(find_data_2(game_path, locallow))


STATUS_BY_MESSAGE = {CACHE_NOT_FOUND: "not_found", CACHE_LOCKED: "locked", NO_WISH_LINK: "no_link"}


def link_status(load: Callable[[], WishLink]) -> dict:
    """Status for Settings; never exposes the link itself."""
    try:
        link = load()
    except ImportFailed as e:
        return {"status": STATUS_BY_MESSAGE.get(e.message, "not_found"), "cached_at": None}
    return {"status": "found", "cached_at": link.cached_at}


def cache_status(game_path: str, locallow: Path) -> dict:
    return link_status(lambda: load_wish_link(game_path, locallow))
