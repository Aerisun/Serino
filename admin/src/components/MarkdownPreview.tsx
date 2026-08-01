import {
  Children,
  isValidElement,
  startTransition,
  useEffect,
  useMemo,
  useState,
  type ComponentPropsWithoutRef,
  type ReactNode,
  type SyntheticEvent,
} from "react";
import { ExternalLink, Link2 } from "lucide-react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkDirective from "remark-directive";
import remarkGfm from "remark-gfm";
import { isSquareImage } from "@serino/utils/image-dimensions";
import { buildPreviewImageUrl, fetchLinkPreview, type LinkPreviewPayload } from "@/lib/link-preview";
import { remarkAdminMarkdownDirectives } from "@/components/markdown-directives";

interface MarkdownPreviewProps {
  content: string;
  className?: string;
}

const cleanChildrenArray = (children: ReactNode) =>
  Children.toArray(children).filter((child) => !(typeof child === "string" && child.trim() === ""));

const flattenDirectiveChildren = (children: ReactNode) => {
  const items: ReactNode[] = [];

  cleanChildrenArray(children).forEach((child) => {
    if (isValidElement<{ children?: ReactNode }>(child) && child.type === "p") {
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

function MarkdownRichLinkCard({ href }: { href: string }) {
  const [preview, setPreview] = useState<LinkPreviewPayload | null>(null);
  const [imageState, setImageState] = useState<"primary" | "fallback" | "hidden">("primary");
  const [thumbnailCropImageUrl, setThumbnailCropImageUrl] = useState<string | null>(null);
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
        className="group block overflow-hidden rounded-2xl border border-border/70 bg-background/95 p-4 no-underline shadow-sm transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md"
      >
        <span className="mb-3 inline-flex items-center gap-2 rounded-full bg-muted px-2.5 py-1 text-[11px] font-medium uppercase tracking-[0.12em] text-muted-foreground">
          <Link2 className="h-3.5 w-3.5" />
          <span>Link</span>
        </span>
        <span className="block break-all text-sm font-medium text-foreground">{href}</span>
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
  const hasCompactMeta = cardMeta === fallbackMeta;
  const primaryImageUrl = preview?.image_url ? buildPreviewImageUrl(preview.image_url) : null;
  const fallbackImageUrl = deriveFallbackImageUrl(preview, href);
  const imageUrl =
    imageState === "primary"
      ? primaryImageUrl
      : imageState === "fallback"
        ? fallbackImageUrl
        : null;
  const isNonSquareImage = thumbnailCropImageUrl === imageUrl;
  const iconUrl = preview?.icon_url || null;
  const isGithubProfile = preview?.card_type === "github_profile";
  const showExternalLink = !isGithubProfile;
  const hasMediaImage = Boolean(imageUrl);

  return (
    <a
      href={cardHref}
      target="_blank"
      rel="noopener noreferrer"
      className={[
        "group relative overflow-hidden rounded-2xl border border-border/70 bg-background/95 no-underline shadow-sm transition hover:-translate-y-0.5 hover:border-primary/40 hover:shadow-md",
        hasMediaImage
          ? "grid grid-cols-[4rem_minmax(0,1fr)] items-center gap-x-3 p-4 sm:grid-cols-[5rem_minmax(0,1fr)]"
          : "block",
      ].join(" ")}
    >
      {imageUrl ? (
        <span className="col-start-1 row-start-1 h-16 w-16 self-center overflow-hidden rounded-xl border border-border/60 bg-muted/40 sm:h-20 sm:w-20">
          <img
            src={imageUrl}
            alt={cardTitle}
            className={`m-0 h-full w-full max-w-none border-0 shadow-none ${isNonSquareImage ? "object-cover" : "object-contain"}`}
            loading="lazy"
            referrerPolicy="no-referrer"
            onLoad={(event) => {
              const image = event.currentTarget;
              setThumbnailCropImageUrl(isSquareImage(image.naturalWidth, image.naturalHeight) ? null : imageUrl);
            }}
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

      <span className={hasMediaImage ? "col-start-2 row-start-1 min-w-0 self-center pr-7" : "flex items-start gap-3 p-4 pr-10"}>
        {!hasMediaImage ? (
          <span className="inline-flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-border/70 bg-muted/60 text-muted-foreground">
            {iconUrl ? (
              <img
                src={iconUrl}
                alt=""
                className="h-5 w-5 object-contain"
                loading="lazy"
                referrerPolicy="no-referrer"
              />
            ) : (
              <Link2 className="h-4 w-4" />
            )}
          </span>
        ) : null}

        <span className={hasMediaImage ? "block min-w-0" : "min-w-0 flex-1"}>
          <span className={`${hasCompactMeta ? "mb-2 leading-tight" : "mb-1.5"} block truncate text-[11px] font-semibold uppercase tracking-[0.14em] text-muted-foreground`}>
            {badgeLabel}
          </span>
          <span className="line-clamp-2 block text-sm font-semibold leading-6 text-foreground">
            {cardTitle}
          </span>
          <span className="mt-1.5 line-clamp-3 block text-sm leading-6 text-muted-foreground sm:line-clamp-2">
            {cardMeta}
          </span>
        </span>

      </span>

      {showExternalLink ? (
        <span className="absolute bottom-3.5 right-3.5 inline-flex shrink-0 text-muted-foreground transition group-hover:text-foreground">
          <ExternalLink className="h-4 w-4" />
        </span>
      ) : null}
    </a>
  );
}

function MarkdownAnchor({ href, children, ...props }: ComponentPropsWithoutRef<"a">) {
  const isExternal = /^https?:\/\//i.test(href ?? "");

  return (
    <a
      href={href}
      target={isExternal ? "_blank" : undefined}
      rel={isExternal ? "noopener noreferrer" : undefined}
      className="text-primary underline decoration-primary/30 underline-offset-4 transition-colors hover:text-primary/80"
      {...props}
    >
      {children}
    </a>
  );
}

function MarkdownParagraph({ children, ...props }: ComponentPropsWithoutRef<"p">) {
  const cleanChildren = cleanChildrenArray(children);
  if (cleanChildren.length === 1) {
    const child = cleanChildren[0];
    if (isValidElement<{ href?: string; children?: ReactNode }>(child)) {
      const href = child.props.href?.trim();
      if (href && /^https?:\/\//i.test(href)) {
        return (
          <div className="not-prose my-4">
            <MarkdownRichLinkCard href={href} />
          </div>
        );
      }
    }
  }

  return <p {...props}>{children}</p>;
}

function MarkdownPreviewImage({
  alt = "",
  src,
  className,
  onLoad,
  ...props
}: ComponentPropsWithoutRef<"img">) {
  const [isPortrait, setIsPortrait] = useState(false);
  const imageClassName = [
    "markdown-preview-image",
    "rounded-2xl",
    isPortrait ? "markdown-preview-image--portrait" : "",
    className ?? "",
  ].join(" ").trim();

  const handleImageLoad = (event: SyntheticEvent<HTMLImageElement>) => {
    const image = event.currentTarget;
    setIsPortrait(image.naturalHeight > image.naturalWidth);
    onLoad?.(event);
  };

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      className={imageClassName}
      onLoad={handleImageLoad}
      {...props}
    />
  );
}

function MarkdownPreviewUnderline({ children }: { children: ReactNode }) {
  return <span className="decoration-primary/70 underline decoration-[0.08em] underline-offset-[0.18em]">{children}</span>;
}

function MarkdownPreviewThumbnail({ children }: { children: ReactNode }) {
  return (
    <div className="mx-auto my-5 w-full max-w-xs [&>p]:m-0 [&_.markdown-preview-image]:block [&_.markdown-preview-image]:aspect-[4/3] [&_.markdown-preview-image]:h-full [&_.markdown-preview-image]:w-full [&_.markdown-preview-image]:object-cover">
      {children}
    </div>
  );
}

function MarkdownPreviewCarousel({ children }: { children: ReactNode }) {
  const items = flattenDirectiveChildren(children);
  if (items.length === 0) return null;

  return (
    <div className="my-5">
      <div className="relative min-h-52 pr-5">
        {items.slice(1, 3).map((item, index) => (
          <div
            key={index}
            aria-hidden="true"
            className={
              index === 0
                ? "absolute inset-3 -right-1 overflow-hidden rounded-2xl border border-border/60 bg-muted/30 opacity-60"
                : "absolute inset-5 -right-3 overflow-hidden rounded-2xl border border-border/50 bg-muted/20 opacity-30"
            }
          >
            {item}
          </div>
        ))}
        <div className="relative z-10 grid min-h-52 place-items-center overflow-hidden rounded-2xl border border-border/70 bg-muted/25 p-3 shadow-sm [&_.markdown-preview-image]:max-h-72 [&_.markdown-preview-image]:w-auto [&_.markdown-preview-image]:max-w-full [&_.markdown-preview-image]:object-contain">
          {items[0]}
        </div>
      </div>
    </div>
  );
}

function MarkdownPreviewDiv({ children, ...props }: ComponentPropsWithoutRef<"div">) {
  if (props["data-md-kind" as keyof typeof props] === "thumbnail") {
    return <MarkdownPreviewThumbnail>{children}</MarkdownPreviewThumbnail>;
  }

  if (props["data-md-kind" as keyof typeof props] === "carousel") {
    return <MarkdownPreviewCarousel>{children}</MarkdownPreviewCarousel>;
  }

  return <div {...props}>{children}</div>;
}

function MarkdownPreviewSpan({ children, ...props }: ComponentPropsWithoutRef<"span">) {
  if (props["data-md-kind" as keyof typeof props] === "underline") {
    return <MarkdownPreviewUnderline>{children}</MarkdownPreviewUnderline>;
  }

  return <span {...props}>{children}</span>;
}

const components = {
  a: MarkdownAnchor,
  p: MarkdownParagraph,
  img: MarkdownPreviewImage,
  div: MarkdownPreviewDiv,
  span: MarkdownPreviewSpan,
  code: ({ className, children, ...props }: ComponentPropsWithoutRef<"code">) => {
    const content = String(children ?? "");
    const isBlock = /\n/.test(content) || Boolean(className);
    if (!isBlock) {
      return (
        <code className="rounded bg-foreground/8 px-1.5 py-0.5 text-[0.92em]" {...props}>
          {children}
        </code>
      );
    }

    return (
      <code className={className} {...props}>
        {children}
      </code>
    );
  },
  pre: ({ children, ...props }: ComponentPropsWithoutRef<"pre">) => (
    <pre
      className="overflow-x-auto rounded-2xl border border-border/70 bg-muted/40 px-4 py-3 dark:bg-card/80"
      {...props}
    >
      {children}
    </pre>
  ),
  blockquote: ({ children, ...props }: ComponentPropsWithoutRef<"blockquote">) => (
    <blockquote
      className="border-l-2 border-primary/30 pl-3 text-foreground/75"
      {...props}
    >
      {children}
    </blockquote>
  ),
} satisfies Components;

export default function MarkdownPreview({ content, className = "" }: MarkdownPreviewProps) {
  return (
    <div className={`prose prose-sm dark:prose-invert max-w-none font-body ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm, remarkDirective, remarkAdminMarkdownDirectives]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
