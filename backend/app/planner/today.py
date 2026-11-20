"""Dashboard: domains open today and weekly bosses, limited to what is still to farm."""
from __future__ import annotations

from app.planner.data import PlannerData

SUNDAY = 6


def _characters(materials: list[dict]) -> list[dict]:
    seen: dict[int, dict] = {}
    for m in materials:
        for c in m["characters"]:
            seen.setdefault(c["id"], {k: c[k] for k in ("id", "name", "slug", "icon")})
    return sorted(seen.values(), key=lambda c: c["name"])


def farm_today(data: PlannerData, weekday: int, index: dict[int, dict]) -> dict:
    domains = []
    for d in data.domains:
        if weekday != SUNDAY and weekday not in d.weekdays:
            continue
        mats = [index[mid] for mid in d.material_ids if mid in index and index[mid]["to_farm"] > 0]
        if mats:
            domains.append({"id": d.id, "name": d.name, "kind": d.kind, "weekdays": d.weekdays,
                            "materials": mats, "characters": _characters(mats)})
    return {"weekday": weekday, "domains": domains}


def weekly_bosses(data: PlannerData, done: set[str], index: dict[int, dict]) -> list[dict]:
    by_boss: dict[str, list[dict]] = {}
    for row in sorted(index.values(), key=lambda r: (r["sort_order"], r["id"])):
        if row["category"] != "weekly" or row["to_farm"] <= 0:
            continue
        boss = next((s["name"] for s in row["sources"] if s["kind"] == "weekly_boss"), "Unknown boss")
        by_boss.setdefault(boss, []).append(row)
    bosses = [{"name": name, "done": name in done, "materials": mats, "characters": _characters(mats)}
              for name, mats in by_boss.items()]
    return sorted(bosses, key=lambda b: b["done"])
