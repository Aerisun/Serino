import { useEffect, useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Loader2, Send } from "lucide-react";
import { AdminSurface } from "@/components/AdminSurface";
import { DirtySaveButton, PendingSaveBadge } from "@/components/ui/DirtySaveButton";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Label } from "@/components/ui/Label";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import {
  type AgentModelConfig,
  getAgentModelConfig,
  testAgentModelConfig,
  updateAgentModelConfig,
} from "@/api/endpoints/agent";
import { useI18n } from "@/i18n";
import { toast } from "sonner";

const MODEL_CONFIG_QUERY_KEY = ["admin", "agent", "model-config"] as const;

const COPY = {
  zh: {
    eyebrow: "Config",
    title: "大模型 API 配置",
    description: "只保留运行时真正要用的最小接入项。",
    ready: "可测试",
    incomplete: "配置未完成",
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
    eyebrow: "Config",
    title: "Model API Config",
    description: "Keep only the minimal fields the runtime actually needs.",
    ready: "Ready to test",
    incomplete: "Config incomplete",
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

  useEffect(() => {
    if (!data) {
      return;
    }
    setForm(toVisibleForm(data));
    setApiKeyEdited(false);
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
    onSuccess: (result) => {
      if (result.ok) {
        toast.success(`${copy.testSuccess}: ${result.model}`);
        return;
      }
      toast.error(result.summary || "模型接口测试失败，请检查配置");
    },
    onError: (error: Error) => {
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
  const updateField = (key: keyof typeof EMPTY_FORM, value: string) => {
    setForm((current) => ({ ...current, [key]: value }));
    if (key === "api_key") {
      setApiKeyEdited(true);
    }
  };

  return (
    <AdminSurface
      eyebrow={copy.eyebrow}
      title={copy.title}
      description={copy.description}
      actions={(
        <>
          {hasChanges ? <PendingSaveBadge /> : null}
          <Button
            type="button"
            variant="outline"
            size="sm"
            className="gap-2"
            onClick={() => test.mutate(payload)}
            disabled={!isReady || test.isPending || save.isPending}
          >
            {test.isPending ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Send className="h-4 w-4" />
            )}
            {test.isPending ? copy.testing : copy.test}
          </Button>
          <DirtySaveButton
            dirty={hasChanges}
            saving={save.isPending}
            disabled={!canSave || test.isPending}
            onClick={() => save.mutate(payload)}
          />
        </>
      )}
    >
      <div className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <Badge variant={isReady ? "success" : "secondary"}>
            {isReady ? copy.ready : copy.incomplete}
          </Badge>
        </div>
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
    </AdminSurface>
  );
}
