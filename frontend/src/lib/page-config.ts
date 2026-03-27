import type { PageMotionConfig } from "@/config";

export type RuntimePageWidth = "narrow" | "content" | "wide";

export interface BaseViewPageConfig {
  eyebrow: string;
  title: string;
  description: string;
  metaDescription?: string;
  metaTitle?: string;
  searchPlaceholder?: string;
  width?: RuntimePageWidth;
  motion: PageMotionConfig;
  pageSize?: number;
  emptyMessage?: string;
  loadingLabel?: string;
  loadMoreLabel?: string;
  retryLabel?: string;
  errorTitle?: string;
}
