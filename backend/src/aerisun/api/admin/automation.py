from __future__ import annotations

import json
import queue
import threading
import time

from fastapi import APIRouter, Depends, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from aerisun.core.db import get_session, get_session_factory
from aerisun.domain.automation.schemas import (
    AgentModelConfigRead,
    AgentModelConfigTestRead,
    AgentModelConfigUpdate,
    AgentRunApprovalRead,
    AgentRunRead,
    AgentRunStepRead,
    AgentWorkflowCreate,
    AgentWorkflowDraftChatWrite,
    AgentWorkflowDraftCreateRead,
    AgentWorkflowDraftCreateWrite,
    AgentWorkflowDraftRead,
    AgentWorkflowRead,
    AgentWorkflowUpdate,
    ApprovalDecisionWrite,
    TelegramWebhookConnectRead,
    TelegramWebhookConnectWrite,
    WebhookDeadLetterRead,
    WebhookDeliveryRead,
    WebhookSubscriptionCreate,
    WebhookSubscriptionRead,
    WebhookSubscriptionUpdate,
)
from aerisun.domain.automation.service import (
    clear_agent_workflow_draft,
    connect_telegram_webhook,
    continue_agent_workflow_draft,
    create_agent_workflow_from_draft,
    create_webhook_subscription,
    delete_webhook_subscription,
    get_agent_workflow_draft,
    get_run_detail,
    list_pending_approvals,
    list_runs,
    list_webhook_dead_letters,
    list_webhook_deliveries,
    list_webhook_subscriptions,
    replay_dead_letter,
    resolve_approval,
    test_agent_model_config,
    test_webhook_subscription,
    trigger_delivery_retry,
    update_webhook_subscription,
)
from aerisun.domain.automation.settings import (
    create_agent_workflow,
    delete_agent_workflow,
    get_agent_model_config,
    list_agent_workflows,
    update_agent_model_config,
    update_agent_workflow,
)
from aerisun.domain.iam.models import AdminUser
from aerisun.domain.ops.config_revisions import capture_config_resource, create_config_revision

from .deps import get_current_admin

router = APIRouter(prefix="/automation", tags=["admin-automation"])


def _workflow_stream_chunks(text: str, *, chunk_size: int = 20) -> list[str]:
    content = text or ""
    return [content[index : index + chunk_size] for index in range(0, len(content), chunk_size)] or [""]


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


@router.get("/workflows", response_model=list[AgentWorkflowRead], summary="获取 Agent 工作流")
def get_workflows(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[AgentWorkflowRead]:
    return list_agent_workflows(session)


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
            except Exception as exc:  # pragma: no cover - surfaced to client as stream event
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
    return create_agent_workflow_from_draft(session, payload)


@router.delete("/workflow-draft", status_code=status.HTTP_204_NO_CONTENT, summary="清空 Agent 工作流草稿")
def delete_workflow_draft(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> None:
    clear_agent_workflow_draft(session)


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
    return result


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
    return result


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


@router.get("/runs", response_model=list[AgentRunRead], summary="获取 Agent 运行记录")
def get_runs(
    _admin: AdminUser = Depends(get_current_admin),
    session: Session = Depends(get_session),
) -> list[AgentRunRead]:
    return list_runs(session)


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
    _session: Session = Depends(get_session),
) -> TelegramWebhookConnectRead:
    return connect_telegram_webhook(
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
