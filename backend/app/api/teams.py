"""Teams and tags. The only side effect on other data is raising goals to build (app.teams.goals)."""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.characters import _all, character_payload
from app.api.planner import gaps_for, is_connected, planner_view
from app.context import AppContext, get_ctx
from app.db.models import OwnedArtifact
from app.teams import store
from app.teams.artifacts import set_line
from app.teams.store import MemberIn, TeamError
from app.teams.view import team_view

router = APIRouter()


class MemberBody(BaseModel):
    character_id: int
    role: str = ""


class TeamBody(BaseModel):
    name: str
    notes: str = ""
    members: list[MemberBody]
    tag_ids: list[int] = []
    new_tags: list[str] = []


class OrderBody(BaseModel):
    ids: list[int]


class TagBody(BaseModel):
    name: str
    color: str | None = None


class TagPatch(BaseModel):
    name: str | None = None
    color: str | None = None


def artifact_lines(s: Session) -> dict[int, str]:
    sets: dict[int, list[str]] = {}
    for a in s.scalars(select(OwnedArtifact)):
        sets.setdefault(a.character_id, []).append(a.set_name)
    return {cid: set_line(names) for cid, names in sets.items()}


def team_views(s: Session) -> list[dict]:
    chars = {p["id"]: p for p in (character_payload(g, o, r) for g, o, r in _all(s))}
    data, index = planner_view(s)
    arts = artifact_lines(s)
    return [team_view(t, members, tags, chars, arts, data, index) for t, members, tags in store.team_rows(s)]


def _one(s: Session, team_id: int) -> dict:
    for v in team_views(s):
        if v["id"] == team_id:
            return v
    raise HTTPException(404, "Team not found")


def _save(ctx: AppContext, team_id: int | None, body: TeamBody) -> dict:
    try:
        with ctx.session_factory.begin() as s:
            team, raised = store.save_team(s, team_id, body.name, body.notes,
                                           [MemberIn(m.character_id, m.role) for m in body.members],
                                           body.tag_ids, body.new_tags)
            tid = team.id
    except TeamError as e:
        raise HTTPException(e.status, e.message) from None
    if raised:
        ctx.sync.schedule_gaps()
    with ctx.session_factory() as s:
        return {"team": _one(s, tid), "raised": raised}


def _write(ctx: AppContext, fn) -> object:
    try:
        with ctx.session_factory.begin() as s:
            result = fn(s)
            return store.tag_dict(result) if result is not None else {"ok": True}
    except TeamError as e:
        raise HTTPException(e.status, e.message) from None


@router.get("/teams")
def list_teams(ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        return {"gaps": gaps_for(ctx, s), "connected": is_connected(ctx, s), "teams": team_views(s)}


@router.post("/teams")
async def create_team(body: TeamBody, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _save(ctx, None, body)


@router.put("/teams/order")
def reorder_teams(body: OrderBody, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _write(ctx, lambda s: store.reorder(s, body.ids))


@router.get("/teams/{team_id}")
def get_team(team_id: int, ctx: AppContext = Depends(get_ctx)) -> dict:
    with ctx.session_factory() as s:
        return {"gaps": gaps_for(ctx, s), "connected": is_connected(ctx, s), "team": _one(s, team_id)}


@router.put("/teams/{team_id}")
async def update_team(team_id: int, body: TeamBody, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _save(ctx, team_id, body)


@router.delete("/teams/{team_id}")
def remove_team(team_id: int, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _write(ctx, lambda s: store.delete_team(s, team_id))


@router.get("/tags")
def get_tags(ctx: AppContext = Depends(get_ctx)) -> list[dict]:
    with ctx.session_factory() as s:
        return store.list_tags(s)


@router.post("/tags")
def add_tag(body: TagBody, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _write(ctx, lambda s: store.create_tag(s, body.name, body.color))


@router.put("/tags/{tag_id}")
def edit_tag(tag_id: int, body: TagPatch, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _write(ctx, lambda s: store.update_tag(s, tag_id, body.name, body.color))


@router.delete("/tags/{tag_id}")
def remove_tag(tag_id: int, ctx: AppContext = Depends(get_ctx)) -> dict:
    return _write(ctx, lambda s: store.delete_tag(s, tag_id))
