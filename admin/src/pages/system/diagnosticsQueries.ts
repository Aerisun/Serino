import { queryOptions } from "@tanstack/react-query";
import {
  getSystemDiagnosticsStateApiV1AdminSystemDiagnosticsGet,
  startSystemDiagnosticsRunApiV1AdminSystemDiagnosticsRunPost,
} from "@serino/api-client/admin";
import type { SystemDiagnosticStateRead } from "@serino/api-client/models";

const DIAGNOSTICS_STALE_TIME = 5 * 60_000;
const DIAGNOSTICS_GC_TIME = 15 * 60_000;

export function systemDiagnosticsQueryKey(includeItems: boolean) {
  return ["admin", "system-diagnostics", includeItems ? "full" : "summary"] as const;
}

export function diagnosticPollingInterval(
  state: Pick<SystemDiagnosticStateRead, "is_running"> | undefined,
  fetchFailureCount = 0,
  idleIntervalMs: number | false = false,
) {
  if (!state || fetchFailureCount > 0) return false;
  return state.is_running ? 3_000 : idleIntervalMs;
}

async function getSystemDiagnostics(
  includeItems: boolean,
  signal?: AbortSignal,
): Promise<SystemDiagnosticStateRead> {
  const response = await getSystemDiagnosticsStateApiV1AdminSystemDiagnosticsGet(
    { include_items: includeItems },
    { signal },
  );
  if (response.status !== 200) {
    throw new Error("Unable to load system diagnostics");
  }
  return response.data;
}

export function systemDiagnosticsQueryOptions({
  includeItems,
  pollWhileRunning = false,
}: {
  includeItems: boolean;
  pollWhileRunning?: boolean;
}) {
  return queryOptions({
    queryKey: systemDiagnosticsQueryKey(includeItems),
    queryFn: ({ signal }) => getSystemDiagnostics(includeItems, signal),
    staleTime: includeItems ? 30_000 : DIAGNOSTICS_STALE_TIME,
    gcTime: DIAGNOSTICS_GC_TIME,
    retry: false,
    refetchOnMount: includeItems ? "always" : true,
    refetchOnWindowFocus: false,
    refetchIntervalInBackground: false,
    refetchInterval: pollWhileRunning
      ? (query) =>
          diagnosticPollingInterval(
            query.state.data,
            query.state.fetchFailureCount,
            includeItems ? false : DIAGNOSTICS_STALE_TIME,
          )
      : false,
  });
}

export async function startSystemDiagnosticRun(): Promise<SystemDiagnosticStateRead> {
  const response = await startSystemDiagnosticsRunApiV1AdminSystemDiagnosticsRunPost();
  return response.data;
}
