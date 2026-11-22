import copy

from sqlalchemy.orm import Session

from app.config import DEFAULT_SYNC_INTERVAL_MINUTES, DEFAULT_TARGETS
from app.db.models import Setting
from app.domain import Targets

DEFAULTS: dict[str, object] = {
    "sync_interval_minutes": DEFAULT_SYNC_INTERVAL_MINUTES,
    "default_targets": DEFAULT_TARGETS,
    "hoyolab_status": None,  # None | "connected" | "expired"
    "game_install_path": "",   # blank = auto-detect from the game's log file
    "default_map": "hoyolab",  # hoyolab | appsample
    "good_import_enabled": False,   # opt-in GOOD scanner import (Phase 6)
}


def get_setting(session: Session, key: str) -> object:
    row = session.get(Setting, key)
    return row.value if row is not None else copy.deepcopy(DEFAULTS[key])


def set_setting(session: Session, key: str, value: object) -> None:
    if key not in DEFAULTS:
        raise KeyError(key)
    row = session.get(Setting, key)
    if row is None:
        session.add(Setting(key=key, value=value))
    else:
        row.value = value
    session.flush()


def default_targets(session: Session) -> Targets:
    return Targets.from_dict(get_setting(session, "default_targets"))
