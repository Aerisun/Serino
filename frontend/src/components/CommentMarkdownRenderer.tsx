import { useState, type ComponentPropsWithoutRef, type CSSProperties } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import rehypeKatex from "rehype-katex";
import remarkDirective from "remark-directive";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import "katex/dist/katex.min.css";
import { resolveMarkdownDocumentIndent } from "@serino/utils/markdown-indentation";
import ImageLightbox from "@/components/ImageLightbox";
import { remarkAerisunIndentDirectives } from "@/components/markdown-directives";
import {
  getMarkdownIndentDirectiveKind,
  getMarkdownParagraphClassName,
  resolveMarkdownParagraphIndent,
} from "@/components/markdown-paragraph-indent";
import { extractMarkdownImageAttachments } from "@/lib/markdown-images";
import "./CommentMarkdownRenderer.css";

interface CommentMarkdownRendererProps {
  content: string;
  className?: string;
  indentParagraphs?: boolean;
  imageSourceMap?: Record<string, string>;
  style?: CSSProperties;
}

function MarkdownParagraph({
  children,
  className,
  node: _node,
  ...props
}: ComponentPropsWithoutRef<"p"> & { node?: unknown }) {
  const resolved = resolveMarkdownParagraphIndent(children);

  return (
    <p
      className={getMarkdownParagraphClassName(className, resolved.modifierClassName)}
      {...props}
    >
      {resolved.children}
    </p>
  );
}

function MarkdownSpan({
  children,
  className,
  node: _node,
  "data-md-kind": dataMarkdownKind,
  ...props
}: ComponentPropsWithoutRef<"span"> & {
  node?: unknown;
  "data-md-kind"?: string;
}) {
  const indentationKind = getMarkdownIndentDirectiveKind(dataMarkdownKind);
  if (indentationKind) {
    return (
      <>
        {children ?? `:${indentationKind}`}
      </>
    );
  }

  return (
    <span className={className} {...props}>
      {children}
    </span>
  );
}

const buildComponents = (
  imageSourceMap: Record<string, string> | undefined,
  onImageOpen: (src: string, alt: string) => void,
) => ({
  p: MarkdownParagraph,
  span: MarkdownSpan,
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
  indentParagraphs = false,
  imageSourceMap,
  style,
}: CommentMarkdownRendererProps) {
  const [lightboxImage, setLightboxImage] = useState<{ src: string; alt: string } | null>(null);
  const documentIndent = resolveMarkdownDocumentIndent(content);
  const { images, text } = extractMarkdownImageAttachments(
    documentIndent.content,
    imageSourceMap,
  );
  const openImage = (src: string, alt: string) => setLightboxImage({ src, alt });
  const shouldIndentParagraphs = documentIndent.indentParagraphs ?? indentParagraphs;
  const indentationClassName = shouldIndentParagraphs ? "markdown-indent-enabled" : "";

  return (
    <>
      <div
        className={`aerisun-comment-markdown prose prose-sm dark:prose-invert max-w-none font-body ${indentationClassName} ${className}`}
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
            remarkPlugins={[
              remarkGfm,
              remarkMath,
              remarkDirective,
              remarkAerisunIndentDirectives,
            ]}
            rehypePlugins={[rehypeKatex]}
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
