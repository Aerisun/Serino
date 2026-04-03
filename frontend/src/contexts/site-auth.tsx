import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { useQueryClient } from "@tanstack/react-query";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import {
  Check,
  BellOff,
  Github,
  Lock,
  Loader2,
  Mail,
  RefreshCcw,
  Sparkles,
  UserRoundPen,
} from "lucide-react";
import { transition } from "@/config";
import { useFrontendI18n } from "@/i18n";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import {
  getOAuthAuthorizationUrl,
  loginWithEmail,
  logoutSiteAuth,
  readContentSubscriptionByEmail,
  readAvatarCandidates,
  readSiteAuthState,
  type SiteContentSubscriptionStatus,
  type SiteAuthAvatarCandidate,
  type SiteAuthAvatarCandidateBatch,
  type SiteAuthState,
  unsubscribeContentSubscriptionByEmail,
  updateSiteAuthProfile,
} from "@/lib/site-auth";
import {
  getTrackedSubscriptionEmails,
  replaceTrackedSubscriptionEmails,
  trackSubscriptionEmail,
  untrackSubscriptionEmail,
} from "@/lib/subscription-tracker";
import {
  SiteAuthContext,
  type SiteAuthContextValue,
} from "@/contexts/site-auth-context";
type AuthDialogMode = "login" | "profile";

const CONTENT_TYPE_LABEL_KEYS: Record<string, string> = {
  posts: "subscribe.content.posts",
  diary: "subscribe.content.diary",
  thoughts: "subscribe.content.thoughts",
  excerpts: "subscribe.content.excerpts",
};

interface SubscriptionChangedDetail {
  email: string;
  content_types: string[];
  subscribed: boolean;
}

const PROFILE_AVATAR_PICKER_COUNT = 12;

function normalizeEmail(value: string | null | undefined) {
  return (value ?? "").trim().toLowerCase();
}

function providerLabel(provider: string) {
  return provider === "google"
    ? "Google"
    : provider === "github"
      ? "GitHub"
      : provider;
}

function providerIcon(provider: string) {
  if (provider === "github") return Github;
  return Sparkles;
}

export function SiteAuthProvider({ children }: { children: ReactNode }) {
  const prefersReducedMotion = useReducedMotionPreference();
  const { t } = useFrontendI18n();
  const queryClient = useQueryClient();
  const [authState, setAuthState] = useState<SiteAuthState | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<AuthDialogMode>("login");
  const [submitting, setSubmitting] = useState(false);
  const [avatarLoading, setAvatarLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [allowEmailLoginInDialog, setAllowEmailLoginInDialog] = useState(true);
  const [email, setEmail] = useState("");
  const [adminPassword, setAdminPassword] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [avatarCandidates, setAvatarCandidates] = useState<
    SiteAuthAvatarCandidate[]
  >([]);
  const [selectedAvatar, setSelectedAvatar] = useState("");
  const [avatarBatch, setAvatarBatch] = useState(0);
  const [_avatarTotalBatches, setAvatarTotalBatches] = useState(1);
  const [needsProfile, setNeedsProfile] = useState(false);
  const [requiresAdminPassword, setRequiresAdminPassword] = useState(false);
  const [subscriptionStatuses, setSubscriptionStatuses] = useState<
    SiteContentSubscriptionStatus[]
  >([]);
  const [subscriptionLoading, setSubscriptionLoading] = useState(false);
  const [subscriptionPendingEmail, setSubscriptionPendingEmail] = useState<
    string | null
  >(null);
  const [subscriptionFeedback, setSubscriptionFeedback] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      const next = await readSiteAuthState();
      setAuthState(next);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const invalidateSiteContentQueries = useCallback(async () => {
    await queryClient.invalidateQueries({
      predicate: (query) => {
        const [firstKey] = query.queryKey;
        return firstKey === "site" || (typeof firstKey === "string" && firstKey.startsWith("/api/v1/site/"));
      },
    });
  }, [queryClient]);

  const resetForm = useCallback(() => {
    setError(null);
    setAllowEmailLoginInDialog(true);
    setEmail("");
    setAdminPassword("");
    setNeedsProfile(false);
    setRequiresAdminPassword(false);
    setDisplayName("");
    setAvatarCandidates([]);
    setSelectedAvatar("");
    setAvatarBatch(0);
    setAvatarTotalBatches(1);
    setAvatarLoading(false);
    setSubscriptionStatuses([]);
    setSubscriptionLoading(false);
    setSubscriptionPendingEmail(null);
    setSubscriptionFeedback(null);
    setMode("login");
  }, []);

  useEffect(() => {
    const handler = () => {
      resetForm();
      setAllowEmailLoginInDialog(true);
      setMode("login");
      setOpen(true);
    };
    window.addEventListener("aerisun:open-site-auth", handler);
    return () => window.removeEventListener("aerisun:open-site-auth", handler);
  }, [resetForm]);

  const closeLogin = useCallback(() => {
    setOpen(false);
    resetForm();
  }, [resetForm]);

  const openLogin = useCallback(
    (options?: { allowEmailLogin?: boolean }) => {
      resetForm();
      setAllowEmailLoginInDialog(options?.allowEmailLogin !== false);
      setMode("login");
      setOpen(true);
    },
    [resetForm],
  );

  const applyAvatarBatch = useCallback(
    (result: SiteAuthAvatarCandidateBatch, preferredAvatar?: string) => {
      const candidatePool = result.avatar_candidates ?? [];
      const nextCandidates =
        preferredAvatar &&
        !candidatePool.some(
          (candidate) => candidate.avatar_url === preferredAvatar,
        )
          ? [
              {
                key: `current:${preferredAvatar}`,
                label: t("siteAuth.currentAvatar"),
                avatar_url: preferredAvatar,
              },
              ...candidatePool,
            ]
          : candidatePool;
      const visibleCandidates = nextCandidates.slice(
        0,
        PROFILE_AVATAR_PICKER_COUNT,
      );

      setAvatarCandidates(visibleCandidates);
      setAvatarBatch(result.batch ?? 0);
      setAvatarTotalBatches(result.total_batches ?? 1);
      setSelectedAvatar((current) => {
        if (preferredAvatar) {
          return preferredAvatar;
        }
        if (
          current &&
          visibleCandidates.some(
            (candidate) => candidate.avatar_url === current,
          )
        ) {
          return current;
        }
        return visibleCandidates[0]?.avatar_url || "";
      });
    },
    [t],
  );

  const loadAvatarBatch = useCallback(
    async (identity: string, nextBatch: number, preferredAvatar?: string) => {
      setAvatarLoading(true);
      setError(null);
      try {
        const result = await readAvatarCandidates({
          identity,
          batch: nextBatch,
        });
        applyAvatarBatch(result, preferredAvatar);
      } catch (err) {
        setError(err instanceof Error ? err.message : t("siteAuth.avatarLoadFailed"));
      } finally {
        setAvatarLoading(false);
      }
    },
    [applyAvatarBatch, t],
  );

  const openProfileEditor = useCallback(() => {
    if (!authState?.user) {
      return;
    }
    setMode("profile");
    setError(null);
    setNeedsProfile(false);
    setEmail(authState.user.email);
    setDisplayName(authState.user.display_name);
    setSelectedAvatar(authState.user.avatar_url);
    setAvatarCandidates([]);
    setAvatarBatch(0);
    setAvatarTotalBatches(1);
    setOpen(true);
  }, [authState?.user]);

  useEffect(() => {
    if (!open || mode !== "profile" || !authState?.user) {
      return;
    }
    void loadAvatarBatch(authState.user.email, 0, authState.user.avatar_url);
  }, [authState?.user, loadAvatarBatch, mode, open]);

  const loadSubscriptionStatuses = useCallback(async () => {
    setSubscriptionLoading(true);
    setSubscriptionFeedback(null);
    try {
      const trackedEmails = getTrackedSubscriptionEmails();
      if (trackedEmails.length === 0) {
        setSubscriptionStatuses([]);
        return;
      }

      const nextStatuses = await Promise.all(
        trackedEmails.map((trackedEmail) =>
          readContentSubscriptionByEmail(trackedEmail),
        ),
      );
      const activeStatuses = nextStatuses.filter((item) => item.subscribed);
      replaceTrackedSubscriptionEmails(
        activeStatuses.map((item) => item.email),
      );
      setSubscriptionStatuses(activeStatuses);
    } catch (err) {
      setSubscriptionFeedback({
        kind: "error",
        message: err instanceof Error ? err.message : t("siteAuth.subscriptionListLoadFailed"),
      });
    } finally {
      setSubscriptionLoading(false);
    }
  }, [t]);

  useEffect(() => {
    if (!open || mode !== "profile") {
      return;
    }
    void loadSubscriptionStatuses();
  }, [loadSubscriptionStatuses, mode, open]);

  useEffect(() => {
    const handleSubscriptionChanged = (event: Event) => {
      const detail = (event as CustomEvent<SubscriptionChangedDetail>).detail;
      if (!detail) {
        return;
      }

      if (detail.subscribed) {
        trackSubscriptionEmail(detail.email);
      } else {
        untrackSubscriptionEmail(detail.email);
      }

      setSubscriptionStatuses((current) => {
        const normalized = normalizeEmail(detail.email);
        const remaining = current.filter(
          (item) => normalizeEmail(item.email) !== normalized,
        );
        if (!detail.subscribed) {
          return remaining;
        }
        return [
          {
            email: detail.email,
            content_types: detail.content_types,
            subscribed: detail.subscribed,
          },
          ...remaining,
        ];
      });
      setSubscriptionLoading(false);
      setSubscriptionFeedback({
        kind: detail.subscribed ? "success" : "error",
        message: detail.subscribed
          ? t("siteAuth.subscriptionAdded", { email: detail.email })
          : t("siteAuth.subscriptionRemoved", { email: detail.email }),
      });
    };

    window.addEventListener(
      "aerisun:subscription-changed",
      handleSubscriptionChanged,
    );
    return () => {
      window.removeEventListener(
        "aerisun:subscription-changed",
        handleSubscriptionChanged,
      );
    };
  }, [t]);

  const handleEmailLogin = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      const payload: {
        email: string;
        display_name?: string;
        avatar_url?: string;
        admin_password?: string;
      } = { email };

      if (needsProfile) {
        payload.display_name = displayName;
        payload.avatar_url = selectedAvatar;
      }
      if (requiresAdminPassword) {
        payload.admin_password = adminPassword;
      }

      const result = await loginWithEmail(payload);
      if (result.requires_admin_password) {
        setRequiresAdminPassword(true);
        setAdminPassword("");
        return;
      }
      if (result.requires_profile) {
        setNeedsProfile(true);
        setRequiresAdminPassword(false);
        setMode("login");
        setDisplayName(result.suggested_display_name || "");
        applyAvatarBatch({
          batch: result.avatar_batch ?? 0,
          total_batches: result.avatar_total_batches ?? 1,
          avatar_candidates: result.avatar_candidates ?? [],
        });
        return;
      }

      setAuthState((current) => ({
        authenticated: true,
        email_login_enabled: current?.email_login_enabled ?? true,
        oauth_providers: current?.oauth_providers ?? [],
        user: result.user,
      }));
      await invalidateSiteContentQueries();
      closeLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("siteAuth.loginFailed"));
    } finally {
      setSubmitting(false);
    }
  }, [
    applyAvatarBatch,
    adminPassword,
    closeLogin,
    displayName,
    email,
    invalidateSiteContentQueries,
    needsProfile,
    requiresAdminPassword,
    selectedAvatar,
    t,
  ]);

  const handleProfileUpdate = useCallback(async () => {
    if (!displayName.trim() || !selectedAvatar) {
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const nextUser = await updateSiteAuthProfile({
        display_name: displayName,
        avatar_url: selectedAvatar,
      });
      setAuthState((current) => ({
        authenticated: true,
        email_login_enabled: current?.email_login_enabled ?? true,
        oauth_providers: current?.oauth_providers ?? [],
        user: nextUser,
      }));
      closeLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : t("siteAuth.profileUpdateFailed"));
    } finally {
      setSubmitting(false);
    }
  }, [closeLogin, displayName, selectedAvatar, t]);

  const handleRefreshAvatars = useCallback(async () => {
    const identity =
      mode === "profile" ? (authState?.user?.email ?? "") : email;
    if (!identity.trim()) {
      setError(t("siteAuth.emailRequired"));
      return;
    }
    await loadAvatarBatch(identity, avatarBatch + 1);
  }, [authState?.user?.email, avatarBatch, email, loadAvatarBatch, mode, t]);

  const handleOAuthLogin = useCallback(async (provider: string) => {
    setSubmitting(true);
    setError(null);
    try {
      const url = await getOAuthAuthorizationUrl(
        provider,
        `${window.location.pathname}${window.location.search}`,
      );
      window.location.assign(url);
    } catch (err) {
      setError(err instanceof Error ? err.message : t("siteAuth.loginFailed"));
      setSubmitting(false);
    }
  }, [t]);

  const handleUnsubscribe = useCallback(async (targetEmail: string) => {
    setSubscriptionPendingEmail(targetEmail);
    setSubscriptionFeedback(null);
    try {
      await unsubscribeContentSubscriptionByEmail(targetEmail);
      untrackSubscriptionEmail(targetEmail);
      setSubscriptionStatuses((current) =>
        current.filter(
          (item) => normalizeEmail(item.email) !== normalizeEmail(targetEmail),
        ),
      );
      setSubscriptionFeedback({
        kind: "success",
        message: t("siteAuth.unsubscribeSuccess", { email: targetEmail }),
      });
    } catch (err) {
      setSubscriptionFeedback({
        kind: "error",
        message: err instanceof Error ? err.message : t("siteAuth.unsubscribeFailed"),
      });
    } finally {
      setSubscriptionPendingEmail(null);
    }
  }, [t]);

  const logout = useCallback(async () => {
    await logoutSiteAuth();
    setAuthState((current) => ({
      authenticated: false,
      email_login_enabled: current?.email_login_enabled ?? true,
      oauth_providers: current?.oauth_providers ?? [],
      user: null,
    }));
    await invalidateSiteContentQueries();
  }, [invalidateSiteContentQueries]);

  const dialogEmailLoginEnabled =
    Boolean(authState?.email_login_enabled) && allowEmailLoginInDialog;
  const enabledOAuthProviderSet = useMemo(
    () =>
      new Set(
        (authState?.oauth_providers ?? [])
          .map((provider) => provider.trim().toLowerCase())
          .filter(Boolean),
      ),
    [authState?.oauth_providers],
  );

  const value = useMemo<SiteAuthContextValue>(
    () => ({
      user: authState?.user ?? null,
      loading,
      emailLoginEnabled: Boolean(authState?.email_login_enabled),
      oauthProviders: authState?.oauth_providers ?? [],
      openLogin,
      openProfileEditor,
      closeLogin,
      logout,
      refresh,
    }),
    [
      authState?.email_login_enabled,
      authState?.oauth_providers,
      authState?.user,
      closeLogin,
      loading,
      logout,
      openLogin,
      openProfileEditor,
      refresh,
    ],
  );

  const showProfileForm = mode === "profile" || needsProfile;
  const hasScrollableSubscriptionList = subscriptionStatuses.length > 2;
  const currentProviderLabel = authState?.user
    ? `${providerLabel(authState.user.primary_auth_provider)}${authState.user.is_admin ? t("siteAuth.adminModeSuffix") : ""}`
    : t("siteAuth.emailProvider");
  const profileEditor = showProfileForm ? (
    <div className="mt-5 rounded-[1.5rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.76] p-4">
      {mode === "profile" ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <UserRoundPen className="h-4 w-4 text-[rgb(var(--shiro-accent-rgb)/0.82)]" />
              {authState?.user?.is_admin ? t("siteAuth.editBaseProfile") : t("siteAuth.loginIdentity")}
            </div>
            <div className="mt-1 text-xs text-foreground/46">
              {t("siteAuth.currentLoginMethod", { provider: currentProviderLabel })}
            </div>
          </div>
          <span className="rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.84] px-3 py-1 text-[0.72rem] text-foreground/50">
            {authState?.user?.is_admin
              ? t("siteAuth.adminCommentIdentity")
              : t("siteAuth.emailBackendOnly")}
          </span>
        </div>
      ) : null}

      {mode === "profile" ? (
        <div className="mt-4 rounded-[1.2rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.82] p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-foreground">
                {t("siteAuth.subscriptionList")}
              </div>
            </div>
            {subscriptionLoading ? (
              <Loader2 className="h-4 w-4 animate-spin text-foreground/52" />
            ) : null}
          </div>

          {subscriptionStatuses.length ? (
            <div
              className={`mt-3 space-y-3 ${
                hasScrollableSubscriptionList
                  ? "max-h-[15rem] overflow-y-auto pr-1 snap-y snap-mandatory"
                  : ""
              }`}
            >
              {subscriptionStatuses.map((subscriptionStatus) => {
                const pending =
                  normalizeEmail(subscriptionPendingEmail) ===
                  normalizeEmail(subscriptionStatus.email);
                return (
                  <div
                    key={subscriptionStatus.email}
                    className={`rounded-[1rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.92] p-3 ${
                      hasScrollableSubscriptionList ? "snap-start" : ""
                    }`}
                  >
                    <div className="text-[0.7rem] uppercase tracking-[0.12em] text-foreground/42">
                      {t("siteAuth.subscriptionEmail")}
                    </div>
                    <div className="mt-1 flex flex-wrap items-center justify-between gap-2">
                      <div className="min-w-0 break-all text-sm font-medium text-foreground">
                        {subscriptionStatus.email}
                      </div>
                      <button
                        type="button"
                        onClick={() =>
                          void handleUnsubscribe(subscriptionStatus.email)
                        }
                        disabled={pending}
                        className="inline-flex shrink-0 items-center gap-2 rounded-full border border-rose-500/30 bg-rose-500/8 px-3 py-1.5 text-xs font-medium text-rose-700 transition hover:bg-rose-500/14 disabled:cursor-not-allowed disabled:opacity-60 dark:text-rose-300"
                      >
                        {pending ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : (
                          <BellOff className="h-3.5 w-3.5" />
                        )}
                        {pending ? t("siteAuth.unsubscribing") : t("siteAuth.unsubscribe")}
                      </button>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {subscriptionStatus.content_types.map((contentType) => {
                        const labelKey = CONTENT_TYPE_LABEL_KEYS[contentType];
                        return (
                          <span
                            key={`${subscriptionStatus.email}-${contentType}`}
                            className="rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.82] px-2.5 py-1 text-xs text-foreground/64"
                          >
                            {labelKey ? t(labelKey) : contentType}
                          </span>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="mt-3 rounded-[1rem] border border-dashed border-[rgb(var(--shiro-border-rgb)/0.2)] bg-background/[0.76] px-3 py-2 text-xs text-foreground/56">
              {t("siteAuth.noActiveSubscription")}
            </div>
          )}

          {hasScrollableSubscriptionList ? (
            <div className="mt-2 text-xs text-foreground/42">{t("siteAuth.maxTwoEmailsHint")}</div>
          ) : null}

          {subscriptionFeedback ? (
            <div
              className={`mt-3 rounded-[0.9rem] border px-3 py-2 text-xs ${
                subscriptionFeedback.kind === "success"
                  ? "border-emerald-500/18 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                  : "border-rose-500/18 bg-rose-500/10 text-rose-700 dark:text-rose-300"
              }`}
            >
              {subscriptionFeedback.message}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 space-y-3">
        <label className="block space-y-2">
          <span className="text-xs font-medium uppercase tracking-[0.14em] text-foreground/46">
            {t("siteAuth.username")}
          </span>
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder={
              mode === "profile" ? t("siteAuth.editNickname") : t("siteAuth.firstLoginNickname")
            }
            className="w-full rounded-[1.1rem] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.84] px-4 py-3 text-sm outline-none transition placeholder:text-foreground/34 focus:border-[rgb(var(--shiro-accent-rgb)/0.26)]"
          />
        </label>
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-medium text-foreground/74">{t("siteAuth.selectAvatar")}</div>
          <button
            type="button"
            onClick={() => void handleRefreshAvatars()}
            disabled={avatarLoading || submitting}
            className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.84] px-3 py-1.5 text-xs font-medium text-foreground/58 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] disabled:opacity-60"
          >
            {avatarLoading ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <RefreshCcw className="h-3.5 w-3.5" />
            )}
            {t("siteAuth.refreshBatch")}
          </button>
        </div>
        <div className="grid grid-cols-6 gap-2">
          {avatarCandidates.map((candidate) => {
            const selected = selectedAvatar === candidate.avatar_url;
            return (
              <button
                key={candidate.key}
                type="button"
                onClick={() => setSelectedAvatar(candidate.avatar_url)}
                aria-pressed={selected}
                className={`relative inline-flex h-14 w-14 items-center justify-center rounded-full border transition ${
                  selected
                    ? "border-[rgb(var(--shiro-accent-rgb)/0.38)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] ring-2 ring-[rgb(var(--shiro-accent-rgb)/0.42)] ring-offset-1 ring-offset-background"
                    : "border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.72] hover:border-[rgb(var(--shiro-accent-rgb)/0.24)]"
                }`}
              >
                <img
                  src={candidate.avatar_url}
                  alt={candidate.label}
                  className="h-11 w-11 rounded-full object-cover"
                />
                {selected ? (
                  <span className="absolute -right-0.5 -top-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-[rgb(var(--shiro-accent-rgb)/0.92)] text-white shadow-sm">
                    <Check className="h-3 w-3" />
                  </span>
                ) : null}
              </button>
            );
          })}
        </div>
        <button
          type="button"
          onClick={() =>
            void (mode === "profile"
              ? handleProfileUpdate()
              : handleEmailLogin())
          }
          disabled={submitting || !displayName.trim() || !selectedAvatar}
          className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-[rgb(var(--shiro-accent-rgb)/0.2)] bg-[rgb(var(--shiro-accent-rgb)/0.12)] px-4 py-3 text-sm font-semibold text-[rgb(var(--shiro-accent-rgb)/0.92)] transition hover:bg-[rgb(var(--shiro-accent-rgb)/0.16)] disabled:opacity-60"
        >
          {submitting ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : mode === "profile" ? (
            <UserRoundPen className="h-4 w-4" />
          ) : (
            <Mail className="h-4 w-4" />
          )}
          {mode === "profile" ? t("siteAuth.saveProfile") : t("siteAuth.completeFirstLogin")}
        </button>
      </div>
    </div>
  ) : null;

  const modal =
    typeof document !== "undefined"
      ? createPortal(
          <AnimatePresence>
            {open ? (
              <div className="fixed inset-0 z-[1200] flex items-center justify-center px-4">
                <motion.button
                  type="button"
                  className="absolute inset-0 bg-[rgb(10_15_23/0.28)] backdrop-blur-sm"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={transition({
                    duration: 0.2,
                    reducedMotion: prefersReducedMotion,
                  })}
                  onClick={closeLogin}
                />
                <motion.div
                  initial={{ opacity: 0, y: 16, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: 12, scale: 0.96 }}
                  transition={transition({
                    duration: 0.24,
                    reducedMotion: prefersReducedMotion,
                  })}
                  className="relative w-full max-w-[34rem] overflow-hidden rounded-[2rem] border border-[rgb(var(--shiro-border-rgb)/0.24)] bg-background/[0.88] p-6 shadow-[0_30px_90px_rgb(15_23_42/0.18)] backdrop-blur-2xl dark:bg-card/[0.92]"
                >
                  <div className="absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-[rgb(var(--shiro-glow-rgb)/0.7)] to-transparent" />
                  <div className="absolute -right-10 -top-10 h-40 w-40 rounded-full bg-[radial-gradient(circle,_rgb(255_107_53/0.18),_transparent_68%)]" />
                  <div className="absolute -left-10 bottom-0 h-36 w-36 rounded-full bg-[radial-gradient(circle,_rgb(66_133_244/0.18),_transparent_66%)]" />

                  <div className="relative">
                    <div
                      className={`inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.76] px-3 py-1 text-foreground/46 ${
                        mode === "profile"
                          ? "font-heading text-[0.9rem] italic tracking-[0.08em] text-[rgb(var(--shiro-accent-rgb)/0.84)]"
                          : "text-[0.68rem] uppercase tracking-[0.24em]"
                      }`}
                    >
                      {mode === "profile" ? (
                        <UserRoundPen className="h-3.5 w-3.5" />
                      ) : (
                        <Sparkles className="h-3.5 w-3.5" />
                      )}
                      {mode === "profile" ? t("siteAuth.profileTag") : t("siteAuth.signInTag")}
                    </div>
                    {mode === "profile" ? (
                      <h2 className="mt-4 text-3xl text-foreground">
                        {authState?.user?.is_admin ? t("siteAuth.updateBaseProfile") : t("siteAuth.visitorProfile")}
                      </h2>
                    ) : null}

                    {mode === "profile" ? null : (
                      <div className="mt-6 grid gap-3 sm:grid-cols-2">
                        {(["google", "github"] as const).map((provider) => {
                          const Icon = providerIcon(provider);
                          const enabled = enabledOAuthProviderSet.has(provider);
                          return (
                            <button
                              key={provider}
                              type="button"
                              onClick={enabled ? () => void handleOAuthLogin(provider) : undefined}
                              disabled={submitting || !enabled}
                              className={`group relative overflow-hidden rounded-[1.35rem] border px-4 py-4 text-left transition ${
                                enabled
                                  ? "border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.8] hover:border-[rgb(var(--shiro-accent-rgb)/0.26)] hover:bg-background/[0.9] disabled:opacity-60"
                                  : "border-[rgb(var(--shiro-border-rgb)/0.1)] bg-foreground/[0.04] opacity-55 cursor-not-allowed"
                              }`}
                            >
                              {enabled ? (
                                <div
                                  className="absolute inset-0 opacity-0 transition group-hover:opacity-100"
                                  style={{
                                    background:
                                      "linear-gradient(135deg, rgb(66 133 244 / 0.12), rgb(234 67 53 / 0.08), rgb(251 188 5 / 0.08), rgb(52 168 83 / 0.12))",
                                  }}
                                />
                              ) : null}
                              <div className="relative flex items-center gap-3">
                                <span className={`inline-flex h-10 w-10 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] ${
                                  enabled ? "bg-white/80 text-foreground/78" : "bg-foreground/[0.06] text-foreground/32"
                                }`}>
                                  <Icon className="h-4 w-4" />
                                </span>
                                <div>
                                  <div className={`text-sm font-semibold ${enabled ? "text-foreground" : "text-foreground/42"}`}>
                                    {providerLabel(provider)}
                                  </div>
                                  <div className={`text-xs ${enabled ? "text-foreground/46" : "text-foreground/32"}`}>
                                    {enabled
                                      ? t("siteAuth.useThirdPartyDirect")
                                      : t("siteAuth.providerDisabled", { provider: providerLabel(provider) })}
                                  </div>
                                </div>
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    )}

                    {mode === "profile" ? (
                      profileEditor
                    ) : dialogEmailLoginEnabled ? (
                      <div className="mt-5 rounded-[1.5rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.76] p-4">
                        <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
                          <Mail className="h-4 w-4 text-[rgb(var(--shiro-accent-rgb)/0.82)]" />
                          {t("siteAuth.emailIdentityLogin")}
                        </div>
                        <div className="mt-4 space-y-3">
                          <input
                            type="email"
                            value={email}
                            onChange={(event) => {
                              setEmail(event.target.value);
                              if (requiresAdminPassword) {
                                setRequiresAdminPassword(false);
                                setAdminPassword("");
                              }
                            }}
                            placeholder={t("siteAuth.emailIdentityPlaceholder")}
                            className="w-full rounded-[1.1rem] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.84] px-4 py-3 text-sm outline-none transition placeholder:text-foreground/34 focus:border-[rgb(var(--shiro-accent-rgb)/0.26)]"
                          />
                          {requiresAdminPassword ? (
                            <>
                              <div className="rounded-[1rem] border border-[rgb(var(--shiro-accent-rgb)/0.16)] bg-[rgb(var(--shiro-accent-rgb)/0.08)] px-4 py-3 text-xs leading-6 text-foreground/66">
                                {t("siteAuth.adminPasswordHint")}
                              </div>
                              <input
                                type="password"
                                value={adminPassword}
                                onChange={(event) =>
                                  setAdminPassword(event.target.value)
                                }
                                placeholder={t("siteAuth.adminPasswordPlaceholder")}
                                className="w-full rounded-[1.1rem] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.84] px-4 py-3 text-sm outline-none transition placeholder:text-foreground/34 focus:border-[rgb(var(--shiro-accent-rgb)/0.26)]"
                              />
                            </>
                          ) : null}
                          {!needsProfile ? (
                            <button
                              type="button"
                              onClick={() => void handleEmailLogin()}
                              disabled={
                                submitting ||
                                !email.trim() ||
                                (requiresAdminPassword &&
                                  !adminPassword.trim())
                              }
                              className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-[rgb(var(--shiro-accent-rgb)/0.2)] bg-[rgb(var(--shiro-accent-rgb)/0.12)] px-4 py-3 text-sm font-semibold text-[rgb(var(--shiro-accent-rgb)/0.92)] transition hover:bg-[rgb(var(--shiro-accent-rgb)/0.16)] disabled:opacity-60"
                            >
                              {submitting ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : requiresAdminPassword ? (
                                <Lock className="h-4 w-4" />
                              ) : (
                                <Mail className="h-4 w-4" />
                              )}
                              {requiresAdminPassword
                                ? t("siteAuth.verifyPasswordAndLogin")
                                : t("siteAuth.continueWithEmail")}
                            </button>
                          ) : null}
                        </div>
                        {profileEditor}
                      </div>
                    ) : null}

                    {error ? (
                      <div className="mt-4 rounded-2xl border border-rose-500/16 bg-rose-500/8 px-4 py-3 text-sm text-rose-700 dark:text-rose-300">
                        {error}
                      </div>
                    ) : null}
                  </div>
                </motion.div>
              </div>
            ) : null}
          </AnimatePresence>,
          document.body,
        )
      : null;

  return (
    <SiteAuthContext.Provider value={value}>
      {children}
      {modal}
    </SiteAuthContext.Provider>
  );
}
