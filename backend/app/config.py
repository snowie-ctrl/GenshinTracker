"""Filesystem locations and app-wide constants. User data lives under data/ and .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_BUILD = REPO_ROOT / "frontend" / "build"

DEFAULT_PORT = 8765
LEVEL_CAPS = [20, 40, 50, 60, 70, 80, 90]
DEFAULT_SYNC_INTERVAL_MINUTES = 10
MANUAL_SYNC_MIN_SECONDS = 60
GAMEDATA_MAX_AGE_DAYS = 7
BACKUPS_KEPT = 5
GAPS_DEBOUNCE_SECONDS = 3.0
# Set from the phase 2 live check (docs/superpowers/notes/2026-11-19-phase2-calculator-findings.md):
# True if HoYoLAB's lack_num already subtracts what can be crafted from spare lower tiers.
LACK_INCLUDES_CRAFTING = False
WISH_BACKUPS_KEPT = 10
APP_VERSION = "0.3.0"
WISH_UPLOAD_MAX_BYTES = 20 * 1024 * 1024
GOOD_UPLOAD_MAX_BYTES = 20 * 1024 * 1024
WISH_PAGE_DELAY = 0.3          # seconds between gacha-log pages (be gentle with the API)
WISH_HISTORY_PAGE_SIZE = 50
BANNERS_URL = "https://raw.githubusercontent.com/MadeBaruna/paimon-moe/main/src/data/banners.js"


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def data(self) -> Path:
        return self.root / "data"

    @property
    def db_file(self) -> Path:
        return self.data / "tracker.db"

    @property
    def backups(self) -> Path:
        return self.data / "backups"

    @property
    def img_cache(self) -> Path:
        return self.data / "cache" / "img"

    @property
    def env_file(self) -> Path:
        return self.root / ".env"

    @property
    def wish_backups(self) -> Path:
        return self.backups / "wishes"

    def ensure(self) -> None:
        for d in (self.data, self.backups, self.wish_backups, self.img_cache):
            d.mkdir(parents=True, exist_ok=True)


def default_paths() -> Paths:
    return Paths(Path(os.environ.get("GT_ROOT", str(REPO_ROOT))))


def offline() -> bool:
    return os.environ.get("GT_OFFLINE") == "1"
