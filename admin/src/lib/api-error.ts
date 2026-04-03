/**
 * Extract a user-facing error message from an API error response.
 *
 * Handles the Axios `error.response.data.detail` shape returned by the
 * FastAPI backend.  Falls back to `fallback` when the detail is absent or
 * not a non-empty string.
 */
export function extractApiErrorMessage(error: unknown, fallback: string): string {
  if (error && typeof error === "object") {
    const response = (error as { response?: { data?: { detail?: unknown } } }).response;
    const detail = response?.data?.detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail.trim();
    }
  }
  return fallback;
}
