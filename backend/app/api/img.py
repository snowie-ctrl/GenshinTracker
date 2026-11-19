from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.context import AppContext, get_ctx
from app.gamedata.images import ImageResult, get_named, get_remote

router = APIRouter()


def _response(result: ImageResult) -> Response:
    cache = "public, max-age=604800" if result.cached else "no-store"
    return Response(result.data, media_type=result.media_type, headers={"Cache-Control": cache})


@router.get("/img/remote")
async def img_remote(url: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    try:
        return _response(await get_remote(ctx.paths.img_cache, ctx.http, url, offline=ctx.offline))
    except ValueError:
        raise HTTPException(400, "Image host not allowed") from None


@router.get("/img/{name}")
async def img_named(name: str, ctx: AppContext = Depends(get_ctx)) -> Response:
    try:
        return _response(await get_named(ctx.paths.img_cache, ctx.http, name, offline=ctx.offline))
    except ValueError:
        raise HTTPException(400, "Bad image name") from None
