"""GOOD keys: the English name in PascalCase with punctuation removed, e.g. "Wolf's Gravestone" -> WolfsGravestone."""
from __future__ import annotations

import re
import unicodedata

_WORD_SPLIT = re.compile(r"[\s\-]+")
_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


def good_key(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    parts = (_NON_ALNUM.sub("", w) for w in _WORD_SPLIT.split(ascii_name))
    return "".join(p[0].upper() + p[1:] for p in parts if p)
