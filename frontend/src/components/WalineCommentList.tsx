import { Loader2, RefreshCw, Reply, Sparkles } from "lucide-react";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import { useFrontendI18n } from "@/i18n";
import {
  communityActionClass,
  communityAvatarClass,
  communityCardClass,
  fallbackAvatar,
  formatTimestamp,
  StatusPill,
  type CommunityCommentItem,
  type CommunityGuestbookItem,
  type ReplyTarget,
} from "./waline-types";

/* ── Recursive comment thread ── */

const CommentThread = ({
  items,
  onReply,
  depth = 0,
}: {
  items: CommunityCommentItem[];
  onReply: (target: ReplyTarget) => void;
  t: (key: string, vars?: Record<string, string | number>) => string;
  depth?: number;
}) => (
  <div className={depth > 0 ? "mt-4 border-l border-[rgb(var(--shiro-border-rgb)/0.14)] pl-4" : "space-y-4"}>
    {items.map((item) => {
      const avatarSrc = item.avatar_url || fallbackAvatar(item.author_name);
      return (
        <article
          key={item.id}
          className={`${communityCardClass} rounded-[1.4rem] p-4`}
        >
          <div className="flex items-start gap-3">
            <img
              src={avatarSrc}
              alt={item.author_name}
              className={`${communityAvatarClass} h-11 w-11 rounded-2xl`}
              loading="lazy"
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-body text-sm font-semibold text-foreground">{item.author_name}</span>
                {item.is_author ? <StatusPill text={t("waline.list.siteOwner")} tone="author" /> : null}
                <span className="text-xs text-foreground/40">{formatTimestamp(item.created_at)}</span>
              </div>
              <div className="mt-2">
                <MarkdownRenderer content={item.body} className="aerisun-comment-body" />
              </div>
              <div className="mt-3 flex items-center gap-3 text-xs text-foreground/45">
                <button
                  type="button"
                  onClick={() => onReply({ id: item.id, name: item.author_name })}
                  className={communityActionClass}
                >
                  <Reply className="h-3.5 w-3.5" />
                  {t("waline.list.reply")}
                </button>
              </div>
              {item.replies?.length ? (
                <CommentThread items={item.replies} onReply={onReply} t={t} depth={depth + 1} />
              ) : null}
            </div>
          </div>
        </article>
      );
    })}
  </div>
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
    <div className="space-y-4">
      {isGuestbook ? (
        <>
          {/* Pending guestbook entries */}
          {pendingGuestbookEntries.length ? (
            <div className="rounded-[1.5rem] border border-dashed border-amber-500/26 bg-amber-500/8 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-700 dark:text-amber-300">
                <Sparkles className="h-4 w-4" />
                {t("waline.list.pendingReviewNew")}
              </div>
              <div className="space-y-3">
                {pendingGuestbookEntries.map((item) => (
                  <article
                    key={`pending-${item.id}`}
                    className="rounded-[1.2rem] border border-amber-500/18 bg-background/[0.76] p-4 dark:bg-card/[0.84]"
                  >
                    <div className="flex items-start gap-3">
                      <img
                        src={item.avatar_url || fallbackAvatar(item.name)}
                        alt={item.name}
                        className={`${communityAvatarClass} h-11 w-11 rounded-2xl`}
                        loading="lazy"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-foreground">{item.name}</span>
                          <StatusPill text={t("waline.list.pending")} tone="pending" />
                          <span className="text-xs text-foreground/40">{formatTimestamp(item.created_at)}</span>
                        </div>
                        <div className="mt-2">
                          <MarkdownRenderer content={item.body} className="aerisun-comment-body" />
                        </div>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          {/* Approved guestbook entries */}
          {guestbookEntries.length ? (
            guestbookEntries.map((item) => (
              <article
                key={item.id}
                className={`${communityCardClass} rounded-[1.5rem] p-4`}
              >
                <div className="flex items-start gap-3">
                  <img
                    src={item.avatar_url || fallbackAvatar(item.name)}
                    alt={item.name}
                    className={`${communityAvatarClass} h-12 w-12 rounded-2xl`}
                    loading="lazy"
                  />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="font-semibold text-foreground">{item.name}</span>
                      <span className="text-xs text-foreground/40">{formatTimestamp(item.created_at)}</span>
                      {item.website ? (
                        <a
                          href={item.website}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-[rgb(var(--shiro-accent-rgb)/0.78)] underline-offset-4 hover:underline"
                        >
                          {item.website.replace(/^https?:\/\//, "")}
                        </a>
                      ) : null}
                    </div>
                    <div className="mt-2">
                      <MarkdownRenderer content={item.body} className="aerisun-comment-body" />
                    </div>
                  </div>
                </div>
              </article>
            ))
          ) : (
            <div className="aerisun-waline-empty">
              {guestbookEmptyMessage}
            </div>
          )}
        </>
      ) : comments.length || pendingComments.length ? (
        <>
          {/* Pending comments */}
          {pendingComments.length ? (
            <div className="rounded-[1.5rem] border border-dashed border-amber-500/26 bg-amber-500/8 p-4">
              <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-700 dark:text-amber-300">
                <Sparkles className="h-4 w-4" />
                {t("waline.list.pendingReviewSubmitted")}
              </div>
              <div className="space-y-3">
                {pendingComments.map((item) => (
                  <article
                    key={`pending-${item.id}`}
                    className="rounded-[1.2rem] border border-amber-500/18 bg-background/[0.76] p-4 dark:bg-card/[0.84]"
                  >
                    <div className="flex items-start gap-3">
                      <img
                        src={item.avatar_url || fallbackAvatar(item.author_name)}
                        alt={item.author_name}
                        className={`${communityAvatarClass} h-11 w-11 rounded-2xl`}
                        loading="lazy"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-foreground">{item.author_name}</span>
                          <StatusPill text={t("waline.list.pending")} tone="pending" />
                          <span className="text-xs text-foreground/40">{formatTimestamp(item.created_at)}</span>
                        </div>
                        <div className="mt-2">
                          <MarkdownRenderer content={item.body} className="aerisun-comment-body" />
                        </div>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ) : null}

          {/* Approved comments */}
          {comments.length ? (
            <CommentThread items={comments} onReply={onReply} t={t} />
          ) : (
            <div className="aerisun-waline-empty">
              {t("waline.list.emptyPublic")}
            </div>
          )}
        </>
      ) : (
        <div className="aerisun-waline-empty">
          {t("waline.list.emptyAfterReview")}
        </div>
      )}

      {/* Load more */}
      {hasMoreEntries ? (
        <div className="flex justify-center pt-2">
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
