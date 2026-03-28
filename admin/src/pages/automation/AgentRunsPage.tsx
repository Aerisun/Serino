import { useGetRunsApiV1AdminAutomationRunsGet } from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { useNavigate } from "react-router-dom";
import { useI18n } from "@/i18n";
import type { AgentRunRead } from "@serino/api-client/models";

export default function AgentRunsPage() {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { data: raw, isLoading } = useGetRunsApiV1AdminAutomationRunsGet();
  const items = (raw?.data ?? []) as AgentRunRead[];

  return (
    <div>
      <PageHeader title={t("automation.runs")} description={t("automation.runsDescription")} />
      <AdminSurface eyebrow="Automation" title={t("automation.runs")} description={t("automation.runsDescription")}>
        <DataTable
          columns={[
            { header: "ID", accessor: (row) => <code className="text-xs">{row.id}</code> },
            { header: t("automation.workflow"), accessor: "workflow_key" },
            {
              header: t("automation.status"),
              accessor: (row) => <Badge variant="outline">{row.status}</Badge>,
            },
            { header: t("automation.trigger"), accessor: (row) => row.trigger_event || row.trigger_kind },
            { header: t("automation.target"), accessor: (row) => [row.target_type, row.target_id].filter(Boolean).join(":") || "-" },
          ]}
          data={items}
          isLoading={isLoading}
          onRowClick={(row) => navigate(`/automation/runs/${row.id}`)}
        />
      </AdminSurface>
    </div>
  );
}
