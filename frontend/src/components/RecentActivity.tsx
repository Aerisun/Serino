import { useMemo } from "react";
import { Heart, MessageCircle, ArrowUpRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useReadRecentActivityApiV1PublicRecentActivityGet } from "@serino/api-client/public";
import type { RecentActivityItemRead } from "@serino/api-client/models";

interface ActivityItem {
  type: "comment" | "like" | "reply" | "guestbook";
  user: string;
  avatar: string;
  target: string;
  content?: string;
  date: string;
  href?: string;
}

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

const humanizeTarget = (value: string) => {
  if (!value) {
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

const normalizeType = (value: string): ActivityItem["type"] => {
  const raw = value.toLowerCase();
  if (raw.includes("reply")) return "reply";
  if (raw.includes("guest")) return "guestbook";
  if (raw.includes("like") || raw.includes("reaction")) return "like";
  return "comment";
};

const normalizeActivity = (value: RecentActivityItemRead): ActivityItem => ({
  type: normalizeType(value.kind),
  user: value.actor_name ?? "",
  avatar: value.actor_avatar ?? "",
  target: humanizeTarget(value.target_title ?? ""),
  content: value.excerpt ?? undefined,
  date: formatRelativeDate(value.created_at),
  href: value.href ?? undefined,
});

const RecentActivity = () => {
  const navigate = useNavigate();

  const { data: response, isLoading, isError, error, refetch } = useReadRecentActivityApiV1PublicRecentActivityGet({ limit: 8 });
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
  const errorMessage = isError ? (error instanceof Error ? error.message : "最近动态加载失败") : "";

  return (
    <div className="flex h-full flex-col">
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-sm font-body font-medium uppercase tracking-widest text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.74)]">
          最近动态
        </h3>
        <span className="flex items-center gap-1 text-[11px] font-body text-foreground/25">
          <span className="h-1.5 w-1.5 rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.42)]" />
          静态流 <ArrowUpRight className="h-3 w-3" />
        </span>
      </div>

      <div className="scrollbar-hide -mr-1 max-h-[420px] overflow-y-auto pr-1">
        {status === "loading" &&
          Array.from({ length: 7 }, (_, index) => (
            <div key={`activity-skeleton-${index}`}>
              {index > 0 && <div className="border-t border-[rgb(var(--shiro-divider-rgb,202_210_226)/0.28)]" />}
              <div className="flex w-full items-start gap-3 py-3.5 text-left">
                <div className="mt-0.5 h-7 w-7 shrink-0 animate-pulse overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)]" />
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-1.5">
                    <div className="h-3 w-3 shrink-0 rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.08)]" />
                    <div className="h-2.5 w-[58%] rounded-full bg-[rgb(var(--shiro-divider-rgb,202_210_226)/0.2)]" />
                    <div className="ml-auto h-2.5 w-[12%] rounded-full bg-[rgb(var(--shiro-divider-rgb,202_210_226)/0.14)]" />
                  </div>
                  <div className="mt-2.5 h-2.5 w-[72%] rounded-full bg-[rgb(var(--shiro-divider-rgb,202_210_226)/0.12)] pl-[18px]" />
                </div>
              </div>
            </div>
          ))}

        {status === "error" && (
          <div>
            <div className="flex w-full items-start gap-3 py-3.5 text-left">
              <div className="mt-0.5 h-7 w-7 shrink-0 overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)]" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <MessageCircle className="h-3 w-3 shrink-0 text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.28)]" />
                  <span className="text-[11px] font-body text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.5)]">
                    最近动态加载失败
                  </span>
                  <span className="ml-auto shrink-0 text-[10px] font-body text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.2)]">
                    —
                  </span>
                </div>
                <p className="mt-1.5 pl-[18px] text-[11px] font-body leading-relaxed text-foreground/35">
                  {errorMessage}
                </p>
                <button
                  type="button"
                  onClick={() => void refetch()}
                  className="mt-1.5 pl-[18px] text-[10px] font-body text-foreground/25 transition-colors hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.62)]"
                >
                  重试
                </button>
              </div>
            </div>
          </div>
        )}

        {status === "empty" && (
          <div>
            <div className="flex w-full items-start gap-3 py-3.5 text-left">
              <div className="mt-0.5 h-7 w-7 shrink-0 overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)]" />
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-1.5">
                  <MessageCircle className="h-3 w-3 shrink-0 text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.28)]" />
                  <span className="text-[11px] font-body text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.5)]">
                    暂时还没有公开的最近动态
                  </span>
                </div>
              </div>
            </div>
          </div>
        )}

        {status === "ready" &&
          activities.map((item, index) => (
            <div key={`${item.type}-${item.user}-${item.date}-${index}`}>
              {index > 0 && <div className="border-t border-[rgb(var(--shiro-divider-rgb,202_210_226)/0.28)]" />}
              <button
                type="button"
                className={`group flex w-full items-start gap-3 rounded-xl py-3.5 text-left transition-colors ${item.href ? "cursor-pointer hover:bg-[rgb(var(--shiro-panel-rgb,247_248_252)/0.35)]" : ""}`}
                onClick={() => {
                  if (item.href) {
                    navigate(item.href);
                  }
                }}
              >
                <div className="mt-0.5 h-7 w-7 shrink-0 overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)]">
                  {item.avatar ? (
                    <img
                      src={item.avatar}
                      alt={item.user}
                      className="h-full w-full object-cover"
                      loading="lazy"
                    />
                  ) : null}
                </div>

                <div className="min-w-0 flex-1">
                  {item.type === "like" && (
                    <div className="flex items-center gap-1.5">
                      <Heart className="h-3 w-3 shrink-0 text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.28)] transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.6)]" />
                      <span className="text-[11px] font-body text-foreground/35">
                        {item.user ? (
                          <span className="text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.68)] transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.84)]">
                            {item.user}
                          </span>
                        ) : null}
                        {item.user ? " 赞了 " : "赞了 "}
                        {item.target ? (
                          <span className="text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.44)] transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.62)]">
                            {item.target}
                          </span>
                        ) : null}
                      </span>
                      <span className="ml-auto shrink-0 text-[10px] font-body text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.2)]">
                        {item.date}
                      </span>
                    </div>
                  )}

                  {(item.type === "comment" || item.type === "reply" || item.type === "guestbook") && (
                    <div>
                      <div className="flex items-center gap-1.5">
                        <MessageCircle className="h-3 w-3 shrink-0 text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.28)] transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.6)]" />
                        <span className="text-[11px] font-body text-foreground/35">
                          {item.user ? (
                            <span className="text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.68)] transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.84)]">
                              {item.user}
                            </span>
                          ) : null}
                          {item.user ? " " : ""}
                          {item.type === "comment" && <>评论了 </>}
                          {item.type === "reply" && <>回复了 </>}
                          {item.type === "guestbook" && <>留言了 </>}
                          {item.target ? (
                            <span className="text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.44)] transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.62)]">
                              {item.target}
                            </span>
                          ) : null}
                        </span>
                        <span className="ml-auto shrink-0 text-[10px] font-body text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.2)]">
                          {item.date}
                        </span>
                      </div>
                      {item.content ? (
                        <p className="mt-1.5 pl-[18px] text-[11px] font-body leading-relaxed text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.34)] transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.48)]">
                          "{item.content}"
                        </p>
                      ) : null}
                    </div>
                  )}
                </div>
              </button>
            </div>
          ))}
      </div>
    </div>
  );
};

export default RecentActivity;
