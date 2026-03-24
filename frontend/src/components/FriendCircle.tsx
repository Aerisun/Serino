import { useEffect, useState } from "react";
import { ArrowUpRight } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { readFriendFeedApiV1PublicFriendFeedGet } from "@/lib/api/generated/public/public";
import { formatFriendFeedDate } from "@/lib/api/utils";
import type { FriendFeedItemRead } from "@/lib/api/generated/model";

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

const FriendCircle = () => {
  const navigate = useNavigate();
  const [friendPosts, setFriendPosts] = useState<FriendPost[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    const loadFriendFeed = async () => {
      setStatus("loading");
      setErrorMessage("");

      try {
        const response = await readFriendFeedApiV1PublicFriendFeedGet({ limit: 12 }, { signal: controller.signal });
        if (controller.signal.aborted) {
          return;
        }

        const nextPosts = response.data.items.map(normalizeFriendPost);
        setFriendPosts(nextPosts);
        setStatus(nextPosts.length > 0 ? "ready" : "empty");
      } catch (error) {
        if (!controller.signal.aborted) {
          setFriendPosts([]);
          setStatus("error");
          setErrorMessage(error instanceof Error ? error.message : "友邻动态加载失败");
        }
      }
    };

    void loadFriendFeed();

    return () => {
      controller.abort();
    };
  }, [reloadKey]);

  return (
    <div className="flex h-full flex-col">
      <div className="mb-5 flex items-baseline justify-between">
        <h3 className="text-sm font-body font-medium uppercase tracking-widest text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.74)]">
          朋友圈
        </h3>
        <button
          onClick={() => navigate("/friends")}
          className="flex items-center gap-1 text-[11px] font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.72)]"
        >
          查看全部 <ArrowUpRight className="h-3 w-3" />
        </button>
      </div>

      <div className="scrollbar-hide -mr-1 flex max-h-[420px] flex-col gap-0.5 overflow-y-auto pr-1">
        {status === "loading" &&
          Array.from({ length: 8 }, (_, index) => (
            <div
              key={`friend-skeleton-${index}`}
              className="group flex w-full items-start gap-3 rounded-xl px-2.5 py-3 text-left"
            >
              <div className="mt-0.5 h-9 w-9 shrink-0 animate-pulse overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)]" />
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
          <div className="group flex w-full items-start gap-3 rounded-xl px-2.5 py-3 text-left">
            <div className="mt-0.5 h-9 w-9 shrink-0 overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)]" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-body font-medium leading-snug text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.68)]">
                友邻动态加载失败
              </p>
              <p className="mt-1 text-[10px] font-body text-foreground/20">
                {errorMessage || "请稍后重试"}
              </p>
              <button
                type="button"
                onClick={() => setReloadKey((value) => value + 1)}
                className="mt-1.5 text-[10px] font-body text-foreground/28 transition-colors hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.7)]"
              >
                重试
              </button>
            </div>
          </div>
        )}

        {status === "empty" && (
          <div className="group flex w-full items-start gap-3 rounded-xl px-2.5 py-3 text-left">
            <div className="mt-0.5 h-9 w-9 shrink-0 overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)]" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-[13px] font-body font-medium leading-snug text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.58)]">
                还没有公开的友邻动态
              </p>
            </div>
          </div>
        )}

        {status === "ready" &&
          friendPosts.map((post) => (
            <button
              type="button"
              key={`${post.blogName}-${post.title}-${post.date}`}
              className="group flex w-full items-start gap-3 rounded-xl px-2.5 py-3 text-left transition-colors hover:bg-[rgb(var(--shiro-panel-rgb,247_248_252)/0.38)]"
              onClick={() => {
                if (post.url) {
                  window.open(post.url, "_blank", "noopener,noreferrer");
                }
              }}
            >
              <div className="mt-0.5 h-9 w-9 shrink-0 overflow-hidden rounded-full bg-[rgb(var(--shiro-accent-rgb,60_100_200)/0.06)]">
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
                  <p className="truncate text-[13px] font-body font-medium leading-snug text-foreground/80 transition-colors group-hover:text-[rgb(var(--shiro-accent-rgb,60_100_200)/0.82)]">
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
