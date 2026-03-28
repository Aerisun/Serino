import { useEffect, useState } from "react";
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
  useSystemInfoApiV1AdminSystemInfoGet,
  useListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGet,
  useUpdateVisitorAuthConfigApiV1AdminVisitorsConfigPut,
} from "@serino/api-client/admin";
import type {
  BindCurrentAdminIdentityApiV1AdminVisitorsAdminIdentitiesBindCurrentPostProvider,
  SiteAdminIdentityAdminRead,
  SiteAuthConfigAdminRead,
} from "@serino/api-client/models";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { PageHeader } from "@/components/PageHeader";
import { DirtySaveButton, PendingSaveBadge } from "@/components/ui/DirtySaveButton";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { cn, formatDate } from "@/lib/utils";
import { VisitorsSectionSwitch } from "@/pages/visitors/VisitorsSectionSwitch";
import {
  Copy,
  ChevronDown,
  ExternalLink,
  Globe,
  Github,
  KeyRound,
  Loader2,
  Mail,
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

type VisitorOAuthProvider = (typeof VISITOR_OAUTH_OPTIONS)[number]["key"];
type AdminAuthMethod = (typeof ADMIN_AUTH_OPTIONS)[number]["key"];
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

const accentStepBadgeClass =
  "inline-flex h-7 w-7 shrink-0 items-center justify-center rounded-full border border-[rgb(var(--admin-accent-rgb)/0.18)] bg-[rgb(var(--admin-accent-rgb)/0.1)] text-xs font-semibold text-[rgb(var(--admin-accent-rgb)/0.96)]";
const accentIconBadgeClass =
  "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border border-[rgb(var(--admin-accent-rgb)/0.16)] bg-[rgb(var(--admin-accent-rgb)/0.1)] text-[rgb(var(--admin-accent-rgb)/0.96)]";
const adminPanelCardClass =
  "admin-glass rounded-[var(--admin-radius-lg)] px-4 py-4 shadow-[var(--admin-shadow-sm)]";

function adminMethodCardClass(active: boolean) {
  return cn(
    "admin-transition-fast flex items-center gap-3 rounded-[var(--admin-radius-lg)] border px-4 py-3 text-left transition-[background-color,border-color,color,box-shadow,transform]",
    active
      ? "border-[rgb(var(--admin-accent-rgb)/0.22)] bg-[rgb(var(--admin-accent-rgb)/0.1)] text-[rgb(var(--admin-accent-rgb)/0.96)] shadow-[0_18px_42px_-28px_rgb(var(--admin-accent-rgb)/0.45)]"
      : "border-border/60 bg-background/55 text-muted-foreground hover:border-border hover:text-foreground",
  );
}

function adminStatusPillClass(active: boolean) {
  return cn(
    "inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-medium",
    active
      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200"
      : "border-border/60 bg-background/60 text-muted-foreground",
  );
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

function normalizeOrigin(value: string | undefined, fallback: string) {
  const candidate = (value || "").trim() || fallback;
  try {
    return new URL(candidate, fallback).origin;
  } catch {
    return fallback;
  }
}

function buildOAuthCallbackUrl(origin: string, provider: VisitorOAuthProvider) {
  return `${origin.replace(/\/+$/, "")}/api/v1/public/auth/oauth/${provider}/callback`;
}

function getOAuthCredentialFields(provider: VisitorOAuthProvider) {
  return provider === "google"
    ? { idField: "google_client_id" as const, secretField: "google_client_secret" as const }
    : { idField: "github_client_id" as const, secretField: "github_client_secret" as const };
}

function formatProviderLabel(provider: VisitorOAuthProvider | BindableAdminProvider) {
  return provider === "google" ? "Google" : provider === "github" ? "GitHub" : "邮箱";
}

function buildEmptyExpandedProviders() {
  return {
    google: false,
    github: false,
  } satisfies Record<VisitorOAuthProvider, boolean>;
}

interface CompactSwitchProps {
  checked: boolean;
  onCheckedChange: (checked: boolean) => void;
  disabled?: boolean;
  ariaLabel: string;
}

function CompactSwitch({ checked, onCheckedChange, disabled = false, ariaLabel }: CompactSwitchProps) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      aria-label={ariaLabel}
      onClick={() => onCheckedChange(!checked)}
      disabled={disabled}
      className={cn(
        "relative inline-flex h-8 w-14 shrink-0 items-center overflow-hidden rounded-full border transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
        checked
          ? "border-sky-400/45 bg-gradient-to-r from-sky-500/35 via-cyan-400/25 to-emerald-400/25 shadow-[inset_0_1px_0_rgba(255,255,255,0.24),0_0_0_1px_rgba(56,189,248,0.14),0_10px_28px_rgba(14,165,233,0.12)]"
          : "border-slate-400/25 bg-slate-500/12 shadow-[inset_0_1px_0_rgba(255,255,255,0.14),0_0_0_1px_rgba(148,163,184,0.08)]",
        disabled && "pointer-events-none opacity-60",
      )}
    >
      <span
        className={cn(
          "pointer-events-none relative block h-6 w-6 rounded-full bg-white shadow-[0_8px_18px_rgba(15,23,42,0.18)] ring-1 ring-black/5 transition-transform duration-200 before:absolute before:inset-[0.15rem] before:rounded-full before:bg-gradient-to-br before:from-white/90 before:to-white/35 before:content-[''] dark:bg-slate-100 dark:ring-white/10 dark:before:from-white/45 dark:before:to-white/10",
          checked ? "translate-x-6" : "translate-x-1",
        )}
      />
    </button>
  );
}

export default function VisitorsPage() {
  const queryClient = useQueryClient();
  const [searchParams, setSearchParams] = useSearchParams();
  const [form, setForm] = useState<VisitorAuthFormState>(() => createForm());
  const [savedForm, setSavedForm] = useState<VisitorAuthFormState | null>(null);
  const [visitorSaveError, setVisitorSaveError] = useState("");
  const [adminEmail, setAdminEmail] = useState("");
  const [bindingError, setBindingError] = useState("");
  const [testingProvider, setTestingProvider] = useState<VisitorOAuthProvider | null>(null);
  const [savingProvider, setSavingProvider] = useState<VisitorOAuthProvider | null>(null);
  const [savingEmailLogin, setSavingEmailLogin] = useState(false);
  const [savingAdminConfig, setSavingAdminConfig] = useState(false);
  const [expandedProviders, setExpandedProviders] =
    useState<Record<VisitorOAuthProvider, boolean>>(buildEmptyExpandedProviders);

  const configQuery = useGetVisitorAuthConfigApiV1AdminVisitorsConfigGet();
  const config = configQuery.data?.data ?? null;
  const adminIdentitiesQuery = useListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGet();
  const adminIdentities = adminIdentitiesQuery.data?.data ?? [];
  const { data: systemInfo } = useSystemInfoApiV1AdminSystemInfoGet();
  const adminOrigin = window.location.origin;
  const frontendOrigin = normalizeOrigin(systemInfo?.site_url, adminOrigin);

  useEffect(() => {
    if (config && !savedForm) {
      const nextForm = createForm(config);
      setForm(nextForm);
      setSavedForm(nextForm);
      setVisitorSaveError("");
    }
  }, [config, savedForm]);

  const saveVisitorProviderConfig = useUpdateVisitorAuthConfigApiV1AdminVisitorsConfigPut();
  const saveVisitorEmailConfig = useUpdateVisitorAuthConfigApiV1AdminVisitorsConfigPut();
  const saveAdminConfig = useUpdateVisitorAuthConfigApiV1AdminVisitorsConfigPut();

  const updateField = <K extends keyof VisitorAuthFormState>(key: K, value: VisitorAuthFormState[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
  };

  const getBaseSavedForm = () => savedForm ?? createForm(config);

  const invalidateConfigQueries = () => {
    void queryClient.invalidateQueries({
      queryKey: getGetVisitorAuthConfigApiV1AdminVisitorsConfigGetQueryKey(),
    });
    void queryClient.invalidateQueries({
      queryKey: getListVisitorUsersApiV1AdminVisitorsUsersGetQueryKey(),
    });
    void queryClient.invalidateQueries({
      queryKey: getListAdminIdentitiesApiV1AdminVisitorsAdminIdentitiesGetQueryKey(),
    });
  };

  const syncSavedEmailLogin = (nextConfig: SiteAuthConfigAdminRead) => {
    const nextForm = createForm(nextConfig);
    setSavedForm((current) => ({
      ...(current ?? nextForm),
      email_login_enabled: nextForm.email_login_enabled,
    }));
    setForm((current) => ({
      ...current,
      email_login_enabled: nextForm.email_login_enabled,
    }));
  };

  const syncSavedAdminConfig = (nextConfig: SiteAuthConfigAdminRead) => {
    const nextForm = createForm(nextConfig);
    setSavedForm((current) => ({
      ...(current ?? nextForm),
      admin_auth_methods: nextForm.admin_auth_methods,
      admin_email_enabled: nextForm.admin_email_enabled,
    }));
    setForm((current) => ({
      ...current,
      admin_auth_methods: nextForm.admin_auth_methods,
      admin_email_enabled: nextForm.admin_email_enabled,
    }));
  };

  const syncSavedOAuthProvider = (provider: VisitorOAuthProvider, nextConfig: SiteAuthConfigAdminRead) => {
    const nextForm = createForm(nextConfig);
    const { idField, secretField } = getOAuthCredentialFields(provider);
    const nextEnabled = nextForm.visitor_oauth_providers.includes(provider);
    setSavedForm((current) => {
      const base = current ?? nextForm;
      return {
        ...base,
        visitor_oauth_providers: toggleListValue(base.visitor_oauth_providers, provider, nextEnabled),
        [idField]: nextForm[idField],
        [secretField]: nextForm[secretField],
      };
    });
    setForm((current) => ({
      ...current,
      visitor_oauth_providers: toggleListValue(current.visitor_oauth_providers, provider, nextEnabled),
      [idField]: nextForm[idField],
      [secretField]: nextForm[secretField],
    }));
  };

  const syncSavedOAuthProviderToggle = (provider: VisitorOAuthProvider, nextConfig: SiteAuthConfigAdminRead) => {
    const nextForm = createForm(nextConfig);
    const nextEnabled = nextForm.visitor_oauth_providers.includes(provider);
    setSavedForm((current) => {
      const base = current ?? nextForm;
      return {
        ...base,
        visitor_oauth_providers: toggleListValue(base.visitor_oauth_providers, provider, nextEnabled),
      };
    });
    setForm((current) => ({
      ...current,
      visitor_oauth_providers: toggleListValue(current.visitor_oauth_providers, provider, nextEnabled),
    }));
  };

  const buildOAuthProviderSavePayload = (provider: VisitorOAuthProvider): VisitorAuthFormState => {
    const base = getBaseSavedForm();
    const { idField, secretField } = getOAuthCredentialFields(provider);
    const enabled = form.visitor_oauth_providers.includes(provider);
    return {
      ...base,
      visitor_oauth_providers: toggleListValue(base.visitor_oauth_providers, provider, enabled),
      [idField]: form[idField],
      [secretField]: form[secretField],
    };
  };

  const buildOAuthProviderTogglePayload = (
    provider: VisitorOAuthProvider,
    checked: boolean,
  ): VisitorAuthFormState => ({
    ...getBaseSavedForm(),
    visitor_oauth_providers: toggleListValue(getBaseSavedForm().visitor_oauth_providers, provider, checked),
  });

  const buildAdminSavePayload = (
    nextAdmin: Pick<VisitorAuthFormState, "admin_auth_methods" | "admin_email_enabled">,
  ): VisitorAuthFormState => ({
    ...getBaseSavedForm(),
    ...nextAdmin,
  });

  const saveOAuthProvider = async (
    provider: VisitorOAuthProvider,
    options?: { silent?: boolean; requireCredentials?: boolean },
  ) => {
    const enabled = form.visitor_oauth_providers.includes(provider);
    const { idField, secretField } = getOAuthCredentialFields(provider);
    if (options?.requireCredentials !== false && enabled && (!form[idField].trim() || !form[secretField].trim())) {
      setVisitorSaveError("先把 Client ID 和 Client Secret 填完整");
      return false;
    }

    setVisitorSaveError("");
    setSavingProvider(provider);
    try {
      const response = await saveVisitorProviderConfig.mutateAsync({
        data: buildOAuthProviderSavePayload(provider),
      });
      if (response.data) {
        syncSavedOAuthProvider(provider, response.data);
      }
      invalidateConfigQueries();
      if (!options?.silent) {
        toast.success("保存成功");
      }
      return true;
    } catch (error) {
      setVisitorSaveError(error instanceof Error ? error.message : "保存失败");
      return false;
    } finally {
      setSavingProvider((current) => (current === provider ? null : current));
    }
  };

  const handleOAuthProviderToggle = async (provider: VisitorOAuthProvider, checked: boolean) => {
    const previousProviders = form.visitor_oauth_providers;
    const nextProviders = toggleListValue(previousProviders, provider, checked);
    setForm((current) => ({
      ...current,
      visitor_oauth_providers: nextProviders,
    }));
    if (checked) {
      setExpandedProviders((current) => ({ ...current, [provider]: true }));
    }
    setVisitorSaveError("");
    setSavingProvider(provider);
    try {
      const response = await saveVisitorProviderConfig.mutateAsync({
        data: buildOAuthProviderTogglePayload(provider, checked),
      });
      if (response.data) {
        syncSavedOAuthProviderToggle(provider, response.data);
      }
      invalidateConfigQueries();
    } catch (error) {
      setForm((current) => ({
        ...current,
        visitor_oauth_providers: previousProviders,
      }));
      setVisitorSaveError(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSavingProvider((current) => (current === provider ? null : current));
    }
  };

  const persistAdminConfig = async (
    nextAdmin: Pick<VisitorAuthFormState, "admin_auth_methods" | "admin_email_enabled">,
    onErrorRestore?: () => void,
  ) => {
    setBindingError("");
    setSavingAdminConfig(true);
    try {
      const response = await saveAdminConfig.mutateAsync({
        data: buildAdminSavePayload(nextAdmin),
      });
      if (response.data) {
        syncSavedAdminConfig(response.data);
      }
      invalidateConfigQueries();
      return true;
    } catch (error) {
      onErrorRestore?.();
      setBindingError(error instanceof Error ? error.message : "保存失败");
      return false;
    } finally {
      setSavingAdminConfig(false);
    }
  };

  const handleEmailLoginToggle = async (checked: boolean) => {
    const previous = form.email_login_enabled;
    updateField("email_login_enabled", checked);
    setVisitorSaveError("");
    setSavingEmailLogin(true);
    try {
      const response = await saveVisitorEmailConfig.mutateAsync({
        data: {
          ...getBaseSavedForm(),
          email_login_enabled: checked,
        },
      });
      if (response.data) {
        syncSavedEmailLogin(response.data);
      }
      invalidateConfigQueries();
      toast.success("保存成功");
    } catch (error) {
      updateField("email_login_enabled", previous);
      setVisitorSaveError(error instanceof Error ? error.message : "保存失败");
    } finally {
      setSavingEmailLogin(false);
    }
  };

  const handleAdminMethodToggle = async (method: AdminAuthMethod) => {
    const previous = form.admin_auth_methods;
    const nextMethods = toggleListValue(previous, method, !previous.includes(method));
    setForm((current) => ({ ...current, admin_auth_methods: nextMethods }));
    await persistAdminConfig(
      {
        admin_auth_methods: nextMethods,
        admin_email_enabled: form.admin_email_enabled,
      },
      () => setForm((current) => ({ ...current, admin_auth_methods: previous })),
    );
  };

  const handleAdminEmailToggle = async () => {
    const previous = form.admin_email_enabled;
    const nextEnabled = !previous;
    setForm((current) => ({ ...current, admin_email_enabled: nextEnabled }));
    await persistAdminConfig(
      {
        admin_auth_methods: form.admin_auth_methods,
        admin_email_enabled: nextEnabled,
      },
      () => setForm((current) => ({ ...current, admin_email_enabled: previous })),
    );
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
        toast.success("管理员邮箱身份已保存");
      },
      onError: (error) => {
        setBindingError(error instanceof Error ? error.message : "管理员邮箱绑定失败");
      },
    },
  });

  const handleBindAdminEmail = async () => {
    const saved = await persistAdminConfig({
      admin_auth_methods: form.admin_auth_methods,
      admin_email_enabled: form.admin_email_enabled,
    });
    if (!saved) {
      return;
    }
    bindEmail.mutate({ data: { email: adminEmail } });
  };

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
        toast.success(`${formatProviderLabel(variables.params.provider)} 认证成功，管理员身份已保存`);
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

  useEffect(() => {
    const provider = searchParams.get("oauth_test_provider") as VisitorOAuthProvider | null;
    const authResult = searchParams.get("auth");
    if (!provider || authResult !== "success") {
      return;
    }
    const next = new URLSearchParams(searchParams);
    next.delete("oauth_test_provider");
    next.delete("auth");
    setSearchParams(next, { replace: true });
    setTestingProvider(null);
    toast.success(`${provider === "google" ? "Google" : "GitHub"} 认证测试成功`);
  }, [searchParams, setSearchParams]);

  const copyText = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      toast.success(`${label}已复制`);
    } catch {
      toast.error("复制失败");
    }
  };

  const startAdminOAuthBinding = async (provider: "google" | "github") => {
    setBindingError("");
    const returnTo = `/admin/visitors?admin_bind_provider=${provider}`;
    try {
      const saved = await persistAdminConfig({
        admin_auth_methods: form.admin_auth_methods,
        admin_email_enabled: form.admin_email_enabled,
      });
      if (!saved) {
        return;
      }
      const authorizationUrl = await getPublicOAuthAuthorizationUrl(provider, returnTo);
      if (!authorizationUrl) {
        throw new Error("没有拿到可用的认证地址");
      }
      window.location.assign(authorizationUrl);
    } catch (error) {
      setBindingError(error instanceof Error ? error.message : "认证发起失败");
    }
  };

  const startOAuthTest = async (provider: VisitorOAuthProvider) => {
    const idField = provider === "google" ? "google_client_id" : "github_client_id";
    const secretField = provider === "google" ? "google_client_secret" : "github_client_secret";
    if (!form.visitor_oauth_providers.includes(provider)) {
      toast.error("先开启这个登录方式再测试");
      return;
    }
    if (!form[idField].trim() || !form[secretField].trim()) {
      toast.error("先把 Client ID 和 Client Secret 填完整");
      return;
    }
    setTestingProvider(provider);
    try {
      const saved = await saveOAuthProvider(provider, { silent: true });
      if (!saved) {
        setTestingProvider(null);
        return;
      }
      const authorizationUrl = await getPublicOAuthAuthorizationUrl(
        provider,
        `/admin/visitors?oauth_test_provider=${provider}`,
      );
      if (!authorizationUrl) {
        throw new Error("没有拿到可用的认证地址");
      }
      window.location.assign(authorizationUrl);
    } catch (error) {
      setTestingProvider(null);
      toast.error(error instanceof Error ? error.message : "测试认证发起失败");
    }
  };

  if (configQuery.isLoading && !config) {
    return <p className="py-6 text-muted-foreground">加载中...</p>;
  }

  const effectiveSavedForm = savedForm ?? (config ? createForm(config) : null);

  return (
    <div className="space-y-6">
      <PageHeader
        title="访客"
        description="统一管理访客的邮箱登录、Google / GitHub 绑定，以及后台预留的管理员认证方式。"
        secondary={<VisitorsSectionSwitch />}
      />

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
              onCheckedChange={(checked) => void handleEmailLoginToggle(checked)}
              label="邮箱登录"
              description="允许访客仅凭邮箱标识进入评论身份。"
              disabled={savingEmailLogin}
            />

            {VISITOR_OAUTH_OPTIONS.map((provider) => {
              const enabled = form.visitor_oauth_providers.includes(provider.key);
              const { idField, secretField } = getOAuthCredentialFields(provider.key);
              const publicCallbackUrl = buildOAuthCallbackUrl(frontendOrigin, provider.key);
              const adminCallbackUrl = buildOAuthCallbackUrl(adminOrigin, provider.key);
              const isTesting = testingProvider === provider.key;
              const isSaving = savingProvider === provider.key;
              const expanded = expandedProviders[provider.key];
              const hasCredentialDirty =
                (effectiveSavedForm?.[idField] ?? "") !== form[idField] ||
                (effectiveSavedForm?.[secretField] ?? "") !== form[secretField];
              const showSaveButton = enabled || hasCredentialDirty || isSaving;
              const githubNeedsSeparateLocalApp =
                provider.key === "github" && publicCallbackUrl !== adminCallbackUrl;
              return (
                <div
                  key={provider.key}
                  className={cn(
                    "overflow-hidden rounded-[var(--admin-radius-xl)] border shadow-[var(--admin-shadow-sm)] transition-[border-color,box-shadow]",
                    expanded
                      ? "border-[rgb(var(--admin-accent-rgb)/0.22)] bg-[linear-gradient(180deg,rgb(var(--admin-surface-strong)/0.78),rgb(var(--admin-surface-1)/0.56))]"
                      : "admin-glass border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))]",
                    hasCredentialDirty && "shadow-[0_22px_48px_-36px_rgb(var(--admin-accent-rgb)/0.48)]",
                  )}
                >
                  <div className="flex flex-col gap-3 px-4 py-4 md:flex-row md:items-center md:justify-between">
                    <div className="min-w-0 space-y-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <div className="text-base font-semibold text-foreground">{provider.label}</div>
                        <span
                          className={cn(
                            "inline-flex items-center rounded-full border px-2.5 py-1 text-[11px] font-medium",
                            enabled
                              ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-700 dark:text-emerald-200"
                              : "border-border/60 bg-background/60 text-muted-foreground",
                          )}
                        >
                          {enabled ? "已开启" : "已关闭"}
                        </span>
                        {hasCredentialDirty ? <PendingSaveBadge /> : null}
                      </div>
                      <p className="text-sm text-muted-foreground">{provider.description}</p>
                    </div>

                    <div className="flex shrink-0 items-center gap-2 self-end md:self-auto">
                      {showSaveButton ? (
                        <DirtySaveButton
                          dirty={hasCredentialDirty}
                          saving={isSaving}
                          onClick={() => void saveOAuthProvider(provider.key)}
                        />
                      ) : null}
                      <CompactSwitch
                        checked={enabled}
                        onCheckedChange={(checked) => void handleOAuthProviderToggle(provider.key, checked)}
                        disabled={isSaving || isTesting}
                        ariaLabel={`${provider.label} 登录开关`}
                      />
                      <Button
                        type="button"
                        variant="ghost"
                        size="icon"
                        onClick={() =>
                          setExpandedProviders((current) => ({
                            ...current,
                            [provider.key]: !current[provider.key],
                          }))
                        }
                        aria-label={expanded ? `收起 ${provider.label} 配置` : `展开 ${provider.label} 配置`}
                        className="h-9 w-9 rounded-full"
                      >
                        <ChevronDown className={cn("h-4 w-4 transition-transform duration-200", expanded && "rotate-180")} />
                      </Button>
                    </div>
                  </div>
                  {expanded ? (
                    <div className="border-t border-border/60 px-4 pb-4 pt-4">
                      <div className={cn("grid gap-4 md:grid-cols-2", !enabled && "opacity-75")}>
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

                      <div className="mt-4 rounded-2xl border border-border/60 bg-background/70 p-4">
                        <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                          <div>
                            <div className="text-sm font-semibold text-foreground">回调地址与测试</div>
                            <p className="mt-1 text-xs leading-5 text-muted-foreground">
                              填完后点保存即可生效，不需要重启。下面的回调地址直接贴到 OAuth 平台。
                            </p>
                          </div>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            onClick={() => void startOAuthTest(provider.key)}
                            disabled={!enabled || isTesting}
                            className="gap-2"
                          >
                            {isTesting ? <Loader2 className="h-4 w-4 animate-spin" /> : <ExternalLink className="h-4 w-4" />}
                            测试认证
                          </Button>
                        </div>

                        <div className="mt-4 grid gap-3">
                          <div className="rounded-2xl border border-border/60 bg-background/55 px-4 py-3">
                            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                              <div className="min-w-0">
                                <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">
                                  <Globe className="h-3.5 w-3.5" />
                                  前台回调地址
                                </div>
                                <div className="mt-2 break-all font-mono text-xs text-foreground">{publicCallbackUrl}</div>
                              </div>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => void copyText(publicCallbackUrl, "前台回调地址")}
                                className="shrink-0 gap-2"
                              >
                                <Copy className="h-4 w-4" />
                                复制
                              </Button>
                            </div>
                          </div>

                          <div className="rounded-2xl border border-border/60 bg-background/55 px-4 py-3">
                            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
                              <div className="min-w-0">
                                <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.22em] text-muted-foreground">
                                  <ShieldCheck className="h-3.5 w-3.5" />
                                  后台绑定回调地址
                                </div>
                                <div className="mt-2 break-all font-mono text-xs text-foreground">{adminCallbackUrl}</div>
                              </div>
                              <Button
                                type="button"
                                variant="ghost"
                                size="sm"
                                onClick={() => void copyText(adminCallbackUrl, "后台绑定回调地址")}
                                className="shrink-0 gap-2"
                              >
                                <Copy className="h-4 w-4" />
                                复制
                              </Button>
                            </div>
                          </div>
                        </div>

                        {githubNeedsSeparateLocalApp ? (
                          <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/10 px-4 py-3 text-xs leading-5 text-amber-700 dark:text-amber-200">
                            GitHub OAuth App 只能保留一个 callback URL。本地如果要同时测试前台和后台绑定，建议单独建一个本地调试用 App。
                          </div>
                        ) : null}
                      </div>
                    </div>
                  ) : null}
                </div>
              );
            })}

            {visitorSaveError ? (
              <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
                {visitorSaveError}
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
            <p className="text-sm leading-6 text-muted-foreground">
              绑定后的前台账号在前端评论或留言时，会使用主页显示名作为名字、Hero 翻转视觉图作为头像。
            </p>

            <section className="space-y-3">
              <div className="flex items-start gap-3">
                <span className={accentStepBadgeClass}>1</span>
                <div>
                  <div className="text-sm font-semibold text-foreground">启用方式</div>
                  <div className="text-xs text-muted-foreground">先决定哪些方式可以绑定为管理员身份。</div>
                </div>
              </div>

              <div className="grid gap-3 sm:grid-cols-3">
                {ADMIN_AUTH_OPTIONS.map((item) => {
                  const active = form.admin_auth_methods.includes(item.key);
                  return (
                    <button
                      key={item.key}
                      type="button"
                      onClick={() => void handleAdminMethodToggle(item.key)}
                      disabled={savingAdminConfig}
                      className={adminMethodCardClass(active)}
                    >
                      <span
                        className={cn(
                          "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border",
                          item.key === "google"
                            ? "border-[#4285F4]/16 bg-[#4285F4]/10 text-[#3367D6]"
                            : "border-slate-900/12 bg-slate-900/8 text-slate-700 dark:border-white/16 dark:bg-white/8 dark:text-white/82",
                        )}
                      >
                        {item.key === "google" ? <ShieldCheck className="h-4 w-4" /> : <Github className="h-4 w-4" />}
                      </span>
                      <span className="min-w-0">
                        <span className="block text-sm font-medium text-foreground">{item.label}</span>
                        <span className="block text-xs text-muted-foreground">OAuth 绑定</span>
                      </span>
                    </button>
                  );
                })}

                <button
                  type="button"
                  onClick={() => void handleAdminEmailToggle()}
                  disabled={savingAdminConfig}
                  className={adminMethodCardClass(form.admin_email_enabled)}
                >
                  <span className={accentIconBadgeClass}>
                    <Mail className="h-4 w-4" />
                  </span>
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-foreground">邮箱</span>
                    <span className="block text-xs text-muted-foreground">仅后台识别</span>
                  </span>
                </button>
              </div>

              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                {savingAdminConfig ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
                <span>{savingAdminConfig ? "正在自动保存管理员认证方式..." : "这里不需要单独保存，点击后会自动保存。"}</span>
              </div>
              <p className="text-xs text-muted-foreground">邮箱仅作为后台识别和绑定使用，不会在前台公开显示。</p>
            </section>

            <section className="space-y-3 border-t border-border/60 pt-5">
              <div className="flex items-start gap-3">
                <span className={accentStepBadgeClass}>2</span>
                <div>
                  <div className="text-sm font-semibold text-foreground">绑定管理员身份</div>
                  <div className="text-xs text-muted-foreground">OAuth 会完成一次登录后自动回到这里完成绑定。</div>
                </div>
              </div>

              <div className="space-y-3">
                {ADMIN_AUTH_OPTIONS.map((item) => {
                  const active = form.admin_auth_methods.includes(item.key);
                  const pending = bindCurrent.isPending || savingAdminConfig;
                  return (
                    <div
                      key={item.key}
                      className={adminPanelCardClass}
                    >
                      <div className="flex items-center justify-between gap-3">
                        <div className="flex min-w-0 items-center gap-3">
                          <span
                            className={cn(
                              "inline-flex h-10 w-10 shrink-0 items-center justify-center rounded-full border",
                              item.key === "google"
                                ? "border-[#4285F4]/16 bg-[#4285F4]/10 text-[#3367D6]"
                                : "border-slate-900/12 bg-slate-900/8 text-slate-700 dark:border-white/16 dark:bg-white/8 dark:text-white/82",
                            )}
                          >
                            {item.key === "google" ? <ShieldCheck className="h-4 w-4" /> : <Github className="h-4 w-4" />}
                          </span>
                          <div>
                            <div className="text-sm font-medium text-foreground">{item.label}</div>
                            <div className="text-xs text-muted-foreground">把当前登录过的 {item.label} 账号绑定成管理员身份。</div>
                          </div>
                        </div>

                        <div className="flex shrink-0 items-center gap-2">
                          <span className={adminStatusPillClass(active)}>
                            {active ? "已开启" : "未开启"}
                          </span>
                          <Button
                            type="button"
                            variant="outline"
                            size="sm"
                            disabled={!active || pending}
                            onClick={() => void startAdminOAuthBinding(item.key)}
                            className="gap-2"
                          >
                            {pending ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                            认证并绑定
                          </Button>
                        </div>
                      </div>
                    </div>
                  );
                })}

                <div className={adminPanelCardClass}>
                  <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                    <div className="flex items-center gap-3">
                      <span className={accentIconBadgeClass}>
                        <Mail className="h-4 w-4" />
                      </span>
                      <div>
                        <div className="text-sm font-medium text-foreground">邮箱管理员身份</div>
                        <div className="text-xs text-muted-foreground">直接把某个邮箱标识保存为管理员身份。</div>
                      </div>
                    </div>

                    <span className={adminStatusPillClass(form.admin_email_enabled)}>
                      {form.admin_email_enabled ? "已开启" : "未开启"}
                    </span>
                  </div>

                  <div className="mt-4 flex flex-col gap-3 sm:flex-row">
                    <Input
                      value={adminEmail}
                      onChange={(event) => setAdminEmail(event.target.value)}
                      placeholder="输入管理员邮箱标识"
                      disabled={!form.admin_email_enabled || bindEmail.isPending || savingAdminConfig}
                    />
                    <Button
                      type="button"
                      onClick={() => void handleBindAdminEmail()}
                      disabled={!form.admin_email_enabled || bindEmail.isPending || savingAdminConfig || !adminEmail.trim()}
                      className="gap-2"
                    >
                      {bindEmail.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Mail className="h-4 w-4" />}
                      绑定邮箱
                    </Button>
                  </div>
                </div>
              </div>
            </section>

            <section className="space-y-3 border-t border-border/60 pt-5">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-start gap-3">
                  <span className={accentStepBadgeClass}>3</span>
                  <div>
                    <div className="text-sm font-semibold text-foreground">已绑定身份</div>
                    <div className="text-xs text-muted-foreground">这里显示已经切换成管理员模式的前台身份。</div>
                  </div>
                </div>
                <Badge variant="outline">{adminIdentities.length} 个</Badge>
              </div>

              <div className="space-y-3">
                {adminIdentitiesQuery.isLoading ? (
                  <div className="rounded-2xl border border-dashed border-border/60 bg-background/35 px-4 py-4 text-sm text-muted-foreground">
                    正在加载管理员身份...
                  </div>
                ) : adminIdentities.length ? (
                  adminIdentities.map((identity: SiteAdminIdentityAdminRead) => (
                    <div
                      key={identity.id}
                      className={cn(adminPanelCardClass, "flex flex-col gap-4")}
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
                    还没有绑定管理员身份。
                  </div>
                )}
              </div>
            </section>

            {bindingError ? (
              <div className="rounded-xl border border-rose-500/20 bg-rose-500/10 px-4 py-3 text-sm text-rose-600 dark:text-rose-300">
                {bindingError}
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
