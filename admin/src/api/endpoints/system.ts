import { adminRequest } from "./admin-request";

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
