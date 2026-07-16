import { useCallback, useEffect, useRef, useState, type PointerEvent as ReactPointerEvent } from "react";
import { createPortal } from "react-dom";
import "./ImageLightbox.css";

interface ImageLightboxProps {
  src: string;
  alt?: string;
  caption?: string;
  onClose: () => void;
}

const clamp = (value: number, limit: number) => Math.min(limit, Math.max(-limit, value));

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

export default function ImageLightbox({ src, alt = "", caption, onClose }: ImageLightboxProps) {
  const [zoom, setZoom] = useState(1);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);
  const overlayRef = useRef<HTMLDivElement | null>(null);
  const imageRef = useRef<HTMLImageElement | null>(null);
  const onCloseRef = useRef(onClose);
  const zoomRef = useRef(1);
  const offsetRef = useRef({ x: 0, y: 0 });
  const transformFrameRef = useRef<number | null>(null);
  const pendingTransformRef = useRef({ zoom: 1, offset: { x: 0, y: 0 } });
  const dragRef = useRef<{ pointerId: number; x: number; y: number; offset: { x: number; y: number } } | null>(null);
  const pointersRef = useRef(new Map<number, { x: number; y: number }>());
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

  useEffect(() => {
    const originalOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onCloseRef.current();
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
  }, [scheduleTransform]);

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
    <div ref={overlayRef} className="aerisun-image-lightbox" role="dialog" aria-modal="true" aria-label="查看图片" onClick={onClose}>
      <figure className="aerisun-image-lightbox__frame" onClick={(event) => event.stopPropagation()}>
        <div className="aerisun-image-lightbox__viewport" onPointerDown={handlePointerDown} onPointerMove={handlePointerMove} onPointerUp={handlePointerEnd} onPointerCancel={handlePointerEnd}>
          <img ref={imageRef} src={src} alt={alt} draggable={false} onDragStart={(event) => event.preventDefault()} className={`aerisun-image-lightbox__image ${zoom > 1 ? "is-zoomed" : ""} ${dragging ? "is-dragging" : ""}`} style={{ transform: `translate3d(${offset.x}px, ${offset.y}px, 0) scale(${zoom})` }} />
        </div>
        {text ? <figcaption className="aerisun-image-lightbox__caption">{text}</figcaption> : null}
      </figure>
    </div>,
    document.body,
  );
}
