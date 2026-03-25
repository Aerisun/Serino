import { createAxiosInstance } from "@serino/api-client";

const adminBasePath =
  typeof __AERISUN_ADMIN_BASE_PATH__ === "string"
    ? __AERISUN_ADMIN_BASE_PATH__
    : "/admin/";
const loginPath = new URL("login", window.location.origin + adminBasePath).pathname;

const client = createAxiosInstance({
  getAuthToken: () => localStorage.getItem("admin_token"),
  onAuthError: () => {
    localStorage.removeItem("admin_token");
    window.location.assign(loginPath);
  },
});

export default client;
