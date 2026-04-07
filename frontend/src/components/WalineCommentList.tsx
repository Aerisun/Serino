import { useEffect, useMemo, useState, type ReactNode } from "react";
import { ArrowUpRight, ChevronDown, Loader2, RefreshCw, Reply, Sparkles } from "lucide-react";
import CommentMarkdownRenderer from "@/components/CommentMarkdownRenderer";
import { useFrontendI18n } from "@/i18n";
import {
  COMMENT_JUMP_REQUEST_EVENT,
  buildCommentAnchorId,
  communityActionClass,
  communityAvatarClass,
  fallbackAvatar,
  formatTimestamp,
  scrollToCommentTarget,
  StatusPill,
  type CommunityCommentItem,
  type CommunityGuestbookItem,
  type ReplyTarget,
} from "./waline-types";

type FlattenedReply = CommunityCommentItem & {
  replyToId: string;
  replyToName: string;
  threadDepth: number;
};

const flattenReplies = (
  items: CommunityCommentItem[],
  replyToId: string,
  replyToName: string,
  threadDepth = 1,
): FlattenedReply[] =>
  items.flatMap((item) => [
    {
      ...item,
      replyToId,
      replyToName,
      threadDepth,
    },
    ...flattenReplies(item.replies ?? [], item.id, item.author_name, threadDepth + 1),
  ]);

const buildCommentRootLookup = (items: CommunityCommentItem[]) => {
  const lookup = new Map<string, string>();

  const visit = (item: CommunityCommentItem, rootId: string) => {
    lookup.set(item.id, rootId);
    (item.replies ?? []).forEach((reply) => visit(reply, rootId));
  };

  items.forEach((item) => visit(item, item.id));

  return lookup;
};

const StreamEntry = ({
  id,
  avatarSrc,
  authorName,
  createdAt,
  body,
  isAuthor,
  pending = false,
  website,
  replyContext,
  onReply,
  actionSlot,
}: {
  id?: string;
  avatarSrc: string;
  authorName: string;
  createdAt: string;
  body: string;
  isAuthor?: boolean;
  pending?: boolean;
  website?: string | null;
  replyContext?: {
    label: string;
    targetId: string;
  };
  onReply?: () => void;
  actionSlot?: ReactNode;
}) => {
  const { t } = useFrontendI18n();

  return (
    <div id={id} className="aerisun-stream-entry">
      <img
        src={avatarSrc}
        alt={authorName}
        className={`${communityAvatarClass} aerisun-comment-avatar h-11 w-11 rounded-full`}
        loading="lazy"
      />
      <div className="min-w-0">
        <div className="aerisun-comment-header">
          <span className="aerisun-comment-author">{authorName}</span>
          {isAuthor ? <StatusPill text={t("waline.list.siteOwner")} tone="author" /> : null}
          {pending ? <StatusPill text={t("waline.list.pending")} tone="pending" /> : null}
          <span className="aerisun-comment-timestamp">{formatTimestamp(createdAt)}</span>
          {website ? (
            <a
              href={website}
              target="_blank"
              rel="noreferrer"
              className="aerisun-comment-website"
            >
              {website.replace(/^https?:\/\//, "")}
            </a>
          ) : null}
          {replyContext ? (
            <button
              type="button"
              onClick={() => scrollToCommentTarget(replyContext.targetId)}
              className="aerisun-comment-context"
              title={replyContext.label}
            >
              <ArrowUpRight className="h-3.5 w-3.5" />
              {replyContext.label}
            </button>
          ) : null}
        </div>
        <div className="mt-3">
          <CommentMarkdownRenderer content={body} className="aerisun-comment-body" />
        </div>
        {onReply || actionSlot ? (
          <div className="aerisun-comment-actions">
            {onReply ? (
              <button type="button" onClick={onReply} className={communityActionClass}>
                <Reply className="h-3.5 w-3.5" />
                {t("waline.list.reply")}
              </button>
            ) : null}
            {actionSlot}
          </div>
        ) : null}
      </div>
    </div>
  );
};

const CommentReplyStream = ({
  item,
  expanded,
  onToggleReplies,
  onReply,
  t,
}: {
  item: CommunityCommentItem;
  expanded: boolean;
  onToggleReplies: (rootId: string) => void;
  onReply: (target: ReplyTarget) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
}) => {
  const replyItems = flattenReplies(item.replies ?? [], item.id, item.author_name);

  return (
    <article className="aerisun-comment-thread" data-comment-id={item.id}>
      <StreamEntry
        id={buildCommentAnchorId(item.id)}
        avatarSrc={item.avatar_url || fallbackAvatar(item.author_name)}
        authorName={item.author_name}
        createdAt={item.created_at}
        body={item.body}
        isAuthor={item.is_author}
        onReply={() => onReply({ id: item.id, name: item.author_name })}
        actionSlot={replyItems.length ? (
          <button
            type="button"
            onClick={() => onToggleReplies(item.id)}
            className={`${communityActionClass} aerisun-comment-thread__reply-toggle`}
            aria-expanded={expanded}
          >
            <ChevronDown className={`h-3.5 w-3.5 transition-transform ${expanded ? "rotate-180" : ""}`} />
            {expanded
              ? t("waline.list.collapseReplies", { count: replyItems.length })
              : t("waline.list.expandReplies", { count: replyItems.length })}
          </button>
        ) : null}
      />

      {replyItems.length ? (
        <>
          {expanded ? (
            <div className="aerisun-comment-thread__replies">
              {replyItems.map((reply) => (
                <div
                  key={reply.id}
                  id={buildCommentAnchorId(reply.id)}
                  className="aerisun-comment-reply"
                  data-depth={Math.min(reply.threadDepth, 4)}
                  data-comment-id={reply.id}
                >
                  <StreamEntry
                    avatarSrc={reply.avatar_url || fallbackAvatar(reply.author_name)}
                    authorName={reply.author_name}
                    createdAt={reply.created_at}
                    body={reply.body}
                    isAuthor={reply.is_author}
                    replyContext={{
                      label: t("waline.form.replyingTo", { name: reply.replyToName }),
                      targetId: reply.replyToId,
                    }}
                    onReply={() => onReply({ id: reply.id, name: reply.author_name })}
                  />
                </div>
              ))}
            </div>
          ) : null}
        </>
      ) : null}
    </article>
  );
};

const StatusStream = ({
  title,
  items,
}: {
  title: string;
  items: ReactNode;
}) => (
  <section className="aerisun-waline-status-panel">
    <div className="aerisun-waline-status-panel__title">
      <Sparkles className="h-4 w-4" />
      {title}
    </div>
    <div className="aerisun-waline-status-panel__list">{items}</div>
  </section>
);

/* ── Main list component ── */

export interface WalineCommentListProps {
  isGuestbook: boolean;

  /* Loading states */
  loadingConfig: boolean;
  loadingEntries: boolean;
  loadingMoreEntries: boolean;
  loadError: string | null;

  /* Data */
  comments: CommunityCommentItem[];
  guestbookEntries: CommunityGuestbookItem[];
  pendingComments: CommunityCommentItem[];
  pendingGuestbookEntries: CommunityGuestbookItem[];
  hasMoreEntries: boolean;

  /* Callbacks */
  onReply: (target: ReplyTarget) => void;
  onLoadMore: () => void;
  onRetry: () => void;

  /* Labels */
  guestbookLoadingLabel: string;
  guestbookRetryLabel: string;
  guestbookEmptyMessage: string;
}

const WalineCommentList = ({
  isGuestbook,
  loadingConfig,
  loadingEntries,
  loadingMoreEntries,
  loadError,
  comments,
  guestbookEntries,
  pendingComments,
  pendingGuestbookEntries,
  hasMoreEntries,
  onReply,
  onLoadMore,
  onRetry,
  guestbookLoadingLabel,
  guestbookRetryLabel,
  guestbookEmptyMessage,
}: WalineCommentListProps) => {
  const { t } = useFrontendI18n();
  const replyRootByCommentId = useMemo(() => buildCommentRootLookup(comments), [comments]);
  const [expandedThreadIds, setExpandedThreadIds] = useState<Set<string>>(() => new Set());

  useEffect(() => {
    setExpandedThreadIds((current) => {
      const next = new Set<string>();
      current.forEach((threadId) => {
        if (replyRootByCommentId.has(threadId)) {
          next.add(threadId);
        }
      });

      if (next.size === current.size) {
        let unchanged = true;
        current.forEach((threadId) => {
          if (!next.has(threadId)) {
            unchanged = false;
          }
        });
        if (unchanged) {
          return current;
        }
      }

      return next;
    });
  }, [replyRootByCommentId]);

  useEffect(() => {
    const handleJumpRequest = (event: Event) => {
      const detail = (event as CustomEvent<{ commentId?: string }>).detail;
      const commentId = detail?.commentId;
      if (!commentId) {
        return;
      }

      const rootId = replyRootByCommentId.get(commentId);
      if (!rootId || rootId === commentId) {
        return;
      }

      setExpandedThreadIds((current) => {
        if (current.has(rootId)) {
          return current;
        }
        const next = new Set(current);
        next.add(rootId);
        return next;
      });
    };

    window.addEventListener(COMMENT_JUMP_REQUEST_EVENT, handleJumpRequest as EventListener);
    return () => {
      window.removeEventListener(COMMENT_JUMP_REQUEST_EVENT, handleJumpRequest as EventListener);
    };
  }, [replyRootByCommentId]);

  const toggleThreadReplies = (rootId: string) => {
    setExpandedThreadIds((current) => {
      const next = new Set(current);
      if (next.has(rootId)) {
        next.delete(rootId);
      } else {
        next.add(rootId);
      }
      return next;
    });
  };

  if (loadingConfig || loadingEntries) {
    return (
      <div className="aerisun-waline-loading">
        <Loader2 className="h-5 w-5 animate-spin" />
        <span>{isGuestbook ? guestbookLoadingLabel : t("waline.list.loadingComments")}</span>
      </div>
    );
  }

  if (loadError) {
    return (
      <div className="aerisun-waline-empty">
        <p>{loadError}</p>
        <button
          type="button"
          onClick={onRetry}
          className="mt-3 inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.7] px-4 py-2 text-sm transition hover:border-[rgb(var(--shiro-accent-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] dark:bg-card/[0.8]"
        >
          <RefreshCw className="h-4 w-4" />
          {isGuestbook ? guestbookRetryLabel : t("waline.list.retryLoad")}
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {isGuestbook ? (
        <>
          {pendingGuestbookEntries.length ? (
            <StatusStream
              title={t("waline.list.pendingReviewNew")}
              items={pendingGuestbookEntries.map((item) => (
                <StreamEntry
                  key={`pending-${item.id}`}
                  avatarSrc={item.avatar_url || fallbackAvatar(item.name)}
                  authorName={item.name}
                  createdAt={item.created_at}
                  body={item.body}
                  isAuthor={item.is_author}
                  pending
                />
              ))}
            />
          ) : null}

          {guestbookEntries.length ? (
            <div className="aerisun-comment-list">
              {guestbookEntries.map((item) => (
                <article key={item.id} className="aerisun-comment-thread">
                  <StreamEntry
                    id={buildCommentAnchorId(item.id)}
                    avatarSrc={item.avatar_url || fallbackAvatar(item.name)}
                    authorName={item.name}
                    createdAt={item.created_at}
                    body={item.body}
                    isAuthor={item.is_author}
                    website={item.website}
                  />
                </article>
              ))}
            </div>
          ) : (
            <div className="aerisun-waline-empty">{guestbookEmptyMessage}</div>
          )}
        </>
      ) : comments.length || pendingComments.length ? (
        <>
          {pendingComments.length ? (
            <StatusStream
              title={t("waline.list.pendingReviewSubmitted")}
              items={pendingComments.map((item) => (
                <StreamEntry
                  key={`pending-${item.id}`}
                  avatarSrc={item.avatar_url || fallbackAvatar(item.author_name)}
                  authorName={item.author_name}
                  createdAt={item.created_at}
                  body={item.body}
                  pending
                />
              ))}
            />
          ) : null}

          {comments.length ? (
            <div className="aerisun-comment-list">
              {comments.map((item) => (
                <CommentReplyStream
                  key={item.id}
                  item={item}
                  expanded={expandedThreadIds.has(item.id)}
                  onToggleReplies={toggleThreadReplies}
                  onReply={onReply}
                  t={t}
                />
              ))}
            </div>
          ) : (
            <div className="aerisun-waline-empty">{t("waline.list.emptyPublic")}</div>
          )}
        </>
      ) : (
        <div className="aerisun-waline-empty">{t("waline.list.emptyAfterReview")}</div>
      )}

      {hasMoreEntries ? (
        <div className="flex justify-center pt-1">
          <button
            type="button"
            onClick={onLoadMore}
            disabled={loadingMoreEntries}
            className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.76] px-4 py-2 text-sm font-medium text-foreground/62 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.84)] disabled:cursor-not-allowed disabled:opacity-60 dark:bg-card/[0.82]"
          >
            {loadingMoreEntries ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {loadingMoreEntries ? t("waline.list.loadingMore") : t("waline.list.showMore")}
          </button>
        </div>
      ) : null}
    </div>
  );
};

export default WalineCommentList;
