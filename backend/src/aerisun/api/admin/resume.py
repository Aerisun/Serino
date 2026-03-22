from __future__ import annotations

from aerisun.domain.site_config.models import ResumeBasics, ResumeExperience, ResumeSkillGroup

from .content import build_crud_router
from .schemas import (
    ResumeBasicsAdminRead,
    ResumeBasicsCreate,
    ResumeBasicsUpdate,
    ResumeExperienceAdminRead,
    ResumeExperienceCreate,
    ResumeExperienceUpdate,
    ResumeSkillGroupAdminRead,
    ResumeSkillGroupCreate,
    ResumeSkillGroupUpdate,
)

from fastapi import APIRouter

router = APIRouter(prefix="/resume", tags=["admin-resume"])

basics_router = build_crud_router(
    ResumeBasics,
    create_schema=ResumeBasicsCreate,
    update_schema=ResumeBasicsUpdate,
    read_schema=ResumeBasicsAdminRead,
    prefix="/basics",
    tag="admin-resume",
)

skills_router = build_crud_router(
    ResumeSkillGroup,
    create_schema=ResumeSkillGroupCreate,
    update_schema=ResumeSkillGroupUpdate,
    read_schema=ResumeSkillGroupAdminRead,
    prefix="/skills",
    tag="admin-resume",
)

experiences_router = build_crud_router(
    ResumeExperience,
    create_schema=ResumeExperienceCreate,
    update_schema=ResumeExperienceUpdate,
    read_schema=ResumeExperienceAdminRead,
    prefix="/experiences",
    tag="admin-resume",
)

router.include_router(basics_router)
router.include_router(skills_router)
router.include_router(experiences_router)
