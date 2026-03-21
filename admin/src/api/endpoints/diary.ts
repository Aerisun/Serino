import client from "../client";
import type { ContentItem, ContentCreate, ContentUpdate, PaginatedResponse } from "@/types/models";

export interface ListParams {
  page?: number;
  page_size?: number;
  status?: string;
}

export async function listDiary(params?: ListParams): Promise<PaginatedResponse<ContentItem>> {
  const res = await client.get("/diary/", { params });
  return res.data;
}

export async function getDiary(id: string): Promise<ContentItem> {
  const res = await client.get(`/diary/${id}`);
  return res.data;
}

export async function createDiary(data: ContentCreate): Promise<ContentItem> {
  const res = await client.post("/diary/", data);
  return res.data;
}

export async function updateDiary(id: string, data: ContentUpdate): Promise<ContentItem> {
  const res = await client.put(`/diary/${id}`, data);
  return res.data;
}

export async function deleteDiary(id: string): Promise<void> {
  await client.delete(`/diary/${id}`);
}
