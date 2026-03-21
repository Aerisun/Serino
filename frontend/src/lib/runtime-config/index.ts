import { pageConfig } from "@/config/pages";
import { siteConfig } from "@/config/site";
import { apiClient } from "@/lib/api";

export type RuntimeSiteConfig = typeof siteConfig;
export type RuntimePageConfig = typeof pageConfig;

export interface RuntimeConfigSnapshot {
  site: RuntimeSiteConfig;
  pages: RuntimePageConfig;
  source: "fallback" | "remote";
  fetchedAt: string;
}

export const runtimeConfigFallback = {
  site: siteConfig,
  pages: pageConfig,
} as const;

export const runtimeConfigPaths = {
  site: "/api/v1/public/site",
  pages: "/api/v1/public/pages",
  resume: "/api/v1/public/resume",
} as const;

type BackendSiteResponse = {
  site: {
    name: string;
    title: string;
    bio: string;
    role: string;
    footer_text?: string;
  };
  social_links: Array<{
    name: string;
    href: string;
    icon_key: string;
  }>;
  poems: Array<{
    content: string;
  }>;
};

type BackendPagesResponse = {
  items: Array<{
    page_key: keyof RuntimePageConfig;
    title: string;
    subtitle: string;
    description?: string | null;
    search_placeholder?: string | null;
    empty_message?: string | null;
    max_width?: string | null;
    page_size?: number | null;
    download_label?: string | null;
    extras?: Record<string, unknown>;
  }>;
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

const mergeConfig = <T extends Record<string, unknown>>(fallback: T, override?: Partial<T>) => ({
  ...fallback,
  ...(override ?? {}),
}) as T;

const normalizeIconKey = (iconKey: string) => {
  if (iconKey === "netease" || iconKey === "netease-music") {
    return "music";
  }

  return iconKey;
};

const widthMap = {
  "max-w-2xl": "narrow",
  "max-w-3xl": "content",
  "max-w-4xl": "wide",
} as const;

const normalizeSiteConfig = (payload: Partial<BackendSiteResponse> | undefined): RuntimeSiteConfig => {
  if (!payload?.site) {
    return runtimeConfigFallback.site;
  }

  return {
    ...runtimeConfigFallback.site,
    name: payload.site.name ?? runtimeConfigFallback.site.name,
    title: payload.site.title ?? runtimeConfigFallback.site.title,
    bio: payload.site.bio ?? runtimeConfigFallback.site.bio,
    role: payload.site.role ?? runtimeConfigFallback.site.role,
    poems:
      payload.poems?.map((item) => item.content).filter(Boolean) ??
      runtimeConfigFallback.site.poems,
    socialLinks:
      payload.social_links?.map((link) => ({
        name: link.name,
        href: link.href,
        iconKey: normalizeIconKey(link.icon_key) as RuntimeSiteConfig["socialLinks"][number]["iconKey"],
      })) ?? runtimeConfigFallback.site.socialLinks,
    footer: {
      ...runtimeConfigFallback.site.footer,
      slogan: payload.site.footer_text ?? runtimeConfigFallback.site.footer.slogan,
    },
  };
};

const normalizePagesConfig = (payload: Partial<BackendPagesResponse> | undefined): RuntimePageConfig => {
  if (!payload?.items?.length) {
    return runtimeConfigFallback.pages;
  }

  const next = { ...runtimeConfigFallback.pages };

  payload.items.forEach((item) => {
    if (!(item.page_key in next)) {
      return;
    }

    const current = next[item.page_key];
    const widthFromApi =
      item.max_width && item.max_width in widthMap
        ? widthMap[item.max_width as keyof typeof widthMap]
        : current.width;

    next[item.page_key] = {
      ...current,
      title: item.title ?? current.title,
      subtitle: item.subtitle ?? current.subtitle,
      description: item.description ?? current.description,
      searchPlaceholder: item.search_placeholder ?? current.searchPlaceholder,
      emptyMessage: item.empty_message ?? current.emptyMessage,
      width: widthFromApi,
      pageSize: item.page_size ?? current.pageSize,
      downloadLabel: item.download_label ?? current.downloadLabel,
      categories: {
        ...("categories" in current ? current.categories : {}),
        all:
          (item.extras?.category_all_label as string | undefined) ??
          ("categories" in current ? current.categories?.all : undefined) ??
          pageConfig.posts.categories.all,
      },
      circleTitle:
        (item.extras?.circle_title as string | undefined) ??
        ("circleTitle" in current ? current.circleTitle : undefined),
    };
  });

  return next;
};

const normalizeResumeConfig = (payload: Partial<BackendResumeResponse> | undefined) => {
  if (!payload) {
    return runtimeConfigFallback.pages.resume;
  }

  return {
    ...runtimeConfigFallback.pages.resume,
    title: payload.title ?? runtimeConfigFallback.pages.resume.title,
    description: payload.summary ?? runtimeConfigFallback.pages.resume.description,
    downloadLabel: payload.download_label ?? runtimeConfigFallback.pages.resume.downloadLabel,
    bio: payload.summary ?? runtimeConfigFallback.pages.resume.bio,
    skills:
      payload.skill_groups?.flatMap((group) => group.items) ??
      runtimeConfigFallback.pages.resume.skills,
    experience:
      payload.experiences?.map((item) => ({
        role: item.title,
        org: item.company,
        period: item.period,
        desc: item.summary,
      })) ?? runtimeConfigFallback.pages.resume.experience,
  };
};

export async function loadRuntimeConfig(): Promise<RuntimeConfigSnapshot> {
  try {
    const [site, pages, resume] = await Promise.all([
      apiClient.get<BackendSiteResponse>(runtimeConfigPaths.site),
      apiClient.get<BackendPagesResponse>(runtimeConfigPaths.pages),
      apiClient.get<BackendResumeResponse>(runtimeConfigPaths.resume),
    ]);

    const normalizedPages = normalizePagesConfig(pages);
    normalizedPages.resume = normalizeResumeConfig(resume);

    return {
      site: normalizeSiteConfig(site),
      pages: normalizedPages,
      source: "remote",
      fetchedAt: new Date().toISOString(),
    };
  } catch {
    return {
      site: runtimeConfigFallback.site,
      pages: runtimeConfigFallback.pages,
      source: "fallback",
      fetchedAt: new Date().toISOString(),
    };
  }
}
