import { useEffect, useMemo } from "react";
import { useSiteConfig } from "@/contexts/runtime-config";
import { buildSearchMetadata } from "@/lib/search-optimization";

interface PageMetaProps {
  title?: string;
  description?: string;
  image?: string;
  author?: string;
}

const SITE_JSON_LD_SCRIPT_ID = "json-ld-site-profile";

const ensureMeta = (
  selector: string,
  attributes: Record<string, string>,
) => {
  let element = document.head.querySelector<HTMLMetaElement>(selector);
  if (!element) {
    element = document.createElement("meta");
    for (const [key, value] of Object.entries(attributes)) {
      element.setAttribute(key, value);
    }
    document.head.appendChild(element);
  }
  return element;
};

const syncMeta = (
  selector: string,
  attributes: Record<string, string>,
  value: string,
) => {
  const normalizedValue = value.trim();
  const existing = document.head.querySelector<HTMLMetaElement>(selector);

  if (!normalizedValue) {
    existing?.remove();
    return;
  }

  ensureMeta(selector, attributes).setAttribute("content", normalizedValue);
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

const syncSiteJsonLd = (payload: Record<string, unknown>) => {
  let script = document.getElementById(SITE_JSON_LD_SCRIPT_ID) as HTMLScriptElement | null;
  if (!script) {
    script = document.createElement("script");
    script.id = SITE_JSON_LD_SCRIPT_ID;
    script.type = "application/ld+json";
    document.head.appendChild(script);
  }
  script.textContent = JSON.stringify(payload);
};

const PageMeta = ({
  title,
  description,
  image,
  author,
}: PageMetaProps) => {
  const site = useSiteConfig();
  const pathname = typeof window !== "undefined" ? window.location.pathname : "/";
  const metadata = useMemo(
    () =>
      buildSearchMetadata({
        site,
        searchOptimization: site.searchOptimization,
        pageTitle: title,
        pageDescription: description,
        pageImage: image,
        pageAuthor: author,
        pathname,
      }),
    [author, description, image, pathname, site, title],
  );

  useEffect(() => {
    document.title = metadata.title;

    syncMeta('meta[name="description"]', { name: "description" }, metadata.description);
    syncMeta('meta[name="author"]', { name: "author" }, metadata.author);
    syncMeta('meta[name="keywords"]', { name: "keywords" }, metadata.keywords);
    syncMeta('meta[name="robots"]', { name: "robots" }, metadata.robots);
    syncMeta('meta[name="title"]', { name: "title" }, metadata.shareTitle);
    syncMeta('meta[property="og:title"]', { property: "og:title" }, metadata.shareTitle);
    syncMeta('meta[property="og:description"]', { property: "og:description" }, metadata.description);
    syncMeta('meta[property="og:image"]', { property: "og:image" }, metadata.image);
    syncMeta('meta[property="og:site_name"]', { property: "og:site_name" }, metadata.siteTitle);
    syncMeta('meta[name="twitter:title"]', { name: "twitter:title" }, metadata.shareTitle);
    syncMeta('meta[name="twitter:description"]', { name: "twitter:description" }, metadata.description);
    syncMeta('meta[name="twitter:image"]', { name: "twitter:image" }, metadata.image);
    syncHeadLink("canonical", metadata.canonicalUrl);
    syncSiteJsonLd(metadata.siteJsonLd);
    const resolvedIcon = site.siteIconUrl || "data:,";
    syncHeadLink("icon", resolvedIcon);
    syncHeadLink("shortcut icon", resolvedIcon);
  }, [metadata, site.siteIconUrl]);

  return null;
};

export default PageMeta;
