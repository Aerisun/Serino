import { lazy, Suspense, useState, useEffect, useCallback } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ThemeProvider } from "@serino/theme";
import { RuntimeConfigProvider } from "@/contexts/RuntimeConfigContext";
import ErrorBoundary from "@/components/ErrorBoundary";
import ShiroAccentController from "@/components/ShiroAccentController";
import ReadingProgress from "@/components/ReadingProgress";
import SearchModal from "@/components/SearchModal";
import { useFeatureFlags } from "@/contexts/runtime-config";

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

function AppContent() {
  const featureFlags = useFeatureFlags();
  const [searchOpen, setSearchOpen] = useState(false);

  const closeSearch = useCallback(() => setSearchOpen(false), []);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen((v) => !v);
      }
    };
    const onOpenSearch = () => setSearchOpen(true);
    document.addEventListener("keydown", onKey);
    window.addEventListener("aerisun:open-search", onOpenSearch);
    return () => {
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("aerisun:open-search", onOpenSearch);
    };
  }, []);

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
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
      <SearchModal open={searchOpen} onClose={closeSearch} />
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
      <RuntimeConfigProvider>
        <AppContent />
      </RuntimeConfigProvider>
    </ThemeProvider>
  </QueryClientProvider>
);

export default App;
