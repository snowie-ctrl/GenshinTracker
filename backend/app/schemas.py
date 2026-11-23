from pydantic import BaseModel, Field


class TargetsIn(BaseModel):
    level: int = Field(ge=1, le=100)
    normal: int = Field(ge=1, le=10)
    skill: int = Field(ge=1, le=10)
    burst: int = Field(ge=1, le=10)
    weapon_level: int = Field(ge=1, le=90)
    constellation: int | None = Field(default=None, ge=0, le=6)
    refinement: int | None = Field(default=None, ge=1, le=5)
