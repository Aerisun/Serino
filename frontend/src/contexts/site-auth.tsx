import {
  useCallback,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import {
  Check,
  BellOff,
  Github,
  Loader2,
  Mail,
  RefreshCcw,
  Sparkles,
  UserRoundPen,
} from "lucide-react";
import { transition } from "@/config";
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

const CONTENT_TYPE_LABELS: Record<string, string> = {
  posts: "文章",
  diary: "日记",
  thoughts: "想法",
  excerpts: "摘录",
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
  const [authState, setAuthState] = useState<SiteAuthState | null>(null);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(false);
  const [mode, setMode] = useState<AuthDialogMode>("login");
  const [submitting, setSubmitting] = useState(false);
  const [avatarLoading, setAvatarLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [allowEmailLoginInDialog, setAllowEmailLoginInDialog] = useState(true);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [avatarCandidates, setAvatarCandidates] = useState<
    SiteAuthAvatarCandidate[]
  >([]);
  const [selectedAvatar, setSelectedAvatar] = useState("");
  const [avatarBatch, setAvatarBatch] = useState(0);
  const [_avatarTotalBatches, setAvatarTotalBatches] = useState(1);
  const [needsProfile, setNeedsProfile] = useState(false);
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

  const resetForm = useCallback(() => {
    setError(null);
    setAllowEmailLoginInDialog(true);
    setEmail("");
    setNeedsProfile(false);
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
      const nextCandidates =
        preferredAvatar &&
        !result.avatar_candidates.some(
          (candidate) => candidate.avatar_url === preferredAvatar,
        )
          ? [
              {
                key: `current:${preferredAvatar}`,
                label: "当前头像",
                avatar_url: preferredAvatar,
              },
              ...result.avatar_candidates,
            ]
          : result.avatar_candidates;
      const visibleCandidates = nextCandidates.slice(
        0,
        PROFILE_AVATAR_PICKER_COUNT,
      );

      setAvatarCandidates(visibleCandidates);
      setAvatarBatch(result.batch);
      setAvatarTotalBatches(result.total_batches);
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
    [],
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
        setError(err instanceof Error ? err.message : "头像加载失败");
      } finally {
        setAvatarLoading(false);
      }
    },
    [applyAvatarBatch],
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
        message: err instanceof Error ? err.message : "订阅列表加载失败",
      });
    } finally {
      setSubscriptionLoading(false);
    }
  }, []);

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
          ? `订阅列表已加入 ${detail.email}。`
          : `${detail.email} 已从订阅列表移除。`,
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
  }, []);

  const handleEmailLogin = useCallback(async () => {
    setSubmitting(true);
    setError(null);
    try {
      const payload: {
        email: string;
        display_name?: string;
        avatar_url?: string;
      } = { email };

      if (needsProfile) {
        payload.display_name = displayName;
        payload.avatar_url = selectedAvatar;
      }

      const result = await loginWithEmail(payload);
      if (result.requires_profile) {
        setNeedsProfile(true);
        setMode("login");
        setDisplayName(result.suggested_display_name || "");
        applyAvatarBatch({
          batch: result.avatar_batch,
          total_batches: result.avatar_total_batches,
          avatar_candidates: result.avatar_candidates,
        });
        return;
      }

      setAuthState((current) => ({
        authenticated: true,
        email_login_enabled: current?.email_login_enabled ?? true,
        oauth_providers: current?.oauth_providers ?? [],
        user: result.user,
      }));
      closeLogin();
    } catch (err) {
      setError(err instanceof Error ? err.message : "登录失败");
    } finally {
      setSubmitting(false);
    }
  }, [
    applyAvatarBatch,
    closeLogin,
    displayName,
    email,
    needsProfile,
    selectedAvatar,
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
      setError(err instanceof Error ? err.message : "资料更新失败");
    } finally {
      setSubmitting(false);
    }
  }, [closeLogin, displayName, selectedAvatar]);

  const handleRefreshAvatars = useCallback(async () => {
    const identity =
      mode === "profile" ? (authState?.user?.email ?? "") : email;
    if (!identity.trim()) {
      setError("请先输入邮箱。");
      return;
    }
    await loadAvatarBatch(identity, avatarBatch + 1);
  }, [authState?.user?.email, avatarBatch, email, loadAvatarBatch, mode]);

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
      setError(err instanceof Error ? err.message : "登录失败");
      setSubmitting(false);
    }
  }, []);

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
        message: `${targetEmail} 取消订阅成功。`,
      });
    } catch (err) {
      setSubscriptionFeedback({
        kind: "error",
        message: err instanceof Error ? err.message : "取消订阅失败",
      });
    } finally {
      setSubscriptionPendingEmail(null);
    }
  }, []);

  const logout = useCallback(async () => {
    await logoutSiteAuth();
    setAuthState((current) => ({
      authenticated: false,
      email_login_enabled: current?.email_login_enabled ?? true,
      oauth_providers: current?.oauth_providers ?? [],
      user: null,
    }));
  }, []);

  const dialogEmailLoginEnabled =
    Boolean(authState?.email_login_enabled) && allowEmailLoginInDialog;

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
    ? `${providerLabel(authState.user.primary_auth_provider)}${authState.user.is_admin ? " · 管理员模式" : ""}`
    : "邮箱";
  const profileEditor = showProfileForm ? (
    <div className="mt-5 rounded-[1.5rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.76] p-4">
      {mode === "profile" ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="flex items-center gap-2 text-sm font-semibold text-foreground">
              <UserRoundPen className="h-4 w-4 text-[rgb(var(--shiro-accent-rgb)/0.82)]" />
              {authState?.user?.is_admin ? "修改基础资料" : "登录身份"}
            </div>
            <div className="mt-1 text-xs text-foreground/46">
              当前登录方式：{currentProviderLabel}
            </div>
          </div>
          <span className="rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.84] px-3 py-1 text-[0.72rem] text-foreground/50">
            {authState?.user?.is_admin
              ? "管理员评论将固定使用站点身份"
              : "邮箱仅用于后台识别"}
          </span>
        </div>
      ) : null}

      {mode === "profile" ? (
        <div className="mt-4 rounded-[1.2rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.82] p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="text-sm font-semibold text-foreground">
                订阅列表
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
                      订阅邮箱
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
                        {pending ? "取消中..." : "取消订阅"}
                      </button>
                    </div>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {subscriptionStatus.content_types.map((contentType) => (
                        <span
                          key={`${subscriptionStatus.email}-${contentType}`}
                          className="rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.82] px-2.5 py-1 text-xs text-foreground/64"
                        >
                          {CONTENT_TYPE_LABELS[contentType] ?? contentType}
                        </span>
                      ))}
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <div className="mt-3 rounded-[1rem] border border-dashed border-[rgb(var(--shiro-border-rgb)/0.2)] bg-background/[0.76] px-3 py-2 text-xs text-foreground/56">
              当前没有活跃订阅。可在站点右上角的“订阅”按钮中添加。
            </div>
          )}

          {hasScrollableSubscriptionList ? (
            <div className="mt-2 text-xs text-foreground/42">最多显示两个邮箱，可上下滚动查看更多。</div>
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
            用户名
          </span>
          <input
            value={displayName}
            onChange={(event) => setDisplayName(event.target.value)}
            placeholder={
              mode === "profile" ? "修改显示昵称" : "首次登录时设置一个显示昵称"
            }
            className="w-full rounded-[1.1rem] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.84] px-4 py-3 text-sm outline-none transition placeholder:text-foreground/34 focus:border-[rgb(var(--shiro-accent-rgb)/0.26)]"
          />
        </label>
        <div className="flex items-center justify-between gap-3">
          <div className="text-sm font-medium text-foreground/74">选择头像</div>
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
            换一批
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
          {mode === "profile" ? "保存资料" : "完成首次登录"}
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
                      {mode === "profile" ? "PROFILE" : "Sign In"}
                    </div>
                    <h2 className="mt-4 font-display text-3xl text-foreground">
                      {mode === "profile"
                        ? authState?.user?.is_admin
                          ? "更新基础资料"
                          : "访客资料"
                        : "进入评论身份"}
                    </h2>
                    {mode === "profile" ? null : (
                      <p className="mt-2 max-w-[28rem] text-sm leading-6 text-foreground/52">
                        登录后评论会使用你的固定昵称和头像。邮箱只作为后台识别标识，不会公开显示。
                      </p>
                    )}

                    {mode === "profile" ? null : (
                      <div className="mt-6 grid gap-3 sm:grid-cols-2">
                        {(authState?.oauth_providers ?? []).map((provider) => {
                          const Icon = providerIcon(provider);
                          return (
                            <button
                              key={provider}
                              type="button"
                              onClick={() => void handleOAuthLogin(provider)}
                              disabled={submitting}
                              className="group relative overflow-hidden rounded-[1.35rem] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.8] px-4 py-4 text-left transition hover:border-[rgb(var(--shiro-accent-rgb)/0.26)] hover:bg-background/[0.9] disabled:opacity-60"
                            >
                              <div
                                className="absolute inset-0 opacity-0 transition group-hover:opacity-100"
                                style={{
                                  background:
                                    "linear-gradient(135deg, rgb(66 133 244 / 0.12), rgb(234 67 53 / 0.08), rgb(251 188 5 / 0.08), rgb(52 168 83 / 0.12))",
                                }}
                              />
                              <div className="relative flex items-center gap-3">
                                <span className="inline-flex h-10 w-10 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-white/80 text-foreground/78">
                                  <Icon className="h-4 w-4" />
                                </span>
                                <div>
                                  <div className="text-sm font-semibold text-foreground">
                                    {providerLabel(provider)}
                                  </div>
                                  <div className="text-xs text-foreground/46">
                                    使用第三方资料直接进入
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
                          邮箱识别登录
                        </div>
                        <div className="mt-4 space-y-3">
                          <input
                            type="email"
                            value={email}
                            onChange={(event) => setEmail(event.target.value)}
                            placeholder="输入邮箱作为身份标识"
                            className="w-full rounded-[1.1rem] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.84] px-4 py-3 text-sm outline-none transition placeholder:text-foreground/34 focus:border-[rgb(var(--shiro-accent-rgb)/0.26)]"
                          />
                          {!needsProfile ? (
                            <button
                              type="button"
                              onClick={() => void handleEmailLogin()}
                              disabled={submitting || !email.trim()}
                              className="inline-flex w-full items-center justify-center gap-2 rounded-full border border-[rgb(var(--shiro-accent-rgb)/0.2)] bg-[rgb(var(--shiro-accent-rgb)/0.12)] px-4 py-3 text-sm font-semibold text-[rgb(var(--shiro-accent-rgb)/0.92)] transition hover:bg-[rgb(var(--shiro-accent-rgb)/0.16)] disabled:opacity-60"
                            >
                              {submitting ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <Mail className="h-4 w-4" />
                              )}
                              继续使用邮箱
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
