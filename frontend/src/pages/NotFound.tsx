import { useLocation, Link } from "react-router-dom";
import { motion } from "motion/react";
import { ArrowLeft, Home, Sparkles } from "lucide-react";
import PageMeta from "@/components/PageMeta";
import { usePageConfig } from "@/contexts/runtime-config";

const NotFound = () => {
  const location = useLocation();
  const config = (usePageConfig().notFound as Record<string, unknown> | undefined) ?? {};

  return (
    <div className="relative flex min-h-screen items-center justify-center overflow-hidden bg-background px-6 text-foreground">
      <PageMeta
        title={String(config.metaTitle ?? config.title ?? "")}
        description={String(config.metaDescription ?? config.description ?? "")}
      />
      <div
        className="absolute inset-0 opacity-70"
        aria-hidden="true"
        style={{
          background:
            "radial-gradient(circle at 20% 20%, hsla(213,45%,55%,0.12) 0%, transparent 32%), radial-gradient(circle at 80% 30%, hsla(18,70%,75%,0.16) 0%, transparent 26%), radial-gradient(circle at 50% 90%, hsla(0,0%,100%,0.35) 0%, transparent 30%)",
        }}
      />

      <div className="absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-background to-transparent" aria-hidden="true" />

      <motion.div
        className="relative w-full max-w-xl liquid-glass rounded-[2rem] border border-foreground/5 p-8 shadow-[0_24px_80px_rgba(0,0,0,0.08)] sm:p-10"
        initial={{ opacity: 0, y: 14, scale: 0.98 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
      >
        <div className="flex items-center gap-2 text-[10px] uppercase tracking-[0.28em] text-foreground/25">
          <Sparkles className="h-3.5 w-3.5" />
          <span>Shell mismatch</span>
        </div>

        <div className="mt-6 flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.3em] text-foreground/25">404</p>
            <h1 className="mt-2 text-3xl font-heading italic tracking-tight text-foreground sm:text-4xl">
              {String(config.title ?? "")}
            </h1>
          </div>
          <p className="max-w-sm text-sm leading-7 text-foreground/45">
            你访问的路径{" "}
            <span className="rounded-md border border-foreground/10 bg-foreground/[0.04] px-1.5 py-0.5 font-mono text-[0.8em] text-foreground/70">
              {location.pathname}
            </span>{" "}
            {String(config.description ?? "")}
          </p>
        </div>

        <div className="mt-8 flex flex-col gap-3 sm:flex-row">
          <Link
            to="/"
            className="inline-flex items-center justify-center gap-2 rounded-full bg-foreground px-5 py-2.5 text-sm font-medium text-background transition-transform active:scale-[0.98]"
          >
            <Home className="h-4 w-4" />
            返回首页
          </Link>
          <button
            type="button"
            onClick={() => {
              if (window.history.length > 1) {
                window.history.back();
                return;
              }

              window.location.assign("/");
            }}
            className="inline-flex items-center justify-center gap-2 rounded-full liquid-glass px-5 py-2.5 text-sm font-medium text-foreground/70 transition-colors hover:text-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
            返回上页
          </button>
        </div>
      </motion.div>
    </div>
  );
};

export default NotFound;
