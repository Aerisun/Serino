import Axios, { type AxiosRequestConfig, type Method } from "axios";

const loginPath = new URL("login", window.location.origin + import.meta.env.BASE_URL).pathname;

const AXIOS_INSTANCE = Axios.create({
  baseURL: "",
});

AXIOS_INSTANCE.interceptors.request.use((config) => {
  const token = localStorage.getItem("admin_token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

AXIOS_INSTANCE.interceptors.response.use(
  (res) => res,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem("admin_token");
      window.location.assign(loginPath);
    }
    return Promise.reject(error);
  },
);

type RequestOptions = Omit<RequestInit, "body" | "headers" | "method"> & {
  body?: BodyType<unknown>;
  headers?: HeadersInit;
  method?: Method;
};

function normalizeHeaders(headers?: HeadersInit): Record<string, string> | undefined {
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

export const customInstance = <T>(url: string, options: RequestOptions = {}): Promise<T> => {
  const source = Axios.CancelToken.source();

  const { body, headers, method, signal } = options;
  const promise = AXIOS_INSTANCE({
    url,
    method,
    headers: normalizeHeaders(headers),
    data: body,
    signal,
    cancelToken: source.token,
  }).then(({ data, status, headers }) => ({
    data,
    status,
    headers,
  } as T));

  // @ts-expect-error -- attach cancel for React Query
  promise.cancel = () => {
    source.cancel("Query was cancelled");
  };

  return promise;
};

export default customInstance;

export type ErrorType<Error> = import("axios").AxiosError<Error>;
export type BodyType<BodyData> = BodyData;
