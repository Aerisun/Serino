import { Suspense, useCallback, useDeferredValue, useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Heart, MessageCircle, Search } from "lucide-react";
import { useLocation } from "react-router-dom";
import ArchiveBadge from "@/components/ArchiveBadge";
import CommentMarkdownRenderer from "@/components/CommentMarkdownRenderer";
import { ImageLoadQueueProvider } from "@/components/QueuedAttachmentImage";
import PageShell from "@/components/PageShell";
import PreviewModeBadge from "@/components/PreviewModeBadge";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/runtime-config";
import { useContentReaction } from "@/hooks/use-content-reaction";
import { useFrontendI18n } from "@/i18n";
import { useInfiniteList } from "@/hooks/use-infinite-list";
import { clampPageSize } from "@/lib/page-size";
import { formatContentRelativeDate } from "@/lib/api/utils";
import { lazyWithPreload } from "@/lib/lazy";
import { usePreviewChannel } from "@/lib/preview";
import { readThoughtsApiV1SiteThoughtsGet } from "@serino/api-client/site";
import type { ContentEntryRead } from "@serino/api-client/models";
import type { BaseViewPageConfig } from "@/lib/page-config";

const CommentSection = lazyWithPreload(() => import("@/components/CommentSection"));

interface Thought {
  id: string;
  content: string;
  date: string;
  isArchived: boolean;
  likes: number;
  comments: number;
  mood?: string;
}

type ThoughtsPageConfig = BaseViewPageConfig;

type TranslateFn = (
  key: string,
  values?: Record<string, string | number>,
  fallback?: string,
) => string;

const mapRemoteThought = (
  entry: ContentEntryRead,
  t: TranslateFn,
  lang: "zh" | "en",
  now: number,
): Thought => {
  return {
    id: entry.slug,
    content: entry.body || entry.summary?.trim() || "",
    date: formatContentRelativeDate(entry, t, lang, now),
    isArchived: entry.visibility === "private",
    likes: entry.like_count ?? 0,
    comments: entry.comment_count ?? 0,
    mood: entry.mood ?? undefined,
  };
};

const buildPreviewThought = (
  preview: {
    slug?: string;
    title: string;
    summary?: string;
    body?: string;
    published_at?: string | null;
    mood?: string;
  },
  draftLabel: string,
  t: TranslateFn,
  lang: "zh" | "en",
  now: number,
): Thought => {
  return {
    id: preview.slug || "__preview-thought",
    content: preview.body || preview.summary?.trim() || "",
    date: formatContentRelativeDate(preview, t, lang, now) || draftLabel,
    isArchived: false,
    likes: 0,
    comments: 0,
    mood: preview.mood ?? undefined,
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
  const pages = usePageConfig();
  const config = pages.thoughts as unknown as ThoughtsPageConfig;
  const errorTitle = config.errorTitle ?? t("thoughts.errorTitle");
  const retryLabel = config.retryLabel ?? t("common.retry");
  const loadMoreLabel = config.loadMoreLabel ?? t("thoughts.loadingMore");
  const pageSize = clampPageSize(config.pageSize, 15);
  const [expandedCommentId, setExpandedCommentId] = useState<string | null>(
    null,
  );
  const searchPlaceholder = config.searchPlaceholder ?? t("thoughts.searchPlaceholder");
  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [relativeNow, setRelativeNow] = useState(() => Date.now());
  const { data: previewData } = usePreviewChannel(previewStorageKey);
  const mapThoughtItem = useCallback(
    (entry: ContentEntryRead) => mapRemoteThought(entry, t, lang, relativeNow),
    [lang, relativeNow, t],
  );

  useEffect(() => {
    const timer = window.setInterval(() => {
      setRelativeNow(Date.now());
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const {
    items,
    status,
    errorMessage,
    hasMore,
    isLoadingMore,
    sentinelRef,
    reload,
  } = useInfiniteList({
    queryKey: ["site", "thoughts", pageSize],
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
    mapItem: mapThoughtItem,
    staleTime: 60_000,
    gcTime: 20 * 60_000,
  });
  const previewThought =
    previewData?.type === "thoughts"
      ? buildPreviewThought(previewData, t("common.draft"), t, lang, relativeNow)
      : null;
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
  const filtered = useMemo(() => {
    return displayItems.filter((thought) => {
      const matchSearch = matchesSearchText(
        [thought.content, thought.date, thought.mood],
        deferredSearch,
      );
      return matchSearch;
    });
  }, [deferredSearch, displayItems]);

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
      noIndex={Boolean(previewThought)}
      width={
        config.width === "narrow" ? "content" : (config.width ?? "content")
      }
      contentClassName="mt-0 sm:mt-10"
    >
      <ImageLoadQueueProvider>
        {previewThought ? <PreviewModeBadge /> : null}
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
        </div>

      <div className="relative mt-6 sm:mt-8">
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

              <CommentMarkdownRenderer
                content={thought.content}
                className="content-detail-markdown mt-2 text-[0.97rem] leading-7 text-foreground/90 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.8)] [&>p:first-child]:mt-0 [&>p:last-child]:mb-0"
                indentParagraphs
              />

              <div className="mt-3 flex items-center gap-5 text-xs text-foreground/20 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.42)]">
                <ThoughtLikeButton
                  thoughtId={thought.id}
                  initialLikes={thought.likes}
                  disabled={previewThought?.id === thought.id}
                />
                <button
                  type="button"
                  onMouseEnter={() => void CommentSection.preload()}
                  onFocus={() => void CommentSection.preload()}
                  onTouchStart={() => void CommentSection.preload()}
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
      </ImageLoadQueueProvider>
    </PageShell>
  );
};

export default Thoughts;
