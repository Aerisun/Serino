import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { Eye, MessageCircle, Search } from "lucide-react";
import { useNavigate } from "react-router-dom";
import PageShell from "@/components/PageShell";
import { staggerItem } from "@/config";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";
import { formatPostCount } from "@/lib/format";
import { fetchPublicContentCollection, formatPublishedDate, type PublicContentEntry } from "@/lib/api";

interface Post {
  slug: string;
  title: string;
  excerpt: string;
  date: string;
  category: string;
  tags: string[];
  views: number;
  comments: number;
}

const categoryMap: Record<string, string> = {
  "design-system": "设计",
  frontend: "设计",
  css: "技术",
  performance: "技术",
  react: "技术",
  animation: "技术",
  essay: "随想",
  career: "随想",
};

const getCategory = (entry: PublicContentEntry) =>
  categoryMap[entry.tags[0] ?? ""] ?? entry.tags[0] ?? "内容";

const mapRemotePost = (entry: PublicContentEntry): Post => ({
  slug: entry.slug,
  title: entry.title,
  excerpt: entry.summary ?? entry.body,
  date: entry.relative_date ?? (formatPublishedDate(entry.published_at) || ""),
  category: entry.category || getCategory(entry),
  tags: entry.tags,
  views: entry.view_count ?? 0,
  comments: entry.comment_count ?? 0,
});

const Posts = () => {
  const config = usePageConfig().posts as Record<string, any>;
  const allCategoryLabel = config.categories?.all ?? "全部";
  const [items, setItems] = useState<Post[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);
  const [search, setSearch] = useState("");
  const [activeCategory, setActiveCategory] = useState(allCategoryLabel);
  const navigate = useNavigate();

  useEffect(() => {
    const controller = new AbortController();

    const loadPosts = async () => {
      setStatus("loading");
      setErrorMessage("");

      try {
        const payload = await fetchPublicContentCollection("posts", 20, { signal: controller.signal });
        if (controller.signal.aborted) {
          return;
        }

        const nextItems = payload.items.map(mapRemotePost);
        setItems(nextItems);
        setStatus(nextItems.length > 0 ? "ready" : "empty");
      } catch (error) {
        if (!controller.signal.aborted) {
          setItems([]);
          setStatus("error");
          setErrorMessage(error instanceof Error ? error.message : "文章加载失败");
        }
      }
    };

    void loadPosts();

    return () => {
      controller.abort();
    };
  }, [reloadKey]);

  const allCategories = [
    allCategoryLabel,
    ...Array.from(new Set(items.map((item) => item.category))),
  ];

  const filtered = items.filter((post) => {
    const matchSearch =
      !search ||
      post.title.toLowerCase().includes(search.toLowerCase()) ||
      post.excerpt.toLowerCase().includes(search.toLowerCase());
    const matchCategory = activeCategory === allCategoryLabel || post.category === activeCategory;
    return matchSearch && matchCategory;
  });

  return (
    <PageShell
      eyebrow={config.eyebrow}
      title={config.title}
      description={config.description}
      metaDescription={config.metaDescription}
      width={config.width}
      headerAside={
        <span className="text-xs tracking-[0.18em] text-foreground/28">
          {formatPostCount(items.length)}
        </span>
      }
    >
      <motion.div
        className="mt-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between"
        initial={{ opacity: 0, y: 12 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: config.motion.duration + 0.05, delay: config.motion.delay, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="relative max-w-xs flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-foreground/25" />
          <input
            type="text"
            placeholder={config.searchPlaceholder}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            className="w-full rounded-xl border border-foreground/8 bg-foreground/[0.03] py-2.5 pl-10 pr-4 text-sm text-foreground placeholder:text-foreground/25 outline-none transition-colors focus:border-foreground/15 focus:bg-foreground/[0.05]"
          />
        </div>

        <div className="flex flex-wrap gap-1.5">
          {allCategories.map((cat) => (
            <button
              key={cat}
              type="button"
              onClick={() => setActiveCategory(cat)}
              className={`rounded-lg px-3 py-1.5 text-xs font-medium transition-colors active:scale-[0.97] ${
                activeCategory === cat
                  ? "bg-foreground/10 text-foreground"
                  : "text-foreground/35 hover:text-foreground/55"
              }`}
            >
              {cat}
            </button>
          ))}
        </div>
      </motion.div>

      <div className="mt-8">
        {status === "loading" &&
          Array.from({ length: 5 }, (_, index) => (
            <div
              key={`post-skeleton-${index}`}
              className="border-t border-foreground/6 py-6 first:border-t-0"
            >
              <div className="h-6 w-[55%] rounded-full bg-foreground/[0.045]" />
              <div className="mt-3 h-4 w-[82%] rounded-full bg-foreground/[0.035]" />
              <div className="mt-2 h-4 w-[64%] rounded-full bg-foreground/[0.03]" />
              <div className="mt-4 flex items-center gap-4">
                <div className="h-3 w-12 rounded-full bg-foreground/[0.03]" />
                <div className="h-3 w-14 rounded-full bg-foreground/[0.03]" />
                <div className="ml-auto h-3 w-10 rounded-full bg-foreground/[0.025]" />
                <div className="h-3 w-8 rounded-full bg-foreground/[0.025]" />
              </div>
            </div>
          ))}

        {status === "error" && (
          <div className="border-t border-foreground/6 py-16 text-center">
            <p className="text-sm text-foreground/35">文章加载失败</p>
            <p className="mt-2 text-xs text-foreground/25">{errorMessage}</p>
            <button
              type="button"
              onClick={() => setReloadKey((value) => value + 1)}
              className="mt-4 text-xs text-foreground/30 transition-colors hover:text-foreground/55"
            >
              重试
            </button>
          </div>
        )}

        {(status === "empty" || (status === "ready" && filtered.length === 0)) && (
          <p className="py-16 text-center text-sm text-foreground/25">
            {config.emptyMessage ?? "没有找到匹配的文章"}
          </p>
        )}

        {status === "ready" &&
          filtered.map((post, i) => (
            <motion.article
              key={post.slug}
              className="group cursor-pointer border-t border-foreground/6 py-6 transition-colors first:border-t-0 hover:bg-foreground/[0.02]"
              onClick={() => navigate(`/posts/${post.slug}`)}
              {...staggerItem(i, {
                baseDelay: config.motion.delay + 0.04,
                step: config.motion.stagger,
                duration: config.motion.duration,
              })}
            >
              <h2 className="text-base font-medium leading-snug text-foreground/90 transition-colors group-hover:text-foreground sm:text-lg">
                {post.title}
              </h2>
              <p className="mt-2 line-clamp-1 text-sm leading-relaxed text-foreground/35">
                {post.excerpt}
              </p>
              <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-foreground/25">
                <span>{post.date}</span>
                <span>{post.category}</span>
                {post.tags.map((tag) => (
                  <span key={tag} className="text-foreground/20">
                    /{tag}
                  </span>
                ))}
                <span className="ml-auto flex items-center gap-1">
                  <Eye className="h-3 w-3" />
                  {post.views.toLocaleString()}
                </span>
                <span className="flex items-center gap-1">
                  <MessageCircle className="h-3 w-3" />
                  {post.comments}
                </span>
              </div>
            </motion.article>
          ))}
      </div>
    </PageShell>
  );
};

export default Posts;
