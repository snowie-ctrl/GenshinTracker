"""Synthetic wish data for tests: fake game installs, pulls, gacha pages, workbooks. No real data."""
from __future__ import annotations

from pathlib import Path

FAKE_AUTHKEY = "SECRET-AUTHKEY+abc/def=="
FAKE_UID = 800000001


def wish_url(authkey: str = FAKE_AUTHKEY, host: str = "public-operation-hk4e-sg.hoyoverse.com") -> str:
    from urllib.parse import quote
    return (f"https://{host}/gacha_info/api/getGachaLog?win_mode=fullscreen&authkey_ver=1"
            f"&authkey={quote(authkey, safe='')}&lang=en&region=os_euro&game_biz=hk4e_global")


def make_game_install(root: Path, *, versions=("2.40.0.0",), urls: tuple[str, ...] | None = None,
                      log: bool = True, newest_has_data: bool = True) -> tuple[Path, Path]:
    """A fake install under root/'Genshin Impact game' with webCaches/<v>/Cache/Cache_Data/data_2.
    The newest version (by number) gets `urls`; older ones get an outdated URL."""
    game_dir = root / "Genshin Impact game"
    data_dir = game_dir / "GenshinImpact_Data"
    urls = (wish_url(),) if urls is None else urls
    ordered = sorted(versions, key=lambda v: tuple(int(p) for p in v.split(".")))
    for v in ordered:
        cache = data_dir / "webCaches" / v / "Cache" / "Cache_Data"
        cache.mkdir(parents=True)
        newest = v == ordered[-1]
        if newest and not newest_has_data:
            continue
        body = urls if newest else (wish_url("OLD-KEY"),)
        payload = b"\x00binary\x00".join(u.encode() + b"\x00" for u in body)
        (cache / "data_2").write_bytes(b"\x00\x01junk" + payload + b"\x00tail")
    locallow = root / "LocalLow"
    if log:
        log_dir = locallow / "miHoYo" / "Genshin Impact"
        log_dir.mkdir(parents=True)
        (log_dir / "output_log.txt").write_text(
            f"[Subsystems] Discovering subsystems at path {data_dir.as_posix()}/UnitySubsystems\n",
            encoding="utf-8")
    return game_dir, locallow
