import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  Bot,
  Braces,
  Copy,
  ExternalLink,
  Loader2,
  LogIn,
  LogOut,
  Stethoscope,
} from "lucide-react";
import { ConfigSettingsCard } from "@/components/ConfigSettingsCard";
import { AdminSegmentedFilter } from "@/components/ui/AdminSegmentedFilter";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { NativeSelect } from "@/components/ui/NativeSelect";
import {
  type AgentModelConfig,
  type AgentModelConfigUpdate,
  type AgentModelDiagnostic,
  diagnoseAgentModelConfig,
  getAgentModelConfig,
  getChatGPTAccount,
  getChatGPTLoginStatus,
  getChatGPTModels,
  getOutboundProxyConfig,
  logoutChatGPTAccount,
  startChatGPTLogin,
  updateAgentModelConfig,
} from "@/pages/automation/api";
import { useI18n } from "@/i18n";
import {
  clearPersistedConfigCheckStatus,
  getPersistedConfigCheckDetails,
  getPersistedConfigCheckStatus,
  setPersistedConfigCheckStatus,
} from "@/lib/storage";
import { toast } from "sonner";

const MODEL_CONFIG_QUERY_KEY = ["admin", "agent", "model-config"] as const;
const CHATGPT_ACCOUNT_QUERY_KEY = ["admin", "agent", "chatgpt-account"] as const;
const CHATGPT_MODELS_QUERY_KEY = ["admin", "agent", "chatgpt-models"] as const;
const PROXY_CONFIG_QUERY_KEY = ["admin", "proxy-config"] as const;
const MODEL_CONFIG_STATUS_STORAGE_KEY = "agent-model-config";

type ModelSource = "chatgpt_oauth" | "openai_compatible";
type ModelSourceDiagnostic = AgentModelDiagnostic["items"][number];

interface ModelConfigForm {
  primary_source: ModelSource;
  chatgpt_enabled: boolean;
  chatgpt_model: string;
  chatgpt_timeout_seconds: number;
  api_enabled: boolean;
  api_base_url: string;
  api_model: string;
  api_key: string;
  api_temperature: number;
  api_timeout_seconds: number;
  api_advisory_prompt: string;
}

const COPY = {
  zh: {
    title: "模型配置",
    loading: "加载中…",
    primary: "首选",
    fallback: "备用",
    priority: "调用优先级",
    chatgptTitle: "ChatGPT OAuth",
    apiTitle: "OpenAI-compatible API",
    enabled: "启用此来源",
    enableShort: "启用",
    proxyRequired: "请先在代理设置中填写代理端口并开启 OAuth 代理。",
    connected: "已连接",
    disconnected: "未连接",
    connecting: "等待登录确认…",
    signIn: "登录 ChatGPT",
    signOut: "退出",
    model: "模型",
    selectModel: "选择套餐可用模型",
    noModels: "登录后加载可用模型",
    plan: "套餐",
    deviceCode: "设备验证码",
    deviceHint: "已打开 OpenAI 登录页。完成登录后，本页面会自动更新。",
    openLogin: "打开登录页",
    copyCode: "复制验证码",
    copied: "验证码已复制",
    baseUrl: "Base URL",
    apiKey: "API Key",
    apiKeySaved: "密钥已保存",
    apiKeySavedPlaceholder: "已配置 · 留空保持不变",
    apiKeyPlaceholder: "sk-…",
    baseUrlPlaceholder: "https://api.openai.com/v1",
    apiModelPlaceholder: "gpt-4.1-mini / deepseek-chat / qwen-max",
    diagnose: "诊断",
    diagnosing: "诊断中…",
    notChecked: "未诊断",
    pending: "待测试",
    available: "可用",
    invalid: "无效",
    checking: "检查中",
    saveSuccess: "模型配置已保存",
    loginSuccess: "ChatGPT 登录成功",
    logoutSuccess: "ChatGPT 已退出",
  },
  en: {
    title: "Model configuration",
    loading: "Loading…",
    primary: "Primary",
    fallback: "Fallback",
    priority: "Call priority",
    chatgptTitle: "ChatGPT OAuth",
    apiTitle: "OpenAI-compatible API",
    enabled: "Enable this source",
    enableShort: "Enable",
    proxyRequired: "Configure a proxy port and enable the OAuth proxy first.",
    connected: "Connected",
    disconnected: "Not connected",
    connecting: "Waiting for sign-in…",
    signIn: "Sign in to ChatGPT",
    signOut: "Sign out",
    model: "Model",
    selectModel: "Select a model available to this plan",
    noModels: "Sign in to load available models",
    plan: "Plan",
    deviceCode: "Device code",
    deviceHint: "The OpenAI sign-in page is open. This page updates automatically after sign-in.",
    openLogin: "Open sign-in page",
    copyCode: "Copy code",
    copied: "Code copied",
    baseUrl: "Base URL",
    apiKey: "API key",
    apiKeySaved: "Key saved",
    apiKeySavedPlaceholder: "Configured · leave blank to keep",
    apiKeyPlaceholder: "sk-…",
    baseUrlPlaceholder: "https://api.openai.com/v1",
    apiModelPlaceholder: "gpt-4.1-mini / deepseek-chat / qwen-max",
    diagnose: "Diagnose",
    diagnosing: "Diagnosing…",
    notChecked: "Not checked",
    pending: "Pending",
    available: "Available",
    invalid: "Invalid",
    checking: "Checking",
    saveSuccess: "Model configuration saved",
    loginSuccess: "ChatGPT sign-in complete",
    logoutSuccess: "Signed out of ChatGPT",
  },
} as const;

function visibleForm(config: AgentModelConfig): ModelConfigForm {
  return {
    primary_source: config.primary_source,
    chatgpt_enabled: config.chatgpt_oauth.enabled,
    chatgpt_model: config.chatgpt_oauth.model,
    chatgpt_timeout_seconds: config.chatgpt_oauth.timeout_seconds,
    api_enabled: config.openai_compatible.enabled,
    api_base_url: config.openai_compatible.base_url,
    api_model: config.openai_compatible.model,
    api_key: "",
    api_temperature: config.openai_compatible.temperature,
    api_timeout_seconds: config.openai_compatible.timeout_seconds,
    api_advisory_prompt: config.openai_compatible.advisory_prompt,
  };
}

function comparableForm(form: ModelConfigForm) {
  return { ...form, api_key: "" };
}

function updatePayload(form: ModelConfigForm, apiKeyEdited: boolean): AgentModelConfigUpdate {
  return {
    primary_source: form.primary_source,
    chatgpt_oauth: {
      enabled: form.chatgpt_enabled,
      model: form.chatgpt_model.trim(),
      timeout_seconds: form.chatgpt_timeout_seconds,
    },
    openai_compatible: {
      enabled: form.api_enabled,
      base_url: form.api_base_url.trim(),
      model: form.api_model.trim(),
      ...(apiKeyEdited ? { api_key: form.api_key.trim() } : {}),
      temperature: form.api_temperature,
      timeout_seconds: form.api_timeout_seconds,
      advisory_prompt: form.api_advisory_prompt,
    },
  };
}

function diagnosticSignature(
  config: AgentModelConfig,
  runtime: {
    chatgptConnected?: boolean;
    proxyPort?: number | null;
    oauthProxyEnabled?: boolean;
  },
) {
  return JSON.stringify({
    schema_version: config.schema_version,
    primary_source: config.primary_source,
    chatgpt_oauth: {
      enabled: config.chatgpt_oauth.enabled,
      model: config.chatgpt_oauth.model,
      timeout_seconds: config.chatgpt_oauth.timeout_seconds,
      connected: config.chatgpt_oauth.enabled
        ? (runtime.chatgptConnected ?? config.chatgpt_oauth.connected)
        : false,
      proxy_port: config.chatgpt_oauth.enabled ? runtime.proxyPort : null,
      oauth_proxy_enabled: config.chatgpt_oauth.enabled
        ? runtime.oauthProxyEnabled
        : false,
    },
    openai_compatible: {
      enabled: config.openai_compatible.enabled,
      base_url: config.openai_compatible.base_url,
      model: config.openai_compatible.model,
      api_key_configured: config.openai_compatible.api_key_configured,
      temperature: config.openai_compatible.temperature,
      timeout_seconds: config.openai_compatible.timeout_seconds,
      advisory_prompt: config.openai_compatible.advisory_prompt,
    },
  });
}

function persistedSourceDiagnostics(value: unknown): ModelSourceDiagnostic[] {
  if (!Array.isArray(value)) return [];
  return value.flatMap((item) => {
    if (!item || typeof item !== "object") return [];
    const candidate = item as Record<string, unknown>;
    if (
      (candidate.source !== "chatgpt_oauth" &&
        candidate.source !== "openai_compatible") ||
      (candidate.status !== "healthy" &&
        candidate.status !== "failed" &&
        candidate.status !== "skipped") ||
      typeof candidate.summary !== "string"
    ) {
      return [];
    }
    return [
      {
        source: candidate.source,
        status: candidate.status,
        model: typeof candidate.model === "string" ? candidate.model : "",
        summary: candidate.summary,
      },
    ];
  });
}

function storableSourceDiagnostics(items: ModelSourceDiagnostic[]) {
  return items.map(({ source, status, model, summary }) => ({
    source,
    status,
    model: model ?? "",
    summary,
  }));
}

function SourceStatusDot({ status, label }: { status?: string; label: string }) {
  const tone =
    status === "healthy"
      ? "bg-emerald-500 shadow-[0_0_0_3px_rgba(16,185,129,0.12)]"
      : status === "failed"
        ? "bg-rose-500 shadow-[0_0_0_3px_rgba(244,63,94,0.12)]"
        : "bg-slate-300 dark:bg-slate-600";
  return (
    <span
      role="status"
      aria-label={label}
      title={label}
      className={`h-2.5 w-2.5 shrink-0 rounded-full ${tone}`}
    />
  );
}

export function AgentModelConfigSection() {
  const { lang } = useI18n();
  const copy = COPY[lang];
  const queryClient = useQueryClient();
  const [form, setForm] = useState<ModelConfigForm | null>(null);
  const [apiKeyEdited, setApiKeyEdited] = useState(false);
  const [sourceDiagnostics, setSourceDiagnostics] = useState<ModelSourceDiagnostic[]>([]);
  const [lastCheckOk, setLastCheckOk] = useState<boolean | null>(null);
  const [deviceLogin, setDeviceLogin] = useState<Awaited<ReturnType<typeof startChatGPTLogin>> | null>(null);

  const configQuery = useQuery({
    queryKey: MODEL_CONFIG_QUERY_KEY,
    queryFn: getAgentModelConfig,
    refetchOnWindowFocus: false,
  });
  const proxyQuery = useQuery({
    queryKey: PROXY_CONFIG_QUERY_KEY,
    queryFn: getOutboundProxyConfig,
    refetchOnWindowFocus: false,
  });
  const oauthProxyReady = Boolean(proxyQuery.data?.proxy_port && proxyQuery.data.oauth_enabled);
  const accountQuery = useQuery({
    queryKey: CHATGPT_ACCOUNT_QUERY_KEY,
    queryFn: getChatGPTAccount,
    enabled: oauthProxyReady,
    refetchOnWindowFocus: false,
  });
  const modelsQuery = useQuery({
    queryKey: CHATGPT_MODELS_QUERY_KEY,
    queryFn: getChatGPTModels,
    enabled: oauthProxyReady && accountQuery.data?.connected === true,
    refetchOnWindowFocus: false,
  });
  const loginStatusQuery = useQuery({
    queryKey: ["admin", "agent", "chatgpt-login", deviceLogin?.login_id],
    queryFn: () => getChatGPTLoginStatus(deviceLogin?.login_id || ""),
    enabled: Boolean(deviceLogin?.login_id),
    refetchInterval: deviceLogin ? 1500 : false,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    if (!configQuery.data) return;
    setForm(visibleForm(configQuery.data));
    setApiKeyEdited(false);
  }, [configQuery.data]);

  useEffect(() => {
    const status = loginStatusQuery.data;
    if (!deviceLogin || !status || status.status === "pending") return;
    if (status.status === "completed") {
      setSourceDiagnostics([]);
      setLastCheckOk(null);
      clearPersistedConfigCheckStatus(MODEL_CONFIG_STATUS_STORAGE_KEY);
      toast.success(copy.loginSuccess);
      void queryClient.invalidateQueries({ queryKey: CHATGPT_ACCOUNT_QUERY_KEY });
      void queryClient.invalidateQueries({ queryKey: CHATGPT_MODELS_QUERY_KEY });
    } else {
      toast.error(status.error || "ChatGPT sign-in failed");
    }
    setDeviceLogin(null);
  }, [copy.loginSuccess, deviceLogin, loginStatusQuery.data, queryClient]);

  const saveMutation = useMutation({
    mutationFn: updateAgentModelConfig,
    onSuccess: (saved) => {
      setForm(visibleForm(saved));
      setApiKeyEdited(false);
      setSourceDiagnostics([]);
      setLastCheckOk(null);
      clearPersistedConfigCheckStatus(MODEL_CONFIG_STATUS_STORAGE_KEY);
      queryClient.setQueryData(MODEL_CONFIG_QUERY_KEY, saved);
      toast.success(copy.saveSuccess);
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const diagnoseMutation = useMutation({
    mutationFn: (_signature: string) => diagnoseAgentModelConfig(),
    onSuccess: (result, signature) => {
      setSourceDiagnostics(result.items);
      const checkOk = result.status === "healthy";
      setLastCheckOk(checkOk);
      setPersistedConfigCheckStatus(
        MODEL_CONFIG_STATUS_STORAGE_KEY,
        signature,
        checkOk,
        storableSourceDiagnostics(result.items),
      );
      const enabledItems = result.items.filter((item) => item.status !== "skipped");
      if (enabledItems.length === 0) {
        toast.info(result.summary);
        return;
      }
      for (const item of enabledItems) {
        if (item.status === "healthy") {
          toast.success(item.summary);
          continue;
        }
        const description = [
          item.detail?.trim(),
          result.status === "warning" ? result.summary : "",
        ]
          .filter(Boolean)
          .join("；");
        const options = description ? { description } : undefined;
        if (result.status === "warning") {
          toast.warning(item.summary, options);
        } else {
          toast.error(item.summary, options);
        }
      }
    },
    onError: (error: Error, signature) => {
      setSourceDiagnostics([]);
      setLastCheckOk(false);
      setPersistedConfigCheckStatus(
        MODEL_CONFIG_STATUS_STORAGE_KEY,
        signature,
        false,
      );
      toast.error(error.message);
    },
  });
  const loginMutation = useMutation({
    mutationFn: startChatGPTLogin,
    onSuccess: (login) => {
      setDeviceLogin(login);
      window.open(login.verification_url, "_blank", "noopener,noreferrer");
    },
    onError: (error: Error) => toast.error(error.message),
  });
  const logoutMutation = useMutation({
    mutationFn: logoutChatGPTAccount,
    onSuccess: async () => {
      setDeviceLogin(null);
      setSourceDiagnostics([]);
      setLastCheckOk(null);
      clearPersistedConfigCheckStatus(MODEL_CONFIG_STATUS_STORAGE_KEY);
      await queryClient.invalidateQueries({ queryKey: CHATGPT_ACCOUNT_QUERY_KEY });
      queryClient.removeQueries({ queryKey: CHATGPT_MODELS_QUERY_KEY });
      toast.success(copy.logoutSuccess);
    },
    onError: (error: Error) => toast.error(error.message),
  });

  const savedForm = useMemo(
    () => (configQuery.data ? visibleForm(configQuery.data) : null),
    [configQuery.data],
  );
  const hasChanges = Boolean(
    form &&
      savedForm &&
      (JSON.stringify(comparableForm(form)) !== JSON.stringify(comparableForm(savedForm)) || apiKeyEdited),
  );
  const savedDiagnosticSignature = useMemo(
    () =>
      configQuery.data
        ? diagnosticSignature(configQuery.data, {
            chatgptConnected: accountQuery.data?.connected,
            proxyPort: proxyQuery.data?.proxy_port,
            oauthProxyEnabled: proxyQuery.data?.oauth_enabled,
          })
        : null,
    [
      accountQuery.data?.connected,
      configQuery.data,
      proxyQuery.data?.oauth_enabled,
      proxyQuery.data?.proxy_port,
    ],
  );

  useEffect(() => {
    if (!savedDiagnosticSignature) return;
    setLastCheckOk(
      getPersistedConfigCheckStatus(
        MODEL_CONFIG_STATUS_STORAGE_KEY,
        savedDiagnosticSignature,
      ),
    );
    setSourceDiagnostics(
      persistedSourceDiagnostics(
        getPersistedConfigCheckDetails(
          MODEL_CONFIG_STATUS_STORAGE_KEY,
          savedDiagnosticSignature,
        ),
      ),
    );
  }, [savedDiagnosticSignature]);

  if (!form || (configQuery.isLoading && !configQuery.data)) {
    return <p className="py-4 text-sm text-muted-foreground">{copy.loading}</p>;
  }

  const busy = saveMutation.isPending || diagnoseMutation.isPending;
  const account = accountQuery.data;
  const visibleSourceDiagnostics = hasChanges ? [] : sourceDiagnostics;
  const chatgptDiagnostic = visibleSourceDiagnostics.find(
    (item) => item.source === "chatgpt_oauth",
  );
  const apiDiagnostic = visibleSourceDiagnostics.find(
    (item) => item.source === "openai_compatible",
  );
  const statusTone = diagnoseMutation.isPending
    ? "checking"
    : hasChanges
      ? "pending"
      : lastCheckOk === true
        ? "available"
        : lastCheckOk === false
          ? "invalid"
          : "pending";
  const statusLabel =
    statusTone === "checking"
      ? copy.checking
      : statusTone === "available"
        ? copy.available
        : statusTone === "invalid"
          ? copy.invalid
          : copy.pending;
  const setField = <K extends keyof ModelConfigForm>(key: K, value: ModelConfigForm[K]) => {
    setForm((current) => (current ? { ...current, [key]: value } : current));
  };

  const runDiagnosis = async (signature: string) => {
    try {
      await diagnoseMutation.mutateAsync(signature);
    } catch {
      // The mutation displays the actionable error notification.
    }
  };

  const handleSave = async () => {
    try {
      const saved = await saveMutation.mutateAsync(updatePayload(form, apiKeyEdited));
      await runDiagnosis(
        diagnosticSignature(saved, {
          chatgptConnected: account?.connected,
          proxyPort: proxyQuery.data?.proxy_port,
          oauthProxyEnabled: proxyQuery.data?.oauth_enabled,
        }),
      );
    } catch {
      // The mutation displays the actionable error notification.
    }
  };

  const copyDeviceCode = async () => {
    if (!deviceLogin) return;
    try {
      await navigator.clipboard.writeText(deviceLogin.user_code);
      toast.success(copy.copied);
    } catch {
      toast.error(deviceLogin.user_code);
    }
  };

  return (
    <ConfigSettingsCard
      title={copy.title}
      className="max-w-6xl"
      dirty={hasChanges}
      saving={saveMutation.isPending}
      saveDisabled={busy || (form.chatgpt_enabled && !oauthProxyReady)}
      onSave={() => void handleSave()}
      statusIndicator={{
        label: statusLabel,
        tone: statusTone,
      }}
      testAction={(
        <Button
          type="button"
          variant="outline"
          size="sm"
          className="gap-2"
          disabled={busy || hasChanges || !savedDiagnosticSignature}
          onClick={() => {
            if (savedDiagnosticSignature) {
              void runDiagnosis(savedDiagnosticSignature);
            }
          }}
        >
          {diagnoseMutation.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Stethoscope className="h-4 w-4" />
          )}
          {diagnoseMutation.isPending ? copy.diagnosing : copy.diagnose}
        </Button>
      )}
    >
      <div className="space-y-5">
        <div className="flex flex-col gap-3 rounded-[var(--admin-radius-lg)] border border-border/45 bg-[rgb(var(--admin-surface-1)/0.42)] p-4 sm:flex-row sm:items-center sm:justify-between">
          <p className="text-sm font-semibold text-foreground/90">{copy.priority}</p>
          <AdminSegmentedFilter
            value={form.primary_source}
            onValueChange={(value) => setField("primary_source", value as ModelSource)}
            items={[
              { value: "chatgpt_oauth", label: copy.chatgptTitle },
              { value: "openai_compatible", label: copy.apiTitle },
            ]}
            size="sm"
            tone="accent"
          />
        </div>

        <div className="grid gap-4 xl:grid-cols-2">
          <section className="rounded-[var(--admin-radius-xl)] border border-border/50 bg-[rgb(var(--admin-surface-1)/0.44)] p-4 shadow-[var(--admin-shadow-xs)] sm:p-5">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-sky-500/10 text-sky-600 dark:text-sky-300">
                  <Bot className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <SourceStatusDot
                      status={chatgptDiagnostic?.status}
                      label={chatgptDiagnostic?.summary || copy.notChecked}
                    />
                    <h3 className="font-semibold tracking-tight">{copy.chatgptTitle}</h3>
                    <Badge variant={form.primary_source === "chatgpt_oauth" ? "info" : "outline"}>
                      {form.primary_source === "chatgpt_oauth" ? `1 · ${copy.primary}` : `2 · ${copy.fallback}`}
                    </Badge>
                  </div>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-sm text-muted-foreground">{copy.enableShort}</span>
                <AppleSwitch
                  checked={form.chatgpt_enabled}
                  onCheckedChange={(checked) => {
                    if (checked && !oauthProxyReady) {
                      toast.warning(copy.proxyRequired);
                      return;
                    }
                    setField("chatgpt_enabled", checked);
                  }}
                  ariaLabel={`${copy.enabled}：${copy.chatgptTitle}`}
                  disabled={busy || proxyQuery.isLoading}
                  className="!rounded-none !border-0 !bg-transparent !p-0 !shadow-none hover:!bg-transparent"
                />
              </div>
            </div>

            <div className="space-y-4">
              <div className="rounded-[var(--admin-radius-lg)] border border-border/45 bg-[rgb(var(--admin-surface-0)/0.42)] p-3.5">
                {proxyQuery.isLoading ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {copy.loading}
                  </div>
                ) : !oauthProxyReady ? (
                  <p className="text-sm text-muted-foreground">{copy.proxyRequired}</p>
                ) : accountQuery.isLoading ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {copy.loading}
                  </div>
                ) : account?.connected ? (
                  <div className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-sm font-medium">{account.email || copy.connected}</span>
                        <Badge variant="success">{copy.connected}</Badge>
                        {account.plan_type ? <Badge variant="outline">{copy.plan}: {account.plan_type}</Badge> : null}
                      </div>
                    </div>
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      className="shrink-0 gap-2"
                      disabled={logoutMutation.isPending}
                      onClick={() => logoutMutation.mutate()}
                    >
                      {logoutMutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogOut className="h-4 w-4" />}
                      {copy.signOut}
                    </Button>
                  </div>
                ) : (
                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div>
                        <p className="text-sm font-medium">{copy.disconnected}</p>
                        {account?.error ? <p className="mt-1 text-xs text-rose-600 dark:text-rose-300">{account.error}</p> : null}
                      </div>
                      <Button
                        type="button"
                        size="sm"
                        className="gap-2"
                        disabled={loginMutation.isPending || Boolean(deviceLogin)}
                        onClick={() => loginMutation.mutate()}
                      >
                        {loginMutation.isPending || deviceLogin ? <Loader2 className="h-4 w-4 animate-spin" /> : <LogIn className="h-4 w-4" />}
                        {deviceLogin ? copy.connecting : copy.signIn}
                      </Button>
                    </div>

                    {deviceLogin ? (
                      <div className="rounded-lg border border-sky-400/25 bg-sky-500/8 p-3">
                        <p className="text-xs text-muted-foreground">{copy.deviceCode}</p>
                        <div className="mt-1 flex flex-wrap items-center gap-2">
                          <code className="text-base font-semibold tracking-[0.16em] text-foreground">{deviceLogin.user_code}</code>
                          <Button type="button" variant="outline" size="sm" className="gap-1.5" onClick={() => void copyDeviceCode()}>
                            <Copy className="h-3.5 w-3.5" />
                            {copy.copyCode}
                          </Button>
                          <Button
                            type="button"
                            variant="ghost"
                            size="sm"
                            className="gap-1.5"
                            onClick={() => window.open(deviceLogin.verification_url, "_blank", "noopener,noreferrer")}
                          >
                            <ExternalLink className="h-3.5 w-3.5" />
                            {copy.openLogin}
                          </Button>
                        </div>
                        <p className="mt-2 text-xs leading-5 text-muted-foreground">{copy.deviceHint}</p>
                      </div>
                    ) : null}
                  </div>
                )}
              </div>

              <div className="space-y-2">
                <Label htmlFor="chatgpt-model">{copy.model}</Label>
                <NativeSelect
                  id="chatgpt-model"
                  aria-label={copy.model}
                  value={form.chatgpt_model}
                  disabled={busy || account?.connected !== true}
                  onChange={(event) => setField("chatgpt_model", event.target.value)}
                >
                  <option value="">{account?.connected ? copy.selectModel : copy.noModels}</option>
                  {form.chatgpt_model && !modelsQuery.data?.some((item) => item.model === form.chatgpt_model) ? (
                    <option value={form.chatgpt_model}>{form.chatgpt_model}</option>
                  ) : null}
                  {modelsQuery.data?.map((item) => (
                    <option key={item.model} value={item.model}>
                      {item.display_name}{item.is_default ? " · Default" : ""}
                    </option>
                  ))}
                </NativeSelect>
              </div>
            </div>
          </section>

          <section className="rounded-[var(--admin-radius-xl)] border border-border/50 bg-[rgb(var(--admin-surface-1)/0.44)] p-4 shadow-[var(--admin-shadow-xs)] sm:p-5">
            <div className="mb-4 flex items-start justify-between gap-3">
              <div className="flex min-w-0 items-start gap-3">
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-violet-500/10 text-violet-600 dark:text-violet-300">
                  <Braces className="h-5 w-5" />
                </span>
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <SourceStatusDot
                      status={apiDiagnostic?.status}
                      label={apiDiagnostic?.summary || copy.notChecked}
                    />
                    <h3 className="font-semibold tracking-tight">{copy.apiTitle}</h3>
                    <Badge variant={form.primary_source === "openai_compatible" ? "info" : "outline"}>
                      {form.primary_source === "openai_compatible" ? `1 · ${copy.primary}` : `2 · ${copy.fallback}`}
                    </Badge>
                  </div>
                </div>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <span className="text-sm text-muted-foreground">{copy.enableShort}</span>
                <AppleSwitch
                  checked={form.api_enabled}
                  onCheckedChange={(checked) => setField("api_enabled", checked)}
                  ariaLabel={`${copy.enabled}：${copy.apiTitle}`}
                  disabled={busy}
                  className="!rounded-none !border-0 !bg-transparent !p-0 !shadow-none hover:!bg-transparent"
                />
              </div>
            </div>

            <div className="space-y-4">
              <div className="space-y-2">
                <Label htmlFor="compatible-base-url">{copy.baseUrl}</Label>
                <Input
                  id="compatible-base-url"
                  value={form.api_base_url}
                  placeholder={copy.baseUrlPlaceholder}
                  disabled={busy}
                  onChange={(event) => setField("api_base_url", event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="compatible-model">{copy.model}</Label>
                <Input
                  id="compatible-model"
                  value={form.api_model}
                  placeholder={copy.apiModelPlaceholder}
                  disabled={busy}
                  onChange={(event) => setField("api_model", event.target.value)}
                />
              </div>
              <div className="space-y-2">
                <div className="flex items-center justify-between gap-2">
                  <Label htmlFor="compatible-api-key">{copy.apiKey}</Label>
                  {configQuery.data?.openai_compatible.api_key_configured && !apiKeyEdited ? (
                    <Badge variant="success">{copy.apiKeySaved}</Badge>
                  ) : null}
                </div>
                <Input
                  id="compatible-api-key"
                  type="password"
                  autoComplete="new-password"
                  value={form.api_key}
                  placeholder={
                    configQuery.data?.openai_compatible.api_key_configured
                      ? copy.apiKeySavedPlaceholder
                      : copy.apiKeyPlaceholder
                  }
                  disabled={busy}
                  onChange={(event) => {
                    setApiKeyEdited(true);
                    setField("api_key", event.target.value);
                  }}
                />
              </div>
            </div>
          </section>
        </div>
      </div>
    </ConfigSettingsCard>
  );
}
