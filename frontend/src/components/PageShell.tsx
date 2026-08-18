import { type ReactNode } from "react";
import { motion } from "motion/react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";
import BackToTop from "@/components/BackToTop";
import PageMeta from "@/components/PageMeta";
import { pageEntrance } from "@/config";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

interface PageShellProps {
  eyebrow: string;
  title: string;
  description: string;
  metaTitle?: string;
  metaDescription?: string;
  metaAuthor?: string;
  metaType?: "website" | "article" | "profile";
  noIndex?: boolean;
  children: ReactNode;
  headerAside?: ReactNode;
  headerAsideClassName?: string;
  width?: "narrow" | "content" | "wide";
  contentClassName?: string;
  mainClassName?: string;
  footerClassName?: string;
  compactHeader?: boolean;
}

const widths = {
  narrow: "max-w-2xl",
  content: "max-w-3xl",
  wide: "max-w-4xl",
};

const PageShell = ({
  eyebrow,
  title,
  description,
  metaTitle,
  metaDescription,
  metaAuthor,
  metaType = "website",
  noIndex = false,
  children,
  headerAside,
  headerAsideClassName = "",
  width = "content",
  contentClassName = "mt-5 sm:mt-10",
  mainClassName = "",
  footerClassName = "",
  compactHeader = false,
}: PageShellProps) => {
  const prefersReducedMotion = useReducedMotionPreference();
  const entrance = pageEntrance(prefersReducedMotion);
  const hasHeader = Boolean(eyebrow || title || description || headerAside);

  return (
    <>
      <Navbar />
      <div className="relative flex min-h-screen min-h-[100dvh] flex-col overflow-hidden bg-background text-foreground">
        <PageMeta
          title={metaTitle ?? title}
          description={metaDescription ?? description}
          author={metaAuthor}
          type={metaType}
          noIndex={noIndex}
        />
        <FallingPetals />

        <div className="pointer-events-none absolute inset-x-0 top-0 h-[440px]">
          <div
            className="absolute inset-x-[-8%] top-[-7rem] h-[20rem] rounded-full"
            style={{
              background:
                "radial-gradient(circle at center, rgb(var(--shiro-glow-rgb) / 0.12) 0%, transparent 64%)",
            }}
          />
        </div>

        <main className={`${widths[width]} relative mx-auto w-full flex-1 px-6 ${compactHeader ? "pt-20 pb-20 sm:pt-24" : "pt-24 pb-20 sm:pt-28"} lg:px-8 ${mainClassName}`.trim()}>
          {hasHeader ? (
            <motion.header
              className={`relative ${compactHeader ? "pb-3 sm:pb-4" : "pb-4 sm:pb-8"}`}
              {...entrance}
            >
              <div
                className="pointer-events-none absolute -left-10 top-0 h-24 w-32"
                style={{
                  background:
                    "radial-gradient(circle at center, rgb(var(--shiro-glow-rgb) / 0.1) 0%, transparent 72%)",
                }}
              />

              <div className={`relative flex flex-col ${compactHeader ? "gap-2" : "gap-6"} md:flex-row md:items-end md:justify-between`}>
                <div className="max-w-2xl">
                  {eyebrow ? (
                    <div className="inline-flex items-center gap-2.5">
                      <span
                        className="h-1.5 w-1.5 rounded-full"
                        style={{
                          backgroundColor: "rgb(var(--shiro-accent-rgb) / 0.56)",
                          boxShadow: "0 0 16px rgb(var(--shiro-glow-rgb) / 0.16)",
                        }}
                      />
                      <p className="text-[11px] uppercase tracking-[0.28em] text-foreground/34">
                        {eyebrow}
                      </p>
                    </div>
                  ) : null}
                  {title ? (
                    <h1 className={`${eyebrow ? "mt-4" : "mt-0"} text-3xl font-heading italic tracking-tight text-foreground sm:text-4xl`}>
                      {title}
                    </h1>
                  ) : null}
                  {description ? (
                    <p className="mt-3 max-w-xl text-sm leading-7 text-foreground/42 sm:text-[0.95rem]">
                      {description}
                    </p>
                  ) : null}
                </div>

                {headerAside ? (
                  <div className={`relative flex shrink-0 items-start text-sm text-foreground/28 md:items-end ${headerAsideClassName}`.trim()}>
                    {headerAside}
                  </div>
                ) : null}
              </div>
            </motion.header>
          ) : null}

          <div className={contentClassName}>{children}</div>
        </main>

        <BackToTop />
        <Footer className={footerClassName} />
      </div>
    </>
  );
};

export default PageShell;
