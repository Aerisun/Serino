import { createI18nRuntime } from "@serino/utils";
import { frontendTranslations, type FrontendLang } from "./translations";

export const FRONTEND_LANGUAGE_STORAGE_KEY = "aerisun-frontend-lang";

export function resolveInitialLang(): FrontendLang {
  if (typeof navigator !== "undefined" && navigator.language.toLowerCase().startsWith("en")) {
    return "en";
  }
  return "zh";
}

export function getFrontendLang(): FrontendLang {
  if (typeof window !== "undefined") {
    try {
      const stored = localStorage.getItem(FRONTEND_LANGUAGE_STORAGE_KEY);
      if (stored === "zh" || stored === "en") {
        return stored;
      }
    } catch {
      // Ignore storage access failures and keep the browser fallback.
    }
  }
  return resolveInitialLang();
}

export function translateFrontendText(
  key: string,
  values?: Record<string, string | number>,
  fallback?: string,
) {
  const lang = getFrontendLang();
  const template = frontendTranslations[lang][key] ?? fallback ?? key;
  if (!values) {
    return template;
  }
  return template.replace(/\{(\w+)\}/g, (_, valueKey) => String(values[valueKey] ?? `{${valueKey}}`));
}

const runtime = createI18nRuntime<FrontendLang>({
  storageKey: FRONTEND_LANGUAGE_STORAGE_KEY,
  defaultLang: "zh",
  translations: frontendTranslations,
  resolveInitialLang,
});

export const FrontendLanguageProvider = runtime.Provider;
export const useFrontendI18n = runtime.useI18n;
export type { FrontendLang };
