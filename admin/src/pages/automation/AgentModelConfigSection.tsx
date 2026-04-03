import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Send } from "lucide-react";
import { ConfigSettingsCard } from "@/components/ConfigSettingsCard";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import {
  type AgentModelConfig,
  getAgentModelConfig,
  testAgentModelConfig,
  updateAgentModelConfig,
} from "@/pages/automation/api";
import { useI18n } from "@/i18n";
import {
  getPersistedConfigCheckStatus,
  setPersistedConfigCheckStatus,
} from "@/lib/storage";
import { toast } from "sonner";

const MODEL_CONFIG_QUERY_KEY = ["admin", "agent", "model-config"] as const;
const MODEL_CONFIG_STATUS_STORAGE_KEY = "agent-model-config";

const COPY = {
  zh: {
    eyebrow: "API",
    title: "大模型 API 配置",
    pending: "待测试",
    available: "可用",
    invalid: "无效",
    checking: "检查中",
    baseUrl: "Base URL",
    model: "Model",
    apiKey: "API Key",
    timeout: "超时（秒）",
    timeoutHint: "第三方中转站较慢时可以适当调高，工作流规划建议至少 60 秒。",
    loading: "加载中...",
    test: "测试",
    testing: "测试中...",
    baseUrlPlaceholder: "https://api.openai.com/v1",
    modelPlaceholder: "gpt-4.1-mini / deepseek-chat / qwen-max",
    apiKeyPlaceholder: "sk-...",
    saveSuccess: "模型配置已保存",
    testSuccess: "模型接口可用",
  },
  en: {
    eyebrow: "API",
    title: "Model API Config",
    pending: "Pending",
    available: "Available",
    invalid: "Invalid",
    checking: "Checking",
    baseUrl: "Base URL",
    model: "Model",
    apiKey: "API Key",
    timeout: "Timeout (s)",
    timeoutHint: "Increase this when the upstream model endpoint is slow. For workflow planning, 60 seconds or more is often safer.",
    loading: "Loading...",
    test: "Test",
    testing: "Testing...",
    baseUrlPlaceholder: "https://api.openai.com/v1",
    modelPlaceholder: "gpt-4.1-mini / deepseek-chat / qwen-max",
    apiKeyPlaceholder: "sk-...",
    saveSuccess: "Model config saved",
    testSuccess: "Model endpoint is available",
  },
} as const;

const EMPTY_FORM = {
  base_url: "",
  model: "",
  api_key: "",
  timeout_seconds: "20",
};

function toVisibleForm(config: AgentModelConfig) {
  return {
    base_url: config.base_url || "",
    model: config.model || "",
    api_key: config.api_key || "",
    timeout_seconds: String(config.timeout_seconds ?? 20),
  };
}

function buildPayload(form: typeof EMPTY_FORM, config?: AgentModelConfig) {
  const normalizedTimeout = Number(form.timeout_seconds) || config?.timeout_seconds || 20;
  return {
    enabled: true,
    provider: config?.provider || "openai_compatible",
    base_url: form.base_url.trim(),
    model: form.model.trim(),
    api_key: form.api_key.trim(),
    temperature: config?.temperature ?? 0.2,
    timeout_seconds: Math.max(5, Math.min(300, normalizedTimeout)),
    advisory_prompt: config?.advisory_prompt || "",
  };
}

export function AgentModelConfigSection() {
  const { lang } = useI18n();
  const copy = COPY[lang];
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: MODEL_CONFIG_QUERY_KEY,
    queryFn: getAgentModelConfig,
    refetchOnWindowFocus: false,
  });
  const [form, setForm] = useState(EMPTY_FORM);
  const [apiKeyEdited, setApiKeyEdited] = useState(false);
  const [lastCheckOk, setLastCheckOk] = useState<boolean | null>(null);

  useEffect(() => {
    if (!data) {
      return;
    }
    const nextForm = toVisibleForm(data);
    const nextPayload = buildPayload(nextForm, data);
    setForm(nextForm);
    setApiKeyEdited(false);
    setLastCheckOk(
      getPersistedConfigCheckStatus(
        MODEL_CONFIG_STATUS_STORAGE_KEY,
        JSON.stringify(nextPayload),
      ),
    );
  }, [data]);

  const save = useMutation({
    mutationFn: updateAgentModelConfig,
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: MODEL_CONFIG_QUERY_KEY });
      toast.success(copy.saveSuccess);
    },
    onError: (error: Error) => {
      toast.error(error.message);
    },
  });

  const test = useMutation({
    mutationFn: testAgentModelConfig,
    onSuccess: (result, variables) => {
      setLastCheckOk(result.ok);
      setPersistedConfigCheckStatus(
        MODEL_CONFIG_STATUS_STORAGE_KEY,
        JSON.stringify(variables),
        result.ok,
      );
      if (result.ok) {
        toast.success(`${copy.testSuccess}: ${result.model}`);
        return;
      }
      toast.error(result.summary || "模型接口测试失败，请检查配置");
    },
    onError: (error: Error, variables) => {
      setLastCheckOk(false);
      setPersistedConfigCheckStatus(
        MODEL_CONFIG_STATUS_STORAGE_KEY,
        JSON.stringify(variables),
        false,
      );
      toast.error(error.message);
    },
  });

  const savedForm = useMemo(() => (data ? toVisibleForm(data) : EMPTY_FORM), [data]);
  const hasChanges = useMemo(
    () =>
      form.base_url !== savedForm.base_url ||
      form.model !== savedForm.model ||
      form.api_key !== savedForm.api_key ||
      form.timeout_seconds !== savedForm.timeout_seconds ||
      apiKeyEdited,
    [apiKeyEdited, form, savedForm],
  );

  if (isLoading && !data) {
    return <p className="py-4 text-sm text-muted-foreground">{copy.loading}</p>;
  }

  const isReady = Boolean(form.base_url.trim() && form.model.trim() && form.api_key.trim());
  const isEmpty = !form.base_url.trim() && !form.model.trim() && !form.api_key.trim();
  const canSave = isReady || isEmpty;
  const payload = buildPayload(form, data);
  const isChecking = test.isPending;
  const statusTone = isChecking
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
  const updateField = (key: keyof typeof EMPTY_FORM, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
    if (key === "api_key") {
      setApiKeyEdited(true);
    }
    setLastCheckOk(null);
  };

  const runConnectionCheck = async (nextPayload = payload) => {
    if (!nextPayload.base_url || !nextPayload.model || !nextPayload.api_key) {
      setLastCheckOk(null);
      return false;
    }
    const result = await test.mutateAsync(nextPayload);
    return Boolean(result.ok);
  };

  const handleSave = async () => {
    await save.mutateAsync(payload);
    if (isReady) {
      await runConnectionCheck(payload);
      return;
    }
    setLastCheckOk(null);
  };

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
          onClick={() => void runConnectionCheck(payload)}
          disabled={!isReady || test.isPending || save.isPending}
        >
          {test.isPending ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Send className="h-4 w-4" />
          )}
          {test.isPending ? copy.testing : copy.test}
        </Button>
      )}
    >
      <div className="space-y-4">
        <div className="grid gap-4 md:grid-cols-2">
          <div className="space-y-2">
            <Label>{copy.model}</Label>
            <Input
              value={form.model}
              onChange={(event) => updateField("model", event.target.value)}
              placeholder={copy.modelPlaceholder}
              disabled={save.isPending || test.isPending}
            />
          </div>
          <div className="space-y-2">
            <Label>{copy.baseUrl}</Label>
            <Input
              value={form.base_url}
              onChange={(event) => updateField("base_url", event.target.value)}
              placeholder={copy.baseUrlPlaceholder}
              disabled={save.isPending || test.isPending}
            />
          </div>
          <div className="space-y-2">
            <Label>{copy.apiKey}</Label>
            <Input
              type="password"
              value={form.api_key}
              autoComplete="new-password"
              onChange={(event) => updateField("api_key", event.target.value)}
              onInput={(event) => updateField("api_key", event.currentTarget.value)}
              placeholder={copy.apiKeyPlaceholder}
              disabled={save.isPending || test.isPending}
            />
          </div>
          <div className="space-y-2">
            <LabelWithHelp
              label={copy.timeout}
              htmlFor="agent-timeout-seconds"
              description={copy.timeoutHint}
            />
            <Input
              id="agent-timeout-seconds"
              type="number"
              min={5}
              max={300}
              step={1}
              value={form.timeout_seconds}
              onChange={(event) => updateField("timeout_seconds", event.target.value)}
              disabled={save.isPending || test.isPending}
            />
          </div>
        </div>
      </div>
    </ConfigSettingsCard>
  );
}
