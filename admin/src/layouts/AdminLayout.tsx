import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/auth/useAuth";
import { useI18n } from "@/i18n";
import {
  listCommentsApiV1AdminModerationCommentsGet,
  listGuestbookApiV1AdminModerationGuestbookGet,
} from "@serino/api-client/admin";
import { Button } from "@/components/ui/Button";
import {
  LayoutDashboard,
  FileText,
  BookOpen,
  MessageSquare,
  Quote,
  FolderTree,
  Settings,
  Briefcase,
  Users,
  Shield,
  Image,
  ClipboardList,
  Bot,
  Database,
  LogOut,
  Menu,
  X,
  Globe,
  Moon,
  Sun,
  User,
  Info,
} from "lucide-react";
import { useTheme } from "@serino/theme";
import { cn } from "@/lib/utils";

const navGroups = [
  {
    labelKey: "nav.dashboard",
    items: [{ to: "/", icon: LayoutDashboard, labelKey: "nav.overview" }],
  },
  {
    labelKey: "nav.content",
    items: [
      { to: "/posts", icon: FileText, labelKey: "nav.posts" },
      { to: "/diary", icon: BookOpen, labelKey: "nav.diary" },
      { to: "/thoughts", icon: MessageSquare, labelKey: "nav.thoughts" },
      { to: "/excerpts", icon: Quote, labelKey: "nav.excerpts" },
      {
        to: "/content/categories",
        icon: FolderTree,
        labelKey: "nav.contentCategories",
      },
      { to: "/resume", icon: Briefcase, labelKey: "nav.resume" },
    ],
  },
  {
    labelKey: "nav.configuration",
    items: [
      { to: "/site-config", icon: Settings, labelKey: "nav.siteConfig" },
      { to: "/more", icon: Settings, labelKey: "nav.more" },
      { to: "/friends", icon: Users, labelKey: "nav.friends" },
    ],
  },
  {
    labelKey: "nav.management",
    items: [
      { to: "/moderation", icon: Shield, labelKey: "nav.moderation" },
      { to: "/visitors", icon: User, labelKey: "nav.visitors" },
      { to: "/assets", icon: Image, labelKey: "nav.assets" },
    ],
  },
  {
    labelKey: "nav.integrations",
    items: [
      { to: "/integrations/mcp", icon: Globe, labelKey: "nav.mcp" },
      { to: "/agent", icon: Bot, labelKey: "nav.agent" },
    ],
  },
  {
    labelKey: "nav.system",
    items: [
      {
        to: "/system/audit-log",
        icon: ClipboardList,
        labelKey: "nav.auditLog",
      },
      { to: "/system/backups", icon: Database, labelKey: "nav.backups" },
      { to: "/system/info", icon: Info, labelKey: "nav.systemInfo" },
    ],
  },
];

export default function AdminLayout() {
  const { user, logout, requiresPasswordChange } = useAuth();
  const { t, lang, setLang } = useI18n();
  const { theme, setTheme } = useTheme();
  const [collapsed, setCollapsed] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { data: pendingComments } = useQuery({
    queryKey: ["comments", "pending-count"],
    queryFn: () =>
      listCommentsApiV1AdminModerationCommentsGet({
        page: 1,
        page_size: 1,
        status: "pending",
      }),
    refetchInterval: 30000,
    enabled: !requiresPasswordChange,
  });
  const { data: pendingGuestbook } = useQuery({
    queryKey: ["guestbook", "pending-count"],
    queryFn: () =>
      listGuestbookApiV1AdminModerationGuestbookGet({
        page: 1,
        page_size: 1,
        status: "pending",
      }),
    refetchInterval: 30000,
    enabled: !requiresPasswordChange,
  });
  const pendingCount =
    (pendingComments?.total ?? 0) + (pendingGuestbook?.total ?? 0);
  const effectiveNavGroups = requiresPasswordChange
    ? [
        {
          labelKey: "nav.system",
          items: [{ to: "/system/info", icon: Info, labelKey: "nav.systemInfo" }],
        },
      ]
    : navGroups;

  const toggleLang = () => setLang(lang === "zh" ? "en" : "zh");

  const sidebarContent = (
    <>
      <nav className="flex-1 overflow-y-auto py-2">
        {effectiveNavGroups.map((group) => (
          <div key={group.labelKey} className="mb-2">
            {!collapsed && !group.hideLabel && (
              <div className="px-4 py-1 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                {t(group.labelKey)}
              </div>
            )}
            {group.items.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={() => setSidebarOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "admin-transition-fast flex items-center gap-3 px-4 py-2 text-sm transition-[background-color,color,box-shadow] hover:bg-[rgb(var(--admin-surface-1)/0.6)] dark:hover:bg-white/[0.05]",
                    isActive &&
                      "bg-[rgb(var(--admin-surface-1)/0.82)] dark:bg-white/[0.08] text-accent-foreground font-medium shadow-[0_12px_30px_-18px_rgb(var(--admin-accent-rgb)/0.46)]",
                    collapsed && "justify-center px-2",
                  )
                }
              >
                <item.icon className="h-4 w-4 shrink-0" />
                {!collapsed && (
                  <span className="flex items-center gap-2">
                    {t(item.labelKey)}
                    {item.to === "/moderation" && pendingCount > 0 && (
                      <span className="inline-flex items-center justify-center rounded-full bg-destructive text-destructive-foreground text-xs font-medium h-5 min-w-[20px] px-1">
                        {pendingCount}
                      </span>
                    )}
                  </span>
                )}
              </NavLink>
            ))}
          </div>
        ))}
      </nav>

      <div className="border-t border-white/10 dark:border-white/5 p-3">
        <div
          className={cn(
            "flex items-center gap-2",
            collapsed && "justify-center",
          )}
        >
          {!collapsed && (
            <span className="text-sm truncate flex-1">{user?.username}</span>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={logout}
            title={t("nav.logout")}
          >
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </>
  );

  return (
    <div className="admin-scrollbars flex h-dvh min-h-screen overflow-hidden bg-gradient-to-br from-background via-background/95 to-muted/35">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Mobile sidebar */}
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col admin-glass-sidebar transition-transform duration-200 md:hidden",
          sidebarOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        <div className="flex h-14 items-center justify-between border-b border-white/10 dark:border-white/5 px-4">
          <span className="font-semibold text-lg">{t("nav.admin")}</span>
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
        {sidebarContent}
      </aside>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden md:flex md:flex-col admin-glass-sidebar transition-all duration-200",
          collapsed ? "md:w-16" : "md:w-60",
        )}
      >
        <div className="flex h-14 items-center justify-between border-b border-white/10 dark:border-white/5 px-4">
          {!collapsed && (
            <span className="font-semibold text-lg">{t("nav.admin")}</span>
          )}
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setCollapsed(!collapsed)}
          >
            {collapsed ? (
              <Menu className="h-4 w-4" />
            ) : (
              <X className="h-4 w-4" />
            )}
          </Button>
        </div>
        {sidebarContent}
      </aside>

      {/* Main */}
      <main className="flex min-h-0 min-w-0 flex-1 flex-col bg-gradient-to-br from-background via-background/90 to-muted/30">
        <div className="h-14 shrink-0 admin-glass-topbar flex items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="h-5 w-5" />
            </Button>
            <span className="text-sm text-muted-foreground">
              {t("nav.adminPanel")}
            </span>
          </div>
          <div className="flex items-center gap-1">
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              className="gap-1.5"
            >
              {theme === "dark" ? (
                <Sun className="h-4 w-4" />
              ) : (
                <Moon className="h-4 w-4" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={toggleLang}
              className="gap-1.5"
            >
              <Globe className="h-4 w-4" />
              {lang === "zh" ? "EN" : "中文"}
            </Button>
          </div>
        </div>
        <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
          <div className="min-w-0 p-4 md:p-6">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
