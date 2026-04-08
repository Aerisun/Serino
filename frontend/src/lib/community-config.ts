import type {
  AvatarPreset,
  CommunityCommentSort,
  CommunitySurface,
  WalineEmojiPreset,
} from "@serino/types";

export type { AvatarPreset, CommunityCommentSort, CommunitySurface, WalineEmojiPreset };
import { readCommunityConfigApiV1SiteCommunityConfigGet } from "@serino/api-client/site";
import { clampPageSize } from "@/lib/page-size";
import { translateFrontendText } from "@/i18n";

const DEFAULT_IMAGE_MAX_BYTES = 512 * 1024;
const COMMUNITY_CONFIG_CACHE_KEY = "aerisun:community-config";
const COMMUNITY_CONFIG_CACHE_TTL_MS = 15 * 60_000;

export interface CommunitySurfaceConfig {
  key: string;
  label: string;
  path: string;
  enabled: boolean;
}

export interface CommunityConfig {
  provider: "waline";
  server_url: string;
  surfaces: CommunitySurfaceConfig[];
  meta: Array<"nick" | "mail" | "link">;
  required_meta: Array<"nick" | "mail">;
  anonymous_enabled: boolean;
  moderation_mode: string;
  default_sorting: CommunityCommentSort;
  image_uploader: boolean;
  emoji_presets: Array<string | WalineEmojiPreset>;
  avatar_helper_copy: string;
  page_size: number;
  image_max_bytes: number;
  migration_state: string;
}

interface CommunityConfigResponse {
  provider?: string;
  server_url?: string;
  surfaces?: CommunitySurfaceConfig[];
  meta?: Array<"nick" | "mail" | "link">;
  required_meta?: Array<"nick" | "mail">;
  anonymous_enabled?: boolean;
  moderation_mode?: string;
  default_sorting?: CommunityCommentSort;
  image_uploader?: boolean;
  emoji_presets?: Array<string | WalineEmojiPreset>;
  avatar_helper_copy?: string | null;
  page_size?: number | null;
  image_max_bytes?: number | null;
  migration_state?: string;
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

const DEFAULT_WALINE_COMMUNITY_CONFIG: CommunityConfig = {
  provider: "waline",
  server_url: "",
  surfaces: [],
  meta: ["nick", "mail", "link"],
  required_meta: ["nick"],
  anonymous_enabled: true,
  moderation_mode: "all_pending",
  default_sorting: "latest",
  image_uploader: false,
  emoji_presets: DEFAULT_WALINE_EMOJI,
  avatar_helper_copy: translateFrontendText(
    "community.avatarHelperCopy",
    undefined,
    "登录后评论会绑定到当前邮箱或第三方身份，邮箱不会公开显示。",
  ),
  page_size: 10,
  image_max_bytes: DEFAULT_IMAGE_MAX_BYTES,
  migration_state: "not_started",
};

let cachedCommunityConfig: CommunityConfig | null = null;
let cachedCommunityConfigExpiresAt = 0;
let inflightCommunityConfigRequest: Promise<CommunityConfig> | null = null;
const hintedCommunityOrigins = new Set<string>();

const normalizeCommentSorting = (value: unknown): CommunityCommentSort => {
  return value === "oldest" || value === "hottest" ? value : "latest";
};

const WALINE_EMOJI_CDN = "https://unpkg.com/@waline/emojis@1.1.0";
const normalizeModerationMode = (value: unknown): string => {
  const normalized = String(value ?? "").trim().toLowerCase().replace(/-/g, "_");
  if (normalized === "no_review" || normalized === "none" || normalized === "off" || normalized === "disabled") {
    return "no_review";
  }
  return "all_pending";
};

const normalizeBasePath = (value: string, fallback: string) => {
  const trimmed = value.trim();
  const candidate = trimmed || fallback;
  return candidate.replace(/\/+$/, "") || fallback;
};

const WALINE_BASE_PATH = normalizeBasePath(
  typeof __AERISUN_WALINE_BASE_PATH__ === "string" ? __AERISUN_WALINE_BASE_PATH__ : "",
  "/waline",
);

const EMOJI_PRESET_ALIAS: Record<string, string> = {
  twemoji: "tw-emoji",
};

const normalizeEmojiPreset = (preset: string | WalineEmojiPreset): string | WalineEmojiPreset => {
  if (typeof preset !== "string") return preset;
  if (/^https?:\/\//.test(preset)) return preset;
  const dir = EMOJI_PRESET_ALIAS[preset] ?? preset;
  return `${WALINE_EMOJI_CDN}/${dir}`;
};

const normalizeServerURL = (raw: string): string => {
  const trimmed = raw.trim();
  if (!trimmed) return `${window.location.origin}${WALINE_BASE_PATH}`;
  if (trimmed.startsWith("/")) return `${window.location.origin}${trimmed}`;
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

const appendConnectionHint = (rel: "dns-prefetch" | "preconnect", href: string) => {
  if (typeof document === "undefined") {
    return;
  }

  const exists = document.head.querySelector(`link[rel="${rel}"][href="${href}"]`);
  if (exists) {
    return;
  }

  const link = document.createElement("link");
  link.rel = rel;
  link.href = href;
  if (rel === "preconnect") {
    link.crossOrigin = "anonymous";
  }
  document.head.appendChild(link);
};

const hintCommunityOrigin = (value: string) => {
  if (typeof window === "undefined") {
    return;
  }

  try {
    const parsed = new URL(value, window.location.origin);
    if (parsed.origin === window.location.origin || hintedCommunityOrigins.has(parsed.origin)) {
      return;
    }

    hintedCommunityOrigins.add(parsed.origin);
    appendConnectionHint("dns-prefetch", parsed.origin);
    appendConnectionHint("preconnect", parsed.origin);
  } catch {
    // Ignore malformed hint URLs.
  }
};

const hintCommunityConnections = (config: CommunityConfig) => {
  hintCommunityOrigin(config.server_url);
  for (const preset of config.emoji_presets) {
    if (typeof preset === "string") {
      hintCommunityOrigin(preset);
    }
  }
};

const normalizeCommunityConfig = (payload: unknown): CommunityConfig => {
  if (!payload || typeof payload !== "object") {
    return DEFAULT_WALINE_COMMUNITY_CONFIG;
  }

  const record = payload as CommunityConfigResponse;
  const meta: Array<"nick" | "mail" | "link"> = record.meta ?? DEFAULT_WALINE_COMMUNITY_CONFIG.meta;
  if (!meta.includes("link")) {
    meta.push("link");
  }

  return {
    provider: "waline",
    server_url: normalizeServerURL(String(record.server_url ?? "")),
    surfaces: record.surfaces ?? DEFAULT_WALINE_COMMUNITY_CONFIG.surfaces,
    meta,
    required_meta: record.required_meta ?? DEFAULT_WALINE_COMMUNITY_CONFIG.required_meta,
    anonymous_enabled: record.anonymous_enabled ?? DEFAULT_WALINE_COMMUNITY_CONFIG.anonymous_enabled,
    moderation_mode: normalizeModerationMode(record.moderation_mode),
    default_sorting: normalizeCommentSorting(record.default_sorting),
    image_uploader: record.image_uploader ?? DEFAULT_WALINE_COMMUNITY_CONFIG.image_uploader,
    emoji_presets: (record.emoji_presets ?? DEFAULT_WALINE_COMMUNITY_CONFIG.emoji_presets).map(normalizeEmojiPreset),
    avatar_helper_copy: record.avatar_helper_copy ?? DEFAULT_WALINE_COMMUNITY_CONFIG.avatar_helper_copy,
    page_size: clampPageSize(record.page_size, DEFAULT_WALINE_COMMUNITY_CONFIG.page_size),
    image_max_bytes: record.image_max_bytes ?? DEFAULT_WALINE_COMMUNITY_CONFIG.image_max_bytes,
    migration_state: record.migration_state ?? DEFAULT_WALINE_COMMUNITY_CONFIG.migration_state,
  };
};

const readStoredCommunityConfig = () => {
  const now = Date.now();
  if (cachedCommunityConfig && cachedCommunityConfigExpiresAt > now) {
    return cachedCommunityConfig;
  }

  cachedCommunityConfig = null;
  cachedCommunityConfigExpiresAt = 0;

  if (typeof sessionStorage === "undefined") {
    return null;
  }

  try {
    const raw = sessionStorage.getItem(COMMUNITY_CONFIG_CACHE_KEY);
    if (!raw) {
      return null;
    }

    const parsed = JSON.parse(raw) as { expiresAt?: number; value?: CommunityConfig };
    if (!parsed || typeof parsed.expiresAt !== "number" || !parsed.value) {
      sessionStorage.removeItem(COMMUNITY_CONFIG_CACHE_KEY);
      return null;
    }

    if (parsed.expiresAt <= now) {
      sessionStorage.removeItem(COMMUNITY_CONFIG_CACHE_KEY);
      return null;
    }

    cachedCommunityConfig = parsed.value;
    cachedCommunityConfigExpiresAt = parsed.expiresAt;
    return parsed.value;
  } catch {
    try {
      sessionStorage.removeItem(COMMUNITY_CONFIG_CACHE_KEY);
    } catch {
      // Ignore storage failures.
    }
    return null;
  }
};

const writeStoredCommunityConfig = (value: CommunityConfig) => {
  const expiresAt = Date.now() + COMMUNITY_CONFIG_CACHE_TTL_MS;
  cachedCommunityConfig = value;
  cachedCommunityConfigExpiresAt = expiresAt;

  if (typeof sessionStorage === "undefined") {
    return;
  }

  try {
    sessionStorage.setItem(
      COMMUNITY_CONFIG_CACHE_KEY,
      JSON.stringify({ expiresAt, value }),
    );
  } catch {
    // Ignore storage failures.
  }
};

export async function loadCommunityConfig(init?: RequestInit): Promise<CommunityConfig> {
  const cached = readStoredCommunityConfig();
  if (cached) {
    hintCommunityConnections(cached);
    return cached;
  }

  if (inflightCommunityConfigRequest) {
    return inflightCommunityConfigRequest;
  }

  inflightCommunityConfigRequest = (async () => {
    let nextConfig: CommunityConfig;

    try {
      const response = await readCommunityConfigApiV1SiteCommunityConfigGet(init);
      nextConfig = normalizeCommunityConfig(response.data);
    } catch {
      nextConfig = {
        ...DEFAULT_WALINE_COMMUNITY_CONFIG,
        server_url: normalizeServerURL(""),
      };
    }

    hintCommunityConnections(nextConfig);
    writeStoredCommunityConfig(nextConfig);
    return nextConfig;
  })();

  try {
    return await inflightCommunityConfigRequest;
  } finally {
    inflightCommunityConfigRequest = null;
  }
}

export const DEFAULT_COMMUNITY_CONFIG = DEFAULT_WALINE_COMMUNITY_CONFIG;
