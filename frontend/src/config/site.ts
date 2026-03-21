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

export const siteConfig: SiteConfig = {
  name: "Felix",
  title: "Felix · 个人网站",
  description: "Felix 的个人网站，收纳网页设计、前端、写作与生活记录。",
  bio: "我做网页设计，也写前端，把视觉、节奏、内容和交互整理成一个自然流动的个人空间。",
  role: "UI/UX Designer · Frontend Developer",
  author: "Felix",
  ogImage: "/images/hero_bg.jpeg",
  poems: [
    "山有木兮木有枝，心悦君兮君不知。",
    "人生若只如初见，何事秋风悲画扇。",
    "曾经沧海难为水，除却巫山不是云。",
    "落霞与孤鹜齐飞，秋水共长天一色。",
    "行到水穷处，坐看云起时。",
    "采菊东篱下，悠然见南山。",
    "大漠孤烟直，长河落日圆。",
    "海内存知己，天涯若比邻。",
    "长风破浪会有时，直挂云帆济沧海。",
    "但愿人长久，千里共婵娟。",
    "世事一场大梦，人生几度秋凉。",
    "浮生若梦，为欢几何。",
  ],
  socialLinks: [
    { name: "GitHub", href: "https://github.com", iconKey: "github" },
    { name: "Telegram", href: "https://t.me", iconKey: "telegram" },
    { name: "X", href: "https://x.com", iconKey: "x" },
    { name: "网易云音乐", href: "https://music.163.com", iconKey: "music" },
  ],
  heroActions: [
    { label: "简历", href: "/resume", iconKey: "resume" },
    { label: "留言板", href: "/guestbook", iconKey: "guestbook" },
  ],
  navigation: [
    {
      label: "首页",
      trigger: "arrow",
      href: "/",
      children: [
        { label: "简历", href: "/resume" },
        { label: "留言板", href: "/guestbook" },
        { label: "日历", href: "/calendar" },
      ],
    },
    { label: "帖子", trigger: "none", href: "/posts" },
    { label: "友链", trigger: "none", href: "/friends" },
    {
      label: "更多",
      trigger: "hover",
      children: [
        { label: "碎碎念", href: "/thoughts" },
        { label: "日记", href: "/diary" },
        { label: "文摘", href: "/excerpts" },
      ],
    },
  ],
  footer: {
    since: 2024,
    copyright: "All rights reserved",
    slogan: "用 ♥ 与代码构建",
  },
};

export const SITE_NAME = siteConfig.name;
export const SITE_TITLE = siteConfig.title;
export const SITE_DESCRIPTION = siteConfig.description;
export const SITE_AUTHOR = siteConfig.author;
export const SITE_OG_IMAGE = siteConfig.ogImage;

export const buildPageTitle = (pageTitle?: string) =>
  pageTitle ? `${pageTitle} · ${siteConfig.name}` : siteConfig.title;
