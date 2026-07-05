import { useCallback, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  Download,
  Loader2,
  RefreshCw,
  RotateCcw,
  ShieldAlert,
  WifiOff,
  XCircle,
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

type UpdateState = NonNullable<SystemUpdateStatusRead["state"]>;

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
  return state === "succeeded" || state === "failed" || state === "rolled_back";
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

export function SystemUpdateNotice() {
  const { t } = useI18n();
  const [open, setOpen] = useState(false);
  const [lastStatus, setLastStatus] = useState<SystemUpdateStatusRead | null>(null);
  const [reconnectDelay, setReconnectDelay] = useState(3000);
  const [reloadScheduled, setReloadScheduled] = useState(false);

  const { data: statusResponse, isError, refetch } = useUpdateStatusApiV1AdminSystemUpdatesStatusGet({
    query: {
      refetchInterval: 10 * 60 * 1000,
      retry: false,
    },
  });

  const status = statusResponse?.data ?? lastStatus;
  const state = status?.state ?? "idle";
  const reconnecting = Boolean(isError && status && isActiveState(status.state));
  const targetVersion = status?.latest_version ?? status?.release?.version ?? "";
  const releaseNotes = status?.release?.notes?.trim() || t("dashboard.updateNoNotes");
  const showReleaseNotes = Boolean(status?.auto_update_supported);
  const canUpgrade = Boolean(
    targetVersion
      && status?.update_available
      && status?.auto_update_supported
      && status?.signature_verified
      && state === "available"
      && !isError,
  );
  const canCancelQueued = Boolean(state === "queued" && status?.request_id);
  const shouldRender = Boolean(
    status
      && (
        status.update_available
        || isActiveState(state)
        || (isTerminalAttentionState(state) && Boolean(status.latest_version))
      ),
  );

  useEffect(() => {
    if (statusResponse?.data) {
      setLastStatus(statusResponse.data);
    }
  }, [statusResponse]);

  useEffect(() => {
    if (!status || !isActiveState(status.state) || reconnecting) {
      return;
    }
    const timer = window.setInterval(() => {
      void refetch();
    }, 3000);
    return () => window.clearInterval(timer);
  }, [reconnecting, refetch, status]);

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
      || !status
      || status.state !== "succeeded"
      || !status.latest_version
      || status.current_version !== status.latest_version
    ) {
      return;
    }
    setReloadScheduled(true);
    const timer = window.setTimeout(() => {
      window.location.reload();
    }, 1800);
    return () => window.clearTimeout(timer);
  }, [reloadScheduled, status]);

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

  const upgradeMutation = useUpgradeSystemApiV1AdminSystemUpdatesUpgradePost({
    mutation: {
      onSuccess: () => {
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

  const noticeCopy = useMemo(() => {
    if (reconnecting) {
      return {
        icon: WifiOff,
        label: t("dashboard.updateServiceRestarting"),
        tone: "amber",
      };
    }
    switch (state) {
      case "checking":
        return { icon: RefreshCw, label: t("dashboard.updateChecking"), tone: "neutral" };
      case "queued":
      case "preflight":
        return { icon: Loader2, label: t("dashboard.updateQueued"), tone: "blue" };
      case "running":
      case "restarting":
        return { icon: Loader2, label: t("dashboard.updateRunning"), tone: "blue" };
      case "succeeded":
        return { icon: CheckCircle2, label: t("dashboard.updateSucceeded"), tone: "green" };
      case "failed":
        return { icon: XCircle, label: t("dashboard.updateFailed"), tone: "red" };
      case "rolled_back":
        return { icon: RotateCcw, label: t("dashboard.updateRolledBack"), tone: "amber" };
      default:
        return {
          icon: Download,
          label: t("dashboard.updateNewVersion", { version: targetVersion }),
          tone: "blue",
        };
    }
  }, [reconnecting, state, t, targetVersion]);

  const statusHint = useMemo(() => {
    if (reconnecting) return t("dashboard.updateReconnectHint");
    if (state === "preflight") return t("dashboard.updatePreflightHint");
    if (state === "running" || state === "restarting") return t("dashboard.updateRunningHint");
    if (state === "succeeded") return t("dashboard.updateSucceededHint");
    if (state === "failed") return status?.last_error || t("dashboard.updateFailedHint");
    if (state === "rolled_back") return status?.last_error || t("dashboard.updateRolledBackHint");
    if (state === "available" && status?.auto_update_supported) return t("dashboard.updateAvailableHint");
    return "";
  }, [reconnecting, state, status, t]);

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
    if (!status?.request_id) return;
    cancelMutation.mutate({ requestId: status.request_id });
  };

  if (!shouldRender || !status) {
    return null;
  }

  const NoticeIcon = noticeCopy.icon;

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "admin-transition-fast inline-flex h-10 max-w-full items-center gap-2 rounded-full border px-3 text-sm font-medium shadow-[var(--admin-shadow-sm)] transition-[background-color,border-color,color,box-shadow,transform] hover:-translate-y-0.5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
          noticeCopy.tone === "red" && "border-red-200/80 bg-red-50 text-red-700 dark:border-red-500/30 dark:bg-red-500/10 dark:text-red-200",
          noticeCopy.tone === "amber" && "border-amber-200/80 bg-amber-50 text-amber-800 dark:border-amber-500/30 dark:bg-amber-500/10 dark:text-amber-100",
          noticeCopy.tone === "green" && "border-emerald-200/80 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-500/10 dark:text-emerald-100",
          noticeCopy.tone === "blue" && "border-sky-200/80 bg-sky-50 text-sky-700 dark:border-sky-500/30 dark:bg-sky-500/10 dark:text-sky-100",
          noticeCopy.tone === "neutral" && "border-border/60 bg-[rgb(var(--admin-surface-1)/0.7)] text-foreground",
        )}
      >
        <NoticeIcon className={cn("h-4 w-4 shrink-0", isActiveState(state) && "animate-spin")} />
        <span className="truncate">{noticeCopy.label}</span>
      </button>

      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[min(88vh,760px)] max-w-2xl overflow-hidden rounded-[var(--admin-radius-lg)] p-0">
          <div className="flex max-h-[min(88vh,760px)] flex-col">
            <div className="border-b border-border/60 px-5 py-5 sm:px-6">
              <DialogHeader className="space-y-2 pr-8 text-left">
                <DialogTitle className="flex items-center gap-2 text-lg">
                  <NoticeIcon className={cn("h-5 w-5", isActiveState(state) && "animate-spin")} />
                  {t("dashboard.updateDialogTitle")}
                </DialogTitle>
                {statusHint ? <DialogDescription>{statusHint}</DialogDescription> : null}
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
                  <p className="mt-1 font-medium">{status.channel || "stable"}</p>
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
                  <pre className="max-h-32 min-w-0 overflow-y-auto whitespace-pre-wrap break-all border-t border-border/60 bg-black/[0.035] p-3 text-xs leading-5 text-muted-foreground dark:bg-white/[0.04]">
                    {status.recent_log.slice(-5).join("\n")}
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
                disabled={checkMutation.isPending || isActiveState(state)}
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
      </Dialog>
    </>
  );
}
