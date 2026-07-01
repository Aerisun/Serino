import { keepPreviousData, queryOptions, type QueryClient } from "@tanstack/react-query";
import type { EnhancedDashboardStats } from "@serino/api-client/models";
import { adminApiRequest } from "@/lib/adminApi";

export const DASHBOARD_STATS_QUERY_KEY = ["dashboard", "stats"] as const;
export const DASHBOARD_STATS_STALE_TIME = 3 * 60_000;
const DASHBOARD_STATS_GC_TIME = 10 * 60_000;

export function getDashboardStats(signal?: AbortSignal) {
  return adminApiRequest<EnhancedDashboardStats>("/api/v1/admin/system/dashboard/stats?summary_only=true", {
    method: "GET",
    signal,
  });
}

export function dashboardStatsQueryOptions() {
  return queryOptions({
    queryKey: DASHBOARD_STATS_QUERY_KEY,
    queryFn: ({ signal }) => getDashboardStats(signal),
    staleTime: DASHBOARD_STATS_STALE_TIME,
    gcTime: DASHBOARD_STATS_GC_TIME,
    placeholderData: keepPreviousData,
    refetchOnWindowFocus: false,
  });
}

export function prefetchDashboardStats(queryClient: QueryClient) {
  return queryClient.prefetchQuery(dashboardStatsQueryOptions());
}
