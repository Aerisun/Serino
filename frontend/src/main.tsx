import { createRoot } from "react-dom/client";
import App from "./App.tsx";
import "./shell.css";
import { initSentry } from "@serino/utils/sentry";
import { initPublicClient } from "@serino/api-client";
import { getInitialRuntimeConfigSnapshot } from "@/lib/runtime-config";

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

const initialRuntimeConfig = getInitialRuntimeConfigSnapshot();

const loadDeferredStyles = () => {
  void import("./fonts-late.css");
};

if (typeof window !== "undefined") {
  if ("requestIdleCallback" in window) {
    window.requestIdleCallback(loadDeferredStyles, { timeout: 1200 });
  } else {
    window.setTimeout(loadDeferredStyles, 240);
  }
}

void clearDevelopmentPwaState().finally(() => {
  createRoot(document.getElementById("root")!).render(
    <App initialRuntimeConfig={initialRuntimeConfig} />,
  );
});

declare const __AERISUN_API_BASE_URL__: string | undefined;
