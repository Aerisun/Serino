export const SEARCH_OPTIMIZATION_FLAG_KEY = "search_optimization";
export const DEFAULT_ROBOTS_DIRECTIVE =
  "index,follow,max-snippet:-1,max-image-preview:large,max-video-preview:-1";

export interface SearchOptimizationConfig {
  metaTitle: string;
  metaDescription: string;
  keywords: string[];
  llmSummary: string;
  realName: string;
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
  canonicalUrl: string;
  siteJsonLd: Record<string, unknown>;
}

const EMPTY_SEARCH_OPTIMIZATION: SearchOptimizationConfig = {
  metaTitle: "",
  metaDescription: "",
  keywords: [],
  llmSummary: "",
  realName: "",
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

const resolveCanonicalUrl = ({
  canonicalBaseUrl,
  pathname = "/",
  origin,
}: {
  canonicalBaseUrl: string;
  pathname?: string;
  origin?: string;
}) => {
  const normalizedPath = pathname.startsWith("/") ? pathname : `/${pathname}`;
  const base = canonicalBaseUrl || origin || (typeof window !== "undefined" ? window.location.origin : "");
  if (!base) {
    return normalizedPath;
  }

  try {
    return new URL(normalizedPath, base.endsWith("/") ? base : `${base}/`).href;
  } catch {
    return normalizedPath;
  }
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

const hasCjk = (value: string) => /[\u3400-\u9fff]/.test(value);

const uniqueTextList = (values: string[]) =>
  Array.from(new Set(values.map((value) => value.trim()).filter(Boolean)));

const buildIdentityLabel = (realName: string, nickname: string) => {
  if (!realName || !nickname || realName === nickname) {
    return realName;
  }
  return hasCjk(realName) ? `${realName}（${nickname}）` : `${realName} (${nickname})`;
};

const strengthenIdentityDescription = ({
  description,
  realName,
  nickname,
}: {
  description: string;
  realName: string;
  nickname: string;
}) => {
  const label = buildIdentityLabel(realName, nickname);
  if (!label || label === realName) {
    return description;
  }
  if (description.includes(realName) && description.includes(nickname)) {
    return description;
  }
  const separator = hasCjk(realName) ? "。" : ".";
  return description ? `${label}${separator} ${description}` : label;
};

export function buildSearchMetadata({
  site,
  searchOptimization,
  pageTitle,
  pageDescription,
  pageImage,
  pageAuthor,
  pathname = "/",
  origin,
}: BuildSearchMetadataInput): SearchMetadata {
  const siteTitle = site.title || site.name;
  const normalizedPathname = normalizePathname(pathname);
  const normalizedPageTitle = pageTitle?.trim() ?? "";
  const normalizedPageAuthor = pageAuthor?.trim() ?? "";
  const isHomePage = normalizedPathname === "/";
  const isResumePage = normalizedPathname === RESUME_PATH;
  const author = searchOptimization.realName || normalizedPageAuthor || site.name || site.title;
  const nickname = siteTitle && siteTitle !== author ? siteTitle : "";
  const title = normalizedPageTitle
    ? `${normalizedPageTitle} · ${siteTitle}`
    : isResumePage && author
      ? author
      : siteTitle;
  const baseDescription =
    (isHomePage ? searchOptimization.metaDescription : "") ||
    pageDescription ||
    site.bio;
  const shareTitle =
    isHomePage && searchOptimization.metaTitle
      ? searchOptimization.metaTitle
      : isResumePage && searchOptimization.realName
        ? `${author} Resume${siteTitle && siteTitle !== author ? ` · ${siteTitle}` : ""}`
        : title;
  const shouldStrengthenIdentity = isHomePage || isResumePage;
  const description =
    shouldStrengthenIdentity && searchOptimization.realName
      ? strengthenIdentityDescription({
          description: baseDescription,
          realName: author,
          nickname,
        })
      : baseDescription;
  const image = pageImage || site.ogImage;
  const canonicalUrl = resolveCanonicalUrl({
    canonicalBaseUrl: searchOptimization.canonicalUrl,
    pathname,
    origin,
  });
  const siteUrl = resolveCanonicalUrl({
    canonicalBaseUrl: searchOptimization.canonicalUrl,
    pathname: "/",
    origin,
  });
  const resumeUrl = resolveCanonicalUrl({
    canonicalBaseUrl: searchOptimization.canonicalUrl,
    pathname: RESUME_PATH,
    origin,
  });
  const identityDescription = searchOptimization.llmSummary || description;
  const personId = `${siteUrl.replace(/\/$/, "")}#person`;
  const profilePageId = `${resumeUrl.replace(/\/$/, "")}#profile`;
  const identityAlternateNames = uniqueTextList([nickname]).filter((value) => value !== author);
  const strengthenedIdentityDescription =
    shouldStrengthenIdentity && searchOptimization.realName
      ? strengthenIdentityDescription({
          description: identityDescription,
          realName: author,
          nickname,
        })
      : identityDescription;

  const person = omitEmpty({
    "@type": "Person",
    "@id": personId,
    name: author,
    alternateName: identityAlternateNames,
    jobTitle: site.role,
    description: strengthenedIdentityDescription,
    image,
    url: siteUrl,
    sameAs: searchOptimization.sameAs,
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

  const webSiteId = `${siteUrl.replace(/\/$/, "")}#website`;
  const webSite = omitEmpty({
    "@type": "WebSite",
    "@id": webSiteId,
    name: siteTitle,
    alternateName: searchOptimization.metaTitle,
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
    name: author ? `${author} Resume` : "Resume",
    description: strengthenedIdentityDescription,
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

  return {
    title,
    shareTitle,
    description,
    image,
    author,
    siteTitle,
    keywords: searchOptimization.keywords.join(", "),
    robots: DEFAULT_ROBOTS_DIRECTIVE,
    canonicalUrl,
    siteJsonLd: {
      "@context": "https://schema.org",
      "@graph": [person, webSite, profilePage],
    },
  };
}
