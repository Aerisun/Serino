import { useQueryClient } from "@tanstack/react-query";
import {
  useListBackupsApiV1AdminSystemBackupsGet,
  useTriggerBackupApiV1AdminSystemBackupsPost,
  useRestoreBackupApiV1AdminSystemBackupsSnapshotIdRestorePost,
  getListBackupsApiV1AdminSystemBackupsGetQueryKey,
} from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Database, RotateCcw } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import type { BackupSnapshotRead } from "@serino/api-client/models";

export default function BackupsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const { data: raw, isLoading } = useListBackupsApiV1AdminSystemBackupsGet();
  const data = raw?.data as BackupSnapshotRead[] | undefined;

  const create = useTriggerBackupApiV1AdminSystemBackupsPost({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListBackupsApiV1AdminSystemBackupsGetQueryKey() }); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  const restore = useRestoreBackupApiV1AdminSystemBackupsSnapshotIdRestorePost({
    mutation: {
      onSuccess: () => { queryClient.invalidateQueries({ queryKey: getListBackupsApiV1AdminSystemBackupsGetQueryKey() }); toast.success(t("common.operationSuccess")); },
      onError: (error: any) => { const msg = error?.response?.data?.detail || t("common.operationFailed"); toast.error(msg); },
    },
  });

  return (
    <div>
      <PageHeader
        title={t("system.backups")}
        description={t("system.backupsDescription")}
        actions={
          <Button onClick={() => create.mutate()} disabled={create.isPending}>
            <Database className="h-4 w-4 mr-2" /> {create.isPending ? t("common.creating") : t("system.triggerBackup")}
          </Button>
        }
      />
      <div className="border rounded-lg">
        <DataTable<BackupSnapshotRead>
          columns={[
            { header: t("system.snapshotType"), accessor: "snapshot_type" },
            { header: t("common.status"), accessor: (row) => <StatusBadge status={row.status} /> },
            { header: t("system.completed"), accessor: (row) => formatDate(row.completed_at) },
            { header: t("system.created"), accessor: (row) => formatDate(row.created_at) },
            {
              header: t("common.actions"),
              accessor: (row) => (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={row.status !== "completed"}
                  onClick={(e) => { e.stopPropagation(); if (confirm(t("system.restoreConfirm"))) restore.mutate({ snapshotId: row.id }); }}
                >
                  <RotateCcw className="h-4 w-4 mr-1" /> {t("system.restore")}
                </Button>
              ),
            },
          ]}
          data={data ?? []}
          total={data?.length ?? 0}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
