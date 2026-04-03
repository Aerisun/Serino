"""AI model config helpers and probes for automation workflows."""

from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.domain.automation.runtime import probe_model_config
from aerisun.domain.automation.schemas import AgentModelConfigTestRead, AgentModelConfigUpdate
from aerisun.domain.automation.settings import resolve_agent_model_config


def _model_chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/chat/completions"):
        return normalized
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _format_model_config_test_failure(message: str) -> str:
    detail = message.strip() or "Model endpoint test failed."
    guidance = "请检查 Base URL 是否为 OpenAI 兼容 API 根地址（通常包含 /v1），并确认 API Key 正确且有权限。"
    if "请检查 Base URL" in detail:
        return detail
    return f"{detail} {guidance}"


def test_agent_model_config(session: Session, payload: AgentModelConfigUpdate) -> AgentModelConfigTestRead:
    config = resolve_agent_model_config(session, payload)
    endpoint = _model_chat_completions_url(str(config.base_url or ""))
    try:
        probe = probe_model_config(config.model_dump(exclude={"is_ready"}))
        return AgentModelConfigTestRead(
            ok=True,
            model=probe["model"],
            endpoint=probe["endpoint"],
            summary=probe["summary"],
        )
    except Exception as exc:
        return AgentModelConfigTestRead(
            ok=False,
            model=str(config.model or ""),
            endpoint=endpoint,
            summary=_format_model_config_test_failure(str(exc)),
        )
