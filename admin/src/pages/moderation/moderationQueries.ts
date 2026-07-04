import { queryOptions, type QueryClient } from "@tanstack/react-query";
import type {
  PaginatedResponseCommentAdminRead,
  PaginatedResponseDiaryAccessRequestAdminRead,
  PaginatedResponseGuestbookAdminRead,
  SiteProfileAdminRead,
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
  const profileResponse = await adminApiRequest<SiteProfileAdminRead>("/api/v1/admin/site-config/profile", {
    method: "GET",
    signal,
  });
  const featureFlags = profileResponse.feature_flags;
  const diaryPrivateEnabled =
    typeof featureFlags === "object" &&
    featureFlags !== null &&
    "diary_private_enabled" in featureFlags
      ? Boolean((featureFlags as Record<string, unknown>).diary_private_enabled)
      : true;

  const diaryAccessPromise: Promise<PaginatedResponseDiaryAccessRequestAdminRead> = diaryPrivateEnabled
    ? adminApiRequest<PaginatedResponseDiaryAccessRequestAdminRead>("/api/v1/admin/moderation/diary-access-requests", {
        method: "GET",
        signal,
        query: {
          page: 1,
          page_size: 100,
        },
      })
    : Promise.resolve({
        items: [],
        total: 0,
        page: 1,
        page_size: 100,
      });

  const [commentsResponse, guestbookResponse, diaryAccessResponse] = await Promise.all([
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
    diaryAccessPromise,
  ]);

  const comments = normalizeCount(commentsResponse.total);
  const guestbook = normalizeCount(guestbookResponse.total);
  const diaryAccess = (diaryAccessResponse.items ?? []).filter((item) => item.status === "pending").length;

  return {
    comments,
    guestbook,
    diaryAccess,
    total: comments + guestbook + diaryAccess,
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
