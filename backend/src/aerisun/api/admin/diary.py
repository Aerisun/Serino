from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from aerisun.core.db import get_session
from aerisun.domain.content.poem_generation import generate_diary_poem
from aerisun.domain.content.schemas import PoemGenerationRequest, PoemGenerationResponse
from aerisun.domain.iam.models import AdminUser

from .deps import get_current_admin

router = APIRouter(prefix="/diary", tags=["admin-diary"])


@router.post("/generate-poem", response_model=PoemGenerationResponse, summary="根据日记草稿生成诗句")
def post_generate_diary_poem(
    payload: PoemGenerationRequest,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> PoemGenerationResponse:
    return generate_diary_poem(session, payload)
