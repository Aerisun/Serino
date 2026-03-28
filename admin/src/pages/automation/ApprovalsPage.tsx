import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  getGetApprovalsApiV1AdminAutomationApprovalsGetQueryKey,
  useGetApprovalsApiV1AdminAutomationApprovalsGet,
  usePostApprovalDecisionApiV1AdminAutomationApprovalsApprovalIdDecisionPost,
} from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import type { AgentRunApprovalRead } from "@serino/api-client/models";

interface ApprovalsPanelProps {
  runDetailBasePath?: string;
}

function shortId(value: string, length = 8) {
  const normalized = (value || "").trim();
  if (normalized.length <= length) {
    return normalized;
  }
  return `${normalized.slice(0, length)}...`;
}

export function ApprovalsPanel({
  runDetailBasePath = "/agent/activity/runs",
}: ApprovalsPanelProps) {
  const { t } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [busyId, setBusyId] = useState<string | null>(null);
  const { data: raw, isLoading } = useGetApprovalsApiV1AdminAutomationApprovalsGet({ query: { refetchInterval: 5000 } });
  const items = (raw?.data ?? []) as AgentRunApprovalRead[];
  const detailBasePath = runDetailBasePath.replace(/\/$/, "");

  const decide = usePostApprovalDecisionApiV1AdminAutomationApprovalsApprovalIdDecisionPost({
    mutation: {
      onSuccess: (_res, vars) => {
        queryClient.invalidateQueries({ queryKey: getGetApprovalsApiV1AdminAutomationApprovalsGetQueryKey() });
        toast.success(t("common.operationSuccess"));
        setBusyId(null);
        const row = items.find((item) => item.id === vars.approvalId);
        if (row?.run_id) navigate(`${detailBasePath}/${row.run_id}`);
      },
      onError: (error: any) => {
        const msg = error?.response?.data?.detail || t("common.operationFailed");
        toast.error(msg);
        setBusyId(null);
      },
    },
  });

  const submitDecision = (approvalId: string, action: "approve" | "reject") => {
    setBusyId(approvalId);
    decide.mutate({ approvalId, data: { action } });
  };

  return (
    <AdminSurface eyebrow="Approval" title={t("automation.approvals")} description={t("automation.approvalsDescription")}>
      <DataTable
        columns={[
          {
            header: t("automation.runId"),
            accessor: (row) => (
              <code className="inline-block max-w-[120px] truncate text-[11px]" title={row.run_id}>
                {shortId(row.run_id)}
              </code>
            ),
            className: "w-[130px]",
          },
          {
            header: t("automation.approvalType"),
            accessor: (row) => <span className="text-sm">{row.approval_type}</span>,
            className: "min-w-[120px]",
          },
          {
            header: t("automation.node"),
            accessor: (row) => <span className="inline-block max-w-[180px] truncate" title={row.node_key}>{row.node_key}</span>,
            className: "min-w-[140px]",
          },
          { header: t("automation.status"), accessor: (row) => <Badge variant="outline">{row.status}</Badge> },
          {
            header: t("common.actions"),
            accessor: (row) => (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={() => submitDecision(row.id, "approve")} disabled={busyId === row.id || decide.isPending}>Approve</Button>
                <Button size="sm" variant="destructive" onClick={() => submitDecision(row.id, "reject")} disabled={busyId === row.id || decide.isPending}>Reject</Button>
              </div>
            ),
            className: "w-[170px]",
          },
        ]}
        data={items}
        isLoading={isLoading}
      />
    </AdminSurface>
  );
}

export default function ApprovalsPage() {
  const { t } = useI18n();

  return (
    <div>
      <PageHeader title={t("automation.approvals")} description={t("automation.approvalsDescription")} />
      <ApprovalsPanel />
    </div>
  );
}
