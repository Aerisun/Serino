import { type ReactNode } from "react";
import { motion } from "motion/react";
import Navbar from "@/components/Navbar";
import Footer from "@/components/Footer";
import FallingPetals from "@/components/FallingPetals";
import PageMeta from "@/components/PageMeta";
import { pageEntrance } from "@/config";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

interface PageShellProps {
  eyebrow: string;
  title: string;
  description: string;
  metaTitle?: string;
  metaDescription?: string;
  children: ReactNode;
  headerAside?: ReactNode;
  width?: "narrow" | "content" | "wide";
  contentClassName?: string;
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
  children,
  headerAside,
  width = "content",
  contentClassName = "mt-10",
}: PageShellProps) => {
  const prefersReducedMotion = useReducedMotionPreference();
  const entrance = pageEntrance(prefersReducedMotion);

  return (
    <div className="relative min-h-screen overflow-hidden bg-background text-foreground">
      <PageMeta title={metaTitle ?? title} description={metaDescription ?? description} />
      <FallingPetals />

      <div className="pointer-events-none absolute inset-x-0 top-0 h-[440px]">
        <div className="absolute inset-x-[-8%] top-[-7rem] h-[20rem] rounded-full bg-[radial-gradient(circle_at_center,rgba(133,182,255,0.16),transparent_62%)] dark:bg-[radial-gradient(circle_at_center,rgba(180,210,255,0.12),transparent_60%)]" />
      </div>

      <Navbar />

      <main className={`${widths[width]} relative mx-auto px-6 pt-28 pb-20 lg:px-8`}>
        <motion.header
          className="relative pb-8"
          {...entrance}
        >
          <div className="pointer-events-none absolute -left-10 top-0 h-24 w-32 bg-[radial-gradient(circle_at_center,rgba(143,190,255,0.16),transparent_70%)] dark:bg-[radial-gradient(circle_at_center,rgba(143,190,255,0.10),transparent_72%)]" />

          <div className="relative flex flex-col gap-6 md:flex-row md:items-end md:justify-between">
            <div className="max-w-2xl">
              <p className="text-[11px] uppercase tracking-[0.28em] text-foreground/28">
                {eyebrow}
              </p>
              <h1 className="mt-3 text-3xl font-heading italic tracking-tight text-foreground sm:text-4xl">
                {title}
              </h1>
              <p className="mt-3 max-w-xl text-sm leading-7 text-foreground/42 sm:text-[0.95rem]">
                {description}
              </p>
            </div>

            {headerAside ? (
              <div className="relative flex shrink-0 items-start text-sm text-foreground/28 md:items-end">
                {headerAside}
              </div>
            ) : null}
          </div>
        </motion.header>

        <div className={contentClassName}>{children}</div>
      </main>

      <Footer />
    </div>
  );
};

export default PageShell;
