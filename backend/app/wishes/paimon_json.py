"""paimon.moe data backup ("Settings → Export data", paimon-moe-local-data.json) → IncomingWish rows.

Pulls carry an item slug, a banner type code, a time and a pity count, but no pull id and no rarity:
names and rarities come from game data via the same slug normalisation as banners. File order is kept."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, GameWeapon
from app.wishes.banners import name_slug
from app.wishes.types import (POOL_BY_GACHA_TYPE, SINGLE_TYPE, UID_MISMATCH, ImportFailed, IncomingWish,
                              bad_rows_message, normalize_time)

KEY_PREFIX = "wish-counter-"
POOL_BY_KEY = {"wish-counter-character-event": "character", "wish-counter-weapon-event": "weapon",
               "wish-counter-standard": "standard", "wish-counter-beginners": "beginner",
               "wish-counter-chronicled": "chronicled"}
NOT_PAIMON = "This file is not a paimon.moe data backup."
UNKNOWN_ITEMS_HINT = "Refresh game data in Settings, then try again."


@dataclass(frozen=True)
class Item:
    name: str
    item_type: str
    rarity: int


def is_paimon_backup(data: object) -> bool:
    return isinstance(data, dict) and any(isinstance(k, str) and k in POOL_BY_KEY for k in data)


def item_index(session: Session) -> dict[str, Item]:
    out = {name_slug(n): Item(n, "weapon", r)
           for n, r in session.execute(select(GameWeapon.name, GameWeapon.rarity))}
    out.update({name_slug(n): Item(n, "character", r)
                for n, r in session.execute(select(GameCharacter.name, GameCharacter.rarity))})
    return out


def parse_paimon_json(data: object, uid: int, items: dict[str, Item]) -> list[IncomingWish]:
    if not is_paimon_backup(data):
        raise ImportFailed(NOT_PAIMON)
    file_uid = data.get("wish-uid")
    if file_uid not in (None, "") and str(file_uid).strip() != str(uid):
        raise ImportFailed(UID_MISMATCH)
    out: list[IncomingWish] = []
    errors: list[str] = []
    unknown: set[str] = set()
    for key, value in data.items():
        if not (isinstance(key, str) and key.startswith(KEY_PREFIX)):
            continue
        pulls = value.get("pulls") if isinstance(value, dict) else None
        if pulls is None:
            continue                                   # e.g. wish-counter-setting
        pool = POOL_BY_KEY.get(key)
        if pool is None:
            errors.append(f'"{key}": unknown banner')
            continue
        if not isinstance(pulls, list):
            errors.append(f'"{key}": pulls is not a list')
            continue
        for n, p in enumerate(pulls, start=1):
            try:
                if not isinstance(p, dict):
                    raise ValueError("not an object")
                slug = p.get("id")
                if not isinstance(slug, str) or not slug.strip():
                    raise ValueError("missing item")
                item = items.get(name_slug(slug))
                if item is None:
                    unknown.add(slug)
                    continue
                code = str(p.get("code", "")).strip()
                gacha_type = code if POOL_BY_GACHA_TYPE.get(code) == pool else SINGLE_TYPE.get(pool)
                out.append(IncomingWish(id=None, pool=pool, gacha_type=gacha_type,
                                        time=normalize_time(p.get("time")), name=item.name,
                                        item_type=item.item_type, rarity=item.rarity))
            except (ValueError, TypeError, OverflowError) as e:
                errors.append(f'"{key}" pull {n}: {e}')
    if unknown:
        shown = ", ".join(sorted(unknown)[:10])
        more = f" (and {len(unknown) - 10} more)" if len(unknown) > 10 else ""
        errors.insert(0, f"unknown items {shown}{more}. {UNKNOWN_ITEMS_HINT}")
    if errors:
        raise ImportFailed(bad_rows_message(errors))
    return out
