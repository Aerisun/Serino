import type { CommunityConfigAdminRead } from "@serino/api-client/models";
import type { CommunityConfigUpdate } from "@serino/api-client/models";
import type { CommunitySurfaceUpdate } from "@serino/api-client/models";

export interface CommunityConfigFormState {
  provider: string;
  server_url: string;
  migration_state: string;
  surfaces: string;
  meta: string;
  required_meta: string;
  emoji_presets: string;
  image_uploader: boolean;
  helper_copy: string;
  email_login_enabled: boolean;
  moderation_mode: string;
  default_sorting: string;
  page_size: string;
  image_max_bytes: string;
  comment_image_rate_limit_count: string;
  comment_image_rate_limit_window_minutes: string;
}

const DEFAULT_COMMUNITY_SURFACES: CommunitySurfaceUpdate[] = [
  { key: "posts", label: "Posts", path: "/posts/{slug}", enabled: true },
  { key: "diary", label: "Diary", path: "/diary/{slug}", enabled: true },
  { key: "guestbook", label: "Guestbook", path: "/guestbook", enabled: true },
  { key: "thoughts", label: "Thoughts", path: "/thoughts/{slug}", enabled: true },
  { key: "excerpts", label: "Excerpts", path: "/excerpts/{slug}", enabled: true },
];

const DEFAULT_META = ["nick", "mail"];
const DEFAULT_REQUIRED_META = ["nick"];
const DEFAULT_EMOJI_PRESETS = ["weibo", "qq", "tieba", "bilibili", "twemoji", "alus", "bmoji"];
const DEFAULT_MODERATION_MODE = "all_pending";
const DEFAULT_DEFAULT_SORTING = "latest";

const normalizeModerationMode = (value: string | null | undefined): string => {
  const normalized = String(value ?? "").trim().toLowerCase().replace(/-/g, "_");
  if (normalized === "no_review" || normalized === "none" || normalized === "off" || normalized === "disabled") {
    return "no_review";
  }
  return DEFAULT_MODERATION_MODE;
};

const splitList = (value: string) =>
  value
    .split(/[\n,]/)
    .map((item) => item.trim())
    .filter(Boolean);

const joinList = (value: string[] | undefined | null) => (value?.length ? value.join(", ") : "");
const toPrettyJson = (value: unknown) => JSON.stringify(value ?? [], null, 2);

const parseSurfaceList = (value: string): CommunitySurfaceUpdate[] => {
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

export const createCommunityForm = (config?: CommunityConfigAdminRead | null): CommunityConfigFormState => ({
  provider: config?.provider ?? "waline",
  server_url: config?.server_url ?? "",
  migration_state: config?.migration_state ?? "draft",
  surfaces: toPrettyJson(config?.surfaces ?? DEFAULT_COMMUNITY_SURFACES),
  meta: joinList(config?.meta ?? DEFAULT_META),
  required_meta: joinList(config?.required_meta ?? DEFAULT_REQUIRED_META),
  emoji_presets: joinList(config?.emoji_presets ?? DEFAULT_EMOJI_PRESETS),
  image_uploader: config?.image_uploader ?? false,
  helper_copy: config?.avatar_helper_copy ?? "",
  email_login_enabled: config?.anonymous_enabled ?? true,
  moderation_mode: normalizeModerationMode(config?.moderation_mode),
  default_sorting: config?.default_sorting ?? DEFAULT_DEFAULT_SORTING,
  page_size: String(config?.page_size ?? 20),
  image_max_bytes: String(config?.image_max_bytes ?? 524288),
  comment_image_rate_limit_count: String(config?.comment_image_rate_limit_count ?? 18),
  comment_image_rate_limit_window_minutes: String(config?.comment_image_rate_limit_window_minutes ?? 30),
});

export const communityFormToUpdate = (form: CommunityConfigFormState): CommunityConfigUpdate => ({
  provider: form.provider.trim() || "waline",
  server_url: form.server_url.trim(),
  migration_state: form.migration_state.trim() || "draft",
  surfaces: parseSurfaceList(form.surfaces),
  meta: splitList(form.meta),
  required_meta: splitList(form.required_meta),
  emoji_presets: splitList(form.emoji_presets),
  image_uploader: form.image_uploader,
  anonymous_enabled: form.email_login_enabled,
  moderation_mode: normalizeModerationMode(form.moderation_mode),
  default_sorting: form.default_sorting.trim() || DEFAULT_DEFAULT_SORTING,
  page_size: Math.max(1, Number.parseInt(form.page_size, 10) || 20),
  image_max_bytes: Math.max(0, Number.parseInt(form.image_max_bytes, 10) || 524288),
  comment_image_rate_limit_count: Math.min(
    60,
    Math.max(1, Number.parseInt(form.comment_image_rate_limit_count, 10) || 18),
  ),
  comment_image_rate_limit_window_minutes: Math.min(
    1440,
    Math.max(1, Number.parseInt(form.comment_image_rate_limit_window_minutes, 10) || 30),
  ),
  avatar_helper_copy: form.helper_copy.trim() || null,
});
