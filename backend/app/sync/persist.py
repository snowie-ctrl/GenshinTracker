"""Write sync results. Only account-data tables are touched here."""
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, LiveNotes, OwnedArtifact, OwnedCharacter
from app.gamedata.yatta import VARIANT_ICONS
from app.sync.hoyolab import DetailEntry, NotesInfo, RosterEntry
from app.timeutil import iso


def save_roster(session: Session, entries: list[RosterEntry], now: datetime) -> set[int]:
    known = set(session.scalars(select(GameCharacter.id)))
    seen: set[int] = set()
    for e in entries:
        seen.add(e.id)
        row = session.get(OwnedCharacter, e.id)
        if row is None:
            row = OwnedCharacter(character_id=e.id, stats=[])
            session.add(row)
        row.name = e.name
        row.element = e.element
        row.icon = VARIANT_ICONS.get(e.raw_id)
        row.level = e.level
        row.constellation = e.constellation
        row.friendship = e.friendship
        row.weapon_name = e.weapon.name
        row.weapon_icon = e.weapon.icon
        row.weapon_rarity = e.weapon.rarity
        row.weapon_level = e.weapon.level
        row.weapon_refinement = e.weapon.refinement
        row.synced_at = now
    session.flush()
    session.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id.not_in(seen)))
    session.execute(delete(OwnedCharacter).where(OwnedCharacter.character_id.not_in(seen)))
    return seen - known


def save_details(session: Session, details: list[DetailEntry]) -> None:
    for d in details:
        row = session.get(OwnedCharacter, d.id)
        if row is None:
            continue
        row.talent_normal, row.talent_skill, row.talent_burst = d.normal, d.skill, d.burst
        row.weapon_name = d.weapon.name
        row.weapon_icon = d.weapon.icon
        row.weapon_rarity = d.weapon.rarity
        row.weapon_level = d.weapon.level
        row.weapon_refinement = d.weapon.refinement
        row.stats = list(d.stats)
        session.execute(delete(OwnedArtifact).where(OwnedArtifact.character_id == d.id))
        for a in d.artifacts:
            session.add(OwnedArtifact(
                character_id=d.id, slot=a.slot, set_name=a.set_name, rarity=a.rarity, level=a.level,
                main_stat=a.main_stat, substats=list(a.substats), icon=a.icon,
            ))
    session.flush()


def save_notes(session: Session, notes: NotesInfo, now: datetime) -> None:
    row = session.get(LiveNotes, 1)
    if row is None:
        row = LiveNotes(id=1)
        session.add(row)
    row.resin = notes.resin
    row.resin_max = notes.resin_max
    row.resin_full_at = now + timedelta(seconds=max(0, notes.resin_recovery_seconds))
    row.commissions_done = notes.commissions_done
    row.commissions_max = notes.commissions_max
    row.realm_currency = notes.realm_currency
    row.realm_currency_max = notes.realm_currency_max
    row.expeditions = [
        {"icon": e.icon, "finished": e.finished,
         "return_at": iso(now + timedelta(seconds=max(0, e.remaining_seconds)))}
        for e in notes.expeditions
    ]
    row.fetched_at = now
    session.flush()
