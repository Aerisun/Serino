/**
 * Pure display-only utility functions extracted from the old hand-written API modules.
 * These do NOT call any API endpoints.
 */

export type PublicContentKind = "posts" | "diary" | "thoughts" | "excerpts";

export const publicContentPaths: Record<PublicContentKind, string> = {
  posts: "/api/v1/public/posts",
  diary: "/api/v1/public/diary",
  thoughts: "/api/v1/public/thoughts",
  excerpts: "/api/v1/public/excerpts",
};

export const formatPublishedDate = (value: string | null | undefined) => {
  if (!value) return "";

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(parsed);
};

export const splitContentParagraphs = (value: string) =>
  value
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter(Boolean);

export const formatFriendFeedDate = (value: string | null | undefined) => {
  if (!value) {
    return "";
  }

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    month: "numeric",
    day: "numeric",
  }).format(parsed);
};
