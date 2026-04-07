import { useCallback, useMemo } from "react";
import { ArrowUpRight, RefreshCw } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useReadFriendFeedApiV1SiteFriendFeedGet } from "@serino/api-client/site";
import { formatFriendFeedDate } from "@/lib/api/utils";
import type { FriendFeedItemRead } from "@serino/api-client/models";
import { useFrontendI18n } from "@/i18n";
import { usePageConfig } from "@/contexts/runtime-config";
import { useContainedWheelScroll } from "@/hooks/use-contained-wheel-scroll";

interface FriendPost {
  avatar: string;
  blogName: string;
  title: string;
  date: string;
  url?: string;
}

const normalizeFriendPost = (value: FriendFeedItemRead): FriendPost => ({
  avatar: value.avatar?.trim() ?? "",
  blogName: value.blogName,
  title: value.title,
  date: formatFriendFeedDate(value.publishedAt),
  url: value.url,
});

interface FriendCircleProps {
  enabled?: boolean;
}

const FriendCircle = ({ enabled = true }: FriendCircleProps) => {
  const { t } = useFrontendI18n();
  const navigate = useNavigate();
  const { regionRef, scrollViewportRef } =
    useContainedWheelScroll<HTMLDivElement>();
  const setScrollRefs = useCallback(
    (node: HTMLDivElement | null) => {
      regionRef.current = node;
      scrollViewportRef.current = node;
    },
    [regionRef, scrollViewportRef],
  );
  const config =
    (usePageConfig().activity as Record<string, unknown> | undefined) ?? {};
  const title = String(config.friendCircleTitle ?? t("friendCircle.title"));
  const viewAllLabel = String(
    config.friendCircleViewAllLabel ?? t("friendCircle.viewAll"),
  );
  const errorTitle = String(
    config.friendCircleErrorTitle ?? t("friendCircle.errorTitle"),
  );
  const retryLabel = String(config.friendCircleRetryLabel ?? t("common.retry"));
  const emptyMessage = String(
    config.friendCircleEmptyMessage ?? t("friendCircle.emptyMessage"),
  );
  const refreshLabel = t("friendCircle.refresh");

  const {
    data: response,
    isLoading,
    isFetching,
    isError,
    error,
    refetch,
  } = useReadFriendFeedApiV1SiteFriendFeedGet(
    { limit: 12 },
    { query: { enabled } },
  );
  const friendPosts = useMemo(
    () => response?.data?.items?.map(normalizeFriendPost) ?? [],
    [response],
  );
  const status: "loading" | "ready" | "empty" | "error" = isLoading
    ? "loading"
    : isError
      ? "error"
      : friendPosts.length > 0
        ? "ready"
        : "empty";
  const errorMessage = isError
    ? error instanceof Error
      ? error.message
      : errorTitle
    : "";

  return (
    <div className="flex h-full flex-col">
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-sm font-body font-medium uppercase tracking-widest text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.74)]">
          {title}
        </h3>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            aria-label={t("friendCircle.refreshAria")}
            title={t("friendCircle.refreshAria")}
            className="flex items-center gap-1 rounded-full px-2.5 py-1 text-[11px] font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.72)] disabled:opacity-60"
          >
            <RefreshCw
              className={`h-3 w-3 ${isFetching ? "animate-spin" : ""}`}
            />
            {refreshLabel}
          </button>
          <button
            onClick={() => navigate("/friends")}
            className="flex items-center gap-1 text-[11px] font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.72)]"
          >
            {viewAllLabel} <ArrowUpRight className="h-3 w-3" />
          </button>
        </div>
      </div>

      <div
        ref={setScrollRefs}
        className="scrollbar-hide ml-1 mr-4 flex max-h-[24rem] flex-col gap-0.5 overflow-y-auto overscroll-y-auto pr-0.5 [touch-action:pan-y] [-webkit-overflow-scrolling:touch] [will-change:scroll-position] md:-mr-1 md:ml-0 md:max-h-[420px] md:overscroll-contain md:pr-1"
        data-wheel-scroll-region="friend-circle"
        data-wheel-scroll-viewport="friend-circle"
      >
        {status === "loading" &&
          Array.from({ length: 8 }, (_, index) => (
            <div
              key={`friend-skeleton-${index}`}
              className="group flex w-full items-start gap-2.5 rounded-xl px-2 py-3 text-left sm:gap-3 sm:px-2.5"
            >
              <div className="mt-0.5 h-8 w-8 shrink-0 animate-pulse overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)] sm:h-9 sm:w-9" />
              <div className="min-w-0 flex-1">
                <div className="h-3.5 w-[78%] rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)]" />
                <div className="mt-2 flex items-center gap-2">
                  <span className="h-2.5 w-[32%] rounded-full bg-[rgb(var(--shiro-divider-rgb,202_210_226)/0.26)]" />
                  <span className="h-2.5 w-[16%] rounded-full bg-[rgb(var(--shiro-divider-rgb,202_210_226)/0.18)]" />
                </div>
              </div>
            </div>
          ))}

        {status === "error" && (
          <div className="group flex w-full items-start gap-2.5 rounded-xl px-2 py-3 text-left sm:gap-3 sm:px-2.5">
            <div className="mt-0.5 h-8 w-8 shrink-0 overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)] sm:h-9 sm:w-9" />
            <div className="min-w-0 flex-1">
              <p className="overflow-hidden text-[13px] font-body font-medium leading-snug text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.68)] [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2] md:block md:truncate">
                {errorTitle}
              </p>
              <p className="mt-1 text-[10px] font-body text-foreground/20">
                {errorMessage || t("common.retryLater")}
              </p>
              <button
                type="button"
                onClick={() => void refetch()}
                className="mt-1.5 text-[10px] font-body text-foreground/28 transition-colors hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.7)]"
              >
                {retryLabel}
              </button>
            </div>
          </div>
        )}

        {status === "empty" && (
          <div className="group flex w-full items-start gap-2.5 rounded-xl px-2 py-3 text-left sm:gap-3 sm:px-2.5">
            <div className="mt-0.5 h-8 w-8 shrink-0 overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)] sm:h-9 sm:w-9" />
            <div className="min-w-0 flex-1">
              <p className="overflow-hidden text-[13px] font-body font-medium leading-snug text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.58)] [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2] md:block md:truncate">
                {emptyMessage}
              </p>
            </div>
          </div>
        )}

        {status === "ready" &&
          friendPosts.map((post) => (
            <button
              type="button"
              key={`${post.blogName}-${post.title}-${post.date}`}
              className="group flex w-full items-start gap-2.5 rounded-xl px-2 py-2.5 text-left transition-colors hover:bg-[rgb(var(--shiro-panel-rgb,247_248_252)/0.38)] sm:gap-3 sm:px-2.5 sm:py-3"
              onClick={() => {
                if (post.url) {
                  window.open(post.url, "_blank", "noopener,noreferrer");
                }
              }}
            >
              <div className="mt-0.5 h-8 w-8 shrink-0 overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)] sm:h-9 sm:w-9">
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
                <div className="flex items-center gap-2">
                  <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.34)] transition-colors group-hover:bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.86)]" />
                  <p className="overflow-hidden text-[13px] font-body font-medium leading-snug text-foreground/80 transition-colors [display:-webkit-box] [-webkit-box-orient:vertical] [-webkit-line-clamp:2] group-hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.82)] md:block md:truncate">
                    {post.title}
                  </p>
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <span className="truncate text-[10px] font-body text-foreground/30 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.46)]">
                    {post.blogName}
                  </span>
                  {post.date ? (
                    <span className="text-[10px] font-body text-foreground/15 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.28)]">
                      · {post.date}
                    </span>
                  ) : null}
                </div>
              </div>
            </button>
          ))}
      </div>
    </div>
  );
};

export default FriendCircle;
