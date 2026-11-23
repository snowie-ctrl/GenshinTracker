"""One short line describing the artifact sets a character wears."""
from __future__ import annotations

from collections import Counter


def set_line(set_names: list[str]) -> str:
    counts = Counter(n for n in set_names if n)
    four = sorted(n for n, c in counts.items() if c >= 4)
    if four:
        return f"4pc {four[0]}"
    twos = sorted((n for n, c in counts.items() if c >= 2), key=lambda n: (-counts[n], n))
    return " + ".join(f"2pc {n}" for n in twos)


def artifact_sets(set_names: list[str], icons: dict[str, str]) -> list[dict]:
    """Same thresholds as set_line, as data: [{name, icon, pieces}] with pieces 4 or 2."""
    counts = Counter(n for n in set_names if n)
    four = sorted(n for n, c in counts.items() if c >= 4)
    if four:
        return [{"name": four[0], "icon": icons.get(four[0]), "pieces": 4}]
    twos = sorted((n for n, c in counts.items() if c >= 2), key=lambda n: (-counts[n], n))
    return [{"name": n, "icon": icons.get(n), "pieces": 2} for n in twos]
