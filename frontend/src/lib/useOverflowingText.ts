import { useEffect, useState, type RefObject } from "react";

export const useOverflowingText = (
  viewportRef: RefObject<HTMLElement | null>,
  measureRef: RefObject<HTMLElement | null>,
  content: string,
  active: boolean,
) => {
  const [overflowing, setOverflowing] = useState(false);

  useEffect(() => {
    if (!active) {
      setOverflowing(false);
      return;
    }

    const measureOverflow = () => {
      const viewport = viewportRef.current;
      const measure = measureRef.current;
      if (!viewport || !measure) return;
      setOverflowing(measure.scrollWidth > viewport.clientWidth + 1);
    };
    const frame = requestAnimationFrame(measureOverflow);
    if (typeof ResizeObserver === "undefined") {
      return () => cancelAnimationFrame(frame);
    }

    const observer = new ResizeObserver(measureOverflow);
    if (viewportRef.current) observer.observe(viewportRef.current);
    if (measureRef.current) observer.observe(measureRef.current);
    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
    };
  }, [active, content, measureRef, viewportRef]);

  return overflowing;
};
