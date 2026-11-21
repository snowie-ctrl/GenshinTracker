# backend/tests/test_wish_paimon.py
from datetime import datetime

import pytest

from app.wishes.paimon_xlsx import NOT_XLSX, parse_paimon_xlsx
from app.wishes.types import ImportFailed
from wishdata import make_paimon_xlsx


def test_parses_sheets_in_file_order():
    content = make_paimon_xlsx({
        "Character Event": [("Character", "Furina", "2024-01-10 10:00:00", 5),
                            ("Weapon", "Slingshot", "2024-01-10 10:00:00", 3)],
        "Weapon Event": [("Weapon", "Favonius Sword", datetime(2024, 1, 11, 9, 30, 0), 4)],
        "Standard": [], "Beginners' Wish": [], "Chronicled Wish": [],
        "Information": [],
    })
    out = parse_paimon_xlsx(content)
    assert [(w.pool, w.gacha_type, w.name, w.time, w.rarity, w.id) for w in out] == [
        ("character", None, "Furina", "2024-01-10 10:00:00", 5, None),
        ("character", None, "Slingshot", "2024-01-10 10:00:00", 3, None),
        ("weapon", "302", "Favonius Sword", "2024-01-11 09:30:00", 4, None),
    ]


def test_bad_rows_import_nothing():
    content = make_paimon_xlsx({"Weapon Event": [("Weapon", "A", "not a time", 4), ("Thing", "B", "2024-01-01 00:00:00", 4)],
                                "Mystery Sheet": [("Weapon", "C", "2024-01-01 00:00:00", 3)]})
    with pytest.raises(ImportFailed) as e:
        parse_paimon_xlsx(content)
    msg = e.value.message
    assert "Mystery Sheet" in msg and 'sheet "Weapon Event" row 2' in msg and 'row 3' in msg


def test_missing_column():
    content = make_paimon_xlsx({"Standard": [("Weapon", "A", "2024-01-01 00:00:00", 3)]},
                               header=("Type", "Name", "When", "⭐"))
    with pytest.raises(ImportFailed) as e:
        parse_paimon_xlsx(content)
    assert "missing column Time" in e.value.message


def test_not_a_workbook():
    with pytest.raises(ImportFailed) as e:
        parse_paimon_xlsx(b"definitely not a zip")
    assert e.value.message == NOT_XLSX


def test_infinite_rarity_is_a_clean_import_failure():
    content = make_paimon_xlsx({"Standard": [("Weapon", "A", "2024-01-01 00:00:00", float("inf"))]})
    with pytest.raises(ImportFailed) as e:
        parse_paimon_xlsx(content)
    assert 'sheet "Standard" row 2' in e.value.message
