import { useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import {
  getListVisitorUsersApiV1AdminVisitorsUsersGetQueryKey,
  useDeleteVisitorUserApiV1AdminVisitorsUsersUserIdDelete,
  useListVisitorUsersApiV1AdminVisitorsUsersGet,
} from "@serino/api-client/admin";
import type {
  ListVisitorUsersApiV1AdminVisitorsUsersGetParams,
  SiteUserAdminRead,
} from "@serino/api-client/models";
import { DataTable } from "@/components/DataTable";
import { Button } from "@/components/ui/Button";
import { AdminSegmentedFilter } from "@/components/ui/AdminSegmentedFilter";
import { ConfirmDialog } from "@/components/ConfirmDialog";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/PageHeader";
import { cn, formatDate } from "@/lib/utils";
import { extractApiErrorMessage } from "@/lib/api-error";
import { useI18n } from "@/i18n";
import { Search } from "lucide-react";
import { VisitorsSubscribersPanel } from "@/pages/visitors/VisitorsSubscribersPage";
import { VisitorsSectionSwitch } from "@/pages/visitors/VisitorsSectionSwitch";
import { toast } from "sonner";

const USER_MODE_OPTIONS = [
  { key: "all", label: "全部" },
  { key: "email", label: "邮箱" },
  { key: "binding", label: "绑定" },
  { key: "subscriber", label: "订阅者" },
] as const;

type VisitorUserMode = (typeof USER_MODE_OPTIONS)[number]["key"];

function providerBadgeTone(provider: string) {
  if (provider === "google")
    return "border-emerald-500/20 bg-emerald-500/12 text-emerald-700 dark:text-emerald-300";
  if (provider === "github") {
    return "border-blue-500/20 bg-blue-500/12 text-blue-700 dark:text-blue-300";
  }
  return "bg-emerald-500/12 text-emerald-700 border-emerald-500/16";
}

export function VisitorsUsersPanel() {
  const { t } = useI18n();
  const queryClient = useQueryClient();
  const [userMode, setUserMode] = useState<VisitorUserMode>("all");
  const [search, setSearch] = useState("");
  const [subscriberSearch, setSubscriberSearch] = useState("");
  const [page, setPage] = useState(1);
  const [deleteTarget, setDeleteTarget] = useState<SiteUserAdminRead | null>(null);
  const isSubscriberMode = userMode === "subscriber";

  const userParams = useMemo<ListVisitorUsersApiV1AdminVisitorsUsersGetParams>(
    () => ({
      mode: userMode === "subscriber" ? "all" : userMode,
      search: search.trim() || undefined,
      page,
      page_size: 20,
    }),
    [page, search, userMode],
  );

  const usersQuery = useListVisitorUsersApiV1AdminVisitorsUsersGet(userParams);
  const response = usersQuery.data?.data;
  const users = response && "items" in response ? response.items : [];
  const total = response && "total" in response ? response.total : 0;

  const deleteVisitor = useDeleteVisitorUserApiV1AdminVisitorsUsersUserIdDelete({
    mutation: {
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: getListVisitorUsersApiV1AdminVisitorsUsersGetQueryKey(),
        });
        setDeleteTarget(null);
        toast.success(t("visitors.deleteUserSuccess"));
      },
      onError: (error) => {
        toast.error(
          extractApiErrorMessage(error, t("visitors.deleteUserFailed")),
        );
      },
    },
  });

  const columns = useMemo(
    () => [
      {
        header: "访客",
        accessor: (row: SiteUserAdminRead) => (
          <div className="flex items-center gap-3">
            <img
              src={row.avatar_url}
              alt={row.display_name}
              className="h-10 w-10 rounded-full border border-border/60 object-cover"
            />
            <div className="min-w-0">
              <div className="truncate font-medium text-foreground">
                {row.display_name}
              </div>
            </div>
          </div>
        ),
      },
      {
        header: "绑定方式",
        accessor: (row: SiteUserAdminRead) =>
          (row.oauth_accounts ?? []).length ? (
            <div className="flex flex-wrap gap-1.5">
              {(row.oauth_accounts ?? []).map((account) => (
                <span
                  key={`${row.id}-${account.provider}`}
                  className={cn(
                    "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold",
                    providerBadgeTone(account.provider),
                  )}
                >
                  {account.provider === "google" ? "Google" : "GitHub"}
                </span>
              ))}
            </div>
          ) : (
            <span className="text-sm text-muted-foreground">仅邮箱</span>
          ),
      },
      {
        header: "最近登录",
        accessor: (row: SiteUserAdminRead) =>
          row.last_login_at ? (
            <span className="text-sm text-muted-foreground">
              {formatDate(row.last_login_at)}
            </span>
          ) : (
            <span className="text-sm text-muted-foreground">未登录</span>
          ),
      },
    ],
    [],
  );

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4 pt-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center sm:justify-between">
        <AdminSegmentedFilter
          value={userMode}
          onValueChange={(next) => {
            setUserMode(next as VisitorUserMode);
            setPage(1);
          }}
          items={USER_MODE_OPTIONS.map((item) => ({
            value: item.key,
            label: item.label,
          }))}
          tone="accent"
        />

        <div className="relative w-full max-w-sm">
          <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={isSubscriberMode ? subscriberSearch : search}
            onChange={(event) => {
              if (isSubscriberMode) {
                setSubscriberSearch(event.target.value);
                return;
              }
              setSearch(event.target.value);
              setPage(1);
            }}
            className="pl-9"
            placeholder={isSubscriberMode ? "搜索订阅邮箱" : "搜索邮箱、昵称"}
          />
        </div>
      </div>

      {userMode === "subscriber" ? (
        <VisitorsSubscribersPanel
          initialMode="subscriber"
          showModeFilter={false}
          showSearch={false}
          searchKeyword={subscriberSearch}
        />
      ) : (
        <DataTable<SiteUserAdminRead>
          columns={columns}
          data={users}
          total={total}
          page={page}
          pageSize={20}
          onPageChange={setPage}
          isLoading={usersQuery.isLoading}
          renderExpandedRow={(row) => (
            <div className="grid items-center gap-x-6 gap-y-2 px-2 py-3 sm:px-4 md:grid-cols-[2.5rem_minmax(0,1.35fr)_minmax(10rem,0.6fr)_minmax(0,0.8fr)]">
              <div className="flex min-w-0 items-center text-sm text-muted-foreground md:col-start-2">
                <span className="shrink-0 font-semibold text-foreground/80">邮箱标识：</span>
                <span className="truncate font-mono">{row.email}</span>
              </div>
              <Button
                type="button"
                variant="destructive"
                size="sm"
                className="justify-self-start md:col-start-3 md:justify-self-center"
                title={t("visitors.deleteUser")}
                onClick={() => setDeleteTarget(row)}
              >
                {t("visitors.deleteUser")}
              </Button>
            </div>
          )}
        />
      )}

      <ConfirmDialog
        open={deleteTarget !== null}
        onConfirm={() => {
          if (deleteTarget) {
            deleteVisitor.mutate({ userId: deleteTarget.id });
          }
        }}
        onCancel={() => {
          if (!deleteVisitor.isPending) {
            setDeleteTarget(null);
          }
        }}
        title={t("visitors.deleteUserTitle")}
        description={t("visitors.deleteUserDescription")}
        confirmLabel={t("common.delete")}
        variant="destructive"
        isPending={deleteVisitor.isPending}
      />
    </div>
  );
}

export default function VisitorsUsersPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="访客用户"
        description=""
        secondary={<VisitorsSectionSwitch />}
      />

      <VisitorsUsersPanel />
    </div>
  );
}
