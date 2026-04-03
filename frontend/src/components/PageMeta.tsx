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

const ensureHeadLink = (rel: string) => {
  let element = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);
  if (!element) {
    element = document.createElement("link");
    element.rel = rel;
    document.head.appendChild(element);
  }
  return element;
};

const syncHeadLink = (rel: string, href: string) => {
  const normalizedHref = href.trim();
  const existing = document.head.querySelector<HTMLLinkElement>(`link[rel="${rel}"]`);

  if (!normalizedHref) {
    existing?.remove();
    return;
  }

  ensureHeadLink(rel).href = normalizedHref;
};

const PageMeta = ({
  title,
  description,
  image,
}: PageMetaProps) => {
  const site = useSiteConfig();
  const resolvedDescription = description ?? site.bio;
  const resolvedImage = image ?? site.ogImage;
  const resolvedSiteTitle = site.title || site.name;
  const resolvedAuthor = site.name || site.title;
  const resolvedPageTitle = buildPageTitle(resolvedSiteTitle, title);

  useEffect(() => {
    document.title = resolvedPageTitle;

    setMeta('meta[name="description"]', resolvedDescription);
    setMeta('meta[name="author"]', resolvedAuthor);
    setMeta('meta[property="og:title"]', resolvedPageTitle);
    setMeta('meta[property="og:description"]', resolvedDescription);
    setMeta('meta[property="og:image"]', resolvedImage);
    setMeta('meta[property="og:site_name"]', resolvedSiteTitle);
    setMeta('meta[name="twitter:title"]', resolvedPageTitle);
    setMeta('meta[name="twitter:description"]', resolvedDescription);
    setMeta('meta[name="twitter:image"]', resolvedImage);
    const resolvedIcon = site.siteIconUrl || "";
    syncHeadLink("icon", resolvedIcon);
    syncHeadLink("shortcut icon", resolvedIcon);
  }, [resolvedAuthor, resolvedDescription, resolvedImage, resolvedPageTitle, resolvedSiteTitle, site.siteIconUrl]);

  return null;
};

export default PageMeta;
