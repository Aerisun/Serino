import type {
  CommunitySurface,
  CommunityCommentSort,
  WalineEmojiPreset,
  AvatarPreset,
} from "@serino/types";

export type { CommunitySurface, CommunityCommentSort, WalineEmojiPreset, AvatarPreset };
import { readCommunityConfigApiV1SiteCommunityConfigGet } from "@serino/api-client/site";
import { clampPageSize } from "@/lib/page-size";

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
  emailLoginEnabled?: boolean;
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

const DEFAULT_AVATAR_PRESETS: AvatarPreset[] = [];

const DEFAULT_WALINE_COMMUNITY_CONFIG: CommunityConfig = {
  provider: "waline",
  serverURL: "", // Will be resolved at runtime via normalizeServerURL
  meta: ["nick", "mail", "link"],
  requiredMeta: ["nick"],
  loginMode: "force",
  commentSorting: "latest",
  emailLoginEnabled: true,
  enableEnjoySearch: true,
  imageUploader: false,
  emojiPresets: DEFAULT_WALINE_EMOJI,
  enjoySearchEndpoint: (import.meta.env.VITE_WALINE_ENJOY_SEARCH_URL ?? "").trim() || null,
  enjoySearchDefaultWords: ["enjoy", "yoyo", "hehe"],
  avatarStrategy: null,
  avatarPresets: DEFAULT_AVATAR_PRESETS,
  helperCopy: "登录后评论会绑定到当前邮箱或第三方身份，邮箱不会公开显示。",
  pageSize: 10,
  imageMaxBytes: DEFAULT_IMAGE_MAX_BYTES,
  lang: "zh-CN",
  darkSelector: "html.dark",
};

const normalizeCommentSorting = (value: unknown): CommunityCommentSort => {
  return value === "oldest" || value === "hottest" ? value : "latest";
};

const WALINE_EMOJI_CDN = "https://unpkg.com/@waline/emojis@1.1.0";
const normalizeBasePath = (value: string, fallback: string) => {
  const trimmed = value.trim();
  const candidate = trimmed || fallback;
  return candidate.replace(/\/+$/, "") || fallback;
};

const WALINE_BASE_PATH = normalizeBasePath(
  typeof __AERISUN_WALINE_BASE_PATH__ === "string" ? __AERISUN_WALINE_BASE_PATH__ : "",
  "/waline",
);

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
 * the browser must use a same-origin path (WALINE_BASE_PATH) so the Vite dev proxy
 * or Caddy reverse-proxy can forward requests without CORS issues.
 *
 * Waline client uses `new URL(path, serverURL)` internally, so the serverURL
 * must be a full origin — we build it from the current page location.
 */
const normalizeServerURL = (raw: string): string => {
  const trimmed = raw.trim();
  if (!trimmed) return `${window.location.origin}${WALINE_BASE_PATH}`;
  // Already a relative path — prepend current origin
  if (trimmed.startsWith("/")) return `${window.location.origin}${trimmed}`;
  // Absolute URL pointing to a different port/host — use proxy path
  try {
    const parsed = new URL(trimmed);
    if (parsed.origin !== window.location.origin) {
      return `${window.location.origin}${WALINE_BASE_PATH}`;
    }
    return trimmed;
  } catch {
    return `${window.location.origin}${WALINE_BASE_PATH}`;
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
  const loginMode: CommunityConfig["loginMode"] = "force";
  const commentSorting = normalizeCommentSorting(
    record.commentSorting ?? record.comment_sorting ?? record.default_sorting,
  );
  const enableEnjoySearch =
    record.enableEnjoySearch ?? record.enable_enjoy_search ?? DEFAULT_WALINE_COMMUNITY_CONFIG.enableEnjoySearch;
  const imageUploader = record.imageUploader ?? record.image_uploader ?? DEFAULT_WALINE_COMMUNITY_CONFIG.imageUploader;
  const emailLoginEnabled = record.anonymous_enabled ?? DEFAULT_WALINE_COMMUNITY_CONFIG.emailLoginEnabled;
  const rawEmoji = record.emojiPresets ?? record.emoji_presets ?? DEFAULT_WALINE_COMMUNITY_CONFIG.emojiPresets;
  const emojiPresets = rawEmoji.map(normalizeEmojiPreset);
  const enjoySearchEndpoint =
    enableEnjoySearch
      ? (record.enjoySearchEndpoint ?? record.enjoy_search_endpoint ?? DEFAULT_WALINE_COMMUNITY_CONFIG.enjoySearchEndpoint)
      : null;
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
    emailLoginEnabled,
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
    pageSize: clampPageSize(
      record.pageSize ?? record.page_size,
      DEFAULT_WALINE_COMMUNITY_CONFIG.pageSize ?? 10,
    ),
    imageMaxBytes: record.imageMaxBytes ?? record.image_max_bytes ?? DEFAULT_WALINE_COMMUNITY_CONFIG.imageMaxBytes,
    lang: record.lang ?? DEFAULT_WALINE_COMMUNITY_CONFIG.lang,
    darkSelector: record.darkSelector ?? record.dark_selector ?? DEFAULT_WALINE_COMMUNITY_CONFIG.darkSelector,
  };
};

export async function loadCommunityConfig(init?: RequestInit): Promise<CommunityConfig> {
  try {
    const response = await readCommunityConfigApiV1SiteCommunityConfigGet(init);
    return normalizeCommunityConfig(response.data);
  } catch {
    return {
      ...DEFAULT_WALINE_COMMUNITY_CONFIG,
      serverURL: normalizeServerURL(""),
    };
  }
}

export const DEFAULT_COMMUNITY_CONFIG = DEFAULT_WALINE_COMMUNITY_CONFIG;
