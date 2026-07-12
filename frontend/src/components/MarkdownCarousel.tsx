import {
  Children,
  isValidElement,
  useEffect,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { getFrontendLang } from "@/i18n";
import { frontendTranslations } from "@/i18n/translations";
import { scheduleIdleTask, shouldBackgroundPrefetch } from "@/lib/idle";
import { resolveMarkdownImageSrc } from "@/lib/markdown-image-url";
import "./markdown.css";

interface MarkdownCarouselProps {
  children: ReactNode;
}

type CarouselDirection = "forward" | "backward";
type CarouselTransition = {
  index: number;
  direction: CarouselDirection;
};
type TouchDrag = {
  startX: number;
  startY: number;
  startedAt: number;
  hasHorizontalIntent: boolean;
};

const MAX_PRELOADED_CAROUSEL_IMAGES = 5;

const cleanChildrenArray = (children: ReactNode) =>
  Children.toArray(children).filter((child) => !(typeof child === "string" && child.trim() === ""));

const flattenDirectiveChildren = (children: ReactNode) => {
  const items: ReactNode[] = [];

  cleanChildrenArray(children).forEach((child) => {
    if (isValidElement<{ children?: ReactNode }>(child)) {
      const paragraphChildren = cleanChildrenArray(child.props.children);
      const containsText = paragraphChildren.some(
        (node) => typeof node === "string" && node.trim() !== "",
      );

      if (!containsText && paragraphChildren.length > 0) {
        items.push(...paragraphChildren);
        return;
      }
    }

    items.push(child);
  });

  return items;
};

const collectImageSources = (node: ReactNode, sources: string[] = []) => {
  Children.toArray(node).forEach((child) => {
    if (!isValidElement<{ children?: ReactNode; src?: unknown }>(child)) {
      return;
    }

    if (typeof child.props.src === "string") {
      sources.push(child.props.src);
    }
    if (child.props.children) {
      collectImageSources(child.props.children, sources);
    }
  });

  return sources;
};

const getCarouselImageDescription = (node: ReactNode): string => {
  for (const child of Children.toArray(node)) {
    if (!isValidElement<{ alt?: unknown; children?: ReactNode; title?: unknown }>(child)) {
      continue;
    }

    const title = typeof child.props.title === "string" ? child.props.title.trim() : "";
    const alt = typeof child.props.alt === "string" ? child.props.alt.trim() : "";
    if (title || alt) {
      return title || alt;
    }

    const nestedDescription = getCarouselImageDescription(child.props.children);
    if (nestedDescription) {
      return nestedDescription;
    }
  }

  return "";
};

const getText = (key: string, fallback: string) => {
  const lang = getFrontendLang();
  return frontendTranslations[lang][key] ?? fallback;
};

export default function MarkdownCarousel({ children }: MarkdownCarouselProps) {
  const items = useMemo(() => flattenDirectiveChildren(children), [children]);
  const carouselImageSources = useMemo(
    () => items.map((item) => Array.from(new Set(
      collectImageSources(item)
        .map(resolveMarkdownImageSrc)
        .filter((src): src is string => Boolean(src)),
    ))),
    [items],
  );
  const [activeIndex, setActiveIndex] = useState(0);
  const [direction, setDirection] = useState<CarouselDirection>("forward");
  const [leavingSlide, setLeavingSlide] = useState<CarouselTransition | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const carouselRef = useRef<HTMLElement>(null);
  const touchDragRef = useRef<TouchDrag | null>(null);
  const preloadedImagesRef = useRef(new Map<string, HTMLImageElement>());
  const total = items.length;
  const activeDescription = getCarouselImageDescription(items[activeIndex]);
  const previousLabel = getText("markdown.previous", "上一张");
  const nextLabel = getText("markdown.next", "下一张");

  useEffect(() => {
    setActiveIndex((current) => (total === 0 ? 0 : Math.min(current, total - 1)));
  }, [total]);

  const preloadCarouselImage = (src: string) => {
    const cachedImage = preloadedImagesRef.current.get(src);
    if (cachedImage) return;

    const image = new Image();
    image.decoding = "async";
    image.onload = () => {
      void image.decode().catch(() => undefined);
    };
    image.onerror = () => {
      preloadedImagesRef.current.delete(src);
    };

    preloadedImagesRef.current.set(src, image);
    while (preloadedImagesRef.current.size > MAX_PRELOADED_CAROUSEL_IMAGES) {
      const oldestSrc = preloadedImagesRef.current.keys().next().value;
      if (!oldestSrc) break;
      preloadedImagesRef.current.delete(oldestSrc);
    }
    image.src = src;
  };

  useEffect(() => {
    if (!shouldBackgroundPrefetch() || total === 0) return;

    const nextIndex = (activeIndex + 1) % total;
    const followingIndex = (activeIndex + 2) % total;
    const previousIndex = (activeIndex - 1 + total) % total;
    const earlierIndex = (activeIndex - 2 + total) % total;
    const sources = new Set<number>([activeIndex, nextIndex, followingIndex, previousIndex, earlierIndex]);
    const imageSources = Array.from(sources).flatMap((index) => carouselImageSources[index] ?? []);

    if (imageSources.length === 0) return;

    return scheduleIdleTask(() => {
      Array.from(new Set(imageSources)).forEach((src) => preloadCarouselImage(src));
    }, 900);
  }, [activeIndex, carouselImageSources, total]);

  const transitionTo = (nextIndex: number, nextDirection: CarouselDirection) => {
    if (nextIndex === activeIndex || leavingSlide) return;
    setDirection(nextDirection);
    setLeavingSlide({ index: activeIndex, direction: nextDirection });
    setActiveIndex(nextIndex);
  };

  const move = (offset: number) => {
    if (total < 2 || leavingSlide) return;
    const nextDirection = offset > 0 ? "forward" : "backward";
    const nextIndex = (activeIndex + offset + total) % total;
    transitionTo(nextIndex, nextDirection);
  };

  const setDragOffset = (offset: number) => {
    const carousel = carouselRef.current;
    if (!carousel) return;

    carousel.style.setProperty("--markdown-carousel-drag-x", `${offset}px`);
    carousel.style.setProperty("--markdown-carousel-preview-drag-x", `${offset * 0.16}px`);
    carousel.style.setProperty("--markdown-carousel-preview-deep-drag-x", `${offset * 0.08}px`);
  };

  const settleDrag = () => {
    touchDragRef.current = null;
    setIsDragging(false);
    setDragOffset(0);
  };

  const selectImage = (index: number) => {
    const forwardDistance = (index - activeIndex + total) % total;
    const backwardDistance = (activeIndex - index + total) % total;
    transitionTo(index, forwardDistance <= backwardDistance ? "forward" : "backward");
  };

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key === "ArrowLeft") {
      event.preventDefault();
      move(-1);
    }
    if (event.key === "ArrowRight") {
      event.preventDefault();
      move(1);
    }
  };

  if (total === 0) return null;

  return (
    <section
      ref={carouselRef}
      className={`markdown-carousel${isDragging ? " is-dragging" : ""}`}
      aria-roledescription="carousel"
      aria-label={getText("markdown.carousel", "图片图集")}
      tabIndex={total > 1 ? 0 : undefined}
      onKeyDown={handleKeyDown}
      onTouchStart={(event) => {
        if (total < 2) return;
        const touch = event.touches[0];
        if (!touch) return;

        touchDragRef.current = {
          startX: touch.clientX,
          startY: touch.clientY,
          startedAt: performance.now(),
          hasHorizontalIntent: false,
        };
      }}
      onTouchMove={(event) => {
        const drag = touchDragRef.current;
        const touch = event.touches[0];
        if (!drag || !touch) return;

        const deltaX = touch.clientX - drag.startX;
        const deltaY = touch.clientY - drag.startY;

        if (!drag.hasHorizontalIntent) {
          if (Math.abs(deltaX) < 6 && Math.abs(deltaY) < 6) return;
          if (Math.abs(deltaY) >= Math.abs(deltaX)) {
            touchDragRef.current = null;
            return;
          }
          drag.hasHorizontalIntent = true;
          setIsDragging(true);
        }

        event.preventDefault();
        const dampedOffset = deltaX / (1 + Math.abs(deltaX) / 260);
        setDragOffset(dampedOffset);
      }}
      onTouchEnd={(event) => {
        const drag = touchDragRef.current;
        const touch = event.changedTouches[0];
        if (!drag || !touch) {
          settleDrag();
          return;
        }

        const deltaX = touch.clientX - drag.startX;
        const duration = Math.max(performance.now() - drag.startedAt, 1);
        const velocity = deltaX / duration;
        const shouldMove = drag.hasHorizontalIntent && (Math.abs(deltaX) >= 56 || Math.abs(velocity) > 0.35);

        settleDrag();
        if (shouldMove) move(deltaX < 0 ? 1 : -1);
      }}
      onTouchCancel={() => {
        settleDrag();
      }}
    >
      {activeDescription ? <div className="markdown-carousel-description">{activeDescription}</div> : null}
      <div className="markdown-carousel-stage">
        {Array.from({ length: Math.min(total - 1, 2) }, (_, index) => (
          <div
            key={`preview-${(activeIndex + index + 1) % total}`}
            className="markdown-carousel-preview"
            data-depth={index + 1}
            aria-hidden="true"
            inert
          >
            {items[(activeIndex + index + 1) % total]}
          </div>
        ))}
        {leavingSlide ? (
          <div className="markdown-carousel-slide is-leaving" aria-hidden="true" inert>
            <div className={`markdown-carousel-slide-motion is-leaving-${leavingSlide.direction}`}>
              {items[leavingSlide.index]}
            </div>
          </div>
        ) : null}
        <div className="markdown-carousel-slide" key={activeIndex}>
          <div
            className={`markdown-carousel-slide-motion is-entering-${direction}`}
            onAnimationEnd={(event) => {
              if (event.target === event.currentTarget) setLeavingSlide(null);
            }}
          >
            {items[activeIndex]}
          </div>
        </div>
      </div>
      {total > 1 ? (
        <div className="markdown-carousel-footer">
          <div className="markdown-carousel-controls">
            <button
              type="button"
              className="markdown-carousel-control"
              onClick={() => move(-1)}
              aria-label={previousLabel}
              title={previousLabel}
            >
              <ArrowLeft className="h-4 w-4" />
            </button>
            <button
              type="button"
              className="markdown-carousel-control"
              onClick={() => move(1)}
              aria-label={nextLabel}
              title={nextLabel}
            >
              <ArrowRight className="h-4 w-4" />
            </button>
          </div>
          <span className="markdown-carousel-count" aria-live="polite">
            {activeIndex + 1} / {total}
          </span>
          <div className="markdown-carousel-pagination" aria-label={getText("markdown.pagination", "图片分页")}>
            {items.map((_, index) => (
              <button
                key={index}
                type="button"
                className={index === activeIndex ? "is-active" : ""}
                onClick={() => selectImage(index)}
                aria-label={`${getText("markdown.image", "图片")} ${index + 1}`}
                aria-current={index === activeIndex ? "true" : undefined}
              />
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}
