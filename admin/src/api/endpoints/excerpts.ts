import client from "../client";
import type { ContentItem, ContentCreate, ContentUpdate, PaginatedResponse } from "@/types/models";

export interface ListParams {
  page?: number;
  page_size?: number;
  status?: string;
}

export async function listExcerpts(params?: ListParams): Promise<PaginatedResponse<ContentItem>> {
  const res = await client.get("/excerpts/", { params });
  return res.data;
}

export async function getExcerpt(id: string): Promise<ContentItem> {
  const res = await client.get(`/excerpts/${id}`);
  return res.data;
}

export async function createExcerpt(data: ContentCreate): Promise<ContentItem> {
  const res = await client.post("/excerpts/", data);
  return res.data;
}

export async function updateExcerpt(id: string, data: ContentUpdate): Promise<ContentItem> {
  const res = await client.put(`/excerpts/${id}`, data);
  return res.data;
}

export async function deleteExcerpt(id: string): Promise<void> {
  await client.delete(`/excerpts/${id}`);
}
