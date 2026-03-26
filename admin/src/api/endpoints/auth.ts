import {
  changePasswordApiV1AdminAuthPasswordPut,
  exchangeSiteUserLoginApiV1AdminAuthExchangeSiteUserPost,
  loginOptionsApiV1AdminAuthOptionsGet,
  listSessionsEndpointApiV1AdminAuthSessionsGet,
  loginWithBoundEmailApiV1AdminAuthEmailPost,
  loginApiV1AdminAuthLoginPost,
  logoutApiV1AdminAuthLogoutPost,
  meApiV1AdminAuthMeGet,
  revokeSessionApiV1AdminAuthSessionsSessionIdDelete,
  updateProfileEndpointApiV1AdminAuthProfilePut,
} from "@serino/api-client/admin";
import type {
  AdminEmailLoginRequest,
  AdminLoginOptionsRead,
  AdminProfileUpdate,
  AdminSessionRead,
  AdminUserRead,
  LoginRequest,
  LoginResponse,
  PasswordChangeRequest,
} from "@serino/api-client/models";

export async function login(data: LoginRequest): Promise<LoginResponse> {
  const response = await loginApiV1AdminAuthLoginPost(data);
  return response.data as LoginResponse;
}

export async function getLoginOptions(): Promise<AdminLoginOptionsRead> {
  const response = await loginOptionsApiV1AdminAuthOptionsGet();
  return response.data as AdminLoginOptionsRead;
}

export async function loginWithBoundEmail(data: AdminEmailLoginRequest): Promise<LoginResponse> {
  const response = await loginWithBoundEmailApiV1AdminAuthEmailPost(data);
  return response.data as LoginResponse;
}

export async function exchangeSiteUserLogin(): Promise<LoginResponse> {
  const response = await exchangeSiteUserLoginApiV1AdminAuthExchangeSiteUserPost();
  return response.data as LoginResponse;
}

export async function logout(): Promise<void> {
  await logoutApiV1AdminAuthLogoutPost();
}

export async function getMe(): Promise<AdminUserRead> {
  const response = await meApiV1AdminAuthMeGet();
  return response.data as AdminUserRead;
}

export async function changePassword(data: PasswordChangeRequest): Promise<void> {
  await changePasswordApiV1AdminAuthPasswordPut(data);
}

export async function updateProfile(data: AdminProfileUpdate): Promise<AdminUserRead> {
  const response = await updateProfileEndpointApiV1AdminAuthProfilePut(data);
  return response.data as AdminUserRead;
}

export type AdminSession = AdminSessionRead;

export async function listSessions(): Promise<AdminSession[]> {
  const response = await listSessionsEndpointApiV1AdminAuthSessionsGet();
  return response.data as AdminSession[];
}

export async function revokeSession(sessionId: string): Promise<void> {
  await revokeSessionApiV1AdminAuthSessionsSessionIdDelete(sessionId);
}
