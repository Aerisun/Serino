import { Suspense, useDeferredValue, useEffect, useMemo, useRef, useState, type CSSProperties } from "react";
import { motion, AnimatePresence } from "motion/react";
import { BookOpen, MessageCircle, Search, X } from "lucide-react";
import { useLocation } from "react-router-dom";
import ArchiveBadge from "@/components/ArchiveBadge";
import CommentMarkdownRenderer from "@/components/CommentMarkdownRenderer";
import PageShell from "@/components/PageShell";
import PreviewModeBadge from "@/components/PreviewModeBadge";
import { staggerItem, transition } from "@/config";
import { usePageConfig } from "@/contexts/runtime-config";
import { useFrontendI18n } from "@/i18n";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { formatPublishedDate } from "@/lib/api/utils";
import { stripMarkdownImages } from "@/lib/markdown-images";
import { clampPageSize } from "@/lib/page-size";
import { lazyWithPreload } from "@/lib/lazy";
import { usePreviewChannel } from "@/lib/preview";
import { readExcerptsApiV1SiteExcerptsGet } from "@serino/api-client/site";
import type { ContentEntryRead } from "@serino/api-client/models";
import type { BaseViewPageConfig } from "@/lib/page-config";
import { useInfiniteList } from "@/hooks/use-infinite-list";

const CommentSection = lazyWithPreload(() => import("@/components/CommentSection"));

interface Excerpt {
  id: string;
  title: string;
  author: string;
  source: string;
  content: string;
  category: string;
  date: string;
  isArchived: boolean;
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
    isArchived: entry.visibility === "private",
    comments: entry.comment_count ?? 0,
  };
};

const buildPreviewExcerpt = (preview: {
  slug?: string;
  title: string;
  body?: string;
  category?: string;
  published_at?: string | null;
  author_name?: string;
  source?: string;
}, draftLabel: string): Excerpt => ({
  id: preview.slug || "__preview-excerpt",
  title: preview.title,
  author: preview.author_name || "",
  source: preview.source || "",
  content: preview.body || "",
  category: preview.category || "",
  date: formatPublishedDate(preview.published_at) || draftLabel,
  isArchived: false,
  comments: 0,
});

const matchesSearchText = (
  fields: Array<string | null | undefined>,
  query: string,
) => {
  const normalizedQuery = query.trim().toLowerCase();
  if (!normalizedQuery) {
    return true;
  }

  return fields.some((field) =>
    (field ?? "").toLowerCase().includes(normalizedQuery),
  );
};

const hasCjkCharacters = (value: string) =>
  /[\u3400-\u9FFF\uF900-\uFAFF]/.test(value);

const Excerpts = () => {
  const { t, lang } = useFrontendI18n();
  const location = useLocation();
  const previewStorageKey =
    new URLSearchParams(location.search).get("previewStorageKey") || "";
  const pages = usePageConfig();
  const config = pages.excerpts as unknown as ExcerptsPageConfig;
  const prefersReducedMotion = useReducedMotionPreference();
  const errorTitle = config.errorTitle ?? t("excerpts.errorTitle");
  const retryLabel = config.retryLabel ?? t("common.retry");
  const loadMoreLabel = config.loadMoreLabel ?? t("excerpts.loadingMore");
  const closeLabel = config.modalCloseLabel ?? t("excerpts.close");
  const commentsOpenLabel = config.commentsOpenLabel ?? t("excerpts.commentsOpen");
  const commentsCloseLabel = config.commentsCloseLabel ?? t("excerpts.commentsClose");
  const allCategoryLabel = config.categories?.all ?? t("excerpts.allCategory");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const pageSize = clampPageSize(config.pageSize, 15);
  const [showModalComments, setShowModalComments] = useState(false);
  const searchPlaceholder = config.searchPlaceholder ?? t("excerpts.searchPlaceholder");
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const previewOpenedRef = useRef<string | null>(null);
  const [activeCategory, setActiveCategory] = useState(allCategoryLabel);
  const { data: previewData } = usePreviewChannel(previewStorageKey);

  const {
    items,
    status,
    errorMessage,
    hasMore,
    isLoadingMore,
    sentinelRef,
    reload,
  } = useInfiniteList({
    queryKey: ["site", "excerpts", pageSize],
    queryFn: async (p) => {
      const data = (await readExcerptsApiV1SiteExcerptsGet(p)).data;

      if (data && "items" in data && Array.isArray(data.items)) {
        return {
          items: data.items,
          has_more: Boolean(data.has_more),
        };
      }

      throw new Error(t("excerpts.invalidResponse"));
    },
    pageSize,
    mapItem: mapRemoteExcerpt,
    staleTime: 60_000,
    gcTime: 20 * 60_000,
  });
  const previewExcerpt =
    previewData?.type === "excerpts" ? buildPreviewExcerpt(previewData, t("common.draft")) : null;
  const displayItems = useMemo(() => {
    if (!previewExcerpt) {
      return items;
    }

    return [
      previewExcerpt,
      ...items.filter((item) => item.id !== previewExcerpt.id),
    ];
  }, [items, previewExcerpt]);
  const viewStatus: typeof status =
    previewExcerpt && status !== "ready" ? "ready" : status;

  const allCategories = useMemo(
    () => [
      allCategoryLabel,
      ...Array.from(
        new Set(displayItems.map((item) => item.category).filter(Boolean)),
      ).sort((a, b) => a.localeCompare(b, lang === "zh" ? "zh-CN" : "en-US")),
    ],
    [allCategoryLabel, displayItems, lang],
  );

  const filtered = useMemo(() => {
    return displayItems.filter((excerpt) => {
      const matchSearch = matchesSearchText(
        [
          excerpt.title,
          excerpt.author,
          excerpt.source,
          excerpt.content,
          excerpt.category,
        ],
        deferredSearch,
      );
      const matchCategory =
        activeCategory === allCategoryLabel ||
        excerpt.category === activeCategory;
      return matchSearch && matchCategory;
    });
  }, [activeCategory, allCategoryLabel, deferredSearch, displayItems]);

  const selected = useMemo(
    () => displayItems.find((excerpt) => excerpt.id === selectedId) ?? null,
    [displayItems, selectedId],
  );
  const excerptDialogHeightClass = "max-h-full sm:max-h-[min(88vh,calc(100dvh-6.5rem),54rem)]";
  const formatSourceLine = (excerpt: Excerpt) =>
    [excerpt.source, excerpt.author].filter(Boolean).join(" · ");
  const excerptCjkFontFamily =
    "'Noto Serif SC', 'Source Han Serif SC', 'Source Han Serif CN', 'Songti SC', 'STSong', 'SimSun', serif";
  const excerptLatinFontFamily =
    "'Times New Roman', Times, 'Nimbus Roman No9 L', serif";
  const getExcerptFontFamily = (value: string) =>
    hasCjkCharacters(value) ? excerptCjkFontFamily : excerptLatinFontFamily;

  useEffect(() => {
    setShowModalComments(false);
  }, [selectedId]);

  useEffect(() => {
    if (previewExcerpt && previewOpenedRef.current !== previewExcerpt.id) {
      previewOpenedRef.current = previewExcerpt.id;
      setSelectedId(previewExcerpt.id);
      return;
    }

    const targetId = location.hash.slice(1);
    if (!targetId) {
      return;
    }

    const matched = displayItems.find((excerpt) => excerpt.id === targetId);
    if (matched) {
      setSelectedId(matched.id);
    }
  }, [displayItems, location.hash, previewExcerpt]);

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      noIndex={Boolean(previewExcerpt)}
      width={
        config.width === "narrow" ? "content" : (config.width ?? "content")
      }
      contentClassName="mt-0 sm:mt-10"
    >
      {previewExcerpt ? <PreviewModeBadge /> : null}
      <div className="mt-3 flex flex-col gap-4 sm:mt-6 sm:flex-row sm:items-center sm:justify-between">
        <div className="group relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground/25 transition-colors group-focus-within:text-[rgb(var(--shiro-accent-rgb)/0.72)]" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
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

      <div className="mt-6 grid grid-cols-1 gap-4 sm:mt-8 sm:grid-cols-2">
        {viewStatus === "loading" &&
          Array.from({ length: 6 }, (_, index) => (
            <div
              key={`excerpt-skeleton-${index}`}
              className="liquid-glass rounded-2xl p-5"
            >
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

        {viewStatus === "error" && (
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

        {(viewStatus === "empty" ||
          (viewStatus === "ready" && filtered.length === 0)) && (
          <div className="liquid-glass rounded-2xl p-5 sm:col-span-2">
            <div className="mb-3 flex items-center gap-2">
              <BookOpen className="h-3.5 w-3.5 text-foreground/20" />
              <span className="truncate text-[10px] font-body uppercase tracking-wider text-foreground/25">
                {String(config.eyebrow ?? "")}
              </span>
            </div>
            <h3 className="text-base font-body font-medium leading-snug text-foreground/70">
              {config.emptyMessage ?? t("excerpts.emptyMessage")}
            </h3>
          </div>
        )}

        {viewStatus === "ready" &&
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
                {excerpt.isArchived ? <ArchiveBadge /> : null}
                <BookOpen className="h-3.5 w-3.5 text-foreground/20 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.52)]" />
                <span
                  className="truncate text-[10px] font-body tracking-wider text-foreground/25 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
                  style={{
                    fontFamily: getExcerptFontFamily(formatSourceLine(excerpt)),
                  }}
                >
                  {formatSourceLine(excerpt)}
                </span>
              </div>

              <p
                className="mt-1 line-clamp-3 indent-[2em] text-[14.5px] font-body leading-relaxed text-foreground/76 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.78)]"
                style={{ fontFamily: getExcerptFontFamily(stripMarkdownImages(excerpt.content)) }}
              >
                {stripMarkdownImages(excerpt.content)}
              </p>

              {excerpt.category ? (
                <div className="mt-3 text-[10px] text-foreground/20 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.58)]">
                  {excerpt.category}
                </div>
              ) : null}
            </motion.button>
          ))}
      </div>

      {viewStatus === "ready" && hasMore && (
        <div ref={sentinelRef} className="py-8 text-center">
          {isLoadingMore && (
            <span className="text-xs text-foreground/25">{loadMoreLabel}</span>
          )}
        </div>
      )}

      <AnimatePresence>
        {selected && (
          <motion.div
            layoutRoot
            className="fixed inset-0 z-[90] flex items-start justify-center px-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-[max(5rem,calc(env(safe-area-inset-top)+4rem))] sm:px-6 sm:pb-6 sm:pt-20"
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
              layoutScroll
              className={`aerisun-excerpt-dialog scrollbar-hide relative flex min-h-0 w-full max-w-[52rem] flex-col overflow-x-hidden overflow-y-auto overscroll-y-contain rounded-[1.65rem] p-5 liquid-glass transition-[background-color,border-color,box-shadow] sm:rounded-3xl sm:p-8 ${excerptDialogHeightClass}`}
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

              <div className="shrink-0 pr-10">
                <div className="mb-4 flex flex-wrap items-center gap-2">
                  {selected.isArchived ? <ArchiveBadge /> : null}
                  <BookOpen className="h-4 w-4 text-foreground/25 transition-colors" />
                  <span
                    className="text-xs font-body text-foreground/30 transition-colors"
                    style={{ fontFamily: getExcerptFontFamily(selected.source) }}
                  >
                    {selected.source}
                  </span>
                </div>
                <p className="mt-0.5 text-xs font-body text-foreground/30 transition-colors">
                  {selected.author ? (
                    <span
                      style={{
                        fontFamily: getExcerptFontFamily(selected.author),
                      }}
                    >
                      {selected.author}
                    </span>
                  ) : null}
                  {selected.author && selected.date ? " · " : null}
                  {selected.date ? <span>{selected.date}</span> : null}
                </p>
                <div className="my-5 border-t border-foreground/[0.06] transition-colors" />
              </div>

              <div className="relative flex min-h-0 flex-1 flex-col">
                <div className={`aerisun-excerpt-reader aerisun-detail-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-y-contain pr-2 touch-pan-y [-webkit-overflow-scrolling:touch] ${showModalComments ? "max-h-[min(8vh,5.5rem)] sm:max-h-[min(18vh,10.5rem)]" : ""}`}>
                  <CommentMarkdownRenderer
                    content={selected.content}
                    className="content-detail-markdown aerisun-excerpt-markdown text-[1.04rem] leading-8 text-foreground/90 transition-colors [overflow-wrap:anywhere] [word-break:break-word] [&>p:first-child]:mt-0 [&>p:last-child]:mb-0"
                    indentParagraphs
                    style={{
                      fontFamily: getExcerptFontFamily(stripMarkdownImages(selected.content)),
                      "--detail-reading-font": getExcerptFontFamily(stripMarkdownImages(selected.content)),
                    } as CSSProperties}
                  />
                  {selected.category ? (
                    <div className="mt-6 text-[11px] font-body text-foreground/25 transition-colors">
                      {selected.category}
                    </div>
                  ) : null}
                </div>

              </div>

              <motion.div
                layout="position"
                transition={transition({ duration: 0.26, reducedMotion: prefersReducedMotion })}
                className="mt-4 shrink-0 border-t border-foreground/[0.06] pt-3"
              >
                <motion.button
                  type="button"
                  aria-controls={`excerpt-comments-${selected.id}`}
                  aria-expanded={showModalComments}
                  onMouseEnter={() => void CommentSection.preload()}
                  onFocus={() => void CommentSection.preload()}
                  onTouchStart={() => void CommentSection.preload()}
                  onClick={() => setShowModalComments((v) => !v)}
                  whileTap={prefersReducedMotion ? undefined : { scale: 0.98 }}
                  transition={transition({ duration: 0.16, reducedMotion: prefersReducedMotion })}
                  className={`flex items-center gap-2 text-[13px] font-body transition-colors sm:py-1 sm:text-sm ${
                    showModalComments
                      ? "text-[rgb(var(--shiro-accent-rgb)/0.78)]"
                      : "text-foreground/30 hover:text-[rgb(var(--shiro-accent-rgb)/0.62)]"
                  }`}
                >
                  <MessageCircle
                    className={`h-3.5 w-3.5 sm:h-4 sm:w-4 ${showModalComments ? "fill-[rgb(var(--shiro-panel-rgb)/0.34)]" : ""}`}
                  />
                  {showModalComments
                    ? commentsCloseLabel
                    : `${commentsOpenLabel} · ${selected.comments}`}
                </motion.button>
              </motion.div>

              <AnimatePresence initial={false}>
                {showModalComments && (
                  <motion.div
                    id={`excerpt-comments-${selected.id}`}
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1, y: 0 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={transition({ duration: 0.28, reducedMotion: prefersReducedMotion })}
                    className="aerisun-excerpt-comment-drawer mt-1 flex min-h-0 flex-col sm:mt-3"
                  >
                    <Suspense fallback={null}>
                      <motion.div
                        initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 6 }}
                        animate={{ opacity: 1, y: 0 }}
                        exit={{ opacity: 0, y: prefersReducedMotion ? 0 : 6 }}
                        transition={transition({ duration: 0.2, reducedMotion: prefersReducedMotion })}
                        className="aerisun-excerpt-comment-drawer__content"
                      >
                        <CommentSection
                          contentType="excerpts"
                          contentSlug={selected.id}
                          expandable={false}
                          layout="modal"
                        />
                      </motion.div>
                    </Suspense>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </PageShell>
  );
};

export default Excerpts;
