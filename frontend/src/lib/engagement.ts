const VIEWER_TOKEN_STORAGE_KEY = "aerisun:engagement:viewer-token";

export const getContentReactionStorageKey = (contentType: string, slug: string) =>
  `aerisun:engagement:reaction:${contentType}:${slug}:like`;

export const getViewerToken = () => {
  if (typeof window === "undefined") return undefined;
  const stored = window.localStorage.getItem(VIEWER_TOKEN_STORAGE_KEY);
  if (stored) return stored;
  const token =
    typeof window.crypto?.randomUUID === "function"
      ? window.crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
  window.localStorage.setItem(VIEWER_TOKEN_STORAGE_KEY, token);
  return token;
};
