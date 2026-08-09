import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { useGetRunsApiV1AdminAutomationRunsGet } from "@serino/api-client/admin";
import { getAgentWorkflows } from "@/pages/automation/api";
import { PageHeader } from "@/components/PageHeader";
import { AdminSurface, AdminToolbar } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { StatusBadge } from "@/components/StatusBadge";
import { formatDate } from "@/lib/utils";
import { useNavigate } from "react-router-dom";
import { useI18n } from "@/i18n";
import type {
  AgentRunRead,
  GetRunsApiV1AdminAutomationRunsGetParams,
} from "@serino/api-client/models";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { NativeSelect } from "@/components/ui/NativeSelect";
import { Badge } from "@/components/ui/Badge";
import { ChevronLeft, ChevronRight, RefreshCw, RotateCcw, Search } from "lucide-react";
import { formatAutomationDuration, getAutomationRunItems } from "./automation-run-view";
import { AutomationQueryError } from "./AutomationQueryError";

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
  const [status, setStatus] = useState("all");
  const [workflowKey, setWorkflowKey] = useState("all");
  const [executionMode, setExecutionMode] = useState("all");
  const [searchDraft, setSearchDraft] = useState("");
  const [search, setSearch] = useState("");
  const [cursorHistory, setCursorHistory] = useState<Array<string | undefined>>([undefined]);
  const [pageIndex, setPageIndex] = useState(0);
  const { data: workflows } = useQuery({
    queryKey: ["admin", "agent", "workflows"],
    queryFn: getAgentWorkflows,
  });
  const params = useMemo<GetRunsApiV1AdminAutomationRunsGetParams>(
    () => ({
      status: status === "all" ? undefined : [status],
      workflow_key: workflowKey === "all" ? undefined : workflowKey,
      execution_mode:
        executionMode === "all" ? undefined : (executionMode as "live" | "dry_run"),
      search: search || undefined,
      cursor: cursorHistory[pageIndex],
      limit: 25,
    }),
    [cursorHistory, executionMode, pageIndex, search, status, workflowKey],
  );
  const { data: raw, isLoading, isFetching, isError, refetch } =
    useGetRunsApiV1AdminAutomationRunsGet(params, {
      query: { refetchOnWindowFocus: true },
    });
  const collection = raw?.data;
  const items = getAutomationRunItems(collection);
  const detailBasePath = runDetailBasePath.replace(/\/$/, "");
  const workflowNameMap = useMemo(
    () => new Map((workflows ?? []).map((item) => [item.key, item.name])),
    [workflows],
  );
  const resetPagination = () => {
    setCursorHistory([undefined]);
    setPageIndex(0);
  };
  const resetFilters = () => {
    setStatus("all");
    setWorkflowKey("all");
    setExecutionMode("all");
    setSearchDraft("");
    setSearch("");
    resetPagination();
  };

  const statusOptions = lang === "zh"
    ? [
        ["all", "全部状态"],
        ["queued", "排队中"],
        ["running", "运行中"],
        ["awaiting_approval", "等待审批"],
        ["interrupted", "已中断"],
        ["completed", "已完成"],
        ["failed", "失败"],
        ["cancelled", "已取消"],
      ]
    : [
        ["all", "All statuses"],
        ["queued", "Queued"],
        ["running", "Running"],
        ["awaiting_approval", "Awaiting approval"],
        ["interrupted", "Interrupted"],
        ["completed", "Completed"],
        ["failed", "Failed"],
        ["cancelled", "Cancelled"],
      ];

  return (
    <AdminSurface
      eyebrow="Automation"
      title={t("automation.runs")}
      description={t("automation.runsDescription")}
      actions={
        <Button variant="outline" size="sm" onClick={() => void refetch()} disabled={isFetching}>
          <RefreshCw className={`mr-2 h-4 w-4 ${isFetching ? "animate-spin" : ""}`} />
          {lang === "zh" ? "刷新" : "Refresh"}
        </Button>
      }
    >
      <AdminToolbar align="start" className="mb-4">
        <form
          className="flex min-w-0 flex-1 gap-2 sm:min-w-[280px]"
          onSubmit={(event) => {
            event.preventDefault();
            setSearch(searchDraft.trim());
            resetPagination();
          }}
        >
          <Input
            value={searchDraft}
            onChange={(event) => setSearchDraft(event.target.value)}
            placeholder={lang === "zh" ? "搜索运行 ID、事件、目标或错误" : "Search run, event, target, or error"}
            aria-label={lang === "zh" ? "搜索运行记录" : "Search runs"}
          />
          <Button type="submit" variant="outline" size="icon" aria-label={lang === "zh" ? "搜索" : "Search"}>
            <Search className="h-4 w-4" />
          </Button>
        </form>

        <NativeSelect
          value={status}
          onChange={(event) => {
            setStatus(event.target.value);
            resetPagination();
          }}
          containerClassName="w-full sm:w-44"
          aria-label={lang === "zh" ? "状态筛选" : "Status filter"}
        >
          {statusOptions.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
        </NativeSelect>

        <NativeSelect
          value={workflowKey}
          onChange={(event) => {
            setWorkflowKey(event.target.value);
            resetPagination();
          }}
          containerClassName="w-full sm:w-52"
          aria-label={lang === "zh" ? "工作流筛选" : "Workflow filter"}
        >
          <option value="all">{lang === "zh" ? "全部工作流" : "All workflows"}</option>
          {(workflows ?? []).map((workflow) => (
            <option key={workflow.key} value={workflow.key}>{workflow.name}</option>
          ))}
        </NativeSelect>

        <NativeSelect
          value={executionMode}
          onChange={(event) => {
            setExecutionMode(event.target.value);
            resetPagination();
          }}
          containerClassName="w-full sm:w-40"
          aria-label={lang === "zh" ? "执行模式筛选" : "Execution mode filter"}
        >
          <option value="all">{lang === "zh" ? "全部模式" : "All modes"}</option>
          <option value="live">{lang === "zh" ? "正式执行" : "Live"}</option>
          <option value="dry_run">{lang === "zh" ? "模拟运行" : "Dry run"}</option>
        </NativeSelect>

        <Button variant="ghost" size="sm" onClick={resetFilters}>
          <RotateCcw className="mr-2 h-4 w-4" />
          {lang === "zh" ? "重置" : "Reset"}
        </Button>
      </AdminToolbar>

      {isError ? (
        <AutomationQueryError lang={lang} onRetry={() => void refetch()} />
      ) : (
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
            header: lang === "zh" ? "模式" : "Mode",
            accessor: (row) => (
              <Badge variant={row.execution_mode === "dry_run" ? "outline" : "info"}>
                {row.execution_mode === "dry_run"
                  ? (lang === "zh" ? "模拟" : "Dry run")
                  : (lang === "zh" ? "正式" : "Live")}
              </Badge>
            ),
            className: "w-[110px]",
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
            header: lang === "zh" ? "耗时" : "Duration",
            accessor: (row) => formatAutomationDuration(row.duration_ms, lang),
            className: "w-[120px]",
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
      )}

      <div className="mt-4 flex flex-col gap-3 text-sm sm:flex-row sm:items-center sm:justify-between">
        <span className="text-muted-foreground">
          {lang === "zh"
            ? `共 ${collection?.total ?? 0} 条 · 第 ${pageIndex + 1} 页`
            : `${collection?.total ?? 0} total · Page ${pageIndex + 1}`}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            disabled={pageIndex === 0 || isFetching}
            onClick={() => setPageIndex((current) => Math.max(0, current - 1))}
          >
            <ChevronLeft className="mr-1 h-4 w-4" />
            {lang === "zh" ? "上一页" : "Previous"}
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={!collection?.has_more || !collection.next_cursor || isFetching}
            onClick={() => {
              if (!collection?.next_cursor) return;
              setCursorHistory((current) => [
                ...current.slice(0, pageIndex + 1),
                collection.next_cursor ?? undefined,
              ]);
              setPageIndex((current) => current + 1);
            }}
          >
            {lang === "zh" ? "下一页" : "Next"}
            <ChevronRight className="ml-1 h-4 w-4" />
          </Button>
        </div>
      </div>
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
