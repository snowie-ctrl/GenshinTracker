"""Artifact domains from genshin-db (MIT, genshin-db-api.vercel.app): which domain drops which 5★ sets.
Public game data only; the request carries no cookie, UID or email (sub-project 8)."""
from __future__ import annotations

import re
from dataclasses import dataclass

import httpx

GENSHINDB_DOMAINS_URL = "https://genshin-db-api.vercel.app/api/v5/domains"
GENSHINDB_PARAMS = {"query": "names", "matchCategories": "true", "verboseCategories": "true"}
RELIC = "UI_ABYSSUS_RELIC"
_TIER = re.compile(r"\s+[IVX]+$")


@dataclass(frozen=True)
class ArtifactDomainData:
    id: int
    name: str
    entrance: str
    region: str | None
    elements: list[str]
    set_ids: list[int]


def base_name(name: str) -> str:
    return _TIER.sub("", name.strip())


def _valid(d) -> bool:
    try:
        return (d.get("domainType") == RELIC and isinstance(d["rewardPreview"], list)
                and int(d["id"]) > 0 and bool(str(d["name"]).strip()))
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _level(d: dict) -> int:
    try:
        return int(d.get("recommendedLevel") or 0)
    except (TypeError, ValueError):
        return 0


def parse_artifact_domains(payload, set_ids_by_name: dict[str, int]) -> tuple[list[ArtifactDomainData], list[str]]:
    """Group tiers by name, take the top tier's 5★ set names, map them to our set ids.
    Returns (domains sorted by id, sorted unmatched set names). Malformed entries are skipped."""
    if not isinstance(payload, list):
        raise ValueError("genshin-db domains: expected a list")
    groups: dict[str, list[dict]] = {}
    for d in payload:
        if isinstance(d, dict) and _valid(d):
            groups.setdefault(base_name(str(d["name"])), []).append(d)
    domains: list[ArtifactDomainData] = []
    unmatched: set[str] = set()
    for name, tiers in groups.items():
        top = max(tiers, key=_level)
        names = list(dict.fromkeys(str(r["name"]) for r in top["rewardPreview"]
                                   if isinstance(r, dict) and r.get("rarity") == 5 and r.get("name")))
        ids: list[int] = []
        for n in names:
            if n in set_ids_by_name:
                ids.append(set_ids_by_name[n])
            else:
                unmatched.add(n)
        if not ids:
            continue
        domains.append(ArtifactDomainData(
            id=min(int(t["id"]) for t in tiers), name=name,
            entrance=str(top.get("entranceName") or name), region=(str(top["regionName"]) if top.get("regionName") else None),
            elements=[str(e) for e in (top.get("recommendedElements") or [])], set_ids=ids))
    return sorted(domains, key=lambda d: d.id), sorted(unmatched)


async def fetch_domains(http: httpx.AsyncClient) -> object:
    response = await http.get(GENSHINDB_DOMAINS_URL, params=GENSHINDB_PARAMS, timeout=30)
    response.raise_for_status()
    return response.json()
