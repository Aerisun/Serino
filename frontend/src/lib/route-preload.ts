import type { QueryClient } from "@tanstack/react-query";
import {
  getReadActivityHeatmapApiV1SiteActivityHeatmapGetQueryOptions,
  getReadCalendarApiV1SiteCalendarGetQueryOptions,
  getReadDiaryEntryApiV1SiteDiarySlugGetQueryOptions,
  getReadFriendFeedApiV1SiteFriendFeedGetQueryOptions,
  getReadFriendsApiV1SiteFriendsGetQueryOptions,
  getReadPostApiV1SitePostsSlugGetQueryOptions,
  getReadRecentActivityApiV1SiteRecentActivityGetQueryOptions,
  readDiaryApiV1SiteDiaryGet,
  readExcerptsApiV1SiteExcerptsGet,
  readPostsApiV1SitePostsGet,
  readThoughtsApiV1SiteThoughtsGet,
} from "@serino/api-client/site";
import { DEFAULT_COMMUNITY_CONFIG, loadCommunityConfig } from "@/lib/community-config";
import { primeGuestbookPage } from "@/lib/community-cache";
import type { BaseViewPageConfig } from "@/lib/page-config";
import { clampPageSize } from "@/lib/page-size";
import type { RuntimeConfigSnapshot } from "@/lib/runtime-config";
import { getBeijingNowParts } from "@/lib/time";

type RuntimePages = RuntimeConfigSnapshot["pages"];

const PREFETCH_STALE_TIME_MS = 5 * 60_000;
const PREFETCH_GC_TIME_MS = 20 * 60_000;
const RECENT_ACTIVITY_LIMIT = 8;
const FRIEND_FEED_HOME_LIMIT = 12;
const FRIEND_FEED_PAGE_LIMIT = 200;
const ACTIVITY_HEATMAP_PARAMS = { weeks: 52, tz: "Asia/Shanghai" } as const;

const readPageSize = (
  pages: RuntimePages | undefined,
  key: string,
  fallback: number,
) =>
  clampPageSize(
    ((pages?.[key] ?? {}) as BaseViewPageConfig | undefined)?.pageSize,
    fallback,
  );

const prefetchInfiniteSiteList = <TItem>(
  queryClient: QueryClient,
  queryKey: readonly unknown[],
  pageSize: number,
  loader: (params: { limit: number; offset: number }) => Promise<{
    items: TItem[];
    has_more: boolean;
  }>,
) =>
  queryClient.prefetchInfiniteQuery({
    queryKey,
    queryFn: ({ pageParam = 0 }) =>
      loader({
        limit: pageSize,
        offset: pageParam as number,
      }),
    initialPageParam: 0,
    getNextPageParam: (lastPage, allPages) => {
      if (!lastPage.has_more) {
        return undefined;
      }
      return allPages.reduce((sum, page) => sum + page.items.length, 0);
    },
    staleTime: PREFETCH_STALE_TIME_MS,
    gcTime: PREFETCH_GC_TIME_MS,
  });

const prefetchSiteQuery = (
  queryClient: QueryClient,
  options: Parameters<QueryClient["prefetchQuery"]>[0],
) => queryClient.prefetchQuery(options);

const buildMonthRange = (year: number, monthIndex: number) => {
  const monthStart = new Date(year, monthIndex, 1);
  const monthEnd = new Date(year, monthIndex + 1, 0);
  const format = (value: Date) => {
    const valueYear = value.getFullYear();
    const valueMonth = String(value.getMonth() + 1).padStart(2, "0");
    const valueDay = String(value.getDate()).padStart(2, "0");
    return `${valueYear}-${valueMonth}-${valueDay}`;
  };

  return {
    from: format(monthStart),
    to: format(monthEnd),
  };
};

const normalizeInternalPath = (href: string | null | undefined) => {
  if (!href || typeof window === "undefined") {
    return null;
  }

  const trimmed = href.trim();
  if (!trimmed) {
    return null;
  }

  if (/^(mailto:|tel:|javascript:)/i.test(trimmed)) {
    return null;
  }

  try {
    const parsed = new URL(trimmed, window.location.origin);

    if (parsed.origin !== window.location.origin) {
      return null;
    }

    return `${parsed.pathname}${parsed.search}${parsed.hash}`;
  } catch {
    return null;
  }
};

export const preloadPostsPage = () => import("@/pages/Posts");
export const preloadPostDetailPage = () => import("@/pages/PostDetail");
export const preloadDiaryPage = () => import("@/pages/Diary");
export const preloadDiaryDetailPage = () => import("@/pages/DiaryDetail");
export const preloadThoughtsPage = () => import("@/pages/Thoughts");
export const preloadExcerptsPage = () => import("@/pages/Excerpts");
export const preloadFriendsPage = () => import("@/pages/Friends");
export const preloadGuestbookPage = () => import("@/pages/Guestbook");
export const preloadCalendarPage = () => import("@/pages/CalendarPage");
export const preloadResumePage = () => import("@/pages/Resume");

export const prefetchPostsData = (queryClient: QueryClient, pages?: RuntimePages) => {
  const pageSize = readPageSize(pages, "posts", 15);

  return prefetchInfiniteSiteList(
    queryClient,
    ["site", "posts", pageSize],
    pageSize,
    async (params) => (await readPostsApiV1SitePostsGet(params)).data,
  );
};

export const prefetchDiaryData = (queryClient: QueryClient, pages?: RuntimePages) => {
  const pageSize = readPageSize(pages, "diary", 15);

  return prefetchInfiniteSiteList(
    queryClient,
    ["site", "diary", pageSize],
    pageSize,
    async (params) => (await readDiaryApiV1SiteDiaryGet(params)).data,
  );
};

export const prefetchThoughtsData = (queryClient: QueryClient, pages?: RuntimePages) => {
  const pageSize = readPageSize(pages, "thoughts", 15);

  return prefetchInfiniteSiteList(
    queryClient,
    ["site", "thoughts", pageSize],
    pageSize,
    async (params) => (await readThoughtsApiV1SiteThoughtsGet(params)).data,
  );
};

export const prefetchExcerptsData = (queryClient: QueryClient, pages?: RuntimePages) => {
  const pageSize = readPageSize(pages, "excerpts", 15);

  return prefetchInfiniteSiteList(
    queryClient,
    ["site", "excerpts", pageSize],
    pageSize,
    async (params) => (await readExcerptsApiV1SiteExcerptsGet(params)).data,
  );
};

export const prefetchPostDetailData = (queryClient: QueryClient, slug: string) =>
  prefetchSiteQuery(
    queryClient,
    getReadPostApiV1SitePostsSlugGetQueryOptions(slug, {
      query: {
        staleTime: PREFETCH_STALE_TIME_MS,
        gcTime: PREFETCH_GC_TIME_MS,
      },
    }),
  );

export const prefetchDiaryDetailData = (queryClient: QueryClient, slug: string) =>
  prefetchSiteQuery(
    queryClient,
    getReadDiaryEntryApiV1SiteDiarySlugGetQueryOptions(slug, {
      query: {
        staleTime: PREFETCH_STALE_TIME_MS,
        gcTime: PREFETCH_GC_TIME_MS,
      },
    }),
  );

export const prefetchFriendsData = (queryClient: QueryClient) =>
  Promise.allSettled([
    prefetchSiteQuery(
      queryClient,
      getReadFriendsApiV1SiteFriendsGetQueryOptions(undefined, {
        query: {
          staleTime: PREFETCH_STALE_TIME_MS,
          gcTime: PREFETCH_GC_TIME_MS,
        },
      }),
    ),
    prefetchSiteQuery(
      queryClient,
      getReadFriendFeedApiV1SiteFriendFeedGetQueryOptions(
        { limit: FRIEND_FEED_PAGE_LIMIT },
        {
          query: {
            staleTime: PREFETCH_STALE_TIME_MS,
            gcTime: PREFETCH_GC_TIME_MS,
          },
        },
      ),
    ),
  ]);

export const prefetchHomeActivityData = (queryClient: QueryClient) =>
  Promise.allSettled([
    prefetchSiteQuery(
      queryClient,
      getReadFriendFeedApiV1SiteFriendFeedGetQueryOptions(
        { limit: FRIEND_FEED_HOME_LIMIT },
        {
          query: {
            staleTime: PREFETCH_STALE_TIME_MS,
            gcTime: PREFETCH_GC_TIME_MS,
          },
        },
      ),
    ),
    prefetchSiteQuery(
      queryClient,
      getReadRecentActivityApiV1SiteRecentActivityGetQueryOptions(
        { limit: RECENT_ACTIVITY_LIMIT },
        {
          query: {
            staleTime: 60_000,
            gcTime: 10 * 60_000,
          },
        },
      ),
    ),
    prefetchSiteQuery(
      queryClient,
      getReadActivityHeatmapApiV1SiteActivityHeatmapGetQueryOptions(
        ACTIVITY_HEATMAP_PARAMS,
        {
          query: {
            staleTime: PREFETCH_STALE_TIME_MS,
            gcTime: PREFETCH_GC_TIME_MS,
          },
        },
      ),
    ),
  ]);

export const prefetchCalendarMonthData = (
  queryClient: QueryClient,
  year: number,
  monthIndex: number,
) =>
  prefetchSiteQuery(
    queryClient,
    getReadCalendarApiV1SiteCalendarGetQueryOptions(
      buildMonthRange(year, monthIndex),
      {
        query: {
          staleTime: PREFETCH_STALE_TIME_MS,
          gcTime: PREFETCH_GC_TIME_MS,
        },
      },
    ),
  );

export const warmGuestbookPage = async () => {
  await preloadGuestbookPage();
  const config = await loadCommunityConfig();
  await primeGuestbookPage({
    page: 1,
    pageSize: Math.max(
      1,
      config.page_size ?? DEFAULT_COMMUNITY_CONFIG.page_size,
    ),
  });
};

export const warmCalendarPage = async (
  queryClient: QueryClient,
  options?: {
    year?: number;
    monthIndex?: number;
    includeNeighbors?: boolean;
  },
) => {
  await preloadCalendarPage();

  const now = getBeijingNowParts();
  const year = options?.year ?? now.year;
  const monthIndex = options?.monthIndex ?? Math.max(now.month - 1, 0);
  const minMonthValue = 2024 * 12;
  const maxMonthValue = now.year * 12 + Math.max(now.month - 1, 0);
  const targets = [{ year, monthIndex }];

  if (options?.includeNeighbors) {
    targets.push({ year, monthIndex: monthIndex - 1 });
    targets.push({ year, monthIndex: monthIndex + 1 });
  }

  await Promise.allSettled(
    targets
      .filter((target) => {
        const normalizedDate = new Date(target.year, target.monthIndex, 1);
        const value = normalizedDate.getFullYear() * 12 + normalizedDate.getMonth();
        return value >= minMonthValue && value <= maxMonthValue;
      })
      .map((target) => {
        const normalizedDate = new Date(target.year, target.monthIndex, 1);
        return prefetchCalendarMonthData(
          queryClient,
          normalizedDate.getFullYear(),
          normalizedDate.getMonth(),
        );
      }),
  );
};

export const warmInternalHref = async ({
  href,
  queryClient,
  pages,
}: {
  href: string | null | undefined;
  queryClient: QueryClient;
  pages?: RuntimePages;
}) => {
  const internalPath = normalizeInternalPath(href);
  if (!internalPath) {
    return;
  }

  const [pathname] = internalPath.split(/[?#]/, 1);

  if (pathname === "/posts") {
    await Promise.allSettled([preloadPostsPage(), prefetchPostsData(queryClient, pages)]);
    return;
  }

  if (pathname.startsWith("/posts/")) {
    const slug = decodeURIComponent(pathname.slice("/posts/".length));
    if (!slug) {
      return;
    }
    await Promise.allSettled([preloadPostDetailPage(), prefetchPostDetailData(queryClient, slug)]);
    return;
  }

  if (pathname === "/diary") {
    await Promise.allSettled([preloadDiaryPage(), prefetchDiaryData(queryClient, pages)]);
    return;
  }

  if (pathname.startsWith("/diary/")) {
    const slug = decodeURIComponent(pathname.slice("/diary/".length));
    if (!slug) {
      return;
    }
    await Promise.allSettled([preloadDiaryDetailPage(), prefetchDiaryDetailData(queryClient, slug)]);
    return;
  }

  if (pathname === "/thoughts") {
    await Promise.allSettled([preloadThoughtsPage(), prefetchThoughtsData(queryClient, pages)]);
    return;
  }

  if (pathname === "/excerpts") {
    await Promise.allSettled([preloadExcerptsPage(), prefetchExcerptsData(queryClient, pages)]);
    return;
  }

  if (pathname === "/friends") {
    await Promise.allSettled([preloadFriendsPage(), prefetchFriendsData(queryClient)]);
    return;
  }

  if (pathname === "/guestbook") {
    await warmGuestbookPage();
    return;
  }

  if (pathname === "/calendar") {
    await warmCalendarPage(queryClient, { includeNeighbors: true });
    return;
  }

  if (pathname === "/resume") {
    await preloadResumePage();
  }
};
