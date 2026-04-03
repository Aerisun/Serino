import type { Edge, Node } from "@xyflow/react";
import type {
  AgentWorkflow,
  AgentWorkflowCatalog,
  AgentWorkflowCatalogNodeType,
  AgentWorkflowCatalogOperation,
  AgentWorkflowGraph,
  AgentWorkflowRuntimePolicy,
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

// ---------------------------------------------------------------------------
// Canvas node/edge types
// ---------------------------------------------------------------------------

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

// ---------------------------------------------------------------------------
// Query keys
// ---------------------------------------------------------------------------

export const WORKFLOWS_QUERY_KEY = ["admin", "agent", "workflows"] as const;
export const WORKFLOW_CATALOG_QUERY_KEY = ["admin", "agent", "workflow-catalog"] as const;

// ---------------------------------------------------------------------------
// Category order fallback & label maps
// ---------------------------------------------------------------------------

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

export const zhOpLabels: Record<string, string> = {
  get_site_config: "读取站点配置",
  list_posts: "读取文章列表",
  get_post: "读取单篇文章",
  search_content: "搜索公开内容",
  list_diary_entries: "读取日记列表",
  get_diary_entry: "读取单篇日记",
  list_thoughts: "读取想法列表",
  list_excerpts: "读取摘录列表",
  list_admin_content: "读取后台内容列表",
  get_admin_content: "读取后台单条内容",
  create_admin_content: "创建内容",
  update_admin_content: "更新内容",
  delete_admin_content: "删除内容",
  bulk_delete_admin_content: "批量删除内容",
  bulk_update_admin_content_status: "批量修改内容状态",
  list_admin_tags: "读取内容标签",
  list_admin_content_categories: "读取内容分类",
  create_admin_content_category: "创建内容分类",
  update_admin_content_category: "修改内容分类",
  delete_admin_content_category: "删除内容分类",
  list_comment_moderation_queue: "读取评论待审队列",
  moderate_comment: "审核评论",
  list_guestbook_moderation_queue: "读取留言待审队列",
  moderate_guestbook_entry: "审核留言",
  "moderate_comment | moderate_guestbook_entry": "按对象自动选择评论 / 留言审核",
  get_admin_site_profile: "读取站点资料设置",
  update_admin_site_profile: "更新站点资料设置",
  get_admin_community_config: "读取评论区设置",
  update_admin_community_config: "更新评论区设置",
  list_admin_assets: "读取资源库列表",
  get_admin_asset: "读取单个资源",
  upload_admin_asset: "上传资源",
  update_admin_asset: "更新资源信息",
  delete_admin_asset: "删除资源",
  bulk_delete_admin_assets: "批量删除资源",
  list_admin_records: "读取通用配置记录",
  get_admin_record: "读取单条通用配置记录",
  create_admin_record: "创建通用配置记录",
  update_admin_record: "更新通用配置记录",
  delete_admin_record: "删除通用配置记录",
  reorder_admin_nav_items: "重排导航项",
  list_friend_feed_sources: "读取友链 RSS 源",
  create_friend_feed_source: "创建友链 RSS 源",
  update_friend_feed_source: "更新友链 RSS 源",
  delete_friend_feed_source: "删除友链 RSS 源",
  trigger_feed_crawl: "触发友链抓取",
  content_publish_review: "记录内容发布审核结果",
  moderation_deferred: "转人工复核，不直接执行",
  noop: "不执行任何动作",
};

export const enOpLabels: Record<string, string> = {};

// ---------------------------------------------------------------------------
// Primary / advanced / hidden field lookup
// ---------------------------------------------------------------------------

export const PRIMARY_FIELDS_BY_NODE_TYPE: Record<string, string[]> = {
  "trigger.event": ["event_type"],
  "trigger.webhook": ["path"],
  "trigger.manual": [],
  "trigger.schedule": ["interval_seconds"],
  "ai.task": ["instructions", "mode"],
  "tool.query": ["surface_keys"],
  "apply.action": ["surface_key"],
  "approval.review": [],
  "operation.capability": ["operation_key"],
  "flow.condition": ["expression"],
  "flow.delay": ["delay_seconds"],
  "flow.poll": ["operation_key", "interval_seconds"],
  "flow.wait_for_event": ["event_type"],
  "notification.webhook": ["linked_subscription_ids", "format_requirements"],
};

export const ALWAYS_ADVANCED_FIELDS = new Set([
  "output_schema",
  "input_mappings",
  "argument_mappings",
  "mappings",
  "model_overrides",
  "retry_policy",
  "example_config",
]);

export const HIDDEN_FIELDS_BY_NODE_TYPE: Record<string, string[]> = {
  "trigger.event": ["target_type", "matched_events"],
  "ai.task": [
    "mode",
    "loop_max_rounds",
    "tool_usage_mode",
    "minimum_tool_calls",
    "input_slots",
    "input_contract",
    "tool_contract",
    "output_contract",
  ],
  "approval.review": ["approval_type", "mode", "required_from_path", "message_path", "force"],
  "notification.webhook": ["event_type"],
  "operation.capability": ["risk_level"],
};

// ---------------------------------------------------------------------------
// Utility functions
// ---------------------------------------------------------------------------

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

import { Position } from "@xyflow/react";

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

export function deriveWorkflowSummary(
  name: string,
  graph: AgentWorkflowGraph,
  triggerBindings: AgentWorkflowTriggerBinding[],
) {
  const operationNodes = graph.nodes.filter((node) => node.type.startsWith("operation."));
  const actionNodes = graph.nodes.filter((node) => node.type === "apply.action");
  const highRiskOperationCount = operationNodes.filter(
    (node) => String((node.config || {}).risk_level || "").toLowerCase() === "high",
  ).length;
  return {
    trigger_labels: triggerBindings.map((item) => item.label),
    node_count: graph.nodes.length,
    operation_count: operationNodes.length + actionNodes.length,
    high_risk_operation_count: highRiskOperationCount,
    narrative: `${name} · ${graph.nodes.length} nodes`,
  };
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

export function latestDeliveriesBySubscription(deliveries: import("@serino/api-client/models").WebhookDeliveryRead[]) {
  const map = new Map<string, import("@serino/api-client/models").WebhookDeliveryRead>();
  for (const item of deliveries) {
    if (!map.has(item.subscription_id)) {
      map.set(item.subscription_id, item);
    }
  }
  return map;
}

export function jsonFieldKey(nodeId: string, field: string) {
  return `${nodeId}:${field}`;
}

export function humanizeFieldName(key: string) {
  return key
    .replace(/_/g, " ")
    .replace(/\./g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
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

export function friendlyOperationLabel(key: string, catalog: AgentWorkflowCatalog | undefined, lang: Lang = "zh") {
  const op = catalog?.operation_catalog?.find((o) => o.key === key);
  if (op?.label) return op.label;
  const surface = catalog?.readonly_tools?.find((item) => item.key === key);
  if (surface?.label) return surface.label;
  const actionSurface = catalog?.workflow_local_action_surfaces?.find((item) => item.key === key);
  if (actionSurface?.label) return actionSurface.label;
  const map = lang === "zh" ? zhOpLabels : enOpLabels;
  return map[key] ?? key;
}

export function suggestedMappingPath(
  paramName: string,
  source: string,
  targetType: string | null | undefined,
  operation: AgentWorkflowCatalogOperation | null | undefined,
) {
  const normalized = paramName.toLowerCase();
  if (operation?.input_schema) {
    const props = operation.input_schema.properties;
    if (props && typeof props === "object" && !Array.isArray(props)) {
      const schemaProps = props as Record<string, unknown>;
      if (normalized in schemaProps && source === "context_payload") {
        return normalized;
      }
    }
  }
  if (source === "context_payload") {
    if (normalized === "comment_id") return "comment_id";
    if (normalized === "entry_id") return "entry_id";
    if (normalized === "content_id" || normalized === "item_id") return "content_id";
    if (normalized === "content_type") return "content_type";
    if (normalized === "slug" || normalized === "content_slug") return "content_slug";
    if (normalized === "email") return "email";
    if (normalized === "author_name") return "author_name";
  }
  if (source === "latest_ai") {
    if (normalized === "action") return "action";
    if (normalized === "reason") return "summary";
    if (normalized === "route") return "route";
  }
  if (source === "approval") {
    if (normalized === "action") return "action";
    if (normalized === "reason") return "reason";
  }
  if (source === "result_payload") {
    if (normalized === "action") return "action";
  }
  if (source === "inputs") {
    if (normalized === "content_id" || normalized === "item_id") return "content_id";
    if (normalized === "feed_id") return "feed_id";
    if (normalized === "email") return "email";
  }
  if (normalized === "target_id") return "target_id";
  if (normalized === "comment_id" && targetType === "comment") return "comment_id";
  if (normalized === "entry_id" && targetType === "guestbook") return "entry_id";
  return "";
}

export function autoMappingHint(
  paramName: string,
  targetType: string | null | undefined,
  lang: Lang,
  operation: AgentWorkflowCatalogOperation | null | undefined,
) {
  const normalized = paramName.toLowerCase();
  if (operation?.input_schema) {
    const props = operation.input_schema.properties;
    if (props && typeof props === "object" && !Array.isArray(props)) {
      const schemaProps = props as Record<string, Record<string, unknown>>;
      const propDef = schemaProps[paramName] || schemaProps[normalized];
      if (propDef?.description && typeof propDef.description === "string") {
        return propDef.description;
      }
    }
  }
  if (normalized === "action") {
    return lang === "zh" ? "默认会优先使用人工审批结果里的动作，其次使用最近一次 AI 的动作建议。" : "Defaults to approval action, then the latest AI action.";
  }
  if (normalized === "reason") {
    return lang === "zh" ? "默认会优先使用人工审批备注，其次使用最近一次 AI 的摘要。" : "Defaults to approval reason, then the latest AI summary.";
  }
  if (normalized === "comment_id" && targetType === "comment") {
    return lang === "zh" ? "默认会自动带入当前评论 ID。" : "Defaults to the current comment ID.";
  }
  if (normalized === "entry_id" && targetType === "guestbook") {
    return lang === "zh" ? "默认会自动带入当前留言 ID。" : "Defaults to the current guestbook entry ID.";
  }
  if ((normalized === "content_id" || normalized === "item_id") && targetType === "content") {
    return lang === "zh" ? "默认会自动带入当前内容 ID。" : "Defaults to the current content ID.";
  }
  return lang === "zh" ? "默认会先尝试使用系统上下文和已有结果自动补足。" : "Defaults to built-in workflow context when possible.";
}

export function friendlyFieldLabel(key: string, lang: Lang, schema?: Record<string, unknown>) {
  if (schema?.title && typeof schema.title === "string") {
    const title = schema.title.trim();
    const hasChinese = /[\u4e00-\u9fff]/.test(title);
    if (lang === "en" || hasChinese) {
      return title;
    }
  }
  const zh: Record<string, string> = {
    event_type: "触发事件",
    target_type: "目标类型",
    path: "Webhook 路径",
    secret: "Webhook 密钥",
    interval_seconds: "轮询/定时间隔",
    delay_seconds: "延迟秒数",
    timeout_seconds: "超时时间",
    cron: "Cron 表达式",
    instructions: "任务说明",
    system_prompt: "系统提示词",
    input_mode: "输入给 AI 的范围",
    output_mode: "输出模式",
    route_path: "路由字段",
    output_schema: "输出 JSON Schema",
    output_fields: "输出字段",
    input_mappings: "输入映射",
    argument_mappings: "参数映射",
    operation_key: "操作目录",
    approval_type: "审批类型",
    mode: "模式",
    required_from_path: "触发审批条件路径",
    message_path: "审批消息路径",
    linked_subscription_ids: "关联 Webhook",
    format_requirements: "格式要求",
    event_types: "事件列表",
    mappings: "字段映射",
    store_as: "保存为",
    risk_level: "风险等级",
    surface_key: "工具面",
    surface_keys: "只读工具",
    max_attempts: "最大尝试次数",
    success_expression: "成功条件",
    until_path: "恢复时间路径",
    content: "备注内容",
    force: "强制审批",
  };
  const en: Record<string, string> = {
    event_type: "Trigger Event",
    target_type: "Target Type",
    path: "Webhook Path",
    secret: "Webhook Secret",
    interval_seconds: "Interval Seconds",
    delay_seconds: "Delay Seconds",
    timeout_seconds: "Timeout Seconds",
    cron: "Cron Expression",
    instructions: "Instructions",
    system_prompt: "System Prompt",
    input_mode: "AI Input Scope",
    output_mode: "Output Mode",
    route_path: "Route Field",
    output_schema: "Output JSON Schema",
    output_fields: "Output Fields",
    input_mappings: "Input Mappings",
    argument_mappings: "Argument Mappings",
    operation_key: "Operation Catalog",
    approval_type: "Approval Type",
    mode: "Mode",
    required_from_path: "Required From Path",
    message_path: "Message Path",
    linked_subscription_ids: "Linked Webhooks",
    format_requirements: "Format Requirements",
    event_types: "Event Types",
    mappings: "Mappings",
    store_as: "Store As",
    risk_level: "Risk Level",
    surface_key: "Tool Surface",
    surface_keys: "Readonly Tools",
    max_attempts: "Max Attempts",
    success_expression: "Success Expression",
    until_path: "Resume Time Path",
    content: "Note Content",
    force: "Force Approval",
  };
  return (lang === "zh" ? zh[key] : en[key]) || humanizeFieldName(key);
}

export function friendlySchemaTypeLabel(schema: Record<string, unknown> | undefined, lang: Lang) {
  const type = normalizedSchemaType(schema || {});
  const zh: Record<string, string> = {
    string: "文本",
    boolean: "开关判断",
    integer: "整数",
    number: "数字",
    array: "列表",
    object: "结构化对象",
  };
  const en: Record<string, string> = {
    string: "Text",
    boolean: "True/False",
    integer: "Integer",
    number: "Number",
    array: "List",
    object: "Structured object",
  };
  return (lang === "zh" ? zh[type] : en[type]) || type;
}

export function friendlyFieldExplanation(key: string, lang: Lang, schema?: Record<string, unknown>) {
  const rawDescription =
    schema?.description && typeof schema.description === "string"
      ? schema.description.trim()
      : "";
  const looksEnglishHeavy =
    /[A-Za-z]/.test(rawDescription) && !/[\u4e00-\u9fff]/.test(rawDescription);
  const zh: Record<string, string> = {
    summary: "给下游看的简短总结。",
    reason: "说明为什么这么判断。",
    action: "告诉下游下一步做什么。",
    decision: "告诉下游最终判断结果。",
    needs_approval: "说明是否要转人工。",
    priority: "说明紧急程度。",
    message: "给下游使用的完整消息。",
    title: "给下游展示的标题。",
    content: "给下游使用的正文。",
    status: "当前这一步的状态。",
    surface_key: "选择这一步要执行的动作。",
    surface_keys: "选择挂给 AI 的只读工具。",
    event_type: "选择什么事件会触发流程。",
    operation_key: "选择这一步要调用的平台能力。",
    approval_type: "选择审批类型。",
    mode: "控制这一步用什么方式运行。",
    required_from_path: "用哪个字段判断是否需要审批。",
    message_path: "用哪个字段给审批页显示说明。",
    input_selector: "决定执行节点从哪里拿输入。",
    argument_mappings: "决定每个参数从哪里取值。",
    linked_subscription_ids: "选择要发送到哪些通知订阅。",
    format_requirements: "补充这条通知希望 AI 输出成什么样。",
  };
  const en: Record<string, string> = {
    summary: "A short summary for downstream nodes so they can understand this result quickly.",
    reason: "Why this decision was made, useful for follow-up actions or human review.",
    action: "Tells the downstream step which action should be executed next.",
    decision: "The final decision, such as approve, reject, or observe.",
    needs_approval: "Whether this item should be sent to human review before continuing.",
    priority: "How urgent this item is, so downstream steps can prioritize it.",
    message: "A complete message for downstream use or notification delivery.",
    title: "A title for downstream display or reference.",
    content: "The main content body for downstream consumption.",
    status: "The current status used by downstream conditions or steps.",
  };
  if (rawDescription) {
    if (!(lang === "zh" && looksEnglishHeavy)) {
      return rawDescription;
    }
    if (zh[key]) {
      return zh[key];
    }
  }
  return (lang === "zh" ? zh[key] : en[key]) ||
    (lang === "zh"
      ? "这是这一步要填写的一项信息。"
      : "A structured value that this step passes to downstream nodes.");
}

export function friendlyFieldCompactLabel(key: string, lang: Lang) {
  const zh: Record<string, string> = {
    summary: "总结",
    reason: "理由",
    action: "下一步动作",
    decision: "判断结果",
    needs_approval: "是否转人工",
    priority: "优先级",
    message: "通知内容",
    title: "标题",
    content: "内容",
    status: "状态",
  };
  const en: Record<string, string> = {
    summary: "Summary",
    reason: "Reason",
    action: "Next Action",
    decision: "Decision",
    needs_approval: "Needs Approval",
    priority: "Priority",
    message: "Message",
    title: "Title",
    content: "Content",
    status: "Status",
  };
  return (lang === "zh" ? zh[key] : en[key]) || friendlyFieldLabel(key, lang);
}

export function friendlyFieldCompactPurpose(key: string, lang: Lang) {
  const zh: Record<string, string> = {
    summary: "让下游快速看懂这次结果",
    reason: "说明为什么这样判断",
    action: "告诉下游要执行什么处理",
    decision: "给出最终判断",
    needs_approval: "决定是否先转人工审核",
    priority: "告诉下游先处理哪一条",
    message: "给通知或下游直接使用",
    title: "给下游展示或引用",
    content: "给下游直接使用的正文",
    status: "告诉下游当前进展",
  };
  const en: Record<string, string> = {
    summary: "Helps downstream understand the result quickly",
    reason: "Explains why this decision was made",
    action: "Tells downstream what to do next",
    decision: "Provides the final judgment",
    needs_approval: "Decides whether human review is needed",
    priority: "Tells downstream what to handle first",
    message: "Ready for notification or direct downstream use",
    title: "Used for downstream display or reference",
    content: "Main body for downstream use",
    status: "Tells downstream the current progress",
  };
  return (lang === "zh" ? zh[key] : en[key]) ||
    (lang === "zh" ? "交给下游使用的一项信息" : "A value for downstream use");
}

export function normalizedSchemaType(schema: Record<string, unknown>) {
  const rawType = schema.type;
  if (typeof rawType === "string") return rawType;
  if (Array.isArray(rawType)) {
    return rawType.find((item) => item !== "null") || "string";
  }
  if (schema.enum) return "string";
  return "string";
}

export function jsonInputValue(value: unknown) {
  return JSON.stringify(value ?? null, null, 2);
}

export function schemaProperties(schema: Record<string, unknown>) {
  const properties = schema.properties;
  if (!properties || typeof properties !== "object" || Array.isArray(properties)) {
    return [];
  }
  return Object.entries(properties as Record<string, Record<string, unknown>>);
}

export function schemaPaths(schema: Record<string, unknown> | null | undefined, prefix = ""): string[] {
  if (!schema || typeof schema !== "object") return [];
  const type = normalizedSchemaType(schema);
  const properties = schema.properties;
  if (type !== "object" || !properties || typeof properties !== "object" || Array.isArray(properties)) {
    return prefix ? [prefix] : [];
  }
  const paths: string[] = [];
  for (const [key, value] of Object.entries(properties as Record<string, Record<string, unknown>>)) {
    const nextPrefix = prefix ? `${prefix}.${key}` : key;
    const nested = schemaPaths(value, nextPrefix);
    if (nested.length > 0) {
      paths.push(...nested);
    } else {
      paths.push(nextPrefix);
    }
  }
  return paths;
}

export function fieldProperties(definition: AgentWorkflowCatalogNodeType | undefined) {
  const properties = definition?.config_schema?.properties;
  if (!properties || typeof properties !== "object" || Array.isArray(properties)) {
    return [];
  }
  return Object.entries(properties as Record<string, Record<string, unknown>>);
}

export function nodeMappings(config: Record<string, unknown>, key: "argument_mappings" | "input_mappings") {
  const raw = config[key];
  if (!Array.isArray(raw)) return [];
  return raw.filter((item): item is Record<string, unknown> => typeof item === "object" && item !== null);
}

export function getInputContract(config: Record<string, unknown>): InputContract {
  return (config?.input_contract as InputContract) ?? { fields: [] };
}

export function getOutputContract(config: Record<string, unknown>): OutputContract {
  return (config?.output_contract as OutputContract) ?? { output_schema: {}, route: null };
}

export function getAiTaskShellConfig(config: Record<string, unknown>): AiTaskShellConfig {
  const rawSlots =
    config?.input_slots && typeof config.input_slots === "object" && !Array.isArray(config.input_slots)
      ? (config.input_slots as Record<string, { note?: string }>)
      : {};
  const input_slots = Object.fromEntries(
    AI_TASK_INPUT_PORT_IDS.map((portId) => [
      portId,
      {
        note: String(rawSlots[portId]?.note || ""),
      },
    ]),
  );
  const mode = String(config?.mode || "direct") === "loop" ? "loop" : "direct";
  const loopMaxRounds = Number(config?.loop_max_rounds || 6);
  return {
    mode,
    loop_max_rounds: Number.isFinite(loopMaxRounds) && loopMaxRounds > 0 ? loopMaxRounds : 6,
    input_slots,
  };
}

export function runtimePolicyDefaults(policy: AgentWorkflowRuntimePolicy | null | undefined): AgentWorkflowRuntimePolicy {
  return {
    approval_mode: policy?.approval_mode || "risk_based",
    allow_high_risk_without_approval: Boolean(policy?.allow_high_risk_without_approval),
    max_steps: policy?.max_steps || 80,
    retry_policy: policy?.retry_policy || {},
    default_model: policy?.default_model ?? null,
  };
}

export function syncTriggerConfigForEvent(
  currentConfig: Record<string, unknown>,
  option: import("@/pages/automation/api").AgentWorkflowCatalogOption | undefined,
) {
  if (!option) {
    return currentConfig;
  }
  const targetTypes = option.target_types || [];
  return {
    ...currentConfig,
    event_type: option.value,
    matched_events: option.value ? [option.value] : [],
    target_type: targetTypes.length === 1 ? targetTypes[0] : null,
  };
}
