import { lazy, Suspense, type ComponentType, type LazyExoticComponent } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/auth/AuthProvider";
import { ThemeProvider } from "@serino/theme";
import { LanguageProvider } from "@/i18n";
import { useAuth } from "@/auth/useAuth";
import { ensureAdminClientInitialized } from "@/lib/adminClient";
import { ADMIN_THEME_STORAGE_KEY } from "@/lib/storage";

const adminBasePath =
  typeof __AERISUN_ADMIN_BASE_PATH__ === "string"
    ? __AERISUN_ADMIN_BASE_PATH__
    : "/admin/";
const routerBasename = adminBasePath === "/" ? undefined : adminBasePath.replace(/\/$/, "");
const ADMIN_QUERY_STALE_TIME = 30_000;

function lazyPage<T extends ComponentType>(loader: () => Promise<{ default: T }>) {
  return lazy(loader);
}

function lazyAdminPage<T extends ComponentType>(loader: () => Promise<{ default: T }>) {
  return lazy(async () => {
    await ensureAdminClientInitialized();
    return loader();
  });
}

const Toaster = lazyPage(() =>
  import("@/components/ui/Toaster").then((module) => ({ default: module.Toaster })),
);
const AdminLayout = lazyPage(() => import("@/layouts/AdminLayout"));
const LoginPage = lazyPage(() => import("@/auth/LoginPage"));
const DashboardPage = lazyPage(() => import("@/pages/DashboardPage"));
const PostListPage = lazyAdminPage(() => import("@/pages/posts/PostListPage"));
const PostEditPage = lazyAdminPage(() => import("@/pages/posts/PostEditPage"));
const DiaryListPage = lazyAdminPage(() => import("@/pages/diary/DiaryListPage"));
const DiaryEditPage = lazyAdminPage(() => import("@/pages/diary/DiaryEditPage"));
const ThoughtListPage = lazyAdminPage(() => import("@/pages/thoughts/ThoughtListPage"));
const ThoughtEditPage = lazyAdminPage(() => import("@/pages/thoughts/ThoughtEditPage"));
const ExcerptListPage = lazyAdminPage(() => import("@/pages/excerpts/ExcerptListPage"));
const ExcerptEditPage = lazyAdminPage(() => import("@/pages/excerpts/ExcerptEditPage"));
const ContentCategoriesPage = lazyAdminPage(() => import("@/pages/content/ContentCategoriesPage"));
const SiteConfigPage = lazyAdminPage(() => import("@/pages/site-config/SiteConfigPage"));
const MorePage = lazyAdminPage(() => import("@/pages/more/MorePage"));
const ResumePage = lazyAdminPage(() => import("@/pages/resume/ResumePage"));
const FriendsPage = lazyAdminPage(() => import("@/pages/friends/FriendsPage"));
const ModerationPage = lazyAdminPage(() => import("@/pages/moderation/ModerationPage"));
const VisitorsPage = lazyAdminPage(() => import("@/pages/visitors/VisitorsPage"));
const VisitorsUsersPage = lazyAdminPage(() => import("@/pages/visitors/VisitorsUsersPage"));
const VisitorsSubscribersPage = lazyAdminPage(() => import("@/pages/visitors/VisitorsSubscribersPage"));
const AssetsPage = lazyAdminPage(() => import("@/pages/assets/AssetsPage"));
const McpPage = lazyAdminPage(() => import("@/pages/integrations/McpPage"));
const AgentPage = lazyAdminPage(() => import("@/pages/automation/AgentPage"));
const AgentRunDetailPage = lazyAdminPage(() => import("@/pages/automation/AgentRunDetailPage"));
const AdminNotFoundPage = lazyPage(() => import("@/pages/AdminNotFoundPage"));
const AuditLogPage = lazyAdminPage(() => import("@/pages/system/AuditLogPage"));
const BackupsPage = lazyAdminPage(() => import("@/pages/system/BackupsPage"));
const SystemInfoPage = lazyAdminPage(() => import("@/pages/system/SystemInfoPage"));

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: ADMIN_QUERY_STALE_TIME,
      refetchOnWindowFocus: false,
    },
  },
});

function RouteSpinner() {
  return (
    <div className="flex h-dvh min-h-screen items-center justify-center text-muted-foreground">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
    </div>
  );
}

function PageSpinner() {
  return (
    <div className="flex min-h-[50vh] items-center justify-center text-muted-foreground">
      <div className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
    </div>
  );
}

function ProtectedLayoutRoute() {
  return (
    <Suspense fallback={<RouteSpinner />}>
      <AdminLayout />
    </Suspense>
  );
}

function RoutePage({
  page: Page,
}: {
  page: LazyExoticComponent<ComponentType>;
}) {
  return (
    <Suspense fallback={<PageSpinner />}>
      <Page />
    </Suspense>
  );
}

function ProtectedRoutes() {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <RouteSpinner />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return (
    <Routes>
      <Route element={<ProtectedLayoutRoute />}>
        <Route index element={<RoutePage page={DashboardPage} />} />
        <Route path="posts" element={<RoutePage page={PostListPage} />} />
        <Route path="posts/:id" element={<RoutePage page={PostEditPage} />} />
        <Route path="diary" element={<RoutePage page={DiaryListPage} />} />
        <Route path="diary/:id" element={<RoutePage page={DiaryEditPage} />} />
        <Route path="thoughts" element={<RoutePage page={ThoughtListPage} />} />
        <Route path="thoughts/:id" element={<RoutePage page={ThoughtEditPage} />} />
        <Route path="excerpts" element={<RoutePage page={ExcerptListPage} />} />
        <Route path="excerpts/:id" element={<RoutePage page={ExcerptEditPage} />} />
        <Route path="content/categories" element={<RoutePage page={ContentCategoriesPage} />} />
        <Route path="site-config/:section?" element={<RoutePage page={SiteConfigPage} />} />
        <Route path="more/:section?" element={<RoutePage page={MorePage} />} />
        <Route path="resume" element={<RoutePage page={ResumePage} />} />
        <Route path="friends" element={<RoutePage page={FriendsPage} />} />
        <Route path="moderation" element={<RoutePage page={ModerationPage} />} />
        <Route path="visitors" element={<RoutePage page={VisitorsPage} />} />
        <Route path="visitors/users" element={<RoutePage page={VisitorsUsersPage} />} />
        <Route
          path="visitors/subscribers"
          element={<RoutePage page={VisitorsSubscribersPage} />}
        />
        <Route path="assets" element={<RoutePage page={AssetsPage} />} />
        <Route path="integrations/mcp/:section?" element={<RoutePage page={McpPage} />} />
        <Route
          path="agent/activity/runs/:runId"
          element={<RoutePage page={AgentRunDetailPage} />}
        />
        <Route path="agent/:section?" element={<RoutePage page={AgentPage} />} />
        <Route path="system/audit-log" element={<RoutePage page={AuditLogPage} />} />
        <Route path="system/backups" element={<RoutePage page={BackupsPage} />} />
        <Route path="system/info" element={<RoutePage page={SystemInfoPage} />} />
        <Route path="settings" element={<Navigate to="/system/info" replace />} />
        <Route path="*" element={<RoutePage page={AdminNotFoundPage} />} />
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider storageKey={ADMIN_THEME_STORAGE_KEY}>
        <LanguageProvider>
          <AuthProvider>
            <BrowserRouter
              basename={routerBasename}
              future={{
                v7_startTransition: true,
                v7_relativeSplatPath: true,
              }}
            >
              <Suspense fallback={null}>
                <Toaster richColors position="top-right" />
              </Suspense>
              <Routes>
                <Route
                  path="/login"
                  element={
                    <Suspense fallback={<RouteSpinner />}>
                      <LoginRoute />
                    </Suspense>
                  }
                />
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
