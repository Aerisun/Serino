import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { transition } from "@/config";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { useSiteConfig } from "@/contexts/RuntimeConfigContext";
import { SocialIcon } from "@/components/icons/SocialIcon";

const HeroContent = () => {
  const prefersReducedMotion = useReducedMotionPreference();
  const site = useSiteConfig();
  const [poem, setPoem] = useState(() => site.poems[0]);
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    setPoem(site.poems[Math.floor(Math.random() * site.poems.length)]);
  }, []);

  useEffect(() => {
    if (prefersReducedMotion) return;

    const timer = window.setInterval(() => {
      setPoem((current) => {
        const candidates = site.poems.filter((item) => item !== current);
        return candidates[Math.floor(Math.random() * candidates.length)] ?? current;
      });
    }, 8000);

    return () => window.clearInterval(timer);
  }, [prefersReducedMotion]);

  return (
    <section className="flex-1 flex flex-col px-6 lg:px-16">
      <div className="flex flex-1 flex-col items-center justify-center gap-8">
        <motion.p
          className="text-[10px] sm:text-[11px] uppercase tracking-[0.32em] text-white/30 text-center"
          initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={transition({ duration: 0.45, reducedMotion: prefersReducedMotion })}
        >
          {site.role}
        </motion.p>

        <motion.div
          className="cursor-pointer select-none"
          style={{ perspective: 1000 }}
          onClick={() => setFlipped((f) => !f)}
          initial={{ opacity: 0, scale: prefersReducedMotion ? 1 : 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={transition({ duration: 0.55, reducedMotion: prefersReducedMotion })}
        >
          <motion.div
            className="relative h-48 w-48 sm:h-56 sm:w-56"
            animate={{ rotateY: flipped ? 180 : 0 }}
            transition={transition({ duration: 0.7, reducedMotion: prefersReducedMotion })}
            style={{ transformStyle: "preserve-3d" }}
          >
            <div className="absolute inset-0 rounded-full" style={{ backfaceVisibility: "hidden" }}>
              <div className="h-full w-full rounded-full liquid-glass-coin flex items-center justify-center">
                <span className="text-5xl sm:text-6xl text-white select-none" style={{ fontFamily: "'Pinyon Script', cursive" }}>
                  {site.name}
                </span>
              </div>
            </div>

            <div className="absolute inset-0 rounded-full" style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}>
              <div className="h-full w-full rounded-full overflow-hidden liquid-glass-coin">
                <img src="/images/avatar.png" alt={site.name} className="h-full w-full object-cover" />
              </div>
            </div>
          </motion.div>
        </motion.div>

        <motion.p
          className="max-w-[30rem] text-center text-[0.98rem] leading-7 text-white/72 sm:text-lg"
          style={{ fontFamily: "'Instrument Serif', serif" }}
          initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={transition({
            duration: 0.55,
            delay: prefersReducedMotion ? 0 : 0.1,
            reducedMotion: prefersReducedMotion,
          })}
        >
          {site.bio}
        </motion.p>

        <motion.div
          className="flex flex-wrap justify-center gap-3"
          initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={transition({
            duration: 0.55,
            delay: prefersReducedMotion ? 0 : 0.18,
            reducedMotion: prefersReducedMotion,
          })}
        >
          {site.socialLinks.map((link) => (
            <a
              key={link.name}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              title={link.name}
              className="flex h-10 w-10 items-center justify-center rounded-full liquid-glass text-white/60 transition-colors duration-200 hover:text-white active:scale-95"
            >
              <SocialIcon iconKey={link.iconKey} className="h-[18px] w-[18px]" />
            </a>
          ))}
        </motion.div>

        <motion.div
          className="flex w-full justify-center gap-3"
          initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={transition({
            duration: 0.55,
            delay: prefersReducedMotion ? 0 : 0.24,
            reducedMotion: prefersReducedMotion,
          })}
        >
          {site.heroActions.map((cta) => (
            <a
              key={cta.label}
              href={cta.href}
              className="group relative flex h-11 w-11 items-center justify-center overflow-hidden rounded-full liquid-glass text-white/70 transition-[width,color] duration-300 ease-out hover:w-[7rem] hover:text-white focus-visible:w-[7rem] focus-visible:text-white active:scale-[0.97]"
            >
              <span className="absolute inset-y-0 left-0 flex w-11 items-center justify-center">
                <SocialIcon iconKey={cta.iconKey} className="h-[18px] w-[18px] shrink-0" />
              </span>
              <span className="max-w-0 overflow-hidden whitespace-nowrap pl-0 pr-0 text-sm font-body font-medium opacity-0 transition-all duration-300 ease-out group-hover:max-w-[4.5rem] group-hover:pl-11 group-hover:pr-4 group-hover:opacity-100 group-focus-visible:max-w-[4.5rem] group-focus-visible:pl-11 group-focus-visible:pr-4 group-focus-visible:opacity-100">
                {cta.label}
              </span>
            </a>
          ))}
        </motion.div>
      </div>

      <motion.div
        className="flex flex-col items-center gap-3 pb-6 pt-2"
        initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 16 }}
        animate={{ opacity: 1, y: 0 }}
        transition={transition({
          duration: 0.55,
          delay: prefersReducedMotion ? 0 : 0.24,
          reducedMotion: prefersReducedMotion,
        })}
      >
        <p className="max-w-[44rem] text-center text-sm leading-6 text-white/42 sm:text-[0.95rem]">
          {poem}
        </p>
        <svg
          className="h-5 w-5 text-white/20 animate-bounce"
          style={{ animationDuration: "2s" }}
          viewBox="0 0 20 20"
          fill="none"
          stroke="currentColor"
          strokeWidth={1.5}
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M4 7l6 6 6-6" />
        </svg>
      </motion.div>
    </section>
  );
};

export default HeroContent;
