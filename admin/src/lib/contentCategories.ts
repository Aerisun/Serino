export const CONTENT_CATEGORY_TYPES = [
  "posts",
  "thoughts",
  "excerpts",
] as const;

export type ContentCategoryType = (typeof CONTENT_CATEGORY_TYPES)[number];

export const CONTENT_CATEGORY_LABEL_KEYS: Record<ContentCategoryType, string> = {
  posts: "nav.posts",
  thoughts: "nav.thoughts",
  excerpts: "nav.excerpts",
};
