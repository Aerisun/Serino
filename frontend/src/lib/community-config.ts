import { apiClient } from "@/lib/api";

/** Default max image size in bytes before compression kicks in (512 KB) */
const DEFAULT_IMAGE_MAX_BYTES = 512 * 1024;

export type CommunitySurface = "posts" | "diary" | "guestbook" | "thoughts" | "excerpts";
export type CommunityCommentSort = "latest" | "oldest" | "hottest";

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

export interface AvatarPreset {
  key: string;
  label: string;
  avatar_url: string;
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

export type WalineRuntimeOptions = {
  serverURL: string;
  path: string;
  dark: string;
  meta: Array<"nick" | "mail" | "link">;
  requiredMeta: Array<"nick" | "mail">;
  login: "disable" | "enable" | "force";
  imageUploader: (image: File) => Promise<string>;
  emoji: Array<string | WalineEmojiPreset>;
  search: WalineSearchOptions | boolean;
  reaction: string[] | boolean;
  pageview: boolean;
  comment: boolean;
  locale?: Record<string, string>;
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
  helperCopy: null,
  pageSize: 10,
  imageMaxBytes: DEFAULT_IMAGE_MAX_BYTES,
  lang: "zh-CN",
  darkSelector: "html.dark",
};

const normalizeCommentSorting = (value: unknown): CommunityCommentSort => {
  return value === "oldest" || value === "hottest" ? value : "latest";
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
          ...(typeof title === "string" ? { title } : {}),
          ...(typeof preview === "string" ? { preview } : {}),
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

export const normalizeCommunityConfig = (payload: unknown): CommunityConfig => {
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
    avatarPresets: record.avatar_presets ?? [],
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
    const payload = await apiClient.get<unknown>(communityConfigPath, init);
    return normalizeCommunityConfig(payload);
  } catch {
    return {
      ...DEFAULT_WALINE_COMMUNITY_CONFIG,
      serverURL: normalizeServerURL(""),
    };
  }
}

/** Max pixel dimension (width or height) */
const IMAGE_MAX_DIM = 1920;

/**
 * Compress an image File via Canvas.  Returns the original if it's already
 * small enough or if it's not a raster format (SVG, etc.).
 */
const compressImage = (file: File, maxBytes: number): Promise<File> => {
  if (file.size <= maxBytes) return Promise.resolve(file);
  if (!file.type.startsWith("image/") || file.type === "image/svg+xml") return Promise.resolve(file);

  const targetBytes = Math.floor(maxBytes * 0.94); // leave headroom

  return new Promise((resolve) => {
    const img = new Image();
    img.onload = () => {
      URL.revokeObjectURL(img.src);
      let { width, height } = img;

      // Scale down if either dimension exceeds the cap
      if (width > IMAGE_MAX_DIM || height > IMAGE_MAX_DIM) {
        const ratio = Math.min(IMAGE_MAX_DIM / width, IMAGE_MAX_DIM / height);
        width = Math.round(width * ratio);
        height = Math.round(height * ratio);
      }

      const canvas = document.createElement("canvas");
      canvas.width = width;
      canvas.height = height;
      const ctx = canvas.getContext("2d")!;
      ctx.drawImage(img, 0, 0, width, height);

      // Binary-search for a quality that stays under budget
      let lo = 0.3;
      let hi = 0.92;
      const tryQuality = (q: number) =>
        new Promise<Blob | null>((r) => canvas.toBlob((b) => r(b), "image/jpeg", q));

      (async () => {
        let best: Blob | null = null;
        for (let i = 0; i < 5; i++) {
          const mid = (lo + hi) / 2;
          const blob = await tryQuality(mid);
          if (!blob) break;
          best = blob;
          if (blob.size > targetBytes) {
            hi = mid;
          } else {
            lo = mid;
          }
        }
        if (!best) {
          resolve(file);
          return;
        }
        const name = file.name.replace(/\.[^.]+$/, ".jpg");
        resolve(new File([best], name, { type: "image/jpeg" }));
      })();
    };
    img.onerror = () => resolve(file);
    img.src = URL.createObjectURL(file);
  });
};

/**
 * Build a Waline-compatible imageUploader that auto-compresses oversized
 * images before uploading to our backend's comment-image endpoint.
 */
const createImageUploader = (_serverURL: string, maxBytes?: number | null) => {
  const limit = maxBytes ?? DEFAULT_IMAGE_MAX_BYTES;
  return async (image: File): Promise<string> => {
    const compressed = await compressImage(image, limit);
    const form = new FormData();
    form.append("file", compressed);

    const res = await fetch("/api/v1/public/comment-image", {
      method: "POST",
      body: form,
    });

    if (!res.ok) throw new Error(`Upload failed: ${res.status}`);
    const data = await res.json();
    // Waline returns { errno: 0, data: { url: "..." } } on success
    if (data?.errno !== 0) throw new Error(data?.errmsg ?? "Upload error");
    return data.data?.url ?? data.data;
  };
};

export const buildWalineRuntimeOptions = (
  config: CommunityConfig,
  surface: CommunitySurface,
  slug?: string,
  commentSorting: CommunityCommentSort = config.commentSorting ?? "latest",
): WalineRuntimeOptions => {
  const path = buildWalineSurfacePath(surface, slug);
  const search = config.enableEnjoySearch && config.enjoySearchEndpoint
    ? createSearchEndpoint(config.enjoySearchEndpoint, config.enjoySearchDefaultWords ?? [])
    : false; // No GIF search — only emoji presets

  return {
    serverURL: config.serverURL,
    path,
    dark: config.darkSelector ?? "html.dark",
    meta: config.meta,
    requiredMeta: config.requiredMeta,
    login: config.loginMode,
    imageUploader: createImageUploader(config.serverURL, config.imageMaxBytes),
    emoji: config.emojiPresets,
    search,
    reaction: false,
    pageview: true,
    comment: true,
    locale: {
      reaction0: "喜欢",
      placeholder: "昵称必填，邮箱选填（填写可收到回复通知）。支持 Markdown 语法。",
    },
    lang: config.lang ?? "zh-CN",
    pageSize: config.pageSize ?? 10,
    commentSorting,
  };
};

export const DEFAULT_COMMUNITY_CONFIG = DEFAULT_WALINE_COMMUNITY_CONFIG;
