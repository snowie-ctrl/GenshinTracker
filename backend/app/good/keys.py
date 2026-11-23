"""GOOD keys: the English name in PascalCase with punctuation removed, e.g. "Wolf's Gravestone" -> WolfsGravestone."""
from __future__ import annotations

import logging
import re
import unicodedata
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

log = logging.getLogger(__name__)

_WORD_SPLIT = re.compile(r"[\s\-]+")
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


def good_key(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    parts = (_NON_ALNUM.sub("", w) for w in _WORD_SPLIT.split(ascii_name))
    return "".join(p[0].upper() + p[1:] for p in parts if p)


def _index(rows, label: str) -> dict[str, int]:
    """First id wins on a key collision; collisions are logged by key only."""
    out: dict[str, int] = {}
    for rid, name in rows:
        key = good_key(name)
        if not key:
            continue
        if key in out and out[key] != rid:
            log.info("GOOD %s key collision: %s", label, key)
            continue
        out[key] = rid
    return out


@dataclass(frozen=True)
class KeyIndex:
    materials: dict[str, int]
    weapons: dict[str, int]
    sets: dict[str, int]
    characters: dict[str, int]
    known_material_keys: frozenset[str]

    @classmethod
    def build(cls, session: Session) -> "KeyIndex":
        from app.db.models import GameArtifactSet, GameCharacter, GameMaterial, GameMeta, GameWeapon
        from app.gamedata.service import META_MAT_KEYS
        meta = session.get(GameMeta, META_MAT_KEYS)
        return cls(
            materials=_index(session.execute(select(GameMaterial.id, GameMaterial.name)
                                             .order_by(GameMaterial.sort_order, GameMaterial.id)), "material"),
            weapons=_index(session.execute(select(GameWeapon.id, GameWeapon.name).order_by(GameWeapon.id)), "weapon"),
            sets=_index(session.execute(select(GameArtifactSet.id, GameArtifactSet.name)
                                        .order_by(GameArtifactSet.id)), "set"),
            characters=_index(session.execute(select(GameCharacter.id, GameCharacter.name)
                                              .order_by(GameCharacter.id)), "character"),
            known_material_keys=frozenset(meta.value or []) if meta is not None else frozenset(),
        )

    def character(self, key: str) -> int | None:
        from app.gamedata.yatta import MANEKIN_ID
        TRAVELER_ID = 10000005  # Task 5
        if not key:
            return None
        if key.startswith("Traveler"):
            return TRAVELER_ID
        if key in ("Manekin", "Manekina"):
            return MANEKIN_ID
        return self.characters.get(key)
