import { useMemo, useState } from "react";
import { useListVisitorUsersApiV1AdminVisitorsUsersGet } from "@serino/api-client/admin";
import type { SiteUserAdminRead } from "@serino/api-client/models";
import type { ListVisitorUsersApiV1AdminVisitorsUsersGetParams } from "../../../../packages/api-client/src/generated/model/listVisitorUsersApiV1AdminVisitorsUsersGetParams";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { AdminSegmentedFilter } from "@/components/ui/AdminSegmentedFilter";
import { Input } from "@/components/ui/Input";
import { PageHeader } from "@/components/PageHeader";
import { cn, formatDate } from "@/lib/utils";
import { Search } from "lucide-react";
import { VisitorsSectionSwitch } from "@/pages/visitors/VisitorsSectionSwitch";

const USER_MODE_OPTIONS = [
  { key: "all", label: "全部" },
  { key: "email", label: "邮箱" },
  { key: "binding", label: "绑定" },
] as const;

type VisitorUserMode = (typeof USER_MODE_OPTIONS)[number]["key"];

function providerBadgeTone(provider: string) {
  if (provider === "google") return "bg-[#4285F4]/12 text-[#3367D6] border-[#4285F4]/16";
  if (provider === "github") {
    return "bg-slate-900/8 text-slate-700 border-slate-900/12 dark:bg-white/8 dark:text-white/82 dark:border-white/16";
  }
  return "bg-emerald-500/12 text-emerald-700 border-emerald-500/16";
}

export function VisitorsUsersPanel() {
  const [userMode, setUserMode] = useState<VisitorUserMode>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);

  const userParams = useMemo<ListVisitorUsersApiV1AdminVisitorsUsersGetParams>(
    () => ({
      mode: userMode,
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
              <div className="truncate font-medium text-foreground">{row.display_name}</div>
              <div className="truncate text-xs text-muted-foreground">{row.primary_auth_provider}</div>
            </div>
          </div>
        ),
      },
      {
        header: "邮箱标识",
        accessor: (row: SiteUserAdminRead) => (
          <span className="font-mono text-xs text-muted-foreground">{row.email}</span>
        ),
      },
      {
        header: "方式",
        accessor: (row: SiteUserAdminRead) => (
          <Badge variant="outline">{row.auth_mode === "binding" ? "绑定" : "邮箱"}</Badge>
        ),
      },
      {
        header: "绑定",
        accessor: (row: SiteUserAdminRead) =>
          (row.oauth_accounts ?? []).length ? (
            <div className="flex flex-wrap gap-2">
              {(row.oauth_accounts ?? []).map((account) => (
                <span
                  key={`${row.id}-${account.provider}`}
                  className={cn(
                    "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
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
            <span className="text-sm text-muted-foreground">{formatDate(row.last_login_at)}</span>
          ) : (
            <span className="text-sm text-muted-foreground">未登录</span>
          ),
      },
    ],
    [],
  );

  return (
    <div className="space-y-4 pt-6">
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
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setPage(1);
            }}
            className="pl-9"
            placeholder="搜索邮箱、昵称"
          />
        </div>
      </div>

      <DataTable<SiteUserAdminRead>
        columns={columns}
        data={users}
        total={total}
        page={page}
        pageSize={20}
        onPageChange={setPage}
        isLoading={usersQuery.isLoading}
        renderExpandedRow={(row) => (
          <div className="grid gap-3 py-4">
            <div className="text-sm font-medium text-foreground">绑定详情</div>
            {(row.oauth_accounts ?? []).length ? (
              (row.oauth_accounts ?? []).map((account) => (
                <div
                  key={`${row.id}-${account.provider}`}
                  className="grid gap-2 rounded-[var(--admin-radius-md)] border border-border/60 bg-background/55 px-4 py-3 text-sm md:grid-cols-[120px_1fr_1fr_180px]"
                >
                  <div className="font-medium text-foreground">
                    {account.provider === "google" ? "Google" : "GitHub"}
                  </div>
                  <div className="text-muted-foreground">{account.provider_email || "未返回邮箱"}</div>
                  <div className="text-muted-foreground">{account.provider_display_name || "未返回昵称"}</div>
                  <div className="text-muted-foreground">{formatDate(account.created_at)}</div>
                </div>
              ))
            ) : (
              <div className="rounded-[var(--admin-radius-md)] border border-dashed border-border/60 bg-background/40 px-4 py-4 text-sm text-muted-foreground">
                当前用户只有邮箱身份，没有绑定第三方账号。
              </div>
            )}
          </div>
        )}
      />
    </div>
  );
}

export default function VisitorsUsersPage() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="访客用户"
        description="展示所有注册过邮箱或绑定过第三方账号的站点访客。"
        secondary={<VisitorsSectionSwitch />}
      />

      <VisitorsUsersPanel />
    </div>
  );
}
