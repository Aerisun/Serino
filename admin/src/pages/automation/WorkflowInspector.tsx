import { useCallback, useMemo } from "react";
import type {
  AgentWorkflow,
  AgentWorkflowCatalog,
  AgentWorkflowCatalogNodeType,
  AgentWorkflowCatalogOperation,
  AgentWorkflowRuntimePolicy,
  DeriveAiSchemaResult,
} from "@/pages/automation/api";
import type { WebhookDeliveryRead, WebhookSubscriptionRead } from "@serino/api-client/models";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/Select";
import { Textarea } from "@/components/ui/Textarea";
import type { Lang } from "@/i18n";
import { cn } from "@/lib/utils";
import { ChevronRight } from "lucide-react";
import {
  AI_TASK_INPUT_PORT_IDS,
  AI_TASK_OUTPUT_PORT_IDS,
  type WorkflowCanvasNode,
  type WorkflowCanvasEdge,
  type CopyShape,
  type InputContractField,
  type UpstreamPortOption,
  PRIMARY_FIELDS_BY_NODE_TYPE,
  ALWAYS_ADVANCED_FIELDS,
  HIDDEN_FIELDS_BY_NODE_TYPE,
  friendlyNodeTypeLabel,
  friendlyOperationLabel,
  friendlyFieldLabel,
  friendlyFieldExplanation,
  normalizedSchemaType,
  jsonInputValue,
  jsonFieldKey,
  schemaProperties,
  schemaPaths as _schemaPaths,
  fieldProperties,
  nodeMappings,
  suggestedMappingPath,
  autoMappingHint,
  syncTriggerConfigForEvent,
  isDataEdge,
  isRouteEdge,
  isToolEdge,
  getAiTaskShellConfig,
  getInputContract as _getInputContract,
  getOutputContract as _getOutputContract,
} from "./workflow-editor-types";
import {
  describeAiDownstreamRequirement,
  describeAiDownstreamUsage,
  describeAiInputSource,
} from "./workflow-ai-io-copy";

function toolSurfaceDomainLabel(domain: string, lang: Lang) {
  const normalized = (domain || "").trim();
  const zh: Record<string, string> = {
    content: "内容",
    site: "站点",
    moderation: "审核",
    visitors: "访客",
    subscription: "订阅",
    assets: "资源",
    social: "友链",
    system: "系统",
    automation: "自动化",
    auth: "认证",
    network: "网络",
    resume: "简历",
    workflow: "工作流",
    misc: "其他",
  };
  const en: Record<string, string> = {
    content: "Content",
    site: "Site",
    moderation: "Moderation",
    visitors: "Visitors",
    subscription: "Subscription",
    assets: "Assets",
    social: "Social",
    system: "System",
    automation: "Automation",
    auth: "Auth",
    network: "Network",
    resume: "Resume",
    workflow: "Workflow",
    misc: "Misc",
  };
  return (lang === "zh" ? zh : en)[normalized] || normalized || (lang === "zh" ? "其他" : "Misc");
}

function toolSurfaceSensitivityLabel(sensitivity: string | undefined, lang: Lang) {
  switch ((sensitivity || "").trim()) {
    case "operational":
      return lang === "zh" ? "运维" : "Operational";
    case "sensitive":
      return lang === "zh" ? "敏感" : "Sensitive";
    case "secret":
      return lang === "zh" ? "机密" : "Secret";
    default:
      return lang === "zh" ? "业务" : "Business";
  }
}

function ApprovalReviewInspector({
  lang,
}: {
  lang: Lang;
}) {
  return (
    <div className="space-y-4">
      <div className="rounded-[18px] border border-border/60 bg-background/70 px-3 py-3 text-sm leading-6 text-foreground">
        {lang === "zh"
          ? "连接在它后面的执行节点，都会在执行前先进入审核列表等待人工处理。"
          : "Execution nodes connected after this gate will wait for manual approval before running."}
      </div>
    </div>
  );
}
import { AiTaskInspector } from "./workflow-inspector/AiTaskInspector";
import { CatalogCardPicker } from "./workflow-inspector/CatalogCardPicker";
import { GenericSchemaInspector } from "./workflow-inspector/GenericSchemaInspector";
import { TriggerInspector } from "./workflow-inspector/TriggerInspector";

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

export interface WorkflowInspectorProps {
  mode?: "edit" | "sketch";
  show: boolean;
  onClose: () => void;
  copy: CopyShape;
  lang: Lang;
  catalog: AgentWorkflowCatalog | undefined;
  workflow: AgentWorkflow;
  // Workflow-level state
  workflowName: string;
  workflowDescription: string;
  workflowEnabled: boolean;
  runtimePolicy: AgentWorkflowRuntimePolicy;
  onWorkflowNameChange: (value: string) => void;
  onWorkflowDescriptionChange: (value: string) => void;
  onWorkflowEnabledChange: (value: boolean) => void;
  onRuntimePolicyChange: (value: AgentWorkflowRuntimePolicy) => void;
  // Selection state
  selectedNode: WorkflowCanvasNode | null;
  selectedEdge: WorkflowCanvasEdge | null;
  selectedNodeDefinition: AgentWorkflowCatalogNodeType | undefined;
  selectedOperation: AgentWorkflowCatalogOperation | null;
  selectedOperationExamples: unknown[];
  selectedSourceNodeDefinition: AgentWorkflowCatalogNodeType | null;
  // Node editing
  setNodeLabel: (value: string) => void;
  setNodeConfig: (key: string, value: unknown) => void;
  updateSelectedNode: (updater: (node: WorkflowCanvasNode) => WorkflowCanvasNode) => void;
  deleteSelectedNode: () => void;
  // Edge editing
  setEdges: React.Dispatch<React.SetStateAction<WorkflowCanvasEdge[]>>;
  deleteSelectedEdge: () => void;
  // JSON editing state
  jsonDrafts: Record<string, string>;
  jsonErrors: Record<string, string>;
  setJsonDrafts: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  setJsonErrors: React.Dispatch<React.SetStateAction<Record<string, string>>>;
  // Catalog-driven data
  operationCatalog: AgentWorkflowCatalogOperation[];
  triggerEventOptions: { value: string; label: string; description?: string; target_types?: string[] }[];
  webhooks: WebhookSubscriptionRead[];
  latestDeliveryMap: Map<string, WebhookDeliveryRead>;
  // Three-contract helpers for ai.task
  upstreamNodes: WorkflowCanvasNode[];
  mountedToolNodes: WorkflowCanvasNode[];
  updateInputField: (index: number, fieldKey: string, value: unknown) => void;
  updateInputFieldSelector: (index: number, selectorKey: string, value: unknown) => void;
  removeInputField: (index: number) => void;
  addInputField: () => void;
  outputSchemaFields: [string, Record<string, unknown>][];
  renameOutputField: (index: number, newName: string) => void;
  updateOutputFieldType: (index: number, type: string) => void;
  removeOutputField: (index: number) => void;
  addOutputField: () => void;
  setRouteField: (field: string) => void;
  setRouteEnumFromEdges: (val: boolean) => void;
  setRouteEnum: (values: string[]) => void;
  // Input mapping helpers for expression mode
  updateInputMapping: (index: number, field: "field_name" | "expression", value: string) => void;
  addInputMapping: () => void;
  removeInputMapping: (index: number) => void;
  // Derived schema
  derivedSchema: DeriveAiSchemaResult | null;
  derivingSchema: boolean;
  // Nodes / edges (for edge inspector source-node lookup - already done via selectedSourceNodeDefinition)
  nodes: WorkflowCanvasNode[];
  edges: WorkflowCanvasEdge[];
  onOpenSurfaceAssistant: () => void;
}

// ---------------------------------------------------------------------------
// WorkflowInspector component
// ---------------------------------------------------------------------------

export function WorkflowInspector(props: WorkflowInspectorProps) {
  const {
    mode = "edit",
    show,
    onClose,
    copy,
    lang,
    catalog,
    workflow,
    workflowName,
    workflowDescription,
    workflowEnabled,
    runtimePolicy: _runtimePolicy,
    onWorkflowNameChange,
    onWorkflowDescriptionChange,
    onWorkflowEnabledChange,
    onRuntimePolicyChange: _onRuntimePolicyChange,
    selectedNode,
    selectedEdge,
    selectedNodeDefinition,
    selectedOperation,
    selectedOperationExamples: _selectedOperationExamples,
    selectedSourceNodeDefinition,
    setNodeLabel,
    setNodeConfig,
    updateSelectedNode,
    setEdges,
    jsonDrafts,
    jsonErrors,
    setJsonDrafts,
    setJsonErrors,
    operationCatalog,
    triggerEventOptions,
    webhooks,
    latestDeliveryMap,
    upstreamNodes,
    mountedToolNodes,
    updateInputField: _updateInputField,
    updateInputFieldSelector: _updateInputFieldSelector,
    removeInputField: _removeInputField,
    addInputField: _addInputField,
    outputSchemaFields: _outputSchemaFields,
    renameOutputField: _renameOutputField,
    updateOutputFieldType: _updateOutputFieldType,
    removeOutputField: _removeOutputField,
    addOutputField: _addOutputField,
    setRouteField: _setRouteField,
    setRouteEnumFromEdges: _setRouteEnumFromEdges,
    setRouteEnum: _setRouteEnum,
    derivedSchema,
    derivingSchema,
    nodes,
    edges,
    onOpenSurfaceAssistant,
  } = props;
  const isSketchMode = mode === "sketch";
  const triggerTypeOptions = useMemo(
    () =>
      [
        "trigger.event",
        "trigger.webhook",
        "trigger.schedule",
        "trigger.manual",
      ]
        .map((type) => catalog?.node_types?.find((item) => item.type === type))
        .filter((item): item is AgentWorkflowCatalogNodeType => Boolean(item)),
    [catalog?.node_types],
  );

  // ---- renderJsonField helper ----
  const renderJsonField = useCallback(
    (nodeId: string, fieldName: string, value: unknown) => {
      const key = jsonFieldKey(nodeId, fieldName);
      const textValue = jsonDrafts[key] ?? jsonInputValue(value);
      return (
        <div className="space-y-2">
          <Textarea
            rows={8}
            value={textValue}
            onChange={(event) => {
              const nextValue = event.target.value;
              setJsonDrafts((current) => ({ ...current, [key]: nextValue }));
              try {
                const parsed = JSON.parse(nextValue) as unknown;
                setNodeConfig(fieldName, parsed);
                setJsonErrors((current) => {
                  const next = { ...current };
                  delete next[key];
                  return next;
                });
              } catch (error) {
                setJsonErrors((current) => ({
                  ...current,
                  [key]: error instanceof Error ? error.message : copy.jsonInvalid,
                }));
              }
            }}
          />
          {jsonErrors[key] ? <div className="text-xs text-rose-500">{copy.jsonInvalid}</div> : null}
        </div>
      );
    },
    [copy.jsonInvalid, jsonDrafts, jsonErrors, setNodeConfig, setJsonDrafts, setJsonErrors],
  );

  const readonlyToolSurfaces = useMemo(
    () =>
      (catalog?.readonly_tools ?? [])
        .filter((surface) => surface.kind === "query")
        .slice()
        .sort((a, b) => {
          const domainCompare = String(a.domain || "misc").localeCompare(String(b.domain || "misc"));
          if (domainCompare !== 0) return domainCompare;
          return a.label.localeCompare(b.label);
        }),
    [catalog?.readonly_tools],
  );
  const readonlyToolSurfaceGroups = useMemo(() => {
    const groups = new Map<string, typeof readonlyToolSurfaces>();
    for (const surface of readonlyToolSurfaces) {
      const domain = String(surface.domain || "misc").trim() || "misc";
      const list = groups.get(domain) || [];
      list.push(surface);
      groups.set(domain, list);
    }
    return Array.from(groups.entries()).map(([domain, items]) => ({ domain, items }));
  }, [readonlyToolSurfaces]);
  const actionSurfaces = useMemo(
    () =>
      (catalog?.workflow_local_action_surfaces ?? []).filter(
        (surface) => surface.kind === "action",
      ),
    [catalog?.workflow_local_action_surfaces],
  );
  const mountedToolSurfaces = useMemo(
    () =>
      mountedToolNodes
        .flatMap((node) => {
          const surfaceKeys = Array.isArray(node.data.config.surface_keys)
            ? node.data.config.surface_keys
                .filter((item): item is string => typeof item === "string")
                .map((item) => item.trim())
                .filter(Boolean)
            : String(node.data.config.surface_key || "").trim()
              ? [String(node.data.config.surface_key || "").trim()]
              : [];
          return surfaceKeys.map((surfaceKey) => ({
            node,
            surfaceKey,
            surface: readonlyToolSurfaces.find((item) => item.key === surfaceKey),
          }));
        })
        .filter((item) => item.node.data.nodeType === "tool.query"),
    [mountedToolNodes, readonlyToolSurfaces],
  );
  const mountedCapabilityItems = useMemo(() => {
    if (!selectedNode || selectedNode.data.nodeType !== "ai.task") return [];

    const mountedActions = edges.flatMap((edge) => {
      if (edge.target !== selectedNode.id) return [];
      const sourceNode = nodes.find((node) => node.id === edge.source);
      if (!sourceNode || sourceNode.data.nodeType !== "apply.action") return [];

      const surfaceKey = String(sourceNode.data.config.surface_key || "").trim();
      if (!surfaceKey) return [];

      const surface = actionSurfaces.find((item) => item.key === surfaceKey);
      if (!surface) {
        return [
          {
            key: `action:${surfaceKey}`,
            label: surfaceKey,
            kindLabel: lang === "zh" ? "执行动作" : "Action",
          },
        ];
      }

      if (surface.surface_mode === "bundle" && Array.isArray(surface.entries) && surface.entries.length > 0) {
        return surface.entries.map((entry) => ({
          key: `action:${surface.key}#${entry.key}`,
          label: entry.label || surface.label,
          kindLabel: lang === "zh" ? "执行动作" : "Action",
        }));
      }

      return [
        {
          key: `action:${surface.key}`,
          label: surface.label,
          kindLabel: lang === "zh" ? "执行动作" : "Action",
        },
      ];
    });

    return Array.from(
      new Map(
        [
          ...mountedToolSurfaces.map((item) => ({
            key: `tool:${item.surface?.key || item.surfaceKey}`,
            label: item.surface?.label || item.surfaceKey,
            kindLabel: lang === "zh" ? "只读工具" : "Readonly Tool",
          })),
          ...mountedActions,
        ].map((item) => [item.key, item]),
      ).values(),
    );
  }, [actionSurfaces, edges, lang, mountedToolSurfaces, nodes, selectedNode]);
  const upstreamPortOptions = useMemo<UpstreamPortOption[]>(() => {
    if (!selectedNode) return [];
    return edges
      .filter((edge) => isDataEdge(edge, nodes) && edge.target === selectedNode.id)
      .map((edge) => {
        const sourceNode = nodes.find((node) => node.id === edge.source);
        if (!sourceNode) return null;
        const sourceDef = catalog?.node_types?.find((item) => item.type === sourceNode.data.nodeType);
        const portId = edge.sourceHandle || sourceDef?.output_ports?.[0]?.id || "result";
        const portDef = sourceDef?.output_ports?.find((port) => port.id === portId);
        return {
          node_id: sourceNode.id,
          node_label: sourceNode.data.label,
          node_type: sourceNode.data.nodeType,
          port_id: portId,
          port_label: portDef?.label || portId,
          data_schema: (portDef?.data_schema as Record<string, unknown> | null | undefined) ?? null,
        };
      })
      .filter((item): item is UpstreamPortOption => item !== null);
  }, [catalog?.node_types, edges, nodes, selectedNode]);

  const downstreamPortOptions = useMemo<UpstreamPortOption[]>(() => {
    if (!selectedNode) return [];
    return edges
      .filter((edge) => isDataEdge(edge, nodes) && edge.source === selectedNode.id)
      .map((edge) => {
        const targetNode = nodes.find((node) => node.id === edge.target);
        if (!targetNode) return null;
        const targetDef = catalog?.node_types?.find((item) => item.type === targetNode.data.nodeType);
        const portId = edge.targetHandle || targetDef?.input_ports?.[0]?.id || "in";
        const portDef = targetDef?.input_ports?.find((port) => port.id === portId);
        let effectiveSchema = (portDef?.data_schema as Record<string, unknown> | null | undefined) ?? null;
        if (!effectiveSchema && targetNode.data.nodeType.startsWith("operation.")) {
          const opType = targetNode.data.nodeType.split(".", 2)[1];
          const opKey = String(targetNode.data.config.operation_key || "");
          const op = operationCatalog.find((item) => item.operation_type === opType && item.key === opKey);
          effectiveSchema = (op?.input_schema as Record<string, unknown> | undefined) ?? null;
        }
        if (!effectiveSchema && targetNode.data.nodeType === "apply.action") {
          const actionSurface = actionSurfaces.find((item) => item.key === String(targetNode.data.config.surface_key || ""));
          effectiveSchema = (actionSurface?.input_schema as Record<string, unknown> | undefined) ?? null;
        }
        const defaultExplanation =
          targetNode.data.nodeType === "ai.task"
            ? lang === "zh"
              ? "下一个 AI 会把这份结构化输出当作输入背景继续处理。"
              : "The next AI task will use this structured output as background input."
            : targetNode.data.nodeType === "notification.webhook"
              ? lang === "zh"
                ? "Webhook 通知会拿这份结构化输出去套用自己的发送模板。"
                : "Webhook notification will apply its own delivery template to this structured output."
              : targetNode.data.nodeType === "apply.action"
                ? lang === "zh"
                  ? "执行动作会从这份结构化输出里取值，然后调用平台能力完成处理。"
                  : "Apply action will read values from this structured output and execute the platform action."
                : targetNode.data.nodeType === "approval.review"
                  ? lang === "zh"
                    ? "人工审批会把这份结构化输出作为审核内容，等待人工决定是否继续。"
                    : "Human approval will use this structured output as review content before continuing."
                  : targetNode.data.nodeType === "flow.condition"
                      ? lang === "zh"
                        ? "条件分支会读取这份结构化输出，再决定接下来走哪条路径。"
                        : "Condition branch will read this structured output to decide which path to follow."
                      : targetNode.data.nodeType === "flow.delay"
                          ? lang === "zh"
                            ? "延时等待会带着这份结构化输出稍后继续执行。"
                            : "Delay will carry this structured output forward after waiting."
                          : targetNode.data.nodeType === "flow.wait_for_event"
                            ? lang === "zh"
                              ? "等待事件会保留这份结构化输出，直到满足继续条件。"
                              : "Wait-for-event will retain this structured output until the continuation condition is met."
                            : targetNode.data.nodeType === "flow.poll"
                              ? lang === "zh"
                                ? "轮询检测会结合这份结构化输出持续检查状态。"
                                : "Polling will use this structured output while checking status over time."
                              : lang === "zh"
                                ? "下游节点会读取这份结构化输出继续处理。"
                                : "The downstream node will read this structured output and continue processing.";
        const explanation =
          targetNode.data.nodeType === "ai.task"
            ? defaultExplanation
            : targetNode.data.nodeType === "notification.webhook"
              ? defaultExplanation
              : targetNode.data.nodeType === "apply.action"
                ? actionSurfaces.find((item) => item.key === String(targetNode.data.config.surface_key || ""))?.description ||
                  defaultExplanation
                : defaultExplanation;
        return {
          node_id: targetNode.id,
          node_label: targetNode.data.label,
          node_type: targetNode.data.nodeType,
          port_id: portId,
          port_label: portDef?.label || portId,
          data_schema: effectiveSchema,
          explanation,
          source_port_id: edge.sourceHandle || "",
          source_port_label:
            catalog?.node_types
              ?.find((item) => item.type === selectedNode.data.nodeType)
              ?.output_ports?.find((port) => port.id === (edge.sourceHandle || ""))?.label ||
            edge.sourceHandle ||
            "",
        };
      })
      .filter((item): item is UpstreamPortOption => item !== null);
  }, [actionSurfaces, catalog?.node_types, edges, lang, nodes, operationCatalog, selectedNode]);

  const _upstreamNodeOptions = useMemo(
    () =>
      upstreamNodes.map((node) => ({
        id: node.id,
        label: node.data.label,
      })),
    [upstreamNodes],
  );
  const hasTriggerUpstream = useMemo(
    () => upstreamNodes.some((node) => node.data.nodeType.startsWith("trigger.")),
    [upstreamNodes],
  );
  const hasWebhookUpstream = useMemo(
    () => upstreamNodes.some((node) => node.data.nodeType === "trigger.webhook"),
    [upstreamNodes],
  );
  const _inputSourceCards = useMemo(
    () => [
      ...(hasTriggerUpstream
        ? [
            {
              key: "trigger",
              label: lang === "zh" ? "触发上下文" : "Trigger Context",
              description:
                lang === "zh"
                  ? "直接读取当前触发事件里的上下文，不需要再指定上游节点。"
                  : "Reads directly from the current trigger context.",
            },
          ]
        : []),
      ...(hasWebhookUpstream
        ? [
            {
              key: "webhook",
              label: "Webhook",
              description:
                lang === "zh"
                  ? "读取当前 Webhook 负载，适合 body / headers / query 这类路径。"
                  : "Reads from the current webhook payload such as body, headers, or query.",
            },
          ]
        : []),
      ...upstreamNodes.map((node) => {
        const portCount = upstreamPortOptions.filter((option) => option.node_id === node.id).length;
        return {
          key: node.id,
          label: node.data.label,
          description:
            lang === "zh"
              ? `${friendlyNodeTypeLabel(node.data.nodeType, catalog, lang)} · ${portCount} 个可选输出`
              : `${friendlyNodeTypeLabel(node.data.nodeType, catalog, lang)} · ${portCount} available outputs`,
        };
      }),
    ],
    [catalog, hasTriggerUpstream, hasWebhookUpstream, lang, upstreamNodes, upstreamPortOptions],
  );
  const _selectorSourceLabel = useCallback(
    (source: string) => {
      switch (source) {
        case "trigger":
          return lang === "zh" ? "触发器" : "Trigger";
        case "webhook":
          return "Webhook";
        case "node_output":
          return lang === "zh" ? "上游节点" : "Upstream Node";
        case "artifact":
          return lang === "zh" ? "中间值" : "Artifact";
        case "literal":
          return lang === "zh" ? "常量" : "Literal";
        default:
          return source || (lang === "zh" ? "未设置" : "Unset");
      }
    },
    [lang],
  );
  const _describeInputField = useCallback(
    (field: InputContractField) => {
      const selector = field.selector || { source: "" };
      const source = String(selector.source || "").trim();
      if (source === "node_output") {
        const option = upstreamPortOptions.find(
          (item) => item.node_id === (selector.node_id ?? "") && item.port_id === (selector.port ?? ""),
        );
        const nodeLabel =
          upstreamNodes.find((node) => node.id === (selector.node_id ?? ""))?.data.label ||
          (lang === "zh" ? "未选择上游节点" : "No upstream node selected");
        const portLabel = option?.port_label || selector.port || (lang === "zh" ? "未选择端口" : "No port selected");
        const pathLabel = selector.path || (lang === "zh" ? "未选择字段路径" : "No field path selected");
        return `${nodeLabel} · ${portLabel} · ${pathLabel}`;
      }
      if (source === "trigger") {
        return `${lang === "zh" ? "当前触发上下文" : "Current trigger context"} · ${selector.path || (lang === "zh" ? "整份上下文" : "Full context")}`;
      }
      if (source === "webhook") {
        return `Webhook · ${selector.path || (lang === "zh" ? "整份请求负载" : "Full payload")}`;
      }
      if (source === "artifact") {
        return `${lang === "zh" ? "中间值" : "Artifact"} · ${selector.path || (lang === "zh" ? "未选择路径" : "No path selected")}`;
      }
      if (source === "literal") {
        return `${lang === "zh" ? "固定值" : "Literal"} · ${String(selector.value ?? "") || (lang === "zh" ? "空值" : "Empty")}`;
      }
      return lang === "zh" ? "尚未完成映射配置" : "Mapping is not configured yet.";
    },
    [lang, upstreamNodes, upstreamPortOptions],
  );

  const _recommendedOutputFields = useMemo(() => {
    const fieldMap = new Map<string, Record<string, unknown>>();
    for (const option of downstreamPortOptions) {
      const properties = schemaProperties(option.data_schema || {});
      for (const [fieldName, fieldSchema] of properties) {
        if (!fieldMap.has(fieldName)) {
          fieldMap.set(fieldName, fieldSchema);
        }
      }
    }
    return Array.from(fieldMap.entries());
  }, [downstreamPortOptions]);

  const _outgoingRouteValues = useMemo(() => {
    if (!selectedNode) return [];
    return edges
      .filter((edge) => !isToolEdge(edge, nodes) && edge.source === selectedNode.id && isRouteEdge(edge))
      .map((edge) => {
        const config = (edge.data?.config as Record<string, unknown> | undefined) || {};
        return String(config.match || edge.label || edge.sourceHandle || "").trim();
      })
      .filter((value, index, all) => value && all.indexOf(value) === index);
  }, [edges, nodes, selectedNode]);
  const _hasOutputBindings = downstreamPortOptions.length > 0;

  const derivedOutputFields = useMemo(
    () => schemaProperties(derivedSchema?.output_schema || {}),
    [derivedSchema],
  );
  const derivedOutputSummary = useMemo(() => {
    if (derivedOutputFields.length === 0) {
      return lang === "zh"
        ? "一份供下游继续使用的结构化结果"
        : "a structured result for downstream use";
    }
    return derivedOutputFields
      .map(([fieldName, fieldSchema]) => friendlyFieldLabel(fieldName, lang, fieldSchema))
      .join(lang === "zh" ? "、" : ", ");
  }, [derivedOutputFields, lang]);
  const _describeDownstreamUsage = useCallback(
    (option: UpstreamPortOption | null) =>
      describeAiDownstreamUsage({ option, lang }),
    [lang],
  );
  const _describeDownstreamRequirement = useCallback(
    (option: UpstreamPortOption | null) =>
      describeAiDownstreamRequirement({ option, lang }),
    [lang],
  );
  const _aiOutputBindings = useMemo(
    () =>
      AI_TASK_OUTPUT_PORT_IDS.map((portId) => {
        const bindings = downstreamPortOptions.filter((item) => item.source_port_id === portId);
        return {
          portId,
          portLabel: bindings[0]?.source_port_label || (lang === "zh" ? `输出口 ${portId.split("_")[1]}` : `Output ${portId.split("_")[1]}`),
          bindings,
        };
      }).filter((item) => item.bindings.length > 0),
    [downstreamPortOptions, lang],
  );

  const _hasApprovalUpstream = useMemo(() => {
    if (!selectedNode) return false;
    return edges.some((edge) => {
      if (!isDataEdge(edge, nodes) || edge.target !== selectedNode.id) return false;
      const sourceNode = nodes.find((node) => node.id === edge.source);
      return sourceNode?.data.nodeType === "approval.review";
    });
  }, [edges, nodes, selectedNode]);
  const selectedEdgeIsTool = useMemo(
    () => (selectedEdge ? isToolEdge(selectedEdge, nodes) : false),
    [nodes, selectedEdge],
  );
  const aiShellConfig = useMemo(
    () => (selectedNode?.data.nodeType === "ai.task" ? getAiTaskShellConfig(selectedNode.data.config) : null),
    [selectedNode],
  );
  const aiInputSlotBindings = useMemo(() => {
    if (!selectedNode || selectedNode.data.nodeType !== "ai.task") return [];
    return AI_TASK_INPUT_PORT_IDS.map((portId) => {
      const edge = edges.find((item) => isDataEdge(item, nodes) && item.target === selectedNode.id && item.targetHandle === portId) || null;
      const sourceNode = edge ? nodes.find((node) => node.id === edge.source) || null : null;
      const sourceDefinition = sourceNode ? catalog?.node_types?.find((item) => item.type === sourceNode.data.nodeType) : null;
      const sourcePortId = edge?.sourceHandle || sourceDefinition?.output_ports?.[0]?.id || "out";
      const sourcePort = sourceDefinition?.output_ports?.find((port) => port.id === sourcePortId);
      const { humanDescription, inputSummary } = describeAiInputSource({
        lang,
        sourceNodeType: sourceNode?.data.nodeType || "",
        sourceNodeLabel: sourceNode?.data.label,
        sourceSummary: "",
        sourceSchema:
          (sourcePort?.data_schema as Record<string, unknown> | null | undefined) || null,
        catalog,
      });
      return {
        portId,
        edge,
        sourceNode,
        sourcePort,
        note: aiShellConfig?.input_slots?.[portId]?.note ?? "",
        humanDescription,
        inputSummary,
      };
    });
  }, [aiShellConfig, catalog, edges, lang, nodes, selectedNode]);
  const _connectedAiInputSlotBindings = useMemo(
    () => aiInputSlotBindings.filter((slot) => Boolean(slot.edge)),
    [aiInputSlotBindings],
  );
  const triggerMountSource = useMemo(() => {
    if (!selectedNode || selectedNode.data.nodeType !== "ai.task") return null;
    const edge = edges.find((item) => item.target === selectedNode.id && item.targetHandle === "mount_trigger") || null;
    return edge ? nodes.find((node) => node.id === edge.source) || null : null;
  }, [edges, nodes, selectedNode]);
  const approvalMountSource = useMemo(() => {
    if (!selectedNode || selectedNode.data.nodeType !== "ai.task") return null;
    const edge = edges.find((item) => item.target === selectedNode.id && item.targetHandle === "mount_approval") || null;
    return edge ? nodes.find((node) => node.id === edge.source) || null : null;
  }, [edges, nodes, selectedNode]);
  const _hasExtraMounts = Boolean(
    triggerMountSource || approvalMountSource || mountedToolSurfaces.length > 0,
  );

  // ---- renderSchemaField helper ----
  const renderSchemaField = useCallback(
    (fieldName: string, schema: Record<string, unknown>) => {
      if (!selectedNode || !selectedNodeDefinition) return null;
      const currentValue = selectedNode.data.config[fieldName];
      const fieldType = normalizedSchemaType(schema);
      const description = friendlyFieldExplanation(fieldName, lang, schema);

      let control: JSX.Element;

      if (selectedNode.data.nodeType === "trigger.event" && fieldName === "event_type") {
        control = (
          <div className="grid gap-2">
            {triggerEventOptions.map((item) => {
              const active = String(currentValue || "") === item.value;
              return (
                <div
                  key={item.value}
                  className={cn(
                    "rounded-[18px] border px-3 py-3 transition-colors",
                    active
                      ? "border-sky-400/60 bg-sky-500/10"
                      : "border-border/60 bg-background/70 hover:bg-background/85",
                  )}
                >
                  <div className="flex items-center gap-3">
                    <button
                      type="button"
                      onClick={() =>
                        updateSelectedNode((node) => ({
                          ...node,
                          data: {
                            ...node.data,
                            config: syncTriggerConfigForEvent(node.data.config, item),
                          },
                        }))
                      }
                      className="flex-1 text-left"
                    >
                      <div className="text-sm font-medium text-foreground">{item.label}</div>
                    </button>
                    {item.description ? (
                      <LabelWithHelp
                        hideLabel
                        label=""
                        title={item.label}
                        description={item.description}
                      />
                    ) : null}
                    {active ? <Badge variant="outline">当前使用</Badge> : null}
                  </div>
                </div>
              );
            })}
          </div>
        );
      } else if (selectedNode.data.nodeType === "tool.query" && fieldName === "surface_keys") {
        const selectedKeys = Array.isArray(currentValue)
          ? currentValue.filter((item): item is string => typeof item === "string")
          : String(selectedNode.data.config.surface_key || "").trim()
            ? [String(selectedNode.data.config.surface_key || "").trim()]
            : [];
        const _selectedSurfaceItems = readonlyToolSurfaces.filter((surface) =>
          selectedKeys.includes(surface.key),
        );
        const groups = readonlyToolSurfaceGroups.map((group) => ({
          key: group.domain,
          label: toolSurfaceDomainLabel(group.domain, lang),
          items: group.items.map((surface) => ({
            key: surface.key,
            label: surface.label,
            description: surface.description,
            meta: toolSurfaceSensitivityLabel(surface.sensitivity, lang),
          })),
        }));
        control = (
          <CatalogCardPicker
            mode="multiple"
            groups={groups}
            selectedKeys={selectedKeys}
            onChange={(nextKeys) => setNodeConfig(fieldName, nextKeys)}
            currentTitle={lang === "zh" ? "当前选择" : "Current Selection"}
            currentEmptyText={
              lang === "zh"
                ? "当前还没有选中任何只读观察工具。"
                : "No readonly observation tools are selected yet."
            }
            groupSelectedSuffix={lang === "zh" ? " 已选" : " selected"}
            selectedSummaryTitle={lang === "zh" ? "已选功能" : "Selected Tools"}
          />
        );
      } else if (selectedNode.data.nodeType === "apply.action" && fieldName === "surface_key") {
        control = (
          <div className="space-y-2">
            <Select value={String(currentValue || "")} onValueChange={(value) => setNodeConfig(fieldName, value)}>
              <SelectTrigger>
                <SelectValue placeholder={lang === "zh" ? "选择动作 surface" : "Select action surface"} />
              </SelectTrigger>
              <SelectContent>
                {actionSurfaces.map((surface) => (
                  <SelectItem key={surface.key} value={surface.key}>
                    {surface.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {String(currentValue || "").trim() ? (
              <div className="rounded-[14px] border border-border/60 bg-background/70 px-3 py-2 text-xs leading-5 text-muted-foreground">
                {actionSurfaces.find((surface) => surface.key === String(currentValue || "").trim())?.description ||
                  (lang === "zh" ? "未找到该动作 surface 的说明。" : "Description unavailable for this action surface.")}
              </div>
            ) : null}
            <Button
              type="button"
              variant="outline"
              size="sm"
              onClick={onOpenSurfaceAssistant}
              className="w-full justify-center"
            >
              {lang === "zh" ? "AI 管理 Surface" : "AI Surface Assistant"}
            </Button>
          </div>
        );
      } else if (
        selectedNode.data.nodeType.startsWith("operation.") &&
        fieldName === "argument_mappings" &&
        selectedOperation
      ) {
        const params = schemaProperties(selectedOperation.input_schema);
        const requiredFields = new Set((selectedOperation.input_schema.required as string[] | undefined) || []);
        const mappings = nodeMappings(selectedNode.data.config, "argument_mappings");
        const targetType = workflow?.target_type;
        control = (
          <div className="space-y-3">
            {params.map(([paramName, paramSchema]) => {
              const currentMapping = mappings.find((item) => String(item.name || "") === paramName);
              const currentSource = String(currentMapping?.source || "__auto__");
              const suggestedPath = suggestedMappingPath(paramName, currentSource, targetType, selectedOperation);
              return (
                <div key={paramName} className="rounded-[18px] border border-border/60 bg-background/70 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="text-sm font-medium text-foreground">
                        {friendlyFieldLabel(paramName, lang, paramSchema)}
                        {requiredFields.has(paramName) ? <span className="ml-1 text-rose-500">*</span> : null}
                      </div>
                      {paramSchema.description ? (
                        <div className="mt-1 text-xs leading-5 text-muted-foreground">
                          {String(paramSchema.description)}
                        </div>
                      ) : null}
                    </div>
                    <Badge variant="outline">{normalizedSchemaType(paramSchema)}</Badge>
                  </div>

                  <div className="mt-3 grid gap-3">
                    <div className="space-y-2">
                      <LabelWithHelp
                        label={copy.mappingSource}
                        description={lang === "zh" ? "决定这个参数的值从哪里来。" : "Choose where this parameter value should come from."}
                      />
                      <Select
                        value={currentSource}
                        onValueChange={(value) => {
                          const rest = mappings.filter((item) => String(item.name || "") !== paramName);
                          if (value === "__auto__") {
                            setNodeConfig(fieldName, rest);
                            return;
                          }
                          setNodeConfig(fieldName, [
                            ...rest,
                            {
                              name: paramName,
                              source: value,
                              ...(value === "literal"
                                ? { value: currentMapping?.value ?? "" }
                                : { path: String(currentMapping?.path || "") }),
                            },
                          ]);
                        }}
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          {(catalog?.variable_sources ?? []).map((vs) => (
                            <SelectItem key={vs.key} value={vs.key}>
                              {vs.label}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>

                    {currentSource === "literal" ? (
                      <div className="space-y-2">
                        <LabelWithHelp
                          label={copy.mappingLiteral}
                          description={lang === "zh" ? "直接写一个固定值。" : "Provide a fixed value."}
                        />
                        <Input
                          value={String(currentMapping?.value ?? "")}
                          onChange={(event) => {
                            const rest = mappings.filter((item) => String(item.name || "") !== paramName);
                            setNodeConfig(fieldName, [
                              ...rest,
                              { name: paramName, source: "literal", value: event.target.value },
                            ]);
                          }}
                        />
                      </div>
                    ) : currentSource !== "__auto__" ? (
                      <div className="space-y-2">
                        <LabelWithHelp
                          label={copy.mappingPath}
                          description={lang === "zh" ? "比如 body_preview、summary、comment_id 这种路径。" : "For example body_preview, summary, or comment_id."}
                        />
                        <Input
                          value={String(currentMapping?.path ?? "")}
                          placeholder={suggestedPath || (lang === "zh" ? "例如 comment_id" : "For example comment_id")}
                          onChange={(event) => {
                            const rest = mappings.filter((item) => String(item.name || "") !== paramName);
                            setNodeConfig(fieldName, [
                              ...rest,
                              { name: paramName, source: currentSource, path: event.target.value },
                            ]);
                          }}
                        />
                      </div>
                    ) : (
                      <div className="rounded-[16px] border border-dashed border-border/60 bg-background/70 px-3 py-3 text-xs leading-5 text-muted-foreground">
                        {autoMappingHint(paramName, targetType, lang, selectedOperation)}
                      </div>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        );
      } else if (
        fieldName === "operation_key" &&
        selectedNode.data.nodeType.startsWith("operation.")
      ) {
        const operationType = selectedNode.data.nodeType.split(".", 2)[1];
        const options = operationCatalog.filter((item) => item.operation_type === operationType);
        const currentOperationKey = String(currentValue || "");
        const selectedOperationItem = options.find((item) => item.key === currentOperationKey) || null;
        const groupedOptions = options.reduce((groups, item) => {
          const groupKey = `${item.group_key}:${item.group_label}`;
          const current = groups.get(groupKey) || { label: item.group_label, items: [] as typeof options };
          current.items.push(item);
          groups.set(groupKey, current);
          return groups;
        }, new Map<string, { label: string; items: typeof options }>());
        control = (
          <CatalogCardPicker
            mode="single"
            groups={Array.from(groupedOptions.entries()).map(([groupKey, group]) => ({
              key: groupKey,
              label: group.label,
              items: group.items.map((item) => ({
                key: item.key,
                label: friendlyOperationLabel(item.key, catalog, lang),
                description: item.description,
              })),
            }))}
            selectedKeys={selectedOperationItem ? [selectedOperationItem.key] : []}
            onChange={(nextKeys) => setNodeConfig(fieldName, nextKeys[0] || "")}
            currentTitle={lang === "zh" ? "当前选择" : "Current Selection"}
            currentEmptyText={lang === "zh" ? "还没有选择平台能力。" : "No operation selected yet."}
          />
        );
      } else if (fieldName === "approval_type") {
        control = (
          <Select value={String(currentValue || "")} onValueChange={(value) => setNodeConfig(fieldName, value)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {(catalog?.approval_types || []).map((item) => (
                <SelectItem key={item.key} value={item.key}>
                  {item.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      } else if (fieldName === "risk_level") {
        control = (
          <Select value={String(currentValue || "low")} onValueChange={(value) => setNodeConfig(fieldName, value)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {["low", "medium", "high"].map((item) => (
                <SelectItem key={item} value={item}>
                  {item}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      } else if (fieldName === "linked_subscription_ids") {
        const linkedIds = Array.isArray(currentValue) ? currentValue.filter((item): item is string => typeof item === "string") : [];
        control = (
          <div className="space-y-2 rounded-[18px] border border-border/60 bg-background/70 p-3">
            {webhooks.length > 0 ? (
              webhooks.map((item) => {
                const latestDelivery = latestDeliveryMap.get(item.id);
                const checked = linkedIds.includes(item.id);
                return (
                  <label key={item.id} className="flex cursor-pointer items-start gap-3 rounded-[14px] px-2 py-2 hover:bg-background/70">
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        const nextIds = checked ? linkedIds.filter((id) => id !== item.id) : [...linkedIds, item.id];
                        setNodeConfig(fieldName, nextIds);
                      }}
                      className="mt-1 h-4 w-4 rounded border-border"
                    />
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-foreground">{item.name}</span>
                      {latestDelivery ? (
                        <span className="mt-1 block text-xs leading-5 text-muted-foreground">
                          {copy.webhookLatest}: {latestDelivery.status}
                        </span>
                      ) : null}
                    </span>
                  </label>
                );
              })
            ) : (
              <div className="text-sm text-muted-foreground">{copy.noWebhooks}</div>
            )}
          </div>
        );
      } else if (Array.isArray(schema.enum)) {
        control = (
          <Select value={String(currentValue || "")} onValueChange={(value) => setNodeConfig(fieldName, value)}>
            <SelectTrigger>
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {schema.enum.map((item) => (
                <SelectItem key={String(item)} value={String(item)}>
                  {String(item)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      } else if (fieldType === "boolean") {
        control = (
          <AppleSwitch
            checked={Boolean(currentValue)}
            onCheckedChange={(checked) => setNodeConfig(fieldName, checked)}
            className="rounded-[18px] border border-border/60 bg-background/70 px-3 py-3 shadow-none"
          />
        );
      } else if (fieldType === "integer" || fieldType === "number") {
        control = (
          <Input
            type="number"
            value={String(currentValue ?? "")}
            onChange={(event) => {
              const raw = event.target.value;
              setNodeConfig(fieldName, raw === "" ? null : Number(raw));
            }}
          />
        );
      } else if (fieldType === "object" || fieldType === "array") {
        control = renderJsonField(selectedNode.id, fieldName, currentValue);
      } else if (["instructions", "system_prompt", "expression", "content", "format_requirements"].includes(fieldName)) {
        control = (
          <Textarea
            rows={fieldName === "instructions" || fieldName === "system_prompt" ? 8 : 5}
            value={String(currentValue ?? "")}
            onChange={(event) => setNodeConfig(fieldName, event.target.value)}
          />
        );
      } else {
        control = (
          <Input
            value={String(currentValue ?? "")}
            onChange={(event) => setNodeConfig(fieldName, event.target.value)}
          />
        );
      }

      if (fieldType === "boolean") {
        return (
          <div key={fieldName} className="space-y-2">
            {description ? (
              <LabelWithHelp
                label={friendlyFieldLabel(fieldName, lang, schema)}
                description={description}
              />
            ) : (
              <Label>{friendlyFieldLabel(fieldName, lang, schema)}</Label>
            )}
            {control}
          </div>
        );
      }

      return (
        <div key={fieldName} className="space-y-2">
          {fieldName === "operation_key" ? (
            <LabelWithHelp
              label={copy.operationKey}
              description={copy.operationKeyHelp}
            />
          ) : description ? (
            <LabelWithHelp
              label={friendlyFieldLabel(fieldName, lang, schema)}
              description={description}
            />
          ) : (
            <Label>{friendlyFieldLabel(fieldName, lang, schema)}</Label>
          )}
          {control}
        </div>
      );
    },
    [
      catalog,
      copy.mappingLiteral,
      copy.mappingPath,
      copy.mappingSource,
      copy.noWebhooks,
      copy.operationKey,
      copy.operationKeyHelp,
      copy.webhookLatest,
      lang,
      latestDeliveryMap,
      operationCatalog,
      actionSurfaces,
      readonlyToolSurfaceGroups,
      readonlyToolSurfaces,
      renderJsonField,
      selectedOperation,
      triggerEventOptions,
      selectedNode,
      selectedNodeDefinition,
      setNodeConfig,
      updateSelectedNode,
      workflow?.target_type,
      webhooks,
      onOpenSurfaceAssistant,
    ],
  );

  // ---- Primary / advanced field computation ----
  const selectedNodePrimaryFields = useMemo(() => {
    if (!selectedNodeDefinition) return [];
    const fields = fieldProperties(selectedNodeDefinition);
    const preferred = PRIMARY_FIELDS_BY_NODE_TYPE[selectedNodeDefinition.type] || [];
    const hidden = new Set(HIDDEN_FIELDS_BY_NODE_TYPE[selectedNodeDefinition.type] || []);
    return fields.filter(([fieldName]) => preferred.includes(fieldName) && !hidden.has(fieldName));
  }, [selectedNodeDefinition]);

  const selectedNodeAdvancedFields = useMemo(() => {
    if (!selectedNodeDefinition) return [];
    const fields = fieldProperties(selectedNodeDefinition);
    const preferred = new Set(PRIMARY_FIELDS_BY_NODE_TYPE[selectedNodeDefinition.type] || []);
    const hidden = new Set(HIDDEN_FIELDS_BY_NODE_TYPE[selectedNodeDefinition.type] || []);
    return fields.filter(([fieldName, schema]) => {
      if (hidden.has(fieldName)) return false;
      if (preferred.has(fieldName)) return false;
      if (ALWAYS_ADVANCED_FIELDS.has(fieldName)) return true;
      const fieldType = normalizedSchemaType(schema);
      return fieldType === "object" || fieldType === "array" || !preferred.has(fieldName);
    });
  }, [selectedNodeDefinition]);

  const switchTriggerType = useCallback(
    (nextType: string) => {
      if (!selectedNode || !selectedNodeDefinition || !selectedNode.data.nodeType.startsWith("trigger.")) {
        return;
      }
      const nextDefinition = triggerTypeOptions.find((item) => item.type === nextType);
      if (!nextDefinition || nextDefinition.type === selectedNode.data.nodeType) {
        return;
      }
      const currentAutoLabels = new Set([
        friendlyNodeTypeLabel(selectedNode.data.nodeType, catalog, "zh"),
        friendlyNodeTypeLabel(selectedNode.data.nodeType, catalog, "en"),
        selectedNode.data.nodeType,
        "触发器",
        "Trigger",
        ...triggerTypeOptions.flatMap((item) => [
          friendlyNodeTypeLabel(item.type, catalog, "zh"),
          friendlyNodeTypeLabel(item.type, catalog, "en"),
        ]),
      ]);
      const shouldSyncLabel =
        !String(selectedNode.data.label || "").trim() || currentAutoLabels.has(String(selectedNode.data.label || "").trim());
      updateSelectedNode((node) => {
        const preservedSketchNote = node.data.config.sketch_note;
        return {
          ...node,
          data: {
            ...node.data,
            nodeType: nextDefinition.type,
            label: shouldSyncLabel
              ? friendlyNodeTypeLabel(nextDefinition.type, catalog, lang)
              : node.data.label,
            config: {
              ...(nextDefinition.default_config || {}),
              ...(preservedSketchNote !== undefined ? { sketch_note: preservedSketchNote } : {}),
            },
          },
        };
      });
    },
    [catalog, lang, selectedNode, selectedNodeDefinition, triggerTypeOptions, updateSelectedNode],
  );

  return (
    <div
      className={cn(
        "absolute bottom-4 right-4 top-[108px] z-40 flex w-[420px] flex-col overflow-hidden rounded-[28px] border border-border/60 bg-background/88 p-4 shadow-[var(--admin-shadow-lg)] backdrop-blur-xl transition-[transform,opacity] duration-200",
        show ? "translate-x-0 opacity-100" : "translate-x-[calc(100%+1rem)] opacity-0 pointer-events-none",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {selectedNode ? copy.selectedNode : selectedEdge ? copy.selectedEdge : copy.workflowSettings}
          </div>
          <div className="mt-1 text-base font-semibold text-foreground">
            {selectedNode ? selectedNode.data.label : selectedEdge ? selectedEdge.id : workflowName || workflow.name}
          </div>
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={onClose}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>

      <div className="mt-4 min-h-0 flex-1 overflow-y-auto pr-1 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
        <div className="space-y-4">
          <div className="rounded-[22px] border border-border/60 bg-background/70 p-4 backdrop-blur-xl">
            {/* ---- Workflow settings (no selection) ---- */}
            {!selectedNode && !selectedEdge ? (
              <div className="space-y-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  {copy.workflowSettings}
                </div>
                <div className="space-y-2">
                  <Label>{copy.workflowName}</Label>
                  <Input value={workflowName} onChange={(event) => onWorkflowNameChange(event.target.value)} />
                </div>
                <div className="space-y-2">
                  <LabelWithHelp
                    label={copy.workflowDescription}
                    description={lang === "zh" ? "一句话概括这个工作流是做什么的，方便后续识别。" : "A short summary of what this workflow is for."}
                  />
                  <Textarea rows={4} value={workflowDescription} onChange={(event) => onWorkflowDescriptionChange(event.target.value)} />
                </div>
                <div className="space-y-2">
                  <LabelWithHelp label={copy.enabled} description={copy.enabledDesc} />
                  <AppleSwitch checked={workflowEnabled} onCheckedChange={onWorkflowEnabledChange} />
                </div>
              </div>
            ) : null}

            {/* ---- Node inspector ---- */}
            {selectedNode && selectedNodeDefinition ? (
              <div className="space-y-4">
                <div className="space-y-2">
                  <Label>{copy.workflowName}</Label>
                  <Input value={selectedNode.data.label} onChange={(event) => setNodeLabel(event.target.value)} />
                </div>
                {isSketchMode ? (
                  <div className="rounded-[18px] border border-emerald-300/45 bg-emerald-500/8 px-3 py-3 text-sm leading-6 text-muted-foreground">
                    {lang === "zh"
                      ? "草图阶段这里只需要写一句描述，说明这个节点大概要做什么。正式参数和字段等到 AI 收敛后再生成。"
                      : "In sketch mode, only describe what this node is roughly supposed to do. Detailed parameters and fields will be generated later after AI clarification."}
                  </div>
                ) : null}

                {isSketchMode ? (
                  <div className="space-y-3">
                    <div className="space-y-2">
                      <Label>{lang === "zh" ? "节点说明" : "Node Description"}</Label>
                      <Textarea
                        rows={8}
                        value={String(selectedNode.data.config.sketch_note ?? "")}
                        onChange={(event) => setNodeConfig("sketch_note", event.target.value)}
                        placeholder={
                          lang === "zh"
                            ? "例如：当出现新的待审核评论时触发；接收待审核评论对象；读取最近待审评论；让 AI 判断是否通过；若高风险则转人工审批。"
                            : "For example: trigger when a new pending comment appears; receive the pending comment object; read the latest pending comments; let AI decide whether to approve; route risky cases to human approval."
                        }
                      />
                    </div>
                  </div>
                ) : selectedNode.data.nodeType === "ai.task" ? (
                  <AiTaskInspector
                    lang={lang}
                    copy={copy}
                    selectedNode={selectedNode}
                    mountedCapabilityItems={mountedCapabilityItems}
                    triggerEventOptions={triggerEventOptions}
                    selectedNodePrimaryFields={selectedNodePrimaryFields}
                    selectedNodeAdvancedFields={selectedNodeAdvancedFields}
                    renderSchemaField={renderSchemaField}
                    aiShellConfig={aiShellConfig}
                    derivingSchema={derivingSchema}
                    derivedSchema={derivedSchema}
                    derivedOutputSummary={derivedOutputSummary}
                    derivedOutputFields={derivedOutputFields}
                    setNodeConfig={setNodeConfig}
                  />
                ) : selectedNode.data.nodeType === "approval.review" ? (
                  <ApprovalReviewInspector lang={lang} />
                ) : selectedNode.data.nodeType.startsWith("trigger.") ? (
                  <TriggerInspector
                    lang={lang}
                    catalog={catalog}
                    selectedNode={selectedNode}
                    triggerTypeOptions={triggerTypeOptions}
                    switchTriggerType={switchTriggerType}
                    selectedNodePrimaryFields={selectedNodePrimaryFields}
                    selectedNodeAdvancedFields={selectedNodeAdvancedFields}
                    renderSchemaField={renderSchemaField}
                    copy={copy}
                  />
                ) : (
                  <GenericSchemaInspector
                    copy={copy}
                    selectedNodePrimaryFields={selectedNodePrimaryFields}
                    selectedNodeAdvancedFields={selectedNodeAdvancedFields}
                    showAdvanced={
                      selectedNode.data.nodeType !== "apply.action" &&
                      selectedNode.data.nodeType !== "operation.capability"
                    }
                    renderSchemaField={renderSchemaField}
                  />
                )}
              </div>
            ) : null}

            {/* ---- Edge inspector ---- */}
            {selectedEdge ? (
              <div className="space-y-4">
                <div className="text-xs font-semibold uppercase tracking-[0.16em] text-muted-foreground">
                  {copy.selectedEdge}
                </div>
                <div className="space-y-2">
                  <Label>{copy.edgeLabel}</Label>
                  <Input
                    value={typeof selectedEdge.label === "string" ? selectedEdge.label : ""}
                    onChange={(event) =>
                      setEdges((current) =>
                        current.map((edge) => (edge.id === selectedEdge.id ? { ...edge, label: event.target.value } : edge)),
                      )
                    }
                  />
                </div>
                {selectedEdgeIsTool ? (
                  <div className="rounded-[18px] border border-sky-300/45 bg-sky-500/8 px-3 py-3 text-sm leading-6 text-muted-foreground">
                    {lang === "zh"
                      ? "这是一条工具挂载边。它只决定 AI 可见的只读工具，不参与流程执行顺序。"
                      : "This is a tool-mount edge. It exposes a readonly tool to the AI task and does not participate in flow execution."}
                  </div>
                ) : (
                  <>
                    <div className="space-y-2">
                      <Label>{copy.edgeMatch}</Label>
                      <Input
                        value={String((selectedEdge.data?.config as Record<string, unknown> | undefined)?.match || "")}
                        onChange={(event) =>
                          setEdges((current) =>
                            current.map((edge) =>
                              edge.id === selectedEdge.id
                                ? {
                                    ...edge,
                                    data: {
                                      ...(edge.data || {}),
                                      config: {
                                        ...((edge.data?.config as Record<string, unknown>) || {}),
                                        match: event.target.value,
                                      },
                                    },
                                  }
                                : edge,
                            ),
                          )
                        }
                      />
                      {selectedSourceNodeDefinition ? (
                        <Select
                          value={
                            String((selectedEdge.data?.config as Record<string, unknown> | undefined)?.match || "") || "__custom__"
                          }
                          onValueChange={(value) =>
                            setEdges((current) =>
                              current.map((edge) =>
                                edge.id === selectedEdge.id
                                  ? {
                                      ...edge,
                                      data: {
                                        ...(edge.data || {}),
                                        config: {
                                          ...((edge.data?.config as Record<string, unknown>) || {}),
                                          match: value === "__custom__" ? "" : value,
                                        },
                                      },
                                    }
                                  : edge,
                              ),
                            )
                          }
                        >
                          <SelectTrigger>
                            <SelectValue />
                          </SelectTrigger>
                          <SelectContent>
                            <SelectItem value="__custom__">{lang === "zh" ? "自定义" : "Custom"}</SelectItem>
                            {selectedSourceNodeDefinition.output_ports
                              .flatMap((port) => port.match_values || [])
                              .filter((value, index, all) => all.indexOf(value) === index)
                              .map((value) => (
                                <SelectItem key={value} value={value}>
                                  {value}
                                </SelectItem>
                              ))}
                          </SelectContent>
                        </Select>
                      ) : null}
                    </div>
                    <div className="space-y-2">
                      <Label>{copy.edgeStyle}</Label>
                      <Select
                        value={String(selectedEdge.data?.variant || "default")}
                        onValueChange={(value) =>
                          setEdges((current) =>
                            current.map((edge) =>
                              edge.id === selectedEdge.id
                                ? {
                                    ...edge,
                                    animated: value === "dashed",
                                    style: value === "dashed" ? { strokeDasharray: "6 6" } : undefined,
                                    data: { ...(edge.data || {}), variant: value },
                                  }
                                : edge,
                            ),
                          )
                        }
                      >
                        <SelectTrigger>
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="default">{copy.defaultEdge}</SelectItem>
                          <SelectItem value="dashed">{copy.dashedEdge}</SelectItem>
                        </SelectContent>
                      </Select>
                    </div>
                  </>
                )}
                <div className="rounded-[18px] border border-border/60 bg-background/70 p-3 text-sm leading-6 text-muted-foreground">
                  <div>{copy.sourceHandle}: {selectedEdge.sourceHandle || "-"}</div>
                  <div>{copy.targetHandle}: {selectedEdge.targetHandle || "-"}</div>
                </div>
              </div>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  );
}
