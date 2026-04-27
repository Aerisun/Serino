import { queryOptions, type QueryClient } from "@tanstack/react-query";
import type {
  PaginatedResponseCommentAdminRead,
  PaginatedResponseGuestbookAdminRead,
} from "@serino/api-client/models";
import { adminApiRequest } from "@/lib/adminApi";

export const MODERATION_PENDING_COUNT_QUERY_KEY = ["moderation", "pending-count"] as const;
export const MODERATION_PENDING_COUNT_STALE_TIME = 60_000;
const MODERATION_PENDING_COUNT_GC_TIME = 10 * 60_000;

function normalizeCount(value: unknown) {
  if (typeof value === "number") {
    return value;
  }

  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isFinite(parsed) ? parsed : 0;
  }

  return 0;
}

export async function getPendingModerationCount(signal?: AbortSignal) {
  const [commentsResponse, guestbookResponse] = await Promise.all([
    adminApiRequest<PaginatedResponseCommentAdminRead>("/api/v1/admin/moderation/comments", {
      method: "GET",
      signal,
      query: {
        page: 1,
        page_size: 1,
        status: "pending",
      },
    }),
    adminApiRequest<PaginatedResponseGuestbookAdminRead>("/api/v1/admin/moderation/guestbook", {
      method: "GET",
      signal,
      query: {
        page: 1,
        page_size: 1,
        status: "pending",
      },
    }),
  ]);

  const comments = normalizeCount(commentsResponse.total);
  const guestbook = normalizeCount(guestbookResponse.total);

  return {
    comments,
    guestbook,
    total: comments + guestbook,
  };
}

export function pendingModerationCountQueryOptions() {
  return queryOptions({
    queryKey: MODERATION_PENDING_COUNT_QUERY_KEY,
    queryFn: ({ signal }) => getPendingModerationCount(signal),
    staleTime: MODERATION_PENDING_COUNT_STALE_TIME,
    gcTime: MODERATION_PENDING_COUNT_GC_TIME,
  });
}

export function prefetchPendingModerationCount(queryClient: QueryClient) {
  return queryClient.prefetchQuery(pendingModerationCountQueryOptions());
}
