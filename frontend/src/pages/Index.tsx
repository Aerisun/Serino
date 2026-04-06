import Navbar from "@/components/Navbar";
import HeroContent from "@/components/HeroContent";
import ActivitySection from "@/components/ActivitySection";
import PageMeta from "@/components/PageMeta";
import { useTheme } from "@serino/theme";
import { useSiteConfig } from "@/contexts/runtime-config";
import { useState } from "react";

const Index = () => {
  const { resolvedTheme } = useTheme();
  const site = useSiteConfig();
  const videoUrl = site.heroVideoUrl;
  const posterUrl = site.heroPosterUrl;
  const [videoFailed, setVideoFailed] = useState(false);
  const fadeTo = resolvedTheme === "dark" ? "hsl(0 0% 4%)" : "hsl(0 0% 100%)";
  const heroOverlayClass = "bg-black/12";
  const showVideo = Boolean(videoUrl) && !videoFailed;
  const showImageFallback = Boolean(posterUrl) && !showVideo;

  return (
    <div
      data-home-scroll
      className="scrollbar-hide h-[100svh] overflow-x-hidden overflow-y-auto"
    >
      <PageMeta description={site.bio} />
      <Navbar glassVariant="hero" />
      <div className="relative min-h-[100svh] flex flex-col overflow-hidden">
        {showImageFallback && (
          <img
            src={posterUrl}
            alt={site.title || site.name}
            className="absolute inset-0 h-full w-full object-cover z-0"
            loading="eager"
          />
        )}

        {/* Background Video */}
        {showVideo && (
        <video
          className="absolute inset-0 w-full h-full object-cover z-0"
          autoPlay
          loop
          muted
          playsInline
          preload="metadata"
          poster={posterUrl}
          onError={() => setVideoFailed(true)}
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

        <div className="relative z-10 flex min-h-[100svh] flex-col">
          <HeroContent />
        </div>
      </div>

      {/* Continuous scrollable content */}
      <ActivitySection />
    </div>
  );
};

export default Index;
