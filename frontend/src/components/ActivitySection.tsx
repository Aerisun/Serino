import FriendCircle from "./FriendCircle";
import RecentActivity from "./RecentActivity";
import ActivityHeatmap from "./ActivityHeatmap";
import Footer from "./Footer";
import { usePageConfig } from "@/contexts/RuntimeConfigContext";

const ActivitySection = () => {
  const config = usePageConfig().activity as Record<string, any>;
  return (
    <section className="relative w-full flex flex-col overflow-hidden bg-background">
      {/* Soft glow at top — echoes the hero video tones for continuity */}
      <div
        className="absolute top-0 left-1/2 -translate-x-1/2 w-[140%] h-[320px] pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 70% 100% at 50% 0%, hsla(213,45%,50%,0.08) 0%, transparent 70%)",
        }}
      />

      {/* Two-column: Friend Circle + Recent Updates */}
      <div className="relative z-10 max-w-6xl mx-auto px-8 lg:px-16 pt-20 pb-12 w-full">
        {/* Section header */}
        <div className="mb-10">
          <p className="text-xs font-body font-medium text-foreground/25 uppercase tracking-[0.2em] mb-2">
            {config.dashboardLabel}
          </p>
          <h2 className="text-3xl md:text-4xl font-heading italic text-foreground leading-[1.1]">
            {config.title}
          </h2>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 lg:gap-10">
          {/* Left — Friend Circle */}
          <div className="liquid-glass rounded-3xl p-6 md:p-8">
            <FriendCircle />
          </div>

          {/* Right — Recent Activity */}
          <div className="liquid-glass rounded-3xl p-6 md:p-8">
            <RecentActivity />
          </div>
        </div>
      </div>

      {/* Full-width Wave Heatmap */}
      <div className="relative z-10 w-full px-4 sm:px-6 py-12">
        <div className="liquid-glass rounded-2xl sm:rounded-3xl p-5 md:p-8 mx-auto" style={{ maxWidth: "100%" }}>
          <ActivityHeatmap />
        </div>
      </div>

      {/* Footer */}
      <Footer />
    </section>
  );
};

export default ActivitySection;
