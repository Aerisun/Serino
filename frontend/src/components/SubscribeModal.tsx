import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { BellRing, Check, Copy, ExternalLink, Mail, Rss, X } from "lucide-react";
import { subscribeToContentApiV1SiteSubscriptionsPost } from "@serino/api-client/site";
import { trackSubscriptionEmail } from "@/lib/subscription-tracker";

const CONTENT_OPTIONS = [
  { key: "posts", label: "文章", feedPath: "/feeds/posts.xml" },
  { key: "diary", label: "日记", feedPath: "/feeds/diary.xml" },
  { key: "thoughts", label: "想法", feedPath: "/feeds/thoughts.xml" },
  { key: "excerpts", label: "摘录", feedPath: "/feeds/excerpts.xml" },
] as const;

type ContentType = (typeof CONTENT_OPTIONS)[number]["key"];

interface SubscribeModalProps {
  open: boolean;
  onClose: () => void;
  enabled: boolean;
}

interface SubscriptionChangedDetail {
  email: string;
  content_types: string[];
  subscribed: boolean;
}

interface SubscriptionSuccessPayload {
  email: string;
  content_types: string[];
  subscribed?: boolean;
}

const isSubscriptionSuccessPayload = (
  value: unknown,
): value is SubscriptionSuccessPayload => {
  if (!value || typeof value !== "object") {
    return false;
  }
  const payload = value as {
    email?: unknown;
    content_types?: unknown;
    subscribed?: unknown;
  };
  return (
    typeof payload.email === "string" &&
    Array.isArray(payload.content_types) &&
    payload.content_types.every((item) => typeof item === "string") &&
    (payload.subscribed === undefined || typeof payload.subscribed === "boolean")
  );
};

const SubscribeModal = ({ open, onClose, enabled }: SubscribeModalProps) => {
  const [email, setEmail] = useState("");
  const [selectedTypes, setSelectedTypes] = useState<ContentType[]>(
    CONTENT_OPTIONS.map((item) => item.key),
  );
  const [submitting, setSubmitting] = useState(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);
  const [toast, setToast] = useState<{
    kind: "success" | "error";
    message: string;
  } | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const toastTimerRef = useRef<number | null>(null);

  const feedLinks = useMemo(() => {
    const origin =
      typeof window !== "undefined"
        ? window.location.origin.replace(/\/+$/, "")
        : "";
    return CONTENT_OPTIONS.map((item) => ({
      ...item,
      url: `${origin}${item.feedPath}`,
    }));
  }, []);

  useEffect(() => {
    if (!open) return;
    setEmail("");
    setSelectedTypes(CONTENT_OPTIONS.map((item) => item.key));
    setCopiedKey(null);
    setFeedback(null);
    setToast(null);
    const timer = window.setTimeout(() => inputRef.current?.focus(), 100);
    return () => window.clearTimeout(timer);
  }, [open]);

  useEffect(() => {
    return () => {
      if (toastTimerRef.current !== null) {
        window.clearTimeout(toastTimerRef.current);
      }
    };
  }, []);

  const pushToast = useCallback((kind: "success" | "error", message: string) => {
    setToast({ kind, message });
    if (toastTimerRef.current !== null) {
      window.clearTimeout(toastTimerRef.current);
    }
    toastTimerRef.current = window.setTimeout(() => {
      setToast(null);
      toastTimerRef.current = null;
    }, 3200);
  }, []);

  useEffect(() => {
    if (!open) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onClose();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  const toggleType = (key: ContentType) => {
    setSelectedTypes((current) =>
      current.includes(key)
        ? current.filter((item) => item !== key)
        : [...current, key],
    );
  };

  const handleCopy = async (key: string, url: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedKey(key);
      window.setTimeout(() => {
        setCopiedKey((current) => (current === key ? null : current));
      }, 1600);
    } catch {
      setFeedback({ kind: "error", message: "复制失败，请手动复制。" });
    }
  };

  const handleSubmit = async () => {
    if (!enabled) {
      const message = "邮箱订阅暂未开放，敬请期待。";
      setFeedback({ kind: "error", message });
      pushToast("error", message);
      return;
    }

    if (!email.trim()) {
      const message = "请输入邮箱。";
      setFeedback({ kind: "error", message });
      pushToast("error", message);
      return;
    }
    if (selectedTypes.length === 0) {
      const message = "至少选择一项内容。";
      setFeedback({ kind: "error", message });
      pushToast("error", message);
      return;
    }

    setSubmitting(true);
    setFeedback(null);
    try {
      const response = await subscribeToContentApiV1SiteSubscriptionsPost({
        email: email.trim(),
        content_types: selectedTypes,
      });
      const subscribed = response.data;
      if (!isSubscriptionSuccessPayload(subscribed)) {
        throw new Error("订阅请求返回异常，请稍后重试。");
      }
      trackSubscriptionEmail(subscribed.email);
      const message = `确认邮件发送成功，订阅已生效。已记录你填写的邮箱 ${subscribed.email}。`;
      setFeedback({ kind: "success", message });
      pushToast("success", message);
      window.dispatchEvent(
        new CustomEvent<SubscriptionChangedDetail>("aerisun:subscription-changed", {
          detail: {
            email: subscribed.email,
            content_types: subscribed.content_types,
            subscribed: Boolean(subscribed.subscribed),
          },
        }),
      );
    } catch (error) {
      const detail =
        typeof error === "object" &&
        error !== null &&
        "response" in error &&
        typeof (error as { response?: { data?: { detail?: unknown } } })
          .response?.data?.detail === "string"
          ? (error as { response?: { data?: { detail?: string } } }).response
              ?.data?.detail
          : "";
      const message =
        (detail?.trim() ?? "") ||
        (error instanceof Error && error.message.trim()
          ? error.message
          : "订阅失败，请稍后重试。");
      setFeedback({ kind: "error", message });
      pushToast("error", message);
    } finally {
      setSubmitting(false);
    }
  };

  const toastNode =
    typeof document !== "undefined"
      ? createPortal(
          <AnimatePresence>
            {toast ? (
              <motion.div
                initial={{ opacity: 0, y: -12, scale: 0.96 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                exit={{ opacity: 0, y: -10, scale: 0.96 }}
                transition={{ duration: 0.2 }}
                className={`pointer-events-none fixed right-4 top-4 z-[1300] w-[min(92vw,360px)] rounded-2xl border px-4 py-3 text-sm shadow-[0_16px_44px_rgba(15,23,42,0.18)] backdrop-blur-xl ${
                  toast.kind === "success"
                    ? "border-emerald-500/28 bg-emerald-500/14 text-emerald-900 dark:text-emerald-200"
                    : "border-rose-500/30 bg-rose-500/16 text-rose-900 dark:text-rose-200"
                }`}
                role="status"
                aria-live="polite"
              >
                {toast.message}
              </motion.div>
            ) : null}
          </AnimatePresence>,
          document.body,
        )
      : null;

  return (
    <>
      {toastNode}
      <AnimatePresence>
        {open && (
          <motion.div
            className="fixed inset-0 z-[1200] flex items-start justify-center overflow-y-auto scrollbar-hide px-3 pb-4 pt-[calc(env(safe-area-inset-top)+4.25rem)] sm:px-4 sm:py-[10vh]"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.18 }}
          >
            <button
              type="button"
              className="fixed inset-0 bg-background/70 backdrop-blur-sm"
              onClick={onClose}
              aria-label="关闭订阅弹窗"
            />
            <motion.div
              initial={{ opacity: 0, y: -20, scale: 0.96 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -20, scale: 0.96 }}
              transition={{ duration: 0.22, ease: [0.16, 1, 0.3, 1] }}
              className="relative z-10 mx-auto flex max-h-[calc(100dvh-5.5rem)] w-full max-w-4xl flex-col overflow-hidden rounded-[30px] border border-[rgb(var(--shiro-border-rgb)/0.24)] liquid-glass shadow-[0_24px_70px_rgba(15,23,42,0.18)] sm:max-h-[calc(100dvh-4.5rem)]"
            >
            <div className="relative flex-1 overflow-y-auto overscroll-contain scrollbar-hide">
              <div
                aria-hidden="true"
                className="pointer-events-none absolute -left-12 top-6 h-28 w-28 rounded-full bg-[rgb(var(--shiro-accent-rgb)/0.12)] blur-3xl"
              />
              <div
                aria-hidden="true"
                className="pointer-events-none absolute right-10 top-10 h-20 w-20 rounded-full bg-white/12 blur-2xl dark:bg-white/6"
              />

              <div className="relative overflow-hidden border-b border-[rgb(var(--shiro-divider-rgb)/0.14)] bg-[linear-gradient(135deg,rgb(var(--shiro-panel-rgb)/0.78),rgb(var(--shiro-panel-strong-rgb)/0.4))] px-5 py-5 sm:px-6">
                <div className="max-w-2xl">
                  <h2 className="font-body text-[1.9rem] text-foreground/88">
                    订阅更新
                  </h2>
                  <div
                    aria-hidden="true"
                    className="mt-4 flex items-center gap-2.5"
                  >
                    <span className="h-1.5 w-1.5 rounded-full bg-[rgb(var(--shiro-accent-rgb)/0.8)]" />
                    <span className="h-1.5 w-1.5 rounded-full bg-[rgb(var(--shiro-accent-rgb)/0.45)]" />
                    <span className="h-px w-16 bg-gradient-to-r from-[rgb(var(--shiro-accent-rgb)/0.36)] to-transparent" />
                  </div>
                </div>
              </div>

              <div className="grid gap-0 md:grid-cols-[minmax(0,1fr)_minmax(320px,0.84fr)]">
                <div className="space-y-5 p-5 sm:p-6">
                  <div>
                    <label className="mb-2 block text-sm font-medium text-foreground/72">
                      接收订阅信息的邮箱
                    </label>
                    <div className="flex h-12 items-center gap-3 rounded-[20px] border border-[rgb(var(--shiro-border-rgb)/0.2)] bg-white/58 px-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.42)] transition focus-within:border-[rgb(var(--shiro-accent-rgb)/0.36)] focus-within:bg-white/72 focus-within:shadow-[0_12px_28px_rgba(15,23,42,0.06)] dark:bg-black/10 dark:focus-within:bg-black/20">
                      <Mail className="h-4 w-4 shrink-0 text-[rgb(var(--shiro-accent-rgb)/0.72)]" />
                      <input
                        ref={inputRef}
                        type="email"
                        value={email}
                        onChange={(event) => setEmail(event.target.value)}
                        placeholder={
                          enabled
                            ? "name@example.com"
                            : "站长还没有配置邮箱服务，敬请期待~"
                        }
                        disabled={!enabled || submitting}
                        className="h-full w-full bg-transparent text-sm text-foreground outline-none placeholder:text-foreground/28"
                      />
                    </div>
                  </div>

                  <div className="space-y-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-sm font-medium text-foreground/72">
                        接收内容
                      </div>
                      <div className="text-[11px] uppercase tracking-[0.16em] text-foreground/34">
                        {selectedTypes.length}/4
                      </div>
                    </div>
                    <div className="grid gap-2 sm:grid-cols-2">
                      {CONTENT_OPTIONS.map((item) => {
                        const checked = selectedTypes.includes(item.key);
                        return (
                          <button
                            key={item.key}
                            type="button"
                            onClick={() => toggleType(item.key)}
                            aria-pressed={checked}
                            disabled={!enabled || submitting}
                            className={`group relative flex h-[68px] items-center justify-between gap-3 overflow-hidden rounded-[20px] border px-4 text-left transition ${
                              checked
                                ? "border-[rgb(var(--shiro-accent-rgb)/0.34)] bg-[linear-gradient(135deg,rgb(var(--shiro-accent-rgb)/0.13),rgb(var(--shiro-accent-rgb)/0.08))] shadow-[0_12px_24px_rgba(15,23,42,0.06)]"
                                : "border-[rgb(var(--shiro-border-rgb)/0.18)] bg-white/36 hover:bg-white/54 hover:shadow-[0_10px_22px_rgba(15,23,42,0.04)] dark:bg-black/10 dark:hover:bg-black/16"
                            } ${!enabled ? "cursor-not-allowed opacity-55" : ""}`}
                          >
                            <span
                              aria-hidden="true"
                              className={`absolute inset-x-4 top-0 h-px transition ${
                                checked
                                  ? "bg-gradient-to-r from-transparent via-white/60 to-transparent"
                                  : "bg-transparent"
                              }`}
                            />
                            <span className="min-w-0">
                              <span className="block text-sm font-medium text-foreground/82">
                                {item.label}
                              </span>
                            </span>
                            <span
                              className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border transition ${
                                checked
                                  ? "border-[rgb(var(--shiro-accent-rgb)/0.42)] bg-[rgb(var(--shiro-accent-rgb)/0.86)] text-white"
                                  : "border-[rgb(var(--shiro-border-rgb)/0.28)] bg-transparent text-transparent"
                              }`}
                            >
                              <Check className="h-3.5 w-3.5" />
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  {feedback ? (
                    <div
                      className={`rounded-[18px] px-4 py-3 text-sm ${
                        feedback.kind === "success"
                          ? "border border-emerald-500/18 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"
                          : "border border-rose-500/18 bg-rose-500/10 text-rose-700 dark:text-rose-300"
                      }`}
                    >
                      {feedback.message}
                    </div>
                  ) : null}

                  <div className="flex justify-end">
                    <button
                      type="button"
                      onClick={() => void handleSubmit()}
                      disabled={submitting || !enabled}
                      className="inline-flex h-11 items-center gap-2 rounded-full border border-[rgb(var(--shiro-accent-rgb)/0.24)] bg-[rgb(var(--shiro-accent-rgb)/0.16)] px-5 text-sm font-medium text-[rgb(var(--shiro-accent-rgb)/0.92)] transition hover:bg-[rgb(var(--shiro-accent-rgb)/0.22)] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      <BellRing className="h-4 w-4" />
                      {enabled ? (submitting ? "提交中..." : "订阅") : "敬请期待"}
                    </button>
                  </div>
                </div>

                <div className="border-t border-[rgb(var(--shiro-divider-rgb)/0.14)] bg-[rgb(var(--shiro-panel-rgb)/0.2)] p-5 sm:p-6 md:border-l md:border-t-0">
                  <div className="flex items-center gap-2 text-sm font-medium text-foreground/78">
                    <Rss className="h-4 w-4 text-[rgb(var(--shiro-accent-rgb)/0.76)]" />
                    RSS
                  </div>
                  <div className="mt-4 grid gap-2.5">
                    {feedLinks.map((item) => (
                      <div
                        key={item.key}
                        className="rounded-[20px] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-white/40 px-4 py-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.42)] transition hover:bg-white/50 dark:bg-black/10 dark:hover:bg-black/16"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <div className="flex items-center gap-2 text-sm font-medium text-foreground/80">
                              <span
                                aria-hidden="true"
                                className="h-1.5 w-1.5 rounded-full bg-[rgb(var(--shiro-accent-rgb)/0.72)]"
                              />
                              {item.label}
                            </div>
                            <div className="mt-1 break-all text-xs leading-5 text-foreground/46">
                              {item.url}
                            </div>
                          </div>
                          <div className="flex shrink-0 items-center gap-1.5">
                            <a
                              href={item.url}
                              target="_blank"
                              rel="noopener noreferrer"
                              title="打开 RSS 链接"
                              aria-label="打开 RSS 链接"
                              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb)/0.2)] text-foreground/64 transition hover:bg-white/60 hover:text-foreground/86 dark:hover:bg-black/16"
                            >
                              <ExternalLink className="h-3.5 w-3.5" />
                            </a>
                            <button
                              type="button"
                              onClick={() => void handleCopy(item.key, item.url)}
                              title={
                                copiedKey === item.key
                                  ? "已复制"
                                  : "复制 RSS 链接"
                              }
                              aria-label={
                                copiedKey === item.key
                                  ? "已复制 RSS 链接"
                                  : "复制 RSS 链接"
                              }
                              className="inline-flex h-9 w-9 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb)/0.2)] text-foreground/64 transition hover:bg-white/60 hover:text-foreground/86 dark:hover:bg-black/16"
                            >
                              {copiedKey === item.key ? (
                                <Check className="h-3.5 w-3.5" />
                              ) : (
                                <Copy className="h-3.5 w-3.5" />
                              )}
                            </button>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>

            <button
              type="button"
              onClick={onClose}
              className="absolute right-4 top-4 inline-flex h-9 w-9 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-white/44 text-foreground/54 transition hover:text-foreground/84 dark:bg-black/10"
              aria-label="关闭订阅弹窗"
            >
              <X className="h-4 w-4" />
            </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </>
  );
};

export default SubscribeModal;
