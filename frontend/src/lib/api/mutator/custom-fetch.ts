const envApiBaseUrl = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/+$/, "");

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

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

  const response = await fetch(targetUrl, {
    method: options.method,
    headers: {
      Accept: "application/json",
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
    signal: options.signal,
  });

  if (!response.ok) {
    throw new ApiError(
      `Request failed with status ${response.status}`,
      response.status,
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json();
};

export default customFetch;

export type ErrorType<Error> = ApiError;
export type BodyType<BodyData> = BodyData;
