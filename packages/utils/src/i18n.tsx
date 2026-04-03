import {
  createContext,
  useCallback,
  useContext,
  useState,
  type ReactNode,
} from "react";

type TemplateValues = Record<string, string | number>;

function formatTemplate(template: string, values?: TemplateValues) {
  if (!values) {
    return template;
  }
  return template.replace(/\{(\w+)\}/g, (_, key) => String(values[key] ?? `{${key}}`));
}

interface CreateI18nRuntimeOptions<Lang extends string> {
  storageKey: string;
  defaultLang: Lang;
  translations: Record<Lang, Record<string, string>>;
  resolveInitialLang?: () => Lang;
}

interface I18nRuntimeValue<Lang extends string> {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, values?: TemplateValues, fallback?: string) => string;
}

export function createI18nRuntime<Lang extends string>({
  storageKey,
  defaultLang,
  translations,
  resolveInitialLang,
}: CreateI18nRuntimeOptions<Lang>) {
  const RuntimeContext = createContext<I18nRuntimeValue<Lang> | null>(null);
  const supportedLangs = new Set(Object.keys(translations) as Lang[]);

  const getInitialLang = () => {
    try {
      const stored = localStorage.getItem(storageKey);
      if (stored && supportedLangs.has(stored as Lang)) {
        return stored as Lang;
      }
    } catch {
      // Ignore storage access failures and keep falling back.
    }

    try {
      const resolved = resolveInitialLang?.();
      if (resolved && supportedLangs.has(resolved)) {
        return resolved;
      }
    } catch {
      // Ignore runtime resolution failures and keep the default locale.
    }

    return defaultLang;
  };

  function Provider({ children }: { children: ReactNode }) {
    const [lang, setLangState] = useState<Lang>(getInitialLang);

    const setLang = useCallback((nextLang: Lang) => {
      setLangState(nextLang);
      try {
        localStorage.setItem(storageKey, nextLang);
      } catch {
        // Ignore storage access failures and keep the in-memory locale.
      }
    }, []);

    const t = useCallback(
      (key: string, values?: TemplateValues, fallback?: string) => {
        const template = translations[lang][key] ?? fallback ?? key;
        return formatTemplate(template, values);
      },
      [lang],
    );

    return <RuntimeContext.Provider value={{ lang, setLang, t }}>{children}</RuntimeContext.Provider>;
  }

  function useI18n() {
    const ctx = useContext(RuntimeContext);
    if (!ctx) {
      throw new Error("i18n hooks must be used within the matching provider");
    }
    return ctx;
  }

  return {
    Provider,
    useI18n,
  };
}
