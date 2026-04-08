import { lazy, Suspense, useState, useEffect, useCallback, useRef } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  dehydrate,
  hydrate,
  useQueryClient,
} from "@tanstack/react-query";
import { ThemeProvider } from "@serino/theme";
import "./index.css";
import { RuntimeConfigProvider } from "@/contexts/RuntimeConfigContext";
import { SiteAuthProvider } from "@/contexts/site-auth";
import { FrontendLanguageProvider } from "@/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";
import ShiroAccentController from "@/components/ShiroAccentController";
import ReadingProgress from "@/components/ReadingProgress";
import { useFeatureFlags, usePageConfig, useSiteConfig } from "@/contexts/runtime-config";
import { lazyWithPreload } from "@/lib/lazy";
import type { RuntimeConfigSnapshot } from "@/lib/runtime-config";
import { useDeferredActivation } from "@/hooks/useDeferredActivation";
import { scheduleIdleTask, shouldBackgroundPrefetch } from "@/lib/idle";
import {
  prefetchHomeActivityData,
  warmInternalHref,
} from "@/lib/route-preload";

const Index = lazy(() => import("./pages/Index"));
const Posts = lazy(() => import("./pages/Posts"));
const PostDetail = lazy(() => import("./pages/PostDetail"));
const Friends = lazy(() => import("./pages/Friends"));
const Thoughts = lazy(() => import("./pages/Thoughts"));
const Diary = lazy(() => import("./pages/Diary"));
const DiaryDetail = lazy(() => import("./pages/DiaryDetail"));
const Excerpts = lazy(() => import("./pages/Excerpts"));
const Resume = lazy(() => import("./pages/Resume"));
const Guestbook = lazy(() => import("./pages/Guestbook"));
const CalendarPage = lazy(() => import("./pages/CalendarPage"));
const Preview = lazy(() => import("./pages/Preview"));
const NotFound = lazy(() => import("./pages/NotFound"));
const SearchModal = lazyWithPreload(() => import("@/components/SearchModal"));
const SubscribeModal = lazyWithPreload(() => import("@/components/SubscribeModal"));
const QUERY_CACHE_STORAGE_KEY = "aerisun:query-cache:v2";
const QUERY_CACHE_TTL_MS = 10 * 60_000;
const CONTENT_FRESHNESS_STORAGE_KEY = "aerisun:content-updated:v1";
const CONTENT_REFRESH_INTERVAL_MS = 60_000;
const CONTENT_REFRESH_COOLDOWN_MS = 15_000;

const shouldPersistQueryKey = (queryKey: readonly unknown[]) => {
  const [first] = queryKey;
  return typeof first === "string" && first.startsWith("/api/v1/site-interactions/");
};

const isFreshnessSensitiveQueryKey = (queryKey: readonly unknown[]) => {
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

const clearPersistedQueryState = () => {
  if (typeof sessionStorage === "undefined") {
    return;
  }

  try {
    sessionStorage.removeItem(QUERY_CACHE_STORAGE_KEY);
  } catch {
    // Ignore storage failures.
  }
};

const readPersistedQueryState = () => {
  if (typeof sessionStorage === "undefined") {
    return null;
  }

  try {
    const raw = sessionStorage.getItem(QUERY_CACHE_STORAGE_KEY);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as { persistedAt?: number; state?: Parameters<typeof hydrate>[1] };
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

const createQueryClient = () => {
  const client = new QueryClient({
    defaultOptions: {
      queries: {
        retry: 1,
        refetchOnWindowFocus: false,
        staleTime: 30_000,
        gcTime: 15 * 60_000,
      },
    },
  });

  const persistedState = readPersistedQueryState();
  if (persistedState) {
    hydrate(client, persistedState);
  }

  return client;
};

function QueryCachePersistence() {
  const queryClient = useQueryClient();

  useEffect(() => {
    if (typeof sessionStorage === "undefined") {
      return;
    }

    let persistTimer: ReturnType<typeof setTimeout> | null = null;

    const persist = (immediate = false) => {
      const write = () => {
        try {
          sessionStorage.setItem(
            QUERY_CACHE_STORAGE_KEY,
            JSON.stringify({
              persistedAt: Date.now(),
              state: dehydrate(queryClient, {
                shouldDehydrateQuery: (query) =>
                  query.state.status === "success" && shouldPersistQueryKey(query.queryKey),
              }),
            }),
          );
        } catch {
          // Ignore storage failures.
        }
      };

      if (immediate) {
        if (persistTimer) {
          clearTimeout(persistTimer);
          persistTimer = null;
        }
        write();
        return;
      }

      if (persistTimer) {
        clearTimeout(persistTimer);
      }

      persistTimer = setTimeout(write, 300);
    };

    const unsubscribe = queryClient.getQueryCache().subscribe(() => persist());
    const handlePageHide = () => persist(true);
    window.addEventListener("pagehide", handlePageHide);

    return () => {
      if (persistTimer) {
        clearTimeout(persistTimer);
      }
      unsubscribe();
      window.removeEventListener("pagehide", handlePageHide);
    };
  }, [queryClient]);

  return null;
}

function ContentFreshnessManager() {
  const queryClient = useQueryClient();
  const lastRefreshAtRef = useRef(0);

  const refreshContent = useCallback((force = false) => {
    if (typeof document !== "undefined" && document.visibilityState === "hidden" && !force) {
      return;
    }

    const now = Date.now();
    if (!force && now - lastRefreshAtRef.current < CONTENT_REFRESH_COOLDOWN_MS) {
      return;
    }

    lastRefreshAtRef.current = now;
    clearPersistedQueryState();
    void queryClient.invalidateQueries({
      predicate: (query) => isFreshnessSensitiveQueryKey(query.queryKey),
      refetchType: "active",
    });
  }, [queryClient]);

  useEffect(() => {
    const handleFocus = () => refreshContent();
    const handleVisibilityChange = () => {
      if (document.visibilityState === "visible") {
        refreshContent();
      }
    };
    const handleStorage = (event: StorageEvent) => {
      if (event.key === CONTENT_FRESHNESS_STORAGE_KEY && event.newValue) {
        refreshContent(true);
      }
    };
    const handleContentUpdated = () => refreshContent(true);
    const intervalId = window.setInterval(() => {
      if (typeof navigator !== "undefined" && navigator.onLine === false) {
        return;
      }
      refreshContent();
    }, CONTENT_REFRESH_INTERVAL_MS);

    window.addEventListener("focus", handleFocus);
    document.addEventListener("visibilitychange", handleVisibilityChange);
    window.addEventListener("storage", handleStorage);
    window.addEventListener("aerisun:content-updated", handleContentUpdated);

    return () => {
      window.clearInterval(intervalId);
      window.removeEventListener("focus", handleFocus);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
      window.removeEventListener("storage", handleStorage);
      window.removeEventListener("aerisun:content-updated", handleContentUpdated);
    };
  }, [refreshContent]);

  return null;
}

function AppContent() {
  const featureFlags = useFeatureFlags();
  const site = useSiteConfig();
  const pages = usePageConfig();
  const queryClient = useQueryClient();
  const readingProgressActive = useDeferredActivation(featureFlags.reading_progress, [
    featureFlags.reading_progress,
  ]);
  const [searchOpen, setSearchOpen] = useState(false);
  const [subscribeOpen, setSubscribeOpen] = useState(false);

  const openSearch = useCallback(() => {
    void SearchModal.preload();
    setSearchOpen(true);
  }, []);
  const openSubscribe = useCallback(() => {
    void SubscribeModal.preload();
    setSubscribeOpen(true);
  }, []);
  const closeSearch = useCallback(() => setSearchOpen(false), []);
  const closeSubscribe = useCallback(() => setSubscribeOpen(false), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        void SearchModal.preload();
        setSearchOpen((v) => !v);
      }
    };
    const onOpenSearch = () => openSearch();
    const onOpenSubscribe = () => openSubscribe();
    document.addEventListener("keydown", onKey);
    window.addEventListener("aerisun:open-search", onOpenSearch);
    window.addEventListener("aerisun:open-subscribe", onOpenSubscribe);
    return () => {
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("aerisun:open-search", onOpenSearch);
      window.removeEventListener("aerisun:open-subscribe", onOpenSubscribe);
    };
  }, [openSearch, openSubscribe]);

  useEffect(() => {
    if (!shouldBackgroundPrefetch()) {
      return;
    }

    const targets = Array.from(
      new Set(
        [
          ...site.navigation.flatMap((item) => [
            item.href,
            ...(item.children?.map((child) => child.href) ?? []),
          ]),
          ...site.heroActions.map((action) => action.href),
        ].filter((href): href is string => Boolean(href)),
      ),
    );

    return scheduleIdleTask(() => {
      void Promise.allSettled([
        ...targets.map((href) => warmInternalHref({ href, queryClient, pages })),
        prefetchHomeActivityData(queryClient),
      ]);
    }, 1_800);
  }, [pages, queryClient, site.heroActions, site.navigation]);

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <SiteAuthProvider>
        <ShiroAccentController />
        <QueryCachePersistence />
        <ContentFreshnessManager />
        {readingProgressActive ? <ReadingProgress /> : null}
        <ErrorBoundary>
          <Suspense
            fallback={
              <div className="flex h-screen items-center justify-center">
                <div className="h-8 w-8 animate-spin rounded-full border-4 border-current border-t-transparent opacity-60" />
              </div>
            }
          >
            <Routes>
              <Route path="/" element={<Index />} />
              <Route path="/posts" element={<Posts />} />
              <Route path="/posts/:id" element={<PostDetail />} />
              <Route path="/friends" element={<Friends />} />
              <Route path="/thoughts" element={<Thoughts />} />
              <Route path="/diary" element={<Diary />} />
              <Route path="/diary/:id" element={<DiaryDetail />} />
              <Route path="/excerpts" element={<Excerpts />} />
              <Route path="/resume" element={<Resume />} />
              <Route path="/guestbook" element={<Guestbook />} />
              <Route path="/calendar" element={<CalendarPage />} />
              <Route path="/preview" element={<Preview />} />
              <Route path="*" element={<NotFound />} />
            </Routes>
          </Suspense>
        </ErrorBoundary>
        <Suspense fallback={null}>
          {searchOpen ? <SearchModal open={searchOpen} onClose={closeSearch} /> : null}
          {subscribeOpen ? (
            <SubscribeModal
              open={subscribeOpen}
              onClose={closeSubscribe}
              enabled={featureFlags.content_subscription}
            />
          ) : null}
        </Suspense>
      </SiteAuthProvider>
    </BrowserRouter>
  );
}

const queryClient = createQueryClient();

const AppRuntime = ({
  initialRuntimeConfig = null,
}: {
  initialRuntimeConfig?: RuntimeConfigSnapshot | null;
}) => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <FrontendLanguageProvider>
        <RuntimeConfigProvider initialConfig={initialRuntimeConfig}>
          <AppContent />
        </RuntimeConfigProvider>
      </FrontendLanguageProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default AppRuntime;
