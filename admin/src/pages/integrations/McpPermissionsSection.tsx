import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import {
  getListApiKeysApiV1AdminIntegrationsApiKeysGetQueryKey,
  useListApiKeysApiV1AdminIntegrationsApiKeysGet,
  useUpdateApiKeyApiV1AdminIntegrationsApiKeysKeyIdPut,
} from "@serino/api-client/admin";
import type { ApiKeyAdminRead } from "@serino/api-client/models";
import { AdminSurface } from "@/components/AdminSurface";
import { Badge } from "@/components/ui/Badge";
import { CollapsibleSection } from "@/components/ui/CollapsibleSection";
import { LabelWithHelp } from "@/components/ui/LabelWithHelp";
import { NativeSelect } from "@/components/ui/NativeSelect";
import { extractApiErrorMessage } from "@/lib/api-error";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import {
  getMcpConfig,
  type McpAdminConfigRead,
  type McpCapabilityConfigRead,
} from "@/pages/integrations/api";
import {
  CONNECT_SCOPE,
  describeMcpPreset,
  MCP_SCOPE_ORDER,
  mcpScopesOnly,
  mergeMcpScopes,
  normalizeMcpScopeSelection,
  relatedWriteScope,
} from "./mcpScopes";

type ScopeHelp = {
  title: string;
  description: string;
  usageTitle: string;
  usageItems: string[];
};

function buildScopeHelp(
  scope: string,
  relatedCapabilities: McpCapabilityConfigRead[],
  lang: "zh" | "en",
): ScopeHelp {
  const kindLabel = (kind: string) =>
    lang === "zh"
      ? kind === "tool"
        ? "工具"
        : "资源"
      : kind === "tool"
        ? "tool"
        : "resource";

  const capabilitySummary =
    relatedCapabilities.length > 0
      ? relatedCapabilities.map((capability) =>
          lang === "zh"
            ? `${capability.name}（${kindLabel(capability.kind)}）：${capability.description}`
            : `${capability.name} (${kindLabel(capability.kind)}): ${capability.description}`,
        )
      : [
          lang === "zh"
            ? "当前没有能力直接依赖这个 scope，但后续新增能力仍可能使用它。"
            : "No capability depends on this scope yet, but future capabilities may still use it.",
        ];

  const toolCount = relatedCapabilities.filter((item) => item.kind === "tool").length;
  const resourceCount = relatedCapabilities.length - toolCount;
  const sharedItems =
    lang === "zh"
      ? [
          `当前直接关联 ${relatedCapabilities.length} 个能力，其中工具 ${toolCount} 个、资源 ${resourceCount} 个。`,
          ...capabilitySummary,
        ]
      : [
          `This scope currently affects ${relatedCapabilities.length} capabilities: ${toolCount} tools and ${resourceCount} resources.`,
          ...capabilitySummary,
        ];

  if (scope === CONNECT_SCOPE) {
    return {
      title:
        lang === "zh"
          ? "MCP 连接控制（agent:connect）"
          : "MCP connection control (agent:connect)",
      description:
        lang === "zh"
          ? "这是 MCP 页面里的内部连接 scope。它决定这个 API Key 是否允许访问 /api/agent/usage、/api/mcp 以及相关能力发现接口。"
          : "This is the internal connection scope shown on the MCP page. It controls whether the API key can reach /api/agent/usage, /api/mcp, and related capability discovery endpoints.",
      usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
      usageItems:
        lang === "zh"
          ? [
              "开启后，远端 Agent 才能建立机器会话并读取当前允许的 tools / resources。",
              "关闭后，所有机器访问都会整体失效，所以界面也会一并清空其它能力 scopes。",
              "它本身不授予业务读写权限，只负责允许机器连接。",
              ...sharedItems,
            ]
          : [
              "When enabled, remote agents can establish a machine session and inspect the tools/resources allowed for this key.",
              "When disabled, all machine access is blocked, which is why the UI also clears the other scoped permissions.",
              "It does not grant business read/write permissions by itself; it only permits the machine connection.",
              ...sharedItems,
            ],
    };
  }

  const [domain, access] = scope.split(":");
  const domainLabels =
    lang === "zh"
      ? {
          content: "内容",
          moderation: "审核",
          config: "配置",
          assets: "资源",
          subscriptions: "订阅",
          visitors: "访客",
          auth: "认证",
          automation: "自动化",
          system: "系统",
          network: "网络",
        }
      : {
          content: "Content",
          moderation: "Moderation",
          config: "Configuration",
          assets: "Assets",
          subscriptions: "Subscriptions",
          visitors: "Visitors",
          auth: "Auth",
          automation: "Automation",
          system: "System",
          network: "Network",
        };
  const label = domainLabels[domain as keyof typeof domainLabels] || domain;
  const counterpart = `${domain}:${access === "write" ? "read" : "write"}`;

  if (access === "read") {
    return {
      title:
        lang === "zh"
          ? `MCP 内部 scope：${scope}`
          : `MCP internal scope: ${scope}`,
      description:
        lang === "zh"
          ? `这是 MCP 页面里控制的内部能力 scope。它允许 Agent 读取 ${label} 域相关的后台信息，用于观察、分析、诊断和生成建议。`
          : `This is an internal capability scope managed from the MCP page. It lets the agent read ${label.toLowerCase()}-related admin data for observation, analysis, diagnostics, and recommendations.`,
      usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
      usageItems:
        lang === "zh"
          ? [
              `开启后，Agent 可以读取 ${label} 域相关的后台信息。`,
              `关闭后，当前 API Key 将无法访问依赖 ${scope} 的机器能力。`,
              `它通常是 ${counterpart} 的基础依赖，因为大多数写入动作都需要先理解当前状态。`,
              ...sharedItems,
            ]
          : [
              `When enabled, the agent can read admin data in the ${label.toLowerCase()} domain.`,
              `When disabled, this API key can no longer access machine capabilities that depend on ${scope}.`,
              `It is usually the base dependency for ${counterpart} because most mutations need current-state context first.`,
              ...sharedItems,
            ],
    };
  }

  return {
    title:
      lang === "zh"
        ? `MCP 内部 scope：${scope}`
        : `MCP internal scope: ${scope}`,
    description:
      lang === "zh"
        ? `这是 MCP 页面里控制的内部能力 scope。它允许 Agent 对 ${label} 域执行写入、状态变更或运维动作。它属于高风险权限，只适合受信任的自动化流程。`
        : `This is an internal capability scope managed from the MCP page. It allows the agent to perform mutations, state transitions, or operational actions in the ${label.toLowerCase()} domain. It is a high-risk permission for trusted automation only.`,
    usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
    usageItems:
      lang === "zh"
        ? [
            `开启后，Agent 可以真正改变 ${label} 域结果，而不只是读取。`,
            `关闭后，保留 ${domain}:read 的前提下仍可观察和给建议，但不能提交变更。`,
            `系统会同时保留 ${domain}:read，确保写入前能读取旧值和当前上下文。`,
            ...sharedItems,
          ]
        : [
            `When enabled, the agent can change actual state in the ${label.toLowerCase()} domain instead of only reading it.`,
            `When disabled, the agent may still inspect and recommend changes if ${domain}:read remains enabled, but it cannot commit mutations.`,
            `The UI keeps ${domain}:read alongside it so the agent can inspect current state before writing.`,
            ...sharedItems,
          ],
  };
}

function PresetCard({
  preset,
  active,
  customized,
  disabled,
  customLabel,
  count,
  onSelect,
}: {
  preset: {
    key: "readonly" | "basic_management" | "full_management";
    name: string;
    description: string;
    capability_ids: string[];
  };
  active: boolean;
  customized: boolean;
  disabled: boolean;
  customLabel: string;
  count: number;
  onSelect: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      disabled={disabled}
      className={cn(
        "rounded-[var(--admin-radius-lg)] border px-4 py-4 text-left transition-[background-color,border-color,box-shadow,transform]",
        active
          ? customized
            ? "border-[rgb(var(--admin-accent-rgb)/0.2)] bg-[linear-gradient(135deg,rgb(var(--admin-accent-rgb)/0.11),rgb(var(--admin-glow-rgb)/0.08))] shadow-[0_18px_36px_-24px_rgb(var(--admin-accent-rgb)/0.4)] ring-1 ring-inset ring-[rgb(var(--admin-accent-rgb)/0.12)]"
            : "border-[rgb(var(--admin-accent-rgb)/0.26)] bg-[linear-gradient(135deg,rgb(var(--admin-accent-rgb)/0.16),rgb(var(--admin-glow-rgb)/0.12))] shadow-[0_18px_36px_-24px_rgb(var(--admin-accent-rgb)/0.55)]"
          : "border-border/60 bg-background/55 hover:bg-[rgb(var(--admin-surface-1)/0.68)]",
        disabled && "cursor-not-allowed opacity-60",
      )}
    >
      <div className="flex items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          <div className="font-semibold text-foreground">{preset.name}</div>
          {customized ? <Badge variant="warning">{customLabel}</Badge> : null}
        </div>
        {active ? <Badge variant="info">{count}</Badge> : null}
      </div>
      <p className="mt-2 text-sm leading-6 text-muted-foreground">
        {preset.description}
      </p>
    </button>
  );
}

function ScopeRow({
  scope,
  relatedCapabilities,
  enabled,
  disabled,
  statusEnabledLabel,
  statusDisabledLabel,
  helpTitle,
  helpDescription,
  helpUsageTitle,
  helpUsageItems,
  onToggle,
}: {
  scope: string;
  relatedCapabilities: McpCapabilityConfigRead[];
  enabled: boolean;
  disabled: boolean;
  statusEnabledLabel: string;
  statusDisabledLabel: string;
  helpTitle: string;
  helpDescription: string;
  helpUsageTitle: string;
  helpUsageItems: string[];
  onToggle: (checked: boolean) => void;
}) {
  return (
    <div className="rounded-[var(--admin-radius-lg)] border border-border/60 bg-background/55 px-4 py-4">
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <LabelWithHelp
              label={
                <span className="inline-flex items-center rounded-full border border-[rgba(var(--admin-border-strong)/var(--admin-border-strong-alpha))] bg-[rgb(var(--admin-surface-1)/0.32)] px-2.5 py-1 font-mono text-xs font-semibold text-foreground">
                  {scope}
                </span>
              }
              title={helpTitle}
              description={helpDescription}
              usageTitle={helpUsageTitle}
              usageItems={helpUsageItems}
              className="gap-1.5"
            />
            <Badge variant={enabled ? "info" : "secondary"}>
              {enabled ? statusEnabledLabel : statusDisabledLabel}
            </Badge>
            <Badge variant="outline">{relatedCapabilities.length}</Badge>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {relatedCapabilities.slice(0, 6).map((capability) => (
              <Badge key={capability.id} variant="outline">
                {capability.name}
              </Badge>
            ))}
            {relatedCapabilities.length > 6 ? (
              <Badge variant="outline">+{relatedCapabilities.length - 6}</Badge>
            ) : null}
          </div>
        </div>
        <button
          type="button"
          role="switch"
          aria-checked={enabled}
          onClick={() => onToggle(!enabled)}
          disabled={disabled}
          className={cn(
            "relative mt-1 inline-flex h-8 w-14 shrink-0 items-center overflow-hidden rounded-full border transition-all duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2",
            enabled
              ? "border-sky-400/45 bg-gradient-to-r from-sky-500/35 via-cyan-400/25 to-emerald-400/25 shadow-[inset_0_1px_0_rgba(255,255,255,0.24),0_0_0_1px_rgba(56,189,248,0.14),0_10px_28px_rgba(14,165,233,0.12)]"
              : "border-slate-400/25 bg-slate-500/12 shadow-[inset_0_1px_0_rgba(255,255,255,0.14),0_0_0_1px_rgba(148,163,184,0.08)]",
            disabled && "pointer-events-none opacity-60",
          )}
        >
          <span
            className={cn(
              "pointer-events-none relative block h-6 w-6 rounded-full bg-white shadow-[0_8px_18px_rgba(15,23,42,0.18)] ring-1 ring-black/5 transition-transform duration-200 before:absolute before:inset-[0.15rem] before:rounded-full before:bg-gradient-to-br before:from-white/90 before:to-white/35 before:content-[''] dark:bg-slate-100 dark:ring-white/10 dark:before:from-white/45 dark:before:to-white/10",
              enabled ? "translate-x-6" : "translate-x-1",
            )}
          />
        </button>
      </div>
    </div>
  );
}

export function McpPermissionsSection() {
  const { t, lang } = useI18n();
  const queryClient = useQueryClient();
  const [selectedApiKeyId, setSelectedApiKeyId] = useState("");
  const { data: rawKeys, isLoading: isKeysLoading } =
    useListApiKeysApiV1AdminIntegrationsApiKeysGet();

  const apiKeys = rawKeys?.data as ApiKeyAdminRead[] | undefined;
  const selectedKey = useMemo(
    () => apiKeys?.find((item) => item.id === selectedApiKeyId) ?? null,
    [apiKeys, selectedApiKeyId],
  );

  const { data: config, isLoading: isConfigLoading } = useQuery<McpAdminConfigRead>({
    queryKey: ["admin", "mcp-config", "permissions", selectedApiKeyId],
    queryFn: () => getMcpConfig(selectedApiKeyId || undefined),
  });

  const capabilities = useMemo(
    () =>
      [...(config?.capabilities ?? [])].sort((left, right) => {
        if (left.kind !== right.kind) {
          return left.kind.localeCompare(right.kind);
        }
        return left.name.localeCompare(right.name);
      }),
    [config?.capabilities],
  );

  const currentScopes = useMemo(
    () => config?.api_key_scopes ?? selectedKey?.scopes ?? [],
    [config?.api_key_scopes, selectedKey?.scopes],
  );
  const currentMcpScopes = useMemo(
    () => mcpScopesOnly(currentScopes),
    [currentScopes],
  );
  const enabledScopeSet = useMemo(
    () => new Set(currentMcpScopes),
    [currentMcpScopes],
  );
  const enabledCapabilityIds = useMemo(
    () => new Set(capabilities.filter((capability) => capability.enabled).map((capability) => capability.id)),
    [capabilities],
  );
  const scopeRows = useMemo(
    () =>
      MCP_SCOPE_ORDER.map((scope) => {
        const relatedCapabilities = capabilities.filter((capability) =>
          (capability.required_scopes ?? []).includes(scope),
        );
        return {
          scope,
          relatedCapabilities,
          help: buildScopeHelp(scope, relatedCapabilities, lang),
        };
      }),
    [capabilities, lang],
  );

  const readonlyPreset = useMemo(
    () =>
      capabilities.filter(
        (item) => !(item.required_scopes ?? []).some((scope) => scope.endsWith(":write")),
      ),
    [capabilities],
  );
  const basicPreset = useMemo(
    () =>
      capabilities.filter((item) =>
        (item.required_scopes ?? []).every(
          (scope) =>
            scope === "content:write" ||
            scope === "moderation:write" ||
            !scope.endsWith(":write"),
        ),
      ),
    [capabilities],
  );
  const fullPreset = capabilities;

  const presets = useMemo(
    () => [
      {
        key: "readonly" as const,
        name: t("integrations.mcpKeyReadonly"),
        description: t("integrations.mcpKeyReadonlyHint"),
        capability_ids: readonlyPreset.map((item) => item.id),
      },
      {
        key: "basic_management" as const,
        name: t("integrations.mcpKeyBasic"),
        description: t("integrations.mcpKeyBasicHint"),
        capability_ids: basicPreset.map((item) => item.id),
      },
      {
        key: "full_management" as const,
        name: t("integrations.mcpKeyFull"),
        description: t("integrations.mcpKeyFullHint"),
        capability_ids: fullPreset.map((item) => item.id),
      },
    ],
    [basicPreset, fullPreset, readonlyPreset, t],
  );

  const presetDisplay = useMemo(
    () => describeMcpPreset(currentScopes),
    [currentScopes],
  );

  const update = useUpdateApiKeyApiV1AdminIntegrationsApiKeysKeyIdPut({
    mutation: {
      onSuccess: async () => {
        await queryClient.invalidateQueries({
          queryKey: getListApiKeysApiV1AdminIntegrationsApiKeysGetQueryKey(),
        });
        await queryClient.invalidateQueries({ queryKey: ["admin", "mcp-config"] });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(extractApiErrorMessage(error, t("common.operationFailed")));
      },
    },
  });

  useEffect(() => {
    if (!apiKeys || apiKeys.length === 0) {
      return;
    }
    if (!selectedApiKeyId || !apiKeys.some((item) => item.id === selectedApiKeyId)) {
      setSelectedApiKeyId(apiKeys[0].id);
    }
  }, [apiKeys, selectedApiKeyId]);

  const saveScopes = async (nextMcpScopes: string[]) => {
    if (!selectedKey) {
      toast.error(t("integrations.selectApiKey"));
      return;
    }
    const nextScopes = mergeMcpScopes(
      currentScopes,
      normalizeMcpScopeSelection(nextMcpScopes),
    );
    try {
      await update.mutateAsync({ keyId: selectedKey.id, data: { scopes: nextScopes } });
    } catch {
      return;
    }
  };

  const applyPreset = async (
    presetKey: "readonly" | "basic_management" | "full_management",
  ) => {
    const preset = presets.find((item) => item.key === presetKey);
    if (!preset) {
      return;
    }
    const presetScopes = capabilities
      .filter((capability) => preset.capability_ids.includes(capability.id))
      .flatMap((capability) => capability.required_scopes ?? []);
    await saveScopes(presetScopes);
  };

  const toggleScope = async (scope: string, checked: boolean) => {
    const nextScopes = new Set(currentMcpScopes);
    if (scope === CONNECT_SCOPE && !checked) {
      nextScopes.clear();
      await saveScopes([...nextScopes]);
      return;
    }

    if (checked) {
      nextScopes.add(scope);
    } else {
      nextScopes.delete(scope);
      const writeScope = relatedWriteScope(scope);
      if (writeScope) {
        nextScopes.delete(writeScope);
      }
    }

    await saveScopes([...nextScopes]);
  };

  if (isKeysLoading || isConfigLoading) {
    return (
      <p className="py-4 text-sm text-muted-foreground">{t("common.loading")}</p>
    );
  }

  if (!apiKeys || apiKeys.length === 0) {
    return (
      <AdminSurface title={t("integrations.configureApiPermissions")}>
        <p className="rounded-[var(--admin-radius-lg)] border border-dashed border-border/60 bg-background/55 px-4 py-4 text-sm text-muted-foreground">
          {t("integrations.noMcpKeys")}
        </p>
      </AdminSurface>
    );
  }

  return (
    <div className="space-y-4">
      <AdminSurface
        title={t("integrations.configureApiPermissions")}
        actions={
          <div className="w-full sm:w-[18rem]">
            <NativeSelect
              value={selectedApiKeyId}
              onChange={(event) => setSelectedApiKeyId(event.target.value)}
              className="h-11 rounded-xl border-border/50 bg-background/70"
              aria-label={t("integrations.selectApiKey")}
            >
              <option value="" disabled>
                {t("integrations.selectApiKey")}
              </option>
              {apiKeys.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.key_name}
                </option>
              ))}
            </NativeSelect>
          </div>
        }
      >
        <div className="grid gap-3 lg:grid-cols-3">
          {presets.map((preset) => (
            <PresetCard
              key={preset.key}
              preset={preset}
              active={presetDisplay.basePreset === preset.key}
              customized={
                presetDisplay.basePreset === preset.key && presetDisplay.isCustom
              }
              disabled={update.isPending}
              customLabel={t("integrations.mcpKeyCustom")}
              count={
                presetDisplay.basePreset === preset.key && presetDisplay.isCustom
                  ? enabledCapabilityIds.size
                  : preset.capability_ids.length
              }
              onSelect={() => void applyPreset(preset.key)}
            />
          ))}
        </div>

        <CollapsibleSection
          title={t("integrations.capabilityToggleTitle")}
          className="mt-4 border border-border/60 bg-background/40"
        >
          <div className="grid gap-3">
            {scopeRows.map((item) => (
              <ScopeRow
                key={item.scope}
                scope={item.scope}
                relatedCapabilities={item.relatedCapabilities}
                enabled={enabledScopeSet.has(item.scope)}
                disabled={update.isPending}
                statusEnabledLabel={t("integrations.mcpEnabled")}
                statusDisabledLabel={t("integrations.mcpDisabled")}
                helpTitle={item.help.title}
                helpDescription={item.help.description}
                helpUsageTitle={item.help.usageTitle}
                helpUsageItems={item.help.usageItems}
                onToggle={(checked) => void toggleScope(item.scope, checked)}
              />
            ))}
          </div>
        </CollapsibleSection>
      </AdminSurface>
    </div>
  );
}
