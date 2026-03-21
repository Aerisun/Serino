import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { siteConfig, transition } from "@/config";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

const iconMap = {
  github: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-[18px] w-[18px]">
      <path d="M12 0C5.37 0 0 5.37 0 12c0 5.31 3.435 9.795 8.205 11.385.6.105.825-.255.825-.57 0-.285-.015-1.23-.015-2.235-3.015.555-3.795-.735-4.035-1.41-.135-.345-.72-1.41-1.23-1.695-.42-.225-1.02-.78-.015-.795.945-.015 1.62.87 1.845 1.23 1.08 1.815 2.805 1.305 3.495.99.105-.78.42-1.305.765-1.605-2.67-.3-5.46-1.335-5.46-5.925 0-1.305.465-2.385 1.23-3.225-.12-.3-.54-1.53.12-3.18 0 0 1.005-.315 3.3 1.23.96-.27 1.98-.405 3-.405s2.04.135 3 .405c2.295-1.56 3.3-1.23 3.3-1.23.66 1.65.24 2.88.12 3.18.765.84 1.23 1.905 1.23 3.225 0 4.605-2.805 5.625-5.475 5.925.435.375.81 1.095.81 2.22 0 1.605-.015 2.895-.015 3.3 0 .315.225.69.825.57A12.02 12.02 0 0024 12c0-6.63-5.37-12-12-12z" />
    </svg>
  ),
  telegram: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-[18px] w-[18px]">
      <path d="M11.944 0A12 12 0 000 12a12 12 0 0012 12 12 12 0 0012-12A12 12 0 0012 0a12 12 0 00-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 01.171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
    </svg>
  ),
  x: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-[18px] w-[18px]">
      <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
    </svg>
  ),
  music: (
    <svg viewBox="0 0 24 24" fill="currentColor" className="h-[18px] w-[18px]">
      <path d="M12 0C5.372 0 0 5.372 0 12s5.372 12 12 12 12-5.372 12-12S18.628 0 12 0zm5.92 17.108c-.745 1.222-1.86 2.068-3.327 2.528-1.378.43-2.71.404-3.996-.08a5.07 5.07 0 01-2.715-2.244c-.674-1.166-.796-2.418-.364-3.746.336-1.032.893-1.907 1.671-2.62.81-.742 1.756-1.207 2.834-1.393.332-.058.666-.076 1-.054.51.034.924.267 1.242.684.318.418.45.895.394 1.43a2.38 2.38 0 01-.564 1.282c-.37.436-.856.7-1.46.792-.39.06-.773.032-1.15-.084a1.474 1.474 0 01-.923-.782c-.11-.228-.15-.472-.122-.73.04-.356.186-.654.44-.894.046-.044.094-.086.144-.126l.11-.086c.07-.05.078-.09.024-.12-.12-.066-.252-.078-.396-.034-.36.11-.648.336-.864.678-.328.52-.408 1.08-.24 1.682.2.718.626 1.24 1.278 1.566.754.378 1.548.434 2.382.17a3.823 3.823 0 002.172-1.75c.43-.796.572-1.648.424-2.554-.19-1.174-.74-2.138-1.648-2.89a5.1 5.1 0 00-2.83-1.188c-1.136-.134-2.216.05-3.242.55-1.322.646-2.27 1.636-2.842 2.97-.442 1.028-.58 2.1-.416 3.216.21 1.42.848 2.614 1.912 3.582 1.128 1.028 2.47 1.598 4.024 1.712.37.028.74.018 1.11-.028.168-.02.266.044.294.192.018.1-.02.178-.114.234-.118.07-.248.112-.388.124-.64.058-1.274.04-1.9-.054z" />
    </svg>
  ),
  resume: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-[18px] w-[18px] shrink-0">
      <path d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
  guestbook: (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={1.5} className="h-[18px] w-[18px] shrink-0">
      <path d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  ),
};

const HeroContent = () => {
  const prefersReducedMotion = useReducedMotionPreference();
  const [poem, setPoem] = useState(() => siteConfig.poems[0]);
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    setPoem(siteConfig.poems[Math.floor(Math.random() * siteConfig.poems.length)]);
  }, []);

  useEffect(() => {
    if (prefersReducedMotion) return;

    const timer = window.setInterval(() => {
      setPoem((current) => {
        const candidates = siteConfig.poems.filter((item) => item !== current);
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
          {siteConfig.role}
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
                  {siteConfig.name}
                </span>
              </div>
            </div>

            <div className="absolute inset-0 rounded-full" style={{ backfaceVisibility: "hidden", transform: "rotateY(180deg)" }}>
              <div className="h-full w-full rounded-full overflow-hidden liquid-glass-coin">
                <img src="/images/avatar.png" alt={siteConfig.name} className="h-full w-full object-cover" />
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
          {siteConfig.bio}
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
          {siteConfig.socialLinks.map((link) => (
            <a
              key={link.name}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              title={link.name}
              className="flex h-10 w-10 items-center justify-center rounded-full liquid-glass text-white/60 transition-colors duration-200 hover:text-white active:scale-95"
            >
              {iconMap[link.iconKey]}
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
          {siteConfig.heroActions.map((cta) => (
            <a
              key={cta.label}
              href={cta.href}
              className="group relative flex h-11 w-11 items-center justify-center overflow-hidden rounded-full liquid-glass text-white/70 transition-[width,color] duration-300 ease-out hover:w-[7rem] hover:text-white focus-visible:w-[7rem] focus-visible:text-white active:scale-[0.97]"
            >
              <span className="absolute inset-y-0 left-0 flex w-11 items-center justify-center">
                {iconMap[cta.iconKey]}
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
