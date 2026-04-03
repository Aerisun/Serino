import { lazy, Suspense, useState, useEffect, useCallback } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@serino/theme";
import { RuntimeConfigProvider } from "@/contexts/RuntimeConfigContext";
import { SiteAuthProvider } from "@/contexts/site-auth";
import { FrontendLanguageProvider } from "@/i18n";
import ErrorBoundary from "@/components/ErrorBoundary";
import ShiroAccentController from "@/components/ShiroAccentController";
import ReadingProgress from "@/components/ReadingProgress";
import { useFeatureFlags } from "@/contexts/runtime-config";
import { lazyWithPreload } from "@/lib/lazy";

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

function AppContent() {
  const featureFlags = useFeatureFlags();
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

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <SiteAuthProvider>
        <ShiroAccentController />
        {featureFlags.reading_progress && <ReadingProgress />}
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

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
});

const App = () => (
  <QueryClientProvider client={queryClient}>
    <ThemeProvider>
      <FrontendLanguageProvider>
        <RuntimeConfigProvider>
          <AppContent />
        </RuntimeConfigProvider>
      </FrontendLanguageProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
