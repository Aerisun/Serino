import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import type { AgentWorkflowCatalog, AgentWorkflow, SurfaceDraftApplyResult } from "@/pages/automation/api";
import {
  applySurfaceDraft,
  clearSurfaceDraft,
  getAgentModelConfig,
  getSurfaceDraft,
  sendSurfaceDraftMessage,
} from "@/pages/automation/api";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import { Textarea } from "@/components/ui/Textarea";
import type { Lang } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { cn } from "@/lib/utils";
import { LoaderCircle, Sparkles, Trash2 } from "lucide-react";
import { toast } from "sonner";

const surfaceDraftQueryKey = (workflowKey: string) => ["admin", "automation", "surface-draft", workflowKey] as const;

interface SurfaceAssistantDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  workflow: AgentWorkflow;
  catalog: AgentWorkflowCatalog | undefined;
  lang: Lang;
  onApplied: (result: SurfaceDraftApplyResult) => void;
}

function copyFor(lang: Lang) {
  return lang === "zh"
    ? {
        title: "AI 管理 Surface",
        description: "只针对当前工作流本地 surface 提出新增、修改、删除请求，AI 先给计划，再由你确认应用。",
        currentSurfaces: "当前工作流 Surface",
        noSurfaces: "这个工作流还没有本地 surface。",
        actionSurfaces: "执行 Action Surfaces",
        draftSummary: "当前计划",
        noDraft: "还没有计划。直接描述你要新增、修改或删除什么 surface。",
        inputPlaceholder: "例如：新增一个执行 surface，只允许通过当前工作流查到的评论，并把原因一并传进去。",
        send: "发送给 AI",
        sending: "AI 收敛中",
        apply: "应用计划",
        applying: "应用中",
        clear: "清空计划",
        patches: "变更计划",
        validation: "编译器提醒",
        messages: "对话记录",
        emptyMessages: "还没有对话。",
        applied: "Surface 计划已应用",
        cleared: "已清空当前 surface 计划",
        impact: "影响",
        modelDisabled: "请先在“Agent 模型配置”里启用模型，然后再让 AI 帮你管理执行 Surface。",
        modelNotReady: "请先在“Agent 模型配置”里填好 Base URL、模型名和 API Key，然后再让 AI 帮你管理执行 Surface。",
        askFailed: "AI 暂时没法整理这份 Surface 方案，请稍后再试。",
        legacyDraft: "当前这份计划还是旧版查询 Surface 方案，已经不能直接应用。重新发送需求时，会按新的“执行 Surface”规则重建。",
        applyFailed: "这份 Surface 计划还不能应用，请先根据提示调整。",
      }
    : {
        title: "AI Surface Assistant",
      description: "Work only on workflow-local surfaces for this workflow. The AI prepares a plan first, and you apply it explicitly.",
        currentSurfaces: "Current Workflow Surfaces",
        noSurfaces: "This workflow does not have any local surfaces yet.",
        actionSurfaces: "Action Surfaces",
        draftSummary: "Current Plan",
        noDraft: "No plan yet. Describe what surface should be created, updated, or removed.",
        inputPlaceholder: "Example: Add an action surface that only approves comments discovered by this workflow and forwards the reason field.",
        send: "Ask AI",
        sending: "Planning",
        apply: "Apply Plan",
        applying: "Applying",
        clear: "Clear Plan",
        patches: "Planned Changes",
        validation: "Compiler Notes",
        messages: "Conversation",
        emptyMessages: "No conversation yet.",
        applied: "Surface plan applied",
        cleared: "Cleared the current surface plan",
        impact: "Impact",
        modelDisabled: "Enable the Agent model first before asking AI to manage workflow-local action surfaces.",
        modelNotReady: "Finish the Agent model config first, then ask AI to manage workflow-local action surfaces.",
        askFailed: "The AI could not prepare a surface plan right now. Please try again.",
        legacyDraft: "This draft still uses the old query-surface format and can no longer be applied directly. Send a new request and it will be rebuilt as action surfaces.",
        applyFailed: "This surface plan cannot be applied yet. Review the note and try again.",
      };
}

function humanizeSurfaceDraftError(error: unknown, copy: ReturnType<typeof copyFor>) {
  const detail = extractApiErrorMessage(error, copy.askFailed);
  if (detail === "Agent model is disabled") {
    return copy.modelDisabled;
  }
  if (detail === "Agent model config is not ready") {
    return copy.modelNotReady;
  }
  if (detail.includes("旧版查询 Surface 方案")) {
    return copy.legacyDraft;
  }
  return detail;
}

function HumanCard({ card }: { card?: Record<string, string[]> }) {
  const rows = useMemo(
    () =>
      [
        ...(card?.reads ?? []),
        ...(card?.cannot_read ?? []),
        ...(card?.can_act ?? []),
        ...(card?.cannot_act ?? []),
        ...(card?.parameter_sources ?? []),
      ].filter(Boolean),
    [card],
  );

  if (!rows.length) return null;
  return (
    <div className="mt-2 space-y-1 text-xs leading-5 text-muted-foreground">
      {rows.map((row, index) => (
        <div key={`${row}:${index}`}>• {row}</div>
      ))}
    </div>
  );
}

export function SurfaceAssistantDialog({
  open,
  onOpenChange,
  workflow,
  catalog,
  lang,
  onApplied,
}: SurfaceAssistantDialogProps) {
  const copy = copyFor(lang);
  const queryClient = useQueryClient();
  const [message, setMessage] = useState("");

  const { data: draft } = useQuery({
    queryKey: surfaceDraftQueryKey(workflow.key),
    queryFn: () => getSurfaceDraft(workflow.key),
    enabled: open,
  });

  const { data: modelConfig } = useQuery({
    queryKey: ["admin", "automation", "model-config"],
    queryFn: () => getAgentModelConfig(),
    enabled: open,
  });

  const askMutation = useMutation({
    mutationFn: async (content: string) => sendSurfaceDraftMessage(workflow.key, content),
    onSuccess: (result) => {
      queryClient.setQueryData(surfaceDraftQueryKey(workflow.key), result);
      setMessage("");
    },
    onError: (error: unknown) => toast.error(humanizeSurfaceDraftError(error, copy)),
  });

  const clearMutation = useMutation({
    mutationFn: async () => clearSurfaceDraft(workflow.key),
    onSuccess: () => {
      queryClient.setQueryData(surfaceDraftQueryKey(workflow.key), null);
      toast.success(copy.cleared);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const applyMutation = useMutation({
    mutationFn: async () => applySurfaceDraft(workflow.key),
    onSuccess: async (result) => {
      queryClient.setQueryData(surfaceDraftQueryKey(workflow.key), null);
      await queryClient.invalidateQueries({ queryKey: ["admin", "agent", "workflow-catalog", workflow.key] });
      onApplied(result);
      toast.success(copy.applied);
    },
    onError: (error: unknown) => toast.error(humanizeSurfaceDraftError(error, copy)),
  });

  const actionSurfaces = useMemo(
    () => (catalog?.workflow_local_action_surfaces ?? []).filter((surface) => surface.kind === "action"),
    [catalog?.workflow_local_action_surfaces],
  );
  const hasLegacyDraftPatches = useMemo(
    () => (draft?.patches ?? []).some((patch) => patch.surface_kind !== "action_surface"),
    [draft?.patches],
  );

  const modelGuardMessage = useMemo(() => {
    if (!modelConfig) return "";
    if (!modelConfig.enabled) return copy.modelDisabled;
    if (!modelConfig.is_ready) return copy.modelNotReady;
    return "";
  }, [copy.modelDisabled, copy.modelNotReady, modelConfig]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-w-[min(92vw,1120px)]">
        <DialogHeader className="text-left">
          <DialogTitle className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-sky-500" />
            {copy.title}
          </DialogTitle>
          <DialogDescription>
            {copy.description}
          </DialogDescription>
        </DialogHeader>

        <div className="grid gap-4 lg:grid-cols-[1.05fr_1.25fr]">
          <section className="space-y-4">
            <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
              <div className="mb-3 flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-foreground">{copy.currentSurfaces}</div>
                <Badge variant="outline">{workflow.key}</Badge>
              </div>
              {!actionSurfaces.length ? (
                <div className="text-sm text-muted-foreground">{copy.noSurfaces}</div>
              ) : (
                <div className="space-y-4">
                  <div className="space-y-2">
                    <div className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
                      {copy.actionSurfaces}
                    </div>
                    {actionSurfaces.map((surface) => (
                      <div key={surface.key} className="rounded-2xl border border-border/60 bg-background/80 p-3">
                        <div className="flex flex-wrap items-center gap-2">
                          <div className="font-medium text-foreground">{surface.label}</div>
                          <Badge variant="outline">{surface.key}</Badge>
                        </div>
                        <div className="mt-1 text-sm leading-6 text-muted-foreground">{surface.description}</div>
                        <HumanCard card={surface.human_card} />
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>

          <section className="space-y-4">
            <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
              <div className="mb-2 flex items-center justify-between gap-2">
                <div className="text-sm font-semibold text-foreground">{copy.draftSummary}</div>
                {draft?.status ? <Badge variant="outline">{draft.status}</Badge> : null}
              </div>
              <div className="text-sm leading-6 text-muted-foreground">
                {draft?.summary || copy.noDraft}
              </div>
            </div>

            <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
              <div className="mb-2 text-sm font-semibold text-foreground">{copy.messages}</div>
              <div className="max-h-[220px] space-y-2 overflow-y-auto pr-1">
                {(draft?.messages ?? []).length ? (
                  draft?.messages.map((item, index) => (
                    <div
                      key={`${item.created_at}:${index}`}
                      className={cn(
                        "rounded-2xl px-3 py-2 text-sm leading-6",
                        item.role === "user"
                          ? "ml-8 bg-sky-500/10 text-sky-900"
                          : "mr-8 border border-border/60 bg-background/85 text-foreground",
                      )}
                    >
                      <div className="mb-1 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                        {item.role}
                      </div>
                      <div>{item.content}</div>
                    </div>
                  ))
                ) : (
                  <div className="text-sm text-muted-foreground">{copy.emptyMessages}</div>
                )}
              </div>
              <div className="mt-3 space-y-3">
                {modelGuardMessage ? (
                  <div className="rounded-2xl border border-amber-300/50 bg-amber-500/5 px-3 py-2 text-sm leading-6 text-amber-900">
                    {modelGuardMessage}
                  </div>
                ) : null}
                {hasLegacyDraftPatches ? (
                  <div className="rounded-2xl border border-amber-300/50 bg-amber-500/5 px-3 py-2 text-sm leading-6 text-amber-900">
                    {copy.legacyDraft}
                  </div>
                ) : null}
                <Textarea
                  rows={4}
                  value={message}
                  onChange={(event) => setMessage(event.target.value)}
                  placeholder={copy.inputPlaceholder}
                />
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => clearMutation.mutate()}
                    disabled={clearMutation.isPending || askMutation.isPending || applyMutation.isPending}
                  >
                    <Trash2 className="mr-2 h-4 w-4" />
                    {copy.clear}
                  </Button>
                  <div className="flex flex-wrap items-center gap-2">
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => applyMutation.mutate()}
                      disabled={!draft?.ready_to_apply || hasLegacyDraftPatches || applyMutation.isPending || askMutation.isPending}
                    >
                      {applyMutation.isPending ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : null}
                      {applyMutation.isPending ? copy.applying : copy.apply}
                    </Button>
                    <Button
                      type="button"
                      size="sm"
                      onClick={() => askMutation.mutate(message.trim())}
                      disabled={!message.trim() || askMutation.isPending || applyMutation.isPending || Boolean(modelGuardMessage)}
                    >
                      {askMutation.isPending ? <LoaderCircle className="mr-2 h-4 w-4 animate-spin" /> : <Sparkles className="mr-2 h-4 w-4" />}
                      {askMutation.isPending ? copy.sending : copy.send}
                    </Button>
                  </div>
                </div>
              </div>
            </div>

            {(draft?.patches?.length ?? 0) > 0 ? (
              <div className="rounded-2xl border border-border/60 bg-background/60 p-4">
                <div className="mb-3 text-sm font-semibold text-foreground">{copy.patches}</div>
                <div className="space-y-3">
                  {draft?.patches.map((patch, index) => (
                    <div key={`${patch.surface_key}:${index}`} className="rounded-2xl border border-border/60 bg-background/80 p-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="outline">{patch.action}</Badge>
                        <Badge variant="outline">{patch.surface_kind}</Badge>
                        <div className="font-medium text-foreground">{patch.surface_key}</div>
                      </div>
                      <div className="mt-2 text-sm leading-6 text-foreground">{patch.human_summary || patch.reason}</div>
                      {patch.impact ? (
                        <div className="mt-2 text-xs leading-5 text-muted-foreground">
                          {copy.impact}：{patch.impact}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              </div>
            ) : null}

            {(draft?.validation_issues?.length ?? 0) > 0 ? (
              <div className="rounded-2xl border border-amber-300/50 bg-amber-500/5 p-4">
                <div className="mb-2 text-sm font-semibold text-amber-800">{copy.validation}</div>
                <div className="space-y-1 text-sm leading-6 text-amber-900">
                  {draft?.validation_issues.map((issue, index) => (
                    <div key={`${issue}:${index}`}>• {issue}</div>
                  ))}
                </div>
              </div>
            ) : null}
          </section>
        </div>
      </DialogContent>
    </Dialog>
  );
}
