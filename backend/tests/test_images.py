import httpx
import pytest

from app.gamedata.images import (
    PLACEHOLDER_PNG, get_named, get_remote, is_allowed_remote,
)

PNG = b"\x89PNG\r\n\x1a\nfake"


def transport(calls: list, status=200):
    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(str(request.url))
        if status != 200:
            return httpx.Response(status)
        return httpx.Response(200, content=PNG, headers={"content-type": "image/png"})
    return httpx.MockTransport(handler)


async def test_named_downloads_once_then_serves_cache(tmp_path):
    calls: list = []
    async with httpx.AsyncClient(transport=transport(calls)) as http:
        first = await get_named(tmp_path, http, "UI_AvatarIcon_Bennett")
        second = await get_named(tmp_path, http, "UI_AvatarIcon_Bennett")
    assert first.data == PNG and first.cached and second.cached
    assert calls == ["https://enka.network/ui/UI_AvatarIcon_Bennett.png"]
    assert (tmp_path / "UI_AvatarIcon_Bennett.png").read_bytes() == PNG


async def test_named_falls_back_then_placeholder_not_cached(tmp_path):
    calls: list = []
    async with httpx.AsyncClient(transport=transport(calls, status=404)) as http:
        result = await get_named(tmp_path, http, "UI_AvatarIcon_Nobody")
    assert result.data == PLACEHOLDER_PNG and not result.cached
    assert len(calls) == 2  # enka then yatta
    assert not (tmp_path / "UI_AvatarIcon_Nobody.png").exists()


async def test_named_rejects_bad_names(tmp_path):
    async with httpx.AsyncClient() as http:
        for bad in ("../secret", "UI_x.png", "foo", "UI_a/b"):
            with pytest.raises(ValueError):
                await get_named(tmp_path, http, bad)


async def test_offline_returns_placeholder_without_network(tmp_path):
    calls: list = []
    async with httpx.AsyncClient(transport=transport(calls)) as http:
        result = await get_named(tmp_path, http, "UI_AvatarIcon_Bennett", offline=True)
    assert result.data == PLACEHOLDER_PNG and calls == []


@pytest.mark.parametrize(
    ("url", "ok"),
    [
        ("https://act-webstatic.hoyoverse.com/x/a.png", True),
        ("https://upload-os-bbs.mihoyo.com/a.png", True),
        ("https://enka.network/ui/a.png", True),
        ("http://act-webstatic.hoyoverse.com/a.png", False),
        ("https://evil.com/a.png", False),
        ("https://hoyoverse.com.evil.com/a.png", False),
    ],
)
def test_remote_allowlist(url, ok):
    assert is_allowed_remote(url) is ok


async def test_remote_cached_by_hash(tmp_path):
    calls: list = []
    url = "https://act-webstatic.hoyoverse.com/w/UI_EquipIcon_Sword.png"
    async with httpx.AsyncClient(transport=transport(calls)) as http:
        await get_remote(tmp_path, http, url)
        again = await get_remote(tmp_path, http, url)
        with pytest.raises(ValueError):
            await get_remote(tmp_path, http, "https://evil.com/a.png")
    assert again.cached and calls == [url]
    assert len(list((tmp_path / "remote").iterdir())) == 1
