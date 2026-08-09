export const AUTOMATION_RUN_DETAIL_POLL_INTERVAL = 5_000;

const LIVE_AUTOMATION_RUN_STATUSES = new Set([
  "queued",
  "running",
  "awaiting_approval",
  "interrupted",
]);

export function isAutomationRunLiveStatus(status: string | null | undefined) {
  return LIVE_AUTOMATION_RUN_STATUSES.has(String(status || "").trim().toLowerCase());
}
