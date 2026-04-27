import { useState, type ComponentPropsWithoutRef } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

interface CommentMarkdownRendererProps {
  content: string;
  className?: string;
  imageSourceMap?: Record<string, string>;
}

interface MarkdownImageAttachment {
  key: string;
  src: string;
  alt: string;
}

const MARKDOWN_IMAGE_RE = /!\[([^\]]*)]\(([^)\s]+)(?:\s+"[^"]*")?\)/g;

const extractImageAttachments = (
  content: string,
  imageSourceMap: Record<string, string> | undefined,
) => {
  const images: MarkdownImageAttachment[] = [];
  const text = content
    .replace(MARKDOWN_IMAGE_RE, (match, alt: string, rawSrc: string) => {
      const src = rawSrc.trim();
      const resolvedSrc = imageSourceMap?.[src] ?? src;
      if (!resolvedSrc) {
        return match;
      }

      images.push({
        key: `${src}-${images.length}`,
        src: resolvedSrc,
        alt: alt.trim(),
      });
      return "";
    })
    .replace(/\n{3,}/g, "\n\n")
    .trim();

  return { images, text };
};

const buildComponents = (
  imageSourceMap: Record<string, string> | undefined,
  onImageOpen: (src: string, alt: string) => void,
) => ({
  a: ({ href, children, ...props }: ComponentPropsWithoutRef<"a">) => (
    <a
      href={href}
      target="_blank"
      rel="noreferrer noopener"
      className="text-[rgb(var(--shiro-accent-rgb)/0.82)] underline decoration-[rgb(var(--shiro-accent-rgb)/0.28)] underline-offset-4 transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.96)]"
      {...props}
    >
      {children}
    </a>
  ),
  img: ({ alt = "", src, ...props }: ComponentPropsWithoutRef<"img">) => {
    const resolvedSrc = src ? imageSourceMap?.[src] ?? src : src;
    if (!resolvedSrc) {
      return null;
    }
    return (
      <button
        type="button"
        className="aerisun-comment-image-button"
        onClick={() => onImageOpen(resolvedSrc, String(alt ?? ""))}
        aria-label={alt ? `查看图片：${alt}` : "查看图片"}
      >
        <img
          src={resolvedSrc}
          alt={alt}
          loading="lazy"
          decoding="async"
          {...props}
        />
      </button>
    );
  },
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
      className="overflow-x-auto rounded-2xl border border-[rgb(var(--shiro-border-rgb)/0.16)] bg-background/[0.76] px-4 py-3 dark:bg-card/[0.82]"
      {...props}
    >
      {children}
    </pre>
  ),
  blockquote: ({ children, ...props }: ComponentPropsWithoutRef<"blockquote">) => (
    <blockquote
      className="border-l-2 border-[rgb(var(--shiro-accent-rgb)/0.34)] pl-3 text-foreground/72"
      {...props}
    >
      {children}
    </blockquote>
  ),
}) satisfies Components;

export default function CommentMarkdownRenderer({
  content,
  className = "",
  imageSourceMap,
}: CommentMarkdownRendererProps) {
  const [lightboxImage, setLightboxImage] = useState<{ src: string; alt: string } | null>(null);
  const { images, text } = extractImageAttachments(content, imageSourceMap);
  const openImage = (src: string, alt: string) => setLightboxImage({ src, alt });

  return (
    <>
      <div className={`prose prose-sm dark:prose-invert max-w-none font-body ${className}`}>
        {images.length > 0 ? (
          <div className="aerisun-comment-attachment-grid">
            {images.map((image) => (
              <button
                key={image.key}
                type="button"
                className="aerisun-comment-image-button"
                onClick={() => openImage(image.src, image.alt)}
                aria-label={image.alt ? `查看图片：${image.alt}` : "查看图片"}
              >
                <img
                  src={image.src}
                  alt={image.alt}
                  loading="lazy"
                  decoding="async"
                />
              </button>
            ))}
          </div>
        ) : null}
        {text ? (
          <ReactMarkdown
            remarkPlugins={[remarkGfm]}
            components={buildComponents(imageSourceMap, openImage)}
          >
            {text}
          </ReactMarkdown>
        ) : null}
      </div>
      {lightboxImage ? (
        <div
          className="aerisun-comment-image-lightbox"
          role="dialog"
          aria-modal="true"
          onClick={() => setLightboxImage(null)}
        >
          <button
            type="button"
            className="aerisun-comment-image-lightbox__close"
            onClick={() => setLightboxImage(null)}
            aria-label="关闭图片预览"
          >
            ×
          </button>
          <img
            src={lightboxImage.src}
            alt={lightboxImage.alt}
            className="aerisun-comment-image-lightbox__image"
            onClick={(event) => event.stopPropagation()}
          />
        </div>
      ) : null}
    </>
  );
}
