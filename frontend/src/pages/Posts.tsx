import { useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import { Eye, MessageCircle } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import ArchiveBadge from "@/components/ArchiveBadge";
import { CategoryFilter } from "@/components/CategoryFilter";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/runtime-config";
import { useFrontendI18n } from "@/i18n";
import { formatPostCount } from "@/lib/format";
import { formatContentRelativeDate } from "@/lib/api/utils";
import { formatDateInBeijing, getBeijingDateParts } from "@/lib/time";
import {
  readNoteApiV1SiteNotesSlugGet,
  readNotesApiV1SiteNotesGet,
  readPostApiV1SitePostsSlugGet,
  readPostsApiV1SitePostsGet,
  readCategoryStatsApiV1SiteCategoryStatsGet,
} from "@serino/api-client/site";
import type { ContentSummaryRead } from "@serino/api-client/models";
import type { BaseViewPageConfig } from "@/lib/page-config";
import { useInfiniteList } from "@/hooks/use-infinite-list";
import { clampPageSize } from "@/lib/page-size";
import { preloadPostDetailPage } from "@/lib/route-preload";

interface Post {
  slug: string;
  title: string;
  excerpt: string;
  date: string;
  publishedAt: string | null;
  isArchived: boolean;
  category: string;
  tags: string[];
  views: number;
  comments: number;
}

interface PostsPageConfig extends BaseViewPageConfig {
  categories?: {
    all?: string;
    fallback?: string;
  };
}

export type PostKind = "manuscript" | "note";

type TranslateFn = (
  key: string,
  values?: Record<string, string | number>,
  fallback?: string,
) => string;

const mapRemotePost = (
  entry: ContentSummaryRead,
  t: TranslateFn,
  lang: "zh" | "en",
  now: number,
): Post => ({
  slug: entry.slug,
  title: entry.title,
  excerpt: entry.summary ?? "",
  date: formatContentRelativeDate(entry, t, lang, now),
  publishedAt: entry.published_at ?? null,
  isArchived: entry.visibility === "private",
  category: entry.category || entry.tags[0] || "",
  tags: entry.tags,
  views: entry.view_count ?? 0,
  comments: entry.comment_count ?? 0,
});

interface NoteListDate {
  year: string;
  label: string;
}

interface NoteListGroup {
  year: string;
  items: Array<{ post: Post; date: NoteListDate | null }>;
}

const getNoteListDate = (value: string | null): NoteListDate | null => {
  const dateParts = getBeijingDateParts(value);
  if (!dateParts) return null;

  return {
    year: String(dateParts.year),
    label: formatDateInBeijing(value, "en-US", { month: "short", day: "2-digit" }),
  };
};

const Posts = ({ kind = "manuscript" }: { kind?: PostKind }) => {
  const { t, lang } = useFrontendI18n();
  const isNoteView = kind === "note";
  const pageKey = kind === "note" ? "notes" : "posts";
  const routePrefix = `/${pageKey}`;
  const config = usePageConfig()[pageKey] as unknown as PostsPageConfig;
  const allCategoryLabel = config.categories?.all ?? t("posts.allCategory");
  const fallbackCategoryLabel = config.categories?.fallback ?? t("posts.fallbackCategory");
  const searchPlaceholder = config.searchPlaceholder ?? t("posts.searchPlaceholder");
  const errorTitle = config.errorTitle ?? t("posts.errorTitle");
  const retryLabel = config.retryLabel ?? t("common.retry");
  const loadMoreLabel = config.loadMoreLabel ?? t("posts.loadingMore");
  const [search, setSearch] = useState("");
  const [rawSearch, setRawSearch] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [activeCategory, setActiveCategory] = useState<string | null>(null);
  const [relativeNow, setRelativeNow] = useState(() => Date.now());
  const pageSize = clampPageSize(config.pageSize, 15);
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const deferredSearch = useDeferredValue(search);
  const mapPostItem = useCallback(
    (entry: ContentSummaryRead) => ({
      ...mapRemotePost(entry, t, lang, relativeNow),
      category: entry.category || fallbackCategoryLabel,
    }),
    [fallbackCategoryLabel, lang, relativeNow, t],
  );

  const { items, status, errorMessage, hasMore, isLoadingMore, sentinelRef, reload } = useInfiniteList({
    queryKey: ["site", pageKey, pageSize, activeCategory],
    queryFn: (p) =>
      (kind === "note"
        ? readNotesApiV1SiteNotesGet({ ...p, category: activeCategory ?? undefined })
        : readPostsApiV1SitePostsGet({ ...p, category: activeCategory ?? undefined })
      ).then(
        (response) => response.data,
      ),
    pageSize,
    mapItem: mapPostItem,
    staleTime: 60_000,
    gcTime: 20 * 60_000,
  });
  const categoryStats = useQuery({
    queryKey: ["site", "category-stats", pageKey],
    queryFn: () => readCategoryStatsApiV1SiteCategoryStatsGet({ content_type: pageKey }).then((response) => response.data),
    staleTime: 0,
  });

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setRelativeNow(Date.now());
    }, 60_000);
    return () => window.clearInterval(timer);
  }, []);

  const filtered = useMemo(() => {
    const normalizedSearch = deferredSearch.trim().toLowerCase();

    return items.filter((post) => {
      const matchSearch =
        !normalizedSearch ||
        post.title.toLowerCase().includes(normalizedSearch) ||
        post.excerpt.toLowerCase().includes(normalizedSearch);
      return matchSearch;
    });
  }, [deferredSearch, items]);

  const noteListGroups = useMemo(() => {
    const groups = new Map<string, NoteListGroup>();

    filtered.forEach((post) => {
      const date = getNoteListDate(post.publishedAt);
      const year = date?.year ?? "—";
      const group = groups.get(year) ?? { year, items: [] };
      group.items.push({ post, date });
      groups.set(year, group);
    });

    return Array.from(groups.values());
  }, [filtered]);

  const prefetchPostDetail = useCallback((slug: string) => {
    void preloadPostDetailPage();
    void queryClient.prefetchQuery({
      queryKey: [`/api/v1/site/${pageKey}/${slug}`],
      queryFn: () =>
        kind === "note" ? readNoteApiV1SiteNotesSlugGet(slug) : readPostApiV1SitePostsSlugGet(slug),
      staleTime: 60_000,
      gcTime: 20 * 60_000,
    });
  }, [kind, pageKey, queryClient]);

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
      contentClassName="mt-0 sm:mt-10"
      headerAsideClassName={isNoteView ? "hidden sm:flex" : ""}
      headerAside={
        <span className="text-xs tracking-[0.18em] text-foreground/28">
          {isNoteView
            ? lang === "zh"
              ? `${items.length} 篇手记`
              : `${items.length} notes`
            : formatPostCount(items.length)}
        </span>
      }
    >
      <motion.div
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: config.motion.duration + 0.05, delay: config.motion.delay, ease: [0.16, 1, 0.3, 1] }}
      >
        <CategoryFilter
          search={rawSearch}
          searchPlaceholder={searchPlaceholder}
          showSearch={!isNoteView}
          onSearchChange={(value) => {
            setRawSearch(value);
            if (debounceRef.current) clearTimeout(debounceRef.current);
            debounceRef.current = setTimeout(() => setSearch(value), 300);
          }}
          allLabel={allCategoryLabel}
          activeCategory={activeCategory}
          onCategoryChange={setActiveCategory}
          stats={categoryStats.data}
          isLoading={categoryStats.isLoading}
          errorMessage={categoryStats.isError ? t("categories.loadFailed") : undefined}
          onRetry={() => void categoryStats.refetch()}
        />
      </motion.div>

      <div className={isNoteView ? "mt-10 sm:mt-9" : "mt-6 sm:mt-8"}>
        {status === "loading" &&
          Array.from({ length: 5 }, (_, index) => (
            <div
              key={`post-skeleton-${index}`}
              className="border-t border-foreground/6 py-6 first:border-t-0"
            >
              <div className="h-6 w-[55%] rounded-full bg-foreground/[0.045]" />
              <div className="mt-3 h-4 w-[82%] rounded-full bg-foreground/[0.035]" />
              <div className="mt-2 h-4 w-[64%] rounded-full bg-foreground/[0.03]" />
              <div className="mt-4 flex items-center gap-4">
                <div className="h-3 w-12 rounded-full bg-foreground/[0.03]" />
                <div className="h-3 w-14 rounded-full bg-foreground/[0.03]" />
                <div className="ml-auto h-3 w-10 rounded-full bg-foreground/[0.025]" />
                <div className="h-3 w-8 rounded-full bg-foreground/[0.025]" />
              </div>
            </div>
          ))}

        {status === "error" && (
          <div className="border-t border-foreground/6 py-16 text-center">
            <p className="text-sm text-foreground/35">{errorTitle}</p>
            <p className="mt-2 text-xs text-foreground/25">{errorMessage}</p>
            <button
              type="button"
              onClick={() => reload()}
              className="mt-4 text-xs text-foreground/30 transition-colors hover:text-foreground/55"
            >
              {retryLabel}
            </button>
          </div>
        )}

        {(status === "empty" || (status === "ready" && filtered.length === 0)) && (
          <p className="py-16 text-center text-sm text-foreground/25">
            {config.emptyMessage ?? t("posts.emptyMessage")}
          </p>
        )}

        {status === "ready" && isNoteView && (
          <div data-note-yearbook className="space-y-10 sm:space-y-14">
            {noteListGroups.map((group) => (
              <section key={group.year} data-note-year>
                <header className="flex items-baseline">
                  <h2 className="font-heading text-[1.9rem] italic leading-none tracking-[0.015em] text-foreground/90 sm:text-[2.25rem]">
                    {group.year}
                  </h2>
                </header>

                <div className="mt-5 sm:mt-6 space-y-1.5 sm:space-y-2">
                  {group.items.map(({ post, date }, i) => (
                    <motion.div
                      key={post.slug}
                      {...staggerItem(i, {
                        baseDelay: config.motion.delay + 0.04,
                        step: config.motion.stagger,
                        duration: config.motion.duration,
                      })}
                    >
                      <button
                        type="button"
                        data-note-list-item
                        onClick={() => navigate(`${routePrefix}/${post.slug}`)}
                        onMouseEnter={() => prefetchPostDetail(post.slug)}
                        onFocus={() => prefetchPostDetail(post.slug)}
                        onTouchStart={() => prefetchPostDetail(post.slug)}
                className="group relative grid w-full grid-cols-[6rem_minmax(0,1fr)] items-center gap-x-3 py-3.5 text-left transition-[color,transform] duration-300 before:absolute before:bottom-3 before:left-0 before:top-3 before:w-px before:origin-center before:scale-y-0 before:bg-[rgb(var(--shiro-accent-rgb)/0.8)] before:transition-transform before:duration-300 hover:translate-x-1 hover:before:scale-y-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--shiro-accent-rgb)/0.42)] focus-visible:ring-offset-2 focus-visible:ring-offset-background sm:grid-cols-[minmax(6rem,0.55fr)_minmax(0,1.85fr)] sm:gap-x-8 sm:py-4"
                      >
                        <time
                          data-note-date
                          dateTime={post.publishedAt ?? undefined}
                          className="pl-1.5 text-[1.4rem] leading-none tracking-normal text-foreground/48 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.78)] sm:pl-4 sm:text-[1.55rem]"
                          style={{ fontFamily: "'Pinyon Script', cursive" }}
                        >
                          {date?.label.replace(" ", "\u00A0") ?? "—"}
                        </time>
                <h3 className="truncate min-w-0 text-[1.35rem] font-medium leading-[1.2] tracking-[-0.03em] text-foreground/88 transition-[color,transform] duration-300 group-hover:translate-x-1 group-hover:text-[rgb(var(--shiro-accent-rgb)/0.98)] sm:text-[1.75rem]">
                          {post.title}
                        </h3>
                      </button>
                    </motion.div>
                  ))}
                </div>
              </section>
            ))}
          </div>
        )}

        {status === "ready" && !isNoteView &&
          filtered.map((post, i) => (
            <motion.article
              key={post.slug}
              className="group cursor-pointer border-t border-foreground/6 py-6 transition-[background-color,border-color,box-shadow] first:border-t-0 hover:bg-[rgb(var(--shiro-panel-rgb)/0.18)] hover:border-[rgb(var(--shiro-border-rgb)/0.2)]"
              onClick={() => navigate(`${routePrefix}/${post.slug}`)}
              onMouseEnter={() => prefetchPostDetail(post.slug)}
              onFocus={() => prefetchPostDetail(post.slug)}
              onTouchStart={() => prefetchPostDetail(post.slug)}
              {...staggerItem(i, {
                baseDelay: config.motion.delay + 0.04,
                step: config.motion.stagger,
                duration: config.motion.duration,
              })}
            >
              <div className="flex flex-wrap items-center gap-2">
                {post.isArchived ? <ArchiveBadge /> : null}
                <h2 className="min-w-0 flex-1 overflow-hidden text-base font-medium leading-snug text-foreground/90 transition-colors [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2] [overflow-wrap:anywhere] [word-break:break-word] group-hover:text-[rgb(var(--shiro-accent-rgb)/0.92)] sm:text-lg">
                  {post.title}
                </h2>
              </div>
              <p className="mt-2 line-clamp-2 text-sm leading-relaxed text-foreground/35 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.68)]">
                {post.excerpt}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-foreground/25 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.7)]">
                <span className="transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.76)]">{post.date}</span>
                {post.category !== fallbackCategoryLabel && (
                  <span className="transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.76)]">{post.category}</span>
                )}
                {post.tags.map((tag) => (
                  <span key={tag} className="text-foreground/20 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.62)]">
                    /{tag}
                  </span>
                ))}
                <div className="ml-auto flex shrink-0 items-center gap-4 whitespace-nowrap">
                  <span className="flex items-center gap-1 text-foreground/22 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.34)]">
                    <Eye className="h-3 w-3" />
                    {post.views.toLocaleString()}
                  </span>
                  <span className="flex items-center gap-1 text-foreground/22 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.34)]">
                    <MessageCircle className="h-3 w-3" />
                    {post.comments}
                  </span>
                </div>
              </div>
            </motion.article>
          ))}
      </div>

      {status === "ready" && hasMore && (
        <div ref={sentinelRef} className="py-8 text-center">
          {isLoadingMore && <span className="text-xs text-foreground/25">{loadMoreLabel}</span>}
        </div>
      )}
    </PageShell>
  );
};

export default Posts;
