import type { SystemUpdateStatusRead } from "@serino/api-client/models";

export const AUTO_CHECK_STALE_MS = 2 * 60 * 1000;

export function isCheckedAtStale(checkedAt: string | null | undefined, now = Date.now()) {
  if (!checkedAt) return true;
  const checkedAtMs = Date.parse(checkedAt);
  return Number.isNaN(checkedAtMs) || now - checkedAtMs >= AUTO_CHECK_STALE_MS;
}

export function shouldQueueSilentUpdateCheck({
  autoCheckPending,
  isError,
  isStateActive,
  lastAutoCheckRequestedAt,
  now = Date.now(),
  state,
  status,
}: {
  autoCheckPending: boolean;
  isError: boolean;
  isStateActive: boolean;
  lastAutoCheckRequestedAt: number;
  now?: number;
  state: SystemUpdateStatusRead["state"] | undefined;
  status: SystemUpdateStatusRead | null | undefined;
}) {
  if (
    !status
    || isError
    || status.update_available
    || state === "unsupported"
    || isStateActive
    || autoCheckPending
    || !isCheckedAtStale(status.checked_at, now)
  ) {
    return false;
  }

  return now - lastAutoCheckRequestedAt >= AUTO_CHECK_STALE_MS;
}

function isGithubReleaseNotFoundPayload(notes: string) {
  try {
    const payload = JSON.parse(notes) as { message?: unknown; status?: unknown };
    return payload.message === "Not Found" && String(payload.status) === "404";
  } catch {
    return false;
  }
}

function isGeneratedEmptyReleaseNotes(notes: string) {
  return notes.includes("本版本未提供额外更新说明。") || notes.includes("No release notes were provided");
}

export function shouldShowUpdateReleaseNotes(status: SystemUpdateStatusRead | null | undefined) {
  if (!status?.auto_update_supported) return false;

  const notes = status.release?.notes?.trim() ?? "";
  if (!notes) return false;
  if (isGithubReleaseNotFoundPayload(notes)) return false;

  if ((status.channel || "").toLowerCase() === "dev" && isGeneratedEmptyReleaseNotes(notes)) {
    return false;
  }

  return true;
}
