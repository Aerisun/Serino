import type { PageMotionConfig } from "@/config";

export type RuntimePageWidth = "narrow" | "content" | "wide";

export interface BaseViewPageConfig {
  eyebrow: string;
  title: string;
  description: string;
  metaDescription?: string;
  metaTitle?: string;
  width?: RuntimePageWidth;
  motion: PageMotionConfig;
  emptyMessage?: string;
  loadingLabel?: string;
  retryLabel?: string;
}
