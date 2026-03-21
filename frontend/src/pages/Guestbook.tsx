import { useEffect, useState, type FormEvent } from "react";
import { motion } from "motion/react";
import { Send } from "lucide-react";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";
import { createPublicGuestbookEntry, fetchPublicGuestbook, type PublicGuestbookEntry } from "@/lib/api";
import type { BaseViewPageConfig } from "@/lib/page-config";

interface Message {
  id: string;
  name: string;
  avatar: string;
  content: string;
  date: string;
}

interface GuestbookPageConfig extends BaseViewPageConfig {
  namePlaceholder?: string;
  contentPlaceholder?: string;
  submitLabel?: string;
}

const formatDate = (value: string | number | Date | null | undefined) => {
  if (!value) return new Date().toISOString().slice(0, 10);

  const parsed = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(parsed.getTime())) return String(value);

  return parsed.toISOString().slice(0, 10);
};

const extractGuestbookItems = (payload: unknown): unknown[] => {
  if (Array.isArray(payload)) return payload;

  if (payload && typeof payload === "object") {
    const record = payload as Record<string, unknown>;
    for (const candidate of [record.items, record.entries, record.data, record.results]) {
      if (Array.isArray(candidate)) return candidate;
    }
  }

  return [];
};

const normalizeGuestbookMessage = (entry: unknown): Message => {
  const record = entry as Record<string, unknown>;
  const name = String(record.name ?? record.author ?? record.nickname ?? "访客");
  const avatar = String(record.avatar ?? record.avatar_url ?? "");
  const content = String(record.body ?? record.content ?? record.message ?? "");
  const date = formatDate(record.date ?? record.created_at ?? record.published_at);

  return {
    id: String(record.id ?? `${name}-${date}-${content.slice(0, 8)}`),
    name,
    avatar,
    content,
    date,
  };
};

const Guestbook = () => {
  const config = usePageConfig().guestbook as GuestbookPageConfig;
  const [messages, setMessages] = useState<Message[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [name, setName] = useState("");
  const [content, setContent] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    const controller = new AbortController();

    const loadGuestbook = async () => {
      setStatus("loading");
      setErrorMessage("");

      try {
        const payload = await fetchPublicGuestbook(50, { signal: controller.signal });
        if (controller.signal.aborted) {
          return;
        }

        const nextMessages = extractGuestbookItems(payload)
          .map(normalizeGuestbookMessage)
          .filter((item) => item.content.trim());

        setMessages(nextMessages);
        setStatus(nextMessages.length > 0 ? "ready" : "empty");
      } catch (error) {
        if (!controller.signal.aborted) {
          setMessages([]);
          setStatus("error");
          setErrorMessage(error instanceof Error ? error.message : "留言板加载失败");
        }
      }
    };

    void loadGuestbook();

    return () => {
      controller.abort();
    };
  }, [reloadKey]);

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();

    const trimmedName = name.trim();
    const trimmedContent = content.trim();
    if (!trimmedName || !trimmedContent || isSubmitting) {
      return;
    }

    const previousMessages = messages;
    const optimisticMessage: Message = {
      id: `pending-${Date.now()}`,
      name: trimmedName,
      avatar: "",
      content: trimmedContent,
      date: formatDate(new Date().toISOString()),
    };

    setIsSubmitting(true);
    setMessages((current) => [optimisticMessage, ...current]);
    setStatus("ready");
    setName("");
    setContent("");

    try {
      const response = await createPublicGuestbookEntry(
        {
          name: trimmedName,
          body: trimmedContent,
        },
        { credentials: "include" },
      );

      const savedMessage = normalizeGuestbookMessage(response.item as PublicGuestbookEntry);
      setMessages((current) =>
        current.map((item) =>
          item.id === optimisticMessage.id ? savedMessage : item,
        ),
      );
    } catch (error) {
      setMessages(previousMessages);
      setStatus(previousMessages.length > 0 ? "ready" : "empty");
      setName(trimmedName);
      setContent(trimmedContent);
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >
      <motion.form
        onSubmit={handleSubmit}
        className="mt-10 liquid-glass rounded-2xl p-6"
        initial={{ opacity: 0, y: 14 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{
          duration: config.motion.duration,
          delay: config.motion.delay,
          ease: [0.16, 1, 0.3, 1],
        }}
      >
        <div className="flex flex-col sm:flex-row gap-3 mb-3">
          <input
            type="text"
            placeholder={config.namePlaceholder}
            value={name}
            onChange={(event) => setName(event.target.value)}
            className="flex-1 rounded-xl border border-foreground/[0.08] bg-foreground/[0.03] px-4 py-2.5 text-sm font-body text-foreground placeholder:text-foreground/20 outline-none transition-[border-color,box-shadow,background-color,color] focus:border-[rgb(var(--shiro-accent-rgb)/0.44)] focus:bg-foreground/[0.05] focus:ring-2 focus:ring-[rgb(var(--shiro-accent-rgb)/0.12)]"
          />
        </div>
        <textarea
          placeholder={config.contentPlaceholder}
          value={content}
          onChange={(event) => setContent(event.target.value)}
          rows={3}
          className="w-full rounded-xl border border-foreground/[0.08] bg-foreground/[0.03] px-4 py-3 text-sm font-body text-foreground placeholder:text-foreground/20 outline-none transition-[border-color,box-shadow,background-color,color] focus:border-[rgb(var(--shiro-accent-rgb)/0.44)] focus:bg-foreground/[0.05] focus:ring-2 focus:ring-[rgb(var(--shiro-accent-rgb)/0.12)] resize-none"
        />
        <div className="mt-3 flex justify-end">
          <button
            type="submit"
            disabled={isSubmitting}
            className="flex items-center gap-2 rounded-full liquid-glass border border-[rgb(var(--shiro-border-rgb)/0.18)] px-5 py-2.5 text-sm font-body font-medium text-foreground/60 transition-[border-color,background-color,color,transform] hover:border-[rgb(var(--shiro-accent-rgb)/0.34)] hover:bg-[rgb(var(--shiro-panel-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.86)] active:scale-[0.97] disabled:opacity-60"
          >
            <Send className="h-3.5 w-3.5" />
            {config.submitLabel}
          </button>
        </div>
      </motion.form>

      <div className="mt-10 flex flex-col gap-0">
        {status === "loading" &&
          Array.from({ length: 3 }, (_, index) => (
            <div
              key={`guestbook-skeleton-${index}`}
              className="flex items-start gap-3.5 border-t border-foreground/[0.05] py-5"
            >
              <div className="mt-0.5 h-9 w-9 shrink-0 rounded-full bg-foreground/[0.06]" />
              <div className="min-w-0 flex-1">
                <div className="h-3.5 w-24 rounded-full bg-foreground/[0.04]" />
                <div className="mt-2 h-3.5 w-[82%] rounded-full bg-foreground/[0.035]" />
                <div className="mt-1.5 h-3.5 w-[64%] rounded-full bg-foreground/[0.03]" />
              </div>
            </div>
          ))}

        {status === "error" && (
          <div className="flex items-start gap-3.5 border-t border-foreground/[0.05] py-5">
            <div className="mt-0.5 h-9 w-9 shrink-0 rounded-full bg-foreground/[0.06]" />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-baseline gap-2">
                <span className="text-sm font-body font-medium text-foreground/70">
                  {errorMessage || String(config.loadingLabel ?? "")}
                </span>
                <button
                  type="button"
                  onClick={() => setReloadKey((value) => value + 1)}
                  className="text-[10px] font-body text-foreground/20 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
                >
                  {String(config.retryLabel ?? "")}
                </button>
              </div>
              <p className="mt-1.5 text-sm font-body leading-relaxed text-foreground/45">
                {String(config.emptyMessage ?? "")}
              </p>
            </div>
          </div>
        )}

        {status === "empty" && (
          <div className="flex items-start gap-3.5 border-t border-foreground/[0.05] py-5">
            <div className="mt-0.5 h-9 w-9 shrink-0 rounded-full bg-foreground/[0.06]" />
            <div className="min-w-0 flex-1">
              <p className="text-sm font-body text-foreground/40">{String(config.emptyMessage ?? "")}</p>
            </div>
          </div>
        )}

        {status === "ready" &&
          messages.map((msg, index) => (
            <motion.div
              key={msg.id}
              className="flex items-start gap-3.5 border-t border-foreground/[0.05] py-5"
              {...staggerItem(index, {
                baseDelay: config.motion.delay + 0.04,
                step: config.motion.stagger,
                duration: config.motion.duration,
              })}
            >
              <div className="mt-0.5 h-9 w-9 shrink-0 overflow-hidden rounded-full bg-foreground/[0.06]">
                {msg.avatar ? (
                  <img src={msg.avatar} alt={msg.name} className="h-full w-full object-cover" loading="lazy" />
                ) : null}
              </div>

              <div className="min-w-0 flex-1">
                <div className="flex items-baseline gap-2">
                  <span className="text-sm font-body font-medium text-foreground/70">{msg.name}</span>
                  <span className="text-[10px] font-body text-foreground/20 tabular-nums">{msg.date}</span>
                </div>
                <p className="mt-1.5 text-sm font-body text-foreground/45 leading-relaxed">{msg.content}</p>
              </div>
            </motion.div>
          ))}
      </div>
    </PageShell>
  );
};

export default Guestbook;
