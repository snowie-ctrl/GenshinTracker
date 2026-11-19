"""SQLite tables. Three categories: game data, account data (overwritten by sync), user data."""
from datetime import datetime

from sqlalchemy import JSON, DateTime, Integer, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


# --- game data -------------------------------------------------------------
class GameCharacter(Base):
    __tablename__ = "game_character"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    slug: Mapped[str] = mapped_column(String, unique=True)
    rarity: Mapped[int] = mapped_column(Integer)
    element: Mapped[str | None] = mapped_column(String, nullable=True)
    weapon_type: Mapped[str] = mapped_column(String)
    region: Mapped[str | None] = mapped_column(String, nullable=True)
    icon: Mapped[str] = mapped_column(String)
    splash: Mapped[str] = mapped_column(String)
    release_at: Mapped[datetime] = mapped_column(DateTime)


class GameMeta(Base):
    __tablename__ = "game_meta"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[object | None] = mapped_column(JSON, nullable=True)


# --- account data (sync overwrites) ----------------------------------------
class OwnedCharacter(Base):
    __tablename__ = "owned_character"
    character_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    element: Mapped[str | None] = mapped_column(String, nullable=True)
    icon: Mapped[str | None] = mapped_column(String, nullable=True)
    level: Mapped[int] = mapped_column(Integer)
    constellation: Mapped[int] = mapped_column(Integer)
    friendship: Mapped[int] = mapped_column(Integer)
    talent_normal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    talent_skill: Mapped[int | None] = mapped_column(Integer, nullable=True)
    talent_burst: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weapon_name: Mapped[str] = mapped_column(String)
    weapon_icon: Mapped[str] = mapped_column(String)
    weapon_rarity: Mapped[int] = mapped_column(Integer)
    weapon_level: Mapped[int] = mapped_column(Integer)
    weapon_refinement: Mapped[int] = mapped_column(Integer)
    stats: Mapped[list] = mapped_column(JSON)
    synced_at: Mapped[datetime] = mapped_column(DateTime)


class OwnedArtifact(Base):
    __tablename__ = "owned_artifact"
    character_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)
    set_name: Mapped[str] = mapped_column(String)
    rarity: Mapped[int] = mapped_column(Integer)
    level: Mapped[int] = mapped_column(Integer)
    main_stat: Mapped[str] = mapped_column(String)
    substats: Mapped[list] = mapped_column(JSON)
    icon: Mapped[str] = mapped_column(String)


class LiveNotes(Base):
    __tablename__ = "live_notes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    resin: Mapped[int] = mapped_column(Integer)
    resin_max: Mapped[int] = mapped_column(Integer)
    resin_full_at: Mapped[datetime] = mapped_column(DateTime)
    commissions_done: Mapped[int] = mapped_column(Integer)
    commissions_max: Mapped[int] = mapped_column(Integer)
    realm_currency: Mapped[int] = mapped_column(Integer)
    realm_currency_max: Mapped[int] = mapped_column(Integer)
    expeditions: Mapped[list] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)


class SyncRun(Base):
    __tablename__ = "sync_run"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trigger: Mapped[str] = mapped_column(String)
    parts: Mapped[dict] = mapped_column(JSON)


# --- user data (sync never writes, except setting.hoyolab_status) ----------
class CharacterGoal(Base):
    __tablename__ = "character_goal"
    character_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    goal: Mapped[str] = mapped_column(String)
    target_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_normal: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_skill: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_burst: Mapped[int | None] = mapped_column(Integer, nullable=True)
    target_weapon_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class Setting(Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[object | None] = mapped_column(JSON, nullable=True)
