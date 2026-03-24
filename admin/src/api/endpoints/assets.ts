import client from "../client";
import type { Asset, PaginatedResponse } from "@/types/models";

export async function listAssets(params?: { page?: number; page_size?: number }): Promise<PaginatedResponse<Asset>> {
  const res = await client.get("/api/v1/admin/assets/", { params });
  return res.data;
}

export async function uploadAsset(file: File): Promise<Asset> {
  const form = new FormData();
  form.append("file", file);
  const res = await client.post("/api/v1/admin/assets/", form, {
    headers: { "Content-Type": "multipart/form-data" },
  });
  return res.data;
}

export async function deleteAsset(id: string): Promise<void> {
  await client.delete(`/api/v1/admin/assets/${id}`);
}
