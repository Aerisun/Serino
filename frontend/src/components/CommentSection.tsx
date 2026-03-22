import { useEffect, useMemo, useState } from "react";
import { motion, AnimatePresence } from "motion/react";
import { AlertCircle, CheckCircle2, Heart, MessageCircle, RefreshCcw, Clock3 } from "lucide-react";
import { useLocation, useParams } from "react-router-dom";
import { transition } from "@/config";
import { createPublicReaction } from "@/lib/api";
import { getViewerToken, getContentReactionStorageKey } from "@/lib/engagement";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import WalineSurface from "@/components/WalineSurface";
import type { CommentSurfaceActivity } from "@/lib/community-config";

type CommentSurface = "posts" | "diary" | "guestbook" | "thoughts" | "excerpts";

interface CommentSectionProps {
  commentCount?: number;
  likeCount?: number;
  contentType?: CommentSurface;
  contentSlug?: string;
  commentDescription?: string;
  commentTitle?: string;
  hideReactions?: boolean;
}

interface CommentContext {
  contentType: CommentSurface;
  slug: string;
  supportsReactions: boolean;
}

const resolveCommentContext = (
  contentType: CommentSurface | undefined,
  contentSlug: string | undefined,
  pathname: string,
  routeId: string | undefined,
): CommentContext | null => {
  if (contentType === "guestbook") {
    return {
      contentType: "guestbook",
      slug: "guestbook",
      supportsReactions: false,
    };
  }

  if ((contentType === "posts" || contentType === "diary" || contentType === "thoughts" || contentType === "excerpts") && contentSlug) {
    return {
      contentType,
      slug: contentSlug,
      supportsReactions: true,
    };
  }

  if (pathname.startsWith("/guestbook")) {
    return {
      contentType: "guestbook",
      slug: "guestbook",
      supportsReactions: false,
    };
  }

  const fallbackSlug = routeId ? decodeURIComponent(routeId) : "";
  if (pathname.startsWith("/posts/") && fallbackSlug) {
    return {
      contentType: "posts",
      slug: fallbackSlug,
      supportsReactions: true,
    };
  }

  if (pathname.startsWith("/diary/") && fallbackSlug) {
    return {
      contentType: "diary",
      slug: fallbackSlug,
      supportsReactions: true,
    };
  }

  return null;
};

const buildCommentActivityCopy = (activity: CommentSurfaceActivity | null) => {
  if (!activity) {
    return "";
  }

  switch (activity.type) {
    case "draft-restored":
      return activity.message;
    case "sort-change":
      return activity.message;
    case "avatar-change":
      return activity.message;
    case "submission-success":
      return activity.message;
    case "submission-error":
      return activity.message;
    case "status":
      return activity.message;
    case "draft-saved":
      return activity.message;
    default:
      return activity.message;
  }
};

const CommentSection = ({
  commentCount,
  likeCount,
  contentType,
  contentSlug,
  commentDescription,
  commentTitle,
  hideReactions,
}: CommentSectionProps) => {
  const [showComments, setShowComments] = useState(false);
  const [liked, setLiked] = useState(false);
  const [likeTotal, setLikeTotal] = useState<number | null>(typeof likeCount === "number" ? likeCount : null);
  const [isReacting, setIsReacting] = useState(false);
  const [errorMessage, setErrorMessage] = useState("");
  const [commentActivity, setCommentActivity] = useState<CommentSurfaceActivity | null>(null);
  const [commentDelta, setCommentDelta] = useState(0);
  const prefersReducedMotion = useReducedMotionPreference();
  const location = useLocation();
  const { id } = useParams();

  const contentContext = useMemo(
    () => resolveCommentContext(contentType, contentSlug, location.pathname, id),
    [contentSlug, contentType, id, location.pathname],
  );

  useEffect(() => {
    setErrorMessage("");
    setLikeTotal(typeof likeCount === "number" ? likeCount : null);
    setCommentActivity(null);
    setCommentDelta(0);
  }, [commentCount, contentContext?.contentType, contentContext?.slug, likeCount]);

  useEffect(() => {
    setShowComments(contentContext?.contentType === "guestbook");
  }, [contentContext?.contentType, contentContext?.slug]);

  useEffect(() => {
    if (!commentActivity) {
      return;
    }

    const timer = window.setTimeout(() => {
      setCommentActivity(null);
    }, 5200);

    return () => {
      window.clearTimeout(timer);
    };
  }, [commentActivity]);

  useEffect(() => {
    if (!contentContext?.supportsReactions || typeof window === "undefined") {
      setLiked(false);
      return;
    }

    const storageKey = getContentReactionStorageKey(contentContext.contentType, contentContext.slug);
    setLiked(window.localStorage.getItem(storageKey) === "true");
  }, [contentContext?.contentType, contentContext?.slug, contentContext?.supportsReactions]);

  const handleLikeToggle = async () => {
    if (!contentContext?.supportsReactions || liked || isReacting) {
      return;
    }

    const previousTotal = likeTotal;
    setIsReacting(true);
    setErrorMessage("");

    try {
      const payload = await createPublicReaction(
        {
          content_type: contentContext.contentType,
          content_slug: contentContext.slug,
          reaction_type: "like",
          client_token: getViewerToken(),
        },
        { credentials: "include" },
      );
      setLiked(true);
      setLikeTotal(typeof payload.total === "number" ? payload.total : (previousTotal ?? 0) + 1);
      if (typeof window !== "undefined") {
        const storageKey = getContentReactionStorageKey(contentContext.contentType, contentContext.slug);
        window.localStorage.setItem(storageKey, "true");
      }
    } catch (error) {
      setLiked(false);
      setLikeTotal(previousTotal);
      setErrorMessage(error instanceof Error ? error.message : "点赞失败");
    } finally {
      setIsReacting(false);
    }
  };

  const isGuestbook = contentContext?.contentType === "guestbook";
  const commentBadge =
    typeof commentCount === "number"
      ? String(Math.max(commentCount + commentDelta, 0))
      : isGuestbook
        ? commentDelta > 0
          ? `留言 +${commentDelta}`
          : "留言"
        : commentDelta > 0
          ? String(commentDelta)
          : "0";
  const commentTitleCopy = commentTitle ?? (isGuestbook ? "留言板" : "评论区");
  const commentDescriptionCopy =
    commentDescription ?? "昵称必填，邮箱可选，支持 Markdown / GFM、Enjoy 表情搜索和更好看的默认头像。";

  const handleCommentActivity = (activity: CommentSurfaceActivity) => {
    setCommentActivity(activity);

    if (activity.type === "submission-success") {
      setCommentDelta((current) => current + 1);
    }
  };

  const activityCopy = buildCommentActivityCopy(commentActivity);

  return (
    <motion.div
      className="mt-12"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={transition({ duration: 0.5, delay: 0.2, reducedMotion: prefersReducedMotion })}
    >
      <div className="mb-4 flex flex-wrap items-center gap-3">
        {contentContext?.supportsReactions && !hideReactions ? (
          <button
            type="button"
            onClick={handleLikeToggle}
            disabled={liked || isReacting}
            className={`liquid-glass rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.18)] px-5 py-3 flex items-center gap-2 transition-all active:scale-[0.97] disabled:opacity-50 ${
              liked
                ? "text-[rgb(var(--shiro-accent-rgb)/0.85)]"
                : "text-foreground/40 hover:border-[rgb(var(--shiro-accent-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.78)]"
            }`}
          >
            <Heart className={`h-4 w-4 ${liked ? "fill-current" : ""}`} />
            <span className="text-sm font-body font-medium tabular-nums">
              {typeof likeTotal === "number" ? likeTotal : 0}
            </span>
          </button>
        ) : null}

        <button
          type="button"
          onClick={() => setShowComments((value) => !value)}
          disabled={!contentContext}
          className={`liquid-glass rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.18)] px-5 py-3 flex items-center gap-2 transition-all active:scale-[0.97] disabled:opacity-50 ${
            showComments
              ? "text-[rgb(var(--shiro-accent-rgb)/0.82)]"
              : "text-foreground/40 hover:border-[rgb(var(--shiro-accent-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.78)]"
          }`}
        >
          <MessageCircle className={`h-4 w-4 ${showComments ? "fill-[rgb(var(--shiro-panel-rgb)/0.34)]" : ""}`} />
          <span className="text-sm font-body font-medium tabular-nums">{commentBadge}</span>
        </button>

        <div className="liquid-glass flex min-h-[2.7rem] min-w-0 flex-1 items-center gap-2 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.14)] px-4 py-2.5 text-[0.72rem] font-body text-foreground/50">
          {commentActivity ? (
            <>
              {commentActivity.type === "submission-success" ? (
                <CheckCircle2 className="h-4 w-4 text-emerald-500" />
              ) : commentActivity.type === "submission-error" ? (
                <AlertCircle className="h-4 w-4 text-rose-500" />
              ) : commentActivity.type === "sort-change" ? (
                <RefreshCcw className="h-4 w-4 text-[rgb(var(--shiro-accent-rgb)/0.78)]" />
              ) : (
                <Clock3 className="h-4 w-4 text-[rgb(var(--shiro-accent-rgb)/0.62)]" />
              )}
              <span className="truncate">{activityCopy}</span>
            </>
          ) : (
            <>
              <RefreshCcw className="h-4 w-4 text-[rgb(var(--shiro-accent-rgb)/0.62)]" />
              <span className="truncate">这里会回显草稿恢复、排序切换和评论提交状态。</span>
            </>
          )}
        </div>
      </div>

      {errorMessage ? (
        <p className="mb-4 text-xs font-body text-[rgb(var(--shiro-accent-rgb)/0.72)]">{errorMessage}</p>
      ) : null}

      <AnimatePresence>
        {showComments && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={transition({ duration: 0.35, reducedMotion: prefersReducedMotion })}
            className="overflow-hidden"
          >
            {contentContext ? (
              <WalineSurface
                surface={contentContext.contentType}
                slug={contentContext.contentType === "guestbook" ? undefined : contentContext.slug}
                title={commentTitleCopy}
                description={commentDescriptionCopy}
                onActivity={(activity) => {
                  handleCommentActivity(activity);
                }}
              />
            ) : (
              <div className="liquid-glass rounded-2xl p-6 text-sm font-body text-foreground/45">
                当前页面缺少评论上下文，暂时无法挂载评论区。
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
};

export default CommentSection;
