import { getAdminToken } from "@/lib/storage";

export interface ObjectStorageConfigRead {
  enabled: boolean;
  provider: "bitiful";
  bucket: string;
  endpoint: string;
  region: string;
  public_base_url: string;
  access_key: string;
  secret_key_configured: boolean;
  cdn_token_key_configured: boolean;
  health_check_enabled: boolean;
  upload_expire_seconds: number;
  public_download_expire_seconds: number;
  mirror_bandwidth_limit_bps: number;
  mirror_retry_count: number;
  last_health_ok?: boolean | null;
  last_health_error?: string | null;
  last_health_checked_at?: string | null;
}

export interface ObjectStorageConfigUpdate {
  enabled?: boolean;
  provider?: "bitiful";
  bucket?: string;
  endpoint?: string;
  region?: string;
  public_base_url?: string;
  access_key?: string;
  secret_key?: string;
  cdn_token_key?: string;
  health_check_enabled?: boolean;
  upload_expire_seconds?: number;
  public_download_expire_seconds?: number;
  mirror_bandwidth_limit_bps?: number;
  mirror_retry_count?: number;
}

export interface ObjectStorageHealthRead {
  ok: boolean;
  summary: string;
  details: Record<string, unknown>;
}

function getHeaders() {
  const token = getAdminToken();
  return {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };
}

async function requestJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      ...getHeaders(),
      ...(init?.headers || {}),
    },
  });
  if (response.ok) {
    return response.json() as Promise<T>;
  }
  let detail = `Request failed: ${response.status}`;
  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string" && payload.detail.trim()) {
      detail = payload.detail;
    }
  } catch {
    // noop
  }
  throw new Error(detail);
}

export function getObjectStorageConfig(): Promise<ObjectStorageConfigRead> {
  return requestJson<ObjectStorageConfigRead>("/api/v1/admin/object-storage/config");
}

export function updateObjectStorageConfig(data: ObjectStorageConfigUpdate): Promise<ObjectStorageConfigRead> {
  return requestJson<ObjectStorageConfigRead>("/api/v1/admin/object-storage/config", {
    method: "PUT",
    body: JSON.stringify(data),
  });
}

export function testObjectStorageConfig(data: ObjectStorageConfigUpdate): Promise<ObjectStorageHealthRead> {
  return requestJson<ObjectStorageHealthRead>("/api/v1/admin/object-storage/config/test", {
    method: "POST",
    body: JSON.stringify(data),
  });
}
