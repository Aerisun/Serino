import {
  createContext,
  useContext,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type ComponentPropsWithoutRef,
  type MouseEvent,
  type ReactNode,
  type RefObject,
} from "react";
import {
  createImageLoadQueue,
  type ImageLoadPriority,
  type ImageLoadQueue,
  type ImageLoadQueueHandle,
} from "@/lib/image-load-queue";
import { shouldBackgroundPrefetch } from "@/lib/idle";

const VIEWPORT_MARGIN = 240;
const OBSERVER_ROOT_MARGIN = `${VIEWPORT_MARGIN}px 0px`;

const ImageLoadQueueContext = createContext<ImageLoadQueue | null>(null);

type AttachmentImageProps = {
  src: string;
  alt: string;
  onOpen: (event: MouseEvent<HTMLButtonElement>) => void;
  imageProps?: Omit<
    ComponentPropsWithoutRef<"img">,
    "alt" | "decoding" | "fetchPriority" | "loading" | "src"
  >;
};

type QueuedImageLoad = {
  isControlled: boolean;
  isReady: boolean;
  imageKey: number | null;
  loading: "eager" | "lazy";
  fetchPriority: "high" | "low" | undefined;
  finish: (token: number) => void;
};

const isVisibleThroughAncestors = (element: HTMLElement) => {
  const elementRect = element.getBoundingClientRect();
  let ancestor = element.parentElement;

  while (ancestor) {
    const style = window.getComputedStyle(ancestor);
    if (style.display === "none" || style.visibility === "hidden") {
      return false;
    }

    const ancestorRect = ancestor.getBoundingClientRect();
    const clipsHorizontally = style.overflowX !== "visible";
    const clipsVertically = style.overflowY !== "visible";
    if (
      (clipsHorizontally && (elementRect.right <= ancestorRect.left || elementRect.left >= ancestorRect.right)) ||
      (clipsVertically && (elementRect.bottom <= ancestorRect.top || elementRect.top >= ancestorRect.bottom))
    ) {
      return false;
    }

    ancestor = ancestor.parentElement;
  }

  return true;
};

const getClippingAncestors = (element: HTMLElement) => {
  const ancestors: HTMLElement[] = [];
  let ancestor = element.parentElement;

  while (ancestor) {
    const style = window.getComputedStyle(ancestor);
    if (style.overflowX !== "visible" || style.overflowY !== "visible") {
      ancestors.push(ancestor);
    }
    ancestor = ancestor.parentElement;
  }

  return ancestors;
};

const isNearViewport = (element: HTMLElement) => {
  if (!isVisibleThroughAncestors(element)) {
    return false;
  }

  const { bottom, top } = element.getBoundingClientRect();
  return bottom >= -VIEWPORT_MARGIN && top <= window.innerHeight + VIEWPORT_MARGIN;
};

export function ImageLoadQueueProvider({ children }: { children: ReactNode }) {
  const queueRef = useRef<ImageLoadQueue | null>(null);
  if (!queueRef.current) {
    queueRef.current = createImageLoadQueue();
  }
  const queue = queueRef.current;

  useEffect(() => {
    if (!shouldBackgroundPrefetch()) {
      return;
    }

    const frameId = window.requestAnimationFrame(() => {
      queue.resumeBackground();
    });

    return () => window.cancelAnimationFrame(frameId);
  }, [queue]);

  return (
    <ImageLoadQueueContext.Provider value={queue}>
      {children}
    </ImageLoadQueueContext.Provider>
  );
}

export function ImageLoadQueueBoundary({ children }: { children: ReactNode }) {
  const parentQueue = useContext(ImageLoadQueueContext);

  if (parentQueue) {
    return children;
  }

  return <ImageLoadQueueProvider>{children}</ImageLoadQueueProvider>;
}

export function useQueuedImageLoad(
  targetRef: RefObject<HTMLElement | null>,
  src: string,
): QueuedImageLoad {
  const queue = useContext(ImageLoadQueueContext);
  const handleRef = useRef<ImageLoadQueueHandle | null>(null);
  const priorityRef = useRef<ImageLoadPriority>("background");
  const tokenRef = useRef(0);
  const [loadedImage, setLoadedImage] = useState<{
    src: string;
    token: number;
  } | null>(null);
  const [loadPriority, setLoadPriority] = useState<ImageLoadPriority>("background");

  useLayoutEffect(() => {
    if (!queue) {
      return undefined;
    }

    const target = targetRef.current;
    if (!target) {
      return undefined;
    }

    const token = tokenRef.current + 1;
    tokenRef.current = token;
    setLoadedImage(null);

    const start = () => {
      setLoadPriority(priorityRef.current);
      setLoadedImage({ src, token });
    };
    const initialPriority = isNearViewport(target) ? "foreground" : "background";
    priorityRef.current = initialPriority;
    const handle = queue.enqueue(initialPriority, start);
    handleRef.current = handle;

    const promoteIfNearViewport = () => {
      if (priorityRef.current === "foreground" || !isNearViewport(target)) {
        return;
      }

      priorityRef.current = "foreground";
      setLoadPriority("foreground");
      handleRef.current = handleRef.current?.promote() ?? null;
    };

    const observer = new IntersectionObserver(
      (entries) => {
        if (!entries.some((entry) => entry.isIntersecting)) {
          return;
        }

        promoteIfNearViewport();
      },
      { rootMargin: OBSERVER_ROOT_MARGIN },
    );
    observer.observe(target);
    const resizeObserver = typeof ResizeObserver === "function"
      ? new ResizeObserver(promoteIfNearViewport)
      : null;
    getClippingAncestors(target).forEach((ancestor) => resizeObserver?.observe(ancestor));

    return () => {
      observer.disconnect();
      resizeObserver?.disconnect();
      handle.cancel();
      if (handleRef.current === handle) {
        handleRef.current = null;
      }
    };
  }, [queue, src, targetRef]);

  const finish = (token: number) => {
    if (token !== tokenRef.current) {
      return;
    }
    handleRef.current?.finish();
  };

  const isReady = !queue || loadedImage?.src === src;
  return {
    isControlled: Boolean(queue),
    isReady,
    imageKey: loadedImage?.token ?? null,
    loading: queue ? "eager" : "lazy",
    fetchPriority: queue
      ? loadPriority === "foreground"
        ? "high"
        : "low"
      : undefined,
    finish,
  };
}

export function QueuedAttachmentImage({ src, alt, onOpen, imageProps }: AttachmentImageProps) {
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const imageLoad = useQueuedImageLoad(buttonRef, src);

  return (
    <button
      ref={buttonRef}
      type="button"
      className="aerisun-comment-image-button"
      onClick={onOpen}
      disabled={imageLoad.isControlled && !imageLoad.isReady}
      aria-busy={imageLoad.isControlled && !imageLoad.isReady}
      aria-label={alt ? `查看图片：${alt}` : "查看图片"}
    >
      {imageLoad.isReady ? (
        <img
          key={imageLoad.imageKey ?? src}
          {...imageProps}
          src={src}
          alt={alt}
          loading={imageLoad.loading}
          decoding="async"
          fetchPriority={imageLoad.fetchPriority}
          onLoad={(event) => {
            imageProps?.onLoad?.(event);
            void event.currentTarget.decode().catch(() => undefined).finally(() => {
              imageLoad.finish(imageLoad.imageKey ?? 0);
            });
          }}
          onError={(event) => {
            imageProps?.onError?.(event);
            imageLoad.finish(imageLoad.imageKey ?? 0);
          }}
        />
      ) : null}
    </button>
  );
}
