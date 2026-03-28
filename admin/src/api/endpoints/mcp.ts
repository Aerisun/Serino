import { getAdminToken } from "@/lib/storage";

export interface McpPresetRead {
  key: string;
  name: string;
  description: string;
  capability_ids: string[];
}

export interface McpCapabilityConfigRead {
  id: string;
  name: string;
  kind: string;
  description: string;
  required_scopes: string[];
  enabled: boolean;
}

export interface McpAdminConfigRead {
  api_key_id: string | null;
  api_key_name: string | null;
  api_key_scopes: string[];
  public_access: boolean;
  selected_preset: string;
  is_customized: boolean;
  enabled_capability_count: number;
  available_capability_count: number;
  usage_url: string;
  endpoint: string;
  transport: string;
  required_scopes: string[];
  recommended_scopes: string[];
  presets: McpPresetRead[];
  capabilities: McpCapabilityConfigRead[];
}

export interface McpAdminConfigUpdate {
  public_access?: boolean;
  selected_preset?: string;
  enabled_capability_ids?: string[];
}

async function adminRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAdminToken();
  if (!token) {
    throw new Error("未登录，无法执行管理操作");
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new Error("请求失败，请检查网络连接或后端服务状态");
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? payload.detail
        : undefined;
    throw new Error(typeof detail === "string" ? detail : "操作失败");
  }
  return payload as T;
}

function buildMcpConfigUrl(apiKeyId?: string) {
  if (!apiKeyId) {
    return "/api/v1/admin/integrations/mcp-config";
  }
  return `/api/v1/admin/integrations/mcp-config?api_key_id=${encodeURIComponent(apiKeyId)}`;
}

export function getMcpConfig(apiKeyId?: string) {
  return adminRequest<McpAdminConfigRead>(buildMcpConfigUrl(apiKeyId), {
    method: "GET",
  });
}

export function updateMcpConfig(data: McpAdminConfigUpdate, apiKeyId?: string) {
  return adminRequest<McpAdminConfigRead>(buildMcpConfigUrl(apiKeyId), {
    method: "PUT",
    body: JSON.stringify(data),
  });
}
