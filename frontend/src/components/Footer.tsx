import { Link } from "react-router-dom";
import { SocialIcon } from "@/components/icons/SocialIcon";
import { useSiteConfig } from "@/contexts/RuntimeConfigContext";

interface InternalLinkItem {
  label: string;
  href: string;
}

const dedupeByHref = <T extends { href: string }>(items: T[]) =>
  Array.from(new Map(items.map((item) => [item.href, item])).values());

const pickByHref = <T extends { href: string }>(items: T[], hrefs: string[]) => {
  const itemMap = new Map(items.map((item) => [item.href, item]));
  return hrefs.flatMap((href) => {
    const item = itemMap.get(href);
    return item ? [item] : [];
  });
};

const Footer = () => {
  const site = useSiteConfig();
  const currentYear = new Date().getFullYear();
  const footerSocialLinks = site.socialLinks.filter((link) => link.placement === "footer" || link.placement === "both");

  const internalLinks = dedupeByHref([
    ...site.navigation.flatMap((item) =>
      item.href ? [{ label: item.label, href: item.href }] : []
    ),
    ...site.navigation.flatMap((item) => item.children ?? []),
    ...site.heroActions.map((item) => ({ label: item.label, href: item.href })),
  ]);

  const footerPrimaryLinks: InternalLinkItem[] = pickByHref(internalLinks, [
    "/posts",
    "/friends",
    "/thoughts",
    "/diary",
    "/excerpts",
    "/resume",
    "/guestbook",
    "/calendar",
  ]);

  return (
    <footer className="mt-20 w-full">
      <div className="mx-auto max-w-6xl px-6 lg:px-16">
        <div className="shiro-accent-divider border-t border-foreground/[0.08] py-6 sm:py-7">
          <div className="flex flex-col gap-5">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
              <div className="min-w-0">
                <Link
                  to="/"
                  className="inline-flex flex-col items-start no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                >
                  <span className="text-[1.9rem] font-heading italic tracking-tight text-foreground">
                    {site.name}
                  </span>
                  <span className="mt-1 text-[11px] uppercase tracking-[0.24em] text-foreground/30">
                    {site.role}
                  </span>
                </Link>

                <p className="mt-3 max-w-2xl text-sm leading-6 text-foreground/42">
                  {site.metaDescription || site.bio}
                </p>
              </div>

              <div className="flex items-center gap-1 sm:shrink-0">
                {footerSocialLinks.map((link) => (
                  <a
                    key={`${link.name}-${link.href}`}
                    href={link.href}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label={link.name}
                    className="inline-flex h-10 w-10 items-center justify-center rounded-full text-foreground/46 transition-colors duration-200 hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                  >
                    <SocialIcon iconKey={link.iconKey} className="h-4 w-4" />
                  </a>
                ))}
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
              <div className="flex flex-wrap items-center gap-y-2 text-sm">
                {footerPrimaryLinks.map((link, index) => (
                  <span key={link.href} className="text-foreground/48">
                    <Link
                      to={link.href}
                      className="font-medium text-foreground/72 underline decoration-foreground/18 underline-offset-4 transition-colors duration-200 hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] hover:decoration-[rgb(var(--shiro-accent-rgb)/0.3)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                    >
                      {link.label}
                    </Link>
                    {index < footerPrimaryLinks.length - 1 ? (
                      <span className="mx-2 text-foreground/24">•</span>
                    ) : null}
                  </span>
                ))}
              </div>

              <div className="text-xs leading-6 text-foreground/34 sm:text-right">
                <p>
                  <span>{`© ${currentYear}`}</span>
                  <span className="mx-2 text-foreground/24">·</span>
                  <span>{site.name}</span>
                  <span className="mx-2 text-foreground/24">·</span>
                  <span>{site.footer.copyright}</span>
                </p>
                {site.footer.slogan ? (
                  <p className="text-foreground/24">{site.footer.slogan}</p>
                ) : null}
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
