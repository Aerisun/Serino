import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  getGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGetQueryKey,
  getListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGetQueryKey,
  getListBackupSyncQueueApiV1AdminSystemBackupSyncQueueGetQueryKey,
  getListBackupSyncRunsApiV1AdminSystemBackupSyncRunsGetQueryKey,
  useGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGet,
  useListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGet,
  useListBackupSyncQueueApiV1AdminSystemBackupSyncQueueGet,
  useListBackupSyncRunsApiV1AdminSystemBackupSyncRunsGet,
  usePauseBackupSyncApiV1AdminSystemBackupSyncPausePost,
  useRestoreBackupCommitApiV1AdminSystemBackupSyncCommitsCommitIdRestorePost,
  useResumeBackupSyncApiV1AdminSystemBackupSyncResumePost,
  useTriggerBackupSyncApiV1AdminSystemBackupSyncRunsPost,
  useUpdateBackupSyncConfigApiV1AdminSystemBackupSyncConfigPut,
} from "@serino/api-client/admin";
import type {
  BackupCommitRead,
  BackupRunRead,
  BackupSyncConfig,
  BackupSyncConfigUpdate,
} from "@serino/api-client/models";
import {
  acknowledgeBackupRecoveryKey,
  createBackupBootstrapClaim,
  ensureBackupCredentials,
  exportBackupRecoveryKey,
  getBackupBootstrapClaim,
  overwriteRemoteBackupHistory,
  previewRemoteBackupHistoryImport,
  probeBackupMachineConnection,
  revokeBackupBootstrapClaim,
  resetBackupSyncSystem,
  restoreRemoteBackupHistory,
  testBackupSyncConfig,
  type BackupBootstrapClaimRead,
  type BackupCredentialEnsureRead,
  type BackupRemoteHistoryCommitRead,
  type BackupRemoteHistoryImportPreviewRead,
  type BackupSyncConfigTestResult,
} from "@/pages/system/api";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { NativeSelect } from "@/components/ui/NativeSelect";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import { Textarea } from "@/components/ui/Textarea";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { cn, formatDate } from "@/lib/utils";
import {
  AlertTriangle,
  Copy,
  Database,
  Clock,
  KeyRound,
  Loader2,
  PauseCircle,
  PlayCircle,
  RefreshCcw,
  RotateCcw,
  Save,
  ShieldCheck,
  SearchCheck,
  TerminalSquare,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

type BackupsSection = "settings" | "records";
type BackupRecordsSection = "commits" | "runs";

const DEFAULT_BACKUP_REMOTE_USERNAME = "serino-backup";
const DEFAULT_BACKUP_REMOTE_PATH = "/srv/serino-backups";
const DEFAULT_BACKUP_CREDENTIAL_REF = "aerisun-backup-source";
const DEFAULT_BACKUP_SITE_SLUG = "aerisun";
const DEFAULT_BACKUP_CREDENTIAL_DIR = `.store/secrets/backup-sync/${DEFAULT_BACKUP_CREDENTIAL_REF}`;
const DEFAULT_BACKUP_INTERVAL_MINUTES = 1440;
const DEFAULT_BACKUP_MAX_RETENTION_COUNT = 80;
const DEFAULT_BACKUP_RETENTION_DAYS = 60;
const BACKUP_BOOTSTRAP_TTL_MINUTES = 10;
const REMOTE_CLEANUP_COMMAND =
  "sudo bash -c 'set -euo pipefail\nuserdel -r serino-backup >/dev/null 2>&1 || true\nrm -rf /srv/serino-backups\necho \"Serino backup user and backup data have been removed.\"'";
const RUNTIME_RESTORE_INTERRUPTED_ERROR =
  "Backup run was interrupted by a runtime restore";

function isRuntimeRestoreInterruption(value: string | null | undefined) {
  return value === RUNTIME_RESTORE_INTERRUPTED_ERROR;
}

function getVisibleRunMessage(row: BackupRunRead, fallback: string) {
  const message = isRuntimeRestoreInterruption(row.message) ? null : row.message;
  const lastError = isRuntimeRestoreInterruption(row.last_error)
    ? null
    : row.last_error;
  return message || lastError || fallback;
}

async function copyTextToClipboard(value: string) {
  if (navigator.clipboard?.writeText) {
    try {
      await navigator.clipboard.writeText(value);
      return;
    } catch {
      // HTTP admin pages on LAN IPs are not secure contexts, so Clipboard API can be blocked.
    }
  }

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.top = "0";
  textarea.style.left = "-9999px";
  textarea.style.opacity = "0";
  document.body.appendChild(textarea);
  textarea.focus();
  textarea.select();
  try {
    if (!document.execCommand("copy")) {
      throw new Error("Copy command was rejected");
    }
  } finally {
    textarea.remove();
  }
}

const emptyForm: BackupSyncConfigUpdate = {
  enabled: true,
  paused: false,
  interval_minutes: DEFAULT_BACKUP_INTERVAL_MINUTES,
  transport_mode: "sftp",
  site_slug: DEFAULT_BACKUP_SITE_SLUG,
  remote_host: "",
  remote_port: 22,
  remote_path: DEFAULT_BACKUP_REMOTE_PATH,
  remote_username: DEFAULT_BACKUP_REMOTE_USERNAME,
  credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
  encrypt_runtime_data: true,
  max_retries: 3,
  retry_backoff_seconds: 300,
  max_retention_count: DEFAULT_BACKUP_MAX_RETENTION_COUNT,
  retention_days: DEFAULT_BACKUP_RETENTION_DAYS,
};

export default function BackupsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [form, setForm] = useState<BackupSyncConfigUpdate>(emptyForm);
  const [section, setSection] = useState<BackupsSection>(() =>
    searchParams.get("section") === "records" ? "records" : "settings",
  );
  const [recordsSection, setRecordsSection] =
    useState<BackupRecordsSection>(() =>
      searchParams.get("records") === "runs" ? "runs" : "commits",
    );
  const [credentialInfo, setCredentialInfo] =
    useState<BackupCredentialEnsureRead | null>(null);
  const [isEnsuringCredential, setIsEnsuringCredential] = useState(false);
  const [keyDialogOpen, setKeyDialogOpen] = useState(false);
  const [keyDialogMode, setKeyDialogMode] = useState<"export" | "rotate">(
    "export",
  );
  const [recoveryPassphrase, setRecoveryPassphrase] = useState("");
  const [recoveryPassphraseConfirm, setRecoveryPassphraseConfirm] =
    useState("");
  const [isRecoveryKeyPending, setIsRecoveryKeyPending] = useState(false);
  const [recoveryKeyDelivered, setRecoveryKeyDelivered] = useState(false);
  const [configTestResult, setConfigTestResult] =
    useState<BackupSyncConfigTestResult | null>(null);
  const [configTestMode, setConfigTestMode] = useState<"probe" | "full" | null>(
    null,
  );
  const [hasInitializedForm, setHasInitializedForm] = useState(false);
  const [bootstrapClaim, setBootstrapClaim] =
    useState<BackupBootstrapClaimRead | null>(null);
  const [bootstrapSecondsLeft, setBootstrapSecondsLeft] = useState(0);
  const [forgotDialogOpen, setForgotDialogOpen] = useState(false);
  const [resetCommand, setResetCommand] = useState(REMOTE_CLEANUP_COMMAND);
  const [remoteImportDialogOpen, setRemoteImportDialogOpen] = useState(false);
  const [remoteImportPassphrase, setRemoteImportPassphrase] = useState("");
  const [remoteImportPreview, setRemoteImportPreview] =
    useState<BackupRemoteHistoryImportPreviewRead | null>(null);
  const [selectedRemoteCommitId, setSelectedRemoteCommitId] = useState("");
  const [restoreConfirmCommit, setRestoreConfirmCommit] =
    useState<BackupCommitRead | null>(null);
  const [remoteHistoryOverwriteAccepted, setRemoteHistoryOverwriteAccepted] =
    useState(false);

  const { data: configRaw, isLoading: isConfigLoading } =
    useGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGet();
  useListBackupSyncQueueApiV1AdminSystemBackupSyncQueueGet();
  const { data: runsRaw, isLoading: isRunsLoading } =
    useListBackupSyncRunsApiV1AdminSystemBackupSyncRunsGet();
  const { data: commitsRaw, isLoading: isCommitsLoading } =
    useListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGet();

  const config = configRaw?.data as
    | (BackupSyncConfig & {
        recovery_key_ready?: boolean;
        recovery_key_acknowledged?: boolean;
        active_recovery_key_fingerprint?: string | null;
        archived_recovery_key_count?: number;
      })
    | undefined;
  const runs = (runsRaw?.data as BackupRunRead[] | undefined) ?? [];
  const commits = (commitsRaw?.data as BackupCommitRead[] | undefined) ?? [];

  useEffect(() => {
    const nextSection = searchParams.get("section") === "records" ? "records" : "settings";
    const nextRecordsSection = searchParams.get("records") === "runs" ? "runs" : "commits";
    setSection((current) => (current === nextSection ? current : nextSection));
    setRecordsSection((current) =>
      current === nextRecordsSection ? current : nextRecordsSection,
    );
  }, [searchParams]);

  const handleSectionChange = (value: BackupsSection) => {
    setSection(value);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      if (value === "records") {
        next.set("section", "records");
      } else {
        next.delete("section");
        next.delete("records");
      }
      return next;
    }, { replace: true });
  };

  const handleRecordsSectionChange = (value: BackupRecordsSection) => {
    setRecordsSection(value);
    setSearchParams((current) => {
      const next = new URLSearchParams(current);
      next.set("section", "records");
      if (value === "runs") {
        next.set("records", "runs");
      } else {
        next.delete("records");
      }
      return next;
    }, { replace: true });
  };

  const invalidateAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey:
          getGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGetQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey:
          getListBackupSyncQueueApiV1AdminSystemBackupSyncQueueGetQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey:
          getListBackupSyncRunsApiV1AdminSystemBackupSyncRunsGetQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey:
          getListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGetQueryKey(),
      }),
    ]);
  };

  const clearBackupHistoryCache = () => {
    const clearDataList = (queryKey: readonly unknown[]) => {
      queryClient.setQueryData(queryKey, (current: unknown) => {
        if (current && typeof current === "object" && "data" in current) {
          return { ...current, data: [] };
        }
        return { data: [] };
      });
    };
    clearDataList(getListBackupSyncQueueApiV1AdminSystemBackupSyncQueueGetQueryKey());
    clearDataList(getListBackupSyncRunsApiV1AdminSystemBackupSyncRunsGetQueryKey());
    clearDataList(getListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGetQueryKey());
  };

  useEffect(() => {
    if (!config) {
      return;
    }
    if (config.recovery_key_ready) {
      setCredentialInfo(
        (current) =>
          current ?? {
            credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
            site_slug: DEFAULT_BACKUP_SITE_SLUG,
            credential_dir: DEFAULT_BACKUP_CREDENTIAL_DIR,
            secrets_fingerprint: config.active_recovery_key_fingerprint ?? "",
            created: false,
            archived_fingerprints: [],
          },
      );
    }
    if (hasInitializedForm) {
      return;
    }
    setForm({
      enabled: true,
      paused: config.paused ?? false,
      interval_minutes: config.interval_minutes ?? DEFAULT_BACKUP_INTERVAL_MINUTES,
      transport_mode: config.transport_mode ?? "sftp",
      site_slug: DEFAULT_BACKUP_SITE_SLUG,
      remote_host: config.transport.remote_host ?? "",
      remote_port: config.transport.remote_port ?? 22,
      remote_path: DEFAULT_BACKUP_REMOTE_PATH,
      remote_username: DEFAULT_BACKUP_REMOTE_USERNAME,
      credential_ref: config.credential_ref ?? DEFAULT_BACKUP_CREDENTIAL_REF,
      encrypt_runtime_data: config.encrypt_runtime_data ?? true,
      max_retries: config.max_retries ?? 3,
      retry_backoff_seconds: config.retry_backoff_seconds ?? 300,
      max_retention_count: config.max_retention_count ?? DEFAULT_BACKUP_MAX_RETENTION_COUNT,
      retention_days: config.retention_days ?? DEFAULT_BACKUP_RETENTION_DAYS,
    });
    setHasInitializedForm(true);
  }, [config, hasInitializedForm]);

  const updateConfig =
    useUpdateBackupSyncConfigApiV1AdminSystemBackupSyncConfigPut({
      mutation: {
        onSuccess: async () => {
          toast.success(t("common.operationSuccess"));
          await invalidateAll();
        },
        onError: (error: any) => {
          toast.error(
            extractApiErrorMessage(error, t("common.operationFailed")),
          );
        },
      },
    });

  const triggerSync = useTriggerBackupSyncApiV1AdminSystemBackupSyncRunsPost({
    mutation: {
      onSuccess: async () => {
        toast.success(t("system.backupSyncTriggered"));
        await invalidateAll();
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const pauseSync = usePauseBackupSyncApiV1AdminSystemBackupSyncPausePost({
    mutation: {
      onSuccess: async () => {
        toast.success(t("system.backupSyncPaused"));
        await invalidateAll();
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const resumeSync = useResumeBackupSyncApiV1AdminSystemBackupSyncResumePost({
    mutation: {
      onSuccess: async () => {
        toast.success(t("system.backupSyncResumed"));
        await invalidateAll();
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const restoreCommit =
    useRestoreBackupCommitApiV1AdminSystemBackupSyncCommitsCommitIdRestorePost({
      mutation: {
        onSuccess: async () => {
          toast.success(t("common.operationSuccess"));
          await invalidateAll();
        },
        onError: (error: any) => {
          toast.error(
            extractApiErrorMessage(error, t("common.operationFailed")),
          );
        },
      },
    });

  const normalizeBackupConfigPayload = (
    payload: BackupSyncConfigUpdate,
  ): BackupSyncConfigUpdate => ({
    enabled: true,
    paused: false,
    interval_minutes: payload.interval_minutes ?? DEFAULT_BACKUP_INTERVAL_MINUTES,
    transport_mode: "sftp",
    site_slug: DEFAULT_BACKUP_SITE_SLUG,
    remote_host: payload.remote_host ?? "",
    remote_port: payload.remote_port ?? 22,
    remote_path: DEFAULT_BACKUP_REMOTE_PATH,
    remote_username: DEFAULT_BACKUP_REMOTE_USERNAME,
    credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
    encrypt_runtime_data: Boolean(payload.encrypt_runtime_data),
    max_retries: payload.max_retries ?? 3,
    retry_backoff_seconds: payload.retry_backoff_seconds ?? 300,
    max_retention_count: payload.max_retention_count ?? DEFAULT_BACKUP_MAX_RETENTION_COUNT,
    retention_days: payload.retention_days ?? DEFAULT_BACKUP_RETENTION_DAYS,
  });

  const probeConnectionMutation = useMutation({
    mutationFn: async (payload: BackupSyncConfigUpdate) =>
      probeBackupMachineConnection(normalizeBackupConfigPayload(payload)),
    onSuccess: (result) => {
      setConfigTestResult(result);
      setConfigTestMode("probe");
      if (result.remote_history_state !== "foreign") {
        setRemoteHistoryOverwriteAccepted(false);
      }
      toast.success(
        result.ok
          ? t("system.backupProbeSuccess")
          : t("system.backupProbeFailed"),
      );
    },
    onError: (error: any) => {
      setConfigTestResult(null);
      setConfigTestMode(null);
      setRemoteHistoryOverwriteAccepted(false);
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    },
  });

  const testConfigMutation = useMutation({
    mutationFn: async (payload: BackupSyncConfigUpdate) =>
      testBackupSyncConfig(normalizeBackupConfigPayload(payload)),
    onSuccess: (result) => {
      setConfigTestResult(result);
      setConfigTestMode("full");
      if (result.remote_history_state !== "foreign") {
        setRemoteHistoryOverwriteAccepted(false);
      }
      toast.success(
        result.ok
          ? t("system.backupConfigTestSuccess")
          : t("system.backupConfigTestFailed"),
      );
    },
    onError: (error: any) => {
      setConfigTestResult(null);
      setConfigTestMode(null);
      setRemoteHistoryOverwriteAccepted(false);
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    },
  });

  const overwriteRemoteHistoryMutation = useMutation({
    mutationFn: async (payload: BackupSyncConfigUpdate) =>
      overwriteRemoteBackupHistory(normalizeBackupConfigPayload(payload)),
    onSuccess: (result) => {
      setConfigTestResult(result);
      setConfigTestMode("full");
      setRemoteHistoryOverwriteAccepted(false);
      clearBackupHistoryCache();
      toast.success(t("system.backupOverwriteHistoryDone"));
    },
    onError: (error: any) => {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    },
  });

  const createBootstrapClaimMutation = useMutation({
    mutationFn: createBackupBootstrapClaim,
    onSuccess: (claim) => {
      setBootstrapClaim(claim);
      setForm((current) => ({
        ...current,
        remote_host: claim.remote_host,
        remote_port: claim.remote_port,
        remote_path: claim.remote_path,
        remote_username: claim.remote_username,
        credential_ref: claim.credential_ref,
        site_slug: claim.site_slug,
      }));
      toast.success(t("system.backupBootstrapCommandReady"));
    },
    onError: (error: any) => {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    },
  });

  const revokeBootstrapClaimMutation = useMutation({
    mutationFn: revokeBackupBootstrapClaim,
    onSuccess: (claim) => {
      setBootstrapClaim((current) => ({
        ...claim,
        setup_command: current?.setup_command ?? claim.setup_command ?? null,
        setup_url: current?.setup_url ?? claim.setup_url ?? null,
      }));
      toast.success(t("system.backupBootstrapRevoked"));
    },
    onError: (error: any) => {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    },
  });

  const remoteHistoryPreviewMutation = useMutation({
    mutationFn: async (passphrase: string) =>
      previewRemoteBackupHistoryImport({
        config: buildConfigPayload(true),
        passphrase,
      }),
    onSuccess: (preview) => {
      setRemoteImportPreview(preview);
      setSelectedRemoteCommitId(preview.commits[0]?.id ?? "");
      toast.success(t("system.backupRemoteHistoryPreviewReady"));
    },
    onError: (error: any) => {
      setRemoteImportPreview(null);
      setSelectedRemoteCommitId("");
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    },
  });

  const remoteHistoryRestoreMutation = useMutation({
    mutationFn: async () =>
      restoreRemoteBackupHistory({
        config: buildConfigPayload(true),
        passphrase: remoteImportPassphrase,
        commit_id: selectedRemoteCommitId,
      }),
    onSuccess: async () => {
      setRemoteImportDialogOpen(false);
      setRemoteImportPassphrase("");
      setRemoteImportPreview(null);
      setSelectedRemoteCommitId("");
      setConfigTestResult(null);
      setConfigTestMode(null);
      toast.success(t("system.backupRemoteHistoryRestored"));
      await invalidateAll();
    },
    onError: (error: any) => {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    },
  });

  const restoreConfirmTime = restoreConfirmCommit
    ? formatDate(
        restoreConfirmCommit.snapshot_finished_at ||
          restoreConfirmCommit.created_at,
      )
    : "-";

  const handleConfirmRestoreCommit = () => {
    if (!restoreConfirmCommit || restoreCommit.isPending) {
      return;
    }
    restoreCommit.mutate({ commitId: restoreConfirmCommit.id });
    setRestoreConfirmCommit(null);
  };

  const latestRun = runs[0];

  const sectionItems = [
    {
      value: "settings",
      label: t("system.backupsTabs.settings"),
      description: t("system.backupsTabs.settingsDescription"),
      icon: ShieldCheck,
    },
    {
      value: "records",
      label: t("system.backupsTabs.records"),
      description: t("system.backupsTabs.recordsDescription"),
      icon: Database,
    },
  ] as const;

  const setField = <K extends keyof BackupSyncConfigUpdate>(
    key: K,
    value: BackupSyncConfigUpdate[K],
  ) => {
    setConfigTestResult(null);
    setConfigTestMode(null);
    setRemoteHistoryOverwriteAccepted(false);
    setForm((current) => ({ ...current, [key]: value }));
  };

  useEffect(() => {
    if (!bootstrapClaim?.expires_at) {
      setBootstrapSecondsLeft(0);
      return;
    }
    const tick = () => {
      const expiresAt = new Date(bootstrapClaim.expires_at).getTime();
      setBootstrapSecondsLeft(
        Math.max(0, Math.floor((expiresAt - Date.now()) / 1000)),
      );
    };
    tick();
    const timer = window.setInterval(tick, 1000);
    return () => window.clearInterval(timer);
  }, [bootstrapClaim?.expires_at]);

  useEffect(() => {
    if (
      !bootstrapClaim ||
      (bootstrapClaim.status !== "pending" &&
        bootstrapClaim.status !== "failed")
    ) {
      return;
    }
    const claimId = bootstrapClaim.id;
    const previousStatus = bootstrapClaim.status;
    const timer = window.setInterval(() => {
      void getBackupBootstrapClaim(claimId)
        .then((nextClaim) => {
          setBootstrapClaim((current) => {
            if (!current || current.id !== claimId) {
              return current;
            }
            return {
              ...nextClaim,
              setup_command:
                current.setup_command ?? nextClaim.setup_command ?? null,
              setup_url: current.setup_url ?? nextClaim.setup_url ?? null,
            };
          });
          if (nextClaim.status === "succeeded") {
            const nextPayload = {
              ...form,
              remote_host: nextClaim.remote_host,
              remote_port: nextClaim.remote_port,
              remote_path: nextClaim.remote_path,
              remote_username: nextClaim.remote_username,
              credential_ref: nextClaim.credential_ref,
              site_slug: nextClaim.site_slug,
            };
            setForm((current) => ({
              ...current,
              remote_host: nextClaim.remote_host,
              remote_port: nextClaim.remote_port,
              remote_path: nextClaim.remote_path,
              remote_username: nextClaim.remote_username,
              credential_ref: nextClaim.credential_ref,
              site_slug: nextClaim.site_slug,
            }));
            if (previousStatus !== "succeeded") {
              toast.success(t("system.backupBootstrapConnected"));
              void testConfigMutation.mutateAsync(nextPayload).catch(() => {
                // Mutation onError renders the user-facing error.
              });
            }
          }
        })
        .catch(() => {
          // The claim poll is best-effort; the visible button can regenerate when needed.
        });
    }, 3000);
    return () => window.clearInterval(timer);
  }, [bootstrapClaim, t]);

  const savedSnapshot = useMemo(
    () => ({
      remote_host: config?.transport.remote_host ?? "",
      remote_username: DEFAULT_BACKUP_REMOTE_USERNAME,
      remote_path: DEFAULT_BACKUP_REMOTE_PATH,
      remote_port: config?.transport.remote_port ?? 22,
      interval_minutes: config?.interval_minutes ?? DEFAULT_BACKUP_INTERVAL_MINUTES,
      encrypt_runtime_data: Boolean(config?.encrypt_runtime_data),
      max_retries: config?.max_retries ?? 3,
      retry_backoff_seconds: config?.retry_backoff_seconds ?? 300,
      max_retention_count: config?.max_retention_count ?? DEFAULT_BACKUP_MAX_RETENTION_COUNT,
      retention_days: config?.retention_days ?? DEFAULT_BACKUP_RETENTION_DAYS,
    }),
    [config],
  );

  const currentSnapshot = useMemo(
    () => ({
      remote_host: form.remote_host ?? "",
      remote_username: DEFAULT_BACKUP_REMOTE_USERNAME,
      remote_path: DEFAULT_BACKUP_REMOTE_PATH,
      remote_port: form.remote_port ?? 22,
      interval_minutes: form.interval_minutes ?? DEFAULT_BACKUP_INTERVAL_MINUTES,
      encrypt_runtime_data: Boolean(form.encrypt_runtime_data),
      max_retries: form.max_retries ?? 3,
      retry_backoff_seconds: form.retry_backoff_seconds ?? 300,
      max_retention_count: form.max_retention_count ?? DEFAULT_BACKUP_MAX_RETENTION_COUNT,
      retention_days: form.retention_days ?? DEFAULT_BACKUP_RETENTION_DAYS,
    }),
    [form],
  );

  const hasConfigChanges =
    JSON.stringify(savedSnapshot) !== JSON.stringify(currentSnapshot);

  const buildConfigPayload = (enabled = true): BackupSyncConfigUpdate => ({
    ...form,
    enabled,
    transport_mode: "sftp",
    remote_path: DEFAULT_BACKUP_REMOTE_PATH,
    remote_username: DEFAULT_BACKUP_REMOTE_USERNAME,
    credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
    site_slug: DEFAULT_BACKUP_SITE_SLUG,
  });

  const resultAllowsRecoveryPassword = (result: BackupSyncConfigTestResult) =>
    Boolean(
      result.ok &&
        (result.remote_history_state === "empty" ||
          result.remote_history_state === "current" ||
          (result.remote_history_state === "foreign" &&
            remoteHistoryOverwriteAccepted)),
    );

  const resultStartsNewRemoteHistory = (result: BackupSyncConfigTestResult) =>
    Boolean(
      (result.ok &&
        result.remote_history_state === "empty" &&
        localBackupHistoryExists) ||
        (result.remote_history_state === "foreign" &&
          remoteHistoryOverwriteAccepted),
    );

  const recoveryPasswordReadyForResult = (result: BackupSyncConfigTestResult) =>
    Boolean(
      canPersistBackupConfig && !resultStartsNewRemoteHistory(result),
    );

  const requireRecoveryPasswordBeforeOperation = (
    result: BackupSyncConfigTestResult,
  ) => {
    if (!resultAllowsRecoveryPassword(result)) {
      return false;
    }
    if (!recoveryPasswordReadyForResult(result)) {
      toast.error(t("system.recoveryKeyRequiredBeforeSave"));
      return false;
    }
    return true;
  };

  const prepareCredential = async (force = false) => {
    setIsEnsuringCredential(true);
    try {
      const info = await ensureBackupCredentials({
        credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
        site_slug: DEFAULT_BACKUP_SITE_SLUG,
        force,
      });
      toast.success(
        info.created
          ? t("system.localKeysGenerated")
          : t("system.localKeysConfirmed"),
      );
      return info;
    } catch (error: any) {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      throw error;
    } finally {
      setIsEnsuringCredential(false);
    }
  };

  const handleSaveAndRun = async () => {
    await prepareCredential();
    if (remoteHistoryIsForeign && remoteHistoryOverwriteAccepted) {
      await overwriteRemoteHistoryMutation.mutateAsync(buildConfigPayload(true));
    } else {
      await updateConfig.mutateAsync({
        data: buildConfigPayload(true),
      });
    }
    await triggerSync.mutateAsync();
    toast.success(t("system.firstBackupStarted"));
  };

  const handleTestAndSaveConfig = async () => {
    const result = await testConfigMutation.mutateAsync(
      buildConfigPayload(true),
    );
    if (!requireRecoveryPasswordBeforeOperation(result)) {
      return;
    }
    await prepareCredential();
    if (result.remote_history_state === "foreign" && remoteHistoryOverwriteAccepted) {
      await overwriteRemoteHistoryMutation.mutateAsync(buildConfigPayload(true));
    } else {
      await updateConfig.mutateAsync({ data: buildConfigPayload(true) });
    }
    toast.success(t("system.backupConfigSaved"));
  };

  const handleDetectBackupMachine = async () => {
    await probeConnectionMutation.mutateAsync(buildConfigPayload(true));
  };

  const handleGenerateBootstrapCommand = async () => {
    const remoteHost = String(form.remote_host ?? "").trim();
    if (!remoteHost) {
      toast.error(t("system.backupBootstrapHostRequired"));
      return;
    }
    await createBootstrapClaimMutation.mutateAsync({
      remote_host: remoteHost,
      remote_port: Number(form.remote_port || 22),
      remote_path: DEFAULT_BACKUP_REMOTE_PATH,
      remote_username: DEFAULT_BACKUP_REMOTE_USERNAME,
      site_slug: DEFAULT_BACKUP_SITE_SLUG,
      credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
      ttl_minutes: BACKUP_BOOTSTRAP_TTL_MINUTES,
    });
  };

  const handleCopyBootstrapCommand = async () => {
    if (!bootstrapClaim?.setup_command) {
      return;
    }
    try {
      await copyTextToClipboard(bootstrapClaim.setup_command);
      toast.success(t("system.backupBootstrapCommandCopied"));
    } catch {
      toast.error(t("system.copyCommandFailed"));
    }
  };

  const handleRevokeBootstrapCommand = async () => {
    if (!bootstrapClaim?.id || bootstrapClaim.status === "revoked") {
      return;
    }
    await revokeBootstrapClaimMutation.mutateAsync(bootstrapClaim.id);
  };

  const handleStartBackup = async () => {
    if (config?.enabled) {
      if (!canPersistBackupConfig) {
        toast.error(t("system.recoveryKeyRequiredBeforeSave"));
        return;
      }
      await triggerSync.mutateAsync();
      return;
    }
    const result =
      configTestMode === "full" && configTestResult?.ok
        ? configTestResult
        : await testConfigMutation.mutateAsync(buildConfigPayload(true));
    if (!requireRecoveryPasswordBeforeOperation(result)) {
      return;
    }
    await handleSaveAndRun();
  };

  const handleRestoreRemoteHistory = () => {
    setRemoteImportPassphrase("");
    setRemoteImportPreview(null);
    setSelectedRemoteCommitId("");
    setRemoteImportDialogOpen(true);
  };

  const handleAcceptOverwriteRemoteHistory = () => {
    if (!window.confirm(t("system.backupOverwriteHistoryIntentConfirm"))) {
      return;
    }
    setRemoteHistoryOverwriteAccepted(true);
    toast.success(t("system.backupOverwriteHistoryIntentReady"));
  };

  const handlePreviewRemoteHistoryImport = async () => {
    try {
      await remoteHistoryPreviewMutation.mutateAsync(remoteImportPassphrase);
    } catch {
      // Mutation onError renders the user-facing error.
    }
  };

  const handleRestoreSelectedRemoteHistory = async () => {
    if (!selectedRemoteCommitId) {
      toast.error(t("system.selectBackupVersionRequired"));
      return;
    }
    try {
      await remoteHistoryRestoreMutation.mutateAsync();
    } catch {
      // Mutation onError renders the user-facing error.
    }
  };

  const remoteCommitLabel = (commit: BackupRemoteHistoryCommitRead) =>
    `${formatDate(commit.created_at)} · ${commit.id.slice(0, 8)}`;

  const handleResetBackupSystem = async () => {
    if (!window.confirm(t("system.resetBackupSystemConfirm"))) {
      return;
    }
    try {
      const result = await resetBackupSyncSystem();
      setResetCommand(result.remote_cleanup_command || REMOTE_CLEANUP_COMMAND);
      setBootstrapClaim(null);
      setConfigTestResult(null);
      setConfigTestMode(null);
      setCredentialInfo(null);
      setRecoveryKeyDelivered(false);
      setForm(emptyForm);
      setHasInitializedForm(true);
      toast.success(t("system.resetBackupSystemDone"));
      await invalidateAll();
    } catch (error: any) {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    }
  };

  const openRecoveryKeyDialog = (mode: "export" | "rotate") => {
    setKeyDialogMode(mode);
    setRecoveryPassphrase("");
    setRecoveryPassphraseConfirm("");
    setRecoveryKeyDelivered(false);
    setKeyDialogOpen(true);
  };

  const handleRecoveryKeySubmit = async () => {
    setIsRecoveryKeyPending(true);
    try {
      const result = await exportBackupRecoveryKey({
        credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
        site_slug: DEFAULT_BACKUP_SITE_SLUG,
        passphrase: recoveryPassphrase,
        rotate: keyDialogMode === "rotate",
      });
      const updated = await acknowledgeBackupRecoveryKey({
        credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
      });
      setCredentialInfo({
        credential_ref: result.credential_ref,
        site_slug: result.site_slug,
        credential_dir: result.credential_dir,
        secrets_fingerprint: result.secrets_fingerprint,
        created: false,
        archived_fingerprints: result.archived_fingerprints,
      });
      setCredentialInfo(updated);
      setRecoveryKeyDelivered(true);
      setKeyDialogOpen(false);
      if (shouldInitializeNewRemoteHistoryAfterPassword) {
        await overwriteRemoteHistoryMutation.mutateAsync(buildConfigPayload(true));
        await invalidateAll();
      }
      toast.success(t("system.recoveryPasswordSet"));
    } catch (error: any) {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    } finally {
      setIsRecoveryKeyPending(false);
    }
  };

  const recoveryKeyReady = Boolean(
    config?.recovery_key_ready || credentialInfo,
  );
  const recoveryKeyAcknowledged = Boolean(
    config?.recovery_key_acknowledged || recoveryKeyDelivered,
  );
  const recoveryKeyRequiresDelivery = false;
  const canPersistBackupConfig =
    recoveryKeyReady && recoveryKeyAcknowledged && !recoveryKeyRequiresDelivery;
  const detectionRequiresBootstrap = Boolean(
    configTestResult && !configTestResult.ok,
  );
  const remoteHistoryIsForeign =
    configTestResult?.remote_history_state === "foreign";
  const remoteHistoryIsEmpty = configTestResult?.remote_history_state === "empty";
  const localBackupHistoryExists = commits.length > 0;
  const emptyRemoteWithLocalHistory = Boolean(
    configTestResult?.ok && remoteHistoryIsEmpty && localBackupHistoryExists,
  );
  const newRemoteHistoryRequested = Boolean(
    emptyRemoteWithLocalHistory ||
      (remoteHistoryIsForeign && remoteHistoryOverwriteAccepted),
  );
  const backupMachineAllowsRecoveryPassword = Boolean(
    configTestResult?.ok &&
      (configTestResult.remote_history_state === "empty" ||
        configTestResult.remote_history_state === "current" ||
        (remoteHistoryIsForeign && remoteHistoryOverwriteAccepted)),
  );
  const canResetRecoveryPasswordForNewHistory = Boolean(
    canPersistBackupConfig &&
      backupMachineAllowsRecoveryPassword &&
      newRemoteHistoryRequested,
  );
  const canUseRecoveryPasswordForTarget = Boolean(
    canPersistBackupConfig && !newRemoteHistoryRequested,
  );
  const shouldInitializeNewRemoteHistoryAfterPassword = Boolean(
    configTestResult?.ok && newRemoteHistoryRequested,
  );
  const recoveryPasswordActionEnabled = Boolean(
    backupMachineAllowsRecoveryPassword &&
      (!canUseRecoveryPasswordForTarget || canResetRecoveryPasswordForNewHistory),
  );
  const recoveryPasswordActionLabel = canResetRecoveryPasswordForNewHistory
    ? t("system.resetRecoveryPassword")
    : canUseRecoveryPasswordForTarget
      ? t("system.recoveryPasswordAlreadySet")
      : t("system.setRecoveryPassword");
  const backupMachineConflictResolved = Boolean(
    configTestResult?.ok && (!remoteHistoryIsForeign || remoteHistoryOverwriteAccepted),
  );
  const isProbeResult = configTestMode === "probe";
  const probeNeedsBootstrap = Boolean(
    isProbeResult &&
    configTestResult &&
    (!configTestResult.ok ||
      configTestResult.remote_history_state === "unreachable"),
  );
  const backupMachineConnectionMeta = probeNeedsBootstrap
    ? t("system.backupProbeNeedsBootstrap")
    : configTestResult
      ? (configTestResult.remote_history_summary ?? configTestResult.summary)
      : undefined;
  const backupMachineStatusLabel = isProbeResult
    ? t("system.backupConnectionStatus")
    : t("system.backupConfigTestStatus");
  const backupMachineStatusValue = probeNeedsBootstrap
    ? t("system.backupConnectionNotConfigured")
    : configTestResult?.ok
      ? t("system.backupConfigTestOk")
      : t("system.backupConfigTestFailed");
  const backupMachineStatusTone =
    !configTestResult?.ok && !probeNeedsBootstrap ? "error" : "default";
  const backupConfigStatusTone = testConfigMutation.isPending
    ? "checking"
    : configTestResult?.ok && backupMachineConflictResolved
      ? "available"
      : configTestResult
        ? "invalid"
        : "pending";
  const backupConfigStatusLabel =
    backupConfigStatusTone === "checking"
      ? t("system.backupConfigTestChecking")
      : backupConfigStatusTone === "available"
        ? t("system.backupConfigTestOk")
        : backupConfigStatusTone === "invalid"
          ? t("system.backupConfigTestInvalid")
          : t("system.backupConfigTestPending");
  const latestRunVisibleError =
    isRuntimeRestoreInterruption(latestRun?.last_error)
      ? null
      : latestRun?.last_error;
  const backupMachineLatencyLabel = isProbeResult
    ? t("system.backupProbeLatency")
    : t("system.backupConfigTestLatency");

  const isBusy =
    isEnsuringCredential ||
    isRecoveryKeyPending ||
    updateConfig.isPending ||
    triggerSync.isPending ||
    pauseSync.isPending ||
    resumeSync.isPending ||
    restoreCommit.isPending ||
    probeConnectionMutation.isPending ||
    createBootstrapClaimMutation.isPending ||
    revokeBootstrapClaimMutation.isPending ||
    overwriteRemoteHistoryMutation.isPending ||
    remoteHistoryPreviewMutation.isPending ||
    remoteHistoryRestoreMutation.isPending;
  const backupMachineHost = String(form.remote_host ?? "").trim();
  const canUseBackupActions =
    !isConfigLoading &&
    !isBusy &&
    (Boolean(config?.enabled) || Boolean(backupMachineHost));

  return (
    <div className="space-y-6">
      <PageHeader
        title={
          <span className="inline-flex flex-wrap items-baseline gap-x-5 gap-y-1">
            <span>{t("system.backups")}</span>
            <span className="text-sm font-medium text-muted-foreground">
              {config?.encrypt_runtime_data
                ? t("system.runtimeEncryptionEnabled")
                : t("system.runtimeEncryptionDisabled")}
            </span>
          </span>
        }
        description={t("system.backupsDescription")}
        secondary={
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start">
            <div className="xl:min-w-[420px] xl:max-w-xl">
              <AdminSectionTabs
                items={sectionItems}
                value={section}
                onValueChange={(value) => handleSectionChange(value as BackupsSection)}
                className="w-fit"
              />
            </div>
          </div>
        }
      />

      <Tabs
        value={section}
        onValueChange={(value) => handleSectionChange(value as BackupsSection)}
      >
        <TabsContent value="settings" className="mt-0 space-y-6">
          <Card>
            <CardHeader>
              <div className="flex justify-end">
                <div className="flex flex-wrap items-center justify-end gap-2">
                  <BackupConfigStatusIndicator
                    label={backupConfigStatusLabel}
                    tone={backupConfigStatusTone}
                  />
                  {hasConfigChanges ? (
                    <span className="rounded-full border border-[rgb(var(--admin-accent-rgb)/0.22)] bg-[rgb(var(--admin-accent-rgb)/0.08)] px-3 py-1 text-xs text-[rgb(var(--admin-accent-rgb)/0.95)]">
                      {t("common.pendingSave")}
                    </span>
                  ) : null}
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    onClick={() => void handleTestAndSaveConfig()}
                    disabled={!canUseBackupActions}
                  >
                    {testConfigMutation.isPending || updateConfig.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Save className="h-4 w-4" />
                    )}
                    {t("system.testAndSave")}
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    className="gap-2"
                    onClick={() => void handleStartBackup()}
                    disabled={!canUseBackupActions}
                  >
                    {triggerSync.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Database className="h-4 w-4" />
                    )}
                    {config?.enabled
                      ? t("system.triggerBackup")
                      : t("system.startBackupAction")}
                  </Button>
                  {config?.enabled ? (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="gap-2"
                      onClick={() =>
                        config?.paused
                          ? resumeSync.mutate()
                          : pauseSync.mutate()
                      }
                      disabled={isBusy}
                    >
                      {config?.paused ? (
                        <PlayCircle className="h-4 w-4" />
                      ) : (
                        <PauseCircle className="h-4 w-4" />
                      )}
                      {config?.paused
                        ? t("system.resumeSync")
                        : t("system.pauseSync")}
                    </Button>
                  ) : null}
                </div>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <SetupRow index="1" title={t("system.backupBootstrapHostTitle")}>
                <div className="grid gap-3 md:grid-cols-[minmax(0,1fr)_auto] md:items-end">
                  <Input
                    value={form.remote_host ?? ""}
                    placeholder="eg: 10.129.237.34 / aerisun (tailscale主机名)"
                    onChange={(e) => setField("remote_host", e.target.value)}
                  />
                  <Button
                    type="button"
                    className="gap-2"
                    onClick={() => void handleDetectBackupMachine()}
                    disabled={isBusy || !String(form.remote_host ?? "").trim()}
                  >
                    {probeConnectionMutation.isPending ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <SearchCheck className="h-4 w-4" />
                    )}
                    {t("system.detectBackupMachine")}
                  </Button>
                </div>
              </SetupRow>

              <SetupRow
                index="2"
                title={t("system.backupDetectTitle")}
                meta={backupMachineConnectionMeta}
                metaTone={probeNeedsBootstrap ? "warning" : "muted"}
                complete={backupMachineConflictResolved}
              >
                {configTestResult ? (
                  <div
                    className={cn(
                      "mb-3 grid gap-3 text-sm",
                      probeNeedsBootstrap ? "md:grid-cols-2" : "md:grid-cols-3",
                    )}
                  >
                    <MetaLine
                      label={backupMachineStatusLabel}
                      value={backupMachineStatusValue}
                      tone={backupMachineStatusTone}
                      formatAsDate={false}
                    />
                    {probeNeedsBootstrap ? null : (
                      <MetaLine
                        label={t("system.remotePathPreviewTitle")}
                        value={configTestResult.remote_path_preview}
                        formatAsDate={false}
                      />
                    )}
                    <MetaLine
                      label={backupMachineLatencyLabel}
                      value={
                        configTestResult.latency_ms != null
                          ? `${configTestResult.latency_ms} ms`
                          : "-"
                      }
                      formatAsDate={false}
                    />
                  </div>
                ) : null}

                {remoteHistoryIsForeign ? (
                  <div className="mb-3 rounded-[var(--admin-radius-md)] border border-amber-400/35 bg-amber-500/10 px-4 py-3 text-sm text-amber-950 dark:text-amber-100">
                    <div className="flex items-start gap-2">
                      <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
                      <div className="min-w-0 space-y-3">
                        <div>{t("system.backupForeignHistoryWarning")}</div>
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className="w-fit"
                            onClick={handleRestoreRemoteHistory}
                          >
                            <RotateCcw className="mr-2 h-4 w-4" />
                            {t("system.restoreThisHistory")}
                          </Button>
                          <Button
                            type="button"
                            variant={
                              remoteHistoryOverwriteAccepted
                                ? "default"
                                : "outline"
                            }
                            size="sm"
                            className="w-fit"
                            onClick={handleAcceptOverwriteRemoteHistory}
                            disabled={isBusy || remoteHistoryOverwriteAccepted}
                          >
                            <Trash2 className="mr-2 h-4 w-4" />
                            {remoteHistoryOverwriteAccepted
                              ? t("system.backupOverwriteHistoryIntentReady")
                              : t("system.overwriteRemoteHistory")}
                          </Button>
                        </div>
                      </div>
                    </div>
                  </div>
                ) : null}

                {detectionRequiresBootstrap ? (
                  <div className="space-y-3">
                    <Button
                      type="button"
                      className="gap-2"
                      onClick={() => void handleGenerateBootstrapCommand()}
                      disabled={
                        isBusy || !String(form.remote_host ?? "").trim()
                      }
                    >
                      {createBootstrapClaimMutation.isPending ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <TerminalSquare className="h-4 w-4" />
                      )}
                      {bootstrapClaim
                        ? t("system.backupBootstrapRegenerate")
                        : t("system.backupBootstrapGenerate")}
                    </Button>
                    {bootstrapClaim ? (
                      <div className="text-xs leading-5 text-muted-foreground">
                        {backupBootstrapStatusText(bootstrapClaim, t)}
                      </div>
                    ) : null}
                    {bootstrapClaim?.setup_command ? (
                      <>
                        <div className="flex min-w-0 items-center rounded-[var(--admin-radius-md)] border border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] bg-[rgb(var(--admin-surface-1)/0.36)]">
                          <code className="min-w-0 flex-1 overflow-x-auto whitespace-nowrap px-3 py-2 font-mono text-xs text-foreground/85">
                            {bootstrapClaim.setup_command}
                          </code>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => void handleCopyBootstrapCommand()}
                          >
                            <Copy className="mr-2 h-4 w-4" />
                            {t("system.copyBootstrapCommand")}
                          </Button>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => void handleRevokeBootstrapCommand()}
                            disabled={
                              isBusy ||
                              bootstrapClaim.status === "revoked" ||
                              bootstrapClaim.status === "succeeded"
                            }
                          >
                            {t("system.backupBootstrapRevoke")}
                          </Button>
                          <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
                            <Clock className="h-3.5 w-3.5" />
                            {formatCountdown(bootstrapSecondsLeft)}
                          </span>
                        </div>
                      </>
                    ) : null}
                  </div>
                ) : null}
              </SetupRow>

              <SetupRow
                index="3"
                title={
                  <LabelWithHelp
                    label={t("system.recoveryPasswordTitle")}
                    title={t("system.recoveryPasswordTitle")}
                    description={t(
                      "system.recoveryPasswordRequiredDescription",
                    )}
                  />
                }
                meta={
                  canUseRecoveryPasswordForTarget
                    ? canResetRecoveryPasswordForNewHistory
                      ? t("system.recoveryPasswordCanResetForNewHistory")
                      : t("system.recoveryPasswordReadyDescription")
                    : emptyRemoteWithLocalHistory
                      ? t("system.recoveryPasswordRequiredForNewRemote")
                    : backupMachineAllowsRecoveryPassword
                      ? remoteHistoryOverwriteAccepted
                        ? t("system.backupOverwriteHistoryIntentReady")
                        : undefined
                      : t("system.recoveryPasswordBlockedUntilBackupReady")
                }
                complete={canPersistBackupConfig}
              >
                <div className="flex flex-wrap items-center gap-2">
                  <Button
                    type="button"
                    variant={
                      canUseRecoveryPasswordForTarget &&
                      !canResetRecoveryPasswordForNewHistory
                        ? "outline"
                        : "default"
                    }
                    className="gap-2"
                    onClick={() =>
                      openRecoveryKeyDialog(
                        canPersistBackupConfig ? "rotate" : "export",
                      )
                    }
                    disabled={isBusy || !recoveryPasswordActionEnabled}
                  >
                    <KeyRound className="h-4 w-4" />
                    {recoveryPasswordActionLabel}
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={() => setForgotDialogOpen(true)}
                  >
                    {t("system.forgotRecoveryPassword")}
                  </Button>
                </div>
              </SetupRow>

              <CollapsibleSection
                title={t("system.advancedOptions")}
                badge={t("common.optional")}
                defaultOpen={false}
              >
                <div className="grid gap-4 md:grid-cols-2">
                  <Field
                    label={
                      <LabelWithHelp
                        label={t("system.syncIntervalLabel")}
                        title={t("system.syncIntervalLabel")}
                        description={t("system.syncIntervalLabelDescription")}
                      />
                    }
                  >
                    <Input
                      type="number"
                      min={1}
                      value={form.interval_minutes ?? DEFAULT_BACKUP_INTERVAL_MINUTES}
                      onChange={(e) =>
                        setField(
                          "interval_minutes",
                          Number(e.target.value || DEFAULT_BACKUP_INTERVAL_MINUTES),
                        )
                      }
                    />
                  </Field>
                  <Field
                    label={
                      <LabelWithHelp
                        label={t("system.sshPortLabel")}
                        title={t("system.sshPortLabel")}
                        description={t("system.sshPortDescription")}
                      />
                    }
                  >
                    <Input
                      type="number"
                      min={1}
                      value={form.remote_port ?? 22}
                      onChange={(e) =>
                        setField("remote_port", Number(e.target.value || 22))
                      }
                    />
                  </Field>
                  <Field
                    label={
                      <LabelWithHelp
                        label={t("system.backupRetentionDays")}
                        title={t("system.backupRetentionDays")}
                        description={t("system.backupRetentionDaysDescription")}
                      />
                    }
                  >
                    <Input
                      type="number"
                      min={0}
                      value={form.retention_days ?? DEFAULT_BACKUP_RETENTION_DAYS}
                      onChange={(e) =>
                        setField(
                          "retention_days",
                          Number(e.target.value || DEFAULT_BACKUP_RETENTION_DAYS),
                        )
                      }
                    />
                  </Field>
                  <Field
                    label={
                      <LabelWithHelp
                        label={t("system.backupMaxRetentionCount")}
                        title={t("system.backupMaxRetentionCount")}
                        description={t("system.backupMaxRetentionCountDescription")}
                      />
                    }
                  >
                    <Input
                      type="number"
                      min={0}
                      value={form.max_retention_count ?? DEFAULT_BACKUP_MAX_RETENTION_COUNT}
                      onChange={(e) =>
                        setField(
                          "max_retention_count",
                          Number(e.target.value || DEFAULT_BACKUP_MAX_RETENTION_COUNT),
                        )
                      }
                    />
                  </Field>
                  <Field
                    label={
                      <LabelWithHelp
                        label={t("system.maxRetries")}
                        title={t("system.maxRetries")}
                        description={t("system.maxRetriesDescription")}
                      />
                    }
                  >
                    <Input
                      type="number"
                      min={0}
                      value={form.max_retries ?? 3}
                      onChange={(e) =>
                        setField("max_retries", Number(e.target.value || 0))
                      }
                    />
                  </Field>
                  <Field
                    label={
                      <LabelWithHelp
                        label={t("system.retryBackoffSeconds")}
                        title={t("system.retryBackoffSeconds")}
                        description={t("system.retryBackoffDescription")}
                      />
                    }
                  >
                    <Input
                      type="number"
                      min={30}
                      value={form.retry_backoff_seconds ?? 300}
                      onChange={(e) =>
                        setField(
                          "retry_backoff_seconds",
                          Number(e.target.value || 300),
                        )
                      }
                    />
                  </Field>
                  <div className="flex min-h-10 items-center justify-between gap-4">
                    <div className="min-w-0">
                      <LabelWithHelp
                        label={
                          form.encrypt_runtime_data
                            ? t("system.runtimeEncryptionLabelEnabled")
                            : t("system.runtimeEncryptionLabelDisabled")
                        }
                        title={t("system.runtimeEncryptionLabel")}
                        description={t("system.runtimeEncryptionDescription")}
                      />
                    </div>
                    <CompactSwitch
                      checked={Boolean(form.encrypt_runtime_data)}
                      onCheckedChange={(checked) =>
                        setField("encrypt_runtime_data", checked)
                      }
                      ariaLabel={t("system.runtimeEncryptionLabel")}
                      disabled={isBusy}
                    />
                  </div>
                  <div className="flex min-h-10 items-center gap-3">
                    <Button
                      type="button"
                      variant="destructive"
                      className="gap-2"
                      onClick={() => void handleResetBackupSystem()}
                    >
                      <Trash2 className="h-4 w-4" />
                      {t("system.resetBackupSystem")}
                    </Button>
                    <LabelWithHelp
                      hideLabel
                      label={t("system.resetBackupSystem")}
                      title={t("system.resetBackupSystem")}
                      description={t("system.resetBackupSystemDescription")}
                    />
                  </div>
                </div>
              </CollapsibleSection>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="records" className="mt-0 space-y-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <AdminSectionTabs
              items={[
                { value: "commits", label: t("system.commitRecords") },
                { value: "runs", label: t("system.runRecords") },
              ]}
              value={recordsSection}
              onValueChange={(value) =>
                handleRecordsSectionChange(value as BackupRecordsSection)
              }
              size="sm"
              className="w-fit"
            />
            <div className="flex flex-wrap items-center gap-2 lg:justify-end">
              <Button
                variant="outline"
                onClick={() => invalidateAll()}
                disabled={isBusy}
              >
                <RefreshCcw className="mr-2 h-4 w-4" />
                {t("common.refresh")}
              </Button>
              <Button onClick={() => triggerSync.mutate()} disabled={isBusy}>
                <Database className="mr-2 h-4 w-4" />
                {t("system.triggerBackup")}
              </Button>
            </div>
          </div>

          <Tabs
            value={recordsSection}
            onValueChange={(value) =>
              handleRecordsSectionChange(value as BackupRecordsSection)
            }
          >
            <TabsContent value="commits" className="mt-0">
              <Card>
                <CardHeader>
                  <CardTitle>{t("system.commitRecords")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataTable<BackupCommitRead>
                    columns={[
                      {
                        header: t("system.transportMode"),
                        accessor: "transport",
                      },
                      {
                        header: t("system.triggerKind"),
                        accessor: "trigger_kind",
                      },
                      {
                        header: t("system.completed"),
                        accessor: (row) =>
                          formatDate(
                            row.snapshot_finished_at || row.created_at,
                          ),
                      },
                      {
                        header: t("system.lastRestoreAt"),
                        accessor: (row) => formatDate(row.restored_at),
                      },
                      {
                        header: t("common.actions"),
                        accessor: (row) => (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={restoreCommit.isPending}
                            onClick={(event) => {
                              event.stopPropagation();
                              setRestoreConfirmCommit(row);
                            }}
                          >
                            <RotateCcw className="mr-1 h-4 w-4" />
                            {t("system.restore")}
                          </Button>
                        ),
                      },
                    ]}
                    data={commits}
                    total={commits.length}
                    pageSize={10}
                    isLoading={isCommitsLoading}
                    renderExpandedRow={(row) => (
                      <div className="space-y-2 py-4 text-sm">
                        <div className="text-muted-foreground">
                          {row.backup_path || "-"}
                        </div>
                        <code className="block whitespace-pre-wrap break-all text-xs text-muted-foreground">
                          {JSON.stringify(row.datasets, null, 2)}
                        </code>
                      </div>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="runs" className="mt-0">
              <Card>
                <CardHeader>
                  <CardTitle>{t("system.runRecords")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataTable<BackupRunRead>
                    columns={[
                      {
                        header: t("common.status"),
                        accessor: (row) => <StatusBadge status={row.status} />,
                      },
                      {
                        header: t("system.triggerKind"),
                        accessor: (row) => row.trigger_kind || "-",
                      },
                      {
                        header: t("system.startedAt"),
                        accessor: (row) => formatDate(row.started_at),
                      },
                      {
                        header: t("system.completed"),
                        accessor: (row) => formatDate(row.finished_at),
                      },
                    ]}
                    data={runs}
                    total={runs.length}
                    pageSize={10}
                    isLoading={isRunsLoading}
                    renderExpandedRow={(row) => (
                      <div className="space-y-2 py-4 text-sm">
                        <div>{getVisibleRunMessage(row, t("system.none"))}</div>
                        <code className="block whitespace-pre-wrap break-all text-xs text-muted-foreground">
                          {JSON.stringify(row.stats_json ?? {}, null, 2)}
                        </code>
                      </div>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          {latestRunVisibleError ? (
            <Card surface="soft" className="border-red-200/60">
              <CardContent className="p-4 text-sm text-red-600">
                {latestRunVisibleError}
              </CardContent>
            </Card>
          ) : null}
        </TabsContent>
      </Tabs>

      <Dialog
        open={remoteImportDialogOpen}
        onOpenChange={(open) => {
          setRemoteImportDialogOpen(open);
          if (!open) {
            setRemoteImportPassphrase("");
            setRemoteImportPreview(null);
            setSelectedRemoteCommitId("");
          }
        }}
      >
        <DialogContent className="max-w-2xl rounded-2xl">
          <DialogHeader className="text-left">
            <DialogTitle>{t("system.remoteHistoryImportTitle")}</DialogTitle>
            <DialogDescription>
              {t("system.remoteHistoryImportDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Field label={t("system.recoveryKeyPassword")}>
              <Input
                type="password"
                autoComplete="current-password"
                value={remoteImportPassphrase}
                onChange={(event) => {
                  setRemoteImportPassphrase(event.target.value);
                  setRemoteImportPreview(null);
                  setSelectedRemoteCommitId("");
                }}
                placeholder="********"
              />
            </Field>
            <div className="flex justify-end">
              <Button
                type="button"
                variant="outline"
                onClick={() => void handlePreviewRemoteHistoryImport()}
                disabled={
                  remoteHistoryPreviewMutation.isPending ||
                  remoteImportPassphrase.length < 8
                }
              >
                {remoteHistoryPreviewMutation.isPending ? (
                  <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                ) : null}
                {t("system.verifyRecoveryPassword")}
              </Button>
            </div>

            {remoteImportPreview ? (
              <div className="space-y-4 rounded-[var(--admin-radius-md)] border border-border/70 bg-muted/30 p-4">
                {remoteImportPreview.commits.length > 0 ? (
                  <Field label={t("system.selectBackupVersion")}>
                    <NativeSelect
                      value={selectedRemoteCommitId}
                      onChange={(event) =>
                        setSelectedRemoteCommitId(event.target.value)
                      }
                    >
                      {remoteImportPreview.commits.map((commit) => (
                        <option key={commit.id} value={commit.id}>
                          {remoteCommitLabel(commit)}
                        </option>
                      ))}
                    </NativeSelect>
                  </Field>
                ) : (
                  <div className="text-sm text-muted-foreground">
                    {t("system.remoteHistoryNoVersions")}
                  </div>
                )}
                <div className="flex justify-end gap-2">
                  <Button
                    type="button"
                    variant="outline"
                    onClick={() => setRemoteImportDialogOpen(false)}
                    disabled={remoteHistoryRestoreMutation.isPending}
                  >
                    {t("common.cancel")}
                  </Button>
                  <Button
                    type="button"
                    onClick={() => void handleRestoreSelectedRemoteHistory()}
                    disabled={
                      remoteHistoryRestoreMutation.isPending ||
                      !selectedRemoteCommitId
                    }
                  >
                    {remoteHistoryRestoreMutation.isPending ? (
                      <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                    ) : (
                      <RotateCcw className="mr-2 h-4 w-4" />
                    )}
                    {t("system.restoreSelectedBackupVersion")}
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={keyDialogOpen} onOpenChange={setKeyDialogOpen}>
        <DialogContent className="max-w-2xl rounded-2xl">
          <DialogHeader className="text-left">
            <DialogTitle>
              {keyDialogMode === "rotate"
                ? t("system.resetRecoveryPassword")
                : t("system.setRecoveryPassword")}
            </DialogTitle>
            <DialogDescription>
              {keyDialogMode === "rotate"
                ? t("system.resetRecoveryPasswordDescription")
                : t("system.setRecoveryPasswordDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="rounded-[var(--admin-radius-md)] border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm leading-6 text-amber-950 dark:text-amber-100">
              {keyDialogMode === "rotate"
                ? t("system.resetRecoveryPasswordImportantWarning")
                : t("system.recoveryPasswordImportantWarning")}
            </div>
            <form
              className="space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                if (
                  isRecoveryKeyPending ||
                  recoveryPassphrase.length < 8 ||
                  recoveryPassphrase !== recoveryPassphraseConfirm
                ) {
                  return;
                }
                void handleRecoveryKeySubmit();
              }}
            >
              <Field
                label={
                  <LabelWithHelp
                    label={t("system.recoveryKeyPassword")}
                    title={t("system.recoveryKeyPassword")}
                    description={t("system.recoveryKeyPasswordDescription")}
                  />
                }
              >
                <Input
                  type="password"
                  autoComplete="new-password"
                  value={recoveryPassphrase}
                  onChange={(event) =>
                    setRecoveryPassphrase(event.target.value)
                  }
                  placeholder="********"
                />
              </Field>
              <Field label={t("system.recoveryPasswordConfirm")}>
                <Input
                  type="password"
                  autoComplete="new-password"
                  value={recoveryPassphraseConfirm}
                  onChange={(event) =>
                    setRecoveryPassphraseConfirm(event.target.value)
                  }
                  placeholder="********"
                />
              </Field>
              {recoveryPassphraseConfirm &&
              recoveryPassphrase !== recoveryPassphraseConfirm ? (
                <div className="text-sm text-red-600">
                  {t("system.recoveryPasswordMismatch")}
                </div>
              ) : null}
              <div className="flex justify-end gap-2">
                <Button
                  type="button"
                  variant="outline"
                  onClick={() => setKeyDialogOpen(false)}
                  disabled={isRecoveryKeyPending}
                >
                  {t("common.cancel")}
                </Button>
                <Button
                  type="submit"
                  disabled={
                    isRecoveryKeyPending ||
                    recoveryPassphrase.length < 8 ||
                    recoveryPassphrase !== recoveryPassphraseConfirm
                  }
                >
                  {isRecoveryKeyPending ? (
                    <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                  ) : null}
                  {keyDialogMode === "rotate"
                    ? t("system.confirmResetRecoveryPassword")
                    : t("system.confirmSetRecoveryPassword")}
                </Button>
              </div>
            </form>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog open={forgotDialogOpen} onOpenChange={setForgotDialogOpen}>
        <DialogContent className="max-w-2xl rounded-2xl">
          <DialogHeader className="text-left">
            <DialogTitle>{t("system.forgotRecoveryPassword")}</DialogTitle>
            <DialogDescription>
              {t("system.forgotRecoveryPasswordDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <Textarea
              value={resetCommand}
              readOnly
              rows={5}
              className="font-mono text-xs"
            />
            <div className="flex flex-wrap justify-end gap-2">
              <Button
                type="button"
                variant="outline"
                onClick={() => {
                  void copyTextToClipboard(resetCommand)
                    .then(() =>
                      toast.success(t("system.backupCleanupCommandCopied")),
                    )
                    .catch(() => toast.error(t("system.copyCommandFailed")));
                }}
              >
                <Copy className="mr-2 h-4 w-4" />
                {t("system.copyBootstrapCommand")}
              </Button>
              <Button type="button" onClick={() => setForgotDialogOpen(false)}>
                {t("common.done")}
              </Button>
            </div>
          </div>
        </DialogContent>
      </Dialog>

      <Dialog
        open={Boolean(restoreConfirmCommit)}
        onOpenChange={(open) => {
          if (!open && !restoreCommit.isPending) {
            setRestoreConfirmCommit(null);
          }
        }}
      >
        <DialogContent
          hideCloseButton
          className="max-w-[560px] overflow-hidden rounded-[28px] border border-white/70 p-0 shadow-[0_26px_80px_rgba(15,23,42,0.28)]"
        >
          <div className="px-8 pb-7 pt-8">
            <DialogHeader className="items-center space-y-0 text-center">
              <div className="flex items-center justify-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-2xl border border-destructive/20 bg-destructive/10 text-destructive">
                  <AlertTriangle className="h-4 w-4" />
                </span>
                <DialogTitle className="text-xl font-semibold leading-tight tracking-normal">
                  {t("system.restoreConfirm")}
                </DialogTitle>
              </div>
            </DialogHeader>
            <DialogDescription asChild>
              <div className="mt-5 space-y-2 text-left text-base leading-7 text-muted-foreground">
                <p>
                  {t("system.restoreConfirmPoint", {
                    time: restoreConfirmTime,
                  })}
                </p>
                <p>
                  {t("system.restoreConfirmBodyPrefix")}
                  <strong className="font-semibold text-foreground">
                    {t("system.restoreConfirmBodyStrong")}
                  </strong>
                  {t("system.restoreConfirmBodySuffix")}
                </p>
                <p>
                  {t("system.restoreConfirmFinalLine", {
                    time: restoreConfirmTime,
                  })}
                </p>
              </div>
            </DialogDescription>
          </div>
          <div className="flex justify-end gap-3 border-t border-border/50 bg-muted/20 px-8 py-5">
            <Button
              type="button"
              variant="outline"
              className="min-w-28 rounded-2xl"
              onClick={() => setRestoreConfirmCommit(null)}
              disabled={restoreCommit.isPending}
            >
              {t("common.cancel")}
            </Button>
            <Button
              type="button"
              variant="destructive"
              className="min-w-28 rounded-2xl"
              onClick={handleConfirmRestoreCommit}
              disabled={restoreCommit.isPending}
            >
              {restoreCommit.isPending ? t("common.loading") : t("system.confirmRestore")}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function formatCountdown(seconds: number) {
  if (seconds <= 0) {
    return "00:00";
  }
  const minutes = Math.floor(seconds / 60);
  const rest = seconds % 60;
  return `${String(minutes).padStart(2, "0")}:${String(rest).padStart(2, "0")}`;
}

function backupBootstrapStatusText(
  claim: BackupBootstrapClaimRead,
  t: (key: string) => string,
) {
  if (claim.status === "succeeded") {
    return t("system.backupBootstrapStatusSucceeded");
  }
  if (claim.status === "failed") {
    return claim.last_error || t("system.backupBootstrapStatusFailed");
  }
  if (claim.status === "expired") {
    return t("system.backupBootstrapStatusExpired");
  }
  if (claim.status === "revoked") {
    return t("system.backupBootstrapStatusRevoked");
  }
  return t("system.backupBootstrapStatusPending");
}

function SetupRow({
  index,
  title,
  meta,
  metaTone = "muted",
  complete = false,
  children,
}: {
  index: string;
  title: ReactNode;
  meta?: string;
  metaTone?: "muted" | "warning";
  complete?: boolean;
  children: ReactNode;
}) {
  return (
    <div className="grid gap-3 rounded-[var(--admin-radius-md)] border border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] bg-[rgb(var(--admin-surface-1)/0.24)] p-4 md:grid-cols-[2.25rem_minmax(0,1fr)]">
      <div
        className={cn(
          "flex h-8 w-8 items-center justify-center rounded-full border text-sm font-semibold",
          complete
            ? "border-emerald-500/30 bg-emerald-500/12 text-emerald-700 dark:text-emerald-200"
            : "border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] bg-[rgb(var(--admin-surface-1)/0.52)] text-muted-foreground",
        )}
      >
        {index}
      </div>
      <div className="min-w-0 space-y-3">
        <div className="min-w-0">
          <div className="text-sm font-semibold text-foreground/90">
            {title}
          </div>
          {meta ? (
            <div
              className={cn(
                "mt-1 text-xs leading-5",
                metaTone === "warning"
                  ? "font-medium text-amber-700 dark:text-amber-300"
                  : "text-muted-foreground",
              )}
            >
              {meta}
            </div>
          ) : null}
        </div>
        <div>{children}</div>
      </div>
    </div>
  );
}

function BackupConfigStatusIndicator({
  label,
  tone,
}: {
  label: ReactNode;
  tone: "pending" | "available" | "invalid" | "checking";
}) {
  const toneClassName =
    tone === "pending"
      ? {
          shell:
            "border-slate-400/20 bg-slate-500/8 text-slate-600 dark:text-slate-300",
          dot: "bg-slate-400 shadow-[0_0_0_4px_rgba(148,163,184,0.12),0_0_14px_rgba(148,163,184,0.28)]",
        }
      : tone === "available"
        ? {
            shell:
              "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
            dot: "bg-emerald-500 shadow-[0_0_0_4px_rgba(34,197,94,0.16),0_0_18px_rgba(34,197,94,0.6)]",
          }
        : tone === "checking"
          ? {
              shell:
                "border-amber-500/20 bg-amber-500/10 text-amber-700 dark:text-amber-300",
              dot: "bg-amber-500 animate-pulse shadow-[0_0_0_4px_rgba(245,158,11,0.14),0_0_16px_rgba(245,158,11,0.45)]",
            }
          : {
              shell:
                "border-rose-500/20 bg-rose-500/10 text-rose-700 dark:text-rose-300",
              dot: "bg-rose-500 shadow-[0_0_0_4px_rgba(244,63,94,0.14),0_0_16px_rgba(244,63,94,0.45)]",
            };

  return (
    <div
      className={cn(
        "inline-flex h-9 items-center gap-2 rounded-full border px-3 text-xs font-medium",
        toneClassName.shell,
      )}
    >
      <span className={cn("h-2.5 w-2.5 rounded-full", toneClassName.dot)} />
      <span>{label}</span>
    </div>
  );
}

function Field({
  label,
  description,
  children,
}: {
  label: ReactNode;
  description?: string;
  children: ReactNode;
}) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-foreground/90">{label}</span>
      {children}
      {description ? (
        <span className="block text-xs leading-5 text-muted-foreground">
          {description}
        </span>
      ) : null}
    </label>
  );
}

function CompactSwitch({
  checked,
  onCheckedChange,
  disabled = false,
  ariaLabel,
}: {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  ariaLabel: string;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={() => onCheckedChange(!checked)}
      disabled={disabled}
      className={cn(
        "relative inline-flex h-8 w-14 shrink-0 items-center overflow-hidden rounded-full border transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        checked
          ? "border-emerald-400/45 bg-emerald-500/35 shadow-[inset_0_1px_0_rgba(255,255,255,0.24),0_0_0_1px_rgba(16,185,129,0.14),0_10px_28px_rgba(16,185,129,0.12)]"
          : "border-slate-300/60 bg-white shadow-[inset_0_1px_0_rgba(255,255,255,0.9),0_1px_2px_rgba(15,23,42,0.06)] dark:border-white/15 dark:bg-white/10",
        disabled && "pointer-events-none opacity-60",
      )}
    >
      <span
        className={cn(
          "pointer-events-none relative block h-6 w-6 rounded-full bg-white shadow-[0_8px_18px_rgba(15,23,42,0.18)] ring-1 ring-black/5 transition-transform duration-200 before:absolute before:inset-[0.15rem] before:rounded-full before:bg-gradient-to-br before:from-white/90 before:to-white/35 before:content-[''] dark:bg-slate-100 dark:ring-white/10 dark:before:from-white/45 dark:before:to-white/10",
          checked ? "translate-x-6" : "translate-x-1",
        )}
      />
    </button>
  );
}

function MetaLine({
  label,
  value,
  tone = "default",
  formatAsDate = true,
}: {
  label: string;
  value: string | null | undefined;
  tone?: "default" | "error";
  formatAsDate?: boolean;
}) {
  return (
    <div className="rounded-[var(--admin-radius-md)] border border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] bg-[rgb(var(--admin-surface-1)/0.36)] px-3 py-2">
      <div className="text-xs text-muted-foreground">{label}</div>
      <div
        className={
          tone === "error"
            ? "mt-1 text-sm text-red-600"
            : "mt-1 text-sm text-foreground/90"
        }
      >
        {value ? (formatAsDate ? formatDate(value) || value : value) : "-"}
      </div>
    </div>
  );
}
