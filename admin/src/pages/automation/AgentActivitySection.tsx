import { useState } from "react";
import { useGetApprovalsApiV1AdminAutomationApprovalsGet, useGetRunsApiV1AdminAutomationRunsGet } from "@serino/api-client/admin";
import { AdminSegmentedFilter } from "@/components/ui/AdminSegmentedFilter";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";
import { AgentRunsPanel } from "./AgentRunsPage";
import { ApprovalsPanel } from "./ApprovalsPage";
import { isAutomationRunLiveStatus } from "./automation-query-shared";

type ActivityView = "runs" | "approvals";

const COPY = {
  zh: {
    approvals: "待审批",
    active: "进行中",
    runs: "最近运行",
    failed: "失败",
    approvalsList: "审批列表",
    runsList: "运行记录",
  },
  en: {
    approvals: "Pending approvals",
    active: "Active",
    runs: "Recent runs",
    failed: "Failed",
    approvalsList: "Approvals",
    runsList: "Runs",
  },
} as const;

export function AgentActivitySection() {
  const { lang } = useI18n();
  const [view, setView] = useState<ActivityView>("runs");
  const copy = COPY[lang];
  const { data: approvalsRaw } = useGetApprovalsApiV1AdminAutomationApprovalsGet();
  const { data: runsRaw } = useGetRunsApiV1AdminAutomationRunsGet();
  const approvals = approvalsRaw?.data ?? [];
  const runs = runsRaw?.data ?? [];
  const activeRuns = runs.filter((item) => isAutomationRunLiveStatus(item.status)).length;
  const failedRuns = runs.filter((item) => item.status === "failed").length;

  const metrics = [
    { key: "approvals", label: copy.approvals, value: approvals.length },
    { key: "active", label: copy.active, value: activeRuns },
    { key: "runs", label: copy.runs, value: runs.length },
    { key: "failed", label: copy.failed, value: failedRuns },
  ] as const;

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-center">
        <AdminSegmentedFilter
          value={view}
          onValueChange={(next) => setView(next as ActivityView)}
          items={[
            { value: "approvals", label: copy.approvalsList, badge: approvals.length },
            { value: "runs", label: copy.runsList, badge: runs.length },
          ]}
          width="content"
          className="!border-none !bg-transparent !p-0 !shadow-none !rounded-none [&::before]:hidden md:mr-4 md:shrink-0"
        />

        <div className="flex min-w-0 items-center gap-2 overflow-x-auto sm:gap-3 md:ml-auto">
          {metrics.map((item) => (
            <div
              key={item.key}
              className={cn(
                "inline-flex shrink-0 items-center gap-2 rounded-full border px-3 py-1.5",
                item.key === "approvals"
                  ? "border-amber-300/70 bg-amber-500/12 text-amber-700 dark:border-amber-300/35 dark:bg-amber-400/12 dark:text-amber-300"
                  : "border-border/60 bg-background/75",
              )}
            >
              <span
                className={cn(
                  "text-xs font-medium",
                  item.key === "approvals" ? "text-amber-700/90 dark:text-amber-300/90" : "text-muted-foreground",
                )}
              >
                {item.label}
              </span>
              <span
                className={cn(
                  "text-sm font-semibold tabular-nums",
                  item.key === "approvals" ? "text-amber-700 dark:text-amber-300" : "text-foreground",
                )}
              >
                {item.value}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="min-w-0">
        {view === "runs" ? (
          <AgentRunsPanel runDetailBasePath="/agent/activity/runs" />
        ) : (
          <ApprovalsPanel runDetailBasePath="/agent/activity/runs" />
        )}
      </div>
    </div>
  );
}
