import { useEffect, useLayoutEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import {
  currentLanguage,
  currentScreenSize,
  navigationLoadMs,
  reportPageView,
} from "@/lib/visit-beacon";

// Paths that should never be counted as public page views.
const IGNORED_PREFIXES = ["/preview", "/admin"];

function isIgnored(pathname: string): boolean {
  return IGNORED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`),
  );
}

/**
 * Reports a page view to the backend whenever the SPA route changes.
 *
 * This is the primary analytics signal in production: the frontend is served as
 * static files by the reverse proxy, so client-side navigations never reach the
 * backend on their own.
 *
 * Each report carries a real "load time":
 * - the first (hard) load uses the Navigation Timing API (full document load);
 * - subsequent SPA navigations are timed from the URL commit to the next paint.
 */
export default function PageViewTracker() {
  const location = useLocation();
  const lastReportedRef = useRef<string | null>(null);
  const isFirstReportRef = useRef(true);
  const transitionMsRef = useRef<number | null>(null);

  // Measure how long this route transition takes to paint. The layout effect
  // runs right after the URL commits (before paint); we then sample after the
  // next frame to capture the client-side render/transition cost.
  useLayoutEffect(() => {
    if (typeof performance === "undefined" || typeof window === "undefined") {
      return;
    }
    const start = performance.now();
    transitionMsRef.current = null;
    let raf2 = 0;
    const raf1 = window.requestAnimationFrame(() => {
      raf2 = window.requestAnimationFrame(() => {
        transitionMsRef.current = Math.max(0, Math.round(performance.now() - start));
      });
    });
    return () => {
      window.cancelAnimationFrame(raf1);
      if (raf2) {
        window.cancelAnimationFrame(raf2);
      }
    };
  }, [location.pathname, location.search]);

  useEffect(() => {
    const url = `${location.pathname}${location.search}`;

    if (isIgnored(location.pathname) || lastReportedRef.current === url) {
      return;
    }
    lastReportedRef.current = url;

    const isInitial = isFirstReportRef.current;
    isFirstReportRef.current = false;

    // Defer slightly so we never compete with the route's initial render (and
    // so the transition timing has been sampled by the rAF callbacks above).
    const timer = window.setTimeout(() => {
      const loadMs = isInitial
        ? (navigationLoadMs() ?? transitionMsRef.current)
        : transitionMsRef.current;
      reportPageView({
        url,
        referer: typeof document !== "undefined" ? document.referrer || null : null,
        screen: currentScreenSize(),
        language: currentLanguage(),
        loadMs,
      });
    }, 300);

    return () => window.clearTimeout(timer);
  }, [location.pathname, location.search]);

  return null;
}
