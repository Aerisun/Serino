const envApiBaseUrl =
  (typeof __AERISUN_API_BASE_URL__ === "string" ? __AERISUN_API_BASE_URL__ : "").replace(
    /\/+$/,
    "",
  );

// Use same-origin API paths by default so the Vite dev proxy can forward
// requests to the backend without tripping browser CORS enforcement.
// Set VITE_API_BASE_URL only when you explicitly want a different origin.
export const API_BASE_URL = envApiBaseUrl;

export { ApiError } from "@serino/api-client";

export const buildApiUrl = (path: string) => {
  if (/^https?:\/\//.test(path)) return path;
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${API_BASE_URL}${normalizedPath}`;
};

export * from "./utils";
