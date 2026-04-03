import { useEffect, useRef, useState } from "react";
import { motion } from "motion/react";
import { Eye, MessageCircle, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import ArchiveBadge from "@/components/ArchiveBadge";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/runtime-config";
import { useFrontendI18n } from "@/i18n";
import { formatPostCount } from "@/lib/format";
import { formatPublishedDate } from "@/lib/api/utils";
import { readPostsApiV1SitePostsGet } from "@serino/api-client/site";
import type { ContentEntryRead } from "@serino/api-client/models";
import type { BaseViewPageConfig } from "@/lib/page-config";
import { useInfiniteList } from "@/hooks/use-infinite-list";
import { clampPageSize } from "@/lib/page-size";

interface Post {
  slug: string;
  title: string;
  excerpt: string;
  date: string;
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

const mapRemotePost = (entry: ContentEntryRead): Post => ({
  slug: entry.slug,
  title: entry.title,
  excerpt: entry.summary ?? entry.body,
  date: entry.relative_date ?? (formatPublishedDate(entry.published_at) || ""),
  isArchived: entry.status === "archived",
  category: entry.category || entry.tags[0] || "",
  tags: entry.tags,
  views: entry.view_count ?? 0,
  comments: entry.comment_count ?? 0,
});

const Posts = () => {
  const { t } = useFrontendI18n();
  const config = usePageConfig().posts as unknown as PostsPageConfig;
  const allCategoryLabel = config.categories?.all ?? t("posts.allCategory");
  const fallbackCategoryLabel = config.categories?.fallback ?? t("posts.fallbackCategory");
  const searchPlaceholder = config.searchPlaceholder ?? t("posts.searchPlaceholder");
  const errorTitle = config.errorTitle ?? t("posts.errorTitle");
  const retryLabel = config.retryLabel ?? t("common.retry");
  const loadMoreLabel = config.loadMoreLabel ?? t("posts.loadingMore");
  const [search, setSearch] = useState("");
  const [rawSearch, setRawSearch] = useState("");
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [activeCategory, setActiveCategory] = useState(allCategoryLabel);
  const pageSize = clampPageSize(config.pageSize, 15);
  const navigate = useNavigate();

  const { items, status, errorMessage, hasMore, isLoadingMore, sentinelRef, reload } = useInfiniteList({
    queryKey: ["site", "posts"],
    queryFn: (p) => readPostsApiV1SitePostsGet(p).then(r => r.data),
    pageSize,
    mapItem: (entry) => ({
      ...mapRemotePost(entry),
      category: entry.category || fallbackCategoryLabel,
    }),
  });

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  const allCategories = [
    allCategoryLabel,
    ...Array.from(new Set(items.map((item) => item.category))).filter(
      (category) => category !== fallbackCategoryLabel,
    ),
  ];

  const filtered = items.filter((post) => {
    const matchSearch =
      !search ||
      post.title.toLowerCase().includes(search.toLowerCase()) ||
      post.excerpt.toLowerCase().includes(search.toLowerCase());
    const matchCategory = activeCategory === allCategoryLabel || post.category === activeCategory;
    return matchSearch && matchCategory;
  });

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
      headerAside={
        <span className="text-xs tracking-[0.18em] text-foreground/28">
          {formatPostCount(items.length)}
        </span>
      }
    >
      <motion.div
        className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: config.motion.duration + 0.05, delay: config.motion.delay, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="group relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground/25 transition-colors group-focus-within:text-[rgb(var(--shiro-accent-rgb)/0.72)]" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={rawSearch}
            onChange={(event) => {
              const val = event.target.value;
              setRawSearch(val);
              if (debounceRef.current) clearTimeout(debounceRef.current);
              debounceRef.current = setTimeout(() => setSearch(val), 300);
            }}
            maxLength={100}
            aria-label={searchPlaceholder}
            className="w-full rounded-xl border border-foreground/8 bg-foreground/[0.03] py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-foreground/25 outline-none transition-colors focus:border-[rgb(var(--shiro-border-rgb)/0.32)] focus:bg-[rgb(var(--shiro-panel-rgb)/0.35)]"
          />
        </div>

        <div className="flex flex-wrap gap-1.5">
          {allCategories.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(cat)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors active:scale-[0.97] ${
                activeCategory === cat
                  ? "bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.9)]"
                  : "text-foreground/35 hover:bg-[rgb(var(--shiro-panel-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </motion.div>

      <div className="mt-8">
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

        {status === "ready" &&
          filtered.map((post, i) => (
            <motion.article
              key={post.slug}
              className="group cursor-pointer border-t border-foreground/6 py-6 transition-[background-color,border-color,box-shadow] first:border-t-0 hover:bg-[rgb(var(--shiro-panel-rgb)/0.18)] hover:border-[rgb(var(--shiro-border-rgb)/0.2)]"
              onClick={() => navigate(`/posts/${post.slug}`)}
              {...staggerItem(i, {
                baseDelay: config.motion.delay + 0.04,
                step: config.motion.stagger,
                duration: config.motion.duration,
              })}
            >
              <div className="flex flex-wrap items-center gap-2">
                {post.isArchived ? <ArchiveBadge /> : null}
                <h2 className="min-w-0 text-base font-medium leading-snug text-foreground/90 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.92)] sm:text-lg">
                  {post.title}
                </h2>
              </div>
              <p className="mt-2 line-clamp-1 text-sm leading-relaxed text-foreground/35 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.68)]">
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
                <span className="ml-auto flex items-center gap-1 text-foreground/22 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.34)]">
                  <Eye className="h-3 w-3" />
                  {post.views.toLocaleString()}
                </span>
                <span className="flex items-center gap-1 text-foreground/22 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.34)]">
                  <MessageCircle className="h-3 w-3" />
                  {post.comments}
                </span>
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
