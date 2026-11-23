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
    (1000000507, "Cryo Traveler", "cryo-traveler", 5, "Cryo", "Sword", "UI_AvatarIcon_PlayerGirl"),
    (1000000502, "Anemo Traveler", "anemo-traveler", 5, "Anemo", "Sword", "UI_AvatarIcon_PlayerGirl"),
    (1000000503, "Geo Traveler", "geo-traveler", 5, "Geo", "Sword", "UI_AvatarIcon_PlayerGirl"),
]


def load_fixture(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def yatta_transport(status: int = 200, fail_details: frozenset[int] = frozenset()) -> httpx.MockTransport:
    avatar = load_fixture("yatta_avatar.json")
    material = load_fixture("yatta_material.json")
    details = load_fixture("yatta_material_details.json")
    dungeon = load_fixture("yatta_daily_dungeon.json")
    weapon = load_fixture("yatta_weapon.json")
    reliquary = load_fixture("yatta_reliquary.json")
    banners_js = (FIXTURES / "paimon_banners.js").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        path = request.url.path
        if status != 200:
            return httpx.Response(status, json={})
        if path.endswith("banners.js"):
            return httpx.Response(200, text=banners_js)
        if path.endswith("/avatar"):
            return httpx.Response(200, json=avatar)
        if path.endswith("/material"):
            return httpx.Response(200, json=material)
        if "/material/" in path:
            mid = int(path.rsplit("/", 1)[1])
            if mid in fail_details:
                return httpx.Response(500)
            body = details.get(str(mid), {"response": 200, "data": {"recipe": None, "source": []}})
            return httpx.Response(200, json=body)
        if path.endswith("/dailyDungeon"):
            return httpx.Response(200, json=dungeon)
        if path.endswith("/weapon"):
            return httpx.Response(200, json=weapon)
        if path.endswith("/reliquary"):
            return httpx.Response(200, json=reliquary)
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


import time  # noqa: E402

from fastapi.testclient import TestClient  # noqa: E402

from app.main import create_app  # noqa: E402


def make_client(paths, source=None, accounts=None, transport=None,
                wish_link_reader=None, wish_page_factory=None) -> TestClient:
    """`accounts`: list[Account] to return, or an Exception to raise, from the account lookup."""
    http = httpx.AsyncClient(transport=transport or httpx.MockTransport(lambda r: httpx.Response(404)))

    async def fetch_accounts(cookies):
        if isinstance(accounts, Exception):
            raise accounts
        return list(accounts or [])

    app = create_app(paths, source_factory=lambda: source, accounts_fetcher=fetch_accounts,
                     http_client=http, offline=True,
                     wish_link_reader=wish_link_reader, wish_page_factory=wish_page_factory)
    return TestClient(app)


def wait_for_sync(client: TestClient, timeout: float = 5.0) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        status = client.get("/api/sync/status").json()
        if not status["running"]:
            return status
        if time.monotonic() > deadline:
            raise TimeoutError("sync did not finish")
        time.sleep(0.02)


def drop_default_tags(sf) -> None:
    """Remove the migration's default tags so a test starts with only Build."""
    from sqlalchemy import delete
    from app.db.models import Tag
    with sf.begin() as s:
        s.execute(delete(Tag).where(Tag.builtin.is_(False)))
