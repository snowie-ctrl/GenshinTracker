"""Traveler element state (user data) and the fan-out of shared Traveler fields to every owned element.
HoYoLAB only reports the current element; other elements keep what was last seen or typed in."""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, GameMeta, OwnedArtifact, OwnedCharacter, TravelerElement
from app.gamedata.traveler import (TRAVELER_ELEMENTS, TRAVELER_IDS, TRAVELER_PENDING, body_icon, body_of,
                                   element_of, traveler_id, traveler_name)
from app.settings.store import get_setting, set_setting
from app.timeutil import utcnow

TALENT_META = "talent_ids"   # same key as app.sync.persist.TALENT_META


def get_or_create(s: Session, element_id: int) -> TravelerElement:
    row = s.get(TravelerElement, element_id)
    if row is None:
        row = TravelerElement(element_id=element_id, seen=False, unlocked=False, talent_normal=1, talent_skill=1,
                              talent_burst=1, constellation=0, source="manual", updated_at=utcnow())
        s.add(row)
        s.flush()
    return row


def owned_elements(s: Session) -> list[int]:
    return sorted(r.element_id for r in s.scalars(select(TravelerElement)) if r.seen or r.unlocked)


def current_element_id(s: Session) -> int | None:
    el = get_setting(s, "traveler_current_element")
    return traveler_id(el) if el in TRAVELER_ELEMENTS else None


def resolve(s: Session, cid: int) -> int | None:
    return current_element_id(s) if cid == TRAVELER_PENDING else cid


def _set_body(s: Session, body: str) -> None:
    if get_setting(s, "traveler_body") == body:
        return
    set_setting(s, "traveler_body", body)
    icon = body_icon(body)
    for g in s.scalars(select(GameCharacter).where(GameCharacter.id.in_(list(TRAVELER_IDS)))):
        g.icon, g.splash = icon, icon.replace("UI_AvatarIcon_", "UI_Gacha_AvatarImg_", 1)
    meta = s.get(GameMeta, TALENT_META)
    if meta is not None and meta.value:
        meta.value = {k: v for k, v in meta.value.items() if int(k) not in TRAVELER_IDS}
    s.flush()


def record_current(s: Session, element_id: int, raw_id: int, constellation: int) -> None:
    set_setting(s, "traveler_current_element", element_of(element_id))
    body = body_of(raw_id)
    if body is not None:
        _set_body(s, body)
    row = get_or_create(s, element_id)
    row.seen, row.constellation, row.source, row.updated_at = True, constellation, "sync", utcnow()
    s.flush()


def record_current_talents(s: Session, element_id: int, normal: int, skill: int, burst: int) -> None:
    row = get_or_create(s, element_id)
    row.talent_normal, row.talent_skill, row.talent_burst = normal, skill, burst
    row.source, row.updated_at = "sync", utcnow()
    s.flush()


def refresh_owned(s: Session, now: datetime) -> set[int]:
    """Copy the current element's shared fields to every other owned element; drop elements no longer owned."""
    current = current_element_id(s)
    src = s.get(OwnedCharacter, current) if current is not None else None
    if src is None:
        return {i for i in TRAVELER_IDS if s.get(OwnedCharacter, i) is not None}
    owned = set(owned_elements(s)) | {current}
    for cid in TRAVELER_IDS:
        if cid == current:
            continue
        if cid not in owned:
            s.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id == cid))
            s.execute(delete(OwnedCharacter).where(OwnedCharacter.character_id == cid))
            continue
        te = get_or_create(s, cid)
        row = s.get(OwnedCharacter, cid)
        if row is None:
            row = OwnedCharacter(character_id=cid, stats=[])
            s.add(row)
        row.name, row.element, row.icon = traveler_name(element_of(cid)), element_of(cid), src.icon
        row.level, row.friendship = src.level, src.friendship
        row.constellation = te.constellation
        row.talent_normal, row.talent_skill, row.talent_burst = te.talent_normal, te.talent_skill, te.talent_burst
        row.weapon_name, row.weapon_icon, row.weapon_rarity = src.weapon_name, src.weapon_icon, src.weapon_rarity
        row.weapon_level, row.weapon_refinement, row.weapon_id = src.weapon_level, src.weapon_refinement, src.weapon_id
        row.stats, row.synced_at = list(src.stats or []), now
        s.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id == cid))
        for a in s.scalars(select(OwnedArtifact).where(OwnedArtifact.character_id == current)).all():
            s.add(OwnedArtifact(character_id=cid, slot=a.slot, set_name=a.set_name, rarity=a.rarity, level=a.level,
                                main_stat=a.main_stat, substats=list(a.substats), icon=a.icon))
    s.flush()
    return owned
