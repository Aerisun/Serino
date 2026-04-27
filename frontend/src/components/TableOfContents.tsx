import { useState, useEffect, useCallback, useRef } from "react";
import { motion, AnimatePresence } from "motion/react";
import { ChevronDown, List } from "lucide-react";
import { useFrontendI18n } from "@/i18n";

interface Heading {
  id: string;
  text: string;
  level: number;
}

interface TableOfContentsProps {
  containerRef: React.RefObject<HTMLElement | null>;
  content: unknown[];
}

const TableOfContents = ({ containerRef, content }: TableOfContentsProps) => {
  const { t } = useFrontendI18n();
  const [headings, setHeadings] = useState<Heading[]>([]);
  const [activeId, setActiveId] = useState("");
  const [expanded, setExpanded] = useState(true);
  const observerRef = useRef<IntersectionObserver | null>(null);
  const autoScrollingRef = useRef(false);
  const followResumeTimerRef = useRef<number | null>(null);

  useEffect(() => {
    const parseHeadings = () => {
      const container = containerRef.current;
      const scoped = Array.from(container?.querySelectorAll("h2, h3") ?? []);
      const fallback =
        scoped.length > 0
          ? scoped
          : Array.from(document.querySelectorAll("article h2, article h3"));

      const items: Heading[] = fallback.map((el, index) => {
        if (!el.id) el.id = `heading-${index}`;
        return {
          id: el.id,
          text: el.textContent || "",
          level: el.tagName === "H2" ? 2 : 3,
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

    observerRef.current?.disconnect();
    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            setActiveId(entry.target.id);
            break;
          }
        }
      },
      { rootMargin: "-80px 0px -70% 0px", threshold: 0 },
    );
    observerRef.current = observer;

    headings.forEach(({ id }) => {
      const el = document.getElementById(id);
      if (el) observer.observe(el);
    });

    return () => observer.disconnect();
  }, [headings]);

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
      const padding = 12;
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
    followResumeTimerRef.current = window.setTimeout(() => {
      followResumeTimerRef.current = null;
      ensureActiveVisible("smooth");
    }, 900);
  }, [clearFollowResumeTimer, ensureActiveVisible]);

  useEffect(() => {
    if (!expanded || !activeId) return;
    if (followResumeTimerRef.current !== null) return;
    ensureActiveVisible("smooth");
  }, [activeId, expanded, ensureActiveVisible]);

  useEffect(() => {
    return () => clearFollowResumeTimer();
  }, [clearFollowResumeTimer]);

  const scrollTo = useCallback((id: string) => {
    clearFollowResumeTimer();
    const el = document.getElementById(id);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [clearFollowResumeTimer]);

  const setTargetHover = useCallback((id: string, hovered: boolean) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.classList.toggle("markdown-target-hover", hovered);
  }, []);

  if (headings.length < 2) return null;

  const tocContent = (
    <nav className="space-y-0.5">
      {headings.map((heading) => (
        <button
          key={heading.id}
          type="button"
          onClick={() => scrollTo(heading.id)}
          onMouseEnter={() => setTargetHover(heading.id, true)}
          onMouseLeave={() => setTargetHover(heading.id, false)}
          className={[
            "block w-full text-left text-[12px] font-body leading-5 transition-all",
            heading.level === 3 ? "pl-5 pr-2 py-1.5" : "pl-2 pr-2 py-1.5",
            activeId === heading.id
              ? "translate-x-2 text-[rgb(var(--shiro-accent-rgb)/0.9)]"
              : "text-foreground/38 hover:text-foreground/68",
          ].join(" ")}
          data-toc-item-id={heading.id}
        >
          <span className="block truncate">{heading.text}</span>
        </button>
      ))}
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
                className="scrollbar-hide max-h-[42vh] overflow-y-auto pr-1 pt-2"
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
      <div className="mb-6 lg:hidden">{panel}</div>
      <div className="fixed right-8 top-24 z-20 hidden w-56 lg:block">{panel}</div>
    </>
  );
};

export default TableOfContents;
