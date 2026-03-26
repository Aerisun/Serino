import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import rehypeHighlight from "rehype-highlight";
import rehypeSlug from "rehype-slug";
import rehypeAutolinkHeadings from "rehype-autolink-headings";
import type { Components } from "react-markdown";
import "./markdown.css";

interface MarkdownRendererProps {
  content: string;
  className?: string;
}

const envApiBaseUrl =
  (typeof __AERISUN_API_BASE_URL__ === "string" ? __AERISUN_API_BASE_URL__ : "").replace(/\/+$/, "");

const resolveMarkdownImageSrc = (src?: string) => {
  if (!src) {
    return src;
  }
  if (!src.startsWith("/")) {
    return src;
  }
  if (!envApiBaseUrl) {
    return src;
  }

  try {
    return new URL(src, envApiBaseUrl).toString();
  } catch {
    return src;
  }
};

const components: Components = {
  h2: ({ children, ...props }) => (
    <h2
      className="border-l-2 border-[rgb(var(--shiro-accent-rgb)/0.34)] pl-3"
      {...props}
    >
      {children}
    </h2>
  ),
  a: ({ children, href, ...props }) => (
    <a
      href={href}
      className="transition-colors hover:text-[rgb(var(--shiro-accent-rgb)/0.92)]"
      target={href?.startsWith("http") ? "_blank" : undefined}
      rel={href?.startsWith("http") ? "noopener noreferrer" : undefined}
      {...props}
    >
      {children}
    </a>
  ),
  img: ({ src, alt, ...props }) => (
    <img
      src={resolveMarkdownImageSrc(src)}
      alt={alt}
      className="block max-w-full rounded-2xl"
      loading="lazy"
      {...props}
    />
  ),
  pre: ({ children, ...props }) => (
    <pre
      className="liquid-glass rounded-xl overflow-hidden"
      {...props}
    >
      {children}
    </pre>
  ),
  blockquote: ({ children, ...props }) => (
    <blockquote
      className="border-l-2 border-[rgb(var(--shiro-accent-rgb)/0.34)]"
      {...props}
    >
      {children}
    </blockquote>
  ),
};

export default function MarkdownRenderer({ content, className = "" }: MarkdownRendererProps) {
  return (
    <div className={`prose prose-sm dark:prose-invert max-w-none font-body ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        rehypePlugins={[
          rehypeHighlight,
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
