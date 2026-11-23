"""Character list from Yatta (gi.yatta.moe), normalised to our ids and display names."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

YATTA_AVATAR_URL = "https://gi.yatta.moe/api/v2/en/avatar"

from app.gamedata.traveler import (BODY_IDS, MANEKIN_RAW_IDS, TRAVELER_ELEMENTS, TRAVELER_PENDING, body_icon,
                                   traveler_id, traveler_name)

VARIANT_ICONS = {10000005: "UI_AvatarIcon_PlayerBoy", 10000007: "UI_AvatarIcon_PlayerGirl"}

ELEMENTS = {
    "Electric": "Electro", "Fire": "Pyro", "Grass": "Dendro", "Ice": "Cryo",
    "Rock": "Geo", "Water": "Hydro", "Wind": "Anemo",
}
WEAPONS = {
    "WEAPON_SWORD_ONE_HAND": "Sword", "WEAPON_CLAYMORE": "Claymore", "WEAPON_POLE": "Polearm",
    "WEAPON_BOW": "Bow", "WEAPON_CATALYST": "Catalyst",
}


@dataclass(frozen=True)
class CharacterData:
    id: int
    name: str
    slug: str
    rarity: int
    element: str | None
    weapon_type: str
    region: str | None
    icon: str
    splash: str
    release_at: datetime


def canonical_id(raw: int | str, element: str | None = None) -> int | None:
    """Our id for a HoYoLAB/Yatta character id. Traveler: the element's id (TRAVELER_PENDING when the
    element is missing or unknown). Manekin: None (not a character in Ad Astra)."""
    n = int(str(raw).split("-")[0])
    if n in MANEKIN_RAW_IDS:
        return None
    if n in BODY_IDS.values():
        return traveler_id(element) if element in TRAVELER_ELEMENTS else TRAVELER_PENDING
    return n


def splash_for(icon: str) -> str:
    return icon.replace("UI_AvatarIcon_", "UI_Gacha_AvatarImg_", 1)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_avatar_list(payload: dict, body: str = "girl") -> list[CharacterData]:
    by_id: dict[int, CharacterData] = {}
    for key, v in payload["data"]["items"].items():
        element = ELEMENTS.get(v.get("element") or "")
        cid = canonical_id(key, element)
        if cid is None or cid == TRAVELER_PENDING:
            continue  # Manekin, or a Traveler element we have no id for yet
        traveler = int(str(key).split("-")[0]) in BODY_IDS.values()
        name = traveler_name(element) if traveler else v["name"]
        icon = body_icon(body) if traveler else v["icon"]
        release = datetime.fromtimestamp(int(v["release"]), tz=timezone.utc).replace(tzinfo=None)
        data = CharacterData(
            id=cid, name=name, slug=slugify(name), rarity=int(v["rank"]), element=element,
            weapon_type=WEAPONS.get(v["weaponType"], v["weaponType"]), region=v.get("region") or None,
            icon=icon, splash=splash_for(icon), release_at=release,
        )
        previous = by_id.get(cid)
        if previous is None or data.release_at < previous.release_at:
            by_id[cid] = data
    return sorted(by_id.values(), key=lambda c: c.id)


async def fetch_avatar_list(http: httpx.AsyncClient, body: str = "girl") -> list[CharacterData]:
    response = await http.get(YATTA_AVATAR_URL, timeout=30)
    response.raise_for_status()
    return parse_avatar_list(response.json(), body)
