import { useEffect, useLayoutEffect, useState, type ReactNode } from "react";
import { ThemeContext, type Theme } from "./theme-context";

const THEME_QUERY = "(prefers-color-scheme: dark)";

const getSystemTheme = (): "light" | "dark" =>
  window.matchMedia(THEME_QUERY).matches ? "dark" : "light";

const getStoredTheme = (): Theme => {
  if (typeof window === "undefined") return "system";

  const stored = window.localStorage.getItem("theme");
  if (stored === "light" || stored === "dark" || stored === "system") {
    return stored;
  }

  return "system";
};

const getDomResolvedTheme = (): "light" | "dark" | null => {
  if (typeof document === "undefined") return null;

  const root = document.documentElement;
  if (root.classList.contains("dark")) return "dark";
  if (root.classList.contains("light")) return "light";
  return null;
};

const resolveTheme = (theme: Theme): "light" | "dark" =>
  theme === "system" ? getSystemTheme() : theme;

const applyResolvedTheme = (resolvedTheme: "light" | "dark") => {
  if (typeof document === "undefined") return;

  const root = document.documentElement;
  const oppositeTheme = resolvedTheme === "dark" ? "light" : "dark";

  if (!root.classList.contains(resolvedTheme) || root.classList.contains(oppositeTheme)) {
    root.classList.remove("light", "dark");
    root.classList.add(resolvedTheme);
  }

  root.dataset.resolvedTheme = resolvedTheme;
};

export const ThemeProvider = ({ children }: { children: ReactNode }) => {
  const [theme, setThemeState] = useState<Theme>(getStoredTheme);

  const [resolvedTheme, setResolvedTheme] = useState<"light" | "dark">(() =>
    getDomResolvedTheme() ?? resolveTheme(getStoredTheme())
  );

  const setTheme = (t: Theme) => {
    setThemeState(t);
    window.localStorage.setItem("theme", t);
  };

  useLayoutEffect(() => {
    const nextResolvedTheme = resolveTheme(theme);
    setResolvedTheme((currentTheme) =>
      currentTheme === nextResolvedTheme ? currentTheme : nextResolvedTheme,
    );
    applyResolvedTheme(nextResolvedTheme);
  }, [theme]);

  useEffect(() => {
    if (theme !== "system") return;

    const mq = window.matchMedia(THEME_QUERY);
    const handler = (e: MediaQueryListEvent) => {
      const nextResolvedTheme = e.matches ? "dark" : "light";
      setResolvedTheme(nextResolvedTheme);
      applyResolvedTheme(nextResolvedTheme);
    };

    if (typeof mq.addEventListener === "function") {
      mq.addEventListener("change", handler);
      return () => mq.removeEventListener("change", handler);
    }

    mq.addListener(handler);
    return () => mq.removeListener(handler);
  }, [theme]);

  return (
    <ThemeContext.Provider value={{ theme, setTheme, resolvedTheme }}>
      {children}
    </ThemeContext.Provider>
  );
};
