"""Profile page: pure functions over the profile snapshot and challenge history."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import ChallengeRun, GameCharacter, HoyolabSnapshot, OwnedCharacter
from app.events.view import parse_iso
from app.timeutil import iso

KINDS = ("abyss", "theater", "stygian")
TILES = (("achievements", "Achievements"), ("characters", "Characters"), ("waypoints", "Waypoints"),
         ("domains", "Domains"))


def _region(r: dict) -> dict:
    rep = r.get("reputation")
    return {**r, "reputation": rep if rep is not None and rep > 0 else None}


def profile_view(data: dict | None) -> dict | None:
    if data is None:
        return None
    s = data["stats"]
    return {
        "ar": s["ar"], "days_active": s["days_active"],
        "tiles": [{"label": label, "value": s[key]} for key, label in TILES],
        "chests": [{"label": k.capitalize(), "value": v} for k, v in s["chests"].items()],
        "oculi": [{"label": k.capitalize(), "value": v} for k, v in s["oculi"].items() if v],
        "regions": [_region(r) for r in sorted(data["regions"], key=lambda r: r["id"])],
    }


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


def profile_summary(session: Session, now: datetime) -> dict:
    snap = session.get(HoyolabSnapshot, "profile")
    views = challenge_views(session, now)
    abyss, theater = views["abyss"]["current"], views["theater"]["current"]
    return {"ar": snap.data["stats"]["ar"] if snap is not None else None,
            "fetched_at": iso(snap.fetched_at) if snap is not None else None,
            "abyss_stars": abyss["summary"].get("stars") if abyss else None,
            "theater_act": theater["summary"].get("act") if theater else None}
