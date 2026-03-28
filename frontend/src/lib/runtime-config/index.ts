import {
  readSiteConfigApiV1SiteSiteGet,
  readPageCopyApiV1SitePagesGet,
  readResumeApiV1SiteResumeGet,
} from "@serino/api-client/site";
import { clampPageSize } from "@/lib/page-size";

// ---------------------------------------------------------------------------
// Width mapping (code constant — not personal data)
// ---------------------------------------------------------------------------
const widthMap = {
  "max-w-2xl": "narrow",
  "max-w-3xl": "content",
  "max-w-4xl": "wide",
} as const;

type PageWidth = "narrow" | "content" | "wide";

// ---------------------------------------------------------------------------
// Backend response types
// ---------------------------------------------------------------------------
type BackendSiteResponse = {
  site: {
    name: string;
    title: string;
    bio: string;
    role: string;
    author: string;
    og_image: string;
    site_icon_url?: string;
    hero_image_url: string;
    hero_poster_url: string;
    meta_description: string;
    copyright: string;
    footer_text?: string;
    hero_video_url?: string | null;
    poem_source?: "custom" | "hitokoto";
    poem_hitokoto_types?: string[];
    poem_hitokoto_keywords?: string[];
    hero_actions?: Array<{
      label: string;
      href: string;
      icon_key: string;
    }>;
    feature_flags?: Record<string, boolean>;
  };
  social_links: Array<{
    name: string;
    href: string;
    icon_key: string;
    placement?: string | null;
  }>;
  poems: Array<{
    content: string;
  }>;
  navigation: Array<{
    label: string;
    trigger: string;
    href?: string | null;
    children: Array<{
      label: string;
      href: string;
    }>;
  }>;
  runtime: {
    public_site_url: string;
    production_cors_origins: string[];
    seo_default_title: string;
    seo_default_description: string;
    rss_title: string;
    rss_description: string;
    robots_indexing_enabled: boolean;
    sitemap_static_pages: Array<{
      path: string;
      changefreq: string;
      priority: string;
    }>;
  };
};

type BackendPageCopyItem = {
  page_key: string;
  title: string;
  subtitle: string;
  description?: string | null;
  search_placeholder?: string | null;
  empty_message?: string | null;
  max_width?: string | null;
  page_size?: number | null;
  download_label?: string | null;
  nav_label?: string | null;
  extras?: Record<string, unknown>;
};

type BackendPagesResponse = {
  items: BackendPageCopyItem[];
};

type BackendResumeResponse = {
  title: string;
  subtitle: string;
  summary: string;
  download_label: string;
  template_key: string;
  accent_tone: string;
  location: string;
  availability: string;
  email: string;
  website: string;
  profile_image_url: string;
  highlights: string[];
  skill_groups: Array<{
    category: string;
    items: string[];
  }>;
  experiences: Array<{
    title: string;
    company: string;
    period: string;
    location: string;
    employment_type: string;
    summary: string;
    achievements: string[];
    tech_stack: string[];
  }>;
};

// ---------------------------------------------------------------------------
// Frontend types
// ---------------------------------------------------------------------------
export interface NavChild {
  label: string;
  href: string;
}

export interface NavItem {
  label: string;
  trigger: "hover" | "arrow" | "none";
  href?: string;
  children?: NavChild[];
}

export interface PageMotionConfig {
  duration: number;
  delay: number;
  stagger: number;
}

export interface ResumeExperienceConfig {
  role: string;
  org: string;
  period: string;
  location?: string;
  employmentType?: string;
  desc: string;
  achievements?: string[];
  techStack?: string[];
}

export interface ResumeSkillGroupConfig {
  category: string;
  items: string[];
}

export interface ResumeContactConfig {
  location?: string;
  availability?: string;
  email?: string;
  website?: string;
}

export interface PageConfig {
  [key: string]: unknown;
}

export interface RuntimeConfigSnapshot {
  source: "remote";
  site: {
    name: string;
    title: string;
    bio: string;
    role: string;
    author: string;
    ogImage: string;
    siteIconUrl: string;
    heroImageUrl: string;
    heroPosterUrl: string;
    metaDescription: string;
    canonicalUrl: string;
    rssTitle: string;
    rssDescription: string;
    robotsIndexingEnabled: boolean;
    sitemapStaticPages: Array<{ path: string; changefreq: string; priority: string }>;
    copyright: string;
    socialLinks: Array<{ name: string; href: string; iconKey: string; placement: "hero" | "footer" | "both" }>;
    poems: string[];
    poemSource: "custom" | "hitokoto";
    poemHitokotoTypes: string[];
    poemHitokotoKeywords: string[];
    heroActions: Array<{ label: string; href: string; iconKey: string }>;
    heroVideoUrl?: string;
    navigation: NavItem[];
    footer: { slogan: string; copyright: string };
    featureFlags: Record<string, boolean>;
  };
  pages: Record<string, PageConfig>;
}

// ---------------------------------------------------------------------------
// Default motion configs (code constants — not personal data)
// ---------------------------------------------------------------------------
const DEFAULT_MOTION: PageMotionConfig = { duration: 0.4, delay: 0.06, stagger: 0.04 };

const PAGE_DEFAULTS: Record<string, { width?: PageWidth; pageSize?: number; motion?: PageMotionConfig }> = {
  posts:    { width: "content", motion: DEFAULT_MOTION },
  diary:    { width: "narrow",  motion: DEFAULT_MOTION },
  friends:  { width: "wide",    pageSize: 10, motion: { duration: 0.4, delay: 0.08, stagger: 0.04 } },
  excerpts: { width: "content", motion: DEFAULT_MOTION },
  thoughts: { width: "narrow",  motion: { duration: 0.4, delay: 0.08, stagger: 0.04 } },
  guestbook:{ width: "narrow",  motion: { duration: 0.45, delay: 0.06, stagger: 0.04 } },
  resume:   { width: "content", motion: { duration: 0.45, delay: 0.06, stagger: 0.04 } },
  calendar: { width: "wide",    motion: { duration: 0.5, delay: 0.08, stagger: 0.05 } },
};

// ---------------------------------------------------------------------------
// Icon key normalization
// ---------------------------------------------------------------------------
const normalizeIconKey = (iconKey: string): string => {
  const aliases: Record<string, string> = {
    netease: "music",
    "netease-music": "music",
    weixin: "wechat",
    lark: "feishu",
    fb: "facebook",
    ig: "instagram",
    mail: "email",
    web: "website",
    site: "website",
    url: "website",
    rednote: "xiaohongshu",
  };
  const normalized = iconKey.toLowerCase();
  return aliases[normalized] ?? normalized;
};

const normalizeSocialPlacement = (placement?: string | null): "hero" | "footer" | "both" => {
  switch ((placement ?? "").toLowerCase()) {
    case "hero":
      return "hero";
    case "footer":
      return "footer";
    case "both":
      return "both";
    default:
      return "both";
  }
};

// ---------------------------------------------------------------------------
// Normalize site config
// ---------------------------------------------------------------------------
const normalizeSiteConfig = (
  payload: BackendSiteResponse,
): RuntimeConfigSnapshot["site"] => {
  // Build navigation from backend data
  const navigation: NavItem[] = (payload.navigation ?? []).map((entry) => {
    const item: NavItem = {
      label: entry.label,
      trigger: (entry.trigger as "hover" | "arrow" | "none") || "none",
    };
    if (entry.href) item.href = entry.href;
    if (entry.children && entry.children.length > 0) {
      item.children = entry.children.map((child) => ({
        label: child.label,
        href: child.href,
      }));
    }
    return item;
  });

  return {
    name: payload.site.name,
    title: payload.runtime.seo_default_title || payload.site.title,
    bio: payload.site.bio,
    role: payload.site.role,
    author: payload.site.author,
    ogImage: payload.site.og_image,
    siteIconUrl: payload.site.site_icon_url ?? "",
    heroImageUrl: payload.site.hero_image_url,
    heroPosterUrl: payload.site.hero_poster_url,
    metaDescription: payload.runtime.seo_default_description || payload.site.meta_description,
    canonicalUrl: payload.runtime.public_site_url,
    rssTitle: payload.runtime.rss_title,
    rssDescription: payload.runtime.rss_description,
    robotsIndexingEnabled: payload.runtime.robots_indexing_enabled,
    sitemapStaticPages: payload.runtime.sitemap_static_pages ?? [],
    copyright: payload.site.copyright,
    poems: payload.poems.map((p) => p.content).filter(Boolean),
    poemSource: payload.site.poem_source ?? "custom",
    poemHitokotoTypes: payload.site.poem_hitokoto_types ?? [],
    poemHitokotoKeywords: payload.site.poem_hitokoto_keywords ?? [],
    socialLinks: payload.social_links.map((link) => ({
      name: link.name,
      href: link.href,
      iconKey: normalizeIconKey(link.icon_key),
      placement: normalizeSocialPlacement(link.placement),
    })),
    heroActions: (payload.site.hero_actions ?? []).map((action) => ({
      label: action.label,
      href: action.href,
      iconKey: normalizeIconKey(action.icon_key),
    })),
    heroVideoUrl: payload.site.hero_video_url ?? undefined,
    navigation,
    footer: {
      slogan: payload.site.footer_text ?? "",
      copyright: payload.site.copyright,
    },
    featureFlags: payload.site.feature_flags ?? { toc: true, reading_progress: true, social_sharing: true },
  };
};

// ---------------------------------------------------------------------------
// Normalize pages config
// ---------------------------------------------------------------------------
const normalizePagesConfig = (payload: BackendPagesResponse): Record<string, PageConfig> => {
  const pages: Record<string, PageConfig> = {};

  for (const item of payload.items) {
    const defaults = PAGE_DEFAULTS[item.page_key];
    const widthFromApi =
      item.max_width && item.max_width in widthMap
        ? widthMap[item.max_width as keyof typeof widthMap]
        : defaults?.width;

    const page: PageConfig = {
      title: item.title,
      description: item.subtitle ?? item.description ?? undefined,
      metaDescription:
        typeof item.extras?.metaDescription === "string" ? item.extras.metaDescription : undefined,
      metaTitle:
        typeof item.extras?.metaTitle === "string" ? item.extras.metaTitle : undefined,
      searchPlaceholder: item.search_placeholder ?? undefined,
      emptyMessage: item.empty_message ?? undefined,
      width: widthFromApi ?? defaults?.width,
      pageSize: clampPageSize(item.page_size, defaults?.pageSize ?? 20),
      downloadLabel: item.download_label ?? undefined,
      motion: defaults?.motion ?? DEFAULT_MOTION,
    };

    // Merge extras
    if (item.extras) {
      if (typeof item.extras.category_all_label === "string") {
        page.categories = {
          ...(typeof page.categories === "object" && page.categories ? page.categories as Record<string, unknown> : {}),
          all: item.extras.category_all_label,
        };
      }
      if (typeof item.extras.category_fallback_label === "string") {
        page.categories = {
          ...(typeof page.categories === "object" && page.categories ? page.categories as Record<string, unknown> : {}),
          fallback: item.extras.category_fallback_label,
        };
      }
      if (typeof item.extras.circle_title === "string") {
        page.circleTitle = item.extras.circle_title;
      }
      if (typeof item.extras.eyebrow === "string") {
        page.eyebrow = item.extras.eyebrow;
      }
      // Pass through remaining extras
      for (const [key, value] of Object.entries(item.extras)) {
        if (
          !(key in page) &&
          key !== "category_all_label" &&
          key !== "category_fallback_label" &&
          key !== "circle_title" &&
          key !== "eyebrow" &&
          key !== "metaTitle" &&
          key !== "metaDescription"
        ) {
          page[key] = value;
        }
      }
    }

    pages[item.page_key] = page;
  }

  return pages;
};

// ---------------------------------------------------------------------------
// Normalize resume config
// ---------------------------------------------------------------------------
const normalizeResumeConfig = (payload: BackendResumeResponse): PageConfig => {
  const defaults = PAGE_DEFAULTS.resume;
  return {
    title: payload.title,
    subtitle: payload.subtitle,
    description: payload.summary,
    downloadLabel: payload.download_label,
    bio: payload.summary,
    templateKey: payload.template_key,
    accentTone: payload.accent_tone,
    profileImageUrl: payload.profile_image_url,
    highlights: payload.highlights,
    contacts: {
      location: payload.location,
      availability: payload.availability,
      email: payload.email,
      website: payload.website,
    },
    skills: payload.skill_groups.flatMap((group) => group.items),
    skillGroups: payload.skill_groups.map((group) => ({
      category: group.category,
      items: group.items,
    })),
    experience: payload.experiences.map((item) => ({
      role: item.title,
      org: item.company,
      period: item.period,
      location: item.location,
      employmentType: item.employment_type,
      desc: item.summary,
      achievements: item.achievements,
      techStack: item.tech_stack,
    })),
    width: defaults?.width,
    motion: defaults?.motion,
  };
};

// ---------------------------------------------------------------------------
// Main loader — errors propagate to caller
// ---------------------------------------------------------------------------
export async function loadRuntimeConfig(): Promise<RuntimeConfigSnapshot> {
  const [siteResponse, pagesResponse, resumeResponse] = await Promise.all([
    readSiteConfigApiV1SiteSiteGet(),
    readPageCopyApiV1SitePagesGet(),
    readResumeApiV1SiteResumeGet(),
  ]);

  const site = siteResponse.data as unknown as BackendSiteResponse;
  const pages = pagesResponse.data as unknown as BackendPagesResponse;
  const resume = resumeResponse.data as unknown as BackendResumeResponse;

  const normalizedPages = normalizePagesConfig(pages);
  normalizedPages.resume = normalizeResumeConfig(resume);

  return {
    source: "remote",
    site: normalizeSiteConfig(site),
    pages: normalizedPages,
  };
}
