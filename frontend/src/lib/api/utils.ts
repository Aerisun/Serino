/**
 * Pure display-only utility functions extracted from the old hand-written API modules.
 * These do NOT call any API endpoints.
 */
import { translateFrontendText } from "@/i18n";
import { formatDateInBeijing, getBeijingDateParts } from "@/lib/time";

const MS_PER_DAY = 86_400_000;

export const formatPublishedDate = (value: string | null | undefined) => {
  if (!value) return "";

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  return formatDateInBeijing(parsed, "zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  });
};

const readDisplayString = (value: unknown) =>
  typeof value === "string" ? value.trim() : "";

type TranslateFn = (
  key: string,
  values?: Record<string, string | number>,
  fallback?: string,
) => string;

const relativeFallback = (
  lang: "zh" | "en",
  unit: "minutes" | "hours" | "days",
  count: number,
) => {
  if (lang === "zh") {
    if (unit === "minutes") return `${count} 分钟前`;
    if (unit === "hours") return `${count} 小时前`;
    return `${count} 天前`;
  }
  if (unit === "minutes") return `${count}m ago`;
  if (unit === "hours") return `${count}h ago`;
  return `${count}d ago`;
};

const beijingDateOrdinal = (value: Date | number) => {
  const parts = getBeijingDateParts(value);
  if (!parts) {
    return null;
  }
  return Date.UTC(parts.year, parts.month - 1, parts.day) / MS_PER_DAY;
};

const diffBeijingCalendarDays = (from: Date, to: number) => {
  const fromOrdinal = beijingDateOrdinal(from);
  const toOrdinal = beijingDateOrdinal(to);
  if (fromOrdinal === null || toOrdinal === null) {
    return 0;
  }
  return Math.max(0, Math.floor(toOrdinal - fromOrdinal));
};

export const formatContentRelativeDate = (
  entry: {
    published_at?: unknown;
    created_at?: unknown;
    updated_at?: unknown;
    relative_date?: unknown;
  },
  t: TranslateFn,
  lang: "zh" | "en",
  now = Date.now(),
) => {
  const timestamp =
    readDisplayString(entry.published_at) || readDisplayString(entry.created_at);
  if (!timestamp) {
    return readDisplayString(entry.relative_date);
  }

  const parsed = new Date(timestamp);
  if (Number.isNaN(parsed.getTime())) {
    return readDisplayString(entry.relative_date);
  }

  const calendarDays = diffBeijingCalendarDays(parsed, now);
  if (calendarDays === 1) {
    return t("recentActivity.yesterday");
  }

  if (calendarDays === 2) {
    return t(
      "recentActivity.dayBeforeYesterday",
      undefined,
      lang === "zh" ? "前天" : "2d ago",
    );
  }

  if (calendarDays > 2 && calendarDays < 7) {
    return t(
      "recentActivity.daysAgo",
      { count: calendarDays },
      relativeFallback(lang, "days", calendarDays),
    );
  }

  if (calendarDays >= 7) {
    return formatDateInBeijing(parsed, lang === "zh" ? "zh-CN" : "en-US", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    }).replaceAll("/", "-");
  }

  const diffMs = Math.max(0, now - parsed.getTime());
  if (diffMs < 60_000) {
    return t("recentActivity.justNow");
  }

  const minutes = Math.floor(diffMs / 60_000);
  if (minutes < 60) {
    return t(
      "recentActivity.minutesAgo",
      { count: Math.max(1, minutes) },
      relativeFallback(lang, "minutes", Math.max(1, minutes)),
    );
  }

  const hours = Math.floor(minutes / 60);
  if (hours < 24) {
    return t(
      "recentActivity.hoursAgo",
      { count: Math.max(1, hours) },
      relativeFallback(lang, "hours", Math.max(1, hours)),
    );
  }

  return formatDateInBeijing(parsed, lang === "zh" ? "zh-CN" : "en-US", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).replaceAll("/", "-");
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

  return formatDateInBeijing(parsed, "zh-CN", {
    month: "numeric",
    day: "numeric",
  });
};

export const formatRelativeUpdatedAt = (value: number | null | undefined, now = Date.now()) => {
  if (value === null || value === undefined || !Number.isFinite(value) || value > now) {
    return "";
  }

  const diffMs = now - value;
  const diffSeconds = Math.max(1, Math.floor(diffMs / 1_000));
  if (diffSeconds < 60) {
    return translateFrontendText("api.updatedSeconds", { count: diffSeconds }, `${diffSeconds} 秒`);
  }

  const diffMinutes = Math.floor(diffSeconds / 60);
  if (diffMinutes < 60) {
    return translateFrontendText("api.updatedMinutes", { count: diffMinutes }, `${diffMinutes} 分钟`);
  }

  const diffHours = Math.floor(diffMinutes / 60);
  if (diffHours < 24) {
    return translateFrontendText("api.updatedHours", { count: diffHours }, `${diffHours} 小时`);
  }

  const diffDays = Math.floor(diffMs / MS_PER_DAY);
  if (diffDays === 1) {
    return translateFrontendText("api.updatedYesterday", undefined, "昨天");
  }
  if (diffDays === 2) {
    return translateFrontendText("api.updatedDayBeforeYesterday", undefined, "前天");
  }
  if (diffDays < 90) {
    return translateFrontendText("api.updatedDays", { count: diffDays }, `${diffDays} 天`);
  }
  if (diffDays < 365) {
    const months = Math.max(1, Math.floor(diffDays / 30));
    return translateFrontendText("api.updatedMonths", { count: months }, `${months} 个月`);
  }

  const years = Math.max(1, Math.floor(diffDays / 365));
  return translateFrontendText("api.updatedYears", { count: years }, `${years} 年`);
};
