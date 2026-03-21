import { useEffect, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, Clock, Eye, MessageCircle, Tag } from "lucide-react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";
import CommentSection from "@/components/CommentSection";
import PageMeta from "@/components/PageMeta";
import { ApiError, fetchPublicContentEntry, formatPublishedDate, splitContentParagraphs, type PublicContentEntry } from "@/lib/api";

interface PostData {
  slug: string;
  title: string;
  date: string;
  category: string;
  tags: string[];
  likes: number;
  views: number;
  comments: number;
  readTime: string;
  content: string[];
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

const estimateReadTime = (value: string) => `${Math.max(1, Math.ceil(value.length / 180))} 分钟`;

const buildRemotePost = (entry: PublicContentEntry): PostData => ({
  slug: entry.slug,
  title: entry.title,
  date: formatPublishedDate(entry.published_at) || "",
  category: entry.category || categoryMap[entry.tags[0] ?? ""] || entry.tags[0] || "内容",
  tags: entry.tags,
  likes: entry.like_count ?? 0,
  views: entry.view_count ?? 0,
  comments: entry.comment_count ?? 0,
  readTime: entry.read_time ?? estimateReadTime(entry.body),
  content: (() => {
    const paragraphs = splitContentParagraphs(entry.body);
    return paragraphs.length > 0 ? paragraphs : [entry.summary?.trim() || entry.body];
  })(),
});

const PostDetail = () => {
  const { id } = useParams();
  const navigate = useNavigate();
  const [post, setPost] = useState<PostData | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "empty" | "error">("loading");
  const [errorMessage, setErrorMessage] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const controller = new AbortController();

    const loadPost = async () => {
      if (!id) {
        setPost(null);
        setStatus("empty");
        setErrorMessage("缺少文章标识");
        return;
      }

      setStatus("loading");
      setErrorMessage("");

      try {
        const entry = await fetchPublicContentEntry("posts", decodeURIComponent(id), { signal: controller.signal });
        if (controller.signal.aborted) {
          return;
        }

        setPost(buildRemotePost(entry));
        setStatus("ready");
      } catch (error) {
        if (controller.signal.aborted) {
          return;
        }

        setPost(null);
        if (error instanceof ApiError && error.status === 404) {
          setStatus("empty");
          setErrorMessage("文章不存在或已被移除");
        } else {
          setStatus("error");
          setErrorMessage(error instanceof Error ? error.message : "文章加载失败");
        }
      }
    };

    void loadPost();

    return () => {
      controller.abort();
    };
  }, [id, reloadKey]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageMeta
        title={post?.title ?? (status === "error" ? "文章加载失败" : "文章不存在")}
        description={post?.content[0] ?? (errorMessage || "你访问的文章暂时不存在。")}
      />
      <FallingPetals />
      <Navbar />

      <main className="mx-auto max-w-2xl px-6 pt-28 pb-20 lg:px-8">
        <motion.button
          type="button"
          onClick={() => navigate(-1)}
          className="mb-8 flex items-center gap-1.5 text-sm font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] active:scale-95"
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          <ArrowLeft className="h-4 w-4" />
          返回
        </motion.button>

        {status === "loading" ? (
          <>
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="mb-4 flex flex-wrap items-center gap-3 text-xs font-body text-foreground/20">
                <div className="h-3 w-28 rounded-full bg-foreground/[0.04]" />
                <div className="h-5 w-12 rounded-md bg-foreground/[0.04]" />
                <div className="h-3 w-14 rounded-full bg-foreground/[0.04]" />
                <div className="h-3 w-12 rounded-full bg-foreground/[0.04]" />
                <div className="h-3 w-10 rounded-full bg-foreground/[0.04]" />
              </div>
              <div className="h-10 w-[72%] rounded-full bg-foreground/[0.045]" />
              <div className="mt-4 flex flex-wrap gap-2">
                <div className="h-6 w-20 rounded-lg bg-foreground/[0.04]" />
                <div className="h-6 w-24 rounded-lg bg-foreground/[0.04]" />
              </div>
            </motion.div>

            <motion.article
              className="mt-10"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            >
              {Array.from({ length: 5 }, (_, index) => (
                <div key={`post-line-${index}`} className="mb-5">
                  <div className="h-4 w-full rounded-full bg-foreground/[0.035]" />
                  <div className="mt-2 h-4 w-[86%] rounded-full bg-foreground/[0.03]" />
                </div>
              ))}
            </motion.article>
          </>
        ) : post ? (
          <>
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="mb-4 flex flex-wrap items-center gap-3 text-xs font-body text-foreground/25">
                <span>{post.date}</span>
                <span className="rounded-md border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-[rgb(var(--shiro-panel-rgb)/0.28)] px-2 py-0.5 text-[rgb(var(--shiro-accent-rgb)/0.72)]">
                  {post.category}
                </span>
                <span className="flex items-center gap-1">
                  <Clock className="h-3 w-3" />
                  {post.readTime}
                </span>
                <span className="flex items-center gap-1">
                  <Eye className="h-3 w-3" />
                  {post.views.toLocaleString()}
                </span>
                <span className="flex items-center gap-1">
                  <MessageCircle className="h-3 w-3" />
                  {post.comments}
                </span>
              </div>

              <h1 className="text-2xl sm:text-3xl font-heading italic tracking-tight text-foreground leading-tight">
                {post.title}
              </h1>

              <div className="mt-4 flex flex-wrap gap-2">
                {post.tags.map((tag) => (
                  <span
                    key={tag}
                    className="inline-flex items-center gap-1 rounded-lg border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-foreground/5 px-2.5 py-1 text-[11px] font-body text-foreground/30 transition-colors hover:border-[rgb(var(--shiro-accent-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.78)]"
                  >
                    <Tag className="h-3 w-3" />
                    {tag}
                  </span>
                ))}
              </div>
            </motion.div>

            <motion.article
              className="mt-10"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            >
              {post.content.map((block, index) => {
                if (block.startsWith("## ")) {
                  return (
                    <h2
                      key={index}
                      className="mb-4 mt-10 border-l-2 border-[rgb(var(--shiro-accent-rgb)/0.34)] pl-3 text-lg font-heading italic text-foreground/90"
                    >
                      {block.replace("## ", "")}
                    </h2>
                  );
                }

                return (
                  <p
                    key={index}
                    className="mb-5 text-sm font-body leading-[1.85] text-foreground/50 first-letter:text-[rgb(var(--shiro-accent-rgb)/0.78)] first-letter:text-base"
                  >
                    {block}
                  </p>
                );
              })}
            </motion.article>

            <div className="mt-12 border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] pt-8">
              <p className="text-center text-xs font-body text-foreground/20">— 完 —</p>
            </div>

            <CommentSection
              contentType="posts"
              contentSlug={post.slug}
              commentCount={post.comments}
              likeCount={post.likes}
            />
          </>
        ) : (
          <motion.div
            className="border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] pt-8"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="text-sm font-body text-foreground/40">
              {status === "error" ? "文章加载失败" : "文章不存在"}
            </p>
            <p className="mt-2 text-xs font-body text-foreground/25">
              {errorMessage || "你访问的文章暂时不存在。"}
            </p>
            <button
              type="button"
              onClick={status === "error" ? () => setReloadKey((value) => value + 1) : () => navigate("/posts")}
              className="mt-4 text-xs font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.8)]"
            >
              {status === "error" ? "重试" : "返回列表"}
            </button>
          </motion.div>
        )}
      </main>

      <Footer />
    </div>
  );
};

export default PostDetail;
