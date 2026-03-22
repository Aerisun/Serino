import { useEffect, useMemo, useRef, useState } from "react";
import { motion } from "motion/react";
import { ChevronDown, RefreshCw } from "lucide-react";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";
import { formatSiteCount, formatFriendCircleSubtitle } from "@/lib/format";
import type { BaseViewPageConfig } from "@/lib/page-config";
import {
  fetchPublicFriendFeed,
  fetchPublicFriends,
  formatFriendFeedDate,
  type PublicFriend,
  type PublicFriendFeedItem,
} from "@/lib/api";

interface Friend {
  name: string;
  desc: string;
  avatar: string;
  url: string;
}

interface CirclePost {
  avatar: string;
  blogName: string;
  title: string;
  date: string;
  url: string;
}

interface FriendsPageConfig extends BaseViewPageConfig {
  pageSize?: number;
  circleTitle?: string;
  statusLabel?: string;
  loadMoreLabel?: string;
}

const toFriend = (value: PublicFriend): Friend => ({
  name: value.name,
  desc: value.description?.trim() ?? "",
  avatar: value.avatar?.trim() ?? "",
  url: value.url,
});

const toCirclePost = (value: PublicFriendFeedItem): CirclePost => ({
  blogName: value.blogName,
  title: value.title,
  date: formatFriendFeedDate(value.publishedAt),
  url: value.url,
  avatar: value.avatar?.trim() ?? "",
});

const Friends = () => {
  const config = usePageConfig().friends as unknown as FriendsPageConfig;
  const pageSize = Number(config.pageSize ?? 10);
  const [friends, setFriends] = useState<Friend[]>([]);
  const [allCirclePosts, setAllCirclePosts] = useState<CirclePost[]>([]);
  const [visibleCount, setVisibleCount] = useState(pageSize);
  const [loadingMore, setLoadingMore] = useState(false);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const loadMoreTimerRef = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (loadMoreTimerRef.current !== null) {
        window.clearTimeout(loadMoreTimerRef.current);
      }
    };
  }, []);

  useEffect(() => {
    const controller = new AbortController();

    const loadRemoteData = async () => {
      setStatus("loading");
      setErrorMessage("");

      try {
        const [friendsPayload, feedPayload] = await Promise.all([
          fetchPublicFriends(undefined, { signal: controller.signal }),
          fetchPublicFriendFeed(undefined, { signal: controller.signal }),
        ]);

        if (controller.signal.aborted) {
          return;
        }

        const nextFriends = friendsPayload.items.map(toFriend).filter((item) => Boolean(item.name));
        const nextCirclePosts = feedPayload.items
          .map(toCirclePost)
          .filter((item) => Boolean(item.blogName && item.title && item.url));

        setFriends(nextFriends);
        setAllCirclePosts(nextCirclePosts);
        setVisibleCount(pageSize);
        setStatus(nextFriends.length > 0 || nextCirclePosts.length > 0 ? "ready" : "empty");
      } catch (error) {
        if (!controller.signal.aborted) {
          setFriends([]);
          setAllCirclePosts([]);
          setVisibleCount(pageSize);
          setStatus("error");
          setErrorMessage(error instanceof Error ? error.message : "友链页面加载失败");
        }
      }
    };

    void loadRemoteData();

    return () => {
      controller.abort();
    };
  }, [pageSize, reloadKey]);

  useEffect(() => {
    setVisibleCount((current) =>
      Math.min(Math.max(current, pageSize), Math.max(allCirclePosts.length, pageSize)),
    );
  }, [allCirclePosts.length, pageSize]);

  const visiblePosts = useMemo(
    () => allCirclePosts.slice(0, visibleCount),
    [allCirclePosts, visibleCount],
  );
  const hasMore = visibleCount < allCirclePosts.length;

  const loadMore = () => {
    if (loadingMore || !hasMore) {
      return;
    }

    setLoadingMore(true);
    loadMoreTimerRef.current = window.setTimeout(() => {
      setVisibleCount((current) => Math.min(current + pageSize, allCirclePosts.length));
      setLoadingMore(false);
      loadMoreTimerRef.current = null;
    }, 600);
  };

  const friendSkeletonCount = 9;
  const circleSkeletonCount = Math.min(4, Math.max(1, pageSize > 0 ? 3 : 1));

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
      headerAside={
        <span className="text-xs tracking-[0.18em] text-foreground/28">
          {formatSiteCount(friends.length)}
        </span>
      }
    >
      <div className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-3 lg:gap-5">
        {status === "loading" && friends.length === 0
          ? Array.from({ length: friendSkeletonCount }).map((_, index) => (
              <motion.div
                key={`friend-skeleton-${index}`}
                className="group flex flex-col items-center rounded-2xl px-4 py-8 text-center"
                {...staggerItem(index, {
                  baseDelay: config.motion.delay,
                  step: config.motion.stagger,
                  duration: config.motion.duration,
                })}
              >
                <div className="h-16 w-16 animate-pulse rounded-full bg-foreground/[0.04]" />
                <div className="mt-4 h-4 w-20 animate-pulse rounded-full bg-foreground/[0.05]" />
                <div className="mt-2 h-3 w-full max-w-[8rem] animate-pulse rounded-full bg-foreground/[0.035]" />
                <div className="mt-1.5 h-3 w-4/5 animate-pulse rounded-full bg-foreground/[0.035]" />
                <div className="mt-3 h-3 w-14 animate-pulse rounded-full bg-foreground/[0.03]" />
              </motion.div>
            ))
          : friends.length > 0
            ? friends.map((friend, index) => (
                <motion.a
                  key={friend.name}
                  href={friend.url}
                  target="_blank"
                  rel="noreferrer"
                  className="group flex flex-col items-center rounded-2xl px-4 py-8 text-center transition-[background-color,border-color,box-shadow] hover:bg-[rgb(var(--shiro-panel-rgb)/0.2)] hover:shadow-[inset_0_1px_0_rgb(var(--shiro-accent-rgb)/0.05)]"
                  {...staggerItem(index, {
                    baseDelay: config.motion.delay,
                    step: config.motion.stagger,
                    duration: config.motion.duration,
                  })}
                >
                  <div className="h-16 w-16 overflow-hidden rounded-full bg-foreground/[0.04]">
                    {friend.avatar ? (
                      <img
                        src={friend.avatar}
                        alt={friend.name}
                        className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-110"
                        loading="lazy"
                      />
                    ) : null}
                  </div>
                  <p className="mt-4 text-sm font-medium text-foreground/80 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.9)]">
                    {friend.name}
                  </p>
                  {friend.desc ? (
                    <p className="mt-1.5 line-clamp-2 text-xs leading-relaxed text-foreground/30 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.62)]">
                      {friend.desc}
                    </p>
                  ) : null}
                </motion.a>
              ))
            : (
              <div className="col-span-full rounded-2xl border border-foreground/[0.06] bg-foreground/[0.02] px-4 py-8 text-center">
                <p className="text-sm text-foreground/35">
                  {status === "error" ? errorMessage || String(config.emptyMessage ?? "") : String(config.emptyMessage ?? "")}
                </p>
                {status === "error" && (
                  <button
                    type="button"
                    onClick={() => setReloadKey((value) => value + 1)}
                    className="mt-3 rounded-full liquid-glass px-4 py-2 text-xs font-medium text-foreground/70 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.88)]"
                  >
                    {String(config.retryLabel ?? "")}
                  </button>
                )}
              </div>
            )}
      </div>

      <div className="mb-10 mt-16 border-t border-foreground/[0.06]" />

      <motion.div
        initial={{ opacity: 0, y: 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: config.motion.duration + 0.05, delay: 0.2, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="mb-2 flex items-baseline justify-between">
          <h2 className="text-2xl font-heading italic tracking-tight text-foreground transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.92)] sm:text-3xl">
            {String(config.circleTitle ?? "")}
          </h2>
          <div className="flex items-center gap-1.5 text-xs font-body text-foreground/25">
            <RefreshCw className={`h-3 w-3 ${status === "loading" ? "animate-spin" : ""}`} />
            {String(config.statusLabel ?? "")}
          </div>
        </div>
        <p className="mb-8 text-xs font-body text-foreground/20">
          {formatFriendCircleSubtitle(friends.length, allCirclePosts.length)}
        </p>
      </motion.div>

      {status === "loading" && visiblePosts.length === 0 ? (
        <div className="flex flex-col">
          {Array.from({ length: circleSkeletonCount }).map((_, index) => (
            <motion.div
              key={`circle-skeleton-${index}`}
              className="group -mx-3 flex items-start gap-3.5 rounded-lg border-t border-foreground/[0.05] px-3 py-4"
              {...staggerItem(index, {
                baseDelay: 0,
                step: 0.03,
                duration: 0.35,
              })}
            >
              <div className="mt-0.5 h-9 w-9 shrink-0 animate-pulse overflow-hidden rounded-full bg-foreground/[0.06]" />
              <div className="min-w-0 flex-1">
                <div className="h-3.5 w-24 animate-pulse rounded-full bg-foreground/[0.04]" />
                <div className="mt-2 h-4 w-[80%] animate-pulse rounded-full bg-foreground/[0.035]" />
                <div className="mt-1.5 h-4 w-[68%] animate-pulse rounded-full bg-foreground/[0.035]" />
              </div>
              <div className="mt-1 h-3.5 w-12 shrink-0 animate-pulse rounded-full bg-foreground/[0.03]" />
            </motion.div>
          ))}
        </div>
      ) : visiblePosts.length > 0 ? (
        <div className="flex flex-col">
          {visiblePosts.map((post, index) => (
            <motion.a
              key={`${post.blogName}-${post.date}-${index}`}
              href={post.url}
              target="_blank"
              rel="noreferrer"
              className="group -mx-3 flex items-start gap-3.5 rounded-lg border-t border-foreground/[0.05] px-3 py-4 transition-[background-color,border-color] hover:bg-[rgb(var(--shiro-panel-rgb)/0.14)] hover:border-[rgb(var(--shiro-divider-rgb)/0.24)]"
              {...staggerItem(index, {
                baseDelay: 0,
                step: 0.03,
                duration: 0.35,
              })}
            >
              <div className="mt-0.5 h-9 w-9 shrink-0 overflow-hidden rounded-full bg-foreground/[0.06]">
                {post.avatar ? (
                  <img
                    src={post.avatar}
                    alt={post.blogName}
                    className="h-full w-full object-cover"
                    loading="lazy"
                  />
                ) : null}
              </div>

              <div className="min-w-0 flex-1">
                <p className="truncate text-sm font-body text-foreground/25 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.62)]">
                  {post.blogName}
                </p>
                <p className="mt-0.5 line-clamp-2 text-[15px] font-body font-medium leading-snug text-foreground/80 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.9)]">
                  {post.title}
                </p>
              </div>

              <span className="mt-1 shrink-0 text-[11px] font-body tabular-nums text-foreground/20 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb)/0.48)]">
                {post.date ? `📅 ${post.date}` : ""}
              </span>
            </motion.a>
          ))}
        </div>
      ) : (
        <div className="flex flex-col">
          <div className="group -mx-3 flex items-start gap-3.5 rounded-lg border-t border-foreground/[0.05] px-3 py-4">
            <div className="mt-0.5 h-9 w-9 shrink-0 overflow-hidden rounded-full bg-foreground/[0.06]" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm font-body text-foreground/25">
                {status === "error" ? String(config.retryLabel ?? "") : String(config.emptyMessage ?? "")}
              </p>
              <p className="mt-0.5 line-clamp-2 text-[15px] font-body font-medium leading-snug text-foreground/35">
                {status === "error"
                  ? errorMessage || String(config.emptyMessage ?? "")
                  : String(config.emptyMessage ?? "")}
              </p>
            </div>
            {status === "error" ? (
            <button
              type="button"
              onClick={() => setReloadKey((value) => value + 1)}
              className="mt-1 shrink-0 rounded-full liquid-glass px-3 py-1.5 text-[11px] font-medium text-foreground/55 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.88)]"
            >
              {String(config.retryLabel ?? "")}
            </button>
            ) : (
              <span className="mt-1 shrink-0 text-[11px] font-body tabular-nums text-foreground/20">
                --
              </span>
            )}
          </div>
        </div>
      )}

      {hasMore && (
        <div className="mt-8 flex justify-center">
          <button
            type="button"
            onClick={loadMore}
            disabled={loadingMore}
            className="flex items-center gap-2 rounded-full px-6 py-2.5 text-sm font-body text-foreground/50 liquid-glass transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] active:scale-[0.97] disabled:opacity-50"
          >
            {loadingMore ? (
              <>
                <RefreshCw className="h-3.5 w-3.5 animate-spin" />
                {String(config.loadingLabel ?? "")}
              </>
            ) : (
              <>
                <ChevronDown className="h-3.5 w-3.5" />
                {String(config.loadMoreLabel ?? "")}
              </>
            )}
          </button>
        </div>
      )}

      {!hasMore && status === "ready" && (
        <p className="mt-8 text-center text-xs font-body text-foreground/15">
          {friends.length} links with {friends.length} active · {allCirclePosts.length} articles in total
        </p>
      )}
    </PageShell>
  );
};

export default Friends;
