import json
from datetime import datetime

import pytest

from app.db.models import Wish
from app.wishes.types import ImportFailed, UID_MISMATCH
from app.wishes.uigf import NOT_UIGF, build_uigf, generated_id, is_generated, parse_uigf

UID = 800000001


def rec(id_, gacha_type, time, name, rarity, item_type="Weapon", uigf_type=None):
    r = {"gacha_type": gacha_type, "item_id": "", "count": "1", "time": time, "name": name,
         "item_type": item_type, "rank_type": str(rarity), "id": id_}
    if uigf_type:
        r["uigf_gacha_type"] = uigf_type
    return r


def v4(records, uid=UID, tz=1):
    return {"info": {"export_timestamp": 1, "export_app": "x", "export_app_version": "1", "version": "v4.0"},
            "hk4e": [{"uid": uid, "timezone": tz, "lang": "en-us", "list": records}]}


def test_generated_ids_round_trip():
    gid = generated_id("2024-01-01 09:00:00", 7, 1)            # 08:00 UTC
    assert gid == "1704096000" + "9" + "00000007"
    assert is_generated(gid, "2024-01-01 09:00:00", 1)
    assert not is_generated("1704096000000000007", "2024-01-01 09:00:00", 1)
    assert not is_generated(gid, "2024-01-01 09:00:01", 1)


def test_parse_v4_maps_pools_and_types():
    out = parse_uigf(v4([rec("1704096000000000001", "400", "2024-01-01 09:00:00", "Furina", 5, "Character", "301"),
                         rec("1704096000000000002", "302", "2024-01-01 09:01:00", "Slingshot", 3)]), UID, 1)
    assert [(w.pool, w.gacha_type, w.item_type, w.rarity) for w in out] == [
        ("character", "400", "character", 5), ("weapon", "302", "weapon", 3)]


def test_parse_v4_converts_timezone_to_server_time():
    out = parse_uigf(v4([rec("1", "200", "2024-01-01 16:00:00", "Slingshot", 3)], tz=8), UID, 1)
    assert out[0].time == "2024-01-01 09:00:00"


def test_parse_v4_wrong_uid():
    with pytest.raises(ImportFailed) as e:
        parse_uigf(v4([], uid=800000009), UID, 1)
    assert e.value.message == UID_MISMATCH


def test_parse_v3():
    data = {"info": {"uid": str(UID), "lang": "en-us", "uigf_version": "v3.0", "region_time_zone": 1},
            "list": [rec("5", "200", "2024-01-01 09:00:00", "Slingshot", 3, uigf_type="200")]}
    assert parse_uigf(data, UID, 1)[0].id == "5"
    data["info"]["uid"] = "800000009"
    with pytest.raises(ImportFailed):
        parse_uigf(data, UID, 1)


def test_parse_reports_bad_rows_and_imports_nothing():
    bad = v4([rec("1", "999", "2024-01-01 09:00:00", "X", 3), rec("2", "200", "nope", "X", 3),
              rec("3", "200", "2024-01-01 09:00:00", "X", 3, item_type="武器")])
    with pytest.raises(ImportFailed) as e:
        parse_uigf(bad, UID, 1)
    assert "3 row(s)" in e.value.message and "row 1:" in e.value.message


def test_not_uigf():
    with pytest.raises(ImportFailed) as e:
        parse_uigf({"hello": 1}, UID, 1)
    assert e.value.message == NOT_UIGF


def test_non_dict_hk4e_entry_is_ignored_for_uid_lookup():
    data = v4([rec("1", "200", "2024-01-01 09:00:00", "Slingshot", 3)])
    data["hk4e"].insert(0, "junk")
    assert len(parse_uigf(data, UID, 1)) == 1
    with pytest.raises(ImportFailed) as e:
        parse_uigf({"hk4e": ["junk"]}, UID, 1)
    assert e.value.message == UID_MISMATCH


def test_non_dict_row_is_reported_not_raised():
    with pytest.raises(ImportFailed) as e:
        parse_uigf(v4(["junk"]), UID, 1)
    assert "row 1: not an object" in e.value.message


def test_non_numeric_timezone_is_not_uigf():
    with pytest.raises(ImportFailed) as e:
        parse_uigf(v4([], tz="abc"), UID, 1)
    assert e.value.message == NOT_UIGF
    data = {"info": {"uid": str(UID), "region_time_zone": "abc"}, "list": []}
    with pytest.raises(ImportFailed) as e:
        parse_uigf(data, UID, 1)
    assert e.value.message == NOT_UIGF


def test_infinite_v4_timezone_is_not_uigf():
    data = json.loads('{"info": {"export_app": "x"}, "hk4e": [{"uid": 800000001, "timezone": Infinity, "list": []}]}')
    with pytest.raises(ImportFailed) as e:
        parse_uigf(data, UID, 1)
    assert e.value.message == NOT_UIGF


def test_infinite_v3_timezone_is_not_uigf():
    data = json.loads('{"info": {"uid": "800000001", "region_time_zone": Infinity}, "list": []}')
    with pytest.raises(ImportFailed) as e:
        parse_uigf(data, UID, 1)
    assert e.value.message == NOT_UIGF


def test_infinite_rank_type_is_a_bad_row():
    data = json.loads('{"info": {"export_app": "x"}, "hk4e": [{"uid": 800000001, "timezone": 1, "list": '
                      '[{"gacha_type": "200", "item_id": "", "count": "1", "time": "2024-01-01 09:00:00", '
                      '"name": "X", "item_type": "Weapon", "rank_type": Infinity, "id": "1"}]}]}')
    with pytest.raises(ImportFailed) as e:
        parse_uigf(data, UID, 1)
    assert "1 row(s)" in e.value.message and "row 1:" in e.value.message


@pytest.mark.parametrize("bad_list", ["abc", {"time": "2024-01-01 09:00:00"}])
def test_non_list_records_is_not_uigf(bad_list):
    data = {"info": {"export_timestamp": 1}, "hk4e": [{"uid": UID, "timezone": 1, "lang": "en-us", "list": bad_list}]}
    with pytest.raises(ImportFailed) as e:
        parse_uigf(data, UID, 1)
    assert e.value.message == NOT_UIGF


def test_build_then_parse_round_trips():
    rows = [Wish(id=None, pool="character", gacha_type=None, time="2024-01-01 09:00:00", seq=0, name="Furina",
                 item_id=10000089, item_type="character", rarity=5, source="paimon", imported_at=datetime(2024, 1, 2)),
            Wish(id="1704096000000000002", pool="weapon", gacha_type="302", time="2024-01-01 09:01:00", seq=0,
                 name="Slingshot", item_id=None, item_type="weapon", rarity=3, source="game",
                 imported_at=datetime(2024, 1, 2))]
    out = parse_uigf(build_uigf(rows, UID, 1, datetime(2024, 1, 3), "0.3.0"), UID, 1)
    assert [(w.id, w.pool, w.time, w.name, w.rarity, w.item_type) for w in out] == [
        (None, "character", "2024-01-01 09:00:00", "Furina", 5, "character"),
        ("1704096000000000002", "weapon", "2024-01-01 09:01:00", "Slingshot", 3, "weapon")]


def test_generated_ids_read_back_as_idless():
    gid = generated_id("2024-01-01 09:00:00", 0, 1)
    assert parse_uigf(v4([rec(gid, "200", "2024-01-01 09:00:00", "Slingshot", 3)]), UID, 1)[0].id is None


def test_exports_from_the_old_app_name_still_import():
    data = v4([rec("1704096000000000001", "301", "2024-01-01 09:00:00", "Slingshot", 3)])
    data["info"]["export_app"] = "GenshinTracker"
    rows = parse_uigf(data, UID, 1)
    assert [r.name for r in rows] == ["Slingshot"]


def test_build_v4():
    rows = [Wish(id=None, pool="character", gacha_type=None, time="2024-01-01 09:00:00", seq=0, name="Furina",
                 item_id=10000089, item_type="character", rarity=5, source="paimon", imported_at=datetime(2024, 1, 2)),
            Wish(id="1704096000000000002", pool="weapon", gacha_type="302", time="2024-01-01 09:01:00", seq=0,
                 name="Slingshot", item_id=None, item_type="weapon", rarity=3, source="game",
                 imported_at=datetime(2024, 1, 2))]
    out = build_uigf(rows, UID, 1, datetime(2024, 1, 3), "0.3.0")
    assert out["info"]["version"] == "v4.0" and out["info"]["export_app"] == "AdAstra"
    entry = out["hk4e"][0]
    assert entry["uid"] == UID and entry["timezone"] == 1 and entry["lang"] == "en-us"
    first, second = entry["list"]
    assert first == {"uigf_gacha_type": "301", "gacha_type": "301", "item_id": "10000089", "count": "1",
                     "time": "2024-01-01 09:00:00", "name": "Furina", "item_type": "Character",
                     "rank_type": "5", "id": generated_id("2024-01-01 09:00:00", 0, 1)}
    assert second["item_id"] == "" and second["id"] == "1704096000000000002"
