import client from "../client";
import type { LoginRequest, LoginResponse, AdminUserRead } from "@/api/generated/model";

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const res = await client.post<LoginResponse>("/api/v1/admin/auth/login", data);
  return res.data;
}

export async function logout(): Promise<void> {
  await client.post("/api/v1/admin/auth/logout");
}

export async function getMe(): Promise<AdminUserRead> {
  const res = await client.get<AdminUserRead>("/api/v1/admin/auth/me");
  return res.data;
}

export async function changePassword(data: { current_password: string; new_password: string }): Promise<void> {
  await client.put("/api/v1/admin/auth/password", data);
}

export async function updateProfile(data: { username?: string }): Promise<AdminUserRead> {
  const res = await client.put<AdminUserRead>("/api/v1/admin/auth/profile", data);
  return res.data;
}

export interface AdminSession {
  id: string;
  created_at: string;
  expires_at: string;
  is_current: boolean;
}

export async function listSessions(): Promise<AdminSession[]> {
  const res = await client.get<AdminSession[]>("/api/v1/admin/auth/sessions");
  return res.data;
}

export async function revokeSession(sessionId: string): Promise<void> {
  await client.delete(`/api/v1/admin/auth/sessions/${sessionId}`);
}
