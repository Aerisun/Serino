import { getAdminToken } from "@/lib/storage";

export async function adminRequest<T>(path: string, init?: RequestInit): Promise<T> {
  const token = getAdminToken();
  if (!token) {
    throw new Error("未登录，无法执行管理操作");
  }

  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${token}`,
        ...(init?.headers ?? {}),
      },
    });
  } catch {
    throw new Error("请求失败，请检查网络连接或后端服务状态");
  }

  const payload = await response
    .json()
    .catch(() => null);
  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? payload.detail
        : undefined;
    throw new Error(typeof detail === "string" ? detail : "操作失败");
  }
  return payload as T;
}
