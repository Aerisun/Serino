import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./index.css";
import { initSentry } from "@serino/utils";
import { initPublicClient } from "@serino/api-client";

const envApiBaseUrl =
  (typeof __AERISUN_API_BASE_URL__ === "string" ? __AERISUN_API_BASE_URL__ : "").replace(
    /\/+$/,
    "",
  );

async function clearDevelopmentPwaState() {
  if (!import.meta.env.DEV || typeof window === "undefined" || !("serviceWorker" in navigator)) {
    return;
  }

  const registrations = await navigator.serviceWorker.getRegistrations();
  await Promise.all(registrations.map((registration) => registration.unregister()));

  if ("caches" in window) {
    const cacheKeys = await caches.keys();
    await Promise.all(cacheKeys.map((key) => caches.delete(key)));
  }
}

initPublicClient({ baseUrl: envApiBaseUrl });
initSentry();

void clearDevelopmentPwaState().finally(() => {
  createRoot(document.getElementById("root")!).render(<App />);
});

declare const __AERISUN_API_BASE_URL__: string | undefined;
