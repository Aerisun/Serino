import { createDeferredMutator, type MutatorRequestOptions } from "./deferred-instance";
import type { ApiClientConfig } from "../types";

const adminMutator = createDeferredMutator("Admin");

export function initAdminClient(config: ApiClientConfig) {
  adminMutator.init(config);
}

export const customInstance = <T>(
  url: string,
  options: MutatorRequestOptions = {},
): Promise<T> => adminMutator.customInstance<T>(url, options);

export type ErrorType<Error> = import("axios").AxiosError<Error>;
export type BodyType<BodyData> = BodyData;
