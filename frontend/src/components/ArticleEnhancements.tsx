import TableOfContents from "@/components/TableOfContents";

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
  const contentKey = [content];

  return (
    <>
      {enableToc ? <TableOfContents containerRef={containerRef} content={contentKey} /> : null}
    </>
  );
}
