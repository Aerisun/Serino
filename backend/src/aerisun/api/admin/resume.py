from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Query as SAQuery
from sqlalchemy.orm import Session

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

router = APIRouter(prefix="/resume", tags=["admin-resume"])


def _get_primary_resume_basics(session: Session) -> ResumeBasics:
    basics = session.query(ResumeBasics).order_by(ResumeBasics.created_at.asc()).first()
    if basics is None:
        raise HTTPException(status_code=404, detail="Resume basics not configured")
    return basics


def _resume_scoped_query(session: Session, model: type[ResumeSkillGroup | ResumeExperience]) -> SAQuery[Any]:
    basics = _get_primary_resume_basics(session)
    return session.query(model).filter(model.resume_basics_id == basics.id)


def _attach_resume_basics_id(session: Session, data: dict[str, Any]) -> dict[str, Any]:
    basics = _get_primary_resume_basics(session)
    if not data.get("resume_basics_id"):
        data["resume_basics_id"] = basics.id
    return data


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
    base_query_factory=lambda session: _resume_scoped_query(session, ResumeSkillGroup),
    prepare_create_data=_attach_resume_basics_id,
)

experiences_router = build_crud_router(
    ResumeExperience,
    create_schema=ResumeExperienceCreate,
    update_schema=ResumeExperienceUpdate,
    read_schema=ResumeExperienceAdminRead,
    prefix="/experiences",
    tag="admin-resume",
    base_query_factory=lambda session: _resume_scoped_query(session, ResumeExperience),
    prepare_create_data=_attach_resume_basics_id,
)

router.include_router(basics_router)
router.include_router(skills_router)
router.include_router(experiences_router)
