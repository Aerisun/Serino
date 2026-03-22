import { useLayoutEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { useTheme } from "@/contexts/ThemeContext";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import {
  SHIRO_ACCENT_PALETTES,
  buildShiroAccentTokens,
} from "@/lib/shiro-accent";

const STORAGE_KEY = "aerisun:shiro-accent-palette-index";
const TRANSITION_MS = 420;

const getInitialPaletteIndex = () => {
  if (typeof window === "undefined") return 0;

  const lastIndex = Number.parseInt(
    window.localStorage.getItem(STORAGE_KEY) ?? "",
    10,
  );

  if (!Number.isNaN(lastIndex) && SHIRO_ACCENT_PALETTES.length > 1) {
    const offset = 1 + Math.floor(Math.random() * (SHIRO_ACCENT_PALETTES.length - 1));
    return (lastIndex + offset) % SHIRO_ACCENT_PALETTES.length;
  }

  return Math.floor(Math.random() * SHIRO_ACCENT_PALETTES.length);
};

const applyPaletteTokens = (paletteIndex: number, theme: "light" | "dark") => {
  const palette = SHIRO_ACCENT_PALETTES[paletteIndex];
  const root = document.documentElement;
  const tokens = buildShiroAccentTokens(palette, theme);

  for (const [key, value] of Object.entries(tokens)) {
    root.style.setProperty(key, value);
  }

  root.dataset.shiroPalette = palette.id;
  root.dataset.shiroPaletteName = palette.name;
  window.localStorage.setItem(STORAGE_KEY, String(paletteIndex));
};

const ShiroAccentController = () => {
  const location = useLocation();
  const { resolvedTheme } = useTheme();
  const prefersReducedMotion = useReducedMotionPreference();
  const paletteIndexRef = useRef<number | null>(null);
  const pathRef = useRef<string | null>(null);

  useLayoutEffect(() => {
    const currentPath = location.pathname;
    const isFirstRender = paletteIndexRef.current === null;
    const didPathChange = pathRef.current !== null && pathRef.current !== currentPath;
    const root = document.documentElement;

    if (isFirstRender) {
      paletteIndexRef.current = getInitialPaletteIndex();
    } else if (didPathChange) {
      paletteIndexRef.current =
        ((paletteIndexRef.current ?? 0) + 1) % SHIRO_ACCENT_PALETTES.length;
    }

    const nextPaletteIndex = paletteIndexRef.current ?? 0;
    pathRef.current = currentPath;

    if (isFirstRender || prefersReducedMotion) {
      applyPaletteTokens(nextPaletteIndex, resolvedTheme);
      return;
    }

    root.dataset.shiroTransition = "true";

    let cleanupTimer = 0;
    let frameA = 0;
    let frameB = 0;

    frameA = window.requestAnimationFrame(() => {
      frameB = window.requestAnimationFrame(() => {
        applyPaletteTokens(nextPaletteIndex, resolvedTheme);
        cleanupTimer = window.setTimeout(() => {
          delete root.dataset.shiroTransition;
        }, TRANSITION_MS);
      });
    });

    return () => {
      window.cancelAnimationFrame(frameA);
      window.cancelAnimationFrame(frameB);
      window.clearTimeout(cleanupTimer);
      delete root.dataset.shiroTransition;
    };
  }, [location.pathname, prefersReducedMotion, resolvedTheme]);

  return null;
};

export default ShiroAccentController;
