import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import {
  addEdge,
  applyEdgeChanges,
  applyNodeChanges,
  type Connection,
  type EdgeChange,
  MarkerType,
  type NodeChange,
  type OnEdgesChange,
  type OnNodesChange,
} from "@xyflow/react";
import {
  type AgentWorkflow,
  type AgentWorkflowCatalog,
  type AgentWorkflowCatalogNodeType,
  type AgentWorkflowRuntimePolicy,
  type DeriveAiSchemaResult,
  deriveAiOutputSchema,
  updateAgentWorkflow,
  validateAgentWorkflow,
} from "@/pages/automation/api";
import type { Lang } from "@/i18n";
import { toast } from "sonner";
import {
  AI_TASK_INPUT_PORT_IDS,
  AI_TASK_MOUNT_PORT_IDS,
  AI_TASK_OUTPUT_PORT_IDS,
  type WorkflowCanvasEdge,
  type WorkflowCanvasNode,
  type CopyShape,
  WORKFLOWS_QUERY_KEY,
  CATEGORY_ORDER_FALLBACK,
  cloneJson,
  workflowGraphToCanvas,
  canvasToGraph,
  deriveTriggerBindings,
  deriveWorkflowSummary,
  nextNodeId,
  nextNodePosition,
  friendlyNodeTypeLabel,
  runtimePolicyDefaults,
  isDataEdge,
  isToolEdge,
  getInputContract,
  getOutputContract,
} from "./workflow-editor-types";

const SKETCH_NODE_TYPES = new Set([
  "trigger.event",
  "trigger.webhook",
  "trigger.manual",
  "trigger.schedule",
  "flow.condition",
  "flow.delay",
  "flow.poll",
  "flow.wait_for_event",
  "ai.task",
  "tool.query",
  "apply.action",
  "approval.review",
  "notification.webhook",
]);

const COMMON_NODE_TYPE_ORDER = [
  "trigger.event",
  "ai.task",
  "approval.review",
  "notification.webhook",
] as const;

const COMMON_NODE_TYPES = new Set([
  "trigger.event",
  "trigger.webhook",
  "trigger.manual",
  "trigger.schedule",
  "ai.task",
  "approval.review",
  "notification.webhook",
]);

const GENERIC_TRIGGER_DEFAULT_TYPE = "trigger.event";

type SelectedEntity =
  | { type: "node"; id: string }
  | { type: "edge"; id: string }
  | null;

interface UseWorkflowEditorStateParams {
  open: boolean;
  workflow: AgentWorkflow | null;
  mode?: "edit" | "sketch";
  lang: Lang;
  copy: CopyShape;
  catalog: AgentWorkflowCatalog | undefined;
}

export function useWorkflowEditorState({
  open,
  workflow,
  mode = "edit",
  lang,
  copy,
  catalog,
}: UseWorkflowEditorStateParams) {
  const queryClient = useQueryClient();
  const isSketchMode = mode === "sketch";

  const [nodes, setNodes] = useState<WorkflowCanvasNode[]>([]);
  const [edges, setEdges] = useState<WorkflowCanvasEdge[]>([]);
  const [selected, setSelected] = useState<SelectedEntity>(null);
  const [viewport, setViewport] = useState({ x: 0, y: 0, zoom: 1 });
  const [showPalette, setShowPalette] = useState(false);
  const [showInspector, setShowInspector] = useState(true);
  const [showSurfaceAssistant, setShowSurfaceAssistant] = useState(false);

  const [workflowName, setWorkflowName] = useState("");
  const [workflowDescription, setWorkflowDescription] = useState("");
  const [workflowEnabled, setWorkflowEnabled] = useState(true);
  const [runtimePolicy, setRuntimePolicy] = useState<AgentWorkflowRuntimePolicy>(
    runtimePolicyDefaults(null),
  );

  const [jsonDrafts, setJsonDrafts] = useState<Record<string, string>>({});
  const [jsonErrors, setJsonErrors] = useState<Record<string, string>>({});

  const previousWorkflowKeyRef = useRef<string | null>(null);
  const deriveDebounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [derivedSchema, setDerivedSchema] = useState<DeriveAiSchemaResult | null>(null);
  const [derivingSchema, setDerivingSchema] = useState(false);

  const visibleNodeTypes = useMemo(
    () =>
      (catalog?.node_types || []).filter(
        (item) => !isSketchMode || SKETCH_NODE_TYPES.has(item.type),
      ),
    [catalog?.node_types, isSketchMode],
  );

  const registry = useMemo(() => {
    const map = new Map<string, AgentWorkflowCatalogNodeType>();
    for (const item of visibleNodeTypes) {
      map.set(item.type, item);
    }
    return map;
  }, [visibleNodeTypes]);

  const paletteGroups = useMemo(() => {
    const toDisplayItem = (
      item: AgentWorkflowCatalogNodeType | undefined,
    ): AgentWorkflowCatalogNodeType | null => {
      if (!item) return null;
      if (!item.type.startsWith("trigger.")) {
        return item;
      }
      return {
        ...item,
        label: lang === "zh" ? "触发器" : "Trigger",
        description:
          lang === "zh"
            ? "先放一个统一触发器节点，再在属性面板里选择具体触发方式。"
            : "Add one generic trigger node first, then choose the specific trigger type in the inspector.",
      };
    };

    const defaultTrigger = visibleNodeTypes.find(
      (item) => item.type === GENERIC_TRIGGER_DEFAULT_TYPE,
    );
    const commonItems = COMMON_NODE_TYPE_ORDER.map((type) =>
      type === GENERIC_TRIGGER_DEFAULT_TYPE
        ? toDisplayItem(defaultTrigger)
        : visibleNodeTypes.find((item) => item.type === type) || null,
    ).filter((item): item is AgentWorkflowCatalogNodeType => item !== null);

    const grouped = new Map<string, AgentWorkflowCatalogNodeType[]>();
    for (const item of visibleNodeTypes) {
      if (COMMON_NODE_TYPES.has(item.type)) {
        continue;
      }
      const list = grouped.get(item.category) || [];
      list.push(item);
      grouped.set(item.category, list);
    }

    const catalogOrder: string[] = [];
    const seen = new Set<string>();
    for (const item of visibleNodeTypes) {
      if (!seen.has(item.category)) {
        seen.add(item.category);
        catalogOrder.push(item.category);
      }
    }
    for (const category of CATEGORY_ORDER_FALLBACK) {
      if (!seen.has(category) && grouped.has(category)) {
        catalogOrder.push(category);
      }
    }

    return [
      ...(commonItems.length > 0
        ? [{ category: "common", items: commonItems }]
        : []),
      ...catalogOrder.map((category) => ({
        category,
        items: (grouped.get(category) || []).sort((a, b) =>
          a.label.localeCompare(b.label),
        ),
      })),
    ].filter((group) => group.items.length > 0);
  }, [lang, visibleNodeTypes]);

  const operationCatalog = useMemo(
    () => catalog?.operation_catalog || [],
    [catalog?.operation_catalog],
  );

  const selectedNode = useMemo(
    () =>
      selected?.type === "node"
        ? nodes.find((node) => node.id === selected.id) ?? null
        : null,
    [nodes, selected],
  );

  const selectedEdge = useMemo(
    () =>
      selected?.type === "edge"
        ? edges.find((edge) => edge.id === selected.id) ?? null
        : null,
    [edges, selected],
  );

  const selectedNodeDefinition = selectedNode
    ? registry.get(selectedNode.data.nodeType)
    : undefined;

  const selectedOperation = useMemo(() => {
    if (!selectedNode || !selectedNode.data.nodeType.startsWith("operation.")) {
      return null;
    }
    const operationType = selectedNode.data.nodeType.split(".", 2)[1];
    const operationKey = String(selectedNode.data.config.operation_key || "");
    return (
      operationCatalog.find(
        (item) =>
          item.operation_type === operationType && item.key === operationKey,
      ) || null
    );
  }, [operationCatalog, selectedNode]);

  const selectedOperationExamples = useMemo(
    () => (selectedOperation?.examples || []).slice(0, 1),
    [selectedOperation],
  );

  const selectedSourceNodeDefinition = useMemo(() => {
    if (!selectedEdge) return null;
    const sourceNode = nodes.find((node) => node.id === selectedEdge.source);
    return sourceNode ? registry.get(sourceNode.data.nodeType) || null : null;
  }, [nodes, registry, selectedEdge]);

  const graphPreview = useMemo(
    () => canvasToGraph(nodes, edges, viewport),
    [nodes, edges, viewport],
  );

  const triggerBindingsPreview = useMemo(
    () => deriveTriggerBindings(nodes),
    [nodes],
  );

  const summaryPreview = useMemo(
    () => deriveWorkflowSummary(workflowName, graphPreview, triggerBindingsPreview),
    [graphPreview, triggerBindingsPreview, workflowName],
  );

  const applyWorkflowState = useCallback((nextWorkflow: AgentWorkflow) => {
    const canvas = workflowGraphToCanvas(nextWorkflow.graph);
    setNodes(canvas.nodes);
    setEdges(canvas.edges);
    setViewport(canvas.viewport);
    setWorkflowName(nextWorkflow.name);
    setWorkflowDescription(nextWorkflow.description);
    setWorkflowEnabled(nextWorkflow.enabled);
    setRuntimePolicy(runtimePolicyDefaults(nextWorkflow.runtime_policy));
    setSelected(null);
    setShowPalette(false);
    setShowInspector(true);
    setJsonDrafts({});
    setJsonErrors({});
    previousWorkflowKeyRef.current = nextWorkflow.key;
  }, []);

  useEffect(() => {
    if (!workflow || !open) return;
    const workflowChanged = previousWorkflowKeyRef.current !== workflow.key;
    if (!workflowChanged && previousWorkflowKeyRef.current != null) return;
    applyWorkflowState(workflow);
  }, [applyWorkflowState, open, workflow]);

  useEffect(() => {
    if (!open) {
      previousWorkflowKeyRef.current = null;
    }
  }, [open]);

  const onNodesChange: OnNodesChange<WorkflowCanvasNode> = useCallback(
    (changes: NodeChange<WorkflowCanvasNode>[]) => {
      if (
        changes.some(
          (change) =>
            change.type === "remove" &&
            selected?.type === "node" &&
            selected.id === change.id,
        )
      ) {
        setSelected(null);
      }
      setNodes((current) => applyNodeChanges(changes, current));
    },
    [selected],
  );

  const onEdgesChange: OnEdgesChange<WorkflowCanvasEdge> = useCallback(
    (changes: EdgeChange<WorkflowCanvasEdge>[]) => {
      if (
        changes.some(
          (change) =>
            change.type === "remove" &&
            selected?.type === "edge" &&
            selected.id === change.id,
        )
      ) {
        setSelected(null);
      }
      setEdges((current) => applyEdgeChanges(changes, current));
    },
    [selected],
  );

  const onConnect = useCallback(
    (connection: Connection) => {
      const sourceNode = nodes.find((node) => node.id === connection.source);
      const targetNode = nodes.find((node) => node.id === connection.target);
      if (!sourceNode || !targetNode) return;

      const sourceDef = registry.get(sourceNode.data.nodeType);
      const targetDef = registry.get(targetNode.data.nodeType);
      let sourceHandle =
        connection.sourceHandle || sourceDef?.output_ports?.[0]?.id || null;
      let targetHandle =
        connection.targetHandle || targetDef?.input_ports?.[0]?.id || null;

      const sourceIsToolNode = sourceNode.data.nodeType === "tool.query";
      const sourceIsActionNode = sourceNode.data.nodeType === "apply.action";
      const targetIsAiTask = targetNode.data.nodeType === "ai.task";
      const sourceIsTriggerNode = sourceNode.data.nodeType.startsWith("trigger.");
      const sourceIsApprovalNode = sourceNode.data.nodeType === "approval.review";
      const targetSupportsAiMount = Boolean(
        targetDef?.input_ports?.some((port) => AI_TASK_MOUNT_PORT_IDS.includes(port.id as (typeof AI_TASK_MOUNT_PORT_IDS)[number])),
      );
      const occupiedMountHandles = new Set(
        edges
          .filter((edge) => edge.target === targetNode.id)
          .map((edge) => edge.targetHandle || "")
          .filter((handle) =>
            AI_TASK_MOUNT_PORT_IDS.includes(handle as (typeof AI_TASK_MOUNT_PORT_IDS)[number]),
          ),
      );
      const nextFreeMountHandle =
        AI_TASK_MOUNT_PORT_IDS.find((portId) => !occupiedMountHandles.has(portId)) || null;

      if ((sourceIsToolNode || sourceIsActionNode || sourceIsTriggerNode || sourceIsApprovalNode) && targetIsAiTask) {
        if (!nextFreeMountHandle) {
          toast.error(
            lang === "zh"
              ? "这个 AI Task 的 3 个额外挂载口已经占满了。"
              : "All 3 AI task mount ports are already occupied.",
          );
          return;
        }
        if (sourceIsToolNode) {
          sourceHandle = "tool";
        } else if (sourceIsActionNode) {
          sourceHandle = sourceHandle || sourceDef?.output_ports?.[0]?.id || "result";
        } else if (sourceIsApprovalNode) {
          sourceHandle = "approval";
        }
        if (targetSupportsAiMount) {
          targetHandle = nextFreeMountHandle;
        }
      } else if (targetIsAiTask && !targetHandle) {
        const occupied = new Set(
          edges
            .filter((edge) => edge.target === targetNode.id)
            .map((edge) => edge.targetHandle || ""),
        );
        const freeInputHandle = AI_TASK_INPUT_PORT_IDS.find(
          (portId) => !occupied.has(portId),
        );
        if (!freeInputHandle) {
          toast.error(
            lang === "zh"
              ? "这个 AI Task 的 3 个输入口已经占满了。"
              : "All 3 AI task input ports are already occupied.",
          );
          return;
        }
        targetHandle = freeInputHandle;
      }

      const isToolMount =
        sourceIsToolNode ||
        (targetHandle !== null &&
          AI_TASK_MOUNT_PORT_IDS.includes(
            targetHandle as (typeof AI_TASK_MOUNT_PORT_IDS)[number],
          ) &&
          sourceIsToolNode);
      const isActionMount =
        sourceIsActionNode &&
        targetHandle !== null &&
        AI_TASK_MOUNT_PORT_IDS.includes(
          targetHandle as (typeof AI_TASK_MOUNT_PORT_IDS)[number],
        );
      const isGenericMount =
        targetHandle !== null &&
        AI_TASK_MOUNT_PORT_IDS.includes(
          targetHandle as (typeof AI_TASK_MOUNT_PORT_IDS)[number],
        );

      if (sourceNode.data.nodeType === "ai.task" && !isToolMount && !isActionMount && !connection.sourceHandle) {
        const occupied = new Set(
          edges
            .filter((edge) => edge.source === sourceNode.id)
            .map((edge) => edge.sourceHandle || ""),
        );
        const requestedOutputHandle =
          sourceHandle &&
          AI_TASK_OUTPUT_PORT_IDS.includes(
            sourceHandle as (typeof AI_TASK_OUTPUT_PORT_IDS)[number],
          )
            ? sourceHandle
            : null;
        const freeOutputHandle =
          (requestedOutputHandle && !occupied.has(requestedOutputHandle)
            ? requestedOutputHandle
            : null) ||
          AI_TASK_OUTPUT_PORT_IDS.find((portId) => !occupied.has(portId));
        if (!freeOutputHandle) {
          toast.error(
            lang === "zh"
              ? "这个 AI Task 的 3 个输出口已经占满了。"
              : "All 3 AI task output ports are already occupied.",
          );
          return;
        }
        sourceHandle = freeOutputHandle;
      }

      if (isToolMount && (!sourceIsToolNode || !targetIsAiTask)) {
        toast.error(
          lang === "zh"
            ? "只读工具只能从工具节点挂载到 AI Task 的额外挂载口。"
            : "Readonly tools can only mount from a tool node into an AI task mount port.",
        );
        return;
      }

      if (isActionMount && (!sourceIsActionNode || !targetIsAiTask)) {
        toast.error(
          lang === "zh"
            ? "执行动作只能从执行节点挂载到 AI Task 的额外挂载口。"
            : "Actions can only mount from an action node into an AI task mount port.",
        );
        return;
      }

      if (!isToolMount && sourceNode.data.nodeType === "tool.query") {
        toast.error(
          lang === "zh"
            ? "工具节点不能参与普通数据流，请连到 AI Task 的额外挂载口。"
            : "Tool nodes do not participate in data flow. Connect them to an AI task mount port.",
        );
        return;
      }

      if (!isActionMount && sourceNode.data.nodeType === "apply.action" && targetIsAiTask) {
        toast.error(
          lang === "zh"
            ? "执行动作挂载失败，请换一个 AI 额外挂载口。"
            : "Action mount failed. Use an available AI mount port.",
        );
        return;
      }

      if (sourceIsApprovalNode && targetIsAiTask && !targetSupportsAiMount) {
        toast.error(
          lang === "zh"
            ? "审批节点只能连接到支持额外挂载口的节点顶部接口。"
            : "Approval nodes can only connect to a node that exposes generic mount ports.",
        );
        return;
      }

      const sourcePort = sourceDef?.output_ports?.find(
        (port) => port.id === sourceHandle,
      );
      const autoMatch =
        sourcePort?.match_values?.length === 1
          ? sourcePort.match_values[0]
          : "";
      const kind = isToolMount
        ? "tool"
        : isActionMount
          ? "action"
        : (isGenericMount && sourceIsTriggerNode) ||
            sourceNode.data.nodeType.startsWith("trigger.")
          ? "trigger"
          : (isGenericMount && sourceIsApprovalNode) ||
              sourceHandle === "route" ||
              targetHandle === "control"
            ? "control"
            : "data";

      setEdges((current) => {
        if (
          sourceNode.data.nodeType === "ai.task" &&
          sourceHandle &&
          AI_TASK_OUTPUT_PORT_IDS.includes(
            sourceHandle as (typeof AI_TASK_OUTPUT_PORT_IDS)[number],
          ) &&
          current.some(
            (edge) =>
              edge.source === sourceNode.id &&
              (edge.sourceHandle || null) === sourceHandle,
          )
        ) {
          toast.error(
            lang === "zh"
              ? "这个 AI Task 输出口已经接入了下游，请换一个输出口。"
              : "This AI task output port is already occupied. Use a different output slot.",
          );
          return current;
        }

        if (
          targetIsAiTask &&
          targetHandle &&
          !AI_TASK_MOUNT_PORT_IDS.includes(
            targetHandle as (typeof AI_TASK_MOUNT_PORT_IDS)[number],
          ) &&
          current.some(
            (edge) =>
              edge.target === targetNode.id &&
              (edge.targetHandle || null) === targetHandle,
          )
        ) {
          toast.error(
            lang === "zh"
              ? "这个 AI Task 端口已经接入了内容，请换一个槽位。"
              : "This AI task port is already occupied. Use a different slot.",
          );
          return current;
        }

        if (
          targetIsAiTask &&
          targetHandle &&
          AI_TASK_MOUNT_PORT_IDS.includes(
            targetHandle as (typeof AI_TASK_MOUNT_PORT_IDS)[number],
          ) &&
          current.some(
            (edge) =>
              edge.target === targetNode.id &&
              (edge.targetHandle || null) === targetHandle,
          )
        ) {
          toast.error(
            lang === "zh"
              ? "这个 AI Task 的额外挂载口已经占用，请换一个槽位。"
              : "This AI task mount port is already occupied. Use a different slot.",
          );
          return current;
        }

        const duplicated = current.some(
          (edge) =>
            edge.source === connection.source &&
            edge.target === connection.target &&
            (edge.sourceHandle || null) === sourceHandle &&
            (edge.targetHandle || null) === targetHandle,
        );
        if (duplicated) {
          return current;
        }

        return addEdge(
          {
            ...connection,
            id: `edge-${connection.source}-${connection.target}-${Date.now()}`,
            sourceHandle,
            targetHandle,
            type: "smoothstep",
            markerEnd: { type: MarkerType.ArrowClosed },
            data: {
              variant: "default",
              config: { ...(autoMatch ? { match: autoMatch } : {}), kind },
            },
          },
          current,
        ) as WorkflowCanvasEdge[];
      });
    },
    [edges, lang, nodes, registry],
  );

  const addNode = useCallback(
    (definition: AgentWorkflowCatalogNodeType) => {
      const createdId = nextNodeId(definition.type, nodes);
      const isGenericTrigger =
        definition.type === GENERIC_TRIGGER_DEFAULT_TYPE &&
        (definition.label === "触发器" || definition.label === "Trigger");

      setNodes((current) => [
        ...current.map((node) => ({ ...node, selected: false })),
        {
          id: createdId,
          type: "workflowNode",
          position: nextNodePosition(current),
          data: {
            nodeType: definition.type,
            label: isGenericTrigger
              ? friendlyNodeTypeLabel(definition.type, catalog, lang)
              : definition.label ||
                friendlyNodeTypeLabel(definition.type, catalog, lang),
            config: cloneJson(definition.default_config || {}),
          },
          selected: true,
        },
      ]);
      setSelected({ type: "node", id: createdId });
    },
    [catalog, lang, nodes],
  );

  const updateSelectedNode = useCallback(
    (updater: (node: WorkflowCanvasNode) => WorkflowCanvasNode) => {
      if (!selectedNode) return;
      setNodes((current) =>
        current.map((node) => (node.id === selectedNode.id ? updater(node) : node)),
      );
    },
    [selectedNode],
  );

  const setNodeConfig = useCallback(
    (key: string, value: unknown) => {
      updateSelectedNode((node) => ({
        ...node,
        data: { ...node.data, config: { ...node.data.config, [key]: value } },
      }));
    },
    [updateSelectedNode],
  );

  const setNodeLabel = useCallback(
    (value: string) => {
      updateSelectedNode((node) => ({
        ...node,
        data: { ...node.data, label: value },
      }));
    },
    [updateSelectedNode],
  );

  const deleteSelectedNode = useCallback(() => {
    if (!selectedNode) return;
    setNodes((current) => current.filter((node) => node.id !== selectedNode.id));
    setEdges((current) =>
      current.filter(
        (edge) =>
          edge.source !== selectedNode.id && edge.target !== selectedNode.id,
      ),
    );
    setSelected(null);
  }, [selectedNode]);

  const deleteSelectedEdge = useCallback(() => {
    if (!selectedEdge) return;
    setEdges((current) => current.filter((edge) => edge.id !== selectedEdge.id));
    setSelected(null);
  }, [selectedEdge]);

  const selectedNodeId = selectedNode?.id;
  const selectedNodeType = selectedNode?.data.nodeType;

  useEffect(() => {
    if (!selectedNodeId || selectedNodeType !== "ai.task") {
      setDerivedSchema(null);
      return;
    }

    if (deriveDebounceRef.current) {
      clearTimeout(deriveDebounceRef.current);
    }

    deriveDebounceRef.current = setTimeout(() => {
      const graph = canvasToGraph(nodes, edges, viewport);
      setDerivingSchema(true);
      deriveAiOutputSchema({
        graph,
        ai_node_id: selectedNodeId,
        workflow_key: workflow?.key ?? null,
      })
        .then((result) => setDerivedSchema(result))
        .catch(() => {
          setDerivedSchema(null);
          toast.error(copy.deriveFailed);
        })
        .finally(() => setDerivingSchema(false));
    }, 600);

    return () => {
      if (deriveDebounceRef.current) {
        clearTimeout(deriveDebounceRef.current);
      }
    };
  }, [selectedNodeId, selectedNodeType, edges, nodes, viewport, copy.deriveFailed, workflow?.key]);

  const updateInputMapping = useCallback(
    (index: number, field: "field_name" | "expression", value: string) => {
      if (!selectedNode) return;
      const current = Array.isArray(selectedNode.data.config.input_mappings)
        ? [
            ...(selectedNode.data.config.input_mappings as Array<{
              field_name: string;
              expression: string;
            }>),
          ]
        : [];
      current[index] = { ...current[index], [field]: value };
      setNodeConfig("input_mappings", current);
    },
    [selectedNode, setNodeConfig],
  );

  const addInputMapping = useCallback(() => {
    if (!selectedNode) return;
    const current = Array.isArray(selectedNode.data.config.input_mappings)
      ? [
          ...(selectedNode.data.config.input_mappings as Array<{
            field_name: string;
            expression: string;
          }>),
        ]
      : [];
    current.push({ field_name: "", expression: "" });
    setNodeConfig("input_mappings", current);
  }, [selectedNode, setNodeConfig]);

  const removeInputMapping = useCallback(
    (index: number) => {
      if (!selectedNode) return;
      const current = Array.isArray(selectedNode.data.config.input_mappings)
        ? [
            ...(selectedNode.data.config.input_mappings as Array<{
              field_name: string;
              expression: string;
            }>),
          ]
        : [];
      current.splice(index, 1);
      setNodeConfig("input_mappings", current);
    },
    [selectedNode, setNodeConfig],
  );

  const upstreamNodes = useMemo(() => {
    if (!selectedNode) return [];
    return nodes.filter((node) =>
      edges.some(
        (edge) =>
          isDataEdge(edge, nodes) &&
          edge.target === selectedNode.id &&
          edge.source === node.id,
      ),
    );
  }, [selectedNode, nodes, edges]);

  const mountedToolNodes = useMemo(() => {
    if (!selectedNode) return [];
    return nodes.filter((node) =>
      edges.some(
        (edge) =>
          isToolEdge(edge, nodes) &&
          edge.target === selectedNode.id &&
          edge.source === node.id,
      ),
    );
  }, [selectedNode, nodes, edges]);

  const updateInputField = useCallback(
    (index: number, fieldKey: string, value: unknown) => {
      if (!selectedNode) return;
      const contract = getInputContract(selectedNode.data.config);
      const fields = [...contract.fields];
      fields[index] = { ...fields[index], [fieldKey]: value };
      setNodeConfig("input_contract", { ...contract, fields });
    },
    [selectedNode, setNodeConfig],
  );

  const updateInputFieldSelector = useCallback(
    (index: number, selectorKey: string, value: unknown) => {
      if (!selectedNode) return;
      const contract = getInputContract(selectedNode.data.config);
      const fields = [...contract.fields];
      fields[index] = {
        ...fields[index],
        selector: { ...fields[index].selector, [selectorKey]: value },
      };
      setNodeConfig("input_contract", { ...contract, fields });
    },
    [selectedNode, setNodeConfig],
  );

  const removeInputField = useCallback(
    (index: number) => {
      if (!selectedNode) return;
      const contract = getInputContract(selectedNode.data.config);
      const fields = [...contract.fields];
      fields.splice(index, 1);
      setNodeConfig("input_contract", { ...contract, fields });
    },
    [selectedNode, setNodeConfig],
  );

  const addInputField = useCallback(() => {
    if (!selectedNode) return;
    const contract = getInputContract(selectedNode.data.config);
    const defaultSource = upstreamNodes.some((node) =>
      node.data.nodeType.startsWith("trigger."),
    )
      ? "trigger"
      : upstreamNodes.length > 0
        ? "node_output"
        : "literal";
    const fields = [
      ...contract.fields,
      {
        key: "",
        field_schema: { type: "string" },
        required: false,
        selector: { source: defaultSource },
      },
    ];
    setNodeConfig("input_contract", { ...contract, fields });
  }, [selectedNode, setNodeConfig, upstreamNodes]);

  const outputSchemaFields = useMemo(() => {
    if (!selectedNode) return [];
    const contract = getOutputContract(selectedNode.data.config);
    const properties = contract.output_schema?.properties;
    if (!properties || typeof properties !== "object" || Array.isArray(properties)) {
      return [];
    }
    return Object.entries(properties as Record<string, Record<string, unknown>>);
  }, [selectedNode]);

  const renameOutputField = useCallback(
    (index: number, newName: string) => {
      if (!selectedNode) return;
      const contract = getOutputContract(selectedNode.data.config);
      const entries = Object.entries(
        (contract.output_schema?.properties ?? {}) as Record<
          string,
          Record<string, unknown>
        >,
      );
      if (index < 0 || index >= entries.length) return;
      const rebuilt: Record<string, Record<string, unknown>> = {};
      entries.forEach(([key, value], entryIndex) => {
        rebuilt[entryIndex === index ? newName : key] = value;
      });
      setNodeConfig("output_contract", {
        ...contract,
        output_schema: { ...contract.output_schema, properties: rebuilt },
      });
    },
    [selectedNode, setNodeConfig],
  );

  const updateOutputFieldType = useCallback(
    (index: number, type: string) => {
      if (!selectedNode) return;
      const contract = getOutputContract(selectedNode.data.config);
      const entries = Object.entries(
        (contract.output_schema?.properties ?? {}) as Record<
          string,
          Record<string, unknown>
        >,
      );
      if (index < 0 || index >= entries.length) return;
      const rebuilt: Record<string, Record<string, unknown>> = {};
      entries.forEach(([key, value], entryIndex) => {
        rebuilt[key] = entryIndex === index ? { ...value, type } : value;
      });
      setNodeConfig("output_contract", {
        ...contract,
        output_schema: { ...contract.output_schema, properties: rebuilt },
      });
    },
    [selectedNode, setNodeConfig],
  );

  const removeOutputField = useCallback(
    (index: number) => {
      if (!selectedNode) return;
      const contract = getOutputContract(selectedNode.data.config);
      const entries = Object.entries(
        (contract.output_schema?.properties ?? {}) as Record<
          string,
          Record<string, unknown>
        >,
      );
      if (index < 0 || index >= entries.length) return;
      const rebuilt: Record<string, Record<string, unknown>> = {};
      entries.forEach(([key, value], entryIndex) => {
        if (entryIndex !== index) {
          rebuilt[key] = value;
        }
      });
      setNodeConfig("output_contract", {
        ...contract,
        output_schema: { ...contract.output_schema, properties: rebuilt },
      });
    },
    [selectedNode, setNodeConfig],
  );

  const addOutputField = useCallback(() => {
    if (!selectedNode) return;
    const contract = getOutputContract(selectedNode.data.config);
    const properties = (contract.output_schema?.properties ?? {}) as Record<
      string,
      Record<string, unknown>
    >;
    const newKey = `field_${Object.keys(properties).length + 1}`;
    setNodeConfig("output_contract", {
      ...contract,
      output_schema: {
        ...contract.output_schema,
        properties: { ...properties, [newKey]: { type: "string" } },
      },
    });
  }, [selectedNode, setNodeConfig]);

  const setRouteField = useCallback(
    (field: string) => {
      if (!selectedNode) return;
      const contract = getOutputContract(selectedNode.data.config);
      setNodeConfig("output_contract", {
        ...contract,
        route: {
          ...(contract.route ?? { field: "", enum: [], enum_from_edges: false }),
          field,
        },
      });
    },
    [selectedNode, setNodeConfig],
  );

  const setRouteEnumFromEdges = useCallback(
    (enabled: boolean) => {
      if (!selectedNode) return;
      const contract = getOutputContract(selectedNode.data.config);
      setNodeConfig("output_contract", {
        ...contract,
        route: {
          ...(contract.route ?? { field: "", enum: [], enum_from_edges: false }),
          enum_from_edges: enabled,
        },
      });
    },
    [selectedNode, setNodeConfig],
  );

  const setRouteEnum = useCallback(
    (values: string[]) => {
      if (!selectedNode) return;
      const contract = getOutputContract(selectedNode.data.config);
      setNodeConfig("output_contract", {
        ...contract,
        route: {
          ...(contract.route ?? { field: "", enum: [], enum_from_edges: false }),
          enum: values,
        },
      });
    },
    [selectedNode, setNodeConfig],
  );

  const buildSavePayload = useCallback(() => {
    const graph = canvasToGraph(nodes, edges, viewport);
    const triggerBindings = deriveTriggerBindings(nodes);
    return {
      name: workflowName.trim(),
      description: workflowDescription.trim(),
      enabled: workflowEnabled,
      schema_version: 2,
      graph,
      trigger_bindings: triggerBindings,
      runtime_policy: runtimePolicy,
      summary: deriveWorkflowSummary(
        workflowName.trim() || workflow?.name || "",
        graph,
        triggerBindings,
      ),
    };
  }, [
    edges,
    nodes,
    runtimePolicy,
    viewport,
    workflowName,
    workflowDescription,
    workflowEnabled,
    workflow?.name,
  ]);

  const buildWorkflowSnapshot = useCallback((): AgentWorkflow | null => {
    if (!workflow) return null;
    return {
      ...workflow,
      ...buildSavePayload(),
    };
  }, [buildSavePayload, workflow]);

  const initialPayloadFingerprint = useMemo(() => {
    if (!workflow) return "";
    return JSON.stringify({
      name: workflow.name,
      description: workflow.description,
      enabled: workflow.enabled,
      schema_version: workflow.schema_version,
      graph: workflow.graph,
      trigger_bindings: workflow.trigger_bindings,
      runtime_policy: workflow.runtime_policy,
      summary: workflow.summary,
    });
  }, [workflow]);

  const currentPayloadFingerprint = useMemo(
    () => JSON.stringify(buildSavePayload()),
    [buildSavePayload],
  );

  const hasUnsavedChanges =
    Boolean(workflow) &&
    currentPayloadFingerprint !== initialPayloadFingerprint;

  const save = useMutation({
    mutationFn: async () => {
      if (!workflow) {
        throw new Error(lang === "zh" ? "没有可保存的工作流" : "No workflow to save");
      }
      return updateAgentWorkflow(workflow.key, buildSavePayload());
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: WORKFLOWS_QUERY_KEY });
      toast.success(copy.save);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const validate = useMutation({
    mutationFn: () => {
      if (!workflow) {
        throw new Error(
          lang === "zh" ? "没有可校验的工作流" : "No workflow to validate",
        );
      }
      return validateAgentWorkflow({ key: workflow.key, ...buildSavePayload() });
    },
    onSuccess: (result) => {
      if (result.ok) {
        toast.success(copy.validationPassed);
        return;
      }
      const firstIssue =
        result.issues.find((item) => item.level === "error") || result.issues[0];
      toast.error(firstIssue?.message || copy.validationFailed);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const persistDisabledDraft = useMutation({
    mutationFn: async () => {
      if (!workflow) {
        throw new Error(lang === "zh" ? "没有可保存的工作流" : "No workflow to persist");
      }
      const payload = {
        ...buildSavePayload(),
        enabled: false,
      };
      if (!hasUnsavedChanges && workflow.enabled === false) {
        return workflow;
      }
      return updateAgentWorkflow(workflow.key, payload);
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: WORKFLOWS_QUERY_KEY });
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return {
    isSketchMode,
    nodes,
    setNodes,
    edges,
    setEdges,
    selected,
    setSelected,
    viewport,
    setViewport,
    showPalette,
    setShowPalette,
    showInspector,
    setShowInspector,
    showSurfaceAssistant,
    setShowSurfaceAssistant,
    workflowName,
    setWorkflowName,
    workflowDescription,
    setWorkflowDescription,
    workflowEnabled,
    setWorkflowEnabled,
    runtimePolicy,
    setRuntimePolicy,
    jsonDrafts,
    setJsonDrafts,
    jsonErrors,
    setJsonErrors,
    derivedSchema,
    derivingSchema,
    registry,
    paletteGroups,
    operationCatalog,
    selectedNode,
    selectedEdge,
    selectedNodeDefinition,
    selectedOperation,
    selectedOperationExamples,
    selectedSourceNodeDefinition,
    summaryPreview,
    onNodesChange,
    onEdgesChange,
    onConnect,
    addNode,
    applyWorkflowState,
    updateSelectedNode,
    setNodeConfig,
    setNodeLabel,
    deleteSelectedNode,
    deleteSelectedEdge,
    updateInputMapping,
    addInputMapping,
    removeInputMapping,
    upstreamNodes,
    mountedToolNodes,
    updateInputField,
    updateInputFieldSelector,
    removeInputField,
    addInputField,
    outputSchemaFields,
    renameOutputField,
    updateOutputFieldType,
    removeOutputField,
    addOutputField,
    setRouteField,
    setRouteEnumFromEdges,
    setRouteEnum,
    buildWorkflowSnapshot,
    hasUnsavedChanges,
    persistDisabledDraft,
    save,
    validate,
  };
}
