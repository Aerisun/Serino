import { lazy, Suspense, useEffect, useMemo, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Heart, MessageCircle } from "lucide-react";
import { useLocation, useParams } from "react-router-dom";
import { transition } from "@/config";
import { useFrontendI18n } from "@/i18n";
import { useContentReaction, type ContentReactionSurface } from "@/hooks/use-content-reaction";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

type CommentSurface = ContentReactionSurface | "guestbook";

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

const resolveCommentContext = (
  contentType: CommentSurface | undefined,
  contentSlug: string | undefined,
  pathname: string,
  routeId: string | undefined,
): CommentContext | null => {
  if (contentType === "guestbook") {
    return { contentType: "guestbook", slug: "guestbook" };
  }

  if (contentType === "friends") {
    return { contentType: "friends", slug: contentSlug || "friends" };
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

  if (pathname.startsWith("/friends")) {
    return { contentType: "friends", slug: "friends" };
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

  const contentContext = useMemo(
    () => resolveCommentContext(contentType, contentSlug, location.pathname, id),
    [contentSlug, contentType, id, location.pathname],
  );
  const reactionContentType = contentContext && contentContext.contentType !== "guestbook"
    ? contentContext.contentType
    : null;

  const isCollapsible = expandable ?? (contentContext?.contentType !== "guestbook");
  const like = useContentReaction({
    contentType: reactionContentType,
    slug: reactionContentType ? contentContext?.slug ?? null : null,
  });
  const shouldLoadSurface = contentContext !== null && (!isCollapsible || showComments);

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
            disabled={like.busy}
            aria-pressed={like.active}
            className={`${btnBase} disabled:cursor-default ${
              like.active
                ? "border-[rgb(var(--shiro-accent-rgb)/0.28)] text-[rgb(var(--shiro-accent-rgb)/0.85)]"
                : "border-[rgb(var(--shiro-border-rgb)/0.18)] text-foreground/45 hover:border-[rgb(var(--shiro-accent-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.76)]"
            }`}
          >
            <Heart className={`h-4 w-4 ${like.active ? "fill-current" : ""}`} />
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
