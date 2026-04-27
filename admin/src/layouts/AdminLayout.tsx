import { useEffect, useRef, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useAuth } from "@/auth/useAuth";
import { useI18n } from "@/i18n";
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
  SlidersHorizontal,
} from "lucide-react";
import { useTheme } from "@serino/theme";
import { cn } from "@/lib/utils";
import { warmAdminRoute } from "@/lib/adminRouteWarmup";
import {
  pendingModerationCountQueryOptions,
} from "@/pages/moderation/moderationQueries";

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
      { to: "/more", icon: SlidersHorizontal, labelKey: "nav.more" },
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

const TOPBAR_SCROLL_DELTA = 10;
const TOPBAR_SHOW_SCROLL_TOP = 24;

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const { t, lang, setLang } = useI18n();
  const { theme, setTheme } = useTheme();
  const location = useLocation();
  const queryClient = useQueryClient();
  const [collapsed, setCollapsed] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [topbarVisible, setTopbarVisible] = useState(true);
  const contentScrollRef = useRef<HTMLDivElement | null>(null);
  const lastScrollTopRef = useRef(0);

  const { data: moderationPending } = useQuery({
    ...pendingModerationCountQueryOptions(),
    refetchOnWindowFocus: true,
  });
  const pendingCount = moderationPending?.total ?? 0;

  const toggleLang = () => setLang(lang === "zh" ? "en" : "zh");

  useEffect(() => {
    const isDesktopViewport = () => window.matchMedia("(min-width: 768px)").matches;

    const getActiveScrollTop = () => {
      if (isDesktopViewport()) {
        return contentScrollRef.current?.scrollTop ?? 0;
      }

      return window.scrollY || document.documentElement.scrollTop || 0;
    };

    const syncTopbarVisibility = () => {
      const nextScrollTop = Math.max(getActiveScrollTop(), 0);
      const previousScrollTop = lastScrollTopRef.current;
      const delta = nextScrollTop - previousScrollTop;

      lastScrollTopRef.current = nextScrollTop;

      if (sidebarOpen) {
        setTopbarVisible(true);
        return;
      }

      if (nextScrollTop <= TOPBAR_SHOW_SCROLL_TOP) {
        setTopbarVisible(true);
        return;
      }

      if (Math.abs(delta) < TOPBAR_SCROLL_DELTA) {
        return;
      }

      setTopbarVisible(delta < 0);
    };

    const handleWindowScroll = () => {
      if (!isDesktopViewport()) {
        syncTopbarVisibility();
      }
    };

    const handleContentScroll = () => {
      if (isDesktopViewport()) {
        syncTopbarVisibility();
      }
    };

    const handleResize = () => {
      lastScrollTopRef.current = Math.max(getActiveScrollTop(), 0);
      setTopbarVisible(true);
    };

    lastScrollTopRef.current = Math.max(getActiveScrollTop(), 0);

    window.addEventListener("scroll", handleWindowScroll, { passive: true });
    window.addEventListener("resize", handleResize);
    const contentNode = contentScrollRef.current;
    contentNode?.addEventListener("scroll", handleContentScroll, { passive: true });

    return () => {
      window.removeEventListener("scroll", handleWindowScroll);
      window.removeEventListener("resize", handleResize);
      contentNode?.removeEventListener("scroll", handleContentScroll);
    };
  }, [sidebarOpen]);

  useEffect(() => {
    const currentScrollTop = window.matchMedia("(min-width: 768px)").matches
      ? contentScrollRef.current?.scrollTop ?? 0
      : window.scrollY || document.documentElement.scrollTop || 0;

    lastScrollTopRef.current = Math.max(currentScrollTop, 0);
    setTopbarVisible(true);
  }, [location.pathname, location.search]);

  const sidebarContent = (
    <>
      <nav className="flex-1 overflow-y-auto py-2">
        {navGroups.map((group) => (
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
                onMouseEnter={() => {
                  void warmAdminRoute(item.to, queryClient);
                }}
                onFocus={() => {
                  void warmAdminRoute(item.to, queryClient);
                }}
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
    <div className="admin-scrollbars flex min-h-screen bg-gradient-to-br from-background via-background/95 to-muted/35 md:h-dvh md:overflow-hidden">
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
          "fixed inset-y-0 left-0 z-50 flex w-max min-w-[10rem] max-w-[calc(100vw-1.5rem)] flex-col admin-glass-sidebar transition-transform duration-200 md:hidden",
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
      <main className="flex min-w-0 flex-1 flex-col bg-gradient-to-br from-background via-background/90 to-muted/30 md:min-h-0">
        <div
          className={cn(
            "sticky top-0 z-10 h-14 shrink-0 admin-glass-topbar flex items-center justify-between px-4 sm:px-6 transition-[transform,margin-bottom,opacity] duration-300",
            topbarVisible
              ? "translate-y-0 opacity-100"
              : "-translate-y-full -mb-14 opacity-0 pointer-events-none",
          )}
        >
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
        <div
          ref={contentScrollRef}
          className="flex-1 overscroll-contain md:min-h-0 md:overflow-y-auto"
        >
          <div className="min-w-0 p-4 pb-[calc(1.5rem+env(safe-area-inset-bottom))] md:p-6 md:pb-6">
            <Outlet />
          </div>
        </div>
      </main>
    </div>
  );
}
