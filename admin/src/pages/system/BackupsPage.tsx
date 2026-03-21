import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listBackups, triggerBackup, restoreBackup } from "@/api/endpoints/system";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { Button } from "@/components/ui/Button";
import { Database, RotateCcw } from "lucide-react";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { BackupSnapshot } from "@/types/models";

export default function BackupsPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();

  const { data, isLoading } = useQuery({
    queryKey: ["backups"],
    queryFn: listBackups,
  });

  const create = useMutation({
    mutationFn: triggerBackup,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["backups"] }),
  });

  const restore = useMutation({
    mutationFn: (id: string) => restoreBackup(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["backups"] }),
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
        <DataTable<BackupSnapshot>
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
                  onClick={(e) => { e.stopPropagation(); if (confirm(t("system.restoreConfirm"))) restore.mutate(row.id); }}
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
