import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Download,
  RefreshCw,
  ShieldAlert,
} from "lucide-react";
import { toast } from "sonner";
import {
  useCancelQueuedUpdateRequestApiV1AdminSystemUpdatesRequestsRequestIdDelete,
  useCheckUpdatesApiV1AdminSystemUpdatesCheckPost,
  useUpdateStatusApiV1AdminSystemUpdatesStatusGet,
  useUpgradeSystemApiV1AdminSystemUpdatesUpgradePost,
} from "@serino/api-client/admin";
import type { SystemUpdateStatusRead } from "@serino/api-client/models";
import MarkdownPreview from "@/components/MarkdownPreview";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { formatDateTimeInBeijing } from "@/lib/time";
import { cn } from "@/lib/utils";
import {
  resolveUpdateNoticeStatus,
  shouldCacheUpdateStatus,
  shouldClearCachedUpdateStatus,
  shouldShowUpdateReleaseNotes,
  shouldSurfaceUpdateStatus,
  shouldQueueSilentUpdateCheck,
} from "@/pages/dashboard/systemUpdateNoticeLogic";

type UpdateState = NonNullable<SystemUpdateStatusRead["state"]>;
const UPDATE_STATUS_CACHE_KEY = "serino:system-update-status:v1";
const UPDATE_STATUS_CACHE_MAX_AGE_MS = 24 * 60 * 60 * 1000;

const ACTIVE_STATES = new Set<UpdateState>([
  "checking",
  "queued",
  "preflight",
  "running",
  "restarting",
]);

function isActiveState(state: SystemUpdateStatusRead["state"] | undefined) {
  return Boolean(state && ACTIVE_STATES.has(state));
}

function isTerminalAttentionState(state: SystemUpdateStatusRead["state"] | undefined) {
  return state === "failed" || state === "rolled_back";
}

function readCachedUpdateStatus(): SystemUpdateStatusRead | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(UPDATE_STATUS_CACHE_KEY);
    if (!raw) return null;
    const cached = JSON.parse(raw) as { cached_at?: unknown; status?: unknown };
    const cachedAt = typeof cached.cached_at === "number" ? cached.cached_at : 0;
    if (!cachedAt || Date.now() - cachedAt > UPDATE_STATUS_CACHE_MAX_AGE_MS) {
      window.localStorage.removeItem(UPDATE_STATUS_CACHE_KEY);
      return null;
    }
    return cached.status && typeof cached.status === "object"
      ? cached.status as SystemUpdateStatusRead
      : null;
  } catch {
    window.localStorage.removeItem(UPDATE_STATUS_CACHE_KEY);
    return null;
  }
}

function cacheUpdateStatus(status: SystemUpdateStatusRead) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(
    UPDATE_STATUS_CACHE_KEY,
    JSON.stringify({ cached_at: Date.now(), status }),
  );
}

function clearCachedUpdateStatus() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(UPDATE_STATUS_CACHE_KEY);
}

function formatReleaseTime(value: string | null | undefined) {
  if (!value) return "";
  return formatDateTimeInBeijing(value, "zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }) || value;
}

function formatChannelLabel(channel: string | null | undefined, t: (key: string) => string) {
  switch ((channel || "stable").toLowerCase()) {
    case "dev":
      return t("dashboard.updateChannelDev");
    case "stable":
      return t("dashboard.updateChannelStable");
    default:
      return channel || t("dashboard.updateChannelStable");
  }
}

export function SystemUpdateNotice() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [lastStatus, setLastStatus] = useState<SystemUpdateStatusRead | null>(() => readCachedUpdateStatus());
  const [upgradeHandoffNotice, setUpgradeHandoffNotice] = useState(false);
  const [reconnectDelay, setReconnectDelay] = useState(3000);
  const [reloadScheduled, setReloadScheduled] = useState(false);
  const lastAutoCheckRequestedAtRef = useRef(0);

  const { data: statusResponse, isError, refetch } = useUpdateStatusApiV1AdminSystemUpdatesStatusGet({
    query: {
      refetchInterval: 30 * 1000,
      refetchOnMount: "always",
      refetchOnReconnect: true,
      refetchOnWindowFocus: true,
      retry: false,
      staleTime: 0,
    },
  });

  const responseStatus = statusResponse?.data ?? null;
  const status = resolveUpdateNoticeStatus(responseStatus, lastStatus);
  const operationStatus = responseStatus ?? status;
  const state = status?.state ?? "idle";
  const operationState = operationStatus?.state ?? "idle";
  const operationActive = isActiveState(operationState);
  const reconnecting = Boolean(isError && operationStatus && isActiveState(operationStatus.state));
  const targetVersion = status?.latest_version ?? status?.release?.version ?? "";
  const releaseNotes = status?.release?.notes?.trim() || t("dashboard.updateNoNotes");
  const showReleaseNotes = shouldShowUpdateReleaseNotes(status);
  const canUpgrade = Boolean(
    targetVersion
      && shouldSurfaceUpdateStatus(status)
      && status?.auto_update_supported
      && status?.signature_verified
      && state === "available"
      && !isError
      && !operationActive
  );
  const canCancelQueued = Boolean(operationState === "queued" && operationStatus?.request_id);
  const shouldRender = shouldSurfaceUpdateStatus(status);

  useEffect(() => {
    const nextStatus = statusResponse?.data;
    if (!nextStatus) {
      return;
    }
    if (shouldCacheUpdateStatus(nextStatus)) {
      setLastStatus(nextStatus);
      cacheUpdateStatus(nextStatus);
      return;
    }
    if (shouldClearCachedUpdateStatus(nextStatus)) {
      setLastStatus(null);
      clearCachedUpdateStatus();
    }
  }, [statusResponse]);

  useEffect(() => {
    if (upgradeHandoffNotice && (operationState === "succeeded" || isTerminalAttentionState(operationState))) {
      setUpgradeHandoffNotice(false);
    }
  }, [operationState, upgradeHandoffNotice]);

  useEffect(() => {
    if (!operationStatus || !isActiveState(operationStatus.state) || reconnecting) {
      return;
    }
    const timer = window.setInterval(() => {
      void refetch();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [operationStatus, reconnecting, refetch]);

  useEffect(() => {
    if (!reconnecting) {
      setReconnectDelay(3000);
      return;
    }
    const timer = window.setTimeout(() => {
      void refetch().finally(() => {
        setReconnectDelay((current) => Math.min(Math.round(current * 1.6), 30000));
      });
    }, reconnectDelay);
    return () => window.clearTimeout(timer);
  }, [reconnecting, reconnectDelay, refetch]);

  useEffect(() => {
    if (
      reloadScheduled
      || !operationStatus
      || operationStatus.state !== "succeeded"
      || !operationStatus.latest_version
      || operationStatus.current_version !== operationStatus.latest_version
    ) {
      return;
    }
    setReloadScheduled(true);
    const timer = window.setTimeout(() => {
      window.location.reload();
    }, 1800);
    return () => window.clearTimeout(timer);
  }, [operationStatus, reloadScheduled]);

  const refreshStatus = useCallback(() => {
    void refetch();
  }, [refetch]);

  const checkMutation = useCheckUpdatesApiV1AdminSystemUpdatesCheckPost({
    mutation: {
      onSuccess: () => {
        toast.success(t("dashboard.updateCheckQueued"));
        refreshStatus();
      },
      onError: (error) => {
        toast.error(extractApiErrorMessage(error, t("dashboard.updateCheckFailed")));
      },
    },
  });

  const autoCheckMutation = useCheckUpdatesApiV1AdminSystemUpdatesCheckPost({
    mutation: {
      onSuccess: refreshStatus,
    },
  });

  const upgradeMutation = useUpgradeSystemApiV1AdminSystemUpdatesUpgradePost({
    mutation: {
      onSuccess: () => {
        setUpgradeHandoffNotice(true);
        setOpen(true);
        toast.success(t("dashboard.updateUpgradeQueued"));
        refreshStatus();
      },
      onError: (error) => {
        toast.error(extractApiErrorMessage(error, t("dashboard.updateUpgradeFailed")));
      },
    },
  });

  const cancelMutation = useCancelQueuedUpdateRequestApiV1AdminSystemUpdatesRequestsRequestIdDelete({
    mutation: {
      onSuccess: () => {
        toast.success(t("dashboard.updateCancelQueuedDone"));
        refreshStatus();
      },
      onError: (error) => {
        toast.error(extractApiErrorMessage(error, t("dashboard.updateCancelQueuedFailed")));
      },
    },
  });

  useEffect(() => {
    const now = Date.now();
    if (!shouldQueueSilentUpdateCheck({
      autoCheckPending: autoCheckMutation.isPending,
      isError,
      isStateActive: operationActive,
      lastAutoCheckRequestedAt: lastAutoCheckRequestedAtRef.current,
      now,
      state: operationState,
      status: operationStatus,
    })) {
      return;
    }

    lastAutoCheckRequestedAtRef.current = now;
    autoCheckMutation.mutate({ data: { force: false } });
  }, [autoCheckMutation, isError, operationActive, operationState, operationStatus]);

  const noticeCopy = useMemo(() => {
    return {
      icon: Download,
      label: t("dashboard.updateNewVersion", { version: targetVersion }),
      tone: "blue",
    };
  }, [t, targetVersion]);

  const statusHint = useMemo(() => {
    if (reconnecting) return t("dashboard.updateReconnectHint");
    if (operationState === "preflight") return t("dashboard.updatePreflightHint");
    if (operationState === "running" || operationState === "restarting") return t("dashboard.updateRunningHint");
    if (operationState === "succeeded") return t("dashboard.updateSucceededHint");
    if (operationState === "failed") return operationStatus?.last_error || t("dashboard.updateFailedHint");
    if (operationState === "rolled_back") return operationStatus?.last_error || t("dashboard.updateRolledBackHint");
    return "";
  }, [operationState, operationStatus, reconnecting, t]);

  const startCheck = () => {
    checkMutation.mutate({ data: { force: true } });
  };

  const startUpgrade = () => {
    if (!targetVersion) return;
    upgradeMutation.mutate({
      data: {
        target_version: targetVersion,
        confirm_version: targetVersion,
      },
    });
  };

  const cancelQueued = () => {
    if (!operationStatus?.request_id) return;
    cancelMutation.mutate({ requestId: operationStatus.request_id });
  };

  if (!shouldRender || !status) {
    return null;
  }

  const NoticeIcon = noticeCopy.icon;
  const compactRestartDialog =
    upgradeHandoffNotice || reconnecting || operationState === "running" || operationState === "restarting";

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "admin-transition-fast inline-flex h-10 max-w-full items-center gap-2 rounded-full border px-3.5 text-sm font-semibold shadow-[var(--admin-shadow-sm)] transition-[background-color,border-color,color,box-shadow,transform] hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          noticeCopy.tone === "red" && "border-red-200/80 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200",
          noticeCopy.tone === "amber" && "border-amber-200/80 bg-amber-50 text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100",
          noticeCopy.tone === "green" && "border-emerald-200/80 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-100",
          noticeCopy.tone === "blue"
            && "border-cyan-400/75 bg-[linear-gradient(135deg,rgb(14_165_233/0.34),rgb(45_212_191/0.28)_58%,rgb(var(--admin-surface-1)/0.88))] text-sky-950 shadow-[0_16px_38px_-20px_rgb(14_165_233/1),0_0_0_1px_rgb(255_255_255/0.68)_inset] hover:border-cyan-500/85 hover:bg-[linear-gradient(135deg,rgb(14_165_233/0.42),rgb(45_212_191/0.34)_58%,rgb(var(--admin-surface-1)/0.95))] dark:border-cyan-300/55 dark:bg-[linear-gradient(135deg,rgb(14_165_233/0.34),rgb(45_212_191/0.26)_58%,rgb(255_255_255/0.08))] dark:text-cyan-50 dark:shadow-[0_18px_40px_-22px_rgb(34_211_238/0.95),0_0_0_1px_rgb(255_255_255/0.1)_inset] dark:hover:border-cyan-200/75",
          noticeCopy.tone === "neutral" && "border-border/60 bg-[rgb(var(--admin-surface-1)/0.7)] text-foreground",
        )}
      >
        <NoticeIcon className="h-4 w-4 shrink-0" />
        <span className="truncate">{noticeCopy.label}</span>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        {compactRestartDialog ? (
          <DialogContent className="max-w-sm overflow-hidden rounded-[var(--admin-radius-lg)] p-0">
            <div className="space-y-5 px-6 py-7">
              <DialogHeader className="items-center space-y-4 pr-0 text-center">
                <div className="flex h-12 w-12 items-center justify-center rounded-full border border-cyan-300/55 bg-[linear-gradient(135deg,rgb(14_165_233/0.2),rgb(45_212_191/0.16))] text-cyan-950 shadow-[0_16px_34px_-24px_rgb(14_165_233/0.95),0_0_0_1px_rgb(255_255_255/0.55)_inset] dark:border-cyan-300/40 dark:text-cyan-50">
                  <NoticeIcon className={cn("h-5 w-5", operationActive && "animate-spin")} />
                </div>
                <div className="space-y-4">
                  <DialogTitle className="text-center">{t("dashboard.updateInterruptingTitle")}</DialogTitle>
                  <DialogDescription className="space-y-1 text-center text-sm leading-6">
                    <span className="block">{t("dashboard.updateInterruptingLine1")}</span>
                    <span className="block">{t("dashboard.updateInterruptingLine2")}</span>
                  </DialogDescription>
                </div>
              </DialogHeader>
            </div>
          </DialogContent>
        ) : (
          <DialogContent className="max-h-[min(88vh,760px)] max-w-2xl overflow-hidden rounded-[var(--admin-radius-lg)] p-0">
          <div className="flex max-h-[min(88vh,760px)] flex-col">
            <div className="border-b border-border/60 px-5 py-5 sm:px-6">
              <DialogHeader className="space-y-2 pr-8 text-left">
                <DialogTitle className="flex items-center gap-2 text-lg">
                  <NoticeIcon className="h-5 w-5" />
                  {t("dashboard.updateDialogTitle")}
                </DialogTitle>
                <DialogDescription className={cn(!statusHint && "sr-only")}>
                  {statusHint || t("dashboard.updateNewVersion", { version: targetVersion })}
                </DialogDescription>
              </DialogHeader>
            </div>

            <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-5 py-5 sm:px-6">
              <div className="grid gap-3 text-sm sm:grid-cols-2">
                <div>
                  <p className="text-xs text-muted-foreground">{t("dashboard.updateCurrentVersion")}</p>
                  <p className="mt-1 font-medium tabular-nums">{status.current_version}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{t("dashboard.updateTargetVersion")}</p>
                  <p className="mt-1 font-medium tabular-nums">{targetVersion || "-"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{t("dashboard.updateReleasedAt")}</p>
                  <p className="mt-1 font-medium">{formatReleaseTime(status.release?.released_at) || "-"}</p>
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">{t("dashboard.updateChannel")}</p>
                  <p className="mt-1 font-medium">{formatChannelLabel(status.channel, t)}</p>
                </div>
              </div>

              <div
                className={cn(
                  "flex items-start gap-3 rounded-[var(--admin-radius-md)] border px-3 py-3 text-sm",
                  status.signature_verified
                    ? "border-emerald-200/70 bg-emerald-50/70 text-emerald-900 dark:border-emerald-500/25 dark:bg-emerald-500/10 dark:text-emerald-100"
                    : "border-amber-200/70 bg-amber-50/70 text-amber-950 dark:border-amber-500/25 dark:bg-amber-500/10 dark:text-amber-100",
                )}
              >
                {status.signature_verified ? (
                  <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                ) : (
                  <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
                )}
                <div className="min-w-0">
                  <p className="font-medium">
                    {status.signature_verified ? t("dashboard.updateSignatureTrusted") : t("dashboard.updateSignatureBlocked")}
                  </p>
                  {!status.auto_update_supported && status.auto_update_blocked_reason ? (
                    <p className="mt-1 leading-5 text-current/80">{status.auto_update_blocked_reason}</p>
                  ) : null}
                </div>
              </div>

              {status.last_error ? (
                <div className="flex items-start gap-3 rounded-[var(--admin-radius-md)] border border-red-200/70 bg-red-50/70 px-3 py-3 text-sm text-red-900 dark:border-red-500/25 dark:bg-red-500/10 dark:text-red-100">
                  <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                  <p className="leading-5">{status.last_error}</p>
                </div>
              ) : null}

              {showReleaseNotes ? (
                <section className="space-y-2">
                  <h3 className="text-sm font-semibold text-foreground/90">{t("dashboard.updateNotes")}</h3>
                  <div className="max-h-[280px] min-w-0 overflow-y-auto rounded-[var(--admin-radius-md)] border border-border/60 bg-[rgb(var(--admin-surface-1)/0.48)] px-3 py-3">
                    <MarkdownPreview
                      content={releaseNotes}
                      className="text-sm leading-6 break-words [&_*]:max-w-full [&_:first-child]:mt-0 [&_:last-child]:mb-0 [&_a]:break-all [&_code]:break-all [&_p]:my-0 [&_p]:leading-6"
                    />
                  </div>
                </section>
              ) : null}

              {status.recent_log?.length ? (
                <details className="group rounded-[var(--admin-radius-md)] border border-border/60 bg-[rgb(var(--admin-surface-1)/0.36)]">
                  <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-2.5 text-sm font-semibold text-foreground/90 [&::-webkit-details-marker]:hidden">
                    <span>{t("dashboard.updateRecentLog")}</span>
                    <ChevronDown className="h-4 w-4 text-muted-foreground transition-transform group-open:rotate-180" />
                  </summary>
                  <pre className="max-h-64 min-w-0 overflow-y-auto whitespace-pre-wrap break-all border-t border-border/60 bg-black/[0.035] p-3 text-xs leading-5 text-muted-foreground [scrollbar-width:none] dark:bg-white/[0.04] [&::-webkit-scrollbar]:hidden">
                    {status.recent_log.slice(-12).join("\n")}
                  </pre>
                </details>
              ) : null}
            </div>

            <div className="flex flex-col gap-2 border-t border-border/60 px-5 py-4 sm:flex-row sm:items-center sm:justify-between sm:px-6">
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={startCheck}
                disabled={checkMutation.isPending || operationActive}
                className="gap-2"
              >
                <RefreshCw className={cn("h-4 w-4", checkMutation.isPending && "animate-spin")} />
                {t("dashboard.updateCheck")}
              </Button>
              <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
                {canCancelQueued ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={cancelQueued}
                    disabled={cancelMutation.isPending}
                  >
                    {cancelMutation.isPending ? t("dashboard.updateCanceling") : t("dashboard.updateCancelQueued")}
                  </Button>
                ) : null}
                <Button type="button" variant="ghost" size="sm" onClick={() => setOpen(false)}>
                  {t("common.cancel")}
                </Button>
                <Button
                  type="button"
                  size="sm"
                  onClick={startUpgrade}
                  disabled={!canUpgrade || upgradeMutation.isPending}
                  className="gap-2"
                >
                  <Download className="h-4 w-4" />
                  {upgradeMutation.isPending ? t("dashboard.updateStarting") : t("dashboard.updateStart")}
                </Button>
              </div>
            </div>
          </div>
          </DialogContent>
        )}
      </Dialog>
    </>
  );
}
