"""Live check against your real account (manual, never in CI):
python -m app.smoke          roster/details/notes
python -m app.smoke --gaps   calculator checks for phase 2 (uses your Build goals from data/tracker.db)
python -m app.smoke --wishes          read-only wish fetch check (needs Wish History opened in-game)
python -m app.smoke --paimon FILE     print sheet names/headers/row counts of a paimon.moe export"""
import asyncio
import sys
from collections import Counter

from sqlalchemy import select

from app.config import default_paths
from app.db.engine import make_engine, make_session_factory, migrate
from app.db.models import GameMaterial
from app.planner.requests import build_inputs, gap_requests, has_work
from app.settings.envfile import cookies_from_env, read_env
from app.settings.store import get_setting
from app.sync.hoyolab import GenshinPySource
from app.wishes.authkey import default_locallow, load_wish_link
from app.wishes.fetch import fetch_new, genshin_page_fn, record_uid
from app.wishes.types import POOL_BY_GACHA_TYPE, ImportFailed


async def basic(source: GenshinPySource) -> None:
    roster = await source.get_roster()
    print(f"roster: {len(roster)} characters")
    details = await source.get_details([r.raw_id for r in roster[:3]])
    for d in details:
        print(f"  {d.id}: talents {d.normal}/{d.skill}/{d.burst}, artifacts {len(d.artifacts)}, stats {len(d.stats)}")
    notes = await source.get_notes()
    print(f"notes: resin {notes.resin}/{notes.resin_max}, commissions "
          f"{notes.commissions_done}/{notes.commissions_max}, expeditions {len(notes.expeditions)}, "
          f"weekly discounts {notes.weekly_discounts_left}/{notes.weekly_discounts_max}")


async def gaps(source: GenshinPySource) -> None:
    paths = default_paths()
    engine = make_engine(paths.db_file)
    migrate(engine)
    sf = make_session_factory(engine)
    with sf() as s:
        inputs, skipped = build_inputs(s)
        catalogue = set(s.scalars(select(GameMaterial.id)))
    work = [i for i in inputs if has_work(i)]
    print(f"build characters: {len(inputs)} ({len(work)} with work), skipped: {skipped}")
    if not work:
        sys.exit("Set at least one owned character to Build with targets above current, then rerun.")
    talent_ids = {i.character_id: await source.get_talent_ids(i.character_id) for i in work}
    print("check 0 (talent ids):", {k: (v.normal, v.skill, v.burst) for k, v in talent_ids.items()})
    requests = gap_requests(work, talent_ids)
    print(f"check 2 (character limit): sending {len(requests)} characters in one request")
    result = await source.compute_gaps(requests)
    print(f"  per-character results: {len(result.per_character)} / {len(requests)}")
    print("check 6 (order): first 3 materials per requested character (should match that character):")
    for r in requests:
        first = [(m.id, m.name, m.need, m.short) for m in result.per_character.get(r.character_id, [])[:3]]
        print(f"  {r.character_id}: {first}")
    print("check 1/5 (crafting, spare): available_material entries:")
    for m in result.spare:
        print(f"  spare {m.id} {m.name} r{m.rarity}: num={m.need}")
    print("totals (id, name, rarity, need, short, in catalogue):")
    for m in result.total:
        print(f"  {m.id} {m.name} r{m.rarity}: need {m.need} short {m.short} {'yes' if m.id in catalogue else 'NO'}")
    weapons = [r for r in requests if r.weapon is not None]
    print(f"check 3 (weapons): {len(weapons)} requests had a weapon part: "
          f"{[(r.character_id, r.weapon) for r in weapons]}")
    print("check 4 (ascension at caps): characters at a cap level:",
          [(i.character_id, i.level) for i in work if i.level in (20, 40, 50, 60, 70, 80)])
    engine.dispose()


async def wishes() -> None:
    """Read-only: never writes the database, never prints the URL or authkey."""
    paths = default_paths()
    engine = make_engine(paths.db_file)
    migrate(engine)
    with make_session_factory(engine)() as s:
        game_path = get_setting(s, "game_install_path")
    try:
        link = load_wish_link(game_path, default_locallow())
    except ImportFailed as e:
        sys.exit(e.message)
    print(f"check 1 (wish link): found, cached at {link.cached_at:%Y-%m-%d %H:%M} UTC")
    raw = await fetch_new(genshin_page_fn(link), set())
    env_uid = read_env(paths.env_file).get("GENSHIN_UID")
    print(f"  records: {len(raw)}; uid matches .env: {str(record_uid(raw)) == env_uid}")
    by_type = Counter(r["gacha_type"] for r in raw)
    print(f"  per gacha type: {dict(sorted(by_type.items()))} (400 present: {'400' in by_type})")
    for pool in ("character", "weapon", "chronicled", "standard", "beginner"):
        rows = sorted((r for r in raw if POOL_BY_GACHA_TYPE[r["gacha_type"]] == pool), key=lambda r: int(r["id"]))
        pity = 0
        for r in rows:
            pity = 0 if r["rank_type"] == "5" else pity + 1
        print(f"  {pool}: {len(rows)} pulls, pity since last 5★: {pity}")
    marked = [r["id"] for r in raw if len(str(r["id"])) == 19 and str(r["id"])[10] == "9"]
    print(f"check 5 (id format): {len(raw)} ids, all 19 digits: "
          f"{all(len(str(r['id'])) == 19 for r in raw)}, ids with '9' as 11th digit: {len(marked)}")


def paimon(path: str) -> None:
    from openpyxl import load_workbook
    wb = load_workbook(path, read_only=True, data_only=True)
    for ws in wb.worksheets:
        rows = ws.iter_rows(values_only=True)
        header = next(rows, None)
        count = sum(1 for r in rows if any(c is not None for c in r))
        print(f"sheet {ws.title!r}: header {list(header) if header else None}, data rows {count}")


async def main() -> None:
    env = read_env(default_paths().env_file)
    if not env.get("GENSHIN_UID"):
        sys.exit("Connect from the app's Settings page first (GENSHIN_UID missing in .env).")
    source = GenshinPySource(cookies_from_env(env), int(env["GENSHIN_UID"]), region=env.get("GENSHIN_REGION"))
    await (gaps(source) if "--gaps" in sys.argv else basic(source))


if __name__ == "__main__":
    if "--paimon" in sys.argv:
        paimon(sys.argv[sys.argv.index("--paimon") + 1])
    elif "--wishes" in sys.argv:
        asyncio.run(wishes())
    else:
        asyncio.run(main())
