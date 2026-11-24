"""Profile page: pure functions over the profile snapshot and challenge history."""
from __future__ import annotations

from collections import Counter
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChallengeRun, GameCharacter, OwnedCharacter
from app.events.view import parse_iso
from app.gamedata.kinds import ELEMENTS, WEAPON_TYPES
from app.profile.showcase import collapse_travelers
from app.traveler.store import current_element_id

KINDS = ("abyss", "theater", "stygian")
def _region(r: dict) -> dict:
    rep = r.get("reputation")
    return {"id": r["id"], "name": r["name"], "explored": r["explored"],
            "reputation": rep if rep is not None and rep > 0 else None, "icon": r.get("icon") or None,
            "offerings": [{"name": o["name"], "level": o["level"], "icon": o.get("icon") or None}
                          for o in r.get("offerings") or []],
            "areas": [dict(a) for a in r.get("areas") or []]}


def _bosses(regions: list[dict]) -> list[dict]:
    kills: Counter = Counter()
    for r in regions:
        for b in r.get("bosses") or []:
            kills[b["name"]] += b["kills"]
    return [{"name": n, "kills": k} for n, k in sorted(kills.items(), key=lambda kv: (-kv[1], kv[0]))]


def profile_view(data: dict | None, name: str = "") -> dict | None:
    if data is None:
        return None
    s = data["stats"]
    chests = [{"label": k.capitalize(), "value": v} for k, v in s["chests"].items()]
    oculi = [{"label": k.capitalize(), "value": v} for k, v in s["oculi"].items() if v]
    tiles = [
        {"key": "characters", "label": "Characters", "value": s["characters"]},
        {"key": "friendship", "label": "Max friendship", "value": s.get("max_friendship")},
        {"key": "waypoint", "label": "Waypoints", "value": s["waypoints"]},
        {"key": "domain", "label": "Domains", "value": s["domains"]},
        {"key": "abyss", "label": "Spiral Abyss", "value": s.get("abyss") or None},
        {"key": "chest", "label": "Chests", "value": sum(c["value"] for c in chests), "detail": chests},
        {"key": "oculus", "label": "Oculi", "value": sum(o["value"] for o in oculi), "detail": oculi},
    ]
    return {
        "header": {"name": name.strip() or "Traveler", "ar": s["ar"], "days_active": s["days_active"],
                   "achievements": s["achievements"]},
        "tiles": [t for t in tiles if t["value"] is not None],
        "regions": [_region(r) for r in sorted(data["regions"], key=lambda r: r["id"])],
        "teapot": data.get("teapot"),
        "bosses": _bosses(data["regions"]),
    }


def roster_view(session: Session) -> dict:
    game = {c.id: c for c in session.scalars(select(GameCharacter))}
    owned = collapse_travelers(list(session.scalars(select(OwnedCharacter))), current_element_id(session))
    elements = dict.fromkeys(ELEMENTS, 0)
    weapons = dict.fromkeys(WEAPON_TYPES, 0)
    rarity = {"5": 0, "4": 0}
    for o in owned:
        g = game.get(o.character_id)
        element = o.element or (g.element if g else None)
        if element in elements:
            elements[element] += 1
        if g is not None and g.weapon_type in weapons:
            weapons[g.weapon_type] += 1
        if g is not None and str(g.rarity) in rarity:
            rarity[str(g.rarity)] += 1
    return {"total": len(owned), "elements": elements, "weapon_types": weapons, "rarity": rarity,
            "constellations": sum(o.constellation for o in owned),
            "c6": sum(1 for o in owned if o.constellation >= 6)}


def _names(session: Session) -> dict[int, dict]:
    out = {c.id: {"id": c.id, "name": c.name, "icon": c.icon} for c in session.scalars(select(GameCharacter))}
    for o in session.scalars(select(OwnedCharacter)):
        out.setdefault(o.character_id, {"id": o.character_id, "name": o.name, "icon": o.icon})
    return out


def _run(r: ChallengeRun, names: dict[int, dict]) -> dict:
    team = lambda ids: [names.get(i, {"id": i, "name": f"Character {i}", "icon": None}) for i in ids]  # noqa: E731
    return {"season": r.season, "start": r.start, "end": r.end, "summary": r.summary,
            "teams": [team(t) for t in r.teams or []]}


def challenge_views(session: Session, now: datetime) -> dict:
    names = _names(session)
    out = {}
    for kind in KINDS:
        rows = sorted(session.scalars(select(ChallengeRun).where(ChallengeRun.kind == kind)),
                      key=lambda r: (r.end or "", r.start or ""), reverse=True)
        current = next((r for r in rows if (parse_iso(r.end) or now) > now), None)
        out[kind] = {"current": _run(current, names) if current is not None else None,
                     "past": [_run(r, names) for r in rows if r is not current]}
    return out
