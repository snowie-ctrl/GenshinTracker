"""Traveler element ids. Inside Ad Astra the Traveler is one character per element; HoYoLAB only knows
the body id (10000005 boy, 10000007 girl) plus a calculator element number. Pure helpers, no I/O."""
from __future__ import annotations

BASE = 10000005
BODY_IDS: dict[str, int] = {"boy": 10000005, "girl": 10000007}
MANEKIN_RAW_IDS = frozenset({10000117, 10000118})
# HoYoLAB calculator element numbers (genshin.py CALCULATOR_ELEMENTS)
TRAVELER_ELEMENTS: dict[str, int] = {"Pyro": 1, "Anemo": 2, "Geo": 3, "Dendro": 4, "Electro": 5, "Hydro": 6, "Cryo": 7}
TRAVELER_IDS: dict[int, str] = {BASE * 100 + n: el for el, n in TRAVELER_ELEMENTS.items()}
TRAVELER_PENDING = BASE  # a Traveler whose element is not known yet; persist resolves it to the current element


def traveler_id(element: str) -> int:
    return BASE * 100 + TRAVELER_ELEMENTS[element]


def is_traveler(cid: int) -> bool:
    return cid in TRAVELER_IDS


def element_of(cid: int) -> str:
    return TRAVELER_IDS[cid]


def calc_element(cid: int) -> int:
    return TRAVELER_ELEMENTS[TRAVELER_IDS[cid]]


def body_of(raw_id: int) -> str | None:
    return next((b for b, i in BODY_IDS.items() if i == raw_id), None)


def traveler_name(element: str) -> str:
    return f"{element} Traveler"


def body_icon(body: str) -> str:
    return "UI_AvatarIcon_PlayerBoy" if body == "boy" else "UI_AvatarIcon_PlayerGirl"
