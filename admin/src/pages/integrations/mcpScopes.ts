export type McpKeyPreset = "readonly" | "basic_management" | "full_management" | "custom";
export type McpResolvedPreset = Exclude<McpKeyPreset, "custom">;

export interface McpPresetDisplayState {
  basePreset: McpResolvedPreset | null;
  isCustom: boolean;
}

export const MCP_SCOPE_PRESETS: Record<McpResolvedPreset, string[]> = {
  readonly: [
    "mcp:connect",
    "mcp:content:read",
    "mcp:moderation:read",
    "mcp:config:read",
    "mcp:assets:read",
  ],
  basic_management: [
    "mcp:connect",
    "mcp:content:read",
    "mcp:content:write",
    "mcp:moderation:read",
    "mcp:moderation:write",
    "mcp:config:read",
    "mcp:assets:read",
  ],
  full_management: [
    "mcp:connect",
    "mcp:content:read",
    "mcp:content:write",
    "mcp:moderation:read",
    "mcp:moderation:write",
    "mcp:config:read",
    "mcp:config:write",
    "mcp:assets:read",
    "mcp:assets:write",
  ],
};

export const MCP_SCOPE_ORDER = Array.from(new Set(Object.values(MCP_SCOPE_PRESETS).flat()));
export const MCP_SCOPE_SET = new Set(MCP_SCOPE_ORDER);
export type McpScope = (typeof MCP_SCOPE_ORDER)[number];
const BASIC_MANAGEMENT_EXTRA_SCOPES = ["mcp:content:write", "mcp:moderation:write"];
const FULL_MANAGEMENT_EXTRA_SCOPES = ["mcp:config:write", "mcp:assets:write"];
const WRITE_TO_READ_SCOPE: Record<string, string> = {
  "mcp:content:write": "mcp:content:read",
  "mcp:moderation:write": "mcp:moderation:read",
  "mcp:config:write": "mcp:config:read",
  "mcp:assets:write": "mcp:assets:read",
};
const READ_TO_WRITE_SCOPE: Record<string, string> = Object.fromEntries(
  Object.entries(WRITE_TO_READ_SCOPE).map(([writeScope, readScope]) => [readScope, writeScope]),
);

export function normalizeScopes(scopes: string[]) {
  return [...new Set(scopes)].sort();
}

export function mcpScopesOnly(scopes: string[]) {
  return normalizeScopes(scopes.filter((scope) => MCP_SCOPE_SET.has(scope)));
}

export function mergeMcpScopes(currentScopes: string[], nextMcpScopes: string[]) {
  const preserved = currentScopes.filter((scope) => !MCP_SCOPE_SET.has(scope));
  return normalizeScopes([...preserved, ...nextMcpScopes]);
}

export function normalizeMcpScopeSelection(scopes: string[]) {
  const enabled = new Set(mcpScopesOnly(scopes));
  if (enabled.size === 0) {
    return [];
  }

  for (const [writeScope, readScope] of Object.entries(WRITE_TO_READ_SCOPE)) {
    if (enabled.has(writeScope)) {
      enabled.add(readScope);
    }
  }

  const hasFunctionalScope = [...enabled].some((scope) => scope !== "mcp:connect");
  if (hasFunctionalScope) {
    enabled.add("mcp:connect");
  }

  return MCP_SCOPE_ORDER.filter((scope) => enabled.has(scope));
}

export function relatedWriteScope(scope: string) {
  return READ_TO_WRITE_SCOPE[scope] ?? null;
}

export function detectMcpPreset(scopes: string[]): McpKeyPreset | null {
  const normalized = mcpScopesOnly(scopes);
  if (!normalized.includes("mcp:connect")) {
    return null;
  }
  for (const [preset, presetScopes] of Object.entries(MCP_SCOPE_PRESETS)) {
    if (JSON.stringify(normalized) === JSON.stringify(normalizeScopes(presetScopes))) {
      return preset as Exclude<McpKeyPreset, "custom">;
    }
  }
  return "custom";
}

export function describeMcpPreset(scopes: string[]): McpPresetDisplayState {
  const detected = detectMcpPreset(scopes);
  if (detected === null) {
    return { basePreset: null, isCustom: false };
  }
  if (detected !== "custom") {
    return { basePreset: detected, isCustom: false };
  }

  const enabledScopes = new Set(mcpScopesOnly(scopes));
  if (FULL_MANAGEMENT_EXTRA_SCOPES.some((scope) => enabledScopes.has(scope))) {
    return { basePreset: "full_management", isCustom: true };
  }
  if (BASIC_MANAGEMENT_EXTRA_SCOPES.some((scope) => enabledScopes.has(scope))) {
    return { basePreset: "basic_management", isCustom: true };
  }
  return { basePreset: "readonly", isCustom: true };
}

export function scopesForPreset(preset: McpKeyPreset, fallbackScopes: string[]) {
  if (preset === "custom") {
    return fallbackScopes;
  }
  return MCP_SCOPE_PRESETS[preset];
}

export function presetLabel(t: (key: string) => string, preset: McpKeyPreset) {
  if (preset === "readonly") return t("integrations.mcpKeyReadonly");
  if (preset === "basic_management") return t("integrations.mcpKeyBasic");
  if (preset === "full_management") return t("integrations.mcpKeyFull");
  return t("integrations.mcpKeyCustom");
}
