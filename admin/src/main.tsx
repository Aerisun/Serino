import { createRoot } from "react-dom/client";
import App from "./App";
import "./index.css";
import { initSentry } from "@serino/utils/sentry";
import { migrateAdminThemePreference } from "@/lib/storage";

initSentry();
migrateAdminThemePreference();

createRoot(document.getElementById("root")!).render(<App />);
