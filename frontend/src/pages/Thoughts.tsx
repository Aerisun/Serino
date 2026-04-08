import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Heart, MessageCircle, Search } from "lucide-react";
import { useLocation } from "react-router-dom";
import ArchiveBadge from "@/components/ArchiveBadge";
import PageShell from "@/components/PageShell";
import PreviewModeBadge from "@/components/PreviewModeBadge";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/runtime-config";
import { useContentReaction } from "@/hooks/use-content-reaction";
import { useFrontendI18n } from "@/i18n";
import { useInfiniteList } from "@/hooks/use-infinite-list";
import { clampPageSize } from "@/lib/page-size";
import { formatPublishedDate } from "@/lib/api/utils";
import { usePreviewChannel } from "@/lib/preview";
import { readThoughtsApiV1SiteThoughtsGet } from "@serino/api-client/site";
import type { ContentEntryRead } from "@serino/api-client/models";
import type { BaseViewPageConfig } from "@/lib/page-config";

const CommentSection = lazy(() => import("@/components/CommentSection"));

interface Thought {
  id: string;
  content: string;
  date: string;
  isArchived: boolean;
  likes: number;
  comments: number;
  mood?: string;
  category: string;
}

interface ThoughtsPageConfig extends BaseViewPageConfig {
  categories?: {
    all?: string;
  };
}

const mapRemoteThought = (entry: ContentEntryRead): Thought => {
  return {
    id: entry.slug,
    content: entry.body || entry.summary?.trim() || "",
    date:
      entry.relative_date ?? (formatPublishedDate(entry.published_at) || ""),
    isArchived: entry.status === "archived",
    likes: entry.like_count ?? 0,
    comments: entry.comment_count ?? 0,
    mood: entry.mood ?? undefined,
    category: entry.category || "",
  };
};

const buildPreviewThought = (preview: {
  slug?: string;
  title: string;
  summary?: string;
  body?: string;
  published_at?: string | null;
  mood?: string;
  category?: string;
}, draftLabel: string): Thought => {
  return {
    id: preview.slug || "__preview-thought",
    content: preview.body || preview.summary?.trim() || "",
    date: formatPublishedDate(preview.published_at) || draftLabel,
    isArchived: false,
    likes: 0,
    comments: 0,
    mood: preview.mood ?? undefined,
    category: preview.category || "",
  };
};

const ThoughtLikeButton = ({
  thoughtId,
  initialLikes,
  disabled = false,
}: {
  thoughtId: string;
  initialLikes: number;
  disabled?: boolean;
}) => {
  const reaction = useContentReaction({
    contentType: disabled ? null : "thoughts",
    slug: disabled ? null : thoughtId,
    initialTotal: initialLikes,
    enabled: !disabled,
  });

  return (
    <button
      type="button"
      onClick={() => void reaction.toggle()}
      disabled={!reaction.enabled || reaction.busy}
      aria-pressed={reaction.active}
      className={`flex items-center gap-1.5 transition-colors active:scale-[0.95] disabled:cursor-default disabled:opacity-50 ${
        reaction.active
          ? "text-[rgb(var(--shiro-accent-rgb)/0.76)]"
          : "hover:text-[rgb(var(--shiro-accent-rgb)/0.76)]"
      }`}
    >
      <Heart className={`h-3.5 w-3.5 ${reaction.active ? "fill-current" : ""}`} />
      {reaction.count}
    </button>
  );
};

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

const Thoughts = () => {
  const { t, lang } = useFrontendI18n();
  const location = useLocation();
  const previewStorageKey =
    new URLSearchParams(location.search).get("previewStorageKey") || "";
  const config = usePageConfig().thoughts as unknown as ThoughtsPageConfig;
  const errorTitle = config.errorTitle ?? t("thoughts.errorTitle");
  const retryLabel = config.retryLabel ?? t("common.retry");
  const loadMoreLabel = config.loadMoreLabel ?? t("thoughts.loadingMore");
  const pageSize = clampPageSize(config.pageSize, 15);
  const allCategoryLabel = config.categories?.all ?? t("thoughts.allCategory");
  const [expandedCommentId, setExpandedCommentId] = useState<string | null>(
    null,
  );
  const searchPlaceholder = config.searchPlaceholder ?? t("thoughts.searchPlaceholder");
  const [search, setSearch] = useState("");
  const [rawSearch, setRawSearch] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
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
    queryKey: ["site", "thoughts"],
    queryFn: async (p) => {
      const data = (await readThoughtsApiV1SiteThoughtsGet(p)).data;

      if (data && "items" in data && Array.isArray(data.items)) {
        return {
          items: data.items,
          has_more: Boolean(data.has_more),
        };
      }

      throw new Error(t("thoughts.invalidResponse"));
    },
    pageSize,
    mapItem: mapRemoteThought,
  });
  const previewThought =
    previewData?.type === "thoughts" ? buildPreviewThought(previewData, t("common.draft")) : null;
  const displayItems = useMemo(() => {
    if (!previewThought) {
      return items;
    }

    return [
      previewThought,
      ...items.filter((item) => item.id !== previewThought.id),
    ];
  }, [items, previewThought]);
  const viewStatus: typeof status =
    previewThought && status !== "ready" ? "ready" : status;

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
      ...Array.from(
        new Set(displayItems.map((item) => item.category).filter(Boolean)),
      ).sort((a, b) => a.localeCompare(b, lang === "zh" ? "zh-CN" : "en-US")),
    ],
    [allCategoryLabel, displayItems, lang],
  );

  const filtered = useMemo(() => {
    return displayItems.filter((thought) => {
      const matchSearch = matchesSearchText(
        [thought.content, thought.date, thought.mood, thought.category],
        search,
      );
      const matchCategory =
        activeCategory === allCategoryLabel ||
        thought.category === activeCategory;
      return matchSearch && matchCategory;
    });
  }, [activeCategory, allCategoryLabel, displayItems, search]);

  useEffect(() => {
    const targetId = previewThought?.id || location.hash.slice(1);
    if (viewStatus !== "ready" || !targetId) {
      return;
    }

    const element = document.getElementById(targetId);
    if (element) {
      requestAnimationFrame(() => {
        element.scrollIntoView({ block: "center" });
      });
    }
  }, [location.hash, previewThought?.id, viewStatus]);

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={
        config.width === "narrow" ? "content" : (config.width ?? "content")
      }
    >
      {previewThought ? <PreviewModeBadge /> : null}
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

      <div className="relative mt-8">
        <div className="absolute bottom-0 left-5 top-0 w-px bg-[rgb(var(--shiro-divider-rgb)/0.26)]" />

        {viewStatus === "loading" &&
          Array.from({ length: 6 }, (_, index) => (
            <div
              key={`thought-skeleton-${index}`}
              className="relative pb-10 pl-14 last:pb-0"
            >
              <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-foreground/12 bg-background" />
              <div className="h-3 w-28 rounded-full bg-foreground/[0.05]" />
              <div className="mt-3 h-4 w-[88%] rounded-full bg-foreground/[0.04]" />
              <div className="mt-2 h-4 w-[72%] rounded-full bg-foreground/[0.035]" />
              <div className="mt-4 flex items-center gap-5">
                <div className="h-3.5 w-10 rounded-full bg-foreground/[0.035]" />
                <div className="h-3.5 w-10 rounded-full bg-foreground/[0.035]" />
                <div className="h-3.5 w-10 rounded-full bg-foreground/[0.03]" />
              </div>
            </div>
          ))}

        {viewStatus === "error" && (
          <div className="relative pb-10 pl-14">
            <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-[rgb(var(--shiro-border-rgb)/0.28)] bg-background" />
            <div className="flex items-center gap-2 text-xs text-foreground/25">
              <span>{t("recentActivity.justNow")}</span>
            </div>
            <p className="mt-2 text-[0.935rem] leading-7 text-foreground/60">
              {errorTitle}
            </p>
            <p className="mt-2 text-sm leading-7 text-foreground/30">
              {errorMessage}
            </p>
            <div className="mt-3">
              <button
                type="button"
                onClick={() => reload()}
                className="text-xs text-foreground/25 transition-colors hover:text-foreground/45"
              >
                {retryLabel}
              </button>
            </div>
          </div>
        )}

        {(viewStatus === "empty" ||
          (viewStatus === "ready" && filtered.length === 0)) && (
          <div className="relative pb-10 pl-14">
            <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-[rgb(var(--shiro-border-rgb)/0.28)] bg-background" />
            <div className="flex items-center gap-2 text-xs text-foreground/25">
              <span>{t("common.today")}</span>
            </div>
            <p className="mt-2 text-[0.935rem] leading-7 text-foreground/60">
              {config.emptyMessage ?? t("thoughts.emptyMessage")}
            </p>
          </div>
        )}

        {viewStatus === "ready" &&
          filtered.map((thought, index) => (
            <motion.div
              key={thought.id}
              id={thought.id}
              className="group relative pb-10 pl-14 last:pb-0"
              {...staggerItem(index, {
                baseDelay: config.motion.delay,
                step: config.motion.stagger,
                duration: config.motion.duration,
              })}
            >
              <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-[rgb(var(--shiro-border-rgb)/0.32)] bg-background transition-colors group-hover:border-[rgb(var(--shiro-accent-rgb)/0.56)] group-hover:bg-[rgb(var(--shiro-accent-rgb)/0.12)]" />

              <div className="flex flex-wrap items-center gap-2 text-xs text-foreground/25 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]">
                {thought.isArchived ? <ArchiveBadge /> : null}
                {thought.date && (
                  <span className="transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.84)]">
                    {thought.date}
                  </span>
                )}
                {thought.mood && (
                  <span className="transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]">
                    {thought.mood}
                  </span>
                )}
              </div>

              <p className="mt-2 whitespace-pre-wrap text-[0.97rem] leading-7 text-foreground/71 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.8)]">
                {thought.content}
              </p>

              {thought.category ? (
                <div className="mt-3 text-[10px] text-foreground/20 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.58)]">
                  {thought.category}
                </div>
              ) : null}

              <div className="mt-3 flex items-center gap-5 text-xs text-foreground/20 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.42)]">
                <ThoughtLikeButton
                  thoughtId={thought.id}
                  initialLikes={thought.likes}
                  disabled={previewThought?.id === thought.id}
                />
                <button
                  type="button"
                  onClick={() =>
                    setExpandedCommentId(
                      expandedCommentId === thought.id ? null : thought.id,
                    )
                  }
                  className={`flex items-center gap-1.5 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.76)] active:scale-[0.95] ${expandedCommentId === thought.id ? "text-[rgb(var(--shiro-accent-rgb)/0.76)]" : ""}`}
                  >
                    <MessageCircle
                      className={`h-3.5 w-3.5 ${expandedCommentId === thought.id ? "fill-[rgb(var(--shiro-panel-rgb)/0.34)]" : ""}`}
                    />
                    {thought.comments}
                  </button>
              </div>

              <AnimatePresence>
                {expandedCommentId === thought.id && (
                  <motion.div
                    initial={{ height: 0, opacity: 0 }}
                    animate={{ height: "auto", opacity: 1 }}
                    exit={{ height: 0, opacity: 0 }}
                    transition={{ duration: 0.35, ease: [0.16, 1, 0.3, 1] }}
                    className="mt-4 overflow-hidden"
                  >
                    <Suspense fallback={null}>
                      <CommentSection
                        contentType="thoughts"
                        contentSlug={thought.id}
                        expandable={false}
                      />
                    </Suspense>
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
          ))}
      </div>

      {viewStatus === "ready" && hasMore && (
        <div ref={sentinelRef} className="py-8 text-center">
          {isLoadingMore && (
            <span className="text-xs text-foreground/25">{loadMoreLabel}</span>
          )}
        </div>
      )}
    </PageShell>
  );
};

export default Thoughts;
