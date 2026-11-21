from pathlib import Path

import pytest

from app.wishes import authkey as ak
from app.wishes.types import ImportFailed
from wishdata import FAKE_AUTHKEY, make_game_install, wish_url


def test_reads_last_link_from_newest_version_by_number(tmp_path):
    later = wish_url("NEWER-KEY")
    game_dir, locallow = make_game_install(tmp_path, versions=("2.9.0.0", "2.40.0.0"),
                                           urls=(wish_url(), later))
    link = ak.load_wish_link("", locallow)                # auto-detect via the log
    assert link.authkey == "NEWER-KEY"
    assert link.region == "os_euro"


def test_authkey_is_url_decoded_without_plus_to_space(tmp_path):
    game_dir, locallow = make_game_install(tmp_path)
    assert ak.load_wish_link(str(game_dir), locallow).authkey == FAKE_AUTHKEY


def test_game_path_setting_wins_over_log(tmp_path):
    game_dir, _ = make_game_install(tmp_path, log=False)
    assert ak.find_data_2(str(game_dir), tmp_path / "nowhere").name == "data_2"
    assert ak.find_data_2(str(game_dir.parent), tmp_path / "nowhere").name == "data_2"  # install root works too


def test_not_found_message(tmp_path):
    with pytest.raises(ImportFailed) as e:
        ak.find_data_2("", tmp_path / "LocalLow")
    assert e.value.message == ak.CACHE_NOT_FOUND


def test_no_link_message(tmp_path):
    game_dir, locallow = make_game_install(tmp_path, urls=())
    with pytest.raises(ImportFailed) as e:
        ak.load_wish_link("", locallow)
    assert e.value.message == ak.NO_WISH_LINK


def test_locked_file_message(tmp_path, monkeypatch):
    game_dir, locallow = make_game_install(tmp_path)

    def locked(self, *a, **k):
        raise PermissionError("in use")
    monkeypatch.setattr(Path, "read_bytes", locked)
    with pytest.raises(ImportFailed) as e:
        ak.load_wish_link("", locallow)
    assert e.value.message == ak.CACHE_LOCKED


def test_repr_hides_authkey(tmp_path):
    _, locallow = make_game_install(tmp_path)
    link = ak.load_wish_link("", locallow)
    assert FAKE_AUTHKEY not in repr(link) and "SECRET" not in repr(link)


def test_cache_status(tmp_path):
    _, locallow = make_game_install(tmp_path)
    st = ak.cache_status("", locallow)
    assert st["status"] == "found" and st["cached_at"] is not None
    assert ak.cache_status("", tmp_path / "missing")["status"] == "not_found"
    _, empty_ll = make_game_install(tmp_path / "b", urls=())
    assert ak.cache_status("", empty_ll)["status"] == "no_link"


def test_unreadable_cache_dir_is_not_found(tmp_path, monkeypatch):
    game_dir, _ = make_game_install(tmp_path)

    def denied(self):
        raise PermissionError("denied")
    monkeypatch.setattr(Path, "iterdir", denied)
    with pytest.raises(ImportFailed) as e:
        ak.find_data_2(str(game_dir), tmp_path / "nowhere")
    assert e.value.message == ak.CACHE_NOT_FOUND
