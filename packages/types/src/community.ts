/** Surface keys where community comments can be enabled */
export type CommunitySurface =
  | "posts"
  | "diary"
  | "guestbook"
  | "thoughts"
  | "excerpts"
  | "friends";

/** Comment sorting options */
export type CommunityCommentSort = "latest" | "oldest" | "hottest";

/** Waline search image result */
export interface WalineSearchImage {
  src: string;
  title?: string;
  preview?: string;
}

/** Waline search configuration */
export interface WalineSearchOptions {
  search: (word: string) => Promise<WalineSearchImage[]>;
  default?: () => Promise<WalineSearchImage[]>;
  more?: (word: string, currentCount: number) => Promise<WalineSearchImage[]>;
}

/** Waline emoji preset configuration */
export interface WalineEmojiPreset {
  name: string;
  folder?: string;
  icon?: string;
  prefix?: string;
  type?: string;
  items: string[];
}

/** Avatar preset for community comments */
export interface AvatarPreset {
  key: string;
  label: string;
  avatar_url: string;
}

/** Surface configuration for community comments */
export interface CommunitySurfaceConfig {
  key: string;
  label: string;
  path: string;
  enabled: boolean;
}
