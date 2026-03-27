import { lazy, Suspense } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Toaster } from "@/components/ui/Toaster";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/auth/AuthProvider";
import { ThemeProvider } from "@serino/theme";
import { LanguageProvider } from "@/i18n";
import { useAuth } from "@/auth/useAuth";
import AdminLayout from "@/layouts/AdminLayout";
import { ADMIN_THEME_STORAGE_KEY } from "@/lib/storage";
import LoginPage from "@/auth/LoginPage";

const adminBasePath =
  typeof __AERISUN_ADMIN_BASE_PATH__ === "string"
    ? __AERISUN_ADMIN_BASE_PATH__
    : "/admin/";
const routerBasename = adminBasePath === "/" ? undefined : adminBasePath.replace(/\/$/, "");

const DashboardPage = lazy(() => import("@/pages/DashboardPage"));
const PostListPage = lazy(() => import("@/pages/posts/PostListPage"));
const PostEditPage = lazy(() => import("@/pages/posts/PostEditPage"));
const DiaryListPage = lazy(() => import("@/pages/diary/DiaryListPage"));
const DiaryEditPage = lazy(() => import("@/pages/diary/DiaryEditPage"));
const ThoughtListPage = lazy(() => import("@/pages/thoughts/ThoughtListPage"));
const ThoughtEditPage = lazy(() => import("@/pages/thoughts/ThoughtEditPage"));
const ExcerptListPage = lazy(() => import("@/pages/excerpts/ExcerptListPage"));
const ExcerptEditPage = lazy(() => import("@/pages/excerpts/ExcerptEditPage"));
const ContentCategoriesPage = lazy(() => import("@/pages/content/ContentCategoriesPage"));
const SiteConfigPage = lazy(() => import("@/pages/site-config/SiteConfigPage"));
const MorePage = lazy(() => import("@/pages/more/MorePage"));
const ResumePage = lazy(() => import("@/pages/resume/ResumePage"));
const FriendsPage = lazy(() => import("@/pages/friends/FriendsPage"));
const ModerationPage = lazy(() => import("@/pages/moderation/ModerationPage"));
const VisitorsPage = lazy(() => import("@/pages/visitors/VisitorsPage"));
const VisitorsUsersPage = lazy(() => import("@/pages/visitors/VisitorsUsersPage"));
const AssetsPage = lazy(() => import("@/pages/assets/AssetsPage"));
const ApiKeysPage = lazy(() => import("@/pages/system/ApiKeysPage"));
const McpPage = lazy(() => import("@/pages/integrations/McpPage"));
const FeedsPage = lazy(() => import("@/pages/integrations/FeedsPage"));
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
          <Route path="content/categories" element={<ContentCategoriesPage />} />
          <Route path="site-config/:section?" element={<SiteConfigPage />} />
          <Route path="site-config/more" element={<Navigate to="/more" replace />} />
          <Route path="more" element={<MorePage />} />
          <Route path="resume" element={<ResumePage />} />
          <Route path="friends" element={<FriendsPage />} />
          <Route path="moderation" element={<ModerationPage />} />
          <Route path="visitors" element={<VisitorsPage />} />
          <Route path="visitors/users" element={<VisitorsUsersPage />} />
          <Route path="assets" element={<AssetsPage />} />
          <Route path="integrations/api-keys" element={<ApiKeysPage />} />
          <Route path="integrations/feeds" element={<FeedsPage />} />
          <Route path="integrations/mcp" element={<McpPage />} />
          <Route path="system/api-keys" element={<Navigate to="/integrations/api-keys" replace />} />
          <Route path="system/feeds" element={<Navigate to="/integrations/feeds" replace />} />
          <Route path="system/mcp" element={<Navigate to="/integrations/mcp" replace />} />
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
      <ThemeProvider storageKey={ADMIN_THEME_STORAGE_KEY}>
        <LanguageProvider>
          <AuthProvider>
            <BrowserRouter basename={routerBasename}>
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
