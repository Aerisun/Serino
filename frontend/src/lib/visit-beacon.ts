import { API_BASE_PATH, API_BASE_URL } from "@/lib/api";

const VISIT_ENDPOINT = `${API_BASE_PATH}/v1/site-interactions/visit`;

function resolveEndpoint(): string {
  return API_BASE_URL ? new URL(VISIT_ENDPOINT, API_BASE_URL).toString() : VISIT_ENDPOINT;
}

export interface VisitBeaconPayload {
  url: string;
  referer?: string | null;
  screen?: string | null;
  language?: string | null;
  loadMs?: number | null;
}

/**
 * Report a page view to the backend analytics endpoint.
 *
 * Fire-and-forget: errors are swallowed so tracking never affects the UX.
 * Uses `fetch` with `keepalive` so the request survives a route change, and
 * falls back to `navigator.sendBeacon` when `fetch` is unavailable.
 */
export function reportPageView(payload: VisitBeaconPayload): void {
  if (typeof window === "undefined") {
    return;
  }

  const body = JSON.stringify({
    url: payload.url,
    referer: payload.referer ?? null,
    screen: payload.screen ?? null,
    language: payload.language ?? null,
    load_ms: payload.loadMs ?? null,
  });
  const endpoint = resolveEndpoint();

  try {
    if (typeof fetch === "function") {
      void fetch(endpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body,
        keepalive: true,
        credentials: "omit",
        cache: "no-store",
      }).catch(() => {
        /* ignore network errors */
      });
      return;
    }

    if (typeof navigator !== "undefined" && typeof navigator.sendBeacon === "function") {
      navigator.sendBeacon(endpoint, new Blob([body], { type: "application/json" }));
    }
  } catch {
    /* never let analytics break the page */
  }
}

export function currentScreenSize(): string | null {
  if (typeof window === "undefined" || !window.screen) {
    return null;
  }
  const { width, height } = window.screen;
  if (!width || !height) {
    return null;
  }
  return `${Math.round(width)}x${Math.round(height)}`;
}

export function currentLanguage(): string | null {
  if (typeof navigator === "undefined") {
    return null;
  }
  return navigator.language || null;
}

/**
 * Real page load time of the initial document, via the Navigation Timing API.
 *
 * Returns the time from navigation start to the load event (falling back to
 * DOMContentLoaded / response end, or `performance.now()` if the load event has
 * not fired yet). Returns `null` when timing data is unavailable. This is only
 * meaningful for the first (hard) page load of a session; SPA route changes are
 * measured separately by the caller.
 */
export function navigationLoadMs(): number | null {
  if (typeof performance === "undefined" || typeof performance.getEntriesByType !== "function") {
    return null;
  }
  const nav = performance.getEntriesByType("navigation")[0] as
    | PerformanceNavigationTiming
    | undefined;
  if (!nav) {
    const now = performance.now();
    return now > 0 ? Math.round(now) : null;
  }
  const end = nav.loadEventEnd || nav.domContentLoadedEventEnd || nav.responseEnd;
  const start = nav.startTime || 0;
  const duration = end > 0 ? end - start : performance.now() - start;
  return duration > 0 ? Math.round(duration) : null;
}
