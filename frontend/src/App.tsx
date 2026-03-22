import { lazy, Suspense } from "react";
import { BrowserRouter, Route, Routes } from "react-router-dom";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { RuntimeConfigProvider } from "@/contexts/RuntimeConfigContext";
import ErrorBoundary from "@/components/ErrorBoundary";
import ShiroAccentController from "@/components/ShiroAccentController";

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
const NotFound = lazy(() => import("./pages/NotFound"));

const App = () => (
  <ThemeProvider>
    <RuntimeConfigProvider>
      <BrowserRouter>
        <ShiroAccentController />
        <ErrorBoundary>
        <Suspense fallback={<div className="flex h-screen items-center justify-center"><div className="h-8 w-8 animate-spin rounded-full border-4 border-current border-t-transparent opacity-60" /></div>}>
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
          <Route path="*" element={<NotFound />} />
        </Routes>
        </Suspense>
        </ErrorBoundary>
      </BrowserRouter>
    </RuntimeConfigProvider>
  </ThemeProvider>
);

export default App;
