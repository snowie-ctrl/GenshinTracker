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


def raw_wish(id_: str, gacha_type: str, time: str, name: str, rarity: int,
             item_type: str = "Weapon", uid: int = FAKE_UID) -> dict:
    """One record as the gacha log API returns it."""
    return {"uid": str(uid), "gacha_type": gacha_type, "item_id": "", "count": "1", "time": time,
            "name": name, "lang": "en-us", "item_type": item_type, "rank_type": str(rarity), "id": id_}


class FakeGachaApi:
    """Pages of 20, newest first, per queried gacha type. Querying 301 or 400 returns both
    (as the real API does); other types return only their own records."""

    def __init__(self, records: list[dict], expire_after: int | None = None, rate_limit_times: int = 0):
        self.records = sorted(records, key=lambda r: int(r["id"]), reverse=True)
        self.calls: list[tuple[str, str]] = []
        self.expire_after = expire_after
        self.rate_limit_times = rate_limit_times

    async def page(self, gacha_type: str, end_id: str) -> list[dict]:
        from app.wishes.fetch import RateLimited, WishLinkExpired
        self.calls.append((gacha_type, end_id))
        if self.rate_limit_times > 0:
            self.rate_limit_times -= 1
            raise RateLimited()
        if self.expire_after is not None and len(self.calls) > self.expire_after:
            raise WishLinkExpired()
        group = {"301", "400"} if gacha_type in ("301", "400") else {gacha_type}
        rows = [r for r in self.records if r["gacha_type"] in group]
        if end_id != "0":
            rows = [r for r in rows if int(r["id"]) < int(end_id)]
        return rows[:20]


PAIMON_HEADER = ("Type", "Name", "Time", "⭐", "Pity", "#Roll", "Group", "Banner", "Part")


def make_paimon_xlsx(sheets: dict[str, list[tuple]], header: tuple = PAIMON_HEADER) -> bytes:
    """rows are (type, name, time, rarity); the other paimon columns are filled with filler."""
    from io import BytesIO
    from openpyxl import Workbook
    wb = Workbook()
    wb.remove(wb.active)
    for title, rows in sheets.items():
        ws = wb.create_sheet(title)
        ws.append(list(header))
        for n, (type_, name, time, rarity) in enumerate(rows, start=1):
            ws.append([type_, name, time, rarity, 1, n, n, "Some Banner", ""])
    buf = BytesIO()
    wb.save(buf)
    return buf.getvalue()
