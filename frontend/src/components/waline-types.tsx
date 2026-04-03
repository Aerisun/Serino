import type { AvatarPreset, CommunityConfig } from "@/lib/community-config";
import { getFrontendLang, translateFrontendText } from "@/i18n";

/* ── Domain types ── */

export interface CommunityCommentItem {
  id: string;
  parent_id?: string | null;
  author_name: string;
  body: string;
  status: string;
  created_at: string;
  avatar?: string | null;
  avatar_url?: string | null;
  like_count?: number;
  liked?: boolean;
  is_author?: boolean;
  replies: CommunityCommentItem[];
}

export interface CommunityGuestbookItem {
  id: string;
  name: string;
  website?: string | null;
  body: string;
  status: string;
  created_at: string;
  avatar?: string | null;
  avatar_url?: string | null;
}

export interface DraftState {
  name: string;
  email: string;
  website: string;
  body: string;
  avatarKey: string;
}

export type EditorMode = "write" | "preview";

export interface ReplyTarget {
  id: string;
  name: string;
}

export interface EmojiChoice {
  emoji: string;
  label: string;
  keywords: string[];
}

export interface EmojiGroup {
  title: string;
  titleKey?: string;
  items: EmojiChoice[];
}

/* ── Constants ── */

export const PROFILE_STORAGE_PREFIX = "aerisun:comment-profile:";

export const EMOJI_GROUPS: EmojiGroup[] = [
  {
    title: "\u65E5\u5E38",
    titleKey: "waline.emoji.groupDaily",
    items: [
      { emoji: "\uD83D\uDE42", label: "\u5FAE\u7B11", keywords: ["\u5FAE\u7B11", "\u7B11", "\u5F00\u5FC3", "smile"] },
      { emoji: "\uD83D\uDE0A", label: "\u5F00\u5FC3", keywords: ["\u5F00\u5FC3", "\u5FEB\u4E50", "\u9AD8\u5174"] },
      { emoji: "\uD83D\uDE09", label: "\u7728\u773C", keywords: ["\u7728\u773C", "\u4FCA\u76AE", "wink"] },
      { emoji: "\uD83E\uDD79", label: "\u611F\u52A8", keywords: ["\u611F\u52A8", "\u60F3\u54ED", "touching"] },
      { emoji: "\uD83D\uDE0C", label: "\u653E\u677E", keywords: ["\u653E\u677E", "\u5B89\u5FC3", "calm"] },
      { emoji: "\uD83E\uDD0D", label: "\u767D\u5FC3", keywords: ["\u767D\u5FC3", "\u7231\u5FC3", "love"] },
      { emoji: "\u2728", label: "\u95EA\u5149", keywords: ["\u95EA\u5149", "\u9B54\u6CD5", "sparkle"] },
      { emoji: "\uD83C\uDF37", label: "\u82B1\u6735", keywords: ["\u82B1", "\u6625\u5929", "flower"] },
    ],
  },
  {
    title: "\u4E92\u52A8",
    titleKey: "waline.emoji.groupInteraction",
    items: [
      { emoji: "\uD83D\uDE04", label: "\u5927\u7B11", keywords: ["\u5927\u7B11", "\u54C8\u54C8", "laugh"] },
      { emoji: "\uD83D\uDE02", label: "\u7B11\u54ED", keywords: ["\u7B11\u54ED", "\u7206\u7B11", "lol"] },
      { emoji: "\uD83E\uDD73", label: "\u5E86\u795D", keywords: ["\u5E86\u795D", "\u6D3E\u5BF9", "party"] },
      { emoji: "\uD83E\uDD1D", label: "\u63E1\u624B", keywords: ["\u63E1\u624B", "\u5408\u4F5C", "\u5408\u4F5C\u6109\u5FEB"] },
      { emoji: "\uD83D\uDE4C", label: "\u4E3E\u624B", keywords: ["\u4E3E\u624B", "\u6B22\u547C", "cheer"] },
      { emoji: "\uD83D\uDC4F", label: "\u9F13\u638C", keywords: ["\u9F13\u638C", "\u8D5E", "applause"] },
      { emoji: "\uD83D\uDD25", label: "\u706B\u70ED", keywords: ["\u706B\u70ED", "\u5F88\u68D2", "hot"] },
      { emoji: "\uD83D\uDCA1", label: "\u7075\u611F", keywords: ["\u7075\u611F", "\u70B9\u5B50", "idea"] },
    ],
  },
  {
    title: "\u6C1B\u56F4",
    titleKey: "waline.emoji.groupAtmosphere",
    items: [
      { emoji: "\uD83E\uDEF6", label: "\u6BD4\u5FC3", keywords: ["\u6BD4\u5FC3", "\u559C\u6B22", "heart"] },
      { emoji: "\uD83D\uDCAD", label: "\u601D\u8003", keywords: ["\u601D\u8003", "\u60F3\u6CD5", "idea"] },
      { emoji: "\uD83C\uDF19", label: "\u6708\u4EAE", keywords: ["\u6708\u4EAE", "\u591C\u665A", "moon"] },
      { emoji: "\u2615", label: "\u5496\u5561", keywords: ["\u5496\u5561", "\u4F11\u606F", "coffee"] },
      { emoji: "\uD83C\uDF75", label: "\u8336", keywords: ["\u8336", "\u653E\u677E", "tea"] },
      { emoji: "\uD83C\uDFA7", label: "\u97F3\u4E50", keywords: ["\u97F3\u4E50", "\u8033\u673A", "music"] },
      { emoji: "\uD83D\uDDBC\uFE0F", label: "\u753B\u6846", keywords: ["\u56FE\u7247", "\u753B\u6846", "art"] },
      { emoji: "\uD83D\uDCDD", label: "\u8BB0\u5F55", keywords: ["\u8BB0\u5F55", "\u7B14\u8BB0", "note"] },
    ],
  },
];

export const AVATAR_PICKER_COUNT = 16;
export const AVATAR_POOL_SIZE = 1000;
export const DICEBEAR_NOTIONISTS_BASE_URL = "https://api.dicebear.com/9.x/notionists/svg";

/* ── Shared CSS class strings ── */

export const communityPanelClass =
  "rounded-[1.7rem] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.74] p-5 shadow-[0_24px_60px_rgb(15_23_42/0.08)] backdrop-blur-xl dark:bg-card/[0.84]";

export const communityCardClass =
  "liquid-glass border border-[rgb(var(--shiro-border-rgb)/0.16)] shadow-[0_14px_40px_rgb(15_23_42/0.06)]";

export const communityInputClass =
  "shiro-focus-ring w-full rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.28)] bg-background/[0.82] px-4 py-3 text-sm text-foreground outline-none transition dark:border-[rgb(var(--shiro-border-rgb)/0.32)] dark:bg-card/[0.9]";

export const communityTextareaClass =
  "aerisun-community-textarea shiro-focus-ring min-h-[160px] w-full rounded-[1.4rem] border border-[rgb(var(--shiro-border-rgb)/0.28)] bg-background/[0.82] px-4 py-4 text-sm leading-7 text-foreground outline-none transition dark:border-[rgb(var(--shiro-border-rgb)/0.32)] dark:bg-card/[0.9]";

export const communityChipClass =
  "inline-flex items-center gap-1.5 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.76] px-3 py-2 text-xs text-foreground/58 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] dark:bg-card/[0.8]";

export const communityPopupClass =
  "liquid-glass-strong border border-[rgb(var(--shiro-border-rgb)/0.16)]";

export const communityEmojiPopupClass =
  "absolute right-0 top-[calc(100%+0.65rem)] z-20 w-[19rem] rounded-[1.15rem] border border-[rgb(var(--shiro-border-rgb)/0.24)] bg-background/[0.94] p-3 shadow-[0_22px_60px_rgb(15_23_42/0.16)] backdrop-blur-xl dark:border-[rgb(var(--shiro-border-rgb)/0.3)] dark:bg-card/[0.96]";

export const communityEmojiSearchClass =
  "shiro-focus-ring w-full rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.2)] bg-background/[0.82] px-3 py-2 text-sm text-foreground outline-none transition placeholder:text-foreground/35 dark:border-[rgb(var(--shiro-border-rgb)/0.24)] dark:bg-card/[0.92]";

export const communityAvatarClass =
  "border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-card/[0.84] object-cover shadow-sm";

export const communityActionClass =
  "inline-flex items-center gap-1 rounded-full border border-transparent px-2.5 py-1 text-foreground/55 transition hover:border-[rgb(var(--shiro-border-rgb)/0.18)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]";

/* ── Utility functions ── */

export const normalizeName = (value: string) => value.trim().replace(/\s+/g, " ").toLowerCase();

export const normalizeEmailSeed = (value: string) => value.trim().toLowerCase().replace(/\s+/g, "");

export const hashString = (value: string) => {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
};

export const createSeededRandom = (seedValue: string) => {
  let state = hashString(seedValue) || 1;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 0x100000000;
  };
};

export const sampleAvatarIndexes = (identity: string, count = AVATAR_PICKER_COUNT) => {
  const normalized = normalizeEmailSeed(identity) || "visitor";
  const pool = Array.from({ length: AVATAR_POOL_SIZE }, (_, index) => index);
  const random = createSeededRandom(normalized);

  for (let index = pool.length - 1; index > 0; index -= 1) {
    const target = Math.floor(random() * (index + 1));
    [pool[index], pool[target]] = [pool[target], pool[index]];
  }

  return pool.slice(0, count);
};

export const buildAvatarSeed = (identity: string, poolIndex: number) => {
  const normalized = normalizeEmailSeed(identity) || "visitor";
  return hashString(`${normalized}:${poolIndex}`).toString(16).padStart(8, "0");
};

export const buildAvatarCandidate = (identity: string, poolIndex: number): AvatarPreset => {
  const seed = buildAvatarSeed(identity, poolIndex);
  return {
    key: seed,
    label: `Notionists ${String(poolIndex).padStart(3, "0")}`,
    avatar_url: `${DICEBEAR_NOTIONISTS_BASE_URL}?seed=${encodeURIComponent(seed)}`,
  };
};

export const shufflePresets = (presets: AvatarPreset[]) => {
  const next = [...presets];
  for (let index = next.length - 1; index > 0; index -= 1) {
    const target = Math.floor(Math.random() * (index + 1));
    [next[index], next[target]] = [next[target], next[index]];
  }
  return next;
};

export const buildAvatarPresets = (identity: string) => {
  const indexes = sampleAvatarIndexes(identity);
  const candidates = indexes.map((index) => buildAvatarCandidate(identity, index));
  return shufflePresets(candidates);
};

export const buildDefaultAvatarPreset = (identity: string): AvatarPreset => {
  const defaultIndex = sampleAvatarIndexes(identity, 1)[0] ?? 0;
  return buildAvatarCandidate(identity, defaultIndex);
};

export const fallbackAvatar = (name: string) =>
  `https://api.dicebear.com/9.x/notionists/svg?seed=${encodeURIComponent(name || "visitor")}`;

export const formatTimestamp = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const locale = getFrontendLang() === "zh" ? "zh-CN" : "en-US";

  return new Intl.DateTimeFormat(locale, {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
};

type EmojiGroupTranslator = (
  key: string,
  values?: Record<string, string | number>,
  fallback?: string,
) => string;

export const getLocalizedEmojiGroups = (
  translate: EmojiGroupTranslator = translateFrontendText,
): EmojiGroup[] => {
  return EMOJI_GROUPS.map((group) => ({
    ...group,
    title: group.titleKey ? translate(group.titleKey, undefined, group.title) : group.title,
  }));
};

export const readStoredDraft = (storageKey: string): Partial<DraftState> => {
  try {
    const raw = localStorage.getItem(storageKey);
    if (!raw) {
      return {};
    }
    const parsed = JSON.parse(raw) as Partial<DraftState>;
    return typeof parsed === "object" && parsed ? parsed : {};
  } catch {
    return {};
  }
};

export const insertTextAtSelection = (
  currentValue: string,
  insertion: string,
  textarea: HTMLTextAreaElement | null,
) => {
  if (!textarea) {
    const nextValue = `${currentValue}${insertion}`;
    return { nextValue, selectionStart: nextValue.length };
  }

  const start = textarea.selectionStart ?? currentValue.length;
  const end = textarea.selectionEnd ?? start;
  const nextValue = `${currentValue.slice(0, start)}${insertion}${currentValue.slice(end)}`;
  const selectionStart = start + insertion.length;
  return { nextValue, selectionStart };
};

export const resolveApiError = (
  error: unknown,
  fallback = translateFrontendText(
    "waline.common.requestFailed",
    undefined,
    "评论请求失败，请稍后再试。",
  ),
) => {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return fallback;
};

export const providerLabel = (provider: string) => {
  const normalized = provider.trim().toLowerCase();
  if (normalized === "github") return "GitHub";
  if (normalized === "google") return "Google";
  return provider;
};

export const sortComments = (items: CommunityCommentItem[], sorting: CommunityConfig["default_sorting"]) => {
  const compare = sorting === "oldest"
    ? (left: CommunityCommentItem, right: CommunityCommentItem) => (
      new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
    )
    : (left: CommunityCommentItem, right: CommunityCommentItem) => (
      new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
    );

  const sortReplies = (replies: CommunityCommentItem[]) =>
    [...replies]
      .sort((left, right) => new Date(left.created_at).getTime() - new Date(right.created_at).getTime())
      .map((reply) => ({
        ...reply,
        replies: sortReplies(reply.replies ?? []),
      }));

  return [...items].sort(compare).map((item) => ({
    ...item,
    replies: sortReplies(item.replies ?? []),
  }));
};

export const sortGuestbookEntries = (items: CommunityGuestbookItem[], sorting: CommunityConfig["default_sorting"]) => {
  const compare = sorting === "oldest"
    ? (left: CommunityGuestbookItem, right: CommunityGuestbookItem) => (
      new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
    )
    : (left: CommunityGuestbookItem, right: CommunityGuestbookItem) => (
      new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
    );

  return [...items].sort(compare);
};

export const collectAvatarUsage = (
  comments: CommunityCommentItem[],
  guestbookEntries: CommunityGuestbookItem[],
  pendingComments: CommunityCommentItem[],
  pendingGuestbookEntries: CommunityGuestbookItem[],
) => {
  const usage = new Map<string, Set<string>>();

  const addUsage = (avatar: string | null | undefined, avatarUrl: string | null | undefined, name: string) => {
    const normalizedName = normalizeName(name);
    for (const key of [avatar, avatarUrl]) {
      if (!key) continue;
      if (!usage.has(key)) {
        usage.set(key, new Set());
      }
      usage.get(key)?.add(normalizedName);
    }
  };

  const walkComments = (items: CommunityCommentItem[]) => {
    for (const item of items) {
      addUsage(item.avatar, item.avatar_url, item.author_name);
      if (item.replies?.length) {
        walkComments(item.replies);
      }
    }
  };

  walkComments(comments);
  walkComments(pendingComments);

  for (const item of [...guestbookEntries, ...pendingGuestbookEntries]) {
    addUsage(item.avatar, item.avatar_url, item.name);
  }

  return usage;
};

/* ── Shared small components ── */

import { ApiError } from "@serino/api-client";

export const StatusPill = ({ text, tone = "neutral" }: { text: string; tone?: "neutral" | "pending" | "author" }) => (
  <span
    className={[
      "inline-flex items-center rounded-full border px-2.5 py-1 text-[0.68rem] font-medium tracking-[0.18em] uppercase",
      tone === "pending"
        ? "border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300"
        : tone === "author"
          ? "border-[rgb(var(--shiro-accent-rgb)/0.22)] bg-[rgb(var(--shiro-accent-rgb)/0.08)] text-[rgb(var(--shiro-accent-rgb)/0.9)]"
          : "border-[rgb(var(--shiro-border-rgb)/0.16)] bg-[rgb(var(--shiro-panel-rgb)/0.08)] text-foreground/50",
    ].join(" ")}
  >
    {text}
  </span>
);
