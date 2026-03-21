import Navbar from "@/components/Navbar";
import HeroContent from "@/components/HeroContent";
import ActivitySection from "@/components/ActivitySection";
import PageMeta from "@/components/PageMeta";
import { useTheme } from "@/contexts/useTheme";
import { siteConfig } from "@/config";

const VIDEO_URL =
  "https://d8j0ntlcm91z4.cloudfront.net/user_38xzZboKViGWJOttwIXH07lWA1P/hf_20260306_115329_5e00c9c5-4d69-49b7-94c3-9c31c60bb644.mp4";

const Index = () => {
  const { resolvedTheme } = useTheme();
  const fadeTo = resolvedTheme === "dark" ? "hsl(0 0% 4%)" : "hsl(0 0% 100%)";

  return (
    <div
      data-home-scroll
      className="h-[100svh] overflow-x-hidden overflow-y-auto"
    >
      <PageMeta description={siteConfig.description} />
      <Navbar />
      {/* Hero Section — full viewport, always dark styled */}
      <div className="relative min-h-screen flex flex-col overflow-hidden dark">
        {/* Background Video */}
        <video
          className="absolute inset-0 w-full h-full object-cover z-0"
          autoPlay
          loop
          muted
          playsInline
          preload="auto"
          poster="/images/hero_bg.jpeg"
        >
          <source src={VIDEO_URL} type="video/mp4" />
        </video>

        {/* Overlay */}
        <div className="absolute inset-0 bg-black/5 z-0" />

        {/* Bottom fade — uses actual page background, not the forced-dark --background */}
        <div
          className="absolute bottom-0 left-0 right-0 h-40 z-[1]"
          style={{ background: `linear-gradient(to bottom, transparent, ${fadeTo})` }}
        />

        {/* Content — force white text for video overlay */}
        <div className="relative z-10 flex flex-col min-h-screen text-white">
          <HeroContent />
        </div>
      </div>

      {/* Continuous scrollable content */}
      <ActivitySection />
    </div>
  );
};

export default Index;
