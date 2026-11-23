"""Team payloads for the API. Character rows come in already built by the characters API."""
from __future__ import annotations

from app.planner.data import PlannerData
from app.teams.shortfall import team_progress, team_shortfall
from app.teams.store import BUILD_TAG_ID, tag_dict

MEMBER_KEYS = ("id", "name", "slug", "icon", "element", "rarity", "owned", "goal", "status", "prefarming",
               "level", "talents", "weapon", "progress")
TOP_MATERIALS = 5


def placeholder(cid: int) -> dict:
    return {"id": cid, "name": f"Unknown character {cid}", "slug": None, "icon": None, "element": None,
            "rarity": 0, "owned": False, "goal": "none", "status": "unobtained", "prefarming": False,
            "level": None, "talents": None, "weapon": None, "progress": None}


def member_view(char: dict | None, cid: int, role: str, artifact_line: str, in_build_team: bool,
                calculated: bool) -> dict:
    base = {k: char[k] for k in MEMBER_KEYS} if char is not None else placeholder(cid)
    is_build = base["goal"] == "build"
    return {**base, "role": role, "artifact_line": artifact_line,
            "not_building": in_build_team and not is_build,
            "not_calculated": is_build and not calculated}


def team_view(team, members, tags, chars: dict[int, dict], arts: dict[int, str], data: PlannerData,
              index: dict[int, dict]) -> dict:
    has_build = any(t.id == BUILD_TAG_ID for t in tags)
    views = [member_view(chars.get(m.character_id), m.character_id, m.role, arts.get(m.character_id, ""), has_build,
                         m.character_id in data.calculated)
             for m in members]
    build = [v for v in views if v["goal"] == "build"]
    counted = [v["id"] for v in build if not v["not_calculated"]]
    return {"id": team.id, "name": team.name, "notes": team.notes, "sort_order": team.sort_order,
            "tags": [tag_dict(t) for t in tags], "has_build_tag": has_build, "members": views,
            "shortfall": team_shortfall(data, counted, index) if build else None,
            "progress": team_progress([v["progress"] for v in build])}


def build_team_cards(views: list[dict]) -> list[dict]:
    cards = []
    for v in views:
        if not v["has_build_tag"]:
            continue
        farm = sorted((m for m in (v["shortfall"] or []) if m["to_farm"] > 0),
                      key=lambda m: (-m["to_farm"], m["name"]))
        build = [m for m in v["members"] if m["goal"] == "build"]
        cards.append({"id": v["id"], "name": v["name"],
                      "all_calculated": all(not m["not_calculated"] for m in build),
                      "short_count": sum(1 for m in (v["shortfall"] or []) if m["short"] > 0),
                      "members": [{k: m[k] for k in ("id", "name", "slug", "icon")} for m in v["members"]],
                      "progress": v["progress"], "top": farm[:TOP_MATERIALS],
                      "more": max(0, len(farm) - TOP_MATERIALS), "has_shortfall": v["shortfall"] is not None})
    return cards
