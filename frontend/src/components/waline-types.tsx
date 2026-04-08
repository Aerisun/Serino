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
  is_author?: boolean;
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

/* ── Constants ── */

export const PROFILE_STORAGE_PREFIX = "aerisun:comment-profile:";

export const EMOJI_CHOICES: EmojiChoice[] = [
  { emoji: "\uD83D\uDE42", label: "\u5FAE\u7B11", keywords: ["\u5FAE\u7B11", "\u7B11", "\u5F00\u5FC3", "smile"] },
  { emoji: "\uD83D\uDE0A", label: "\u5F00\u5FC3", keywords: ["\u5F00\u5FC3", "\u5FEB\u4E50", "\u9AD8\u5174"] },
  { emoji: "\uD83D\uDE09", label: "\u7728\u773C", keywords: ["\u7728\u773C", "\u4FCA\u76AE", "wink"] },
  { emoji: "\uD83E\uDD70", label: "\u6696\u5FC3", keywords: ["\u6696\u5FC3", "\u5FC3\u52A8", "warm"] },
  { emoji: "\uD83E\uDEE0", label: "\u62E5\u62B1", keywords: ["\u62E5\u62B1", "\u5B89\u6170", "hug"] },
  { emoji: "\uD83E\uDD79", label: "\u611F\u52A8", keywords: ["\u611F\u52A8", "\u60F3\u54ED", "touching"] },
  { emoji: "\uD83D\uDE0C", label: "\u653E\u677E", keywords: ["\u653E\u677E", "\u5B89\u5FC3", "calm"] },
  { emoji: "\uD83D\uDE34", label: "\u56F0\u4E86", keywords: ["\u56F0", "\u75B2\u60EB", "sleepy"] },
  { emoji: "\uD83E\uDD17", label: "\u50BB\u7B11", keywords: ["\u50BB\u7B11", "\u5F00\u6717", "grin"] },
  { emoji: "\uD83E\uDD73", label: "\u5FAE\u9189", keywords: ["\u5FAE\u9189", "\u653E\u677E", "tipsy"] },
  { emoji: "\uD83E\uDD0D", label: "\u767D\u5FC3", keywords: ["\u767D\u5FC3", "\u7231\u5FC3", "love"] },
  { emoji: "\u2728", label: "\u95EA\u5149", keywords: ["\u95EA\u5149", "\u9B54\u6CD5", "sparkle"] },
  { emoji: "\uD83C\uDF37", label: "\u82B1\u6735", keywords: ["\u82B1", "\u6625\u5929", "flower"] },
  { emoji: "\uD83C\uDF3F", label: "\u56DB\u53F6\u8349", keywords: ["\u56DB\u53F6\u8349", "\u5E78\u8FD0", "lucky"] },
  { emoji: "\uD83D\uDE04", label: "\u5927\u7B11", keywords: ["\u5927\u7B11", "\u54C8\u54C8", "laugh"] },
  { emoji: "\uD83D\uDE02", label: "\u7B11\u54ED", keywords: ["\u7B11\u54ED", "\u7206\u7B11", "lol"] },
  { emoji: "\uD83D\uDE06", label: "\u76D8\u7B11", keywords: ["\u76D8\u7B11", "\u559C\u611F", "grinning"] },
  { emoji: "\uD83E\uDD73", label: "\u5E86\u795D", keywords: ["\u5E86\u795D", "\u6D3E\u5BF9", "party"] },
  { emoji: "\uD83E\uDD1D", label: "\u63E1\u624B", keywords: ["\u63E1\u624B", "\u5408\u4F5C", "\u5408\u4F5C\u6109\u5FEB"] },
  { emoji: "\uD83D\uDE4C", label: "\u4E3E\u624B", keywords: ["\u4E3E\u624B", "\u6B22\u547C", "cheer"] },
  { emoji: "\uD83D\uDC4F", label: "\u9F13\u638C", keywords: ["\u9F13\u638C", "\u8D5E", "applause"] },
  { emoji: "\uD83D\uDC4D", label: "\u70B9\u8D5E", keywords: ["\u70B9\u8D5E", "\u8D5E\u540C", "like"] },
  { emoji: "\uD83E\uDD18", label: "\u6253 call", keywords: ["call", "\u5E94\u63F4", "\u6253call"] },
  { emoji: "\uD83D\uDD25", label: "\u706B\u70ED", keywords: ["\u706B\u70ED", "\u5F88\u68D2", "hot"] },
  { emoji: "\uD83D\uDCA1", label: "\u7075\u611F", keywords: ["\u7075\u611F", "\u70B9\u5B50", "idea"] },
  { emoji: "\uD83D\uDE4F", label: "\u8C22\u8C22", keywords: ["\u611F\u8C22", "\u8C22\u8C22", "thanks"] },
  { emoji: "\uD83D\uDC4C", label: "\u6CA1\u95EE\u9898", keywords: ["ok", "\u6CA1\u95EE\u9898", "\u53EF\u4EE5"] },
  { emoji: "\uD83E\uDD14", label: "\u601D\u8003", keywords: ["\u601D\u8003", "\u60F3\u6CD5", "thinking"] },
  { emoji: "\uD83D\uDE2E", label: "\u60CA\u8BB6", keywords: ["\u60CA\u8BB6", "\u610F\u5916", "surprised"] },
  { emoji: "\uD83D\uDE0D", label: "\u5FC3\u52A8", keywords: ["\u5FC3\u52A8", "\u559C\u6B22", "love"] },
  { emoji: "\uD83E\uDD7A", label: "\u59D4\u5C48", keywords: ["\u59D4\u5C48", "\u60F3\u54ED", "sad"] },
  { emoji: "\uD83D\uDE0F", label: "\u5F97\u610F", keywords: ["\u5F97\u610F", "\u5C0F\u5F97\u610F", "smirk"] },
  { emoji: "\uD83D\uDE0E", label: "\u9177", keywords: ["\u9177", "\u6F47\u6D12", "cool"] },
  { emoji: "\uD83E\uDD79", label: "\u7834\u9632", keywords: ["\u7834\u9632", "\u611F\u52A8", "moved"] },
  { emoji: "\uD83D\uDE2D", label: "\u5927\u54ED", keywords: ["\u5927\u54ED", "\u6CEA\u76EE", "cry"] },
  { emoji: "\uD83D\uDE24", label: "\u4E0A\u5934", keywords: ["\u4E0A\u5934", "\u6FC0\u52A8", "frustrated"] },
  { emoji: "\uD83D\uDE2C", label: "\u5C34\u5C2C", keywords: ["\u5C34\u5C2C", "\u554A\u8FD9", "awkward"] },
  { emoji: "\uD83E\uDEE1", label: "\u5FEB\u8981\u878D\u5316", keywords: ["\u878D\u5316", "\u592A\u53EF\u7231", "melt"] },
  { emoji: "\uD83E\uDD72", label: "\u6492\u5A07", keywords: ["\u6492\u5A07", "\u53EF\u7231", "pleading"] },
  { emoji: "\uD83E\uDEF6", label: "\u6BD4\u5FC3", keywords: ["\u6BD4\u5FC3", "\u559C\u6B22", "heart"] },
  { emoji: "\uD83D\uDCAD", label: "\u804A\u804A", keywords: ["\u804A\u5929", "\u60F3\u6CD5", "chat"] },
  { emoji: "\uD83C\uDF19", label: "\u6708\u4EAE", keywords: ["\u6708\u4EAE", "\u591C\u665A", "moon"] },
  { emoji: "\u2615", label: "\u5496\u5561", keywords: ["\u5496\u5561", "\u4F11\u606F", "coffee"] },
  { emoji: "\uD83C\uDF75", label: "\u8336", keywords: ["\u8336", "\u653E\u677E", "tea"] },
  { emoji: "\uD83C\uDFA7", label: "\u97F3\u4E50", keywords: ["\u97F3\u4E50", "\u8033\u673A", "music"] },
  { emoji: "\uD83D\uDDBC\uFE0F", label: "\u753B\u6846", keywords: ["\u56FE\u7247", "\u753B\u6846", "art"] },
  { emoji: "\uD83D\uDCDD", label: "\u8BB0\u5F55", keywords: ["\u8BB0\u5F55", "\u7B14\u8BB0", "note"] },
  { emoji: "\uD83D\uDCD6", label: "\u9605\u8BFB", keywords: ["\u9605\u8BFB", "\u4E66", "book"] },
  { emoji: "\uD83D\uDD6F\uFE0F", label: "\u706F\u6CE1", keywords: ["\u6C1B\u56F4", "\u6696\u5149", "lamp"] },
  { emoji: "\uD83C\uDF08", label: "\u5F69\u8679", keywords: ["\u5F69\u8679", "\u6C1B\u56F4", "rainbow"] },
  { emoji: "\uD83C\uDF0C", label: "\u661F\u7A7A", keywords: ["\u661F\u7A7A", "\u591C\u666F", "night"] },
  { emoji: "\uD83C\uDF70", label: "\u86CB\u7CD5", keywords: ["\u86CB\u7CD5", "\u751C", "cake"] },
  { emoji: "\uD83C\uDF6A", label: "\u66F2\u5947", keywords: ["\u66F2\u5947", "\u96F6\u98DF", "cookie"] },
  { emoji: "\uD83C\uDF5C", label: "\u62C9\u9762", keywords: ["\u9762", "\u62C9\u9762", "ramen"] },
  { emoji: "\uD83C\uDF5F", label: "\u8591\u6761", keywords: ["\u8591\u6761", "\u5C0F\u5403", "fries"] },
  { emoji: "\uD83C\uDF71", label: "\u4FBF\u5F53", keywords: ["\u4FBF\u5F53", "\u5403\u996D", "bento"] },
  { emoji: "\uD83C\uDF53", label: "\u8349\u8393", keywords: ["\u8349\u8393", "\u6C34\u679C", "strawberry"] },
  { emoji: "\uD83C\uDF79", label: "\u679C\u6C41", keywords: ["\u996E\u6599", "\u679C\u6C41", "juice"] },
  { emoji: "\uD83E\uDD64", label: "\u51B7\u996E", keywords: ["\u51B7\u996E", "\u996E\u6599", "cup"] },
  { emoji: "\uD83C\uDF7B", label: "\u5E72\u676F", keywords: ["\u5E72\u676F", "\u78B0\u676F", "cheers"] },
  { emoji: "\uD83C\uDF68", label: "\u51B0\u6DC7\u6DCB", keywords: ["\u51B0\u6DC7\u6DCB", "\u751C\u54C1", "icecream"] },
  { emoji: "\uD83C\uDF72", label: "\u70ED\u4E4E\u4E4E", keywords: ["\u70ED\u4E4E", "\u6696\u80C3", "soup"] },
  { emoji: "\uD83C\uDF6C", label: "\u751C\u70B9", keywords: ["\u751C\u70B9", "\u96F6\u98DF", "candy"] },
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
  "absolute right-0 top-[calc(100%+0.65rem)] z-20 w-[19rem] max-w-[calc(100vw-2rem)] rounded-[1.15rem] border border-[rgb(var(--shiro-border-rgb)/0.24)] bg-background/[0.96] p-3 shadow-[0_22px_60px_rgb(15_23_42/0.16)] backdrop-blur-xl sm:w-[22rem] sm:max-w-[22rem] dark:border-[rgb(var(--shiro-border-rgb)/0.3)] dark:bg-card/[0.98]";

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

export const buildCommentAnchorId = (commentId: string) => `comment-${commentId}`;
export const COMMENT_JUMP_REQUEST_EVENT = "aerisun:comment-jump-request";

let activeHighlightedElement: HTMLElement | null = null;
let activeHighlightTimer: number | null = null;

export const scrollToCommentTarget = (commentId: string) => {
  if (typeof document === "undefined") {
    return;
  }

  let jumpRequested = false;

  const highlightTarget = (target: HTMLElement) => {
    if (activeHighlightedElement && activeHighlightedElement !== target) {
      activeHighlightedElement.classList.remove("aerisun-comment-jump-highlight");
    }
    if (activeHighlightTimer !== null) {
      window.clearTimeout(activeHighlightTimer);
    }

    target.classList.remove("aerisun-comment-jump-highlight");
    void target.getBoundingClientRect();
    target.classList.add("aerisun-comment-jump-highlight");
    activeHighlightedElement = target;

    activeHighlightTimer = window.setTimeout(() => {
      target.classList.remove("aerisun-comment-jump-highlight");
      if (activeHighlightedElement === target) {
        activeHighlightedElement = null;
      }
      activeHighlightTimer = null;
    }, 1600);
  };

  const tryScroll = (remainingAttempts: number) => {
    const target = document.getElementById(buildCommentAnchorId(commentId));
    if (target instanceof HTMLElement) {
      target.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
      highlightTarget(target);
      return;
    }

    if (!jumpRequested) {
      jumpRequested = true;
      window.dispatchEvent(
        new CustomEvent(COMMENT_JUMP_REQUEST_EVENT, {
          detail: { commentId },
        }),
      );
    }

    if (remainingAttempts <= 0) {
      return;
    }

    window.requestAnimationFrame(() => {
      tryScroll(remainingAttempts - 1);
    });
  };

  tryScroll(8);
};

export const formatTimestamp = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  const locale = getFrontendLang() === "zh" ? "zh-CN" : "en-US";

  return new Intl.DateTimeFormat(locale, {
    timeZone: "Asia/Shanghai",
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
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
