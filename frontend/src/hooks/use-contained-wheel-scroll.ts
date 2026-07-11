import { useEffect, useRef } from "react";

const SCROLL_EDGE_EPSILON = 1;
const WHEEL_DELTA_LINE = 1;
const WHEEL_DELTA_PAGE = 2;

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

export const getVerticalWheelDelta = ({
  deltaX,
  deltaY,
  deltaMode,
  pageSize,
}: {
  deltaX: number;
  deltaY: number;
  deltaMode: number;
  pageSize: number;
}) => {
  if (deltaY === 0 || Math.abs(deltaY) < Math.abs(deltaX)) {
    return 0;
  }

  const multiplier =
    deltaMode === WHEEL_DELTA_LINE
      ? 16
      : deltaMode === WHEEL_DELTA_PAGE
        ? pageSize
        : 1;

  return deltaY * multiplier;
};

export const shouldCaptureWheelScroll = ({
  scrollTop,
  clientHeight,
  scrollHeight,
  deltaY,
}: {
  scrollTop: number;
  clientHeight: number;
  scrollHeight: number;
  deltaY: number;
}) =>
  canScrollInDirection(scrollTop, clientHeight, scrollHeight, deltaY);

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

      const deltaY = getVerticalWheelDelta({
        deltaX: event.deltaX,
        deltaY: event.deltaY,
        deltaMode: event.deltaMode,
        pageSize: viewport.clientHeight,
      });
      const canScrollVertically = shouldCaptureWheelScroll({
        scrollTop: viewport.scrollTop,
        clientHeight: viewport.clientHeight,
        scrollHeight: viewport.scrollHeight,
        deltaY,
      });

      if (canScrollVertically) {
        event.preventDefault();
        event.stopPropagation();
        viewport.scrollTop += deltaY;
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
