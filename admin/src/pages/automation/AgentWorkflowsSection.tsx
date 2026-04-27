import { lazy, Suspense, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AdminSurface } from "@/components/AdminSurface";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import type { AgentWorkflow, AgentWorkflowInput } from "@/pages/automation/api";
import {
  createAgentWorkflow,
  deleteAgentWorkflow,
  getAgentWorkflows,
} from "@/pages/automation/api";
import { useI18n } from "@/i18n";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import {
  deriveWorkflowSummary,
  runtimePolicyDefaults,
  WORKFLOWS_QUERY_KEY,
} from "./workflow-shared";

const loadWorkflowVisualEditorDialog = () =>
  import("./WorkflowVisualEditorDialog").then((module) => ({
    default: module.WorkflowVisualEditorDialog,
  }));

const WorkflowVisualEditorDialog = lazy(loadWorkflowVisualEditorDialog);

function buildBlankWorkflowPayload(lang: "zh" | "en"): AgentWorkflowInput {
  const key = `workflow_${Date.now().toString(36)}`;
  const name = lang === "zh" ? "未命名工作流" : "Untitled Workflow";
  const graph = {
    version: 2,
    nodes: [],
    edges: [],
    viewport: { x: 0, y: 0, zoom: 1 },
  };
  return {
    key,
    name,
    description: "",
    enabled: false,
    schema_version: 2,
    graph,
    trigger_bindings: [],
    runtime_policy: runtimePolicyDefaults(null),
    summary: deriveWorkflowSummary(name, graph, []),
    require_human_approval: false,
    instructions: "",
  };
}

export function AgentWorkflowsSection() {
  const { lang } = useI18n();
  const queryClient = useQueryClient();
  const copy =
    lang === "zh"
      ? {
          title: "Agent 工作流",
          description: "",
          add: "新建工作流",
          loading: "加载中...",
          empty: "还没有工作流，先新建一个。",
          builtIn: "系统内置",
          custom: "自定义",
          visualEditor: "可视化编辑",
          creating: "正在创建...",
          deleteConfirm: "确定删除这个工作流吗？",
          createSuccess: "已创建空白工作流，直接进入画布编辑。",
        }
      : {
          title: "Agent Workflows",
          description:
            "Create workflows directly on an empty canvas. New drafts stay disabled until you enable them.",
          add: "New Blank Workflow",
          loading: "Loading...",
          empty: "No workflows yet.",
          builtIn: "Built-in",
          custom: "Custom",
          visualEditor: "Visual Editor",
          creating: "Creating...",
          deleteConfirm: "Delete this workflow?",
          createSuccess: "Blank workflow created. Opening the canvas editor.",
        };

  const { data: workflows, isLoading } = useQuery({
    queryKey: WORKFLOWS_QUERY_KEY,
    queryFn: getAgentWorkflows,
  });

  const items = useMemo(() => workflows ?? [], [workflows]);
  const [visualEditorOpen, setVisualEditorOpen] = useState(false);
  const [visualWorkflowKey, setVisualWorkflowKey] = useState<string | null>(
    null,
  );
  const [visualWorkflowOverride, setVisualWorkflowOverride] =
    useState<AgentWorkflow | null>(null);
  const [persistDisabledOnClose, setPersistDisabledOnClose] = useState(false);

  const activeVisualWorkflow = useMemo(() => {
    if (!visualWorkflowKey) return null;
    return (
      items.find((item) => item.key === visualWorkflowKey) ??
      visualWorkflowOverride
    );
  }, [items, visualWorkflowKey, visualWorkflowOverride]);

  const createBlankWorkflow = useMutation({
    mutationFn: () => createAgentWorkflow(buildBlankWorkflowPayload(lang)),
    onSuccess: async (workflow) => {
      await queryClient.invalidateQueries({ queryKey: WORKFLOWS_QUERY_KEY });
      setVisualWorkflowKey(workflow.key);
      setVisualWorkflowOverride(workflow);
      setPersistDisabledOnClose(true);
      setVisualEditorOpen(true);
      toast.success(copy.createSuccess);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const remove = useMutation({
    mutationFn: deleteAgentWorkflow,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: WORKFLOWS_QUERY_KEY });
      toast.success(lang === "zh" ? "工作流已删除" : "Workflow deleted");
    },
    onError: (error: Error) => toast.error(error.message),
  });

  return (
    <div className="space-y-4">
      <div className="flex justify-end">
        <Button
          onClick={() => createBlankWorkflow.mutate()}
          disabled={createBlankWorkflow.isPending}
        >
          <Plus className="mr-2 h-4 w-4" />
          {createBlankWorkflow.isPending ? copy.creating : copy.add}
        </Button>
      </div>

      <AdminSurface
        eyebrow="Workflow"
        title={copy.title}
        description={copy.description}
      >
        {isLoading ? (
          <p className="text-sm text-muted-foreground">{copy.loading}</p>
        ) : items.length === 0 ? (
          <p className="text-sm text-muted-foreground">{copy.empty}</p>
        ) : (
          <div className="grid gap-3">
            {items.map((item) => (
              <div
                key={item.key}
                className="rounded-[var(--admin-radius-lg)] border border-border/60 bg-background/55 px-4 py-4"
              >
                <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                  <div className="min-w-0 space-y-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant={item.built_in ? "outline" : "info"}>
                        {item.built_in ? copy.builtIn : copy.custom}
                      </Badge>
                      <Badge variant={item.enabled ? "success" : "secondary"}>
                        {item.enabled
                          ? lang === "zh"
                            ? "启用中"
                            : "Enabled"
                          : lang === "zh"
                            ? "未启用"
                            : "Disabled"}
                      </Badge>
                    </div>
                    <div className="text-base font-medium leading-6 text-foreground">
                      {item.name}
                    </div>
                    {item.description ? (
                      <div className="text-sm leading-6 text-muted-foreground">
                        {item.description}
                      </div>
                    ) : null}
                  </div>

                  <div className="flex items-center gap-2">
                    <Button
                      variant="default"
                      size="sm"
                      onClick={() => {
                        void loadWorkflowVisualEditorDialog();
                        setVisualWorkflowKey(item.key);
                        setVisualWorkflowOverride(item);
                        setPersistDisabledOnClose(false);
                        setVisualEditorOpen(true);
                      }}
                    >
                      <Pencil className="mr-2 h-4 w-4" />
                      {copy.visualEditor}
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        if (!window.confirm(copy.deleteConfirm)) {
                          return;
                        }
                        remove.mutate(item.key);
                      }}
                      disabled={remove.isPending}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </AdminSurface>

      {visualEditorOpen ? (
        <Suspense fallback={null}>
          <WorkflowVisualEditorDialog
            open={visualEditorOpen}
            onOpenChange={(nextOpen) => {
              setVisualEditorOpen(nextOpen);
              if (!nextOpen) {
                setVisualWorkflowKey(null);
                setVisualWorkflowOverride(null);
                setPersistDisabledOnClose(false);
              }
            }}
            workflow={activeVisualWorkflow}
            persistDisabledOnClose={persistDisabledOnClose}
          />
        </Suspense>
      ) : null}
    </div>
  );
}
