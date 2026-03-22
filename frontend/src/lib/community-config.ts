import { apiClient } from "@/lib/api";

export type CommunitySurface = "posts" | "diary" | "guestbook";
export type CommunityCommentSort = "latest" | "oldest" | "hottest";

export interface CommentAvatarPreset {
  id: string;
  label: string;
  src: string;
  note?: string;
  accent?: string;
}

export interface CommentFeaturePill {
  key: string;
  label: string;
  detail?: string;
  tone?: "default" | "muted" | "accent" | "positive" | "warning";
}

export interface CommentSurfaceActivity {
  type:
    | "sort-change"
    | "draft-restored"
    | "draft-saved"
    | "avatar-change"
    | "submission-success"
    | "submission-error"
    | "status";
  surface: CommunitySurface;
  slug: string;
  message: string;
  sort?: CommunityCommentSort;
  avatarId?: string | null;
  avatarLabel?: string | null;
  draftLength?: number;
}

export interface CommentDraftSnapshot {
  body: string;
  fields: Record<string, string>;
  avatarId: string | null;
  updatedAt: number;
}

export type WalineSearchImage = {
  src: string;
  title?: string;
  preview?: string;
};

export interface WalineSearchOptions {
  search: (word: string) => Promise<WalineSearchImage[]>;
  default?: () => Promise<WalineSearchImage[]>;
  more?: (word: string, currentCount: number) => Promise<WalineSearchImage[]>;
}

export interface WalineEmojiPreset {
  name: string;
  folder?: string;
  icon?: string;
  prefix?: string;
  type?: string;
  items: string[];
}

export interface CommunityConfig {
  provider: "waline";
  serverURL: string;
  meta: Array<"nick" | "mail" | "link">;
  requiredMeta: Array<"nick" | "mail">;
  loginMode: "disable" | "enable" | "force";
  commentSorting: CommunityCommentSort;
  oauthProviders?: string[];
  anonymousEnabled?: boolean;
  moderationMode?: string;
  enableEnjoySearch: boolean;
  imageUploader: boolean;
  emojiPresets: Array<string | WalineEmojiPreset>;
  enjoySearchEndpoint?: string | null;
  enjoySearchDefaultWords?: string[];
  avatarStrategy?: string | null;
  avatarLibraryEnabled: boolean;
  avatarLibrary: CommentAvatarPreset[];
  guestAvatarMode?: string | null;
  draftEnabled?: boolean;
  helperCopy?: string | null;
  pageSize?: number | null;
  lang?: string | null;
  darkSelector?: string | null;
}

export interface CommunityConfigResponse {
  provider?: string;
  serverURL?: string;
  server_url?: string;
  meta?: Array<"nick" | "mail" | "link">;
  requiredMeta?: Array<"nick" | "mail">;
  required_meta?: Array<"nick" | "mail">;
  loginMode?: "disable" | "enable" | "force";
  login_mode?: "disable" | "enable" | "force";
  commentSorting?: CommunityCommentSort;
  comment_sorting?: CommunityCommentSort;
  oauth_providers?: string[];
  anonymous_enabled?: boolean;
  moderation_mode?: string;
  default_sorting?: CommunityCommentSort;
  enableEnjoySearch?: boolean;
  enable_enjoy_search?: boolean;
  imageUploader?: boolean;
  image_uploader?: boolean;
  emojiPresets?: Array<string | WalineEmojiPreset>;
  emoji_presets?: Array<string | WalineEmojiPreset>;
  enjoySearchEndpoint?: string | null;
  enjoy_search_endpoint?: string | null;
  enjoySearchDefaultWords?: string[];
  enjoy_search_default_words?: string[];
  avatarStrategy?: string | null;
  avatar_strategy?: string | null;
  avatarLibraryEnabled?: boolean;
  avatar_library_enabled?: boolean;
  avatarLibrary?: CommentAvatarPreset[];
  avatar_library?: CommentAvatarPreset[];
  anonymousAvatarLibrary?: CommentAvatarPreset[];
  anonymous_avatar_library?: CommentAvatarPreset[];
  avatar_presets?: CommentAvatarPreset[];
  guest_avatar_mode?: string;
  draft_enabled?: boolean;
  helperCopy?: string | null;
  helper_copy?: string | null;
  avatar_helper_copy?: string | null;
  pageSize?: number | null;
  page_size?: number | null;
  lang?: string | null;
  darkSelector?: string | null;
  dark_selector?: string | null;
}

export type WalineRuntimeOptions = {
  serverURL: string;
  path: string;
  dark: string;
  meta: Array<"nick" | "mail" | "link">;
  requiredMeta: Array<"nick" | "mail">;
  login: "disable" | "enable" | "force";
  imageUploader: boolean;
  emoji: Array<string | WalineEmojiPreset>;
  search: WalineSearchOptions | false;
  lang?: string;
  pageSize?: number;
  commentSorting?: CommunityCommentSort;
};

export const communityConfigPath = "/api/v1/public/community-config";

export const DEFAULT_WALINE_EMOJI: Array<string> = [
  "https://unpkg.com/@waline/emojis@1.1.0/weibo",
  "https://unpkg.com/@waline/emojis@1.1.0/qq",
  "https://unpkg.com/@waline/emojis@1.1.0/tieba",
  "https://unpkg.com/@waline/emojis@1.1.0/bilibili",
  "https://unpkg.com/@waline/emojis@1.1.0/tw-emoji",
  "https://unpkg.com/@waline/emojis@1.1.0/alus",
  "https://unpkg.com/@waline/emojis@1.1.0/bmoji",
];

const DEFAULT_WALINE_COMMUNITY_CONFIG: CommunityConfig = {
  provider: "waline",
  serverURL: (import.meta.env.VITE_WALINE_SERVER_URL ?? "").trim(),
  meta: ["nick", "mail"],
  requiredMeta: ["nick"],
  loginMode: "disable",
  commentSorting: "latest",
  enableEnjoySearch: true,
  imageUploader: false,
  emojiPresets: DEFAULT_WALINE_EMOJI,
  enjoySearchEndpoint: (import.meta.env.VITE_WALINE_ENJOY_SEARCH_URL ?? "").trim() || null,
  enjoySearchDefaultWords: ["enjoy", "yoyo", "hehe"],
  avatarStrategy: null,
  avatarLibraryEnabled: true,
  avatarLibrary: [],
  helperCopy: null,
  pageSize: 10,
  lang: "zh-CN",
  darkSelector: "html.dark",
};

export const DEFAULT_COMMENT_AVATAR_LIBRARY: CommentAvatarPreset[] = [
  {
    id: "mist-blue",
    label: "雾蓝",
    note: "清冷、安静、适合匿名留言",
    accent: "#5f8dd3",
    src:
      "data:image/svg+xml;charset=UTF-8," +
      encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" fill="none"><rect width="96" height="96" rx="28" fill="#0f172a"/><circle cx="48" cy="48" r="28" fill="#5f8dd3"/><circle cx="36" cy="40" r="6" fill="#eff6ff"/><circle cx="60" cy="40" r="6" fill="#eff6ff"/><path d="M34 58c4.8 5.4 10.3 8.1 14 8.1S57.2 63.4 62 58" stroke="#eff6ff" stroke-width="5" stroke-linecap="round"/></svg>`,
      ),
  },
  {
    id: "amber-glow",
    label: "晨橘",
    note: "更热烈一点的默认头像",
    accent: "#f59e0b",
    src:
      "data:image/svg+xml;charset=UTF-8," +
      encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" fill="none"><rect width="96" height="96" rx="28" fill="#1f1305"/><circle cx="48" cy="48" r="28" fill="#f59e0b"/><path d="M29 62C34 48 39 42 48 42s14 6 19 20" stroke="#fff7ed" stroke-width="5" stroke-linecap="round"/><circle cx="38" cy="38" r="5" fill="#fff7ed"/><circle cx="58" cy="38" r="5" fill="#fff7ed"/></svg>`,
      ),
  },
  {
    id: "mint-line",
    label: "薄荷",
    note: "清爽、干净、偏极简",
    accent: "#34d399",
    src:
      "data:image/svg+xml;charset=UTF-8," +
      encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" fill="none"><rect width="96" height="96" rx="28" fill="#04160f"/><circle cx="48" cy="48" r="28" fill="#34d399"/><path d="M34 56c6-14 8-22 14-22s8 8 14 22" stroke="#f0fdf4" stroke-width="5" stroke-linecap="round"/><circle cx="40" cy="38" r="4" fill="#f0fdf4"/><circle cx="56" cy="38" r="4" fill="#f0fdf4"/></svg>`,
      ),
  },
  {
    id: "graphite",
    label: "石墨",
    note: "更稳重的中性选择",
    accent: "#64748b",
    src:
      "data:image/svg+xml;charset=UTF-8," +
      encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" fill="none"><rect width="96" height="96" rx="28" fill="#111827"/><circle cx="48" cy="48" r="28" fill="#64748b"/><path d="M31 59h34" stroke="#f8fafc" stroke-width="5" stroke-linecap="round"/><path d="M35 37h26" stroke="#f8fafc" stroke-width="5" stroke-linecap="round"/><path d="M38 45h20" stroke="#f8fafc" stroke-width="5" stroke-linecap="round"/></svg>`,
      ),
  },
  {
    id: "violet-spark",
    label: "暮紫",
    note: "更有一点情绪和温度",
    accent: "#a855f7",
    src:
      "data:image/svg+xml;charset=UTF-8," +
      encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" fill="none"><rect width="96" height="96" rx="28" fill="#1e102b"/><circle cx="48" cy="48" r="28" fill="#a855f7"/><path d="M48 28l4 12h12l-10 7 4 12-10-7-10 7 4-12-10-7h12z" fill="#f5f3ff"/></svg>`,
      ),
  },
  {
    id: "sunset-rose",
    label: "落霞",
    note: "带一点柔和的记忆感",
    accent: "#fb7185",
    src:
      "data:image/svg+xml;charset=UTF-8," +
      encodeURIComponent(
        `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 96 96" fill="none"><rect width="96" height="96" rx="28" fill="#2b0f16"/><circle cx="48" cy="48" r="28" fill="#fb7185"/><circle cx="48" cy="45" r="14" fill="#fff1f2"/><path d="M35 63c5-5 9-7 13-7s8 2 13 7" stroke="#fff1f2" stroke-width="5" stroke-linecap="round"/></svg>`,
      ),
  },
];

DEFAULT_WALINE_COMMUNITY_CONFIG.avatarLibrary = DEFAULT_COMMENT_AVATAR_LIBRARY;

const sortLabelMap: Record<CommunityCommentSort, string> = {
  latest: "最新优先",
  oldest: "最早优先",
  hottest: "最热优先",
};

const normalizeAvatarLibrary = (payload: unknown): CommentAvatarPreset[] => {
  if (!Array.isArray(payload)) {
    return DEFAULT_COMMENT_AVATAR_LIBRARY;
  }

  const items = payload
    .map((item, index) => {
      if (!item || typeof item !== "object") {
        return null;
      }
      const record = item as Record<string, unknown>;
      const src =
        typeof record.src === "string"
          ? record.src.trim()
          : typeof record.avatar_url === "string"
            ? record.avatar_url.trim()
            : "";
      if (!src) {
        return null;
      }
      const label =
        typeof record.label === "string" && record.label.trim()
          ? record.label.trim()
          : typeof record.name === "string" && record.name.trim()
            ? record.name.trim()
            : `头像 ${index + 1}`;
      return {
        id:
          typeof record.id === "string" && record.id.trim()
            ? record.id.trim()
            : typeof record.key === "string" && record.key.trim()
              ? record.key.trim()
              : `${label}-${index + 1}`,
        label,
        src,
        note: typeof record.note === "string" ? record.note : undefined,
        accent: typeof record.accent === "string" ? record.accent : undefined,
      } satisfies CommentAvatarPreset;
    })
    .filter((item): item is CommentAvatarPreset => item !== null);

  return items.length ? items : DEFAULT_COMMENT_AVATAR_LIBRARY;
};

const normalizeCommentSorting = (value: unknown): CommunityCommentSort => {
  return value === "oldest" || value === "hottest" ? value : "latest";
};

const normalizeScopeKey = (surface: CommunitySurface, slug?: string) => `${surface}:${(slug ?? "guestbook").trim() || "guestbook"}`;

export const buildCommentSortLabel = (sort: CommunityCommentSort) => sortLabelMap[sort];

export const buildCommentFeaturePills = (
  config: CommunityConfig,
  sort: CommunityCommentSort,
  avatarLabel?: string | null,
): CommentFeaturePill[] => {
  const requiredMeta = config.requiredMeta.length ? config.requiredMeta.join(" / ") : "昵称";
  const loginLabel =
    config.loginMode === "force"
      ? "登录必需"
      : config.loginMode === "enable"
        ? "匿名 / 登录"
        : "匿名优先";

  return [
    {
      key: "meta",
      label: `${requiredMeta}必填`,
      tone: "positive",
    },
    {
      key: "login",
      label: loginLabel,
      tone: config.loginMode === "force" ? "warning" : "default",
    },
    {
      key: "sort",
      label: buildCommentSortLabel(sort),
      tone: "accent",
    },
    {
      key: "search",
      label: config.enableEnjoySearch ? "Enjoy 搜索" : "无 Enjoy 搜索",
      tone: config.enableEnjoySearch ? "positive" : "muted",
    },
    {
      key: "upload",
      label: config.imageUploader ? "图片上传" : "图片上传关闭",
      tone: config.imageUploader ? "default" : "muted",
    },
    {
      key: "avatar",
      label: avatarLabel ? `匿名头像 · ${avatarLabel}` : config.avatarLibraryEnabled ? "匿名头像库" : "默认头像",
      tone: avatarLabel ? "accent" : config.avatarLibraryEnabled ? "positive" : "muted",
    },
  ];
};

export const getCommentDraftStorageKey = (surface: CommunitySurface, slug?: string) =>
  `aerisun:community:${normalizeScopeKey(surface, slug)}:draft`;

export const getCommentSortStorageKey = (surface: CommunitySurface, slug?: string) =>
  `aerisun:community:${normalizeScopeKey(surface, slug)}:sort`;

export const getCommentAvatarStorageKey = (surface: CommunitySurface, slug?: string) =>
  `aerisun:community:${normalizeScopeKey(surface, slug)}:avatar`;

export const getCommentFeatureStorageKey = (surface: CommunitySurface, slug?: string) =>
  `aerisun:community:${normalizeScopeKey(surface, slug)}:feature`;

export const resolveCommentAvatarPreset = (
  library: CommentAvatarPreset[] | null | undefined,
  avatarId: string | null | undefined,
) => {
  const presets = library?.length ? library : DEFAULT_COMMENT_AVATAR_LIBRARY;
  return presets.find((item) => item.id === avatarId) ?? presets[0] ?? null;
};

export const buildWalineSurfacePath = (surface: CommunitySurface, slug?: string) => {
  if (surface === "guestbook") {
    return "/guestbook";
  }

  if (!slug) {
    throw new Error(`Waline surface "${surface}" requires a slug`);
  }

  return `/${surface}/${slug}`;
};

export const normalizeWalineSearchResult = (payload: unknown): WalineSearchImage[] => {
  if (Array.isArray(payload)) {
    return payload
      .map((item) => {
        if (!item || typeof item !== "object") return null;
        const record = item as Record<string, unknown>;
        const src = String(record.src ?? record.url ?? record.image ?? "");
        if (!src) return null;
        const title = record.title ?? record.alt ?? record.name;
        const preview = record.preview ?? record.thumbnail ?? record.thumb;
        return {
          src,
          title: typeof title === "string" ? title : undefined,
          preview: typeof preview === "string" ? preview : undefined,
        };
      })
      .filter((item): item is WalineSearchImage => item !== null);
  }

  if (!payload || typeof payload !== "object") {
    return [];
  }

  const record = payload as Record<string, unknown>;
  for (const candidate of [record.items, record.results, record.data, record.list, record.images]) {
    if (Array.isArray(candidate)) {
      return normalizeWalineSearchResult(candidate);
    }
  }

  return [];
};

const createSearchEndpoint = (endpoint: string, fallbackWords: string[]) => {
  const buildUrl = (word: string, page: number) => {
    const url = new URL(endpoint, window.location.origin);
    url.searchParams.set("q", word);
    url.searchParams.set("page", String(page));
    url.searchParams.set("pageSize", "20");
    return url;
  };

  const search = async (word: string) => {
    const response = await fetch(buildUrl(word, 1));
    if (!response.ok) {
      return [];
    }
    const payload = await response.json();
    return normalizeWalineSearchResult(payload);
  };

  return {
    search,
    default: async () => {
      for (const word of fallbackWords) {
        const results = await search(word);
        if (results.length) return results;
      }
      return [];
    },
    more: async (word: string, currentCount: number) => {
      const page = Math.floor(currentCount / 20) + 1;
      const response = await fetch(buildUrl(word, page));
      if (!response.ok) {
        return [];
      }
      const payload = await response.json();
      return normalizeWalineSearchResult(payload);
    },
  } satisfies WalineSearchOptions;
};

export const normalizeCommunityConfig = (payload: unknown): CommunityConfig => {
  if (!payload || typeof payload !== "object") {
    return DEFAULT_WALINE_COMMUNITY_CONFIG;
  }

  const record = payload as CommunityConfigResponse;
  const serverURL = String(record.serverURL ?? record.server_url ?? DEFAULT_WALINE_COMMUNITY_CONFIG.serverURL).trim();
  const meta = record.meta ?? DEFAULT_WALINE_COMMUNITY_CONFIG.meta;
  const requiredMeta = record.requiredMeta ?? record.required_meta ?? DEFAULT_WALINE_COMMUNITY_CONFIG.requiredMeta;
  const loginMode = record.loginMode ?? record.login_mode ?? DEFAULT_WALINE_COMMUNITY_CONFIG.loginMode;
  const commentSorting = normalizeCommentSorting(
    record.commentSorting ?? record.comment_sorting ?? record.default_sorting,
  );
  const enableEnjoySearch =
    record.enableEnjoySearch ?? record.enable_enjoy_search ?? DEFAULT_WALINE_COMMUNITY_CONFIG.enableEnjoySearch;
  const imageUploader = record.imageUploader ?? record.image_uploader ?? DEFAULT_WALINE_COMMUNITY_CONFIG.imageUploader;
  const emojiPresets = record.emojiPresets ?? record.emoji_presets ?? DEFAULT_WALINE_COMMUNITY_CONFIG.emojiPresets;
  const enjoySearchEndpoint =
    record.enjoySearchEndpoint ?? record.enjoy_search_endpoint ?? DEFAULT_WALINE_COMMUNITY_CONFIG.enjoySearchEndpoint;
  const enjoySearchDefaultWords =
    record.enjoySearchDefaultWords ?? record.enjoy_search_default_words ?? DEFAULT_WALINE_COMMUNITY_CONFIG.enjoySearchDefaultWords;
  const guestAvatarMode = record.guest_avatar_mode ?? null;
  const avatarLibraryEnabled =
    record.avatarLibraryEnabled
      ?? record.avatar_library_enabled
      ?? (guestAvatarMode ? guestAvatarMode === "preset" : DEFAULT_WALINE_COMMUNITY_CONFIG.avatarLibraryEnabled);
  const avatarLibrary = normalizeAvatarLibrary(
    record.avatarLibrary
      ?? record.avatar_library
      ?? record.anonymousAvatarLibrary
      ?? record.anonymous_avatar_library
      ?? record.avatar_presets
      ?? DEFAULT_WALINE_COMMUNITY_CONFIG.avatarLibrary,
  );

  return {
    provider: "waline",
    serverURL,
    meta,
    requiredMeta,
    loginMode,
    commentSorting,
    oauthProviders: record.oauth_providers ?? [],
    anonymousEnabled: record.anonymous_enabled,
    moderationMode: record.moderation_mode,
    enableEnjoySearch,
    imageUploader,
    emojiPresets,
    enjoySearchEndpoint,
    enjoySearchDefaultWords,
    avatarStrategy: record.avatarStrategy ?? record.avatar_strategy ?? DEFAULT_WALINE_COMMUNITY_CONFIG.avatarStrategy,
    avatarLibraryEnabled,
    avatarLibrary,
    guestAvatarMode,
    draftEnabled: record.draft_enabled,
    helperCopy:
      record.helperCopy
      ?? record.helper_copy
      ?? record.avatar_helper_copy
      ?? DEFAULT_WALINE_COMMUNITY_CONFIG.helperCopy,
    pageSize: record.pageSize ?? record.page_size ?? DEFAULT_WALINE_COMMUNITY_CONFIG.pageSize,
    lang: record.lang ?? DEFAULT_WALINE_COMMUNITY_CONFIG.lang,
    darkSelector: record.darkSelector ?? record.dark_selector ?? DEFAULT_WALINE_COMMUNITY_CONFIG.darkSelector,
  };
};

export async function loadCommunityConfig(init?: RequestInit): Promise<CommunityConfig> {
  try {
    const payload = await apiClient.get<unknown>(communityConfigPath, init);
    return normalizeCommunityConfig(payload);
  } catch {
    return DEFAULT_WALINE_COMMUNITY_CONFIG;
  }
}

export const buildWalineRuntimeOptions = (
  config: CommunityConfig,
  surface: CommunitySurface,
  slug?: string,
  commentSorting: CommunityCommentSort = config.commentSorting ?? "latest",
): WalineRuntimeOptions => {
  const path = buildWalineSurfacePath(surface, slug);
  const search = config.enableEnjoySearch && config.enjoySearchEndpoint
    ? createSearchEndpoint(config.enjoySearchEndpoint, config.enjoySearchDefaultWords ?? [])
    : false;

  return {
    serverURL: config.serverURL,
    path,
    dark: config.darkSelector ?? "html.dark",
    meta: config.meta,
    requiredMeta: config.requiredMeta,
    login: config.loginMode,
    imageUploader: config.imageUploader,
    emoji: config.emojiPresets,
    search,
    lang: config.lang ?? "zh-CN",
    pageSize: config.pageSize ?? 10,
    commentSorting,
  };
};

export const DEFAULT_COMMUNITY_CONFIG = DEFAULT_WALINE_COMMUNITY_CONFIG;
