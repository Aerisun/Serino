import { useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Heart, MessageCircle } from "lucide-react";
import { useLocation, useParams } from "react-router-dom";
import { transition } from "@/config";
import {
  buildWalineSurfacePath,
  DEFAULT_COMMUNITY_CONFIG,
  loadCommunityConfig,
  type CommunityConfig,
} from "@/lib/community-config";
import WalineSurface from "@/components/WalineSurface";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

type CommentSurface = "posts" | "diary" | "guestbook" | "thoughts" | "excerpts";

interface CommentSectionProps {
  contentType?: CommentSurface;
  contentSlug?: string;
  expandable?: boolean;
}

interface CommentContext {
  contentType: CommentSurface;
  slug: string;
}

const LIKE_STORAGE_PREFIX = "aerisun:liked:";

const resolveCommentContext = (
  contentType: CommentSurface | undefined,
  contentSlug: string | undefined,
  pathname: string,
  routeId: string | undefined,
): CommentContext | null => {
  if (contentType === "guestbook") {
    return { contentType: "guestbook", slug: "guestbook" };
  }

  if (
    (contentType === "posts" || contentType === "diary" || contentType === "thoughts" || contentType === "excerpts") &&
    contentSlug
  ) {
    return { contentType, slug: contentSlug };
  }

  if (pathname.startsWith("/guestbook")) {
    return { contentType: "guestbook", slug: "guestbook" };
  }

  const fallbackSlug = routeId ? decodeURIComponent(routeId) : "";
  if (pathname.startsWith("/posts/") && fallbackSlug) {
    return { contentType: "posts", slug: fallbackSlug };
  }
  if (pathname.startsWith("/diary/") && fallbackSlug) {
    return { contentType: "diary", slug: fallbackSlug };
  }

  return null;
};

/**
 * Like via Waline's /api/article counter endpoint (reaction0 field).
 * This is the same mechanism Waline's built-in reaction feature uses.
 */
const useLike = (ctx: CommentContext | null, config: CommunityConfig | null) => {
  const [liked, setLiked] = useState(false);
  const [count, setCount] = useState(0);
  const [busy, setBusy] = useState(false);

  const serverURL = (config ?? DEFAULT_COMMUNITY_CONFIG).serverURL.replace(/\/+$/, "");
  const walinePath = ctx && ctx.contentType !== "guestbook"
    ? buildWalineSurfacePath(ctx.contentType, ctx.slug)
    : null;

  // Fetch current count
  useEffect(() => {
    if (!walinePath || !serverURL) return;
    const storageKey = `${LIKE_STORAGE_PREFIX}${walinePath}`;
    setLiked(localStorage.getItem(storageKey) === "1");

    fetch(`${serverURL}/api/article?path=${encodeURIComponent(walinePath)}&type=reaction0&lang=zh-CN`)
      .then((r) => r.ok ? r.json() : null)
      .then((data) => {
        if (data && Array.isArray(data.data) && data.data.length > 0) {
          setCount(data.data[0].reaction0 ?? 0);
        }
      })
      .catch(() => {});
  }, [walinePath, serverURL]);

  const toggle = useCallback(async () => {
    if (!walinePath || !serverURL || busy) return;
    setBusy(true);
    const action = liked ? "desc" : "inc";
    try {
      const res = await fetch(`${serverURL}/api/article`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ path: walinePath, type: "reaction0", action }),
      });
      if (res.ok) {
        const data = await res.json();
        const newCount = data.data?.[0]?.reaction0 ?? (liked ? Math.max(count - 1, 0) : count + 1);
        setCount(newCount);
        const newLiked = !liked;
        setLiked(newLiked);
        if (newLiked) {
          localStorage.setItem(`${LIKE_STORAGE_PREFIX}${walinePath}`, "1");
        } else {
          localStorage.removeItem(`${LIKE_STORAGE_PREFIX}${walinePath}`);
        }
      }
    } catch {
      // silently fail
    } finally {
      setBusy(false);
    }
  }, [walinePath, serverURL, liked, busy, count]);

  return { liked, count, busy, toggle, enabled: walinePath !== null };
};

const CommentSection = ({
  contentType,
  contentSlug,
  expandable,
}: CommentSectionProps) => {
  const prefersReducedMotion = useReducedMotionPreference();
  const location = useLocation();
  const { id } = useParams();
  const [showComments, setShowComments] = useState(false);
  const [config, setConfig] = useState<CommunityConfig | null>(null);

  const contentContext = useMemo(
    () => resolveCommentContext(contentType, contentSlug, location.pathname, id),
    [contentSlug, contentType, id, location.pathname],
  );

  const isCollapsible = expandable ?? (contentContext?.contentType !== "guestbook");
  const like = useLike(contentContext, config);

  useEffect(() => {
    loadCommunityConfig().then(setConfig).catch(() => {});
  }, []);

  useEffect(() => {
    setShowComments(!isCollapsible && contentContext !== null);
  }, [contentContext, isCollapsible]);

  const body = contentContext ? (
    <WalineSurface
      surface={contentContext.contentType}
      slug={contentContext.contentType === "guestbook" ? undefined : contentContext.slug}
      communityConfig={config}
    />
  ) : (
    <div className="liquid-glass rounded-[1.5rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] px-5 py-6 text-sm font-body text-foreground/45">
      当前页面缺少评论上下文，暂时无法挂载评论区。
    </div>
  );

  /* Guestbook: always expanded, no toggle */
  if (!isCollapsible) {
    return (
      <motion.div
        className="mt-12"
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={transition({ duration: 0.5, delay: 0.2, reducedMotion: prefersReducedMotion })}
      >
        {body}
      </motion.div>
    );
  }

  const btnBase =
    "inline-flex items-center gap-2 rounded-full border px-5 py-2.5 text-sm font-body transition-all active:scale-[0.97]";

  /* Posts / diary / thoughts / excerpts */
  return (
    <motion.section
      className="mt-12"
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      transition={transition({ duration: 0.5, delay: 0.2, reducedMotion: prefersReducedMotion })}
    >
      <div className="flex flex-wrap items-center gap-3">
        {/* Like button — writes to Waline counter (reaction0) */}
        {like.enabled && (
          <button
            type="button"
            onClick={like.toggle}
            disabled={like.busy}
            className={`${btnBase} disabled:cursor-default ${
              like.liked
                ? "border-[rgb(var(--shiro-accent-rgb)/0.28)] text-[rgb(var(--shiro-accent-rgb)/0.85)]"
                : "border-[rgb(var(--shiro-border-rgb)/0.18)] text-foreground/45 hover:border-[rgb(var(--shiro-accent-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.76)]"
            }`}
          >
            <Heart className={`h-4 w-4 ${like.liked ? "fill-current" : ""}`} />
            <span className="tabular-nums">{like.count}</span>
          </button>
        )}

        {/* Comment toggle */}
        <button
          type="button"
          onClick={() => setShowComments((v) => !v)}
          disabled={!contentContext}
          className={`${btnBase} disabled:opacity-50 ${
            showComments
              ? "border-[rgb(var(--shiro-accent-rgb)/0.28)] text-[rgb(var(--shiro-accent-rgb)/0.82)]"
              : "border-[rgb(var(--shiro-border-rgb)/0.18)] text-foreground/45 hover:border-[rgb(var(--shiro-accent-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.76)]"
          }`}
        >
          <MessageCircle className={`h-4 w-4 ${showComments ? "fill-[rgb(var(--shiro-panel-rgb)/0.34)]" : ""}`} />
          {showComments ? "收起评论" : "展开评论"}
        </button>
      </div>

      <AnimatePresence initial={false}>
        {showComments ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={transition({ duration: 0.35, reducedMotion: prefersReducedMotion })}
            className="mt-4 overflow-hidden"
          >
            {body}
          </motion.div>
        ) : null}
      </AnimatePresence>
    </motion.section>
  );
};

export default CommentSection;
