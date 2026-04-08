import { Suspense, useEffect, useRef, useState } from "react";
import { useParams, useNavigate, useSearchParams } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, FileText, Tag } from "lucide-react";
import ArchiveBadge from "@/components/ArchiveBadge";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";
import BackToTop from "@/components/BackToTop";

import PageMeta from "@/components/PageMeta";
import JsonLd from "@/components/JsonLd";
import PreviewModeBadge from "@/components/PreviewModeBadge";
import LazyOnVisible from "@/components/LazyOnVisible";
import ArticleEnhancements from "@/components/ArticleEnhancements";
import { useFeatureFlags } from "@/contexts/runtime-config";
import { usePageConfig } from "@/contexts/runtime-config";
import { useFrontendI18n, type FrontendLang } from "@/i18n";
import { formatPublishedDate } from "@/lib/api/utils";
import { usePreviewChannel, type ContentPreviewData } from "@/lib/preview";
import { useReadPostApiV1SitePostsSlugGet } from "@serino/api-client/site";
import type { ContentEntryRead } from "@serino/api-client/models";
import type { BaseViewPageConfig } from "@/lib/page-config";
import { lazyWithPreload } from "@/lib/lazy";

const CommentSection = lazyWithPreload(() => import("@/components/CommentSection"));
const ArticleMarkdownRenderer = lazyWithPreload(() => import("@/components/ArticleMarkdownRenderer"));

interface PostData {
  slug: string;
  title: string;
  date: string;
  isArchived: boolean;
  category: string;
  tags: string[];
  likes: number;
  views: number;
  comments: number;
  content: string;
}

interface PostDetailPageConfig extends BaseViewPageConfig {
  categories?: {
    fallback?: string;
  };
  detailBackLabel?: string;
  detailListLabel?: string;
  detailMissingTitle?: string;
  detailMissingDescription?: string;
  detailEndLabel?: string;
}

const estimateWordCount = (value: string, lang: FrontendLang, wordsLabel: string) => {
  const plainText = value
    .replace(/```[\s\S]*?```/g, " ")
    .replace(/`[^`]*`/g, " ")
    .replace(/!\[[^\]]*\]\([^)]*\)/g, " ")
    .replace(/\[([^\]]+)\]\([^)]*\)/g, "$1")
    .replace(/<[^>]+>/g, " ")
    .replace(/[#>*_~-]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

  const cjkCount = (plainText.match(/[\u3400-\u9FFF\uF900-\uFAFF]/g) ?? []).length;
  const latinWordCount = (
    plainText
      .replace(/[\u3400-\u9FFF\uF900-\uFAFF]/g, " ")
      .match(/[A-Za-z0-9]+(?:['’-][A-Za-z0-9]+)*/g) ?? []
  ).length;

  const total = cjkCount + latinWordCount;
  return `${total.toLocaleString(lang === "zh" ? "zh-CN" : "en-US")} ${wordsLabel}`;
};

const buildRemotePost = (
  entry: ContentEntryRead,
  fallbackCategoryLabel: string,
): PostData => ({
  slug: entry.slug,
  title: entry.title,
  date: formatPublishedDate(entry.published_at) || "",
  isArchived: entry.status === "archived",
  category: entry.category || fallbackCategoryLabel,
  tags: entry.tags,
  likes: entry.like_count ?? 0,
  views: entry.view_count ?? 0,
  comments: entry.comment_count ?? 0,
  content: entry.body,
});

const buildPreviewPost = (
  preview: ContentPreviewData,
  fallbackCategoryLabel: string,
  draftLabel: string,
): PostData => ({
  slug: preview.slug || "",
  title: preview.title,
  date: formatPublishedDate(preview.published_at) || draftLabel,
  isArchived: false,
  category: preview.category || fallbackCategoryLabel,
  tags: preview.tags || [],
  likes: 0,
  views: 0,
  comments: 0,
  content: preview.body || "",
});

const useEstimatedWordCount = (
  content: string,
  lang: FrontendLang,
  wordsLabel: string,
) => {
  const [wordCount, setWordCount] = useState("");

  useEffect(() => {
    if (!content) {
      setWordCount("");
      return;
    }

    let cancelled = false;
    const compute = () => {
      if (cancelled) {
        return;
      }
      setWordCount(estimateWordCount(content, lang, wordsLabel));
    };

    if (typeof window === "undefined") {
      compute();
      return;
    }

    if ("requestIdleCallback" in window) {
      const handle = window.requestIdleCallback(compute, { timeout: 240 });
      return () => {
        cancelled = true;
        window.cancelIdleCallback(handle);
      };
    }

    const handle = window.setTimeout(compute, 32);
    return () => {
      cancelled = true;
      window.clearTimeout(handle);
    };
  }, [content, lang, wordsLabel]);

  return wordCount;
};

const PostDetail = () => {
  const { t, lang } = useFrontendI18n();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const featureFlags = useFeatureFlags();
  const pages = usePageConfig();
  const postsConfig = (pages.posts ?? {}) as PostDetailPageConfig;
  const fallbackCategoryLabel = postsConfig.categories?.fallback ?? t("posts.fallbackCategory");
  const detailBackLabel = postsConfig.detailBackLabel ?? t("postDetail.back");
  const detailListLabel = postsConfig.detailListLabel ?? t("postDetail.backToList");
  const detailMissingTitle = postsConfig.detailMissingTitle ?? t("postDetail.missingTitle");
  const detailMissingDescription =
    postsConfig.detailMissingDescription ?? t("postDetail.missingDescription");
  const detailEndLabel = postsConfig.detailEndLabel ?? t("postDetail.endLabel");
  const errorTitle = postsConfig.errorTitle ?? t("posts.errorTitle");
  const retryLabel = postsConfig.retryLabel ?? t("common.retry");
  const articleRef = useRef<HTMLElement>(null);
  const previewStorageKey = searchParams.get("previewStorageKey") || "";

  const slug = id ? decodeURIComponent(id) : "";
  const { data: previewData, isLoading: isPreviewLoading } =
    usePreviewChannel(previewStorageKey);
  const { data: response, isLoading, isError, error, refetch } = useReadPostApiV1SitePostsSlugGet(slug, {
    query: {
      enabled: !!id,
      staleTime: 5 * 60_000,
      gcTime: 20 * 60_000,
    },
  });

  const previewPost =
    previewData?.type === "posts"
      ? buildPreviewPost(previewData, fallbackCategoryLabel, t("common.draft"))
      : null;
  const post =
    previewPost ??
    (response?.data ? buildRemotePost(response.data, fallbackCategoryLabel) : null);
  const is404 = isError && error != null && typeof error === "object" && "response" in error && (error as { response?: { status?: number } }).response?.status === 404;
  const status: "loading" | "ready" | "empty" | "error" = previewPost
    ? "ready"
    : isLoading
      ? "loading"
      : isError
        ? is404 ? "empty" : "error"
        : post ? "ready" : "empty";
  const pageStatus: "loading" | "ready" | "empty" | "error" =
    isPreviewLoading && !previewPost ? "loading" : status;
  const errorMessage = isError
    ? is404
      ? detailMissingDescription
      : error instanceof Error ? error.message : errorTitle
    : !id ? t("postDetail.missingId") : "";
  const showArticleEnhancements = Boolean(post) && featureFlags.toc;
  const wordCount = useEstimatedWordCount(post?.content ?? "", lang, t("common.words"));

  useEffect(() => {
    if (post) {
      void ArticleMarkdownRenderer.preload();
      void CommentSection.preload();
    }
  }, [post]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      <PageMeta
        title={post?.title ?? (status === "error" ? errorTitle : detailMissingTitle)}
        description={post?.content.slice(0, 150) ?? (errorMessage || detailMissingDescription)}
      />
      {post && (
        <JsonLd
          title={post.title}
          description={post.content.slice(0, 200) || ""}
          slug={post.slug}
          type="posts"
          publishedAt={post.date}
          tags={post.tags}
        />
      )}
      <FallingPetals />
      <Navbar />
      {previewPost ? <PreviewModeBadge /> : null}

      <main className="mx-auto max-w-5xl px-6 pt-28 pb-20 lg:px-8">
        <motion.button
          type="button"
          onClick={() => navigate(-1)}
          className="mb-8 flex items-center gap-1.5 text-sm font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] active:scale-95"
          initial={{ opacity: 0, x: -8 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
        >
          <ArrowLeft className="h-4 w-4" />
          {detailBackLabel}
        </motion.button>

        {pageStatus === "loading" ? (
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
                {post.isArchived ? <ArchiveBadge /> : null}
                <span>{post.date}</span>
                <span className="rounded-md border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-[rgb(var(--shiro-panel-rgb)/0.28)] px-2 py-0.5 text-[rgb(var(--shiro-accent-rgb)/0.72)]">
                  {post.category}
                </span>
                <span className="flex items-center gap-1">
                  <FileText className="h-3 w-3" />
                  {wordCount ? (
                    wordCount
                  ) : (
                    <span
                      aria-hidden="true"
                      className="inline-block h-3 w-14 rounded-full bg-foreground/[0.05]"
                    />
                  )}
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
              ref={articleRef}
              className="mt-10"
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1, ease: [0.16, 1, 0.3, 1] }}
            >
              <Suspense
                fallback={
                  <div className="space-y-4">
                    <div className="h-4 w-full rounded-full bg-foreground/[0.035]" />
                    <div className="h-4 w-[92%] rounded-full bg-foreground/[0.03]" />
                    <div className="h-4 w-[78%] rounded-full bg-foreground/[0.03]" />
                  </div>
                }
              >
                <ArticleMarkdownRenderer content={post.content} className="detail-markdown" />
              </Suspense>
            </motion.article>

            {showArticleEnhancements ? (
              <ArticleEnhancements
                containerRef={articleRef}
                content={post.content}
                enableToc={featureFlags.toc}
              />
            ) : null}

            <div className="mt-12 border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] pt-8">
              <p
                className="text-center text-[2.4rem] leading-none text-[rgb(var(--shiro-accent-rgb)/0.78)]"
                style={{
                  fontFamily: "'Pinyon Script', cursive",
                  textShadow: "0 0 14px rgb(var(--shiro-glow-rgb) / 0.24)",
                }}
              >
                {detailEndLabel}
              </p>
            </div>

            <LazyOnVisible
              fallback={
                <div className="mt-12 h-24 rounded-[1.5rem] border border-[rgb(var(--shiro-border-rgb)/0.12)] bg-foreground/[0.02]" />
              }
            >
              <Suspense fallback={null}>
                <CommentSection
                  contentType="posts"
                  contentSlug={post.slug}
                />
              </Suspense>
            </LazyOnVisible>
          </>
        ) : (
          <motion.div
            className="border-t border-[rgb(var(--shiro-divider-rgb)/0.26)] pt-8"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="text-sm font-body text-foreground/40">
              {pageStatus === "error" ? errorTitle : detailMissingTitle}
            </p>
            <p className="mt-2 text-xs font-body text-foreground/25">
              {errorMessage || detailMissingDescription}
            </p>
            <button
              type="button"
              onClick={pageStatus === "error" ? () => refetch() : () => navigate("/posts")}
              className="mt-4 text-xs font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.8)]"
            >
              {pageStatus === "error" ? retryLabel : detailListLabel}
            </button>
          </motion.div>
        )}
      </main>

      <BackToTop />
      <Footer />
    </div>
  );
};

export default PostDetail;
