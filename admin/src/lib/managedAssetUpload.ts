import { getAdminToken } from "@/lib/storage";

export interface UploadedAssetRead {
  id: string;
  file_name: string;
  resource_key: string;
  visibility: "internal" | "public";
  scope: "system" | "user";
  category: string;
  note?: string | null;
  storage_path: string;
  internal_url: string;
  public_url?: string | null;
  mime_type?: string | null;
  byte_size?: number | null;
  sha256?: string | null;
}

type AssetUploadPlanRead = {
  mode: "local" | "oss" | "existing";
  asset_id?: string | null;
  resource_key?: string | null;
  upload_url?: string | null;
  upload_method?: "PUT" | null;
  upload_headers?: Record<string, string>;
  asset?: UploadedAssetRead | null;
};

export interface ManagedAssetUploadInput {
  file: File;
  visibility: "internal" | "public";
  scope: "system" | "user";
  category: string;
  note?: string;
}

function getAuthHeaders(contentType = "application/json") {
  const token = getAdminToken();
  const headers: Record<string, string> = {};
  if (contentType) {
    headers["Content-Type"] = contentType;
  }
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }
  return headers;
}

async function parseApiResponse<T>(response: Response): Promise<T> {
  if (response.ok) {
    return response.json() as Promise<T>;
  }

  let detail = `Request failed: ${response.status}`;
  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string" && payload.detail.trim()) {
      detail = payload.detail;
    }
  } catch {
    // ignore malformed error payloads
  }
  throw new Error(detail);
}

async function sha256File(file: File): Promise<string> {
  const bytes = await file.arrayBuffer();
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return Array.from(new Uint8Array(digest))
    .map((value) => value.toString(16).padStart(2, "0"))
    .join("");
}

async function localUpload(input: ManagedAssetUploadInput): Promise<UploadedAssetRead> {
  const formData = new FormData();
  formData.append("file", input.file);
  formData.append("visibility", input.visibility);
  formData.append("scope", input.scope);
  formData.append("category", input.category);
  if (input.note?.trim()) {
    formData.append("note", input.note.trim());
  }

  const response = await fetch("/api/v1/admin/assets/", {
    method: "POST",
    headers: getAuthHeaders(""),
    body: formData,
  });
  return parseApiResponse<UploadedAssetRead>(response);
}

export async function uploadManagedAsset(input: ManagedAssetUploadInput): Promise<UploadedAssetRead> {
  const sha256 = await sha256File(input.file);
  const initResponse = await fetch("/api/v1/admin/assets/init-upload", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({
      file_name: input.file.name,
      byte_size: input.file.size,
      sha256,
      mime_type: input.file.type || undefined,
      visibility: input.visibility,
      scope: input.scope,
      category: input.category,
      note: input.note?.trim() || undefined,
    }),
  });
  const plan = await parseApiResponse<AssetUploadPlanRead>(initResponse);

  if (plan.mode === "existing" && plan.asset) {
    return plan.asset;
  }

  if (plan.mode === "local") {
    return localUpload(input);
  }

  if (plan.mode !== "oss" || !plan.asset_id || !plan.upload_url) {
    throw new Error("OSS 上传初始化失败");
  }

  const uploadResponse = await fetch(plan.upload_url, {
    method: plan.upload_method || "PUT",
    headers: {
      ...(plan.upload_headers || {}),
      ...(input.file.type ? { "Content-Type": input.file.type } : {}),
    },
    body: input.file,
  });
  if (!uploadResponse.ok) {
    throw new Error(`OSS 上传失败：${uploadResponse.status}`);
  }

  const completeResponse = await fetch("/api/v1/admin/assets/complete-upload", {
    method: "POST",
    headers: getAuthHeaders(),
    body: JSON.stringify({ asset_id: plan.asset_id }),
  });
  return parseApiResponse<UploadedAssetRead>(completeResponse);
}
