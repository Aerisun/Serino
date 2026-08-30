import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, List } from "lucide-react";
import { useFrontendI18n } from "@/i18n";

interface Heading {
  id: string;
  text: string;
  level: number;
  element: HTMLHeadingElement;
  key: string;
}

interface TableOfContentsProps {
  containerRef: React.RefObject<HTMLElement | null>;
  content: unknown[];
}

const TOC_HEADING_SELECTOR = "h1, h2, h3, h4";
const TOC_EXCLUDE_SELECTOR = '[data-toc-exclude="true"]';
const isTableOfContentsHeading = (element: HTMLHeadingElement) =>
  !element.closest(TOC_EXCLUDE_SELECTOR);

const TableOfContents = ({ containerRef, content }: TableOfContentsProps) => {
  const { t } = useFrontendI18n();
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeId, setActiveId] = useState("");
  const [expanded, setExpanded] = useState(true);
  const [mobileOpen, setMobileOpen] = useState(false);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const autoScrollingRef = useRef(false);
  const followResumeTimerRef = useRef<number | null>(null);
  const scrollRafRef = useRef<number | null>(null);
  const clickActiveLockRef = useRef<string | null>(null);
  const clickActiveLockTimerRef = useRef<number | null>(null);

  const clearClickActiveLock = useCallback(() => {
    if (clickActiveLockTimerRef.current !== null) {
      window.clearTimeout(clickActiveLockTimerRef.current);
      clickActiveLockTimerRef.current = null;
    }
    clickActiveLockRef.current = null;
  }, []);

  useEffect(() => {
    const parseHeadings = () => {
      const container = containerRef.current;
      const scoped = Array.from(
        container?.querySelectorAll<HTMLHeadingElement>(TOC_HEADING_SELECTOR) ?? [],
      ).filter(isTableOfContentsHeading);
      const fallback =
        scoped.length > 0
          ? scoped
          : Array.from(
              document.querySelectorAll<HTMLHeadingElement>(
                `article ${TOC_HEADING_SELECTOR.split(", ").join(", article ")}`,
              ),
            ).filter(isTableOfContentsHeading);

      const items: Heading[] = fallback.map((el, index) => {
        if (!el.id) el.id = `heading-${index}`;
        const level = Number(el.tagName.slice(1));
        return {
          id: el.id,
          text: el.textContent || "",
          level,
          element: el,
          key: `${el.id}-${index}`,
        };
      });

      setHeadings(items);
      return items.length;
    };

    const observerTarget = containerRef.current ?? document.body;
    const initialCount = parseHeadings();
    const timer = window.setTimeout(parseHeadings, 200);
    const timer2 = window.setTimeout(parseHeadings, 900);

    if (initialCount > 0) {
      return () => {
        window.clearTimeout(timer);
        window.clearTimeout(timer2);
      };
    }

    const observer = new MutationObserver(() => {
      if (parseHeadings() > 0) {
        observer.disconnect();
      }
    });
    observer.observe(observerTarget, { childList: true, subtree: true });

    return () => {
      window.clearTimeout(timer);
      window.clearTimeout(timer2);
      observer.disconnect();
    };
  }, [containerRef, content]);

  useEffect(() => {
    if (headings.length === 0) return;

    const getActiveHeadingId = () => {
      const lockedId = clickActiveLockRef.current;
      if (lockedId) {
        const lockedHeading = headings.find((heading) => heading.id === lockedId);
        if (lockedHeading) return lockedId;
      }

      const scrollLine = Math.min(180, Math.max(96, window.innerHeight * 0.22));
      let current = headings[0];
      let closestBelow = headings[0];
      let closestBelowDistance = Number.POSITIVE_INFINITY;

      for (const heading of headings) {
        const rect = heading.element.getBoundingClientRect();
        if (rect.top <= scrollLine) {
          current = heading;
          continue;
        }

        const distance = rect.top - scrollLine;
        if (distance < closestBelowDistance) {
          closestBelowDistance = distance;
          closestBelow = heading;
        }
      }

      const firstRect = headings[0]?.element.getBoundingClientRect();
      if (firstRect && firstRect.top > scrollLine) return closestBelow.id;

      return current.id;
    };

    const updateActive = () => {
      scrollRafRef.current = null;
      const next = getActiveHeadingId();
      setActiveId((current) => (current === next ? current : next));
    };

    const requestActiveUpdate = () => {
      if (scrollRafRef.current !== null) return;
      scrollRafRef.current = window.requestAnimationFrame(updateActive);
    };

    observerRef.current?.disconnect();
    const observer = new IntersectionObserver(
      () => {
        requestActiveUpdate();
      },
      { rootMargin: "-100px 0px -55% 0px", threshold: [0, 1] },
    );
    observerRef.current = observer;

    const scrollRoot = containerRef.current;

    headings.forEach(({ element }) => observer.observe(element));
    requestActiveUpdate();
    window.addEventListener("scroll", requestActiveUpdate, { passive: true });
    window.addEventListener("resize", requestActiveUpdate);
    scrollRoot?.addEventListener("scroll", requestActiveUpdate, {
      passive: true,
    });

    return () => {
      observer.disconnect();
      window.removeEventListener("scroll", requestActiveUpdate);
      window.removeEventListener("resize", requestActiveUpdate);
      scrollRoot?.removeEventListener("scroll", requestActiveUpdate);
      if (scrollRafRef.current !== null) {
        window.cancelAnimationFrame(scrollRafRef.current);
        scrollRafRef.current = null;
      }
    };
  }, [containerRef, headings]);

  const getVisibleViewport = useCallback(() => {
    if (typeof document === "undefined") return null;

    return (
      Array.from(
        document.querySelectorAll<HTMLElement>("[data-toc-viewport]"),
      ).find((node) => node.offsetParent !== null) ?? null
    );
  }, []);

  const stopAutoScrollFlagLater = useCallback((delay = 280) => {
    window.setTimeout(() => {
      autoScrollingRef.current = false;
    }, delay);
  }, []);

  const ensureActiveVisible = useCallback(
    (behavior: ScrollBehavior = "smooth") => {
      if (!expanded || !activeId) return;

      const viewport = getVisibleViewport();
      if (!viewport) return;

      const activeItem =
        Array.from(
          viewport.querySelectorAll<HTMLElement>("[data-toc-item-id]"),
        ).find((node) => node.dataset.tocItemId === activeId) ?? null;

      if (!activeItem) return;

      const viewportHeight = viewport.clientHeight;
      const top = activeItem.offsetTop - viewport.scrollTop;
      const bottom = top + activeItem.offsetHeight;
      const padding = 28;
      const needsScroll =
        top < padding || bottom > viewportHeight - padding;

      if (!needsScroll) return;

      autoScrollingRef.current = true;
      viewport.scrollTo({
        top: Math.max(
          0,
          activeItem.offsetTop - viewportHeight / 2 + activeItem.offsetHeight / 2,
        ),
        behavior,
      });
      stopAutoScrollFlagLater(behavior === "smooth" ? 320 : 0);
    },
    [activeId, expanded, getVisibleViewport, stopAutoScrollFlagLater],
  );

  const clearFollowResumeTimer = useCallback(() => {
    if (followResumeTimerRef.current !== null) {
      window.clearTimeout(followResumeTimerRef.current);
      followResumeTimerRef.current = null;
    }
  }, []);

  const pauseAutoFollow = useCallback(() => {
    if (autoScrollingRef.current) return;

    clearFollowResumeTimer();
  }, [clearFollowResumeTimer]);

  useEffect(() => {
    if (!expanded || !activeId) return;
    if (followResumeTimerRef.current !== null) return;
    if (clickActiveLockRef.current) return;
    ensureActiveVisible("smooth");
  }, [activeId, expanded, ensureActiveVisible]);

  useEffect(() => {
    if (!mobileOpen || !activeId) return;

    const timer = window.setTimeout(() => {
      ensureActiveVisible("auto");
    }, 80);

    return () => window.clearTimeout(timer);
  }, [activeId, ensureActiveVisible, mobileOpen]);

  useEffect(() => {
    return () => {
      clearFollowResumeTimer();
      clearClickActiveLock();
    };
  }, [clearClickActiveLock, clearFollowResumeTimer]);

  const scrollTo = useCallback(
    (heading: Heading) => {
      clearFollowResumeTimer();
      clearClickActiveLock();

      const { element, id } = heading;
      clickActiveLockRef.current = id;
      setActiveId(id);
      setMobileOpen(false);

      if (element.classList.contains("markdown-target-hover")) {
        element.classList.remove("markdown-target-hover");
      }

      const nextHash = `#${encodeURIComponent(id)}`;
      if (window.location.hash !== nextHash) {
        window.history.replaceState(window.history.state, "", nextHash);
      }

      autoScrollingRef.current = true;
      element.scrollIntoView({ behavior: "smooth", block: "start" });
      stopAutoScrollFlagLater(900);
      clickActiveLockTimerRef.current = window.setTimeout(() => {
        clearClickActiveLock();
      }, 1100);
    },
    [
      clearClickActiveLock,
      clearFollowResumeTimer,
      stopAutoScrollFlagLater,
    ],
  );

  const setTargetHover = useCallback((heading: Heading, hovered: boolean) => {
    heading.element.classList.toggle("markdown-target-hover", hovered);
  }, []);

  if (headings.length < 2) return null;

  const tocContent = (
    <nav className="space-y-0.5">
      {headings.map((heading) => {
        const isActive = activeId === heading.id;
        const indentClass =
          heading.level === 4
            ? "pl-8"
            : heading.level === 3
              ? "pl-5"
              : heading.level === 2
                ? "pl-2"
                : "pl-0";

        return (
          <div
            key={heading.key}
            className="relative"
            data-toc-item-id={heading.id}
            data-active={isActive ? "true" : undefined}
          >
            {isActive ? (
              <motion.span
                layoutId="toc-active-indicator"
                className="absolute inset-y-[5px] left-0 w-[2px] rounded-full bg-[rgb(var(--shiro-accent-rgb)/0.9)] shadow-[0_0_12px_rgb(var(--shiro-accent-rgb)/0.35)]"
                transition={{ type: "spring", stiffness: 420, damping: 34 }}
              />
            ) : null}
            <button
              type="button"
              onClick={() => scrollTo(heading)}
              onMouseEnter={() => setTargetHover(heading, true)}
              onMouseLeave={() => setTargetHover(heading, false)}
              className={[
                "block w-full rounded-sm pr-2 py-1.5 text-left text-[12px] font-body leading-5 outline-none transition-all",
                "focus-visible:bg-[rgb(var(--shiro-accent-rgb)/0.08)]",
                indentClass,
                isActive
                  ? "translate-x-2 text-[rgb(var(--shiro-accent-rgb)/0.92)]"
                  : "text-foreground/38 hover:text-foreground/68",
              ].join(" ")}
              title={heading.text}
              aria-current={isActive ? "location" : undefined}
            >
              <span className="block truncate">{heading.text}</span>
            </button>
          </div>
        );
      })}
    </nav>
  );

  const panel = (
    <div className="text-foreground/56">
      <button
        type="button"
        onClick={() => setExpanded((current) => !current)}
        className="flex w-full items-center justify-between gap-3 py-2 text-left transition-colors hover:text-foreground/78"
        aria-expanded={expanded}
        aria-label={t("toc.toggle")}
      >
        <span className="flex items-center gap-2">
          <span className="text-[rgb(var(--shiro-accent-rgb)/0.72)]">
            <List className="h-4 w-4" />
          </span>
        </span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-foreground/30 transition-transform duration-200 ${
            expanded ? "rotate-180" : ""
          }`}
        />
      </button>

      <AnimatePresence initial={false}>
        {expanded ? (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.22 }}
            className="overflow-hidden"
          >
            <div className="border-l border-[rgb(var(--shiro-divider-rgb)/0.16)] pl-2">
              <div
                className="toc-scroll-mask scrollbar-hide max-h-[42vh] overflow-y-auto pr-1 pt-2"
                data-toc-viewport="true"
                onPointerDown={pauseAutoFollow}
                onTouchStart={pauseAutoFollow}
                onWheel={pauseAutoFollow}
                onScroll={pauseAutoFollow}
              >
                {tocContent}
              </div>
            </div>
          </motion.div>
        ) : null}
      </AnimatePresence>
    </div>
  );

  return (
    <>
      <AnimatePresence initial={false}>
        {mobileOpen ? (
          <motion.button
            type="button"
            aria-label={t("toc.toggle")}
            className="fixed inset-0 z-30 cursor-default bg-background/10 backdrop-blur-[1px] min-[1600px]:hidden"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.16 }}
            onClick={() => setMobileOpen(false)}
          />
        ) : null}
      </AnimatePresence>

      <div className="pointer-events-none fixed inset-x-3 bottom-[calc(env(safe-area-inset-bottom)+0.75rem)] z-40 min-[1600px]:hidden">
        <AnimatePresence initial={false}>
          {mobileOpen ? (
            <motion.div
              data-toc-mobile-panel="true"
              initial={{ opacity: 0, y: 18 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: 18 }}
              transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
              className="pointer-events-auto mb-3 rounded-[0.5rem] border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.94] px-3 py-3 shadow-[0_18px_52px_rgb(0_0_0/0.16)] backdrop-blur-xl"
            >
              <div
                className="toc-scroll-mask max-h-[min(58vh,31rem)] overflow-y-auto pr-1 pt-1 [will-change:scroll-position]"
                data-toc-viewport="true"
                onPointerDown={pauseAutoFollow}
                onTouchStart={pauseAutoFollow}
                onWheel={pauseAutoFollow}
                onScroll={pauseAutoFollow}
              >
                {tocContent}
              </div>
            </motion.div>
          ) : null}
        </AnimatePresence>
        <button
          data-toc-mobile-button="true"
          type="button"
          onClick={() => {
            setExpanded(true);
            setMobileOpen((current) => !current);
          }}
          className="pointer-events-auto ml-auto flex h-11 w-11 items-center justify-center rounded-full border border-[rgb(var(--shiro-border-rgb)/0.18)] bg-background/[0.9] text-[rgb(var(--shiro-accent-rgb)/0.82)] shadow-[0_12px_34px_rgb(0_0_0/0.14)] backdrop-blur-xl transition hover:border-[rgb(var(--shiro-accent-rgb)/0.28)] hover:text-[rgb(var(--shiro-accent-rgb)/0.95)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--shiro-accent-rgb)/0.32)] focus-visible:ring-offset-2 focus-visible:ring-offset-background"
          aria-label={t("toc.toggle")}
          aria-expanded={mobileOpen}
        >
          <List className="h-4 w-4" />
        </button>
      </div>
      <div className="fixed right-8 top-24 z-20 hidden w-56 min-[1600px]:block">{panel}</div>
    </>
  );
};

export default TableOfContents;
