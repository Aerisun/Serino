import type { DehydratedState, QueryClient } from "@tanstack/react-query";

export const QUERY_CACHE_STORAGE_KEY = "aerisun:query-cache:v2";
export const QUERY_CACHE_TTL_MS = 10 * 60_000;

export const shouldPersistQueryKey = (queryKey: readonly unknown[]) => {
  const [first] = queryKey;
  return typeof first === "string" && first.startsWith("/api/v1/site-interactions/");
};

export const isFreshnessSensitiveQueryKey = (queryKey: readonly unknown[]) => {
  const [first] = queryKey;

  if (first === "site") {
    return true;
  }

  if (typeof first !== "string") {
    return false;
  }

  return (
    first === "/api/v1/site/posts" ||
    first.startsWith("/api/v1/site/posts/") ||
    first === "/api/v1/site/diary" ||
    first.startsWith("/api/v1/site/diary/") ||
    first === "/api/v1/site/thoughts" ||
    first === "/api/v1/site/excerpts" ||
    first === "/api/v1/site/friends" ||
    first === "/api/v1/site/friend-feed" ||
    first === "/api/v1/site/recent-activity" ||
    first === "/api/v1/site/activity-heatmap" ||
    first === "/api/v1/site/calendar"
  );
};

export const isAuthSensitiveQueryKey = (queryKey: readonly unknown[]) => {
  const [first] = queryKey;

  if (first === "site") {
    return true;
  }

  if (typeof first !== "string") {
    return false;
  }

  return first.startsWith("/api/v1/site/") || first.startsWith("/api/v1/site-interactions/");
};

export const clearPersistedQueryState = () => {
  if (typeof sessionStorage === "undefined") {
    return;
  }

  try {
    sessionStorage.removeItem(QUERY_CACHE_STORAGE_KEY);
  } catch {
    // Ignore storage failures.
  }
};

export const readPersistedQueryState = (): DehydratedState | null => {
  if (typeof sessionStorage === "undefined") {
    return null;
  }

  try {
    const raw = sessionStorage.getItem(QUERY_CACHE_STORAGE_KEY);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as { persistedAt?: number; state?: DehydratedState };
    if (!parsed || typeof parsed.persistedAt !== "number" || !parsed.state) {
      sessionStorage.removeItem(QUERY_CACHE_STORAGE_KEY);
      return null;
    }

    if (Date.now() - parsed.persistedAt > QUERY_CACHE_TTL_MS) {
      sessionStorage.removeItem(QUERY_CACHE_STORAGE_KEY);
      return null;
    }

    return parsed.state;
  } catch {
    try {
      sessionStorage.removeItem(QUERY_CACHE_STORAGE_KEY);
    } catch {
      // Ignore storage failures.
    }
    return null;
  }
};

export const resetAuthSensitiveQueryCache = async (queryClient: QueryClient) => {
  const predicate = (query: { queryKey: readonly unknown[] }) =>
    isAuthSensitiveQueryKey(query.queryKey);

  clearPersistedQueryState();
  await queryClient.cancelQueries({ predicate });
  await queryClient.resetQueries({ predicate }, { cancelRefetch: true });
};
