export type ContentPathType = "posts" | "diary" | "thoughts" | "excerpts";

type Translator = (key: string) => string;

const CONTENT_PATH_SEGMENT_TO_TYPE: Record<string, ContentPathType> = {
  posts: "posts",
  diary: "diary",
  thoughts: "thoughts",
  excerpts: "excerpts",
};

const CONTENT_TYPE_ALIAS_TO_TYPE: Record<string, ContentPathType> = {
  post: "posts",
  posts: "posts",
  diary: "diary",
  thought: "thoughts",
  thoughts: "thoughts",
  excerpt: "excerpts",
  excerpts: "excerpts",
};

function decodePathSegment(value: string) {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
}

export function normalizeContentSlugForMatch(slug: string) {
  return decodePathSegment(slug).trim().replace(/\s+/g, "-").toLowerCase();
}

export function getContentSlugSearchTerms(slug: string) {
  const decoded = decodePathSegment(slug).trim();
  const hyphenated = decoded.replace(/\s+/g, "-");
  const spaced = decoded.replace(/[-_]+/g, " ");

  return Array.from(
    new Set([slug.trim(), decoded, hyphenated, spaced].filter(Boolean)),
  );
}

export function formatContentSlugFallback(slug: string) {
  const formatted = decodePathSegment(slug).trim().replace(/[-_]+/g, " ");
  return formatted || slug;
}

export function getContentPathType(contentType: string | undefined | null) {
  if (!contentType) return null;
  return CONTENT_TYPE_ALIAS_TO_TYPE[contentType] ?? null;
}

export function getContentTargetFromPath(path: string) {
  const normalizedPath = path.split("?", 1)[0].split("#", 1)[0];
  const segments = normalizedPath.split("/").filter(Boolean);
  if (segments.length < 2) return null;

  const contentType = CONTENT_PATH_SEGMENT_TO_TYPE[segments[0] ?? ""];
  if (!contentType) return null;

  const slug = segments[segments.length - 1];
  if (!slug) return null;

  return { contentType, slug };
}

function getContentTypeLabel(contentType: ContentPathType, t: Translator) {
  const labels: Record<ContentPathType, string> = {
    posts: t("nav.posts"),
    diary: t("nav.diary"),
    thoughts: t("nav.thoughts"),
    excerpts: t("nav.excerpts"),
  };
  return labels[contentType];
}

export function formatContentTypeTitleLabel({
  contentType,
  t,
  contentTypeLabel,
  title,
  slug,
  separator = " / ",
}: {
  contentType: ContentPathType;
  t?: Translator;
  contentTypeLabel?: string;
  title?: string | null;
  slug: string;
  separator?: string;
}) {
  const resolvedContentTypeLabel =
    contentTypeLabel ?? (t ? getContentTypeLabel(contentType, t) : contentType);
  const normalizedTitle = title?.trim();
  const displayTitle = normalizedTitle || formatContentSlugFallback(slug);
  return `${resolvedContentTypeLabel}${separator}${displayTitle}`;
}
