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

export async function listThoughts(params?: ListParams): Promise<PaginatedResponse<ContentItem>> {
  const res = await client.get("/thoughts/", { params });
  return res.data;
}

export async function getThought(id: string): Promise<ContentItem> {
  const res = await client.get(`/thoughts/${id}`);
  return res.data;
}

export async function createThought(data: ContentCreate): Promise<ContentItem> {
  const res = await client.post("/thoughts/", data);
  return res.data;
}

export async function updateThought(id: string, data: ContentUpdate): Promise<ContentItem> {
  const res = await client.put(`/thoughts/${id}`, data);
  return res.data;
}

export async function deleteThought(id: string): Promise<void> {
  await client.delete(`/thoughts/${id}`);
}

export async function bulkDeleteThoughts(ids: string[]): Promise<BulkActionResponse> {
  const res = await client.post("/thoughts/bulk-delete", { ids });
  return res.data;
}

export async function bulkStatusThoughts(ids: string[], status: string): Promise<BulkActionResponse> {
  const res = await client.post("/thoughts/bulk-status", { ids, status });
  return res.data;
}
