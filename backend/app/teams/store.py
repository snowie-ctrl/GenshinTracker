"""Team and tag writes and reads. Every function works inside the caller's transaction."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.db.models import GameCharacter, OwnedCharacter, Tag, Team, TeamMember, TeamTag
from app.settings.store import default_targets
from app.teams.goals import raise_to_build
from app.timeutil import utcnow

BUILD_TAG_ID = 1
TAG_COLORS = ("orange", "red", "yellow", "green", "teal", "blue", "purple", "pink", "navy", "gold")
NAME_MAX, NOTES_MAX, ROLE_MAX, TAG_MAX, MEMBERS_MAX = 60, 2000, 40, 30, 4


class TeamError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


@dataclass(frozen=True)
class MemberIn:
    character_id: int
    role: str = ""


def _text(raw: str, max_len: int, what: str, required: bool = True) -> str:
    value = (raw or "").strip()
    if required and not value:
        raise TeamError(422, f"{what} is required")
    if len(value) > max_len:
        raise TeamError(422, f"{what} can be at most {max_len} characters")
    return value


def _known_character(s: Session, cid: int) -> bool:
    if s.get(OwnedCharacter, cid) is not None:
        return True
    g = s.get(GameCharacter, cid)
    return g is not None and g.release_at <= utcnow()


def tag_dict(t: Tag) -> dict:
    return {"id": t.id, "name": t.name, "color": t.color, "builtin": t.builtin}


def _tag_order(t: Tag) -> tuple:
    return (not t.builtin, t.name_key)


def _find_tag(s: Session, name: str) -> Tag | None:
    return s.scalar(select(Tag).where(Tag.name_key == name.strip().lower()))


def create_tag(s: Session, name: str, color: str | None = None) -> Tag:
    clean = _text(name, TAG_MAX, "Tag name")
    if _find_tag(s, clean) is not None:
        raise TeamError(409, "A tag with that name exists")
    if color is None:
        count = s.scalar(select(func.count()).select_from(Tag)) or 0
        color = TAG_COLORS[count % len(TAG_COLORS)]
    elif color not in TAG_COLORS:
        raise TeamError(422, "Unknown tag colour")
    tag = Tag(name=clean, name_key=clean.lower(), color=color, builtin=False)
    s.add(tag)
    s.flush()
    return tag


def update_tag(s: Session, tag_id: int, name: str | None, color: str | None) -> Tag:
    tag = s.get(Tag, tag_id)
    if tag is None:
        raise TeamError(404, "Tag not found")
    if name is not None:
        clean = _text(name, TAG_MAX, "Tag name")
        if clean != tag.name:
            if tag.builtin:
                raise TeamError(409, "Build is a built-in tag")
            other = _find_tag(s, clean)
            if other is not None and other.id != tag.id:
                raise TeamError(409, "A tag with that name exists")
            tag.name, tag.name_key = clean, clean.lower()
    if color is not None:
        if color not in TAG_COLORS:
            raise TeamError(422, "Unknown tag colour")
        tag.color = color
    s.flush()
    return tag


def delete_tag(s: Session, tag_id: int) -> None:
    tag = s.get(Tag, tag_id)
    if tag is None:
        raise TeamError(404, "Tag not found")
    if tag.builtin:
        raise TeamError(409, "Build is a built-in tag")
    s.execute(delete(Tag).where(Tag.id == tag_id))


def list_tags(s: Session) -> list[dict]:
    counts = dict(s.execute(select(TeamTag.tag_id, func.count()).group_by(TeamTag.tag_id)).all())
    tags = sorted(s.scalars(select(Tag)), key=_tag_order)
    return [{**tag_dict(t), "team_count": counts.get(t.id, 0)} for t in tags]


def save_team(s: Session, team_id: int | None, name: str, notes: str, members: list[MemberIn],
              tag_ids: list[int], new_tags: list[str]) -> tuple[Team, list[int]]:
    clean_name = _text(name, NAME_MAX, "Team name")
    clean_notes = _text(notes, NOTES_MAX, "Notes", required=False)
    if not 1 <= len(members) <= MEMBERS_MAX:
        raise TeamError(422, "A team needs 1 to 4 members")
    ids = [m.character_id for m in members]
    if len(set(ids)) != len(ids):
        raise TeamError(422, "A character can be in a team only once")
    roles = [_text(m.role, ROLE_MAX, "Role", required=False) for m in members]
    for cid in ids:
        if not _known_character(s, cid):
            raise TeamError(422, f"Unknown character {cid}")
    final_tags: list[int] = []
    for tid in tag_ids:
        if s.get(Tag, tid) is None:
            raise TeamError(422, "Unknown tag")
        if tid not in final_tags:
            final_tags.append(tid)

    if team_id is None:
        lowest = s.scalar(select(func.min(Team.sort_order)))
        team = Team(name=clean_name, notes=clean_notes, sort_order=(lowest if lowest is not None else 1) - 1,
                    created_at=utcnow(), updated_at=utcnow())
        s.add(team)
        s.flush()
        old_members: set[int] = set()
        had_build = False
    else:
        team = s.get(Team, team_id)
        if team is None:
            raise TeamError(404, "Team not found")
        old_members = set(s.scalars(select(TeamMember.character_id).where(TeamMember.team_id == team.id)))
        had_build = s.get(TeamTag, (team.id, BUILD_TAG_ID)) is not None

    for raw in new_tags:
        if not (raw or "").strip():
            continue
        tag = _find_tag(s, raw) or create_tag(s, raw)
        if tag.id not in final_tags:
            final_tags.append(tag.id)

    s.execute(delete(TeamMember).where(TeamMember.team_id == team.id))
    s.execute(delete(TeamTag).where(TeamTag.team_id == team.id))
    s.flush()
    for slot, (cid, role) in enumerate(zip(ids, roles)):
        s.add(TeamMember(team_id=team.id, slot=slot, character_id=cid, role=role))
    for tid in final_tags:
        s.add(TeamTag(team_id=team.id, tag_id=tid))
    team.name, team.notes, team.updated_at = clean_name, clean_notes, utcnow()
    s.flush()

    to_raise: list[int] = []
    if BUILD_TAG_ID in final_tags:
        to_raise = ids if not had_build else [cid for cid in ids if cid not in old_members]
    raised = raise_to_build(s, to_raise, default_targets(s)) if to_raise else []
    return team, raised


def delete_team(s: Session, team_id: int) -> None:
    if s.get(Team, team_id) is None:
        raise TeamError(404, "Team not found")
    s.execute(delete(Team).where(Team.id == team_id))


def reorder(s: Session, ids: list[int]) -> None:
    teams = {t.id: t for t in s.scalars(select(Team))}
    if len(ids) != len(set(ids)) or set(ids) != set(teams):
        raise TeamError(422, "The order must list every team once")
    for order, tid in enumerate(ids):
        teams[tid].sort_order = order
    s.flush()


def team_rows(s: Session) -> list[tuple[Team, list[TeamMember], list[Tag]]]:
    teams = s.scalars(select(Team).order_by(Team.sort_order, Team.id)).all()
    members: dict[int, list[TeamMember]] = {}
    for m in s.scalars(select(TeamMember).order_by(TeamMember.team_id, TeamMember.slot)):
        members.setdefault(m.team_id, []).append(m)
    tags = {t.id: t for t in s.scalars(select(Tag))}
    links: dict[int, list[Tag]] = {}
    for link in s.scalars(select(TeamTag)):
        links.setdefault(link.team_id, []).append(tags[link.tag_id])
    for tag_list in links.values():
        tag_list.sort(key=_tag_order)
    return [(t, members.get(t.id, []), links.get(t.id, [])) for t in teams]


def memberships(s: Session) -> dict[int, list[dict]]:
    out: dict[int, list[dict]] = {}
    for team, members, tags in team_rows(s):
        ref = {"id": team.id, "name": team.name, "tags": [tag_dict(t) for t in tags]}
        for m in members:
            out.setdefault(m.character_id, []).append(ref)
    return out
