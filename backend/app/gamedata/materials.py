"""Material catalogue, daily-domain schedule and weapon list from Yatta (gi.yatta.moe)."""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

from app.gamedata.yatta import WEAPONS

YATTA_BASE = "https://gi.yatta.moe/api/v2/en"

CATEGORIES: tuple[str, ...] = ("exp", "ascension", "specialty", "talent", "weapon", "enemy", "weekly", "special")
CATEGORY_LABELS = {
    "exp": "Character EXP & weapon enhancement",
    "ascension": "Character ascension",
    "specialty": "Local specialties",
    "talent": "Talent books",
    "weapon": "Weapon ascension",
    "enemy": "Common enemy drops",
    "weekly": "Weekly boss drops",
    "special": "Crowns & special",
    "other": "Other",
}
MORA_ID = 202
DREAM_SOLVENT_ID = 113021
CROWN_ID = 104319
DAY_INDEX = {"monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3, "friday": 4, "saturday": 5, "sunday": 6}
WEEKLY_RE = re.compile(r"^Lv\. \d+\+ (?P<boss>.+?) Challenge Reward$")
SPECIALTY_RE = re.compile(r"\((?P<region>[^)]+)\)")


@dataclass(frozen=True)
class MaterialData:
    id: int
    name: str
    icon: str
    rarity: int
    yatta_type: str
    category: str
    region: str | None


@dataclass(frozen=True)
class MaterialDetail:
    craft_from: int | None
    sources: list[dict]


@dataclass(frozen=True)
class DomainData:
    id: int
    name: str
    kind: str
    city: int | None
    weekdays: list[int]
    material_ids: list[int]


@dataclass(frozen=True)
class WeaponData:
    id: int
    name: str
    icon: str
    rarity: int
    weapon_type: str


def categorize(yatta_type: str, rank: int, material_id: int) -> str | None:
    if material_id == MORA_ID or yatta_type in ("characterEXPMaterial", "weaponEnhancementMaterial"):
        return "exp"
    if material_id in (DREAM_SOLVENT_ID, CROWN_ID):
        return "special"
    if yatta_type == "characterAscensionMaterial":
        return "ascension"
    if yatta_type == "characterLevelUpMaterial":
        return "weekly" if rank >= 5 else "ascension"
    if yatta_type.startswith("localSpecialty"):
        return "specialty"
    if yatta_type == "characterTalentMaterial":
        return "talent"
    if yatta_type == "weaponAscensionMaterial":
        return "weapon"
    if yatta_type == "characterandWeaponEnhancementMaterial":
        return "enemy"
    return None


def parse_material_list(payload: dict) -> list[MaterialData]:
    types = payload["data"].get("types") or {}
    out: list[MaterialData] = []
    for v in payload["data"]["items"].values():
        mid, rank, ytype = int(v["id"]), int(v["rank"]), str(v["type"])
        category = categorize(ytype, rank, mid)
        if category is None:
            continue
        region = None
        if category == "specialty":
            m = SPECIALTY_RE.search(str(types.get(ytype, "")))
            region = m["region"] if m else ytype.removeprefix("localSpecialty")
        out.append(MaterialData(mid, str(v["name"]), str(v["icon"]), rank, ytype, category, region))
    return sorted(out, key=lambda m: m.id)


def parse_material_detail(payload: dict, rarity: int) -> MaterialDetail:
    d = payload["data"]
    craft_from = None
    for ingredients in (d.get("recipe") or {}).values():
        if len(ingredients) != 1:
            continue
        (iid, info), = ingredients.items()
        if int(info.get("count", 0)) == 3 and int(info.get("rank", 0)) == rarity - 1:
            craft_from = int(iid)
            break
    sources: list[dict] = []
    for s in d.get("source") or []:
        name = str(s.get("name", "")).strip()
        if s.get("type") == "domain":
            days = sorted(DAY_INDEX[x] for x in s.get("days") or [] if x in DAY_INDEX)
            sources.append({"kind": "domain", "name": name, "days": days})
        elif (m := WEEKLY_RE.match(name)) is not None:
            sources.append({"kind": "weekly_boss", "name": m["boss"], "days": []})
        elif name and "Placeholder" not in name:
            sources.append({"kind": "text", "name": name, "days": []})
    return MaterialDetail(craft_from, sources)


def parse_daily_dungeon(payload: dict, material_ids: set[int]) -> list[DomainData]:
    found: dict[int, dict] = {}
    for day, domains in payload["data"].items():
        if day not in DAY_INDEX:
            continue
        for v in domains.values():
            name = str(v["name"])
            kind = ("talent" if name.startswith("Domain of Mastery")
                    else "weapon" if name.startswith("Domain of Forgery") else None)
            if kind is None:
                continue
            entry = found.setdefault(int(v["id"]), {"name": name, "kind": kind, "city": v.get("city"),
                                                     "days": set(), "mats": []})
            entry["days"].add(DAY_INDEX[day])
            for r in v.get("reward") or []:
                if int(r) in material_ids and int(r) not in entry["mats"]:
                    entry["mats"].append(int(r))
    return [DomainData(did, e["name"], e["kind"], e["city"], sorted(e["days"]), e["mats"])
            for did, e in sorted(found.items())]


def parse_weapon_list(payload: dict) -> list[WeaponData]:
    weapons = [WeaponData(int(v["id"]), str(v["name"]), str(v["icon"]), int(v["rank"]),
                          WEAPONS.get(v["type"], v["type"]))
               for v in payload["data"]["items"].values()]
    return sorted(weapons, key=lambda w: (-w.rarity, w.name))


async def _get_json(http: httpx.AsyncClient, path: str) -> dict:
    response = await http.get(f"{YATTA_BASE}/{path}", timeout=30)
    response.raise_for_status()
    return response.json()


async def fetch_material_list(http: httpx.AsyncClient) -> list[MaterialData]:
    return parse_material_list(await _get_json(http, "material"))


async def fetch_material_catalogue(http: httpx.AsyncClient) -> tuple[list[MaterialData], list[str]]:
    """The eight-category catalogue plus the GOOD key of every Yatta item (food, quest items...),
    so a GOOD import can tell 'not a planner material' apart from 'unknown'."""
    from app.good.keys import good_key
    payload = await _get_json(http, "material")
    keys = sorted({good_key(str(v["name"])) for v in payload["data"]["items"].values()} - {""})
    return parse_material_list(payload), keys


async def fetch_material_detail(http: httpx.AsyncClient, material_id: int, rarity: int) -> MaterialDetail:
    return parse_material_detail(await _get_json(http, f"material/{material_id}"), rarity)


async def fetch_daily_dungeon(http: httpx.AsyncClient, material_ids: set[int]) -> list[DomainData]:
    return parse_daily_dungeon(await _get_json(http, "dailyDungeon"), material_ids)


async def fetch_weapon_list(http: httpx.AsyncClient) -> list[WeaponData]:
    return parse_weapon_list(await _get_json(http, "weapon"))
