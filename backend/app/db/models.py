"""SQLite tables. Three categories: game data, account data (overwritten by sync), user data."""
from datetime import datetime

from sqlalchemy import JSON, Boolean, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
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


class GameMaterial(Base):
    __tablename__ = "game_material"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    icon: Mapped[str] = mapped_column(String)
    rarity: Mapped[int] = mapped_column(Integer)
    yatta_type: Mapped[str] = mapped_column(String)
    category: Mapped[str] = mapped_column(String)
    family: Mapped[int | None] = mapped_column(Integer, nullable=True)
    craft_from: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sources: Mapped[list] = mapped_column(JSON)
    sort_order: Mapped[int] = mapped_column(Integer)
    detail_fetched: Mapped[bool] = mapped_column(Boolean)


class GameDomain(Base):
    __tablename__ = "game_domain"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    kind: Mapped[str] = mapped_column(String)
    city: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekdays: Mapped[list] = mapped_column(JSON)
    material_ids: Mapped[list] = mapped_column(JSON)


class GameWeapon(Base):
    __tablename__ = "game_weapon"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)
    icon: Mapped[str] = mapped_column(String)
    rarity: Mapped[int] = mapped_column(Integer)
    weapon_type: Mapped[str] = mapped_column(String)


class GameArtifactSet(Base):
    __tablename__ = "game_artifact_set"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    name: Mapped[str] = mapped_column(String)
    icon: Mapped[str] = mapped_column(String)
    sort_order: Mapped[int] = mapped_column(Integer)


class GameBanner(Base):
    __tablename__ = "game_banner"
    key: Mapped[str] = mapped_column(String, primary_key=True)        # f"{pool}|{start}|{order}"
    pool: Mapped[str] = mapped_column(String)
    name: Mapped[str] = mapped_column(String)
    short_name: Mapped[str] = mapped_column(String)
    start: Mapped[str] = mapped_column(String)                       # as given by paimon.moe
    end: Mapped[str] = mapped_column(String)
    timezone_dependent: Mapped[bool] = mapped_column(Boolean)       # start is a UTC+8 instant
    timezone_dependent_end: Mapped[bool] = mapped_column(Boolean)   # end is a UTC+8 instant
    order: Mapped[int] = mapped_column(Integer)
    featured_5: Mapped[list] = mapped_column(JSON)                   # item ids
    featured_4: Mapped[list] = mapped_column(JSON)
    version: Mapped[str | None] = mapped_column(String, nullable=True)


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
    weapon_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
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
    weekly_discounts_left: Mapped[int | None] = mapped_column(Integer, nullable=True)
    weekly_discounts_max: Mapped[int | None] = mapped_column(Integer, nullable=True)
    expeditions: Mapped[list] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)


class SyncRun(Base):
    __tablename__ = "sync_run"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    trigger: Mapped[str] = mapped_column(String)
    parts: Mapped[dict] = mapped_column(JSON)


class MaterialGap(Base):
    __tablename__ = "material_gap"
    character_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    material_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    need: Mapped[int] = mapped_column(Integer)
    short: Mapped[int] = mapped_column(Integer)


class MaterialTotal(Base):
    __tablename__ = "material_total"
    material_id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String)   # HoYoLAB's name/icon, used for ids missing from the catalogue
    icon: Mapped[str] = mapped_column(String)
    rarity: Mapped[int] = mapped_column(Integer)
    need: Mapped[int] = mapped_column(Integer)
    short: Mapped[int] = mapped_column(Integer)
    spare: Mapped[int] = mapped_column(Integer)


class GapRun(Base):
    __tablename__ = "gap_run"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    computed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    snapshot: Mapped[list | None] = mapped_column(JSON, nullable=True)
    ok: Mapped[bool] = mapped_column(Boolean)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    skipped: Mapped[list] = mapped_column(JSON)


class HoyolabSnapshot(Base):
    __tablename__ = "hoyolab_snapshot"
    part: Mapped[str] = mapped_column(String, primary_key=True)          # calendar | profile
    data: Mapped[dict] = mapped_column(JSON)
    fetched_at: Mapped[datetime] = mapped_column(DateTime)


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
    planned_weapon_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class WeeklyBossDone(Base):
    __tablename__ = "weekly_boss_done"
    boss: Mapped[str] = mapped_column(String, primary_key=True)
    week_start: Mapped[datetime] = mapped_column(DateTime, primary_key=True)


class Team(Base):
    __tablename__ = "team"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    notes: Mapped[str] = mapped_column(String)
    sort_order: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class TeamMember(Base):
    __tablename__ = "team_member"
    __table_args__ = (UniqueConstraint("team_id", "character_id", name="uq_team_member_character"),)
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id", ondelete="CASCADE"), primary_key=True)
    slot: Mapped[int] = mapped_column(Integer, primary_key=True)                 # 0-3, contiguous
    character_id: Mapped[int] = mapped_column(Integer)                           # canonical id
    role: Mapped[str] = mapped_column(String)


class Tag(Base):
    __tablename__ = "tag"
    __table_args__ = (UniqueConstraint("name_key", name="uq_tag_name_key"),)
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String)
    name_key: Mapped[str] = mapped_column(String)                                # name.lower()
    color: Mapped[str] = mapped_column(String)
    builtin: Mapped[bool] = mapped_column(Boolean)


class TeamTag(Base):
    __tablename__ = "team_tag"
    team_id: Mapped[int] = mapped_column(Integer, ForeignKey("team.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tag.id", ondelete="CASCADE"), primary_key=True)


class Wish(Base):
    __tablename__ = "wish"
    __table_args__ = (
        UniqueConstraint("id", name="uq_wish_id"),
        Index("ix_wish_pool_time_seq", "pool", "time", "seq"),
    )
    pk: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    id: Mapped[str | None] = mapped_column(String, nullable=True)     # real pull id; None for paimon rows
    pool: Mapped[str] = mapped_column(String)
    gacha_type: Mapped[str | None] = mapped_column(String, nullable=True)
    time: Mapped[str] = mapped_column(String)                        # server-local "YYYY-MM-DD HH:MM:SS"
    seq: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String)
    item_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    item_type: Mapped[str] = mapped_column(String)                   # character | weapon
    rarity: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String)                      # game | uigf | paimon
    imported_at: Mapped[datetime] = mapped_column(DateTime)


class WishImport(Base):
    __tablename__ = "wish_import"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    started_at: Mapped[datetime] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    source: Mapped[str] = mapped_column(String)
    ok: Mapped[bool | None] = mapped_column(Boolean, nullable=True)   # None while running
    added: Mapped[int] = mapped_column(Integer)
    upgraded: Mapped[int] = mapped_column(Integer)
    skipped: Mapped[int] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(String, nullable=True)
    backup_file: Mapped[str | None] = mapped_column(String, nullable=True)
    snapshot_file: Mapped[str | None] = mapped_column(String, nullable=True)


class WishChart(Base):
    __tablename__ = "wish_chart"
    pool: Mapped[str] = mapped_column(String, primary_key=True)      # weapon | chronicled
    item_id: Mapped[int] = mapped_column(Integer)
    set_at: Mapped[datetime] = mapped_column(DateTime)


class Setting(Base):
    __tablename__ = "setting"
    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[object | None] = mapped_column(JSON, nullable=True)


class ChallengeRun(Base):
    __tablename__ = "challenge_run"
    kind: Mapped[str] = mapped_column(String, primary_key=True)          # abyss | theater | stygian
    season: Mapped[str] = mapped_column(String, primary_key=True)        # HoYoLAB period id
    start: Mapped[str | None] = mapped_column(String, nullable=True)     # iso UTC "...Z"
    end: Mapped[str | None] = mapped_column(String, nullable=True)
    summary: Mapped[dict] = mapped_column(JSON)
    teams: Mapped[list] = mapped_column(JSON)
    seen_at: Mapped[datetime] = mapped_column(DateTime)
    updated_at: Mapped[datetime] = mapped_column(DateTime)


class EventDone(Base):
    __tablename__ = "event_done"
    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    done_at: Mapped[datetime] = mapped_column(DateTime)


# --- GOOD import (user data; sync never writes these) -----------------------
class GoodImport(Base):
    __tablename__ = "good_import"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)          # always 1
    imported_at: Mapped[datetime] = mapped_column(DateTime)
    source: Mapped[str | None] = mapped_column(String, nullable=True)
    counts: Mapped[dict] = mapped_column(JSON)
    unmatched: Mapped[list] = mapped_column(JSON)


class GoodMaterial(Base):
    __tablename__ = "good_material"
    material_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    count: Mapped[int] = mapped_column(Integer)


class GoodWeaponRow(Base):
    __tablename__ = "good_weapon"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    weapon_id: Mapped[int] = mapped_column(Integer, index=True)
    level: Mapped[int] = mapped_column(Integer)
    ascension: Mapped[int] = mapped_column(Integer)
    refinement: Mapped[int] = mapped_column(Integer)
    location: Mapped[str | None] = mapped_column(String, nullable=True)     # raw GOOD character key
    character_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lock: Mapped[bool] = mapped_column(Boolean)


class GoodArtifactRow(Base):
    __tablename__ = "good_artifact"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    set_id: Mapped[int] = mapped_column(Integer)
    slot: Mapped[str] = mapped_column(String)
    rarity: Mapped[int] = mapped_column(Integer)
    level: Mapped[int] = mapped_column(Integer)
    main_stat: Mapped[str] = mapped_column(String)
    substats: Mapped[list] = mapped_column(JSON)
    location: Mapped[str | None] = mapped_column(String, nullable=True)
    character_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    lock: Mapped[bool] = mapped_column(Boolean)
