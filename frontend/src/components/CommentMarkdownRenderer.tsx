import { useState, type ComponentPropsWithoutRef, type CSSProperties } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import ImageLightbox from "@/components/ImageLightbox";
import { extractMarkdownImageAttachments } from "@/lib/markdown-images";
import "./CommentMarkdownRenderer.css";

interface CommentMarkdownRendererProps {
  content: string;
  className?: string;
  imageSourceMap?: Record<string, string>;
  style?: CSSProperties;
}

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
  style,
}: CommentMarkdownRendererProps) {
  const [lightboxImage, setLightboxImage] = useState<{ src: string; alt: string } | null>(null);
  const { images, text } = extractMarkdownImageAttachments(content, imageSourceMap);
  const openImage = (src: string, alt: string) => setLightboxImage({ src, alt });

  return (
    <>
      <div
        className={`prose prose-sm dark:prose-invert max-w-none font-body ${className}`}
        style={style}
      >
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
        <ImageLightbox
          src={lightboxImage.src}
          alt={lightboxImage.alt}
          onClose={() => setLightboxImage(null)}
        />
      ) : null}
    </>
  );
}
