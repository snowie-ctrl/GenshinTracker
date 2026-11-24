from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.artifacts.stats import SLOT_OPTIONS, SUB_KEYS


class TargetsIn(BaseModel):
    level: int = Field(ge=1, le=100)
    normal: int = Field(ge=1, le=10)
    skill: int = Field(ge=1, le=10)
    burst: int = Field(ge=1, le=10)
    weapon_level: int = Field(ge=1, le=90)
    constellation: int | None = Field(default=None, ge=0, le=6)
    refinement: int | None = Field(default=None, ge=1, le=5)


class ArtifactSetIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    set_id: int
    pieces: Literal[2, 4]


class ArtifactMainIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sands: list[str] = Field(default_factory=list)
    goblet: list[str] = Field(default_factory=list)
    circlet: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _allowed(self):
        for slot, options in SLOT_OPTIONS.items():
            values = getattr(self, slot)
            if len(set(values)) != len(values):
                raise ValueError(f"{slot}: a stat is listed twice")
            bad = [v for v in values if v not in options]
            if bad:
                raise ValueError(f"{slot}: not a {slot} main stat: {', '.join(bad)}")
        return self


class ArtifactTargetIn(BaseModel):
    """One 4-piece set, or up to two 2-piece sets; allowed main stats per slot; ordered substats."""
    model_config = ConfigDict(extra="forbid")
    sets: list[ArtifactSetIn] = Field(default_factory=list, max_length=2)
    main: ArtifactMainIn = Field(default_factory=ArtifactMainIn)
    subs: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _shape(self):
        if len(self.sets) == 2:
            if any(e.pieces != 2 for e in self.sets):
                raise ValueError("Two sets must both be 2-piece")
            if self.sets[0].set_id == self.sets[1].set_id:
                raise ValueError("Pick two different sets, or one 4-piece set")
        if len(set(self.subs)) != len(self.subs):
            raise ValueError("A substat is listed twice")
        bad = [v for v in self.subs if v not in SUB_KEYS]
        if bad:
            raise ValueError(f"Not a substat: {', '.join(bad)}")
        return self
