import TableOfContents from "@/components/TableOfContents";
import { useMemo } from "react";

interface ArticleEnhancementsProps {
  containerRef: React.RefObject<HTMLElement | null>;
  content: string;
  enableToc: boolean;
}

export default function ArticleEnhancements({
  containerRef,
  content,
  enableToc,
}: ArticleEnhancementsProps) {
  const contentKey = useMemo(() => [content], [content]);

  return (
    <>
      {enableToc ? <TableOfContents containerRef={containerRef} content={contentKey} /> : null}
    </>
  );
}
