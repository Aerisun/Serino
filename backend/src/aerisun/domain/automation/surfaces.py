"""Workflow-local surface draft helpers."""

from __future__ import annotations

import json
import logging
from typing import Any

from sqlalchemy.orm import Session

from aerisun.domain.automation import repository as repo
from aerisun.domain.automation._helpers import (
    backend_capability_catalog,
    ensure_workflow_ai_model,
    now_utc,
    planning_model_config,
)
from aerisun.domain.automation.catalog import build_workflow_catalog
from aerisun.domain.automation.drafts import WORKFLOW_DRAFT_MAX_MESSAGES, _draft_conversation_text
from aerisun.domain.automation.packs import (
    compiled_surface_catalog_from_pack,
    load_workflow_pack,
    workflow_from_pack,
    write_workflow_pack,
)
from aerisun.domain.automation.runtime import invoke_model_json
from aerisun.domain.automation.schemas import (
    ActionSurfaceSpec,
    AgentWorkflowGraph,
    SurfaceDraftApplyRead,
    SurfaceDraftChatWrite,
    SurfaceDraftMessageRead,
    SurfaceDraftPatchItemRead,
    SurfaceDraftRead,
)
from aerisun.domain.automation.settings import (
    clear_surface_draft_payload,
    get_agent_workflow,
    get_surface_draft_payload,
    save_surface_draft_payload,
)
from aerisun.domain.automation.validation import compile_workflow
from aerisun.domain.exceptions import ResourceNotFound, ValidationError

logger = logging.getLogger(__name__)


def _surface_draft_from_payload(raw: dict[str, Any] | None) -> SurfaceDraftRead | None:
    if not raw:
        return None
    try:
        return SurfaceDraftRead.model_validate(raw)
    except Exception:
        logger.warning("Failed to parse surface draft payload", exc_info=True)
        return None


def get_surface_draft(session: Session, *, workflow_key: str) -> SurfaceDraftRead | None:
    return _normalize_surface_draft(_surface_draft_from_payload(get_surface_draft_payload(session, workflow_key)))


def _persist_surface_draft(session: Session, *, workflow_key: str, draft: SurfaceDraftRead) -> SurfaceDraftRead:
    payload = save_surface_draft_payload(session, workflow_key, draft.model_dump(mode="json"))
    stored = _surface_draft_from_payload(payload)
    if stored is None:
        raise ValidationError("Failed to persist surface draft")
    return stored


def clear_surface_draft(session: Session, *, workflow_key: str) -> None:
    clear_surface_draft_payload(session, workflow_key)


def _normalize_surface_patches(raw: Any) -> list[SurfaceDraftPatchItemRead]:
    if not isinstance(raw, list):
        return []
    patches: list[SurfaceDraftPatchItemRead] = []
    for item in raw[:20]:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "").strip().lower()
        surface_kind = str(item.get("surface_kind") or "").strip()
        surface_key = str(item.get("surface_key") or "").strip()
        if action not in {"create", "update", "delete"} or surface_kind != "action_surface" or not surface_key:
            continue
        patches.append(
            SurfaceDraftPatchItemRead(
                action=action,
                surface_kind=surface_kind,
                surface_key=surface_key,
                reason=str(item.get("reason") or "").strip(),
                impact=str(item.get("impact") or "").strip(),
                human_summary=str(item.get("human_summary") or "").strip(),
                spec=dict(item.get("spec") or {}),
            )
        )
    return patches


def _canonicalize_action_surface_spec(surface_key: str, raw_spec: dict[str, Any]) -> dict[str, Any]:
    spec = dict(raw_spec or {})
    surface_mode = str(spec.get("surface_mode") or spec.get("mode") or "").strip().lower() or "atomic"
    raw_entries = spec.get("entries")
    if isinstance(raw_entries, list) and raw_entries:
        surface_mode = "bundle"
    label = str(spec.get("label") or spec.get("name") or spec.get("title") or "").strip()
    description = str(spec.get("description") or "").strip()
    action_key = str(spec.get("action_key") or "").strip()
    base_capability = str(spec.get("base_capability") or "").strip()
    if not action_key and base_capability:
        action_key = base_capability
    if not base_capability and action_key:
        base_capability = action_key
    entries: list[dict[str, Any]] = []
    if isinstance(raw_entries, list):
        for index, item in enumerate(raw_entries, start=1):
            entry = dict(item or {})
            entry_key = str(entry.get("key") or entry.get("entry_key") or f"entry_{index}").strip()
            entry_label = str(entry.get("label") or entry.get("name") or entry.get("title") or "").strip()
            entry_description = str(entry.get("description") or "").strip()
            entry_action_key = str(entry.get("action_key") or "").strip()
            entry_base_capability = str(entry.get("base_capability") or "").strip()
            if not entry_action_key and entry_base_capability:
                entry_action_key = entry_base_capability
            if not entry_base_capability and entry_action_key:
                entry_base_capability = entry_action_key
            entry_input_schema = dict(entry.get("input_schema") or {})
            entry_allowed_args = entry.get("allowed_args")
            if not isinstance(entry_allowed_args, list):
                entry_allowed_args = list(dict(entry_input_schema.get("properties") or {}).keys())
            entry_required_scopes = entry.get("required_scopes")
            if not isinstance(entry_required_scopes, list):
                entry_required_scopes = entry.get("scopes") if isinstance(entry.get("scopes"), list) else []
            entry_ref_binding = entry.get("ref_binding")
            if not isinstance(entry_ref_binding, dict):
                entry_ref_binding = {
                    "source": "input",
                    "path": "surface_ref",
                    "requires_surface": "",
                    "resolve_to": "",
                }
            entries.append(
                {
                    **entry,
                    "key": entry_key,
                    "label": entry_label,
                    "description": entry_description,
                    "action_key": entry_action_key,
                    "base_capability": entry_base_capability,
                    "allowed_args": entry_allowed_args,
                    "required_scopes": entry_required_scopes,
                    "ref_binding": entry_ref_binding,
                }
            )
    input_schema = dict(spec.get("input_schema") or {})
    input_properties = input_schema.get("properties")
    allowed_args = spec.get("allowed_args")
    if not isinstance(allowed_args, list):
        allowed_args = list(input_properties.keys()) if isinstance(input_properties, dict) else []
    required_scopes = spec.get("required_scopes")
    if not isinstance(required_scopes, list):
        required_scopes = spec.get("scopes") if isinstance(spec.get("scopes"), list) else []
    ref_binding = spec.get("ref_binding")
    if not isinstance(ref_binding, dict):
        ref_binding = {
            "source": "input",
            "path": "surface_ref",
            "requires_surface": "",
            "resolve_to": "",
        }
    return {
        **spec,
        "key": surface_key,
        "kind": "action_surface",
        "surface_mode": "bundle" if surface_mode == "bundle" else "atomic",
        "label": label,
        "description": description,
        "action_key": action_key,
        "base_capability": base_capability,
        "allowed_args": allowed_args,
        "required_scopes": required_scopes,
        "ref_binding": ref_binding,
        "entries": entries,
    }


def _action_surface_patch_issues(patch: SurfaceDraftPatchItemRead) -> list[str]:
    if (patch.surface_kind or "").strip() != "action_surface":
        return ["当前只支持工作流本地执行 Surface。"]
    spec = dict(patch.spec or {})
    issues: list[str] = []
    if isinstance(spec.get("steps"), list) or isinstance(spec.get("invocation"), dict):
        issues.append(
            f"执行 Surface '{patch.surface_key}' 仍然是旧的多步骤格式。执行 Surface 只能包装一个写能力；\"先查对象\"要放到只读工具里。"
        )
    canonical = _canonicalize_action_surface_spec(patch.surface_key, spec)
    if not str(canonical.get("label") or "").strip():
        issues.append(f"执行 Surface '{patch.surface_key}' 缺少显示名称。")
    if canonical.get("surface_mode") == "bundle":
        entries = list(canonical.get("entries") or [])
        if not entries:
            issues.append(f"动作包 Surface '{patch.surface_key}' 至少要包含一个 entry。")
        for entry in entries:
            entry_key = str(entry.get("key") or "").strip() or "entry"
            if not str(entry.get("label") or "").strip():
                issues.append(f"动作包 Surface '{patch.surface_key}' 的 entry '{entry_key}' 缺少显示名称。")
            if not str(entry.get("base_capability") or "").strip():
                issues.append(f"动作包 Surface '{patch.surface_key}' 的 entry '{entry_key}' 缺少基础能力 key。")
    elif not str(canonical.get("base_capability") or "").strip():
        issues.append(f"执行 Surface '{patch.surface_key}' 缺少基础能力 key。")
    return issues


def _normalize_surface_draft(draft: SurfaceDraftRead | None) -> SurfaceDraftRead | None:
    if draft is None:
        return None
    normalized_patches: list[SurfaceDraftPatchItemRead] = []
    patch_issues: list[str] = []
    for patch in draft.patches:
        normalized_patch = patch
        if (patch.surface_kind or "").strip() == "action_surface":
            normalized_patch = patch.model_copy(
                update={"spec": _canonicalize_action_surface_spec(patch.surface_key, dict(patch.spec or {}))}
            )
        normalized_patches.append(normalized_patch)
        patch_issues.extend(_action_surface_patch_issues(normalized_patch))
    deduped_issues = list(dict.fromkeys([*(draft.validation_issues or []), *patch_issues]))
    if patch_issues:
        return draft.model_copy(
            update={
                "status": "active",
                "ready_to_apply": False,
                "patches": normalized_patches,
                "validation_issues": deduped_issues,
            }
        )
    if normalized_patches != draft.patches:
        return draft.model_copy(update={"patches": normalized_patches, "validation_issues": deduped_issues})
    return draft


def _surface_draft_has_legacy_query_content(draft: SurfaceDraftRead | None) -> bool:
    if draft is None:
        return False
    return any(
        (patch.surface_kind or "").strip() != "action_surface"
        or isinstance((patch.spec or {}).get("steps"), list)
        or isinstance((patch.spec or {}).get("invocation"), dict)
        for patch in draft.patches
    )


def continue_surface_draft(
    session: Session,
    *,
    workflow_key: str,
    payload: SurfaceDraftChatWrite,
) -> SurfaceDraftRead:
    workflow = get_agent_workflow(session, workflow_key)
    pack = load_workflow_pack(workflow_key)
    current = get_surface_draft(session, workflow_key=workflow_key)
    if _surface_draft_has_legacy_query_content(current):
        current = None
    now = now_utc()
    messages = list(current.messages if current else [])
    messages.append(SurfaceDraftMessageRead(role="user", content=payload.message.strip(), created_at=now))
    trimmed_messages = messages[-WORKFLOW_DRAFT_MAX_MESSAGES:]

    model_config = planning_model_config(ensure_workflow_ai_model(session), minimum_timeout_seconds=60)
    validation = compile_workflow(workflow.model_dump(mode="json"), session=session)
    compiled_catalog = compiled_surface_catalog_from_pack(pack)
    parsed = invoke_model_json(
        model_config,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are the Aerisun workflow-local surface assistant. "
                    "You may only propose create/update/delete patches for workflow-local action surfaces inside the current workflow pack. "
                    "Do not generate Python code. Return strict JSON with keys assistant_message, summary, ready_to_apply, "
                    "patches, and graph_mutation. patches is an array of objects with keys action, surface_kind, surface_key, "
                    "reason, impact, human_summary, and spec. surface_kind must always be action_surface. "
                    "Action surface specs support two modes: atomic or bundle. "
                    "atomic = one direct action capability with base_capability/action_key. "
                    "bundle = one surface file that groups multiple single-step action entries under entries[]. "
                    "Each bundle entry must still be single-step and must declare its own base_capability/action_key. "
                    "Do not invent steps, invocation scripts, or embedded readonly queries inside action surfaces. "
                    "Readonly queries belong to mounted tools, not action surfaces. "
                    "graph_mutation may include graph to fully replace the workflow graph when surface references must be updated. "
                    "Current workflow:\n"
                    f"{json.dumps(workflow.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                    "Current surfaces:\n"
                    f"{json.dumps({'query_surfaces': [item.model_dump(mode='json') for item in pack.query_surfaces], 'action_surfaces': [item.model_dump(mode='json') for item in pack.action_surfaces], 'human_catalog': compiled_catalog.model_dump(mode='json')}, ensure_ascii=False)}\n\n"
                    "Current validation issues:\n"
                    f"{json.dumps(validation.model_dump(mode='json'), ensure_ascii=False)}\n\n"
                    "Available capabilities:\n"
                    f"{json.dumps(backend_capability_catalog(session), ensure_ascii=False)}"
                ),
            },
            {
                "role": "user",
                "content": _draft_conversation_text(trimmed_messages),
            },
        ],
    )
    assistant_message = str(parsed.get("assistant_message") or "我已经整理了当前 surface 方案。").strip()
    summary = str(parsed.get("summary") or "").strip()
    ready_to_apply = bool(parsed.get("ready_to_apply"))
    patches = _normalize_surface_patches(parsed.get("patches"))
    graph_mutation = dict(parsed.get("graph_mutation") or {})
    trimmed_messages.append(SurfaceDraftMessageRead(role="assistant", content=assistant_message, created_at=now_utc()))
    draft = SurfaceDraftRead(
        workflow_key=workflow_key,
        status="ready" if ready_to_apply else "active",
        summary=summary,
        ready_to_apply=ready_to_apply,
        messages=trimmed_messages,
        patches=patches,
        graph_mutation=graph_mutation,
        validation_issues=[item.message for item in validation.issues],
        created_at=current.created_at if current else now,
        updated_at=now_utc(),
    )
    normalized_draft = _normalize_surface_draft(draft)
    return _persist_surface_draft(session, workflow_key=workflow_key, draft=normalized_draft or draft)


def apply_surface_draft(session: Session, *, workflow_key: str) -> SurfaceDraftApplyRead:
    workflow = get_agent_workflow(session, workflow_key)
    draft = get_surface_draft(session, workflow_key=workflow_key)
    if draft is None:
        raise ResourceNotFound("Surface draft not found")
    if _surface_draft_has_legacy_query_content(draft):
        raise ValidationError(
            "当前这份 Surface 计划还是旧版查询 Surface 方案，请先清空，然后重新让 AI 生成执行 Surface。"
        )
    if not draft.ready_to_apply and not draft.patches:
        raise ValidationError("Surface draft is not ready to apply")

    pack = load_workflow_pack(workflow_key)
    action_index = {item.key: item for item in pack.action_surfaces}
    task = repo.create_workflow_build_task(
        session,
        workflow_key=workflow_key,
        task_type="surface_apply",
        summary=draft.summary or "Apply workflow-local surface changes",
    )
    repo.add_workflow_build_task_step(
        session, task_id=task.id, name="load_pack", status="completed", detail="Loaded current workflow pack."
    )

    for patch in draft.patches:
        if patch.surface_kind != "action_surface":
            raise ValidationError("当前只支持应用工作流本地执行 Surface。")
        if patch.action == "delete":
            action_index.pop(patch.surface_key, None)
            continue
        try:
            action_index[patch.surface_key] = ActionSurfaceSpec.model_validate(
                _canonicalize_action_surface_spec(patch.surface_key, dict(patch.spec or {}))
            )
        except Exception as exc:
            raise ValidationError(f"Invalid action surface spec for {patch.surface_key}: {exc}") from exc

    next_graph = workflow.graph
    replacement_graph = draft.graph_mutation.get("graph")
    if isinstance(replacement_graph, dict):
        next_graph = AgentWorkflowGraph.model_validate(replacement_graph)
    next_workflow = workflow.model_copy(update={"graph": next_graph})
    validation = compile_workflow(next_workflow.model_dump(mode="json"), session=session)
    error = next((item for item in validation.issues if item.level == "error"), None)
    if error is not None:
        repo.add_workflow_build_task_step(
            session, task_id=task.id, name="validate", status="failed", detail=error.message
        )
        task.status = "failed"
        task.result_payload = validation.model_dump(mode="json")
        session.commit()
        raise ValidationError(error.message)

    repo.add_workflow_build_task_step(
        session,
        task_id=task.id,
        name="validate",
        status="completed",
        detail="Workflow graph and surfaces passed validation.",
    )
    saved_pack = write_workflow_pack(
        workflow=next_workflow,
        query_surfaces=list(pack.query_surfaces),
        action_surfaces=list(action_index.values()),
        built_in=pack.manifest.built_in,
    )
    repo.add_workflow_build_task_step(
        session,
        task_id=task.id,
        name="write_pack",
        status="completed",
        detail="Workflow pack written to .store/automation/packs.",
    )
    task.status = "completed"
    task.result_payload = {"workflow_key": workflow_key, "patch_count": len(draft.patches)}
    clear_surface_draft(session, workflow_key=workflow_key)
    session.commit()
    return SurfaceDraftApplyRead(
        ok=True,
        summary=draft.summary or "Surface changes applied.",
        workflow=workflow_from_pack(saved_pack),
        catalog=build_workflow_catalog(session, workflow_key=workflow_key),
    )
