import { type ReactNode, useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
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
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/PageHeader";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/Select";
import { useI18n } from "@/i18n";
import { formatDate } from "@/lib/utils";
import { Clock3, Database, PauseCircle, PlayCircle, RefreshCcw, RotateCcw, ShieldCheck } from "lucide-react";
import { toast } from "sonner";

const emptyForm: BackupSyncConfigUpdate = {
  enabled: false,
  paused: false,
  interval_minutes: 60,
  transport_mode: "receiver",
  site_slug: "aerisun",
  receiver_base_url: "",
  remote_host: "",
  remote_port: 22,
  remote_path: "",
  remote_username: "",
  credential_ref: "",
  age_public_key_fingerprint: "",
  max_retries: 3,
  retry_backoff_seconds: 300,
};

export default function BackupsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<BackupSyncConfigUpdate>(emptyForm);

  const { data: configRaw, isLoading: isConfigLoading } =
    useGetBackupSyncConfigApiV1AdminSystemBackupSyncConfigGet();
  const { data: queueRaw, isLoading: isQueueLoading } =
    useListBackupSyncQueueApiV1AdminSystemBackupSyncQueueGet();
  const { data: runsRaw, isLoading: isRunsLoading } =
    useListBackupSyncRunsApiV1AdminSystemBackupSyncRunsGet();
  const { data: commitsRaw, isLoading: isCommitsLoading } =
    useListBackupSyncCommitsApiV1AdminSystemBackupSyncCommitsGet();

  const config = configRaw?.data as BackupSyncConfig | undefined;
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
      enabled: config.enabled ?? false,
      paused: config.paused ?? false,
      interval_minutes: config.interval_minutes ?? 60,
      transport_mode: config.transport_mode ?? "receiver",
      site_slug: config.site_slug ?? "aerisun",
      receiver_base_url: config.transport.receiver_base_url ?? "",
      remote_host: config.transport.remote_host ?? "",
      remote_port: config.transport.remote_port ?? 22,
      remote_path: config.transport.remote_path ?? "",
      remote_username: config.transport.remote_username ?? "",
      credential_ref: config.credential_ref ?? "",
      age_public_key_fingerprint: config.age_public_key_fingerprint ?? "",
      max_retries: config.max_retries ?? 3,
      retry_backoff_seconds: config.retry_backoff_seconds ?? 300,
    });
  }, [config]);

  const updateConfig = useUpdateBackupSyncConfigApiV1AdminSystemBackupSyncConfigPut({
    mutation: {
      onSuccess: async () => {
        toast.success(t("common.operationSuccess"));
        await invalidateAll();
      },
      onError: (error: any) => {
        const message = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(message);
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
        const message = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(message);
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
        const message = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(message);
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
        const message = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(message);
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
        const message = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(message);
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
        const message = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(message);
      },
    },
  });

  const latestCommit = commits[0];
  const latestRun = runs[0];
  const activeQueueItem = queue.find((item) => item.status === "queued" || item.status === "running" || item.status === "retrying");

  const setField = <K extends keyof BackupSyncConfigUpdate>(key: K, value: BackupSyncConfigUpdate[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const handleSave = async () => {
    await updateConfig.mutateAsync({ data: form });
  };

  const isBusy =
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
        actions={
          <>
            <Button variant="outline" onClick={() => invalidateAll()} disabled={isBusy}>
              <RefreshCcw className="mr-2 h-4 w-4" />
              {t("common.refresh")}
            </Button>
            <Button onClick={() => triggerSync.mutate()} disabled={isBusy}>
              <Database className="mr-2 h-4 w-4" />
              {t("system.triggerBackup")}
            </Button>
          </>
        }
      />

      <div className="grid gap-4 lg:grid-cols-3">
        <SummaryCard
          icon={<Database className="h-4 w-4" />}
          title={t("system.latestCommit")}
          value={latestCommit ? formatDate(latestCommit.snapshot_finished_at || latestCommit.created_at) : t("common.noData")}
          hint={latestCommit ? latestCommit.transport : t("system.backupNotConfigured")}
        />
        <SummaryCard
          icon={<Clock3 className="h-4 w-4" />}
          title={t("system.queueDepth")}
          value={String(queue.filter((item) => item.status !== "completed").length)}
          hint={activeQueueItem ? `${t("common.status")} · ${t(`status.${activeQueueItem.status}`)}` : t("system.noPendingQueue")}
        />
        <SummaryCard
          icon={<ShieldCheck className="h-4 w-4" />}
          title={t("system.protectionStatus")}
          value={config?.transport_mode === "receiver" ? t("system.transportReceiver") : t("system.transportSftp")}
          hint={config?.age_public_key_fingerprint || t("system.missingFingerprint")}
        />
      </div>

      <Card>
        <CardHeader className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div>
            <CardTitle>{t("system.backupSyncConfig")}</CardTitle>
            <p className="text-sm text-muted-foreground">{t("system.backupSyncConfigDescription")}</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button
              variant="outline"
              onClick={() => (config?.paused ? resumeSync.mutate() : pauseSync.mutate())}
              disabled={isBusy}
            >
              {config?.paused ? <PlayCircle className="mr-2 h-4 w-4" /> : <PauseCircle className="mr-2 h-4 w-4" />}
              {config?.paused ? t("system.resumeSync") : t("system.pauseSync")}
            </Button>
            <Button onClick={handleSave} disabled={isBusy || isConfigLoading}>
              {t("common.save")}
            </Button>
          </div>
        </CardHeader>
        <CardContent className="space-y-5">
          <AppleSwitch
            checked={Boolean(form.enabled)}
            onCheckedChange={(checked) => setField("enabled", checked)}
            label={t("system.syncEnabled")}
            description={t("system.syncEnabledDescription")}
            disabled={isBusy}
          />
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            <Field label={t("system.transportMode")}>
              <Select
                value={form.transport_mode ?? "receiver"}
                onValueChange={(value) => setField("transport_mode", value)}
              >
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="receiver">{t("system.transportReceiver")}</SelectItem>
                  <SelectItem value="sftp">{t("system.transportSftp")}</SelectItem>
                </SelectContent>
              </Select>
            </Field>
            <Field label={t("system.siteSlug")}>
              <Input value={form.site_slug ?? ""} onChange={(e) => setField("site_slug", e.target.value)} />
            </Field>
            <Field label={t("system.credentialRef")}>
              <Input value={form.credential_ref ?? ""} onChange={(e) => setField("credential_ref", e.target.value)} />
            </Field>
            <Field label={t("system.syncIntervalMinutes")}>
              <Input
                type="number"
                min={1}
                value={form.interval_minutes ?? 60}
                onChange={(e) => setField("interval_minutes", Number(e.target.value || 60))}
              />
            </Field>
            <Field label={t("system.maxRetries")}>
              <Input
                type="number"
                min={0}
                value={form.max_retries ?? 3}
                onChange={(e) => setField("max_retries", Number(e.target.value || 0))}
              />
            </Field>
            <Field label={t("system.retryBackoffSeconds")}>
              <Input
                type="number"
                min={30}
                value={form.retry_backoff_seconds ?? 300}
                onChange={(e) => setField("retry_backoff_seconds", Number(e.target.value || 300))}
              />
            </Field>
            <Field label={t("system.receiverUrl")}>
              <Input
                value={form.receiver_base_url ?? ""}
                onChange={(e) => setField("receiver_base_url", e.target.value)}
                disabled={form.transport_mode !== "receiver"}
              />
            </Field>
            <Field label={t("system.remoteHost")}>
              <Input
                value={form.remote_host ?? ""}
                onChange={(e) => setField("remote_host", e.target.value)}
                disabled={form.transport_mode !== "sftp"}
              />
            </Field>
            <Field label={t("system.remotePort")}>
              <Input
                type="number"
                min={1}
                value={form.remote_port ?? 22}
                onChange={(e) => setField("remote_port", Number(e.target.value || 22))}
                disabled={form.transport_mode !== "sftp"}
              />
            </Field>
            <Field label={t("system.remotePath")}>
              <Input
                value={form.remote_path ?? ""}
                onChange={(e) => setField("remote_path", e.target.value)}
                disabled={form.transport_mode !== "sftp"}
              />
            </Field>
            <Field label={t("system.remoteUsername")}>
              <Input
                value={form.remote_username ?? ""}
                onChange={(e) => setField("remote_username", e.target.value)}
                disabled={form.transport_mode !== "sftp"}
              />
            </Field>
            <Field label={t("system.ageFingerprint")}>
              <Input
                value={form.age_public_key_fingerprint ?? ""}
                onChange={(e) => setField("age_public_key_fingerprint", e.target.value)}
              />
            </Field>
          </div>
          <div className="grid gap-3 md:grid-cols-3">
            <MetaLine label={t("system.lastScheduledAt")} value={config?.last_scheduled_at} />
            <MetaLine label={t("system.lastSyncedAt")} value={config?.last_synced_at} />
            <MetaLine
              label={t("system.lastError")}
              value={config?.last_error || t("system.none")}
              tone={config?.last_error ? "error" : "default"}
              formatAsDate={false}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t("system.queueRecords")}</CardTitle>
        </CardHeader>
        <CardContent>
          <DataTable<BackupQueueItemRead>
            columns={[
              { header: t("common.status"), accessor: (row) => <StatusBadge status={row.status} /> },
              { header: t("system.transportMode"), accessor: "transport" },
              { header: t("system.triggerKind"), accessor: "trigger_kind" },
              { header: t("system.retryCount"), accessor: (row) => row.retry_count },
              { header: t("system.nextRetryAt"), accessor: (row) => formatDate(row.next_retry_at) },
              { header: t("system.created"), accessor: (row) => formatDate(row.created_at) },
            ]}
            data={queue}
            total={queue.length}
            isLoading={isQueueLoading}
            renderExpandedRow={(row) => (
              <div className="space-y-2 py-4 text-sm">
                <div className="text-muted-foreground">{row.last_error || t("system.none")}</div>
                <code className="block whitespace-pre-wrap break-all text-xs text-muted-foreground">
                  {JSON.stringify(row.dataset_versions, null, 2)}
                </code>
              </div>
            )}
          />
        </CardContent>
      </Card>

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
              { header: t("system.completed"), accessor: (row) => formatDate(row.snapshot_finished_at || row.created_at) },
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

      {latestRun?.last_error ? (
        <Card surface="soft" className="border-red-200/60">
          <CardContent className="p-4 text-sm text-red-600">{latestRun.last_error}</CardContent>
        </Card>
      ) : null}
    </div>
  );
}

function SummaryCard({
  icon,
  title,
  value,
  hint,
}: {
  icon: ReactNode;
  title: string;
  value: string;
  hint: string;
}) {
  return (
    <Card>
      <CardContent className="flex items-start gap-4 p-5">
        <div className="rounded-full bg-[rgb(var(--admin-accent-rgb)/0.12)] p-3 text-[rgb(var(--admin-accent-rgb))]">
          {icon}
        </div>
        <div className="min-w-0">
          <div className="text-sm text-muted-foreground">{title}</div>
          <div className="mt-1 text-lg font-semibold text-foreground/95">{value}</div>
          <div className="mt-1 text-xs text-muted-foreground">{hint}</div>
        </div>
      </CardContent>
    </Card>
  );
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="space-y-2">
      <span className="text-sm font-medium text-foreground/90">{label}</span>
      {children}
    </label>
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
