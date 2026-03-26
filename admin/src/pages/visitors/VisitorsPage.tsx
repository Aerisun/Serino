import { useEffect, useMemo, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";
import {
  getListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGetQueryKey,
  getGetVisitorAuthConfigApiV1AdminVisitorsConfigGetQueryKey,
  getListVisitorUsersApiV1AdminVisitorsUsersGetQueryKey,
  useBindAdminIdentityEmailApiV1AdminVisitorsAdminIdentitiesEmailPost,
  useBindCurrentAdminIdentityApiV1AdminVisitorsAdminIdentitiesBindCurrentPost,
  useDeleteAdminIdentityEndpointApiV1AdminVisitorsAdminIdentitiesIdentityIdDelete,
  useGetVisitorAuthConfigApiV1AdminVisitorsConfigGet,
  useListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGet,
  useListVisitorUsersApiV1AdminVisitorsUsersGet,
  useUpdateVisitorAuthConfigApiV1AdminVisitorsConfigPut,
} from "@serino/api-client/admin";
import type {
  BindCurrentAdminIdentityApiV1AdminVisitorsAdminIdentitiesBindCurrentPostProvider,
  ListVisitorUsersApiV1AdminVisitorsUsersGetParams,
  SiteAdminIdentityAdminRead,
  SiteAuthConfigAdminRead,
  SiteUserAdminRead,
} from "@serino/api-client/models";
import { DataTable } from "@/components/DataTable";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { cn, formatDate } from "@/lib/utils";
import { HintBanner } from "@/components/ui/HintBanner";
import {
  ArrowRight,
  Github,
  KeyRound,
  Loader2,
  Mail,
  Save,
  Search,
  ShieldCheck,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";

const VISITOR_OAUTH_OPTIONS = [
  {
    key: "google",
    label: "Google",
    description: "允许访客使用 Google 绑定并登录站点身份。",
  },
  {
    key: "github",
    label: "GitHub",
    description: "允许访客使用 GitHub 绑定并登录站点身份。",
  },
] as const;

const ADMIN_AUTH_OPTIONS = [
  { key: "google", label: "Google" },
  { key: "github", label: "GitHub" },
] as const;

const USER_MODE_OPTIONS = [
  { key: "all", label: "全部" },
  { key: "email", label: "邮箱" },
  { key: "binding", label: "绑定" },
] as const;

type VisitorOAuthProvider = (typeof VISITOR_OAUTH_OPTIONS)[number]["key"];
type AdminAuthMethod = (typeof ADMIN_AUTH_OPTIONS)[number]["key"];
type VisitorUserMode = (typeof USER_MODE_OPTIONS)[number]["key"];
type BindableAdminProvider = BindCurrentAdminIdentityApiV1AdminVisitorsAdminIdentitiesBindCurrentPostProvider;

interface VisitorAuthFormState {
  email_login_enabled: boolean;
  visitor_oauth_providers: VisitorOAuthProvider[];
  admin_auth_methods: AdminAuthMethod[];
  admin_email_enabled: boolean;
  google_client_id: string;
  google_client_secret: string;
  github_client_id: string;
  github_client_secret: string;
}

function createForm(config?: SiteAuthConfigAdminRead | null): VisitorAuthFormState {
  return {
    email_login_enabled: config?.email_login_enabled ?? true,
    visitor_oauth_providers: (config?.visitor_oauth_providers ?? []) as VisitorOAuthProvider[],
    admin_auth_methods: (config?.admin_auth_methods ?? ["google", "github"]) as AdminAuthMethod[],
    admin_email_enabled: config?.admin_email_enabled ?? false,
    google_client_id: config?.google_client_id ?? "",
    google_client_secret: config?.google_client_secret ?? "",
    github_client_id: config?.github_client_id ?? "",
    github_client_secret: config?.github_client_secret ?? "",
  };
}

function toggleListValue<T extends string>(items: T[], item: T, enabled: boolean) {
  if (enabled) {
    return items.includes(item) ? items : [...items, item];
  }
  return items.filter((value) => value !== item);
}

function providerBadgeTone(provider: string) {
  if (provider === "google") return "bg-[#4285F4]/12 text-[#3367D6] border-[#4285F4]/16";
  if (provider === "github") return "bg-slate-900/8 text-slate-700 border-slate-900/12 dark:bg-white/8 dark:text-white/82 dark:border-white/16";
  return "bg-emerald-500/12 text-emerald-700 border-emerald-500/16";
}

async function getPublicOAuthAuthorizationUrl(provider: "google" | "github", returnTo: string) {
  const query = new URLSearchParams({ return_to: returnTo });
  const response = await fetch(`/api/v1/public/auth/oauth/${provider}/start?${query.toString()}`, {
    method: "GET",
    credentials: "include",
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    throw new Error(String((payload as { detail?: string }).detail || "认证发起失败"));
  }
  return String((payload as { authorization_url?: string }).authorization_url || "");
}

export default function VisitorsPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [form, setForm] = useState<VisitorAuthFormState>(() => createForm());
  const [saveError, setSaveError] = useState("");
  const [userMode, setUserMode] = useState<VisitorUserMode>("all");
  const [search, setSearch] = useState("");
  const [page, setPage] = useState(1);
  const [adminEmail, setAdminEmail] = useState("");
  const [bindingError, setBindingError] = useState("");

  const configQuery = useGetVisitorAuthConfigApiV1AdminVisitorsConfigGet();
  const config = configQuery.data?.data ?? null;
  const adminIdentitiesQuery = useListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGet();
  const adminIdentities = adminIdentitiesQuery.data?.data ?? [];

  useEffect(() => {
    if (config) {
      setForm(createForm(config));
      setSaveError("");
    }
  }, [config]);

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
  const users = usersQuery.data?.data?.items ?? [];
  const total = usersQuery.data?.data?.total ?? 0;

  const save = useUpdateVisitorAuthConfigApiV1AdminVisitorsConfigPut({
    mutation: {
      onMutate: () => setSaveError(""),
      onSuccess: (response) => {
        queryClient.invalidateQueries({
          queryKey: getGetVisitorAuthConfigApiV1AdminVisitorsConfigGetQueryKey(),
        });
        queryClient.invalidateQueries({
          queryKey: getListVisitorUsersApiV1AdminVisitorsUsersGetQueryKey(),
        });
        queryClient.invalidateQueries({
          queryKey: getListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGetQueryKey(),
        });
        if (response.data) {
          setForm(createForm(response.data));
        }
        toast.success("访客认证配置已保存");
      },
      onError: (error) => {
        setSaveError(error instanceof Error ? error.message : "保存失败");
      },
    },
  });

  const updateField = <K extends keyof VisitorAuthFormState>(key: K, value: VisitorAuthFormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const bindEmail = useBindAdminIdentityEmailApiV1AdminVisitorsAdminIdentitiesEmailPost({
    mutation: {
      onMutate: () => setBindingError(""),
      onSuccess: () => {
        setAdminEmail("");
        queryClient.invalidateQueries({
          queryKey: getListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGetQueryKey(),
        });
        queryClient.invalidateQueries({
          queryKey: getListVisitorUsersApiV1AdminVisitorsUsersGetQueryKey(),
        });
        toast.success("管理员邮箱身份已绑定");
      },
      onError: (error) => {
        setBindingError(error instanceof Error ? error.message : "管理员邮箱绑定失败");
      },
    },
  });

  const bindCurrent = useBindCurrentAdminIdentityApiV1AdminVisitorsAdminIdentitiesBindCurrentPost({
    mutation: {
      onMutate: () => setBindingError(""),
      onSuccess: (response, variables) => {
        queryClient.invalidateQueries({
          queryKey: getListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGetQueryKey(),
        });
        queryClient.invalidateQueries({
          queryKey: getListVisitorUsersApiV1AdminVisitorsUsersGetQueryKey(),
        });
        const provider = variables.params.provider === "google" ? "Google" : variables.params.provider === "github" ? "GitHub" : "邮箱";
        toast.success(`${provider} 管理员身份已绑定`);
      },
      onError: (error) => {
        setBindingError(error instanceof Error ? error.message : "管理员身份绑定失败");
      },
    },
  });

  const deleteAdminIdentity = useDeleteAdminIdentityEndpointApiV1AdminVisitorsAdminIdentitiesIdentityIdDelete({
    mutation: {
      onSuccess: () => {
        queryClient.invalidateQueries({
          queryKey: getListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGetQueryKey(),
        });
        toast.success("管理员身份已移除");
      },
      onError: (error) => {
        setBindingError(error instanceof Error ? error.message : "管理员身份删除失败");
      },
    },
  });

  useEffect(() => {
    const provider = searchParams.get("admin_bind_provider") as BindableAdminProvider | null;
    const authResult = searchParams.get("auth");
    if (!provider || authResult !== "success") {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.delete("admin_bind_provider");
    next.delete("auth");
    setSearchParams(next, { replace: true });
    bindCurrent.mutate({ params: { provider } });
  }, [bindCurrent, searchParams, setSearchParams]);

  const startAdminOAuthBinding = async (provider: "google" | "github") => {
    setBindingError("");
    const returnTo = `/admin/visitors?admin_bind_provider=${provider}`;
    try {
      const authorizationUrl = await getPublicOAuthAuthorizationUrl(provider, returnTo);
      if (!authorizationUrl) {
        throw new Error("没有拿到可用的认证地址");
      }
      window.location.assign(authorizationUrl);
    } catch (error) {
      setBindingError(error instanceof Error ? error.message : "认证发起失败");
    }
  };

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
          row.oauth_accounts.length ? (
            <div className="flex flex-wrap gap-2">
              {row.oauth_accounts.map((account) => (
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

  if (configQuery.isLoading && !config) {
    return <p className="py-6 text-muted-foreground">加载中...</p>;
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight text-foreground">访客</h1>
          <p className="mt-2 max-w-3xl text-sm leading-6 text-muted-foreground">
            统一管理访客的邮箱登录、Google / GitHub 绑定，以及后台预留的管理员认证方式。
          </p>
        </div>
        <Button
          type="button"
          onClick={() => save.mutate({ data: form })}
          disabled={save.isPending}
          className="min-w-[9rem] gap-2"
        >
          <Save className="h-4 w-4" />
          {save.isPending ? "保存中..." : "保存配置"}
        </Button>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.4fr_1fr]">
        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-xl">
              <KeyRound className="h-5 w-5 text-primary" />
              访客绑定
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <AppleSwitch
              checked={form.email_login_enabled}
              onCheckedChange={(checked) => updateField("email_login_enabled", checked)}
              label="邮箱登录"
              description="允许访客仅凭邮箱标识进入评论身份。"
            />

            {VISITOR_OAUTH_OPTIONS.map((provider) => {
              const enabled = form.visitor_oauth_providers.includes(provider.key);
              const idField = provider.key === "google" ? "google_client_id" : "github_client_id";
              const secretField =
                provider.key === "google" ? "google_client_secret" : "github_client_secret";
              return (
                <div key={provider.key} className="rounded-2xl border border-border/60 bg-background/45 p-4">
                  <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                    <div className="space-y-1">
                      <div className="text-base font-semibold text-foreground">{provider.label}</div>
                      <p className="text-sm text-muted-foreground">{provider.description}</p>
                    </div>
                    <AppleSwitch
                      checked={enabled}
                      onCheckedChange={(checked) =>
                        updateField(
                          "visitor_oauth_providers",
                          toggleListValue(form.visitor_oauth_providers, provider.key, checked),
                        )
                      }
                    />
                  </div>
                  <div className={cn("mt-4 grid gap-4 md:grid-cols-2", !enabled && "opacity-70")}>
                    <div className="space-y-1">
                      <Label>Client ID</Label>
                      <Input
                        value={form[idField]}
                        onChange={(event) => updateField(idField, event.target.value)}
                        placeholder={`${provider.label} client id`}
                      />
                    </div>
                    <div className="space-y-1">
                      <Label>Client Secret</Label>
                      <Input
                        type="password"
                        value={form[secretField]}
                        onChange={(event) => updateField(secretField, event.target.value)}
                        placeholder={`${provider.label} client secret`}
                      />
                    </div>
                  </div>
                </div>
              );
            })}

            {saveError ? (
              <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
                {saveError}
              </div>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-4">
            <CardTitle className="flex items-center gap-2 text-xl">
              <ShieldCheck className="h-5 w-5 text-primary" />
              管理员认证
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <HintBanner>
              这里绑定的是“前台管理员身份”。绑定成功后，对应邮箱或 OAuth 账号在前台登录时会直接切换成站点标题 + Hero 图的管理员模式。
            </HintBanner>
            <div className="rounded-2xl border border-border/60 bg-background/45 p-4">
              <div className="text-sm font-semibold text-foreground">允许的管理员认证方式</div>
              <div className="mt-3 flex flex-wrap gap-2">
                {ADMIN_AUTH_OPTIONS.map((item) => {
                  const active = form.admin_auth_methods.includes(item.key);
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() =>
                        updateField(
                          "admin_auth_methods",
                          toggleListValue(form.admin_auth_methods, item.key, !active),
                        )
                      }
                      className={cn(
                        "inline-flex items-center rounded-full border px-4 py-2 text-sm font-medium transition",
                        active
                          ? "border-[rgb(var(--shiro-accent-rgb)/0.22)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] text-[rgb(var(--shiro-accent-rgb)/0.96)]"
                          : "border-border/60 bg-background/55 text-muted-foreground hover:text-foreground",
                      )}
                    >
                      {item.label}
                    </button>
                  );
                })}
              </div>

              <div className="mt-4">
                <AppleSwitch
                  checked={form.admin_email_enabled}
                  onCheckedChange={(checked) => updateField("admin_email_enabled", checked)}
                  label="管理员邮箱身份"
                  description="开启后，可以直接把某个邮箱标识保存为前台管理员身份。"
                />
              </div>
            </div>

            <div className="rounded-2xl border border-border/60 bg-background/45 p-4">
              <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                <ShieldCheck className="h-4 w-4 text-primary" />
                认证并绑定
              </div>
              <p className="mt-2 text-sm leading-6 text-muted-foreground">
                Google / GitHub 会先完成一次前台认证，再自动回到这里保存为管理员身份。邮箱因为本身就是站内标识，所以直接录入即可。
              </p>
              <div className="mt-4 grid gap-3">
                {ADMIN_AUTH_OPTIONS.map((item) => {
                  const active = form.admin_auth_methods.includes(item.key);
                  const pending = bindCurrent.isPending;
                  return (
                    <button
                      key={item.key}
                      type="button"
                      disabled={!active || pending}
                      onClick={() => void startAdminOAuthBinding(item.key)}
                      className={cn(
                        "flex items-center justify-between rounded-2xl border px-4 py-3 text-left transition",
                        active
                          ? "border-border/60 bg-background/70 hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:bg-background/90"
                          : "cursor-not-allowed border-border/40 bg-background/35 opacity-55",
                      )}
                    >
                      <div className="flex items-center gap-3">
                        <span
                          className={cn(
                            "inline-flex h-10 w-10 items-center justify-center rounded-full border",
                            item.key === "google"
                              ? "border-[#4285F4]/16 bg-[#4285F4]/10 text-[#3367D6]"
                              : "border-slate-900/12 bg-slate-900/8 text-slate-700 dark:border-white/16 dark:bg-white/8 dark:text-white/82",
                          )}
                        >
                          {item.key === "google" ? <ShieldCheck className="h-4 w-4" /> : <Github className="h-4 w-4" />}
                        </span>
                        <div>
                          <div className="text-sm font-medium text-foreground">{item.label}</div>
                          <div className="text-xs text-muted-foreground">
                            {active ? "完成一次认证后保存为管理员身份" : "先在上方开启这个方式"}
                          </div>
                        </div>
                      </div>
                      {pending ? <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" /> : <ArrowRight className="h-4 w-4 text-muted-foreground" />}
                    </button>
                  );
                })}
              </div>

              <div className={cn("mt-4 rounded-2xl border border-border/60 bg-background/70 p-4", !form.admin_email_enabled && "opacity-60")}>
                <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                  <Mail className="h-4 w-4 text-primary" />
                  邮箱管理员身份
                </div>
                <div className="mt-3 flex flex-col gap-3 sm:flex-row">
                  <Input
                    value={adminEmail}
                    onChange={(event) => setAdminEmail(event.target.value)}
                    placeholder="输入管理员邮箱标识"
                    disabled={!form.admin_email_enabled || bindEmail.isPending}
                  />
                  <Button
                    type="button"
                    onClick={() => bindEmail.mutate({ data: { email: adminEmail } })}
                    disabled={!form.admin_email_enabled || bindEmail.isPending || !adminEmail.trim()}
                    className="gap-2"
                  >
                    {bindEmail.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                    绑定邮箱
                  </Button>
                </div>
              </div>
            </div>

            <div className="rounded-2xl border border-border/60 bg-background/45 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-sm font-semibold text-foreground">已绑定的管理员前台身份</div>
                <Badge variant="outline">{adminIdentities.length} 个</Badge>
              </div>
              <div className="mt-4 space-y-3">
                {adminIdentitiesQuery.isLoading ? (
                  <div className="rounded-2xl border border-dashed border-border/60 bg-background/35 px-4 py-4 text-sm text-muted-foreground">
                    正在加载管理员身份...
                  </div>
                ) : adminIdentities.length ? (
                  adminIdentities.map((identity: SiteAdminIdentityAdminRead) => (
                    <div
                      key={identity.id}
                      className="flex flex-col gap-4 rounded-2xl border border-border/60 bg-background/70 px-4 py-4"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-3">
                          <img
                            src={identity.site_user_avatar_url}
                            alt={identity.site_user_display_name}
                            className="h-10 w-10 rounded-full border border-border/60 object-cover"
                          />
                          <div className="min-w-0">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="truncate font-medium text-foreground">{identity.site_user_display_name}</span>
                              <span
                                className={cn(
                                  "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
                                  providerBadgeTone(identity.provider),
                                )}
                              >
                                {identity.provider === "google" ? "Google" : identity.provider === "github" ? "GitHub" : "邮箱"}
                              </span>
                            </div>
                            <div className="mt-1 text-xs text-muted-foreground">{identity.email}</div>
                          </div>
                        </div>
                        <button
                          type="button"
                          onClick={() => deleteAdminIdentity.mutate({ identityId: identity.id })}
                          disabled={deleteAdminIdentity.isPending}
                          className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-rose-500/16 bg-rose-500/6 text-rose-600 transition hover:bg-rose-500/12 disabled:opacity-60 dark:text-rose-300"
                          aria-label="删除管理员身份"
                        >
                          {deleteAdminIdentity.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                        </button>
                      </div>
                      <div className="grid gap-2 text-xs text-muted-foreground sm:grid-cols-2">
                        <div>标识：{identity.identifier}</div>
                        <div>绑定时间：{formatDate(identity.updated_at)}</div>
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-2xl border border-dashed border-border/60 bg-background/35 px-4 py-4 text-sm text-muted-foreground">
                    还没有绑定管理员前台身份。绑定后，前台登录会直接进入站点标题与 Hero 图的管理员模式。
                  </div>
                )}
              </div>
            </div>

            {bindingError ? (
              <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
                {bindingError}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>

      <Card>
        <CardHeader className="pb-4">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <CardTitle className="text-xl">访客用户</CardTitle>
              <p className="mt-2 text-sm text-muted-foreground">
                展示所有注册过邮箱或绑定过第三方账号的站点访客。
              </p>
            </div>
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
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-2">
            {USER_MODE_OPTIONS.map((item) => {
              const active = userMode === item.key;
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => {
                    setUserMode(item.key);
                    setPage(1);
                  }}
                  className={cn(
                    "inline-flex items-center rounded-full border px-4 py-2 text-sm font-medium transition",
                    active
                      ? "border-[rgb(var(--shiro-accent-rgb)/0.22)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] text-[rgb(var(--shiro-accent-rgb)/0.96)]"
                      : "border-border/60 bg-background/55 text-muted-foreground hover:text-foreground",
                  )}
                >
                  {item.label}
                </button>
              );
            })}
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
                {row.oauth_accounts.length ? (
                  row.oauth_accounts.map((account) => (
                    <div
                      key={`${row.id}-${account.provider}`}
                      className="grid gap-2 rounded-xl border border-border/60 bg-background/55 px-4 py-3 text-sm md:grid-cols-[120px_1fr_1fr_180px]"
                    >
                      <div className="font-medium text-foreground">
                        {account.provider === "google" ? "Google" : "GitHub"}
                      </div>
                      <div className="text-muted-foreground">
                        {account.provider_email || "未返回邮箱"}
                      </div>
                      <div className="text-muted-foreground">
                        {account.provider_display_name || "未返回昵称"}
                      </div>
                      <div className="text-muted-foreground">{formatDate(account.created_at)}</div>
                    </div>
                  ))
                ) : (
                  <div className="rounded-xl border border-dashed border-border/60 bg-background/40 px-4 py-4 text-sm text-muted-foreground">
                    当前用户只有邮箱身份，没有绑定第三方账号。
                  </div>
                )}
              </div>
            )}
          />
        </CardContent>
      </Card>
    </div>
  );
}
