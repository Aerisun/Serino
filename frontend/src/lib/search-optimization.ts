import {
  isPublicHttpUrl,
  resolvePublicResourceUrl,
  resolvePublicUrl,
} from "@/lib/public-url";

export const SEARCH_OPTIMIZATION_FLAG_KEY = "search_optimization";
export const DEFAULT_ROBOTS_DIRECTIVE =
  "index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1";

export interface SearchOptimizationConfig {
  metaTitle: string;
  metaDescription: string;
  keywords: string[];
  llmSummary: string;
  realName: string;
  englishName: string;
  expertise: string[];
  sameAs: string[];
  canonicalUrl: string;
}

interface SearchMetadataSite {
  name: string;
  title: string;
  bio: string;
  role: string;
  ogImage: string;
}

interface BuildSearchMetadataInput {
  site: SearchMetadataSite;
  searchOptimization: SearchOptimizationConfig;
  pageTitle?: string;
  pageDescription?: string;
  pageImage?: string;
  pageAuthor?: string;
  pathname?: string;
  origin?: string;
  noIndex?: boolean;
  ogType?: "website" | "article" | "profile";
}

export interface SearchMetadata {
  title: string;
  shareTitle: string;
  description: string;
  image: string;
  author: string;
  siteTitle: string;
  keywords: string;
  robots: string;
  ogType: "website" | "article" | "profile";
  canonicalUrl: string;
  siteJsonLd: Record<string, unknown>;
}

const EMPTY_SEARCH_OPTIMIZATION: SearchOptimizationConfig = {
  metaTitle: "",
  metaDescription: "",
  keywords: [],
  llmSummary: "",
  realName: "",
  englishName: "",
  expertise: [],
  sameAs: [],
  canonicalUrl: "",
};

const RESUME_PATH = "/resume";

const isRecord = (value: unknown): value is Record<string, unknown> =>
  Boolean(value) && typeof value === "object" && !Array.isArray(value);

const normalizeText = (value: unknown): string =>
  typeof value === "string" ? value.trim() : "";

const splitTextList = (value: unknown): string[] => {
  if (Array.isArray(value)) {
    return value.map(normalizeText).filter(Boolean);
  }

  if (typeof value !== "string") {
    return [];
  }

  return value
    .split(/[\n,，]/)
    .map((item) => item.trim())
    .filter(Boolean);
};

export function normalizeSearchOptimization(raw: unknown): SearchOptimizationConfig {
  if (!isRecord(raw)) {
    return EMPTY_SEARCH_OPTIMIZATION;
  }

  return {
    metaTitle: normalizeText(raw.meta_title),
    metaDescription: normalizeText(raw.meta_description),
    keywords: splitTextList(raw.keywords),
    llmSummary: normalizeText(raw.llm_summary),
    realName: normalizeText(raw.real_name),
    englishName: normalizeText(raw.english_name),
    expertise: splitTextList(raw.expertise),
    sameAs: splitTextList(raw.same_as),
    canonicalUrl: normalizeText(raw.canonical_url),
  };
}

const normalizePathname = (value: string): string => {
  const path = (value || "/").split(/[?#]/)[0] || "/";
  const normalized = path.startsWith("/") ? path : `/${path}`;
  return normalized === "/" ? "/" : normalized.replace(/\/+$/, "");
};

const omitEmpty = (value: Record<string, unknown>) =>
  Object.fromEntries(
    Object.entries(value).filter(([, entry]) => {
      if (Array.isArray(entry)) {
        return entry.length > 0;
      }
      return entry !== "" && entry !== undefined && entry !== null;
    }),
  );

const uniqueTextList = (values: string[]) =>
  Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));

const buildIdentityAliases = (realName: string, englishName: string, nickname: string) =>
  uniqueTextList([englishName, nickname]).filter((value) => value !== realName);

const buildBilingualName = (realName: string, englishName: string) => {
  const names = uniqueTextList([realName, englishName]);
  return names.join(" - ");
};

const buildSiteBrandTitle = (siteName: string, realName: string, englishName: string) =>
  siteName && realName && englishName
    ? `${siteName} - ${realName}(${englishName})`
    : siteName;

export function buildSearchMetadata({
  site,
  searchOptimization,
  pageTitle,
  pageDescription,
  pageImage,
  pageAuthor,
  pathname = "/",
  origin,
  noIndex = false,
  ogType = "website",
}: BuildSearchMetadataInput): SearchMetadata {
  const siteTitle = normalizeText(site.name) || normalizeText(site.title);
  const homepageTitle = buildSiteBrandTitle(
    siteTitle,
    searchOptimization.realName,
    searchOptimization.englishName,
  );
  const normalizedPathname = normalizePathname(pathname);
  const normalizedPageTitle = pageTitle?.trim() ?? "";
  const normalizedPageAuthor = pageAuthor?.trim() ?? "";
  const isHomePage = normalizedPathname === "/";
  const isResumePage = normalizedPathname === RESUME_PATH;
  const author = searchOptimization.realName || normalizedPageAuthor || site.name || site.title;
  const nickname = siteTitle && siteTitle !== author ? siteTitle : "";
  const identityAliases = buildIdentityAliases(
    author,
    searchOptimization.englishName,
    nickname,
  );
  const identityKeywords = uniqueTextList([
    author,
    searchOptimization.englishName,
    nickname,
    ...searchOptimization.keywords,
  ]);
  const bilingualName = buildBilingualName(author, searchOptimization.englishName) || author;
  const title = isResumePage && author
    ? bilingualName
    : normalizedPageTitle
      ? `${normalizedPageTitle} · ${siteTitle}`
      : isHomePage
        ? homepageTitle
        : siteTitle;
  const baseDescription =
    (isHomePage ? searchOptimization.metaDescription : "") ||
    pageDescription ||
    site.bio;
  const shareTitle =
    isHomePage && searchOptimization.metaTitle
      ? searchOptimization.metaTitle
      : isResumePage && searchOptimization.realName
        ? `${bilingualName} Resume${siteTitle && siteTitle !== author ? ` · ${siteTitle}` : ""}`
        : title;
  const description = baseDescription;
  const rawImage = pageImage || site.ogImage;
  const fallbackBaseUrl =
    origin || (typeof window !== "undefined" ? window.location.origin : "");
  const canonicalUrl = resolvePublicUrl({
    canonicalBaseUrl: searchOptimization.canonicalUrl,
    pathname: normalizedPathname,
    fallbackBaseUrl,
  });
  const siteUrl = resolvePublicUrl({
    canonicalBaseUrl: searchOptimization.canonicalUrl,
    pathname: "/",
    fallbackBaseUrl,
  });
  const resumeUrl = resolvePublicUrl({
    canonicalBaseUrl: searchOptimization.canonicalUrl,
    pathname: RESUME_PATH,
    fallbackBaseUrl,
  });
  const image = resolvePublicResourceUrl({
    value: rawImage,
    canonicalBaseUrl: searchOptimization.canonicalUrl,
    fallbackBaseUrl,
  });
  const identityDescription = searchOptimization.llmSummary || description;
  const personId = `${siteUrl}#person`;
  const profilePageId = `${resumeUrl.replace(/\/$/, "")}#profile`;
  const structuredIdentityDescription = identityDescription;
  const publicSameAs = searchOptimization.sameAs.filter(isPublicHttpUrl);

  const person = omitEmpty({
    "@type": "Person",
    "@id": personId,
    name: author,
    alternateName: identityAliases,
    jobTitle: site.role,
    description: structuredIdentityDescription,
    image,
    url: siteUrl,
    sameAs: publicSameAs,
    knowsAbout: searchOptimization.expertise,
    mainEntityOfPage: {
      "@id": profilePageId,
    },
    subjectOf: [
      {
        "@id": profilePageId,
      },
    ],
  });

  const webSiteId = `${siteUrl}#website`;
  const webSite = omitEmpty({
    "@type": "WebSite",
    "@id": webSiteId,
    name: siteTitle,
    url: siteUrl,
    description,
    publisher: {
      "@id": personId,
    },
    about: {
      "@id": personId,
    },
    mainEntity: {
      "@id": personId,
    },
  });

  const profilePage = omitEmpty({
    "@type": "ProfilePage",
    "@id": profilePageId,
    url: resumeUrl,
    name: bilingualName ? `${bilingualName} Resume` : "Resume",
    description: structuredIdentityDescription,
    isPartOf: {
      "@id": webSiteId,
    },
    about: {
      "@id": personId,
    },
    mainEntity: {
      "@id": personId,
    },
  });
  const structuredDataGraph = isHomePage
    ? [person, webSite]
    : isResumePage
      ? [person, profilePage]
      : [person];

  return {
    title,
    shareTitle,
    description,
    image,
    author,
    siteTitle,
    keywords: identityKeywords.join(", "),
    robots: noIndex ? "noindex,follow" : DEFAULT_ROBOTS_DIRECTIVE,
    ogType,
    canonicalUrl,
    siteJsonLd: {
      "@context": "https://schema.org",
      "@graph": structuredDataGraph,
    },
  };
}
