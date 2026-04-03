import {
  deleteWorkflowApiV1AdminAutomationWorkflowsWorkflowKeyDelete,
  deleteWorkflowSurfaceDraftApiV1AdminAutomationWorkflowsWorkflowKeySurfaceDraftDelete,
  getModelConfigApiV1AdminAutomationModelConfigGet,
  getWorkflowCatalogApiV1AdminAutomationWorkflowCatalogGet,
  getWorkflowSurfaceDraftApiV1AdminAutomationWorkflowsWorkflowKeySurfaceDraftGet,
  getWorkflowsApiV1AdminAutomationWorkflowsGet,
  postDeriveAiSchemaApiV1AdminAutomationWorkflowsDeriveAiSchemaPost,
  postModelConfigTestApiV1AdminAutomationModelConfigTestPost,
  postWorkflowApiV1AdminAutomationWorkflowsPost,
  postWorkflowRunApiV1AdminAutomationWorkflowsWorkflowKeyRunsPost,
  postWorkflowSurfaceDraftApplyApiV1AdminAutomationWorkflowsWorkflowKeySurfaceDraftApplyPost,
  postWorkflowSurfaceDraftMessageApiV1AdminAutomationWorkflowsWorkflowKeySurfaceDraftMessagesPost,
  postWorkflowTestRunApiV1AdminAutomationWorkflowsWorkflowKeyTestRunsPost,
  postWorkflowValidateApiV1AdminAutomationWorkflowsValidatePost,
  postWebhookTelegramConnectApiV1AdminAutomationWebhooksTelegramConnectPost,
  postWebhookTestApiV1AdminAutomationWebhooksTestPost,
  putModelConfigApiV1AdminAutomationModelConfigPut,
  putWorkflowApiV1AdminAutomationWorkflowsWorkflowKeyPut,
} from "@serino/api-client/admin";
import type {
  AgentModelConfigUpdate as AgentModelConfigUpdatePayload,
  AgentWorkflowCreate as AgentWorkflowInputPayload,
  AgentWorkflowRunCreateWrite as AgentWorkflowRunInputPayload,
  DeriveAiSchemaRequest as DeriveAiSchemaRequestPayload,
  GetWorkflowCatalogApiV1AdminAutomationWorkflowCatalogGetParams,
  PostWebhookTestApiV1AdminAutomationWebhooksTestPostParams,
  SurfaceDraftChatWrite as SurfaceDraftChatWritePayload,
  TelegramWebhookConnectRead,
  TelegramWebhookConnectWrite,
  WebhookSubscriptionCreate,
} from "@serino/api-client/models";
import type * as ApiModels from "@serino/api-client/models";

type RequireKeys<T, K extends keyof T> = Omit<T, K> & {
  [P in K]-?: NonNullable<T[P]>;
};

type RequireGraphShape<T extends { version?: unknown; nodes?: unknown; edges?: unknown; viewport?: unknown }> = RequireKeys<
  T,
  "version" | "nodes" | "edges" | "viewport"
>;

export type AgentModelConfig = Required<ApiModels.AgentModelConfigRead>;
export type AgentModelConfigTestResult = RequireKeys<ApiModels.AgentModelConfigTestRead, "ok">;
export type AgentRunRead = ApiModels.AgentRunRead;
export type AgentRunStepRead = ApiModels.AgentRunStepRead;
export type AgentWorkflowGraphViewport = ApiModels.AgentWorkflowGraphViewport;
export type AgentWorkflowGraphNodePosition = ApiModels.AgentWorkflowGraphNodePosition;
export type AgentWorkflowGraphNode = RequireKeys<ApiModels.AgentWorkflowGraphNode, "label" | "config">;
export type AgentWorkflowGraphEdge = RequireKeys<ApiModels.AgentWorkflowGraphEdge, "label" | "type" | "config">;
export type AgentWorkflowGraph = RequireGraphShape<ApiModels.AgentWorkflowGraphInput>;
export type AgentWorkflowTriggerBinding = RequireKeys<ApiModels.AgentWorkflowTriggerBinding, "label" | "enabled" | "config">;
export type AgentWorkflowRuntimePolicy = RequireKeys<
  ApiModels.AgentWorkflowRuntimePolicy,
  "approval_mode" | "allow_high_risk_without_approval" | "max_steps" | "retry_policy"
>;
export type AgentWorkflowSummary = RequireKeys<
  ApiModels.AgentWorkflowSummaryRead,
  "trigger_labels" | "node_count" | "operation_count" | "high_risk_operation_count" | "narrative"
>;
export type AgentWorkflowCatalogOption = RequireKeys<
  ApiModels.AgentWorkflowCatalogOptionRead,
  "description" | "system_value"
>;
export type AgentWorkflowCatalogPort = RequireKeys<
  ApiModels.AgentWorkflowCatalogPortRead,
  "description" | "match_values"
>;
export type AgentWorkflowCatalogNodeType = RequireKeys<
  ApiModels.AgentWorkflowCatalogNodeTypeRead,
  "description" | "icon" | "default_config" | "config_schema" | "input_ports" | "output_ports" | "risk_level"
>;
export type AgentWorkflowCatalogTriggerType = RequireKeys<
  ApiModels.AgentWorkflowCatalogTriggerTypeRead,
  "description" | "config_schema" | "example_config" | "supports_target_types"
>;
export type AgentWorkflowCatalogOperation = RequireKeys<
  ApiModels.AgentWorkflowCatalogOperationRead,
  "description" | "group_key" | "group_label" | "risk_level" | "required_scopes" | "input_schema" | "output_schema" | "invocation" | "examples"
>;
export type AgentWorkflowCatalogApprovalType = RequireKeys<
  ApiModels.AgentWorkflowCatalogApprovalTypeRead,
  "description" | "config_schema"
>;
export type AgentWorkflowExpressionCatalog = RequireKeys<
  ApiModels.AgentWorkflowExpressionCatalogRead,
  "helpers" | "variables" | "examples"
>;
export type AgentWorkflowTemplateCatalogItem = RequireKeys<ApiModels.AgentWorkflowTemplateRead, "workflow">;
export type AgentWorkflowVariableSource = RequireKeys<ApiModels.AgentWorkflowVariableSourceRead, "description" | "payload_schema">;
export type AgentWorkflowToolSurface = RequireKeys<ApiModels.ToolSurfaceRead, "kind" | "label" | "description" | "risk_level">;
export type AgentWorkflowActionSurface = RequireKeys<
  ApiModels.ActionSurfaceRead,
  "kind" | "label" | "description" | "risk_level"
>;
export type AgentWorkflowCatalog = RequireKeys<
  ApiModels.AgentWorkflowCatalogRead,
  "node_types" | "trigger_types" | "operation_catalog" | "approval_types" | "expression_catalog" | "template_catalog" | "variable_sources"
>;
export type AgentWorkflowValidationIssue = RequireKeys<ApiModels.AgentWorkflowValidationIssueRead, "level" | "code" | "path">;
export type AgentWorkflowValidationResult = RequireKeys<ApiModels.AgentWorkflowValidationRead, "ok" | "issues">;
export type AgentWorkflow = RequireKeys<
  ApiModels.AgentWorkflowRead,
  "enabled" | "schema_version" | "graph" | "trigger_bindings" | "runtime_policy" | "summary" | "built_in" | "trigger_event" | "target_type" | "require_human_approval" | "instructions"
> & {
  graph: AgentWorkflowGraph;
  trigger_bindings: AgentWorkflowTriggerBinding[];
  runtime_policy: AgentWorkflowRuntimePolicy;
  summary: AgentWorkflowSummary;
};

export interface AgentWorkflowRunInput {
  trigger_binding_id?: string | null;
  trigger_event?: string | null;
  target_type?: string | null;
  target_id?: string | null;
  context_payload?: Record<string, unknown>;
  input_payload?: Record<string, unknown>;
  execute_immediately?: boolean;
}

export type AgentWorkflowRunResult = RequireKeys<
  ApiModels.AgentWorkflowRunCreateRead,
  "steps" | "validation"
> & {
  run: AgentRunRead;
  steps: AgentRunStepRead[];
  validation: AgentWorkflowValidationResult;
};

export type SurfaceDraftMessage = ApiModels.SurfaceDraftMessageRead;
export type SurfaceDraftPatchItem = RequireKeys<
  ApiModels.SurfaceDraftPatchItemRead,
  "reason" | "impact" | "human_summary" | "spec"
>;

export interface SurfaceDraft {
  workflow_key: string;
  status: string;
  summary: string;
  ready_to_apply: boolean;
  messages: SurfaceDraftMessage[];
  patches: SurfaceDraftPatchItem[];
  graph_mutation: Record<string, unknown>;
  validation_issues: string[];
  created_at: string;
  updated_at: string;
}

export type SurfaceDraftApplyResult = RequireKeys<ApiModels.SurfaceDraftApplyRead, "ok" | "summary"> & {
  workflow: AgentWorkflow;
  catalog?: AgentWorkflowCatalog | null;
};

export type AgentModelConfigUpdate = AgentModelConfigUpdatePayload;

export type AgentWorkflowInput = AgentWorkflowInputPayload;

export function getAgentModelConfig() {
  return getModelConfigApiV1AdminAutomationModelConfigGet().then((response) => response.data as AgentModelConfig);
}

export function updateAgentModelConfig(data: AgentModelConfigUpdate) {
  return putModelConfigApiV1AdminAutomationModelConfigPut(data).then((response) => response.data as AgentModelConfig);
}

export function testAgentModelConfig(data: AgentModelConfigUpdate) {
  return postModelConfigTestApiV1AdminAutomationModelConfigTestPost(data).then(
    (response) => response.data as AgentModelConfigTestResult,
  );
}

export function getAgentWorkflows() {
  return getWorkflowsApiV1AdminAutomationWorkflowsGet().then((response) => response.data as AgentWorkflow[]);
}

export function getAgentWorkflowCatalog(workflowKey?: string | null) {
  const params: GetWorkflowCatalogApiV1AdminAutomationWorkflowCatalogGetParams | undefined = workflowKey
    ? { workflow_key: workflowKey }
    : undefined;
  return getWorkflowCatalogApiV1AdminAutomationWorkflowCatalogGet(params).then(
    (response) => response.data as AgentWorkflowCatalog,
  );
}

export function createAgentWorkflow(data: AgentWorkflowInput) {
  return postWorkflowApiV1AdminAutomationWorkflowsPost(data).then((response) => response.data as AgentWorkflow);
}

export function updateAgentWorkflow(workflowKey: string, data: AgentWorkflowInput) {
  return putWorkflowApiV1AdminAutomationWorkflowsWorkflowKeyPut(workflowKey, data).then(
    (response) => response.data as AgentWorkflow,
  );
}

export function validateAgentWorkflow(data: AgentWorkflowInput) {
  return postWorkflowValidateApiV1AdminAutomationWorkflowsValidatePost(data).then(
    (response) => response.data as AgentWorkflowValidationResult,
  );
}

export function createAgentWorkflowRun(workflowKey: string, data: AgentWorkflowRunInput) {
  return postWorkflowRunApiV1AdminAutomationWorkflowsWorkflowKeyRunsPost(
    workflowKey,
    data as AgentWorkflowRunInputPayload,
  ).then((response) => response.data as AgentWorkflowRunResult);
}

export function testAgentWorkflowRun(workflowKey: string, data: AgentWorkflowRunInput) {
  return postWorkflowTestRunApiV1AdminAutomationWorkflowsWorkflowKeyTestRunsPost(
    workflowKey,
    data as AgentWorkflowRunInputPayload,
  ).then((response) => response.data as AgentWorkflowRunResult);
}

export async function deleteAgentWorkflow(workflowKey: string) {
  await deleteWorkflowApiV1AdminAutomationWorkflowsWorkflowKeyDelete(workflowKey);
}

export function getSurfaceDraft(workflowKey: string) {
  return getWorkflowSurfaceDraftApiV1AdminAutomationWorkflowsWorkflowKeySurfaceDraftGet(workflowKey).then(
    (response) => response.data as SurfaceDraft | null,
  );
}

export function sendSurfaceDraftMessage(workflowKey: string, message: string) {
  const payload: SurfaceDraftChatWritePayload = { message };
  return postWorkflowSurfaceDraftMessageApiV1AdminAutomationWorkflowsWorkflowKeySurfaceDraftMessagesPost(
    workflowKey,
    payload,
  ).then((response) => response.data as SurfaceDraft);
}

export function applySurfaceDraft(workflowKey: string) {
  return postWorkflowSurfaceDraftApplyApiV1AdminAutomationWorkflowsWorkflowKeySurfaceDraftApplyPost(
    workflowKey,
  ).then((response) => response.data as SurfaceDraftApplyResult);
}

export async function clearSurfaceDraft(workflowKey: string) {
  await deleteWorkflowSurfaceDraftApiV1AdminAutomationWorkflowsWorkflowKeySurfaceDraftDelete(workflowKey);
}

export interface DeriveAiSchemaResult {
  output_schema: Record<string, unknown>;
  source_nodes: string[];
  contract_context: {
    node_id: string;
    node_type: string;
    upstream_inputs: Array<{
      kind: string;
      slot: string;
      label: string;
      from_node_id: string;
      from_node_type: string;
      from_node_label: string;
      source: {
        node_label: string;
        node_type: string;
      };
      from_port: {
        id: string;
        label: string;
      };
      provided_fields: string[];
      usage_note: string;
      source_summary: string;
      slot_note: string;
      note: {
        title: string;
        summary: string;
        operator_note: string;
      };
    }>;
    downstream_consumers: Array<{
      target_node_id: string;
      target_node_type: string;
      target_node_label: string;
      target: {
        node_label: string;
        node_type: string;
      };
      target_port: {
        id: string;
        label: string;
      };
      required_fields: string[];
      usage_note: string;
      requirement_note: string;
      surface_key: string;
      surface_label: string;
      surface_description: string;
      surface_hints: string[];
      format_requirements: string;
      note: {
        title: string;
        summary: string;
        requirement: string;
        tips: string[];
      };
    }>;
    mounted_tools: Array<{
      key: string;
      label: string;
      description: string;
      domain: string;
      sensitivity: string;
      parameters_schema: Record<string, unknown>;
      allowed_arguments: string[];
      fixed_arguments: Record<string, unknown>;
      auto_bound_arguments: string[];
      usage_notes: Record<string, string[]>;
      note: {
        title: string;
        summary: string;
        tips: string[];
      };
    }>;
    mounted_actions: Array<{
      key: string;
      label: string;
      description: string;
      domain: string;
      risk_level: string;
      parameters_schema: Record<string, unknown>;
      allowed_arguments: string[];
      fixed_arguments: Record<string, unknown>;
      auto_bound_arguments: string[];
      usage_notes: Record<string, string[]>;
      note: {
        title: string;
        summary: string;
        tips: string[];
      };
    }>;
    tool_usage_policy: {
      mode: string;
      minimum_tool_calls: number;
    };
    output_contract: {
      summary: string;
      field_keys: string[];
    };
  };
}

export function deriveAiOutputSchema(body: {
  graph: AgentWorkflowGraph;
  ai_node_id: string;
  workflow_key?: string | null;
}) {
  return postDeriveAiSchemaApiV1AdminAutomationWorkflowsDeriveAiSchemaPost(
    body as DeriveAiSchemaRequestPayload,
  ).then((response) => response.data as DeriveAiSchemaResult);
}

export interface WebhookTestResult {
  ok: boolean;
  provider: string;
  target_url: string;
  status_code: number | null;
  summary: string;
  response_body?: string | null;
}

export type TelegramWebhookConnectResult = TelegramWebhookConnectRead;

export function testWebhookSubscription(
  data: WebhookSubscriptionCreate,
  options?: { subscriptionId?: string | null },
): Promise<WebhookTestResult> {
  const params: PostWebhookTestApiV1AdminAutomationWebhooksTestPostParams | undefined =
    options?.subscriptionId ? { subscription_id: options.subscriptionId } : undefined;

  return postWebhookTestApiV1AdminAutomationWebhooksTestPost(data, params).then(
    (response) => response.data as WebhookTestResult,
  );
}

export function connectTelegramWebhook(
  botToken: string,
  sendTestMessage = true,
): Promise<TelegramWebhookConnectResult> {
  const payload: TelegramWebhookConnectWrite = {
    bot_token: botToken,
    send_test_message: sendTestMessage,
  };

  return postWebhookTelegramConnectApiV1AdminAutomationWebhooksTelegramConnectPost(payload).then(
    (response) => response.data as TelegramWebhookConnectResult,
  );
}
