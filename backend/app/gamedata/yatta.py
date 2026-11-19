"""Character list from Yatta (gi.yatta.moe), normalised to our ids and display names."""
from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

YATTA_AVATAR_URL = "https://gi.yatta.moe/api/v2/en/avatar"

TRAVELER_ID = 10000005
MANEKIN_ID = 10000117
_ALIASES = {10000005: TRAVELER_ID, 10000007: TRAVELER_ID, 10000117: MANEKIN_ID, 10000118: MANEKIN_ID}
VARIANT_ICONS = {
    10000005: "UI_AvatarIcon_PlayerBoy",
    10000007: "UI_AvatarIcon_PlayerGirl",
    10000117: "UI_AvatarIcon_MannequinBoy",
    10000118: "UI_AvatarIcon_MannequinGirl",
}
_FIXED_NAMES = {TRAVELER_ID: "Traveler", MANEKIN_ID: "Manekin"}

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


def canonical_id(raw: int | str) -> int:
    n = int(str(raw).split("-")[0])
    return _ALIASES.get(n, n)


def splash_for(icon: str) -> str:
    return icon.replace("UI_AvatarIcon_", "UI_Gacha_AvatarImg_", 1)


def slugify(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def parse_avatar_list(payload: dict) -> list[CharacterData]:
    by_id: dict[int, CharacterData] = {}
    for key, v in payload["data"]["items"].items():
        cid = canonical_id(key)
        name = _FIXED_NAMES.get(cid, v["name"])
        icon = VARIANT_ICONS.get(cid, v["icon"])
        element = None if cid in _FIXED_NAMES else ELEMENTS.get(v.get("element") or "")
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


async def fetch_avatar_list(http: httpx.AsyncClient) -> list[CharacterData]:
    response = await http.get(YATTA_AVATAR_URL, timeout=30)
    response.raise_for_status()
    return parse_avatar_list(response.json())
