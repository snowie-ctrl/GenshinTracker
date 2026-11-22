"""Write sync results. Only account-data tables are touched here."""
from datetime import datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db.models import (
    ChallengeRun, GameCharacter, GameMaterial, GameMeta, GapRun, HoyolabSnapshot, LiveNotes, MaterialGap,
    MaterialTotal, OwnedArtifact, OwnedCharacter,
)
from app.sync.chronicle import ChallengeRunInfo
from app.gamedata.yatta import VARIANT_ICONS
from app.sync.hoyolab import DetailEntry, GapResult, MaterialAmount, NotesInfo, RosterEntry, TalentIds
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
        row.weapon_id = e.weapon.id or None
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
        row.weapon_id = d.weapon.id or None
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
    row.weekly_discounts_left = notes.weekly_discounts_left
    row.weekly_discounts_max = notes.weekly_discounts_max
    row.expeditions = [
        {"icon": e.icon, "finished": e.finished,
         "return_at": iso(now + timedelta(seconds=max(0, e.remaining_seconds)))}
        for e in notes.expeditions
    ]
    row.fetched_at = now
    session.flush()


TALENT_META = "talent_ids"


def save_gaps(session: Session, result: GapResult | None, snapshot: list, skipped: list[str],
              now: datetime) -> set[int]:
    """Replace gap rows with a successful result (None = nothing to calculate). Returns unknown ids."""
    session.execute(delete(MaterialGap))
    session.execute(delete(MaterialTotal))
    seen: set[int] = set()
    if result is not None:
        for cid, mats in result.per_character.items():
            merged: dict[int, list[int]] = {}
            for m in mats:
                acc = merged.setdefault(m.id, [0, 0])
                acc[0] += m.need
                acc[1] += m.short
            for mid, (need, short) in merged.items():
                if need > 0 or short > 0:
                    session.add(MaterialGap(character_id=cid, material_id=mid, need=need, short=short))
        spare: dict[int, MaterialAmount] = {m.id: m for m in result.spare}
        for m in result.total:
            extra = spare.pop(m.id, None)
            session.add(MaterialTotal(material_id=m.id, name=m.name, icon=m.icon, rarity=m.rarity,
                                      need=m.need, short=m.short, spare=extra.need if extra else 0))
            seen.add(m.id)
        for m in spare.values():
            session.add(MaterialTotal(material_id=m.id, name=m.name, icon=m.icon, rarity=m.rarity,
                                      need=0, short=0, spare=m.need))
            seen.add(m.id)
    run = session.get(GapRun, 1) or GapRun(id=1)
    run.computed_at, run.snapshot, run.ok, run.error, run.skipped = now, snapshot, True, None, list(skipped)
    session.merge(run)
    session.flush()
    known = set(session.scalars(select(GameMaterial.id)))
    return seen - known


def save_gap_failure(session: Session, error: str, now: datetime) -> None:
    run = session.get(GapRun, 1)
    if run is None:
        run = GapRun(id=1, computed_at=None, snapshot=None, skipped=[])
        session.add(run)
    run.ok = False
    run.error = error[:300]
    session.flush()


def load_talent_ids(session: Session) -> dict[int, TalentIds]:
    row = session.get(GameMeta, TALENT_META)
    return {int(k): TalentIds(*v) for k, v in (row.value or {}).items()} if row else {}


def save_talent_ids(session: Session, ids: dict[int, TalentIds]) -> None:
    session.merge(GameMeta(key=TALENT_META,
                           value={str(k): [v.normal, v.skill, v.burst] for k, v in sorted(ids.items())}))
    session.flush()


def save_snapshot(session: Session, part: str, data: dict, now: datetime) -> None:
    row = session.get(HoyolabSnapshot, part)
    if row is None:
        session.add(HoyolabSnapshot(part=part, data=data, fetched_at=now))
    else:
        row.data, row.fetched_at = data, now
    session.flush()


def save_challenge_runs(session: Session, runs: list[ChallengeRunInfo], now: datetime) -> int:
    for r in runs:
        row = session.get(ChallengeRun, (r.kind, r.season))
        if row is None:
            row = ChallengeRun(kind=r.kind, season=r.season, seen_at=now)
            session.add(row)
        row.start, row.end, row.summary, row.teams, row.updated_at = r.start, r.end, r.summary, r.teams, now
    session.flush()
    return len(runs)


def unknown_character_ids(session: Session, ids: set[int]) -> set[int]:
    return {i for i in ids if session.get(GameCharacter, i) is None and session.get(OwnedCharacter, i) is None}
