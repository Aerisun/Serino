export type SiteIconKey =
  | "github"
  | "telegram"
  | "x"
  | "music"
  | "resume"
  | "guestbook"
  | "calendar";

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
  author: string;
  ogImage: string;
  poems: string[];
  socialLinks: SiteSocialLink[];
  heroActions: SiteActionLink[];
  navigation: SiteNavItem[];
  footer: {
    since: number;
    copyright: string;
    slogan: string;
  };
}

export const buildPageTitle = (siteName: string, pageTitle?: string): string =>
  pageTitle ? `${pageTitle} · ${siteName}` : siteName;
