import { getAdminToken } from "@/lib/storage";

export interface ConfigRevisionListItem {
  id: string;
  actor_id: string | null;
  resource_key: string;
  resource_label: string;
  operation: string;
  resource_version: string;
  summary: string;
  changed_fields: string[];
  sensitive_fields: string[];
  restored_from_revision_id: string | null;
  created_at: string;
}

export interface ConfigDiffLine {
  path: string;
  before: string;
  after: string;
}

export interface ConfigRevisionDetail extends ConfigRevisionListItem {
  before_preview: unknown;
  after_preview: unknown;
  diff_lines: ConfigDiffLine[];
  restorable: boolean;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

interface ConfigRevisionListParams {
  page?: number;
  page_size?: number;
  resource_key?: string;
  actor_id?: string;
  date_from?: string;
  date_to?: string;
}

interface RestoreRevisionPayload {
  target?: "before" | "after";
  reason?: string;
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

function buildQuery(params: ConfigRevisionListParams): string {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  const query = search.toString();
  return query ? `?${query}` : "";
}

export function listConfigRevisions(params: ConfigRevisionListParams) {
  return adminRequest<PaginatedResponse<ConfigRevisionListItem>>(
    `/api/v1/admin/system/config-revisions${buildQuery(params)}`,
    {
      method: "GET",
    },
  );
}

export function getConfigRevisionDetail(revisionId: string) {
  return adminRequest<ConfigRevisionDetail>(`/api/v1/admin/system/config-revisions/${revisionId}`, {
    method: "GET",
  });
}

export function restoreConfigRevision(revisionId: string, payload: RestoreRevisionPayload = {}) {
  return adminRequest<ConfigRevisionDetail>(`/api/v1/admin/system/config-revisions/${revisionId}/restore`, {
    method: "POST",
    body: JSON.stringify({
      target: payload.target ?? "before",
      reason: payload.reason,
    }),
  });
}
