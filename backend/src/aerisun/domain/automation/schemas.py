from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from aerisun.core.schemas import ModelBase


class ApprovalDecisionWrite(BaseModel):
    action: str = Field(default="approve")
    reason: str | None = None


class AgentModelConfigRead(ModelBase):
    enabled: bool = False
    provider: str = "openai_compatible"
    base_url: str = ""
    model: str = ""
    api_key: str = ""
    temperature: float = Field(default=0.2, ge=0, le=2)
    timeout_seconds: int = Field(default=20, ge=5, le=300)
    advisory_prompt: str = ""
    is_ready: bool = False


class AgentModelConfigUpdate(BaseModel):
    enabled: bool | None = None
    provider: str | None = None
    base_url: str | None = None
    model: str | None = None
    api_key: str | None = None
    temperature: float | None = Field(default=None, ge=0, le=2)
    timeout_seconds: int | None = Field(default=None, ge=5, le=300)
    advisory_prompt: str | None = None


class AgentModelConfigTestRead(ModelBase):
    ok: bool = True
    model: str
    endpoint: str
    summary: str


class AgentWorkflowGraphViewport(BaseModel):
    x: float = 0
    y: float = 0
    zoom: float = 1


class AgentWorkflowGraphNodePosition(BaseModel):
    x: float
    y: float


class AgentWorkflowGraphNode(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    type: str = Field(min_length=1, max_length=120)
    label: str = Field(default="", max_length=160)
    position: AgentWorkflowGraphNodePosition
    config: dict[str, Any] = Field(default_factory=dict)


class AgentWorkflowGraphEdge(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    source: str = Field(min_length=1, max_length=120)
    target: str = Field(min_length=1, max_length=120)
    source_handle: str | None = Field(default=None, max_length=120)
    target_handle: str | None = Field(default=None, max_length=120)
    label: str = Field(default="", max_length=160)
    type: str = Field(default="default", max_length=80)
    config: dict[str, Any] = Field(default_factory=dict)


class AgentWorkflowGraph(BaseModel):
    version: int = Field(default=2, ge=1, le=10)
    nodes: list[AgentWorkflowGraphNode] = Field(default_factory=list)
    edges: list[AgentWorkflowGraphEdge] = Field(default_factory=list)
    viewport: AgentWorkflowGraphViewport = Field(default_factory=AgentWorkflowGraphViewport)


class AgentWorkflowTriggerBinding(BaseModel):
    id: str = Field(min_length=1, max_length=120)
    type: str = Field(min_length=1, max_length=120)
    label: str = Field(default="", max_length=160)
    enabled: bool = True
    config: dict[str, Any] = Field(default_factory=dict)


class AgentWorkflowRuntimePolicy(BaseModel):
    approval_mode: str = Field(default="risk_based", max_length=80)
    allow_high_risk_without_approval: bool = False
    max_steps: int = Field(default=80, ge=1, le=500)
    retry_policy: dict[str, Any] = Field(default_factory=dict)
    default_model: str | None = Field(default=None, max_length=160)


class AgentWorkflowSummaryRead(ModelBase):
    trigger_labels: list[str] = Field(default_factory=list)
    node_count: int = 0
    operation_count: int = 0
    high_risk_operation_count: int = 0
    built_from_template: str | None = None
    narrative: str = ""


class AgentWorkflowCreate(BaseModel):
    key: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    enabled: bool = True
    schema_version: int = Field(default=2, ge=1, le=10)
    graph: AgentWorkflowGraph | None = None
    trigger_bindings: list[AgentWorkflowTriggerBinding] = Field(default_factory=list)
    runtime_policy: AgentWorkflowRuntimePolicy | None = None
    summary: dict[str, Any] | None = None

    # Legacy compatibility for old create flows during the replacement.
    trigger_event: str | None = Field(default=None, max_length=120)
    target_type: str | None = Field(default=None, max_length=80)
    require_human_approval: bool | None = None
    instructions: str | None = Field(default=None, max_length=4000)


class AgentWorkflowUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=500)
    enabled: bool | None = None
    schema_version: int | None = Field(default=None, ge=1, le=10)
    graph: AgentWorkflowGraph | None = None
    trigger_bindings: list[AgentWorkflowTriggerBinding] | None = None
    runtime_policy: AgentWorkflowRuntimePolicy | None = None
    summary: dict[str, Any] | None = None

    # Legacy compatibility for old update flows during the replacement.
    trigger_event: str | None = Field(default=None, max_length=120)
    target_type: str | None = Field(default=None, max_length=80)
    require_human_approval: bool | None = None
    instructions: str | None = Field(default=None, max_length=4000)


class AgentWorkflowRead(ModelBase):
    key: str
    name: str
    description: str
    enabled: bool = True
    schema_version: int = 2
    graph: AgentWorkflowGraph = Field(default_factory=AgentWorkflowGraph)
    trigger_bindings: list[AgentWorkflowTriggerBinding] = Field(default_factory=list)
    runtime_policy: AgentWorkflowRuntimePolicy = Field(default_factory=AgentWorkflowRuntimePolicy)
    summary: AgentWorkflowSummaryRead = Field(default_factory=AgentWorkflowSummaryRead)
    built_in: bool = False

    # Read-only derived fields kept for list views and transitional UI pieces.
    trigger_event: str | None = None
    target_type: str | None = None
    instructions: str = ""
    require_human_approval: bool = False


class AgentWorkflowCatalogOptionRead(ModelBase):
    value: str
    label: str
    description: str = ""
    system_value: str = ""
    group_key: str = ""
    group_label: str = ""
    target_types: list[str] = Field(default_factory=list)
    payload_fields: list[dict[str, str]] = Field(default_factory=list)
    example_payload: dict[str, Any] = Field(default_factory=dict)
    parameters: list[dict[str, Any]] = Field(default_factory=list)


class AgentWorkflowCatalogPortRead(ModelBase):
    id: str
    label: str
    side: str
    description: str = ""
    match_values: list[str] = Field(default_factory=list)
    data_schema: dict[str, Any] | None = None
    required: bool = True


class AgentWorkflowCatalogNodeTypeRead(ModelBase):
    type: str
    label: str
    category: str
    description: str = ""
    icon: str = ""
    default_config: dict[str, Any] = Field(default_factory=dict)
    config_schema: dict[str, Any] = Field(default_factory=dict)
    input_ports: list[AgentWorkflowCatalogPortRead] = Field(default_factory=list)
    output_ports: list[AgentWorkflowCatalogPortRead] = Field(default_factory=list)
    risk_level: str = "low"


class AgentWorkflowCatalogTriggerTypeRead(ModelBase):
    type: str
    label: str
    description: str = ""
    config_schema: dict[str, Any] = Field(default_factory=dict)
    example_config: dict[str, Any] = Field(default_factory=dict)
    supports_target_types: list[str] = Field(default_factory=list)


class AgentWorkflowCatalogOperationRead(ModelBase):
    key: str
    operation_type: str
    label: str
    description: str = ""
    group_key: str = ""
    group_label: str = ""
    risk_level: str = "low"
    required_scopes: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_schema: dict[str, Any] = Field(default_factory=dict)
    invocation: dict[str, Any] = Field(default_factory=dict)
    examples: list[dict[str, Any]] = Field(default_factory=list)


class AgentWorkflowCatalogApprovalTypeRead(ModelBase):
    key: str
    label: str
    description: str = ""
    config_schema: dict[str, Any] = Field(default_factory=dict)


class AgentWorkflowExpressionCatalogRead(ModelBase):
    helpers: list[dict[str, str]] = Field(default_factory=list)
    variables: list[dict[str, str]] = Field(default_factory=list)
    examples: list[str] = Field(default_factory=list)


class AgentWorkflowTemplateRead(ModelBase):
    key: str
    title: str
    description: str
    workflow: dict[str, Any] = Field(default_factory=dict)


class AgentWorkflowVariableSourceRead(ModelBase):
    key: str
    label: str
    description: str = ""
    payload_schema: dict[str, Any] = Field(default_factory=dict)


class AgentWorkflowCatalogRead(ModelBase):
    node_types: list[AgentWorkflowCatalogNodeTypeRead] = Field(default_factory=list)
    trigger_types: list[AgentWorkflowCatalogTriggerTypeRead] = Field(default_factory=list)
    trigger_events: list[AgentWorkflowCatalogOptionRead] = Field(default_factory=list)
    operation_catalog: list[AgentWorkflowCatalogOperationRead] = Field(default_factory=list)
    approval_types: list[AgentWorkflowCatalogApprovalTypeRead] = Field(default_factory=list)
    expression_catalog: AgentWorkflowExpressionCatalogRead = Field(default_factory=AgentWorkflowExpressionCatalogRead)
    template_catalog: list[AgentWorkflowTemplateRead] = Field(default_factory=list)
    variable_sources: list[AgentWorkflowVariableSourceRead] = Field(default_factory=list)
    readonly_tools: list[ToolSurfaceRead] = Field(default_factory=list)
    workflow_local_action_surfaces: list[ActionSurfaceRead] = Field(default_factory=list)


class AgentWorkflowValidationIssueRead(ModelBase):
    level: str = "error"
    code: str = ""
    message: str
    path: str = ""
    node_id: str | None = None
    edge_id: str | None = None


class AgentWorkflowValidationRead(ModelBase):
    ok: bool = True
    issues: list[AgentWorkflowValidationIssueRead] = Field(default_factory=list)


class AgentWorkflowDraftMessageRead(ModelBase):
    role: str
    content: str
    created_at: datetime


class AgentWorkflowDraftOptionRead(ModelBase):
    label: str
    value: str
    description: str = ""
    requires_input: bool = False


class AgentWorkflowDraftQuestionRead(ModelBase):
    key: str = ""
    prompt: str
    options: list[AgentWorkflowDraftOptionRead] = Field(default_factory=list)


class AgentWorkflowDraftBoundaryRead(ModelBase):
    requires_platform_extension: bool = False
    summary: str = ""
    missing_capabilities: list[str] = Field(default_factory=list)
    recommended_actions: list[str] = Field(default_factory=list)


class AgentWorkflowDraftLockStateRead(ModelBase):
    locked_nodes: list[str] = Field(default_factory=list)
    locked_edges: list[str] = Field(default_factory=list)
    locked_semantics: list[str] = Field(default_factory=list)


class AgentWorkflowDraftPreviewRead(ModelBase):
    name: str = ""
    description: str = ""
    graph: AgentWorkflowGraph = Field(default_factory=AgentWorkflowGraph)
    trigger_bindings: list[AgentWorkflowTriggerBinding] = Field(default_factory=list)
    runtime_policy: AgentWorkflowRuntimePolicy = Field(default_factory=AgentWorkflowRuntimePolicy)
    notes: list[str] = Field(default_factory=list)
    lock_state: AgentWorkflowDraftLockStateRead = Field(default_factory=AgentWorkflowDraftLockStateRead)


class AgentWorkflowDraftCompileReportRead(ModelBase):
    status: str = "idle"
    attempts: int = 0
    summary: str = ""
    issues: list[AgentWorkflowValidationIssueRead] = Field(default_factory=list)


class AgentWorkflowDraftRead(ModelBase):
    id: str = "global"
    status: str = "active"
    stage: str = "intent_collecting"
    summary: str = ""
    ready_to_create: bool = False
    suggested_template: str | None = None
    boundary: AgentWorkflowDraftBoundaryRead = Field(default_factory=AgentWorkflowDraftBoundaryRead)
    questions: list[AgentWorkflowDraftQuestionRead] = Field(default_factory=list)
    current_question: str = ""
    options: list[AgentWorkflowDraftOptionRead] = Field(default_factory=list)
    working_document: str = ""
    sketch_preview: AgentWorkflowDraftPreviewRead | None = None
    semantic_preview: AgentWorkflowDraftPreviewRead | None = None
    graph_candidate: AgentWorkflowDraftPreviewRead | None = None
    compile_report: AgentWorkflowDraftCompileReportRead = Field(default_factory=AgentWorkflowDraftCompileReportRead)
    messages: list[AgentWorkflowDraftMessageRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class AgentWorkflowDraftChatWrite(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    sketch_workflow: AgentWorkflowDraftPreviewRead | None = None


class AgentWorkflowDraftCreateWrite(BaseModel):
    force: bool = False
    refined_sketch_workflow: AgentWorkflowDraftPreviewRead | None = None


class AgentWorkflowDraftCreateRead(ModelBase):
    ok: bool = True
    summary: str
    draft_cleared: bool = True
    workflow: AgentWorkflowRead


class DeriveAiSchemaRequest(BaseModel):
    graph: AgentWorkflowGraph
    ai_node_id: str = Field(..., min_length=1, max_length=120)
    workflow_key: str | None = Field(default=None, max_length=80)


class AiContractNodeRefRead(BaseModel):
    node_label: str = ""
    node_type: str = ""


class AiContractPortRead(BaseModel):
    id: str = ""
    label: str = ""


class AiContractInputNoteRead(BaseModel):
    title: str = ""
    summary: str = ""
    operator_note: str = ""


class AiContractDownstreamNoteRead(BaseModel):
    title: str = ""
    summary: str = ""
    requirement: str = ""
    tips: list[str] = Field(default_factory=list)


class AiContractToolNoteRead(BaseModel):
    title: str = ""
    summary: str = ""
    tips: list[str] = Field(default_factory=list)


class AiContractUpstreamInputRead(BaseModel):
    kind: str = ""
    slot: str = ""
    label: str = ""
    from_node_id: str = ""
    from_node_type: str = ""
    from_node_label: str = ""
    source: AiContractNodeRefRead = Field(default_factory=AiContractNodeRefRead)
    from_port: AiContractPortRead = Field(default_factory=AiContractPortRead)
    provided_fields: list[str] = Field(default_factory=list)
    usage_note: str = ""
    source_summary: str = ""
    slot_note: str = ""
    note: AiContractInputNoteRead = Field(default_factory=AiContractInputNoteRead)


class AiContractDownstreamConsumerRead(BaseModel):
    target_node_id: str = ""
    target_node_type: str = ""
    target_node_label: str = ""
    target: AiContractNodeRefRead = Field(default_factory=AiContractNodeRefRead)
    target_port: AiContractPortRead = Field(default_factory=AiContractPortRead)
    required_fields: list[str] = Field(default_factory=list)
    usage_note: str = ""
    requirement_note: str = ""
    surface_key: str = ""
    surface_label: str = ""
    surface_description: str = ""
    surface_hints: list[str] = Field(default_factory=list)
    format_requirements: str = ""
    note: AiContractDownstreamNoteRead = Field(default_factory=AiContractDownstreamNoteRead)


class AiContractMountedToolRead(BaseModel):
    key: str = ""
    label: str = ""
    description: str = ""
    domain: str = ""
    sensitivity: str = ""
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    allowed_arguments: list[str] = Field(default_factory=list)
    fixed_arguments: dict[str, Any] = Field(default_factory=dict)
    auto_bound_arguments: list[str] = Field(default_factory=list)
    usage_notes: dict[str, list[str]] = Field(default_factory=dict)
    note: AiContractToolNoteRead = Field(default_factory=AiContractToolNoteRead)


class AiContractMountedActionRead(BaseModel):
    key: str = ""
    surface_key: str = ""
    entry_key: str = ""
    label: str = ""
    description: str = ""
    domain: str = ""
    risk_level: str = "medium"
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    allowed_arguments: list[str] = Field(default_factory=list)
    fixed_arguments: dict[str, Any] = Field(default_factory=dict)
    auto_bound_arguments: list[str] = Field(default_factory=list)
    usage_notes: dict[str, list[str]] = Field(default_factory=dict)
    note: AiContractToolNoteRead = Field(default_factory=AiContractToolNoteRead)


class AiContractToolUsagePolicyRead(BaseModel):
    mode: str = "recommended"
    minimum_tool_calls: int = 1


class AiContractOutputContractRead(BaseModel):
    summary: str = ""
    field_keys: list[str] = Field(default_factory=list)


class AiContractContextRead(BaseModel):
    node_id: str = ""
    node_type: str = "ai.task"
    upstream_inputs: list[AiContractUpstreamInputRead] = Field(default_factory=list)
    downstream_consumers: list[AiContractDownstreamConsumerRead] = Field(default_factory=list)
    mounted_tools: list[AiContractMountedToolRead] = Field(default_factory=list)
    mounted_actions: list[AiContractMountedActionRead] = Field(default_factory=list)
    tool_usage_policy: AiContractToolUsagePolicyRead = Field(default_factory=AiContractToolUsagePolicyRead)
    output_contract: AiContractOutputContractRead = Field(default_factory=AiContractOutputContractRead)


class DeriveAiSchemaResponse(BaseModel):
    output_schema: dict[str, Any]
    source_nodes: list[str] = Field(default_factory=list, description="Node IDs that contributed to the schema")
    contract_context: AiContractContextRead = Field(default_factory=AiContractContextRead)


# ---------------------------------------------------------------------------
# Tool Surface catalog (read-only view for frontend)
# ---------------------------------------------------------------------------


class ToolSurfaceRead(ModelBase):
    key: str
    base_capability: str = ""
    kind: str = ""
    workflow_local: bool = False
    domain: str = "misc"
    sensitivity: str = "business"
    label: str = ""
    description: str = ""
    risk_level: str = "low"
    required_scopes: list[str] = Field(default_factory=list)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    response_schema: dict[str, Any] = Field(default_factory=dict)
    output_projection: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    allowed_args: list[str] = Field(default_factory=list)
    fixed_args: dict[str, Any] = Field(default_factory=dict)
    bound_args: dict[str, dict[str, Any]] = Field(default_factory=dict)
    human_card: dict[str, list[str]] = Field(default_factory=dict)


class ActionSurfaceEntryRead(ModelBase):
    key: str
    label: str = ""
    description: str = ""
    action_key: str = ""
    base_capability: str = ""
    risk_level: str = "low"
    required_scopes: list[str] = Field(default_factory=list)
    fixed_args: dict[str, Any] = Field(default_factory=dict)
    allowed_args: list[str] = Field(default_factory=list)
    bound_args: dict[str, dict[str, Any]] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_projection: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    requires_ref: bool = False
    allowed_source_query_keys: list[str] = Field(default_factory=list)
    ref_binding: dict[str, Any] = Field(default_factory=dict)
    human_card: dict[str, list[str]] = Field(default_factory=dict)


class ActionSurfaceRead(ModelBase):
    key: str
    surface_mode: str = "atomic"
    action_key: str = ""
    domain: str = ""
    base_capability: str = ""
    kind: str = ""
    workflow_local: bool = False
    label: str = ""
    description: str = ""
    risk_level: str = "low"
    required_scopes: list[str] = Field(default_factory=list)
    fixed_args: dict[str, Any] = Field(default_factory=dict)
    allowed_args: list[str] = Field(default_factory=list)
    bound_args: dict[str, dict[str, Any]] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_projection: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    requires_ref: bool = False
    allowed_source_query_keys: list[str] = Field(default_factory=list)
    ref_binding: dict[str, Any] = Field(default_factory=dict)
    human_card: dict[str, list[str]] = Field(default_factory=dict)
    entries: list[ActionSurfaceEntryRead] = Field(default_factory=list)


class SurfaceBoundArgConfig(ModelBase):
    source: str = ""
    path: str = ""


class SurfaceRefBindingConfig(ModelBase):
    source: str = "input"
    path: str = "surface_ref"
    requires_surface: str = ""
    resolve_to: str = ""


class ActionSurfaceEntrySpec(ModelBase):
    key: str = Field(min_length=1, max_length=160)
    label: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    action_key: str = Field(default="", max_length=160)
    base_capability: str = Field(default="", max_length=160)
    risk_level: str = Field(default="medium", max_length=40)
    required_scopes: list[str] = Field(default_factory=list)
    fixed_args: dict[str, Any] = Field(default_factory=dict)
    allowed_args: list[str] = Field(default_factory=list)
    bound_args: dict[str, SurfaceBoundArgConfig] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_projection: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    requires_ref: bool = False
    allowed_source_query_keys: list[str] = Field(default_factory=list)
    ref_binding: SurfaceRefBindingConfig = Field(default_factory=SurfaceRefBindingConfig)
    notes: list[str] = Field(default_factory=list)


class QuerySurfaceSpec(ModelBase):
    key: str = Field(min_length=1, max_length=160)
    kind: str = Field(default="query_surface", pattern=r"^query_surface$")
    label: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    base_capability: str = Field(min_length=1, max_length=160)
    risk_level: str = Field(default="low", max_length=40)
    required_scopes: list[str] = Field(default_factory=list)
    fixed_args: dict[str, Any] = Field(default_factory=dict)
    allowed_args: list[str] = Field(default_factory=list)
    bound_args: dict[str, SurfaceBoundArgConfig] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_projection: dict[str, Any] = Field(default_factory=dict)
    ref_resource: str = Field(default="", max_length=120)
    ref_id_field: str = Field(default="", max_length=120)
    allowed_action_keys: list[str] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


class ActionSurfaceSpec(ModelBase):
    key: str = Field(min_length=1, max_length=160)
    kind: str = Field(default="action_surface", pattern=r"^action_surface$")
    surface_mode: str = Field(default="atomic", pattern=r"^(atomic|bundle)$")
    action_key: str = Field(default="", max_length=160)
    domain: str = Field(default="", max_length=80)
    label: str = Field(min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)
    base_capability: str = Field(default="", max_length=160)
    risk_level: str = Field(default="medium", max_length=40)
    required_scopes: list[str] = Field(default_factory=list)
    fixed_args: dict[str, Any] = Field(default_factory=dict)
    allowed_args: list[str] = Field(default_factory=list)
    bound_args: dict[str, SurfaceBoundArgConfig] = Field(default_factory=dict)
    input_schema: dict[str, Any] = Field(default_factory=dict)
    output_projection: dict[str, Any] = Field(default_factory=dict)
    requires_approval: bool = False
    requires_ref: bool = False
    allowed_source_query_keys: list[str] = Field(default_factory=list)
    ref_binding: SurfaceRefBindingConfig = Field(default_factory=SurfaceRefBindingConfig)
    notes: list[str] = Field(default_factory=list)
    entries: list[ActionSurfaceEntrySpec] = Field(default_factory=list)


class WorkflowPackManifest(ModelBase):
    key: str = Field(min_length=3, max_length=80, pattern=r"^[a-z0-9][a-z0-9_-]*$")
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    enabled: bool = True
    schema_version: int = Field(default=2, ge=1, le=10)
    built_in: bool = False
    trigger_bindings: list[AgentWorkflowTriggerBinding] = Field(default_factory=list)
    runtime_policy: AgentWorkflowRuntimePolicy = Field(default_factory=AgentWorkflowRuntimePolicy)
    summary: AgentWorkflowSummaryRead = Field(default_factory=AgentWorkflowSummaryRead)
    archived: bool = False


class WorkflowPackRead(ModelBase):
    manifest: WorkflowPackManifest
    graph: AgentWorkflowGraph = Field(default_factory=AgentWorkflowGraph)
    query_surfaces: list[QuerySurfaceSpec] = Field(default_factory=list)
    action_surfaces: list[ActionSurfaceSpec] = Field(default_factory=list)
    readme: str = ""


class CompiledSurfaceCatalog(ModelBase):
    workflow_key: str
    query_surfaces: list[ToolSurfaceRead] = Field(default_factory=list)
    action_surfaces: list[ActionSurfaceRead] = Field(default_factory=list)
    readme: str = ""


class SurfaceDraftMessageRead(ModelBase):
    role: str
    content: str
    created_at: datetime


class SurfaceDraftPatchItemRead(ModelBase):
    action: str
    surface_kind: str
    surface_key: str
    reason: str = ""
    impact: str = ""
    human_summary: str = ""
    spec: dict[str, Any] = Field(default_factory=dict)


class SurfaceDraftRead(ModelBase):
    workflow_key: str
    status: str = "active"
    summary: str = ""
    ready_to_apply: bool = False
    messages: list[SurfaceDraftMessageRead] = Field(default_factory=list)
    patches: list[SurfaceDraftPatchItemRead] = Field(default_factory=list)
    graph_mutation: dict[str, Any] = Field(default_factory=dict)
    validation_issues: list[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class SurfaceDraftChatWrite(BaseModel):
    message: str = Field(min_length=1, max_length=4000)


class SurfaceDraftApplyRead(ModelBase):
    ok: bool = True
    summary: str = ""
    workflow: AgentWorkflowRead
    catalog: AgentWorkflowCatalogRead | None = None


class WorkflowBuildTaskStepRead(ModelBase):
    name: str
    status: str
    detail: str = ""
    created_at: datetime


class WorkflowBuildTaskRead(ModelBase):
    id: str
    workflow_key: str
    task_type: str
    status: str
    summary: str = ""
    steps: list[WorkflowBuildTaskStepRead] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime


class GateStateRead(ModelBase):
    workflow_key: str
    node_id: str
    status: str = "closed"
    in_flight_run_id: str | None = None
    buffer_size: int = 0


# ---------------------------------------------------------------------------
# Agent three-contract types
# ---------------------------------------------------------------------------


class InputSelectorConfig(ModelBase):
    source: str = ""
    node_id: str = ""
    port: str = ""
    path: str = ""
    value: Any = None


class InputContractField(ModelBase):
    key: str
    field_schema: dict[str, Any] = Field(default_factory=dict)
    required: bool = True
    selector: InputSelectorConfig = Field(default_factory=InputSelectorConfig)


class InputContractConfig(ModelBase):
    fields: list[InputContractField] = Field(default_factory=list)


class RouteConfig(ModelBase):
    field: str = ""
    enum: list[str] = Field(default_factory=list)
    enum_from_edges: bool = False


class OutputContractConfig(ModelBase):
    output_schema: dict[str, Any] = Field(default_factory=dict)
    route: RouteConfig | None = None


class ToolContractConfig(ModelBase):
    tools: list[str] = Field(default_factory=list)


class AgentWorkflowRunCreateWrite(BaseModel):
    trigger_binding_id: str | None = Field(default=None, max_length=120)
    trigger_event: str | None = Field(default=None, max_length=120)
    target_type: str | None = Field(default=None, max_length=80)
    target_id: str | None = Field(default=None, max_length=120)
    context_payload: dict[str, Any] = Field(default_factory=dict)
    input_payload: dict[str, Any] = Field(default_factory=dict)
    execute_immediately: bool = True


class AgentWorkflowRunCreateRead(ModelBase):
    run: AgentRunRead
    steps: list[AgentRunStepRead] = Field(default_factory=list)
    validation: AgentWorkflowValidationRead = Field(default_factory=AgentWorkflowValidationRead)


class AgentWorkflowWebhookTriggerRead(ModelBase):
    ok: bool = True
    run: AgentRunRead | None = None
    accepted: bool = True
    summary: str = ""


class WebhookSubscriptionCreate(BaseModel):
    name: str
    target_url: str
    event_types: list[str] = Field(default_factory=list)
    secret: str | None = None
    timeout_seconds: int = 10
    max_attempts: int = 6
    status: str = "active"
    headers: dict[str, Any] = Field(default_factory=dict)


class WebhookSubscriptionUpdate(BaseModel):
    name: str | None = None
    target_url: str | None = None
    event_types: list[str] | None = None
    secret: str | None = None
    timeout_seconds: int | None = None
    max_attempts: int | None = None
    status: str | None = None
    headers: dict[str, Any] | None = None


class TelegramWebhookConnectWrite(BaseModel):
    bot_token: str = Field(min_length=10, max_length=256)
    send_test_message: bool = True


class TelegramWebhookConnectRead(ModelBase):
    ok: bool = False
    status: str
    summary: str
    bot_username: str | None = None
    chat_id: int | str | None = None
    target_url: str | None = None


class AgentRunRead(ModelBase):
    id: str
    workflow_key: str
    status: str
    trigger_kind: str
    trigger_event: str | None = None
    target_type: str | None = None
    target_id: str | None = None
    thread_id: str
    latest_checkpoint_id: str | None = None
    checkpoint_ns: str | None = None
    input_payload: dict[str, Any] = Field(default_factory=dict)
    context_payload: dict[str, Any] = Field(default_factory=dict)
    result_payload: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentRunStepRead(ModelBase):
    id: str
    run_id: str
    sequence_no: int
    node_key: str
    step_kind: str
    status: str
    narrative: str
    input_payload: dict[str, Any] = Field(default_factory=dict)
    output_payload: dict[str, Any] = Field(default_factory=dict)
    error_payload: dict[str, Any] = Field(default_factory=dict)
    started_at: datetime | None = None
    finished_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentRunApprovalRead(ModelBase):
    id: str
    run_id: str
    step_id: str | None = None
    interrupt_id: str
    node_key: str
    approval_type: str
    status: str
    request_payload: dict[str, Any] = Field(default_factory=dict)
    response_payload: dict[str, Any] = Field(default_factory=dict)
    requested_by_type: str
    resolved_by_type: str | None = None
    resolved_by_id: str | None = None
    resolved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class AgentRunCollectionRead(BaseModel):
    items: list[AgentRunRead] = Field(default_factory=list)


class WebhookSubscriptionRead(ModelBase):
    id: str
    name: str
    status: str
    target_url: str
    secret: str | None = None
    event_types: list[str] = Field(default_factory=list)
    timeout_seconds: int
    max_attempts: int
    backoff_policy: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    last_delivery_at: datetime | None = None
    last_success_at: datetime | None = None
    last_test_status: str | None = None
    last_test_error: str | None = None
    last_tested_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebhookDeliveryRead(ModelBase):
    id: str
    subscription_id: str
    event_type: str
    event_id: str
    status: str
    target_url: str
    payload: dict[str, Any] = Field(default_factory=dict)
    headers: dict[str, Any] = Field(default_factory=dict)
    attempt_count: int
    next_attempt_at: datetime | None = None
    last_attempt_at: datetime | None = None
    last_response_status: int | None = None
    last_response_body: str | None = None
    last_error: str | None = None
    delivered_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class WebhookDeadLetterRead(ModelBase):
    id: str
    delivery_id: str
    subscription_id: str
    event_type: str
    event_id: str
    reason: str
    payload: dict[str, Any] = Field(default_factory=dict)
    last_response_status: int | None = None
    last_error: str | None = None
    dead_lettered_at: datetime
    created_at: datetime
    updated_at: datetime
