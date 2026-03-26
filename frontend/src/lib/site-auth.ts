export interface SiteAuthAvatarCandidate {
  key: string;
  label: string;
  avatar_url: string;
}

export interface SiteAuthUser {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string;
  effective_display_name: string;
  effective_avatar_url: string;
  primary_auth_provider: string;
  is_admin?: boolean;
  last_login_at?: string | null;
}

export interface SiteAuthState {
  authenticated: boolean;
  user: SiteAuthUser | null;
  email_login_enabled: boolean;
  oauth_providers: string[];
}

export interface EmailLoginResponse {
  authenticated: boolean;
  requires_profile: boolean;
  user: SiteAuthUser | null;
  suggested_display_name?: string | null;
  avatar_candidates: SiteAuthAvatarCandidate[];
  avatar_batch: number;
  avatar_total_batches: number;
}

export interface SiteAuthAvatarCandidateBatch {
  batch: number;
  total_batches: number;
  avatar_candidates: SiteAuthAvatarCandidate[];
}

async function request<T>(input: string, init?: RequestInit): Promise<T> {
  const response = await fetch(input, {
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let detail = "请求失败";
    try {
      const payload = await response.json();
      detail = String(payload?.detail || payload?.message || detail);
    } catch {
      // ignore
    }
    throw new Error(detail);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export function readSiteAuthState() {
  return request<SiteAuthState>("/api/v1/public/auth/me", { method: "GET" });
}

export function loginWithEmail(payload: {
  email: string;
  display_name?: string;
  avatar_url?: string;
}) {
  return request<EmailLoginResponse>("/api/v1/public/auth/email", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export function logoutSiteAuth() {
  return request<void>("/api/v1/public/auth/logout", {
    method: "POST",
  });
}

export function readAvatarCandidates(payload: { identity?: string; batch?: number }) {
  const query = new URLSearchParams();
  if (payload.identity?.trim()) {
    query.set("identity", payload.identity.trim());
  }
  if (typeof payload.batch === "number") {
    query.set("batch", String(payload.batch));
  }
  const suffix = query.toString();
  return request<SiteAuthAvatarCandidateBatch>(
    `/api/v1/public/auth/avatar-candidates${suffix ? `?${suffix}` : ""}`,
    { method: "GET" },
  );
}

export function updateSiteAuthProfile(payload: {
  display_name: string;
  avatar_url: string;
}) {
  return request<SiteAuthUser>("/api/v1/public/auth/me", {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function getOAuthAuthorizationUrl(provider: string, returnTo: string) {
  const query = new URLSearchParams({ return_to: returnTo });
  const payload = await request<{ authorization_url: string }>(
    `/api/v1/public/auth/oauth/${provider}/start?${query.toString()}`,
    { method: "GET" },
  );
  return payload.authorization_url;
}
