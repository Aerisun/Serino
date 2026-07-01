import { Fragment, useCallback, useState, type ReactNode } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  useSystemInfoApiV1AdminSystemInfoGet,
  useVisitorRecordGroupRecordsApiV1AdminSystemVisitorRecordGroupsNewestRecordIdOldestRecordIdRecordsGet,
  useVisitorRecordGroupsApiV1AdminSystemVisitorRecordGroupsGet,
} from "@serino/api-client/admin";
import type { EnhancedDashboardStats } from "@serino/api-client/models";
import { Activity, ChevronDown, ChevronLeft, ChevronRight, ChevronUp, MonitorSmartphone, Users } from "lucide-react";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { SummaryMetricCard } from "@/components/dashboard/SummaryMetricCard";
import { Button } from "@/components/ui/Button";
import { TableCell, TableRow } from "@/components/ui/Table";
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

type VisitorRecordGroup = {
  id: string;
  ip_address: string;
  record_count: number;
  newest_record: VisitorRecord;
  oldest_record: VisitorRecord;
  newest_visited_at: string;
  oldest_visited_at: string;
};

type PaginatedResponse<T> = {
  items: T[];
  total: number;
  page: number;
  page_size: number;
};

const PAGE_SIZE = 20;
const DETAIL_PAGE_SIZE = 20;

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

function isGroupedVisit(row: VisitorRecordGroup) {
  return row.record_count > 1;
}

function statusPillClass(ok: boolean) {
  return cn(
    "inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium",
    ok
      ? "border-emerald-500/16 bg-emerald-500/12 text-emerald-700 dark:border-emerald-400/20 dark:text-emerald-200"
      : "border-rose-500/20 bg-rose-500/10 text-rose-600 dark:border-rose-400/20 dark:text-rose-300",
  );
}

function VisitorStatusPill({ record }: { record: VisitorRecord }) {
  const ok = record.status_code < 400;
  return <span className={statusPillClass(ok)}>{record.status_text || `${record.status_code}`}</span>;
}

function VisitorRecordCells({ record, frontendUrl, t }: { record: VisitorRecord; frontendUrl: string; t: (key: string) => string }) {
  const visitedPath = getVisitedPath(record);
  return (
    <>
      <TableCell className="min-w-[9rem]">{formatDateTime(record.visited_at)}</TableCell>
      <TableCell className="min-w-[9rem]">
        <div className="flex flex-col">
          <span className="tabular-nums text-foreground/90">{record.ip_address}</span>
          <span className="text-xs text-muted-foreground">{record.location || t("dashboard.visitorsUnknown")}</span>
        </div>
      </TableCell>
      <TableCell className="min-w-[6rem]">
        <a
          href={buildVisitedHref(frontendUrl, record)}
          target="_blank"
          rel="noreferrer"
          className="block max-w-[32rem] truncate text-[rgb(var(--admin-accent-rgb)/0.92)] underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
          title={visitedPath}
          onClick={(event) => event.stopPropagation()}
        >
          {record.path}
        </a>
      </TableCell>
      <TableCell className="min-w-[5rem]">
        <VisitorStatusPill record={record} />
      </TableCell>
    </>
  );
}

function VisitorGroupSummaryCell({ group, t }: { group: VisitorRecordGroup; t: (key: string) => string }) {
  return (
    <TableCell colSpan={4} className="py-2 pl-0 pr-4">
      <div className="grid min-h-9 min-w-[44rem] grid-cols-[minmax(16rem,1fr)_minmax(12rem,auto)_auto] items-center gap-4 rounded-[var(--admin-radius-md)] border border-[rgb(var(--admin-accent-rgb)/0.18)] bg-[linear-gradient(90deg,rgb(var(--admin-accent-rgb)/0.1),rgb(var(--admin-surface-1)/0.64)_52%,rgb(var(--admin-glow-rgb)/0.07))] px-3 py-1.5 shadow-[inset_2px_0_0_rgb(var(--admin-accent-rgb)/0.46),0_12px_28px_-24px_rgb(var(--admin-accent-rgb)/0.6)]">
        <div className="flex min-w-0 items-center gap-3">
          <span className="shrink-0 tabular-nums font-medium text-foreground/92">{group.ip_address}</span>
          <span className="min-w-0 truncate text-xs text-muted-foreground">
            {group.newest_record.location || t("dashboard.visitorsUnknown")}
          </span>
        </div>
        <div className="flex min-w-0 items-center justify-center gap-2 text-xs">
          <span className="shrink-0 font-medium text-muted-foreground">{t("dashboard.visitorsGroupFirstVisit")}</span>
          <span className="truncate tabular-nums text-foreground/82">{formatDateTime(group.oldest_visited_at)}</span>
        </div>
        <span className="shrink-0 justify-self-end rounded-full border border-[rgb(var(--admin-accent-rgb)/0.18)] bg-[rgb(var(--admin-accent-rgb)/0.1)] px-2 py-0.5 text-[11px] font-medium text-[rgb(var(--admin-accent-rgb)/0.92)]">
          {t("dashboard.visitorsGroupCount").replace("{count}", String(group.record_count))}
        </span>
      </div>
    </TableCell>
  );
}

function VisitorRecordDetails({
  record,
  deviceTypeLabel,
  t,
}: {
  record: VisitorRecord;
  deviceTypeLabel: (value?: string | null) => string;
  t: (key: string) => string;
}) {
  const details: { label: string; value: ReactNode }[] = [
    { label: t("dashboard.visitorsColumnPath"), value: getVisitedPath(record) },
    { label: t("dashboard.visitorsDetailDevice"), value: deviceTypeLabel(record.device_type) },
    {
      label: t("dashboard.visitorsDetailBrowser"),
      value: [record.browser, record.browser_version].filter(Boolean).join(" ") || "-",
    },
    {
      label: t("dashboard.visitorsDetailOs"),
      value: [record.os, record.os_version].filter(Boolean).join(" ") || "-",
    },
    { label: t("dashboard.visitorsDetailScreen"), value: record.screen || "-" },
    { label: t("dashboard.visitorsDetailLanguage"), value: record.language || "-" },
    { label: t("dashboard.visitorsDetailLocation"), value: record.location || "-" },
    { label: "ISP", value: record.isp || "-" },
    { label: t("dashboard.visitorsDetailOwner"), value: record.owner || "-" },
    { label: t("dashboard.visitorsDetailDuration"), value: formatDurationMs(record.duration_ms) },
    {
      label: t("dashboard.visitorsDetailReferrer"),
      value: record.referer || record.referer_domain || "-",
    },
    {
      label: "UTM",
      value:
        [record.utm_source, record.utm_medium, record.utm_campaign, record.utm_term, record.utm_content]
          .filter(Boolean)
          .join(" / ") || "-",
    },
    { label: t("dashboard.visitorsDetailVisitorId"), value: record.visitor_id || "-" },
    { label: "User-Agent", value: record.user_agent || "-" },
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
}

function SingleRecordDetailRow({
  record,
  colSpan,
  deviceTypeLabel,
  t,
  grouped = false,
}: {
  record: VisitorRecord;
  colSpan: number;
  deviceTypeLabel: (value?: string | null) => string;
  t: (key: string) => string;
  grouped?: boolean;
}) {
  return (
    <TableRow className={grouped ? "border-l-4 border-l-[rgb(var(--admin-accent-rgb)/0.48)]" : undefined}>
      <TableCell colSpan={colSpan} className="bg-muted/20 px-4 py-0">
        <VisitorRecordDetails record={record} deviceTypeLabel={deviceTypeLabel} t={t} />
      </TableCell>
    </TableRow>
  );
}

function VisitorGroupRecordRows({
  group,
  colSpan,
  frontendUrl,
  deviceTypeLabel,
  t,
}: {
  group: VisitorRecordGroup;
  colSpan: number;
  frontendUrl: string;
  deviceTypeLabel: (value?: string | null) => string;
  t: (key: string) => string;
}) {
  const [page, setPage] = useState(1);
  const [expandedRecordIds, setExpandedRecordIds] = useState<Set<string>>(new Set());
  const recordsQuery =
    useVisitorRecordGroupRecordsApiV1AdminSystemVisitorRecordGroupsNewestRecordIdOldestRecordIdRecordsGet(
      group.newest_record.id,
      group.oldest_record.id,
      {
        page,
        page_size: DETAIL_PAGE_SIZE,
      },
    );
  const data = recordsQuery.data?.data as PaginatedResponse<VisitorRecord> | undefined;
  const records = data?.items ?? [];
  const total = data?.total ?? 0;
  const totalPages = Math.max(1, Math.ceil(total / DETAIL_PAGE_SIZE));

  const toggleRecord = (id: string) => {
    setExpandedRecordIds((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  if (recordsQuery.isLoading) {
    return (
      <TableRow className="border-l-4 border-l-[rgb(var(--admin-accent-rgb)/0.48)]">
        <TableCell colSpan={colSpan} className="bg-muted/20 px-4 py-5 text-sm text-muted-foreground">
          {t("common.loading")}
        </TableCell>
      </TableRow>
    );
  }

  if (records.length === 0) {
    return (
      <TableRow className="border-l-4 border-l-[rgb(var(--admin-accent-rgb)/0.48)]">
        <TableCell colSpan={colSpan} className="bg-muted/20 px-4 py-5 text-sm text-muted-foreground">
          {t("common.noData")}
        </TableCell>
      </TableRow>
    );
  }

  return (
    <>
      {records.map((record) => {
        const expanded = expandedRecordIds.has(record.id);
        return (
          <Fragment key={record.id}>
            <TableRow className="border-l-4 border-l-[rgb(var(--admin-accent-rgb)/0.48)] bg-[linear-gradient(90deg,rgb(var(--admin-accent-rgb)/0.075),rgb(var(--admin-surface-1)/0.36)_3.5rem)] hover:bg-[linear-gradient(90deg,rgb(var(--admin-accent-rgb)/0.12),rgb(var(--admin-surface-1)/0.68)_3.5rem)] dark:bg-[linear-gradient(90deg,rgb(var(--admin-accent-rgb)/0.12),rgb(255_255_255/0.025)_3.5rem)] dark:hover:bg-[linear-gradient(90deg,rgb(var(--admin-accent-rgb)/0.16),rgb(255_255_255/0.05)_3.5rem)]">
              <TableCell className="w-10 py-2 pl-3 pr-2">
                <Button
                  type="button"
                  variant="ghost"
                  size="icon"
                  className="h-8 w-8"
                  onClick={() => toggleRecord(record.id)}
                  aria-label={expanded ? t("common.collapse") : t("common.expand")}
                >
                  {expanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
                </Button>
              </TableCell>
              <VisitorRecordCells record={record} frontendUrl={frontendUrl} t={t} />
            </TableRow>
            {expanded ? (
              <SingleRecordDetailRow
                record={record}
                colSpan={colSpan}
                deviceTypeLabel={deviceTypeLabel}
                t={t}
                grouped
              />
            ) : null}
          </Fragment>
        );
      })}
      {totalPages > 1 ? (
        <TableRow className="border-l-4 border-l-[rgb(var(--admin-accent-rgb)/0.48)]">
          <TableCell colSpan={colSpan} className="bg-muted/20 px-4 py-3">
            <div className="flex items-center justify-end gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <span className="text-xs text-muted-foreground">
                {page} / {totalPages}
              </span>
              <Button
                variant="outline"
                size="sm"
                disabled={page >= totalPages}
                onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
            </div>
          </TableCell>
        </TableRow>
      ) : null}
    </>
  );
}

export default function VisitorMonitoringPage() {
  const { t } = useI18n();
  const [page, setPage] = useState(1);

  const { data: systemInfo } = useSystemInfoApiV1AdminSystemInfoGet();
  const frontendUrl = resolveFrontendUrl(systemInfo?.data?.site_url);
  const { data: dashboardStats } = useQuery(dashboardStatsQueryOptions());
  const stats = dashboardStats as EnhancedDashboardStats | undefined;
  const visitors = stats?.visitors;

  const groupsQuery = useVisitorRecordGroupsApiV1AdminSystemVisitorRecordGroupsGet({
    page,
    page_size: PAGE_SIZE,
  });
  const groupsData = groupsQuery.data?.data as PaginatedResponse<VisitorRecordGroup> | undefined;
  const groups = groupsData?.items ?? [];
  const total = groupsData?.total ?? 0;

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
        </div>
        <DataTable
          isLoading={groupsQuery.isLoading}
          columns={[
            { header: t("dashboard.visitorsColumnTime"), accessor: () => null, className: "min-w-[9rem]" },
            { header: t("dashboard.visitorsColumnIp"), accessor: () => null, className: "min-w-[9rem]" },
            { header: t("dashboard.visitorsColumnPath"), accessor: () => null, className: "min-w-[6rem]" },
            { header: t("dashboard.visitorsColumnStatus"), accessor: () => null, className: "min-w-[5rem]" },
          ]}
          data={groups}
          page={page}
          pageSize={PAGE_SIZE}
          total={total}
          onPageChange={setPage}
          getRowClassName={(row) =>
            isGroupedVisit(row)
              ? "bg-transparent hover:bg-transparent dark:hover:bg-transparent"
              : undefined
          }
          getExpandButtonClassName={(row) =>
            isGroupedVisit(row)
              ? "h-7 w-7 rounded-full border border-[rgb(var(--admin-accent-rgb)/0.16)] bg-[rgb(var(--admin-surface-1)/0.66)] text-[rgb(var(--admin-accent-rgb)/0.92)] shadow-none hover:bg-[rgb(var(--admin-accent-rgb)/0.1)]"
              : undefined
          }
          getExpandCellClassName={(row) => (isGroupedVisit(row) ? "py-2 pl-3 pr-2" : undefined)}
          renderCells={(row) =>
            isGroupedVisit(row) ? (
              <VisitorGroupSummaryCell group={row} t={t} />
            ) : (
              <VisitorRecordCells record={row.newest_record} frontendUrl={frontendUrl} t={t} />
            )
          }
          renderExpandedRows={(row, { colSpan }) =>
            isGroupedVisit(row) ? (
              <VisitorGroupRecordRows
                group={row}
                colSpan={colSpan}
                frontendUrl={frontendUrl}
                deviceTypeLabel={deviceTypeLabel}
                t={t}
              />
            ) : (
              <SingleRecordDetailRow
                record={row.newest_record}
                colSpan={colSpan}
                deviceTypeLabel={deviceTypeLabel}
                t={t}
              />
            )
          }
        />
      </section>
    </div>
  );
}
