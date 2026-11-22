"""Check how a real GOOD export matches the game data, printing only counts and unmatched keys.

    python -m app.good.check --db COPY_OF_DB.sqlite [--refresh] FILE

Point --db at a COPY of the database: --refresh downloads public game data from Yatta into it.
Nothing from the file except unmatched key names is printed; nothing is written to the database's GOOD tables.
"""
from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

import httpx

from app.db.engine import make_engine, make_session_factory, migrate
from app.good.keys import KeyIndex
from app.good.parse import GoodFormatError, parse_good
from app.good.store import match_file


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.good.check")
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--refresh", action="store_true", help="download game data into the (copied) database first")
    ap.add_argument("file", type=Path)
    args = ap.parse_args(argv)
    engine = make_engine(args.db)
    migrate(engine)
    sf = make_session_factory(engine)
    try:
        if args.refresh:
            from app.gamedata.service import refresh_all

            async def go():
                async with httpx.AsyncClient() as http:
                    await refresh_all(sf, http, force=True)
            asyncio.run(go())
        try:
            parsed = parse_good(args.file.read_bytes())
        except GoodFormatError as e:
            print(f"error: {e}")
            return 2
        with sf() as s:
            result = match_file(parsed, KeyIndex.build(s))
        c = result.counts
        print(f"materials: {c['materials']['matched']} matched, {c['materials']['ignored']} ignored, "
              f"{c['materials']['unmatched']} unmatched")
        print(f"weapons: {c['weapons']['matched']} matched, {c['weapons']['unmatched']} unmatched")
        print(f"artifacts: {c['artifacts']['matched']} matched, {c['artifacts']['unmatched']} unmatched")
        for key in result.unmatched:
            print(f"  unmatched {key}")
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
