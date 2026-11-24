"""Dashboard Artifact domains: which domains to run and for whom, in Build priority order (sub-project 8)."""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.artifacts.gear import check_for
from app.db.models import CharacterGoal, GameArtifactDomain, GameArtifactSet, GameCharacter, OwnedCharacter
from app.planner.order import build_order

HINT = "Set artifact targets on a character's Build tab to plan domains here"


def group_artifact_domains(builds: list[dict], sets: dict[int, dict], domains: list[dict]) -> dict:
    """`builds`: Build characters in priority order, each {character, target, done, check}.
    A character counts when its target has sets, it is not ticked done and its check is "missing"."""
    wanted: dict[int, list[dict]] = {}
    best: dict[int, int] = {}
    for rank, b in enumerate(builds):
        target_sets = (b["target"] or {}).get("sets") or []
        if not target_sets or b["done"] or b["check"]["status"] != "missing":
            continue
        worn = {e["set_id"]: e["equipped"] for e in b["check"].get("sets", [])}
        for e in target_sets:
            sid = e["set_id"]
            wanted.setdefault(sid, []).append({**b["character"], "pieces": e["pieces"], "equipped": worn.get(sid, 0)})
            best.setdefault(sid, rank)

    def set_row(sid: int) -> dict:
        info = sets.get(sid) or {"id": sid, "name": f"Set {sid}", "icon": None}
        chars = wanted.get(sid, [])
        return {"id": sid, "name": info["name"], "icon": info["icon"], "needed": bool(chars), "characters": chars}

    shown, covered = [], set()
    for d in domains:
        needed = [sid for sid in d["set_ids"] if sid in wanted]
        if not needed:
            continue
        covered.update(d["set_ids"])
        row = {k: d[k] for k in ("id", "name", "entrance", "region", "elements")}
        row["sets"] = [set_row(sid) for sid in d["set_ids"]]
        shown.append((min(best[sid] for sid in needed), d["name"], row))
    shown.sort(key=lambda t: (t[0], t[1]))
    other = sorted((set_row(sid) for sid in wanted if sid not in covered), key=lambda r: (best[r["id"]], r["name"]))
    has_targets = any((b["target"] or {}).get("sets") for b in builds)
    return {"domains": [r for _, _, r in shown], "other": other,
            "hint": HINT if builds and not has_targets else None}


def artifact_domains_view(s: Session) -> dict:
    goals = {r.character_id: r for r in s.scalars(select(CharacterGoal))}
    games = {g.id: g for g in s.scalars(select(GameCharacter))}
    owned = {o.character_id: o for o in s.scalars(select(OwnedCharacter))}
    builds = []
    for cid in build_order(s):
        g, o, row = games.get(cid), owned.get(cid), goals[cid]
        if g is None and o is None:
            continue
        icon = (o.icon if o is not None and o.icon else None) or (g.icon if g is not None else None)
        builds.append({
            "character": {"id": cid, "name": g.name if g is not None else o.name,
                          "slug": g.slug if g is not None else f"id-{cid}", "icon": icon},
            "target": row.artifact_target, "done": bool(row.artifacts_done),
            "check": check_for(s, cid, row.artifact_target)})
    sets = {a.id: {"id": a.id, "name": a.name, "icon": a.icon} for a in s.scalars(select(GameArtifactSet))}
    domains = [{"id": d.id, "name": d.name, "entrance": d.entrance, "region": d.region, "elements": d.elements,
                "set_ids": d.set_ids} for d in s.scalars(select(GameArtifactDomain).order_by(GameArtifactDomain.id))]
    return group_artifact_domains(builds, sets, domains)
