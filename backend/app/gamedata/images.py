"""Download-once image cache for game art (named) and HoYoLAB icon URLs (remote, allow-listed)."""
from __future__ import annotations

import base64
import hashlib
import mimetypes
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

import httpx

NAME_RE = re.compile(r"^UI_[A-Za-z0-9_]+$")
ALLOWED_HOST_SUFFIXES = ("hoyoverse.com", "mihoyo.com", "hoyolab.com", "enka.network", "yatta.moe")
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}
PLACEHOLDER_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
)


@dataclass(frozen=True)
class ImageResult:
    data: bytes
    media_type: str
    cached: bool


def _named_sources(name: str) -> list[str]:
    return [f"https://enka.network/ui/{name}.png", f"https://gi.yatta.moe/assets/UI/{name}.png"]


def is_allowed_remote(url: str) -> bool:
    parts = urlsplit(url)
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(
        host == s or host.endswith("." + s) for s in ALLOWED_HOST_SUFFIXES
    )


async def _fetch(path: Path, urls: list[str], http: httpx.AsyncClient, offline: bool) -> ImageResult:
    media = mimetypes.guess_type(path.name)[0] or "image/png"
    if path.exists():
        return ImageResult(path.read_bytes(), media, True)
    if offline:
        return ImageResult(PLACEHOLDER_PNG, "image/png", False)
    for url in urls:
        try:
            response = await http.get(url, timeout=20)
        except httpx.HTTPError:
            continue
        if response.status_code == 200 and response.headers.get("content-type", "").startswith("image/"):
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".part")
            tmp.write_bytes(response.content)
            tmp.replace(path)
            return ImageResult(response.content, media, True)
    return ImageResult(PLACEHOLDER_PNG, "image/png", False)


async def get_named(cache_dir: Path, http: httpx.AsyncClient, name: str, offline: bool = False) -> ImageResult:
    if not NAME_RE.fullmatch(name):
        raise ValueError("bad image name")
    return await _fetch(cache_dir / f"{name}.png", _named_sources(name), http, offline)


async def get_remote(cache_dir: Path, http: httpx.AsyncClient, url: str, offline: bool = False) -> ImageResult:
    if not is_allowed_remote(url):
        raise ValueError("image host not allowed")
    ext = Path(urlsplit(url).path).suffix.lower()
    key = hashlib.sha256(url.encode()).hexdigest()[:32]
    path = cache_dir / "remote" / f"{key}{ext if ext in IMAGE_EXTS else '.png'}"
    return await _fetch(path, [url], http, offline)
