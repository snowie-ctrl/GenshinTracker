from __future__ import annotations

from dataclasses import dataclass
from typing import Awaitable, Callable

import httpx
from fastapi import Request
from sqlalchemy.orm import sessionmaker

from app.config import Paths
from app.settings.envfile import cookies_from_env, read_env
from app.settings.store import get_setting
from app.sync.hoyolab import Account, GenshinPySource, HoyolabSource
from app.sync.runner import SyncManager


@dataclass
class AppContext:
    paths: Paths
    session_factory: sessionmaker
    http: httpx.AsyncClient
    offline: bool
    sync: SyncManager
    accounts_fetcher: Callable[[dict[str, str]], Awaitable[list[Account]]]


def get_ctx(request: Request) -> AppContext:
    return request.app.state.ctx


def make_source_factory(paths: Paths, session_factory: sessionmaker) -> Callable[[], HoyolabSource | None]:
    def factory() -> HoyolabSource | None:
        env = read_env(paths.env_file)
        cookies = cookies_from_env(env)
        if "ltuid_v2" not in cookies or "ltoken_v2" not in cookies or not env.get("GENSHIN_UID"):
            return None
        with session_factory() as s:
            if get_setting(s, "hoyolab_status") == "expired":
                return None
        return GenshinPySource(cookies, int(env["GENSHIN_UID"]), region=env.get("GENSHIN_REGION"))

    return factory
