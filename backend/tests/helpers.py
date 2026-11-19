import json
from datetime import datetime
from pathlib import Path

import httpx

from app.db.models import GameCharacter

FIXTURES = Path(__file__).parent / "fixtures"

# (id, name, slug, rarity, element, weapon_type, icon)
GAME_ROWS = [
    (10000032, "Bennett", "bennett", 4, "Pyro", "Sword", "UI_AvatarIcon_Bennett"),
    (10000089, "Furina", "furina", 5, "Hydro", "Sword", "UI_AvatarIcon_Furina"),
    (10000023, "Xiangling", "xiangling", 4, "Pyro", "Polearm", "UI_AvatarIcon_Xiangling"),
    (10000073, "Nahida", "nahida", 5, "Dendro", "Catalyst", "UI_AvatarIcon_Nahida"),
    (10000005, "Traveler", "traveler", 5, None, "Sword", "UI_AvatarIcon_PlayerBoy"),
]


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def yatta_transport(status: int = 200) -> httpx.MockTransport:
    payload = load_fixture("yatta_avatar.json")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/avatar"):
            return httpx.Response(status, json=payload if status == 200 else {})
        return httpx.Response(404)

    return httpx.MockTransport(handler)


def seed_game(session_factory, rows=GAME_ROWS, release: datetime = datetime(2020, 9, 28)) -> None:
    with session_factory.begin() as s:
        for cid, name, slug, rarity, element, weapon, icon in rows:
            s.merge(GameCharacter(
                id=cid, name=name, slug=slug, rarity=rarity, element=element, weapon_type=weapon,
                region=None, icon=icon, splash=icon.replace("UI_AvatarIcon_", "UI_Gacha_AvatarImg_"),
                release_at=release,
            ))
