import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import type { SystemDiagnosticItemRead } from "@serino/api-client/models";
import {
  ArrowUpRight,
  Loader2,
  RefreshCcw,
} from "lucide-react";
import { AdminSurface } from "@/components/AdminSurface";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/i18n";
import { cn } from "@/lib/utils";
import { formatDateTimeInBeijing } from "@/lib/time";
import {
  startSystemDiagnosticRun,
  systemDiagnosticsQueryKey,
  systemDiagnosticsQueryOptions,
} from "@/pages/system/diagnosticsQueries";

const ACTION_ROUTES: Partial<Record<SystemDiagnosticItemRead["action_target"], string>> = {
  model_api: "/more/api-config",
  smtp: "/more/mail-config",
  proxy: "/more/proxy-config",
  object_storage: "/more/object-storage",
  object_storage_sync: "/assets?view=oss_sync",
  backup_settings: "/system/backups",
  backup_runs: "/system/backups?section=records&records=runs",
  mcp: "/integrations/mcp/settings",
  service_forwards: "/assets?view=service_forward",
};

const SYSTEM_GUIDANCE_KEYS: Record<string, string> = {
  database: "diagnostics.systemGuide.database",
  storage: "diagnostics.systemGuide.storage",
  diagnostic_runner: "diagnostics.systemGuide.runner",
};

const CHECK_LABEL_KEYS: Record<string, string> = {
  database: "diagnostics.check.database",
  storage: "diagnostics.check.storage",
  model_api: "diagnostics.check.modelApi",
  smtp: "diagnostics.check.smtp",
  object_storage: "diagnostics.check.objectStorage",
  proxy: "diagnostics.check.proxy",
  backup: "diagnostics.check.backup",
  mcp: "diagnostics.check.mcp",
  service_forwards: "diagnostics.check.serviceForwards",
  diagnostic_runner: "diagnostics.check.runner",
};

const STATUS_ORDER: Record<SystemDiagnosticItemRead["status"], number> = {
  failed: 0,
  warning: 1,
  healthy: 2,
  skipped: 3,
};

type Translate = (
  key: string,
  values?: Record<string, string | number>,
  fallback?: string,
) => string;

function diagnosticMessage(
  t: Translate,
  messageKey: string | null | undefined,
  params: Record<string, string | number> | null | undefined,
  fallback: string | null | undefined,
) {
  if (messageKey) {
    return t(messageKey, params ?? undefined, fallback ?? undefined);
  }
  return fallback ?? null;
}

function formatCompletedAt(value: string | null | undefined, lang: string) {
  if (!value) return null;
  return formatDateTimeInBeijing(value, lang === "zh" ? "zh-CN" : "en-US", {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function DiagnosticsPage() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const diagnosticsQuery = useQuery(
    systemDiagnosticsQueryOptions({ includeItems: true, pollWhileRunning: true }),
  );
  const state = diagnosticsQuery.data;
  const completedAt = formatCompletedAt(state?.completed_at, lang);
  const latestCheckValue = completedAt
    ?? (!state && diagnosticsQuery.isError
      ? t("diagnostics.latestUnavailable")
      : !state && diagnosticsQuery.isLoading
        ? t("common.loading")
        : t("diagnostics.neverRun"));
  const runMutation = useMutation({
    mutationFn: startSystemDiagnosticRun,
    onSuccess: (nextState) => {
      queryClient.setQueryData(systemDiagnosticsQueryKey(true), nextState);
      void queryClient.invalidateQueries({
        queryKey: systemDiagnosticsQueryKey(false),
      });
    },
  });

  const running = Boolean(state?.is_running || runMutation.isPending);
  const items = state?.items ?? [];
  const orderedItems = [...items].sort(
    (left, right) => STATUS_ORDER[left.status] - STATUS_ORDER[right.status],
  );

  return (
    <div className="space-y-6">
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-baseline gap-x-4 gap-y-1">
            <span>{t("diagnostics.title")}</span>
            <span className="text-sm font-medium text-muted-foreground">
              {t("diagnostics.latestCheck", {
                time: latestCheckValue,
              })}
            </span>
          </span>
        }
        actions={
          <Button
            onClick={() => {
              runMutation.reset();
              runMutation.mutate();
            }}
            disabled={running}
          >
            {running ? (
              <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            ) : (
              <RefreshCcw className="mr-2 h-4 w-4" />
            )}
            {running ? t("diagnostics.checking") : t("diagnostics.runNow")}
          </Button>
        }
      />

      {diagnosticsQuery.isError ? (
          <div
            role="alert"
            className="flex flex-col gap-3 rounded-[var(--admin-radius-lg)] border border-red-500/20 bg-red-500/[0.06] p-4 text-sm text-red-700 sm:flex-row sm:items-center sm:justify-between dark:text-red-300"
          >
            <span>{t("diagnostics.loadFailed")}</span>
            <Button
              type="button"
              variant="outline"
              className="shrink-0"
              onClick={() => void diagnosticsQuery.refetch()}
            >
              {t("diagnostics.reload")}
            </Button>
          </div>
        ) : null}
      {runMutation.isError ? (
          <div role="alert" className="rounded-[var(--admin-radius-lg)] border border-red-500/20 bg-red-500/[0.06] p-4 text-sm text-red-700 dark:text-red-300">
            {t("diagnostics.runFailed")}
          </div>
        ) : null}
      {state?.last_error ? (
          <div role="alert" className="rounded-[var(--admin-radius-lg)] border border-red-500/20 bg-red-500/[0.06] p-4 text-sm text-red-700 dark:text-red-300">
            {diagnosticMessage(t, state.last_error_key, undefined, state.last_error)}
          </div>
        ) : null}

      <AdminSurface>
        {diagnosticsQuery.isLoading ? (
          <div className="flex min-h-40 items-center justify-center text-muted-foreground">
            <Loader2 className="h-5 w-5 animate-spin" />
          </div>
        ) : orderedItems.length > 0 ? (
          <div className="grid gap-3 lg:grid-cols-3">
            {orderedItems.map((item) => {
              const isProblem = item.status === "warning" || item.status === "failed";
              const route = ACTION_ROUTES[item.action_target];
              const itemLabel = t(CHECK_LABEL_KEYS[item.key] ?? item.key);
              const systemGuideKey = SYSTEM_GUIDANCE_KEYS[item.key] ?? "diagnostics.systemGuide.default";
              const summary = diagnosticMessage(
                t,
                item.summary_key,
                item.summary_params,
                item.summary,
              );
              const detail = diagnosticMessage(
                t,
                item.detail_key,
                item.detail_params,
                item.detail,
              );
              return (
                <article
                  key={`${item.key}:${item.action_target}`}
                  className={cn(
                    "group relative flex min-h-40 flex-col rounded-[var(--admin-radius-lg)] border p-4",
                    route && "cursor-pointer transition-[border-color,box-shadow] hover:shadow-sm",
                    item.status === "failed" && "border-red-500/20 bg-red-500/[0.045]",
                    item.status === "warning" && "border-amber-500/20 bg-amber-500/[0.045]",
                    item.status === "healthy" && "border-emerald-500/15 bg-emerald-500/[0.035]",
                    item.status === "skipped" && "border-border/60 bg-muted/15",
                  )}
                >
                  {route ? (
                    <Link
                      to={route}
                      aria-label={t(
                        isProblem
                          ? "diagnostics.goFixLabel"
                          : "diagnostics.openConfigLabel",
                        { item: itemLabel },
                      )}
                      className="absolute inset-0 z-10 rounded-[var(--admin-radius-lg)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
                    />
                  ) : null}
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <h4 className="font-semibold text-foreground/95">{itemLabel}</h4>
                      <p className="mt-2 break-words text-sm leading-6 text-foreground/85">{summary}</p>
                    </div>
                    <StatusBadge status={item.status} />
                  </div>
                  {detail ? (
                    <p className="mt-2 break-words text-xs leading-5 text-muted-foreground">{detail}</p>
                  ) : null}
                  {isProblem && item.action_target === "system" ? (
                    <p className="mt-3 rounded-md border border-border/60 bg-background/55 p-3 text-xs leading-5 text-muted-foreground">
                      {t(systemGuideKey)}
                    </p>
                  ) : null}
                  <div className="mt-auto flex items-end justify-between gap-3 pt-4">
                    <span className="text-[11px] text-muted-foreground">
                      {typeof item.duration_ms === "number"
                        ? t("diagnostics.duration", { duration: item.duration_ms })
                        : null}
                    </span>
                    {route ? (
                      <span className="inline-flex items-center gap-1.5 text-sm font-medium text-[rgb(var(--admin-accent-rgb)/0.95)] transition-opacity group-hover:opacity-80">
                        {t(isProblem ? "diagnostics.goFix" : "diagnostics.openConfig")}
                        <ArrowUpRight className="h-3.5 w-3.5" />
                      </span>
                    ) : null}
                  </div>
                </article>
              );
            })}
          </div>
        ) : (
          <div className="rounded-[var(--admin-radius-lg)] border border-dashed p-8 text-center text-sm text-muted-foreground">
            {t("diagnostics.noResults")}
          </div>
        )}
      </AdminSurface>
    </div>
  );
}
