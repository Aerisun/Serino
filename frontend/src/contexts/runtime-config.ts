import { createContext, useContext } from "react";
import { API_BASE_PATH, API_BASE_URL, ApiError } from "@/lib/api";
import { translateFrontendText } from "@/i18n";
import type { RuntimeConfigSnapshot } from "@/lib/runtime-config";

interface RuntimeConfigContextValue {
  config: RuntimeConfigSnapshot;
}

export const RuntimeConfigContext = createContext<RuntimeConfigContextValue | null>(null);

export function describeRuntimeConfigError(error: Error | null) {
  if (!error) {
    return translateFrontendText("runtime.notLoaded");
  }

  if (error instanceof ApiError) {
    return translateFrontendText("runtime.apiFailed", { status: error.status });
  }

  if (error.message === "Failed to fetch") {
    return translateFrontendText("runtime.unreachable", {
      target: API_BASE_URL || API_BASE_PATH,
    });
  }

  return error.message;
}

function useRuntimeConfig() {
  const ctx = useContext(RuntimeConfigContext);
  if (!ctx) {
    throw new Error("runtime config hooks must be used within RuntimeConfigProvider");
  }
  return ctx.config;
}

export function useSiteConfig() {
  return useRuntimeConfig().site;
}

export function usePageConfig() {
  return useRuntimeConfig().pages;
}

export function useFeatureFlags() {
  return useRuntimeConfig().site.featureFlags;
}
