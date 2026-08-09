"""Shared internal helpers used across automation submodules."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from aerisun.core.settings import get_settings
from aerisun.core.time import shanghai_now
from aerisun.domain.agent.service import build_workflow_planning_usage_context
from aerisun.domain.automation.models import AgentRun
from aerisun.domain.automation.schemas import AgentWorkflowRead
from aerisun.domain.automation.settings import agent_model_runtime_config, get_agent_model_config_resolved
from aerisun.domain.exceptions import ValidationError

logger = logging.getLogger(__name__)


def now_utc() -> datetime:
    return shanghai_now()


def ensure_workflow_ai_model(session: Session) -> dict[str, Any]:
    resolved = get_agent_model_config_resolved(session)
    sources = (resolved.chatgpt_oauth, resolved.openai_compatible)
    if not any(source.enabled for source in sources):
        raise ValidationError("Agent model is disabled")
    if not any(source.enabled and source.is_ready for source in sources):
        raise ValidationError("Agent model config is not ready")
    return agent_model_runtime_config(resolved)


def planning_model_config(
    model_config: dict[str, Any],
    *,
    minimum_timeout_seconds: int,
) -> dict[str, Any]:
    next_config = dict(model_config)
    if int(next_config.get("schema_version") or 0) >= 2:
        for source in ("chatgpt_oauth", "openai_compatible"):
            source_config = next_config.get(source)
            if not isinstance(source_config, dict):
                continue
            next_source_config = dict(source_config)
            current_timeout = int(float(next_source_config.get("timeout_seconds") or 20))
            next_source_config["timeout_seconds"] = max(current_timeout, minimum_timeout_seconds)
            next_config[source] = next_source_config
        return next_config
    current_timeout = int(float(next_config.get("timeout_seconds") or 20))
    next_config["timeout_seconds"] = max(current_timeout, minimum_timeout_seconds)
    return next_config


def backend_capability_catalog(session: Session) -> list[dict[str, Any]]:
    site_url = get_settings().site_url
    usage_context = build_workflow_planning_usage_context(session, site_url)
    capabilities = list(usage_context.get("capabilities") or [])
    return [dict(item) for item in capabilities if isinstance(item, dict)]


def normalize_string_list(raw: Any, *, limit: int = 8) -> list[str]:
    if not isinstance(raw, list):
        return []
    values: list[str] = []
    for item in raw[:limit]:
        text = str(item or "").strip()
        if text:
            values.append(text)
    return values


def fallback_workflow_config(run: AgentRun) -> AgentWorkflowRead:
    return AgentWorkflowRead(
        key=run.workflow_key,
        name=run.workflow_key,
        description="Workflow configuration is no longer present in admin settings.",
        enabled=True,
        schema_version=2,
        graph={"version": 2, "nodes": [], "edges": [], "viewport": {"x": 0, "y": 0, "zoom": 1}},
        trigger_bindings=[],
        runtime_policy={"approval_mode": "risk_based", "allow_high_risk_without_approval": False, "max_steps": 80},
        summary={"narrative": "Missing workflow config snapshot."},
        built_in=False,
        trigger_event=run.trigger_event or "manual",
        target_type=run.target_type,
        require_human_approval=False,
        instructions="",
    )
