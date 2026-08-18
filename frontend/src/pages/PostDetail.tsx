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
import { ImageLoadQueueProvider } from "@/components/QueuedAttachmentImage";
import {
  getDiaryAccessErrorStatus,
  useDiaryAccessPrompt,
} from "@/components/DiaryAccessPrompt";
import { useFeatureFlags } from "@/contexts/runtime-config";
import { usePageConfig } from "@/contexts/runtime-config";
import { useFrontendI18n, type FrontendLang } from "@/i18n";
import { formatPublishedDate, formatRelativeUpdatedAt } from "@/lib/api/utils";
import { usePreviewChannel, type ContentPreviewData } from "@/lib/preview";
import {
  useReadNoteApiV1SiteNotesSlugGet,
  useReadPostApiV1SitePostsSlugGet,
} from "@serino/api-client/site";
import type { ContentEntryRead } from "@serino/api-client/models";
import type { BaseViewPageConfig } from "@/lib/page-config";
import { lazyWithPreload } from "@/lib/lazy";
import { buildContentSearchDescription } from "@/lib/article-structured-data";

const CommentSection = lazyWithPreload(() => import("@/components/CommentSection"));
const ArticleMarkdownRenderer = lazyWithPreload(() => import("@/components/ArticleMarkdownRenderer"));

interface PostData {
  slug: string;
  title: string;
  date: string;
  publishedAt?: string;
  modifiedAt?: string;
  updatedAt: number | null;
  isArchived: boolean;
  requiresApproval: boolean;
  summary: string;
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

const parseUpdateTimestamp = (value: unknown) => {
  if (typeof value !== "string") {
    return null;
  }

  const timestamp = Date.parse(value);
  return Number.isFinite(timestamp) ? timestamp : null;
};

const normalizeContentTags = (value: unknown): string[] => {
  const rawTags = Array.isArray(value) ? value : [value];

  return rawTags.flatMap((tag) =>
    typeof tag === "string"
      ? tag.split(/[,，]/).map((item) => item.trim()).filter(Boolean)
      : [],
  );
};

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
  publishedAt: entry.published_at ?? undefined,
  modifiedAt: entry.updated_at ?? undefined,
  updatedAt: parseUpdateTimestamp(entry.updated_at),
  isArchived: entry.visibility === "private",
  requiresApproval: entry.requires_approval === true,
  summary: typeof entry.summary === "string" ? entry.summary : "",
  category: entry.category || fallbackCategoryLabel,
  tags: normalizeContentTags(entry.tags),
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
  publishedAt: preview.published_at ?? undefined,
  modifiedAt: preview.updated_at ?? undefined,
  updatedAt: parseUpdateTimestamp(preview.updated_at),
  isArchived: false,
  requiresApproval: false,
  summary: preview.summary || "",
  category: preview.category || fallbackCategoryLabel,
  tags: normalizeContentTags(preview.tags),
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

const PostDetail = ({ kind = "manuscript" }: { kind?: "manuscript" | "note" }) => {
  const { t, lang } = useFrontendI18n();
  const { id } = useParams();
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const featureFlags = useFeatureFlags();
  const pages = usePageConfig();
  const contentType = kind === "note" ? "notes" : "posts";
  const routePrefix = `/${contentType}`;
  const postsConfig = (pages[contentType] ?? {}) as PostDetailPageConfig;
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
  const postApprovalEnabled = featureFlags.post_access_approval_enabled !== false;

  const slug = id ? decodeURIComponent(id) : "";
  const { promptNode, openLoginDialog, openRequestDialog } = useDiaryAccessPrompt({
    postApprovalEnabled,
    postSlug: slug,
  });
  const { data: previewData, isLoading: isPreviewLoading } =
    usePreviewChannel(previewStorageKey);
  const queryOptions = {
    query: {
      staleTime: 60_000,
      gcTime: 20 * 60_000,
      retry: (failureCount, requestError) => {
        const statusCode = getDiaryAccessErrorStatus(requestError);
        if (statusCode === 401 || statusCode === 403 || statusCode === 404) {
          return false;
        }
        return failureCount < 2;
      },
    },
  };
  const manuscriptQuery = useReadPostApiV1SitePostsSlugGet(slug, {
    ...queryOptions,
    query: { ...queryOptions.query, enabled: !!id && kind === "manuscript" },
  });
  const noteQuery = useReadNoteApiV1SiteNotesSlugGet(slug, {
    ...queryOptions,
    query: { ...queryOptions.query, enabled: !!id && kind === "note" },
  });
  const { data: response, isLoading, isError, error, refetch } =
    kind === "note" ? noteQuery : manuscriptQuery;

  const previewPost =
    previewData?.type === "posts"
      ? buildPreviewPost(previewData, fallbackCategoryLabel, t("common.draft"))
      : null;
  const post =
    previewPost ??
    (response?.data ? buildRemotePost(response.data, fallbackCategoryLabel) : null);
  const is404 = isError && error != null && typeof error === "object" && "response" in error && (error as { response?: { status?: number } }).response?.status === 404;
  const accessErrorStatus = getDiaryAccessErrorStatus(error);
  const accessBlocked = isError && (accessErrorStatus === 401 || accessErrorStatus === 403);
  const status: "loading" | "ready" | "empty" | "error" | "blocked" = previewPost
    ? "ready"
    : isLoading
      ? "loading"
      : accessBlocked
        ? "blocked"
      : isError
        ? is404 ? "empty" : "error"
        : post ? "ready" : "empty";
  const pageStatus: "loading" | "ready" | "empty" | "error" | "blocked" =
    isPreviewLoading && !previewPost ? "loading" : status;
  const errorMessage = isError
    ? accessBlocked
      ? t("postAccess.privateDescription")
      : is404
        ? detailMissingDescription
        : error instanceof Error ? error.message : errorTitle
    : !id ? t("postDetail.missingId") : "";
  const showArticleEnhancements = Boolean(post) && featureFlags.toc;
  const postDescription = post
    ? buildContentSearchDescription({ summary: post.summary, body: post.content })
    : pageStatus === "blocked"
      ? t("postAccess.privateDescription")
      : errorMessage || detailMissingDescription;
  const shouldNoIndex =
    pageStatus !== "ready" ||
    Boolean(previewPost) ||
    Boolean(post?.isArchived) ||
    Boolean(postApprovalEnabled && post?.requiresApproval);
  const wordCount = useEstimatedWordCount(post?.content ?? "", lang, t("common.words"));
  const updatedRelativeLabel = post?.updatedAt != null
    ? formatRelativeUpdatedAt(post.updatedAt)
    : "";
  const updatedRelativeSuffix =
    updatedRelativeLabel === "昨天" || updatedRelativeLabel === "前天" ? "" : "前";

  useEffect(() => {
    if (post) {
      void ArticleMarkdownRenderer.preload();
      void CommentSection.preload();
    }
  }, [post]);

  return (
    <div className="min-h-screen bg-background text-foreground">
      {promptNode}
      <PageMeta
        title={post?.title ?? (status === "error" ? errorTitle : detailMissingTitle)}
        description={postDescription}
        type="article"
        noIndex={shouldNoIndex}
      />
      {post && !shouldNoIndex && (
        <JsonLd
          title={post.title}
          description={postDescription}
          slug={post.slug}
          type={contentType}
          publishedAt={post.publishedAt}
          modifiedAt={post.modifiedAt}
          tags={post.tags}
        />
      )}
      <FallingPetals />
      <Navbar />
      {previewPost ? <PreviewModeBadge /> : null}

      <main className="mx-auto max-w-5xl px-6 pt-[5.5rem] pb-20 sm:pt-28 lg:px-8">
        <ImageLoadQueueProvider>
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
        ) : pageStatus === "blocked" ? (
          <motion.div
            className="liquid-glass mx-auto max-w-xl rounded-[2rem] border border-sky-400/28 px-6 py-8 text-center shadow-[0_18px_60px_rgba(14,165,233,0.14)] backdrop-blur-xl"
            initial={{ opacity: 0, y: 12 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4, ease: [0.16, 1, 0.3, 1] }}
          >
            <p className="text-base font-heading text-foreground/78">
              {accessErrorStatus === 401
                ? t("postAccess.loginTitle")
                : t("postAccess.privateTitle")}
            </p>
            {accessErrorStatus !== 401 ? (
              <p className="mt-3 text-sm font-body leading-7 text-foreground/48">
                {t("postAccess.privateDescription")}
              </p>
            ) : null}
            <div className="mt-6 flex items-center justify-center">
              <button
                type="button"
                onClick={accessErrorStatus === 401 ? openLoginDialog : openRequestDialog}
                className="inline-flex items-center justify-center rounded-full border border-sky-400/36 bg-sky-500/14 px-5 py-2 text-sm font-semibold text-sky-700 shadow-[0_10px_28px_rgba(14,165,233,0.14)] transition hover:border-sky-400/58 hover:bg-sky-500/22 dark:text-sky-100"
              >
                {accessErrorStatus === 401 ? t("navbar.login") : t("postAccess.apply")}
              </button>
            </div>
          </motion.div>
        ) : post ? (
          <>
            <motion.div
              initial={{ opacity: 0, y: 16 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
            >
              <div className="mb-4 flex flex-wrap items-center gap-3 text-xs font-body text-foreground/25">
                {post.isArchived ? <ArchiveBadge /> : null}
                <span className="inline-flex items-baseline gap-1 mr-4">
                  <span>{post.date}</span>
                  {updatedRelativeLabel ? (
                    <span className="post-updated-at">
                          {" ("}最后更新于 <span className="post-updated-at-value">{updatedRelativeLabel}</span>{updatedRelativeSuffix ? ` ${updatedRelativeSuffix}` : ""})
                    </span>
                  ) : null}
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

              <h1 className="text-3xl sm:text-4xl font-heading font-bold not-italic tracking-normal text-foreground leading-[1.08]">
                {post.title}
              </h1>

                  <div className="mt-4 flex flex-wrap gap-2">
                    <span className="inline-flex items-center rounded-lg border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-[rgb(var(--shiro-panel-rgb)/0.28)] px-2.5 py-1 text-[11px] font-body text-[rgb(var(--shiro-accent-rgb)/0.72)]">
                      {post.category}
                    </span>
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
                <ArticleMarkdownRenderer
                  content={post.content}
                  className="content-detail-markdown detail-markdown post-detail-markdown"
                />
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
                  contentType={contentType}
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
              onClick={pageStatus === "error" ? () => refetch() : () => navigate(routePrefix)}
              className="mt-4 text-xs font-body text-foreground/30 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.8)]"
            >
              {pageStatus === "error" ? retryLabel : detailListLabel}
            </button>
          </motion.div>
        )}
        </ImageLoadQueueProvider>
      </main>

      <BackToTop />
      <Footer />
    </div>
  );
};

export default PostDetail;
