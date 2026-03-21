import { apiClient } from "@/lib/api";

export type PublicContentKind = "posts" | "diary" | "thoughts" | "excerpts";

export interface PublicContentEntry {
  slug: string;
  title: string;
  summary: string | null;
  body: string;
  tags: string[];
  status: string;
  visibility: string;
  published_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface PublicContentCollection {
  items: PublicContentEntry[];
}

export const publicContentPaths: Record<PublicContentKind, string> = {
  posts: "/api/v1/public/posts",
  diary: "/api/v1/public/diary",
  thoughts: "/api/v1/public/thoughts",
  excerpts: "/api/v1/public/excerpts",
};

export const formatPublishedDate = (value: string | null | undefined) => {
  if (!value) return "";

  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return "";
  }

  return new Intl.DateTimeFormat("zh-CN", {
    year: "numeric",
    month: "long",
    day: "numeric",
  }).format(parsed);
};

export const splitContentParagraphs = (value: string) =>
  value
    .split(/\n{2,}/)
    .map((item) => item.trim())
    .filter(Boolean);

export async function fetchPublicContentCollection(kind: PublicContentKind, limit?: number) {
  const path = new URL(publicContentPaths[kind], "http://localhost");
  if (limit) {
    path.searchParams.set("limit", String(limit));
  }

  return apiClient.get<PublicContentCollection>(`${path.pathname}${path.search}`);
}

export async function fetchPublicContentEntry(kind: Exclude<PublicContentKind, "thoughts" | "excerpts">, slug: string) {
  const normalizedSlug = encodeURIComponent(slug);
  return apiClient.get<PublicContentEntry>(`${publicContentPaths[kind]}/${normalizedSlug}`);
}
