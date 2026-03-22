import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/Toaster";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/auth/AuthProvider";
import { ThemeProvider } from "@/contexts/ThemeContext";
import { LanguageProvider } from "@/i18n";
import { useAuth } from "@/auth/useAuth";
import AdminLayout from "@/layouts/AdminLayout";
import LoginPage from "@/auth/LoginPage";

const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const PostListPage = lazy(() => import("@/pages/posts/PostListPage"));
const PostEditPage = lazy(() => import("@/pages/posts/PostEditPage"));
const DiaryListPage = lazy(() => import("@/pages/diary/DiaryListPage"));
const DiaryEditPage = lazy(() => import("@/pages/diary/DiaryEditPage"));
const ThoughtListPage = lazy(() => import("@/pages/thoughts/ThoughtListPage"));
const ThoughtEditPage = lazy(() => import("@/pages/thoughts/ThoughtEditPage"));
const ExcerptListPage = lazy(() => import("@/pages/excerpts/ExcerptListPage"));
const ExcerptEditPage = lazy(() => import("@/pages/excerpts/ExcerptEditPage"));
const SiteConfigPage = lazy(() => import("@/pages/site-config/SiteConfigPage"));
const ResumePage = lazy(() => import("@/pages/resume/ResumePage"));
const FriendsPage = lazy(() => import("@/pages/friends/FriendsPage"));
const ModerationPage = lazy(() => import("@/pages/moderation/ModerationPage"));
const AssetsPage = lazy(() => import("@/pages/assets/AssetsPage"));
const ApiKeysPage = lazy(() => import("@/pages/system/ApiKeysPage"));
const AuditLogPage = lazy(() => import("@/pages/system/AuditLogPage"));
const BackupsPage = lazy(() => import("@/pages/system/BackupsPage"));
const SystemInfoPage = lazy(() => import("@/pages/system/SystemInfoPage"));
const SettingsPage = lazy(() => import("@/pages/settings/SettingsPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { retry: 1, refetchOnWindowFocus: false },
  },
});

function ProtectedRoutes() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <div className="flex h-screen items-center justify-center text-muted-foreground">Loading...</div>;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <Suspense fallback={<div className="flex h-screen items-center justify-center text-muted-foreground"><div className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" /></div>}>
    <Routes>
      <Route element={<AdminLayout />}>
        <Route index element={<DashboardPage />} />
        <Route path="posts" element={<PostListPage />} />
        <Route path="posts/:id" element={<PostEditPage />} />
        <Route path="diary" element={<DiaryListPage />} />
        <Route path="diary/:id" element={<DiaryEditPage />} />
        <Route path="thoughts" element={<ThoughtListPage />} />
        <Route path="thoughts/:id" element={<ThoughtEditPage />} />
        <Route path="excerpts" element={<ExcerptListPage />} />
        <Route path="excerpts/:id" element={<ExcerptEditPage />} />
        <Route path="site-config" element={<SiteConfigPage />} />
        <Route path="resume" element={<ResumePage />} />
        <Route path="friends" element={<FriendsPage />} />
        <Route path="moderation" element={<ModerationPage />} />
        <Route path="assets" element={<AssetsPage />} />
        <Route path="system/api-keys" element={<ApiKeysPage />} />
        <Route path="system/audit-log" element={<AuditLogPage />} />
        <Route path="system/backups" element={<BackupsPage />} />
        <Route path="system/info" element={<SystemInfoPage />} />
        <Route path="settings" element={<SettingsPage />} />
      </Route>
    </Routes>
    </Suspense>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <LanguageProvider>
          <AuthProvider>
            <BrowserRouter>
              <Toaster richColors position="top-right" />
              <Routes>
                <Route path="/login" element={<LoginRoute />} />
                <Route path="/*" element={<ProtectedRoutes />} />
              </Routes>
            </BrowserRouter>
          </AuthProvider>
        </LanguageProvider>
      </ThemeProvider>
    </QueryClientProvider>
  );
}

function LoginRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return null;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <LoginPage />;
}
