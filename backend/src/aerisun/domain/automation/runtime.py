from __future__ import annotations

import sqlite3
from contextlib import AbstractContextManager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt


class ModerationWorkflowState(TypedDict, total=False):
    run_id: str
    target_type: str
    target_id: str
    trigger_event: str
    context_payload: dict[str, Any]
    evaluation: dict[str, Any]
    approval_decision: dict[str, Any]
    result_payload: dict[str, Any]


class AutomationRuntime:
    def __init__(self, *, checkpoint_path: Path) -> None:
        self._checkpoint_path = checkpoint_path
        self._connection: sqlite3.Connection | None = None
        self._checkpointer: SqliteSaver | None = None
        self._graph = None

    def start(self) -> None:
        if self._graph is not None:
            return
        self._checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(str(self._checkpoint_path), check_same_thread=False)
        self._checkpointer = SqliteSaver(self._connection)
        self._graph = _build_moderation_graph(self._checkpointer)

    def stop(self) -> None:
        if self._connection is not None:
            self._connection.close()
        self._connection = None
        self._checkpointer = None
        self._graph = None

    @property
    def graph(self):
        if self._graph is None:
            raise RuntimeError("Automation runtime not started")
        return self._graph

    def invoke(self, state: dict[str, Any], *, thread_id: str) -> dict[str, Any]:
        return self.graph.invoke(state, config={"configurable": {"thread_id": thread_id}})

    def resume(self, *, thread_id: str, resume_value: Any) -> dict[str, Any]:
        return self.graph.invoke(Command(resume=resume_value), config={"configurable": {"thread_id": thread_id}})

    def get_state(self, *, thread_id: str, checkpoint_id: str | None = None):
        config = {"configurable": {"thread_id": thread_id}}
        if checkpoint_id:
            config["configurable"]["checkpoint_id"] = checkpoint_id
        return self.graph.get_state(config)

    def get_state_history(self, *, thread_id: str):
        return list(self.graph.get_state_history({"configurable": {"thread_id": thread_id}}))


def _load_target_context(state: ModerationWorkflowState) -> ModerationWorkflowState:
    payload = dict(state.get("context_payload") or {})
    payload.setdefault("loaded_at", datetime.now(UTC).isoformat())
    return {"context_payload": payload}


def _evaluate_moderation(state: ModerationWorkflowState) -> ModerationWorkflowState:
    context_payload = dict(state.get("context_payload") or {})
    preview = context_payload.get("body_preview") or ""
    needs_approval = True
    return {
        "evaluation": {
            "summary": f"需要人工确认 {state.get('target_type')}:{state.get('target_id')} 的处理动作。",
            "body_preview": preview,
            "needs_approval": needs_approval,
            "proposed_action": "approve",
        }
    }


def _request_approval(state: ModerationWorkflowState) -> ModerationWorkflowState:
    evaluation = dict(state.get("evaluation") or {})
    response = interrupt(
        {
            "approval_type": "moderation_decision",
            "run_id": state.get("run_id"),
            "target_type": state.get("target_type"),
            "target_id": state.get("target_id"),
            "message": evaluation.get("summary") or "需要人工审批。",
            "proposed_action": evaluation.get("proposed_action") or "approve",
            "body_preview": evaluation.get("body_preview") or "",
        }
    )
    return {"approval_decision": response}


def _apply_decision(state: ModerationWorkflowState) -> ModerationWorkflowState:
    decision = dict(state.get("approval_decision") or {})
    action = decision.get("action") or decision.get("proposed_action") or "approve"
    return {
        "result_payload": {
            "action": action,
            "target_type": state.get("target_type"),
            "target_id": state.get("target_id"),
            "applied": False,
            "note": "v1 runtime 仅记录决策，不直接执行站点写操作。",
        }
    }


def _build_moderation_graph(checkpointer: SqliteSaver):
    builder = StateGraph(ModerationWorkflowState)
    builder.add_node("load_target_context", _load_target_context)
    builder.add_node("evaluate_moderation", _evaluate_moderation)
    builder.add_node("request_approval", _request_approval)
    builder.add_node("apply_decision", _apply_decision)
    builder.add_edge(START, "load_target_context")
    builder.add_edge("load_target_context", "evaluate_moderation")
    builder.add_edge("evaluate_moderation", "request_approval")
    builder.add_edge("request_approval", "apply_decision")
    builder.add_edge("apply_decision", END)
    return builder.compile(checkpointer=checkpointer)
