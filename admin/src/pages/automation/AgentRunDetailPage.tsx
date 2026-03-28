import { useGetApprovalsApiV1AdminAutomationApprovalsGet, useGetRunApiV1AdminAutomationRunsRunIdGet, useGetRunStepsApiV1AdminAutomationRunsRunIdStepsGet } from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { Badge } from "@/components/ui/Badge";
import { useParams } from "react-router-dom";
import { useI18n } from "@/i18n";
import { AgentSectionSwitch } from "./AgentSectionSwitch";

export default function AgentRunDetailPage() {
  const { t } = useI18n();
  const { runId = "" } = useParams();
  const { data: runRaw, isLoading: runLoading } = useGetRunApiV1AdminAutomationRunsRunIdGet(runId, { query: { enabled: !!runId, refetchInterval: 5000 } });
  const { data: stepsRaw, isLoading: stepsLoading } = useGetRunStepsApiV1AdminAutomationRunsRunIdStepsGet(runId, { query: { enabled: !!runId, refetchInterval: 5000 } });
  const { data: approvalsRaw } = useGetApprovalsApiV1AdminAutomationApprovalsGet({ query: { refetchInterval: 5000 } });
  const run = runRaw?.data;
  const steps = stepsRaw?.data ?? [];
  const approvals = (approvalsRaw?.data ?? []).filter((item) => item.run_id === runId);

  return (
    <div>
      <PageHeader title={t("automation.runDetail")} description={runId} secondary={<AgentSectionSwitch />} />
      <div className="grid gap-4">
        <AdminSurface eyebrow="Run" title={run?.workflow_key || t("automation.runDetail")} description={run?.trigger_event || run?.trigger_kind}>
          {runLoading ? (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : run ? (
            <div className="grid gap-3 md:grid-cols-2">
              <div><div className="text-xs text-muted-foreground">ID</div><code className="text-xs break-all">{run.id}</code></div>
              <div><div className="text-xs text-muted-foreground">{t("automation.status")}</div><Badge variant="outline">{run.status}</Badge></div>
              <div><div className="text-xs text-muted-foreground">{t("automation.target")}</div><div className="text-sm">{[run.target_type, run.target_id].filter(Boolean).join(":") || "-"}</div></div>
              <div><div className="text-xs text-muted-foreground">Thread</div><code className="text-xs break-all">{run.thread_id}</code></div>
              <div><div className="text-xs text-muted-foreground">Checkpoint ID</div><code className="text-xs break-all">{run.latest_checkpoint_id || "-"}</code></div>
              <div><div className="text-xs text-muted-foreground">Checkpoint NS</div><code className="text-xs break-all">{run.checkpoint_ns || "-"}</code></div>
            </div>
          ) : (
            <p className="text-sm text-muted-foreground">-</p>
          )}
        </AdminSurface>

        <AdminSurface eyebrow="Result" title={t("automation.resultPayload")} description={t("automation.resultPayloadDescription")}>
          <pre className="overflow-x-auto rounded-md bg-muted/60 p-3 text-xs">{JSON.stringify(run?.result_payload ?? {}, null, 2)}</pre>
        </AdminSurface>

        <AdminSurface eyebrow="Approvals" title={t("automation.approvals")} description={t("automation.approvalsDescription")}>
          <div className="space-y-3">
            {approvals.map((approval) => (
              <div key={approval.id} className="rounded-[var(--admin-radius-lg)] border border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="font-medium">{approval.approval_type}</div>
                    <div className="text-xs text-muted-foreground">{approval.node_key}</div>
                  </div>
                  <Badge variant="outline">{approval.status}</Badge>
                </div>
              </div>
            ))}
            {approvals.length === 0 && <p className="text-sm text-muted-foreground">{t("common.noData")}</p>}
          </div>
        </AdminSurface>

        <AdminSurface eyebrow="Steps" title={t("automation.steps")} description={t("automation.stepsDescription")}>
          {stepsLoading ? (
            <p className="text-sm text-muted-foreground">{t("common.loading")}</p>
          ) : (
            <div className="space-y-3">
              {steps.map((step) => (
                <div key={step.id} className="rounded-[var(--admin-radius-lg)] border border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div>
                      <div className="font-medium">{step.node_key}</div>
                      <div className="text-xs text-muted-foreground">{step.step_kind}</div>
                    </div>
                    <Badge variant="outline">{step.status}</Badge>
                  </div>
                  <p className="mt-3 text-sm text-muted-foreground">{step.narrative}</p>
                </div>
              ))}
              {steps.length === 0 && <p className="text-sm text-muted-foreground">{t("common.noData")}</p>}
            </div>
          )}
        </AdminSurface>
      </div>
    </div>
  );
}
