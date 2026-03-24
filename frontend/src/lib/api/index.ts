const envApiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

// Use same-origin API paths by default so the Vite dev proxy can forward
// requests to the backend without tripping browser CORS enforcement.
// Set VITE_API_BASE_URL only when you explicitly want a different origin.
export const API_BASE_URL = envApiBaseUrl;

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export const buildApiUrl = (path: string) => {
  if (/^https?:\/\//.test(path)) return path;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

export async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(buildApiUrl(path), {
    ...init,
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    throw new ApiError(`Request failed with status ${response.status}`, response.status);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}

export const apiClient = {
  get: <T>(path: string, init?: RequestInit) => requestJson<T>(path, { ...init, method: "GET" }),
  post: <T>(path: string, body?: unknown, init?: RequestInit) =>
    requestJson<T>(path, {
      ...init,
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(init?.headers ?? {}),
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
};

export * from "./utils";
