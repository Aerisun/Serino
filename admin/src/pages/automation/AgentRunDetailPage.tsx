import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getGetOverviewApiV1AdminAutomationOverviewGetQueryKey,
  getGetRunApiV1AdminAutomationRunsRunIdGetQueryKey,
  getGetRunsApiV1AdminAutomationRunsGetQueryKey,
  getGetRunStepsApiV1AdminAutomationRunsRunIdStepsGetQueryKey,
  useGetApprovalsApiV1AdminAutomationApprovalsGet,
  useGetRunApiV1AdminAutomationRunsRunIdGet,
  useGetRunStepsApiV1AdminAutomationRunsRunIdStepsGet,
  usePostRunCancelApiV1AdminAutomationRunsRunIdCancelPost,
  usePostRunRetryApiV1AdminAutomationRunsRunIdRetryPost,
} from "@serino/api-client/admin";
import type { AgentRunCollectionRead } from "@serino/api-client/models";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { StatusBadge } from "@/components/StatusBadge";
import { useNavigate, useParams } from "react-router-dom";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { formatDate } from "@/lib/utils";
import { RotateCw, XCircle } from "lucide-react";
import { toast } from "sonner";
import { AgentSectionSwitch } from "./AgentSectionSwitch";
import {
  AUTOMATION_RUN_DETAIL_POLL_INTERVAL,
  isAutomationRunLiveStatus,
} from "./automation-query-shared";
import {
  formatAutomationDuration,
  getAutomationRunItems,
} from "./automation-run-view";
import { AutomationQueryError } from "./AutomationQueryError";

type RunAction = "cancel" | "retry";

function payloadHasContent(value: unknown) {
  return Boolean(value && typeof value === "object" && Object.keys(value).length > 0);
}

function MetadataItem({ label, value, code = false }: { label: string; value: string; code?: boolean }) {
  return (
    <div className="min-w-0 space-y-1">
      <div className="text-xs text-muted-foreground">{label}</div>
      {code ? (
        <code className="block break-all text-xs text-foreground/90">{value}</code>
      ) : (
        <div className="break-words text-sm text-foreground/90">{value}</div>
      )}
    </div>
  );
}

export default function AgentRunDetailPage() {
  const { t, lang } = useI18n();
  const { runId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [pendingAction, setPendingAction] = useState<RunAction | null>(null);
  const cachedRun = useMemo(() => {
    const collections = queryClient.getQueriesData<{ data?: AgentRunCollectionRead }>({
      queryKey: getGetRunsApiV1AdminAutomationRunsGetQueryKey(),
    });
    for (const [, response] of collections) {
      const match = getAutomationRunItems(response?.data).find((item) => item.id === runId);
      if (match) return match;
    }
    return undefined;
  }, [queryClient, runId]);
  const { data: runRaw, isLoading: runLoading, isError: runError, refetch: refetchRun } =
    useGetRunApiV1AdminAutomationRunsRunIdGet(runId, {
      query: {
        enabled: !!runId,
        placeholderData: cachedRun
          ? { data: cachedRun, status: 200, headers: new Headers() }
          : undefined,
        refetchInterval: (query) =>
          isAutomationRunLiveStatus(query.state.data?.data?.status)
            ? AUTOMATION_RUN_DETAIL_POLL_INTERVAL
            : false,
        refetchOnWindowFocus: true,
      },
    });
  const run = runRaw?.data;
  const shouldPollRunDetails = isAutomationRunLiveStatus(run?.status);
  const { data: stepsRaw, isLoading: stepsLoading, isError: stepsError, refetch: refetchSteps } =
    useGetRunStepsApiV1AdminAutomationRunsRunIdStepsGet(runId, {
      query: {
        enabled: !!runId,
        refetchInterval: shouldPollRunDetails
          ? AUTOMATION_RUN_DETAIL_POLL_INTERVAL
          : false,
        refetchOnWindowFocus: true,
      },
    });
  const { data: approvalsRaw } = useGetApprovalsApiV1AdminAutomationApprovalsGet({
    query: { refetchOnWindowFocus: true },
  });
  const steps = stepsRaw?.data ?? [];
  const approvals = (approvalsRaw?.data ?? []).filter((item) => item.run_id === runId);

  const invalidateRunState = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: getGetRunApiV1AdminAutomationRunsRunIdGetQueryKey(runId) }),
      queryClient.invalidateQueries({ queryKey: getGetRunStepsApiV1AdminAutomationRunsRunIdStepsGetQueryKey(runId) }),
      queryClient.invalidateQueries({ queryKey: getGetRunsApiV1AdminAutomationRunsGetQueryKey() }),
      queryClient.invalidateQueries({ queryKey: getGetOverviewApiV1AdminAutomationOverviewGetQueryKey() }),
    ]);
  };

  const cancelRun = usePostRunCancelApiV1AdminAutomationRunsRunIdCancelPost({
    mutation: {
      onSuccess: async () => {
        setPendingAction(null);
        await invalidateRunState();
        toast.success(lang === "zh" ? "已请求取消运行" : "Run cancellation requested");
      },
      onError: (error: unknown) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const retryRun = usePostRunRetryApiV1AdminAutomationRunsRunIdRetryPost({
    mutation: {
      onSuccess: async (response) => {
        setPendingAction(null);
        await invalidateRunState();
        toast.success(lang === "zh" ? "已创建重试运行" : "Retry run created");
        navigate(`/agent/activity/runs/${response.data.id}`);
      },
      onError: (error: unknown) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const actionPending = cancelRun.isPending || retryRun.isPending;
  const executionMode = run?.execution_mode === "dry_run"
    ? (lang === "zh" ? "模拟运行" : "Dry run")
    : (lang === "zh" ? "正式执行" : "Live");

  return (
    <div>
      <PageHeader
        title={t("automation.runDetail")}
        description={runId}
        secondary={<AgentSectionSwitch />}
      />
      <div className="grid gap-4">
        <AdminSurface
          eyebrow="Run"
          title={run?.workflow_key || t("automation.runDetail")}
          description={run?.trigger_event || run?.trigger_kind}
          actions={run ? (
            <div className="flex flex-wrap gap-2">
              {run.can_cancel ? (
                <Button variant="destructive" size="sm" onClick={() => setPendingAction("cancel")}>
                  <XCircle className="mr-2 h-4 w-4" />
                  {lang === "zh" ? "取消运行" : "Cancel run"}
                </Button>
              ) : null}
              {run.can_retry ? (
                <Button variant="outline" size="sm" onClick={() => setPendingAction("retry")}>
                  <RotateCw className="mr-2 h-4 w-4" />
                  {lang === "zh" ? "重新运行" : "Retry"}
                </Button>
              ) : null}
            </div>
          ) : null}
        >
          {runError ? (
            <AutomationQueryError lang={lang} onRetry={() => void refetchRun()} />
          ) : runLoading ? (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : run ? (
            <div className="space-y-5">
              <div className="flex flex-wrap items-center gap-2">
                <StatusBadge status={run.status} />
                <Badge variant={run.execution_mode === "dry_run" ? "outline" : "info"}>{executionMode}</Badge>
                {run.cancel_requested_at ? (
                  <Badge variant="warning">{lang === "zh" ? "正在取消" : "Cancelling"}</Badge>
                ) : null}
              </div>
              <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <MetadataItem label="ID" value={run.id} code />
                <MetadataItem
                  label={lang === "zh" ? "目标" : "Target"}
                  value={[run.target_type, run.target_id].filter(Boolean).join(":") || "-"}
                />
                <MetadataItem
                  label={lang === "zh" ? "尝试次数" : "Attempts"}
                  value={`${run.attempt_count ?? 0} / ${run.max_attempts ?? 0}`}
                />
                <MetadataItem
                  label={lang === "zh" ? "耗时" : "Duration"}
                  value={formatAutomationDuration(run.duration_ms, lang)}
                />
                <MetadataItem
                  label={lang === "zh" ? "请求主体" : "Requested by"}
                  value={[run.requested_by_type, run.requested_by_id].filter(Boolean).join(":") || "-"}
                />
                <MetadataItem label="Thread" value={run.thread_id} code />
                <MetadataItem
                  label={lang === "zh" ? "创建时间" : "Created"}
                  value={formatDate(run.created_at)}
                />
                <MetadataItem
                  label={lang === "zh" ? "开始 / 完成" : "Started / finished"}
                  value={`${run.started_at ? formatDate(run.started_at) : "-"} / ${run.finished_at ? formatDate(run.finished_at) : "-"}`}
                />
                {run.retry_of_run_id ? <MetadataItem label={lang === "zh" ? "重试来源" : "Retry of"} value={run.retry_of_run_id} code /> : null}
                {run.idempotency_key ? <MetadataItem label="Idempotency key" value={run.idempotency_key} code /> : null}
                {run.lease_owner ? <MetadataItem label={lang === "zh" ? "执行租约" : "Lease owner"} value={run.lease_owner} code /> : null}
                {run.heartbeat_at ? <MetadataItem label={lang === "zh" ? "最近心跳" : "Last heartbeat"} value={formatDate(run.heartbeat_at)} /> : null}
              </div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">-</p>
          )}
        </AdminSurface>

        {run?.error_message || run?.error_code ? (
          <AdminSurface
            eyebrow="Failure"
            title={lang === "zh" ? "失败原因" : "Failure reason"}
            surface="soft"
            className="border-destructive/35 bg-destructive/[0.04]"
          >
            <div className="space-y-2">
              {run.error_code ? <code className="text-xs text-destructive">{run.error_code}</code> : null}
              {run.error_message ? <p className="text-sm leading-6 text-foreground/90">{run.error_message}</p> : null}
            </div>
          </AdminSurface>
        ) : null}

        <AdminSurface
          eyebrow="Steps"
          title={t("automation.steps")}
          description={t("automation.stepsDescription")}
        >
          {stepsError ? (
            <AutomationQueryError lang={lang} onRetry={() => void refetchSteps()} />
          ) : stepsLoading ? (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : (
            <div className="space-y-0">
              {steps.map((step, index) => (
                <div key={step.id} className="relative flex gap-4 pb-5 last:pb-0">
                  {index < steps.length - 1 ? (
                    <div className="absolute bottom-0 left-4 top-8 w-px bg-border/70" />
                  ) : null}
                  <div className="relative z-10 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-border/70 bg-background text-xs font-semibold tabular-nums">
                    {step.sequence_no}
                  </div>
                  <div className="min-w-0 flex-1 rounded-[var(--admin-radius-lg)] border border-border/60 bg-background/50 p-4">
                    <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                      <div>
                        <div className="font-medium">{step.node_key}</div>
                        <div className="mt-1 text-xs text-muted-foreground">{step.step_kind}</div>
                      </div>
                      <div className="flex flex-wrap items-center gap-2">
                        <StatusBadge status={step.status} />
                        <span className="text-xs text-muted-foreground">
                          {step.finished_at || step.started_at ? formatDate(step.finished_at || step.started_at || step.created_at) : ""}
                        </span>
                      </div>
                    </div>
                    {step.narrative ? <p className="mt-3 text-sm leading-6 text-muted-foreground">{step.narrative}</p> : null}
                    {payloadHasContent(step.error_payload) ? (
                      <pre className="mt-3 overflow-x-auto rounded-md bg-destructive/8 p-3 text-xs text-destructive">{JSON.stringify(step.error_payload, null, 2)}</pre>
                    ) : null}
                  </div>
                </div>
              ))}
              {steps.length === 0 ? <p className="text-sm text-muted-foreground">{t("common.noData")}</p> : null}
            </div>
          )}
        </AdminSurface>

        <AdminSurface
          eyebrow="Approvals"
          title={t("automation.approvals")}
          description={t("automation.approvalsDescription")}
        >
          <div className="space-y-3">
            {approvals.map((approval) => (
              <div key={approval.id} className="rounded-[var(--admin-radius-lg)] border border-amber-300/60 bg-amber-500/[0.06] p-4 dark:border-amber-300/25">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium">{approval.approval_type}</div>
                    <div className="text-xs text-muted-foreground">{approval.node_key}</div>
                  </div>
                  <StatusBadge status={approval.status} />
                </div>
              </div>
            ))}
            {approvals.length === 0 ? <p className="text-sm text-muted-foreground">{t("common.noData")}</p> : null}
          </div>
        </AdminSurface>

        <AdminSurface
          eyebrow="Result"
          title={t("automation.resultPayload")}
          description={t("automation.resultPayloadDescription")}
        >
          <pre className="max-h-[480px] overflow-auto rounded-md bg-muted/60 p-3 text-xs">{JSON.stringify(run?.result_payload ?? {}, null, 2)}</pre>
        </AdminSurface>
      </div>

      <ConfirmDialog
        open={pendingAction !== null}
        title={pendingAction === "cancel"
          ? (lang === "zh" ? "确认取消这次运行？" : "Cancel this run?")
          : (lang === "zh" ? "确认重新运行？" : "Retry this run?")}
        description={pendingAction === "cancel"
          ? (lang === "zh" ? "系统会尽快停止后续步骤；已经完成的外部操作不会自动回滚。" : "The system will stop future steps as soon as possible. Completed external actions are not rolled back.")
          : (lang === "zh" ? "系统会基于原始输入创建一条新的独立运行记录。" : "A new independent run will be created from the original input.")}
        confirmLabel={pendingAction === "cancel"
          ? (lang === "zh" ? "确认取消" : "Cancel run")
          : (lang === "zh" ? "确认重试" : "Retry")}
        variant={pendingAction === "cancel" ? "destructive" : "default"}
        isPending={actionPending}
        onCancel={() => setPendingAction(null)}
        onConfirm={() => {
          if (pendingAction === "cancel") cancelRun.mutate({ runId });
          if (pendingAction === "retry") retryRun.mutate({ runId });
        }}
      />
    </div>
  );
}
