from __future__ import annotations

from fastapi import APIRouter

from aerisun.domain.site_config.models import ResumeBasics, ResumeExperience, ResumeSkillGroup
from aerisun.domain.site_config.service import (
    attach_resume_basics_id,
    resume_scoped_query,
)

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
    base_query_factory=lambda session: resume_scoped_query(session, ResumeSkillGroup),
    prepare_create_data=attach_resume_basics_id,
)

experiences_router = build_crud_router(
    ResumeExperience,
    create_schema=ResumeExperienceCreate,
    update_schema=ResumeExperienceUpdate,
    read_schema=ResumeExperienceAdminRead,
    prefix="/experiences",
    tag="admin-resume",
    base_query_factory=lambda session: resume_scoped_query(session, ResumeExperience),
    prepare_create_data=attach_resume_basics_id,
)

router.include_router(basics_router)
router.include_router(skills_router)
router.include_router(experiences_router)
