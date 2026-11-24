# backend/app/profile/showcase.py
"""Profile showcase (sub-project 7): up to 8 owned characters with their build, from synced data only."""
from __future__ import annotations

import re
from collections import Counter

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, OwnedArtifact, OwnedCharacter
from app.settings.store import get_setting

SHOWCASE_MAX = 8
HIDDEN_STATS = {"Max Stamina"}
ZERO = re.compile(r"^-?0+(\.0+)?%?$")
PERCENT_SUB = re.compile(r"^(?P<name>.+?)\s+(?P<value>-?\d+(?:\.\d+)?)%$")


def crit_value(artifacts: list[OwnedArtifact]) -> float:
    """CRIT Rate × 2 + CRIT DMG over artifact substats (percent substats only)."""
    total = 0.0
    for a in artifacts:
        for sub in a.substats or []:
            m = PERCENT_SUB.match(sub.strip())
            if m is None:
                continue
            if m["name"] == "CRIT Rate":
                total += 2 * float(m["value"])
            elif m["name"] == "CRIT DMG":
                total += float(m["value"])
    return round(total, 1)


def set_summary(artifacts: list[OwnedArtifact]) -> str:
    counts = Counter(a.set_name for a in artifacts)
    four = sorted(n for n, c in counts.items() if c >= 4)
    if four:
        return f"{four[0]} 4"
    return " · ".join(f"{n} 2" for n in sorted(n for n, c in counts.items() if c >= 2))


def default_ids(owned: list[OwnedCharacter], game: dict[int, GameCharacter]) -> list[int]:
    def key(o: OwnedCharacter) -> tuple:
        g = game.get(o.character_id)
        return (-o.level, -o.constellation, -(g.rarity if g else 0), o.name)
    return [o.character_id for o in sorted(owned, key=key)][:SHOWCASE_MAX]


def _entry(o: OwnedCharacter, g: GameCharacter | None, arts: list[OwnedArtifact]) -> dict:
    return {
        "id": o.character_id, "slug": g.slug if g else None, "name": o.name, "rarity": g.rarity if g else None,
        "element": o.element or (g.element if g else None), "icon": o.icon or (g.icon if g else None),
        "level": o.level, "constellation": o.constellation, "friendship": o.friendship,
        "talents": {"normal": o.talent_normal, "skill": o.talent_skill, "burst": o.talent_burst},
        "weapon": {"name": o.weapon_name, "icon": o.weapon_icon, "level": o.weapon_level,
                   "refinement": o.weapon_refinement, "rarity": o.weapon_rarity},
        "stats": [s for s in o.stats or [] if s.get("name") not in HIDDEN_STATS
                  and not ZERO.match(str(s.get("value", "")).strip())],
        "artifacts": [{"slot": a.slot, "set_name": a.set_name, "icon": a.icon, "rarity": a.rarity, "level": a.level,
                       "main_stat": a.main_stat, "substats": list(a.substats or [])}
                      for a in sorted(arts, key=lambda a: a.slot)],
        "sets": set_summary(arts), "crit_value": crit_value(arts),
    }


def showcase_view(session: Session) -> dict:
    owned = {o.character_id: o for o in session.scalars(select(OwnedCharacter))}
    game = {g.id: g for g in session.scalars(select(GameCharacter))}
    arts: dict[int, list[OwnedArtifact]] = {}
    for a in session.scalars(select(OwnedArtifact)):
        arts.setdefault(a.character_id, []).append(a)
    saved = [i for i in get_setting(session, "profile_showcase") or [] if isinstance(i, int)]
    ids = [i for i in saved if i in owned][:SHOWCASE_MAX] if saved else default_ids(list(owned.values()), game)
    return {"mode": "custom" if saved else "auto",
            "entries": [_entry(owned[i], game.get(i), arts.get(i, [])) for i in ids]}


def owned_options(session: Session) -> list[dict]:
    game = {g.id: g for g in session.scalars(select(GameCharacter))}
    rows = sorted(session.scalars(select(OwnedCharacter)), key=lambda o: o.name)
    return [{"id": o.character_id, "name": o.name,
             "icon": o.icon or (game[o.character_id].icon if o.character_id in game else None)} for o in rows]


def validate_ids(session: Session, ids: list[int]) -> str | None:
    if len(ids) > SHOWCASE_MAX:
        return f"Pick at most {SHOWCASE_MAX} characters."
    if len(set(ids)) != len(ids):
        return "Each character can be shown once."
    owned = set(session.scalars(select(OwnedCharacter.character_id)))
    if any(i not in owned for i in ids):
        return "Only characters you own can be shown."
    return None
