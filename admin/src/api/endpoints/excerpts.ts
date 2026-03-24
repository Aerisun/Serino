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

export async function listExcerpts(params?: ListParams): Promise<PaginatedResponse<ContentItem>> {
  const res = await client.get("/api/v1/admin/excerpts/", { params });
  return res.data;
}

export async function getExcerpt(id: string): Promise<ContentItem> {
  const res = await client.get(`/api/v1/admin/excerpts/${id}`);
  return res.data;
}

export async function createExcerpt(data: ContentCreate): Promise<ContentItem> {
  const res = await client.post("/api/v1/admin/excerpts/", data);
  return res.data;
}

export async function updateExcerpt(id: string, data: ContentUpdate): Promise<ContentItem> {
  const res = await client.put(`/api/v1/admin/excerpts/${id}`, data);
  return res.data;
}

export async function deleteExcerpt(id: string): Promise<void> {
  await client.delete(`/api/v1/admin/excerpts/${id}`);
}

export async function bulkDeleteExcerpts(ids: string[]): Promise<BulkActionResponse> {
  const res = await client.post("/api/v1/admin/excerpts/bulk-delete", { ids });
  return res.data;
}

export async function bulkStatusExcerpts(ids: string[], status: string): Promise<BulkActionResponse> {
  const res = await client.post("/api/v1/admin/excerpts/bulk-status", { ids, status });
  return res.data;
}
