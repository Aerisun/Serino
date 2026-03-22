import client from "../client";
import type {
  ApiKey,
  ApiKeyCreate,
  ApiKeyUpdate,
  ApiKeyCreateResponse,
  AuditLog,
  BackupSnapshot,
  EnhancedDashboardStats,
  PaginatedResponse,
} from "@/types/models";

// --- Dashboard ---
export async function getDashboardStats(): Promise<EnhancedDashboardStats> {
  const res = await client.get("/system/dashboard/stats");
  return res.data;
}

// --- API Keys ---
export async function listApiKeys(): Promise<ApiKey[]> {
  const res = await client.get("/system/api-keys");
  return res.data;
}

export async function createApiKey(data: ApiKeyCreate): Promise<ApiKeyCreateResponse> {
  const res = await client.post("/system/api-keys", data);
  return res.data;
}

export async function updateApiKey(id: string, data: ApiKeyUpdate): Promise<ApiKey> {
  const res = await client.put(`/system/api-keys/${id}`, data);
  return res.data;
}

export async function deleteApiKey(id: string): Promise<void> {
  await client.delete(`/system/api-keys/${id}`);
}

// --- Audit Logs ---
export async function listAuditLogs(params?: { page?: number; page_size?: number; action?: string; date_from?: string; date_to?: string }): Promise<PaginatedResponse<AuditLog>> {
  const res = await client.get("/system/audit-logs", { params });
  return res.data;
}

// --- Backups ---
export async function listBackups(): Promise<BackupSnapshot[]> {
  const res = await client.get("/system/backups");
  return res.data;
}

export async function triggerBackup(): Promise<BackupSnapshot> {
  const res = await client.post("/system/backups");
  return res.data;
}

export async function restoreBackup(id: string): Promise<BackupSnapshot> {
  const res = await client.post(`/system/backups/${id}/restore`);
  return res.data;
}

// --- System Info ---
export interface SystemInfo {
  version: string;
  python_version: string;
  db_size_bytes: number;
  media_dir_size_bytes: number;
  uptime_seconds: number;
  environment: string;
}

export async function getSystemInfo(): Promise<SystemInfo> {
  const res = await client.get<SystemInfo>("/system/info");
  return res.data;
}
