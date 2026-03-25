import { startTransition, useCallback, useDeferredValue, useEffect, useMemo, useRef, useState } from "react";
import {
  Check,
  ChevronDown,
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
import {
  DEFAULT_COMMUNITY_CONFIG,
  loadCommunityConfig,
  type AvatarPreset,
  type CommunityConfig,
  type CommunitySurface,
} from "@/lib/community-config";
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
const EMOJI_GROUPS = [
  ["🙂", "😊", "😉", "🥹", "😌", "🤍", "✨", "🌷"],
  ["😄", "😂", "🥳", "🤝", "🙌", "👏", "🔥", "💡"],
  ["🫶", "💭", "🌙", "☕", "🍵", "🎧", "🖼️", "📝"],
];

const FALLBACK_AVATAR_PRESETS: AvatarPreset[] = [
  { key: "shiro", label: "Shiro", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Shiro" },
  { key: "glass", label: "Glass", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Glass" },
  { key: "aurora", label: "Aurora", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Aurora" },
  { key: "paper", label: "Paper", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Paper" },
  { key: "dawn", label: "Dawn", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Dawn" },
  { key: "pebble", label: "Pebble", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Pebble" },
  { key: "amber", label: "Amber", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Amber" },
  { key: "mint", label: "Mint", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Mint" },
  { key: "cinder", label: "Cinder", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Cinder" },
  { key: "tide", label: "Tide", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Tide" },
  { key: "plum", label: "Plum", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Plum" },
  { key: "linen", label: "Linen", avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Linen" },
];

const normalizeName = (value: string) => value.trim().replace(/\s+/g, " ").toLowerCase();

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
          className="rounded-[1.4rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-[rgb(var(--shiro-panel-rgb)/0.1)] p-4 shadow-[0_14px_40px_rgb(15_23_42/0.06)] backdrop-blur"
        >
          <div className="flex items-start gap-3">
            <img
              src={avatarSrc}
              alt={item.author_name}
              className="h-11 w-11 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-white/70 object-cover shadow-sm"
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
                  className="inline-flex items-center gap-1 rounded-full border border-transparent px-2.5 py-1 transition hover:border-[rgb(var(--shiro-border-rgb)/0.18)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
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
  const isGuestbook = surface === "guestbook";
  const storageKey = `${PROFILE_STORAGE_PREFIX}${surface}:${slug ?? "guestbook"}`;
  const storedDraft = readStoredDraft(storageKey);
  const [config, setConfig] = useState<CommunityConfig | null>(communityConfig ?? null);
  const [loadingConfig, setLoadingConfig] = useState(!communityConfig);
  const [loadingEntries, setLoadingEntries] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [refreshSeed, setRefreshSeed] = useState(0);
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
  const [editorMode, setEditorMode] = useState<EditorMode>("write");
  const [imageUploading, setImageUploading] = useState(false);
  const avatarPickerRef = useRef<HTMLDivElement | null>(null);
  const emojiPickerRef = useRef<HTMLDivElement | null>(null);
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
  const [avatarPresets, setAvatarPresets] = useState<AvatarPreset[]>(FALLBACK_AVATAR_PRESETS);

  useEffect(() => {
    const source = resolvedConfig.avatarPresets?.length ? resolvedConfig.avatarPresets : FALLBACK_AVATAR_PRESETS;
    setAvatarPresets(shufflePresets(source));
  }, [resolvedConfig.avatarPresets, refreshSeed]);

  useEffect(() => {
    if (!avatarPresets.length) {
      return;
    }
    if (draft.avatarKey && avatarPresets.some((preset) => preset.key === draft.avatarKey)) {
      return;
    }
    setDraft((current) => ({ ...current, avatarKey: avatarPresets[0].key }));
  }, [avatarPresets, draft.avatarKey]);

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

  const handleEmojiInsert = useCallback((emoji: string) => {
    insertIntoBody(emoji);
    setEmojiPickerOpen(false);
  }, [insertIntoBody]);

  const handleImageUpload = useCallback(async (file: File) => {
    setImageUploading(true);
    setSubmitError(null);
    setSubmitNotice(null);

    try {
      const response = await uploadCommentImageApiV1PublicCommentImagePost({ file } as never);
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
  }, [draft.body, insertIntoBody]);

  const handleSubmit = useCallback(async () => {
    if (!draft.name.trim()) {
      setSubmitError("请先填写昵称。");
      return;
    }
    if (!draft.email.trim()) {
      setSubmitError("请填写邮箱，昵称会和邮箱绑定。");
      return;
    }
    if (!draft.body.trim()) {
      setSubmitError(isGuestbook ? "留言内容不能为空。" : "评论内容不能为空。");
      return;
    }
    if (!draft.avatarKey) {
      setSubmitError("请先选择一个头像。");
      return;
    }

    setSubmitting(true);
    setSubmitError(null);
    setSubmitNotice(null);

    try {
      if (isGuestbook) {
        const payload = {
          name: draft.name.trim(),
          email: draft.email.trim(),
          website: draft.website.trim() || null,
          body: draft.body.trim(),
          avatar_key: draft.avatarKey,
        };
        const response = await createGuestbookApiV1PublicGuestbookPost(payload as never);
        const created = response.data.item as CommunityGuestbookItem;
        setPendingGuestbookEntries((current) => [created, ...current]);
      } else {
        const payload = {
          author_name: draft.name.trim(),
          author_email: draft.email.trim(),
          body: draft.body.trim(),
          parent_id: replyTarget?.id ?? null,
          avatar_key: draft.avatarKey,
        };
        const response = await createCommentApiV1PublicCommentsContentTypeSlugPost(surface, slug ?? "", payload as never);
        const created = response.data.item as CommunityCommentItem;
        setPendingComments((current) => [created, ...current]);
      }

      setDraft((current) => ({ ...current, body: "" }));
      setReplyTarget(null);
      setSubmitNotice("已经收到，审核通过后会出现在当前页面。");
      startTransition(() => {
        void loadEntries();
      });
    } catch (error) {
      setSubmitError(resolveApiError(error));
    } finally {
      setSubmitting(false);
    }
  }, [draft, isGuestbook, loadEntries, replyTarget, slug, surface]);

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
      <div className="rounded-[1.7rem] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-[linear-gradient(135deg,rgba(var(--shiro-panel-rgb),0.16),rgba(255,255,255,0.82))] p-5 shadow-[0_24px_60px_rgb(15_23_42/0.08)] backdrop-blur">
        <div className="inline-flex items-center gap-2 text-[0.72rem] font-medium uppercase tracking-[0.22em] text-foreground/42">
          <Sparkles className="h-3.5 w-3.5" />
          {isGuestbook ? "Guestbook" : "Comments"}
        </div>

        <div className="mt-5 grid gap-3 md:grid-cols-2">
          <label className="space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">昵称</span>
            <input
              value={draft.name}
              onChange={(event) => handleFieldChange("name", event.target.value)}
              placeholder="输入要显示的名字"
              className="w-full rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-white/70 px-4 py-3 text-sm text-foreground outline-none transition focus:border-[rgb(var(--shiro-accent-rgb)/0.28)] focus:ring-2 focus:ring-[rgb(var(--shiro-accent-rgb)/0.12)]"
            />
          </label>
          <label className="space-y-2">
            <span className="flex items-center gap-2 text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">
              邮箱
              <LockKeyhole className="h-3.5 w-3.5" />
            </span>
            <input
              type="email"
              value={draft.email}
              onChange={(event) => handleFieldChange("email", event.target.value)}
              placeholder="仅用于绑定昵称，不会公开显示"
              className="w-full rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-white/70 px-4 py-3 text-sm text-foreground outline-none transition focus:border-[rgb(var(--shiro-accent-rgb)/0.28)] focus:ring-2 focus:ring-[rgb(var(--shiro-accent-rgb)/0.12)]"
            />
          </label>
        </div>

        {isGuestbook ? (
          <label className="mt-3 block space-y-2">
            <span className="text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">网站</span>
            <input
              value={draft.website}
              onChange={(event) => handleFieldChange("website", event.target.value)}
              placeholder="https://example.com"
              className="w-full rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-white/70 px-4 py-3 text-sm text-foreground outline-none transition focus:border-[rgb(var(--shiro-accent-rgb)/0.28)] focus:ring-2 focus:ring-[rgb(var(--shiro-accent-rgb)/0.12)]"
            />
          </label>
        ) : null}

        <div ref={avatarPickerRef} className="relative mt-4">
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={toggleAvatarPicker}
              className="group relative inline-flex h-14 w-14 shrink-0 items-center justify-center overflow-hidden rounded-full border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-white/86 p-1.5 shadow-[0_14px_36px_rgb(15_23_42/0.08)] transition hover:border-[rgb(var(--shiro-accent-rgb)/0.26)] hover:shadow-[0_18px_40px_rgb(15_23_42/0.12)]"
              aria-expanded={avatarPickerOpen}
              aria-label="打开头像库"
            >
              <img
                src={selectedPreset?.avatar_url || fallbackAvatar(draft.name)}
                alt={selectedPreset?.label || draft.name || "当前头像"}
                className="h-full w-full rounded-full object-cover"
              />
              <span className="absolute inset-0 rounded-full ring-1 ring-black/5 ring-inset" />
            </button>
            <button
              type="button"
              onClick={toggleAvatarPicker}
              className="inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-white/62 px-3 py-2 text-xs uppercase tracking-[0.2em] text-foreground/52 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
            >
              头像
              <ChevronDown className={`h-3.5 w-3.5 transition ${avatarPickerOpen ? "rotate-180" : ""}`} />
            </button>
            <p className="text-xs text-foreground/42">点开选择，展开时会重新打散顺序。</p>
          </div>

          {avatarPickerOpen ? (
            <div className="absolute left-0 top-full z-20 mt-3 w-full max-w-[26rem] rounded-[1.35rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(var(--shiro-panel-rgb),0.16))] p-4 shadow-[0_28px_70px_rgb(15_23_42/0.16)] backdrop-blur">
              <div className="grid grid-cols-4 gap-3 sm:grid-cols-5">
                {avatarPresets.map((preset) => {
                  const occupied = isAvatarOccupied(preset);
                  const selected = draft.avatarKey === preset.key;
                  return (
                    <button
                      key={preset.key}
                      type="button"
                      title={preset.label}
                      disabled={occupied && !selected}
                      onClick={() => {
                        handleFieldChange("avatarKey", preset.key);
                        setAvatarPickerOpen(false);
                      }}
                      className={[
                        "group relative rounded-full border p-1 transition",
                        selected
                          ? "border-[rgb(var(--shiro-accent-rgb)/0.38)] bg-[rgb(var(--shiro-accent-rgb)/0.1)] shadow-[0_12px_28px_rgb(var(--shiro-accent-rgb)/0.14)]"
                          : "border-[rgb(var(--shiro-border-rgb)/0.14)] bg-white/80 hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:bg-white",
                        occupied && !selected ? "cursor-not-allowed opacity-35" : "",
                      ].join(" ")}
                    >
                      <img
                        src={preset.avatar_url}
                        alt={preset.label}
                        className="h-12 w-12 rounded-full object-cover shadow-sm sm:h-14 sm:w-14"
                        loading="lazy"
                      />
                      {selected ? (
                        <span className="absolute -right-0.5 -top-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-[rgb(var(--shiro-accent-rgb)/0.92)] text-white shadow-sm">
                          <Check className="h-3 w-3" />
                        </span>
                      ) : null}
                      {occupied && !selected ? (
                        <span className="absolute -right-0.5 -top-0.5 inline-flex h-5 w-5 items-center justify-center rounded-full bg-black/70 text-white shadow-sm">
                          <LockKeyhole className="h-3 w-3" />
                        </span>
                      ) : null}
                    </button>
                  );
                })}
              </div>
            </div>
          ) : null}
        </div>

        {replyTarget ? (
          <div className="mt-4 flex flex-wrap items-center gap-2 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-[rgb(var(--shiro-panel-rgb)/0.12)] px-4 py-3 text-sm text-foreground/62">
            <CornerDownRight className="h-4 w-4" />
            正在回复 <span className="font-semibold text-foreground">{replyTarget.name}</span>
            <button
              type="button"
              onClick={() => setReplyTarget(null)}
              className="inline-flex items-center gap-1 rounded-full border border-transparent px-2 py-1 text-xs transition hover:border-[rgb(var(--shiro-border-rgb)/0.16)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
            >
              <X className="h-3.5 w-3.5" />
              取消回复
            </button>
          </div>
        ) : null}

        <div className="mt-4 space-y-2">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <span className="text-xs font-medium uppercase tracking-[0.22em] text-foreground/40">
              {isGuestbook ? "留言正文" : "评论正文"}
            </span>
            <div className="flex flex-wrap items-center gap-2">
              <div className="inline-flex rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-white/68 p-1">
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

              <div ref={emojiPickerRef} className="relative">
                <button
                  type="button"
                  onClick={() => setEmojiPickerOpen((current) => !current)}
                  className="inline-flex items-center gap-1.5 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-white/68 px-3 py-2 text-xs text-foreground/58 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
                >
                  <Smile className="h-3.5 w-3.5" />
                  Emoji
                </button>
                {emojiPickerOpen ? (
                  <div className="absolute right-0 top-full z-20 mt-2 w-[18rem] rounded-[1.2rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-[linear-gradient(180deg,rgba(255,255,255,0.96),rgba(var(--shiro-panel-rgb),0.16))] p-3 shadow-[0_22px_60px_rgb(15_23_42/0.14)] backdrop-blur">
                    <div className="space-y-2">
                      {EMOJI_GROUPS.map((group, index) => (
                        <div key={`emoji-group-${index}`} className="grid grid-cols-8 gap-1.5">
                          {group.map((emoji) => (
                            <button
                              key={emoji}
                              type="button"
                              onClick={() => handleEmojiInsert(emoji)}
                              className="inline-flex h-8 w-8 items-center justify-center rounded-full bg-white/72 text-base transition hover:bg-[rgb(var(--shiro-accent-rgb)/0.12)]"
                            >
                              {emoji}
                            </button>
                          ))}
                        </div>
                      ))}
                    </div>
                  </div>
                ) : null}
              </div>

              <button
                type="button"
                onClick={() => imageInputRef.current?.click()}
                disabled={imageUploading}
                className="inline-flex items-center gap-1.5 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-white/68 px-3 py-2 text-xs text-foreground/58 transition hover:border-[rgb(var(--shiro-accent-rgb)/0.22)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] disabled:cursor-not-allowed disabled:opacity-60"
              >
                {imageUploading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImagePlus className="h-3.5 w-3.5" />}
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
            </div>
          </div>

          {editorMode === "preview" ? (
            <div className="min-h-[160px] rounded-[1.4rem] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-white/76 px-4 py-4">
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
              className="aerisun-community-textarea min-h-[160px] w-full rounded-[1.4rem] border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-white/76 px-4 py-4 text-sm leading-7 text-foreground outline-none transition focus:border-[rgb(var(--shiro-accent-rgb)/0.28)] focus:ring-2 focus:ring-[rgb(var(--shiro-accent-rgb)/0.12)]"
            />
          )}
        </div>

        {submitError ? (
          <div className="mt-4 rounded-2xl border border-red-500/18 bg-red-500/8 px-4 py-3 text-sm text-red-600 dark:text-red-300">
            {submitError}
          </div>
        ) : null}
        {submitNotice ? (
          <div className="mt-4 rounded-2xl border border-emerald-500/18 bg-emerald-500/8 px-4 py-3 text-sm text-emerald-700 dark:text-emerald-300">
            {submitNotice}
          </div>
        ) : null}

        <div className="mt-5 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs leading-6 text-foreground/42">
            提交后会先进入审核队列；昵称和邮箱一旦绑定，后续只有相同邮箱才能继续使用这个昵称。
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
            className="mt-3 inline-flex items-center gap-2 rounded-full border border-[rgb(var(--shiro-border-rgb)/0.18)] px-4 py-2 text-sm transition hover:border-[rgb(var(--shiro-accent-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
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
                        className="rounded-[1.2rem] border border-amber-500/18 bg-white/72 p-4"
                      >
                        <div className="flex items-start gap-3">
                          <img
                            src={item.avatar_url || fallbackAvatar(item.name)}
                            alt={item.name}
                            className="h-11 w-11 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-white object-cover"
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
                    className="rounded-[1.5rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-[rgb(var(--shiro-panel-rgb)/0.1)] p-4 shadow-[0_14px_40px_rgb(15_23_42/0.06)]"
                  >
                    <div className="flex items-start gap-3">
                      <img
                        src={item.avatar_url || fallbackAvatar(item.name)}
                        alt={item.name}
                        className="h-12 w-12 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-white/70 object-cover shadow-sm"
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
                        className="rounded-[1.2rem] border border-amber-500/18 bg-white/72 p-4"
                      >
                        <div className="flex items-start gap-3">
                          <img
                            src={item.avatar_url || fallbackAvatar(item.author_name)}
                            alt={item.author_name}
                            className="h-11 w-11 rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-white object-cover"
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
