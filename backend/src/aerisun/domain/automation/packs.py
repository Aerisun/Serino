from __future__ import annotations

import json
import shutil
from pathlib import Path
from tempfile import mkdtemp
from typing import Any
from uuid import uuid4

import yaml

from aerisun.core.settings import get_settings
from aerisun.domain.automation import compat
from aerisun.domain.automation.schemas import (
    ActionSurfaceEntryRead,
    ActionSurfaceRead,
    ActionSurfaceSpec,
    AgentWorkflowGraph,
    AgentWorkflowRead,
    CompiledSurfaceCatalog,
    QuerySurfaceSpec,
    ToolSurfaceRead,
    WorkflowPackManifest,
    WorkflowPackRead,
)
from aerisun.domain.exceptions import ResourceNotFound, ValidationError

PACKS_DIRNAME = "automation/packs"
MANIFEST_FILENAME = "manifest.yaml"
GRAPH_FILENAME = "workflow.graph.json"
README_FILENAME = "README.generated.md"
SURFACES_DIRNAME = "surfaces"


def workflow_packs_root() -> Path:
    return get_settings().data_dir / PACKS_DIRNAME


def workflow_pack_path(workflow_key: str) -> Path:
    return workflow_packs_root() / workflow_key


def _manifest_path(pack_dir: Path) -> Path:
    return pack_dir / MANIFEST_FILENAME


def _graph_path(pack_dir: Path) -> Path:
    return pack_dir / GRAPH_FILENAME


def _surfaces_path(pack_dir: Path) -> Path:
    return pack_dir / SURFACES_DIRNAME


def _readme_path(pack_dir: Path) -> Path:
    return pack_dir / README_FILENAME


def _load_yaml_file(path: Path) -> dict[str, Any]:
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ResourceNotFound(f"Missing workflow pack file: {path.name}") from exc
    except yaml.YAMLError as exc:
        raise ValidationError(f"Invalid YAML in {path.name}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValidationError(f"Workflow pack file {path.name} must contain one object")
    return raw


def _load_json_file(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ResourceNotFound(f"Missing workflow pack file: {path.name}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"Invalid JSON in {path.name}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ValidationError(f"Workflow pack file {path.name} must contain one object")
    return raw


def _human_card_for_query(spec: QuerySurfaceSpec) -> dict[str, list[str]]:
    reads = [f"读取 {spec.label}。"]
    cannot_read = [
        "不会读取未在这个 surface 中声明的字段。",
        "不会读取当前工作流以外的其他本地 surface 数据。",
    ]
    can_act = [
        "这是只读 surface，本身不会执行写入或审批动作。",
    ]
    cannot_act = [
        "不能直接修改内容、评论、留言或配置。",
    ]
    parameter_sources = []
    if spec.fixed_args:
        parameter_sources.append(f"固定参数：{', '.join(sorted(spec.fixed_args.keys()))}")
    if spec.allowed_args:
        parameter_sources.append(f"允许 AI 传入：{', '.join(spec.allowed_args)}")
    if spec.bound_args:
        parameter_sources.append(f"自动绑定：{', '.join(sorted(spec.bound_args.keys()))}")
    if spec.ref_id_field:
        can_act.append(f"会为返回对象生成不透明引用，用于后续受限动作：{spec.ref_id_field}")
    return {
        "reads": reads,
        "cannot_read": cannot_read,
        "can_act": can_act,
        "cannot_act": cannot_act,
        "parameter_sources": parameter_sources,
    }


def _human_card_for_action(spec: ActionSurfaceSpec) -> dict[str, list[str]]:
    reads = ["不会额外读取未授权对象，只消费已有输入和对象引用。"]
    cannot_read = ["不能绕过上游 query surface 直接操作任意对象。"]
    can_act = [f"执行动作：{spec.label}。"]
    if spec.surface_mode == "bundle" and spec.entries:
        can_act = [f"执行动作包：{spec.label}。"]
        can_act.append(f"可选动作：{', '.join(entry.label for entry in spec.entries[:5])}")
    if spec.allowed_source_query_keys:
        can_act.append(f"只允许来自：{', '.join(spec.allowed_source_query_keys)}")
    cannot_act = ["不能接收裸对象 ID。", "不能操作未通过 surface_ref 授权的对象。"]
    parameter_sources = []
    if spec.fixed_args:
        parameter_sources.append(f"固定参数：{', '.join(sorted(spec.fixed_args.keys()))}")
    if spec.bound_args:
        parameter_sources.append(f"自动绑定：{', '.join(sorted(spec.bound_args.keys()))}")
    if spec.ref_binding.resolve_to:
        parameter_sources.append(f"对象引用会在服务端解出为：{spec.ref_binding.resolve_to}")
    if spec.surface_mode == "bundle":
        parameter_sources.append("这是一个动作能力包，AI 会在可选 entry 中自行选择。")
    return {
        "reads": reads,
        "cannot_read": cannot_read,
        "can_act": can_act,
        "cannot_act": cannot_act,
        "parameter_sources": parameter_sources,
    }


def compile_query_surface(spec: QuerySurfaceSpec) -> ToolSurfaceRead:
    return ToolSurfaceRead(
        key=spec.key,
        base_capability=spec.base_capability,
        kind="query",
        workflow_local=True,
        domain="workflow",
        sensitivity="business" if spec.risk_level == "low" else "operational",
        label=spec.label,
        description=spec.description,
        risk_level=spec.risk_level,
        required_scopes=list(spec.required_scopes),
        fixed_args=dict(spec.fixed_args),
        allowed_args=list(spec.allowed_args),
        bound_args={key: value.model_dump(mode="json") for key, value in spec.bound_args.items()},
        input_schema=dict(spec.input_schema),
        response_schema=dict(spec.output_projection),
        output_projection=dict(spec.output_projection),
        requires_approval=False,
        human_card=_human_card_for_query(spec),
    )


def compile_action_surface(spec: ActionSurfaceSpec) -> ActionSurfaceRead:
    return ActionSurfaceRead(
        key=spec.key,
        surface_mode=spec.surface_mode,
        action_key=spec.action_key,
        domain=spec.domain,
        base_capability=spec.base_capability,
        kind="action",
        workflow_local=True,
        label=spec.label,
        description=spec.description,
        risk_level=spec.risk_level,
        required_scopes=list(spec.required_scopes),
        fixed_args=dict(spec.fixed_args),
        allowed_args=list(spec.allowed_args),
        bound_args={key: value.model_dump(mode="json") for key, value in spec.bound_args.items()},
        input_schema=dict(spec.input_schema),
        output_projection=dict(spec.output_projection),
        requires_approval=spec.requires_approval,
        requires_ref=spec.requires_ref,
        allowed_source_query_keys=list(spec.allowed_source_query_keys),
        ref_binding=spec.ref_binding.model_dump(mode="json"),
        human_card=_human_card_for_action(spec),
        entries=[
            ActionSurfaceEntryRead(
                key=entry.key,
                label=entry.label,
                description=entry.description,
                action_key=entry.action_key,
                base_capability=entry.base_capability,
                risk_level=entry.risk_level,
                required_scopes=list(entry.required_scopes),
                fixed_args=dict(entry.fixed_args),
                allowed_args=list(entry.allowed_args),
                bound_args={key: value.model_dump(mode="json") for key, value in entry.bound_args.items()},
                input_schema=dict(entry.input_schema),
                output_projection=dict(entry.output_projection),
                requires_approval=entry.requires_approval,
                requires_ref=entry.requires_ref,
                allowed_source_query_keys=list(entry.allowed_source_query_keys),
                ref_binding=entry.ref_binding.model_dump(mode="json"),
                human_card={
                    "reads": ["不会额外读取未授权对象，只消费已有输入和对象引用。"],
                    "cannot_read": ["不能绕过上游 query surface 直接操作任意对象。"],
                    "can_act": [f"执行动作：{entry.label}。"],
                    "cannot_act": ["不能接收裸对象 ID。", "不能操作未通过 surface_ref 授权的对象。"],
                    "parameter_sources": [
                        *([f"固定参数：{', '.join(sorted(entry.fixed_args.keys()))}"] if entry.fixed_args else []),
                        *([f"自动绑定：{', '.join(sorted(entry.bound_args.keys()))}"] if entry.bound_args else []),
                        *(
                            [f"对象引用会在服务端解出为：{entry.ref_binding.resolve_to}"]
                            if entry.ref_binding.resolve_to
                            else []
                        ),
                    ],
                },
            )
            for entry in spec.entries
        ],
    )


def render_pack_readme(pack: WorkflowPackRead) -> str:
    lines = [
        f"# {pack.manifest.name}",
        "",
        pack.manifest.description.strip() or "No description.",
        "",
        "## Workflow",
        f"- Key: `{pack.manifest.key}`",
        f"- Enabled: `{str(pack.manifest.enabled).lower()}`",
        f"- Built-in: `{str(pack.manifest.built_in).lower()}`",
        "",
        "## Query Surfaces",
    ]
    if not pack.query_surfaces:
        lines.append("- None")
    for spec in pack.query_surfaces:
        lines.extend(
            [
                f"### {spec.label} (`{spec.key}`)",
                spec.description or "No description.",
                f"- Base capability: `{spec.base_capability}`",
                f"- Reads object type: `{spec.ref_resource or 'generic'}`",
                f"- Ref field: `{spec.ref_id_field or 'none'}`",
                f"- Allowed actions: {', '.join(spec.allowed_action_keys) if spec.allowed_action_keys else 'none'}",
                "",
            ]
        )
    lines.append("## Action Surfaces")
    if not pack.action_surfaces:
        lines.append("- None")
    for spec in pack.action_surfaces:
        lines.extend(
            [
                f"### {spec.label} (`{spec.key}`)",
                spec.description or "No description.",
                f"- Base capability: `{spec.base_capability}`",
                f"- Requires approval: `{str(spec.requires_approval).lower()}`",
                (
                    f"- Allowed source queries: {', '.join(spec.allowed_source_query_keys)}"
                    if spec.allowed_source_query_keys
                    else "- Allowed source queries: none"
                ),
                (
                    f"- Surface ref resolves to: `{spec.ref_binding.resolve_to}`"
                    if spec.ref_binding.resolve_to
                    else "- Surface ref resolves to: none"
                ),
                "",
            ]
        )
    return "\n".join(lines).strip() + "\n"


def _load_surface_specs(pack_dir: Path) -> tuple[list[QuerySurfaceSpec], list[ActionSurfaceSpec]]:
    query_surfaces: list[QuerySurfaceSpec] = []
    action_surfaces: list[ActionSurfaceSpec] = []
    surfaces_dir = _surfaces_path(pack_dir)
    if not surfaces_dir.exists():
        return query_surfaces, action_surfaces
    seen: set[str] = set()
    for path in sorted(surfaces_dir.glob("*.surface.yaml")):
        raw = _load_yaml_file(path)
        kind = str(raw.get("kind") or "").strip()
        if kind == "query_surface":
            spec = QuerySurfaceSpec.model_validate(raw)
        elif kind == "action_surface":
            spec = ActionSurfaceSpec.model_validate(raw)
        else:
            raise ValidationError(f"Unknown surface kind in {path.name}: {kind}")
        if spec.key in seen:
            raise ValidationError(f"Duplicate surface key in workflow pack {pack_dir.name}: {spec.key}")
        seen.add(spec.key)
        if kind == "query_surface":
            query_surfaces.append(spec)
        else:
            action_surfaces.append(spec)  # type: ignore[arg-type]
    return query_surfaces, action_surfaces


def load_workflow_pack(workflow_key: str) -> WorkflowPackRead:
    pack_dir = workflow_pack_path(workflow_key)
    if not pack_dir.exists():
        raise ResourceNotFound("Workflow pack not found")
    manifest = WorkflowPackManifest.model_validate(_load_yaml_file(_manifest_path(pack_dir)))
    graph = AgentWorkflowGraph.model_validate(_load_json_file(_graph_path(pack_dir)))
    query_surfaces, action_surfaces = _load_surface_specs(pack_dir)
    readme = _readme_path(pack_dir).read_text(encoding="utf-8") if _readme_path(pack_dir).exists() else ""
    return WorkflowPackRead(
        manifest=manifest,
        graph=AgentWorkflowGraph.model_validate(compat.normalize_graph_payload(graph.model_dump(mode="json"))),
        query_surfaces=query_surfaces,
        action_surfaces=action_surfaces,
        readme=readme,
    )


def workflow_from_pack(pack: WorkflowPackRead) -> AgentWorkflowRead:
    manifest = pack.manifest
    payload = {
        "key": manifest.key,
        "name": manifest.name,
        "description": manifest.description,
        "enabled": manifest.enabled and not manifest.archived,
        "schema_version": manifest.schema_version,
        "graph": pack.graph.model_dump(mode="json"),
        "trigger_bindings": [item.model_dump(mode="json") for item in manifest.trigger_bindings],
        "runtime_policy": manifest.runtime_policy.model_dump(mode="json"),
        "summary": manifest.summary.model_dump(mode="json"),
        "built_in": manifest.built_in,
    }
    return AgentWorkflowRead.model_validate(
        {
            **payload,
            **compat.derive_legacy_fields(payload),
        }
    )


def compiled_surface_catalog_from_pack(pack: WorkflowPackRead) -> CompiledSurfaceCatalog:
    return CompiledSurfaceCatalog(
        workflow_key=pack.manifest.key,
        query_surfaces=[compile_query_surface(item) for item in pack.query_surfaces],
        action_surfaces=[compile_action_surface(item) for item in pack.action_surfaces],
        readme=pack.readme or render_pack_readme(pack),
    )


def list_workflow_packs() -> list[WorkflowPackRead]:
    root = workflow_packs_root()
    if not root.exists():
        return []
    packs: list[WorkflowPackRead] = []
    for path in sorted(root.iterdir()):
        if not path.is_dir():
            continue
        packs.append(load_workflow_pack(path.name))
    return packs


def workflow_pack_exists(workflow_key: str) -> bool:
    return workflow_pack_path(workflow_key).exists()


def write_workflow_pack(
    *,
    workflow: AgentWorkflowRead,
    query_surfaces: list[QuerySurfaceSpec] | None = None,
    action_surfaces: list[ActionSurfaceSpec] | None = None,
    built_in: bool | None = None,
) -> WorkflowPackRead:
    root = workflow_packs_root()
    root.mkdir(parents=True, exist_ok=True)
    pack_dir = workflow_pack_path(workflow.key)
    staging = Path(mkdtemp(prefix=f".pack-{workflow.key}-", dir=str(root)))
    surfaces_dir = _surfaces_path(staging)
    surfaces_dir.mkdir(parents=True, exist_ok=True)

    manifest = WorkflowPackManifest(
        key=workflow.key,
        name=workflow.name,
        description=workflow.description,
        enabled=workflow.enabled,
        schema_version=workflow.schema_version,
        built_in=workflow.built_in if built_in is None else built_in,
        trigger_bindings=workflow.trigger_bindings,
        runtime_policy=workflow.runtime_policy,
        summary=workflow.summary,
    )
    pack = WorkflowPackRead(
        manifest=manifest,
        graph=AgentWorkflowGraph.model_validate(compat.normalize_graph_payload(workflow.graph.model_dump(mode="json"))),
        query_surfaces=query_surfaces or [],
        action_surfaces=action_surfaces or [],
        readme="",
    )
    pack = pack.model_copy(update={"readme": render_pack_readme(pack)})

    _manifest_path(staging).write_text(
        yaml.safe_dump(manifest.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )
    _graph_path(staging).write_text(
        json.dumps(pack.graph.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for spec in pack.query_surfaces:
        (surfaces_dir / f"{spec.key}.surface.yaml").write_text(
            yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    for spec in pack.action_surfaces:
        (surfaces_dir / f"{spec.key}.surface.yaml").write_text(
            yaml.safe_dump(spec.model_dump(mode="json"), sort_keys=False, allow_unicode=True),
            encoding="utf-8",
        )
    _readme_path(staging).write_text(pack.readme, encoding="utf-8")

    backup: Path | None = None
    try:
        if pack_dir.exists():
            backup = pack_dir.with_name(f"{pack_dir.name}.bak-{uuid4().hex}")
            pack_dir.replace(backup)
        staging.replace(pack_dir)
    except Exception:
        if staging.exists():
            shutil.rmtree(staging, ignore_errors=True)
        if backup is not None and backup.exists() and not pack_dir.exists():
            backup.replace(pack_dir)
        raise
    if backup is not None and backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    return load_workflow_pack(workflow.key)


def delete_workflow_pack(workflow_key: str) -> None:
    pack_dir = workflow_pack_path(workflow_key)
    if not pack_dir.exists():
        raise ResourceNotFound("Workflow pack not found")
    shutil.rmtree(pack_dir)
