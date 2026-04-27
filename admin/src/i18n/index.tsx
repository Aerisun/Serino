import {
  createContext,
  startTransition,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { zhTranslations } from "./translations-zh";
import type { Lang, TranslationDict } from "./translations";

type TemplateValues = Record<string, string | number>;

interface I18nRuntimeValue {
  lang: Lang;
  setLang: (lang: Lang) => void;
  t: (key: string, values?: TemplateValues, fallback?: string) => string;
}

const STORAGE_KEY = "aerisun-admin-lang";
const DEFAULT_LANG: Lang = "zh";
const RuntimeContext = createContext<I18nRuntimeValue | null>(null);

let enTranslationsPromise: Promise<TranslationDict> | null = null;

function formatTemplate(template: string, values?: TemplateValues) {
  if (!values) {
    return template;
  }
  return template.replace(/\{(\w+)\}/g, (_, key) => String(values[key] ?? `{${key}}`));
}

function resolveInitialLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === "zh" || stored === "en") {
      return stored;
    }
  } catch {
    // Ignore storage access failures and keep the default locale.
  }
  return DEFAULT_LANG;
}

function persistLang(nextLang: Lang) {
  try {
    localStorage.setItem(STORAGE_KEY, nextLang);
  } catch {
    // Ignore storage access failures and keep the in-memory locale.
  }
}

function loadTranslations(lang: Lang) {
  if (lang === "zh") {
    return Promise.resolve(zhTranslations);
  }
  if (!enTranslationsPromise) {
    enTranslationsPromise = import("./translations-en").then((module) => module.enTranslations);
  }
  return enTranslationsPromise;
}

export function LanguageProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(resolveInitialLang);
  const [translationsByLang, setTranslationsByLang] = useState<Record<Lang, TranslationDict | null>>({
    zh: zhTranslations,
    en: null,
  });
  const [isReady, setIsReady] = useState(() => lang === "zh");

  useEffect(() => {
    if (translationsByLang[lang]) {
      setIsReady(true);
      return;
    }

    let cancelled = false;
    setIsReady(false);
    void loadTranslations(lang)
      .then((translations) => {
        if (cancelled) {
          return;
        }
        setTranslationsByLang((current) => (
          current[lang] ? current : { ...current, [lang]: translations }
        ));
        setIsReady(true);
      })
      .catch(() => {
        if (!cancelled) {
          persistLang(DEFAULT_LANG);
          startTransition(() => {
            setLangState(DEFAULT_LANG);
          });
          setIsReady(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [lang, translationsByLang]);

  const setLang = useCallback((nextLang: Lang) => {
    persistLang(nextLang);

    if (nextLang === lang) {
      return;
    }

    const cachedTranslations = translationsByLang[nextLang];
    if (cachedTranslations) {
      startTransition(() => {
        setLangState(nextLang);
      });
      return;
    }

    void loadTranslations(nextLang).then((translations) => {
      setTranslationsByLang((current) => (
        current[nextLang] ? current : { ...current, [nextLang]: translations }
      ));
      startTransition(() => {
        setLangState(nextLang);
      });
    }).catch(() => {
      persistLang(lang);
    });
  }, [lang, translationsByLang]);

  const activeTranslations = translationsByLang[lang] ?? zhTranslations;

  const t = useCallback(
    (key: string, values?: TemplateValues, fallback?: string) => {
      const template = activeTranslations[key] ?? fallback ?? key;
      return formatTemplate(template, values);
    },
    [activeTranslations],
  );

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);

  if (!isReady) {
    return (
      <div className="flex h-dvh min-h-screen items-center justify-center text-muted-foreground">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-current border-t-transparent" />
      </div>
    );
  }

  return <RuntimeContext.Provider value={value}>{children}</RuntimeContext.Provider>;
}

export function useI18n() {
  const ctx = useContext(RuntimeContext);
  if (!ctx) {
    throw new Error("i18n hooks must be used within the matching provider");
  }
  return ctx;
}

export type { Lang };
