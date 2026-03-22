from __future__ import annotations

import io
import json
import zipfile

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.content.models import DiaryEntry, ExcerptEntry, PostEntry, ThoughtEntry
from aerisun.domain.iam.models import AdminUser

from .deps import get_current_admin
from .schemas import ContentAdminRead

router = APIRouter(prefix="/content", tags=["admin-import-export"])

_CONTENT_MODELS = {
    "posts": PostEntry,
    "diary": DiaryEntry,
    "thoughts": ThoughtEntry,
    "excerpts": ExcerptEntry,
}


class ImportResult(BaseModel):
    created: int = 0
    updated: int = 0
    errors: list[str] = []


@router.get("/export", summary="导出内容")
def export_content(
    content_type: str = Query(..., description="posts, diary, thoughts, or excerpts"),
    format: str = Query(default="json", description="json or markdown_zip"),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    """将指定类型的内容导出为 JSON 或 Markdown ZIP 文件。"""
    model = _CONTENT_MODELS.get(content_type)
    if not model:
        raise HTTPException(status_code=400, detail=f"Invalid content_type: {content_type}")

    items = session.query(model).order_by(model.created_at.desc()).all()

    if format == "markdown_zip":
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            for item in items:
                # Front matter + body
                front = f"---\ntitle: {item.title}\nslug: {item.slug}\nstatus: {item.status}\ntags: {json.dumps(item.tags or [])}\ncreated_at: {item.created_at.isoformat() if item.created_at else ''}\n---\n\n"
                content = front + (item.body or "")
                zf.writestr(f"{item.slug}.md", content)
        buf.seek(0)
        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename={content_type}-export.zip"},
        )

    # JSON export
    data = []
    for item in items:
        d = ContentAdminRead.model_validate(item).model_dump(mode="json")
        data.append(d)

    content_bytes = json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8")
    return StreamingResponse(
        io.BytesIO(content_bytes),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={content_type}-export.json"},
    )


@router.post("/import", response_model=ImportResult, summary="导入内容")
async def import_content(
    content_type: str = Query(...),
    file: UploadFile = File(...),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ImportResult:
    """从上传的 JSON 文件导入内容，支持新增和更新。"""
    model = _CONTENT_MODELS.get(content_type)
    if not model:
        raise HTTPException(status_code=400, detail=f"Invalid content_type: {content_type}")

    result = ImportResult()
    raw = await file.read()

    try:
        items_data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail="Invalid JSON") from exc

    if not isinstance(items_data, list):
        raise HTTPException(status_code=400, detail="Expected JSON array")

    for entry in items_data:
        slug = entry.get("slug")
        if not slug:
            result.errors.append(f"Missing slug in entry: {entry.get('title', 'unknown')}")
            continue

        existing = session.query(model).filter(model.slug == slug).first()

        # Only keep fields that are actual model columns
        allowed = {
            "slug",
            "title",
            "summary",
            "body",
            "tags",
            "status",
            "visibility",
            "published_at",
            "category",
            "view_count",
            "mood",
            "weather",
            "poem",
            "author_name",
            "source",
            "is_pinned",
            "pin_order",
        }
        filtered = {k: v for k, v in entry.items() if k in allowed}

        if existing:
            for k, v in filtered.items():
                if k != "slug":
                    setattr(existing, k, v)
            result.updated += 1
        else:
            obj = model(**filtered)
            session.add(obj)
            result.created += 1

    session.commit()
    return result
