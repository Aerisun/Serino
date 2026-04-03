import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  deleteSubscriptionSubscriber,
  listSubscriptionSubscriberMessages,
  listSubscriptionSubscribers,
  type SubscriptionDeliveryItem,
  type SubscriptionSubscriberItem,
  updateSubscriptionSubscriber,
} from "@/pages/visitors/api";
import { DataTable } from "@/components/DataTable";
import { PageHeader } from "@/components/PageHeader";
import {
  ActivationStateText,
  ActivationToggleButton,
  inactiveRowClassName,
} from "@/components/ActivationState";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { AdminSegmentedFilter } from "@/components/ui/AdminSegmentedFilter";
import { Input } from "@/components/ui/Input";
import { cn, formatDate } from "@/lib/utils";
import { Search, Trash2 } from "lucide-react";
import { VisitorsSectionSwitch } from "@/pages/visitors/VisitorsSectionSwitch";
import { toast } from "sonner";

const SUBSCRIBER_MODE_OPTIONS = [
  { key: "all", label: "全部" },
  { key: "email", label: "邮箱" },
  { key: "binding", label: "绑定" },
  { key: "subscriber", label: "订阅者" },
] as const;

type SubscriberMode = (typeof SUBSCRIBER_MODE_OPTIONS)[number]["key"];

type SubscriberRow = SubscriptionSubscriberItem & { id: string };

interface VisitorsSubscribersPanelProps {
  initialMode?: SubscriberMode;
  showModeFilter?: boolean;
  showSearch?: boolean;
  searchKeyword?: string;
}

const CONTENT_TYPE_LABELS: Record<string, string> = {
  posts: "文章",
  diary: "日记",
  thoughts: "碎碎念",
  excerpts: "文摘",
};

function authModeLabel(mode: string): string {
  if (mode === "binding") return "绑定";
  if (mode === "email") return "邮箱";
  return "未知";
}

function SubscriberMessageList({ email }: { email: string }) {
  const [page, setPage] = useState(1);
  const pageSize = 6;

  const messagesQuery = useQuery({
    queryKey: ["subscription-subscriber-messages", email, page],
    queryFn: () =>
      listSubscriptionSubscriberMessages(email, {
        page,
        page_size: pageSize,
      }),
  });

  const total = messagesQuery.data?.total ?? 0;
  const items = messagesQuery.data?.items ?? [];
  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <div className="grid gap-3 py-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm font-medium text-foreground">已发送消息</div>
        <div className="text-xs text-muted-foreground">{total} 条记录</div>
      </div>

      {messagesQuery.isLoading ? (
        <div className="rounded-[var(--admin-radius-md)] border border-border/60 bg-background/40 px-4 py-4 text-sm text-muted-foreground">
          加载中...
        </div>
      ) : items.length === 0 ? (
        <div className="rounded-[var(--admin-radius-md)] border border-dashed border-border/60 bg-background/40 px-4 py-4 text-sm text-muted-foreground">
          暂无发送记录。
        </div>
      ) : (
        <div className="grid gap-2">
          {items.map((item) => (
            <SubscriberMessageRow key={item.id} item={item} />
          ))}
        </div>
      )}

      {total > pageSize ? (
        <div className="flex items-center justify-end gap-2">
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page <= 1}
            onClick={() => setPage((current) => Math.max(1, current - 1))}
          >
            上一页
          </Button>
          <span className="text-xs text-muted-foreground">
            {page}/{totalPages}
          </span>
          <Button
            type="button"
            variant="outline"
            size="sm"
            disabled={page >= totalPages}
            onClick={() => setPage((current) => Math.min(totalPages, current + 1))}
          >
            下一页
          </Button>
        </div>
      ) : null}
    </div>
  );
}

function SubscriberMessageRow({ item }: { item: SubscriptionDeliveryItem }) {
  return (
    <div className="grid gap-2 rounded-[var(--admin-radius-md)] border border-border/60 bg-background/55 px-4 py-3 text-sm md:grid-cols-[130px_1fr_120px_160px]">
      <div className="text-muted-foreground">{CONTENT_TYPE_LABELS[item.content_type] ?? item.content_type}</div>
      <a
        href={item.content_url}
        target="_blank"
        rel="noreferrer"
        className="truncate text-foreground hover:underline"
        title={item.content_title}
      >
        {item.content_title}
      </a>
      <div>
        <Badge variant={item.status === "sent" ? "secondary" : "outline"}>
          {item.status === "sent" ? "已发送" : "发送失败"}
        </Badge>
      </div>
      <div className="text-muted-foreground">{item.sent_at ? formatDate(item.sent_at) : "-"}</div>
      {item.error_message ? (
        <div className="md:col-span-4 text-xs text-rose-500">{item.error_message}</div>
      ) : null}
    </div>
  );
}

export function VisitorsSubscribersPanel({
  initialMode = "all",
  showModeFilter = true,
  showSearch = true,
  searchKeyword,
}: VisitorsSubscribersPanelProps = {}) {
  const queryClient = useQueryClient();
  const [mode, setMode] = useState<SubscriberMode>(initialMode);
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const effectiveSearch = searchKeyword ?? search;
  const queryKey = ["subscription-subscribers", mode, effectiveSearch, page] as const;

  useEffect(() => {
    if (searchKeyword === undefined) {
      return;
    }
    setPage(1);
  }, [searchKeyword]);

  const query = useQuery({
    queryKey,
    queryFn: () =>
      listSubscriptionSubscribers({
        mode,
        search: effectiveSearch.trim() || undefined,
        page,
        page_size: 20,
      }),
  });

  const refreshSubscribers = async () => {
    await queryClient.invalidateQueries({ queryKey: ["subscription-subscribers"] });
  };

  const toggleSubscriber = useMutation({
    mutationFn: ({ email, isActive }: { email: string; isActive: boolean }) =>
      updateSubscriptionSubscriber(email, { is_active: isActive }),
    onSuccess: async (_data, variables) => {
      await refreshSubscribers();
      toast.success(variables.isActive ? "已启用订阅发送" : "已暂停订阅发送");
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "操作失败");
    },
  });

  const removeSubscriber = useMutation({
    mutationFn: (email: string) => deleteSubscriptionSubscriber(email),
    onSuccess: async (_data, email) => {
      await Promise.all([
        refreshSubscribers(),
        queryClient.invalidateQueries({ queryKey: ["subscription-subscriber-messages", email] }),
      ]);
      toast.success("已删除订阅");
      if (rows.length === 1 && page > 1) {
        setPage((current) => Math.max(1, current - 1));
      }
    },
    onError: (error) => {
      toast.error(error instanceof Error ? error.message : "操作失败");
    },
  });

  const rows = useMemo<SubscriberRow[]>(
    () => (query.data?.items ?? []).map((item) => ({ ...item, id: item.email })),
    [query.data?.items],
  );

  const total = query.data?.total ?? 0;

  const columns = useMemo(
    () => [
      {
        header: "订阅者",
        accessor: (row: SubscriberRow) => (
          <div className="flex items-center gap-3">
            {row.avatar_url ? (
              <img
                src={row.avatar_url}
                alt={row.display_name ?? row.email}
                className={cn(
                  "h-10 w-10 rounded-full border border-border/60 object-cover",
                  !row.is_active && "grayscale opacity-40",
                )}
              />
            ) : (
              <div
                className={cn(
                  "flex h-10 w-10 items-center justify-center rounded-full border border-border/60 bg-muted text-sm font-semibold text-muted-foreground",
                  !row.is_active && "opacity-45",
                )}
              >
                {(row.display_name ?? row.email).slice(0, 1).toUpperCase()}
              </div>
            )}
            <div className="min-w-0">
              <ActivationStateText
                as="div"
                inactive={!row.is_active}
                className="truncate font-medium text-foreground"
              >
                {row.display_name || "未匹配访客身份"}
              </ActivationStateText>
              <ActivationStateText
                as="div"
                inactive={!row.is_active}
                className="truncate text-xs text-muted-foreground"
              >
                {row.initiator_email || row.primary_auth_provider || "未记录访客邮箱"}
              </ActivationStateText>
            </div>
          </div>
        ),
      },
      {
        header: "邮箱",
        accessor: (row: SubscriberRow) => (
          <ActivationStateText inactive={!row.is_active} className="font-mono text-xs text-muted-foreground">
            {row.email}
          </ActivationStateText>
        ),
      },
      {
        header: "身份",
        accessor: (row: SubscriberRow) => (
          <div className="space-y-1 text-sm">
            <ActivationStateText
              as="div"
              inactive={!row.is_active}
              className="text-foreground"
            >
              {authModeLabel(row.auth_mode)}
            </ActivationStateText>
            {(row.oauth_providers ?? []).length > 0 ? (
              <ActivationStateText
                as="div"
                inactive={!row.is_active}
                className="text-xs text-muted-foreground"
              >
                {(row.oauth_providers ?? [])
                  .map((provider) =>
                    provider === "google" ? "Google" : provider === "github" ? "GitHub" : provider,
                  )
                  .join(" / ")}
              </ActivationStateText>
            ) : null}
          </div>
        ),
      },
      {
        header: "订阅内容",
        accessor: (row: SubscriberRow) => (
          <ActivationStateText inactive={!row.is_active} className="text-sm text-muted-foreground">
            {(row.content_types ?? []).map((item) => CONTENT_TYPE_LABELS[item] ?? item).join(" / ") || "-"}
          </ActivationStateText>
        ),
      },
      {
        header: "已发送",
        accessor: (row: SubscriberRow) => (
          <ActivationStateText inactive={!row.is_active} className="text-sm text-foreground">
            {row.sent_count}
          </ActivationStateText>
        ),
      },
      {
        header: "最近发送",
        accessor: (row: SubscriberRow) => (
          <ActivationStateText inactive={!row.is_active} className="text-sm text-muted-foreground">
            {row.last_sent_at ? formatDate(row.last_sent_at) : "-"}
          </ActivationStateText>
        ),
      },
      {
        header: "操作",
        className: "w-[120px] text-center whitespace-nowrap",
        accessor: (row: SubscriberRow) => {
          const isToggling =
            toggleSubscriber.isPending && toggleSubscriber.variables?.email === row.email;
          const isRemoving =
            removeSubscriber.isPending && removeSubscriber.variables === row.email;
          const busy = isToggling || isRemoving;

          return (
            <div className="flex items-center justify-center gap-1.5">
              <ActivationToggleButton
                isActive={row.is_active}
                disabled={busy}
                activeLabel="禁用"
                inactiveLabel="启用"
                activeTitle="禁用发送"
                inactiveTitle="启用发送"
                onClick={() =>
                  toggleSubscriber.mutate({
                    email: row.email,
                    isActive: !row.is_active,
                  })
                }
              />
              <Button
                type="button"
                variant="ghost"
                size="icon"
                className={cn(
                  "h-8 w-8",
                  !row.is_active && "text-muted-foreground/80 opacity-70 hover:bg-muted/35 hover:text-muted-foreground",
                )}
                title="删除订阅"
                disabled={busy}
                onClick={() => {
                  if (!window.confirm(`确认删除订阅：${row.email}？`)) {
                    return;
                  }
                  removeSubscriber.mutate(row.email);
                }}
              >
                <Trash2 className={cn("h-4 w-4", row.is_active ? "text-rose-500" : "text-muted-foreground/80")} />
              </Button>
            </div>
          );
        },
      },
    ],
    [removeSubscriber, toggleSubscriber],
  );

  return (
    <div className={cn("space-y-4", showModeFilter ? "pt-6" : "")}>
      <div
        className={cn(
          "flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center",
          showModeFilter ? "sm:justify-between" : "sm:justify-end",
        )}
      >
        {showModeFilter ? (
          <AdminSegmentedFilter
            value={mode}
            onValueChange={(next) => {
              setMode(next as SubscriberMode);
              setPage(1);
            }}
            items={SUBSCRIBER_MODE_OPTIONS.map((item) => ({
              value: item.key,
              label: item.label,
            }))}
            tone="accent"
          />
        ) : null}

        {showSearch ? (
          <div className="relative w-full max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              value={search}
              onChange={(event) => {
                setSearch(event.target.value);
                setPage(1);
              }}
              className="pl-9"
              placeholder="搜索订阅邮箱"
            />
          </div>
        ) : null}
      </div>

      <DataTable<SubscriberRow>
        columns={columns}
        data={rows}
        total={total}
        page={page}
        pageSize={20}
        onPageChange={setPage}
        isLoading={query.isLoading}
        getRowClassName={(row) => inactiveRowClassName(row.is_active)}
        renderExpandedRow={(row) => <SubscriberMessageList email={row.email} />}
      />
    </div>
  );
}

export default function VisitorsSubscribersPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="订阅者"
        description="显示订阅邮箱、订阅内容以及已发送消息记录。"
        secondary={<VisitorsSectionSwitch />}
      />

      <VisitorsSubscribersPanel />
    </div>
  );
}
