import type { ComponentPropsWithoutRef } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";

interface CommentMarkdownRendererProps {
  content: string;
  className?: string;
}

const components = {
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
  img: ({ alt = "", src, ...props }: ComponentPropsWithoutRef<"img">) => (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      decoding="async"
      className="rounded-2xl"
      {...props}
    />
  ),
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
} satisfies Components;

export default function CommentMarkdownRenderer({
  content,
  className = "",
}: CommentMarkdownRendererProps) {
  return (
    <div className={`prose prose-sm dark:prose-invert max-w-none font-body ${className}`}>
      <ReactMarkdown remarkPlugins={[remarkGfm]} components={components}>
        {content}
      </ReactMarkdown>
    </div>
  );
}
