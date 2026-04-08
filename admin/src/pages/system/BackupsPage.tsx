import { type ReactNode, useEffect, useMemo, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
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
  useRetryBackupSyncApiV1AdminSystemBackupSyncRunsRunIdRetryPost,
  useTriggerBackupSyncApiV1AdminSystemBackupSyncRunsPost,
  useUpdateBackupSyncConfigApiV1AdminSystemBackupSyncConfigPut,
} from "@serino/api-client/admin";
import type {
  BackupCommitRead,
  BackupQueueItemRead,
  BackupRunRead,
  BackupSyncConfig,
  BackupSyncConfigUpdate,
} from "@serino/api-client/models";
import {
  acknowledgeBackupRecoveryKey,
  ensureBackupCredentials,
  exportBackupRecoveryKey,
  testBackupSyncConfig,
  type BackupCredentialEnsureRead,
  type BackupCredentialExportRead,
  type BackupSyncConfigTestRead,
} from "@/pages/system/api";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { ConfigSettingsCard } from "@/components/ConfigSettingsCard";
import { AdminSectionTabs } from "@/components/ui/AdminSectionTabs";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/Dialog";
import { Input } from "@/components/ui/Input";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { Tabs, TabsContent } from "@/components/ui/Tabs";
import { Textarea } from "@/components/ui/Textarea";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { cn, formatDate } from "@/lib/utils";
import {
  Copy,
  Database,
  Download,
  Loader2,
  PauseCircle,
  PlayCircle,
  RefreshCcw,
  RotateCcw,
  Stethoscope,
  ShieldCheck,
} from "lucide-react";
import { toast } from "sonner";

type BackupsSection = "settings" | "records";
type BackupRecordsSection = "runs" | "commits";

const REMOTE_PATH_PLACEHOLDER = "/home/<ssh-user>/aerisun-backups";
const DEFAULT_BACKUP_CREDENTIAL_REF = "aerisun-backup-source";
const DEFAULT_BACKUP_SITE_SLUG = "aerisun";
const DEFAULT_BACKUP_CREDENTIAL_DIR = `.store/secrets/backup-sync/${DEFAULT_BACKUP_CREDENTIAL_REF}`;

const emptyForm: BackupSyncConfigUpdate = {
  enabled: true,
  paused: false,
  interval_minutes: 60,
  transport_mode: "sftp",
  site_slug: DEFAULT_BACKUP_SITE_SLUG,
  remote_host: "",
  remote_port: 22,
  remote_path: "",
  remote_username: "",
  credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
  encrypt_runtime_data: false,
  max_retries: 3,
  retry_backoff_seconds: 300,
};

export default function BackupsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<BackupSyncConfigUpdate>(emptyForm);
  const [section, setSection] = useState<BackupsSection>("settings");
  const [recordsSection, setRecordsSection] = useState<BackupRecordsSection>("runs");
  const [credentialInfo, setCredentialInfo] = useState<BackupCredentialEnsureRead | null>(null);
  const [isEnsuringCredential, setIsEnsuringCredential] = useState(false);
  const [keyDialogOpen, setKeyDialogOpen] = useState(false);
  const [keyDialogMode, setKeyDialogMode] = useState<"export" | "rotate">("export");
  const [recoveryPassphrase, setRecoveryPassphrase] = useState("");
  const [recoveryKeyResult, setRecoveryKeyResult] = useState<BackupCredentialExportRead | null>(null);
  const [isRecoveryKeyPending, setIsRecoveryKeyPending] = useState(false);
  const [recoveryKeyDelivered, setRecoveryKeyDelivered] = useState(false);
  const [configTestResult, setConfigTestResult] = useState<BackupSyncConfigTestRead | null>(null);

  const { data: configRaw, isLoading: isConfigLoading } =
    useGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGet();
  const { data: queueRaw, isLoading: _isQueueLoading } =
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
  const queue = (queueRaw?.data as BackupQueueItemRead[] | undefined) ?? [];
  const runs = (runsRaw?.data as BackupRunRead[] | undefined) ?? [];
  const commits = (commitsRaw?.data as BackupCommitRead[] | undefined) ?? [];

  const invalidateAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({
        queryKey: getGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGetQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey: getListBackupSyncQueueApiV1AdminSystemBackupSyncQueueGetQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey: getListBackupSyncRunsApiV1AdminSystemBackupSyncRunsGetQueryKey(),
      }),
      queryClient.invalidateQueries({
        queryKey: getListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGetQueryKey(),
      }),
    ]);
  };

  useEffect(() => {
    if (!config) {
      return;
    }
    setForm({
      enabled: true,
      paused: config.paused ?? false,
      interval_minutes: config.interval_minutes ?? 60,
      transport_mode: config.transport_mode ?? "sftp",
      site_slug: DEFAULT_BACKUP_SITE_SLUG,
      remote_host: config.transport.remote_host ?? "",
      remote_port: config.transport.remote_port ?? 22,
      remote_path: config.transport.remote_path ?? "",
      remote_username: config.transport.remote_username ?? "",
      credential_ref: config.credential_ref ?? DEFAULT_BACKUP_CREDENTIAL_REF,
      encrypt_runtime_data: config.encrypt_runtime_data ?? false,
      max_retries: config.max_retries ?? 3,
      retry_backoff_seconds: config.retry_backoff_seconds ?? 300,
    });
    if (config.recovery_key_ready) {
      setCredentialInfo((current) => current ?? {
        credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
        site_slug: DEFAULT_BACKUP_SITE_SLUG,
        credential_dir: DEFAULT_BACKUP_CREDENTIAL_DIR,
        secrets_fingerprint: config.active_recovery_key_fingerprint ?? "",
        created: false,
        archived_fingerprints: [],
      });
    }
  }, [config]);

  const updateConfig = useUpdateBackupSyncConfigApiV1AdminSystemBackupSyncConfigPut({
    mutation: {
      onSuccess: async () => {
        toast.success(t("common.operationSuccess"));
        await invalidateAll();
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
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

  const retryRun = useRetryBackupSyncApiV1AdminSystemBackupSyncRunsRunIdRetryPost({
    mutation: {
      onSuccess: async () => {
        toast.success(t("system.backupSyncRetried"));
        await invalidateAll();
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const restoreCommit = useRestoreBackupCommitApiV1AdminSystemBackupSyncCommitsCommitIdRestorePost({
    mutation: {
      onSuccess: async () => {
        toast.success(t("common.operationSuccess"));
        await invalidateAll();
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const testConfigMutation = useMutation({
    mutationFn: async (payload: BackupSyncConfigUpdate) =>
      testBackupSyncConfig({
        enabled: true,
        paused: false,
        interval_minutes: payload.interval_minutes ?? 60,
        transport_mode: "sftp",
        site_slug: DEFAULT_BACKUP_SITE_SLUG,
        remote_host: payload.remote_host ?? "",
        remote_port: payload.remote_port ?? 22,
        remote_path: payload.remote_path ?? "",
        remote_username: payload.remote_username ?? "",
        credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
        encrypt_runtime_data: Boolean(payload.encrypt_runtime_data),
        max_retries: payload.max_retries ?? 3,
        retry_backoff_seconds: payload.retry_backoff_seconds ?? 300,
      }),
    onSuccess: (result) => {
      setConfigTestResult(result);
      toast.success(result.ok ? t("system.backupConfigTestSuccess") : t("system.backupConfigTestFailed"));
    },
    onError: (error: any) => {
      setConfigTestResult(null);
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    },
  });

  const latestRun = runs[0];
  const activeQueueItem = queue.find(
    (item) => item.status === "queued" || item.status === "running" || item.status === "retrying",
  );

  const configuredTransportMode = config?.transport_mode ?? "sftp";

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

  const setField = <K extends keyof BackupSyncConfigUpdate>(key: K, value: BackupSyncConfigUpdate[K]) => {
    setConfigTestResult(null);
    setForm((current) => ({ ...current, [key]: value }));
  };

  const savedSnapshot = useMemo(
    () => ({
      remote_host: config?.transport.remote_host ?? "",
      remote_username: config?.transport.remote_username ?? "",
      remote_path: config?.transport.remote_path ?? "",
      remote_port: config?.transport.remote_port ?? 22,
      interval_minutes: config?.interval_minutes ?? 60,
      encrypt_runtime_data: Boolean(config?.encrypt_runtime_data),
      max_retries: config?.max_retries ?? 3,
      retry_backoff_seconds: config?.retry_backoff_seconds ?? 300,
    }),
    [config],
  );

  const currentSnapshot = useMemo(
    () => ({
      remote_host: form.remote_host ?? "",
      remote_username: form.remote_username ?? "",
      remote_path: form.remote_path ?? "",
      remote_port: form.remote_port ?? 22,
      interval_minutes: form.interval_minutes ?? 60,
      encrypt_runtime_data: Boolean(form.encrypt_runtime_data),
      max_retries: form.max_retries ?? 3,
      retry_backoff_seconds: form.retry_backoff_seconds ?? 300,
    }),
    [form],
  );

  const hasConfigChanges = JSON.stringify(savedSnapshot) !== JSON.stringify(currentSnapshot);

  const handleSave = async () => {
    await prepareCredential();
    await updateConfig.mutateAsync({
      data: {
        ...form,
        enabled: true,
        transport_mode: "sftp",
        credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
        site_slug: DEFAULT_BACKUP_SITE_SLUG,
      },
    });
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
        info.created ? t("system.localKeysGenerated") : t("system.localKeysConfirmed"),
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
    await updateConfig.mutateAsync({
      data: {
        ...form,
        enabled: true,
        transport_mode: "sftp",
        credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF,
        site_slug: DEFAULT_BACKUP_SITE_SLUG,
      },
    });
    await triggerSync.mutateAsync();
    setSection("records");
    setRecordsSection("runs");
    toast.success(t("system.firstBackupStarted"));
  };

  const handleTestConfig = async () => {
    await testConfigMutation.mutateAsync(form);
  };

  const openRecoveryKeyDialog = (mode: "export" | "rotate") => {
    setKeyDialogMode(mode);
    setRecoveryPassphrase("");
    setRecoveryKeyResult(null);
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
      setRecoveryKeyResult(result);
      setCredentialInfo({
        credential_ref: result.credential_ref,
        site_slug: result.site_slug,
        credential_dir: result.credential_dir,
        secrets_fingerprint: result.secrets_fingerprint,
        created: false,
        archived_fingerprints: result.archived_fingerprints,
      });
      toast.success(
        keyDialogMode === "rotate" ? t("system.recoveryKeyRotated") : t("system.recoveryKeyExported"),
      );
    } catch (error: any) {
      toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
    } finally {
      setIsRecoveryKeyPending(false);
    }
  };

  const copyRecoveryKey = async (value: string) => {
    await navigator.clipboard.writeText(value);
    setRecoveryKeyDelivered(true);
    const updated = await acknowledgeBackupRecoveryKey({ credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF });
    setCredentialInfo(updated);
    toast.success(t("system.recoveryKeyCopied"));
  };

  const downloadRecoveryKey = async (result: BackupCredentialExportRead) => {
    const blob = new Blob([result.private_key_pem], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = result.filename;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    URL.revokeObjectURL(url);
    setRecoveryKeyDelivered(true);
    const updated = await acknowledgeBackupRecoveryKey({ credential_ref: DEFAULT_BACKUP_CREDENTIAL_REF });
    setCredentialInfo(updated);
  };

  const recoveryKeyReady = Boolean(config?.recovery_key_ready || credentialInfo);
  const recoveryKeyAcknowledged = Boolean(config?.recovery_key_acknowledged || recoveryKeyDelivered);
  const recoveryKeyRequiresDelivery = Boolean(recoveryKeyResult) && !recoveryKeyDelivered;
  const canPersistBackupConfig = recoveryKeyReady && recoveryKeyAcknowledged && !recoveryKeyRequiresDelivery;
  const recoveryKeyActionMode: "export" | "rotate" = recoveryKeyReady ? "rotate" : "export";
  const recoveryKeyActionLabel =
    recoveryKeyActionMode === "rotate" ? t("system.rotateRecoveryKey") : t("system.exportRecoveryKey");

  const isBusy =
    isEnsuringCredential ||
    isRecoveryKeyPending ||
    updateConfig.isPending ||
    triggerSync.isPending ||
    pauseSync.isPending ||
    resumeSync.isPending ||
    retryRun.isPending ||
    restoreCommit.isPending;

  return (
    <div className="space-y-6">
      <PageHeader
        title={t("system.backups")}
        description={t("system.backupsDescription")}
        secondary={
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div className="xl:min-w-[420px] xl:max-w-xl">
              <AdminSectionTabs
                items={sectionItems}
                value={section}
                onValueChange={(value) => setSection(value as BackupsSection)}
                className="w-fit"
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <HeaderMetric
                title={t("system.queueDepth")}
                value={String(queue.filter((item) => item.status !== "completed").length)}
                hint={
                  activeQueueItem
                    ? `${t("common.status")} · ${t(`status.${activeQueueItem.status}`)}`
                    : t("system.noPendingQueue")
                }
              />
              <HeaderMetric
                title={t("system.transportMode")}
                value={configuredTransportMode === "sftp" ? t("system.transportSftp") : configuredTransportMode}
                hint={
                  config?.encrypt_runtime_data
                    ? t("system.runtimeEncryptionEnabled")
                    : t("system.runtimeEncryptionDisabled")
                }
              />
            </div>
          </div>
        }
      />

      <Tabs value={section} onValueChange={(value) => setSection(value as BackupsSection)}>
        <TabsContent value="settings" className="mt-0 space-y-6">
          <ConfigSettingsCard
            eyebrow={t("nav.system")}
            title={t("system.backupBasicSettings")}
            description={
              !recoveryKeyReady ? (
                <span className="font-medium text-amber-600 dark:text-amber-300">
                  {t("system.backupBasicSettingsDescription")}
                </span>
              ) : undefined
            }
            dirty={hasConfigChanges}
            saving={isBusy}
            saveDisabled={isConfigLoading || !canPersistBackupConfig}
            onSave={() => void handleSave()}
            statusIndicator={configTestResult ? {
              label: configTestResult.ok ? t("system.backupConfigTestOk") : t("system.backupConfigTestFailed"),
              tone: testConfigMutation.isPending
                ? "checking"
                : configTestResult.ok
                  ? "available"
                  : "invalid",
            } : undefined}
            testAction={(
              <>
                {config?.enabled ? (
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    className="gap-2"
                    onClick={() => (config?.paused ? resumeSync.mutate() : pauseSync.mutate())}
                    disabled={isBusy}
                  >
                    {config?.paused ? <PlayCircle className="h-4 w-4" /> : <PauseCircle className="h-4 w-4" />}
                    {config?.paused ? t("system.resumeSync") : t("system.pauseSync")}
                  </Button>
                ) : null}
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => void handleTestConfig()}
                  disabled={isBusy}
                >
                  {testConfigMutation.isPending ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Stethoscope className="h-4 w-4" />
                  )}
                  {testConfigMutation.isPending ? t("system.testingBackupConfig") : t("system.testBackupConfig")}
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  className="gap-2"
                  onClick={() => void handleSaveAndRun()}
                  disabled={isBusy || isConfigLoading || !canPersistBackupConfig}
                >
                  <Database className="h-4 w-4" />
                  {t("system.saveAndRunFirstBackup")}
                </Button>
              </>
            )}
          >
            <div className="space-y-5">
              {configTestResult ? (
                <Card surface="soft">
                  <CardContent className="grid gap-3 p-4 text-sm md:grid-cols-3">
                    <MetaLine
                      label={t("system.backupConfigTestStatus")}
                      value={configTestResult.ok ? t("system.backupConfigTestOk") : t("system.backupConfigTestFailed")}
                      tone={configTestResult.ok ? "default" : "error"}
                      formatAsDate={false}
                    />
                    <MetaLine
                      label={t("system.remotePathPreviewTitle")}
                      value={configTestResult.remote_path_preview}
                      formatAsDate={false}
                    />
                    <MetaLine
                      label={t("system.backupConfigTestLatency")}
                      value={configTestResult.latency_ms != null ? `${configTestResult.latency_ms} ms` : "-"}
                      formatAsDate={false}
                    />
                    <div className="md:col-span-3 rounded-[var(--admin-radius-md)] border border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] bg-[rgb(var(--admin-surface-1)/0.36)] px-3 py-2 text-sm text-foreground/85">
                      {configTestResult.summary}
                    </div>
                  </CardContent>
                </Card>
              ) : null}
              {recoveryKeyRequiresDelivery ? (
                <Card surface="soft">
                  <CardContent className="space-y-2 p-4 text-sm">
                    <div className="font-medium text-foreground/90">{t("system.recoveryKeyOneTimeWarning")}</div>
                    <div className="text-muted-foreground">{t("system.recoveryKeyMustBeCopiedBeforeSave")}</div>
                  </CardContent>
                </Card>
              ) : null}
              <div
                className={cn(
                  "grid gap-4",
                  "md:grid-cols-2",
                )}
              >
                <Field
                  label={
                    <LabelWithHelp
                      label={t("system.sshHostLabel")}
                      title={t("system.sshHostLabel")}
                      description={t("system.sshHostDescription")}
                    />
                  }
                >
                  <Input
                    value={form.remote_host ?? ""}
                    placeholder="backup.example.com"
                    onChange={(e) => setField("remote_host", e.target.value)}
                  />
                </Field>
                <Field
                  label={
                    <LabelWithHelp
                      label={t("system.sshUsernameLabel")}
                      title={t("system.sshUsernameLabel")}
                      description={t("system.sshUsernameDescription")}
                    />
                  }
                >
                  <Input
                    value={form.remote_username ?? ""}
                    placeholder="backup-user"
                    onChange={(e) => setField("remote_username", e.target.value)}
                  />
                </Field>
                <Field
                  label={
                    <LabelWithHelp
                      label={t("system.remoteBackupRootLabel")}
                      title={t("system.remoteBackupRootLabel")}
                      description={t("system.remoteBackupRootDescription")}
                    />
                  }
                >
                  <Input
                    value={form.remote_path ?? ""}
                    placeholder={REMOTE_PATH_PLACEHOLDER}
                    onChange={(e) => setField("remote_path", e.target.value)}
                  />
                </Field>
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
                    value={form.interval_minutes ?? 60}
                    onChange={(e) => setField("interval_minutes", Number(e.target.value || 60))}
                  />
                </Field>
              </div>

              <CollapsibleSection
                title={t("system.advancedOptions")}
                badge={t("common.optional")}
                defaultOpen={!credentialInfo}
              >
                <div className="space-y-4">
                  <div className="grid gap-4 md:grid-cols-2">
                    <Field
                      label={
                        <LabelWithHelp
                          label={t("system.runtimeEncryptionLabel")}
                          title={t("system.runtimeEncryptionLabel")}
                          description={t("system.runtimeEncryptionDescription")}
                        />
                      }
                    >
                      <div
                        className={cn(
                          "flex h-10 items-center justify-between rounded-[var(--admin-radius-md)] border px-3 transition-colors",
                          form.encrypt_runtime_data
                            ? "border-emerald-500/30 bg-emerald-500/8"
                            : "border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] bg-[rgb(var(--admin-surface-1)/0.36)]",
                        )}
                      >
                        <span className="mr-3 text-xs text-muted-foreground">
                          {form.encrypt_runtime_data
                            ? t("system.runtimeEncryptionEnabled")
                            : t("system.runtimeEncryptionDisabled")}
                        </span>
                        <CompactSwitch
                          checked={Boolean(form.encrypt_runtime_data)}
                          onCheckedChange={(checked) => setField("encrypt_runtime_data", checked)}
                          ariaLabel={t("system.runtimeEncryptionLabel")}
                          disabled={isBusy}
                        />
                      </div>
                    </Field>
                    <Field
                      label={
                        <LabelWithHelp
                          label={t("system.recoveryKeyActions")}
                          title={t("system.recoveryKeyActions")}
                          description={t("system.localBackupKeyDirDescription")}
                        />
                      }
                    >
                      <div className="space-y-2">
                        {credentialInfo ? <Input value={credentialInfo.credential_dir} readOnly /> : null}
                        {credentialInfo ? (
                          <div className="text-xs text-muted-foreground">
                            {t("system.recoveryKeyFingerprint")}: {credentialInfo.secrets_fingerprint}
                          </div>
                        ) : null}
                        <div className="flex flex-wrap gap-2">
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            className={cn(
                              "border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))]",
                              recoveryKeyReady
                                ? "bg-[rgb(var(--admin-surface-1)/0.36)]"
                                : "bg-sky-500/10 text-sky-700 hover:bg-sky-500/15 dark:text-sky-200",
                            )}
                            onClick={() => openRecoveryKeyDialog(recoveryKeyActionMode)}
                            disabled={isBusy}
                          >
                            {recoveryKeyActionLabel}
                          </Button>
                        </div>
                      </div>
                    </Field>
                  </div>
                  <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
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
                        onChange={(e) => setField("remote_port", Number(e.target.value || 22))}
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
                        onChange={(e) => setField("max_retries", Number(e.target.value || 0))}
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
                        onChange={(e) => setField("retry_backoff_seconds", Number(e.target.value || 300))}
                      />
                    </Field>
                  </div>
                </div>
              </CollapsibleSection>
            </div>
          </ConfigSettingsCard>
        </TabsContent>

        <TabsContent value="records" className="mt-0 space-y-6">
          <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <AdminSectionTabs
              items={[
                { value: "runs", label: t("system.runRecords") },
                { value: "commits", label: t("system.commitRecords") },
              ]}
              value={recordsSection}
              onValueChange={(value) => setRecordsSection(value as BackupRecordsSection)}
              size="sm"
              className="w-fit"
            />
            <div className="flex flex-wrap items-center gap-2 lg:justify-end">
              <Button variant="outline" onClick={() => invalidateAll()} disabled={isBusy}>
                <RefreshCcw className="mr-2 h-4 w-4" />
                {t("common.refresh")}
              </Button>
              <Button onClick={() => triggerSync.mutate()} disabled={isBusy}>
                <Database className="mr-2 h-4 w-4" />
                {t("system.triggerBackup")}
              </Button>
            </div>
          </div>

          <Tabs value={recordsSection} onValueChange={(value) => setRecordsSection(value as BackupRecordsSection)}>
            <TabsContent value="runs" className="mt-0">
              <Card>
                <CardHeader>
                  <CardTitle>{t("system.runRecords")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataTable<BackupRunRead>
                    columns={[
                      { header: t("common.status"), accessor: (row) => <StatusBadge status={row.status} /> },
                      { header: t("system.transportMode"), accessor: (row) => row.transport || "-" },
                      { header: t("system.triggerKind"), accessor: (row) => row.trigger_kind || "-" },
                      { header: t("system.startedAt"), accessor: (row) => formatDate(row.started_at) },
                      { header: t("system.completed"), accessor: (row) => formatDate(row.finished_at) },
                      {
                        header: t("common.actions"),
                        accessor: (row) =>
                          row.status === "failed" ? (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={(event) => {
                                event.stopPropagation();
                                retryRun.mutate({ runId: row.id });
                              }}
                            >
                              <RotateCcw className="mr-1 h-4 w-4" />
                              {t("system.retryRun")}
                            </Button>
                          ) : (
                            "-"
                          ),
                      },
                    ]}
                    data={runs}
                    total={runs.length}
                    isLoading={isRunsLoading}
                    renderExpandedRow={(row) => (
                      <div className="space-y-2 py-4 text-sm">
                        <div>{row.message || row.last_error || t("system.none")}</div>
                        <code className="block whitespace-pre-wrap break-all text-xs text-muted-foreground">
                          {JSON.stringify(row.stats_json ?? {}, null, 2)}
                        </code>
                      </div>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="commits" className="mt-0">
              <Card>
                <CardHeader>
                  <CardTitle>{t("system.commitRecords")}</CardTitle>
                </CardHeader>
                <CardContent>
                  <DataTable<BackupCommitRead>
                    columns={[
                      { header: t("system.transportMode"), accessor: "transport" },
                      { header: t("system.triggerKind"), accessor: "trigger_kind" },
                      { header: t("system.remoteCommitId"), accessor: "remote_commit_id" },
                      {
                        header: t("system.completed"),
                        accessor: (row) => formatDate(row.snapshot_finished_at || row.created_at),
                      },
                      { header: t("system.lastRestoreAt"), accessor: (row) => formatDate(row.restored_at) },
                      {
                        header: t("common.actions"),
                        accessor: (row) => (
                          <Button
                            variant="outline"
                            size="sm"
                            disabled={restoreCommit.isPending}
                            onClick={(event) => {
                              event.stopPropagation();
                              if (confirm(t("system.restoreConfirm"))) {
                                restoreCommit.mutate({ commitId: row.id });
                              }
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
                    isLoading={isCommitsLoading}
                    renderExpandedRow={(row) => (
                      <div className="space-y-2 py-4 text-sm">
                        <div className="text-muted-foreground">{row.backup_path || "-"}</div>
                        <code className="block whitespace-pre-wrap break-all text-xs text-muted-foreground">
                          {JSON.stringify(row.datasets, null, 2)}
                        </code>
                      </div>
                    )}
                  />
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          {latestRun?.last_error ? (
            <Card surface="soft" className="border-red-200/60">
              <CardContent className="p-4 text-sm text-red-600">{latestRun.last_error}</CardContent>
            </Card>
          ) : null}
        </TabsContent>
      </Tabs>

      <Dialog open={keyDialogOpen} onOpenChange={setKeyDialogOpen}>
        <DialogContent className="max-w-2xl rounded-2xl">
          <DialogHeader className="text-left">
            <DialogTitle>
              {keyDialogMode === "rotate" ? t("system.rotateRecoveryKey") : t("system.exportRecoveryKey")}
            </DialogTitle>
            <DialogDescription>
              {keyDialogMode === "rotate"
                ? t("system.rotateRecoveryKeyDescription")
                : t("system.exportRecoveryKeyDescription")}
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            {!recoveryKeyResult ? (
              <form
                className="space-y-4"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (isRecoveryKeyPending || recoveryPassphrase.length < 8) {
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
                    onChange={(event) => setRecoveryPassphrase(event.target.value)}
                    placeholder="********"
                  />
                </Field>
                <div className="flex justify-end gap-2">
                    <Button type="button" variant="outline" onClick={() => setKeyDialogOpen(false)} disabled={isRecoveryKeyPending}>
                      {t("common.cancel")}
                    </Button>
                  <Button type="submit" disabled={isRecoveryKeyPending || recoveryPassphrase.length < 8}>
                    {keyDialogMode === "rotate" ? t("system.rotateRecoveryKey") : t("system.exportRecoveryKey")}
                  </Button>
                </div>
              </form>
            ) : (
              <>
                <div className="rounded-[var(--admin-radius-md)] border border-amber-400/30 bg-amber-500/10 px-4 py-3 text-sm text-amber-900 dark:text-amber-100">
                  {t("system.recoveryKeyOneTimeWarning")}
                </div>
                <Field
                  label={
                    <LabelWithHelp
                      label={t("system.recoveryKeyPrivatePem")}
                      title={t("system.recoveryKeyPrivatePem")}
                      description={t("system.recoveryKeyPrivatePemDescription")}
                    />
                  }
                >
                  <Textarea value={recoveryKeyResult.private_key_pem} readOnly rows={10} />
                </Field>
                <div className="flex flex-wrap justify-end gap-2">
                  <Button variant="outline" onClick={() => void copyRecoveryKey(recoveryKeyResult.private_key_pem)}>
                    <Copy className="mr-2 h-4 w-4" />
                    {t("system.copyRecoveryKey")}
                  </Button>
                  <Button variant="outline" onClick={() => downloadRecoveryKey(recoveryKeyResult)}>
                    <Download className="mr-2 h-4 w-4" />
                    {t("system.downloadRecoveryKey")}
                  </Button>
                  <Button onClick={() => setKeyDialogOpen(false)}>{t("common.done")}</Button>
                </div>
              </>
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function HeaderMetric({
  title,
  value,
  hint,
}: {
  title: string;
  value: string;
  hint: string;
}) {
  return (
    <div className="min-w-0 rounded-[var(--admin-radius-lg)] border border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] bg-[rgb(var(--admin-surface-1)/0.34)] px-4 py-3">
      <div className="text-xs text-muted-foreground">{title}</div>
      <div className="mt-1 truncate text-base font-semibold text-foreground/95">{value}</div>
      <div className="mt-1 truncate text-xs text-muted-foreground">{hint}</div>
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
      {description ? <span className="block text-xs leading-5 text-muted-foreground">{description}</span> : null}
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
      <div className={tone === "error" ? "mt-1 text-sm text-red-600" : "mt-1 text-sm text-foreground/90"}>
        {value ? (formatAsDate ? formatDate(value) || value : value) : "-"}
      </div>
    </div>
  );
}
