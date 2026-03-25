import { createCustomInstance } from "@serino/api-client";
import type { Method } from "axios";

const adminBasePath =
  typeof __AERISUN_ADMIN_BASE_PATH__ === "string"
    ? __AERISUN_ADMIN_BASE_PATH__
    : "/admin/";
const loginPath = new URL("login", window.location.origin + adminBasePath).pathname;

const instance = createCustomInstance({
  getAuthToken: () => localStorage.getItem("admin_token"),
  onAuthError: () => {
    localStorage.removeItem("admin_token");
    window.location.assign(loginPath);
  },
});

type RequestOptions = Omit<RequestInit, "body" | "headers" | "method"> & {
  body?: BodyType<unknown>;
  headers?: HeadersInit;
  method?: Method;
};

export const customInstance = <T>(url: string, options: RequestOptions = {}): Promise<T> => {
  return instance<T>(url, options);
};

export default customInstance;

export type ErrorType<Error> = import("axios").AxiosError<Error>;
export type BodyType<BodyData> = BodyData;
