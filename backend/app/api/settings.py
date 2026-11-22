import re
from dataclasses import asdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, ValidationInfo, field_validator
from sqlalchemy.orm import Session

from app.config import LEVEL_CAPS
from app.context import AppContext, get_ctx
from app.gamedata.service import gamedata_status, refresh_all
from app.schemas import TargetsIn
from app.settings.connect import ConnectError, connect
from app.settings.envfile import COOKIE_KEYS, connection_status, read_env
from app.settings.store import get_setting, set_setting

router = APIRouter()


class SettingsIn(BaseModel):
    sync_interval_minutes: int | None = Field(default=None, ge=1, le=1440)
    default_targets: TargetsIn | None = None
    game_install_path: str | None = Field(default=None, max_length=500)
    default_map: Literal["hoyolab", "appsample"] | None = None
    good_import_enabled: bool | None = None


class HoyolabIn(BaseModel):
    ltuid_v2: str = ""
    ltoken_v2: str = ""
    ltmid_v2: str = ""
    account_id_v2: str = ""
    account_mid_v2: str = ""
    cookie_token_v2: str = ""
    uid: int | None = None

    @field_validator(*COOKIE_KEYS, mode="before")
    @classmethod
    def _clean(cls, value, info: ValidationInfo) -> str:
        """Accept values pasted with spaces, quotes, a `name=` prefix, or a trailing `;`."""
        text = "" if value is None else str(value)
        prefix = re.compile(rf"^{re.escape(info.field_name)}\s*=\s*", re.IGNORECASE)
        while True:  # peel layers in any order until nothing changes
            cleaned = prefix.sub("", text.strip().strip("\"'").rstrip(";").strip())
            if cleaned == text:
                return cleaned
            text = cleaned

    def cookies(self) -> dict[str, str]:
        return {k: getattr(self, k) for k in COOKIE_KEYS if getattr(self, k)}


def settings_payload(ctx: AppContext, s: Session) -> dict:
    env = read_env(ctx.paths.env_file)
    return {
        "connection": connection_status(env, get_setting(s, "hoyolab_status")),
        "sync_interval_minutes": get_setting(s, "sync_interval_minutes"),
        "default_targets": get_setting(s, "default_targets"),
        "game_install_path": get_setting(s, "game_install_path"),
        "default_map": get_setting(s, "default_map"),
        "good_import_enabled": bool(get_setting(s, "good_import_enabled")),
        "level_caps": LEVEL_CAPS,
        "gamedata": gamedata_status(s),
    }


@router.get("/settings")
def get_settings(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        return settings_payload(ctx, s)


@router.put("/settings")
def put_settings(body: SettingsIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory.begin() as s:
        if body.sync_interval_minutes is not None:
            set_setting(s, "sync_interval_minutes", body.sync_interval_minutes)
        if body.default_targets is not None:
            set_setting(s, "default_targets", body.default_targets.model_dump())
        if body.game_install_path is not None:
            set_setting(s, "game_install_path", body.game_install_path.strip())
        if body.default_map is not None:
            set_setting(s, "default_map", body.default_map)
        if body.good_import_enabled is not None:
            set_setting(s, "good_import_enabled", body.good_import_enabled)
        return settings_payload(ctx, s)


@router.post("/settings/hoyolab")
async def connect_hoyolab(body: HoyolabIn, ctx: AppContext = Depends(get_ctx)) -> dict:
    cookies = body.cookies()
    if "ltuid_v2" not in cookies or "ltoken_v2" not in cookies:
        raise HTTPException(400, "ltuid_v2 and ltoken_v2 are required.")
    try:
        result = await connect(ctx.paths.env_file, ctx.session_factory, cookies, body.uid,
                               ctx.accounts_fetcher)
    except ConnectError as e:
        raise HTTPException(400, str(e)) from None
    if result.status == "choose":
        return {"status": "choose", "accounts": [asdict(a) for a in result.accounts]}
    # A sync using the old cookie may still be running: stop it from marking us expired,
    # let it finish, then start a fresh run with the new cookie.
    ctx.sync.invalidate_auth()
    await ctx.sync.wait()
    await ctx.sync.request("connect")
    return {"status": "connected", "uid": result.uid}


@router.post("/gamedata/refresh")
async def refresh_gamedata(ctx: AppContext = Depends(get_ctx)) -> dict:
    refreshed = await refresh_all(ctx.session_factory, ctx.http, force=True)
    with ctx.session_factory() as s:
        return {"refreshed": refreshed, "gamedata": gamedata_status(s)}
