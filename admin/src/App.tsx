import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { AuthProvider } from "@/auth/AuthProvider";
import { LanguageProvider } from "@/i18n";
import { useAuth } from "@/auth/useAuth";
import AdminLayout from "@/layouts/AdminLayout";
import LoginPage from "@/auth/LoginPage";
import DashboardPage from "@/pages/DashboardPage";
import PostListPage from "@/pages/posts/PostListPage";
import PostEditPage from "@/pages/posts/PostEditPage";
import DiaryListPage from "@/pages/diary/DiaryListPage";
import DiaryEditPage from "@/pages/diary/DiaryEditPage";
import ThoughtListPage from "@/pages/thoughts/ThoughtListPage";
import ThoughtEditPage from "@/pages/thoughts/ThoughtEditPage";
import ExcerptListPage from "@/pages/excerpts/ExcerptListPage";
import ExcerptEditPage from "@/pages/excerpts/ExcerptEditPage";
import SiteConfigPage from "@/pages/site-config/SiteConfigPage";
import ResumePage from "@/pages/resume/ResumePage";
import FriendsPage from "@/pages/friends/FriendsPage";
import ModerationPage from "@/pages/moderation/ModerationPage";
import AssetsPage from "@/pages/assets/AssetsPage";
import ApiKeysPage from "@/pages/system/ApiKeysPage";
import AuditLogPage from "@/pages/system/AuditLogPage";
import BackupsPage from "@/pages/system/BackupsPage";

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
      </Route>
    </Routes>
  );
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <LanguageProvider>
        <AuthProvider>
          <BrowserRouter>
            <Routes>
              <Route path="/login" element={<LoginRoute />} />
              <Route path="/*" element={<ProtectedRoutes />} />
            </Routes>
          </BrowserRouter>
        </AuthProvider>
      </LanguageProvider>
    </QueryClientProvider>
  );
}

function LoginRoute() {
  const { isAuthenticated, isLoading } = useAuth();
  if (isLoading) return null;
  if (isAuthenticated) return <Navigate to="/" replace />;
  return <LoginPage />;
}
