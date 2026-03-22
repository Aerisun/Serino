import { useState } from "react";
import { NavLink, Outlet } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "@/auth/useAuth";
import { useI18n } from "@/i18n";
import { getDashboardStats } from "@/api/endpoints/system";
import { listComments } from "@/api/endpoints/comments";
import { listGuestbook } from "@/api/endpoints/comments";
import { Button } from "@/components/ui/Button";
import {
  LayoutDashboard,
  FileText,
  BookOpen,
  MessageSquare,
  Quote,
  Settings,
  Briefcase,
  Users,
  Shield,
  Image,
  Key,
  ClipboardList,
  Database,
  LogOut,
  Menu,
  X,
  Globe,
  UserCog,
  Info,
} from "lucide-react";
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
    ],
  },
  {
    labelKey: "nav.configuration",
    items: [
      { to: "/site-config", icon: Settings, labelKey: "nav.siteConfig" },
      { to: "/resume", icon: Briefcase, labelKey: "nav.resume" },
      { to: "/friends", icon: Users, labelKey: "nav.friends" },
    ],
  },
  {
    labelKey: "nav.moderation",
    items: [
      { to: "/moderation", icon: Shield, labelKey: "nav.moderation" },
      { to: "/assets", icon: Image, labelKey: "nav.assets" },
    ],
  },
  {
    labelKey: "nav.system",
    items: [
      { to: "/system/api-keys", icon: Key, labelKey: "nav.apiKeys" },
      { to: "/system/audit-log", icon: ClipboardList, labelKey: "nav.auditLog" },
      { to: "/system/backups", icon: Database, labelKey: "nav.backups" },
      { to: "/system/info", icon: Info, labelKey: "nav.systemInfo" },
      { to: "/settings", icon: UserCog, labelKey: "nav.settings" },
    ],
  },
];

export default function AdminLayout() {
  const { user, logout } = useAuth();
  const { t, lang, setLang } = useI18n();
  const [collapsed, setCollapsed] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);

  const { data: pendingComments } = useQuery({
    queryKey: ["comments", "pending-count"],
    queryFn: () => listComments({ page: 1, page_size: 1, status: "pending" }),
    refetchInterval: 30000,
  });
  const { data: pendingGuestbook } = useQuery({
    queryKey: ["guestbook", "pending-count"],
    queryFn: () => listGuestbook({ page: 1, page_size: 1, status: "pending" }),
    refetchInterval: 30000,
  });
  const pendingCount = (pendingComments?.total ?? 0) + (pendingGuestbook?.total ?? 0);

  const toggleLang = () => setLang(lang === "zh" ? "en" : "zh");

  const sidebarContent = (
    <>
      <nav className="flex-1 overflow-y-auto py-2">
        {navGroups.map((group) => (
          <div key={group.labelKey} className="mb-2">
            {!collapsed && (
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
                    "flex items-center gap-3 px-4 py-2 text-sm transition-colors hover:bg-accent",
                    isActive && "bg-accent text-accent-foreground font-medium",
                    collapsed && "justify-center px-2"
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

      <div className="border-t p-3">
        <div className={cn("flex items-center gap-2", collapsed && "justify-center")}>
          {!collapsed && (
            <span className="text-sm truncate flex-1">{user?.username}</span>
          )}
          <Button variant="ghost" size="icon" onClick={logout} title={t("nav.logout")}>
            <LogOut className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </>
  );

  return (
    <div className="flex h-screen overflow-hidden">
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
          "fixed inset-y-0 left-0 z-50 flex w-64 flex-col border-r bg-card transition-transform duration-200 md:hidden",
          sidebarOpen ? "translate-x-0" : "-translate-x-full"
        )}
      >
        <div className="flex h-14 items-center justify-between border-b px-4">
          <span className="font-semibold text-lg">{t("nav.admin")}</span>
          <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(false)}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        {sidebarContent}
      </aside>

      {/* Desktop sidebar */}
      <aside
        className={cn(
          "hidden md:flex md:flex-col border-r bg-card transition-all duration-200",
          collapsed ? "md:w-16" : "md:w-60"
        )}
      >
        <div className="flex h-14 items-center justify-between border-b px-4">
          {!collapsed && <span className="font-semibold text-lg">{t("nav.admin")}</span>}
          <Button variant="ghost" size="icon" onClick={() => setCollapsed(!collapsed)}>
            {collapsed ? <Menu className="h-4 w-4" /> : <X className="h-4 w-4" />}
          </Button>
        </div>
        {sidebarContent}
      </aside>

      {/* Main */}
      <main className="flex-1 overflow-y-auto">
        <div className="h-14 border-b flex items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              className="md:hidden"
              onClick={() => setSidebarOpen(true)}
            >
              <Menu className="h-5 w-5" />
            </Button>
            <span className="text-sm text-muted-foreground">{t("nav.adminPanel")}</span>
          </div>
          <Button variant="ghost" size="sm" onClick={toggleLang} className="gap-1.5">
            <Globe className="h-4 w-4" />
            {lang === "zh" ? "EN" : "中文"}
          </Button>
        </div>
        <div className="p-6 overflow-x-auto">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
