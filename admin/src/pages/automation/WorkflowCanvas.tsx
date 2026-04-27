import { useMemo } from "react";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  MiniMap,
  type NodeProps,
  type OnEdgesChange,
  type OnNodesChange,
  Panel,
  ReactFlow,
  type Connection,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import type { AgentWorkflowCatalog, AgentWorkflowCatalogNodeType } from "@/pages/automation/api";
import type { AgentWorkflowValidationIssue } from "@/pages/automation/api";
import { Badge } from "@/components/ui/Badge";
import type { Lang } from "@/i18n";
import { cn } from "@/lib/utils";
import {
  type WorkflowCanvasNode,
  type WorkflowCanvasEdge,
  type CopyShape,
  edgeKind,
  iconForName,
  toneForCategory,
  toneClasses,
  portPosition,
  portStyle,
  friendlyNodeTypeLabel,
  summaryForNode,
} from "./workflow-editor-core";

// ---------------------------------------------------------------------------
// Custom node card
// ---------------------------------------------------------------------------

function portHandleClasses(portId: string, kind: "input" | "output") {
  if (kind === "input") {
    if (portId.startsWith("mount_")) {
      return "!h-4 !w-4 !border-2 !border-white/80 !bg-fuchsia-400";
    }
    return "!h-4 !w-4 !border-2 !border-white/80 !bg-sky-400";
  }
  return "!h-4 !w-4 !border-2 !border-white/80 !bg-emerald-400";
}

function WorkflowCanvasNodeCard({
  data,
  selected,
}: NodeProps<WorkflowCanvasNode>) {
  const renderMeta = data.__renderMeta;
  const definition = renderMeta?.definition;
  const Icon = iconForName(definition?.icon || "");
  const tone = toneForCategory(definition?.category || "utility", definition?.risk_level);
  const inputPorts = definition?.input_ports || [];
  const outputPorts = definition?.output_ports || [];
  const nodeSummary = summaryForNode(definition, data.config);
  const issueCount = renderMeta?.issueCount || 0;
  const issueLevel = renderMeta?.issueLevel || null;
  const nodeTypeLabel = renderMeta?.nodeTypeLabel || data.nodeType;
  const lang = renderMeta?.lang || "zh";
  const approvalCompatOutputHandles =
    data.nodeType === "approval.review"
      ? ["approval", "approved", "rejected", "default"].filter(
          (portId) => !outputPorts.some((port) => port.id === portId),
        )
      : [];
  const approvalCompatAnchorSide =
    outputPorts.find((port) => port.id === "approval")?.side || outputPorts[0]?.side || "right";
  const approvalCompatStyle = portStyle(approvalCompatAnchorSide, 0, 1);

  const buildPortSlots = <TPort extends { side: string }>(ports: TPort[]) => {
    const sideCounts = new Map<string, number>();
    for (const port of ports) {
      sideCounts.set(port.side, (sideCounts.get(port.side) || 0) + 1);
    }
    const sideSeen = new Map<string, number>();
    return ports.map((port) => {
      const sideIndex = sideSeen.get(port.side) || 0;
      sideSeen.set(port.side, sideIndex + 1);
      return {
        port,
        sideIndex,
        sideCount: sideCounts.get(port.side) || 1,
      };
    });
  };

  const inputPortSlots = buildPortSlots(inputPorts);
  const outputPortSlots = buildPortSlots(outputPorts);

  const leftPortCount = inputPortSlots.filter((slot) => slot.port.side === "left").length +
    outputPortSlots.filter((slot) => slot.port.side === "left").length;
  const rightPortCount = inputPortSlots.filter((slot) => slot.port.side === "right").length +
    outputPortSlots.filter((slot) => slot.port.side === "right").length;
  const verticalPortCount = Math.max(leftPortCount, rightPortCount, 1);
  const minCardHeight = Math.max(88, 64 + (verticalPortCount - 1) * 22);

  return (
    <div
      className={cn(
        "min-w-[210px] rounded-[22px] border p-3 shadow-[0_18px_48px_rgba(15,23,42,0.12)] backdrop-blur-sm",
        toneClasses(tone),
        issueLevel === "error" && "border-rose-400/80 ring-2 ring-rose-300/60",
        issueLevel === "warning" && "border-amber-400/80 ring-2 ring-amber-300/50",
        selected && "ring-2 ring-sky-300/80",
      )}
      style={{ minHeight: `${minCardHeight}px` }}
    >
      {inputPortSlots.map(({ port, sideIndex, sideCount }) => (
        <Handle
          key={port.id}
          id={port.id}
          type="target"
          position={portPosition(port.side)}
          style={portStyle(port.side, sideIndex, sideCount)}
          className={portHandleClasses(port.id, "input")}
        />
      ))}
      <div className="flex items-start gap-3">
        <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-2xl border border-white/30 bg-white/20">
          <Icon className="h-4 w-4" />
        </div>
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className="w-fit px-2 py-0.5 text-[10px]">
              {nodeTypeLabel}
            </Badge>
            {issueCount > 0 ? (
              <Badge variant={issueLevel === "error" ? "warning" : "outline"} className="px-2 py-0.5 text-[10px]">
                {lang === "zh" ? `${issueCount} 条问题` : `${issueCount} issues`}
              </Badge>
            ) : null}
          </div>
          <div className="font-semibold text-foreground">{data.label}</div>
          {nodeSummary && nodeSummary !== "-" ? (
            <div className="line-clamp-3 text-xs leading-5 text-muted-foreground">
              {nodeSummary}
            </div>
          ) : null}
        </div>
      </div>
      {outputPortSlots.map(({ port, sideIndex, sideCount }) => (
        <Handle
          key={port.id}
          id={port.id}
          type="source"
          position={portPosition(port.side)}
          style={portStyle(port.side, sideIndex, sideCount)}
          className={portHandleClasses(port.id, "output")}
        />
      ))}
      {approvalCompatOutputHandles.map((portId) => (
        <Handle
          key={`compat-${portId}`}
          id={portId}
          type="source"
          position={portPosition(approvalCompatAnchorSide)}
          style={approvalCompatStyle}
          className="!h-0 !w-0 !border-0 !bg-transparent !shadow-none"
        />
      ))}
    </div>
  );
}

function WorkflowCanvasNodeRenderer(props: NodeProps<WorkflowCanvasNode>) {
  return <WorkflowCanvasNodeCard {...props} />;
}

const WORKFLOW_NODE_TYPES = {
  workflowNode: WorkflowCanvasNodeRenderer,
};

// ---------------------------------------------------------------------------
// Canvas props
// ---------------------------------------------------------------------------

interface WorkflowCanvasProps {
  nodes: WorkflowCanvasNode[];
  edges: WorkflowCanvasEdge[];
  validationIssues?: AgentWorkflowValidationIssue[];
  workflowEnabled: boolean;
  onWorkflowEnabledChange: (value: boolean) => void;
  registry: Map<string, AgentWorkflowCatalogNodeType>;
  catalog: AgentWorkflowCatalog | undefined;
  lang: Lang;
  copy: CopyShape;
  viewport: { x: number; y: number; zoom: number };
  summaryPreview: {
    trigger_labels: string[];
    node_count: number;
    operation_count: number;
    high_risk_operation_count: number;
  };
  onNodesChange: OnNodesChange<WorkflowCanvasNode>;
  onEdgesChange: OnEdgesChange<WorkflowCanvasEdge>;
  onConnect: (connection: Connection) => void;
  onNodeClick: (nodeId: string) => void;
  onEdgeClick: (edgeId: string) => void;
  onPaneClick: () => void;
  onViewportChange: (viewport: { x: number; y: number; zoom: number }) => void;
}

// ---------------------------------------------------------------------------
// WorkflowCanvas component
// ---------------------------------------------------------------------------

export function WorkflowCanvas({
  nodes,
  edges,
  validationIssues = [],
  workflowEnabled: _workflowEnabled,
  onWorkflowEnabledChange: _onWorkflowEnabledChange,
  registry,
  catalog,
  lang,
  copy,
  viewport,
  summaryPreview,
  onNodesChange,
  onEdgesChange,
  onConnect,
  onNodeClick,
  onEdgeClick,
  onPaneClick,
  onViewportChange,
}: WorkflowCanvasProps) {
  const nodeIssueMap = useMemo(() => {
    const map = new Map<string, { count: number; level: "error" | "warning" | null }>();
    for (const issue of validationIssues) {
      if (!issue.node_id) continue;
      const current = map.get(issue.node_id) || { count: 0, level: null };
      const nextLevel =
        issue.level === "error"
          ? "error"
          : current.level === "error"
            ? "error"
            : issue.level === "warning"
              ? "warning"
              : current.level;
      map.set(issue.node_id, { count: current.count + 1, level: nextLevel });
    }
    return map;
  }, [validationIssues]);

  const edgeIssueMap = useMemo(() => {
    const map = new Map<string, "error" | "warning" | null>();
    for (const issue of validationIssues) {
      if (!issue.edge_id) continue;
      const current = map.get(issue.edge_id) || null;
      if (issue.level === "error") {
        map.set(issue.edge_id, "error");
      } else if (issue.level === "warning" && current !== "error") {
        map.set(issue.edge_id, "warning");
      }
    }
    return map;
  }, [validationIssues]);

  const decoratedEdges = useMemo(
    () =>
      edges.map((edge) => {
        const kind = edgeKind(edge, nodes);
        const issueLevel = edgeIssueMap.get(edge.id) || null;
        const stroke =
          issueLevel === "error"
            ? "rgba(244,63,94,0.95)"
            : issueLevel === "warning"
              ? "rgba(245,158,11,0.95)"
              :
          kind === "tool"
            ? "rgba(14,165,233,0.9)"
            : kind === "control"
              ? "rgba(245,158,11,0.9)"
              : kind === "trigger"
                ? "rgba(139,92,246,0.92)"
                : "rgba(16,185,129,0.92)";
        const dashed = kind === "tool" || edge.data?.variant === "dashed";
        return {
          ...edge,
          animated: kind === "tool" ? false : edge.animated,
          style: {
            ...(edge.style || {}),
            stroke,
            strokeWidth: issueLevel ? 2.6 : kind === "tool" ? 2.2 : kind === "control" ? 2.15 : 2,
            ...(dashed ? { strokeDasharray: "6 6" } : {}),
          },
        };
      }),
    [edgeIssueMap, edges, nodes],
  );

  const decoratedNodes = useMemo(
    () =>
      nodes.map((node) => {
        const definition = registry.get(node.data.nodeType);
        return {
          ...node,
          data: {
            ...node.data,
            __renderMeta: {
              issueCount: nodeIssueMap.get(node.id)?.count || 0,
              issueLevel: nodeIssueMap.get(node.id)?.level || null,
              definition,
              nodeTypeLabel: friendlyNodeTypeLabel(node.data.nodeType, catalog, lang),
              lang,
            },
          },
        };
      }),
    [catalog, lang, nodeIssueMap, nodes, registry],
  );

  return (
    <div className="absolute inset-0 pt-[92px]">
      <ReactFlow
        nodes={decoratedNodes}
        edges={decoratedEdges}
        defaultEdgeOptions={{ markerEnd: { type: MarkerType.ArrowClosed } }}
        nodeTypes={WORKFLOW_NODE_TYPES}
        onNodesChange={onNodesChange}
        onEdgesChange={onEdgesChange}
        onConnect={onConnect}
        onNodeClick={(_event, node) => onNodeClick(node.id)}
        onEdgeClick={(_event, edge) => onEdgeClick(edge.id)}
        onPaneClick={() => onPaneClick()}
        onMoveEnd={(_event, nextViewport) => onViewportChange(nextViewport)}
        defaultViewport={viewport}
        colorMode="light"
        fitView
        fitViewOptions={{ padding: 0.18 }}
        minZoom={0.35}
        maxZoom={1.8}
        onlyRenderVisibleElements
        snapToGrid
        snapGrid={[20, 20]}
        proOptions={{ hideAttribution: true }}
      >
        <Background variant={BackgroundVariant.Dots} gap={20} size={1.1} color="rgba(148,163,184,0.22)" />
        <MiniMap pannable zoomable className="!bottom-5 !right-5 !rounded-2xl !border !border-border/60 !bg-background/85" />
        <Controls className="!bottom-5 !left-5" />

        <Panel position="bottom-left">
          <div className="w-[240px] rounded-[22px] border border-border/60 bg-background/82 px-4 py-3 shadow-[var(--admin-shadow-md)] backdrop-blur-xl">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
              {copy.runtimeSummary}
            </div>
            <div className="mt-2 space-y-2 text-sm leading-6">
              <div>
                <div className="text-xs text-muted-foreground">{copy.triggers}</div>
                <div className="text-foreground">{summaryPreview.trigger_labels.length}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{copy.nodes}</div>
                <div className="text-foreground">{summaryPreview.node_count}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{copy.operations}</div>
                <div className="text-foreground">{summaryPreview.operation_count}</div>
              </div>
              <div>
                <div className="text-xs text-muted-foreground">{copy.highRisk}</div>
                <div className="text-foreground">{summaryPreview.high_risk_operation_count}</div>
              </div>
            </div>
          </div>
        </Panel>
      </ReactFlow>
    </div>
  );
}
