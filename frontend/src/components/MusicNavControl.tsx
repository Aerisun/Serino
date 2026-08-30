import {
  useEffect,
  useId,
  useRef,
  useState,
  type CSSProperties,
  type FocusEvent,
} from "react";
import { AnimatePresence, motion } from "motion/react";
import { Music2, SkipForward } from "@/components/icons/AppIcon";
import { useMusicPlayer } from "@/contexts/music-player";
import { useFrontendI18n } from "@/i18n";
import { resolveDesktopMusicOverlay } from "@/lib/music-playback";
import { useOverflowingText } from "@/lib/useOverflowingText";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { transition } from "@/config";
import "./MusicNavControl.css";

type MusicNavControlProps = {
  glassVariant?: "default" | "hero";
};

export default function MusicNavControl({
  glassVariant = "default",
}: MusicNavControlProps) {
  const { t } = useFrontendI18n();
  const {
    available,
    currentTrack,
    isPlaying,
    currentTime,
    duration,
    togglePlayback,
    nextTrack,
    seekTo,
  } = useMusicPlayer();
  const prefersReducedMotion = useReducedMotionPreference();
  const [open, setOpen] = useState(false);
  const [pointerInside, setPointerInside] = useState(false);
  const [focusWithin, setFocusWithin] = useState(false);
  const closeTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const titleViewportRef = useRef<HTMLDivElement>(null);
  const titleMeasureRef = useRef<HTMLSpanElement>(null);
  const playHintId = useId();
  const titleOverflowing = useOverflowingText(
    titleViewportRef,
    titleMeasureRef,
    currentTrack?.title ?? "",
    open,
  );

  useEffect(
    () => () => {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
    },
    [],
  );

  useEffect(() => {
    if (!isPlaying) {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
      setOpen(false);
      return;
    }

    if (pointerInside || focusWithin) {
      if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
      setOpen(true);
    }
  }, [focusWithin, isPlaying, pointerInside]);

  if (!available || !currentTrack) return null;

  const clearCloseTimer = () => {
    if (closeTimerRef.current) clearTimeout(closeTimerRef.current);
  };
  const handleMouseEnter = () => {
    setPointerInside(true);
    clearCloseTimer();
    if (isPlaying) setOpen(true);
  };
  const scheduleClose = () => {
    closeTimerRef.current = setTimeout(() => setOpen(false), 140);
  };
  const handleMouseLeave = () => {
    setPointerInside(false);
    scheduleClose();
  };
  const handleFocus = () => {
    setFocusWithin(true);
    clearCloseTimer();
    if (isPlaying) setOpen(true);
  };
  const handleBlur = (event: FocusEvent<HTMLDivElement>) => {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setFocusWithin(false);
      scheduleClose();
    }
  };
  const glassClass =
    glassVariant === "hero" ? "liquid-glass-nav-hero-strong" : "liquid-glass-nav-strong";
  const toneClass =
    glassVariant === "hero"
      ? "text-white/76 hover:text-white"
      : "text-foreground/60 hover:text-foreground";
  const progress = duration > 0 ? Math.min((currentTime / duration) * 100, 100) : 0;
  const interactionActive = pointerInside || focusWithin;
  const overlay = resolveDesktopMusicOverlay(isPlaying, isPlaying ? open : interactionActive);

  return (
    <div
      className="relative hidden md:block"
      onMouseEnter={handleMouseEnter}
      onMouseLeave={handleMouseLeave}
      onFocusCapture={handleFocus}
      onBlurCapture={handleBlur}
    >
      <motion.button
        type="button"
        onClick={togglePlayback}
        aria-label={isPlaying ? t("music.pause") : t("music.play")}
        aria-expanded={overlay === "player"}
        aria-describedby={overlay === "play-hint" ? playHintId : undefined}
        className={`flex h-9 w-9 items-center justify-center rounded-full transition-colors active:scale-95 ${glassClass} ${toneClass}`}
        whileHover={prefersReducedMotion ? undefined : { y: -1.8, scale: 1.05 }}
        whileTap={prefersReducedMotion ? undefined : { scale: 0.98 }}
        transition={transition({ duration: 0.2, reducedMotion: prefersReducedMotion })}
      >
        <span className={`music-nav-icon ${isPlaying ? "music-nav-icon--playing" : ""}`}>
          <Music2 className="h-4 w-4" />
        </span>
      </motion.button>

      <AnimatePresence mode="wait">
        {overlay === "play-hint" ? (
          <motion.div
            key="play-hint"
            id={playHintId}
            role="tooltip"
            initial={{ opacity: 0, x: "-50%", y: -3, scale: 0.96 }}
            animate={{ opacity: 1, x: "-50%", y: 0, scale: 1 }}
            exit={{ opacity: 0, x: "-50%", y: -3, scale: 0.96 }}
            transition={transition({ duration: 0.14, reducedMotion: prefersReducedMotion })}
            className="music-play-hint pointer-events-none absolute left-1/2 top-[calc(100%+0.55rem)] z-10 -translate-x-1/2 origin-top whitespace-nowrap"
          >
            <div className="music-play-hint__surface rounded-full bg-[rgb(var(--shiro-panel-rgb)/0.94)] px-3 py-1.5 text-[11px] font-medium text-foreground/72 shadow-[0_5px_16px_rgba(15,23,42,0.16)]">
              {t("music.play")}
            </div>
          </motion.div>
        ) : open && isPlaying ? (
          <motion.div
            key="player"
            initial={{ opacity: 0, y: -4, scale: 0.96 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -4, scale: 0.96 }}
            transition={transition({ duration: 0.18, reducedMotion: prefersReducedMotion })}
            className="absolute right-0 top-[calc(100%+0.65rem)] w-64 origin-top-right pt-1"
          >
            <div
              className={`music-nav-popover__card--literary relative flex h-24 flex-col gap-1 overflow-hidden rounded-[1.45rem] px-4 py-3 shadow-[0_18px_48px_rgba(15,23,42,0.14)] ${glassClass}`}
            >
              <div
                ref={titleViewportRef}
                className={`music-nav-popover__title relative z-[1] flex min-h-0 min-w-0 flex-1 items-center overflow-hidden text-center font-heading text-sm tracking-[0.015em] ${
                  glassVariant === "hero" ? "text-white/88" : "text-foreground/82"
                }`}
                title={currentTrack.title}
              >
                <span ref={titleMeasureRef} className="music-nav-popover__measure" aria-hidden="true">
                  {currentTrack.title}
                </span>
                <span className="sr-only">{currentTrack.title}</span>
                {titleOverflowing && !prefersReducedMotion ? (
                  <span className="music-nav-popover__marquee" aria-hidden="true">
                    <span>{currentTrack.title}</span>
                    <span>{currentTrack.title}</span>
                  </span>
                ) : (
                  <span className="block min-w-0 flex-1 truncate" aria-hidden="true">
                    {currentTrack.title}
                  </span>
                )}
              </div>

              <div className="music-nav-popover__controls relative z-[1] flex h-10 items-center gap-3">
                <div
                  className={`flex min-w-0 flex-1 items-center ${
                    glassVariant === "hero" ? "text-white/72" : "text-foreground/52"
                  }`}
                >
                  <input
                    type="range"
                    min={0}
                    max={duration || 0}
                    step={0.1}
                    value={duration > 0 ? Math.min(currentTime, duration) : 0}
                    disabled={duration <= 0}
                    onChange={(event) => seekTo(Number(event.currentTarget.value))}
                    aria-label={t("music.progress")}
                    className="music-nav-progress"
                    style={{ "--music-progress": `${progress}%` } as CSSProperties}
                  />
                </div>
                <button
                  type="button"
                  onClick={nextTrack}
                  className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-[rgb(var(--shiro-panel-rgb)/0.24)] transition-colors hover:bg-[rgb(var(--shiro-panel-rgb)/0.42)] active:scale-95 ${toneClass}`}
                  aria-label={t("music.next")}
                >
                  <SkipForward className="h-3.5 w-3.5" />
                </button>
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );
}
