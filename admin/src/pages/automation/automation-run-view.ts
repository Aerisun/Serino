import type {
  AgentOverviewRead,
  AgentRunCollectionRead,
  AgentRunRead,
} from "@serino/api-client/models";

export function getAutomationRunItems(
  collection: AgentRunCollectionRead | null | undefined,
): AgentRunRead[] {
  return collection?.items ?? [];
}

export function summarizeAutomationOverview(
  overview: AgentOverviewRead | null | undefined,
) {
  return {
    active:
      (overview?.queued_run_count ?? 0) +
      (overview?.running_run_count ?? 0) +
      (overview?.awaiting_approval_count ?? 0),
    approvals: overview?.pending_approval_count ?? 0,
    runs: overview?.total_run_count ?? 0,
    failed: overview?.recent_failed_run_count ?? 0,
  };
}

export function formatAutomationDuration(
  durationMs: number | null | undefined,
  lang: "zh" | "en",
) {
  if (durationMs === null || durationMs === undefined) return "-";
  if (durationMs < 1_000) {
    return lang === "zh" ? `${durationMs} 毫秒` : `${durationMs} ms`;
  }
  if (durationMs < 60_000) {
    const seconds = Math.round(durationMs / 100) / 10;
    return lang === "zh" ? `${seconds} 秒` : `${seconds} s`;
  }

  const totalSeconds = Math.round(durationMs / 1_000);
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = totalSeconds % 60;
  if (lang === "zh") {
    return seconds ? `${minutes} 分 ${seconds} 秒` : `${minutes} 分`;
  }
  return seconds ? `${minutes}m ${seconds}s` : `${minutes}m`;
}
