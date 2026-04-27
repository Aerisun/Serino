import { clearAdminToken, getAdminToken } from "@/lib/storage";

type AdminApiQueryPrimitive = string | number | boolean | null | undefined;
type AdminApiQueryValue = AdminApiQueryPrimitive | AdminApiQueryPrimitive[];

export type AdminApiRequestInit = Omit<RequestInit, "body"> & {
  body?: unknown;
  query?: Record<string, AdminApiQueryValue>;
};

const adminBasePath =
  typeof __AERISUN_ADMIN_BASE_PATH__ === "string"
    ? __AERISUN_ADMIN_BASE_PATH__
    : "/admin/";
const loginPath =
  typeof window === "undefined"
    ? `${adminBasePath.replace(/\/$/, "")}/login`
    : new URL("login", window.location.origin + adminBasePath).pathname;

function normalizeApiError(detail: unknown, fallback: string) {
  if (typeof detail === "string" && detail.trim()) {
    return detail.trim();
  }

  if (Array.isArray(detail) && detail.length > 0) {
    const parts = detail
      .map((item) => {
        if (!item || typeof item !== "object") {
          return null;
        }

        const record = item as { msg?: unknown; loc?: unknown };
        const message = typeof record.msg === "string" ? record.msg.trim() : "";
        const location = Array.isArray(record.loc)
          ? record.loc
              .filter(
                (value): value is string | number =>
                  typeof value === "string" || typeof value === "number",
              )
              .join(".")
          : "";

        if (!message) {
          return null;
        }

        return location ? `${location}: ${message}` : message;
      })
      .filter((item): item is string => Boolean(item));

    if (parts.length > 0) {
      return parts.join("; ");
    }
  }

  return fallback;
}

async function readResponsePayload(response: Response) {
  const text = await response.text();
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as unknown;
  } catch {
    return text;
  }
}

function appendQueryParams(url: URL, query?: Record<string, AdminApiQueryValue>) {
  if (!query) {
    return;
  }

  Object.entries(query).forEach(([key, value]) => {
    if (value === undefined) {
      return;
    }

    if (Array.isArray(value)) {
      value.forEach((item) => {
        if (item !== undefined) {
          url.searchParams.append(key, String(item));
        }
      });
      return;
    }

    url.searchParams.set(key, String(value));
  });
}

function normalizeRequestBody(body: unknown, headers: Headers) {
  if (body === undefined) {
    return undefined;
  }

  if (
    body instanceof FormData ||
    body instanceof URLSearchParams ||
    body instanceof Blob ||
    typeof body === "string" ||
    body instanceof ArrayBuffer
  ) {
    return body;
  }

  headers.set("Content-Type", "application/json");
  return JSON.stringify(body);
}

export async function adminApiRequest<T>(
  path: string,
  init: AdminApiRequestInit = {},
): Promise<T> {
  const url = new URL(path, window.location.origin);
  appendQueryParams(url, init.query);

  const headers = new Headers(init.headers);
  const token = getAdminToken();

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  const response = await fetch(url.pathname + url.search, {
    ...init,
    body: normalizeRequestBody(init.body, headers),
    credentials: "include",
    headers,
  });
  const payload = await readResponsePayload(response);

  if (response.status === 401) {
    clearAdminToken();
    if (window.location.pathname !== loginPath) {
      window.location.assign(loginPath);
    }
    throw new Error("Authentication required");
  }

  if (!response.ok) {
    const detail =
      payload && typeof payload === "object" && "detail" in payload
        ? (payload as { detail?: unknown }).detail
        : payload;
    throw new Error(
      normalizeApiError(detail, response.statusText || "Request failed"),
    );
  }

  return payload as T;
}
