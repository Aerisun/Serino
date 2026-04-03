import { createDeferredMutator, type MutatorRequestOptions } from "./deferred-instance";
import type { ApiClientConfig } from "../types";

const publicMutator = createDeferredMutator("Public");

export function initPublicClient(config: ApiClientConfig) {
  publicMutator.init(config);
}

export const customInstance = <T>(
  url: string,
  options: MutatorRequestOptions = {},
): Promise<T> => publicMutator.customInstance<T>(url, options);

export type ErrorType<Error> = import("axios").AxiosError<Error>;
export type BodyType<BodyData> = BodyData;
