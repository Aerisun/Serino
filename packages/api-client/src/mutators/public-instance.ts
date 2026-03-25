import type { Method } from "axios";
import { createCustomInstance } from "./custom-instance";
import type { ApiClientConfig } from "../types";

type RequestOptions = Omit<RequestInit, "body" | "headers" | "method"> & {
  body?: BodyType<unknown>;
  headers?: HeadersInit;
  method?: Method;
};

let instance: ReturnType<typeof createCustomInstance> | null = null;

export function initPublicClient(config: ApiClientConfig) {
  instance = createCustomInstance(config);
}

export const customInstance = <T>(
  url: string,
  options: RequestOptions = {},
): Promise<T> => {
  if (!instance) {
    throw new Error(
      "Public API client not initialized. Call initPublicClient() before using any public API hooks.",
    );
  }
  return instance<T>(url, options);
};

export type ErrorType<Error> = import("axios").AxiosError<Error>;
export type BodyType<BodyData> = BodyData;
