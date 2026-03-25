import Navbar from "@/components/Navbar";
import HeroContent from "@/components/HeroContent";
import ActivitySection from "@/components/ActivitySection";
import PageMeta from "@/components/PageMeta";
import { useTheme } from "@serino/theme";
import { useSiteConfig } from "@/contexts/runtime-config";

const Index = () => {
  const { resolvedTheme } = useTheme();
  const site = useSiteConfig();
  const videoUrl = site.heroVideoUrl;
  const fadeTo = resolvedTheme === "dark" ? "hsl(0 0% 4%)" : "hsl(0 0% 100%)";
  const heroOverlayClass = resolvedTheme === "dark" ? "bg-black/12" : "bg-black/18";

  return (
    <div
      data-home-scroll
      className="h-[100svh] overflow-x-hidden overflow-y-auto"
    >
      <PageMeta description={site.metaDescription} />
      <Navbar glassVariant="hero" />
      <div className="relative min-h-screen flex flex-col overflow-hidden">
        {/* Background Video */}
        {videoUrl && (
        <video
          className="absolute inset-0 w-full h-full object-cover z-0"
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          poster="/images/hero_bg.jpeg"
        >
          <source src={videoUrl} type="video/mp4" />
        </video>
        )}

        {/* Overlay */}
        <div className={`absolute inset-0 z-0 ${heroOverlayClass}`} />

        {/* Bottom fade — uses actual page background, not the forced-dark --background */}
        <div
          className="absolute bottom-0 left-0 right-0 h-40 z-[1]"
          style={{ background: `linear-gradient(to bottom, transparent, ${fadeTo})` }}
        />

        <div className="relative z-10 flex flex-col min-h-screen">
          <HeroContent />
        </div>
      </div>

      {/* Continuous scrollable content */}
      <ActivitySection />
    </div>
  );
};

export default Index;
