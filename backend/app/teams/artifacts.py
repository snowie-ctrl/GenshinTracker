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
