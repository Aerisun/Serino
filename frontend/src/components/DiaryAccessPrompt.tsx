import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { Lock, Send, X } from "lucide-react";
import {
  createPostAccessRequestApiV1SitePostAccessSlugRequestsPost,
  createDiaryAccessRequestApiV1SiteDiaryAccessRequestsPost,
  getReadMyPostAccessApiV1SitePostAccessSlugMeGetQueryKey,
  getReadMyDiaryAccessApiV1SiteDiaryAccessMeGetQueryKey,
  readMyPostAccessApiV1SitePostAccessSlugMeGet,
  readMyDiaryAccessApiV1SiteDiaryAccessMeGet,
} from "@serino/api-client/site";
import { normalizeErrorMessage } from "@serino/api-client";
import { useQueryClient } from "@tanstack/react-query";
import { useFrontendI18n } from "@/i18n";
import { useSiteAuth } from "@/contexts/use-site-auth";

type ToastKind = "info" | "success" | "error";
type ToastActionType = "request" | "login";

interface ToastState {
  kind: ToastKind;
  message: string;
  actionLabel?: string;
  actionType?: ToastActionType;
}

interface UseDiaryAccessPromptOptions {
  diaryPrivateEnabled?: boolean;
  postApprovalEnabled?: boolean;
  postSlug?: string;
}

interface AccessState {
  authenticated: boolean;
  has_access: boolean;
  owner_name?: string;
  mail_feedback_available?: boolean;
  diary_private_enabled?: boolean;
  requires_approval?: boolean;
}

const ACTION_TOAST_DURATION_MS = 2000;
const PASSIVE_TOAST_DURATION_MS = 3600;

const toastToneClass: Record<ToastKind, string> = {
  info: "border-[rgb(var(--shiro-border-rgb)/0.30)] bg-[rgb(var(--shiro-panel-rgb)/0.88)] text-foreground dark:border-sky-200/20 dark:bg-slate-950/88 dark:text-sky-50",
  success: "border-emerald-500/28 bg-emerald-500/14 text-emerald-900 dark:border-emerald-300/30 dark:bg-emerald-950/70 dark:text-emerald-50",
  error: "border-[rgba(225,29,72,0.64)] bg-[linear-gradient(135deg,rgb(255_241_242/0.98),rgb(255_228_230/0.94)_58%,rgb(255_255_255/0.88))] text-rose-950 shadow-[0_22px_70px_rgba(225,29,72,0.26),inset_0_0_0_1px_rgba(225,29,72,0.12),inset_0_1px_0_rgba(255,255,255,0.72)] dark:border-[rgba(255,205,215,0.72)] dark:bg-[linear-gradient(135deg,rgb(127_29_54/0.98),rgb(76_18_42/0.98)_52%,rgb(16_8_14/0.98))] dark:text-rose-50 dark:shadow-[0_30px_88px_rgba(244,63,94,0.38),inset_0_0_0_1px_rgba(255,255,255,0.12),inset_0_1px_0_rgba(255,255,255,0.16)]",
};

const toastIconToneClass: Record<ToastKind, string> = {
  info: "text-[rgb(var(--shiro-accent-rgb)/0.78)] dark:text-sky-200/82",
  success: "text-emerald-600/80 dark:text-emerald-200/88",
  error: "text-rose-800 dark:text-rose-100",
};

const toastActionToneClass: Record<ToastKind, string> = {
  info: "border-[rgb(var(--shiro-border-rgb)/0.22)] bg-background/45 text-foreground/72 hover:border-[rgb(var(--shiro-border-rgb)/0.36)] hover:text-[rgb(var(--shiro-accent-rgb)/0.86)] dark:border-sky-100/20 dark:bg-sky-100/10 dark:text-sky-50/86 dark:hover:border-sky-100/34 dark:hover:bg-sky-100/16",
  success: "border-emerald-500/24 bg-emerald-500/12 text-emerald-900/82 hover:border-emerald-500/38 hover:bg-emerald-500/18 dark:border-emerald-200/24 dark:bg-emerald-200/10 dark:text-emerald-50/86 dark:hover:bg-emerald-200/16",
  error: "border-[rgba(225,29,72,0.62)] bg-rose-100/82 font-semibold text-rose-950 shadow-[0_10px_28px_rgba(225,29,72,0.16)] hover:border-[rgba(190,18,60,0.78)] hover:bg-rose-200/88 dark:border-rose-100/54 dark:bg-rose-100/20 dark:text-rose-50 dark:shadow-[0_12px_34px_rgba(244,63,94,0.28)] dark:hover:border-rose-100/78 dark:hover:bg-rose-100/30",
};

const isAxiosErrorLike = (
  error: unknown,
): error is { isAxiosError: true; response?: { status?: number; data?: { detail?: unknown; message?: unknown } } } =>
  typeof error === "object" &&
  error !== null &&
  (error as { isAxiosError?: unknown }).isAxiosError === true;

export const getDiaryAccessErrorStatus = (error: unknown) =>
  isAxiosErrorLike(error) ? error.response?.status : undefined;

export const getDiaryAccessErrorMessage = (error: unknown) => {
  if (isAxiosErrorLike(error)) {
    const detail = error.response?.data;
    return normalizeErrorMessage(detail?.detail) ?? normalizeErrorMessage(detail?.message) ?? error.message;
  }
  return error instanceof Error && error.message.trim() ? error.message : "";
};

export function useDiaryAccessPrompt(options: UseDiaryAccessPromptOptions = {}) {
  const { t } = useFrontendI18n();
  const { openLogin } = useSiteAuth();
  const queryClient = useQueryClient();
  const [toast, setToast] = useState<ToastState | null>(null);
  const [requestOpen, setRequestOpen] = useState(false);
  const [reason, setReason] = useState("");
  const [feedback, setFeedback] = useState<{ kind: "success" | "error"; message: string } | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [mailFeedbackAvailable, setMailFeedbackAvailable] = useState(false);
  const toastTimerRef = useRef<number | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const isPostAccess = Boolean(options.postSlug);
  const featureEnabled = isPostAccess
    ? options.postApprovalEnabled !== false
    : options.diaryPrivateEnabled !== false;
  const accessKey = useCallback(
    (key: string) => `${isPostAccess ? "postAccess" : "diaryAccess"}.${key}`,
    [isPostAccess],
  );

  useEffect(() => {
    return () => {
      if (toastTimerRef.current !== null) {
        window.clearTimeout(toastTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    if (!requestOpen) {
      return;
    }
    const timer = window.setTimeout(() => textareaRef.current?.focus(), 120);
    return () => window.clearTimeout(timer);
  }, [requestOpen]);

  const pushToast = useCallback((kind: ToastKind, message: string, actionLabel?: string, actionType?: ToastActionType) => {
    setToast({ kind, message, actionLabel, actionType });
    if (toastTimerRef.current !== null) {
      window.clearTimeout(toastTimerRef.current);
    }
    toastTimerRef.current = window.setTimeout(() => {
      setToast(null);
      toastTimerRef.current = null;
    }, actionLabel ? ACTION_TOAST_DURATION_MS : PASSIVE_TOAST_DURATION_MS);
  }, []);

  const refreshDiaryAccessState = useCallback(async (): Promise<{ data: AccessState }> => {
    if (isPostAccess && options.postSlug) {
      const response = await readMyPostAccessApiV1SitePostAccessSlugMeGet(options.postSlug);
      queryClient.setQueryData(
        getReadMyPostAccessApiV1SitePostAccessSlugMeGetQueryKey(options.postSlug),
        response,
      );
      const data = response.data as unknown as AccessState;
      setMailFeedbackAvailable(Boolean(data.mail_feedback_available));
      return { data };
    }
    const response = await readMyDiaryAccessApiV1SiteDiaryAccessMeGet();
    queryClient.setQueryData(getReadMyDiaryAccessApiV1SiteDiaryAccessMeGetQueryKey(), response);
    const data = response.data as unknown as AccessState;
    setMailFeedbackAvailable(Boolean(data.mail_feedback_available));
    return { data };
  }, [isPostAccess, options.postSlug, queryClient]);

  useEffect(() => {
    if (!requestOpen || !featureEnabled) {
      return;
    }
    void refreshDiaryAccessState().catch(() => {
      setMailFeedbackAvailable(false);
    });
  }, [featureEnabled, refreshDiaryAccessState, requestOpen]);

  const showLoginRequired = useCallback(() => {
    pushToast("error", t(accessKey("loginRequired")), t("navbar.login"), "login");
  }, [accessKey, pushToast, t]);

  const showNoAccess = useCallback(
    (ownerName?: string) => {
      pushToast(
        "error",
        t(accessKey("noPermission"), { username: ownerName || t(accessKey("defaultOwner")) }),
        t(accessKey("apply")),
        "request",
      );
    },
    [accessKey, pushToast, t],
  );

  const ensureDiaryAccess = useCallback(async () => {
    if (!featureEnabled) {
      return true;
    }
    try {
      const response = await refreshDiaryAccessState();
      const state = response.data;
      const requiresApproval = isPostAccess
        ? Boolean(state.requires_approval)
        : Boolean(state.diary_private_enabled);
      if (!requiresApproval || state.has_access) {
        return true;
      }
      if (!state.authenticated) {
        showLoginRequired();
        return false;
      }
      showNoAccess(state.owner_name);
      return false;
    } catch {
      pushToast("error", t(accessKey("checkFailed")));
      return false;
    }
  }, [accessKey, featureEnabled, isPostAccess, pushToast, refreshDiaryAccessState, showLoginRequired, showNoAccess, t]);

  const showBlockedFromError = useCallback(
    (status: number | undefined, detail?: string) => {
      if (status === 401) {
        showLoginRequired();
        return;
      }
      if (status === 403) {
        pushToast("error", detail || t(accessKey("noPermission"), { username: t(accessKey("defaultOwner")) }), t(accessKey("apply")), "request");
      }
    },
    [accessKey, pushToast, showLoginRequired, t],
  );

  const closeRequest = useCallback(() => {
    setRequestOpen(false);
    setFeedback(null);
  }, []);

  const openLoginDialog = useCallback(() => {
    setToast(null);
    openLogin();
  }, [openLogin]);

  const submitRequest = useCallback(async () => {
    const normalizedReason = reason.trim();
    if (!normalizedReason) {
      setFeedback({ kind: "error", message: t(accessKey("reasonRequired")) });
      return;
    }
    setSubmitting(true);
    setFeedback(null);
    try {
      if (isPostAccess && options.postSlug) {
        await createPostAccessRequestApiV1SitePostAccessSlugRequestsPost(options.postSlug, {
          reason: normalizedReason,
        });
      } else {
        await createDiaryAccessRequestApiV1SiteDiaryAccessRequestsPost({ reason: normalizedReason });
      }
      await queryClient.invalidateQueries({
        queryKey: isPostAccess && options.postSlug
          ? getReadMyPostAccessApiV1SitePostAccessSlugMeGetQueryKey(options.postSlug)
          : getReadMyDiaryAccessApiV1SiteDiaryAccessMeGetQueryKey(),
      });
      setReason("");
      setRequestOpen(false);
      pushToast("success", t(accessKey("requestSubmitted")));
    } catch (error) {
      const message = getDiaryAccessErrorMessage(error) || t(accessKey("requestFailed"));
      setFeedback({ kind: "error", message });
      pushToast("error", message);
    } finally {
      setSubmitting(false);
    }
  }, [accessKey, isPostAccess, options.postSlug, pushToast, queryClient, reason, t]);

  const promptNode: ReactNode =
    typeof document !== "undefined"
      ? createPortal(
          <>
            <AnimatePresence>
              {toast ? (
                <motion.div
                  initial={{ opacity: 0, y: -12, scale: 0.96 }}
                  animate={{ opacity: 1, y: 0, scale: 1 }}
                  exit={{ opacity: 0, y: -10, scale: 0.96 }}
                  transition={{ duration: 0.2 }}
                  className={`fixed right-4 top-4 z-[1300] w-fit max-w-[calc(100vw-2rem)] rounded-2xl border py-3 pl-4 pr-7 text-sm shadow-[0_16px_44px_rgba(15,23,42,0.18)] backdrop-blur-xl ${toastToneClass[toast.kind]}`}
                  role="status"
                  aria-live="polite"
                >
                  <div className="flex items-start gap-3">
                    <Lock className={`mt-0.5 h-4 w-4 shrink-0 ${toastIconToneClass[toast.kind]}`} />
                    <div className="min-w-0">
                      <p className="max-w-[min(72vw,24rem)] leading-relaxed">{toast.message}</p>
                      {toast.actionLabel ? (
                        <button
                          type="button"
                          onClick={() => {
                            if (toast.actionType === "login") {
                              openLoginDialog();
                            } else {
                              void refreshDiaryAccessState().catch(() => undefined);
                              setRequestOpen(true);
                              setToast(null);
                            }
                          }}
                          className={`mx-auto mt-2 flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs transition ${toastActionToneClass[toast.kind]}`}
                        >
                          <Send className="h-3 w-3" />
                          {toast.actionLabel}
                        </button>
                      ) : null}
                    </div>
                  </div>
                </motion.div>
              ) : null}
            </AnimatePresence>

            <AnimatePresence>
              {requestOpen ? (
                <motion.div
                  className="fixed inset-0 z-[1250] flex items-start justify-center overflow-y-auto px-4 pb-10 pt-[calc(env(safe-area-inset-top)+5rem)] sm:pt-[12vh]"
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  exit={{ opacity: 0 }}
                  transition={{ duration: 0.18 }}
                >
                  <button
                    type="button"
                    className="fixed inset-0 bg-background/70 backdrop-blur-sm"
                    onClick={closeRequest}
                    aria-label={t("common.close")}
                  />
                  <motion.div
                    initial={{ opacity: 0, y: -18, scale: 0.97 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    exit={{ opacity: 0, y: -18, scale: 0.97 }}
                    transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
                    className={`relative z-10 w-full max-w-lg overflow-hidden rounded-[26px] border liquid-glass shadow-[0_24px_70px_rgba(15,23,42,0.18)] ${isPostAccess ? "border-sky-400/42 shadow-[0_24px_70px_rgba(14,165,233,0.2)]" : "border-[rgb(var(--shiro-border-rgb)/0.24)]"}`}
                  >
                    <div className="flex items-center justify-between border-b border-[rgb(var(--shiro-divider-rgb)/0.22)] px-5 py-4">
                      <div>
                        <h2 className="text-base font-heading leading-6 text-foreground/86">
                          {mailFeedbackAvailable
                            ? t(accessKey("requestTitleWithMailFeedback"))
                            : t(accessKey("requestTitle"))}
                        </h2>
                      </div>
                      <button
                        type="button"
                        onClick={closeRequest}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-full text-foreground/35 transition hover:bg-foreground/[0.06] hover:text-foreground/70"
                        aria-label={t("common.close")}
                      >
                        <X className="h-4 w-4" />
                      </button>
                    </div>
                    <div className="px-5 py-5">
                      <label className="text-xs font-body text-foreground/48" htmlFor={isPostAccess ? "post-access-reason" : "diary-access-reason"}>
                        {t(accessKey("reasonLabel"))}
                      </label>
                      <textarea
                        id={isPostAccess ? "post-access-reason" : "diary-access-reason"}
                        ref={textareaRef}
                        value={reason}
                        maxLength={1000}
                        onChange={(event) => setReason(event.target.value)}
                        placeholder={t(accessKey("reasonPlaceholder"))}
                        className={`mt-2 min-h-36 w-full resize-none rounded-2xl border bg-foreground/[0.03] px-4 py-3 text-sm leading-6 text-foreground outline-none transition placeholder:text-foreground/25 focus:bg-[rgb(var(--shiro-panel-rgb)/0.34)] ${isPostAccess ? "border-sky-400/24 focus:border-sky-400/60" : "border-[rgb(var(--shiro-border-rgb)/0.18)] focus:border-[rgb(var(--shiro-border-rgb)/0.34)]"}`}
                      />
                      <div className="mt-2 flex items-center justify-between gap-3">
                        <p className={`text-xs ${feedback?.kind === "error" ? "text-rose-500/82" : "text-emerald-500/82"}`}>
                          {feedback?.message ?? ""}
                        </p>
                        <span className="shrink-0 text-[11px] text-foreground/28">{reason.length}/1000</span>
                      </div>
                      <div className="mt-5 flex justify-end gap-2">
                        <button
                          type="button"
                          onClick={closeRequest}
                          className="rounded-full px-4 py-2 text-sm text-foreground/45 transition hover:bg-foreground/[0.05] hover:text-foreground/72"
                        >
                          {t(accessKey("cancel"))}
                        </button>
                        <button
                          type="button"
                          disabled={submitting}
                          onClick={submitRequest}
                          className={`inline-flex items-center gap-2 rounded-full border px-4 py-2 text-sm transition disabled:cursor-not-allowed disabled:opacity-55 ${isPostAccess ? "border-sky-400/36 bg-sky-500/14 text-sky-700 hover:border-sky-400/58 hover:bg-sky-500/22 dark:text-sky-100" : "border-[rgb(var(--shiro-border-rgb)/0.22)] bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.9)] hover:border-[rgb(var(--shiro-border-rgb)/0.36)] hover:bg-[rgb(var(--shiro-accent-rgb)/0.18)]"}`}
                        >
                          <Send className="h-4 w-4" />
                          {submitting ? t(accessKey("submitting")) : t(accessKey("submit"))}
                        </button>
                      </div>
                    </div>
                  </motion.div>
                </motion.div>
              ) : null}
            </AnimatePresence>
          </>,
          document.body,
        )
      : null;

  return {
    promptNode,
    ensureDiaryAccess,
    showBlockedFromError,
    openLoginDialog,
    openRequestDialog: () => {
      void refreshDiaryAccessState().catch(() => undefined);
      setRequestOpen(true);
    },
  };
}
