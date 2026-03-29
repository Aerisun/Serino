import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getListAuditLogsApiV1AdminSystemAuditLogsGetQueryKey,
  useListAuditLogsApiV1AdminSystemAuditLogsGet,
} from "@serino/api-client/admin";
import type { AuditLogRead } from "@serino/api-client/models";
import { toast } from "sonner";
import { PageHeader } from "@/components/PageHeader";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/Tabs";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import {
  type ConfigRevisionListItem,
  getConfigRevisionDetail,
  listConfigRevisions,
  restoreConfigRevision,
} from "@/api/endpoints/system";

function ConfigRevisionExpandedRow({ revisionId }: { revisionId: string }) {
  const { t } = useI18n();
  const { data, isLoading } = useQuery({
    queryKey: ["system", "config-revision-detail", revisionId],
    queryFn: () => getConfigRevisionDetail(revisionId),
  });

  if (isLoading || !data) {
    return <div className="py-4 text-sm text-muted-foreground">{t("common.loading")}</div>;
  }

  return (
    <div className="space-y-4 py-4">
      <div className="grid gap-4 lg:grid-cols-2">
        <div className="space-y-2">
          <div className="text-sm font-medium">{t("auditLog.diffLines")}</div>
          {data.diff_lines.length === 0 ? (
            <div className="text-sm text-muted-foreground">{t("auditLog.noDiff")}</div>
          ) : (
            <div className="overflow-hidden rounded-md border border-border/70">
              <table className="w-full text-sm">
                <thead className="bg-muted/40">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium">{t("auditLog.changedField")}</th>
                    <th className="px-3 py-2 text-left font-medium">{t("auditLog.beforePreview")}</th>
                    <th className="px-3 py-2 text-left font-medium">{t("auditLog.afterPreview")}</th>
                  </tr>
                </thead>
                <tbody>
                  {data.diff_lines.map((line) => (
                    <tr key={line.path} className="border-t border-border/50">
                      <td className="px-3 py-2 align-top font-mono text-xs">{line.path}</td>
                      <td className="px-3 py-2 align-top text-xs">{line.before}</td>
                      <td className="px-3 py-2 align-top text-xs">{line.after}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="grid gap-4">
          <div className="space-y-2">
            <div className="text-sm font-medium">{t("auditLog.beforePreview")}</div>
            <pre className="max-h-72 overflow-auto rounded-md border border-border/70 bg-muted/20 p-3 text-xs">
              {JSON.stringify(data.before_preview, null, 2)}
            </pre>
          </div>
          <div className="space-y-2">
            <div className="text-sm font-medium">{t("auditLog.afterPreview")}</div>
            <pre className="max-h-72 overflow-auto rounded-md border border-border/70 bg-muted/20 p-3 text-xs">
              {JSON.stringify(data.after_preview, null, 2)}
            </pre>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function AuditLogPage() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [view, setView] = useState<"config" | "audit">("config");
  const [page, setPage] = useState(1);
  const [actionFilter, setActionFilter] = useState("");
  const [resourceFilter, setResourceFilter] = useState("");
  const [dateFrom, setDateFrom] = useState("");
  const [dateTo, setDateTo] = useState("");

  const auditParams = useMemo(
    () => ({
      page,
      action: actionFilter || undefined,
      date_from: dateFrom || undefined,
      date_to: dateTo || undefined,
    }),
    [actionFilter, dateFrom, dateTo, page],
  );

  const { data: rawAudit, isLoading: isAuditLoading } = useListAuditLogsApiV1AdminSystemAuditLogsGet(
    auditParams,
    {
      query: {
        enabled: view === "audit",
      },
    },
  );
  const auditData = rawAudit?.data;

  const { data: configData, isLoading: isConfigLoading } = useQuery({
    queryKey: ["system", "config-revisions", page, resourceFilter, dateFrom, dateTo],
    queryFn: () =>
      listConfigRevisions({
        page,
        resource_key: resourceFilter || undefined,
        date_from: dateFrom || undefined,
        date_to: dateTo || undefined,
      }),
    enabled: view === "config",
  });

  const restoreMutation = useMutation({
    mutationFn: (revisionId: string) => restoreConfigRevision(revisionId, { target: "before" }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["system", "config-revisions"] });
      queryClient.invalidateQueries({ queryKey: ["system", "config-revision-detail"] });
      queryClient.invalidateQueries({ queryKey: getListAuditLogsApiV1AdminSystemAuditLogsGetQueryKey() });
      toast.success(t("common.operationSuccess"));
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : t("common.operationFailed"));
    },
  });

  const handleFilter = () => {
    setPage(1);
  };

  const handleClear = () => {
    setActionFilter("");
    setResourceFilter("");
    setDateFrom("");
    setDateTo("");
    setPage(1);
  };

  const handleRestore = (revisionId: string) => {
    if (!window.confirm(t("auditLog.restoreConfigConfirm"))) {
      return;
    }
    restoreMutation.mutate(revisionId);
  };

  return (
    <div>
      <PageHeader title={t("system.auditLog")} description={t("system.auditLogDescription")} />

      <Tabs
        value={view}
        onValueChange={(next) => {
          setView(next as "config" | "audit");
          setPage(1);
        }}
      >
        <TabsList className="mb-4">
          <TabsTrigger value="config">{t("auditLog.viewConfigHistory")}</TabsTrigger>
          <TabsTrigger value="audit">{t("auditLog.viewAuditLog")}</TabsTrigger>
        </TabsList>

        <div className="mb-4 flex flex-wrap items-end gap-3">
          {view === "config" ? (
            <div className="flex flex-col gap-1">
              <label className="text-sm text-muted-foreground">{t("auditLog.filterByResource")}</label>
              <input
                type="text"
                value={resourceFilter}
                onChange={(e) => setResourceFilter(e.target.value)}
                placeholder={t("auditLog.filterByResource")}
                className="h-9 rounded-md border border-input bg-background px-3 text-sm"
              />
            </div>
          ) : (
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
          )}
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

        <TabsContent value="config">
          <div className="border rounded-lg">
            <DataTable<ConfigRevisionListItem>
              columns={[
                { header: t("auditLog.resource"), accessor: (row) => <Badge variant="outline">{row.resource_label}</Badge> },
                { header: t("system.action"), accessor: (row) => <Badge variant="secondary">{row.operation}</Badge> },
                { header: t("auditLog.summary"), accessor: "summary" },
                { header: t("system.actor"), accessor: (row) => row.actor_id || "-" },
                { header: t("auditLog.changedFields"), accessor: (row) => row.changed_fields.length },
                { header: t("common.date"), accessor: (row) => formatDate(row.created_at) },
                {
                  header: t("common.actions"),
                  accessor: (row) => (
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={restoreMutation.isPending}
                      onClick={(event) => {
                        event.stopPropagation();
                        handleRestore(row.id);
                      }}
                    >
                      {t("system.restore")}
                    </Button>
                  ),
                },
              ]}
              data={configData?.items ?? []}
              total={configData?.total ?? 0}
              page={page}
              pageSize={configData?.page_size ?? 20}
              onPageChange={setPage}
              isLoading={isConfigLoading}
              renderExpandedRow={(row) => <ConfigRevisionExpandedRow revisionId={row.id} />}
            />
          </div>
        </TabsContent>

        <TabsContent value="audit">
          <div className="border rounded-lg">
            <DataTable<AuditLogRead>
              columns={[
                { header: t("system.action"), accessor: (row) => <Badge variant="outline">{row.action}</Badge> },
                {
                  header: t("system.actor"),
                  accessor: (row) => `${row.actor_type}${row.actor_id ? `:${row.actor_id}` : ""}`,
                },
                {
                  header: t("system.target"),
                  accessor: (row) => (row.target_type ? `${row.target_type}:${row.target_id || ""}` : "-"),
                },
                {
                  header: t("common.payload"),
                  accessor: (row) => <code className="text-xs max-w-xs truncate block">{JSON.stringify(row.payload)}</code>,
                },
                { header: t("common.date"), accessor: (row) => formatDate(row.created_at) },
              ]}
              data={auditData?.items ?? []}
              total={auditData?.total ?? 0}
              page={page}
              pageSize={auditData?.page_size ?? 20}
              onPageChange={setPage}
              isLoading={isAuditLoading}
            />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
