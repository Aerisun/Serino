from __future__ import annotations

from fastapi import APIRouter, Response, status
from fastapi.responses import JSONResponse

from aerisun.core.settings import get_settings
from aerisun.domain.agent.install import (
    build_claude_install_script,
    build_claude_marketplace,
    build_codex_install_script,
    build_mcp_install_manifest,
)

router = APIRouter(prefix="/mcp/install", tags=["mcp-install"], include_in_schema=False)
CACHE_HEADERS = {"Cache-Control": "public, max-age=300"}


@router.get("", status_code=status.HTTP_200_OK, summary="获取 MCP 安装入口")
def mcp_install_manifest() -> JSONResponse:
    payload = build_mcp_install_manifest(get_settings().site_url)
    return JSONResponse(payload, headers=CACHE_HEADERS)


@router.get("/claude-marketplace.json", status_code=status.HTTP_200_OK, summary="获取 Claude Code 插件市场")
def claude_marketplace() -> JSONResponse:
    payload = build_claude_marketplace(get_settings().site_url)
    return JSONResponse(payload, headers=CACHE_HEADERS)


def _shell_script(content: str) -> Response:
    return Response(
        content,
        media_type="text/x-shellscript; charset=utf-8",
        headers={**CACHE_HEADERS, "Content-Disposition": "inline"},
    )


@router.get("/codex.sh", status_code=status.HTTP_200_OK, summary="安装 Codex MCP 插件")
def codex_install_script() -> Response:
    return _shell_script(build_codex_install_script(get_settings().site_url))


@router.get("/claude.sh", status_code=status.HTTP_200_OK, summary="安装 Claude Code MCP 插件")
def claude_install_script() -> Response:
    return _shell_script(build_claude_install_script(get_settings().site_url))
