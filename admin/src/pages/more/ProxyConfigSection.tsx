import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Plug, Stethoscope } from "lucide-react";
import { toast } from "sonner";
import { ConfigSettingsCard } from "@/components/ConfigSettingsCard";
import { AppleSwitch } from "@/components/ui/AppleSwitch";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardContent } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import {
  getProxyConfigApiV1AdminProxyConfigGet,
  postProxyConfigTestApiV1AdminProxyConfigTestPost,
  putProxyConfigApiV1AdminProxyConfigPut,
} from "@serino/api-client/admin";
import type {
  OutboundProxyConfigRead,
  OutboundProxyConfigUpdate,
  OutboundProxyHealthRead,
} from "@serino/api-client/models";
import { useI18n } from "@/i18n";
import {
  getPersistedConfigCheckStatus,
  setPersistedConfigCheckStatus,
} from "@/lib/storage";

const QUERY_KEY = ["admin", "proxy-config"] as const;
const PROXY_CONFIG_STATUS_STORAGE_KEY = "proxy-config";

type OutboundProxyConfig = Required<OutboundProxyConfigRead>;
type OutboundProxyHealthResult = OutboundProxyHealthRead;

const COPY = {
  zh: {
    eyebrow: "Network",
    title: "代理设置",
    loading: "加载中...",
    pending: "待测试",
    available: "可用",
    invalid: "无效",
    checking: "检查中",
    configured: "代理端口已设置",
    unconfigured: "未设置代理端口",
    webhookProxyOn: "Webhook 走代理",
    webhookProxyOff: "Webhook 不走代理",
    oauthProxyOn: "OAuth 走代理",
    oauthProxyOff: "OAuth 不走代理",
    proxyPort: "代理端口",
    proxyPortTitle: "本机 HTTP/HTTPS 代理监听端口",
    proxyPortHint:
      "这里只需要填写端口号。运行时会优先尝试 127.0.0.1，也会自动尝试 Docker 宿主机网关地址，例如 host.docker.internal。",
    proxyPortPlaceholder: "7890",
    proxyPortInvalid: "请输入 1 到 65535 之间的端口号，或者清空以关闭代理。",
    webhookToggle: "Webhook 走代理",
    webhookToggleHint:
      "开启后，Webhook 测试、实际投递，以及 Telegram 连接这类 webhook 相关出站请求都会优先走本机代理。",
    webhookToggleDisabled: "请先填写可用的代理端口，再决定是否让 Webhook 走代理。",
    oauthToggle: "OAuth 走代理",
    oauthToggleHint:
      "开启后，Google / GitHub 的授权换 token、读取用户资料等出站请求都会优先走这份代理配置。",
    oauthToggleDisabled: "请先填写可用的代理端口，再决定是否让 Google / GitHub 认证走代理。",
    scopeNote:
      "现在这份配置已经支持 Webhook 和 OAuth 两个作用域，后面如果还要让大模型 API 走代理，也可以继续沿用这套结构。",
    test: "端口健康测试",
    testing: "测试中...",
    saveSuccess: "代理设置已保存",
    testSuccess: "代理端口测试通过",
    testFailed: "代理端口测试失败",
    lastTest: "最近一次测试",
    latency: "耗时",
    statusCode: "返回码",
  },
  en: {
    eyebrow: "Network",
    title: "Proxy Settings",
    loading: "Loading...",
    pending: "Pending",
    available: "Available",
    invalid: "Invalid",
    checking: "Checking",
    configured: "Proxy port configured",
    unconfigured: "No proxy port configured",
    webhookProxyOn: "Webhook uses proxy",
    webhookProxyOff: "Webhook bypasses proxy",
    oauthProxyOn: "OAuth uses proxy",
    oauthProxyOff: "OAuth bypasses proxy",
    proxyPort: "Proxy Port",
    proxyPortTitle: "Local HTTP/HTTPS proxy listening port",
    proxyPortHint:
      "Only the port is required here. Runtime will try 127.0.0.1 first and also common Docker host gateway addresses such as host.docker.internal.",
    proxyPortPlaceholder: "7890",
    proxyPortInvalid: "Enter a port between 1 and 65535, or clear it to disable the proxy.",
    webhookToggle: "Use Proxy For Webhook",
    webhookToggleHint:
      "When enabled, webhook tests, actual deliveries, and Telegram webhook connect requests will prefer the local proxy.",
    webhookToggleDisabled: "Configure a valid proxy port first, then decide whether webhook traffic should use it.",
    oauthToggle: "Use Proxy For OAuth",
    oauthToggleHint:
      "When enabled, Google / GitHub token exchange and user profile requests will prefer this proxy configuration.",
    oauthToggleDisabled: "Configure a valid proxy port first, then decide whether Google / GitHub auth traffic should use it.",
    scopeNote:
      "This config now covers webhook and OAuth traffic. If model APIs need the proxy later, we can extend the same scope-based structure.",
    test: "Health Check",
    testing: "Testing...",
    saveSuccess: "Proxy settings saved",
    testSuccess: "Proxy port health check passed",
    testFailed: "Proxy port health check failed",
    lastTest: "Latest Check",
    latency: "Latency",
    statusCode: "Status",
  },
} as const;

const EMPTY_FORM = {
  proxy_port: "",
  webhook_enabled: false,
  oauth_enabled: false,
};

function toForm(config: OutboundProxyConfig) {
  return {
    proxy_port: config.proxy_port ? String(config.proxy_port) : "",
    webhook_enabled: Boolean(config.webhook_enabled),
    oauth_enabled: Boolean(config.oauth_enabled),
  };
}

function normalizePort(value: string): number | null {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed < 1 || parsed > 65535) {
    return null;
  }
  return parsed;
}

function buildPayload(form: typeof EMPTY_FORM): OutboundProxyConfigUpdate {
  const proxyPort = normalizePort(form.proxy_port);
  return {
    proxy_port: proxyPort,
    webhook_enabled: proxyPort ? form.webhook_enabled : false,
    oauth_enabled: proxyPort ? form.oauth_enabled : false,
  };
}

export function ProxyConfigSection() {
  const { lang } = useI18n();
  const copy = COPY[lang];
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: QUERY_KEY,
    queryFn: async (): Promise<OutboundProxyConfig> => {
      const { data } = await getProxyConfigApiV1AdminProxyConfigGet();
      return {
        proxy_port: data.proxy_port ?? null,
        webhook_enabled: data.webhook_enabled ?? false,
        oauth_enabled: data.oauth_enabled ?? false,
      };
    },
    refetchOnWindowFocus: false,
  });
  const [form, setForm] = useState(EMPTY_FORM);
  const [healthResult, setHealthResult] = useState<OutboundProxyHealthResult | null>(null);
  const [lastCheckOk, setLastCheckOk] = useState<boolean | null>(null);

  useEffect(() => {
    if (!data) {
      return;
    }
    const nextForm = toForm(data);
    const nextPayload = buildPayload(nextForm);
    setForm(nextForm);
    setHealthResult(null);
    setLastCheckOk(
      nextPayload.proxy_port == null
        ? null
        : getPersistedConfigCheckStatus(
            PROXY_CONFIG_STATUS_STORAGE_KEY,
            JSON.stringify(nextPayload),
          ),
    );
  }, [data]);

  const save = useMutation({
    mutationFn: async (payload: OutboundProxyConfigUpdate): Promise<OutboundProxyConfig> => {
      const { data } = await putProxyConfigApiV1AdminProxyConfigPut(payload);
      return {
        proxy_port: data.proxy_port ?? null,
        webhook_enabled: data.webhook_enabled ?? false,
        oauth_enabled: data.oauth_enabled ?? false,
      };
    },
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: QUERY_KEY });
      toast.success(copy.saveSuccess);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  const test = useMutation({
    mutationFn: (payload: OutboundProxyConfigUpdate) =>
      postProxyConfigTestApiV1AdminProxyConfigTestPost(payload).then((r) => r.data),
    onSuccess: (result, variables) => {
      setHealthResult(result);
      setLastCheckOk(result.ok);
      setPersistedConfigCheckStatus(
        PROXY_CONFIG_STATUS_STORAGE_KEY,
        JSON.stringify(variables),
        result.ok,
      );
      if (result.ok) {
        toast.success(copy.testSuccess);
        return;
      }
      toast.error(copy.testFailed);
    },
    onError: (error: Error, variables) => {
      setLastCheckOk(false);
      setPersistedConfigCheckStatus(
        PROXY_CONFIG_STATUS_STORAGE_KEY,
        JSON.stringify(variables),
        false,
      );
      toast.error(error.message);
    },
  });

  const savedForm = useMemo(() => (data ? toForm(data) : EMPTY_FORM), [data]);
  const hasChanges = useMemo(
    () =>
      form.proxy_port !== savedForm.proxy_port ||
      form.webhook_enabled !== savedForm.webhook_enabled ||
      form.oauth_enabled !== savedForm.oauth_enabled,
    [form, savedForm],
  );
  const normalizedPort = useMemo(() => normalizePort(form.proxy_port), [form.proxy_port]);
  const isPortBlank = form.proxy_port.trim() === "";
  const isPortValid = normalizedPort !== null || isPortBlank;
  const canSave =
    isPortValid &&
    (normalizedPort !== null || (!form.webhook_enabled && !form.oauth_enabled));
  const canTest = normalizedPort !== null && !save.isPending;
  const payload = buildPayload(form);
  const statusTone = test.isPending
    ? "checking"
    : lastCheckOk === true && !hasChanges
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

  const setPortValue = (value: string) => {
    const nextValue = value.replace(/[^\d]/g, "").slice(0, 5);
    setForm((current) => ({
      proxy_port: nextValue,
      webhook_enabled: nextValue.trim() ? current.webhook_enabled : false,
      oauth_enabled: nextValue.trim() ? current.oauth_enabled : false,
    }));
    setHealthResult(null);
    setLastCheckOk(null);
  };

  const runHealthCheck = async (nextPayload = payload) => {
    if (nextPayload.proxy_port == null) {
      setHealthResult(null);
      return false;
    }
    const result = await test.mutateAsync(nextPayload);
    return Boolean(result.ok);
  };

  const handleSave = async () => {
    await save.mutateAsync(payload);
    if (payload.proxy_port != null) {
      await runHealthCheck(payload);
      return;
    }
    setHealthResult(null);
  };

  if (isLoading && !data) {
    return <p className="py-4 text-sm text-muted-foreground">{copy.loading}</p>;
  }

  return (
    <ConfigSettingsCard
      eyebrow={copy.eyebrow}
      title={copy.title}
      dirty={hasChanges}
      saving={save.isPending || test.isPending}
      saveDisabled={!canSave || test.isPending}
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
          onClick={() => void runHealthCheck(payload)}
          disabled={!canTest || test.isPending}
        >
          {test.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Stethoscope className="h-4 w-4" />
          )}
          {test.isPending ? copy.testing : copy.test}
        </Button>
      )}
    >
      <div className="space-y-5">
        <div className="space-y-4">
          <div className="max-w-[340px] space-y-2">
            <LabelWithHelp
              label={copy.proxyPort}
              htmlFor="proxy-port"
              title={copy.proxyPortTitle}
              description={copy.proxyPortHint}
            />
            <Input
              id="proxy-port"
              type="text"
              inputMode="numeric"
              value={form.proxy_port}
              onChange={(event) => setPortValue(event.target.value)}
              placeholder={copy.proxyPortPlaceholder}
              disabled={save.isPending || test.isPending}
            />
            {!isPortValid ? (
              <p className="text-xs text-amber-600 dark:text-amber-300">{copy.proxyPortInvalid}</p>
            ) : null}
          </div>

          <AppleSwitch
            checked={form.webhook_enabled}
            onCheckedChange={(checked) => {
              if (!normalizedPort) {
                return;
              }
              setForm((current) => ({ ...current, webhook_enabled: checked }));
              setHealthResult(null);
              setLastCheckOk(null);
            }}
            leading={<Plug className="h-4 w-4 text-[rgb(var(--admin-accent-rgb)/0.82)]" />}
            label={copy.webhookToggle}
            description={normalizedPort ? copy.webhookToggleHint : copy.webhookToggleDisabled}
            disabled={!normalizedPort || save.isPending || test.isPending}
          />

          <AppleSwitch
            checked={form.oauth_enabled}
            onCheckedChange={(checked) => {
              if (!normalizedPort) {
                return;
              }
              setForm((current) => ({ ...current, oauth_enabled: checked }));
              setHealthResult(null);
              setLastCheckOk(null);
            }}
            leading={<Plug className="h-4 w-4 text-[rgb(var(--admin-accent-rgb)/0.82)]" />}
            label={copy.oauthToggle}
            description={normalizedPort ? copy.oauthToggleHint : copy.oauthToggleDisabled}
            disabled={!normalizedPort || save.isPending || test.isPending}
          />

          <Card surface="soft" className="border-dashed">
            <CardContent className="pt-6">
              <p className="text-sm leading-6 text-muted-foreground">{copy.scopeNote}</p>
            </CardContent>
          </Card>
        </div>

        {healthResult ? (
          <Card surface="soft">
            <CardContent className="space-y-3 pt-6">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant={healthResult.ok ? "success" : "warning"}>
                  {copy.lastTest}
                </Badge>
                <code className="rounded-md bg-black/5 px-2 py-1 text-xs text-foreground/80 dark:bg-white/5">
                  {healthResult.proxy_url}
                </code>
              </div>
              <p className="text-sm leading-6 text-foreground/88">{healthResult.summary}</p>
              <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
                {typeof healthResult.latency_ms === "number" ? (
                  <span>{copy.latency}: {healthResult.latency_ms}ms</span>
                ) : null}
                {typeof healthResult.status_code === "number" ? (
                  <span>{copy.statusCode}: {healthResult.status_code}</span>
                ) : null}
              </div>
            </CardContent>
          </Card>
        ) : null}
      </div>
    </ConfigSettingsCard>
  );
}
