/**
 * Pure display-only utility functions extracted from the old hand-written API modules.
 * These do NOT call any API endpoints.
 */
import { translateFrontendText } from "@/i18n";

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

export const formatRelativeUpdatedAt = (value: number | null | undefined, now = Date.now()) => {
  if (!value) {
    return "--";
  }

  const diffSeconds = Math.max(0, Math.floor((now - value) / 1000));
  if (diffSeconds < 60) {
    return translateFrontendText("api.updatedSeconds", { count: diffSeconds }, `${diffSeconds}s前更新`);
  }

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return translateFrontendText("api.updatedMinutes", { count: diffMinutes }, `${diffMinutes}min前更新`);
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return translateFrontendText("api.updatedHours", { count: diffHours }, `${diffHours}h前更新`);
  }

  const diffDays = Math.floor(diffHours / 24);
  return translateFrontendText("api.updatedDays", { count: diffDays }, `${diffDays}d前更新`);
};
