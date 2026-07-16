import { queryOptions, type QueryClient } from "@tanstack/react-query";
import { getAttentionCountsApiV1AdminModerationAttentionCountsGet } from "@serino/api-client/admin";
import type { ModerationAttentionCounts } from "@serino/api-client/models";

export const MODERATION_ATTENTION_COUNT_QUERY_KEY = ["moderation", "attention-counts"] as const;
export const MODERATION_ATTENTION_COUNT_STALE_TIME = 60_000;
const MODERATION_ATTENTION_COUNT_GC_TIME = 10 * 60_000;

export async function getModerationAttentionCounts(signal?: AbortSignal): Promise<ModerationAttentionCounts> {
  const response = await getAttentionCountsApiV1AdminModerationAttentionCountsGet({ signal });
  return response.data;
}

export function moderationAttentionCountQueryOptions() {
  return queryOptions({
    queryKey: MODERATION_ATTENTION_COUNT_QUERY_KEY,
    queryFn: ({ signal }) => getModerationAttentionCounts(signal),
    staleTime: MODERATION_ATTENTION_COUNT_STALE_TIME,
    gcTime: MODERATION_ATTENTION_COUNT_GC_TIME,
    refetchInterval: MODERATION_ATTENTION_COUNT_STALE_TIME,
    refetchOnWindowFocus: true,
  });
}

export function prefetchModerationAttentionCount(queryClient: QueryClient) {
  return queryClient.prefetchQuery(moderationAttentionCountQueryOptions());
}
