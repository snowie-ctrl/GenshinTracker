"""Validate and parse a GOOD (Genshin Open Object Description) export. In memory only; nothing is logged."""
from __future__ import annotations

import json
from dataclasses import dataclass

SUPPORTED_VERSIONS = (1, 2, 3)
SLOTS: tuple[str, ...] = ("flower", "plume", "sands", "goblet", "circlet")
SOURCE_MAX = 64


class GoodFormatError(ValueError):
    """A user-facing reason the file was rejected."""


@dataclass(frozen=True)
class GoodWeapon:
    key: str
    level: int
    ascension: int
    refinement: int
    location: str
    lock: bool


@dataclass(frozen=True)
class GoodArtifact:
    set_key: str
    slot: str
    rarity: int
    level: int
    main_stat: str
    substats: tuple[tuple[str, float], ...]
    location: str
    lock: bool


@dataclass(frozen=True)
class GoodFile:
    version: int
    source: str | None
    materials: dict[str, int]
    weapons: list[GoodWeapon]
    artifacts: list[GoodArtifact]


def _bad(block: str) -> GoodFormatError:
    return GoodFormatError(f"The {block} section of this GOOD file is not in the expected format")


def _int(value, block: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise _bad(block)
    return value


def _str(value, block: str, required: bool = True) -> str:
    if value is None and not required:
        return ""
    if not isinstance(value, str) or (required and not value):
        raise _bad(block)
    return value


def _materials(value) -> dict[str, int]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise _bad("materials")
    return {_str(k, "materials"): _int(v, "materials") for k, v in value.items()}


def _list(value, block: str) -> list[dict]:
    if value is None:
        return []
    if not isinstance(value, list) or not all(isinstance(x, dict) for x in value):
        raise _bad(block)
    return value


def _weapon(w: dict) -> GoodWeapon:
    b = "weapons"
    return GoodWeapon(_str(w.get("key"), b), _int(w.get("level"), b, 1), _int(w.get("ascension", 0), b),
                      _int(w.get("refinement"), b, 1), _str(w.get("location"), b, required=False),
                      bool(w.get("lock", False)))


def _artifact(a: dict) -> GoodArtifact:
    b = "artifacts"
    slot = _str(a.get("slotKey"), b)
    if slot not in SLOTS:
        raise _bad(b)
    subs_raw = a.get("substats", [])
    if not isinstance(subs_raw, list) or not all(isinstance(x, dict) for x in subs_raw):
        raise _bad(b)
    subs: list[tuple[str, float]] = []
    for sub in subs_raw:
        key, value = sub.get("key"), sub.get("value")
        if not key:
            continue                      # scanners emit {"key": ""} for unrolled substats
        if not isinstance(key, str) or isinstance(value, bool) or not isinstance(value, (int, float)):
            raise _bad(b)
        subs.append((key, float(value)))
    return GoodArtifact(_str(a.get("setKey"), b), slot, _int(a.get("rarity"), b, 1), _int(a.get("level"), b),
                        _str(a.get("mainStatKey"), b), tuple(subs), _str(a.get("location"), b, required=False),
                        bool(a.get("lock", False)))


def parse_good(content: bytes) -> GoodFile:
    try:
        body = json.loads(content.decode("utf-8-sig"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise GoodFormatError("Not a GOOD file (could not read JSON)") from None
    if not isinstance(body, dict) or body.get("format") != "GOOD":
        raise GoodFormatError("Not a GOOD file")
    version = body.get("version")
    if isinstance(version, bool) or not isinstance(version, int) or version not in SUPPORTED_VERSIONS:
        raise GoodFormatError(f"Unsupported GOOD version {version}")
    source = body.get("source")
    return GoodFile(
        version=version,
        source=source[:SOURCE_MAX] if isinstance(source, str) and source else None,
        materials=_materials(body.get("materials")),
        weapons=[_weapon(w) for w in _list(body.get("weapons"), "weapons")],
        artifacts=[_artifact(a) for a in _list(body.get("artifacts"), "artifacts")],
    )
