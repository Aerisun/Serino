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
  enable_enjoy_search: boolean;
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
  enable_enjoy_search?: boolean;
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
  enable_enjoy_search: true,
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
    enable_enjoy_search: record.enable_enjoy_search ?? DEFAULT_WALINE_COMMUNITY_CONFIG.enable_enjoy_search,
    image_uploader: record.image_uploader ?? DEFAULT_WALINE_COMMUNITY_CONFIG.image_uploader,
    emoji_presets: (record.emoji_presets ?? DEFAULT_WALINE_COMMUNITY_CONFIG.emoji_presets).map(normalizeEmojiPreset),
    avatar_helper_copy: record.avatar_helper_copy ?? DEFAULT_WALINE_COMMUNITY_CONFIG.avatar_helper_copy,
    page_size: clampPageSize(record.page_size, DEFAULT_WALINE_COMMUNITY_CONFIG.page_size),
    image_max_bytes: record.image_max_bytes ?? DEFAULT_WALINE_COMMUNITY_CONFIG.image_max_bytes,
    migration_state: record.migration_state ?? DEFAULT_WALINE_COMMUNITY_CONFIG.migration_state,
  };
};

export async function loadCommunityConfig(init?: RequestInit): Promise<CommunityConfig> {
  try {
    const response = await readCommunityConfigApiV1SiteCommunityConfigGet(init);
    return normalizeCommunityConfig(response.data);
  } catch {
    return {
      ...DEFAULT_WALINE_COMMUNITY_CONFIG,
      server_url: normalizeServerURL(""),
    };
  }
}

export const DEFAULT_COMMUNITY_CONFIG = DEFAULT_WALINE_COMMUNITY_CONFIG;
