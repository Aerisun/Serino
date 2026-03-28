import { useEffect } from "react";
import { buildPageTitle } from "@/config";
import { useSiteConfig } from "@/contexts/runtime-config";

interface PageMetaProps {
  title?: string;
  description?: string;
  image?: string;
}

const setMeta = (selector: string, value: string, attr = "content") => {
  const element = document.head.querySelector<HTMLMetaElement>(selector);
  if (element) {
    element.setAttribute(attr, value);
  }
};

const ensureHeadLink = (rel: string, fallbackHref: string) => {
  let element = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!element) {
    element = document.createElement("link");
    element.rel = rel;
    element.href = fallbackHref;
    document.head.appendChild(element);
  }
  return element;
};

const PageMeta = ({
  title,
  description,
  image,
}: PageMetaProps) => {
  const site = useSiteConfig();
  const resolvedDescription = description ?? site.metaDescription;
  const resolvedImage = image ?? site.ogImage;
  const resolvedSiteTitle = site.title || site.name;
  const resolvedPageTitle = buildPageTitle(resolvedSiteTitle, title);

  useEffect(() => {
    document.title = resolvedPageTitle;

    setMeta('meta[name="description"]', resolvedDescription);
    setMeta('meta[name="author"]', site.author);
    setMeta('meta[property="og:title"]', resolvedPageTitle);
    setMeta('meta[property="og:description"]', resolvedDescription);
    setMeta('meta[property="og:image"]', resolvedImage);
    setMeta('meta[property="og:site_name"]', resolvedSiteTitle);
    setMeta('meta[property="og:url"]', site.canonicalUrl);
    setMeta('meta[name="twitter:title"]', resolvedPageTitle);
    setMeta('meta[name="twitter:description"]', resolvedDescription);
    setMeta('meta[name="twitter:image"]', resolvedImage);
    const resolvedIcon = site.siteIconUrl || "/favicon.svg";
    ensureHeadLink("icon", "/favicon.svg").href = resolvedIcon;
    ensureHeadLink("shortcut icon", "/favicon.ico").href = resolvedIcon;
    ensureHeadLink("canonical", site.canonicalUrl).href = site.canonicalUrl;
  }, [resolvedDescription, resolvedImage, resolvedPageTitle, resolvedSiteTitle, site.author, site.canonicalUrl, site.siteIconUrl]);

  return null;
};

export default PageMeta;
