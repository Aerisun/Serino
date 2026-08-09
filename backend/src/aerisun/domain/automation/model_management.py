"""Admin-facing ChatGPT account and two-source model diagnostics."""

from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.core.redaction import safe_exception_detail
from aerisun.domain.automation.codex_app_server import (
    CodexAppServerError,
    get_codex_app_server_client,
)
from aerisun.domain.automation.runtime import (
    probe_chatgpt_config,
    probe_model_config,
    record_model_source_probe,
    reset_model_source_health,
)
from aerisun.domain.automation.schemas import (
    AgentModelDiagnosticRead,
    AgentModelSourceDiagnosticRead,
    ChatGPTAccountRead,
    ChatGPTDeviceLoginRead,
    ChatGPTLoginStatusRead,
    ChatGPTModelOptionRead,
)
from aerisun.domain.automation.settings import get_agent_model_config_resolved
from aerisun.domain.exceptions import ValidationError
from aerisun.domain.outbound_proxy.service import require_outbound_proxy_scope

_SOURCE_LABELS = {
    "chatgpt_oauth": "ChatGPT OAuth",
    "openai_compatible": "OpenAI-compatible API",
}


def _codex_error(exc: Exception) -> ValidationError:
    return ValidationError(safe_exception_detail(exc) or "Codex App Server 暂时不可用。")


def read_chatgpt_account(session: Session) -> ChatGPTAccountRead:
    try:
        require_outbound_proxy_scope(session, scope="oauth")
    except ValidationError as exc:
        return ChatGPTAccountRead(connected=False, error=safe_exception_detail(exc))
    try:
        account = get_codex_app_server_client().read_account(refresh_token=False)
    except CodexAppServerError as exc:
        return ChatGPTAccountRead(connected=False, error=safe_exception_detail(exc))
    if account is None:
        return ChatGPTAccountRead(connected=False)
    return ChatGPTAccountRead(
        connected=True,
        email=account.email,
        plan_type=account.plan_type,
    )


def start_chatgpt_device_login(session: Session) -> ChatGPTDeviceLoginRead:
    require_outbound_proxy_scope(session, scope="oauth")
    try:
        login = get_codex_app_server_client().start_device_login()
    except CodexAppServerError as exc:
        raise _codex_error(exc) from exc
    return ChatGPTDeviceLoginRead(
        login_id=login.login_id,
        verification_url=login.verification_url,
        user_code=login.user_code,
    )


def read_chatgpt_login_status(session: Session, login_id: str) -> ChatGPTLoginStatusRead:
    require_outbound_proxy_scope(session, scope="oauth")
    try:
        status = get_codex_app_server_client().get_login_status(login_id)
    except CodexAppServerError as exc:
        raise _codex_error(exc) from exc
    account = None
    if status.account is not None:
        account = ChatGPTAccountRead(
            connected=True,
            email=status.account.email,
            plan_type=status.account.plan_type,
        )
    if status.status == "completed":
        reset_model_source_health("chatgpt_oauth")
    return ChatGPTLoginStatusRead(
        status=status.status,
        account=account,
        error=status.error,
    )


def logout_chatgpt_account(session: Session) -> None:
    require_outbound_proxy_scope(session, scope="oauth")
    try:
        get_codex_app_server_client().logout()
    except CodexAppServerError as exc:
        raise _codex_error(exc) from exc
    reset_model_source_health("chatgpt_oauth")


def list_chatgpt_models(session: Session) -> list[ChatGPTModelOptionRead]:
    require_outbound_proxy_scope(session, scope="oauth")
    client = get_codex_app_server_client()
    try:
        if client.read_account(refresh_token=False) is None:
            raise ValidationError("请先登录 ChatGPT 账号。")
        models = client.list_models()
    except ValidationError:
        raise
    except CodexAppServerError as exc:
        raise _codex_error(exc) from exc
    return [
        ChatGPTModelOptionRead(
            model=item.model,
            display_name=item.display_name,
            is_default=item.is_default,
        )
        for item in models
    ]


def diagnose_agent_model_config(session: Session) -> AgentModelDiagnosticRead:
    config = get_agent_model_config_resolved(session)
    primary = config.primary_source
    order = [primary, *(source for source in _SOURCE_LABELS if source != primary)]
    items: list[AgentModelSourceDiagnosticRead] = []

    for source in order:
        label = _SOURCE_LABELS[source]
        source_model = config.chatgpt_oauth if source == "chatgpt_oauth" else config.openai_compatible
        model_name = source_model.model
        if not source_model.enabled:
            items.append(
                AgentModelSourceDiagnosticRead(
                    source=source,
                    status="skipped",
                    model=model_name,
                    summary=f"{label} 未启用",
                )
            )
            continue
        if not source_model.is_ready:
            items.append(
                AgentModelSourceDiagnosticRead(
                    source=source,
                    status="failed",
                    model=model_name,
                    summary=f"{label} 配置不完整",
                    detail=(
                        "请选择模型并完成 ChatGPT 登录。"
                        if source == "chatgpt_oauth"
                        else "请填写 Base URL、模型名称和 API Key。"
                    ),
                )
            )
            continue

        payload = source_model.model_dump(exclude={"is_ready"})
        if source == "openai_compatible":
            payload["timeout_seconds"] = min(int(source_model.timeout_seconds), 20)
        try:
            probe = probe_chatgpt_config(payload) if source == "chatgpt_oauth" else probe_model_config(payload)
        except Exception as exc:
            record_model_source_probe(source, payload, error=exc)
            secrets = (
                (config.openai_compatible.api_key, config.openai_compatible.base_url)
                if source == "openai_compatible"
                else ()
            )
            items.append(
                AgentModelSourceDiagnosticRead(
                    source=source,
                    status="failed",
                    model=model_name,
                    summary=f"{label} 当前不可用",
                    detail=safe_exception_detail(exc, known_secrets=secrets),
                )
            )
            continue

        record_model_source_probe(source, payload)
        items.append(
            AgentModelSourceDiagnosticRead(
                source=source,
                status="healthy",
                model=str(probe.get("model") or model_name),
                summary=f"{label} 响应正常",
            )
        )

    healthy_sources = [item.source for item in items if item.status == "healthy"]
    failed_count = sum(item.status == "failed" for item in items)
    enabled_count = sum(item.status != "skipped" for item in items)
    if failed_count and healthy_sources:
        status = "warning"
        summary = "一个模型来源不可用，已保留可用来源用于自动容灾。"
    elif failed_count:
        status = "failed"
        summary = "当前没有可用的模型来源。"
    elif healthy_sources:
        status = "healthy"
        summary = "已启用的模型来源均可用。"
    elif enabled_count == 0:
        status = "skipped"
        summary = "尚未启用模型来源。"
    else:
        status = "failed"
        summary = "当前没有可用的模型来源。"

    return AgentModelDiagnosticRead(
        status=status,
        primary_source=primary,
        active_source=healthy_sources[0] if healthy_sources else None,
        summary=summary,
        items=items,
    )
