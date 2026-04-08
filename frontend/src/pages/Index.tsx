import { Suspense, useEffect, useState } from "react";
import { useTheme } from "@serino/theme";
import Navbar from "@/components/Navbar";
import HeroContent from "@/components/HeroContent";
import LazyOnVisible from "@/components/LazyOnVisible";
import PageMeta from "@/components/PageMeta";
import { useSiteConfig } from "@/contexts/runtime-config";
import { useDeferredActivation } from "@/hooks/useDeferredActivation";
import { scheduleIdleTask, shouldBackgroundPrefetch } from "@/lib/idle";
import { lazyWithPreload } from "@/lib/lazy";

const ActivitySection = lazyWithPreload(() => import("@/components/ActivitySection"));

const Index = () => {
  const { resolvedTheme } = useTheme();
  const site = useSiteConfig();
  const videoUrl = site.heroVideoUrl;
  const posterUrl = site.heroPosterUrl;
  const [videoFailed, setVideoFailed] = useState(false);
  const videoActivated = useDeferredActivation(Boolean(videoUrl), [videoUrl]);
  const fadeTo = resolvedTheme === "dark" ? "hsl(0 0% 4%)" : "hsl(0 0% 100%)";
  const heroOverlayClass = "bg-black/12";
  const showVideo = Boolean(videoUrl) && videoActivated && !videoFailed;
  const showImageFallback = Boolean(posterUrl);

  useEffect(() => {
    if (!shouldBackgroundPrefetch()) {
      return;
    }

    return scheduleIdleTask(() => {
      void ActivitySection.preload();
    }, 1_600);
  }, []);

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
            decoding="async"
            fetchPriority="high"
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
      <LazyOnVisible
        rootMargin="480px 0px"
        fallback={
          <section className="relative flex w-full flex-col overflow-hidden bg-background">
            <div className="mx-auto w-full max-w-[84rem] px-6 pt-20 pb-12 lg:px-8 xl:px-10">
              <div className="mb-10">
                <div className="h-3 w-24 rounded-full bg-foreground/[0.05]" />
                <div className="mt-3 h-10 w-72 rounded-full bg-foreground/[0.05]" />
              </div>
              <div className="grid grid-cols-1 gap-8 lg:grid-cols-2 lg:gap-12 xl:gap-14">
                <div className="liquid-glass h-64 rounded-[2rem] p-6 md:p-8" />
                <div className="liquid-glass h-64 rounded-[2rem] p-6 md:p-8" />
              </div>
            </div>
          </section>
        }
      >
        <Suspense fallback={null}>
          <ActivitySection />
        </Suspense>
      </LazyOnVisible>
    </div>
  );
};

export default Index;
