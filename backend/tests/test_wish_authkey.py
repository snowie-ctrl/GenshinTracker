import sys
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
    monkeypatch.setattr(ak, "_read_shared", locked)
    with pytest.raises(ImportFailed) as e:
        ak.load_wish_link("", locallow)
    assert e.value.message == ak.CACHE_LOCKED


@pytest.mark.skipif(sys.platform != "win32", reason="Windows share modes")
def test_reads_cache_while_game_holds_it_with_delete_access(tmp_path):
    """The running game opens data_2 with DELETE access; a plain open() then fails."""
    import ctypes
    from ctypes import wintypes
    _, locallow = make_game_install(tmp_path)
    data_2 = ak.find_data_2("", locallow)
    k32 = ctypes.WinDLL("kernel32", use_last_error=True)
    k32.CreateFileW.restype = wintypes.HANDLE
    k32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID,
                                wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    k32.CloseHandle.argtypes = [wintypes.HANDLE]
    held = k32.CreateFileW(str(data_2), 0x80000000 | 0x00010000, 0x7, None, 3, 0x80, None)
    assert held not in (None, wintypes.HANDLE(-1).value)
    try:
        with pytest.raises(PermissionError):
            data_2.read_bytes()
        assert ak.load_wish_link("", locallow).authkey == FAKE_AUTHKEY
    finally:
        k32.CloseHandle(held)


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
