import type {
  CommunitySurface,
  CommunityCommentSort,
  WalineEmojiPreset,
  AvatarPreset,
} from "@serino/types";

export type { CommunitySurface, CommunityCommentSort, WalineEmojiPreset, AvatarPreset };
import { readCommunityConfigApiV1PublicCommunityConfigGet } from "@serino/api-client/public";

/** Default max image size in bytes before compression kicks in (512 KB) */
const DEFAULT_IMAGE_MAX_BYTES = 512 * 1024;

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
  avatarPresets?: AvatarPreset[];
  helperCopy?: string | null;
  pageSize?: number | null;
  imageMaxBytes?: number | null;
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
  helperCopy?: string | null;
  helper_copy?: string | null;
  avatar_helper_copy?: string | null;
  avatar_presets?: AvatarPreset[];
  pageSize?: number | null;
  page_size?: number | null;
  imageMaxBytes?: number | null;
  image_max_bytes?: number | null;
  lang?: string | null;
  darkSelector?: string | null;
  dark_selector?: string | null;
}

const DEFAULT_WALINE_EMOJI: Array<string> = [
  "https://unpkg.com/@waline/emojis@1.1.0/weibo",
  "https://unpkg.com/@waline/emojis@1.1.0/qq",
  "https://unpkg.com/@waline/emojis@1.1.0/tieba",
  "https://unpkg.com/@waline/emojis@1.1.0/bilibili",
  "https://unpkg.com/@waline/emojis@1.1.0/tw-emoji",
  "https://unpkg.com/@waline/emojis@1.1.0/alus",
  "https://unpkg.com/@waline/emojis@1.1.0/bmoji",
];

const DEFAULT_AVATAR_PRESETS: AvatarPreset[] = [
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

const DEFAULT_WALINE_COMMUNITY_CONFIG: CommunityConfig = {
  provider: "waline",
  serverURL: "", // Will be resolved at runtime via normalizeServerURL
  meta: ["nick", "mail", "link"],
  requiredMeta: ["nick"],
  loginMode: "enable",
  commentSorting: "latest",
  enableEnjoySearch: true,
  imageUploader: false,
  emojiPresets: DEFAULT_WALINE_EMOJI,
  enjoySearchEndpoint: (import.meta.env.VITE_WALINE_ENJOY_SEARCH_URL ?? "").trim() || null,
  enjoySearchDefaultWords: ["enjoy", "yoyo", "hehe"],
  avatarStrategy: null,
  avatarPresets: DEFAULT_AVATAR_PRESETS,
  helperCopy: null,
  pageSize: 10,
  imageMaxBytes: DEFAULT_IMAGE_MAX_BYTES,
  lang: "zh-CN",
  darkSelector: "html.dark",
};

const normalizeCommentSorting = (value: unknown): CommunityCommentSort => {
  return value === "oldest" || value === "hottest" ? value : "latest";
};

const WALINE_EMOJI_CDN = "https://unpkg.com/@waline/emojis@1.1.0";

/** Backend preset names that differ from CDN directory names */
const EMOJI_PRESET_ALIAS: Record<string, string> = {
  twemoji: "tw-emoji",
};

/**
 * If the backend returns a bare preset name (e.g. "twemoji"), expand it to
 * the full CDN URL that @waline/client expects.
 */
const normalizeEmojiPreset = (preset: string | WalineEmojiPreset): string | WalineEmojiPreset => {
  if (typeof preset !== "string") return preset;
  if (/^https?:\/\//.test(preset)) return preset;
  const dir = EMOJI_PRESET_ALIAS[preset] ?? preset;
  return `${WALINE_EMOJI_CDN}/${dir}`;
};

/**
 * The backend stores the Waline origin (e.g. "http://localhost:8360") but
 * the browser must use a same-origin path ("/waline") so the Vite dev proxy
 * or Caddy reverse-proxy can forward requests without CORS issues.
 *
 * Waline client uses `new URL(path, serverURL)` internally, so the serverURL
 * must be a full origin — we build it from the current page location.
 */
const normalizeServerURL = (raw: string): string => {
  const trimmed = raw.trim();
  if (!trimmed) return `${window.location.origin}/waline`;
  // Already a relative path — prepend current origin
  if (trimmed.startsWith("/")) return `${window.location.origin}${trimmed}`;
  // Absolute URL pointing to a different port/host — use proxy path
  try {
    const parsed = new URL(trimmed);
    if (parsed.origin !== window.location.origin) {
      return `${window.location.origin}/waline`;
    }
    return trimmed;
  } catch {
    return `${window.location.origin}/waline`;
  }
};

const normalizeCommunityConfig = (payload: unknown): CommunityConfig => {
  if (!payload || typeof payload !== "object") {
    return DEFAULT_WALINE_COMMUNITY_CONFIG;
  }

  const record = payload as CommunityConfigResponse;
  const serverURL = normalizeServerURL(
    String(record.serverURL ?? record.server_url ?? ""),
  );
  const meta: Array<"nick" | "mail" | "link"> = record.meta ?? DEFAULT_WALINE_COMMUNITY_CONFIG.meta;
  // Ensure "link" is always present so the Website field shows
  if (!meta.includes("link")) meta.push("link");
  const requiredMeta = record.requiredMeta ?? record.required_meta ?? DEFAULT_WALINE_COMMUNITY_CONFIG.requiredMeta;
  // "disable" hides the login button AND part of the meta input UI in Waline.
  // We always want at least "enable" so guest nick/mail/link fields render.
  const rawLogin = record.loginMode ?? record.login_mode ?? DEFAULT_WALINE_COMMUNITY_CONFIG.loginMode;
  const loginMode = rawLogin === "disable" ? "enable" : rawLogin;
  const commentSorting = normalizeCommentSorting(
    record.commentSorting ?? record.comment_sorting ?? record.default_sorting,
  );
  const enableEnjoySearch =
    record.enableEnjoySearch ?? record.enable_enjoy_search ?? DEFAULT_WALINE_COMMUNITY_CONFIG.enableEnjoySearch;
  const imageUploader = record.imageUploader ?? record.image_uploader ?? DEFAULT_WALINE_COMMUNITY_CONFIG.imageUploader;
  const rawEmoji = record.emojiPresets ?? record.emoji_presets ?? DEFAULT_WALINE_COMMUNITY_CONFIG.emojiPresets;
  const emojiPresets = rawEmoji.map(normalizeEmojiPreset);
  const enjoySearchEndpoint =
    record.enjoySearchEndpoint ?? record.enjoy_search_endpoint ?? DEFAULT_WALINE_COMMUNITY_CONFIG.enjoySearchEndpoint;
  const enjoySearchDefaultWords =
    record.enjoySearchDefaultWords ?? record.enjoy_search_default_words ?? DEFAULT_WALINE_COMMUNITY_CONFIG.enjoySearchDefaultWords;

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
    avatarPresets: record.avatar_presets ?? DEFAULT_AVATAR_PRESETS,
    helperCopy:
      record.helperCopy
      ?? record.helper_copy
      ?? record.avatar_helper_copy
      ?? DEFAULT_WALINE_COMMUNITY_CONFIG.helperCopy,
    pageSize: record.pageSize ?? record.page_size ?? DEFAULT_WALINE_COMMUNITY_CONFIG.pageSize,
    imageMaxBytes: record.imageMaxBytes ?? record.image_max_bytes ?? DEFAULT_WALINE_COMMUNITY_CONFIG.imageMaxBytes,
    lang: record.lang ?? DEFAULT_WALINE_COMMUNITY_CONFIG.lang,
    darkSelector: record.darkSelector ?? record.dark_selector ?? DEFAULT_WALINE_COMMUNITY_CONFIG.darkSelector,
  };
};

export async function loadCommunityConfig(init?: RequestInit): Promise<CommunityConfig> {
  try {
    const response = await readCommunityConfigApiV1PublicCommunityConfigGet(init);
    return normalizeCommunityConfig(response.data);
  } catch {
    return {
      ...DEFAULT_WALINE_COMMUNITY_CONFIG,
      serverURL: normalizeServerURL(""),
    };
  }
}

export const DEFAULT_COMMUNITY_CONFIG = DEFAULT_WALINE_COMMUNITY_CONFIG;
