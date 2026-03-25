import type { ApiClientConfig, BodyType } from "../types";
import { ApiError, normalizeErrorMessage } from "../errors";

interface FetchOptions {
  method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
  headers?: Record<string, string>;
  body?: BodyType<unknown>;
  params?: Record<string, string>;
  signal?: AbortSignal;
}

export function createCustomFetch(config: ApiClientConfig) {
  const baseUrl = (config.baseUrl ?? "").replace(/\/+$/, "");

  const customFetch = async <T>(
    url: string,
    options: FetchOptions,
  ): Promise<T> => {
    let targetUrl = `${baseUrl}${url}`;
    if (options.params) {
      const searchParams = new URLSearchParams(
        Object.entries(options.params).filter(
          ([, v]) => v !== undefined && v !== null,
        ),
      );
      const qs = searchParams.toString();
      if (qs) targetUrl += `?${qs}`;
    }

    const isFormData =
      typeof FormData !== "undefined" && options.body instanceof FormData;
    const serializedBody: BodyInit | undefined = options.body
      ? isFormData
        ? (options.body as FormData)
        : typeof options.body === "string"
          ? options.body
          : JSON.stringify(options.body)
      : undefined;

    const response = await fetch(targetUrl, {
      method: options.method,
      headers: {
        Accept: "application/json",
        ...(!isFormData && options.body
          ? { "Content-Type": "application/json" }
          : {}),
        ...options.headers,
      },
      body: serializedBody,
      signal: options.signal,
    });

    if (!response.ok) {
      let message = `Request failed with status ${response.status}`;
      try {
        const payload = (await response.clone().json()) as {
          detail?: unknown;
          message?: unknown;
        };
        const detailMessage = normalizeErrorMessage(payload.detail);
        if (detailMessage) {
          message = detailMessage;
        } else if (
          typeof payload.message === "string" &&
          payload.message.trim()
        ) {
          message = payload.message;
        }
      } catch {
        try {
          const text = await response.text();
          if (text.trim()) {
            message = text.trim();
          }
        } catch {
          // Keep the default status message.
        }
      }

      if (response.status === 401) {
        config.onAuthError?.();
      }

      throw new ApiError(message, response.status);
    }

    if (response.status === 204) {
      return undefined as T;
    }

    const data = await response.json();

    return {
      data,
      status: response.status,
      headers: response.headers,
    } as T;
  };

  return customFetch;
}
