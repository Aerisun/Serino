import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { ArrowUp } from "lucide-react";
import { useFrontendI18n } from "@/i18n";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";

const MIN_SCROLL_TOP = 320;
const MIN_UPWARD_DELTA = 6;
const APPEAR_DELAY_MS = 300;
const HIDE_DELAY_MS = 2000;

type ScrollContainer = Window | HTMLElement;

const resolveScrollContainer = (): ScrollContainer => {
  if (typeof document === "undefined") {
    return window;
  }

  return (document.querySelector("[data-home-scroll]") as HTMLElement | null) ?? window;
};

const readScrollTop = (container: ScrollContainer) =>
  container === window ? window.scrollY : container.scrollTop;

const scrollContainerToTop = (container: ScrollContainer) => {
  if (container === window) {
    window.scrollTo({ top: 0, behavior: "smooth" });
    return;
  }

  container.scrollTo({ top: 0, behavior: "smooth" });
};

const BackToTop = () => {
  const { t } = useFrontendI18n();
  const prefersReducedMotion = useReducedMotionPreference();
  const [visible, setVisible] = useState(false);
  const [mounted, setMounted] = useState(false);
  const scrollContainerRef = useRef<ScrollContainer | null>(null);
  const lastScrollTopRef = useRef(0);
  const visibleRef = useRef(false);
  const pendingShowTimerRef = useRef<number | null>(null);
  const pendingHideTimerRef = useRef<number | null>(null);

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    setMounted(true);

    const scrollContainer = resolveScrollContainer();
    scrollContainerRef.current = scrollContainer;
    lastScrollTopRef.current = readScrollTop(scrollContainer);

    const clearPendingShow = () => {
      if (pendingShowTimerRef.current !== null) {
        window.clearTimeout(pendingShowTimerRef.current);
        pendingShowTimerRef.current = null;
      }
    };

    const clearPendingHide = () => {
      if (pendingHideTimerRef.current !== null) {
        window.clearTimeout(pendingHideTimerRef.current);
        pendingHideTimerRef.current = null;
      }
    };

    const hideNow = () => {
      clearPendingHide();
      visibleRef.current = false;
      setVisible(false);
    };

    const scheduleHide = () => {
      clearPendingHide();
      pendingHideTimerRef.current = window.setTimeout(() => {
        pendingHideTimerRef.current = null;
        visibleRef.current = false;
        setVisible(false);
      }, HIDE_DELAY_MS);
    };

    const scheduleShow = () => {
      if (pendingShowTimerRef.current !== null || visibleRef.current) {
        return;
      }

      pendingShowTimerRef.current = window.setTimeout(() => {
        pendingShowTimerRef.current = null;

        if (readScrollTop(scrollContainer) <= MIN_SCROLL_TOP) {
          return;
        }

        visibleRef.current = true;
        setVisible(true);
        scheduleHide();
      }, APPEAR_DELAY_MS);
    };

    const onScroll = () => {
      const currentTop = readScrollTop(scrollContainer);
      const delta = currentTop - lastScrollTopRef.current;

      if (currentTop <= MIN_SCROLL_TOP || delta > 0) {
        clearPendingShow();
        hideNow();
      } else if (delta <= -MIN_UPWARD_DELTA) {
        if (visibleRef.current) {
          scheduleHide();
        } else {
          scheduleShow();
        }
      }

      lastScrollTopRef.current = currentTop;
    };

    onScroll();
    scrollContainer.addEventListener("scroll", onScroll, { passive: true });

    return () => {
      clearPendingShow();
      clearPendingHide();
      scrollContainer.removeEventListener("scroll", onScroll);
    };
  }, []);

  if (!mounted || typeof document === "undefined") {
    return null;
  }

  return createPortal(
    <AnimatePresence>
      {visible ? (
        <motion.button
          key="back-to-top"
          type="button"
          initial={{ opacity: 0, y: 12, scale: 0.9 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: 8, scale: 0.94 }}
          transition={
            prefersReducedMotion
              ? { duration: 0.01 }
              : { duration: 0.42, ease: [0.22, 1, 0.36, 1] }
          }
          onClick={() => {
            const scrollContainer = scrollContainerRef.current ?? window;
            scrollContainerToTop(scrollContainer);
          }}
          className="fixed z-[1200] flex h-10 w-10 items-center justify-center rounded-full border text-foreground/60 shadow-[0_12px_30px_rgba(15,23,42,0.1)] backdrop-blur-xl transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.82)] dark:text-white/72 dark:shadow-[0_16px_36px_rgba(0,0,0,0.28)]"
          style={{
            right: "max(1.5rem, calc(env(safe-area-inset-right) + 1rem))",
            bottom: "max(1.5rem, calc(env(safe-area-inset-bottom) + 1rem))",
            backgroundColor: "rgb(var(--shiro-panel-rgb) / 0.26)",
            borderColor: "rgb(var(--shiro-border-rgb) / 0.22)",
          }}
          aria-label={t("common.backToTop")}
        >
          <ArrowUp className="h-4 w-4" />
        </motion.button>
      ) : null}
    </AnimatePresence>,
    document.body,
  );
};

export default BackToTop;
