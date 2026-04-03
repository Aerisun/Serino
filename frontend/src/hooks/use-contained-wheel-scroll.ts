import { useEffect, useRef } from "react";

const WHEEL_LINE_HEIGHT_PX = 18;

const normalizeWheelDelta = (
  delta: number,
  deltaMode: number,
  viewportSize: number,
) => {
  if (deltaMode === 1) {
    return delta * WHEEL_LINE_HEIGHT_PX;
  }

  if (deltaMode === 2) {
    return delta * viewportSize;
  }

  return delta;
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

      const maxScrollTop = viewport.scrollHeight - viewport.clientHeight;
      const maxScrollLeft = viewport.scrollWidth - viewport.clientWidth;
      if (maxScrollTop <= 0 && maxScrollLeft <= 0) {
        return;
      }

      const nextScrollTop = Math.max(
        0,
        Math.min(
          viewport.scrollTop +
            normalizeWheelDelta(event.deltaY, event.deltaMode, viewport.clientHeight),
          maxScrollTop,
        ),
      );
      const nextScrollLeft = Math.max(
        0,
        Math.min(
          viewport.scrollLeft +
            normalizeWheelDelta(event.deltaX, event.deltaMode, viewport.clientWidth),
          maxScrollLeft,
        ),
      );

      const scrollChanged =
        Math.abs(nextScrollTop - viewport.scrollTop) > 0.5 ||
        Math.abs(nextScrollLeft - viewport.scrollLeft) > 0.5;

      viewport.scrollTop = nextScrollTop;
      viewport.scrollLeft = nextScrollLeft;

      if (scrollChanged || maxScrollTop > 0 || maxScrollLeft > 0) {
        event.preventDefault();
        event.stopPropagation();
      }
    };

    region.addEventListener("wheel", handleWheel, { passive: false });
    return () => region.removeEventListener("wheel", handleWheel);
  }, []);

  return {
    regionRef,
    scrollViewportRef,
  };
};
