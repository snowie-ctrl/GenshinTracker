"""Pure rules shared by the API: status derivation, progress, target defaults."""
from __future__ import annotations

from dataclasses import asdict, dataclass

GOALS = ("none", "want", "build")


@dataclass(frozen=True)
class Targets:
    level: int
    normal: int
    skill: int
    burst: int
    weapon_level: int

    @classmethod
    def from_dict(cls, d: dict) -> Targets:
        return cls(
            level=int(d["level"]),
            normal=int(d["normal"]),
            skill=int(d["skill"]),
            burst=int(d["burst"]),
            weapon_level=int(d["weapon_level"]),
        )

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Current:
    level: int
    normal: int | None
    skill: int | None
    burst: int | None


def derive_status(owned: bool, goal: str) -> tuple[str, bool]:
    """Return (status, prefarming). Ownership comes from sync; intent from the goal."""
    if goal not in GOALS:
        raise ValueError(f"unknown goal: {goal!r}")
    if owned:
        return ("building", False) if goal == "build" else ("obtained", False)
    if goal == "none":
        return ("unobtained", False)
    return ("wanted", goal == "build")


def progress(current: Current, targets: Targets) -> float:
    """Average of level and three talents, each counted up to its target (weapon excluded)."""
    pairs = [
        (current.level, targets.level),
        (current.normal or 1, targets.normal),
        (current.skill or 1, targets.skill),
        (current.burst or 1, targets.burst),
    ]
    parts = [1.0 if target <= cur else cur / target for cur, target in pairs]
    return round(sum(parts) / len(parts), 4)


def resolve_targets(goal: str, stored: Targets | None, defaults: Targets) -> Targets | None:
    """Targets to keep after a goal change. Choosing build fills defaults once; stored targets survive."""
    if goal == "build" and stored is None:
        return defaults
    return stored
