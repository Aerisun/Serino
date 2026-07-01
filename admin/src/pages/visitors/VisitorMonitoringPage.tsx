import { useCallback, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  useSystemInfoApiV1AdminSystemInfoGet,
  useVisitorRecordsApiV1AdminSystemVisitorRecordsGet,
} from "@serino/api-client/admin";
import type { EnhancedDashboardStats } from "@serino/api-client/models";
import { Activity, MonitorSmartphone, Users } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { SummaryMetricCard } from "@/components/dashboard/SummaryMetricCard";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { useI18n } from "@/i18n";
import { formatDateTimeInBeijing } from "@/lib/time";
import { resolveFrontendUrl } from "@/lib/frontend-url";
import { cn } from "@/lib/utils";
import { dashboardStatsQueryOptions } from "@/pages/dashboard/dashboardQueries";
import { VisitorsSectionSwitch } from "@/pages/visitors/VisitorsSectionSwitch";

type VisitorRecord = {
  id: string;
  visited_at: string;
  path: string;
  query?: string | null;
  ip_address: string;
  visitor_id?: string | null;
  location?: string | null;
  country?: string | null;
  region?: string | null;
  city?: string | null;
  isp?: string | null;
  owner?: string | null;
  status_text?: string | null;
  user_agent?: string | null;
  browser?: string | null;
  browser_version?: string | null;
  os?: string | null;
  os_version?: string | null;
  device_type?: string | null;
  screen?: string | null;
  language?: string | null;
  referer?: string | null;
  referer_domain?: string | null;
  utm_source?: string | null;
  utm_medium?: string | null;
  utm_campaign?: string | null;
  utm_term?: string | null;
  utm_content?: string | null;
  status_code: number;
  duration_ms: number;
  is_bot?: boolean;
};

const PAGE_SIZE = 20;

function formatDateTime(value: string) {
  const formatted = formatDateTimeInBeijing(value, "en-US", {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
  return formatted || value;
}

function formatDurationMs(value: number) {
  return `${value} ms`;
}

function getVisitedPath(row: Pick<VisitorRecord, "path" | "query">) {
  const path = row.path || "/";
  if (!row.query) return path;
  return `${path}${row.query.startsWith("?") ? row.query : `?${row.query}`}`;
}

function buildVisitedHref(frontendUrl: string, row: Pick<VisitorRecord, "path" | "query">) {
  const visitedPath = getVisitedPath(row);
  const normalizedPath = visitedPath.replace(/^\/+/, "");
  return new URL(normalizedPath, `${frontendUrl.replace(/\/+$/, "")}/`).toString();
}

export default function VisitorMonitoringPage() {
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const [includeBots, setIncludeBots] = useState(false);

  const { data: systemInfo } = useSystemInfoApiV1AdminSystemInfoGet();
  const frontendUrl = resolveFrontendUrl(systemInfo?.data?.site_url);
  const { data: dashboardStats } = useQuery(dashboardStatsQueryOptions());
  const stats = dashboardStats as EnhancedDashboardStats | undefined;
  const visitors = stats?.visitors;

  const recordsQuery = useVisitorRecordsApiV1AdminSystemVisitorRecordsGet({
    page,
    page_size: PAGE_SIZE,
    include_bots: includeBots,
  });
  const recordsData = recordsQuery.data?.data as
    | { items: VisitorRecord[]; total: number; page: number; page_size: number }
    | undefined;
  const records = recordsData?.items ?? [];
  const total = recordsData?.total ?? 0;

  const deviceTypeLabel = useCallback(
    (value?: string | null) => {
      const key = (value || "unknown").toLowerCase();
      const known = ["desktop", "mobile", "tablet", "bot", "unknown"];
      return t(`dashboard.visitorsDevice.${known.includes(key) ? key : "unknown"}`);
    },
    [t],
  );

  const kpiCards = [
    {
      label: t("dashboard.visitorsTotal"),
      value: visitors?.total_visits ?? 0,
      hint: t("dashboard.visitorsTotalHint"),
      icon: Activity,
      tone: "accent" as const,
    },
    {
      label: t("dashboard.visitorsUv24h"),
      value: visitors?.unique_visitors_24h ?? 0,
      hint: t("dashboard.visitorsUv24hHint"),
      icon: Users,
      tone: "default" as const,
    },
    {
      label: t("dashboard.visitorsUv7d"),
      value: visitors?.unique_visitors_7d ?? 0,
      hint: t("dashboard.visitorsUv7dHint"),
      icon: Users,
      tone: "default" as const,
    },
    {
      label: t("dashboard.visitorsAvgDuration"),
      value: formatDurationMs(visitors?.average_request_duration_ms ?? 0),
      hint: t("dashboard.visitorsAvgDurationHint"),
      icon: MonitorSmartphone,
      tone: "default" as const,
    },
  ];

  return (
    <div className="space-y-6">
      <PageHeader title={t("nav.visitors")} secondary={<VisitorsSectionSwitch />} />

      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {kpiCards.map((card) => (
          <SummaryMetricCard
            key={card.label}
            label={card.label}
            value={card.value}
            hint={card.hint}
            icon={card.icon}
            tone={card.tone}
            compact
          />
        ))}
      </div>

      <section className="space-y-3">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h3 className="text-sm font-semibold tracking-[0.01em] text-foreground/92">
            {t("dashboard.visitorsRecordsTitle")}
          </h3>
          <AppleSwitch
            className="w-auto"
            checked={includeBots}
            onCheckedChange={(checked) => {
              setPage(1);
              setIncludeBots(checked);
            }}
            label={t("dashboard.visitorsIncludeBots")}
          />
        </div>
        <DataTable
          isLoading={recordsQuery.isLoading}
          columns={[
            {
              header: t("dashboard.visitorsColumnTime"),
              accessor: (row: VisitorRecord) => formatDateTime(row.visited_at),
              className: "min-w-[9rem]",
            },
            {
              header: t("dashboard.visitorsColumnIp"),
              accessor: (row: VisitorRecord) => (
                <div className="flex flex-col">
                  <span className="tabular-nums text-foreground/90">{row.ip_address}</span>
                  <span className="text-xs text-muted-foreground">
                    {row.location || t("dashboard.visitorsUnknown")}
                  </span>
                </div>
              ),
              className: "min-w-[9rem]",
            },
            {
              header: t("dashboard.visitorsColumnPath"),
              accessor: (row: VisitorRecord) => {
                const visitedPath = getVisitedPath(row);
                return (
                  <a
                    href={buildVisitedHref(frontendUrl, row)}
                    target="_blank"
                    rel="noreferrer"
                    className="block max-w-[32rem] text-[rgb(var(--admin-accent-rgb)/0.92)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    title={visitedPath}
                  >
                    {row.path}
                  </a>
                );
              },
              className: "min-w-[6rem]",
            },
            {
              header: t("dashboard.visitorsColumnStatus"),
              accessor: (row: VisitorRecord) => {
                const ok = row.status_code < 400;
                return (
                  <span
                    className={cn(
                      "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
                      ok
                        ? "border-emerald-500/16 bg-emerald-500/12 text-emerald-700 dark:border-emerald-400/20 dark:text-emerald-200"
                        : "border-rose-500/20 bg-rose-500/10 text-rose-600 dark:border-rose-400/20 dark:text-rose-300",
                    )}
                  >
                    {row.status_text || `${row.status_code}`}
                  </span>
                );
              },
              className: "min-w-[5rem]",
            },
          ]}
          data={records}
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={setPage}
          renderExpandedRow={(row: VisitorRecord) => {
            const details: { label: string; value: ReactNode }[] = [
              { label: t("dashboard.visitorsColumnPath"), value: getVisitedPath(row) },
              { label: t("dashboard.visitorsDetailDevice"), value: deviceTypeLabel(row.device_type) },
              {
                label: t("dashboard.visitorsDetailBrowser"),
                value: [row.browser, row.browser_version].filter(Boolean).join(" ") || "-",
              },
              {
                label: t("dashboard.visitorsDetailOs"),
                value: [row.os, row.os_version].filter(Boolean).join(" ") || "-",
              },
              { label: t("dashboard.visitorsDetailScreen"), value: row.screen || "-" },
              { label: t("dashboard.visitorsDetailLanguage"), value: row.language || "-" },
              { label: t("dashboard.visitorsDetailLocation"), value: row.location || "-" },
              { label: "ISP", value: row.isp || "-" },
              { label: t("dashboard.visitorsDetailOwner"), value: row.owner || "-" },
              { label: t("dashboard.visitorsDetailDuration"), value: formatDurationMs(row.duration_ms) },
              {
                label: t("dashboard.visitorsDetailReferrer"),
                value: row.referer || row.referer_domain || "-",
              },
              {
                label: "UTM",
                value:
                  [row.utm_source, row.utm_medium, row.utm_campaign, row.utm_term, row.utm_content]
                    .filter(Boolean)
                    .join(" / ") || "-",
              },
              { label: t("dashboard.visitorsDetailVisitorId"), value: row.visitor_id || "-" },
              { label: "User-Agent", value: row.user_agent || "-" },
            ];
            return (
              <div className="grid gap-x-6 gap-y-2 py-4 text-sm text-muted-foreground sm:grid-cols-2">
                {details.map((detail) => (
                  <div key={detail.label} className="flex gap-2">
                    <span className="shrink-0 font-medium text-foreground/90">{detail.label}:</span>
                    <span className="break-all">{detail.value}</span>
                  </div>
                ))}
              </div>
            );
          }}
        />
      </section>
    </div>
  );
}
