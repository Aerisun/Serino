import { useMemo, useState, type ReactNode } from "react";
import { useNavigate } from "react-router-dom";
import {
  BarChart3,
  BookOpen,
  ChevronRight,
  FileText,
  Flag,
  MessageSquare,
  Quote,
  TrendingUp,
  Users,
} from "lucide-react";
import { useDashboardStatsApiV1AdminSystemDashboardStatsGet } from "@serino/api-client/admin";
import type { EnhancedDashboardStats, RecentContentItem } from "@serino/api-client/models";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import {
  DashboardEmptyState,
  DashboardSkeleton,
} from "@/components/dashboard/DashboardStates";
import { DashboardSurface } from "@/components/dashboard/DashboardSurface";
import { SummaryMetricCard } from "@/components/dashboard/SummaryMetricCard";
import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import { useI18n } from "@/i18n";
import {
  formatContentSlugFallback,
  formatContentTypeTitleLabel,
  getContentTargetFromPath,
} from "@/lib/contentPathLabel";

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

type TrafficPlotPoint = TrafficPoint & {
  x: number;
  y: number;
  xPercent: number;
  yPercent: number;
};

type TopPageMetric = {
  url: string;
  views: number;
  share?: number;
  title?: string | null;
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

type DashboardSection = "metrics" | "charts" | "recent" | "visitors";

function buildTrafficPlotPoints(points: TrafficPoint[], width: number, height: number): TrafficPlotPoint[] {
  if (points.length === 0) return [];
  const max = Math.max(...points.map((point) => point.views), 1);
  const stepX = points.length > 1 ? width / Math.max(points.length - 1, 1) : 0;
  return points.map((point, index) => {
    const x = points.length === 1 ? width / 2 : index * stepX;
    const y = height - (point.views / max) * (height - 20) - 10;
    return {
      ...point,
      x,
      y,
      xPercent: width === 0 ? 0 : (x / width) * 100,
      yPercent: height === 0 ? 0 : (y / height) * 100,
    };
  });
}

function buildTrafficPath(points: TrafficPlotPoint[]) {
  if (points.length <= 1) return "";

  let path = `M ${points[0].x} ${points[0].y}`;
  for (let index = 0; index < points.length - 1; index += 1) {
    const current = points[index];
    const next = points[index + 1];
    const controlX = (current.x + next.x) / 2;
    path += ` C ${controlX} ${current.y}, ${controlX} ${next.y}, ${next.x} ${next.y}`;
  }
  return path;
}

function clamp(value: number, min: number, max: number) {
  return Math.min(Math.max(value, min), max);
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

function formatPageLabel(url: string, t: (key: string) => string, explicitTitle?: string | null) {
  if (url === "/" || url === "") {
    return t("dashboard.homePage");
  }
  if (url === "/guestbook") {
    return t("dashboard.guestbook");
  }

  const target = getContentTargetFromPath(url);
  if (target) {
    return formatContentTypeTitleLabel({
      contentType: target.contentType,
      t,
      title: explicitTitle,
      slug: target.slug,
      separator: " / ",
    });
  }

  const normalizedExplicitTitle = explicitTitle?.trim();
  if (normalizedExplicitTitle) {
    return normalizedExplicitTitle;
  }

  const segments = url.split("/").filter(Boolean);
  const lastSegment = segments[segments.length - 1];
  if (!lastSegment) {
    return url;
  }
  return formatContentSlugFallback(lastSegment);
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
  const [activeSection, setActiveSection] = useState<DashboardSection>("metrics");
  const [hoveredVisitorIndex, setHoveredVisitorIndex] = useState<number | null>(null);

  const { data: raw, isLoading } =
    useDashboardStatsApiV1AdminSystemDashboardStatsGet();
  const stats = raw?.data as EnhancedDashboardStats | undefined;

  const distribution = useMemo(() => stats?.traffic?.distribution ?? [], [stats]);
  const topPages = useMemo(() => stats?.traffic?.top_pages ?? [], [stats]);
  const recentContent = useMemo(() => stats?.recent_content ?? [], [stats]);
  const visitorSeries = useMemo(
    () =>
      (stats?.visitors?.history ?? [])
        .map((point) => ({
          date: String(point.date),
          views: point.views ?? 0,
        }))
        .slice(-30),
    [stats],
  );
  const visitorTopPages = useMemo(() => stats?.visitors?.top_pages ?? [], [stats]);
  const recentVisits = useMemo(
    () => (stats?.visitors?.recent_visits ?? []) as VisitorRecord[],
    [stats],
  );

  const visitorPlotPoints = useMemo(
    () => buildTrafficPlotPoints(visitorSeries, 100, 100),
    [visitorSeries],
  );
  const visitorPath = useMemo(() => buildTrafficPath(visitorPlotPoints), [visitorPlotPoints]);
  const visitorMax = Math.max(...visitorSeries.map((point) => point.views), 0);
  const visitorPeakIndex = visitorSeries.findIndex((point) => point.views === visitorMax);
  const visitorPeakPoint = visitorPeakIndex >= 0 ? visitorSeries[visitorPeakIndex] : undefined;
  const visitorPeakPlotPoint =
    visitorPeakIndex >= 0 ? visitorPlotPoints[visitorPeakIndex] : undefined;
  const visitorLatestPoint = visitorSeries[visitorSeries.length - 1];
  const visitorLatestPlotPoint = visitorPlotPoints[visitorPlotPoints.length - 1];
  const hoveredVisitorPoint =
    hoveredVisitorIndex !== null ? visitorSeries[hoveredVisitorIndex] : undefined;
  const hoveredVisitorPlotPoint =
    hoveredVisitorIndex !== null ? visitorPlotPoints[hoveredVisitorIndex] : undefined;
  const visitorAverage = useMemo(
    () =>
      visitorSeries.length > 0
        ? visitorSeries.reduce((sum, point) => sum + point.views, 0) / visitorSeries.length
        : 0,
    [visitorSeries],
  );
  const visitorAxisPoints = useMemo(() => {
    if (visitorSeries.length === 0) return [] as TrafficPoint[];
    if (visitorSeries.length <= 3) return visitorSeries;

    const lastIndex = visitorSeries.length - 1;
    const selectedIndexes = [
      0,
      Math.floor(lastIndex / 2),
      lastIndex,
    ];
    const uniqueSortedIndexes = Array.from(new Set(selectedIndexes)).sort((a, b) => a - b);
    return uniqueSortedIndexes.map((index) => visitorSeries[index]);
  }, [visitorSeries]);
  const visitorStartPoint = visitorSeries[0];
  const trafficChartWidth = Math.max(520, Math.max(visitorSeries.length, 12) * 42);
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
  const sectionItems = [
    {
      value: "metrics",
      label: t("dashboard.sectionMetrics"),
      icon: TrendingUp,
    },
    {
      value: "charts",
      label: t("dashboard.sectionCharts"),
      icon: BarChart3,
    },
    {
      value: "recent",
      label: t("dashboard.sectionRecent"),
      icon: FileText,
    },
    {
      value: "visitors",
      label: t("dashboard.sectionVisitors"),
      icon: Users,
    },
  ] as const;

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
      <PageHeader
        title={t("dashboard.title")}
        secondary={
          <AdminSectionTabs
            items={sectionItems}
            value={activeSection}
            onValueChange={(value) => setActiveSection(value as DashboardSection)}
            className="w-fit"
          />
        }
      />

      <section className="admin-glass space-y-6 rounded-[var(--admin-radius-xl)] px-4 py-4 shadow-[var(--admin-shadow-sm)] md:px-6 md:py-5">
        {isLoading || !stats ? (
          <DashboardLoading />
        ) : (
          <Tabs
            value={activeSection}
            onValueChange={(value) => setActiveSection(value as DashboardSection)}
            className="space-y-6"
          >
            <TabsContent value="metrics" className="mt-0 space-y-6">
              <div className="grid gap-3 xl:grid-cols-[1.35fr_0.85fr]">
                <AdminSurface
                  eyebrow={t("dashboard.heroEyebrow")}
                  actions={<span className="text-xs text-muted-foreground">{latestSnapshotAt}</span>}
                  className="bg-[linear-gradient(180deg,rgb(var(--admin-surface-strong)/0.78),rgb(var(--admin-surface-1)/0.52))]"
                  contentClassName="grid gap-4 pt-0 sm:grid-cols-3"
                >
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
                </AdminSurface>

                <AdminSurface
                  eyebrow={t("dashboard.heroTopPage")}
                  actions={
                    featuredPage ? (
                      <span className="text-xs font-medium text-[rgb(var(--admin-accent-rgb)/0.85)]">
                        {formatShare(featuredPage.share)}
                      </span>
                    ) : null
                  }
                  className="bg-[rgb(var(--admin-surface-1)/0.62)]"
                  contentClassName="pt-0"
                >
                  {featuredPage ? (
                    <div className="space-y-2">
                      <div className="truncate text-xl font-semibold tracking-tight text-foreground/95">
                        {formatPageLabel(featuredPage.url, t, featuredPage.title)}
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
                </AdminSurface>
              </div>

              <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
                {summaryCards.map((card) => (
                  <SummaryMetricCard key={card.label} {...card} />
                ))}
              </div>
            </TabsContent>

            <TabsContent value="charts" className="mt-0 space-y-4">
              <div className="grid gap-4 xl:grid-cols-[1.5fr_0.9fr]">
                <DashboardSurface
                  title={t("dashboard.trafficTrendTitle")}
                  contentClassName="space-y-4"
                >
                  {visitorSeries.length > 0 ? (
                    <div className="space-y-3">
                      <div className="grid gap-3 border-b border-black/6 pb-3 dark:border-white/10 md:grid-cols-3">
                        {[
                          {
                            label: t("dashboard.trafficPeak"),
                            value: formatCompactNumber(visitorMax),
                            meta: visitorPeakPoint?.date ?? "--",
                          },
                          {
                            label: t("dashboard.trafficAverage"),
                            value: formatCompactNumber(visitorAverage),
                            meta: t("dashboard.trafficAverageMeta"),
                          },
                          {
                            label: t("dashboard.trafficPeriods"),
                            value: visitorSeries.length,
                            meta: `${visitorSeries.length}d`,
                          },
                        ].map((item) => (
                          <div
                            key={item.label}
                            className="space-y-1 md:border-l md:border-black/6 md:pl-4 md:first:border-l-0 md:first:pl-0 dark:md:border-white/10"
                          >
                            <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                              {item.label}
                            </p>
                            <p className="text-[1.75rem] font-semibold leading-none tracking-[-0.04em] text-foreground/96">
                              {item.value}
                            </p>
                            <p className="text-[12px] tabular-nums text-muted-foreground">
                              {item.meta}
                            </p>
                          </div>
                        ))}
                      </div>

                      <div className="overflow-x-auto overflow-y-hidden rounded-[22px] border border-black/6 bg-[linear-gradient(180deg,rgba(255,255,255,0.88),rgba(248,250,252,0.72))] dark:border-white/10 dark:bg-[linear-gradient(180deg,rgba(255,255,255,0.04),rgba(255,255,255,0.02))]">
                        <div className="min-w-full" style={{ minWidth: `${trafficChartWidth}px` }}>
                          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-black/6 px-4 py-3 dark:border-white/10 sm:px-5">
                            <div className="space-y-1">
                              <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted-foreground">
                                {t("dashboard.trafficPeriods")} / {visitorSeries.length}d
                              </p>
                              <p className="text-[13px] tabular-nums text-muted-foreground">
                                {visitorStartPoint?.date} - {visitorLatestPoint?.date}
                              </p>
                            </div>

                            <div className="flex items-center gap-4 text-[11px] font-medium tabular-nums text-muted-foreground">
                              {visitorPeakPlotPoint ? (
                                <span className="inline-flex items-center gap-2">
                                  <span className="h-2 w-2 rounded-full border border-[rgb(var(--admin-accent-rgb)/0.45)] bg-transparent" />
                                  {t("dashboard.trafficPeak")}
                                </span>
                              ) : null}
                              {visitorLatestPlotPoint ? (
                                <span className="inline-flex items-center gap-2">
                                  <span className="h-2 w-2 rounded-full bg-[rgb(var(--admin-accent-rgb)/0.9)]" />
                                  {visitorLatestPoint?.date}
                                </span>
                              ) : null}
                            </div>
                          </div>

                          <div className="px-4 pb-4 pt-5 sm:px-5 sm:pb-5">
                            <div
                              className="relative h-[216px]"
                              onMouseLeave={() => setHoveredVisitorIndex(null)}
                            >
                              <div className="pointer-events-none absolute inset-x-0 top-[18%] h-px bg-black/5 dark:bg-white/8" />
                              <div className="pointer-events-none absolute inset-x-0 top-[52%] h-px bg-black/[0.04] dark:bg-white/[0.06]" />
                              <div className="pointer-events-none absolute inset-x-0 bottom-0 h-px bg-black/6 dark:bg-white/10" />

                              {hoveredVisitorPoint && hoveredVisitorPlotPoint ? (
                                <div
                                  className="pointer-events-none absolute z-10 rounded-2xl border border-black/6 bg-background/94 px-3 py-2 text-left shadow-[0_16px_40px_-24px_rgba(15,23,42,0.35)] backdrop-blur dark:border-white/10 dark:bg-slate-950/88"
                                  style={{
                                    left: `${clamp(hoveredVisitorPlotPoint.xPercent, 10, 90)}%`,
                                    top: `${clamp(hoveredVisitorPlotPoint.yPercent - 14, 10, 76)}%`,
                                    transform: "translate(-50%, -100%)",
                                  }}
                                >
                                  <div className="text-[10px] font-medium uppercase tracking-[0.16em] text-muted-foreground">
                                    {hoveredVisitorPoint.date}
                                  </div>
                                  <div className="mt-1 text-sm font-semibold tabular-nums text-foreground/94">
                                    {formatCompactNumber(hoveredVisitorPoint.views)}
                                  </div>
                                </div>
                              ) : null}

                              <svg
                                viewBox="0 0 100 100"
                                preserveAspectRatio="none"
                                className="relative h-full w-full overflow-visible"
                              >
                                {visitorPath ? (
                                  <path
                                    d={visitorPath}
                                    fill="none"
                                    stroke="rgb(var(--admin-accent-rgb) / 0.88)"
                                    strokeWidth="1.05"
                                    strokeLinecap="round"
                                  />
                                ) : null}

                                {hoveredVisitorPlotPoint ? (
                                  <g>
                                    <circle
                                      cx={hoveredVisitorPlotPoint.x}
                                      cy={hoveredVisitorPlotPoint.y}
                                      r="2.8"
                                      fill="rgb(var(--admin-accent-rgb) / 0.12)"
                                    />
                                    <circle
                                      cx={hoveredVisitorPlotPoint.x}
                                      cy={hoveredVisitorPlotPoint.y}
                                      r="1.45"
                                      fill="rgb(var(--admin-accent-rgb) / 0.96)"
                                      stroke="rgb(255 255 255 / 0.94)"
                                      strokeWidth="0.6"
                                    />
                                  </g>
                                ) : null}
                              </svg>

                              <div className="absolute inset-0">
                                {visitorPlotPoints.map((point, index) => (
                                  <button
                                    key={`${point.date}-${index}`}
                                    type="button"
                                    className="absolute h-7 w-7 -translate-x-1/2 -translate-y-1/2 rounded-full bg-transparent focus:outline-none"
                                    style={{
                                      left: `${point.xPercent}%`,
                                      top: `${point.yPercent}%`,
                                    }}
                                    aria-label={`${point.date}: ${point.views}`}
                                    onMouseEnter={() => setHoveredVisitorIndex(index)}
                                    onFocus={() => setHoveredVisitorIndex(index)}
                                    onBlur={() => setHoveredVisitorIndex((current) => (current === index ? null : current))}
                                    onClick={() => setHoveredVisitorIndex(index)}
                                  />
                                ))}
                              </div>
                            </div>

                            <div className="mt-4 flex items-center justify-between text-[11px] tabular-nums text-muted-foreground">
                              {visitorAxisPoints.map((point, index) => {
                                const isLatest = point.date === visitorLatestPoint?.date;
                                const alignmentClass =
                                  index === 0
                                    ? "items-start text-left"
                                    : index === visitorAxisPoints.length - 1
                                      ? "items-end text-right"
                                      : "items-center text-center";

                                return (
                                  <div
                                    key={point.date}
                                    className={`flex flex-col gap-1 ${alignmentClass}`}
                                  >
                                    <span
                                      className={`h-1.5 w-1.5 rounded-full ${
                                        isLatest
                                          ? "bg-[rgb(var(--admin-accent-rgb)/0.85)]"
                                          : "bg-black/12 dark:bg-white/12"
                                      }`}
                                    />
                                    <div className={isLatest ? "font-medium text-foreground/88" : undefined}>
                                      {point.date}
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  ) : (
                    <DashboardEmptyState
                      title={t("dashboard.trafficEmptyTitle")}
                      description={t("dashboard.trafficEmptyDescription")}
                    />
                  )}
                </DashboardSurface>

                <DashboardSurface
                  title={t("dashboard.distributionTitle")}
                  contentClassName="max-h-[480px] space-y-1 divide-y divide-black/5 overflow-y-auto pr-1 dark:divide-white/10"
                >
                  {visitorTopPages.length > 0 ? (
                    visitorTopPages.map((item: TopPageMetric) => {
                      const percentage = Math.max((item.views / Math.max(...visitorTopPages.map((entry) => entry.views), 1)) * 100, 3);
                      return (
                        <div key={item.url} className="py-3 first:pt-0 last:pb-0">
                          <DashboardListRow
                            title={formatPageLabel(item.url, t, item.title)}
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
                              className="h-full rounded-full bg-[rgb(var(--admin-accent-rgb)/0.78)] transition-[width] duration-500"
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
              <div className="grid gap-4 xl:grid-cols-[1fr_0.95fr]">
                <DashboardSurface
                  title={t("dashboard.recentContent")}
                  contentClassName="max-h-[480px] space-y-1 divide-y divide-black/5 overflow-y-auto pr-1 dark:divide-white/10"
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
                                <span className="rounded-full border border-black/5 bg-white/70 px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.14em] text-[rgb(var(--admin-accent-rgb)/0.8)] dark:border-white/10 dark:bg-white/[0.04]">
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
                  title={t("dashboard.contentBreakdownTitle")}
                  contentClassName="max-h-[480px] space-y-4 overflow-y-auto pr-1"
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
                                <Icon className="h-4 w-4 text-[rgb(var(--admin-accent-rgb)/0.8)]" />
                              </div>
                              <span className="text-sm font-medium text-foreground/92">{item.label}</span>
                            </div>
                            <span className="text-sm font-semibold tabular-nums text-foreground/92">
                              {value}
                            </span>
                          </div>
                          <div className="h-2 overflow-hidden rounded-full bg-black/[0.05] dark:bg-white/[0.08]">
                            <div
                              className="h-full rounded-full bg-[rgb(var(--admin-accent-rgb)/0.76)]"
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
              <div className="grid gap-5 sm:grid-cols-2 xl:grid-cols-4">
                {[
                  {
                    label: t("dashboard.visitorsTotal"),
                    value: stats.visitors?.total_visits ?? 0,
                  },
                  {
                    label: t("dashboard.visitorsUv24h"),
                    value: stats.visitors?.unique_visitors_24h ?? 0,
                  },
                  {
                    label: t("dashboard.visitorsUv7d"),
                    value: stats.visitors?.unique_visitors_7d ?? 0,
                  },
                  {
                    label: t("dashboard.visitorsAvgDuration"),
                    value: formatDurationMs(stats.visitors?.average_request_duration_ms ?? 0),
                  },
                ].map((item) => (
                  <div key={item.label} className="flex items-baseline gap-2 whitespace-nowrap">
                    <span className="text-sm font-medium text-muted-foreground">{item.label}:</span>
                    <span className="text-lg font-bold tabular-nums text-foreground/95">
                      {item.value}
                    </span>
                  </div>
                ))}
              </div>

              <section className="space-y-3">
                <div className="flex items-center justify-between">
                  <h3 className="text-sm font-semibold tracking-[0.01em] text-foreground/92">
                    {t("dashboard.visitorsRecordsTitle")}
                  </h3>
                </div>
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
              </section>
            </TabsContent>
          </Tabs>
        )}
      </section>
    </div>
  );
}
