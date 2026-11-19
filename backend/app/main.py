"""App factory: database, shared HTTP client, sync manager, API routers, built frontend."""
from __future__ import annotations

import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from app import config
from app.api import ROUTERS
from app.config import FRONTEND_BUILD, Paths, default_paths
from app.context import AppContext, make_source_factory
from app.db.engine import make_engine, make_session_factory, migrate
from app.gamedata.service import refresh
from app.sync.hoyolab import fetch_accounts
from app.sync.runner import SyncManager

log = logging.getLogger(__name__)
USER_AGENT = "GenshinTracker/0.1 (local personal tool)"


def create_app(paths: Paths | None = None, *, source_factory=None, accounts_fetcher=None,
               http_client: httpx.AsyncClient | None = None, offline: bool | None = None) -> FastAPI:
    paths = paths or default_paths()
    paths.ensure()
    engine = make_engine(paths.db_file)
    migrate(engine)
    session_factory = make_session_factory(engine)
    http = http_client or httpx.AsyncClient(headers={"User-Agent": USER_AGENT}, follow_redirects=True)
    is_offline = config.offline() if offline is None else offline

    async def on_unknown_ids(_ids: set[int]) -> None:
        if not is_offline:
            await refresh(session_factory, http, force=True)

    sync = SyncManager(session_factory, paths.db_file, paths.backups,
                       source_factory or make_source_factory(paths, session_factory), on_unknown_ids)
    ctx = AppContext(paths=paths, session_factory=session_factory, http=http, offline=is_offline,
                     sync=sync, accounts_fetcher=accounts_fetcher or fetch_accounts)

    @asynccontextmanager
    async def lifespan(_app: FastAPI):
        task = None if is_offline else asyncio.create_task(refresh(session_factory, http))
        yield
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await task
        if http_client is None:
            await http.aclose()
        engine.dispose()

    app = FastAPI(title="GenshinTracker", lifespan=lifespan)
    app.state.ctx = ctx

    @app.get("/api/health")
    def health() -> dict:
        return {"ok": True}

    for router in ROUTERS:
        app.include_router(router, prefix="/api")
    _mount_frontend(app, FRONTEND_BUILD)
    return app


def _mount_frontend(app: FastAPI, build_dir: Path) -> None:
    index = build_dir / "index.html"
    if not index.exists():
        @app.get("/", include_in_schema=False)
        def _not_built() -> HTMLResponse:
            return HTMLResponse("<h1>Frontend not built</h1><p>Run <code>python run.py</code> "
                                "or <code>cd frontend; npm install; npm run build</code>.</p>")
        return

    root = build_dir.resolve()

    @app.get("/{path:path}", include_in_schema=False)
    def _spa(path: str) -> FileResponse:
        if path.startswith("api/"):
            raise HTTPException(404)
        candidate = (build_dir / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)
