import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useState,
  type ReactNode,
} from "react";

// ── Types ────────────────────────────────────────────────────────────

export type Theme = "light" | "dark" | "system";

export interface ThemeContextType {
  theme: Theme;
  setTheme: (theme: Theme) => void;
  resolvedTheme: "light" | "dark";
}

export interface ThemeProviderProps {
  children: ReactNode;
  storageKey?: string;
  applyDataAttribute?: boolean;
}

// ── Context ──────────────────────────────────────────────────────────

const ThemeContext = createContext<ThemeContextType | undefined>(undefined);

// ── Hook ─────────────────────────────────────────────────────────────

export const useTheme = () => {
  const ctx = useContext(ThemeContext);
  if (!ctx) throw new Error("useTheme must be used within ThemeProvider");
  return ctx;
};

// ── Helpers ──────────────────────────────────────────────────────────

const THEME_QUERY = "(prefers-color-scheme: dark)";

const getSystemTheme = (): "light" | "dark" =>
  window.matchMedia(THEME_QUERY).matches ? "dark" : "light";

const getStoredTheme = (storageKey: string): Theme => {
  if (typeof window === "undefined") return "system";

  const stored = window.localStorage.getItem(storageKey);
  if (stored === "light" || stored === "dark" || stored === "system") {
    return stored;
  }

  return "system";
};

export const getDomResolvedTheme = (): "light" | "dark" | null => {
  if (typeof document === "undefined") return null;

  const root = document.documentElement;
  if (root.classList.contains("dark")) return "dark";
  if (root.classList.contains("light")) return "light";
  return null;
};

const resolveTheme = (theme: Theme): "light" | "dark" =>
  theme === "system" ? getSystemTheme() : theme;

const applyResolvedTheme = (
  resolvedTheme: "light" | "dark",
  applyDataAttribute: boolean,
) => {
  if (typeof document === "undefined") return;

  const root = document.documentElement;
  const oppositeTheme = resolvedTheme === "dark" ? "light" : "dark";

  if (
    !root.classList.contains(resolvedTheme) ||
    root.classList.contains(oppositeTheme)
  ) {
    root.classList.remove("light", "dark");
    root.classList.add(resolvedTheme);
  }

  if (applyDataAttribute) {
    root.dataset.resolvedTheme = resolvedTheme;
  }
};

// ── Provider ─────────────────────────────────────────────────────────

export const ThemeProvider = ({
  children,
  storageKey = "theme",
  applyDataAttribute = true,
}: ThemeProviderProps) => {
  const [theme, setThemeState] = useState<Theme>(() =>
    getStoredTheme(storageKey),
  );

  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">(
    () => getDomResolvedTheme() ?? resolveTheme(getStoredTheme(storageKey)),
  );

  const setTheme = (t: Theme) => {
    setThemeState(t);
    window.localStorage.setItem(storageKey, t);
  };

  useLayoutEffect(() => {
    const nextResolvedTheme = resolveTheme(theme);
    setResolvedTheme((currentTheme) =>
      currentTheme === nextResolvedTheme ? currentTheme : nextResolvedTheme,
    );
    applyResolvedTheme(nextResolvedTheme, applyDataAttribute);
  }, [theme, applyDataAttribute]);

  useEffect(() => {
    if (theme !== "system") return;

    const mq = window.matchMedia(THEME_QUERY);
    const handler = (e: MediaQueryListEvent) => {
      const nextResolvedTheme = e.matches ? "dark" : "light";
      setResolvedTheme(nextResolvedTheme);
      applyResolvedTheme(nextResolvedTheme, applyDataAttribute);
    };

    // Safari < 14 compat: addEventListener may not exist on MediaQueryList
    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", handler);
      return () => mq.removeEventListener("change", handler);
    }

    mq.addListener(handler);
    return () => mq.removeListener(handler);
  }, [theme, applyDataAttribute]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, resolvedTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
