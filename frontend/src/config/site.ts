export type SiteIconKey = string;
export type SiteSocialPlacement = "hero" | "footer" | "both";

export interface SiteNavChild {
  label: string;
  href: string;
}

export interface SiteNavItem {
  label: string;
  trigger: "hover" | "arrow" | "none";
  href?: string;
  children?: SiteNavChild[];
}

export interface SiteSocialLink {
  name: string;
  href: string;
  iconKey: SiteIconKey;
  placement: SiteSocialPlacement;
}

export interface SiteActionLink {
  label: string;
  href: string;
  iconKey: SiteIconKey;
}

export interface SiteConfig {
  name: string;
  title: string;
  description: string;
  bio: string;
  role: string;
  ogImage: string;
  poems: string[];
  poemSource: "custom" | "hitokoto";
  poemHitokotoTypes: string[];
  poemHitokotoKeywords: string[];
  socialLinks: SiteSocialLink[];
  heroActions: SiteActionLink[];
  navigation: SiteNavItem[];
  footer: {
    since: number;
    filingInfo: string;
  };
}

export const buildPageTitle = (siteName: string, pageTitle?: string): string =>
  pageTitle ? `${pageTitle} · ${siteName}` : siteName;
