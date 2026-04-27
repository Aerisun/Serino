import { lazy, Suspense, useCallback, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { ReactFlowProvider } from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import {
  useGetDeliveriesApiV1AdminAutomationDeliveriesGet,
  useGetWebhooksApiV1AdminAutomationWebhooksGet,
} from "@serino/api-client/admin";
import type {
  WebhookDeliveryRead,
  WebhookSubscriptionRead,
} from "@serino/api-client/models";
import {
  getAgentWorkflowCatalog,
} from "@/pages/automation/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "@/components/ui/Dialog";
import { useI18n } from "@/i18n";
import {
  ChevronLeft,
  ChevronRight,
  DiamondPlus,
  Link2,
  Save,
  SlidersHorizontal,
  Sparkles,
  Trash2,
} from "lucide-react";
import { WorkflowCanvas } from "./WorkflowCanvas";
import { WorkflowPalette } from "./WorkflowPalette";
import { useWorkflowEditorState } from "./useWorkflowEditorState";
import {
  type WorkflowVisualEditorDialogProps,
  COPY,
} from "./workflow-editor-core";
import {
  WORKFLOWS_QUERY_KEY,
  WORKFLOW_CATALOG_QUERY_KEY,
  latestDeliveriesBySubscription,
} from "./workflow-shared";

const WorkflowInspector = lazy(() =>
  import("./WorkflowInspector").then((module) => ({
    default: module.WorkflowInspector,
  })),
);
const SurfaceAssistantDialog = lazy(() =>
  import("./SurfaceAssistantDialog").then((module) => ({
    default: module.SurfaceAssistantDialog,
  })),
);

function WorkflowInspectorFallback({
  show,
  copy,
  workflowName,
  workflowKey,
  selectedNodeLabel,
  selectedEdgeId,
  onClose,
}: {
  show: boolean;
  copy: { inspector: string; selectedNode: string; selectedEdge: string; workflowSettings: string };
  workflowName: string;
  workflowKey: string;
  selectedNodeLabel: string | null;
  selectedEdgeId: string | null;
  onClose: () => void;
}) {
  return (
    <div
      className={
        show
          ? "absolute bottom-4 right-4 top-[108px] z-40 flex w-[420px] flex-col overflow-hidden rounded-[28px] border border-border/60 bg-background/88 p-4 shadow-[var(--admin-shadow-lg)] backdrop-blur-xl"
          : "hidden"
      }
    >
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-muted-foreground">
            {selectedNodeLabel ? copy.selectedNode : selectedEdgeId ? copy.selectedEdge : copy.workflowSettings}
          </div>
          <div className="mt-1 text-base font-semibold text-foreground">
            {selectedNodeLabel || selectedEdgeId || workflowName || workflowKey}
          </div>
        </div>
        <Button type="button" variant="ghost" size="icon" onClick={onClose}>
          <ChevronRight className="h-4 w-4" />
        </Button>
      </div>
      <div className="mt-4 flex min-h-0 flex-1 items-center justify-center rounded-[22px] border border-border/60 bg-background/70 p-4 text-sm text-muted-foreground">
        {copy.inspector}
      </div>
    </div>
  );
}

function SurfaceAssistantDialogFallback({
  open,
  title,
  description,
}: {
  open: boolean;
  title: string;
  description: string;
}) {
  return (
    <Dialog open={open}>
      <DialogContent className="max-w-[min(92vw,1120px)]">
        <DialogTitle className="flex items-center gap-2">
          <Sparkles className="h-4 w-4 text-sky-500" />
          {title}
        </DialogTitle>
        <DialogDescription>{description}</DialogDescription>
        <div className="flex min-h-[320px] items-center justify-center text-sm text-muted-foreground">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function WorkflowVisualEditorDialog(
  props: WorkflowVisualEditorDialogProps,
) {
  return (
    <ReactFlowProvider>
      <WorkflowVisualEditorDialogInner {...props} />
    </ReactFlowProvider>
  );
}

function WorkflowVisualEditorDialogInner({
  open,
  onOpenChange,
  workflow,
  mode = "edit",
  draftValidationIssues = [],
  persistDisabledOnClose = false,
  onContinueSketch,
}: WorkflowVisualEditorDialogProps) {
  const { lang } = useI18n();
  const copy = COPY[lang];
  const queryClient = useQueryClient();
  const [isClosing, setIsClosing] = useState(false);

  const { data: catalog } = useQuery({
    queryKey: [...WORKFLOW_CATALOG_QUERY_KEY, mode, mode === "sketch" ? "" : workflow?.key ?? ""],
    queryFn: () =>
      getAgentWorkflowCatalog(mode === "sketch" ? undefined : workflow?.key ?? undefined),
    enabled: open,
  });
  const catalogReady = Boolean(catalog);
  const triggerEventOptions = useMemo(
    () => catalog?.trigger_events || [],
    [catalog?.trigger_events],
  );

  const {
    isSketchMode,
    nodes,
    setEdges,
    edges,
    selected: _selected,
    setSelected,
    viewport,
    setViewport,
    setShowPalette,
    showPalette,
    setShowInspector,
    showInspector,
    setShowSurfaceAssistant,
    showSurfaceAssistant,
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
    persistDisabledDraft,
    save,
    validate,
  } = useWorkflowEditorState({
    open,
    workflow,
    mode,
    lang,
    copy,
    catalog,
  });

  const { data: deliveriesRaw } =
    useGetDeliveriesApiV1AdminAutomationDeliveriesGet({
      query: { enabled: open && showInspector },
    });
  const { data: webhooksRaw } = useGetWebhooksApiV1AdminAutomationWebhooksGet({
    query: { enabled: open && showInspector },
  });

  const webhooks = (webhooksRaw?.data ?? []) as WebhookSubscriptionRead[];
  const latestDeliveryMap = useMemo(
    () =>
      latestDeliveriesBySubscription(
        (deliveriesRaw?.data ?? []) as WebhookDeliveryRead[],
      ),
    [deliveriesRaw?.data],
  );

  const handleOpenChange = useCallback(
    (nextOpen: boolean) => {
      if (nextOpen) {
        onOpenChange(true);
        return;
      }
      if (persistDisabledOnClose && !isSketchMode) {
        if (isClosing) return;
        setIsClosing(true);
        void persistDisabledDraft.mutateAsync().finally(() => {
          setIsClosing(false);
          onOpenChange(false);
        });
        return;
      }
      onOpenChange(false);
    },
    [isClosing, isSketchMode, onOpenChange, persistDisabledOnClose, persistDisabledDraft],
  );

  if (!workflow) return null;

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogContent className="max-w-[min(98vw,1680px)] overflow-hidden p-0">
        <DialogTitle className="sr-only">{copy.title}</DialogTitle>
        <DialogDescription className="sr-only">
          {workflow.name} · {copy.description}
        </DialogDescription>

        <div className="relative h-[92vh] min-h-[780px] bg-[linear-gradient(180deg,rgba(var(--admin-surface-strong)/0.98),rgba(var(--admin-surface-1)/0.96))]">
          <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_top_left,rgba(56,189,248,0.12),transparent_34%),radial-gradient(circle_at_bottom_right,rgba(16,185,129,0.08),transparent_28%)]" />

          <div className="absolute inset-x-0 top-0 z-30 border-b border-border/60 bg-background/80 px-5 py-4 backdrop-blur-xl">
            <div className="flex flex-wrap items-start justify-between gap-4">
              <div className="min-w-0">
                <div className="flex flex-wrap items-center gap-2">
                  <Sparkles className="h-5 w-5 text-sky-500" />
                  <div className="text-lg font-semibold text-foreground">
                    {copy.title}
                  </div>
                  <Badge variant="outline">{workflow.key}</Badge>
                  <Badge variant={workflowEnabled ? "success" : "secondary"}>
                    {workflowEnabled
                      ? lang === "zh"
                        ? "启用中"
                        : "Enabled"
                      : lang === "zh"
                        ? "已停用"
                        : "Disabled"}
                  </Badge>
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowPalette((current) => !current)}
                >
                  {showPalette ? (
                    <ChevronLeft className="mr-2 h-4 w-4" />
                  ) : (
                    <DiamondPlus className="mr-2 h-4 w-4" />
                  )}
                  {copy.palette}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => setShowInspector((current) => !current)}
                >
                  {showInspector ? (
                    <ChevronRight className="mr-2 h-4 w-4" />
                  ) : (
                    <SlidersHorizontal className="mr-2 h-4 w-4" />
                  )}
                  {copy.inspector}
                </Button>
                {!isSketchMode ? (
                  null
                ) : null}
                {selectedNode ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={deleteSelectedNode}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    {copy.deleteNode}
                  </Button>
                ) : null}
                {selectedEdge ? (
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={deleteSelectedEdge}
                  >
                    <Link2 className="mr-2 h-4 w-4" />
                    {copy.deleteEdge}
                  </Button>
                ) : null}
                {isSketchMode ? (
                  <Button
                    type="button"
                    variant="default"
                    size="sm"
                    onClick={async () => {
                      const snapshot = buildWorkflowSnapshot();
                      if (!snapshot) return;
                      await onContinueSketch?.(snapshot);
                    }}
                  >
                    <Sparkles className="mr-2 h-4 w-4" />
                    {lang === "zh" ? "把草图交给 AI 分析" : "Send Sketch to AI"}
                  </Button>
                ) : (
                  <>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => validate.mutate()}
                      disabled={validate.isPending || isClosing}
                    >
                      <Sparkles className="mr-2 h-4 w-4" />
                      {validate.isPending ? copy.validating : copy.validate}
                    </Button>
                    <Button
                      type="button"
                      variant="default"
                      size="sm"
                      onClick={() => save.mutate()}
                      disabled={save.isPending || isClosing}
                    >
                      <Save className="mr-2 h-4 w-4" />
                      {save.isPending ? copy.saving : copy.save}
                    </Button>
                  </>
                )}
              </div>
            </div>
          </div>

          {catalogReady ? (
            <WorkflowCanvas
              key={`${mode}:${workflow.key}:catalog-ready`}
              nodes={nodes}
              edges={edges}
              validationIssues={draftValidationIssues}
              workflowEnabled={workflowEnabled}
              onWorkflowEnabledChange={setWorkflowEnabled}
              registry={registry}
              catalog={catalog}
              lang={lang}
              copy={copy}
              viewport={viewport}
              summaryPreview={summaryPreview}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={(nodeId) => setSelected({ type: "node", id: nodeId })}
              onEdgeClick={(edgeId) => setSelected({ type: "edge", id: edgeId })}
              onPaneClick={() => setSelected(null)}
              onViewportChange={setViewport}
            />
          ) : (
            <div className="absolute inset-0 pt-[92px]">
              <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                {lang === "zh" ? "正在加载工作流节点目录..." : "Loading workflow node catalog..."}
              </div>
            </div>
          )}

          <WorkflowPalette
            show={showPalette}
            onClose={() => setShowPalette(false)}
            paletteGroups={paletteGroups}
            catalog={catalog}
            lang={lang}
            copy={copy}
            onAddNode={addNode}
          />

          {showInspector ? (
            <Suspense
              fallback={(
                <WorkflowInspectorFallback
                  show={showInspector}
                  copy={copy}
                  workflowName={workflowName}
                  workflowKey={workflow.key}
                  selectedNodeLabel={selectedNode?.data.label ?? null}
                  selectedEdgeId={selectedEdge?.id ?? null}
                  onClose={() => setShowInspector(false)}
                />
              )}
            >
              <WorkflowInspector
                mode={mode}
                show={showInspector}
                onClose={() => setShowInspector(false)}
                copy={copy}
                lang={lang}
                catalog={catalog}
                workflow={workflow}
                workflowName={workflowName}
                workflowDescription={workflowDescription}
                workflowEnabled={workflowEnabled}
                runtimePolicy={runtimePolicy}
                onWorkflowNameChange={setWorkflowName}
                onWorkflowDescriptionChange={setWorkflowDescription}
                onWorkflowEnabledChange={setWorkflowEnabled}
                onRuntimePolicyChange={setRuntimePolicy}
                selectedNode={selectedNode}
                selectedEdge={selectedEdge}
                selectedNodeDefinition={selectedNodeDefinition}
                selectedOperation={selectedOperation}
                selectedOperationExamples={selectedOperationExamples}
                selectedSourceNodeDefinition={selectedSourceNodeDefinition}
                setNodeLabel={setNodeLabel}
                setNodeConfig={setNodeConfig}
                updateSelectedNode={updateSelectedNode}
                deleteSelectedNode={deleteSelectedNode}
                setEdges={setEdges}
                deleteSelectedEdge={deleteSelectedEdge}
                jsonDrafts={jsonDrafts}
                jsonErrors={jsonErrors}
                setJsonDrafts={setJsonDrafts}
                setJsonErrors={setJsonErrors}
                operationCatalog={operationCatalog}
                triggerEventOptions={triggerEventOptions}
                webhooks={webhooks}
                latestDeliveryMap={latestDeliveryMap}
                upstreamNodes={upstreamNodes}
                mountedToolNodes={mountedToolNodes}
                updateInputField={updateInputField}
                updateInputFieldSelector={updateInputFieldSelector}
                removeInputField={removeInputField}
                addInputField={addInputField}
                outputSchemaFields={outputSchemaFields}
                renameOutputField={renameOutputField}
                updateOutputFieldType={updateOutputFieldType}
                removeOutputField={removeOutputField}
                addOutputField={addOutputField}
                setRouteField={setRouteField}
                setRouteEnumFromEdges={setRouteEnumFromEdges}
                setRouteEnum={setRouteEnum}
                updateInputMapping={updateInputMapping}
                addInputMapping={addInputMapping}
                removeInputMapping={removeInputMapping}
                derivedSchema={derivedSchema}
                derivingSchema={derivingSchema}
                nodes={nodes}
                edges={edges}
                onOpenSurfaceAssistant={() => setShowSurfaceAssistant(true)}
              />
            </Suspense>
          ) : null}

          {!isSketchMode && showSurfaceAssistant ? (
            <Suspense
              fallback={(
                <SurfaceAssistantDialogFallback
                  open={showSurfaceAssistant}
                  title={lang === "zh" ? "AI 管理 Surface" : "AI Surface Assistant"}
                  description={lang === "zh"
                    ? "只针对当前工作流本地 surface 提出新增、修改、删除请求，AI 先给计划，再由你确认应用。"
                    : "Work only on workflow-local surfaces for this workflow. The AI prepares a plan first, and you apply it explicitly."}
                />
              )}
            >
              <SurfaceAssistantDialog
                open={showSurfaceAssistant}
                onOpenChange={setShowSurfaceAssistant}
                workflow={workflow}
                catalog={catalog}
                lang={lang}
                onApplied={async (result) => {
                  applyWorkflowState(result.workflow);
                  await queryClient.invalidateQueries({
                    queryKey: WORKFLOWS_QUERY_KEY,
                  });
                  await queryClient.invalidateQueries({
                    queryKey: [...WORKFLOW_CATALOG_QUERY_KEY, mode, workflow.key],
                  });
                }}
              />
            </Suspense>
          ) : null}
        </div>
      </DialogContent>
    </Dialog>
  );
}
