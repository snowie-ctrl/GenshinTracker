"""paimon.moe "Export to Excel" workbook → IncomingWish rows (no pull ids; file order kept)."""
from __future__ import annotations

import zipfile
from io import BytesIO

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.wishes.types import SINGLE_TYPE, ImportFailed, IncomingWish, bad_rows_message, item_type_of, normalize_time

SHEETS = {"Character Event": "character", "Weapon Event": "weapon", "Standard": "standard",
          "Beginners' Wish": "beginner", "Chronicled Wish": "chronicled"}
IGNORED_SHEETS = {"Information"}
COLUMNS = {"type": "Type", "name": "Name", "time": "Time", "rarity": "⭐"}
NOT_XLSX = "This file is not an Excel workbook."


def parse_paimon_xlsx(content: bytes) -> list[IncomingWish]:
    try:
        wb = load_workbook(BytesIO(content), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError, OSError):
        raise ImportFailed(NOT_XLSX) from None
    out, errors = [], []
    for ws in wb.worksheets:
        if ws.title in IGNORED_SHEETS:
            continue
        pool = SHEETS.get(ws.title)
        if pool is None:
            errors.append(f'sheet "{ws.title}": unknown banner sheet')
            continue
        rows = ws.iter_rows(values_only=True)
        header = [str(c).strip() if c is not None else "" for c in (next(rows, None) or [])]
        missing = [label for label in COLUMNS.values() if label not in header]
        if missing:
            errors.append(f'sheet "{ws.title}": missing column {", ".join(missing)}')
            continue
        col = {k: header.index(label) for k, label in COLUMNS.items()}
        for n, row in enumerate(rows, start=2):
            if row is None or all(c is None for c in row):
                continue
            try:
                rarity = int(row[col["rarity"]])
                if rarity not in (3, 4, 5):
                    raise ValueError(f"unknown rarity {rarity}")
                name = str(row[col["name"]] or "").strip()
                if not name:
                    raise ValueError("empty name")
                out.append(IncomingWish(id=None, pool=pool, gacha_type=SINGLE_TYPE.get(pool),
                                        time=normalize_time(row[col["time"]]), name=name,
                                        item_type=item_type_of(row[col["type"]]), rarity=rarity))
            except (ValueError, TypeError, IndexError, OverflowError) as e:
                errors.append(f'sheet "{ws.title}" row {n}: {e}')
    wb.close()
    if errors:
        raise ImportFailed(bad_rows_message(errors))
    return out
