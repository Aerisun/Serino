import { lazy, Suspense, useCallback, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Heart, MessageCircle } from "lucide-react";
import { useLocation, useParams } from "react-router-dom";
import { transition } from "@/config";
import { useFrontendI18n } from "@/i18n";
import {
  loadCommunityConfig,
  type CommunityConfig,
} from "@/lib/community-config";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import {
  createReactionApiV1SiteInteractionsReactionsPost,
  readReactionApiV1SiteInteractionsReactionsContentTypeSlugReactionTypeGet,
} from "@serino/api-client/site-interactions";

type CommentSurface = "posts" | "diary" | "guestbook" | "thoughts" | "excerpts";

const WalineSurface = lazy(() => import("@/components/WalineSurface"));

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
const LIKE_TOKEN_PREFIX = "aerisun:like-token:";

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
 * Like via the site's public reaction API.
 * Reactions are append-only, so once liked on this device the button stays active.
 */
const useLike = (ctx: CommentContext | null) => {
  const [liked, setLiked] = useState(false);
  const [count, setCount] = useState(0);
  const [busy, setBusy] = useState(false);

  const reactionKey = ctx && ctx.contentType !== "guestbook" ? `${ctx.contentType}:${ctx.slug}` : null;

  useEffect(() => {
    if (!ctx || ctx.contentType === "guestbook" || !reactionKey) return;
    const storageKey = `${LIKE_STORAGE_PREFIX}${reactionKey}`;
    setLiked(localStorage.getItem(storageKey) === "1");

    readReactionApiV1SiteInteractionsReactionsContentTypeSlugReactionTypeGet(ctx.contentType, ctx.slug, "like")
      .then((response) => {
        setCount(response.data.total ?? 0);
      })
      .catch(() => {});
  }, [ctx, reactionKey]);

  const toggle = useCallback(async () => {
    if (!ctx || ctx.contentType === "guestbook" || !reactionKey || liked || busy) return;
    setBusy(true);
    try {
      const tokenStorageKey = `${LIKE_TOKEN_PREFIX}${reactionKey}`;
      let clientToken = localStorage.getItem(tokenStorageKey);
      if (!clientToken) {
        clientToken = `${reactionKey}:${Math.random().toString(36).slice(2)}`;
        localStorage.setItem(tokenStorageKey, clientToken);
      }

      const response = await createReactionApiV1SiteInteractionsReactionsPost({
        content_type: ctx.contentType,
        content_slug: ctx.slug,
        reaction_type: "like",
        client_token: clientToken,
      });
      setCount(response.data.total ?? count + 1);
      setLiked(true);
      localStorage.setItem(`${LIKE_STORAGE_PREFIX}${reactionKey}`, "1");
    } catch {
      // silently fail
    } finally {
      setBusy(false);
    }
  }, [busy, count, ctx, liked, reactionKey]);

  return { liked, count, busy, toggle, enabled: ctx !== null && ctx.contentType !== "guestbook" };
};

const CommentSection = ({
  contentType,
  contentSlug,
  expandable,
}: CommentSectionProps) => {
  const { t } = useFrontendI18n();
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
  const like = useLike(contentContext);
  const shouldLoadSurface = contentContext !== null && (!isCollapsible || showComments);

  useEffect(() => {
    if (!shouldLoadSurface || config) {
      return;
    }
    loadCommunityConfig().then(setConfig).catch(() => {});
  }, [config, shouldLoadSurface]);

  useEffect(() => {
    setShowComments(!isCollapsible && contentContext !== null);
  }, [contentContext, isCollapsible]);

  const body = contentContext ? (
    shouldLoadSurface ? (
      <Suspense
        fallback={
          <div className="liquid-glass rounded-[1.5rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] px-5 py-6 text-sm font-body text-foreground/45">
            {t("comments.loading")}
          </div>
        }
      >
        <WalineSurface
          surface={contentContext.contentType}
          slug={contentContext.contentType === "guestbook" ? undefined : contentContext.slug}
          communityConfig={config}
        />
      </Suspense>
    ) : null
  ) : (
    <div className="liquid-glass rounded-[1.5rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] px-5 py-6 text-sm font-body text-foreground/45">
      {t("comments.missingContext")}
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
            disabled={like.busy || like.liked}
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
          {showComments ? t("comments.collapse") : t("comments.expand")}
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
