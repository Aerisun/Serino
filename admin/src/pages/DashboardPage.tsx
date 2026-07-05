import { useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  ArrowUpRight,
  BookOpen,
  ChevronRight,
  Eye,
  FileText,
  Flag,
  Image as ImageIcon,
  Lightbulb,
  Link2,
  MessageSquare,
  MessagesSquare,
  Quote,
  Users,
  type LucideIcon,
} from "lucide-react";
import {
  useGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGet,
  useListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGet,
} from "@serino/api-client/admin";
import type {
  BackupCommitRead,
  BackupSyncConfig,
  EnhancedDashboardStats,
  RecentContentItem,
} from "@serino/api-client/models";
import { StatusBadge } from "@/components/StatusBadge";
import {
  DashboardEmptyState,
  DashboardSkeleton,
} from "@/components/dashboard/DashboardStates";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";
import { formatDateTimeInBeijing } from "@/lib/time";
import {
  DASHBOARD_STATS_STALE_TIME,
  dashboardStatsQueryOptions,
} from "@/pages/dashboard/dashboardQueries";

const CONTENT_TYPE_ROUTES: Record<string, string> = {
  post: "/posts",
  diary: "/diary",
  thought: "/thoughts",
  excerpt: "/excerpts",
};

function formatCompactNumber(value: number) {
  return new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatDateTime(value: string) {
  const formatted = formatDateTimeInBeijing(value, "en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return formatted || value;
}

function formatBackupCommitTime(commit: BackupCommitRead | undefined) {
  const value = commit?.snapshot_finished_at ?? commit?.created_at;
  return typeof value === "string" ? formatDateTime(value) : null;
}

function greetingKey() {
  const hour = new Date().getHours();
  if (hour < 6) return "dashboard.greetingNight";
  if (hour < 12) return "dashboard.greetingMorning";
  if (hour < 18) return "dashboard.greetingAfternoon";
  return "dashboard.greetingEvening";
}

function contentTypeLabel(type: string, t: (key: string) => string) {
  const map: Record<string, string> = {
    post: t("nav.posts"),
    diary: t("nav.diary"),
    thought: t("nav.thoughts"),
    excerpt: t("nav.excerpts"),
  };
  return map[type] || type;
}

function StatTile({
  icon: Icon,
  label,
  value,
  onClick,
}: {
  icon: LucideIcon;
  label: string;
  value: number;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="admin-glass admin-transition-fast group flex min-h-[82px] min-w-0 flex-col items-center justify-center gap-1.5 rounded-[var(--admin-radius-lg)] px-3 py-3 text-center shadow-[var(--admin-shadow-sm)] transition-[background-color,border-color,box-shadow,transform] hover:-translate-y-0.5 hover:bg-[rgb(var(--admin-surface-1)/0.72)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 xl:min-h-[76px] xl:gap-1 xl:rounded-[var(--admin-radius-md)] xl:px-2 xl:py-2 dark:hover:bg-white/[0.05]"
    >
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-black/5 bg-white/70 text-foreground/65 xl:h-8 xl:w-8 dark:border-white/10 dark:bg-white/[0.04]",
        )}
      >
        <Icon className="h-[18px] w-[18px] xl:h-4 xl:w-4" />
      </span>
      <span className="min-w-0 w-full">
        <span className="block text-xl font-semibold leading-none tracking-tight tabular-nums text-foreground/95">
          {formatCompactNumber(value)}
        </span>
        <span className="mt-0.5 block truncate text-xs leading-4 text-muted-foreground">{label}</span>
      </span>
    </button>
  );
}

function TrafficMetricTile({
  icon: Icon,
  label,
  value,
  hint,
  warning,
}: {
  icon: LucideIcon;
  label: string;
  value: number | string;
  hint: string;
  warning?: boolean;
}) {
  return (
    <div
      className={cn(
        "admin-glass flex min-h-[88px] items-center justify-between gap-4 rounded-[var(--admin-radius-lg)] border px-4 py-3 shadow-none transition-[background-color,border-color]",
        warning
          ? "border-amber-200/70 bg-amber-50/60 text-amber-950 dark:border-amber-400/20 dark:bg-amber-500/8 dark:text-amber-100"
          : "border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] bg-[rgb(var(--admin-surface-1)/0.42)] text-foreground/90 dark:bg-white/[0.03]",
      )}
    >
      <div className="min-w-0">
        <p className="truncate text-[11px] font-medium uppercase tracking-[0.14em] text-muted-foreground/88">
          {label}
        </p>
        <p className="mt-2 text-[1.75rem] font-semibold leading-none tracking-tight tabular-nums text-foreground/95">
          {value}
        </p>
        <p className="mt-2 truncate text-xs leading-4 text-muted-foreground">
          {hint}
        </p>
      </div>
      <span
        className={cn(
          "flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-black/5 bg-white/65 text-muted-foreground/80 dark:border-white/10 dark:bg-white/[0.04]",
          warning && "text-amber-700 dark:text-amber-200",
        )}
      >
        <Icon className="h-4 w-4" />
      </span>
    </div>
  );
}

function DashboardLoading() {
  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 gap-3 xl:grid-cols-8">
        {Array.from({ length: 8 }, (_, index) => (
          <DashboardSkeleton key={index} className="h-[82px] rounded-[22px] xl:h-[76px] xl:rounded-[18px]" />
        ))}
      </div>
      <div className="grid gap-3 sm:grid-cols-3">
        {Array.from({ length: 3 }, (_, index) => (
          <DashboardSkeleton key={index} className="h-[120px] rounded-[22px]" />
        ))}
      </div>
      <DashboardSkeleton className="h-[280px] rounded-[26px]" />
    </div>
  );
}

export default function DashboardPage() {
  const { t } = useI18n();
  const navigate = useNavigate();

  const { data: dashboardStats, isLoading } = useQuery(dashboardStatsQueryOptions());
  const { data: backupConfigRaw } =
    useGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGet();
  const stats = dashboardStats as EnhancedDashboardStats | undefined;
  const backupConfig = backupConfigRaw?.data as BackupSyncConfig | undefined;
  const backupEnabled = backupConfig?.enabled === true;
  const { data: backupCommitsRaw } =
    useListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGet({
      query: {
        enabled: backupEnabled,
        staleTime: DASHBOARD_STATS_STALE_TIME,
        refetchOnWindowFocus: false,
      },
    });
  const backupCommits = (backupCommitsRaw?.data as BackupCommitRead[] | undefined) ?? [];
  const latestBackupAt = backupEnabled
    ? formatBackupCommitTime(backupCommits[0]) ?? t("dashboard.heroSnapshotEmpty")
    : null;

  const recentContent = useMemo(
    () => (stats?.recent_content ?? []) as RecentContentItem[],
    [stats],
  );

  const pendingModeration = stats?.aux_metrics?.pending_moderation ?? 0;
  const totalViews = stats?.traffic?.total_views ?? 0;
  const uniqueVisitors24h = stats?.visitors?.unique_visitors_24h ?? 0;

  const contentTiles: {
    key: string;
    icon: LucideIcon;
    label: string;
    value: number;
    route: string;
  }[] = stats
    ? [
        { key: "posts", icon: FileText, label: t("nav.posts"), value: stats.posts ?? 0, route: "/posts" },
        { key: "diary", icon: BookOpen, label: t("nav.diary"), value: stats.diary_entries ?? 0, route: "/diary" },
        { key: "thoughts", icon: Lightbulb, label: t("nav.thoughts"), value: stats.thoughts ?? 0, route: "/thoughts" },
        { key: "excerpts", icon: Quote, label: t("nav.excerpts"), value: stats.excerpts ?? 0, route: "/excerpts" },
        { key: "comments", icon: MessageSquare, label: t("dashboard.statComments"), value: stats.comments ?? 0, route: "/moderation" },
        { key: "guestbook", icon: MessagesSquare, label: t("dashboard.statGuestbook"), value: stats.guestbook_entries ?? 0, route: "/moderation" },
        { key: "friends", icon: Link2, label: t("nav.friends"), value: stats.friends ?? 0, route: "/friends" },
        { key: "assets", icon: ImageIcon, label: t("nav.assets"), value: stats.assets ?? 0, route: "/assets" },
      ]
    : [];

  return (
    <div className="space-y-6">
      {isLoading || !stats ? (
        <DashboardLoading />
      ) : (
        <div className="space-y-7">
          <section className="space-y-1.5">
            <div className="min-w-0 space-y-1.5">
              <h2 className="text-2xl font-semibold tracking-tight text-foreground/95 md:text-3xl">
                {t(greetingKey())}
              </h2>
              <p className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-sm text-muted-foreground">
                <span>{t("dashboard.welcomeSubtitle")}</span>
                {backupEnabled ? (
                  <span>{t("dashboard.heroLastBackup")} {latestBackupAt}</span>
                ) : null}
              </p>
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold tracking-[0.01em] text-foreground/90">
              {t("dashboard.overviewContent")}
            </h3>
            <div className="grid grid-cols-2 gap-3 xl:grid-cols-8">
              {contentTiles.map((tile) => (
                <StatTile
                  key={tile.key}
                  icon={tile.icon}
                  label={tile.label}
                  value={tile.value}
                  onClick={() => navigate(tile.route)}
                />
              ))}
            </div>
          </section>

          <section className="space-y-3">
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-sm font-semibold tracking-[0.01em] text-foreground/90">
                {t("dashboard.overviewTraffic")}
              </h3>
              <button
                type="button"
                onClick={() => navigate("/visitors/monitoring")}
                className="inline-flex items-center gap-1 text-xs font-medium text-[rgb(var(--admin-accent-rgb)/0.9)] transition-opacity hover:opacity-80"
              >
                {t("dashboard.viewMonitoring")}
                <ArrowUpRight className="h-3.5 w-3.5" />
              </button>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <TrafficMetricTile
                label={t("dashboard.heroTraffic")}
                value={formatCompactNumber(totalViews)}
                hint={t("dashboard.visitorsTotalHint")}
                icon={Eye}
              />
              <TrafficMetricTile
                label={t("dashboard.visitorsUv24h")}
                value={uniqueVisitors24h}
                hint={t("dashboard.visitorsUv24hHint")}
                icon={Users}
              />
              <TrafficMetricTile
                label={t("dashboard.pendingModeration")}
                value={pendingModeration}
                hint={
                  pendingModeration > 0
                    ? t("dashboard.pendingModerationAttention")
                    : t("dashboard.pendingModerationClear")
                }
                icon={Flag}
                warning={pendingModeration > 0}
              />
            </div>
          </section>

          <section className="space-y-3">
            <h3 className="text-sm font-semibold tracking-[0.01em] text-foreground/90">
              {t("dashboard.recentContent")}
            </h3>
            <div className="admin-glass rounded-[var(--admin-radius-lg)] px-4 py-2 shadow-[var(--admin-shadow-sm)]">
              {recentContent.length > 0 ? (
                <div className="divide-y divide-black/5 dark:divide-white/10">
                  {recentContent.map((item) => (
                    <button
                      key={item.id}
                      type="button"
                      onClick={() =>
                        navigate(`${CONTENT_TYPE_ROUTES[item.content_type] || "/posts"}/${item.id}`)
                      }
                      className="flex w-full items-center justify-between gap-4 rounded-2xl px-1 py-3 text-left transition-colors hover:bg-black/[0.028] dark:hover:bg-white/[0.03]"
                    >
                      <div className="min-w-0 space-y-1">
                        <div className="truncate text-sm font-medium text-foreground/92">{item.title}</div>
                        <div className="truncate text-xs text-muted-foreground">
                          {formatDateTime(item.updated_at)}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <span className="hidden rounded-full border border-black/5 bg-white/70 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-[rgb(var(--admin-accent-rgb)/0.8)] dark:border-white/10 dark:bg-white/[0.04] sm:inline">
                          {contentTypeLabel(item.content_type, t)}
                        </span>
                        <StatusBadge status={String(item.visibility || "")} />
                        <ChevronRight className="h-4 w-4 text-muted-foreground" />
                      </div>
                    </button>
                  ))}
                </div>
              ) : (
                <div className="py-6">
                  <DashboardEmptyState
                    title={t("dashboard.recentEmptyTitle")}
                    description={t("dashboard.recentEmptyDescription")}
                    compact
                  />
                </div>
              )}
            </div>
          </section>
        </div>
      )}
    </div>
  );
}
