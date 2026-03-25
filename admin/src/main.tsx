import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import { initSentry } from "@serino/utils";
import { initAdminClient } from "@serino/api-client";

initSentry();

const adminBasePath =
  typeof __AERISUN_ADMIN_BASE_PATH__ === "string"
    ? __AERISUN_ADMIN_BASE_PATH__
    : "/admin/";
const loginPath = new URL("login", window.location.origin + adminBasePath).pathname;

initAdminClient({
  getAuthToken: () => localStorage.getItem("admin_token"),
  onAuthError: () => {
    localStorage.removeItem("admin_token");
    window.location.assign(loginPath);
  },
});

createRoot(document.getElementById("root")!).render(<App />);
