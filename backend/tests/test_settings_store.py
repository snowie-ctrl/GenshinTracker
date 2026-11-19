import pytest

from app.domain import Targets
from app.settings.envfile import (
    connection_status, cookies_from_env, read_env, update_env,
)
from app.settings.store import default_targets, get_setting, set_setting


def test_defaults_when_unset(session_factory):
    with session_factory() as s:
        assert get_setting(s, "sync_interval_minutes") == 10
        assert get_setting(s, "hoyolab_status") is None
        assert default_targets(s) == Targets(90, 8, 8, 8, 90)


def test_set_and_get(session_factory):
    with session_factory.begin() as s:
        set_setting(s, "sync_interval_minutes", 30)
        set_setting(s, "sync_interval_minutes", 15)
    with session_factory() as s:
        assert get_setting(s, "sync_interval_minutes") == 15


def test_unknown_key_rejected(session_factory):
    with session_factory() as s, pytest.raises(KeyError):
        set_setting(s, "nope", 1)


def test_default_value_is_a_copy(session_factory):
    with session_factory() as s:
        get_setting(s, "default_targets")["level"] = 1
        assert get_setting(s, "default_targets")["level"] == 90


def test_update_env_preserves_other_lines(tmp_path):
    env = tmp_path / ".env"
    env.write_text("# my comment\nPORT=9000\nLTOKEN_V2=old\nCOOKIE_TOKEN_V2=stale\n", encoding="utf-8")
    update_env(env, {"LTOKEN_V2": "new", "LTUID_V2": "123", "COOKIE_TOKEN_V2": ""})
    text = env.read_text(encoding="utf-8")
    assert "# my comment" in text and "PORT=9000" in text
    assert read_env(env) == {"PORT": "9000", "LTOKEN_V2": "new", "LTUID_V2": "123"}


def test_update_env_creates_file(tmp_path):
    env = tmp_path / ".env"
    update_env(env, {"GENSHIN_UID": "800000001"})
    assert read_env(env) == {"GENSHIN_UID": "800000001"}


def test_cookies_from_env():
    env = {"LTUID_V2": "1", "LTOKEN_V2": "t", "PORT": "1"}
    assert cookies_from_env(env) == {"ltuid_v2": "1", "ltoken_v2": "t"}


@pytest.mark.parametrize(
    ("env", "stored", "expected"),
    [
        ({}, None, {"status": "missing", "uid": None}),
        ({"LTUID_V2": "1"}, None, {"status": "missing", "uid": None}),
        ({"LTUID_V2": "1", "LTOKEN_V2": "t", "GENSHIN_UID": "800000001"}, "connected",
         {"status": "connected", "uid": 800000001}),
        ({"LTUID_V2": "1", "LTOKEN_V2": "t", "GENSHIN_UID": "800000001"}, "expired",
         {"status": "expired", "uid": 800000001}),
    ],
)
def test_connection_status(env, stored, expected):
    assert connection_status(env, stored) == expected
