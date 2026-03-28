import { useGetRunsApiV1AdminAutomationRunsGet } from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { useNavigate } from "react-router-dom";
import { useI18n } from "@/i18n";
import type { AgentRunRead } from "@serino/api-client/models";

interface AgentRunsPanelProps {
  runDetailBasePath?: string;
}

function shortId(value: string, length = 8) {
  const normalized = (value || "").trim();
  if (normalized.length <= length) {
    return normalized;
  }
  return `${normalized.slice(0, length)}...`;
}

export function AgentRunsPanel({
  runDetailBasePath = "/agent/activity/runs",
}: AgentRunsPanelProps) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const { data: raw, isLoading } = useGetRunsApiV1AdminAutomationRunsGet();
  const items = (raw?.data ?? []) as AgentRunRead[];
  const detailBasePath = runDetailBasePath.replace(/\/$/, "");

  return (
    <AdminSurface eyebrow="Automation" title={t("automation.runs")} description={t("automation.runsDescription")}>
      <DataTable
        columns={[
          {
            header: "ID",
            accessor: (row) => (
              <code className="inline-block max-w-[120px] truncate text-[11px]" title={row.id}>
                {shortId(row.id)}
              </code>
            ),
            className: "w-[130px]",
          },
          {
            header: t("automation.workflow"),
            accessor: (row) => <span className="inline-block max-w-[220px] truncate" title={row.workflow_key}>{row.workflow_key}</span>,
            className: "min-w-[180px]",
          },
          {
            header: t("automation.status"),
            accessor: (row) => <Badge variant="outline">{row.status}</Badge>,
            className: "w-[120px]",
          },
          {
            header: t("automation.trigger"),
            accessor: (row) => <span className="inline-block max-w-[180px] truncate" title={row.trigger_event || row.trigger_kind}>{row.trigger_event || row.trigger_kind}</span>,
            className: "min-w-[140px]",
          },
          {
            header: t("automation.target"),
            accessor: (row) => {
              const target = [row.target_type, row.target_id].filter(Boolean).join(":") || "-";
              return <span className="inline-block max-w-[220px] truncate" title={target}>{target}</span>;
            },
            className: "min-w-[180px]",
          },
        ]}
        data={items}
        isLoading={isLoading}
        onRowClick={(row) => navigate(`${detailBasePath}/${row.id}`)}
      />
    </AdminSurface>
  );
}

export default function AgentRunsPage() {
  const { t } = useI18n();
  return (
    <div>
      <PageHeader title={t("automation.runs")} description={t("automation.runsDescription")} />
      <AgentRunsPanel />
    </div>
  );
}
