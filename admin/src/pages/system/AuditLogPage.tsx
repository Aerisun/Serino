import { useState } from "react";
import {
  useListAuditLogsApiV1AdminSystemAuditLogsGet,
} from "@/api/generated/admin/admin";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import type { AuditLogRead } from "@/api/generated/model";

export default function AuditLogPage() {
  const { t } = useI18n();
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const { data: raw, isLoading } = useListAuditLogsApiV1AdminSystemAuditLogsGet({
    page,
    action: actionFilter || undefined,
    date_from: dateFrom || undefined,
    date_to: dateTo || undefined,
  });
  const data = raw?.data;

  const handleFilter = () => {
    setPage(1);
  };

  const handleClear = () => {
    setActionFilter("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };

  return (
    <div>
      <PageHeader title={t("system.auditLog")} description={t("system.auditLogDescription")} />

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <label className="text-sm text-muted-foreground">{t("auditLog.filterByAction")}</label>
          <input
            type="text"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
            placeholder={t("auditLog.filterByAction")}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-sm text-muted-foreground">{t("auditLog.dateFrom")}</label>
          <input
            type="date"
            value={dateFrom}
            onChange={(e) => setDateFrom(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          />
        </div>
        <div className="flex flex-col gap-1">
          <label className="text-sm text-muted-foreground">{t("auditLog.dateTo")}</label>
          <input
            type="date"
            value={dateTo}
            onChange={(e) => setDateTo(e.target.value)}
            className="h-9 rounded-md border border-input bg-background px-3 text-sm"
          />
        </div>
        <Button size="sm" onClick={handleFilter}>
          {t("auditLog.filter")}
        </Button>
        <Button size="sm" variant="outline" onClick={handleClear}>
          {t("auditLog.clearFilter")}
        </Button>
      </div>

      <div className="border rounded-lg">
        <DataTable<AuditLogRead>
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
