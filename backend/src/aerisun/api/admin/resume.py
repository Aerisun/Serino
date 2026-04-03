from __future__ import annotations

from fastapi import APIRouter

from aerisun.domain.site_config.models import ResumeBasics

from .content import build_crud_router
from .schemas import (
    ResumeBasicsAdminRead,
    ResumeBasicsCreate,
    ResumeBasicsUpdate,
)

router = APIRouter(prefix="/resume", tags=["admin-resume"])

basics_router = build_crud_router(
    ResumeBasics,
    create_schema=ResumeBasicsCreate,
    update_schema=ResumeBasicsUpdate,
    read_schema=ResumeBasicsAdminRead,
    prefix="/basics",
    tag="admin-resume",
)

router.include_router(basics_router)
