import { useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { BookOpen, MessageCircle, Search, X } from "lucide-react";
import { useLocation } from "react-router-dom";
import PageShell from "@/components/PageShell";
import CommentSection from "@/components/CommentSection";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/runtime-config";
import { formatPublishedDate } from "@/lib/api/utils";
import { clampPageSize } from "@/lib/page-size";
import { readExcerptsApiV1SiteExcerptsGet } from "@serino/api-client/site";
import type { ContentEntryRead } from "@serino/api-client/models";
import type { BaseViewPageConfig } from "@/lib/page-config";
import { useInfiniteList } from "@/hooks/use-infinite-list";

interface Excerpt {
  id: string;
  title: string;
  author: string;
  source: string;
  content: string;
  category: string;
  date: string;
  comments: number;
}

interface ExcerptsPageConfig extends BaseViewPageConfig {
  categories?: {
    all?: string;
  };
  modalCloseLabel?: string;
  commentsOpenLabel?: string;
  commentsCloseLabel?: string;
}

const mapRemoteExcerpt = (entry: ContentEntryRead): Excerpt => {
  return {
    id: entry.slug,
    title: entry.title,
    author: entry.author ?? "",
    source: entry.source ?? "",
    content: entry.body,
    category: entry.category || "",
    date: formatPublishedDate(entry.published_at) || "",
    comments: entry.comment_count ?? 0,
  };
};

const matchesSearchText = (fields: Array<string | null | undefined>, query: string) => {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return true;
  }

  return fields.some((field) => (field ?? "").toLowerCase().includes(normalizedQuery));
};

const Excerpts = () => {
  const location = useLocation();
  const config = usePageConfig().excerpts as unknown as ExcerptsPageConfig;
  const errorTitle = config.errorTitle ?? "文摘加载失败";
  const retryLabel = config.retryLabel ?? "重试";
  const loadMoreLabel = config.loadMoreLabel ?? "加载更多...";
  const closeLabel = config.modalCloseLabel ?? "关闭";
  const commentsOpenLabel = config.commentsOpenLabel ?? "查看评论";
  const commentsCloseLabel = config.commentsCloseLabel ?? "收起评论";
  const allCategoryLabel = config.categories?.all ?? "全部";
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const pageSize = clampPageSize(config.pageSize, 40);
  const [showModalComments, setShowModalComments] = useState(false);
  const searchPlaceholder = config.searchPlaceholder ?? "搜索文摘...";
  const [search, setSearch] = useState("");
  const [rawSearch, setRawSearch] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [activeCategory, setActiveCategory] = useState(allCategoryLabel);

  const { items, status, errorMessage, hasMore, isLoadingMore, sentinelRef, reload } = useInfiniteList({
    queryKey: ["site", "excerpts"],
    queryFn: (p) => readExcerptsApiV1SiteExcerptsGet(p).then(r => r.data),
    pageSize,
    mapItem: mapRemoteExcerpt,
  });

  useEffect(() => {
    return () => {
      if (debounceRef.current) {
        clearTimeout(debounceRef.current);
      }
    };
  }, []);

  const allCategories = useMemo(
    () => [
      allCategoryLabel,
      ...Array.from(new Set(items.map((item) => item.category).filter(Boolean))).sort((a, b) => a.localeCompare(b, "zh-CN")),
    ],
    [allCategoryLabel, items],
  );

  const filtered = useMemo(() => {
    return items.filter((excerpt) => {
      const matchSearch = matchesSearchText(
        [excerpt.title, excerpt.author, excerpt.source, excerpt.content, excerpt.category],
        search,
      );
      const matchCategory = activeCategory === allCategoryLabel || excerpt.category === activeCategory;
      return matchSearch && matchCategory;
    });
  }, [activeCategory, allCategoryLabel, items, search]);

  const selected = useMemo(
    () => items.find((excerpt) => excerpt.id === selectedId) ?? null,
    [items, selectedId],
  );
  const formatSourceLine = (excerpt: Excerpt) => [excerpt.source, excerpt.author].filter(Boolean).join(" · ");

  useEffect(() => {
    setShowModalComments(false);
  }, [selectedId]);

  useEffect(() => {
    const targetId = location.hash.slice(1);
    if (!targetId) {
      return;
    }

    const matched = items.find((excerpt) => excerpt.id === targetId);
    if (matched) {
      setSelectedId(matched.id);
    }
  }, [items, location.hash]);

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >
      <div className="mt-6 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="group relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground/25 transition-colors group-focus-within:text-[rgb(var(--shiro-accent-rgb)/0.72)]" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={rawSearch}
            onChange={(event) => {
              const value = event.target.value;
              setRawSearch(value);
              if (debounceRef.current) {
                clearTimeout(debounceRef.current);
              }
              debounceRef.current = setTimeout(() => setSearch(value), 300);
            }}
            maxLength={100}
            aria-label={searchPlaceholder}
            className="w-full rounded-xl border border-foreground/8 bg-foreground/[0.03] py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-foreground/25 outline-none transition-colors focus:border-[rgb(var(--shiro-border-rgb)/0.32)] focus:bg-[rgb(var(--shiro-panel-rgb)/0.35)]"
          />
        </div>

        <div className="flex flex-wrap gap-1.5">
          <button
            type="button"
            onClick={() => setActiveCategory(allCategoryLabel)}
            className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors active:scale-[0.97] ${
              activeCategory === allCategoryLabel
                ? "bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.9)]"
                : "text-foreground/35 hover:bg-[rgb(var(--shiro-panel-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
            }`}
          >
            {allCategoryLabel}
          </button>
          {allCategories.slice(1).map((category) => (
            <button
              key={category}
              type="button"
              onClick={() => setActiveCategory(category)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors active:scale-[0.97] ${
                activeCategory === category
                  ? "bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.9)]"
                  : "text-foreground/35 hover:bg-[rgb(var(--shiro-panel-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
              }`}
            >
              {category}
            </button>
          ))}
        </div>
      </div>

      <div className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
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
              {errorTitle}
            </h3>
            <p className="mt-2 text-[12px] font-body leading-relaxed text-foreground/30">
              {errorMessage}
            </p>
            <div className="mt-3 flex flex-wrap gap-1.5">
              <button
                type="button"
                onClick={() => reload()}
                className="rounded-full border border-foreground/[0.08] px-3 py-1 text-[11px] text-foreground/25 transition-colors hover:border-[rgb(var(--shiro-divider-rgb)/0.26)] hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
              >
                {retryLabel}
              </button>
            </div>
          </div>
        )}

        {(status === "empty" || (status === "ready" && filtered.length === 0)) && (
          <div className="liquid-glass rounded-2xl p-5 sm:col-span-2">
            <div className="mb-3 flex items-center gap-2">
              <BookOpen className="h-3.5 w-3.5 text-foreground/20" />
              <span className="truncate text-[10px] font-body uppercase tracking-wider text-foreground/25">
                {String(config.eyebrow ?? "")}
              </span>
            </div>
            <h3 className="text-base font-body font-medium leading-snug text-foreground/70">
              {config.emptyMessage ?? "没有找到匹配的文摘"}
            </h3>
          </div>
        )}

        {status === "ready" &&
          filtered.map((excerpt, index) => (
            <motion.button
              key={excerpt.id}
              id={excerpt.id}
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

              {excerpt.category ? (
                <div className="mt-3 text-[10px] text-foreground/20 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.58)]">
                  {excerpt.category}
                </div>
              ) : null}
            </motion.button>
          ))}
      </div>

      {status === "ready" && hasMore && (
        <div ref={sentinelRef} className="py-8 text-center">
          {isLoadingMore && <span className="text-xs text-foreground/25">{loadMoreLabel}</span>}
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
                aria-label={closeLabel}
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
              {selected.category ? (
                <div className="mt-6 text-[11px] font-body text-foreground/25 transition-colors">
                  {selected.category}
                </div>
              ) : null}

              <div className="mt-6 border-t border-foreground/[0.06] pt-4">
                <button
                  type="button"
                  onClick={() => setShowModalComments((v) => !v)}
                  className={`flex items-center gap-2 text-xs font-body transition-colors ${
                    showModalComments
                      ? "text-[rgb(var(--shiro-accent-rgb)/0.78)]"
                      : "text-foreground/30 hover:text-[rgb(var(--shiro-accent-rgb)/0.62)]"
                  }`}
                >
                  <MessageCircle className={`h-3.5 w-3.5 ${showModalComments ? "fill-[rgb(var(--shiro-panel-rgb)/0.34)]" : ""}`} />
                  {showModalComments ? commentsCloseLabel : `${commentsOpenLabel} · ${selected.comments}`}
                </button>

                <AnimatePresence>
                  {showModalComments && (
                    <motion.div
                      initial={{ height: 0, opacity: 0 }}
                      animate={{ height: "auto", opacity: 1 }}
                      exit={{ height: 0, opacity: 0 }}
                      transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                      className="mt-3 overflow-hidden"
                    >
                      <CommentSection
                        contentType="excerpts"
                        contentSlug={selected.id}
                        expandable={false}
                      />
                    </motion.div>
                  )}
                </AnimatePresence>
              </div>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </PageShell>
  );
};

export default Excerpts;
