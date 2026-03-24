import client from "../client";
import type { ContentItem, ContentCreate, ContentUpdate, PaginatedResponse, BulkActionResponse } from "@/types/models";

export interface ListParams {
  page?: number;
  page_size?: number;
  status?: string;
  search?: string;
  sort_by?: string;
  sort_order?: string;
}

export async function listDiary(params?: ListParams): Promise<PaginatedResponse<ContentItem>> {
  const res = await client.get("/api/v1/admin/diary/", { params });
  return res.data;
}

export async function getDiary(id: string): Promise<ContentItem> {
  const res = await client.get(`/api/v1/admin/diary/${id}`);
  return res.data;
}

export async function createDiary(data: ContentCreate): Promise<ContentItem> {
  const res = await client.post("/api/v1/admin/diary/", data);
  return res.data;
}

export async function updateDiary(id: string, data: ContentUpdate): Promise<ContentItem> {
  const res = await client.put(`/api/v1/admin/diary/${id}`, data);
  return res.data;
}

export async function deleteDiary(id: string): Promise<void> {
  await client.delete(`/api/v1/admin/diary/${id}`);
}

export async function bulkDeleteDiary(ids: string[]): Promise<BulkActionResponse> {
  const res = await client.post("/api/v1/admin/diary/bulk-delete", { ids });
  return res.data;
}

export async function bulkStatusDiary(ids: string[], status: string): Promise<BulkActionResponse> {
  const res = await client.post("/api/v1/admin/diary/bulk-status", { ids, status });
  return res.data;
}
