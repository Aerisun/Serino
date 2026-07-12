import {
  Children,
  cloneElement,
  Fragment,
  isValidElement,
  startTransition,
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  useCallback,
  type ComponentPropsWithoutRef,
  type HTMLAttributes,
  type KeyboardEvent as ReactKeyboardEvent,
  type MouseEvent,
  type PointerEvent as ReactPointerEvent,
  type ReactNode,
  type SyntheticEvent,
} from "react";
import { createPortal } from "react-dom";
import {
  Check,
  ChevronDown,
  Copy,
  ExternalLink,
  Info,
  Lightbulb,
  Link2,
  TriangleAlert,
  type LucideIcon,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkDirective from "remark-directive";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeHighlight from "rehype-highlight";
import rehypeKatex from "rehype-katex";
import rehypeSlug from "rehype-slug";
import rehypeAutolinkHeadings from "rehype-autolink-headings";
import type { Components } from "react-markdown";
import type { Options as RehypeHighlightOptions } from "rehype-highlight";
import { getFrontendLang } from "@/i18n";
import { frontendTranslations } from "@/i18n/translations";
import {
  buildPreviewImageUrl,
  fetchLinkPreview,
  type LinkPreviewPayload,
} from "@/lib/link-preview";
import MarkdownMermaid from "@/components/MarkdownMermaid";
import MarkdownCarousel from "@/components/MarkdownCarousel";
import { remarkAerisunDirectives } from "@/components/markdown-directives";
import { resolveMarkdownImageSrc } from "@/lib/markdown-image-url";
import "katex/dist/katex.min.css";
import "./markdown.css";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

type MarkdownDataPropsBase = {
  "data-md-kind"?: string;
  "data-md-type"?: string;
  "data-md-title"?: string;
  "data-md-label"?: string;
  "data-md-value"?: string;
  "data-md-summary"?: string;
};

type MarkdownDataDivProps = ComponentPropsWithoutRef<"div"> & MarkdownDataPropsBase;

type MarkdownDataSpanProps = ComponentPropsWithoutRef<"span"> & MarkdownDataPropsBase;

type MarkdownSectionProps = ComponentPropsWithoutRef<"section"> & {
  "data-footnotes"?: string | boolean;
};

type MarkdownAnchorProps = ComponentPropsWithoutRef<"a"> & {
  "data-footnote-backref"?: string | boolean;
  "data-footnote-ref"?: string | boolean;
};

type MarkdownAdmonitionType = "tip" | "warning" | "note" | "info" | "danger" | "success";
type MarkdownHeadingLevel = "h1" | "h2" | "h3" | "h4" | "h5" | "h6";
type MarkdownHeadingProps = HTMLAttributes<HTMLHeadingElement> & {
  level: MarkdownHeadingLevel;
};

const rehypeHighlightOptions: RehypeHighlightOptions = {
  plainText: ["mermaid", "text", "txt", "plain"],
  aliases: {
    javascript: ["js", "mjs", "cjs", "node", "jsx"],
    typescript: ["ts", "mts", "cts", "tsx"],
    bash: ["sh", "zsh"],
    shell: ["console", "shellsession"],
    python: "py",
    yaml: "yml",
    markdown: ["md", "mdx"],
    json: ["jsonc", "json5"],
    plaintext: ["text", "txt", "plain"],
    xml: ["html", "svg", "vue"],
    ini: ["env", "dotenv", "conf", "cfg"],
    csharp: ["cs", "dotnet"],
    cpp: ["cc", "cxx", "hpp", "hxx"],
  },
};

const isMermaidLanguage = (className?: string) => /(^|\s)language-mermaid(\s|$)/i.test(className ?? "");

const extractTextContent = (node: ReactNode): string => {
  if (typeof node === "string" || typeof node === "number") {
    return String(node);
  }

  if (Array.isArray(node)) {
    return node.map(extractTextContent).join("");
  }

  if (isValidElement<{ children?: ReactNode }>(node)) {
    return extractTextContent(node.props.children);
  }

  return "";
};

const normalizeCodeContent = (value: string) => value.replace(/\n$/, "");

const getText = (key: string, fallback: string) => {
  const lang = getFrontendLang();
  return frontendTranslations[lang][key] ?? fallback;
};

const copyTextToClipboard = async (value: string) => {
  if (typeof navigator !== "undefined" && navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(value);
    return;
  }

  if (typeof document === "undefined") {
    throw new Error("Clipboard is unavailable");
  }

  const textarea = document.createElement("textarea");
  textarea.value = value;
  textarea.setAttribute("readonly", "");
  textarea.style.position = "absolute";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();

  try {
    const copied = document.execCommand("copy");
    if (!copied) {
      throw new Error("Copy failed");
    }
  } finally {
    document.body.removeChild(textarea);
  }
};

let activeCopyToastElement: HTMLDivElement | null = null;
let activeCopyToastTimer: number | null = null;

const showCopyToast = (message: string) => {
  if (typeof document === "undefined") {
    return;
  }

  if (!activeCopyToastElement) {
    activeCopyToastElement = document.createElement("div");
    activeCopyToastElement.className = "markdown-copy-toast";
    activeCopyToastElement.setAttribute("role", "status");
    activeCopyToastElement.setAttribute("aria-live", "polite");
    document.body.appendChild(activeCopyToastElement);
  }

  activeCopyToastElement.textContent = message;
  activeCopyToastElement.classList.remove("is-visible");
  void activeCopyToastElement.getBoundingClientRect();
  activeCopyToastElement.classList.add("is-visible");

  if (activeCopyToastTimer !== null) {
    window.clearTimeout(activeCopyToastTimer);
  }

  activeCopyToastTimer = window.setTimeout(() => {
    activeCopyToastElement?.classList.remove("is-visible");
    activeCopyToastTimer = null;
  }, 1500);
};

const navigateToMarkdownTarget = (href: string) => {
  if (typeof window === "undefined" || !href.startsWith("#")) {
    return false;
  }

  const targetId = decodeURIComponent(href.slice(1));
  if (!targetId) {
    return false;
  }

  const target = document.getElementById(targetId);
  if (!target) {
    return false;
  }

  target.scrollIntoView({
    behavior: "smooth",
    block: "center",
  });
  window.history.pushState(null, "", href);
  return true;
};

const cleanChildrenArray = (children: ReactNode) =>
  Children.toArray(children).filter((child) => !(typeof child === "string" && child.trim() === ""));

const headingNumberPattern = /^(\d+(?:\.\d+)+\.?|\d+\.)(?=\s*(?:[\p{Script=Han}A-Za-z]|$))/u;

const formatHeadingNumberSpacing = (children: ReactNode): ReactNode => {
  let matched = false;

  const formatNode = (node: ReactNode): ReactNode => {
    if (matched) {
      return node;
    }

    if (typeof node === "string" || typeof node === "number") {
      const value = String(node);
      const match = value.match(headingNumberPattern);
      if (!match) {
        return node;
      }

      matched = true;
      const sectionNumber = match[1];
      const headingTitle = value.slice(sectionNumber.length).replace(/^\s+/, "");

      return (
        <>
          <span className="markdown-heading-number">{sectionNumber}</span>
          {headingTitle}
        </>
      );
    }

    if (isValidElement<{ children?: ReactNode }>(node) && node.props.children !== undefined) {
      return cloneElement(node, undefined, formatChildren(node.props.children));
    }

    return node;
  };

  const formatChildren = (value: ReactNode): ReactNode => Children.map(value, formatNode);

  return formatChildren(children);
};

const getHostnameLabel = (hostname: string) => hostname.replace(/^www\./, "");

const formatRichLinkTitle = (url: URL) => {
  const hostname = getHostnameLabel(url.hostname);
  const segments = url.pathname
    .split("/")
    .filter(Boolean)
    .map((segment) => {
      try {
        return decodeURIComponent(segment);
      } catch {
        return segment;
      }
    });

  if (hostname === "github.com" && segments.length >= 2) {
    return `${segments[0]}/${segments[1]}`;
  }

  if ((hostname === "youtu.be" || hostname.endsWith("youtube.com")) && segments.length > 0) {
    return segments.at(-1) ?? hostname;
  }

  if (hostname.endsWith("bilibili.com") && segments.length > 0) {
    return segments.join(" / ");
  }

  if (segments.length === 0) {
    return hostname;
  }

  return segments.join(" / ");
};

const formatRichLinkMeta = (url: URL) => {
  const hostname = getHostnameLabel(url.hostname);
  const path = `${url.pathname}${url.search}`.replace(/\/$/, "");
  return path ? `${hostname}${path}` : hostname;
};

const deriveFallbackImageUrl = (preview: LinkPreviewPayload | null, href: string) => {
  if (!preview) {
    return null;
  }

  try {
    const parsed = new URL(preview.resolved_url || href);
    const hostname = parsed.hostname.replace(/^www\./, "");

    if (hostname === "github.com") {
      const [owner] = parsed.pathname.split("/").filter(Boolean);
      if (owner) {
        return `https://avatars.githubusercontent.com/${owner}?size=160`;
      }
    }
  } catch {
    return null;
  }

  return null;
};

const normalizeRichLinkTitle = (title: string, siteName?: string | null, hostname?: string | null) => {
  const trimmed = title.trim();
  const candidates = [siteName, hostname?.replace(/^www\./, "", "")].filter(
    (value): value is string => Boolean(value?.trim()),
  );
  const separators = [" - ", ": ", " | ", " · "];

  for (const candidate of candidates) {
    const candidateValue = candidate.trim();
    const lowerCandidate = candidateValue.toLowerCase();
    const lowerTitle = trimmed.toLowerCase();

    for (const separator of separators) {
      const prefix = `${lowerCandidate}${separator}`;
      if (lowerTitle.startsWith(prefix)) {
        const normalized = trimmed.slice(prefix.length).trim();
        return normalized || trimmed;
      }
    }
  }

  return trimmed;
};

const normalizeRichLinkDescription = (description: string, title: string, fallback: string) => {
  const normalizedDescription = description.trim();
  const normalizedTitle = title.trim();
  if (!normalizedDescription) {
    return fallback;
  }

  const clean = (value: string) =>
    value
      .toLowerCase()
      .replace(/\s+/g, " ")
      .replace(/[|·:：\-–—]+/g, " ")
      .trim();

  const plainDescription = clean(normalizedDescription);
  const plainTitle = clean(normalizedTitle);

  if (!plainDescription || !plainTitle) {
    return normalizedDescription;
  }

  if (plainDescription === plainTitle) {
    return fallback;
  }

  if (plainDescription.startsWith(plainTitle) || plainTitle.startsWith(plainDescription)) {
    return fallback;
  }

  return normalizedDescription;
};

const getAdmonitionConfig = (type: MarkdownAdmonitionType): { icon: LucideIcon; label: string } => {
  switch (type) {
    case "tip":
      return { icon: Lightbulb, label: getText("markdown.tip", "提示") };
    case "warning":
      return { icon: TriangleAlert, label: getText("markdown.warning", "注意") };
    case "danger":
      return { icon: TriangleAlert, label: getText("markdown.danger", "警告") };
    case "success":
      return { icon: Check, label: getText("markdown.success", "完成") };
    case "info":
      return { icon: Info, label: getText("markdown.info", "信息") };
    case "note":
    default:
      return { icon: Info, label: getText("markdown.note", "注记") };
  }
};

function MarkdownTabPane({ title: _title, children }: { title: string; children: ReactNode }) {
  return <Fragment>{children}</Fragment>;
}

function MarkdownRichLinkCard({ href }: { href: string }) {
  const [preview, setPreview] = useState<LinkPreviewPayload | null>(null);
  const [imageState, setImageState] = useState<"primary" | "fallback" | "hidden">("primary");
  const parsedUrl = useMemo(() => {
    try {
      return new URL(href);
    } catch {
      return null;
    }
  }, [href]);

  useEffect(() => {
    if (!parsedUrl || typeof window === "undefined") {
      return undefined;
    }

    const controller = new AbortController();

    void fetchLinkPreview(href, controller.signal).then((payload) => {
      if (!payload?.available) {
        return;
      }

      startTransition(() => {
        setPreview(payload);
      });
    });

    return () => controller.abort();
  }, [href, parsedUrl]);

  useEffect(() => {
    setImageState("primary");
  }, [href, preview?.image_url]);

  if (!parsedUrl) {
    return (
      <a
        href={href}
        target="_blank"
        rel="noopener noreferrer"
        className="markdown-link-card"
      >
        <span className="markdown-link-card-badge">
          <Link2 className="h-3.5 w-3.5" />
          <span>{getText("markdown.linkCard", "链接")}</span>
        </span>
        <span className="markdown-link-card-title">{href}</span>
      </a>
    );
  }

  const cardHref = preview?.resolved_url || href;
  const badgeLabel = preview?.site_name || getHostnameLabel(parsedUrl.hostname);
  const cardTitle = preview?.title
    ? normalizeRichLinkTitle(preview.title, preview.site_name, preview.hostname)
    : formatRichLinkTitle(parsedUrl);
  const fallbackMeta = formatRichLinkMeta(parsedUrl);
  const cardMeta = preview?.description
    ? normalizeRichLinkDescription(preview.description, cardTitle, fallbackMeta)
    : fallbackMeta;
  const primaryImageUrl = preview?.image_url ? buildPreviewImageUrl(preview.image_url) : null;
  const fallbackImageUrl = deriveFallbackImageUrl(preview, href);
  const imageUrl =
    imageState === "primary"
      ? primaryImageUrl
      : imageState === "fallback"
        ? fallbackImageUrl
        : null;
  const iconUrl = preview?.icon_url || null;
  const imageMode =
    preview?.image_mode === "thumbnail" || preview?.card_type === "github_profile"
      ? "thumbnail"
      : "cover";
  const mediaModeClass = imageUrl
    ? imageMode === "thumbnail"
      ? " has-thumbnail-media"
      : " has-cover-media"
    : "";

  return (
    <a
      href={cardHref}
      target="_blank"
      rel="noopener noreferrer"
      className={`markdown-link-card${imageUrl ? " has-media" : ""}${mediaModeClass}`}
    >
      {imageUrl ? (
        <span className="markdown-link-card-media">
          <img
            src={imageUrl}
            alt={cardTitle}
            className="markdown-link-card-image"
            loading="lazy"
            referrerPolicy="no-referrer"
            onError={() => {
              if (imageState === "primary" && fallbackImageUrl) {
                setImageState("fallback");
                return;
              }
              setImageState("hidden");
            }}
          />
        </span>
      ) : null}

      <span className="markdown-link-card-badge">
        {iconUrl ? (
          <img
            src={iconUrl}
            alt=""
            className="markdown-link-card-favicon"
            loading="lazy"
            referrerPolicy="no-referrer"
          />
        ) : (
          <Link2 className="h-3.5 w-3.5" />
        )}
        <span>{badgeLabel}</span>
      </span>
      <span className="markdown-link-card-title">{cardTitle}</span>
      <span className="markdown-link-card-meta">{cardMeta}</span>
      <span className="markdown-link-card-arrow">
        <ExternalLink className="h-4 w-4" />
      </span>
    </a>
  );
}

function MarkdownImage({
  src,
  alt,
  title,
  className,
  onLoad,
  ...props
}: ComponentPropsWithoutRef<"img">) {
  const [open, setOpen] = useState(false);
  const [isPortrait, setIsPortrait] = useState(false);
  const [viewerZoom, setViewerZoom] = useState(1);
  const [viewerOffset, setViewerOffset] = useState({ x: 0, y: 0 });
  const [isViewerDragging, setIsViewerDragging] = useState(false);
  const viewerZoomRef = useRef(1);
  const viewerOffsetRef = useRef({ x: 0, y: 0 });
  const viewerImageRef = useRef<HTMLImageElement | null>(null);
  const viewerOverlayRef = useRef<HTMLDivElement | null>(null);
  const viewerPointersRef = useRef(new Map<number, { x: number; y: number }>());
  const viewerDragRef = useRef<{
    pointerId: number;
    origin: { x: number; y: number };
    offset: { x: number; y: number };
  } | null>(null);
  const viewerPinchRef = useRef<{
    distance: number;
    center: { x: number; y: number };
    zoom: number;
    offset: { x: number; y: number };
  } | null>(null);
  const caption = title?.trim() || alt?.trim();
  const resolvedSrc = resolveMarkdownImageSrc(src);
  const zoomLabel = getText("markdown.imageZoom", "查看大图");
  const imageClassName = [
    "markdown-figure-image",
    isPortrait ? "markdown-figure-image--portrait" : "",
    className ?? "",
  ].join(" ").trim();

  const handleImageLoad = (event: SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    setIsPortrait(image.naturalHeight > image.naturalWidth);
    onLoad?.(event);
  };

  const resetViewerTransform = useCallback(() => {
    viewerPointersRef.current.clear();
    viewerDragRef.current = null;
    viewerPinchRef.current = null;
    viewerZoomRef.current = 1;
    viewerOffsetRef.current = { x: 0, y: 0 };
    setViewerZoom(1);
    setViewerOffset({ x: 0, y: 0 });
    setIsViewerDragging(false);
  }, []);

  const closeViewer = useCallback(() => {
    resetViewerTransform();
    setOpen(false);
  }, [resetViewerTransform]);

  const clampViewerOffset = (offset: { x: number; y: number }, zoom: number) => {
    const image = viewerImageRef.current;
    if (!image) {
      return offset;
    }

    const maxX = Math.max(0, (image.offsetWidth * (zoom - 1)) / 2);
    const maxY = Math.max(0, (image.offsetHeight * (zoom - 1)) / 2);
    return {
      x: Math.min(maxX, Math.max(-maxX, offset.x)),
      y: Math.min(maxY, Math.max(-maxY, offset.y)),
    };
  };

  const getViewerPointerPair = () => Array.from(viewerPointersRef.current.values()).slice(0, 2);

  const handleViewerPointerDown = (event: ReactPointerEvent<HTMLElement>) => {
    event.currentTarget.setPointerCapture(event.pointerId);
    viewerPointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const pointers = getViewerPointerPair();
    const currentZoom = viewerZoomRef.current;

    if (pointers.length === 2) {
      const [first, second] = pointers;
      viewerDragRef.current = null;
      viewerPinchRef.current = {
        distance: Math.hypot(second.x - first.x, second.y - first.y),
        center: { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 },
        zoom: currentZoom,
        offset: viewerOffsetRef.current,
      };
      setIsViewerDragging(true);
      return;
    }

    if (currentZoom > 1) {
      viewerDragRef.current = {
        pointerId: event.pointerId,
        origin: { x: event.clientX, y: event.clientY },
        offset: viewerOffsetRef.current,
      };
      setIsViewerDragging(true);
    }
  };

  const handleViewerPointerMove = (event: ReactPointerEvent<HTMLElement>) => {
    if (!viewerPointersRef.current.has(event.pointerId)) {
      return;
    }

    viewerPointersRef.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const pointers = getViewerPointerPair();
    const pinch = viewerPinchRef.current;

    if (pointers.length === 2 && pinch) {
      const [first, second] = pointers;
      const distance = Math.hypot(second.x - first.x, second.y - first.y);
      const center = { x: (first.x + second.x) / 2, y: (first.y + second.y) / 2 };
      const nextZoom = Math.min(4, Math.max(1, pinch.zoom * (distance / Math.max(pinch.distance, 1))));
      const nextOffset = clampViewerOffset(
        {
          x: pinch.offset.x + center.x - pinch.center.x,
          y: pinch.offset.y + center.y - pinch.center.y,
        },
        nextZoom,
      );
      viewerZoomRef.current = nextZoom;
      viewerOffsetRef.current = nextOffset;
      setViewerZoom(nextZoom);
      setViewerOffset(nextOffset);
      return;
    }

    const drag = viewerDragRef.current;
    const currentZoom = viewerZoomRef.current;
    if (drag?.pointerId !== event.pointerId || currentZoom <= 1) {
      return;
    }

    const nextOffset = clampViewerOffset({
      x: drag.offset.x + event.clientX - drag.origin.x,
      y: drag.offset.y + event.clientY - drag.origin.y,
    }, currentZoom);
    viewerOffsetRef.current = nextOffset;
    setViewerOffset(nextOffset);
  };

  const handleViewerPointerEnd = (event: ReactPointerEvent<HTMLElement>) => {
    viewerPointersRef.current.delete(event.pointerId);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }

    const [remainingPointer] = viewerPointersRef.current.entries();
    if (remainingPointer && viewerZoomRef.current > 1) {
      const [pointerId, origin] = remainingPointer;
      viewerDragRef.current = {
        pointerId,
        origin,
        offset: viewerOffsetRef.current,
      };
      setIsViewerDragging(true);
    } else {
      viewerDragRef.current = null;
      setIsViewerDragging(false);
    }
    viewerPinchRef.current = null;
  };

  useEffect(() => {
    if (!open || typeof window === "undefined") {
      return undefined;
    }

    const originalOverflow = document.body.style.overflow;
    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeViewer();
      }
    };

    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", handleKeyDown);

    return () => {
      document.body.style.overflow = originalOverflow;
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [open, closeViewer]);

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const overlay = viewerOverlayRef.current;
    if (!overlay) {
      return undefined;
    }

    const handleNativeViewerWheel = (event: WheelEvent) => {
      if (!event.ctrlKey && !event.metaKey) {
        return;
      }

      event.preventDefault();
      const nextZoom = Math.min(4, Math.max(1, viewerZoomRef.current * Math.exp(-event.deltaY * 0.002)));
      viewerZoomRef.current = nextZoom;
      setViewerZoom(nextZoom);
      const nextOffset = clampViewerOffset(viewerOffsetRef.current, nextZoom);
      viewerOffsetRef.current = nextOffset;
      setViewerOffset(nextOffset);
    };

    overlay.addEventListener("wheel", handleNativeViewerWheel, { passive: false });
    return () => overlay.removeEventListener("wheel", handleNativeViewerWheel);
  }, [open]);

  return (
    <>
      <span className="markdown-figure">
        <button
          type="button"
          className="markdown-figure-button"
          onClick={() => {
            resetViewerTransform();
            setOpen(true);
          }}
          aria-label={zoomLabel}
        >
          <img
            src={resolvedSrc}
            alt={alt}
            className={imageClassName}
            loading="lazy"
            decoding="async"
            onLoad={handleImageLoad}
            {...props}
          />
        </button>
        {caption ? <span className="markdown-figure-caption">{caption}</span> : null}
      </span>

      {open && resolvedSrc && typeof document !== "undefined"
        ? createPortal(
            <div
              ref={viewerOverlayRef}
              className="markdown-image-lightbox"
              role="dialog"
              aria-modal="true"
              aria-label={zoomLabel}
              onClick={closeViewer}
            >
              <figure
                className="markdown-image-lightbox-frame"
                onClick={(event) => event.stopPropagation()}
              >
                <div
                  className="markdown-image-lightbox-viewport"
                  onPointerDown={handleViewerPointerDown}
                  onPointerMove={handleViewerPointerMove}
                  onPointerUp={handleViewerPointerEnd}
                  onPointerCancel={handleViewerPointerEnd}
                >
                  <img
                    ref={viewerImageRef}
                    src={resolvedSrc}
                    alt={alt}
                    className={`markdown-image-lightbox-image ${viewerZoom > 1 ? "is-zoomed" : ""} ${isViewerDragging ? "is-dragging" : ""}`}
                    style={{ transform: `translate3d(${viewerOffset.x}px, ${viewerOffset.y}px, 0) scale(${viewerZoom})` }}
                    draggable={false}
                    onDragStart={(event) => event.preventDefault()}
                  />
                </div>
                {caption ? (
                  <figcaption className="markdown-image-lightbox-caption">{caption}</figcaption>
                ) : null}
              </figure>
            </div>,
            document.body,
          )
        : null}
    </>
  );
}

function MarkdownParagraph({ children, ...props }: ComponentPropsWithoutRef<"p">) {
  const cleanChildren = cleanChildrenArray(children);
  if (cleanChildren.length === 1) {
    const child = cleanChildren[0];
    if (isValidElement<{ href?: string; children?: ReactNode }>(child)) {
      const href = child.props.href?.trim();
      if (href && /^https?:\/\//i.test(href)) {
        return <MarkdownRichLinkCard href={href} />;
      }
    }
  }

  return <p {...props}>{children}</p>;
}

function MarkdownAdmonition({
  type,
  title,
  children,
}: {
  type: MarkdownAdmonitionType;
  title?: string;
  children: ReactNode;
}) {
  const { icon: Icon, label } = getAdmonitionConfig(type);

  return (
    <div className={`markdown-admonition markdown-admonition-${type}`}>
      <div className="markdown-admonition-head">
        <span className="markdown-admonition-icon">
          <Icon className="h-4 w-4" />
        </span>
        <span className="markdown-admonition-title">{title || label}</span>
      </div>
      <div className="markdown-admonition-body">{children}</div>
    </div>
  );
}

function MarkdownDetailsBlock({ summary, children }: { summary: string; children: ReactNode }) {
  const [open, setOpen] = useState(false);
  const toggleLabel = open
    ? getText("markdown.collapse", "收起内容")
    : getText("markdown.expand", "展开内容");

  return (
    <div className={`markdown-details ${open ? "is-open" : ""}`}>
      <button
        type="button"
        className="markdown-details-summary"
        aria-expanded={open}
        aria-label={toggleLabel}
        onClick={() => setOpen((value) => !value)}
      >
        <span>{summary || getText("markdown.expand", "展开内容")}</span>
        <ChevronDown className="h-4 w-4" />
      </button>
      <div className="markdown-details-panel">{children}</div>
    </div>
  );
}

function MarkdownUnderline({ children }: { children: ReactNode }) {
  return <span className="markdown-underline">{children}</span>;
}

function MarkdownThumbnailBlock({ children }: { children: ReactNode }) {
  return <div className="markdown-thumbnail">{children}</div>;
}

function MarkdownCarouselBlock({ children }: { children: ReactNode }) {
  return <MarkdownCarousel>{children}</MarkdownCarousel>;
}

function MarkdownTabsBlock({ children }: { children: ReactNode }) {
  const tabsId = useId();
  const panes = useMemo(() => {
    return cleanChildrenArray(children)
      .map((child, index) => {
        if (!isValidElement<{ title?: string; children?: ReactNode }>(child)) {
          return null;
        }

        if (child.type !== MarkdownTabPane) {
          return null;
        }

        const title = child.props.title?.trim() || `${getText("markdown.tab", "标签")} ${index + 1}`;
        return {
          id: `${tabsId}-${index}`,
          title,
          content: child.props.children,
        };
      })
      .filter((item): item is { id: string; title: string; content: ReactNode } => item !== null);
  }, [children, tabsId]);
  const [activeId, setActiveId] = useState<string | null>(panes[0]?.id ?? null);

  useEffect(() => {
    if (!panes.some((pane) => pane.id === activeId)) {
      setActiveId(panes[0]?.id ?? null);
    }
  }, [activeId, panes]);

  const activePane = panes.find((pane) => pane.id === activeId) ?? panes[0];
  if (!activePane) {
    return <div className="markdown-tabs">{children}</div>;
  }

  return (
    <div className="markdown-tabs">
      <div className="markdown-tabs-list" role="tablist">
        {panes.map((pane) => {
          const active = pane.id === activePane.id;
          return (
            <button
              key={pane.id}
              type="button"
              role="tab"
              aria-selected={active}
              className={`markdown-tab-trigger ${active ? "is-active" : ""}`}
              onClick={() => setActiveId(pane.id)}
            >
              {pane.title}
            </button>
          );
        })}
      </div>
      <div className="markdown-tab-panel" role="tabpanel">
        {activePane.content}
      </div>
    </div>
  );
}

function MarkdownStepsBlock({ children }: { children: ReactNode }) {
  return <div className="markdown-steps">{children}</div>;
}

function MarkdownCopySurface({
  children,
  title,
  label,
  value,
  inline = false,
}: {
  children: ReactNode;
  title?: string;
  label?: string;
  value?: string;
  inline?: boolean;
}) {
  const contentRef = useRef<HTMLDivElement | HTMLSpanElement | null>(null);
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");

  useEffect(() => {
    if (copyState === "idle") {
      return undefined;
    }

    const timer = window.setTimeout(() => {
      setCopyState("idle");
    }, 1600);
    return () => window.clearTimeout(timer);
  }, [copyState]);

  const idleLabel = label?.trim() || getText("markdown.copyAction", "点击复制");
  const statusLabel =
    copyState === "copied"
      ? getText("code.copied", "已复制")
      : copyState === "failed"
        ? getText("code.failed", "失败")
        : idleLabel;

  const handleCopy = async (nextValue?: string) => {
    const resolvedValue =
      nextValue?.trim()
      || value?.trim()
      || contentRef.current?.innerText?.trim()
      || extractTextContent(children).trim();

    if (!resolvedValue) {
      setCopyState("failed");
      return;
    }

    try {
      await copyTextToClipboard(resolvedValue);
      setCopyState("copied");
      showCopyToast(getText("code.copied", "已复制"));
    } catch {
      setCopyState("failed");
    }
  };

  const handleKeyDown = (event: ReactKeyboardEvent<HTMLDivElement | HTMLSpanElement>) => {
    if (event.key !== "Enter" && event.key !== " ") {
      return;
    }
    event.preventDefault();
    void handleCopy();
  };

  if (inline) {
    return (
      <span
        className={`markdown-copy-inline ${copyState !== "idle" ? `is-${copyState}` : ""}`}
        role="button"
        tabIndex={0}
        aria-label={title?.trim() || statusLabel}
        onClick={() => void handleCopy()}
        onKeyDown={handleKeyDown}
      >
        <code ref={contentRef} className="markdown-copy-inline-content">
          {children}
        </code>
      </span>
    );
  }

  return (
    <div className={`markdown-copy-block ${copyState !== "idle" ? `is-${copyState}` : ""}`}>
      <div
        ref={(node) => {
          contentRef.current = node;
        }}
        className="markdown-copy-block-body"
      >
        {children}
      </div>
      <button
        type="button"
        className="markdown-copy-block-icon"
        aria-label={title?.trim() || statusLabel}
        title={statusLabel}
        onClick={() => void handleCopy()}
        onKeyDown={handleKeyDown}
      >
        {copyState === "copied" ? <Check className="h-3.5 w-3.5" /> : <Copy className="h-3.5 w-3.5" />}
      </button>
    </div>
  );
}

function MarkdownDiv({
  children,
  className,
  ...props
}: MarkdownDataDivProps) {
  const kind = props["data-md-kind"];

  if (kind === "admonition") {
    return (
      <MarkdownAdmonition
        type={(props["data-md-type"] as MarkdownAdmonitionType) || "note"}
        title={props["data-md-title"]}
      >
        {children}
      </MarkdownAdmonition>
    );
  }

  if (kind === "details") {
    return (
      <MarkdownDetailsBlock summary={props["data-md-summary"] || ""}>
        {children}
      </MarkdownDetailsBlock>
    );
  }

  if (kind === "thumbnail") {
    return <MarkdownThumbnailBlock>{children}</MarkdownThumbnailBlock>;
  }

  if (kind === "carousel") {
    return <MarkdownCarouselBlock>{children}</MarkdownCarouselBlock>;
  }

  if (kind === "tabs") {
    return <MarkdownTabsBlock>{children}</MarkdownTabsBlock>;
  }

  if (kind === "tab") {
    return (
      <MarkdownTabPane title={props["data-md-title"] || ""}>
        {children}
      </MarkdownTabPane>
    );
  }

  if (kind === "steps") {
    return <MarkdownStepsBlock>{children}</MarkdownStepsBlock>;
  }

  if (kind === "copy") {
    return (
      <MarkdownCopySurface
        title={props["data-md-title"]}
        label={props["data-md-label"]}
        value={props["data-md-value"]}
      >
        {children}
      </MarkdownCopySurface>
    );
  }

  return (
    <div className={className} {...props}>
      {children}
    </div>
  );
}

function MarkdownSpan({
  children,
  className,
  ...props
}: MarkdownDataSpanProps) {
  if (props["data-md-kind"] === "underline") {
    return <MarkdownUnderline>{children}</MarkdownUnderline>;
  }

  if (props["data-md-kind"] === "copy") {
    return (
      <MarkdownCopySurface
        title={props["data-md-title"]}
        label={props["data-md-label"]}
        value={props["data-md-value"]}
        inline
      >
        {children}
      </MarkdownCopySurface>
    );
  }

  return (
    <span className={className} {...props}>
      {children}
    </span>
  );
}

function MarkdownAnchor({ children, href, className, ...props }: MarkdownAnchorProps) {
  const isExternal = /^https?:\/\//i.test(href ?? "");
  const isHashLink = href?.startsWith("#");
  const isFootnoteBackref = Boolean(props["data-footnote-backref"]);
  const isFootnoteRef = Boolean(props["data-footnote-ref"]);
  const footnoteBackLabel = getText("markdown.footnoteBack", "返回引用");

  const handleClick = (event: MouseEvent<HTMLAnchorElement>) => {
    if (isHashLink && href) {
      const navigated = navigateToMarkdownTarget(href);
      if (navigated) {
        event.preventDefault();
      }
    }
  };

  return (
    <a
      href={href}
      className={[
        "transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.92)]",
        isFootnoteBackref ? "markdown-footnote-backref" : "",
        isFootnoteRef ? "markdown-footnote-ref-link" : "",
        className ?? "",
      ].join(" ").trim()}
      aria-label={isFootnoteBackref ? footnoteBackLabel : props["aria-label"]}
      title={isFootnoteBackref ? footnoteBackLabel : props.title}
      target={isExternal ? "_blank" : undefined}
      rel={isExternal ? "noopener noreferrer" : undefined}
      onClick={handleClick}
      {...props}
    >
      {children}
    </a>
  );
}

function MarkdownTable({ children, className, ...props }: ComponentPropsWithoutRef<"table">) {
  return (
    <div className="markdown-table-wrap">
      <table
        className={["markdown-table", className ?? ""].join(" ").trim()}
        {...props}
      >
        {children}
      </table>
    </div>
  );
}

function MarkdownSection({ children, className, ...props }: MarkdownSectionProps) {
  if (props["data-footnotes"]) {
    return (
      <section
        className={["markdown-footnotes", className ?? ""].join(" ").trim()}
        {...props}
      >
        {children}
      </section>
    );
  }

  return (
    <section className={className} {...props}>
      {children}
    </section>
  );
}

function MarkdownSup({ children, className, ...props }: ComponentPropsWithoutRef<"sup">) {
  const cleanChildren = cleanChildrenArray(children);
  const child = cleanChildren[0];
  const isFootnoteRef =
    cleanChildren.length === 1
    && isValidElement<{ href?: string }>(child)
    && child.type === "a"
    && typeof child.props.href === "string"
    && /#(?:user-content-)?fn-/.test(child.props.href);

  return (
    <sup
      className={[
        isFootnoteRef ? "markdown-footnote-ref" : "",
        className ?? "",
      ].join(" ").trim()}
      {...props}
    >
      {children}
    </sup>
  );
}

function MarkdownHeading({
  level,
  children,
  className,
  ...props
}: MarkdownHeadingProps) {
  const headingClassName = [
    `markdown-heading markdown-heading--${level}`,
    className ?? "",
  ].join(" ").trim();
  const content = formatHeadingNumberSpacing(children);

  switch (level) {
    case "h1":
      return <h1 className={headingClassName} {...props}>{content}</h1>;
    case "h2":
      return <h2 className={headingClassName} {...props}>{content}</h2>;
    case "h3":
      return <h3 className={headingClassName} {...props}>{content}</h3>;
    case "h4":
      return <h4 className={headingClassName} {...props}>{content}</h4>;
    case "h5":
      return <h5 className={headingClassName} {...props}>{content}</h5>;
    case "h6":
      return <h6 className={headingClassName} {...props}>{content}</h6>;
    default:
      return <h2 className={headingClassName} {...props}>{content}</h2>;
  }
}

function MarkdownPre({ children, className, ...props }: ComponentPropsWithoutRef<"pre">) {
  const [copyState, setCopyState] = useState<"idle" | "copied" | "failed">("idle");
  const lang = getFrontendLang();
  const labels = frontendTranslations[lang];
  const childArray = Children.toArray(children);
  const codeChild = childArray.find((child) => isValidElement(child));
  const codeClassName =
    isValidElement<{ className?: string; children?: ReactNode }>(codeChild)
      ? codeChild.props.className
      : undefined;
  const copyValue = normalizeCodeContent(
    isValidElement<{ children?: ReactNode }>(codeChild)
      ? extractTextContent(codeChild.props.children)
      : extractTextContent(children),
  );
  const mermaidBlock = isMermaidLanguage(codeClassName);

  useEffect(() => {
    if (copyState === "idle") {
      return undefined;
    }

    const timer = window.setTimeout(() => setCopyState("idle"), 1800);
    return () => window.clearTimeout(timer);
  }, [copyState]);

  const handleCopy = async () => {
    try {
      await copyTextToClipboard(copyValue);
      setCopyState("copied");
    } catch {
      setCopyState("failed");
    }
  };

  const copyLabel =
    copyState === "copied"
      ? labels["code.copied"]
      : copyState === "failed"
        ? labels["code.failed"]
        : labels["code.copy"];

  if (mermaidBlock) {
    return <MarkdownMermaid chart={copyValue} />;
  }

  return (
    <div className="markdown-code-block">
      <button
        type="button"
        className="markdown-copy-button"
        aria-label={copyLabel}
        title={copyLabel}
        onClick={() => void handleCopy()}
      >
        {copyState === "copied" ? (
          <Check className="h-3.5 w-3.5" />
        ) : (
          <Copy className="h-3.5 w-3.5" />
        )}
        <span>{copyLabel}</span>
      </button>
      <pre className={`markdown-code-pre ${className ?? ""}`.trim()} {...props}>
        {children}
      </pre>
    </div>
  );
}

const components = {
  h1: (props: ComponentPropsWithoutRef<"h1">) => <MarkdownHeading level="h1" {...props} />,
  h2: (props: ComponentPropsWithoutRef<"h2">) => <MarkdownHeading level="h2" {...props} />,
  h3: (props: ComponentPropsWithoutRef<"h3">) => <MarkdownHeading level="h3" {...props} />,
  h4: (props: ComponentPropsWithoutRef<"h4">) => <MarkdownHeading level="h4" {...props} />,
  h5: (props: ComponentPropsWithoutRef<"h5">) => <MarkdownHeading level="h5" {...props} />,
  h6: (props: ComponentPropsWithoutRef<"h6">) => <MarkdownHeading level="h6" {...props} />,
  a: MarkdownAnchor,
  p: MarkdownParagraph,
  img: MarkdownImage,
  pre: MarkdownPre,
  div: MarkdownDiv,
  span: MarkdownSpan,
  table: MarkdownTable,
  section: MarkdownSection,
  sup: MarkdownSup,
  blockquote: ({ children, ...props }: ComponentPropsWithoutRef<"blockquote">) => (
    <blockquote
      className="border-l-2 border-[rgb(var(--shiro-accent-rgb)/0.34)]"
      {...props}
    >
      {children}
    </blockquote>
  ),
} satisfies Components;

export default function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  return (
    <div className={`prose prose-sm dark:prose-invert max-w-none font-body ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath, remarkDirective, remarkAerisunDirectives]}
        rehypePlugins={[
          rehypeKatex,
          [rehypeHighlight, rehypeHighlightOptions],
          rehypeSlug,
          [rehypeAutolinkHeadings, { behavior: "wrap" }],
        ]}
        components={components}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
