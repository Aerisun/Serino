import { useEffect } from "react";
import {
  SITE_AUTHOR,
  SITE_DESCRIPTION,
  SITE_NAME,
  SITE_OG_IMAGE,
  buildPageTitle,
} from "@/config/site";

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
  description = SITE_DESCRIPTION,
  image = SITE_OG_IMAGE,
}: PageMetaProps) => {
  useEffect(() => {
    document.title = buildPageTitle(title);

    setMeta('meta[name="description"]', description);
    setMeta('meta[name="author"]', SITE_AUTHOR);
    setMeta('meta[property="og:title"]', buildPageTitle(title));
    setMeta('meta[property="og:description"]', description);
    setMeta('meta[property="og:image"]', image);
    setMeta('meta[property="og:site_name"]', SITE_NAME);
    setMeta('meta[name="twitter:title"]', buildPageTitle(title));
    setMeta('meta[name="twitter:description"]', description);
    setMeta('meta[name="twitter:image"]', image);
  }, [description, image, title]);

  return null;
};

export default PageMeta;
