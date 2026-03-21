import type { CommunityConfig, CommunityConfigUpdate, CommunitySurfaceConfig } from "@/types/models";

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
}

export const COMMUNITY_CONFIG_ENDPOINTS = ["/site-config/community", "/site-config/community-config"] as const;

export const DEFAULT_COMMUNITY_SURFACES: CommunitySurfaceConfig[] = [
  { key: "posts", label: "Posts", path: "/posts/{slug}", enabled: true },
  { key: "diary", label: "Diary", path: "/diary/{slug}", enabled: true },
  { key: "guestbook", label: "Guestbook", path: "/guestbook", enabled: true },
];

const DEFAULT_META = ["nick", "mail"];
const DEFAULT_REQUIRED_META = ["nick"];
const DEFAULT_EMOJI_PRESETS = ["apple", "weibo", "qq", "bilibili", "twemoji", "github"];

const splitList = (value: string) =>
  value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);

const joinList = (value: string[] | undefined) => (value?.length ? value.join(", ") : "");

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
  avatar_strategy: form.avatar_strategy.trim() || "identicon",
  avatar_helper_copy: form.helper_copy.trim() || null,
});

export const formatCommunitySurfaces = (value: CommunitySurfaceConfig[]) => toPrettyJson(value);
