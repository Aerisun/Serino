import client from "../client";
import type { LoginRequest, LoginResponse, AdminUser } from "@/types/models";

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const res = await client.post<LoginResponse>("/auth/login", data);
  return res.data;
}

export async function logout(): Promise<void> {
  await client.post("/auth/logout");
}

export async function getMe(): Promise<AdminUser> {
  const res = await client.get<AdminUser>("/auth/me");
  return res.data;
}

export async function changePassword(data: { current_password: string; new_password: string }): Promise<void> {
  await client.put("/auth/password", data);
}

export async function updateProfile(data: { username?: string }): Promise<AdminUser> {
  const res = await client.put<AdminUser>("/auth/profile", data);
  return res.data;
}

export interface AdminSession {
  id: string;
  created_at: string;
  expires_at: string;
  is_current: boolean;
}

export async function listSessions(): Promise<AdminSession[]> {
  const res = await client.get<AdminSession[]>("/auth/sessions");
  return res.data;
}

export async function revokeSession(sessionId: string): Promise<void> {
  await client.delete(`/auth/sessions/${sessionId}`);
}
