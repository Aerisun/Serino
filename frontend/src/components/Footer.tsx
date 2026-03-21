const Footer = () => {
  const currentYear = new Date().getFullYear();

  return (
    <footer className="w-full border-t border-foreground/[0.06] bg-background">
      <div className="max-w-6xl mx-auto px-8 lg:px-16 py-10">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          {/* Left — copyright */}
          <p className="text-xs font-body text-foreground/25">
            © {currentYear} Felix · All rights reserved
          </p>

          {/* Center — links */}
          <div className="flex items-center gap-5">
            {[
              { label: "GitHub", href: "https://github.com" },
              { label: "Telegram", href: "https://t.me" },
              { label: "X", href: "https://x.com" },
            ].map((link) => (
              <a
                key={link.label}
                href={link.href}
                target="_blank"
                rel="noopener noreferrer"
                className="text-xs font-body text-foreground/25 hover:text-foreground/50 transition-colors"
              >
                {link.label}
              </a>
            ))}
          </div>

          {/* Right — heartbeat */}
          <p className="text-xs font-body text-foreground/20">
            用 ♥ 与代码构建
          </p>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
