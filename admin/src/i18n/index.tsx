import { createI18nRuntime } from "@serino/utils";
import { translations, type Lang } from "./translations";

const runtime = createI18nRuntime<Lang>({
  storageKey: "aerisun-admin-lang",
  defaultLang: "zh",
  translations,
});

export const LanguageProvider = runtime.Provider;
export const useI18n = runtime.useI18n;

export type { Lang };
