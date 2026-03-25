import Axios, { type AxiosInstance, type Method } from "axios";
import type { ApiClientConfig, BodyType } from "../types";

type RequestOptions = Omit<RequestInit, "body" | "headers" | "method"> & {
  body?: BodyType<unknown>;
  headers?: HeadersInit;
  method?: Method;
};

function normalizeHeaders(
  headers?: HeadersInit,
): Record<string, string> | undefined {
  if (!headers) {
    return undefined;
  }

  if (headers instanceof Headers) {
    return Object.fromEntries(headers.entries());
  }

  if (Array.isArray(headers)) {
    return Object.fromEntries(headers);
  }

  return headers;
}

export function createCustomInstance(config: ApiClientConfig) {
  const instance = Axios.create({
    baseURL: config.baseUrl ?? "",
  });

  instance.interceptors.request.use((req) => {
    const token = config.getAuthToken?.();
    if (token) {
      req.headers.Authorization = `Bearer ${token}`;
    }
    return req;
  });

  instance.interceptors.response.use(
    (res) => res,
    (error) => {
      if (error.response?.status === 401) {
        config.onAuthError?.();
      }
      return Promise.reject(error);
    },
  );

  const customInstance = <T>(
    url: string,
    options: RequestOptions = {},
  ): Promise<T> => {
    const source = Axios.CancelToken.source();

    const { body, headers, method, signal } = options;
    const promise = instance({
      url,
      method,
      headers: normalizeHeaders(headers),
      data: body,
      signal: signal ?? undefined,
      cancelToken: source.token,
    }).then(
      ({ data, status, headers }) =>
        ({
          data,
          status,
          headers,
        }) as T,
    );

    // @ts-expect-error -- attach cancel for React Query
    promise.cancel = () => {
      source.cancel("Query was cancelled");
    };

    return promise;
  };

  return customInstance;
}

export function createAxiosInstance(config: ApiClientConfig): AxiosInstance {
  const instance = Axios.create({
    baseURL: config.baseUrl ?? "",
  });

  instance.interceptors.request.use((req) => {
    const token = config.getAuthToken?.();
    if (token) {
      req.headers.Authorization = `Bearer ${token}`;
    }
    return req;
  });

  instance.interceptors.response.use(
    (res) => res,
    (error) => {
      if (error.response?.status === 401) {
        config.onAuthError?.();
      }
      return Promise.reject(error);
    },
  );

  return instance;
}
