import { useMemo } from "react";
import { ArrowUpRight, Monitor, Moon, Rss, Sun } from "lucide-react";
import { useReadActivityHeatmapApiV1SiteActivityHeatmapGet } from "@serino/api-client/site";
import { useTheme } from "@serino/theme";
import { useSiteConfig } from "@/contexts/runtime-config";
import { useFrontendI18n } from "@/i18n";
import { SocialIcon } from "@/components/icons/SocialIcon";

const parseLocalDate = (value: string) => {
  const [year, month, day] = value.split("-").map(Number);
  return new Date(year, (month || 1) - 1, day || 1);
};

const themeIcons = {
  light: Sun,
  dark: Moon,
  system: Monitor,
} as const;

const Footer = () => {
  const site = useSiteConfig();
  const { t } = useFrontendI18n();
  const { theme, setTheme } = useTheme();
  const { data: heatmapResponse } = useReadActivityHeatmapApiV1SiteActivityHeatmapGet({
    weeks: 52,
    tz: "Asia/Shanghai",
  });

  const ownerName = site.name.trim() || site.title.trim() || "Aerisun";
  const filingText = site.footer.filingInfo.trim();
  const footerSocialLinks = site.socialLinks.filter((link) => link.placement === "footer" || link.placement === "both");
  const ThemeIcon = themeIcons[theme];

  const copyrightYears = useMemo(() => {
    const weeks = heatmapResponse?.data?.weeks ?? [];
    if (weeks.length === 0) {
      return String(new Date().getFullYear());
    }

    const startDate = parseLocalDate(weeks[0].week_start);
    const endDate = parseLocalDate(weeks[weeks.length - 1].week_start);
    endDate.setDate(endDate.getDate() + 6);

    const startYear = startDate.getFullYear();
    const endYear = endDate.getFullYear();
    return startYear === endYear ? String(endYear) : `${startYear} - ${endYear}`;
  }, [heatmapResponse?.data?.weeks]);

  return (
    <footer className="mt-16 w-full">
      <div className="mx-auto max-w-6xl px-6 lg:px-16">
        <div className="border-t border-[rgb(var(--shiro-divider-rgb)/0.28)] py-5">
          <div className="flex max-w-6xl flex-col gap-2 text-[0.78rem] leading-5">
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
              <p className="flex flex-wrap items-center gap-x-1.5 gap-y-0.5 text-[0.9rem] font-medium text-foreground/46">
                <span>{`© ${copyrightYears}`}</span>
                <span className="text-foreground/18">·</span>
                <span>{ownerName}</span>
                {filingText ? (
                  <>
                    <span className="mx-0.5 text-foreground/20">|</span>
                    <span>{filingText}</span>
                  </>
                ) : null}
              </p>

              {footerSocialLinks.length > 0 ? (
                <div className="flex flex-wrap items-center gap-3 sm:justify-end">
                  {footerSocialLinks.map((link) => (
                    <a
                      key={`${link.name}-${link.href}`}
                      href={link.href}
                      target="_blank"
                      rel="noopener noreferrer"
                      aria-label={link.name}
                      className="shiro-focus-ring inline-flex h-5 w-5 items-center justify-center rounded-full text-foreground/34 no-underline transition-[color,background-color,transform] duration-200 hover:-translate-y-0.5 hover:bg-[rgb(var(--shiro-panel-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
                    >
                      <SocialIcon iconKey={link.iconKey} className="h-3.5 w-3.5" />
                    </a>
                  ))}
                </div>
              ) : null}
            </div>

            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between sm:gap-6">
              <p className="flex min-w-0 flex-wrap items-center gap-x-1.5 gap-y-0.5 text-foreground/28">
                <span>{t("footer.poweredBy")}</span>
                <a
                  href="https://github.com/Aerisun/Serino"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={t("footer.githubRepoAria")}
                  className="shiro-focus-ring inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-foreground/28 no-underline transition-[color,background-color,transform] duration-200 hover:-translate-y-0.5 hover:bg-[rgb(var(--shiro-panel-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
                >
                  <ArrowUpRight className="h-2.75 w-2.75" strokeWidth={1.8} />
                </a>
              </p>

              <div className="flex items-center gap-2 sm:justify-end">
                <button
                  type="button"
                  onClick={() => {
                    const cycle = ["light", "dark", "system"] as const;
                    const index = cycle.indexOf(theme);
                    setTheme(cycle[(index + 1) % cycle.length]);
                  }}
                  className="shiro-focus-ring inline-flex h-5 w-5 items-center justify-center rounded-full text-foreground/30 transition-[color,background-color,transform] duration-200 hover:-translate-y-0.5 hover:bg-[rgb(var(--shiro-panel-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
                  aria-label={t("common.themeToggle")}
                >
                  <ThemeIcon className="h-3.25 w-3.25" strokeWidth={1.8} />
                </button>

                <a
                  href="/rss.xml"
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={t("footer.rssAria")}
                  className="shiro-focus-ring inline-flex h-5 w-5 items-center justify-center rounded-full text-foreground/30 no-underline transition-[color,background-color,transform] duration-200 hover:-translate-y-0.5 hover:bg-[rgb(var(--shiro-panel-rgb)/0.24)] hover:text-[rgb(var(--shiro-accent-rgb)/0.82)]"
                >
                  <Rss className="h-3.25 w-3.25" strokeWidth={1.8} />
                </a>
              </div>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
