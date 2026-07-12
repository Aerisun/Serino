import { API_BASE_URL } from "@/lib/api";

export const resolveMarkdownImageSrc = (src?: string) => {
  if (!src || !src.startsWith("/") || !API_BASE_URL) {
    return src;
  }

  try {
    return new URL(src, API_BASE_URL).toString();
  } catch {
    return src;
  }
};
