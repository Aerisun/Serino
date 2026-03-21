export const SITE_NAME = "Felix";
export const SITE_TITLE = "Felix · 个人网站";
export const SITE_DESCRIPTION =
  "Felix 的个人网站，收纳网页设计、前端、写作与生活记录。";
export const SITE_AUTHOR = "Felix";
export const SITE_OG_IMAGE = "/images/hero_bg.jpeg";

export const buildPageTitle = (pageTitle?: string) =>
  pageTitle ? `${pageTitle} · ${SITE_NAME}` : SITE_TITLE;
