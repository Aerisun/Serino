import { lazy, Suspense, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  useGetMessageApiV1AdminAutomationMessagesMessageIdGet,
  useGetMessagesApiV1AdminAutomationMessagesGet,
} from "@serino/api-client/admin";
import type {
  AgentMessageRead,
  AgentMessageSummaryRead,
  GetMessagesApiV1AdminAutomationMessagesGetParams,
} from "@serino/api-client/models";
import { useNavigate } from "react-router-dom";
import { AdminSurface } from "@/components/AdminSurface";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/Dialog";
import { formatDate } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { getAgentWorkflows } from "@/pages/automation/api";
import {
  ArrowUpRight,
  ChevronLeft,
  ChevronRight,
  RefreshCw,
} from "lucide-react";
import { AutomationQueryError } from "./AutomationQueryError";

const MarkdownPreview = lazy(() => import("@/components/MarkdownPreview"));

interface AgentMessagesPanelProps {
  runDetailBasePath?: string;
}

export function AgentMessagesPanel({
  runDetailBasePath = "/agent/activity/runs",
}: AgentMessagesPanelProps) {
  const { lang } = useI18n();
  const navigate = useNavigate();
  const [selectedMessage, setSelectedMessage] =
    useState<AgentMessageSummaryRead | null>(null);
  const [cursorHistory, setCursorHistory] = useState<Array<string | undefined>>([
    undefined,
  ]);
  const [pageIndex, setPageIndex] = useState(0);
  const { data: workflows } = useQuery({
    queryKey: ["admin", "agent", "workflows"],
    queryFn: getAgentWorkflows,
  });
  const params = useMemo<GetMessagesApiV1AdminAutomationMessagesGetParams>(
    () => ({
      cursor: cursorHistory[pageIndex],
      limit: 25,
    }),
    [cursorHistory, pageIndex],
  );
  const { data: raw, isLoading, isFetching, isError, refetch } =
    useGetMessagesApiV1AdminAutomationMessagesGet(params, {
      query: { refetchOnWindowFocus: true },
    });
  const collection = raw?.data;
  const items = (collection?.items ?? []) as AgentMessageSummaryRead[];
  const {
    data: messageDetailRaw,
    isLoading: isMessageDetailLoading,
    isError: isMessageDetailError,
    refetch: refetchMessageDetail,
  } = useGetMessageApiV1AdminAutomationMessagesMessageIdGet(
    selectedMessage?.id ?? "",
    {
      query: {
        enabled: selectedMessage !== null,
        refetchOnWindowFocus: false,
      },
    },
  );
  const messageDetail =
    messageDetailRaw?.status === 200
      ? (messageDetailRaw.data as AgentMessageRead)
      : undefined;
  const detailBasePath = runDetailBasePath.replace(/\/$/, "");
  const workflowNameMap = useMemo(
    () => new Map((workflows ?? []).map((item) => [item.key, item.name])),
    [workflows],
  );

  return (
    <>
      <AdminSurface
        title={lang === "zh" ? "留言列表" : "Messages"}
        actions={
          <Button
            variant="outline"
            size="sm"
            onClick={() => void refetch()}
            disabled={isFetching}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${isFetching ? "animate-spin" : ""}`}
            />
            {lang === "zh" ? "刷新" : "Refresh"}
          </Button>
        }
      >
        {isError ? (
          <AutomationQueryError lang={lang} onRetry={() => void refetch()} />
        ) : (
          <DataTable
            tableClassName="table-fixed"
            columns={[
              {
                header: lang === "zh" ? "留言" : "Message",
                accessor: (row) => (
                  <div
                    className="block max-w-full truncate leading-6 text-foreground"
                    title={row.message_preview}
                  >
                    {row.message_preview}
                  </div>
                ),
                className: "min-w-0",
              },
              {
                header: lang === "zh" ? "工作流" : "Workflow",
                accessor: (row) => {
                  const name =
                    workflowNameMap.get(row.workflow_key) || row.workflow_key;
                  return (
                    <span
                      className="inline-block max-w-[240px] truncate"
                      title={name}
                    >
                      {name}
                    </span>
                  );
                },
                className: "w-56",
              },
              {
                header: lang === "zh" ? "时间" : "Time",
                accessor: (row) => formatDate(row.created_at),
                className: "w-44",
              },
            ]}
            data={items}
            isLoading={isLoading}
            onRowClick={(row) => setSelectedMessage(row)}
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
              onClick={() =>
                setPageIndex((current) => Math.max(0, current - 1))
              }
            >
              <ChevronLeft className="mr-1 h-4 w-4" />
              {lang === "zh" ? "上一页" : "Previous"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              disabled={
                !collection?.has_more ||
                !collection.next_cursor ||
                isFetching
              }
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

      <Dialog
        open={selectedMessage !== null}
        onOpenChange={(nextOpen) => {
          if (!nextOpen) setSelectedMessage(null);
        }}
      >
        <DialogContent className="max-h-[calc(100dvh-1.5rem)] w-[calc(100%-1.5rem)] max-w-3xl grid-rows-[auto_minmax(0,1fr)_auto] gap-0 overflow-hidden rounded-[var(--admin-radius-xl)] p-0 sm:max-h-[min(88vh,800px)]">
          <DialogHeader className="border-b border-border/60 px-4 py-4 pr-12 text-left sm:px-6 sm:py-5">
            <DialogTitle>
              {lang === "zh" ? "留言详情" : "Message details"}
            </DialogTitle>
            {selectedMessage ? (
              <DialogDescription>
                {workflowNameMap.get(selectedMessage.workflow_key) ||
                  selectedMessage.workflow_key}
                <span aria-hidden="true"> · </span>
                {formatDate(selectedMessage.created_at)}
              </DialogDescription>
            ) : null}
          </DialogHeader>

          <div className="min-h-0 overflow-y-auto overscroll-contain px-4 py-4 sm:px-6 sm:py-5">
            {isMessageDetailLoading ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                {lang === "zh" ? "正在加载留言..." : "Loading message..."}
              </div>
            ) : isMessageDetailError ? (
              <div className="flex flex-col items-center gap-3 py-8 text-center">
                <p className="text-sm text-muted-foreground">
                  {lang === "zh"
                    ? "留言加载失败，请重试。"
                    : "Message failed to load."}
                </p>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => void refetchMessageDetail()}
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  {lang === "zh" ? "重新加载" : "Retry"}
                </Button>
              </div>
            ) : messageDetail ? (
              <Suspense
                fallback={
                  <div className="py-8 text-center text-sm text-muted-foreground">
                    {lang === "zh" ? "正在渲染留言..." : "Rendering message..."}
                  </div>
                }
              >
                <MarkdownPreview
                  content={messageDetail.message}
                  className="text-foreground"
                />
              </Suspense>
            ) : null}
          </div>

          {selectedMessage ? (
            <div className="flex justify-end border-t border-border/60 px-4 py-3 sm:px-6 sm:py-4">
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="w-full sm:w-auto"
                onClick={() => {
                  const runId = selectedMessage.run_id;
                  setSelectedMessage(null);
                  navigate(`${detailBasePath}/${runId}`);
                }}
              >
                {lang === "zh" ? "查看运行详情" : "View run details"}
                <ArrowUpRight className="ml-2 h-4 w-4" />
              </Button>
            </div>
          ) : null}
        </DialogContent>
      </Dialog>
    </>
  );
}
