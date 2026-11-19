"""Filesystem locations and app-wide constants. User data lives under data/ and .env."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
FRONTEND_BUILD = REPO_ROOT / "frontend" / "build"

DEFAULT_PORT = 8765
LEVEL_CAPS = [20, 40, 50, 60, 70, 80, 90]
DEFAULT_TARGETS = {"level": 90, "normal": 8, "skill": 8, "burst": 8, "weapon_level": 90}
DEFAULT_SYNC_INTERVAL_MINUTES = 10
MANUAL_SYNC_MIN_SECONDS = 60
GAMEDATA_MAX_AGE_DAYS = 7
BACKUPS_KEPT = 5


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

    def ensure(self) -> None:
        for d in (self.data, self.backups, self.img_cache):
            d.mkdir(parents=True, exist_ok=True)


def default_paths() -> Paths:
    return Paths(Path(os.environ.get("GT_ROOT", str(REPO_ROOT))))


def offline() -> bool:
    return os.environ.get("GT_OFFLINE") == "1"
