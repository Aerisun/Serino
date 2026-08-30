import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import { Music2, Pause, Play, SkipBack, SkipForward } from "@/components/icons/AppIcon";
import { useMusicPlayer } from "@/contexts/music-player";
import { useFrontendI18n } from "@/i18n";
import {
  MOBILE_MUSIC_COLLAPSE_MS,
  resolveCollapsedMusicTap,
} from "@/lib/music-playback";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import { useOverflowingText } from "@/lib/useOverflowingText";
import { transition } from "@/config";
import "./MusicNavControl.css";

export default function MobileMusicControl() {
  const { t } = useFrontendI18n();
  const {
    available,
    currentTrack,
    isPlaying,
    hasStarted,
    togglePlayback,
    previousTrack,
    nextTrack,
  } = useMusicPlayer();
  const prefersReducedMotion = useReducedMotionPreference();
  const [expanded, setExpanded] = useState(false);
  const [interactionVersion, setInteractionVersion] = useState(0);
  const [hasMobileToc, setHasMobileToc] = useState(false);
  const titleViewportRef = useRef<HTMLDivElement>(null);
  const titleMeasureRef = useRef<HTMLSpanElement>(null);
  const titleOverflowing = useOverflowingText(
    titleViewportRef,
    titleMeasureRef,
    currentTrack?.title ?? "",
    expanded,
  );

  useEffect(() => {
    const updateTocPresence = () => {
      setHasMobileToc(Boolean(document.querySelector("[data-toc-mobile-button]")));
    };

    updateTocPresence();
    const observer = new MutationObserver(updateTocPresence);
    observer.observe(document.body, { childList: true, subtree: true });
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    if (!expanded) return;
    const timer = window.setTimeout(() => setExpanded(false), MOBILE_MUSIC_COLLAPSE_MS);
    return () => window.clearTimeout(timer);
  }, [expanded, interactionVersion]);

  if (!available || !currentTrack) return null;

  const keepExpanded = () => setInteractionVersion((version) => version + 1);
  const handleCollapsedTap = () => {
    const action = resolveCollapsedMusicTap(hasStarted);
    setExpanded(true);
    keepExpanded();
    if (action === "start-and-expand") togglePlayback();
  };
  const runExpandedAction = (action: () => void) => {
    keepExpanded();
    action();
  };

  return (
    <motion.div
      layout
      data-mobile-music-control="true"
      className="fixed z-[950] md:hidden"
      style={{
        right: "max(0.75rem, env(safe-area-inset-right))",
        bottom: hasMobileToc
          ? "max(4.25rem, calc(env(safe-area-inset-bottom) + 4.25rem))"
          : "max(0.75rem, calc(env(safe-area-inset-bottom) + 0.75rem))",
      }}
      transition={transition({ duration: 0.24, reducedMotion: prefersReducedMotion })}
    >
      <AnimatePresence mode="wait" initial={false}>
        {expanded ? (
          <motion.div
            key="expanded"
            initial={{ opacity: 0, scale: 0.92, width: 44 }}
            animate={{ opacity: 1, scale: 1, width: 240 }}
            exit={{ opacity: 0, scale: 0.94, width: 44 }}
            transition={transition({ duration: 0.22, reducedMotion: prefersReducedMotion })}
            onPointerDown={keepExpanded}
            className="flex h-11 max-w-[calc(100vw-1.5rem)] items-center gap-0.5 overflow-hidden rounded-full border border-[rgb(var(--shiro-border-rgb)/0.24)] px-1 liquid-glass shadow-[0_14px_36px_rgba(15,23,42,0.14)]"
            role="group"
            aria-label={t("music.player")}
          >
            <button
              type="button"
              onClick={() => runExpandedAction(previousTrack)}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-foreground/52 transition-colors hover:bg-[rgb(var(--shiro-panel-rgb)/0.38)] hover:text-foreground active:scale-95"
              aria-label={t("music.previous")}
            >
              <SkipBack className="h-3.5 w-3.5" />
            </button>
            <div
              ref={titleViewportRef}
              className="relative flex min-w-0 flex-1 items-center overflow-hidden px-0.5 text-center text-[11px] font-medium text-foreground/78"
            >
              <span ref={titleMeasureRef} className="music-nav-popover__measure" aria-hidden="true">
                {currentTrack.title}
              </span>
              <span className="sr-only">{currentTrack.title}</span>
              {titleOverflowing && !prefersReducedMotion ? (
                <span
                  className="music-nav-popover__marquee music-mobile-title__marquee"
                  aria-hidden="true"
                >
                  <span>{currentTrack.title}</span>
                  <span>{currentTrack.title}</span>
                </span>
              ) : (
                <span className="block min-w-0 flex-1 truncate" aria-hidden="true">
                  {currentTrack.title}
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={() => runExpandedAction(togglePlayback)}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-[rgb(var(--shiro-accent-rgb)/0.1)] text-[rgb(var(--shiro-accent-rgb)/0.88)] transition-colors active:scale-95"
              aria-label={isPlaying ? t("music.pause") : t("music.play")}
            >
              {isPlaying ? <Pause className="h-3 w-3" /> : <Play className="h-3 w-3" />}
            </button>
            <button
              type="button"
              onClick={() => runExpandedAction(nextTrack)}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full text-foreground/52 transition-colors hover:bg-[rgb(var(--shiro-panel-rgb)/0.38)] hover:text-foreground active:scale-95"
              aria-label={t("music.next")}
            >
              <SkipForward className="h-3.5 w-3.5" />
            </button>
          </motion.div>
        ) : (
          <motion.button
            key="collapsed"
            type="button"
            onClick={handleCollapsedTap}
            initial={{ opacity: 0, scale: 0.9 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.9 }}
            transition={transition({ duration: 0.18, reducedMotion: prefersReducedMotion })}
            className="relative flex h-11 w-11 items-center justify-center overflow-hidden rounded-full border border-[rgb(var(--shiro-border-rgb)/0.24)] text-[rgb(var(--shiro-accent-rgb)/0.84)] liquid-glass shadow-[0_12px_32px_rgba(15,23,42,0.14)] active:scale-95"
            aria-label={hasStarted ? t("music.expand") : t("music.playAndExpand")}
          >
            <span
              className={`music-nav-icon ${isPlaying ? "music-nav-icon--playing" : ""}`}
            >
              <Music2 className="h-4 w-4" />
            </span>
          </motion.button>
        )}
      </AnimatePresence>
    </motion.div>
  );
}
