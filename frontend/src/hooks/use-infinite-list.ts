import { useRef, useEffect, useMemo, useCallback } from "react";
import { useInfiniteQuery, useQueryClient } from "@tanstack/react-query";
import { translateFrontendText } from "@/i18n";
import { clampPageSize } from "@/lib/page-size";

interface UseInfiniteListOptions<TRemote, TLocal> {
  queryKey: readonly unknown[];
  queryFn: (params: {
    limit: number;
    offset: number;
  }) => Promise<{ items: TRemote[]; has_more: boolean }>;
  pageSize: number;
  mapItem: (item: TRemote, index: number) => TLocal;
  enabled?: boolean;
}

interface UseInfiniteListResult<TLocal> {
  items: TLocal[];
  status: "loading" | "ready" | "empty" | "error";
  errorMessage: string;
  hasMore: boolean;
  isLoadingMore: boolean;
  sentinelRef: React.RefObject<HTMLDivElement | null>;
  reload: () => void;
}

export function useInfiniteList<TRemote, TLocal>(
  options: UseInfiniteListOptions<TRemote, TLocal>,
): UseInfiniteListResult<TLocal> {
  const { queryKey, queryFn, pageSize, mapItem, enabled = true } = options;
  const safePageSize = clampPageSize(pageSize, 20);
  const sentinelRef = useRef<HTMLDivElement | null>(null);
  const queryClient = useQueryClient();

  const {
    data,
    isLoading,
    isError,
    error,
    fetchNextPage,
    hasNextPage,
    isFetchingNextPage,
  } = useInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam = 0 }) =>
      queryFn({ limit: safePageSize, offset: pageParam as number }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage.has_more) return undefined;
      const totalItems = allPages.reduce((sum, p) => sum + p.items.length, 0);
      return totalItems;
    },
    enabled,
  });

  const items = useMemo(() => {
    if (!data?.pages) return [];
    let globalIndex = 0;
    return data.pages.flatMap((page) =>
      page.items.map((item) => mapItem(item, globalIndex++)),
    );
  }, [data?.pages, mapItem]);

  const status = isLoading
    ? "loading"
    : isError
      ? "error"
      : items.length === 0
        ? "empty"
        : "ready";

  const errorMessage =
    error instanceof Error ? error.message : isError ? translateFrontendText("list.loadFailed") : "";

  const reload = useCallback(() => {
    queryClient.invalidateQueries({ queryKey });
  }, [queryClient, queryKey]);

  // IntersectionObserver for infinite scroll
  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || !hasNextPage || status !== "ready") return;

    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !isFetchingNextPage) {
          void fetchNextPage();
        }
      },
      { rootMargin: "200px" },
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasNextPage, status, isFetchingNextPage, fetchNextPage]);

  return {
    items,
    status,
    errorMessage,
    hasMore: hasNextPage ?? false,
    isLoadingMore: isFetchingNextPage,
    sentinelRef,
    reload,
  };
}
