import { createCustomFetch } from "@serino/api-client";

const envApiBaseUrl =
  (typeof __AERISUN_API_BASE_URL__ === "string" ? __AERISUN_API_BASE_URL__ : "").replace(
    /\/+$/,
    "",
  );

const instance = createCustomFetch({ baseUrl: envApiBaseUrl });

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
  return instance<T>(url, options);
};

export default customFetch;

export { ApiError } from "@serino/api-client";
export type ErrorType<Error> = import("@serino/api-client").ApiError;
export type BodyType<BodyData> = BodyData;
