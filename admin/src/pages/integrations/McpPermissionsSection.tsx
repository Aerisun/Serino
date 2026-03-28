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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/Select";
import { cn } from "@/lib/utils";
import { useI18n } from "@/i18n";
import { toast } from "sonner";
import { getMcpConfig, type McpAdminConfigRead, type McpCapabilityConfigRead } from "@/api/endpoints/mcp";
import {
  describeMcpPreset,
  MCP_SCOPE_ORDER,
  mcpScopesOnly,
  mergeMcpScopes,
  normalizeMcpScopeSelection,
  relatedWriteScope,
} from "./mcpScopes";

function buildScopeHelp(
  scope: string,
  relatedCapabilities: McpCapabilityConfigRead[],
  lang: "zh" | "en",
) {
  const kindLabel = (kind: string) => {
    if (lang === "zh") {
      return kind === "tool" ? "工具" : "资源";
    }
    return kind === "tool" ? "tool" : "resource";
  };

  const capabilitySummary =
    relatedCapabilities.length > 0
      ? relatedCapabilities.map((capability) =>
          lang === "zh"
            ? `${capability.name}（${kindLabel(capability.kind)}）：${capability.description}`
            : `${capability.name} (${kindLabel(capability.kind)}): ${capability.description}`,
        )
      : [
          lang === "zh"
            ? "当前版本还没有 MCP 能力直接依赖这个 scope，但它会影响后续新增能力是否可用。"
            : "No MCP capability depends on this scope yet, but it still affects future capability expansion.",
        ];

  const toolCount = relatedCapabilities.filter((item) => item.kind === "tool").length;
  const resourceCount = relatedCapabilities.length - toolCount;
  const sharedItems =
    lang === "zh"
      ? [
          `当前直接关联 ${relatedCapabilities.length} 个 MCP 能力，其中工具 ${toolCount} 个、资源 ${resourceCount} 个。`,
          ...capabilitySummary,
        ]
      : [
          `This scope currently affects ${relatedCapabilities.length} MCP capabilities: ${toolCount} tools and ${resourceCount} resources.`,
          ...capabilitySummary,
        ];

  if (scope === "mcp:connect") {
    return {
      title: lang === "zh" ? "mcp:connect 详细说明" : "mcp:connect details",
      description:
        lang === "zh"
          ? "这是 MCP 访问的总开关。它本身不直接授予内容、配置、资源或审核操作，但决定这个 API Key 是否允许远端 Agent 连接 /api/mcp，并读取 /api/agent/usage 里的 MCP 能力说明。只要它关闭，其他 mcp:* scopes 即使保留在 API Key 上，也无法真正建立 MCP 会话。"
          : "This is the master switch for MCP access. It does not directly grant content, config, asset, or moderation actions, but it decides whether the API key can connect to /api/mcp and read MCP usage metadata from /api/agent/usage. If it is off, the other mcp:* scopes cannot establish a usable MCP session even if they remain on the key.",
      usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
      usageItems:
        lang === "zh"
          ? [
              "开启后，远端 Agent 才能真正发起 MCP 连接并枚举当前允许访问的 tools / resources。",
              "关闭后，当前 API Key 的所有 MCP 访问会被整体阻断；这也是界面里关闭它时会一并清空其他 MCP scopes 的原因。",
              "它通常应该与至少一个具体读写 scope 一起使用；单独开启 connect 只能建立连接，无法访问具体能力。",
              ...sharedItems,
            ]
          : [
              "When enabled, remote agents can establish an MCP session and enumerate the tools and resources available to this API key.",
              "When disabled, MCP access is effectively blocked for the current API key, which is why turning it off also clears the other MCP scopes in the UI.",
              "It is usually paired with at least one functional read/write scope. Enabling connect alone allows the connection but not meaningful capability access.",
              ...sharedItems,
            ],
    };
  }

  if (scope === "mcp:content:read") {
    return {
      title: lang === "zh" ? "mcp:content:read 详细说明" : "mcp:content:read details",
      description:
        lang === "zh"
          ? "这个 scope 负责内容读取权限，覆盖站点内容与后台内容的查看、列表、搜索、详情读取等能力。它适合只做检索、分析、汇总、问答、生成草稿参考的 Agent，不包含创建、修改、发布或删除内容的写操作。"
          : "This scope controls read-only content access, including listing, searching, and viewing public or admin-side content. It suits agents that analyze, summarize, answer questions, or prepare drafts without changing content state.",
      usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
      usageItems:
        lang === "zh"
          ? [
              "开启后，Agent 可以读取文章、日记、想法、摘录等内容，以及后台内容列表和详情类能力。",
              "关闭后，所有依赖内容读取的 MCP 工具与资源都会消失，Agent 无法再基于站点内容做检索和分析。",
              "它是 mcp:content:write 的基础依赖；只要你给了内容写权限，系统会同时保留内容读权限。",
              "这是内容类最安全的最小授权，适合知识问答、内容审校前检查、摘要和分类建议等场景。",
              ...sharedItems,
            ]
          : [
              "When enabled, agents can read posts, diary entries, thoughts, excerpts, and admin-side content list/detail capabilities.",
              "When disabled, all content-reading tools and resources disappear, so agents can no longer search or analyze site content.",
              "It is the base dependency for mcp:content:write. If write access is granted, read access should remain available as well.",
              "This is the safest minimum scope for Q&A, content review preparation, summaries, and classification suggestions.",
              ...sharedItems,
            ],
    };
  }

  if (scope === "mcp:content:write") {
    return {
      title: lang === "zh" ? "mcp:content:write 详细说明" : "mcp:content:write details",
      description:
        lang === "zh"
          ? "这个 scope 负责内容写入和状态变更，包含创建、更新、删除、发布、取消发布、标签维护等会改变内容结果的能力。它属于高风险权限，适合可信任的自动化流程或明确受控的编辑型 Agent。"
          : "This scope controls content mutations such as create, update, delete, publish, unpublish, and taxonomy changes. It is a high-risk permission intended for trusted automation or tightly controlled editorial agents.",
      usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
      usageItems:
        lang === "zh"
          ? [
              "开启后，Agent 可以直接改动内容结果，而不只是读取，因此会影响线上展示、内容可见性和后台数据状态。",
              "关闭后，内容类 Agent 仍可在保留 read 的前提下做分析和建议，但不能真正提交修改。",
              "系统会自动补齐 mcp:content:read，因为绝大多数写入动作都需要先读取现有内容、slug、标签或发布状态。",
              "建议只给明确需要发布、修文、批量整理标签、自动归档等流程使用，不建议给只做问答的 Agent。",
              ...sharedItems,
            ]
          : [
              "When enabled, the agent can change actual content state instead of only reading it, which may affect live pages and admin data.",
              "When disabled, content agents can still analyze and recommend changes if read access remains, but they cannot commit modifications.",
              "The UI automatically keeps mcp:content:read because most write flows need to inspect current content, slugs, tags, or publication state first.",
              "Grant this only to trusted workflows that truly need publishing or editing privileges, not to read-only assistant agents.",
              ...sharedItems,
            ],
    };
  }

  if (scope === "mcp:moderation:read") {
    return {
      title: lang === "zh" ? "mcp:moderation:read 详细说明" : "mcp:moderation:read details",
      description:
        lang === "zh"
          ? "这个 scope 负责审核信息读取，主要用于查看评论、留言及其审核队列、详情和上下文。它适合只做巡检、分类、风险分析和人工复核辅助的 Agent，不会直接做通过、拒绝或隐藏等写动作。"
          : "This scope controls read-only moderation access for comments, guestbook entries, moderation queues, and related context. It suits review, categorization, and risk-analysis agents without granting moderation actions.",
      usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
      usageItems:
        lang === "zh"
          ? [
              "开启后，Agent 可以读取待审核数据并理解上下文，用于打标、排序、预判风险或给人工审核提供建议。",
              "关闭后，审核队列与详情类 MCP 能力不会再暴露给当前 API Key。",
              "它是 mcp:moderation:write 的基础依赖，因为执行审核动作前通常需要先看到原始评论、状态和上下文。",
              "如果你只想让 Agent 看，不想让它真正处理审核结果，只保留 read 就够了。",
              ...sharedItems,
            ]
          : [
              "When enabled, the agent can inspect moderation data and context for triage, labeling, ranking, or review assistance.",
              "When disabled, moderation queue and detail capabilities are no longer exposed to the current API key.",
              "It is the base dependency for mcp:moderation:write because moderation actions usually require reading the original comment and context first.",
              "Use read-only moderation access when the agent should observe and recommend rather than act.",
              ...sharedItems,
            ],
    };
  }

  if (scope === "mcp:moderation:write") {
    return {
      title: lang === "zh" ? "mcp:moderation:write 详细说明" : "mcp:moderation:write details",
      description:
        lang === "zh"
          ? "这个 scope 允许执行真正的审核动作，例如通过、拒绝、隐藏或更新审核状态。它会直接影响评论和留言是否可见，因此应只授予受信任、规则明确的审核 Agent。"
          : "This scope allows real moderation actions such as approve, reject, hide, or otherwise change moderation state. Because it directly affects comment visibility, it should only be granted to trusted moderation agents.",
      usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
      usageItems:
        lang === "zh"
          ? [
              "开启后，Agent 不只是能看审核队列，还能真正改变审核结果和前台可见状态。",
              "关闭后，审核类 Agent 如果仍保留 read，就只能给建议、打标或做预判，不能落地处理。",
              "系统会同时保留 mcp:moderation:read，确保 Agent 在执行动作前仍能看到审核对象的完整上下文。",
              "这种权限建议结合明确策略、审计日志和可追踪责任链使用。",
              ...sharedItems,
            ]
          : [
              "When enabled, the agent can change moderation outcomes instead of merely reading the queue.",
              "When disabled, moderation agents can still recommend or classify items if read access remains, but they cannot apply decisions.",
              "The UI keeps mcp:moderation:read alongside it so the agent can still inspect the full moderation context before acting.",
              "This permission is best paired with clear policy, auditability, and accountability.",
              ...sharedItems,
            ],
    };
  }

  if (scope === "mcp:config:read") {
    return {
      title: lang === "zh" ? "mcp:config:read 详细说明" : "mcp:config:read details",
      description:
        lang === "zh"
          ? "这个 scope 负责读取站点配置、站点资料和记录类信息。它适合做后台配置检查、环境理解、问题排查和建议生成，但不会直接修改站点设置。"
          : "This scope allows read-only access to site configuration, profile, and record-like administrative data. It is suitable for diagnostics, configuration review, and recommendation workflows without allowing mutations.",
      usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
      usageItems:
        lang === "zh"
          ? [
              "开启后，Agent 可以理解站点当前配置状态，帮助做排障、审查和配置建议。",
              "关闭后，配置类读取能力将不会再暴露，Agent 对站点结构和配置环境的理解会明显下降。",
              "它是 mcp:config:write 的基础依赖；需要改配置的 Agent 通常也必须先看到当前值。",
              "如果你的 Agent 只需要懂站点怎么配，而不应该改配置，这个 scope 是正确选择。",
              ...sharedItems,
            ]
          : [
              "When enabled, the agent can inspect current site configuration and use it for diagnostics, review, and recommendations.",
              "When disabled, configuration-reading capabilities disappear, which reduces the agent's understanding of the site's setup.",
              "It is the base dependency for mcp:config:write because config-changing agents usually need to inspect the current state first.",
              "Use this when the agent should understand configuration but not change it.",
              ...sharedItems,
            ],
    };
  }

  if (scope === "mcp:config:write") {
    return {
      title: lang === "zh" ? "mcp:config:write 详细说明" : "mcp:config:write details",
      description:
        lang === "zh"
          ? "这个 scope 允许修改站点配置、记录项以及部分管理动作。它会直接影响站点行为和后台系统状态，因此属于高风险管理权限。"
          : "This scope allows changing site configuration, records, and some operational actions. It directly affects system behavior and is therefore a high-risk administrative permission.",
      usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
      usageItems:
        lang === "zh"
          ? [
              "开启后，Agent 可以真正改动配置结果，而不只是给建议，这可能影响前台显示、系统行为或内部数据。",
              "关闭后，配置类 Agent 仍可在保留 read 的前提下做检查和建议，但不能提交配置变更。",
              "系统会同时保留 mcp:config:read，确保写入前能读取旧值、理解当前状态并做差异判断。",
              "建议只给后台运维、配置同步、定时修复等强信任自动化流程使用。",
              ...sharedItems,
            ]
          : [
              "When enabled, the agent can change actual configuration state rather than only recommending changes.",
              "When disabled, configuration agents can still inspect and advise if read access remains, but cannot commit modifications.",
              "The UI keeps mcp:config:read alongside it so the agent can compare against the current state before writing.",
              "Grant this only to highly trusted maintenance or operations workflows.",
              ...sharedItems,
            ],
    };
  }

  if (scope === "mcp:assets:read") {
    return {
      title: lang === "zh" ? "mcp:assets:read 详细说明" : "mcp:assets:read details",
      description:
        lang === "zh"
          ? "这个 scope 负责素材库读取，允许查看资源列表、资源详情和资源元数据。它适合素材检索、引用、盘点和内容编排辅助，但不允许上传、更新或删除素材。"
          : "This scope provides read-only asset library access for listing assets, viewing details, and inspecting metadata. It is useful for retrieval, referencing, and inventory workflows without permitting uploads or changes.",
      usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
      usageItems:
        lang === "zh"
          ? [
              "开启后，Agent 可以知道素材库里有什么、如何引用、哪些资源可用于内容生成或发布流程。",
              "关闭后，素材类读取能力会消失，Agent 无法再基于已有资源做查找和引用建议。",
              "它是 mcp:assets:write 的基础依赖，因为写入资源前通常需要查看已有文件、元数据或引用关系。",
              "如果你只想让 Agent 挑素材、看素材，不让它改素材，这个 scope 就足够。",
              ...sharedItems,
            ]
          : [
              "When enabled, the agent can inspect what exists in the asset library and how assets may be referenced.",
              "When disabled, asset lookup capabilities disappear and the agent can no longer search or reference existing assets.",
              "It is the base dependency for mcp:assets:write because asset management flows often need to inspect current files or metadata first.",
              "Use this when the agent should browse assets but not mutate them.",
              ...sharedItems,
            ],
    };
  }

  return {
    title: lang === "zh" ? "mcp:assets:write 详细说明" : "mcp:assets:write details",
    description:
      lang === "zh"
        ? "这个 scope 允许上传、更新、删除素材资源及其相关信息。它会直接改变素材库内容，适合可信任的媒体管理、自动发布或批量整理流程。"
        : "This scope allows uploading, updating, and deleting assets and related metadata. It directly changes the asset library and should be reserved for trusted media-management workflows.",
    usageTitle: lang === "zh" ? "详细权限与影响范围" : "Detailed behavior and impact",
    usageItems:
      lang === "zh"
        ? [
            "开启后，Agent 可以真正改动物料库，包括新增资源、更新资源信息或删除已有资源。",
            "关闭后，资源类 Agent 如果仍保留 read，就只能查找和引用现有素材，不能改动素材库。",
            "系统会同时保留 mcp:assets:read，确保写入前能先看到已有资源与元数据。",
            "建议把它限制在素材同步、批量清理、自动上传等明确流程中，不要给泛用问答 Agent。",
            ...sharedItems,
          ]
        : [
            "When enabled, the agent can upload, update, or delete asset-library entries.",
            "When disabled, asset-oriented agents can still inspect and reference assets if read access remains, but cannot mutate the library.",
            "The UI keeps mcp:assets:read alongside it so the agent can inspect current files and metadata before writing.",
            "Grant this only to explicit upload, sync, or cleanup workflows rather than general-purpose assistants.",
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
  preset: { key: "readonly" | "basic_management" | "full_management"; name: string; description: string; capability_ids: string[] };
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
        "text-left rounded-[var(--admin-radius-lg)] border px-4 py-4 transition-[background-color,border-color,box-shadow,transform]",
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
      <p className="mt-2 text-sm leading-6 text-muted-foreground">{preset.description}</p>
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
  const [selectedApiKeyId, setSelectedApiKeyId] = useState<string>("");
  const { data: rawKeys, isLoading: isKeysLoading } = useListApiKeysApiV1AdminIntegrationsApiKeysGet();

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
  const currentMcpScopes = useMemo(() => mcpScopesOnly(currentScopes), [currentScopes]);
  const enabledScopeSet = useMemo(() => new Set(currentMcpScopes), [currentMcpScopes]);
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
    () => capabilities.filter((item) => !(item.required_scopes ?? []).some((scope) => scope.endsWith(":write"))),
    [capabilities],
  );
  const basicPreset = useMemo(
    () =>
      capabilities.filter((item) =>
        (item.required_scopes ?? []).every(
          (scope) =>
            scope === "mcp:content:write" ||
            scope === "mcp:moderation:write" ||
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

  const presetDisplay = useMemo(() => describeMcpPreset(currentScopes), [currentScopes]);

  const update = useUpdateApiKeyApiV1AdminIntegrationsApiKeysKeyIdPut({
    mutation: {
      onSuccess: async () => {
        await queryClient.invalidateQueries({ queryKey: getListApiKeysApiV1AdminIntegrationsApiKeysGetQueryKey() });
        await queryClient.invalidateQueries({ queryKey: ["admin", "mcp-config"] });
        toast.success(t("common.operationSuccess"));
      },
      onError: (error: any) => {
        toast.error(error?.response?.data?.detail || t("common.operationFailed"));
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
    const nextScopes = mergeMcpScopes(currentScopes, normalizeMcpScopeSelection(nextMcpScopes));
    try {
      await update.mutateAsync({ keyId: selectedKey.id, data: { scopes: nextScopes } });
    } catch {
      return;
    }
  };

  const applyPreset = async (presetKey: "readonly" | "basic_management" | "full_management") => {
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
    if (scope === "mcp:connect" && !checked) {
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
    return <p className="py-4 text-sm text-muted-foreground">{t("common.loading")}</p>;
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
            <Select value={selectedApiKeyId} onValueChange={(value) => setSelectedApiKeyId(value)}>
              <SelectTrigger className="h-11 rounded-xl border-border/50 bg-background/70">
                <SelectValue placeholder={t("integrations.selectApiKey")} />
              </SelectTrigger>
              <SelectContent>
                {apiKeys.map((item) => (
                  <SelectItem key={item.id} value={item.id}>
                    {item.key_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        }
      >
        <div className="grid gap-3 lg:grid-cols-3">
          {presets.map((preset) => (
            <PresetCard
              key={preset.key}
              preset={preset}
              active={presetDisplay.basePreset === preset.key}
              customized={presetDisplay.basePreset === preset.key && presetDisplay.isCustom}
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
