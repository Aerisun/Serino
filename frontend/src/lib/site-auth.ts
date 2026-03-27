import { normalizeErrorMessage } from "@serino/api-client";
import {
  emailLoginApiV1SiteAuthEmailPost,
  logoutApiV1SiteAuthLogoutPost,
  oauthStartApiV1SiteAuthOauthProviderStartGet,
  readAvatarCandidatesApiV1SiteAuthAvatarCandidatesGet,
  readSiteAuthStateApiV1SiteAuthMeGet,
  updateMyProfileApiV1SiteAuthMePatch,
} from "@serino/api-client/site-auth";
import type {
  EmailLoginRequest,
  EmailLoginResponse as GeneratedEmailLoginResponse,
  SiteAuthAvatarCandidate,
  SiteAuthAvatarCandidateBatchRead as GeneratedSiteAuthAvatarCandidateBatch,
  SiteAuthProfileUpdateRequest,
  SiteAuthStateRead,
  SiteAuthUserRead,
} from "@serino/api-client/models";
import type { AxiosError } from "axios";

export type SiteAuthUser = SiteAuthUserRead;
export type SiteAuthState = SiteAuthStateRead;
export type EmailLoginResponse = GeneratedEmailLoginResponse;
export type SiteAuthAvatarCandidateBatch = GeneratedSiteAuthAvatarCandidateBatch;

const resolveErrorMessage = (error: unknown) => {
  if (error instanceof AxiosError) {
    const detail = error.response?.data as { detail?: unknown; message?: unknown } | undefined;
    return normalizeErrorMessage(detail?.detail) ?? normalizeErrorMessage(detail?.message) ?? error.message;
  }

  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }

  return "请求失败";
};

async function withApiError<T>(request: Promise<{ data: T }>): Promise<T> {
  try {
    const response = await request;
    return response.data;
  } catch (error) {
    throw new Error(resolveErrorMessage(error));
  }
}

export function readSiteAuthState() {
  return withApiError(readSiteAuthStateApiV1SiteAuthMeGet());
}

export function loginWithEmail(payload: EmailLoginRequest) {
  return withApiError(emailLoginApiV1SiteAuthEmailPost(payload));
}

export async function logoutSiteAuth() {
  await withApiError(logoutApiV1SiteAuthLogoutPost());
}

export function readAvatarCandidates(payload: { identity?: string; batch?: number }) {
  return withApiError(readAvatarCandidatesApiV1SiteAuthAvatarCandidatesGet(payload));
}

export function updateSiteAuthProfile(payload: SiteAuthProfileUpdateRequest) {
  return withApiError(updateMyProfileApiV1SiteAuthMePatch(payload));
}

export async function getOAuthAuthorizationUrl(provider: string, returnTo: string) {
  const payload = await withApiError(
    oauthStartApiV1SiteAuthOauthProviderStartGet(provider, { return_to: returnTo }),
  );
  return payload.authorization_url;
}

export type { EmailLoginRequest, SiteAuthAvatarCandidate, SiteAuthProfileUpdateRequest };
