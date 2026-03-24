const envApiBaseUrl =
  (typeof __AERISUN_API_BASE_URL__ === "string" ? __AERISUN_API_BASE_URL__ : "").replace(
    /\/+$/,
    "",
  );

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

const normalizeErrorMessage = (detail: unknown): string | null => {
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== "object") {
          return null;
        }
        const record = item as { msg?: unknown; loc?: unknown };
        const msg = typeof record.msg === "string" ? record.msg.trim() : "";
        const loc = Array.isArray(record.loc)
          ? record.loc
            .filter((value): value is string | number => typeof value === "string" || typeof value === "number")
            .join(".")
          : "";
        if (!msg) {
          return null;
        }
        return loc ? `${loc}: ${msg}` : msg;
      })
      .filter((item): item is string => Boolean(item));

    return parts.length ? parts.join("; ") : null;
  }

  return null;
};

export const customFetch = async <T>(
  url: string,
  options: {
    method: "GET" | "POST" | "PUT" | "DELETE" | "PATCH";
    headers?: Record<string, string>;
    body?: BodyType<unknown>;
    params?: Record<string, string>;
    signal?: AbortSignal;
  },
): Promise<T> => {
  let targetUrl = `${envApiBaseUrl}${url}`;
  if (options.params) {
    const searchParams = new URLSearchParams(
      Object.entries(options.params).filter(
        ([, v]) => v !== undefined && v !== null,
      ),
    );
    const qs = searchParams.toString();
    if (qs) targetUrl += `?${qs}`;
  }

  const isFormData = typeof FormData !== "undefined" && options.body instanceof FormData;
  const serializedBody = options.body
    ? (
      isFormData
        ? options.body
        : typeof options.body === "string"
          ? options.body
          : JSON.stringify(options.body)
    )
    : undefined;

  const response = await fetch(targetUrl, {
    method: options.method,
    headers: {
      Accept: "application/json",
      ...(!isFormData && options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
    body: serializedBody,
    signal: options.signal,
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}`;
    try {
      const payload = await response.clone().json() as { detail?: unknown; message?: unknown };
      const detailMessage = normalizeErrorMessage(payload.detail);
      if (detailMessage) {
        message = detailMessage;
      } else if (typeof payload.message === "string" && payload.message.trim()) {
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

export default customFetch;

export type ErrorType<Error> = ApiError;
export type BodyType<BodyData> = BodyData;
