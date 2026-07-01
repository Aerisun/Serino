import { lazy, Suspense, useState, useEffect, useCallback, useRef } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import {
  QueryClient,
  QueryClientProvider,
  dehydrate,
  useQueryClient,
  hydrate,
} from "@tanstack/react-query";
import { ThemeProvider } from "@serino/theme";
import "./index.css";
import { RuntimeConfigProvider } from "@/contexts/RuntimeConfigContext";
import { SiteAuthProvider } from "@/contexts/site-auth";
import { FrontendLanguageProvider } from "@/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";
import ShiroAccentController from "@/components/ShiroAccentController";
import ReadingProgress from "@/components/ReadingProgress";
import PageViewTracker from "@/components/PageViewTracker";
import { useFeatureFlags, useSiteConfig } from "@/contexts/runtime-config";
import { lazyWithPreload } from "@/lib/lazy";
import type { RuntimeConfigSnapshot } from "@/lib/runtime-config";
import { useDeferredActivation } from "@/hooks/useDeferredActivation";
import { scheduleIdleTask, shouldBackgroundPrefetch } from "@/lib/idle";
import {
  preloadInternalHref,
  prefetchHomeActivityData,
} from "@/lib/route-preload";
import {
  clearPersistedQueryState,
  isFreshnessSensitiveQueryKey,
  readPersistedQueryState,
  shouldPersistQueryKey,
} from "@/lib/query-cache";

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
const CONTENT_FRESHNESS_STORAGE_KEY = "aerisun:content-updated:v1";
const CONTENT_REFRESH_INTERVAL_MS = 60_000;
const CONTENT_REFRESH_COOLDOWN_MS = 15_000;
const BACKGROUND_ROUTE_PRELOAD_DELAY_MS = 3_200;
const BACKGROUND_ROUTE_PRELOAD_GAP_MS = 320;

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
    if (
      !shouldBackgroundPrefetch() ||
      typeof window === "undefined" ||
      window.location.pathname !== "/"
    ) {
      return;
    }

    let cancelled = false;
    const gapTimers = new Set<number>();
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

    const isStillHome = () => !cancelled && window.location.pathname === "/";
    const waitForGap = () =>
      new Promise<void>((resolve) => {
        const timer = window.setTimeout(() => {
          gapTimers.delete(timer);
          resolve();
        }, BACKGROUND_ROUTE_PRELOAD_GAP_MS);
        gapTimers.add(timer);
      });

    const preloadRoutes = async () => {
      for (const href of targets) {
        if (!isStillHome()) {
          return;
        }

        await preloadInternalHref({ href });
        await waitForGap();
      }

      if (isStillHome()) {
        await prefetchHomeActivityData(queryClient);
      }
    };

    const cancelIdleTask = scheduleIdleTask(() => {
      void preloadRoutes();
    }, BACKGROUND_ROUTE_PRELOAD_DELAY_MS);

    return () => {
      cancelled = true;
      cancelIdleTask();
      gapTimers.forEach((timer) => window.clearTimeout(timer));
      gapTimers.clear();
    };
  }, [queryClient, site.heroActions, site.navigation]);

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <SiteAuthProvider>
        <ShiroAccentController />
        <QueryCachePersistence />
        <ContentFreshnessManager />
        <PageViewTracker />
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
