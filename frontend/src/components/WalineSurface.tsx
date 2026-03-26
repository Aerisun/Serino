import { startTransition, useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  CornerDownRight,
  Eye,
  ImagePlus,
  Loader2,
  LockKeyhole,
  PencilLine,
  RefreshCw,
  Reply,
  Send,
  Smile,
  Sparkles,
  X,
} from "lucide-react";
import {
  createCommentApiV1PublicCommentsContentTypeSlugPost,
  createGuestbookApiV1PublicGuestbookPost,
  readCommentsApiV1PublicCommentsContentTypeSlugGet,
  readGuestbookApiV1PublicGuestbookGet,
  uploadCommentImageApiV1PublicCommentImagePost,
} from "@serino/api-client/public";
import { ApiError } from "@serino/api-client";
import { AnimatePresence, motion } from "motion/react";
import { transition } from "@/config";
import {
  DEFAULT_COMMUNITY_CONFIG,
  loadCommunityConfig,
  type AvatarPreset,
  type CommunityConfig,
  type CommunitySurface,
} from "@/lib/community-config";
import { useSiteAuth } from "@/contexts/site-auth";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { compressImageFile } from "@/lib/image-upload";
import MarkdownRenderer from "@/components/MarkdownRenderer";
import "./WalineSurface.css";

export interface WalineSurfaceProps {
  surface: CommunitySurface;
  slug?: string;
  className?: string;
  communityConfig?: CommunityConfig | null;
}

interface CommunityCommentItem {
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

interface CommunityGuestbookItem {
  id: string;
  name: string;
  website?: string | null;
  body: string;
  status: string;
  created_at: string;
  avatar?: string | null;
  avatar_url?: string | null;
}

interface DraftState {
  name: string;
  email: string;
  website: string;
  body: string;
  avatarKey: string;
}

type EditorMode = "write" | "preview";

interface ReplyTarget {
  id: string;
  name: string;
}

const PROFILE_STORAGE_PREFIX = "aerisun:comment-profile:";
interface EmojiChoice {
  emoji: string;
  label: string;
  keywords: string[];
}

interface EmojiGroup {
  title: string;
  items: EmojiChoice[];
}

const EMOJI_GROUPS: EmojiGroup[] = [
  {
    title: "日常",
    items: [
      { emoji: "🙂", label: "微笑", keywords: ["微笑", "笑", "开心", "smile"] },
      { emoji: "😊", label: "开心", keywords: ["开心", "快乐", "高兴"] },
      { emoji: "😉", label: "眨眼", keywords: ["眨眼", "俏皮", "wink"] },
      { emoji: "🥹", label: "感动", keywords: ["感动", "想哭", "touching"] },
      { emoji: "😌", label: "放松", keywords: ["放松", "安心", "calm"] },
      { emoji: "🤍", label: "白心", keywords: ["白心", "爱心", "love"] },
      { emoji: "✨", label: "闪光", keywords: ["闪光", "魔法", "sparkle"] },
      { emoji: "🌷", label: "花朵", keywords: ["花", "春天", "flower"] },
    ],
  },
  {
    title: "互动",
    items: [
      { emoji: "😄", label: "大笑", keywords: ["大笑", "哈哈", "laugh"] },
      { emoji: "😂", label: "笑哭", keywords: ["笑哭", "爆笑", "lol"] },
      { emoji: "🥳", label: "庆祝", keywords: ["庆祝", "派对", "party"] },
      { emoji: "🤝", label: "握手", keywords: ["握手", "合作", "合作愉快"] },
      { emoji: "🙌", label: "举手", keywords: ["举手", "欢呼", "cheer"] },
      { emoji: "👏", label: "鼓掌", keywords: ["鼓掌", "赞", "applause"] },
      { emoji: "🔥", label: "火热", keywords: ["火热", "很棒", "hot"] },
      { emoji: "💡", label: "灵感", keywords: ["灵感", "点子", "idea"] },
    ],
  },
  {
    title: "氛围",
    items: [
      { emoji: "🫶", label: "比心", keywords: ["比心", "喜欢", "heart"] },
      { emoji: "💭", label: "思考", keywords: ["思考", "想法", "idea"] },
      { emoji: "🌙", label: "月亮", keywords: ["月亮", "夜晚", "moon"] },
      { emoji: "☕", label: "咖啡", keywords: ["咖啡", "休息", "coffee"] },
      { emoji: "🍵", label: "茶", keywords: ["茶", "放松", "tea"] },
      { emoji: "🎧", label: "音乐", keywords: ["音乐", "耳机", "music"] },
      { emoji: "🖼️", label: "画框", keywords: ["图片", "画框", "art"] },
      { emoji: "📝", label: "记录", keywords: ["记录", "笔记", "note"] },
    ],
  },
];

const AVATAR_PICKER_COUNT = 16;
const AVATAR_POOL_SIZE = 1000;
const DICEBEAR_NOTIONISTS_BASE_URL = "https://api.dicebear.com/9.x/notionists/svg";

const normalizeName = (value: string) => value.trim().replace(/\s+/g, " ").toLowerCase();

const normalizeEmailSeed = (value: string) => value.trim().toLowerCase().replace(/\s+/g, "");

const hashString = (value: string) => {
  let hash = 0x811c9dc5;
  for (let index = 0; index < value.length; index += 1) {
    hash ^= value.charCodeAt(index);
    hash = Math.imul(hash, 0x01000193);
  }
  return hash >>> 0;
};

const createSeededRandom = (seedValue: string) => {
  let state = hashString(seedValue) || 1;
  return () => {
    state = (Math.imul(state, 1664525) + 1013904223) >>> 0;
    return state / 0x100000000;
  };
};

const sampleAvatarIndexes = (identity: string, count = AVATAR_PICKER_COUNT) => {
  const normalized = normalizeEmailSeed(identity) || "visitor";
  const pool = Array.from({ length: AVATAR_POOL_SIZE }, (_, index) => index);
  const random = createSeededRandom(normalized);

  for (let index = pool.length - 1; index > 0; index -= 1) {
    const target = Math.floor(random() * (index + 1));
    [pool[index], pool[target]] = [pool[target], pool[index]];
  }

  return pool.slice(0, count);
};

const buildAvatarSeed = (identity: string, poolIndex: number) => {
  const normalized = normalizeEmailSeed(identity) || "visitor";
  return hashString(`${normalized}:${poolIndex}`).toString(16).padStart(8, "0");
};

const buildAvatarCandidate = (identity: string, poolIndex: number): AvatarPreset => {
  const seed = buildAvatarSeed(identity, poolIndex);
  return {
    key: seed,
    label: `Notionists ${String(poolIndex).padStart(3, "0")}`,
    avatar_url: `${DICEBEAR_NOTIONISTS_BASE_URL}?seed=${encodeURIComponent(seed)}`,
  };
};

const buildAvatarPresets = (identity: string) => {
  const indexes = sampleAvatarIndexes(identity);
  const candidates = indexes.map((index) => buildAvatarCandidate(identity, index));
  return shufflePresets(candidates);
};

const buildDefaultAvatarPreset = (identity: string): AvatarPreset => {
  const defaultIndex = sampleAvatarIndexes(identity, 1)[0] ?? 0;
  return buildAvatarCandidate(identity, defaultIndex);
};

const fallbackAvatar = (name: string) =>
  `https://api.dicebear.com/9.x/notionists/svg?seed=${encodeURIComponent(name || "visitor")}`;

const formatTimestamp = (value: string) => {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }

  return new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
};

const shufflePresets = (presets: AvatarPreset[]) => {
  const next = [...presets];
  for (let index = next.length - 1; index > 0; index -= 1) {
    const target = Math.floor(Math.random() * (index + 1));
    [next[index], next[target]] = [next[target], next[index]];
  }
  return next;
};

const readStoredDraft = (storageKey: string): Partial<DraftState> => {
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

const insertTextAtSelection = (
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

const resolveApiError = (error: unknown) => {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error && error.message.trim()) {
    return error.message;
  }
  return "评论请求失败，请稍后再试。";
};

const providerLabel = (provider: string) => {
  const normalized = provider.trim().toLowerCase();
  if (normalized === "github") return "GitHub";
  if (normalized === "google") return "Google";
  return provider;
};

const sortComments = (items: CommunityCommentItem[], sorting: CommunityConfig["commentSorting"]) => {
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

const sortGuestbookEntries = (items: CommunityGuestbookItem[], sorting: CommunityConfig["commentSorting"]) => {
  const compare = sorting === "oldest"
    ? (left: CommunityGuestbookItem, right: CommunityGuestbookItem) => (
      new Date(left.created_at).getTime() - new Date(right.created_at).getTime()
    )
    : (left: CommunityGuestbookItem, right: CommunityGuestbookItem) => (
      new Date(right.created_at).getTime() - new Date(left.created_at).getTime()
    );

  return [...items].sort(compare);
};

const collectAvatarUsage = (
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

const StatusPill = ({ text, tone = "neutral" }: { text: string; tone?: "neutral" | "pending" | "author" }) => (
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

const communityPanelClass =
  "rounded-[1.7rem] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.74] p-5 shadow-[0_24px_60px_rgb(15_23_42/0.08)] backdrop-blur-xl dark:bg-card/[0.84]";

const communityCardClass =
  "liquid-glass border border-[rgb(var(--shiro-border-rgb)/0.16)] shadow-[0_14px_40px_rgb(15_23_42/0.06)]";

const communityInputClass =
  "shiro-focus-ring w-full rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.28)] bg-background/[0.82] px-4 py-3 text-sm text-foreground outline-none transition dark:border-[rgb(var(--shiro-border-rgb)/0.32)] dark:bg-card/[0.9]";

const communityTextareaClass =
  "aerisun-community-textarea shiro-focus-ring min-h-[160px] w-full rounded-[1.4rem] border border-[rgb(var(--shiro-border-rgb)/0.28)] bg-background/[0.82] px-4 py-4 text-sm leading-7 text-foreground outline-none transition dark:border-[rgb(var(--shiro-border-rgb)/0.32)] dark:bg-card/[0.9]";

const communityChipClass =
  "inline-flex items-center gap-1.5 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.76] px-3 py-2 text-xs text-foreground/58 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] dark:bg-card/[0.8]";

const communityPopupClass =
  "liquid-glass-strong border border-[rgb(var(--shiro-border-rgb)/0.16)]";

const communityEmojiPopupClass =
  "absolute right-0 top-[calc(100%+0.65rem)] z-20 w-[19rem] rounded-[1.15rem] border border-[rgb(var(--shiro-border-rgb)/0.24)] bg-background/[0.94] p-3 shadow-[0_22px_60px_rgb(15_23_42/0.16)] backdrop-blur-xl dark:border-[rgb(var(--shiro-border-rgb)/0.3)] dark:bg-card/[0.96]";

const communityEmojiSearchClass =
  "shiro-focus-ring w-full rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.2)] bg-background/[0.82] px-3 py-2 text-sm text-foreground outline-none transition placeholder:text-foreground/35 dark:border-[rgb(var(--shiro-border-rgb)/0.24)] dark:bg-card/[0.92]";

const communityAvatarClass =
  "border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-card/[0.84] object-cover shadow-sm";

const communityActionClass =
  "inline-flex items-center gap-1 rounded-full border border-transparent px-2.5 py-1 text-foreground/55 transition hover:border-[rgb(var(--shiro-border-rgb)/0.18)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]";

const CommentThread = ({
  items,
  onReply,
  depth = 0,
}: {
  items: CommunityCommentItem[];
  onReply: (target: ReplyTarget) => void;
  depth?: number;
}) => (
  <div className={depth > 0 ? "mt-4 border-l border-[rgb(var(--shiro-border-rgb)/0.14)] pl-4" : "space-y-4"}>
    {items.map((item) => {
      const avatarSrc = item.avatar_url || fallbackAvatar(item.author_name);
      return (
        <article
          key={item.id}
          className={`${communityCardClass} rounded-[1.4rem] p-4`}
        >
          <div className="flex items-start gap-3">
            <img
              src={avatarSrc}
              alt={item.author_name}
              className={`${communityAvatarClass} h-11 w-11 rounded-2xl`}
              loading="lazy"
            />
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="font-body text-sm font-semibold text-foreground">{item.author_name}</span>
                {item.is_author ? <StatusPill text="站长" tone="author" /> : null}
                <span className="text-xs text-foreground/40">{formatTimestamp(item.created_at)}</span>
              </div>
              <div className="mt-2">
                <MarkdownRenderer content={item.body} className="aerisun-comment-body" />
              </div>
              <div className="mt-3 flex items-center gap-3 text-xs text-foreground/45">
                <button
                  type="button"
                  onClick={() => onReply({ id: item.id, name: item.author_name })}
                  className={communityActionClass}
                >
                  <Reply className="h-3.5 w-3.5" />
                  回复
                </button>
              </div>
              {item.replies?.length ? (
                <CommentThread items={item.replies} onReply={onReply} depth={depth + 1} />
              ) : null}
            </div>
          </div>
        </article>
      );
    })}
  </div>
);

const WalineSurface = ({
  surface,
  slug,
  className,
  communityConfig,
}: WalineSurfaceProps) => {
  const prefersReducedMotion = useReducedMotionPreference();
  const isGuestbook = surface === "guestbook";
  const storageKey = `${PROFILE_STORAGE_PREFIX}${surface}:${slug ?? "guestbook"}`;
  const storedDraft = readStoredDraft(storageKey);
  const { user: siteUser, loading: authLoading, openLogin, logout } = useSiteAuth();
  const [config, setConfig] = useState<CommunityConfig | null>(communityConfig ?? null);
  const [loadingConfig, setLoadingConfig] = useState(!communityConfig);
  const [loadingEntries, setLoadingEntries] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [refreshSeed, setRefreshSeed] = useState(0);
  const [authError, setAuthError] = useState<string | null>(null);
  const [comments, setComments] = useState<CommunityCommentItem[]>([]);
  const [guestbookEntries, setGuestbookEntries] = useState<CommunityGuestbookItem[]>([]);
  const [pendingComments, setPendingComments] = useState<CommunityCommentItem[]>([]);
  const [pendingGuestbookEntries, setPendingGuestbookEntries] = useState<CommunityGuestbookItem[]>([]);
  const [draft, setDraft] = useState<DraftState>({
    name: typeof storedDraft.name === "string" ? storedDraft.name : "",
    email: typeof storedDraft.email === "string" ? storedDraft.email : "",
    website: typeof storedDraft.website === "string" ? storedDraft.website : "",
    body: "",
    avatarKey: typeof storedDraft.avatarKey === "string" ? storedDraft.avatarKey : "",
  });
  const [replyTarget, setReplyTarget] = useState<ReplyTarget | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [submitNotice, setSubmitNotice] = useState<string | null>(null);
  const [avatarPickerOpen, setAvatarPickerOpen] = useState(false);
  const [emojiPickerOpen, setEmojiPickerOpen] = useState(false);
  const [emojiQuery, setEmojiQuery] = useState("");
  const [editorMode, setEditorMode] = useState<EditorMode>("write");
  const [composerOpen, setComposerOpen] = useState(false);
  const [imageUploading, setImageUploading] = useState(false);
  const avatarPickerRef = useRef<HTMLDivElement | null>(null);
  const emojiPickerRef = useRef<HTMLDivElement | null>(null);
  const emojiSearchRef = useRef<HTMLInputElement | null>(null);
  const imageInputRef = useRef<HTMLInputElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const deferredBody = useDeferredValue(draft.body);

  useEffect(() => {
    if (communityConfig) {
      setConfig(communityConfig);
      setLoadingConfig(false);
      return;
    }

    let active = true;
    setLoadingConfig(true);
    void loadCommunityConfig()
      .then((nextConfig) => {
        if (!active) return;
        setConfig(nextConfig);
      })
      .finally(() => {
        if (active) {
          setLoadingConfig(false);
        }
      });

    return () => {
      active = false;
    };
  }, [communityConfig]);

  const resolvedConfig = config ?? DEFAULT_COMMUNITY_CONFIG;
  const emojiSelectionEnabled = resolvedConfig.enableEnjoySearch !== false;
  const imageUploadsEnabled = resolvedConfig.imageUploader;
  const loginMode = resolvedConfig.loginMode ?? "enable";
  const requiresAuthentication = loginMode === "force" || resolvedConfig.anonymousEnabled === false;
  const oauthProviderLabels = useMemo(
    () => (resolvedConfig.oauthProviders ?? []).map(providerLabel),
    [resolvedConfig.oauthProviders],
  );
  const authSession = siteUser
    ? {
        objectId: siteUser.id,
        display_name: siteUser.effective_display_name,
        email: siteUser.email,
        url: "",
        avatar: siteUser.effective_avatar_url,
        is_admin: siteUser.is_admin ?? false,
      }
    : null;
  const [avatarPresets, setAvatarPresets] = useState<AvatarPreset[]>([]);
  const defaultAvatarPreset = useMemo(
    () => buildDefaultAvatarPreset(draft.email || draft.name),
    [draft.email, draft.name],
  );

  useEffect(() => {
    setAvatarPresets(buildAvatarPresets(draft.email || draft.name));
  }, [draft.email, draft.name, refreshSeed]);

  useEffect(() => {
    if (authSession) {
      return;
    }
    if (!avatarPresets.length) {
      return;
    }
    if (draft.avatarKey && avatarPresets.some((preset) => preset.key === draft.avatarKey)) {
      return;
    }
    setDraft((current) => ({ ...current, avatarKey: defaultAvatarPreset.key }));
  }, [authSession, avatarPresets, defaultAvatarPreset.key, draft.avatarKey]);

  useEffect(() => {
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({
          name: draft.name,
          email: draft.email,
          website: draft.website,
          avatarKey: draft.avatarKey,
        }),
      );
    } catch {
      // Ignore storage failures.
    }
  }, [draft.avatarKey, draft.email, draft.name, draft.website, storageKey]);

  const loadEntries = useCallback(async () => {
    if (!isGuestbook && !slug) {
      setLoadError("当前内容缺少评论路径，暂时无法加载评论。");
      setLoadingEntries(false);
      return;
    }

    setLoadingEntries(true);
    setLoadError(null);

    try {
      if (isGuestbook) {
        const response = await readGuestbookApiV1PublicGuestbookGet();
        setGuestbookEntries(sortGuestbookEntries(response.data.items as CommunityGuestbookItem[], resolvedConfig.commentSorting));
        return;
      }

      const response = await readCommentsApiV1PublicCommentsContentTypeSlugGet(surface, slug ?? "");
      setComments(sortComments(response.data.items as CommunityCommentItem[], resolvedConfig.commentSorting));
    } catch (error) {
      setLoadError(resolveApiError(error));
    } finally {
      setLoadingEntries(false);
    }
  }, [isGuestbook, resolvedConfig.commentSorting, slug, surface]);

  useEffect(() => {
    void loadEntries();
  }, [loadEntries]);

  useEffect(() => {
    if (!avatarPickerOpen && !emojiPickerOpen) {
      return;
    }

    const handlePointerDown = (event: MouseEvent) => {
      if (!avatarPickerRef.current?.contains(event.target as Node)) {
        setAvatarPickerOpen(false);
      }
      if (!emojiPickerRef.current?.contains(event.target as Node)) {
        setEmojiPickerOpen(false);
      }
    };

    document.addEventListener("mousedown", handlePointerDown);
    return () => {
      document.removeEventListener("mousedown", handlePointerDown);
    };
  }, [avatarPickerOpen, emojiPickerOpen]);

  useEffect(() => {
    if (!emojiSelectionEnabled) {
      setEmojiPickerOpen(false);
      setEmojiQuery("");
    }
  }, [emojiSelectionEnabled]);

  useEffect(() => {
    if (!emojiPickerOpen) {
      setEmojiQuery("");
      return;
    }

    const frame = requestAnimationFrame(() => {
      emojiSearchRef.current?.focus();
    });

    return () => {
      cancelAnimationFrame(frame);
    };
  }, [emojiPickerOpen]);

  useEffect(() => {
    if (replyTarget) {
      setComposerOpen(true);
    }
  }, [replyTarget]);

  const avatarUsage = useMemo(
    () => collectAvatarUsage(comments, guestbookEntries, pendingComments, pendingGuestbookEntries),
    [comments, guestbookEntries, pendingComments, pendingGuestbookEntries],
  );

  const isAvatarOccupied = useCallback((preset: AvatarPreset) => {
    const occupants = avatarUsage.get(preset.key) ?? avatarUsage.get(preset.avatar_url);
    if (!occupants || occupants.size === 0) {
      return false;
    }

    const activeName = normalizeName(draft.name);
    if (!activeName) {
      return true;
    }

    return Array.from(occupants).some((name) => name !== activeName);
  }, [avatarUsage, draft.name]);

  const handleFieldChange = useCallback(
    (field: keyof DraftState, value: string) => {
      setDraft((current) => ({ ...current, [field]: value }));
      setSubmitError(null);
      setSubmitNotice(null);
    },
    [],
  );

  const insertIntoBody = useCallback((insertion: string) => {
    const textarea = textareaRef.current;
    const { nextValue, selectionStart } = insertTextAtSelection(draft.body, insertion, textarea);
    setDraft((current) => ({ ...current, body: nextValue }));
    setSubmitError(null);
    setSubmitNotice(null);
    setEditorMode("write");
    requestAnimationFrame(() => {
      textareaRef.current?.focus();
      textareaRef.current?.setSelectionRange(selectionStart, selectionStart);
    });
  }, [draft.body]);

  const deferredEmojiQuery = useDeferredValue(emojiQuery.trim().toLowerCase());

  const filteredEmojiGroups = useMemo(() => {
    const query = deferredEmojiQuery;
    if (!query) {
      return EMOJI_GROUPS;
    }

    return EMOJI_GROUPS
      .map((group) => ({
        ...group,
        items: group.items.filter((choice) => {
          const label = choice.label.toLowerCase();
          return (
            choice.emoji.includes(query)
            || label.includes(query)
            || choice.keywords.some((keyword) => keyword.toLowerCase().includes(query))
          );
        }),
      }))
      .filter((group) => group.items.length > 0);
  }, [deferredEmojiQuery]);

  const handleEmojiInsert = useCallback((emoji: string) => {
    if (!emojiSelectionEnabled) {
      return;
    }
    insertIntoBody(emoji);
    setEmojiPickerOpen(false);
  }, [emojiSelectionEnabled, insertIntoBody]);

  const handleImageUpload = useCallback(async (file: File) => {
    if (!imageUploadsEnabled) {
      setSubmitError("当前站点已关闭评论图片上传。");
      if (imageInputRef.current) {
        imageInputRef.current.value = "";
      }
      return;
    }

    setImageUploading(true);
    setSubmitError(null);
    setSubmitNotice(null);

    try {
      const compressedFile = await compressImageFile(file, {
        maxDimension: 1920,
        quality: 0.82,
        minBytesToCompress: config?.imageMaxBytes ?? 512 * 1024,
      });
      const response = await uploadCommentImageApiV1PublicCommentImagePost({ file: compressedFile } as never);
      const imageUrl = response.data.data?.url;
      if (!imageUrl) {
        throw new Error("图片上传成功，但没有返回可用地址。");
      }
      const alt = file.name.replace(/\.[^.]+$/, "").trim() || "image";
      const prefix = draft.body.trim() ? "\n" : "";
      insertIntoBody(`${prefix}![${alt}](${imageUrl})\n`);
    } catch (error) {
      setSubmitError(resolveApiError(error));
    } finally {
      setImageUploading(false);
      if (imageInputRef.current) {
        imageInputRef.current.value = "";
      }
    }
  }, [config?.imageMaxBytes, draft.body, imageUploadsEnabled, insertIntoBody]);

  const handleLogout = useCallback(() => {
    setAuthError(null);
    void logout();
  }, [logout]);

  const handleSubmit = useCallback(async () => {
    if (requiresAuthentication && !authSession) {
      setSubmitError(isGuestbook ? "当前站点已关闭匿名留言，请先登录后再留言。" : "当前站点已关闭匿名评论，请先登录后再发表评论。");
      return;
    }

    const authorName = authSession?.display_name?.trim() || draft.name.trim();
    const authorEmail = authSession?.email?.trim() || draft.email.trim();
    const authorWebsite = authSession?.url?.trim() || draft.website.trim();
    const avatarKey = authSession ? `oauth-${authSession.objectId}` : draft.avatarKey;

    if (!authSession && !authorName) {
      setSubmitError("请先填写昵称。");
      return;
    }
    if (!authSession && !authorEmail) {
      setSubmitError("请填写邮箱，昵称会和邮箱绑定。");
      return;
    }
    if (!draft.body.trim()) {
      setSubmitError(isGuestbook ? "留言内容不能为空。" : "评论内容不能为空。");
      return;
    }
    if (!authSession && !avatarKey) {
      setSubmitError("请先选择一个头像。");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setSubmitNotice(null);

    try {
      if (isGuestbook) {
        const payload = {
          name: authorName,
          email: authorEmail,
          website: authorWebsite || null,
          body: draft.body.trim(),
          avatar_key: avatarKey,
        };
        const response = await createGuestbookApiV1PublicGuestbookPost(payload as never);
        const created = response.data.item as CommunityGuestbookItem;
        setPendingGuestbookEntries((current) => [created, ...current]);
      } else {
        const payload = {
          author_name: authorName,
          author_email: authorEmail,
          body: draft.body.trim(),
          parent_id: replyTarget?.id ?? null,
          avatar_key: avatarKey,
        };
        const response = await createCommentApiV1PublicCommentsContentTypeSlugPost(surface, slug ?? "", payload as never);
        const created = response.data.item as CommunityCommentItem;
        setPendingComments((current) => [created, ...current]);
      }

      setDraft((current) => ({ ...current, body: "" }));
      setReplyTarget(null);
      setComposerOpen(false);
      setSubmitNotice("已经收到，审核通过后会出现在当前页面。");
      startTransition(() => {
        void loadEntries();
      });
    } catch (error) {
      setSubmitError(resolveApiError(error));
    } finally {
      setSubmitting(false);
    }
  }, [authSession, draft, isGuestbook, loadEntries, requiresAuthentication, replyTarget, slug, surface]);

  const selectedPreset = avatarPresets.find((preset) => preset.key === draft.avatarKey) ?? avatarPresets[0] ?? null;
  const toggleAvatarPicker = useCallback(() => {
    setAvatarPickerOpen((current) => {
      if (!current) {
        setRefreshSeed((value) => value + 1);
      }
      return !current;
    });
  }, []);

  return (
    <section className={`aerisun-community-surface space-y-5 ${className ?? ""}`.trim()}>
      <div className={communityPanelClass}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="inline-flex items-center gap-2 text-[0.72rem] font-medium uppercase tracking-[0.22em] text-foreground/42">
            <Sparkles className="h-3.5 w-3.5" />
            {isGuestbook ? "Guestbook" : "Comments"}
          </div>
          <button
            type="button"
            onClick={() => setComposerOpen((current) => !current)}
            className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.76] px-4 py-2 text-sm font-medium text-foreground/60 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] dark:bg-card/[0.82]"
          >
            <PencilLine className="h-4 w-4" />
            {composerOpen ? (replyTarget ? "收起回复框" : "收起编辑区") : replyTarget ? "写回复" : isGuestbook ? "写留言" : "写评论"}
          </button>
        </div>

        <div className="mt-4 space-y-3">

          <AnimatePresence initial={false}>
            {composerOpen ? (
              <motion.div
                key="composer-open"
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: "auto", opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={transition({ duration: 0.3, reducedMotion: prefersReducedMotion })}
                className="overflow-hidden"
              >
                <div ref={avatarPickerRef} className="space-y-4">
                  {replyTarget ? (
                    <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.72] px-4 py-3 text-sm text-foreground/48 dark:bg-card/[0.82]">
                      <Sparkles className="h-4 w-4" />
                      正在回复 {replyTarget.name}
                    </div>
                  ) : null}

                  {authLoading ? (
                    <div className="rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.7] px-4 py-3 text-sm text-foreground/48 dark:bg-card/[0.78]">
                      正在检查登录状态...
                    </div>
                  ) : authSession ? (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.72] px-4 py-3 dark:bg-card/[0.82]">
                      <div className="flex items-center gap-3">
                        <img
                          src={authSession.avatar || fallbackAvatar(authSession.display_name)}
                          alt={authSession.display_name}
                          className="h-12 w-12 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] object-cover"
                        />
                        <div className="min-w-0">
                          <div className="flex flex-wrap items-center gap-2">
                            <span className="font-semibold text-foreground">{authSession.display_name}</span>
                            <StatusPill text={authSession.is_admin ? "管理员模式" : "已登录"} tone="author" />
                          </div>
                          <p className="mt-1 text-xs text-foreground/45">
                            {authSession.is_admin
                              ? `将使用 ${authSession.display_name} 和站点 Hero 图以管理员身份提交评论。`
                              : `将使用 ${authSession.display_name} 的昵称、邮箱和头像提交评论。`}
                          </p>
                        </div>
                      </div>
                      <button
                        type="button"
                        onClick={handleLogout}
                        className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.7] px-3.5 py-2 text-xs font-medium text-foreground/60 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:text-[rgb(var(--shiro-accent-rgb)/0.84)] dark:bg-card/[0.82]"
                      >
                        <X className="h-3.5 w-3.5" />
                        退出登录
                      </button>
                    </div>
                  ) : loginMode !== "disable" || requiresAuthentication ? (
                    <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.72] px-4 py-3 dark:bg-card/[0.82]">
                      <div className="space-y-1">
                        <p className="text-sm font-medium text-foreground">登录后自动使用 Google / GitHub 资料</p>
                        <p className="text-xs text-foreground/45">
                          登录后昵称、邮箱和头像会由 OAuth 资料固定，手动输入项会隐藏。
                        </p>
                        {oauthProviderLabels.length ? (
                          <div className="flex flex-wrap gap-2 pt-1">
                            {oauthProviderLabels.map((label) => (
                              <span
                                key={label}
                                className="inline-flex items-center rounded-full border border-[rgb(var(--shiro-border-rgb)/0.14)] bg-background/[0.8] px-2.5 py-1 text-[0.7rem] text-foreground/58 dark:bg-card/[0.88]"
                              >
                                {label}
                              </span>
                            ))}
                          </div>
                        ) : null}
                      </div>
                      <button
                        type="button"
                        onClick={openLogin}
                        className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-accent-rgb)/0.24)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] px-4 py-2.5 text-sm font-semibold text-[rgb(var(--shiro-accent-rgb)/0.88)] transition hover:bg-[rgb(var(--shiro-accent-rgb)/0.14)] disabled:cursor-not-allowed disabled:opacity-60"
                      >
                        <LockKeyhole className="h-4 w-4" />
                        登录评论
                      </button>
                    </div>
                  ) : null}

                  {authError ? (
                    <div className="rounded-2xl border border-amber-500/18 bg-amber-500/8 px-4 py-3 text-sm text-amber-700 dark:text-amber-300">
                      {authError}
                    </div>
                  ) : null}

                  {!authSession ? (
                    <div className="relative">
                      {loginMode !== "force" || !requiresAuthentication ? (
                        <div className="grid grid-cols-[auto_minmax(0,1fr)] items-end gap-3 md:grid-cols-[auto_minmax(0,0.92fr)_minmax(0,1.08fr)] md:gap-4">
                          <div className="self-end">
                            <button
                              type="button"
                              onClick={toggleAvatarPicker}
                              className="group relative inline-flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-full border border-[rgb(var(--shiro-border-rgb)/0.22)] bg-card/[0.9] p-1.5 shadow-[0_14px_36px_rgb(15_23_42/0.08)] transition hover:border-[rgb(var(--shiro-accent-rgb)/0.28)] hover:shadow-[0_18px_40px_rgb(15_23_42/0.12)] dark:border-[rgb(var(--shiro-border-rgb)/0.28)] dark:bg-card/[0.96]"
                              aria-expanded={avatarPickerOpen}
                              aria-label="打开头像库"
                            >
                              <img
                                src={selectedPreset?.avatar_url || fallbackAvatar(draft.name)}
                                alt={selectedPreset?.label || draft.name || "当前头像"}
                                className="h-full w-full rounded-full object-cover"
                              />
                              <span className="absolute inset-0 rounded-full ring-1 ring-black/5 ring-inset dark:ring-white/10" />
                            </button>
                          </div>

                          <label className="space-y-2">
                            <span className="text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">昵称</span>
                            <input
                              value={draft.name}
                              onChange={(event) => handleFieldChange("name", event.target.value)}
                              placeholder="输入要显示的名字"
                              className={communityInputClass}
                            />
                          </label>
                          <label className="col-span-full space-y-2 md:col-span-1">
                            <span className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">
                              邮箱
                              <LockKeyhole className="h-3.5 w-3.5" />
                            </span>
                            <input
                              type="email"
                              value={draft.email}
                              onChange={(event) => handleFieldChange("email", event.target.value)}
                              placeholder="仅用于绑定昵称，不会公开显示"
                              className={communityInputClass}
                            />
                          </label>
                        </div>
                      ) : null}

                      {avatarPickerOpen ? (
                        <div className="pointer-events-none absolute left-0 top-[calc(100%+0.8rem)] z-20 w-[18.5rem] max-w-[calc(100vw-4rem)] md:w-[20rem]">
                          <div className={`pointer-events-auto rounded-[1.35rem] p-4 shadow-[0_28px_70px_rgb(15_23_42/0.16)] ${communityPopupClass}`}>
                            <div className="grid grid-cols-4 gap-3">
                              {avatarPresets.map((preset) => {
                                const occupied = isAvatarOccupied(preset);
                                const selected = draft.avatarKey === preset.key;
                                const locked = occupied && !selected;
                                return (
                                  <button
                                    key={preset.key}
                                    type="button"
                                    title={locked ? `${preset.label} 已被占用` : preset.label}
                                    disabled={locked}
                                    aria-disabled={locked}
                                    onClick={() => {
                                      handleFieldChange("avatarKey", preset.key);
                                      setAvatarPickerOpen(false);
                                    }}
                                    className={[
                                      "group relative rounded-full border p-1 transition",
                                      selected
                                        ? "border-[rgb(var(--shiro-accent-rgb)/0.38)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] shadow-[0_12px_28px_rgb(var(--shiro-accent-rgb)/0.14)]"
                                        : "border-[rgb(var(--shiro-border-rgb)/0.14)] bg-card/[0.84] hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] dark:bg-card/[0.92]",
                                      locked ? "cursor-not-allowed opacity-45 grayscale-[0.2] saturate-50" : "",
                                    ].join(" ")}
                                  >
                                    <img
                                      src={preset.avatar_url}
                                      alt={preset.label}
                                      className={`h-12 w-12 rounded-full object-cover shadow-sm md:h-14 md:w-14 ${locked ? "opacity-80" : ""}`}
                                      loading="lazy"
                                    />
                                    {selected ? (
                                      <span className="absolute -right-0.5 -top-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-[rgb(var(--shiro-accent-rgb)/0.92)] text-white shadow-sm">
                                        <Check className="h-3 w-3" />
                                      </span>
                                    ) : null}
                                    {locked ? (
                                      <span className="absolute inset-0 flex items-center justify-center rounded-full bg-black/32 text-white/92 shadow-sm backdrop-blur-[1px]">
                                        <LockKeyhole className="h-3 w-3" />
                                      </span>
                                    ) : null}
                                  </button>
                                );
                              })}
                            </div>
                          </div>
                        </div>
                      ) : null}
                    </div>
                  ) : null}

                  {!authSession && isGuestbook ? (
                    <label className="block space-y-2">
                      <span className="text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">网站</span>
                      <input
                        value={draft.website}
                        onChange={(event) => handleFieldChange("website", event.target.value)}
                        placeholder="https://example.com"
                        className={communityInputClass}
                      />
                    </label>
                  ) : null}

                  {replyTarget ? (
                    <div className="shiro-accent-panel flex flex-wrap items-center gap-2 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] px-4 py-3 text-sm text-foreground/62">
                      <CornerDownRight className="h-4 w-4" />
                      正在回复 <span className="font-semibold text-foreground">{replyTarget.name}</span>
                      <button
                        type="button"
                        onClick={() => setReplyTarget(null)}
                        className={`${communityActionClass} px-2 text-xs`}
                      >
                        <X className="h-3.5 w-3.5" />
                        取消回复
                      </button>
                    </div>
                  ) : null}

                  {!authSession && isGuestbook ? (
                    <label className="block space-y-2">
                      <span className="text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">网站</span>
                      <input
                        value={draft.website}
                        onChange={(event) => handleFieldChange("website", event.target.value)}
                        placeholder="https://example.com"
                        className={communityInputClass}
                      />
                    </label>
                  ) : null}

                  {replyTarget ? (
                    <div className="shiro-accent-panel flex flex-wrap items-center gap-2 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] px-4 py-3 text-sm text-foreground/62">
                      <CornerDownRight className="h-4 w-4" />
                      正在回复 <span className="font-semibold text-foreground">{replyTarget.name}</span>
                      <button
                        type="button"
                        onClick={() => setReplyTarget(null)}
                        className={`${communityActionClass} px-2 text-xs`}
                      >
                        <X className="h-3.5 w-3.5" />
                        取消回复
                      </button>
                    </div>
                  ) : null}

                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="inline-flex rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.74] p-1 dark:bg-card/[0.8]">
                        <button
                          type="button"
                          onClick={() => setEditorMode("write")}
                          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition ${
                            editorMode === "write"
                              ? "bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.88)]"
                              : "text-foreground/52 hover:text-foreground/76"
                          }`}
                        >
                          <PencilLine className="h-3.5 w-3.5" />
                          编辑
                        </button>
                        <button
                          type="button"
                          onClick={() => setEditorMode("preview")}
                          className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs transition ${
                            editorMode === "preview"
                              ? "bg-[rgb(var(--shiro-accent-rgb)/0.12)] text-[rgb(var(--shiro-accent-rgb)/0.88)]"
                              : "text-foreground/52 hover:text-foreground/76"
                          }`}
                        >
                          <Eye className="h-3.5 w-3.5" />
                          预览
                        </button>
                      </div>

                      <div className="flex flex-wrap items-center gap-2">
                        {emojiSelectionEnabled ? (
                          <div ref={emojiPickerRef} className="relative">
                            <button
                              type="button"
                              onClick={() => setEmojiPickerOpen((current) => !current)}
                              className={communityChipClass}
                              aria-expanded={emojiPickerOpen}
                              aria-label="打开表情选择器"
                            >
                              <Smile className="h-3.5 w-3.5" />
                              表情
                            </button>
                            {emojiPickerOpen ? (
                              <div className={communityEmojiPopupClass}>
                                <label className="block space-y-2">
                                  <span className="text-[0.65rem] font-medium uppercase tracking-[0.22em] text-foreground/40">
                                    搜索表情
                                  </span>
                                  <input
                                    ref={emojiSearchRef}
                                    value={emojiQuery}
                                    onChange={(event) => setEmojiQuery(event.target.value)}
                                    placeholder="输入表情名、关键词或表情本身"
                                    className={communityEmojiSearchClass}
                                  />
                                </label>

                                <div className="mt-3 max-h-56 space-y-3 overflow-auto pr-1">
                                  {filteredEmojiGroups.length ? filteredEmojiGroups.map((group) => (
                                    <div key={group.title} className="space-y-2">
                                      <p className="text-[0.65rem] font-medium uppercase tracking-[0.22em] text-foreground/35">
                                        {group.title}
                                      </p>
                                      <div className="grid grid-cols-6 gap-2">
                                        {group.items.map((choice) => (
                                          <button
                                            key={choice.emoji}
                                            type="button"
                                            title={choice.label}
                                            onClick={() => handleEmojiInsert(choice.emoji)}
                                            className="inline-flex h-8 w-8 items-center justify-center rounded-full border border-transparent bg-background/[0.76] text-base transition hover:border-[rgb(var(--shiro-accent-rgb)/0.2)] hover:bg-[rgb(var(--shiro-accent-rgb)/0.12)] dark:bg-card/[0.82]"
                                          >
                                            {choice.emoji}
                                          </button>
                                        ))}
                                      </div>
                                    </div>
                                  )) : (
                                    <div className="rounded-2xl border border-dashed border-[rgb(var(--shiro-border-rgb)/0.18)] px-3 py-6 text-center text-sm text-foreground/40">
                                      没有找到匹配的表情。
                                    </div>
                                  )}
                                </div>
                              </div>
                            ) : null}
                          </div>
                        ) : null}

                        {imageUploadsEnabled ? (
                          <>
                            <button
                              type="button"
                              onClick={() => imageInputRef.current?.click()}
                              disabled={imageUploading}
                              className={`${communityChipClass} disabled:cursor-not-allowed disabled:opacity-60`}
                            >
                              {imageUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImagePlus className="h-3.5 w-4" />}
                              图片
                            </button>
                            <input
                              ref={imageInputRef}
                              type="file"
                              accept="image/*"
                              className="hidden"
                              onChange={(event) => {
                                const file = event.target.files?.[0];
                                if (file) {
                                  void handleImageUpload(file);
                                }
                              }}
                            />
                          </>
                        ) : null}
                      </div>
                    </div>

                    {editorMode === "preview" ? (
                      <div className="min-h-[160px] rounded-[1.4rem] border border-[rgb(var(--shiro-border-rgb)/0.28)] bg-background/[0.82] px-4 py-4 dark:border-[rgb(var(--shiro-border-rgb)/0.32)] dark:bg-card/[0.9]">
                        {deferredBody.trim() ? (
                          <MarkdownRenderer content={deferredBody} className="aerisun-comment-preview" />
                        ) : (
                          <div className="flex min-h-[128px] items-center justify-center text-sm text-foreground/42">
                            这里会显示 Markdown 预览。
                          </div>
                        )}
                      </div>
                    ) : (
                      <textarea
                        ref={textareaRef}
                        value={draft.body}
                        onChange={(event) => handleFieldChange("body", event.target.value)}
                        placeholder={isGuestbook ? "写下一句问候、反馈或交换友链时想说的话" : "写下你的看法、补充或追问"}
                        className={communityTextareaClass}
                      />
                    )}
                  </div>

                  {submitError ? (
                    <div className="rounded-2xl border border-red-500/18 bg-red-500/8 px-4 py-3 text-sm text-red-600 dark:text-red-300">
                      {submitError}
                    </div>
                  ) : null}
                  {submitNotice ? (
                    <div className="rounded-2xl border border-emerald-500/18 bg-emerald-500/8 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
                      {submitNotice}
                    </div>
                  ) : null}

                  <div className="flex flex-wrap items-center justify-between gap-3">
                    <p className="text-xs leading-6 text-foreground/42">
                      {authSession
                        ? "提交后会先进入审核队列；当前内容将固定使用你的 OAuth 昵称和头像。"
                        : "提交后会先进入审核队列；昵称和邮箱一旦绑定，后续只有相同邮箱才能继续使用这个昵称。"}
                    </p>
                    <button
                      type="button"
                      onClick={() => void handleSubmit()}
                      disabled={submitting}
                      className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-accent-rgb)/0.24)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] px-5 py-2.5 text-sm font-semibold text-[rgb(var(--shiro-accent-rgb)/0.88)] transition hover:bg-[rgb(var(--shiro-accent-rgb)/0.14)] disabled:cursor-not-allowed disabled:opacity-60"
                    >
                      {submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
                      {submitting ? "提交中..." : isGuestbook ? "发表留言" : replyTarget ? "提交回复" : "提交评论"}
                    </button>
                  </div>
                </div>
              </motion.div>
            ) : null}
          </AnimatePresence>
        </div>
      </div>

      {loadingConfig || loadingEntries ? (
        <div className="aerisun-waline-loading">
          <Loader2 className="h-5 w-5 animate-spin" />
          <span>{isGuestbook ? "留言板正在更新..." : "正在载入评论..."}</span>
        </div>
      ) : loadError ? (
        <div className="aerisun-waline-empty">
          <p>{loadError}</p>
          <button
            type="button"
            onClick={() => void loadEntries()}
            className="mt-3 inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.7] px-4 py-2 text-sm transition hover:border-[rgb(var(--shiro-accent-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] dark:bg-card/[0.8]"
          >
            <RefreshCw className="h-4 w-4" />
            重试加载
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {isGuestbook ? (
            <>
              {pendingGuestbookEntries.length ? (
                <div className="rounded-[1.5rem] border border-dashed border-amber-500/26 bg-amber-500/8 p-4">
                  <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-700 dark:text-amber-300">
                    <Sparkles className="h-4 w-4" />
                    刚刚提交，等待审核
                  </div>
                  <div className="space-y-3">
                    {pendingGuestbookEntries.map((item) => (
                      <article
                        key={`pending-${item.id}`}
                        className="rounded-[1.2rem] border border-amber-500/18 bg-background/[0.76] p-4 dark:bg-card/[0.84]"
                      >
                        <div className="flex items-start gap-3">
                          <img
                            src={item.avatar_url || fallbackAvatar(item.name)}
                            alt={item.name}
                            className={`${communityAvatarClass} h-11 w-11 rounded-2xl`}
                            loading="lazy"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold text-foreground">{item.name}</span>
                              <StatusPill text="待审核" tone="pending" />
                              <span className="text-xs text-foreground/40">{formatTimestamp(item.created_at)}</span>
                            </div>
                            <div className="mt-2">
                              <MarkdownRenderer content={item.body} className="aerisun-comment-body" />
                            </div>
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}

              {guestbookEntries.length ? (
                guestbookEntries.map((item) => (
                  <article
                    key={item.id}
                    className={`${communityCardClass} rounded-[1.5rem] p-4`}
                  >
                    <div className="flex items-start gap-3">
                      <img
                        src={item.avatar_url || fallbackAvatar(item.name)}
                        alt={item.name}
                        className={`${communityAvatarClass} h-12 w-12 rounded-2xl`}
                        loading="lazy"
                      />
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-semibold text-foreground">{item.name}</span>
                          <span className="text-xs text-foreground/40">{formatTimestamp(item.created_at)}</span>
                          {item.website ? (
                            <a
                              href={item.website}
                              target="_blank"
                              rel="noreferrer"
                              className="text-xs text-[rgb(var(--shiro-accent-rgb)/0.78)] underline-offset-4 hover:underline"
                            >
                              {item.website.replace(/^https?:\/\//, "")}
                            </a>
                          ) : null}
                        </div>
                        <div className="mt-2">
                          <MarkdownRenderer content={item.body} className="aerisun-comment-body" />
                        </div>
                      </div>
                    </div>
                  </article>
                ))
              ) : (
                <div className="aerisun-waline-empty">
                  还没有公开留言，第一条就写在这里。
                </div>
              )}
            </>
          ) : comments.length || pendingComments.length ? (
            <>
              {pendingComments.length ? (
                <div className="rounded-[1.5rem] border border-dashed border-amber-500/26 bg-amber-500/8 p-4">
                  <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-amber-700 dark:text-amber-300">
                    <Sparkles className="h-4 w-4" />
                    已提交，等待审核
                  </div>
                  <div className="space-y-3">
                    {pendingComments.map((item) => (
                      <article
                        key={`pending-${item.id}`}
                        className="rounded-[1.2rem] border border-amber-500/18 bg-background/[0.76] p-4 dark:bg-card/[0.84]"
                      >
                        <div className="flex items-start gap-3">
                          <img
                            src={item.avatar_url || fallbackAvatar(item.author_name)}
                            alt={item.author_name}
                            className={`${communityAvatarClass} h-11 w-11 rounded-2xl`}
                            loading="lazy"
                          />
                          <div className="min-w-0 flex-1">
                            <div className="flex flex-wrap items-center gap-2">
                              <span className="font-semibold text-foreground">{item.author_name}</span>
                              <StatusPill text="待审核" tone="pending" />
                              <span className="text-xs text-foreground/40">{formatTimestamp(item.created_at)}</span>
                            </div>
                            <div className="mt-2">
                              <MarkdownRenderer content={item.body} className="aerisun-comment-body" />
                            </div>
                          </div>
                        </div>
                      </article>
                    ))}
                  </div>
                </div>
              ) : null}

              {comments.length ? (
                <CommentThread items={comments} onReply={setReplyTarget} />
              ) : (
                <div className="aerisun-waline-empty">
                  还没有公开评论，第一条就从这里开始。
                </div>
              )}
            </>
          ) : (
            <div className="aerisun-waline-empty">
              当前还没有评论，第一条会在审核后显示在这里。
            </div>
          )}
        </div>
      )}
    </section>
  );
};

export default WalineSurface;
