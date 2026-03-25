export interface ApiClientConfig {
  /** Base URL prepended to all requests (e.g. "" for same-origin). */
  baseUrl?: string;
  /** Return a bearer token, or null if unauthenticated. */
  getAuthToken?: () => string | null;
  /** Called on HTTP 401 — typically clear credentials and redirect. */
  onAuthError?: () => void;
}

export type ErrorType<E> = import("axios").AxiosError<E>;
export type BodyType<D> = D;
