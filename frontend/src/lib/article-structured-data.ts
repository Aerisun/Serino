import { resolvePublicResourceUrl, resolvePublicUrl } from "@/lib/public-url";

const truncateText = (value: string, maxLength: number) => {
  if (value.length <= maxLength) return value;
  return `${value.slice(0, maxLength - 1).trimEnd()}…`;
};

const normalizeWhitespace = (value: string) => value.replace(/\s+/g, " ").trim();

const markdownToPlainText = (value: string) =>
  normalizeWhitespace(
    value
      .replace(/\[([^\]]+)]\([^)]+\)/g, "$1")
      .replace(/[#>*_`~-]+/g, " "),
  );

export function buildContentSearchDescription({
  summary = "",
  body = "",
  maxLength = 260,
}: {
  summary?: string;
  body?: string;
  maxLength?: number;
}): string {
  const normalizedSummary = normalizeWhitespace(summary);
  const source = normalizedSummary || markdownToPlainText(body);
  return truncateText(source, maxLength);
}

interface BuildArticleStructuredDataInput {
  title: string;
  description: string;
  slug: string;
  type: "posts" | "notes" | "diary";
  publishedAt?: string;
  modifiedAt?: string;
  tags?: string[];
  image?: string;
  origin: string;
  canonicalBaseUrl?: string;
  siteName: string;
  realName: string;
}

export function buildArticleStructuredData({
  title,
  description,
  slug,
  type,
  publishedAt,
  modifiedAt,
  tags,
  image,
  origin,
  canonicalBaseUrl,
  siteName,
  realName,
}: BuildArticleStructuredDataInput): Record<string, unknown> {
  const siteUrl = resolvePublicUrl({ canonicalBaseUrl, fallbackBaseUrl: origin });
  const baseUrl = siteUrl.replace(/\/$/, "");
  const articleUrl = resolvePublicUrl({
    canonicalBaseUrl,
    fallbackBaseUrl: origin,
    pathname: `/${type}/${slug}`,
  });
  const personName = realName.trim() || siteName.trim();
  const personId = `${baseUrl}/#person`;
  const data: Record<string, unknown> = {
    "@context": "https://schema.org",
    "@type": "BlogPosting",
    "@id": `${articleUrl}#article`,
    headline: title,
    description: description || "",
    url: articleUrl,
    author: {
      "@type": "Person",
      "@id": personId,
      name: personName,
      url: `${baseUrl}/resume`,
    },
    publisher: {
      "@id": personId,
    },
    mainEntityOfPage: {
      "@type": "WebPage",
      "@id": articleUrl,
    },
  };

  if (publishedAt) data.datePublished = publishedAt;
  if (modifiedAt) data.dateModified = modifiedAt;
  const resolvedImage = resolvePublicResourceUrl({
    value: image ?? "",
    canonicalBaseUrl,
    fallbackBaseUrl: origin,
  });
  if (resolvedImage) data.image = resolvedImage;
  if (tags && tags.length > 0) data.keywords = tags.join(", ");
  return data;
}
