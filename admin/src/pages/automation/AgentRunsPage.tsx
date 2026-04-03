import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { useGetRunsApiV1AdminAutomationRunsGet } from "@serino/api-client/admin";
import { getAgentWorkflows } from "@/pages/automation/api";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { useI18n } from "@/i18n";
import type { AgentRunRead } from "@serino/api-client/models";

interface AgentRunsPanelProps {
  runDetailBasePath?: string;
}

function humanizeTrigger(run: AgentRunRead, lang: "zh" | "en") {
  const event = String(run.trigger_event || "").trim();
  const kind = String(run.trigger_kind || "").trim();
  if (lang === "zh") {
    switch (event) {
      case "engagement.pending":
        return "评论 / 留言待处理";
      case "comment.pending":
        return "评论待审核";
      case "guestbook.pending":
        return "留言待审核";
      case "content.publish_requested":
        return "内容发布申请";
      default:
        if (kind === "manual") return "手动触发";
        if (kind === "webhook") return "Webhook 触发";
        if (kind === "schedule") return "定时触发";
        if (kind === "event") return event || "事件触发";
        return event || kind || "-";
    }
  }
  switch (event) {
    case "engagement.pending":
      return "Comment / guestbook pending";
    case "comment.pending":
      return "Comment pending";
    case "guestbook.pending":
      return "Guestbook pending";
    case "content.publish_requested":
      return "Publish request";
    default:
      if (kind === "manual") return "Manual";
      if (kind === "webhook") return "Webhook";
      if (kind === "schedule") return "Scheduled";
      if (kind === "event") return event || "Event";
      return event || kind || "-";
  }
}

function humanizeTarget(run: AgentRunRead, lang: "zh" | "en") {
  const targetType = String(run.target_type || "").trim();
  const targetId = String(run.target_id || "").trim();
  if (!targetType && !targetId) return "-";
  const zhMap: Record<string, string> = {
    comment: "评论",
    guestbook: "留言",
    content: "内容",
    content_batch: "内容批次",
    friend: "友链",
    asset: "资源",
  };
  const enMap: Record<string, string> = {
    comment: "Comment",
    guestbook: "Guestbook",
    content: "Content",
    content_batch: "Content batch",
    friend: "Friend",
    asset: "Asset",
  };
  const label = (lang === "zh" ? zhMap : enMap)[targetType] || targetType || "-";
  return targetId ? `${label}:${targetId}` : label;
}

export function AgentRunsPanel({
  runDetailBasePath = "/agent/activity/runs",
}: AgentRunsPanelProps) {
  const { t, lang } = useI18n();
  const navigate = useNavigate();
  const { data: raw, isLoading } = useGetRunsApiV1AdminAutomationRunsGet();
  const { data: workflows } = useQuery({
    queryKey: ["admin", "agent", "workflows"],
    queryFn: getAgentWorkflows,
  });
  const items = (raw?.data ?? []) as AgentRunRead[];
  const detailBasePath = runDetailBasePath.replace(/\/$/, "");
  const workflowNameMap = useMemo(
    () => new Map((workflows ?? []).map((item) => [item.key, item.name])),
    [workflows],
  );

  return (
    <AdminSurface eyebrow="Automation" title={t("automation.runs")} description={t("automation.runsDescription")}>
      <DataTable
        columns={[
          {
            header: t("automation.workflow"),
            accessor: (row) => {
              const workflowName = workflowNameMap.get(row.workflow_key) || row.workflow_key;
              return (
                <span className="inline-block max-w-[260px] truncate" title={workflowName}>
                  {workflowName}
                </span>
              );
            },
            className: "min-w-[220px]",
          },
          {
            header: t("automation.status"),
            accessor: (row) => <StatusBadge status={row.status} />,
            className: "w-[120px]",
          },
          {
            header: t("automation.trigger"),
            accessor: (row) => {
              const trigger = humanizeTrigger(row, lang);
              return (
                <span className="inline-block max-w-[220px] truncate" title={trigger}>
                  {trigger}
                </span>
              );
            },
            className: "min-w-[180px]",
          },
          {
            header: t("automation.target"),
            accessor: (row) => {
              const target = humanizeTarget(row, lang);
              return <span className="inline-block max-w-[220px] truncate" title={target}>{target}</span>;
            },
            className: "min-w-[180px]",
          },
          {
            header: lang === "zh" ? "时间" : "Time",
            accessor: (row) => formatDate(row.finished_at || row.started_at || row.created_at),
            className: "w-[180px]",
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
