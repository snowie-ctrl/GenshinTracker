"""Match a parsed GOOD file against our catalogue and store it as the single current snapshot."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import GoodArtifactRow, GoodImport, GoodMaterial, GoodWeaponRow
from app.good.keys import KeyIndex
from app.good.parse import GoodFile
from app.settings.store import get_setting
from app.timeutil import iso

UNMATCHED_MAX = 200


@dataclass
class MatchResult:
    materials: dict[int, int] = field(default_factory=dict)
    weapons: list[dict] = field(default_factory=list)
    artifacts: list[dict] = field(default_factory=list)
    counts: dict = field(default_factory=dict)
    unmatched: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ImportSummary:
    imported_at: str
    source: str | None
    counts: dict
    unmatched: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


def _holder(index: KeyIndex, location: str, missing: set[str]) -> tuple[str | None, int | None]:
    if not location:
        return None, None
    cid = index.character(location)
    if cid is None:
        missing.add(f"character:{location}")
    return location, cid


def match_file(parsed: GoodFile, index: KeyIndex) -> MatchResult:
    out = MatchResult()
    missing: set[str] = set()
    mat = {"matched": 0, "ignored": 0, "unmatched": 0}
    for key, count in parsed.materials.items():
        mid = index.materials.get(key)
        if mid is not None:
            out.materials[mid] = out.materials.get(mid, 0) + count
            mat["matched"] += 1
        elif key in index.known_material_keys:
            mat["ignored"] += 1
        else:
            mat["unmatched"] += 1
            missing.add(f"material:{key}")
    wpn = {"matched": 0, "unmatched": 0}
    for w in parsed.weapons:
        wid = index.weapons.get(w.key)
        if wid is None:
            wpn["unmatched"] += 1
            missing.add(f"weapon:{w.key}")
            continue
        location, cid = _holder(index, w.location, missing)
        out.weapons.append({"weapon_id": wid, "level": w.level, "ascension": w.ascension,
                            "refinement": w.refinement, "location": location, "character_id": cid,
                            "lock": w.lock})
        wpn["matched"] += 1
    art = {"matched": 0, "unmatched": 0}
    for a in parsed.artifacts:
        sid = index.sets.get(a.set_key)
        if sid is None:
            art["unmatched"] += 1
            missing.add(f"set:{a.set_key}")
            continue
        location, cid = _holder(index, a.location, missing)
        out.artifacts.append({"set_id": sid, "slot": a.slot, "rarity": a.rarity, "level": a.level,
                              "main_stat": a.main_stat,
                              "substats": [{"key": k, "value": v} for k, v in a.substats],
                              "location": location, "character_id": cid, "lock": a.lock})
        art["matched"] += 1
    out.counts = {"materials": mat, "weapons": wpn, "artifacts": art}
    out.unmatched = sorted(missing)[:UNMATCHED_MAX]
    return out


def _clear(session: Session) -> None:
    for model in (GoodArtifactRow, GoodWeaponRow, GoodMaterial, GoodImport):
        session.execute(delete(model))


def replace_snapshot(session: Session, parsed: GoodFile, index: KeyIndex, now: datetime) -> ImportSummary:
    """Caller owns the transaction (use session_factory.begin()), so a failure rolls everything back."""
    m = match_file(parsed, index)
    _clear(session)
    session.add(GoodImport(id=1, imported_at=now, source=parsed.source, counts=m.counts, unmatched=m.unmatched))
    session.add_all(GoodMaterial(material_id=mid, count=n) for mid, n in m.materials.items())
    session.add_all(GoodWeaponRow(**w) for w in m.weapons)
    session.add_all(GoodArtifactRow(**a) for a in m.artifacts)
    session.flush()
    return ImportSummary(iso(now), parsed.source, m.counts, m.unmatched)


def delete_snapshot(session: Session) -> None:
    _clear(session)
    session.flush()


def import_summary(row: GoodImport) -> ImportSummary:
    return ImportSummary(iso(row.imported_at), row.source, row.counts, row.unmatched)


def good_enabled(session: Session) -> bool:
    return bool(get_setting(session, "good_import_enabled"))


def good_active(session: Session) -> GoodImport | None:
    """The current snapshot, but only while the user has GOOD import switched on."""
    return session.get(GoodImport, 1) if good_enabled(session) else None


def scan_counts(session: Session) -> dict[int, int]:
    return {r.material_id: r.count for r in session.scalars(select(GoodMaterial))}


def owned_weapons(session: Session) -> dict[int, dict]:
    rows = session.execute(select(GoodWeaponRow.weapon_id, func.count(), func.max(GoodWeaponRow.level),
                                  func.max(GoodWeaponRow.refinement)).group_by(GoodWeaponRow.weapon_id))
    return {wid: {"count": n, "best_level": lvl, "best_refinement": ref} for wid, n, lvl, ref in rows}
