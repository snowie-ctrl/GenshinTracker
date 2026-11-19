from dataclasses import dataclass, field
from pathlib import Path
from typing import Awaitable, Callable

from sqlalchemy.orm import sessionmaker

from app.settings.envfile import COOKIE_KEYS, update_env
from app.settings.store import set_setting
from app.sync.hoyolab import Account, HoyolabError


class ConnectError(Exception):
    pass


@dataclass
class ConnectResult:
    status: str  # "connected" | "choose"
    uid: int | None = None
    accounts: list[Account] = field(default_factory=list)


async def connect(env_file: Path, session_factory: sessionmaker, cookies: dict[str, str],
                  chosen_uid: int | None,
                  fetch_accounts: Callable[[dict[str, str]], Awaitable[list[Account]]]) -> ConnectResult:
    """Test cookies first; only write .env after HoYoLAB accepts them."""
    try:
        accounts = await fetch_accounts(cookies)
    except HoyolabError as e:
        raise ConnectError(str(e) or "HoYoLAB rejected these cookies.") from None
    if not accounts:
        raise ConnectError("No Genshin Impact account is linked to this HoYoLAB login.")
    if chosen_uid is not None:
        account = next((a for a in accounts if a.uid == chosen_uid), None)
        if account is None:
            raise ConnectError("That UID is not linked to this HoYoLAB login.")
    elif len(accounts) == 1:
        account = accounts[0]
    else:
        return ConnectResult("choose", accounts=list(accounts))

    values = {k.upper(): cookies.get(k, "") for k in COOKIE_KEYS}  # "" clears stale optional keys
    values.update(GENSHIN_UID=str(account.uid), GENSHIN_REGION=account.server)
    update_env(env_file, values)
    with session_factory.begin() as s:
        set_setting(s, "hoyolab_status", "connected")
    return ConnectResult("connected", uid=account.uid)
