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

const PageMeta = ({
  title,
  description,
  image,
}: PageMetaProps) => {
  const site = useSiteConfig();
  const resolvedDescription = description ?? site.metaDescription;
  const resolvedImage = image ?? site.ogImage;

  useEffect(() => {
    document.title = buildPageTitle(site.name, title);

    setMeta('meta[name="description"]', resolvedDescription);
    setMeta('meta[name="author"]', site.author);
    setMeta('meta[property="og:title"]', buildPageTitle(site.name, title));
    setMeta('meta[property="og:description"]', resolvedDescription);
    setMeta('meta[property="og:image"]', resolvedImage);
    setMeta('meta[property="og:site_name"]', site.name);
    setMeta('meta[name="twitter:title"]', buildPageTitle(site.name, title));
    setMeta('meta[name="twitter:description"]', resolvedDescription);
    setMeta('meta[name="twitter:image"]', resolvedImage);
  }, [resolvedDescription, resolvedImage, title, site]);

  return null;
};

export default PageMeta;
