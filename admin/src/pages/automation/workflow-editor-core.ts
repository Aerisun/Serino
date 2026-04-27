import { Position, type Edge, type Node } from "@xyflow/react";
import type {
  AgentWorkflow,
  AgentWorkflowCatalog,
  AgentWorkflowCatalogNodeType,
  AgentWorkflowGraph,
  AgentWorkflowTriggerBinding,
  AgentWorkflowValidationIssue,
} from "@/pages/automation/api";
import type { Lang } from "@/i18n";
import {
  Bot,
  Boxes,
  Braces,
  Cable,
  Clock3,
  GitBranch,
  PauseCircle,
  Play,
  RefreshCw,
  Send,
  Server,
  ShieldCheck,
  StickyNote,
  Timer,
  Wand2,
  Webhook,
  Zap,
} from "lucide-react";

export type WorkflowCanvasNodeData = {
  nodeType: string;
  label: string;
  config: Record<string, unknown>;
  __renderMeta?: {
    issueCount: number;
    issueLevel: "error" | "warning" | null;
    definition?: AgentWorkflowCatalogNodeType;
    nodeTypeLabel: string;
    lang: Lang;
  };
};

export type WorkflowCanvasNode = Node<WorkflowCanvasNodeData, "workflowNode">;
export type WorkflowCanvasEdge = Edge<{ variant?: string; config?: Record<string, unknown> }>;

export type SelectedEntity =
  | { type: "node"; id: string }
  | { type: "edge"; id: string }
  | null;

// ---------------------------------------------------------------------------
// Three-contract helpers for ai.task nodes
// ---------------------------------------------------------------------------

export type InputContractField = {
  key: string;
  field_schema: Record<string, unknown>;
  required: boolean;
  selector: { source: string; node_id?: string; port?: string; path?: string; expr?: string; value?: unknown };
};

export type InputContract = { fields: InputContractField[] };

export type OutputContractRoute = { field: string; enum: string[]; enum_from_edges: boolean } | null;

export type OutputContract = {
  output_schema: Record<string, unknown>;
  route?: OutputContractRoute;
};

export type UpstreamPortOption = {
  node_id: string;
  node_label: string;
  node_type: string;
  port_id: string;
  port_label: string;
  data_schema: Record<string, unknown> | null;
  explanation?: string;
  source_port_id?: string;
  source_port_label?: string;
};

export const AI_TASK_INPUT_PORT_IDS = ["input_1", "input_2", "input_3"] as const;
export const AI_TASK_OUTPUT_PORT_IDS = ["output_1", "output_2", "output_3"] as const;
export const AI_TASK_MOUNT_PORT_IDS = ["mount_1", "mount_2", "mount_3"] as const;
export type AiTaskInputPortId = (typeof AI_TASK_INPUT_PORT_IDS)[number];
export type AiTaskOutputPortId = (typeof AI_TASK_OUTPUT_PORT_IDS)[number];
export type AiTaskMountPortId = (typeof AI_TASK_MOUNT_PORT_IDS)[number];

export type AiTaskInputSlotConfig = {
  note: string;
};

export type AiTaskShellConfig = {
  mode: "direct" | "loop";
  loop_max_rounds: number;
  input_slots: Record<string, AiTaskInputSlotConfig>;
};

// ---------------------------------------------------------------------------
// Dialog props
// ---------------------------------------------------------------------------

export interface WorkflowVisualEditorDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workflow: AgentWorkflow | null;
  mode?: "edit" | "sketch";
  draftValidationIssues?: AgentWorkflowValidationIssue[];
  persistDisabledOnClose?: boolean;
  onContinueSketch?: (workflow: AgentWorkflow) => void | Promise<void>;
}

// ---------------------------------------------------------------------------
// COPY strings
// ---------------------------------------------------------------------------

export type CopyShape = {
  title: string;
  description: string;
  save: string;
  saving: string;
  validate: string;
  validating: string;
  palette: string;
  addNode: string;
  inspector: string;
  selectedNode: string;
  selectedEdge: string;
  workflowSettings: string;
  noSelection: string;
  deleteNode: string;
  deleteEdge: string;
  workflowName: string;
  workflowDescription: string;
  enabled: string;
  enabledDesc: string;
  approvalMode: string;
  allowHighRiskWithoutApproval: string;
  maxSteps: string;
  runtimeSummary: string;
  runtimeSummaryHint: string;
  triggers: string;
  nodes: string;
  operations: string;
  highRisk: string;
  nodeConfig: string;
  definition: string;
  essentials: string;
  advanced: string;
  simpleHint: string;
  edgeLabel: string;
  edgeMatch: string;
  edgeStyle: string;
  defaultEdge: string;
  dashedEdge: string;
  jsonInvalid: string;
  validationPassed: string;
  validationFailed: string;
  operationKey: string;
  operationKeyHelp: string;
  argumentMappings: string;
  mappingSource: string;
  mappingPath: string;
  mappingLiteral: string;
  mappingAuto: string;
  required: string;
  addOutputField: string;
  linkedWebhooks: string;
  webhookLatest: string;
  noWebhooks: string;
  sourceHandle: string;
  targetHandle: string;
  exampleInput: string;
  triggerEvent: string;
  triggerEventHelp: string;
  outputConstraints: string;
  outputConstraintsHelp: string;
  inputMappings: string;
  addMapping: string;
  removeMapping: string;
  deriving: string;
  deriveFailed: string;
};

export const COPY: Record<Lang, CopyShape> = {
  zh: {
    title: "工作流画布编辑器",
    description: "节点注册和属性面板都直接来自 workflow catalog，画布按真实 graph 保存。",
    save: "保存工作流",
    saving: "保存中...",
    validate: "校验流程",
    validating: "校验中...",
    palette: "节点面板",
    addNode: "添加节点",
    inspector: "属性侧栏",
    selectedNode: "当前节点",
    selectedEdge: "当前连线",
    workflowSettings: "工作流设置",
    noSelection: "选中节点或连线后，这里会根据 catalog 自动渲染对应的属性表单。",
    deleteNode: "删除节点",
    deleteEdge: "删除连线",
    workflowName: "名称",
    workflowDescription: "摘要说明",
    enabled: "启用工作流",
    enabledDesc: "关闭后保留图结构，但不会继续接收触发。",
    approvalMode: "审批策略",
    allowHighRiskWithoutApproval: "允许高风险操作直跑",
    maxSteps: "最大步骤数",
    runtimeSummary: "当前图摘要",
    runtimeSummaryHint: "这里展示的是 graph 和 trigger bindings 的即时摘要，不再从旧固定字段反向推导。",
    triggers: "触发器",
    nodes: "节点数",
    operations: "操作节点",
    highRisk: "高风险操作",
    nodeConfig: "节点配置",
    definition: "节点定义",
    essentials: "常用配置",
    advanced: "高级配置",
    simpleHint: "默认只展开最常用的字段，完整能力都保留在高级配置里。",
    edgeLabel: "连线标签",
    edgeMatch: "匹配条件",
    edgeStyle: "连线样式",
    defaultEdge: "默认",
    dashedEdge: "虚线",
    jsonInvalid: "JSON 格式无效，暂未写入配置",
    validationPassed: "当前工作流校验通过",
    validationFailed: "工作流校验失败",
    operationKey: "操作目录",
    operationKeyHelp: "选择这一步到底要调用哪个后端能力、内部 API 或 MCP 工具。",
    argumentMappings: "参数映射",
    mappingSource: "值来源",
    mappingPath: "取值路径",
    mappingLiteral: "固定值",
    mappingAuto: "自动",
    required: "必填",
    addOutputField: "添加输出字段",
    linkedWebhooks: "关联 Webhook 订阅",
    webhookLatest: "最近状态",
    noWebhooks: "还没有找到可关联的 Webhook 订阅。",
    sourceHandle: "来源端口",
    targetHandle: "目标端口",
    exampleInput: "示例输入",
    triggerEvent: "触发事件",
    triggerEventHelp: "决定什么情况下会启动这条流程。通常只需要选一个最贴近你需求的事件。",
    outputConstraints: "输出约束 (自动推导)",
    outputConstraintsHelp: "根据下游连接的节点自动推导 AI 必须输出的字段",
    inputMappings: "输入映射",
    addMapping: "添加映射",
    removeMapping: "移除",
    deriving: "推导中...",
    deriveFailed: "自动推导失败",
  },
  en: {
    title: "Workflow Canvas Editor",
    description: "The node registry and inspector now come from the workflow catalog, and the canvas saves the real graph.",
    save: "Save Workflow",
    saving: "Saving...",
    validate: "Validate",
    validating: "Validating...",
    palette: "Node Palette",
    addNode: "Add Node",
    inspector: "Inspector",
    selectedNode: "Selected Node",
    selectedEdge: "Selected Edge",
    workflowSettings: "Workflow Settings",
    noSelection: "Select a node or edge to render its catalog-driven property form here.",
    deleteNode: "Delete Node",
    deleteEdge: "Delete Edge",
    workflowName: "Name",
    workflowDescription: "Summary",
    enabled: "Enable workflow",
    enabledDesc: "Disabled workflows keep the graph but stop receiving triggers.",
    approvalMode: "Approval mode",
    allowHighRiskWithoutApproval: "Allow high-risk operations without approval",
    maxSteps: "Max steps",
    runtimeSummary: "Graph Summary",
    runtimeSummaryHint: "This summary comes from the graph and trigger bindings instead of legacy derived runtime fields.",
    triggers: "Triggers",
    nodes: "Nodes",
    operations: "Operations",
    highRisk: "High-risk ops",
    nodeConfig: "Node Config",
    definition: "Definition",
    essentials: "Essentials",
    advanced: "Advanced",
    simpleHint: "Common fields stay visible by default, while the full power remains under advanced settings.",
    edgeLabel: "Edge label",
    edgeMatch: "Match rule",
    edgeStyle: "Edge style",
    defaultEdge: "Default",
    dashedEdge: "Dashed",
    jsonInvalid: "Invalid JSON. The config has not been updated yet.",
    validationPassed: "Workflow validation passed",
    validationFailed: "Workflow validation failed",
    operationKey: "Operation Catalog",
    operationKeyHelp: "Choose which backend capability, internal API, or MCP tool this node should execute.",
    argumentMappings: "Argument Mappings",
    mappingSource: "Value Source",
    mappingPath: "Path",
    mappingLiteral: "Literal Value",
    mappingAuto: "Auto",
    required: "Required",
    addOutputField: "Add Output Field",
    linkedWebhooks: "Linked webhook subscriptions",
    webhookLatest: "Latest status",
    noWebhooks: "No webhook subscriptions are available.",
    sourceHandle: "Source port",
    targetHandle: "Target port",
    exampleInput: "Example Input",
    triggerEvent: "Trigger Event",
    triggerEventHelp: "Choose the event that should start this workflow.",
    outputConstraints: "Output Constraints (Auto-derived)",
    outputConstraintsHelp: "Auto-derived from downstream node requirements",
    inputMappings: "Input Mappings",
    addMapping: "Add mapping",
    removeMapping: "Remove",
    deriving: "Deriving...",
    deriveFailed: "Auto-derivation failed",
  },
};

export const CATEGORY_ORDER_FALLBACK = [
  "common",
  "trigger",
  "ai",
  "tool",
  "approval",
  "operation",
  "flow",
  "transform",
  "notification",
  "utility",
] as const;

export const zhCategoryLabels: Record<string, string> = {
  common: "常用组件",
  trigger: "触发器",
  ai: "AI",
  tool: "工具挂载",
  approval: "审批",
  operation: "执行动作",
  flow: "流程控制",
  transform: "数据整理",
  notification: "通知",
  utility: "备注 / 辅助",
};

export const enCategoryLabels: Record<string, string> = {};

export const zhNodeLabels: Record<string, string> = {
  "trigger.event": "事件触发",
  "trigger.webhook": "Webhook 触发",
  "trigger.manual": "手动触发",
  "trigger.schedule": "定时触发",
  "ai.task": "AI 任务",
  "tool.query": "只读工具",
  "apply.action": "执行动作",
  "approval.review": "人工审批",
  "operation.capability": "平台能力调用",
  "flow.condition": "条件分支",
  "flow.delay": "延时等待",
  "flow.poll": "轮询检测",
  "flow.wait_for_event": "等待事件",
  "notification.webhook": "Webhook 通知",
};

export const enNodeLabels: Record<string, string> = {};

export function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

export function iconForName(icon: string) {
  switch (icon) {
    case "zap":
      return Zap;
    case "bot":
      return Bot;
    case "shield-check":
      return ShieldCheck;
    case "cable":
      return Cable;
    case "git-branch":
      return GitBranch;
    case "send":
      return Send;
    case "sticky-note":
      return StickyNote;
    case "clock-3":
      return Clock3;
    case "play":
      return Play;
    case "webhook":
      return Webhook;
    case "refresh-cw":
      return RefreshCw;
    case "pause-circle":
      return PauseCircle;
    case "wand-2":
      return Wand2;
    case "server":
      return Server;
    case "timer":
      return Timer;
    case "braces":
      return Braces;
    default:
      return Boxes;
  }
}

export function toneForCategory(category: string, riskLevel?: string) {
  if ((riskLevel || "").toLowerCase() === "high") return "rose";
  switch (category) {
    case "trigger":
      return "sky";
    case "ai":
      return "emerald";
    case "tool":
      return "sky";
    case "approval":
      return "rose";
    case "operation":
      return "amber";
    case "flow":
      return "amber";
    case "transform":
      return "violet";
    case "notification":
      return "violet";
    default:
      return "slate";
  }
}

export function toneClasses(tone: string) {
  switch (tone) {
    case "sky":
      return "border-sky-300/55 bg-[linear-gradient(180deg,rgba(56,189,248,0.17),rgba(56,189,248,0.05))]";
    case "emerald":
      return "border-emerald-300/55 bg-[linear-gradient(180deg,rgba(16,185,129,0.17),rgba(16,185,129,0.05))]";
    case "rose":
      return "border-rose-300/55 bg-[linear-gradient(180deg,rgba(244,63,94,0.17),rgba(244,63,94,0.05))]";
    case "amber":
      return "border-amber-300/55 bg-[linear-gradient(180deg,rgba(245,158,11,0.17),rgba(245,158,11,0.05))]";
    case "violet":
      return "border-violet-300/55 bg-[linear-gradient(180deg,rgba(139,92,246,0.17),rgba(139,92,246,0.05))]";
    default:
      return "border-slate-300/55 bg-[linear-gradient(180deg,rgba(148,163,184,0.17),rgba(148,163,184,0.05))]";
  }
}

export function portPosition(side: string) {
  switch (side) {
    case "left":
      return Position.Left;
    case "right":
      return Position.Right;
    case "top":
      return Position.Top;
    case "bottom":
      return Position.Bottom;
    default:
      return Position.Right;
  }
}

export function portStyle(side: string, index: number, count: number) {
  const ratio = `${((index + 1) / (count + 1)) * 100}%`;
  if (side === "left" || side === "right") {
    return { top: ratio };
  }
  return { left: ratio };
}

export function summaryForNode(definition: AgentWorkflowCatalogNodeType | undefined, config: Record<string, unknown>) {
  const sketchNote = String(config.sketch_note || "").trim();
  if (sketchNote) {
    return sketchNote;
  }
  if (!definition) {
    return "-";
  }
  if (definition.type === "note") {
    return String(config.content || "").trim() || "-";
  }
  if (definition.type.startsWith("trigger.")) {
    return String(config.event_type || config.path || config.interval_seconds || config.cron || definition.label || "-");
  }
  if (definition.type === "ai.task") {
    const instructions = String(config.instructions || config.system_prompt || "").trim();
    const mode = String(config.mode || "direct").trim();
    if (!instructions) {
      return mode === "loop" ? "loop" : "-";
    }
    return `${mode} · ${instructions.slice(0, 72)}${instructions.length > 72 ? "..." : ""}`;
  }
  if (definition.type === "tool.query") {
    const surfaceKeys = Array.isArray(config.surface_keys)
      ? config.surface_keys.filter((item): item is string => typeof item === "string" && item.trim().length > 0)
      : String(config.surface_key || "").trim()
        ? [String(config.surface_key || "").trim()]
        : [];
    if (!surfaceKeys.length) {
      return "-";
    }
    if (surfaceKeys.length === 1) {
      return surfaceKeys[0];
    }
    return `${surfaceKeys.length} tools`;
  }
  if (definition.type === "apply.action") {
    return String(config.surface_key || "-");
  }
  if (definition.type === "approval.review") {
    return `${String(config.approval_type || "manual_review")} · ${String(config.mode || "conditional")}`;
  }
  if (definition.type.startsWith("operation.")) {
    return String(config.operation_key || "-");
  }
  if (definition.type === "flow.condition") {
    return String(config.expression || "-");
  }
  if (definition.type === "flow.delay") {
    return config.until_path ? String(config.until_path) : `${String(config.delay_seconds || 0)}s`;
  }
  if (definition.type === "flow.poll") {
    return String(config.operation_key || "-");
  }
  if (definition.type === "flow.wait_for_event") {
    return String(config.event_type || "-");
  }
  if (definition.type === "notification.webhook") {
    const linked = Array.isArray(config.linked_subscription_ids) ? config.linked_subscription_ids.length : 0;
    return `${linked} webhook${linked === 1 ? "" : "s"}`;
  }
  return String(Object.values(config).find((value) => typeof value === "string" && value.trim()) || "-");
}

export function normalizeGraphForCanvas(graph: AgentWorkflowGraph): AgentWorkflowGraph {
  const nodesById = new Map(graph.nodes.map((node) => [node.id, node]));
  const edges = graph.edges.map((edge) => ({ ...edge }));
  const aiOutputUsage = new Map<string, string[]>();
  const aiInputUsage = new Map<string, string[]>();
  const aiMountUsage = new Map<string, string[]>();

  for (const edge of edges) {
    const sourceType = nodesById.get(edge.source)?.type || "";
    const targetType = nodesById.get(edge.target)?.type || "";
    const sourceHandle = String(edge.source_handle || "").trim();
    const targetHandle = String(edge.target_handle || "").trim();

    if (sourceType === "ai.task" && sourceHandle !== "route") {
      const used = aiOutputUsage.get(edge.source) || [];
      if (!AI_TASK_OUTPUT_PORT_IDS.includes(sourceHandle as AiTaskOutputPortId) || used.includes(sourceHandle)) {
        const freeHandle =
          AI_TASK_OUTPUT_PORT_IDS.find((portId) => !used.includes(portId)) ||
          AI_TASK_OUTPUT_PORT_IDS[0];
        edge.source_handle = freeHandle;
        used.push(freeHandle);
      } else {
        used.push(sourceHandle);
      }
      aiOutputUsage.set(edge.source, used);
    }

    if (targetType === "ai.task") {
      const isSpecialMount =
        AI_TASK_MOUNT_PORT_IDS.includes(targetHandle as AiTaskMountPortId) ||
        sourceType === "tool.query" ||
        sourceType.startsWith("trigger.") ||
        sourceType === "approval.review" ||
        sourceType === "apply.action";
      if (isSpecialMount) {
        const used = aiMountUsage.get(edge.target) || [];
        if (!AI_TASK_MOUNT_PORT_IDS.includes(targetHandle as AiTaskMountPortId) || used.includes(targetHandle)) {
          const freeHandle =
            AI_TASK_MOUNT_PORT_IDS.find((portId) => !used.includes(portId)) ||
            AI_TASK_MOUNT_PORT_IDS[0];
          edge.target_handle = freeHandle;
          used.push(freeHandle);
        } else {
          used.push(targetHandle);
        }
        aiMountUsage.set(edge.target, used);
        continue;
      }

      const used = aiInputUsage.get(edge.target) || [];
      if (!AI_TASK_INPUT_PORT_IDS.includes(targetHandle as AiTaskInputPortId) || used.includes(targetHandle)) {
        const freeHandle =
          AI_TASK_INPUT_PORT_IDS.find((portId) => !used.includes(portId)) ||
          AI_TASK_INPUT_PORT_IDS[0];
        edge.target_handle = freeHandle;
        used.push(freeHandle);
      } else {
        used.push(targetHandle);
      }
      aiInputUsage.set(edge.target, used);
    }
  }

  return {
    ...graph,
    edges,
  };
}

export function workflowGraphToCanvas(graph: AgentWorkflowGraph) {
  const normalized = normalizeGraphForCanvas(graph);
  const nodes: WorkflowCanvasNode[] = normalized.nodes.map((node) => ({
    id: node.id,
    type: "workflowNode",
    position: node.position,
    data: {
      nodeType: node.type,
      label: node.label || node.type,
      config: cloneJson(node.config || {}),
    },
    selected: false,
  }));
  const edges: WorkflowCanvasEdge[] = normalized.edges.map((edge) => ({
    id: edge.id,
    source: edge.source,
    target: edge.target,
    sourceHandle: edge.source_handle || null,
    targetHandle: edge.target_handle || null,
    label: edge.label || "",
    type: "smoothstep",
    animated: edge.type === "dashed",
    style: edge.type === "dashed" ? { strokeDasharray: "6 6" } : undefined,
    markerEnd: { type: "arrowclosed" as const },
    data: {
      variant: edge.type || "default",
      config: cloneJson(edge.config || {}),
    },
  }));
  return { nodes, edges, viewport: normalized.viewport ?? { x: 0, y: 0, zoom: 1 } };
}

export function canvasToGraph(
  nodes: WorkflowCanvasNode[],
  edges: WorkflowCanvasEdge[],
  viewport: { x: number; y: number; zoom: number },
): AgentWorkflowGraph {
  return {
    version: 2,
    viewport,
    nodes: nodes.map((node) => ({
      id: node.id,
      type: node.data.nodeType,
      label: node.data.label,
      position: { x: node.position.x, y: node.position.y },
      config: cloneJson(node.data.config || {}),
    })),
    edges: edges.map((edge) => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      source_handle: edge.sourceHandle || null,
      target_handle: edge.targetHandle || null,
      label: typeof edge.label === "string" ? edge.label : "",
      type: String(edge.data?.variant || "default"),
      config: cloneJson((edge.data?.config as Record<string, unknown>) || {}),
    })),
  };
}

export function edgeKind(edge: WorkflowCanvasEdge, nodes: WorkflowCanvasNode[]) {
  const configuredKind = String((edge.data?.config as Record<string, unknown> | undefined)?.kind || "").trim();
  if (configuredKind === "tool" || configuredKind === "action" || configuredKind === "data" || configuredKind === "control" || configuredKind === "trigger") {
    return configuredKind;
  }
  const sourceNode = nodes.find((node) => node.id === edge.source);
  if (sourceNode?.data.nodeType === "tool.query") return "tool";
  if (sourceNode?.data.nodeType === "approval.review") return "control";
  if (sourceNode?.data.nodeType.startsWith("trigger.")) return "trigger";
  if (AI_TASK_MOUNT_PORT_IDS.includes(String(edge.targetHandle || "") as AiTaskMountPortId)) {
    if (sourceNode?.data.nodeType === "tool.query") return "tool";
    if (sourceNode?.data.nodeType === "apply.action") return "action";
    if (sourceNode?.data.nodeType === "approval.review") return "control";
    if (sourceNode?.data.nodeType.startsWith("trigger.")) return "trigger";
  }
  if ((edge.sourceHandle || "") === "approval" || (edge.sourceHandle || "") === "approved" || (edge.sourceHandle || "") === "rejected" || (edge.sourceHandle || "") === "default") {
    return "control";
  }
  if ((edge.targetHandle || "") === "control") {
    return "control";
  }
  return "data";
}

export function isToolEdge(edge: WorkflowCanvasEdge, nodes: WorkflowCanvasNode[]) {
  return edgeKind(edge, nodes) === "tool";
}

export function isFlowEdge(edge: WorkflowCanvasEdge, nodes: WorkflowCanvasNode[]) {
  return edgeKind(edge, nodes) !== "tool" && edgeKind(edge, nodes) !== "action";
}

export function isRouteEdge(edge: WorkflowCanvasEdge) {
  return (edge.sourceHandle || "") === "route";
}

export function isDataEdge(edge: WorkflowCanvasEdge, nodes: WorkflowCanvasNode[]) {
  return edgeKind(edge, nodes) === "data" && !isRouteEdge(edge);
}

export function deriveTriggerBindings(nodes: WorkflowCanvasNode[]): AgentWorkflowTriggerBinding[] {
  return nodes
    .filter((node) => node.data.nodeType.startsWith("trigger."))
    .map((node) => ({
      id: node.id,
      type: node.data.nodeType,
      label: node.data.label,
      enabled: true,
      config: cloneJson(node.data.config || {}),
    }));
}

export function nextNodeId(nodeType: string, nodes: WorkflowCanvasNode[]) {
  const normalized = nodeType.replace(/[^\w]+/g, "-");
  const count = nodes.filter((node) => node.data.nodeType === nodeType).length + 1;
  return `${normalized}-${count}`;
}

export function nextNodePosition(nodes: WorkflowCanvasNode[]) {
  const index = nodes.length;
  return {
    x: 120 + (index % 3) * 280,
    y: 120 + Math.floor(index / 3) * 190,
  };
}


export function friendlyCategoryLabel(category: string, _catalog: AgentWorkflowCatalog | undefined, lang: Lang = "zh") {
  const map = lang === "zh" ? zhCategoryLabels : enCategoryLabels;
  return map[category] ?? category;
}

export function friendlyNodeTypeLabel(type: string, catalog: AgentWorkflowCatalog | undefined, lang: Lang = "zh") {
  const nodeDef = catalog?.node_types?.find((nt) => nt.type === type);
  if (nodeDef?.label) return nodeDef.label;
  const map = lang === "zh" ? zhNodeLabels : enNodeLabels;
  return map[type] ?? type;
}

export function getInputContract(config: Record<string, unknown>): InputContract {
  return (config?.input_contract as InputContract) ?? { fields: [] };
}

export function getOutputContract(config: Record<string, unknown>): OutputContract {
  return (config?.output_contract as OutputContract) ?? { output_schema: {}, route: null };
}
