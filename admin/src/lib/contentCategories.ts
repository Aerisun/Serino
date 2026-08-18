export const CONTENT_CATEGORY_TYPES = [
  "posts",
  "notes",
  "excerpts",
] as const;

export type ContentCategoryType = (typeof CONTENT_CATEGORY_TYPES)[number];

export const CONTENT_CATEGORY_LABEL_KEYS: Record<ContentCategoryType, string> = {
  posts: "nav.posts",
  notes: "nav.notes",
  excerpts: "nav.excerpts",
};
