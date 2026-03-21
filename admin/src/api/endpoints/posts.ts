import client from "../client";
import type { ContentItem, ContentCreate, ContentUpdate, PaginatedResponse } from "@/types/models";

export interface ListParams {
  page?: number;
  page_size?: number;
  status?: string;
  tag?: string;
}

export async function listPosts(params?: ListParams): Promise<PaginatedResponse<ContentItem>> {
  const res = await client.get("/posts/", { params });
  return res.data;
}

export async function getPost(id: string): Promise<ContentItem> {
  const res = await client.get(`/posts/${id}`);
  return res.data;
}

export async function createPost(data: ContentCreate): Promise<ContentItem> {
  const res = await client.post("/posts/", data);
  return res.data;
}

export async function updatePost(id: string, data: ContentUpdate): Promise<ContentItem> {
  const res = await client.put(`/posts/${id}`, data);
  return res.data;
}

export async function deletePost(id: string): Promise<void> {
  await client.delete(`/posts/${id}`);
}
