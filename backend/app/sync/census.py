"""TEMPORARY diagnostic: which fields do raw HoYoLAB responses carry?

Records key paths and value types only. The only values kept are the true/false counts of
`has_set_recommend_prop` and, for `lineup_recommend`, its type plus the host of a link (or a
string's length). No names, ids, text or query strings are stored. Remove once checked.
"""
from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

_BOOL_COUNTS = {"has_set_recommend_prop"}
_DESCRIBE = {"lineup_recommend"}


def _type(v: Any) -> str:
    if v is None:
        return "null"
    if isinstance(v, bool):
        return "bool"
    return {int: "int", float: "float", str: "str", dict: "dict", list: "list"}.get(type(v), type(v).__name__)


def _describe(v: Any) -> str:
    if isinstance(v, str):
        host = urlparse(v).netloc if v.startswith(("http://", "https://")) else ""
        return f"str host={host}" if host else f"str len={len(v)}"
    return _type(v)


def _walk(v: Any, path: str, out: dict) -> None:
    key = path or "$"
    types = out["types"].setdefault(key, [])
    t = _type(v)
    if t not in types:
        types.append(t)
    name = path.rsplit(".", 1)[-1]
    if name in _BOOL_COUNTS and isinstance(v, bool):
        counts = out["kept"].setdefault(key, {"true": 0, "false": 0})
        counts["true" if v else "false"] += 1
    if name in _DESCRIBE:
        seen = out["kept"].setdefault(key, [])
        d = _describe(v)
        if d not in seen:
            seen.append(d)
    if isinstance(v, dict):
        for k, child in v.items():
            part = "<n>" if str(k).isdigit() else str(k)
            _walk(child, f"{path}.{part}" if path else part, out)
    elif isinstance(v, list):
        for item in v:
            _walk(item, f"{path}[]", out)


def field_census(raw: Any, into: dict | None = None) -> dict:
    """Add `raw`'s key paths and types to `into` (a new census when None) and return it."""
    out = into if into is not None else {"types": {}, "kept": {}}
    out.setdefault("types", {})
    out.setdefault("kept", {})
    _walk(raw, "", out)
    return out
