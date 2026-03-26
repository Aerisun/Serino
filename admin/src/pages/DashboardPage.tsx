import { useMemo, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  BookOpen,
  ChevronRight,
  Clock3,
  FileText,
  Flag,
  Globe,
  MessageSquare,
  Quote,
  TrendingUp,
  Users,
} from "lucide-react";
import { useDashboardStatsApiV1AdminSystemDashboardStatsGet } from "@serino/api-client/admin";
import type { EnhancedDashboardStats, RecentContentItem } from "@serino/api-client/models";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import {
  DashboardEmptyState,
  DashboardSkeleton,
} from "@/components/dashboard/DashboardStates";
import { DashboardSurface } from "@/components/dashboard/DashboardSurface";
import { SummaryMetricCard } from "@/components/dashboard/SummaryMetricCard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { useI18n } from "@/i18n";

const CONTENT_TYPE_ROUTES: Record<string, string> = {
  post: "/posts",
  diary: "/diary",
  thought: "/thoughts",
  excerpt: "/excerpts",
};

type TrafficPoint = {
  date: string;
  views: number;
};

type TopPageMetric = {
  url: string;
  views: number;
  share?: number;
};

type VisitorRecord = {
  id: string;
  visited_at: string;
  path: string;
  ip_address: string;
  location?: string | null;
  isp?: string | null;
  owner?: string | null;
  status_text?: string | null;
  user_agent?: string | null;
  referer?: string | null;
  status_code: number;
  duration_ms: number;
  is_bot?: boolean;
};

function buildTrafficPath(points: TrafficPoint[], width: number, height: number) {
  if (points.length === 0) return "";
  if (points.length === 1) return `M 0 ${height / 2}`;

  const max = Math.max(...points.map((point) => point.views), 1);
  const stepX = width / Math.max(points.length - 1, 1);
  const normalized = points.map((point, index) => ({
    x: index * stepX,
    y: height - (point.views / max) * (height - 12) - 6,
  }));

  let path = `M ${normalized[0].x} ${normalized[0].y}`;
  for (let index = 0; index < normalized.length - 1; index += 1) {
    const current = normalized[index];
    const next = normalized[index + 1];
    const controlX = (current.x + next.x) / 2;
    path += ` C ${controlX} ${current.y}, ${controlX} ${next.y}, ${next.x} ${next.y}`;
  }
  return path;
}

function formatCompactNumber(value: number) {
  return new Intl.NumberFormat("en", {
    notation: "compact",
    maximumFractionDigits: 1,
  }).format(value);
}

function formatDateTime(value: string) {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString([], {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function formatShare(value?: number) {
  return `${Math.round((value ?? 0) * 100)}%`;
}

function formatDurationMs(value: number) {
  return `${value} ms`;
}

function formatReadableSegment(segment: string) {
  try {
    const decoded = decodeURIComponent(segment).replace(/[-_]+/g, " ").trim();
    if (!decoded) return segment;
    return decoded.charAt(0).toUpperCase() + decoded.slice(1);
  } catch {
    return segment;
  }
}

function formatPageLabel(url: string, t: (key: string) => string) {
  if (url === "/" || url === "") {
    return t("dashboard.homePage");
  }
  if (url === "/guestbook") {
    return t("dashboard.guestbook");
  }

  const segments = url.split("/").filter(Boolean);
  const lastSegment = segments.at(-1);
  if (!lastSegment) {
    return url;
  }
  return formatReadableSegment(lastSegment);
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

function DashboardLoading() {
  return (
    <div className="space-y-6">
      <div className="flex gap-2">
        {Array.from({ length: 3 }, (_, index) => (
          <DashboardSkeleton key={index} className="h-10 w-28 rounded-2xl" />
        ))}
      </div>
      <DashboardSkeleton className="h-[152px] rounded-[26px]" />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <DashboardSkeleton key={index} className="h-[124px] rounded-[22px]" />
        ))}
      </div>
      <div className="grid gap-5 xl:grid-cols-[1.5fr_0.9fr]">
        <DashboardSkeleton className="h-[340px] rounded-[26px]" />
        <DashboardSkeleton className="h-[340px] rounded-[26px]" />
      </div>
      <div className="grid gap-5 xl:grid-cols-[1fr_0.95fr]">
        <DashboardSkeleton className="h-[300px] rounded-[26px]" />
        <DashboardSkeleton className="h-[300px] rounded-[26px]" />
      </div>
    </div>
  );
}

function DashboardListRow({
  title,
  subtitle,
  trailing,
  onClick,
}: {
  title: string;
  subtitle?: string;
  trailing?: ReactNode;
  onClick?: () => void;
}) {
  const content = (
    <>
      <div className="min-w-0 space-y-1">
        <div className="truncate text-sm font-medium text-foreground/92">{title}</div>
        {subtitle ? <div className="truncate text-xs text-muted-foreground">{subtitle}</div> : null}
      </div>
      <div className="flex items-center gap-3">{trailing}</div>
    </>
  );

  if (onClick) {
    return (
      <button
        type="button"
        className="flex w-full cursor-pointer items-center justify-between gap-4 rounded-2xl border border-transparent px-1 py-3 text-left transition-colors duration-200 hover:border-black/5 hover:bg-black/[0.028] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 dark:hover:border-white/10 dark:hover:bg-white/[0.03]"
        onClick={onClick}
      >
        {content}
      </button>
    );
  }

  return <div className="flex items-center justify-between gap-4 px-1 py-3">{content}</div>;
}

export default function DashboardPage() {
  const { t } = useI18n();
  const navigate = useNavigate();

  const { data: raw, isLoading } =
    useDashboardStatsApiV1AdminSystemDashboardStatsGet();
  const stats = raw?.data as EnhancedDashboardStats | undefined;

  const trafficSeries = useMemo(
    () =>
      (stats?.traffic?.history ?? []).map((point) => ({
        date: String(point.date),
        views: point.views,
      })),
    [stats],
  );
  const distribution = useMemo(() => stats?.traffic?.distribution ?? [], [stats]);
  const topPages = useMemo(() => stats?.traffic?.top_pages ?? [], [stats]);
  const recentContent = useMemo(() => stats?.recent_content ?? [], [stats]);
  const visitorSeries = useMemo(
    () =>
      (stats?.visitors?.history ?? []).map((point) => ({
        date: String(point.date),
        views: point.views,
      })),
    [stats],
  );
  const visitorTopPages = useMemo(() => stats?.visitors?.top_pages ?? [], [stats]);
  const recentVisits = useMemo(
    () => (stats?.visitors?.recent_visits ?? []) as VisitorRecord[],
    [stats],
  );

  const trafficPath = buildTrafficPath(trafficSeries, 100, 100);
  const visitorPath = buildTrafficPath(visitorSeries, 100, 100);
  const visitorMax = Math.max(...visitorSeries.map((point) => point.views), 1);
  const trafficChartWidth = Math.max(760, Math.max(trafficSeries.length, visitorSeries.length) * 72);
  const distributionChartWidth = Math.max(760, Math.max(distribution.length, visitorTopPages.length) * 88);
  const totalPublished =
    (stats?.aux_metrics?.published_posts ?? 0) +
    (stats?.aux_metrics?.published_diary_entries ?? 0) +
    (stats?.aux_metrics?.published_thoughts ?? 0) +
    (stats?.aux_metrics?.published_excerpts ?? 0);
  const totalComments = stats?.comments ?? 0;
  const totalGuestbook = stats?.guestbook_entries ?? 0;
  const pendingModeration = stats?.aux_metrics?.pending_moderation ?? 0;
  const totalViews = stats?.traffic?.total_views ?? 0;
  const latestSnapshotAt = stats?.traffic?.last_snapshot_at
    ? formatDateTime(stats.traffic.last_snapshot_at)
    : t("dashboard.heroSnapshotEmpty");
  const trackedPages = new Set([
    ...distribution.map((item) => item.url),
    ...topPages.map((item) => item.url),
  ]).size;
  const featuredPage = topPages[0];

  const summaryCards = [
    {
      label: t("dashboard.contentPublished"),
      value: totalPublished,
      hint: `${t("nav.posts")} · ${stats?.aux_metrics?.published_posts ?? 0}`,
      icon: FileText,
      tone: "accent" as const,
    },
    {
      label: t("dashboard.commentsTotal"),
      value: totalComments,
      hint: t("dashboard.commentsHint"),
      icon: MessageSquare,
      tone: "default" as const,
    },
    {
      label: t("dashboard.guestbookTotal"),
      value: totalGuestbook,
      hint: t("dashboard.guestbookHint"),
      icon: BookOpen,
      tone: "default" as const,
    },
    {
      label: t("dashboard.pendingModeration"),
      value: pendingModeration,
      hint:
        pendingModeration > 0
          ? t("dashboard.pendingModerationAttention")
          : t("dashboard.pendingModerationClear"),
      icon: Flag,
      tone: pendingModeration > 0 ? "warning" : "default",
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("dashboard.title")} description={t("dashboard.description")} />

      <section className="space-y-6 rounded-[30px] border border-black/5 bg-white/42 px-4 py-4 shadow-[0_12px_36px_rgba(15,23,42,0.04)] backdrop-blur-xl dark:border-white/10 dark:bg-white/[0.03] dark:shadow-none md:px-6 md:py-5">
        {isLoading || !stats ? (
          <DashboardLoading />
        ) : (
          <Tabs defaultValue="metrics" className="space-y-6">
            <TabsList className="h-11 rounded-2xl border border-black/5 bg-white/64 p-1 text-muted-foreground shadow-none dark:border-white/10 dark:bg-white/[0.04]">
              <TabsTrigger
                value="metrics"
                className="h-8 rounded-xl px-4 text-sm font-medium tracking-[0.01em] data-[state=active]:bg-white data-[state=active]:text-foreground data-[state=active]:shadow-none dark:data-[state=active]:bg-white/[0.08]"
              >
                {t("dashboard.sectionMetrics")}
              </TabsTrigger>
              <TabsTrigger
                value="charts"
                className="h-8 rounded-xl px-4 text-sm font-medium tracking-[0.01em] data-[state=active]:bg-white data-[state=active]:text-foreground data-[state=active]:shadow-none dark:data-[state=active]:bg-white/[0.08]"
              >
                {t("dashboard.sectionCharts")}
              </TabsTrigger>
              <TabsTrigger
                value="recent"
                className="h-8 rounded-xl px-4 text-sm font-medium tracking-[0.01em] data-[state=active]:bg-white data-[state=active]:text-foreground data-[state=active]:shadow-none dark:data-[state=active]:bg-white/[0.08]"
              >
                {t("dashboard.sectionRecent")}
              </TabsTrigger>
              <TabsTrigger
                value="visitors"
                className="h-8 rounded-xl px-4 text-sm font-medium tracking-[0.01em] data-[state=active]:bg-white data-[state=active]:text-foreground data-[state=active]:shadow-none dark:data-[state=active]:bg-white/[0.08]"
              >
                {t("dashboard.sectionVisitors")}
              </TabsTrigger>
            </TabsList>

            <TabsContent value="metrics" className="mt-0 space-y-6">
              <div className="grid gap-3 xl:grid-cols-[1.35fr_0.85fr]">
                <div className="rounded-[26px] border border-black/5 bg-[linear-gradient(180deg,rgba(255,255,255,0.72),rgba(255,255,255,0.44))] px-5 py-5 dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.025))]">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.78)]">
                      {t("dashboard.heroEyebrow")}
                    </span>
                    <span className="text-xs text-muted-foreground">{latestSnapshotAt}</span>
                  </div>
                  <div className="mt-5 grid gap-4 sm:grid-cols-3">
                    {[
                      { label: t("dashboard.heroTraffic"), value: formatCompactNumber(totalViews) },
                      { label: t("dashboard.heroPages"), value: trackedPages },
                      { label: t("dashboard.heroModeration"), value: pendingModeration },
                    ].map((item) => (
                      <div key={item.label} className="space-y-1.5 border-l border-black/6 pl-4 first:border-l-0 first:pl-0 dark:border-white/10">
                        <div className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                          {item.label}
                        </div>
                        <div className="text-3xl font-semibold tracking-tight text-foreground/95">
                          {item.value}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="rounded-[26px] border border-black/5 bg-white/54 px-5 py-5 dark:border-white/10 dark:bg-white/[0.035]">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                      {t("dashboard.heroTopPage")}
                    </span>
                    {featuredPage ? (
                      <span className="text-xs font-medium text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.85)]">
                        {formatShare(featuredPage.share)}
                      </span>
                    ) : null}
                  </div>
                  {featuredPage ? (
                    <div className="mt-5 space-y-2">
                      <div className="truncate text-xl font-semibold tracking-tight text-foreground/95">
                        {formatPageLabel(featuredPage.url, t)}
                      </div>
                      <div className="truncate text-xs text-muted-foreground">{featuredPage.url}</div>
                      <div className="pt-3 text-3xl font-semibold tracking-tight text-foreground/95">
                        {formatCompactNumber(featuredPage.views)}
                      </div>
                    </div>
                  ) : (
                    <div className="mt-5 text-sm text-muted-foreground">
                      {t("dashboard.heroTopPageEmpty")}
                    </div>
                  )}
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {summaryCards.map((card) => (
                  <SummaryMetricCard key={card.label} {...card} />
                ))}
              </div>
            </TabsContent>

            <TabsContent value="charts" className="mt-0 space-y-5">
              <div className="grid gap-5 xl:grid-cols-[1.5fr_0.9fr]">
                <DashboardSurface
                  eyebrow={t("dashboard.trafficEyebrow")}
                  title={t("dashboard.trafficTrendTitle")}
                  description={t("dashboard.trafficTrendDescription")}
                  contentClassName="space-y-5"
                >
                  {visitorSeries.length > 0 ? (
                    <>
                      <div className="grid gap-3 sm:grid-cols-3">
                        {[
                          {
                            label: t("dashboard.trafficCurrent"),
                            value: formatCompactNumber(visitorSeries.at(-1)?.views ?? 0),
                          },
                          {
                            label: t("dashboard.trafficPeak"),
                            value: formatCompactNumber(visitorMax),
                          },
                          {
                            label: t("dashboard.trafficPeriods"),
                            value: visitorSeries.length,
                          },
                        ].map((item) => (
                          <div
                            key={item.label}
                            className="rounded-2xl border border-black/5 bg-black/[0.018] px-4 py-3 dark:border-white/10 dark:bg-white/[0.02]"
                          >
                            <p className="text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
                              {item.label}
                            </p>
                            <p className="mt-2 text-xl font-semibold tracking-tight text-foreground/95">
                              {item.value}
                            </p>
                          </div>
                        ))}
                      </div>

                      <div className="overflow-x-auto overflow-y-hidden rounded-[22px] border border-black/5 bg-[linear-gradient(180deg,rgba(255,255,255,0.48),rgba(255,255,255,0.12))] p-5 dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(255,255,255,0.05),rgba(255,255,255,0.015))]">
                        <div className="min-w-full" style={{ minWidth: `${trafficChartWidth}px` }}>
                          <div className="relative h-[220px] w-full">
                            <div className="absolute inset-0 grid grid-rows-4">
                            {Array.from({ length: 4 }, (_, index) => (
                              <div
                                key={index}
                                className="border-b border-dashed border-black/6 dark:border-white/8"
                              />
                            ))}
                            </div>
                            <svg
                              viewBox="0 0 100 100"
                              preserveAspectRatio="none"
                              className="relative h-full w-full overflow-visible"
                            >
                              <defs>
                                <linearGradient
                                  id="admin-dashboard-line-fill"
                                  x1="0"
                                  y1="0"
                                  x2="0"
                                  y2="1"
                                >
                                  <stop
                                    offset="0%"
                                    stopColor="rgb(var(--shiro-accent-rgb,60 100 200) / 0.18)"
                                  />
                                  <stop
                                    offset="100%"
                                    stopColor="rgb(var(--shiro-accent-rgb,60 100 200) / 0)"
                                  />
                                </linearGradient>
                              </defs>
                              {visitorPath ? (
                                <>
                                  <path
                                    d={`${visitorPath} L 100 100 L 0 100 Z`}
                                    fill="url(#admin-dashboard-line-fill)"
                                  />
                                  <path
                                    d={visitorPath}
                                    fill="none"
                                    stroke="rgb(var(--shiro-accent-rgb,60 100 200) / 0.88)"
                                    strokeWidth="2.1"
                                    strokeLinecap="round"
                                  />
                                  {visitorSeries.map((point, index) => {
                                    const x =
                                      visitorSeries.length === 1
                                        ? 0
                                        : (index / (visitorSeries.length - 1)) * 100;
                                    const y = 100 - (point.views / visitorMax) * 88 - 6;
                                    return (
                                      <circle
                                        key={`${point.date}-${index}`}
                                        cx={x}
                                        cy={y}
                                        r="1.65"
                                        fill="rgb(var(--shiro-accent-rgb,60 100 200) / 0.95)"
                                      />
                                    );
                                  })}
                                </>
                              ) : null}
                            </svg>
                          </div>
                          <div className="mt-4 grid grid-cols-4 gap-2 text-[11px] uppercase tracking-[0.14em] text-muted-foreground">
                            {visitorSeries
                              .filter(
                                (_, index) =>
                                  index === 0 ||
                                  index === visitorSeries.length - 1 ||
                                  index === Math.floor((visitorSeries.length - 1) / 2) ||
                                  index === Math.floor(((visitorSeries.length - 1) * 3) / 4),
                              )
                              .map((point) => (
                                <span key={point.date} className="truncate">
                                  {point.date}
                                </span>
                              ))}
                          </div>
                        </div>
                      </div>
                    </>
                  ) : (
                    <DashboardEmptyState
                      title={t("dashboard.trafficEmptyTitle")}
                      description={t("dashboard.trafficEmptyDescription")}
                    />
                  )}
                </DashboardSurface>

                <DashboardSurface
                  eyebrow={t("dashboard.distributionEyebrow")}
                  title={t("dashboard.distributionTitle")}
                  description={t("dashboard.distributionDescription")}
                  contentClassName="max-h-[520px] space-y-1 divide-y divide-black/5 overflow-y-auto pr-1 dark:divide-white/10"
                >
                  {visitorTopPages.length > 0 ? (
                    visitorTopPages.map((item: TopPageMetric) => {
                      const percentage = Math.max((item.views / Math.max(...visitorTopPages.map((entry) => entry.views), 1)) * 100, 3);
                      return (
                        <div key={item.url} className="py-3 first:pt-0 last:pb-0">
                          <DashboardListRow
                            title={formatPageLabel(item.url, t)}
                            subtitle={item.url}
                            trailing={
                              <div className="text-right">
                                <div className="text-sm font-semibold tabular-nums text-foreground/92">
                                  {formatCompactNumber(item.views)}
                                </div>
                                <div className="text-[11px] text-muted-foreground">
                                  {formatShare(item.share)}
                                </div>
                              </div>
                            }
                          />
                          <div className="mt-2 h-2 overflow-hidden rounded-full bg-black/[0.05] dark:bg-white/[0.08]">
                            <div
                              className="h-full rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.78)] transition-[width] duration-500"
                              style={{ width: `${percentage}%` }}
                            />
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <DashboardEmptyState
                      title={t("dashboard.distributionEmptyTitle")}
                      description={t("dashboard.distributionEmptyDescription")}
                      compact
                    />
                  )}
                </DashboardSurface>
              </div>

            </TabsContent>

            <TabsContent value="recent" className="mt-0">
              <div className="grid gap-5 xl:grid-cols-[1fr_0.95fr]">
                <DashboardSurface
                  eyebrow={t("dashboard.recentEyebrow")}
                  title={t("dashboard.recentContent")}
                  description={t("dashboard.recentContentDescription")}
                  contentClassName="max-h-[520px] space-y-1 divide-y divide-black/5 overflow-y-auto pr-1 dark:divide-white/10"
                >
                  {recentContent.length > 0 ? (
                    recentContent.map((item: RecentContentItem) => (
                      <div key={item.id} className="py-2.5 first:pt-0 last:pb-0">
                        <DashboardListRow
                          title={item.title}
                          subtitle={formatDateTime(item.updated_at)}
                          onClick={() =>
                            navigate(
                              `${CONTENT_TYPE_ROUTES[item.content_type] || "/posts"}/${item.id}`,
                            )
                          }
                          trailing={
                            <>
                              <div className="hidden items-center gap-2 sm:flex">
                                <span className="rounded-full border border-black/5 bg-white/70 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.8)] dark:border-white/10 dark:bg-white/[0.04]">
                                  {contentTypeLabel(item.content_type, t)}
                                </span>
                                <StatusBadge status={item.status} />
                              </div>
                              <ChevronRight className="h-4 w-4 text-muted-foreground" />
                            </>
                          }
                        />
                      </div>
                    ))
                  ) : (
                    <DashboardEmptyState
                      title={t("dashboard.recentEmptyTitle")}
                      description={t("dashboard.recentEmptyDescription")}
                      compact
                    />
                  )}
                </DashboardSurface>

                <DashboardSurface
                  eyebrow={t("dashboard.contentEyebrow")}
                  title={t("dashboard.contentBreakdownTitle")}
                  description={t("dashboard.contentBreakdownDescription")}
                  contentClassName="max-h-[520px] space-y-4 overflow-y-auto pr-1"
                >
                  {totalPublished > 0 ? (
                    [
                      { key: "post", label: t("nav.posts"), icon: FileText },
                      { key: "diary", label: t("nav.diary"), icon: BookOpen },
                      {
                        key: "thought",
                        label: t("nav.thoughts"),
                        icon: TrendingUp,
                      },
                      { key: "excerpt", label: t("nav.excerpts"), icon: Quote },
                    ].map((item) => {
                      const value =
                        item.key === "post"
                          ? stats.aux_metrics.published_posts
                          : item.key === "diary"
                            ? stats.aux_metrics.published_diary_entries
                            : item.key === "thought"
                              ? stats.aux_metrics.published_thoughts
                              : stats.aux_metrics.published_excerpts;
                      const share = Math.max((value / totalPublished) * 100, value > 0 ? 4 : 0);
                      const Icon = item.icon;
                      return (
                        <div key={item.key} className="space-y-2">
                          <div className="flex items-center justify-between gap-3">
                            <div className="flex items-center gap-3">
                              <div className="rounded-full border border-black/5 bg-white/70 p-2 dark:border-white/10 dark:bg-white/[0.04]">
                                <Icon className="h-4 w-4 text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.8)]" />
                              </div>
                              <span className="text-sm font-medium text-foreground/92">{item.label}</span>
                            </div>
                            <span className="text-sm font-semibold tabular-nums text-foreground/92">
                              {value}
                            </span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-black/[0.05] dark:bg-white/[0.08]">
                            <div
                              className="h-full rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.76)]"
                              style={{ width: `${share}%` }}
                            />
                          </div>
                        </div>
                      );
                    })
                  ) : (
                    <DashboardEmptyState
                      title={t("dashboard.contentBreakdownEmptyTitle")}
                      description={t("dashboard.contentBreakdownEmptyDescription")}
                    />
                  )}
                </DashboardSurface>
              </div>
            </TabsContent>

            <TabsContent value="visitors" className="mt-0 space-y-5">
              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {[
                  {
                    label: t("dashboard.visitorsTotal"),
                    value: stats.visitors?.total_visits ?? 0,
                    hint: t("dashboard.visitorsTotalHint"),
                    icon: Globe,
                    tone: "accent" as const,
                  },
                  {
                    label: t("dashboard.visitorsUv24h"),
                    value: stats.visitors?.unique_visitors_24h ?? 0,
                    hint: t("dashboard.visitorsUv24hHint"),
                    icon: Users,
                    tone: "default" as const,
                  },
                  {
                    label: t("dashboard.visitorsUv7d"),
                    value: stats.visitors?.unique_visitors_7d ?? 0,
                    hint: t("dashboard.visitorsUv7dHint"),
                    icon: Users,
                    tone: "default" as const,
                  },
                  {
                    label: t("dashboard.visitorsAvgDuration"),
                    value: formatDurationMs(stats.visitors?.average_request_duration_ms ?? 0),
                    hint: t("dashboard.visitorsAvgDurationHint"),
                    icon: Clock3,
                    tone: "default" as const,
                  },
                ].map((card) => (
                  <SummaryMetricCard key={card.label} {...card} />
                ))}
              </div>

              <DashboardSurface
                eyebrow={t("dashboard.visitorsRecordsEyebrow")}
                title={t("dashboard.visitorsRecordsTitle")}
                description={t("dashboard.visitorsRecordsDescription")}
                contentClassName="space-y-4"
              >
                <DataTable
                  columns={[
                    {
                      header: t("dashboard.visitorsColumnTime"),
                      accessor: (row: VisitorRecord) => formatDateTime(row.visited_at),
                    },
                    {
                      header: t("dashboard.visitorsColumnPath"),
                      accessor: (row: VisitorRecord) => row.path,
                    },
                    {
                      header: t("dashboard.visitorsColumnIp"),
                      accessor: (row: VisitorRecord) => row.ip_address,
                    },
                    {
                      header: t("dashboard.visitorsColumnLocation"),
                      accessor: (row: VisitorRecord) => row.location || "未知",
                    },
                    {
                      header: t("dashboard.visitorsColumnDuration"),
                      accessor: (row: VisitorRecord) => formatDurationMs(row.duration_ms),
                    },
                    {
                      header: t("dashboard.visitorsColumnStatus"),
                      accessor: (row: VisitorRecord) => row.status_text || `${row.status_code}`,
                    },
                  ]}
                  data={recentVisits}
                  page={1}
                  pageSize={recentVisits.length || 10}
                  total={recentVisits.length}
                  renderExpandedRow={(row: VisitorRecord) => (
                    <div className="space-y-2 py-4 text-sm text-muted-foreground">
                      <div>
                        <span className="font-medium text-foreground/90">ISP:</span> {row.isp || "-"}
                      </div>
                      <div>
                        <span className="font-medium text-foreground/90">Owner:</span> {row.owner || "-"}
                      </div>
                      <div>
                        <span className="font-medium text-foreground/90">UA:</span> {row.user_agent || "-"}
                      </div>
                      <div>
                        <span className="font-medium text-foreground/90">Referer:</span> {row.referer || "-"}
                      </div>
                    </div>
                  )}
                />
              </DashboardSurface>
            </TabsContent>
          </Tabs>
        )}
      </section>
    </div>
  );
}
