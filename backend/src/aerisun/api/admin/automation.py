from __future__ import annotations

import json
import queue
import threading
import time
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from aerisun.core.db import get_session, get_session_factory
from aerisun.domain.automation.ai_contract_context import build_ai_contract_context
from aerisun.domain.automation.catalog import build_workflow_catalog, derive_ai_output_schema
from aerisun.domain.automation.model_management import (
    diagnose_agent_model_config,
    list_chatgpt_models,
    logout_chatgpt_account,
    read_chatgpt_account,
    read_chatgpt_login_status,
    start_chatgpt_device_login,
)
from aerisun.domain.automation.schemas import (
    AgentMessageCollectionRead,
    AgentMessageRead,
    AgentModelConfigRead,
    AgentModelConfigTestRead,
    AgentModelConfigUpdate,
    AgentModelDiagnosticRead,
    AgentOverviewRead,
    AgentRunApprovalRead,
    AgentRunCollectionRead,
    AgentRunRead,
    AgentRunStepRead,
    AgentWorkflowCatalogRead,
    AgentWorkflowCreate,
    AgentWorkflowDraftChatWrite,
    AgentWorkflowDraftCreateRead,
    AgentWorkflowDraftCreateWrite,
    AgentWorkflowDraftRead,
    AgentWorkflowMessageRunCreateWrite,
    AgentWorkflowRead,
    AgentWorkflowRunCreateRead,
    AgentWorkflowRunCreateWrite,
    AgentWorkflowUpdate,
    AgentWorkflowValidationRead,
    ApprovalDecisionWrite,
    ChatGPTAccountRead,
    ChatGPTDeviceLoginRead,
    ChatGPTLoginStatusRead,
    ChatGPTModelOptionRead,
    DeriveAiSchemaRequest,
    DeriveAiSchemaResponse,
    SurfaceDraftApplyRead,
    SurfaceDraftChatWrite,
    SurfaceDraftRead,
    TelegramWebhookConnectRead,
    TelegramWebhookConnectWrite,
    WebhookDeadLetterRead,
    WebhookDeliveryRead,
    WebhookSubscriptionCreate,
    WebhookSubscriptionRead,
    WebhookSubscriptionUpdate,
)
from aerisun.domain.automation.service import (
    apply_surface_draft,
    cancel_workflow_run,
    clear_agent_workflow_draft,
    clear_surface_draft,
    connect_telegram_webhook,
    continue_agent_workflow_draft,
    continue_surface_draft,
    create_agent_workflow_from_draft,
    create_message_workflow_run,
    create_webhook_subscription,
    create_workflow_run,
    delete_webhook_subscription,
    full_access_run_principal,
    get_agent_message,
    get_agent_overview,
    get_agent_workflow_catalog,
    get_agent_workflow_draft,
    get_run_detail,
    get_surface_draft,
    list_agent_messages,
    list_pending_approvals,
    list_run_collection,
    list_webhook_dead_letters,
    list_webhook_deliveries,
    list_webhook_subscriptions,
    replay_dead_letter,
    resolve_approval,
    retry_workflow_run,
    test_agent_model_config,
    test_webhook_subscription,
    test_workflow_run,
    trigger_delivery_retry,
    update_webhook_subscription,
)
from aerisun.domain.automation.settings import (
    create_agent_workflow,
    delete_agent_workflow,
    get_agent_model_config,
    list_agent_workflows,
    public_agent_workflow,
    update_agent_model_config,
    update_agent_workflow,
)
from aerisun.domain.automation.validation import compile_workflow
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.ops.config_revisions import capture_config_resource, create_config_revision

from .deps import get_current_admin

router = APIRouter(prefix="/automation", tags=["admin-automation"])


def _workflow_stream_chunks(message: str, *, chunk_size: int = 48) -> list[str]:
    text = str(message or "")
    if not text:
        return []
    return [text[index : index + chunk_size] for index in range(0, len(text), chunk_size)]


@router.get("/model-config", response_model=AgentModelConfigRead, summary="获取 Agent 模型配置")
def get_model_config(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentModelConfigRead:
    return get_agent_model_config(session)


@router.put("/model-config", response_model=AgentModelConfigRead, summary="更新 Agent 模型配置")
def put_model_config(
    payload: AgentModelConfigUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentModelConfigRead:
    before_snapshot = capture_config_resource(session, "automation.model_config")
    result = update_agent_model_config(session, payload)
    after_snapshot = capture_config_resource(session, "automation.model_config")
    create_config_revision(
        session,
        actor_id=_admin.id,
        resource_key="automation.model_config",
        operation="update",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return result


@router.post("/model-config/test", response_model=AgentModelConfigTestRead, summary="测试 Agent 模型配置")
def post_model_config_test(
    payload: AgentModelConfigUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentModelConfigTestRead:
    return test_agent_model_config(session, payload)


@router.get(
    "/model-config/chatgpt/account",
    response_model=ChatGPTAccountRead,
    summary="获取 ChatGPT OAuth 账号状态",
)
def get_chatgpt_account(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ChatGPTAccountRead:
    return read_chatgpt_account(session)


@router.post(
    "/model-config/chatgpt/login",
    response_model=ChatGPTDeviceLoginRead,
    summary="开始 ChatGPT 设备码登录",
)
def post_chatgpt_login(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ChatGPTDeviceLoginRead:
    return start_chatgpt_device_login(session)


@router.get(
    "/model-config/chatgpt/login/{login_id}",
    response_model=ChatGPTLoginStatusRead,
    summary="获取 ChatGPT 登录进度",
)
def get_chatgpt_login_status(
    login_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> ChatGPTLoginStatusRead:
    return read_chatgpt_login_status(session, login_id)


@router.delete(
    "/model-config/chatgpt/account",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="退出 ChatGPT OAuth 账号",
)
def delete_chatgpt_account(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> Response:
    logout_chatgpt_account(session)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/model-config/chatgpt/models",
    response_model=list[ChatGPTModelOptionRead],
    summary="获取 ChatGPT 套餐可用模型",
)
def get_chatgpt_models(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[ChatGPTModelOptionRead]:
    return list_chatgpt_models(session)


@router.post(
    "/model-config/diagnose",
    response_model=AgentModelDiagnosticRead,
    summary="诊断模型主备来源",
)
def post_model_config_diagnose(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentModelDiagnosticRead:
    return diagnose_agent_model_config(session)


@router.get("/workflows", response_model=list[AgentWorkflowRead], summary="获取 Agent 工作流")
def get_workflows(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[AgentWorkflowRead]:
    return [public_agent_workflow(item) for item in list_agent_workflows(session)]


@router.get("/workflow-catalog", response_model=AgentWorkflowCatalogRead, summary="获取工作流 v2 目录")
def get_workflow_catalog(
    workflow_key: str | None = Query(default=None),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentWorkflowCatalogRead:
    return get_agent_workflow_catalog(session, workflow_key=workflow_key)


@router.get(
    "/workflows/{workflow_key}/surface-draft",
    response_model=SurfaceDraftRead | None,
    summary="获取当前工作流的 Surface 草稿",
)
def get_workflow_surface_draft(
    workflow_key: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> SurfaceDraftRead | None:
    return get_surface_draft(session, workflow_key=workflow_key)


@router.post(
    "/workflows/{workflow_key}/surface-draft/messages",
    response_model=SurfaceDraftRead,
    summary="继续当前工作流的 Surface 对话",
)
def post_workflow_surface_draft_message(
    workflow_key: str,
    payload: SurfaceDraftChatWrite,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> SurfaceDraftRead:
    return continue_surface_draft(session, workflow_key=workflow_key, payload=payload)


@router.post(
    "/workflows/{workflow_key}/surface-draft/apply",
    response_model=SurfaceDraftApplyRead,
    summary="应用当前工作流的 Surface 草稿",
)
def post_workflow_surface_draft_apply(
    workflow_key: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> SurfaceDraftApplyRead:
    return apply_surface_draft(session, workflow_key=workflow_key)


@router.delete(
    "/workflows/{workflow_key}/surface-draft",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="清空当前工作流的 Surface 草稿",
)
def delete_workflow_surface_draft(
    workflow_key: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    clear_surface_draft(session, workflow_key=workflow_key)


@router.post(
    "/workflows",
    response_model=AgentWorkflowRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建 Agent 工作流",
)
def post_workflow(
    payload: AgentWorkflowCreate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentWorkflowRead:
    before_snapshot = capture_config_resource(session, "automation.workflows")
    result = create_agent_workflow(session, payload)
    after_snapshot = capture_config_resource(session, "automation.workflows")
    create_config_revision(
        session,
        actor_id=_admin.id,
        resource_key="automation.workflows",
        operation="create",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return public_agent_workflow(result)


@router.post("/workflows/validate", response_model=AgentWorkflowValidationRead, summary="校验工作流定义")
def post_workflow_validate(
    payload: AgentWorkflowCreate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentWorkflowValidationRead:
    return compile_workflow(payload.model_dump(mode="json"), session=session)


@router.post("/workflows/derive-ai-schema", response_model=DeriveAiSchemaResponse, summary="推导 AI 节点输出 Schema")
def post_derive_ai_schema(
    body: DeriveAiSchemaRequest,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> DeriveAiSchemaResponse:
    """Derive the required output schema for an AI node based on its downstream connections."""
    catalog = build_workflow_catalog(session)

    # Build node type registry for quick lookup
    node_type_registry = {nt.type: nt for nt in catalog.node_types}

    # Convert graph model to dicts for the derive function
    graph_nodes = [n.model_dump() if hasattr(n, "model_dump") else n for n in body.graph.nodes]
    graph_edges = [e.model_dump() if hasattr(e, "model_dump") else e for e in body.graph.edges]
    graph_payload = body.graph.model_dump() if hasattr(body.graph, "model_dump") else dict(body.graph)
    ai_node = next(
        (
            node
            for node in graph_nodes
            if str(getattr(node, "id", None) or node.get("id") or "").strip() == body.ai_node_id
        ),
        None,
    )

    output_schema, source_nodes = derive_ai_output_schema(
        graph_nodes=graph_nodes,
        graph_edges=graph_edges,
        ai_node_id=body.ai_node_id,
        operation_catalog=catalog.operation_catalog,
        node_type_registry=node_type_registry,
        workflow_key=body.workflow_key,
    )
    contract_context = build_ai_contract_context(
        workflow_key=body.workflow_key or "",
        workflow_config={"graph": graph_payload},
        ai_node_id=body.ai_node_id,
        node_config=dict(
            getattr(ai_node, "config", None) or (ai_node.get("config") if isinstance(ai_node, dict) else {}) or {}
        ),
    )

    return DeriveAiSchemaResponse(
        output_schema=output_schema,
        source_nodes=source_nodes,
        contract_context=contract_context,
    )


@router.put("/workflows/{workflow_key}", response_model=AgentWorkflowRead, summary="更新 Agent 工作流")
def put_workflow(
    workflow_key: str,
    payload: AgentWorkflowUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentWorkflowRead:
    before_snapshot = capture_config_resource(session, "automation.workflows")
    result = update_agent_workflow(session, workflow_key=workflow_key, payload=payload)
    after_snapshot = capture_config_resource(session, "automation.workflows")
    create_config_revision(
        session,
        actor_id=_admin.id,
        resource_key="automation.workflows",
        operation="update",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )
    return public_agent_workflow(result)


@router.post("/workflows/{workflow_key}/runs", response_model=AgentWorkflowRunCreateRead, summary="手动触发工作流")
def post_workflow_run(
    workflow_key: str,
    payload: AgentWorkflowRunCreateWrite,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentWorkflowRunCreateRead:
    from aerisun.domain.automation.runtime_registry import get_automation_runtime

    return create_workflow_run(
        session,
        get_automation_runtime(),
        workflow_key=workflow_key,
        payload=payload,
        trigger_kind="manual",
        principal=full_access_run_principal("admin", _admin.id),
    )


@router.post(
    "/workflows/{workflow_key}/message-runs",
    response_model=AgentWorkflowRunCreateRead,
    summary="使用留言触发工作流",
)
def post_workflow_message_run(
    workflow_key: str,
    payload: AgentWorkflowMessageRunCreateWrite,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentWorkflowRunCreateRead:
    from aerisun.domain.automation.runtime_registry import get_automation_runtime

    return create_message_workflow_run(
        session,
        get_automation_runtime(),
        workflow_key=workflow_key,
        payload=payload,
        principal=full_access_run_principal("admin", _admin.id),
    )


@router.post("/workflows/{workflow_key}/test-runs", response_model=AgentWorkflowRunCreateRead, summary="测试运行工作流")
def post_workflow_test_run(
    workflow_key: str,
    payload: AgentWorkflowRunCreateWrite,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentWorkflowRunCreateRead:
    from aerisun.domain.automation.runtime_registry import get_automation_runtime

    return test_workflow_run(
        session,
        get_automation_runtime(),
        workflow_key=workflow_key,
        payload=payload,
        principal=full_access_run_principal("admin", _admin.id),
    )


@router.delete("/workflows/{workflow_key}", status_code=status.HTTP_204_NO_CONTENT, summary="删除 Agent 工作流")
def delete_workflow(
    workflow_key: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    before_snapshot = capture_config_resource(session, "automation.workflows")
    delete_agent_workflow(session, workflow_key=workflow_key)
    after_snapshot = capture_config_resource(session, "automation.workflows")
    create_config_revision(
        session,
        actor_id=_admin.id,
        resource_key="automation.workflows",
        operation="delete",
        before_snapshot=before_snapshot,
        after_snapshot=after_snapshot,
    )


@router.get("/overview", response_model=AgentOverviewRead, summary="获取 Agent 总览")
def get_overview(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentOverviewRead:
    return get_agent_overview(session)


@router.get("/runs", response_model=AgentRunCollectionRead, summary="获取 Agent 运行记录")
def get_runs(
    status_filter: list[str] | None = Query(default=None, alias="status"),
    workflow_key: str | None = Query(default=None, max_length=120),
    execution_mode: Literal["live", "dry_run"] | None = Query(default=None),
    search: str | None = Query(default=None, max_length=200),
    created_from: datetime | None = Query(default=None),
    created_to: datetime | None = Query(default=None),
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=25, ge=1, le=100),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentRunCollectionRead:
    return list_run_collection(
        session,
        statuses=status_filter,
        workflow_key=workflow_key,
        execution_mode=execution_mode,
        search=search,
        created_from=created_from,
        created_to=created_to,
        cursor=cursor,
        limit=limit,
    )


@router.get("/messages", response_model=AgentMessageCollectionRead, summary="获取 Agent 留言列表")
def get_messages(
    workflow_key: str | None = Query(default=None, max_length=120),
    execution_mode: Literal["live", "dry_run"] | None = Query(default=None),
    cursor: str | None = Query(default=None, max_length=512),
    limit: int = Query(default=25, ge=1, le=100),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentMessageCollectionRead:
    return list_agent_messages(
        session,
        workflow_key=workflow_key,
        execution_mode=execution_mode,
        cursor=cursor,
        limit=limit,
    )


@router.get("/messages/{message_id}", response_model=AgentMessageRead, summary="获取 Agent 留言详情")
def get_message(
    message_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentMessageRead:
    return get_agent_message(session, message_id=message_id)


@router.get("/runs/{run_id}", response_model=AgentRunRead, summary="获取单个 Agent 运行记录")
def get_run(
    run_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentRunRead:
    run, _steps = get_run_detail(session, run_id)
    return run


@router.get("/runs/{run_id}/steps", response_model=list[AgentRunStepRead], summary="获取运行步骤")
def get_run_steps(
    run_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[AgentRunStepRead]:
    _run, steps = get_run_detail(session, run_id)
    return steps


@router.post("/runs/{run_id}/cancel", response_model=AgentRunRead, summary="取消 Agent 运行")
def post_run_cancel(
    run_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentRunRead:
    return cancel_workflow_run(session, run_id=run_id)


@router.post("/runs/{run_id}/retry", response_model=AgentRunRead, summary="重试 Agent 运行")
def post_run_retry(
    run_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentRunRead:
    return retry_workflow_run(session, run_id=run_id)


@router.get("/approvals", response_model=list[AgentRunApprovalRead], summary="获取待审批项目")
def get_approvals(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[AgentRunApprovalRead]:
    return list_pending_approvals(session)


@router.post(
    "/approvals/{approval_id}/decision",
    response_model=AgentRunRead,
    status_code=status.HTTP_200_OK,
    summary="提交审批结果并恢复工作流",
)
def post_approval_decision(
    approval_id: str,
    payload: ApprovalDecisionWrite,
    admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentRunRead:
    from aerisun.domain.automation.runtime_registry import get_automation_runtime

    return resolve_approval(
        session,
        get_automation_runtime(),
        approval_id=approval_id,
        actor_id=admin.id,
        decision_payload=payload,
    )


@router.get("/webhooks", response_model=list[WebhookSubscriptionRead], summary="获取 Webhook 订阅")
def get_webhooks(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[WebhookSubscriptionRead]:
    return list_webhook_subscriptions(session)


@router.post(
    "/webhooks",
    response_model=WebhookSubscriptionRead,
    status_code=status.HTTP_201_CREATED,
    summary="创建 Webhook 订阅",
)
def post_webhook(
    payload: WebhookSubscriptionCreate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> WebhookSubscriptionRead:
    return create_webhook_subscription(session, payload)


@router.post("/webhooks/test", summary="测试 Webhook 订阅")
def post_webhook_test(
    payload: WebhookSubscriptionCreate,
    subscription_id: str | None = Query(default=None),
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> dict[str, object]:
    return test_webhook_subscription(session, payload, subscription_id=subscription_id)


@router.post(
    "/webhooks/telegram/connect",
    response_model=TelegramWebhookConnectRead,
    summary="连接 Telegram 并自动识别 chat_id",
)
def post_webhook_telegram_connect(
    payload: TelegramWebhookConnectWrite,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> TelegramWebhookConnectRead:
    return connect_telegram_webhook(
        session=session,
        bot_token=payload.bot_token,
        send_test_message=payload.send_test_message,
    )


@router.put("/webhooks/{subscription_id}", response_model=WebhookSubscriptionRead, summary="更新 Webhook 订阅")
def put_webhook(
    subscription_id: str,
    payload: WebhookSubscriptionUpdate,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> WebhookSubscriptionRead:
    return update_webhook_subscription(session, subscription_id=subscription_id, payload=payload)


@router.delete("/webhooks/{subscription_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除 Webhook 订阅")
def delete_webhook(
    subscription_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    delete_webhook_subscription(session, subscription_id=subscription_id)


@router.get("/deliveries", response_model=list[WebhookDeliveryRead], summary="获取 Webhook 投递记录")
def get_deliveries(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[WebhookDeliveryRead]:
    return list_webhook_deliveries(session)


@router.post("/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryRead, summary="重试 Webhook 投递")
def post_delivery_retry(
    delivery_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> WebhookDeliveryRead:
    return trigger_delivery_retry(session, delivery_id=delivery_id)


@router.get("/dead-letters", response_model=list[WebhookDeadLetterRead], summary="获取 Webhook 死信列表")
def get_dead_letters(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[WebhookDeadLetterRead]:
    return list_webhook_dead_letters(session)


@router.post("/dead-letters/{dead_letter_id}/replay", response_model=WebhookDeliveryRead, summary="回放死信投递")
def post_dead_letter_replay(
    dead_letter_id: str,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> WebhookDeliveryRead:
    return replay_dead_letter(session, dead_letter_id=dead_letter_id)


@router.get("/workflow-draft", response_model=AgentWorkflowDraftRead | None, summary="获取 Agent 工作流草稿")
def get_workflow_draft(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentWorkflowDraftRead | None:
    return get_agent_workflow_draft(session)


@router.post("/workflow-draft/messages", response_model=AgentWorkflowDraftRead, summary="继续 Agent 工作流对话")
def post_workflow_draft_message(
    payload: AgentWorkflowDraftChatWrite,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentWorkflowDraftRead:
    return continue_agent_workflow_draft(session, payload)


@router.post("/workflow-draft/messages/stream", summary="流式继续 Agent 工作流对话")
def post_workflow_draft_message_stream(
    payload: AgentWorkflowDraftChatWrite,
    _admin: AdminUser = Depends(get_current_admin),
) -> StreamingResponse:
    session_factory = get_session_factory()

    def event_stream():
        result_queue: queue.Queue[tuple[str, AgentWorkflowDraftRead | str]] = queue.Queue(maxsize=16)
        last_status = "starting"
        last_model_wait_seconds = 0

        def run_planner() -> None:
            try:
                with session_factory() as session:
                    draft = continue_agent_workflow_draft(
                        session,
                        payload,
                        progress_callback=lambda status, extra=None: result_queue.put(
                            ("status", json.dumps({"status": status, **(extra or {})}, ensure_ascii=False))
                        ),
                    )
                result_queue.put(("done", draft))
            except Exception as exc:  # pragma: no cover
                result_queue.put(("error", str(exc)))

        worker = threading.Thread(target=run_planner, daemon=True)
        worker.start()
        started_at = time.monotonic()

        while True:
            try:
                kind, payload_or_error = result_queue.get(timeout=1.0)
            except queue.Empty:
                if worker.is_alive() and last_status == "invoking_planner_model":
                    elapsed_seconds = max(1, int(time.monotonic() - started_at))
                    if elapsed_seconds != last_model_wait_seconds:
                        last_model_wait_seconds = elapsed_seconds
                        yield (
                            json.dumps(
                                {
                                    "type": "status",
                                    "status": "waiting_for_model",
                                    "elapsed_seconds": elapsed_seconds,
                                },
                                ensure_ascii=False,
                            )
                            + "\n"
                        )
                    continue
                if worker.is_alive():
                    continue
                break

            if kind == "status":
                status_payload = json.loads(str(payload_or_error))
                last_status = str(status_payload.get("status") or last_status)
                yield json.dumps({"type": "status", **status_payload}, ensure_ascii=False) + "\n"
                continue

            if kind == "error":
                yield json.dumps({"type": "error", "error": str(payload_or_error)}, ensure_ascii=False) + "\n"
                return

            draft = payload_or_error
            break

        assistant_message = (
            draft.messages[-1].content if draft.messages and draft.messages[-1].role == "assistant" else ""
        )
        for chunk in _workflow_stream_chunks(assistant_message):
            yield json.dumps({"type": "chunk", "content": chunk}, ensure_ascii=False) + "\n"
        yield json.dumps({"type": "done", "draft": draft.model_dump(mode="json")}, ensure_ascii=False) + "\n"

    return StreamingResponse(event_stream(), media_type="application/x-ndjson")


@router.post("/workflow-draft/create", response_model=AgentWorkflowDraftCreateRead, summary="从草稿创建 Agent 工作流")
def post_workflow_draft_create(
    payload: AgentWorkflowDraftCreateWrite,
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> AgentWorkflowDraftCreateRead:
    result = create_agent_workflow_from_draft(session, payload)
    return result.model_copy(update={"workflow": public_agent_workflow(result.workflow)})


@router.delete("/workflow-draft", status_code=status.HTTP_204_NO_CONTENT, summary="清空 Agent 工作流草稿")
def delete_workflow_draft(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    clear_agent_workflow_draft(session)
