import { apiClient } from "@/lib/api";

export type CommunitySurface = "posts" | "diary" | "guestbook";

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
  enableEnjoySearch: boolean;
  imageUploader: boolean;
  emojiPresets: Array<string | WalineEmojiPreset>;
  enjoySearchEndpoint?: string | null;
  enjoySearchDefaultWords?: string[];
  avatarStrategy?: string | null;
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
  commentSorting?: "latest" | "oldest" | "hottest";
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
  enableEnjoySearch: true,
  imageUploader: false,
  emojiPresets: DEFAULT_WALINE_EMOJI,
  enjoySearchEndpoint: (import.meta.env.VITE_WALINE_ENJOY_SEARCH_URL ?? "").trim() || null,
  enjoySearchDefaultWords: ["enjoy", "yoyo", "hehe"],
  avatarStrategy: null,
  helperCopy: null,
  pageSize: 10,
  lang: "zh-CN",
  darkSelector: "html.dark",
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
  const enableEnjoySearch =
    record.enableEnjoySearch ?? record.enable_enjoy_search ?? DEFAULT_WALINE_COMMUNITY_CONFIG.enableEnjoySearch;
  const imageUploader = record.imageUploader ?? record.image_uploader ?? DEFAULT_WALINE_COMMUNITY_CONFIG.imageUploader;
  const emojiPresets = record.emojiPresets ?? record.emoji_presets ?? DEFAULT_WALINE_COMMUNITY_CONFIG.emojiPresets;
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
    enableEnjoySearch,
    imageUploader,
    emojiPresets,
    enjoySearchEndpoint,
    enjoySearchDefaultWords,
    avatarStrategy: record.avatarStrategy ?? record.avatar_strategy ?? DEFAULT_WALINE_COMMUNITY_CONFIG.avatarStrategy,
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

export const buildWalineRuntimeOptions = (config: CommunityConfig, surface: CommunitySurface, slug?: string): WalineRuntimeOptions => {
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
    commentSorting: "latest",
  };
};

export const DEFAULT_COMMUNITY_CONFIG = DEFAULT_WALINE_COMMUNITY_CONFIG;
