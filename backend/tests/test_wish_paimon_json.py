# backend/tests/test_wish_paimon_json.py
import pytest

from app.wishes.paimon_json import NOT_PAIMON, Item, is_paimon_backup, parse_paimon_json
from app.wishes.types import UID_MISMATCH, ImportFailed
from wishdata import FAKE_UID, paimon_backup

ITEMS = {"furina": Item("Furina", "character", 5), "slingshot": Item("Slingshot", "weapon", 3),
         "freedom_sworn": Item("Freedom-Sworn", "weapon", 5), "favonius_sword": Item("Favonius Sword", "weapon", 4)}


def test_maps_slugs_codes_and_keeps_file_order():
    data = paimon_backup({
        "wish-counter-character-event": [("furina", "400", "2024-01-10 10:00:00"),
                                         ("slingshot", "301", "2024-01-10 10:00:00")],
        "wish-counter-weapon-event": [("freedom-sworn", "302", "2024-01-11 09:30:00")],
        "wish-counter-standard": [("favonius_sword", "999", "2024-01-12 08:00:00")],
    })
    out = parse_paimon_json(data, FAKE_UID, ITEMS)
    assert [(w.pool, w.gacha_type, w.name, w.item_type, w.time, w.rarity, w.id) for w in out] == [
        ("character", "400", "Furina", "character", "2024-01-10 10:00:00", 5, None),
        ("character", "301", "Slingshot", "weapon", "2024-01-10 10:00:00", 3, None),
        ("weapon", "302", "Freedom-Sworn", "weapon", "2024-01-11 09:30:00", 5, None),
        ("standard", "200", "Favonius Sword", "weapon", "2024-01-12 08:00:00", 4, None),  # bad code → pool's type
    ]


def test_detects_backup_and_ignores_settings_and_other_keys():
    data = paimon_backup({"wish-counter-beginners": [("slingshot", "100", "2024-01-01 00:00:00")]})
    data["characters"] = {"amber": {"default": 1}}
    assert is_paimon_backup(data)
    assert not is_paimon_backup({"info": {}, "list": []})
    assert [w.pool for w in parse_paimon_json(data, FAKE_UID, ITEMS)] == ["beginner"]


def test_other_account_is_refused():
    data = paimon_backup({"wish-counter-standard": []}, uid="800000002")
    with pytest.raises(ImportFailed) as e:
        parse_paimon_json(data, FAKE_UID, ITEMS)
    assert e.value.message == UID_MISMATCH


def test_missing_uid_is_accepted():
    data = paimon_backup({"wish-counter-standard": [("slingshot", "200", "2024-01-01 00:00:00")]}, uid=None)
    assert len(parse_paimon_json(data, FAKE_UID, ITEMS)) == 1


def test_unknown_items_and_bad_rows_import_nothing():
    data = paimon_backup({"wish-counter-weapon-event": [("mystery_blade", "302", "2024-01-01 00:00:00"),
                                                        ("slingshot", "302", "not a time")],
                          "wish-counter-mystery": [("slingshot", "302", "2024-01-01 00:00:00")]})
    data["wish-counter-standard"] = {"pulls": [42]}
    with pytest.raises(ImportFailed) as e:
        parse_paimon_json(data, FAKE_UID, ITEMS)
    msg = e.value.message
    assert msg.startswith("Nothing was imported")
    assert "unknown items mystery_blade" in msg and "Refresh game data" in msg
    assert '"wish-counter-weapon-event" pull 2' in msg
    assert '"wish-counter-mystery": unknown banner' in msg
    assert '"wish-counter-standard" pull 1: not an object' in msg


def test_not_a_backup():
    with pytest.raises(ImportFailed) as e:
        parse_paimon_json([1, 2], FAKE_UID, ITEMS)
    assert e.value.message == NOT_PAIMON
