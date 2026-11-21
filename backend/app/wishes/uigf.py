"""UIGF (uigf.org) v3/v4 import and v4 export for Genshin (hk4e)."""
from __future__ import annotations

import calendar
from datetime import datetime
from typing import Sequence

from app.db.models import Wish
from app.wishes.types import (POOL_BY_GACHA_TYPE, SINGLE_TYPE, UID_MISMATCH, ImportFailed, IncomingWish,
                              bad_rows_message, item_type_of, normalize_time, shift_time, to_utc_seconds)

GEN_MARK = "9"
NOT_UIGF = "This file is not a UIGF export."


def generated_id(time: str, seq: int, offset: int) -> str:
    return f"{to_utc_seconds(time, offset):010d}{GEN_MARK}{seq:08d}"


def is_generated(id_: str, time: str, offset: int) -> bool:
    return (len(id_) == 19 and id_[10] == GEN_MARK
            and id_[:10] == f"{to_utc_seconds(time, offset):010d}")


def _tz(value) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ImportFailed(NOT_UIGF)


def _rows(value) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ImportFailed(NOT_UIGF)
    return value


def _entries(data: dict, uid: int) -> tuple[list, int | None]:
    if isinstance(data.get("hk4e"), list):
        mine = [e for e in data["hk4e"] if isinstance(e, dict) and str(e.get("uid")) == str(uid)]
        if not mine:
            raise ImportFailed(UID_MISMATCH)
        return _rows(mine[0].get("list")), _tz(mine[0].get("timezone"))
    info = data.get("info")
    if isinstance(info, dict) and isinstance(data.get("list"), list):
        if str(info.get("uid")) != str(uid):
            raise ImportFailed(UID_MISMATCH)
        return list(data["list"]), _tz(info.get("region_time_zone"))
    raise ImportFailed(NOT_UIGF)


def parse_uigf(data: dict, uid: int, offset: int) -> list[IncomingWish]:
    if not isinstance(data, dict):
        raise ImportFailed(NOT_UIGF)
    rows, tz = _entries(data, uid)
    tz = offset if tz is None else tz
    out, errors = [], []
    for i, r in enumerate(rows, start=1):
        if not isinstance(r, dict):
            errors.append(f"row {i}: not an object")
            continue
        try:
            gacha_type = str(r.get("gacha_type") or "")
            uigf_type = str(r.get("uigf_gacha_type") or gacha_type)
            if uigf_type not in POOL_BY_GACHA_TYPE:
                raise ValueError(f"unknown banner type {uigf_type!r}")
            time = normalize_time(r["time"])
            if tz != offset:
                time = shift_time(time, tz, offset)
            rarity = int(r["rank_type"])
            if rarity not in (3, 4, 5):
                raise ValueError(f"unknown rarity {rarity}")
            name = str(r["name"]).strip()
            if not name:
                raise ValueError("empty name")
            id_ = str(r.get("id") or "").strip() or None
            if id_ is not None and is_generated(id_, time, offset):
                id_ = None
            out.append(IncomingWish(id=id_, pool=POOL_BY_GACHA_TYPE[uigf_type],
                                    gacha_type=gacha_type if gacha_type in POOL_BY_GACHA_TYPE else None,
                                    time=time, name=name, item_type=item_type_of(r["item_type"]), rarity=rarity))
        except KeyError as e:
            errors.append(f"row {i}: missing {e.args[0]}")
        except (ValueError, TypeError) as e:
            errors.append(f"row {i}: {e}")
    if errors:
        raise ImportFailed(bad_rows_message(errors))
    return out


def build_uigf(rows: Sequence[Wish], uid: int, offset: int, now: datetime, app_version: str) -> dict:
    records = []
    for w in sorted(rows, key=lambda w: (w.time, w.pool, w.seq)):
        gacha_type = w.gacha_type or ("301" if w.pool == "character" else SINGLE_TYPE[w.pool])
        records.append({
            "uigf_gacha_type": "301" if gacha_type in ("301", "400") else gacha_type,
            "gacha_type": gacha_type,
            "item_id": str(w.item_id) if w.item_id else "",
            "count": "1",
            "time": w.time,
            "name": w.name,
            "item_type": w.item_type.capitalize(),
            "rank_type": str(w.rarity),
            "id": w.id or generated_id(w.time, w.seq, offset),
        })
    return {
        "info": {"export_timestamp": calendar.timegm(now.timetuple()), "export_app": "GenshinTracker",
                 "export_app_version": app_version, "version": "v4.0"},
        "hk4e": [{"uid": uid, "timezone": offset, "lang": "en-us", "list": records}],
    }
