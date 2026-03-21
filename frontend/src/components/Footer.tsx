import { Link } from "react-router-dom";
import { siteConfig } from "@/config";

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

const internalLinks = dedupeByHref([
  ...siteConfig.navigation.flatMap((item) =>
    item.href ? [{ label: item.label, href: item.href }] : []
  ),
  ...siteConfig.navigation.flatMap((item) => item.children ?? []),
  ...siteConfig.heroActions.map((item) => ({ label: item.label, href: item.href })),
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

const renderSocialIcon = (iconKey: string) => {
  switch (iconKey) {
    case "github":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
          <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
        </svg>
      );
    case "telegram":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
          <path d="M11.944 0A12 12 0 000 12a12 12 0 0012 12 12 12 0 0012-12A12 12 0 0012 0a12 12 0 00-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 01.171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
        </svg>
      );
    case "x":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
          <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
        </svg>
      );
    case "music":
      return (
        <svg viewBox="0 0 24 24" fill="currentColor" className="h-4 w-4">
          <path d="M12 0C5.372 0 0 5.372 0 12s5.372 12 12 12 12-5.372 12-12S18.628 0 12 0zm5.92 17.108c-.745 1.222-1.86 2.068-3.327 2.528-1.378.43-2.71.404-3.996-.08a5.07 5.07 0 01-2.715-2.244c-.674-1.166-.796-2.418-.364-3.746.336-1.032.893-1.907 1.671-2.62.81-.742 1.756-1.207 2.834-1.393.332-.058.666-.076 1-.054.51.034.924.267 1.242.684.318.418.45.895.394 1.43a2.38 2.38 0 01-.564 1.282c-.37.436-.856.7-1.46.792-.39.06-.773.032-1.15-.084a1.474 1.474 0 01-.923-.782c-.11-.228-.15-.472-.122-.73.04-.356.186-.654.44-.894.046-.044.094-.086.144-.126l.11-.086c.07-.05.078-.09.024-.12-.12-.066-.252-.078-.396-.034-.36.11-.648.336-.864.678-.328.52-.408 1.08-.24 1.682.2.718.626 1.24 1.278 1.566.754.378 1.548.434 2.382.17a3.823 3.823 0 002.172-1.75c.43-.796.572-1.648.424-2.554-.19-1.174-.74-2.138-1.648-2.89a5.1 5.1 0 00-2.83-1.188c-1.136-.134-2.216.05-3.242.55-1.322.646-2.27 1.636-2.842 2.97-.442 1.028-.58 2.1-.416 3.216.21 1.42.848 2.614 1.912 3.582 1.128 1.028 2.47 1.598 4.024 1.712.37.028.74.018 1.11-.028.168-.02.266.044.294.192.018.1-.02.178-.114.234-.118.07-.248.112-.388.124-.64.058-1.274.04-1.9-.054z" />
        </svg>
      );
    default:
      return null;
  }
};

const Footer = () => {
  const currentYear = new Date().getFullYear();
  const yearLabel =
    siteConfig.footer.since < currentYear
      ? `© ${siteConfig.footer.since}-${currentYear}`
      : `© ${currentYear}`;

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
                    {siteConfig.name}
                  </span>
                  <span className="mt-1 text-[11px] uppercase tracking-[0.24em] text-foreground/30">
                    {siteConfig.role}
                  </span>
                </Link>

                <p className="mt-3 max-w-2xl text-sm leading-6 text-foreground/42">
                  {siteConfig.description}
                </p>
              </div>

              <div className="flex items-center gap-1 sm:shrink-0">
                {siteConfig.socialLinks.map((link) => {
                  const icon = renderSocialIcon(link.iconKey);

                  return (
                    <a
                      key={link.name}
                      href={link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={link.name}
                      className="inline-flex h-10 w-10 items-center justify-center rounded-full text-foreground/46 transition-colors duration-200 hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-foreground/20 focus-visible:ring-offset-2 focus-visible:ring-offset-background"
                    >
                      {icon ?? <span className="text-xs">{link.name}</span>}
                    </a>
                  );
                })}
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
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

              <p className="text-xs leading-6 text-foreground/34">
                <span>{yearLabel}</span>
                <span className="mx-2 text-foreground/24">·</span>
                <span>{siteConfig.name}</span>
                <span className="mx-2 text-foreground/24">·</span>
                <span>{siteConfig.footer.copyright}</span>
              </p>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
