import type { Method } from "axios";
import { createCustomInstance } from "./custom-instance";
import type { ApiClientConfig, BodyType } from "../types";

export type MutatorRequestOptions = Omit<RequestInit, "body" | "headers" | "method"> & {
  body?: BodyType<unknown>;
  headers?: HeadersInit;
  method?: Method;
};

export function createDeferredMutator(clientLabel: string) {
  let instance: ReturnType<typeof createCustomInstance> | null = null;

  return {
    init(config: ApiClientConfig) {
      instance = createCustomInstance(config);
    },
    customInstance<T>(url: string, options: MutatorRequestOptions = {}): Promise<T> {
      if (!instance) {
        throw new Error(
          `${clientLabel} API client not initialized. Call the corresponding init function before using generated API hooks.`,
        );
      }
      return instance<T>(url, options);
    },
  };
}
