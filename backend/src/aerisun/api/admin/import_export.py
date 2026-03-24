from __future__ import annotations

import io
import json

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.content.import_export_service import (
    export_content_json,
    export_content_markdown_zip,
    import_content_json,
)
from aerisun.domain.content.schemas import ImportResult
from aerisun.domain.iam.models import AdminUser

from .deps import get_current_admin

router = APIRouter(prefix="/content", tags=["admin-import-export"])


@router.get("/export", summary="导出内容")
def export_content(
    content_type: str = Query(..., description="posts, diary, thoughts, or excerpts"),
    format: str = Query(default="json", description="json or markdown_zip"),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    try:
        if format == "markdown_zip":
            zip_bytes = export_content_markdown_zip(session, content_type)
            return StreamingResponse(
                io.BytesIO(zip_bytes),
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={content_type}-export.zip"},
            )
        data = export_content_json(session, content_type)
        content_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
        return StreamingResponse(
            io.BytesIO(content_bytes),
            media_type="application/json",
            headers={"Content-Disposition": f"attachment; filename={content_type}-export.json"},
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/import", response_model=ImportResult, summary="导入内容")
async def import_content(
    content_type: str = Query(...),
    file: UploadFile = File(...),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ImportResult:
    raw = await file.read()
    try:
        items_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc
    if not isinstance(items_data, list):
        raise HTTPException(status_code=400, detail="Expected JSON array")
    try:
        return import_content_json(session, content_type, items_data)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
