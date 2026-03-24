import client from "../client";
import type { ContentItem, ContentCreate, ContentUpdate, PaginatedResponse, BulkActionResponse } from "@/types/models";

export interface ListParams {
  page?: number;
  page_size?: number;
  status?: string;
  tag?: string;
  search?: string;
  sort_by?: string;
  sort_order?: string;
}

export async function listPosts(params?: ListParams): Promise<PaginatedResponse<ContentItem>> {
  const res = await client.get("/api/v1/admin/posts/", { params });
  return res.data;
}

export async function getPost(id: string): Promise<ContentItem> {
  const res = await client.get(`/api/v1/admin/posts/${id}`);
  return res.data;
}

export async function createPost(data: ContentCreate): Promise<ContentItem> {
  const res = await client.post("/api/v1/admin/posts/", data);
  return res.data;
}

export async function updatePost(id: string, data: ContentUpdate): Promise<ContentItem> {
  const res = await client.put(`/api/v1/admin/posts/${id}`, data);
  return res.data;
}

export async function deletePost(id: string): Promise<void> {
  await client.delete(`/api/v1/admin/posts/${id}`);
}

export async function bulkDeletePosts(ids: string[]): Promise<BulkActionResponse> {
  const res = await client.post("/api/v1/admin/posts/bulk-delete", { ids });
  return res.data;
}

export async function bulkStatusPosts(ids: string[], status: string): Promise<BulkActionResponse> {
  const res = await client.post("/api/v1/admin/posts/bulk-status", { ids, status });
  return res.data;
}
