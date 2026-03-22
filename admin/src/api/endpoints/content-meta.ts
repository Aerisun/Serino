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
  const res = await client.get<TagInfo[]>("/content/tags");
  return res.data;
}

export async function listCategories(): Promise<CategoryInfo[]> {
  const res = await client.get<CategoryInfo[]>("/content/categories");
  return res.data;
}
