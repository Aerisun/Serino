import { siteConfig } from "@/config";

const Footer = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="w-full border-t border-foreground/[0.06] bg-background">
      <div className="max-w-6xl mx-auto px-8 lg:px-16 py-10">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <p className="text-xs font-body text-foreground/25">
            © {currentYear} {siteConfig.name} · {siteConfig.footer.copyright}
          </p>

          <div className="flex items-center gap-5">
            {siteConfig.socialLinks.map((link) => (
              <a
                key={link.name}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-body text-foreground/25 hover:text-foreground/50 transition-colors"
              >
                {link.name}
              </a>
            ))}
          </div>

          <p className="text-xs font-body text-foreground/20">{siteConfig.footer.slogan}</p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
