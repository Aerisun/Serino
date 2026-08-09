"""AI model config helpers and probes for automation workflows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.core.redaction import safe_exception_detail, sanitize_url
from aerisun.domain.automation.runtime import build_model_chat_completions_url, probe_model_config
from aerisun.domain.automation.schemas import AgentModelConfigTestRead, AgentModelConfigUpdate
from aerisun.domain.automation.settings import resolve_agent_model_config


def _format_model_config_test_failure(message: str) -> str:
    detail = message.strip() or "Model endpoint test failed."
    guidance = "请检查 Base URL 是否为 OpenAI 兼容 API 根地址（如 /v1 或 /api/v3），并确认 API Key 正确且有权限。"
    if "请检查 Base URL" in detail:
        return detail
    return f"{detail} {guidance}"


def test_agent_model_config(session: Session, payload: AgentModelConfigUpdate) -> AgentModelConfigTestRead:
    config = resolve_agent_model_config(session, payload)
    api_config = config.openai_compatible
    endpoint = build_model_chat_completions_url(str(api_config.base_url or ""))
    try:
        probe = probe_model_config(api_config.model_dump(exclude={"is_ready"}))
        return AgentModelConfigTestRead(
            ok=True,
            model=probe["model"],
            endpoint=sanitize_url(probe["endpoint"]),
            summary=probe["summary"],
        )
    except Exception as exc:
        return AgentModelConfigTestRead(
            ok=False,
            model=str(api_config.model or ""),
            endpoint=sanitize_url(endpoint),
            summary=_format_model_config_test_failure(
                safe_exception_detail(exc, known_secrets=(api_config.api_key, api_config.base_url))
            ),
        )
