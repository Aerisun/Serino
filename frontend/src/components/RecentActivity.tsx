import { type ReactNode, useMemo } from "react";
import { BookOpen, FileText, Heart, MessageCircle, PencilLine, Quote } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useReadRecentActivityApiV1SiteRecentActivityGet } from "@serino/api-client/site";
import type { RecentActivityItemRead } from "@serino/api-client/models";
import { usePageConfig } from "@/contexts/runtime-config";
import { useContainedWheelScroll } from "@/hooks/use-contained-wheel-scroll";

type ActivityType =
  | "comment"
  | "like"
  | "reply"
  | "guestbook"
  | "publish_post"
  | "publish_diary"
  | "publish_thought"
  | "publish_excerpt";

interface ActivityItem {
  type: ActivityType;
  user: string;
  target: string;
  detail?: string;
  date: string;
  href?: string;
}

const GUESTBOOK_ROUTE = "/guestbook";

const isPublishType = (value: ActivityType) => value.startsWith("publish_");

const formatRelativeDate = (value: string) => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }

  const diffMs = Date.now() - parsed.getTime();
  if (diffMs < 60_000) {
    return "刚刚";
  }

  const hours = Math.floor(diffMs / 3_600_000);
  if (hours < 24) {
    return `${Math.max(1, hours)} 小时前`;
  }

  const days = Math.floor(hours / 24);
  if (days === 1) {
    return "昨天";
  }

  if (days < 7) {
    return `${days} 天前`;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  })
    .format(parsed)
    .replaceAll("/", "-");
};

const looksMachineLike = (value: string) => {
  const normalized = value.trim();
  if (!normalized) return true;
  if (/[:/@]/.test(normalized)) return true;
  if (/^[a-z0-9_-]{20,}$/i.test(normalized)) return true;
  if (/^(posts|post|diary|thoughts|guestbook|preview|excerpt|resume)\b/i.test(normalized)) return true;
  return false;
};

const normalizeActorName = (value: string) => {
  const normalized = value.trim();
  if (looksMachineLike(normalized)) {
    return "访客";
  }
  return normalized;
};

const humanizeTarget = (value: string) => {
  if (!value) {
    return "";
  }

  if (looksMachineLike(value)) {
    return "";
  }

  if (!/[-_]/.test(value)) {
    return value;
  }

  return value
    .split(/[-_]+/g)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
};

const normalizeType = (value: string): ActivityType => {
  const raw = value.toLowerCase();
  if (raw === "publish_post") return "publish_post";
  if (raw === "publish_diary") return "publish_diary";
  if (raw === "publish_thought") return "publish_thought";
  if (raw === "publish_excerpt") return "publish_excerpt";
  if (raw.includes("reply")) return "reply";
  if (raw.includes("guest")) return "guestbook";
  if (raw.includes("like") || raw.includes("reaction")) return "like";
  return "comment";
};

const normalizeActivity = (value: RecentActivityItemRead): ActivityItem => {
  const type = normalizeType(value.kind);

  return {
    type,
    user: normalizeActorName(value.actor_name ?? ""),
    target: humanizeTarget(value.target_title ?? ""),
    detail: isPublishType(type) ? value.excerpt?.trim() || undefined : undefined,
    date: formatRelativeDate(value.created_at),
    href: value.href ?? (type === "guestbook" ? GUESTBOOK_ROUTE : undefined),
  };
};

const timelineLineClass =
  "bg-[rgb(var(--shiro-divider-rgb,202_210_226)/0.24)] dark:bg-[rgb(var(--shiro-divider-rgb,202_210_226)/0.18)]";
const summaryClass = "text-[12px] leading-6 text-foreground/54 dark:text-foreground/68";
const actorClass = "font-medium text-foreground/76 dark:text-foreground/86";
const targetClass =
  "font-medium text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.68)] dark:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.78)]";
const verbClass = "pl-2 text-foreground/40 dark:text-foreground/52";
const timeClass =
  "shrink-0 pt-0.5 text-[10px] tracking-[0.08em] text-foreground/30 dark:text-foreground/42";
const errorBubbleClass =
  "mt-2 rounded-2xl rounded-tl-md border border-[rgb(var(--shiro-border-rgb,202_210_226)/0.14)] bg-[rgb(var(--shiro-panel-rgb,247_248_252)/0.2)] px-3.5 py-2.5 text-[11px] leading-6 text-foreground/48 dark:bg-[rgb(var(--shiro-panel-rgb,247_248_252)/0.18)] dark:text-foreground/64";
const detailClass =
  "mt-0.5 block overflow-hidden text-ellipsis whitespace-nowrap text-[11px] leading-5 text-foreground/34 dark:text-foreground/46";
const itemClass =
  "group relative flex w-full gap-4 rounded-2xl py-1 text-left transition-colors";

const renderSummary = (item: ActivityItem): ReactNode => {
  const actor = <span className={actorClass}>{item.user || "访客"}</span>;
  const target = item.target ? <span className={targetClass}>{item.target}</span> : null;

  if (item.type === "like") {
    return (
      <>
        {actor}
        {target ? <span className="px-1.5 text-foreground/22 dark:text-foreground/34">·</span> : null}
        {target}
      </>
    );
  }

  if (item.type === "guestbook") {
    return (
      <>
        {actor}
        <span className={verbClass}>留言了</span>
      </>
    );
  }

  if (item.type === "comment" || item.type === "reply") {
    return (
      <>
        {actor}
        {target ? <span className="px-1.5 text-foreground/22 dark:text-foreground/34">·</span> : null}
        {target}
      </>
    );
  }

  if (item.type === "publish_post") {
    return (
      <>
        {actor}
        <span className={verbClass}>发布了文章</span>
        {target ? <span className="pl-2">{target}</span> : null}
      </>
    );
  }

  if (item.type === "publish_diary") {
    return (
      <>
        {actor}
        <span className={verbClass}>发布了日记</span>
        {target ? <span className="pl-2">{target}</span> : null}
      </>
    );
  }

  if (item.type === "publish_thought") {
    return (
      <>
        {actor}
        <span className={verbClass}>发布了一条碎碎念</span>
      </>
    );
  }

  if (item.type === "publish_excerpt") {
    return (
      <>
        {actor}
        <span className={verbClass}>发布了一条文摘</span>
      </>
    );
  }

  return actor;
};

const RecentActivity = () => {
  const navigate = useNavigate();
  const { regionRef, scrollViewportRef } =
    useContainedWheelScroll<HTMLDivElement>();
  const config = (usePageConfig().activity as Record<string, unknown> | undefined) ?? {};
  const title = String(config.recentActivityTitle ?? "最近动态");
  const errorTitle = String(config.recentActivityErrorTitle ?? "最近动态加载失败");
  const retryLabel = String(config.recentActivityRetryLabel ?? "重试");
  const emptyMessage = String(config.recentActivityEmptyMessage ?? "暂时还没有公开的最近动态");

  const { data: response, isLoading, isError, error, refetch } =
    useReadRecentActivityApiV1SiteRecentActivityGet({ limit: 8 });
  const activities = useMemo(
    () => response?.data?.items?.map(normalizeActivity) ?? [],
    [response],
  );
  const status: "loading" | "ready" | "empty" | "error" = isLoading
    ? "loading"
    : isError
      ? "error"
      : activities.length > 0
        ? "ready"
        : "empty";
  const errorMessage = isError ? (error instanceof Error ? error.message : errorTitle) : "";

  return (
    <div
      ref={regionRef}
      className="flex h-full flex-col"
      data-wheel-scroll-region="recent-activity"
    >
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-sm font-body font-medium uppercase tracking-widest text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.74)]">
          {title}
        </h3>
      </div>

      <div
        ref={scrollViewportRef}
        className="scrollbar-hide relative -mr-1 max-h-[420px] overflow-y-auto overscroll-contain pr-1"
        data-wheel-scroll-viewport="recent-activity"
      >
        {status === "loading" ? (
          <div className="relative">
            <div className={`absolute bottom-4 left-4 top-4 w-px ${timelineLineClass}`} />
            {Array.from({ length: 6 }, (_, index) => (
              <div key={`activity-skeleton-${index}`} className="relative flex gap-4 pb-5 last:pb-0">
                <div className="relative z-10 mt-1 h-8 w-8 shrink-0 animate-pulse rounded-full border border-[rgb(var(--shiro-border-rgb,202_210_226)/0.18)] bg-background/90" />
                <div className="min-w-0 flex-1 pt-0.5">
                  <div className="flex items-start justify-between gap-3">
                    <div className="h-3 w-[62%] animate-pulse rounded-full bg-[rgb(var(--shiro-divider-rgb,202_210_226)/0.18)]" />
                    <div className="h-2.5 w-12 shrink-0 animate-pulse rounded-full bg-[rgb(var(--shiro-divider-rgb,202_210_226)/0.12)]" />
                  </div>
                  <div className="mt-2 h-2.5 w-[52%] animate-pulse rounded-full bg-[rgb(var(--shiro-divider-rgb,202_210_226)/0.12)]" />
                </div>
              </div>
            ))}
          </div>
        ) : null}

        {status === "error" ? (
          <div className="relative flex gap-4">
            <div className="relative z-10 mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb,202_210_226)/0.18)] bg-background/90 text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.6)]">
              <MessageCircle className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0 flex-1 pt-0.5">
              <div className="flex items-start justify-between gap-3">
                <p className={summaryClass}>{errorTitle}</p>
                <span className={timeClass}>--</span>
              </div>
              <p className={`${errorBubbleClass} max-w-full`}>{errorMessage}</p>
              <button
                type="button"
                onClick={() => void refetch()}
                className="mt-2 text-[11px] font-body text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.68)] transition-colors hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.84)]"
              >
                {retryLabel}
              </button>
            </div>
          </div>
        ) : null}

        {status === "empty" ? (
          <div className="relative flex gap-4">
            <div className="relative z-10 mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb,202_210_226)/0.18)] bg-background/90 text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.6)]">
              <MessageCircle className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0 flex-1 pt-0.5">
              <p className={summaryClass}>{emptyMessage}</p>
            </div>
          </div>
        ) : null}

        {status === "ready" ? (
          <div className="relative">
            <div className={`absolute bottom-4 left-4 top-4 w-px ${timelineLineClass}`} />
            {activities.map((item, index) => {
              const Icon =
                item.type === "like"
                  ? Heart
                  : item.type === "publish_post"
                    ? FileText
                    : item.type === "publish_diary"
                      ? BookOpen
                      : item.type === "publish_thought"
                        ? PencilLine
                        : item.type === "publish_excerpt"
                          ? Quote
                          : MessageCircle;
              const iconClass =
                item.type === "like"
                  ? "text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.76)]"
                  : isPublishType(item.type)
                    ? "text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.72)]"
                    : "text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.64)]";

              const content = (
                <div className={`${itemClass} ${item.href ? "cursor-pointer hover:bg-[rgb(var(--shiro-panel-rgb,247_248_252)/0.18)]" : ""}`}>
                  <div className="relative z-10 mt-1 flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb,202_210_226)/0.18)] bg-background/90 shadow-[0_8px_20px_rgb(15_23_42/0.04)]">
                    <Icon className={`h-3.5 w-3.5 ${iconClass}`} />
                  </div>

                  <div className="min-w-0 flex-1 pt-0.5">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className={`${summaryClass} min-w-0 truncate`}>
                          {renderSummary(item)}
                        </p>
                        {item.detail ? (
                          <span className={detailClass}>{item.detail}</span>
                        ) : null}
                      </div>
                      <span className={timeClass}>{item.date}</span>
                    </div>
                  </div>
                </div>
              );

              return item.href ? (
                <button
                  key={`${item.type}-${item.user}-${item.date}-${index}`}
                  type="button"
                  className="block w-full pb-5 last:pb-0"
                  onClick={() => navigate(item.href!)}
                >
                  {content}
                </button>
              ) : (
                <div
                  key={`${item.type}-${item.user}-${item.date}-${index}`}
                  className="pb-5 last:pb-0"
                >
                  {content}
                </div>
              );
            })}
          </div>
        ) : null}
      </div>
    </div>
  );
};

export default RecentActivity;
