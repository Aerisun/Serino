from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from aerisun.api.request_base import public_base_url_from_request
from aerisun.core.db import get_session
from aerisun.domain.ops.backup_sync import (
    register_backup_bootstrap_result,
    render_backup_bootstrap_script,
)
from aerisun.domain.ops.schemas import BackupBootstrapClaimRead, BackupBootstrapClaimResultWrite

router = APIRouter(prefix="/api/v1/backup/setup", tags=["backup-setup"], include_in_schema=True)


@router.get("/{claim}.sh", response_class=PlainTextResponse, summary="下载备份机临时接入脚本")
def get_backup_setup_script(
    claim: str,
    request: Request,
    session: Session = Depends(get_session),
) -> PlainTextResponse:
    script = render_backup_bootstrap_script(
        session,
        token=claim,
        public_base_url=public_base_url_from_request(request),
    )
    return PlainTextResponse(script, media_type="text/x-shellscript; charset=utf-8")


@router.post(
    "/{claim}/result",
    response_model=BackupBootstrapClaimRead,
    status_code=status.HTTP_200_OK,
    summary="回传备份机临时接入结果",
)
def post_backup_setup_result(
    claim: str,
    payload: BackupBootstrapClaimResultWrite,
    session: Session = Depends(get_session),
) -> BackupBootstrapClaimRead:
    return register_backup_bootstrap_result(session, token=claim, payload=payload)
