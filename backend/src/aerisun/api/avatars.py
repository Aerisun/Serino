from __future__ import annotations

from fastapi import APIRouter, Query, Response

from aerisun.domain.avatars.service import render_notionists_svg

AVATAR_CACHE_CONTROL = "public, max-age=31536000, immutable"

router = APIRouter(prefix="/api/v1/avatars", tags=["site"])


@router.get("/10.x/notionists/svg", summary="生成 Notionists SVG 头像")
def read_notionists_avatar(seed: str = Query("visitor", max_length=256)) -> Response:
    svg = render_notionists_svg(seed)
    return Response(
        content=svg.encode("utf-8"),
        media_type="image/svg+xml",
        headers={
            "Cache-Control": AVATAR_CACHE_CONTROL,
            "X-Content-Type-Options": "nosniff",
        },
    )
