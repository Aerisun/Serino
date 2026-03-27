import { useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { Heart, MessageCircle, Repeat2 } from "lucide-react";
import PageShell from "@/components/PageShell";
import CommentSection from "@/components/CommentSection";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/runtime-config";
import { useInfiniteList } from "@/hooks/use-infinite-list";
import { clampPageSize } from "@/lib/page-size";
import {
  formatPublishedDate,
  splitContentParagraphs,
} from "@/lib/api/utils";
import { readThoughtsApiV1SiteThoughtsGet } from "@serino/api-client/site";
import type { ContentEntryRead } from "@serino/api-client/models";
import type { BaseViewPageConfig } from "@/lib/page-config";

interface Thought {
  id: string;
  content: string;
  date: string;
  likes: number;
  comments: number;
  reposts: number;
  mood?: string;
}

type ThoughtsPageConfig = BaseViewPageConfig;

const mapRemoteThought = (entry: ContentEntryRead): Thought => {
  const paragraphs = splitContentParagraphs(entry.body);

  return {
    id: entry.slug,
    content: entry.summary?.trim() || paragraphs[0] || entry.body || entry.title,
    date: entry.relative_date ?? (formatPublishedDate(entry.published_at) || ""),
    likes: entry.like_count ?? 0,
    comments: entry.comment_count ?? 0,
    reposts: entry.repost_count ?? 0,
    mood: entry.mood ?? undefined,
  };
};

const Thoughts = () => {
  const config = usePageConfig().thoughts as unknown as ThoughtsPageConfig;
  const errorTitle = config.errorTitle ?? "碎碎念加载失败";
  const retryLabel = config.retryLabel ?? "重试";
  const loadMoreLabel = config.loadMoreLabel ?? "加载更多...";
  const pageSize = clampPageSize(config.pageSize, 30);
  const [expandedCommentId, setExpandedCommentId] = useState<string | null>(null);

  const { items, status, errorMessage, hasMore, isLoadingMore, sentinelRef, reload } = useInfiniteList({
    queryKey: ["site", "thoughts"],
    queryFn: (p) => readThoughtsApiV1SiteThoughtsGet(p).then(r => r.data),
    pageSize,
    mapItem: mapRemoteThought,
  });

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
    >
      <div className="relative mt-10">
        <div className="absolute bottom-0 left-5 top-0 w-px bg-[rgb(var(--shiro-divider-rgb)/0.26)]" />

        {status === "loading" &&
          Array.from({ length: 6 }, (_, index) => (
            <div key={`thought-skeleton-${index}`} className="relative pb-10 pl-14 last:pb-0">
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

        {status === "error" && (
          <div className="relative pb-10 pl-14">
            <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-[rgb(var(--shiro-border-rgb)/0.28)] bg-background" />
            <div className="flex items-center gap-2 text-xs text-foreground/25">
              <span>刚刚</span>
            </div>
            <p className="mt-2 text-[0.935rem] leading-7 text-foreground/45">{errorTitle}</p>
            <p className="mt-2 text-sm leading-7 text-foreground/30">{errorMessage}</p>
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

        {status === "empty" && (
          <div className="relative pb-10 pl-14">
            <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-[rgb(var(--shiro-border-rgb)/0.28)] bg-background" />
            <div className="flex items-center gap-2 text-xs text-foreground/25">
              <span>今天</span>
            </div>
            <p className="mt-2 text-[0.935rem] leading-7 text-foreground/45">
              {config.emptyMessage ?? "最近没有新的碎碎念"}
            </p>
          </div>
        )}

        {status === "ready" &&
          items.map((thought, index) => (
            <motion.div
              key={thought.id}
              className="group relative pb-10 pl-14 last:pb-0"
              {...staggerItem(index, {
                baseDelay: config.motion.delay,
                step: config.motion.stagger,
                duration: config.motion.duration,
              })}
            >
              <div className="absolute left-[14px] top-1.5 h-3 w-3 rounded-full border-2 border-[rgb(var(--shiro-border-rgb)/0.32)] bg-background transition-colors group-hover:border-[rgb(var(--shiro-accent-rgb)/0.56)] group-hover:bg-[rgb(var(--shiro-accent-rgb)/0.12)]" />

              <div className="flex items-center gap-2 text-xs text-foreground/25 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]">
                {thought.date && <span className="transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.84)]">{thought.date}</span>}
                {thought.mood && <span className="transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.72)]">{thought.mood}</span>}
              </div>

              <p className="mt-2 text-[0.935rem] leading-7 text-foreground/65 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.8)]">
                {thought.content}
              </p>

              <div className="mt-3 flex items-center gap-5 text-xs text-foreground/20 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.42)]">
                <span className="flex items-center gap-1.5">
                  <Heart className="h-3.5 w-3.5" />
                  {thought.likes}
                </span>
                <button
                  type="button"
                  onClick={() => setExpandedCommentId(expandedCommentId === thought.id ? null : thought.id)}
                  className={`flex items-center gap-1.5 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.76)] active:scale-[0.95] ${expandedCommentId === thought.id ? "text-[rgb(var(--shiro-accent-rgb)/0.76)]" : ""}`}
                >
                  <MessageCircle className={`h-3.5 w-3.5 ${expandedCommentId === thought.id ? "fill-[rgb(var(--shiro-panel-rgb)/0.34)]" : ""}`} />
                  {thought.comments}
                </button>
                <button type="button" className="flex items-center gap-1.5 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.76)] active:scale-[0.95]">
                  <Repeat2 className="h-3.5 w-3.5" />
                  {thought.reposts}
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
                    <CommentSection
                      contentType="thoughts"
                      contentSlug={thought.id}
                      expandable={false}
                    />
                  </motion.div>
                )}
              </AnimatePresence>
            </motion.div>
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

export default Thoughts;
