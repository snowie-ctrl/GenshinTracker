"""Live check against your real account (manual, never in CI): python -m app.smoke"""
import asyncio
import sys

from app.config import default_paths
from app.settings.envfile import cookies_from_env, read_env
from app.sync.hoyolab import GenshinPySource


async def main() -> None:
    env = read_env(default_paths().env_file)
    if not env.get("GENSHIN_UID"):
        sys.exit("Connect from the app's Settings page first (GENSHIN_UID missing in .env).")
    source = GenshinPySource(cookies_from_env(env), int(env["GENSHIN_UID"]), region=env.get("GENSHIN_REGION"))
    roster = await source.get_roster()
    print(f"roster: {len(roster)} characters")
    details = await source.get_details([r.raw_id for r in roster[:3]])
    for d in details:
        print(f"  {d.id}: talents {d.normal}/{d.skill}/{d.burst}, artifacts {len(d.artifacts)}, stats {len(d.stats)}")
    notes = await source.get_notes()
    print(f"notes: resin {notes.resin}/{notes.resin_max}, commissions "
          f"{notes.commissions_done}/{notes.commissions_max}, expeditions {len(notes.expeditions)}")


if __name__ == "__main__":
    asyncio.run(main())
