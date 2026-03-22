import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { BookOpen, X } from "lucide-react";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";
import { fetchPublicContentCollection, formatPublishedDate, type PublicContentEntry } from "@/lib/api";
import type { BaseViewPageConfig } from "@/lib/page-config";

interface Excerpt {
  id: string;
  title: string;
  author: string;
  source: string;
  content: string;
  tags: string[];
  date: string;
}

interface ExcerptsPageConfig extends BaseViewPageConfig {
  modalCloseLabel?: string;
}

const mapRemoteExcerpt = (entry: PublicContentEntry): Excerpt => {
  return {
    id: entry.slug,
    title: entry.title,
    author: entry.author ?? "",
    source: entry.source ?? "",
    content: entry.body,
    tags: entry.tags,
    date: formatPublishedDate(entry.published_at) || "",
  };
};

const Excerpts = () => {
  const config = usePageConfig().excerpts as unknown as ExcerptsPageConfig;
  const [items, setItems] = useState<Excerpt[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [hasMore, setHasMore] = useState(true);
  const [isLoadingMore, setIsLoadingMore] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const PAGE_SIZE = 40;

  const selected = useMemo(
    () => items.find((excerpt) => excerpt.id === selectedId) ?? null,
    [items, selectedId],
  );
  const formatSourceLine = (excerpt: Excerpt) => [excerpt.source, excerpt.author].filter(Boolean).join(" · ");

  useEffect(() => {
    const controller = new AbortController();

    const loadExcerpts = async () => {
      setStatus("loading");
      setErrorMessage("");

      try {
        const payload = await fetchPublicContentCollection("excerpts", PAGE_SIZE, undefined, { signal: controller.signal });
        if (controller.signal.aborted) {
          return;
        }

        const nextItems = payload.items.map(mapRemoteExcerpt);
        setItems(nextItems);
        setHasMore(payload.has_more ?? false);
        setStatus(nextItems.length > 0 ? "ready" : "empty");
      } catch (error) {
        if (!controller.signal.aborted) {
          setItems([]);
          setStatus("error");
          setErrorMessage(error instanceof Error ? error.message : "文摘加载失败");
        }
      }
    };

    void loadExcerpts();

    return () => {
      controller.abort();
    };
  }, [reloadKey]);

  const loadMore = async () => {
    if (isLoadingMore || !hasMore) return;
    setIsLoadingMore(true);
    try {
      const payload = await fetchPublicContentCollection("excerpts", PAGE_SIZE, items.length);
      const moreItems = payload.items.map(mapRemoteExcerpt);
      setItems(prev => [...prev, ...moreItems]);
      setHasMore(payload.has_more ?? false);
    } catch {
      // silently fail on load more
    } finally {
      setIsLoadingMore(false);
    }
  };

  useEffect(() => {
    const el = sentinelRef.current;
    if (!el || !hasMore || status !== "ready") return;
    const observer = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) loadMore(); },
      { rootMargin: "200px" }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [hasMore, status, items.length]);

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >
      <div className="mt-10 grid grid-cols-1 gap-4 sm:grid-cols-2">
        {status === "loading" &&
          Array.from({ length: 6 }, (_, index) => (
            <div key={`excerpt-skeleton-${index}`} className="liquid-glass rounded-2xl p-5">
              <div className="mb-3 flex items-center gap-2">
                <div className="h-3.5 w-3.5 rounded-full bg-foreground/[0.04]" />
                <div className="h-3 w-28 rounded-full bg-foreground/[0.04]" />
              </div>
              <div className="h-5 w-[58%] rounded-full bg-foreground/[0.045]" />
              <div className="mt-3 h-3.5 w-[92%] rounded-full bg-foreground/[0.035]" />
              <div className="mt-2 h-3.5 w-[78%] rounded-full bg-foreground/[0.03]" />
              <div className="mt-3 flex flex-wrap gap-1.5">
                <div className="h-6 w-12 rounded-full bg-foreground/[0.03]" />
                <div className="h-6 w-14 rounded-full bg-foreground/[0.03]" />
              </div>
            </div>
          ))}

        {status === "error" && (
          <div className="liquid-glass rounded-2xl p-5 sm:col-span-2">
            <div className="mb-3 flex items-center gap-2">
              <BookOpen className="h-3.5 w-3.5 text-foreground/20 transition-colors" />
              <span className="truncate text-[10px] font-body uppercase tracking-wider text-foreground/25 transition-colors">
                {String(config.eyebrow ?? "")}
              </span>
            </div>
            <h3 className="text-base font-body font-medium leading-snug text-foreground/70 transition-colors">
              文摘加载失败
            </h3>
            <p className="mt-2 text-[12px] font-body leading-relaxed text-foreground/30">
              {errorMessage}
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => setReloadKey((value) => value + 1)}
                className="rounded-full border border-foreground/[0.08] px-3 py-1 text-[11px] text-foreground/25 transition-colors hover:border-[rgb(var(--shiro-divider-rgb)/0.26)] hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
              >
                重试
              </button>
            </div>
          </div>
        )}

        {(status === "empty" || (status === "ready" && items.length === 0)) && (
          <div className="liquid-glass rounded-2xl p-5 sm:col-span-2">
            <div className="mb-3 flex items-center gap-2">
              <BookOpen className="h-3.5 w-3.5 text-foreground/20" />
              <span className="truncate text-[10px] font-body uppercase tracking-wider text-foreground/25">
                {String(config.eyebrow ?? "")}
              </span>
            </div>
            <h3 className="text-base font-body font-medium leading-snug text-foreground/70">
              {config.emptyMessage ?? "还没有整理好的文摘"}
            </h3>
          </div>
        )}

        {status === "ready" &&
          items.map((excerpt, index) => (
            <motion.button
              key={excerpt.id}
              type="button"
              onClick={() => setSelectedId(excerpt.id)}
              className="group text-left liquid-glass rounded-2xl p-5 transition-[background-color,border-color,box-shadow] hover:bg-[rgb(var(--shiro-panel-rgb)/0.18)] hover:border-[rgb(var(--shiro-border-rgb)/0.14)] active:scale-[0.98]"
              {...staggerItem(index, {
                baseDelay: config.motion.delay,
                step: config.motion.stagger,
                duration: config.motion.duration,
              })}
            >
              <div className="mb-3 flex items-center gap-2">
                <BookOpen className="h-3.5 w-3.5 text-foreground/20 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.52)]" />
                <span className="truncate text-[10px] font-body uppercase tracking-wider text-foreground/25 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]">
                  {formatSourceLine(excerpt)}
                </span>
              </div>

              <h3 className="text-base font-body font-medium leading-snug text-foreground/80 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.92)]">
                {excerpt.title}
              </h3>

              <p className="mt-2 line-clamp-3 text-[12px] font-body leading-relaxed text-foreground/30 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.62)]">
                {excerpt.content}
              </p>

              <div className="mt-3 flex flex-wrap gap-1.5">
                {excerpt.tags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full border border-foreground/[0.06] px-2 py-0.5 text-[10px] font-body text-foreground/20 transition-colors group-hover:border-[rgb(var(--shiro-divider-rgb)/0.24)] group-hover:text-[rgb(var(--shiro-accent-rgb)/0.56)]"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            </motion.button>
          ))}
      </div>

      {status === "ready" && hasMore && (
        <div ref={sentinelRef} className="py-8 text-center">
          {isLoadingMore && <span className="text-xs text-foreground/25">加载更多...</span>}
        </div>
      )}

      <AnimatePresence>
        {selected && (
          <motion.div
            className="fixed inset-0 z-[90] flex items-center justify-center px-6"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.25 }}
          >
            <div
              className="absolute inset-0 bg-background/80 backdrop-blur-sm"
              onClick={() => setSelectedId(null)}
            />

            <motion.div
              className="relative max-h-[80vh] w-full max-w-lg overflow-y-auto rounded-3xl p-8 liquid-glass scrollbar-hide transition-[background-color,border-color,box-shadow]"
              initial={{ scale: 0.95, opacity: 0, y: 16 }}
              animate={{ scale: 1, opacity: 1, y: 0 }}
              exit={{ scale: 0.95, opacity: 0, y: 16 }}
              transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
            >
              <button
                type="button"
                onClick={() => setSelectedId(null)}
                aria-label={String(config.modalCloseLabel ?? "")}
                className="absolute right-4 top-4 flex h-8 w-8 items-center justify-center rounded-full text-foreground/30 transition-colors hover:bg-[rgb(var(--shiro-panel-rgb)/0.2)] hover:text-[rgb(var(--shiro-accent-rgb)/0.78)]"
              >
                <X className="h-4 w-4" />
              </button>

              <div className="mb-4 flex items-center gap-2">
                <BookOpen className="h-4 w-4 text-foreground/25 transition-colors" />
                <span className="text-xs font-body text-foreground/30 transition-colors">
                  {selected.source}
                </span>
              </div>
              <h2 className="mt-4 text-xl font-heading italic leading-snug text-foreground transition-colors">
                {selected.title}
              </h2>
              <p className="mt-1 text-xs font-body text-foreground/25 transition-colors">
                {[selected.author, selected.date].filter(Boolean).join(" · ")}
              </p>
              <div className="my-5 border-t border-foreground/[0.06] transition-colors" />
              <p
                className="text-[0.935rem] font-body leading-8 text-foreground/60 transition-colors"
                style={{ fontFamily: "'Instrument Serif', serif" }}
              >
                {selected.content}
              </p>
              {selected.tags.length > 0 && (
                <div className="mt-6 flex flex-wrap gap-2">
                  {selected.tags.map((tag) => (
                    <span
                      key={tag}
                      className="rounded-full border border-foreground/[0.08] px-3 py-1 text-[11px] font-body text-foreground/25 transition-colors hover:border-[rgb(var(--shiro-divider-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.62)]"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              )}
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </PageShell>
  );
};

export default Excerpts;
