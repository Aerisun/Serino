import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { listAuditLogs } from "@/api/endpoints/system";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { AuditLog } from "@/types/models";

export default function AuditLogPage() {
  const { t } = useI18n();
  const [page, setPage] = useState(1);

  const { data, isLoading } = useQuery({
    queryKey: ["audit-logs", page],
    queryFn: () => listAuditLogs({ page }),
  });

  return (
    <div>
      <PageHeader title={t("system.auditLog")} description={t("system.auditLogDescription")} />
      <div className="border rounded-lg">
        <DataTable<AuditLog>
          columns={[
            { header: t("system.action"), accessor: (row) => <Badge variant="outline">{row.action}</Badge> },
            { header: t("system.actor"), accessor: (row) => `${row.actor_type}${row.actor_id ? `:${row.actor_id}` : ""}` },
            { header: t("system.target"), accessor: (row) => row.target_type ? `${row.target_type}:${row.target_id || ""}` : "-" },
            { header: t("common.payload"), accessor: (row) => <code className="text-xs max-w-xs truncate block">{JSON.stringify(row.payload)}</code> },
            { header: t("common.date"), accessor: (row) => formatDate(row.created_at) },
          ]}
          data={data?.items ?? []}
          total={data?.total ?? 0}
          page={page}
          pageSize={data?.page_size ?? 20}
          onPageChange={setPage}
          isLoading={isLoading}
        />
      </div>
    </div>
  );
}
