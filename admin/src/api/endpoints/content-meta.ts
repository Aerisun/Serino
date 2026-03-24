import client from "../client";

export interface TagInfo {
  name: string;
  count: number;
}

export interface CategoryInfo {
  name: string;
  count: number;
}

export async function listTags(): Promise<TagInfo[]> {
  const res = await client.get<TagInfo[]>("/api/v1/admin/content/tags");
  return res.data;
}

export async function listCategories(): Promise<CategoryInfo[]> {
  const res = await client.get<CategoryInfo[]>("/api/v1/admin/content/categories");
  return res.data;
}
