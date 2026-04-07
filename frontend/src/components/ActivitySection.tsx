import FriendCircle from "./FriendCircle";
import RecentActivity from "./RecentActivity";
import ActivityHeatmap from "./ActivityHeatmap";
import Footer from "./Footer";
import LazyOnVisible from "./LazyOnVisible";
import { usePageConfig } from "@/contexts/runtime-config";

interface ActivitySectionConfig {
  dashboardLabel?: string;
  title?: string;
}

const ActivitySection = () => {
  const config = usePageConfig().activity as ActivitySectionConfig | undefined;

  return (
    <section className="relative flex w-full flex-col overflow-hidden bg-background">
      <div
        className="pointer-events-none absolute inset-x-0 top-0 h-[520px]"
        style={{
          background:
            "radial-gradient(ellipse 60% 100% at 50% 0%, hsl(var(--shiro-accent-hsl, 220 55% 50%) / 0.08) 0%, transparent 72%)",
        }}
      />

      <div className="relative z-10 mx-auto w-full max-w-[84rem] px-6 pt-20 pb-12 lg:px-8 xl:px-10">
        <div className="mb-10">
          <p className="text-xs font-body font-medium text-foreground/25 uppercase tracking-[0.2em] mb-2">
            {config?.dashboardLabel}
          </p>
          <h2 className="text-3xl md:text-4xl font-heading italic text-foreground leading-[1.1]">
            {config?.title}
          </h2>
        </div>

        <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-12 xl:gap-14">
          <LazyOnVisible
            rootMargin="240px 0px"
            fallback={<div className="liquid-glass h-64 rounded-[2rem] p-6 md:p-8" />}
          >
            <div className="liquid-glass rounded-[2rem] p-6 md:p-8">
              <FriendCircle enabled />
            </div>
          </LazyOnVisible>

          <LazyOnVisible
            rootMargin="240px 0px"
            fallback={<div className="liquid-glass h-64 rounded-[2rem] p-6 md:p-8" />}
          >
            <div className="liquid-glass rounded-[2rem] p-6 md:p-8">
              <RecentActivity enabled />
            </div>
          </LazyOnVisible>
        </div>
      </div>

      <LazyOnVisible
        rootMargin="320px 0px"
        fallback={<div className="relative z-10 w-full px-4 pb-12 sm:px-6 lg:px-8 xl:px-10" />}
      >
        <div className="relative z-10 w-full px-4 pb-12 sm:px-6 lg:px-8 xl:px-10">
          <div className="relative mx-auto w-full max-w-[84rem] px-2 sm:px-0">
            <ActivityHeatmap enabled />
          </div>
        </div>
      </LazyOnVisible>

      <LazyOnVisible rootMargin="320px 0px" fallback={<div className="h-20" />}>
        <Footer enabled />
      </LazyOnVisible>
    </section>
  );
};

export default ActivitySection;
