import type {
  AdminLoginOptionsRead,
  AdminUserRead,
  LoginResponse,
} from "@serino/api-client/models";
import { adminApiRequest } from "@/lib/adminApi";

export function loginAdmin(username: string, password: string) {
  return adminApiRequest<LoginResponse>("/api/v1/admin/auth/login", {
    method: "POST",
    body: { username, password },
  });
}

export function getAdminLoginOptions(signal?: AbortSignal) {
  return adminApiRequest<AdminLoginOptionsRead>("/api/v1/admin/auth/options", {
    method: "GET",
    signal,
  });
}

export function loginWithAdminEmail(email: string, password: string) {
  return adminApiRequest<LoginResponse>("/api/v1/admin/auth/email", {
    method: "POST",
    body: { email, password },
  });
}

export function exchangeSiteAdminLogin() {
  return adminApiRequest<LoginResponse>("/api/v1/admin/auth/exchange-site-user", {
    method: "POST",
  });
}

export function getCurrentAdmin(signal?: AbortSignal) {
  return adminApiRequest<AdminUserRead>("/api/v1/admin/auth/me", {
    method: "GET",
    signal,
  });
}

export function logoutAdmin() {
  return adminApiRequest<void>("/api/v1/admin/auth/logout", {
    method: "POST",
  });
}
