import { createCustomFetch } from "./custom-fetch";
import type { ApiClientConfig } from "../types";

interface FetchOptions {
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  headers?: Record<string, string>;
  body?: BodyType<unknown>;
  params?: Record<string, string>;
  signal?: AbortSignal;
}

let instance: ReturnType<typeof createCustomFetch> | null = null;

export function initPublicClient(config: ApiClientConfig) {
  instance = createCustomFetch(config);
}

export const customFetch = async <T>(
  url: string,
  options: FetchOptions,
): Promise<T> => {
  if (!instance) {
    throw new Error(
      "Public API client not initialized. Call initPublicClient() before using any public API functions.",
    );
  }
  return instance<T>(url, options);
};
export type ErrorType<Error> = import("../errors").ApiError;
export type BodyType<BodyData> = BodyData;
