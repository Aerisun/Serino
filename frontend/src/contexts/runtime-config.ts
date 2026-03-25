import { createContext, useContext } from "react";
import { API_BASE_URL, ApiError } from "@/lib/api";
import type { RuntimeConfigSnapshot } from "@/lib/runtime-config";

interface RuntimeConfigContextValue {
  config: RuntimeConfigSnapshot;
}

export const RuntimeConfigContext = createContext<RuntimeConfigContextValue | null>(null);

export function describeRuntimeConfigError(error: Error | null) {
  if (!error) {
    return "站点配置未加载";
  }

  if (error instanceof ApiError) {
    return `接口请求失败（HTTP ${error.status}）`;
  }

  if (error.message === "Failed to fetch") {
    return `无法访问接口 ${API_BASE_URL || "/api"}`;
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
