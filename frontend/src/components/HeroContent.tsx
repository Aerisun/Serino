import { useEffect, useState } from "react";
import { motion } from "motion/react";
import { transition } from "@/config";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { useSiteConfig } from "@/contexts/runtime-config";
import { SocialIcon } from "@/components/icons/SocialIcon";
import { API_BASE_PATH } from "@/lib/api";

const EMPTY_POEMS = [""];
const POEM_PREVIEW_ENDPOINT = `${API_BASE_PATH}/v1/site/poem-preview`;
const POEM_ROTATION_INTERVAL_MS = 8_000;

type PoemPreviewPayload = {
  mode: "custom" | "hitokoto";
  content: string;
};

const fetchPoemPreview = async () => {
  const requestUrl = `${POEM_PREVIEW_ENDPOINT}?_ts=${Date.now()}`;
  const response = await fetch(requestUrl, {
    cache: "no-store",
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`Poem preview request failed: ${response.status}`);
  }
  const payload = (await response.json()) as PoemPreviewPayload;
  return payload.content.trim();
};

const HeroContent = () => {
  const prefersReducedMotion = useReducedMotionPreference();
  const site = useSiteConfig();
  const heroSocialLinks = site.socialLinks.filter(
    (link) => link.placement === "hero" || link.placement === "both",
  );
  const fallbackPoems = site.poems.length > 0 ? site.poems : EMPTY_POEMS;
  const [poem, setPoem] = useState(() => fallbackPoems[0]);
  const [flipped, setFlipped] = useState(false);

  useEffect(() => {
    if (site.poemSource !== "hitokoto") {
      setPoem(fallbackPoems[Math.floor(Math.random() * fallbackPoems.length)]);
      return;
    }

    let cancelled = false;

    const load = async () => {
      try {
        const next = await fetchPoemPreview();
        if (!cancelled && next) {
          setPoem(next);
        }
      } catch {
        if (!cancelled) {
          setPoem(
            fallbackPoems[Math.floor(Math.random() * fallbackPoems.length)],
          );
        }
      }
    };

    void load();

    return () => {
      cancelled = true;
    };
  }, [fallbackPoems, site.poemSource]);

  useEffect(() => {
    if (prefersReducedMotion) return;

    const timer = window.setInterval(() => {
      if (site.poemSource === "hitokoto") {
        void fetchPoemPreview()
          .then((next) => {
            if (next) setPoem(next);
          })
          .catch(() => {
            setPoem((current) => {
              const candidates = fallbackPoems.filter(
                (item) => item && item !== current,
              );
              return (
                candidates[Math.floor(Math.random() * candidates.length)] ??
                fallbackPoems[0] ??
                current
              );
            });
          });
        return;
      }

      setPoem((current) => {
        const candidates = fallbackPoems.filter((item) => item !== current);
        return (
          candidates[Math.floor(Math.random() * candidates.length)] ?? current
        );
      });
    }, POEM_ROTATION_INTERVAL_MS);

    return () => window.clearInterval(timer);
  }, [fallbackPoems, prefersReducedMotion, site.poemSource]);

  return (
    <section className="flex-1 flex flex-col px-6 lg:px-16">
      <div className="mt-9 flex flex-1 flex-col items-center justify-center gap-6 sm:mt-0 sm:gap-8">
        <motion.p
          className="text-center text-[10px] uppercase tracking-[0.32em] text-white/32 sm:text-[11px]"
          initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={transition({
            duration: 0.45,
            reducedMotion: prefersReducedMotion,
          })}
        >
          {site.role}
        </motion.p>

        <motion.div
          className="cursor-pointer select-none"
          style={{ perspective: 1000 }}
          onClick={() => setFlipped((f) => !f)}
          initial={{ opacity: 0, scale: prefersReducedMotion ? 1 : 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={transition({
            duration: 0.55,
            reducedMotion: prefersReducedMotion,
          })}
        >
          <motion.div
            className="relative h-48 w-48 sm:h-56 sm:w-56"
            animate={{ rotateY: flipped ? 180 : 0 }}
            transition={transition({
              duration: 0.7,
              reducedMotion: prefersReducedMotion,
            })}
            style={{ transformStyle: "preserve-3d" }}
          >
            <div
              className="absolute inset-0 rounded-full"
              style={{ backfaceVisibility: "hidden" }}
            >
              <div className="h-full w-full rounded-full liquid-glass-coin-hero flex items-center justify-center">
                <span
                  className="select-none text-5xl text-foreground sm:text-6xl"
                  style={{ fontFamily: "'Pinyon Script', cursive" }}
                >
                  {site.name}
                </span>
              </div>
            </div>

            <div
              className="absolute inset-0 rounded-full"
              style={{
                backfaceVisibility: "hidden",
                transform: "rotateY(180deg)",
              }}
            >
              <div className="h-full w-full rounded-full overflow-hidden liquid-glass-coin-hero">
                <img
                  src={site.heroImageUrl || site.ogImage}
                  alt={site.name}
                  className="h-full w-full object-cover"
                  loading="lazy"
                />
              </div>
            </div>
          </motion.div>
        </motion.div>

        <motion.p
          className="mx-auto max-w-[34rem] text-center text-[1.02rem] leading-6 text-[rgb(14_22_40/0.98)] [text-shadow:0_1px_0_rgba(255,255,255,0.42),0_2px_10px_rgba(255,255,255,0.18),0_8px_20px_rgba(15,23,42,0.16)] [-webkit-text-stroke:0.4px_rgba(255,255,255,0.34)] dark:text-[rgb(255_255_255/0.92)] dark:[text-shadow:0_1px_0_rgba(0,0,0,0.24),0_8px_18px_rgba(0,0,0,0.3)] dark:[-webkit-text-stroke:0.35px_rgba(9,14,24,0.28)] sm:text-[1.1rem] sm:leading-7"
          initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={transition({
            duration: 0.55,
            delay: prefersReducedMotion ? 0 : 0.1,
            reducedMotion: prefersReducedMotion,
          })}
          style={{
            fontFamily:
              "'PingFang SC', 'SF Pro SC', 'SF Pro Display', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
            fontWeight: 600,
            letterSpacing: "0.015em",
            WebkitFontSmoothing: "antialiased",
            MozOsxFontSmoothing: "grayscale",
          }}
        >
          {site.bio}
        </motion.p>

        <motion.div
          className="mt-3 flex flex-wrap justify-center gap-4 sm:mt-4"
          initial={{ opacity: 0, y: prefersReducedMotion ? 0 : 12 }}
          animate={{ opacity: 1, y: 0 }}
          transition={transition({
            duration: 0.55,
            delay: prefersReducedMotion ? 0 : 0.18,
            reducedMotion: prefersReducedMotion,
          })}
        >
          {heroSocialLinks.map((link) => (
            <a
              key={`${link.name}-${link.href}`}
              href={link.href}
              target="_blank"
              rel="noopener noreferrer"
              title={link.name}
              className="flex h-10 w-10 items-center justify-center rounded-full liquid-glass-hero text-white/68 transition-colors duration-200 hover:text-white focus-visible:text-white active:scale-95"
            >
              <SocialIcon
                iconKey={link.iconKey}
                className="h-[18px] w-[18px]"
              />
            </a>
          ))}
        </motion.div>

        <motion.div
          className="mt-1.5 flex w-full justify-center gap-3 sm:mt-3"
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
              className="group relative flex h-11 w-11 items-center justify-center overflow-hidden rounded-full liquid-glass-hero text-white/72 transition-[width,color] duration-300 ease-out hover:w-[7rem] hover:text-white focus-visible:w-[7rem] focus-visible:text-white active:scale-[0.97]"
            >
              <span className="absolute inset-y-0 left-0 flex w-11 items-center justify-center">
                <SocialIcon
                  iconKey={cta.iconKey}
                  className="h-[18px] w-[18px] shrink-0"
                />
              </span>
              <span className="max-w-0 overflow-hidden whitespace-nowrap pl-0 pr-0 text-sm font-body font-medium opacity-0 transition-all duration-300 ease-out group-hover:max-w-[4.5rem] group-hover:pl-11 group-hover:pr-4 group-hover:opacity-100 group-focus-visible:max-w-[4.5rem] group-focus-visible:pl-11 group-focus-visible:pr-4 group-focus-visible:opacity-100">
                {cta.label}
              </span>
            </a>
          ))}
        </motion.div>
      </div>

      <motion.div
        className="flex flex-col items-center gap-3 pb-3 pt-2 sm:pb-6"
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
          className="h-5 w-5 animate-bounce text-white/22"
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
