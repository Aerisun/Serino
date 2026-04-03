"""Automation service — public API facade.

All public functions are implemented in focused submodules and re-exported here
so that external callers can continue to use:

    from aerisun.domain.automation.service import <name>

without any import changes.
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from aerisun.domain.automation.ai_config import test_agent_model_config
from aerisun.domain.automation.approvals import list_pending_approvals, resolve_approval
from aerisun.domain.automation.catalog import build_workflow_catalog
from aerisun.domain.automation.drafts import (
    clear_agent_workflow_draft,
    continue_agent_workflow_draft,
    create_agent_workflow_from_draft,
    get_agent_workflow_draft,
)
from aerisun.domain.automation.runs import (
    create_workflow_run,
    dispatch_due_schedule_runs,
    emit_event,
    enqueue_workflow_run,
    execute_due_runs,
    get_run_detail,
    list_runs,
    test_workflow_run,
    trigger_webhook_workflow,
)
from aerisun.domain.automation.schemas import AgentWorkflowCatalogRead
from aerisun.domain.automation.settings import get_agent_model_config, resolve_agent_model_config
from aerisun.domain.automation.surfaces import (
    apply_surface_draft,
    clear_surface_draft,
    continue_surface_draft,
    get_surface_draft,
)
from aerisun.domain.automation.webhooks import (
    connect_telegram_webhook,
    create_webhook_subscription,
    delete_webhook_subscription,
    dispatch_due_webhooks,
    list_webhook_dead_letters,
    list_webhook_deliveries,
    list_webhook_subscriptions,
    replay_dead_letter,
    test_webhook_subscription,
    trigger_delivery_retry,
    update_webhook_subscription,
)


def get_agent_workflow_catalog(session: Session, workflow_key: str | None = None) -> AgentWorkflowCatalogRead:
    return build_workflow_catalog(session, workflow_key=workflow_key)


__all__ = [
    "apply_surface_draft",
    "clear_agent_workflow_draft",
    "clear_surface_draft",
    "connect_telegram_webhook",
    "continue_agent_workflow_draft",
    "continue_surface_draft",
    "create_agent_workflow_from_draft",
    "create_webhook_subscription",
    "create_workflow_run",
    "delete_webhook_subscription",
    "dispatch_due_schedule_runs",
    "dispatch_due_webhooks",
    "emit_event",
    "enqueue_workflow_run",
    "execute_due_runs",
    "get_agent_model_config",
    "get_agent_workflow_catalog",
    "get_agent_workflow_draft",
    "get_run_detail",
    "get_surface_draft",
    "list_pending_approvals",
    "list_runs",
    "list_webhook_dead_letters",
    "list_webhook_deliveries",
    "list_webhook_subscriptions",
    "replay_dead_letter",
    "resolve_agent_model_config",
    "resolve_approval",
    "test_agent_model_config",
    "test_webhook_subscription",
    "test_workflow_run",
    "trigger_delivery_retry",
    "trigger_webhook_workflow",
    "update_webhook_subscription",
]
