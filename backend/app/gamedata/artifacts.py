"""Artifact set names and icons from Yatta (gi.yatta.moe /reliquary); used to match GOOD setKeys."""
from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.gamedata.materials import _get_json


@dataclass(frozen=True)
class ArtifactSetData:
    id: int
    name: str
    icon: str
    sort_order: int


def parse_reliquary_list(payload: dict) -> list[ArtifactSetData]:
    sets = [ArtifactSetData(int(v["id"]), str(v["name"]), str(v["icon"]), int(v.get("sortOrder") or 0))
            for v in payload["data"]["items"].values()]
    return sorted(sets, key=lambda a: a.id)


async def fetch_reliquary_list(http: httpx.AsyncClient) -> list[ArtifactSetData]:
    return parse_reliquary_list(await _get_json(http, "reliquary"))
