import type {
  CommunityAvatarPreset,
  CommunityConfig,
  CommunityConfigUpdate,
  CommunitySurfaceConfig,
} from "@/types/models";

export interface CommunityConfigFormState {
  provider: string;
  server_url: string;
  migration_state: string;
  surfaces: string;
  meta: string;
  required_meta: string;
  emoji_presets: string;
  enable_enjoy_search: boolean;
  image_uploader: boolean;
  login_mode: string;
  oauth_url: string;
  avatar_strategy: string;
  helper_copy: string;
  oauth_providers: string;
  anonymous_enabled: boolean;
  moderation_mode: string;
  default_sorting: string;
  page_size: string;
  avatar_presets: string;
  guest_avatar_mode: string;
  draft_enabled: boolean;
}

export const COMMUNITY_CONFIG_ENDPOINTS = ["/site-config/community-config"] as const;

export const DEFAULT_COMMUNITY_SURFACES: CommunitySurfaceConfig[] = [
  { key: "posts", label: "Posts", path: "/posts/{slug}", enabled: true },
  { key: "diary", label: "Diary", path: "/diary/{slug}", enabled: true },
  { key: "guestbook", label: "Guestbook", path: "/guestbook", enabled: true },
  { key: "thoughts", label: "Thoughts", path: "/thoughts/{slug}", enabled: true },
  { key: "excerpts", label: "Excerpts", path: "/excerpts/{slug}", enabled: true },
];

const DEFAULT_META = ["nick", "mail"];
const DEFAULT_REQUIRED_META = ["nick"];
const DEFAULT_EMOJI_PRESETS = ["apple", "weibo", "qq", "bilibili", "twemoji", "github"];
const DEFAULT_OAUTH_PROVIDERS = ["github", "google"];
const DEFAULT_AVATAR_PRESETS: CommunityAvatarPreset[] = [
  {
    key: "shiro",
    label: "Shiro",
    avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Shiro",
  },
  {
    key: "glass",
    label: "Glass",
    avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Glass",
  },
  {
    key: "aurora",
    label: "Aurora",
    avatar_url: "https://api.dicebear.com/9.x/notionists/svg?seed=Aurora",
  },
];
const DEFAULT_MODERATION_MODE = "all_pending";
const DEFAULT_DEFAULT_SORTING = "latest";
const DEFAULT_GUEST_AVATAR_MODE = "preset";

const splitList = (value: string) =>
  value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);

const joinList = (value: string[] | undefined | null) => (value?.length ? value.join(", ") : "");
const toPrettyJson = (value: unknown) => JSON.stringify(value ?? [], null, 2);

const parseSurfaceList = (value: string): CommunitySurfaceConfig[] => {
  const raw = value.trim();
  if (!raw) {
    return DEFAULT_COMMUNITY_SURFACES;
  }

  const parsed = JSON.parse(raw) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error("Surface config must be a JSON array");
  }

  return parsed.map((item) => {
    if (!item || typeof item !== "object") {
      throw new Error("Surface config item is invalid");
    }

    const record = item as Record<string, unknown>;
    return {
      key: String(record.key ?? record.page_key ?? ""),
      label: String(record.label ?? ""),
      path: String(record.path ?? ""),
      enabled: Boolean(record.enabled ?? true),
    };
  });
};

const parseAvatarPresets = (value: string): CommunityAvatarPreset[] => {
  const raw = value.trim();
  if (!raw) {
    return DEFAULT_AVATAR_PRESETS;
  }

  const parsed = JSON.parse(raw) as unknown;
  if (!Array.isArray(parsed)) {
    throw new Error("Avatar presets must be a JSON array");
  }

  return parsed.map((item, index) => {
    if (!item || typeof item !== "object") {
      throw new Error(`Avatar preset #${index + 1} is invalid`);
    }

    const record = item as Record<string, unknown>;
    const key = String(record.key ?? record.id ?? "").trim();
    const label = String(record.label ?? record.name ?? "").trim();
    const avatarUrl = String(record.avatar_url ?? record.src ?? "").trim();
    if (!key || !label || !avatarUrl) {
      throw new Error(`Avatar preset #${index + 1} must include key, label and avatar_url`);
    }

    return {
      key,
      label,
      avatar_url: avatarUrl,
      note: typeof record.note === "string" ? record.note : null,
    };
  });
};

export const createCommunityForm = (config?: CommunityConfig | null): CommunityConfigFormState => ({
  provider: config?.provider ?? "waline",
  server_url: config?.server_url ?? "",
  migration_state: config?.migration_state ?? "draft",
  surfaces: toPrettyJson(config?.surfaces ?? DEFAULT_COMMUNITY_SURFACES),
  meta: joinList(config?.meta ?? DEFAULT_META),
  required_meta: joinList(config?.required_meta ?? DEFAULT_REQUIRED_META),
  emoji_presets: joinList(config?.emoji_presets ?? DEFAULT_EMOJI_PRESETS),
  enable_enjoy_search: config?.enable_enjoy_search ?? true,
  image_uploader: config?.image_uploader ?? false,
  login_mode: config?.login_mode ?? "disable",
  oauth_url: config?.oauth_url ?? "",
  avatar_strategy: config?.avatar_strategy ?? "identicon",
  helper_copy: config?.avatar_helper_copy ?? "",
  oauth_providers: joinList(config?.oauth_providers ?? DEFAULT_OAUTH_PROVIDERS),
  anonymous_enabled: config?.anonymous_enabled ?? true,
  moderation_mode: config?.moderation_mode ?? DEFAULT_MODERATION_MODE,
  default_sorting: config?.default_sorting ?? DEFAULT_DEFAULT_SORTING,
  page_size: String(config?.page_size ?? 20),
  avatar_presets: toPrettyJson(config?.avatar_presets ?? DEFAULT_AVATAR_PRESETS),
  guest_avatar_mode: config?.guest_avatar_mode ?? DEFAULT_GUEST_AVATAR_MODE,
  draft_enabled: config?.draft_enabled ?? true,
});

export const communityFormToUpdate = (form: CommunityConfigFormState): CommunityConfigUpdate => ({
  provider: form.provider.trim() || "waline",
  server_url: form.server_url.trim(),
  migration_state: form.migration_state.trim() || "draft",
  surfaces: parseSurfaceList(form.surfaces),
  meta: splitList(form.meta),
  required_meta: splitList(form.required_meta),
  emoji_presets: splitList(form.emoji_presets),
  enable_enjoy_search: form.enable_enjoy_search,
  image_uploader: form.image_uploader,
  login_mode: form.login_mode.trim() || "disable",
  oauth_url: form.oauth_url.trim() || null,
  oauth_providers: splitList(form.oauth_providers),
  anonymous_enabled: form.anonymous_enabled,
  moderation_mode: form.moderation_mode.trim() || DEFAULT_MODERATION_MODE,
  default_sorting: form.default_sorting.trim() || DEFAULT_DEFAULT_SORTING,
  page_size: Math.max(1, Number.parseInt(form.page_size, 10) || 20),
  avatar_presets: parseAvatarPresets(form.avatar_presets),
  guest_avatar_mode: form.guest_avatar_mode.trim() || DEFAULT_GUEST_AVATAR_MODE,
  draft_enabled: form.draft_enabled,
  avatar_strategy: form.avatar_strategy.trim() || "identicon",
  avatar_helper_copy: form.helper_copy.trim() || null,
});

export const formatCommunitySurfaces = (value: CommunitySurfaceConfig[]) => toPrettyJson(value);

export const parseCommunityList = (value: string) =>
  value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);
