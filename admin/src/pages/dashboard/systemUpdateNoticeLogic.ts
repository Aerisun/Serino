import type { SystemUpdateStatusRead } from "@serino/api-client/models";

export const AUTO_CHECK_STALE_MS = 2 * 60 * 1000;
const SEMVER_PATTERN = /^v?(\d+)\.(\d+)\.(\d+)$/;
const CACHE_CLEAR_STATES = new Set<SystemUpdateStatusRead["state"]>([
  "idle",
  "available",
  "unsupported",
  "succeeded",
]);

function parseSemver(value: string | null | undefined) {
  if (!value) return null;
  const match = SEMVER_PATTERN.exec(value.trim());
  if (!match) return null;
  return match.slice(1).map((part) => Number.parseInt(part, 10)) as [number, number, number];
}

export function hasHigherUpdateVersion(status: SystemUpdateStatusRead | null | undefined) {
  const current = parseSemver(status?.current_version);
  const latest = parseSemver(status?.latest_version);
  if (!current || !latest) return false;
  for (let index = 0; index < latest.length; index += 1) {
    if (latest[index] > current[index]) return true;
    if (latest[index] < current[index]) return false;
  }
  return false;
}

export function shouldSurfaceUpdateStatus(status: SystemUpdateStatusRead | null | undefined) {
  return hasHigherUpdateVersion(status);
}

export function shouldCacheUpdateStatus(status: SystemUpdateStatusRead | null | undefined) {
  return hasHigherUpdateVersion(status);
}

export function shouldClearCachedUpdateStatus(status: SystemUpdateStatusRead | null | undefined) {
  return Boolean(status?.state && CACHE_CLEAR_STATES.has(status.state) && !hasHigherUpdateVersion(status));
}

export function resolveUpdateNoticeStatus(
  status: SystemUpdateStatusRead | null | undefined,
  cachedStatus: SystemUpdateStatusRead | null | undefined,
) {
  if (!status) return cachedStatus ?? null;
  if (hasHigherUpdateVersion(status)) return status;
  if (!shouldClearCachedUpdateStatus(status) && hasHigherUpdateVersion(cachedStatus)) {
    return cachedStatus ?? null;
  }
  return status;
}

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
    || hasHigherUpdateVersion(status)
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
