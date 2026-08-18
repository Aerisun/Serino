import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";
import {
  getGetApprovalsApiV1AdminAutomationApprovalsGetQueryKey,
  getGetOverviewApiV1AdminAutomationOverviewGetQueryKey,
  getGetRunsApiV1AdminAutomationRunsGetQueryKey,
  useGetApprovalsApiV1AdminAutomationApprovalsGet,
  usePostApprovalDecisionApiV1AdminAutomationApprovalsApprovalIdDecisionPost,
  useGetRunsApiV1AdminAutomationRunsGet,
} from "@serino/api-client/admin";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { StatusBadge } from "@/components/StatusBadge";
import { useI18n } from "@/i18n";
import { extractApiErrorMessage } from "@/lib/api-error";
import { formatDate } from "@/lib/utils";
import { toast } from "sonner";
import type { AgentRunApprovalRead } from "@serino/api-client/models";
import type { AgentRunRead } from "@serino/api-client/models";
import { getAutomationRunItems } from "./automation-run-view";
import { AutomationQueryError } from "./AutomationQueryError";

interface ApprovalsPanelProps {
  runDetailBasePath?: string;
}

interface PendingDecision {
  approvalId: string;
  action: "approve" | "reject";
}

function humanizeApprovalType(value: string, lang: "zh" | "en") {
  const normalized = String(value || "").trim();
  if (lang === "zh") {
    if (normalized === "moderation_decision") return "审核决定";
    if (normalized === "manual_review") return "人工复核";
    return normalized || "-";
  }
  if (normalized === "moderation_decision") return "Moderation decision";
  if (normalized === "manual_review") return "Manual review";
  return normalized || "-";
}

function approvalSummary(row: AgentRunApprovalRead, lang: "zh" | "en") {
  const payload = (row.request_payload || {}) as Record<string, unknown>;
  const value = (payload.value || {}) as Record<string, unknown>;
  const proposedAction = String(value.proposed_action || "").trim();
  const message = String(value.message || "").trim();

  const actionLabel =
    proposedAction === "approve"
      ? lang === "zh"
        ? "建议通过"
        : "Approve"
      : proposedAction === "reject"
        ? lang === "zh"
          ? "建议拒绝"
          : "Reject"
        : proposedAction === "pending"
          ? lang === "zh"
            ? "建议待定"
            : "Pending"
          : "";

  if (actionLabel && message) {
    return `${actionLabel} · ${message}`;
  }
  if (message) return message;
  if (actionLabel) return actionLabel;
  return humanizeApprovalType(row.approval_type, lang);
}

function humanizeNode(nodeKey: string, lang: "zh" | "en") {
  const normalized = String(nodeKey || "").trim();
  if (lang === "zh") {
    if (normalized.includes("approval")) return "人工审批节点";
    if (normalized.includes("ai")) return "AI 节点";
    return normalized || "-";
  }
  if (normalized.includes("approval")) return "Approval node";
  if (normalized.includes("ai")) return "AI node";
  return normalized || "-";
}

export function ApprovalsPanel({
  runDetailBasePath = "/agent/activity/runs",
}: ApprovalsPanelProps) {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [pendingDecision, setPendingDecision] = useState<PendingDecision | null>(null);
  const [reason, setReason] = useState("");
  const { data: raw, isLoading, isError, refetch } = useGetApprovalsApiV1AdminAutomationApprovalsGet();
  const { data: runsRaw } = useGetRunsApiV1AdminAutomationRunsGet({ limit: 100 });
  const items = (raw?.data ?? []) as AgentRunApprovalRead[];
  const runs = getAutomationRunItems(runsRaw?.data) as AgentRunRead[];
  const detailBasePath = runDetailBasePath.replace(/\/$/, "");
  const workflowNameMap = useMemo(
    () => new Map(runs.map((item) => [item.id, item.workflow_key])),
    [runs],
  );

  const decide = usePostApprovalDecisionApiV1AdminAutomationApprovalsApprovalIdDecisionPost({
    mutation: {
      onSuccess: (_res, vars) => {
        queryClient.invalidateQueries({ queryKey: getGetApprovalsApiV1AdminAutomationApprovalsGetQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetRunsApiV1AdminAutomationRunsGetQueryKey() });
        queryClient.invalidateQueries({ queryKey: getGetOverviewApiV1AdminAutomationOverviewGetQueryKey() });
        toast.success(t("common.operationSuccess"));
        setPendingDecision(null);
        setReason("");
        const row = items.find((item) => item.id === vars.approvalId);
        if (row?.run_id) navigate(`${detailBasePath}/${row.run_id}`);
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  const submitDecision = (approvalId: string, action: "approve" | "reject") => {
    setReason("");
    setPendingDecision({ approvalId, action });
  };

  return (
    <AdminSurface title={t("automation.approvals")} description={t("automation.approvalsDescription")}>
      {isError ? (
        <AutomationQueryError lang={lang} onRetry={() => void refetch()} />
      ) : (
      <DataTable
        columns={[
          {
            header: t("automation.workflow"),
            accessor: (row) => {
              const workflowName = workflowNameMap.get(row.run_id) || row.run_id;
              return <span className="inline-block max-w-[220px] truncate" title={workflowName}>{workflowName}</span>;
            },
            className: "min-w-[200px]",
          },
          {
            header: lang === "zh" ? "审批内容" : "Approval",
            accessor: (row) => {
              const summary = approvalSummary(row, lang);
              return (
                <span className="inline-block max-w-[320px] truncate text-sm" title={summary}>
                  {summary}
                </span>
              );
            },
            className: "min-w-[240px]",
          },
          {
            header: lang === "zh" ? "节点" : "Node",
            accessor: (row) => <span className="inline-block max-w-[180px] truncate" title={row.node_key}>{humanizeNode(row.node_key, lang)}</span>,
            className: "min-w-[140px]",
          },
          {
            header: t("automation.status"),
            accessor: (row) => <StatusBadge status={row.status} />,
            className: "w-[120px]",
          },
          {
            header: lang === "zh" ? "时间" : "Time",
            accessor: (row) => formatDate(row.created_at),
            className: "w-[180px]",
          },
          {
            header: t("common.actions"),
            accessor: (row) => (
              <div className="flex flex-wrap gap-2">
                <Button size="sm" onClick={() => submitDecision(row.id, "approve")} disabled={decide.isPending}>
                  {lang === "zh" ? "通过" : "Approve"}
                </Button>
                <Button size="sm" variant="destructive" onClick={() => submitDecision(row.id, "reject")} disabled={decide.isPending}>
                  {lang === "zh" ? "拒绝" : "Reject"}
                </Button>
              </div>
            ),
            className: "w-[170px]",
          },
        ]}
        data={items}
        isLoading={isLoading}
      />
      )}

      <ConfirmDialog
        open={pendingDecision !== null}
        title={pendingDecision?.action === "reject"
          ? (lang === "zh" ? "确认拒绝这项审批？" : "Reject this approval?")
          : (lang === "zh" ? "确认通过这项审批？" : "Approve this request?")}
        description={lang === "zh"
          ? "决定会立即恢复对应工作流，请确认审批内容与目标无误。"
          : "This decision resumes the workflow immediately. Verify the request and target first."}
        confirmLabel={pendingDecision?.action === "reject"
          ? (lang === "zh" ? "确认拒绝" : "Reject")
          : (lang === "zh" ? "确认通过" : "Approve")}
        variant={pendingDecision?.action === "reject" ? "destructive" : "default"}
        isPending={decide.isPending}
        onCancel={() => {
          setPendingDecision(null);
          setReason("");
        }}
        onConfirm={() => {
          if (!pendingDecision) return;
          decide.mutate({
            approvalId: pendingDecision.approvalId,
            data: { action: pendingDecision.action, reason: reason.trim() || null },
          });
        }}
      >
        <label className="grid gap-2 text-sm">
          <span className="font-medium">{lang === "zh" ? "处理说明（可选）" : "Decision note (optional)"}</span>
          <textarea
            value={reason}
            onChange={(event) => setReason(event.target.value)}
            rows={3}
            maxLength={500}
            className="w-full resize-y rounded-[var(--admin-radius-md)] admin-glass-input px-3 py-2 text-sm outline-none ring-offset-background focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
            placeholder={lang === "zh" ? "记录通过或拒绝的原因" : "Record why this was approved or rejected"}
          />
        </label>
      </ConfirmDialog>
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
