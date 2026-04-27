import { useEffect, useRef } from "react";

const SCROLL_EDGE_EPSILON = 1;

const canScrollInDirection = (
  scrollOffset: number,
  viewportSize: number,
  scrollSize: number,
  delta: number,
) => {
  if (Math.abs(delta) <= 0) {
    return false;
  }

  const maxScrollOffset = scrollSize - viewportSize;
  if (maxScrollOffset <= SCROLL_EDGE_EPSILON) {
    return false;
  }

  if (delta < 0) {
    return scrollOffset > SCROLL_EDGE_EPSILON;
  }

  return scrollOffset < maxScrollOffset - SCROLL_EDGE_EPSILON;
};

export const useContainedWheelScroll = <T extends HTMLElement>() => {
  const regionRef = useRef<T | null>(null);
  const scrollViewportRef = useRef<T | null>(null);

  useEffect(() => {
    const region = regionRef.current;
    if (!region) {
      return;
    }

    const handleWheel = (event: WheelEvent) => {
      if (event.ctrlKey) {
        return;
      }

      const viewport = scrollViewportRef.current;
      if (!viewport) {
        return;
      }

      const canScrollVertically = canScrollInDirection(
        viewport.scrollTop,
        viewport.clientHeight,
        viewport.scrollHeight,
        event.deltaY,
      );
      const canScrollHorizontally = canScrollInDirection(
        viewport.scrollLeft,
        viewport.clientWidth,
        viewport.scrollWidth,
        event.deltaX,
      );

      if (canScrollVertically || canScrollHorizontally) {
        event.stopPropagation();
      }
    };

    region.addEventListener("wheel", handleWheel, { passive: true });
    return () => region.removeEventListener("wheel", handleWheel);
  }, []);

  return {
    regionRef,
    scrollViewportRef,
  };
};
