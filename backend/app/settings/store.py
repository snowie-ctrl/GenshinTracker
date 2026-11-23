import copy

from sqlalchemy.orm import Session

from app.config import DEFAULT_SYNC_INTERVAL_MINUTES
from app.db.models import Setting

DEFAULTS: dict[str, object] = {
    "sync_interval_minutes": DEFAULT_SYNC_INTERVAL_MINUTES,
    "hoyolab_status": None,  # None | "connected" | "expired"
    "game_install_path": "",   # blank = auto-detect from the game's log file
    "display_name": "",   # Dashboard greeting (sub-project 3); local only
    "default_map": "hoyolab",  # hoyolab | appsample
    "good_import_enabled": False,   # opt-in GOOD scanner import (Phase 6)
    "background_animated": True,    # Ad Astra drifting-dust background (Foundation)
    "traveler_body": "girl",             # "boy" | "girl", from the synced Traveler (sub-project 2)
    "traveler_current_element": None,    # e.g. "Cryo"; the element HoYoLAB reported last
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
