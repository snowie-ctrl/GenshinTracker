"""The only network code for wishes: page the gacha log API, newest first, stopping at known ids."""
from __future__ import annotations

import asyncio
from typing import Awaitable, Callable

from app.config import WISH_PAGE_DELAY
from app.wishes.authkey import WishLink
from app.wishes.types import POOL_BY_GACHA_TYPE, IncomingWish, item_type_of, normalize_time

FETCH_TYPES = ("100", "200", "301", "400", "302", "500")
PAGE_SIZE = 20
RETRY_DELAYS = (2.0, 4.0, 8.0)
LINK_EXPIRED = "Your wish link has expired. Open Wish History in-game once, then press Import again."

PageFn = Callable[[str, str], Awaitable[list[dict]]]


class RateLimited(Exception):
    pass


class WishLinkExpired(Exception):
    pass


class FetchFailed(Exception):
    """Carries only an exception class name: genshin/httpx messages can contain the wish URL."""

    def __init__(self, kind: str):
        super().__init__(kind)
        self.kind = kind


async def _page_with_retry(page: PageFn, gacha_type: str, end_id: str, sleep) -> list[dict]:
    for attempt in range(len(RETRY_DELAYS) + 1):
        try:
            return await page(gacha_type, end_id)
        except RateLimited:
            if attempt == len(RETRY_DELAYS):
                raise FetchFailed("RateLimited") from None
            await sleep(RETRY_DELAYS[attempt])
    raise AssertionError("unreachable")


async def fetch_new(page: PageFn, known_ids: set[str], *, sleep=asyncio.sleep,
                    page_delay: float = WISH_PAGE_DELAY) -> list[dict]:
    seen: set[str] = set()
    out: list[dict] = []
    for gacha_type in FETCH_TYPES:
        end_id = "0"
        while True:
            records = await _page_with_retry(page, gacha_type, end_id, sleep)
            hit_known = False
            for r in records:
                rid = str(r["id"])
                if rid in known_ids:
                    hit_known = True
                    break
                if rid not in seen:
                    seen.add(rid)
                    out.append(r)
            if hit_known or len(records) < PAGE_SIZE:
                break
            end_id = str(records[-1]["id"])
            await sleep(page_delay)
    return out


def to_incoming(raw: dict) -> IncomingWish:
    gacha_type = str(raw["gacha_type"])
    return IncomingWish(id=str(raw["id"]), pool=POOL_BY_GACHA_TYPE[gacha_type], gacha_type=gacha_type,
                        time=normalize_time(raw["time"]), name=str(raw["name"]),
                        item_type=item_type_of(raw["item_type"]), rarity=int(raw["rank_type"]))


def record_uid(raw: list[dict]) -> int | None:
    for r in raw:
        if r.get("uid"):
            return int(r["uid"])
    return None


def genshin_page_fn(link: WishLink) -> PageFn:
    import genshin
    from genshin import errors as gerrors

    client = genshin.Client(lang="en-us", game=genshin.Game.GENSHIN)

    async def page(gacha_type: str, end_id: str) -> list[dict]:
        try:
            data = await client.request_gacha_info(
                "getGachaLog", lang="en-us", authkey=link.authkey,
                params={"gacha_type": gacha_type, "size": PAGE_SIZE, "end_id": end_id})
        except gerrors.AuthkeyException:
            raise WishLinkExpired() from None
        except gerrors.VisitsTooFrequently:
            raise RateLimited() from None
        except Exception as e:  # noqa: BLE001 - message may contain the URL; keep the class name only
            raise FetchFailed(type(e).__name__) from None
        return list(data.get("list") or [])

    return page
