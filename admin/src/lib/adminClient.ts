import { clearAdminToken, getAdminToken } from "@/lib/storage";

const adminBasePath =
  typeof __AERISUN_ADMIN_BASE_PATH__ === "string"
    ? __AERISUN_ADMIN_BASE_PATH__
    : "/admin/";
const loginPath = new URL("login", window.location.origin + adminBasePath).pathname;

let adminClientInitPromise: Promise<void> | null = null;

export function ensureAdminClientInitialized() {
  if (!adminClientInitPromise) {
    adminClientInitPromise = import("@serino/api-client")
      .then(({ initAdminClient }) => {
        initAdminClient({
          getAuthToken: getAdminToken,
          onAuthError: () => {
            clearAdminToken();
            window.location.assign(loginPath);
          },
        });
      })
      .catch((error) => {
        adminClientInitPromise = null;
        throw error;
      });
  }

  return adminClientInitPromise;
}
