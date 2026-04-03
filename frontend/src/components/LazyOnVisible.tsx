import { useEffect, useRef, useState, type ReactNode } from "react";

interface LazyOnVisibleProps {
  children: ReactNode;
  fallback?: ReactNode;
  rootMargin?: string;
  className?: string;
}

const DEFAULT_ROOT_MARGIN = "320px 0px";

export default function LazyOnVisible({
  children,
  fallback = null,
  rootMargin = DEFAULT_ROOT_MARGIN,
  className,
}: LazyOnVisibleProps) {
  const [visible, setVisible] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (visible) {
      return;
    }

    const element = containerRef.current;
    if (!element) {
      return;
    }

    if (typeof IntersectionObserver === "undefined") {
      setVisible(true);
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some((entry) => entry.isIntersecting)) {
          setVisible(true);
        }
      },
      { rootMargin },
    );

    observer.observe(element);
    return () => observer.disconnect();
  }, [rootMargin, visible]);

  return <div ref={containerRef} className={className}>{visible ? children : fallback}</div>;
}
