import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { createPortal } from "react-dom";
import {
  buildImageTransitionKeyframes,
  buildInterruptedCloseTransition,
  type ImageTransitionFrame,
} from "@/lib/image-lightbox-transition";
import { useReducedMotionPreference } from "@/lib/useReducedMotion";
import "./ImageLightbox.css";

interface ImageLightboxProps {
  src: string;
  alt?: string;
  caption?: string;
  showCaption?: boolean;
  originImage?: HTMLImageElement | null;
  onClose: () => void;
}

const clamp = (value: number, limit: number) => Math.min(limit, Math.max(-limit, value));
const OPEN_TRANSITION_DURATION = 280;
const CLOSE_TRANSITION_DURATION = 220;
const TRANSITION_EASING = "cubic-bezier(0.22, 0.61, 0.36, 1)";

const constrainImageOffset = (
  image: HTMLImageElement | null,
  next: { x: number; y: number },
  nextZoom: number,
) => {
  if (!image) return next;
  return {
    x: clamp(next.x, (image.offsetWidth * (nextZoom - 1)) / 2),
    y: clamp(next.y, (image.offsetHeight * (nextZoom - 1)) / 2),
  };
};

const isVisibleRect = (rect: DOMRect) => {
  return rect.width > 0
    && rect.height > 0
    && rect.right > 0
    && rect.bottom > 0
    && rect.left < window.innerWidth
    && rect.top < window.innerHeight;
};

const getRenderedBorderRadius = (image: HTMLImageElement, rect: DOMRect) => {
  const radius = Number.parseFloat(window.getComputedStyle(image).borderTopLeftRadius);
  if (!Number.isFinite(radius)) return 0;
  const scaleX = image.offsetWidth > 0 ? rect.width / image.offsetWidth : 1;
  const scaleY = image.offsetHeight > 0 ? rect.height / image.offsetHeight : 1;
  return radius * Math.min(scaleX, scaleY);
};

const createTransitionImage = (
  previewImage: HTMLImageElement,
  previewRect: DOMRect,
  initialFrame: ImageTransitionFrame,
) => {
  const transitionImage = document.createElement("img");
  transitionImage.src = previewImage.currentSrc || previewImage.src;
  transitionImage.alt = "";
  transitionImage.setAttribute("aria-hidden", "true");
  transitionImage.decoding = "async";
  Object.assign(transitionImage.style, {
    position: "fixed",
    top: `${previewRect.top}px`,
    left: `${previewRect.left}px`,
    width: `${previewRect.width}px`,
    height: `${previewRect.height}px`,
    maxWidth: "none",
    maxHeight: "none",
    margin: "0",
    borderRadius: "0",
    objectFit: "fill",
    objectPosition: "center",
    pointerEvents: "none",
    transformOrigin: "top left",
    transform: initialFrame.transform,
    clipPath: initialFrame.clipPath,
    willChange: "transform, clip-path",
    contain: "paint",
    zIndex: "1201",
  });
  document.body.appendChild(transitionImage);
  return transitionImage;
};

export default function ImageLightbox({
  src,
  alt = "",
  caption,
  showCaption = true,
  originImage = null,
  onClose,
}: ImageLightboxProps) {
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const [imageLoaded, setImageLoaded] = useState(false);
  const [imageReady, setImageReady] = useState(false);
  const [opening, setOpening] = useState(false);
  const [presented, setPresented] = useState(false);
  const [closing, setClosing] = useState(false);
  const prefersReducedMotion = useReducedMotionPreference();
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const onCloseRef = useRef(onClose);
  const zoomRef = useRef(1);
  const offsetRef = useRef({ x: 0, y: 0 });
  const transformFrameRef = useRef<number | null>(null);
  const pendingTransformRef = useRef({ zoom: 1, offset: { x: 0, y: 0 } });
  const dragRef = useRef<{ pointerId: number; x: number; y: number; offset: { x: number; y: number } } | null>(null);
  const pointersRef = useRef(new Map<number, { x: number; y: number }>());
  const transitionImageRef = useRef<HTMLImageElement | null>(null);
  const transitionAnimationRef = useRef<Animation | null>(null);
  const hiddenOriginRef = useRef<{ image: HTMLImageElement; opacity: string; willChange: string } | null>(null);
  const revealFrameRef = useRef<number | null>(null);
  const closingRef = useRef(false);
  const imageLoadedRef = useRef(false);
  const pinchRef = useRef<{
    distance: number;
    center: { x: number; y: number };
    zoom: number;
    offset: { x: number; y: number };
  } | null>(null);

  const constrainOffset = (next: { x: number; y: number }, nextZoom: number) => {
    return constrainImageOffset(imageRef.current, next, nextZoom);
  };

  const scheduleTransform = useCallback((nextZoom: number, nextOffset: { x: number; y: number }) => {
    zoomRef.current = nextZoom;
    offsetRef.current = nextOffset;
    pendingTransformRef.current = { zoom: nextZoom, offset: nextOffset };
    if (transformFrameRef.current !== null) return;
    transformFrameRef.current = window.requestAnimationFrame(() => {
      transformFrameRef.current = null;
      const nextTransform = pendingTransformRef.current;
      setZoom(nextTransform.zoom);
      setOffset(nextTransform.offset);
    });
  }, []);

  useEffect(() => {
    onCloseRef.current = onClose;
  }, [onClose]);

  const removeTransitionImage = useCallback(() => {
    const animation = transitionAnimationRef.current;
    if (animation) animation.cancel();
    transitionAnimationRef.current = null;
    transitionImageRef.current?.remove();
    transitionImageRef.current = null;
  }, []);

  const restoreOriginImage = useCallback(() => {
    const hiddenOrigin = hiddenOriginRef.current;
    if (!hiddenOrigin) return;
    hiddenOrigin.image.style.opacity = hiddenOrigin.opacity;
    hiddenOrigin.image.style.willChange = hiddenOrigin.willChange;
    hiddenOriginRef.current = null;
  }, []);

  const hideOriginImage = useCallback((image: HTMLImageElement) => {
    if (hiddenOriginRef.current?.image === image) return;
    restoreOriginImage();
    hiddenOriginRef.current = { image, opacity: image.style.opacity, willChange: image.style.willChange };
    image.style.willChange = "opacity";
    image.style.opacity = "0";
  }, [restoreOriginImage]);

  const playImageTransition = useCallback((
    previewImage: HTMLImageElement,
    sourceImage: HTMLImageElement,
    originRect: DOMRect,
    previewRect: DOMRect,
    direction: "open" | "close",
    duration: number,
    onFinished: () => void,
    retainTransitionImage = false,
    resumeActiveTransition = false,
  ) => {
    const keyframes = buildImageTransitionKeyframes({
      originRect,
      previewRect,
      objectPosition: window.getComputedStyle(sourceImage).objectPosition,
      originBorderRadius: getRenderedBorderRadius(sourceImage, originRect),
      previewBorderRadius: getRenderedBorderRadius(previewImage, previewRect),
    });
    if (!keyframes) {
      removeTransitionImage();
      onFinished();
      return;
    }

    let animationFrames = keyframes[direction];
    let animationDuration = duration;
    let transitionImage: HTMLImageElement;
    const activeTransitionImage = resumeActiveTransition ? transitionImageRef.current : null;
    const activeTransitionAnimation = resumeActiveTransition ? transitionAnimationRef.current : null;

    if (activeTransitionImage && activeTransitionAnimation) {
      const currentStyle = window.getComputedStyle(activeTransitionImage);
      const interrupted = buildInterruptedCloseTransition({
        currentFrame: {
          transform: currentStyle.transform,
          clipPath: currentStyle.clipPath,
        },
        originFrame: keyframes.close[1],
        openProgress: activeTransitionAnimation.effect?.getComputedTiming().progress ?? null,
        fullDuration: duration,
      });
      activeTransitionAnimation.cancel();
      animationFrames = interrupted.keyframes;
      animationDuration = interrupted.duration;
      transitionImage = activeTransitionImage;
      transitionImage.style.transform = animationFrames[0].transform;
      transitionImage.style.clipPath = animationFrames[0].clipPath;
    } else {
      const initialFrame = animationFrames[0];
      transitionImage = createTransitionImage(previewImage, previewRect, initialFrame);
    }

    transitionImageRef.current = transitionImage;
    const animation = transitionImage.animate(animationFrames, {
      duration: animationDuration,
      easing: TRANSITION_EASING,
      fill: "forwards",
    });
    transitionAnimationRef.current = animation;
    void animation.finished
      .catch(() => undefined)
      .then(() => {
        if (transitionAnimationRef.current !== animation) return;
        transitionAnimationRef.current = null;
        if (!retainTransitionImage) {
          transitionImage.remove();
          if (transitionImageRef.current === transitionImage) {
            transitionImageRef.current = null;
          }
        }
        onFinished();
      });
  }, [removeTransitionImage]);

  const finishClose = useCallback(() => {
    restoreOriginImage();
    onCloseRef.current();
  }, [restoreOriginImage]);

  const fadeOutAndClose = useCallback(() => {
    const overlay = overlayRef.current;
    if (!overlay) {
      finishClose();
      return;
    }
    const animation = overlay.animate([{ opacity: window.getComputedStyle(overlay).opacity }, { opacity: 0 }], {
      duration: prefersReducedMotion ? 1 : CLOSE_TRANSITION_DURATION,
      easing: TRANSITION_EASING,
      fill: "forwards",
    });
    transitionAnimationRef.current = animation;
    void animation.finished
      .catch(() => undefined)
      .then(() => {
        if (transitionAnimationRef.current !== animation) return;
        transitionAnimationRef.current = null;
        finishClose();
      });
  }, [finishClose, prefersReducedMotion]);

  const requestClose = useCallback(() => {
    if (closingRef.current) return;
    closingRef.current = true;
    setClosing(true);
    setOpening(false);
    if (revealFrameRef.current !== null) {
      window.cancelAnimationFrame(revealFrameRef.current);
      revealFrameRef.current = null;
    }
    const resumeActiveTransition = Boolean(
      transitionImageRef.current && transitionAnimationRef.current,
    );
    if (!resumeActiveTransition) removeTransitionImage();

    const targetImage = imageRef.current;
    if (prefersReducedMotion || !originImage || !targetImage || !originImage.isConnected) {
      removeTransitionImage();
      fadeOutAndClose();
      return;
    }

    const from = targetImage.getBoundingClientRect();
    const to = originImage.getBoundingClientRect();
    if (!isVisibleRect(from) || !isVisibleRect(to)) {
      removeTransitionImage();
      fadeOutAndClose();
      return;
    }

    hideOriginImage(originImage);
    setImageReady(false);
    playImageTransition(
      targetImage,
      originImage,
      to,
      from,
      "close",
      CLOSE_TRANSITION_DURATION,
      finishClose,
      false,
      resumeActiveTransition,
    );
  }, [fadeOutAndClose, finishClose, hideOriginImage, originImage, playImageTransition, prefersReducedMotion, removeTransitionImage]);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      setPresented(true);
    });
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    if (!presented || !imageLoaded || opening || closing) return;
    revealFrameRef.current = window.requestAnimationFrame(() => {
      revealFrameRef.current = null;
      setImageReady(true);
    });
    return () => {
      if (revealFrameRef.current !== null) {
        window.cancelAnimationFrame(revealFrameRef.current);
        revealFrameRef.current = null;
      }
    };
  }, [closing, imageLoaded, opening, presented]);

  useEffect(() => {
    if (!opening || !imageReady) return;
    removeTransitionImage();
    revealFrameRef.current = window.requestAnimationFrame(() => {
      revealFrameRef.current = window.requestAnimationFrame(() => {
        revealFrameRef.current = null;
        setOpening(false);
      });
    });
    return () => {
      if (revealFrameRef.current !== null) {
        window.cancelAnimationFrame(revealFrameRef.current);
        revealFrameRef.current = null;
      }
    };
  }, [imageReady, opening, removeTransitionImage]);

  useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") requestClose();
    };
    const overlay = overlayRef.current;
    const handleWheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) return;
      event.preventDefault();
      const nextZoom = Math.min(4, Math.max(1, zoomRef.current * Math.exp(-event.deltaY * 0.002)));
      const nextOffset = constrainImageOffset(imageRef.current, offsetRef.current, nextZoom);
      scheduleTransform(nextZoom, nextOffset);
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);
    overlay?.addEventListener("wheel", handleWheel, { passive: false });
    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", handleKeyDown);
      overlay?.removeEventListener("wheel", handleWheel);
      if (transformFrameRef.current !== null) {
        window.cancelAnimationFrame(transformFrameRef.current);
        transformFrameRef.current = null;
      }
    };
  }, [requestClose, scheduleTransform]);

  useEffect(() => {
    return () => {
      removeTransitionImage();
      restoreOriginImage();
      if (revealFrameRef.current !== null) {
        window.cancelAnimationFrame(revealFrameRef.current);
      }
    };
  }, [removeTransitionImage, restoreOriginImage]);

  const handlePreviewImageLoad = useCallback(() => {
    if (imageLoadedRef.current) return;
    imageLoadedRef.current = true;
    const targetImage = imageRef.current;
    if (prefersReducedMotion || !originImage || !targetImage || !originImage.isConnected) {
      setImageLoaded(true);
      return;
    }

    const from = originImage.getBoundingClientRect();
    const to = targetImage.getBoundingClientRect();
    if (!isVisibleRect(from) || !isVisibleRect(to)) {
      setImageLoaded(true);
      return;
    }

    hideOriginImage(originImage);
    setOpening(true);
    playImageTransition(
      targetImage,
      originImage,
      from,
      to,
      "open",
      OPEN_TRANSITION_DURATION,
      () => {
        setImageReady(true);
      },
      true,
    );
    setImageLoaded(true);
  }, [hideOriginImage, originImage, playImageTransition, prefersReducedMotion]);

  const handlePointerDown = (event: ReactPointerEvent<HTMLDivElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const pointers = [...pointersRef.current.values()];
    if (pointers.length === 2) {
      const center = { x: (pointers[0].x + pointers[1].x) / 2, y: (pointers[0].y + pointers[1].y) / 2 };
      pinchRef.current = {
        distance: Math.hypot(pointers[1].x - pointers[0].x, pointers[1].y - pointers[0].y),
        center,
        zoom: zoomRef.current,
        offset: offsetRef.current,
      };
      dragRef.current = null;
      setDragging(true);
      return;
    }
    if (zoomRef.current > 1) {
      dragRef.current = { pointerId: event.pointerId, x: event.clientX, y: event.clientY, offset: offsetRef.current };
      setDragging(true);
    }
  };

  const handlePointerMove = (event: ReactPointerEvent<HTMLDivElement>) => {
    if (!pointersRef.current.has(event.pointerId)) return;
    pointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const pointers = [...pointersRef.current.values()];
    if (pointers.length === 2 && pinchRef.current) {
      const distance = Math.hypot(pointers[1].x - pointers[0].x, pointers[1].y - pointers[0].y);
      const center = { x: (pointers[0].x + pointers[1].x) / 2, y: (pointers[0].y + pointers[1].y) / 2 };
      const nextZoom = Math.min(4, Math.max(1, pinchRef.current.zoom * distance / Math.max(pinchRef.current.distance, 1)));
      const nextOffset = constrainOffset({
        x: pinchRef.current.offset.x + center.x - pinchRef.current.center.x,
        y: pinchRef.current.offset.y + center.y - pinchRef.current.center.y,
      }, nextZoom);
      scheduleTransform(nextZoom, nextOffset);
      return;
    }
    const drag = dragRef.current;
    if (!drag || drag.pointerId !== event.pointerId) return;
    const nextOffset = constrainOffset({ x: drag.offset.x + event.clientX - drag.x, y: drag.offset.y + event.clientY - drag.y }, zoomRef.current);
    scheduleTransform(zoomRef.current, nextOffset);
  };

  const handlePointerEnd = (event: ReactPointerEvent<HTMLDivElement>) => {
    pointersRef.current.delete(event.pointerId);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) event.currentTarget.releasePointerCapture(event.pointerId);
    const [remainingPointer] = pointersRef.current.entries();
    if (remainingPointer && zoomRef.current > 1) {
      const [pointerId, point] = remainingPointer;
      dragRef.current = { pointerId, x: point.x, y: point.y, offset: offsetRef.current };
      setDragging(true);
    } else {
      dragRef.current = null;
      setDragging(false);
    }
    pinchRef.current = null;
  };

  const text = caption?.trim() || alt.trim();
  if (typeof document === "undefined") return null;
  return createPortal(
    <div ref={overlayRef} className={`aerisun-image-lightbox ${presented ? "is-presented" : ""} ${closing ? "is-closing" : ""}`} role="dialog" aria-modal="true" aria-label="查看图片" onClick={requestClose}>
      <figure className="aerisun-image-lightbox__frame" onClick={(event) => event.stopPropagation()}>
        <div className="aerisun-image-lightbox__viewport" onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerEnd} onPointerCancel={handlePointerEnd}>
          <img ref={imageRef} src={src} alt={alt} draggable={false} onLoad={handlePreviewImageLoad} onError={() => setImageLoaded(true)} onDragStart={(event) => event.preventDefault()} className={`aerisun-image-lightbox__image ${opening ? "is-opening" : ""} ${imageReady ? "is-ready" : ""} ${zoom > 1 ? "is-zoomed" : ""} ${dragging ? "is-dragging" : ""}`} style={{ transform: `translate3d(${offset.x}px, ${offset.y}px, 0) scale(${zoom})` }} />
        </div>
        {showCaption && text ? (
          <figcaption
            className={`aerisun-image-lightbox__caption ${imageReady && !closing ? "is-visible" : ""}`}
          >
            {text}
          </figcaption>
        ) : null}
      </figure>
    </div>,
    document.body,
  );
}
