import {
  readSiteConfigApiV1PublicSiteGet,
  readPageCopyApiV1PublicPagesGet,
  readResumeApiV1PublicResumeGet,
} from "@serino/api-client/public";

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
    meta_description: string;
    copyright: string;
    footer_text?: string;
    hero_video_url?: string | null;
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
  skill_groups: Array<{
    items: string[];
  }>;
  experiences: Array<{
    title: string;
    company: string;
    period: string;
    summary: string;
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
  desc: string;
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
    metaDescription: string;
    copyright: string;
    socialLinks: Array<{ name: string; href: string; iconKey: string; placement: "hero" | "footer" | "both" }>;
    poems: string[];
    heroActions: Array<{ label: string; href: string; iconKey: string }>;
    heroVideoUrl?: string;
    navigation: NavItem[];
    footer: { slogan: string; copyright: string };
    featureFlags: Record<string, boolean>;
  };
  pages: Record<string, PageConfig>;
}

// ---------------------------------------------------------------------------
// API paths
// ---------------------------------------------------------------------------
export const runtimeConfigPaths = {
  site: "/api/v1/public/site",
  pages: "/api/v1/public/pages",
  resume: "/api/v1/public/resume",
} as const;

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
    title: payload.site.title,
    bio: payload.site.bio,
    role: payload.site.role,
    author: payload.site.author,
    ogImage: payload.site.og_image,
    metaDescription: payload.site.meta_description,
    copyright: payload.site.copyright,
    poems: payload.poems.map((p) => p.content).filter(Boolean),
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
      subtitle: item.subtitle,
      description: item.description ?? undefined,
      searchPlaceholder: item.search_placeholder ?? undefined,
      emptyMessage: item.empty_message ?? undefined,
      width: widthFromApi ?? defaults?.width,
      pageSize: item.page_size ?? defaults?.pageSize,
      downloadLabel: item.download_label ?? undefined,
      motion: defaults?.motion ?? DEFAULT_MOTION,
    };

    // Merge extras
    if (item.extras) {
      if (typeof item.extras.category_all_label === "string") {
        page.categories = { all: item.extras.category_all_label };
      }
      if (typeof item.extras.circle_title === "string") {
        page.circleTitle = item.extras.circle_title;
      }
      if (typeof item.extras.eyebrow === "string") {
        page.eyebrow = item.extras.eyebrow;
      }
      // Pass through remaining extras
      for (const [key, value] of Object.entries(item.extras)) {
        if (!(key in page) && key !== "category_all_label" && key !== "circle_title" && key !== "eyebrow") {
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
    skills: payload.skill_groups.flatMap((group) => group.items),
    experience: payload.experiences.map((item) => ({
      role: item.title,
      org: item.company,
      period: item.period,
      desc: item.summary,
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
    readSiteConfigApiV1PublicSiteGet(),
    readPageCopyApiV1PublicPagesGet(),
    readResumeApiV1PublicResumeGet(),
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
