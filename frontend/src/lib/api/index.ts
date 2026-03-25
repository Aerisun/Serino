const envApiBasePath =
  typeof __AERISUN_API_BASE_PATH__ === "string" ? __AERISUN_API_BASE_PATH__ : "/api";
const envApiBaseUrl =
  (typeof __AERISUN_API_BASE_URL__ === "string" ? __AERISUN_API_BASE_URL__ : "").replace(
    /\/+$/,
    "",
  );

// Use same-origin API paths by default so the Vite dev proxy can forward
// requests to the backend without tripping browser CORS enforcement.
// Set VITE_API_BASE_URL only when you explicitly want a different origin.
export const API_BASE_PATH = envApiBasePath.replace(/\/+$/, "") || "/api";
export const API_BASE_URL = envApiBaseUrl;

export { ApiError } from "@serino/api-client";

export * from "./utils";
