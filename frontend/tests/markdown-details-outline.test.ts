import { readFileSync } from "node:fs";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import MarkdownRenderer from "../src/components/MarkdownRenderer";

const renderMarkdown = (content: string) =>
  renderToStaticMarkup(createElement(MarkdownRenderer, { content }));

describe("nested Markdown outline", () => {
  it("marks collapsible content as excluded from the document table of contents", () => {
    const markup = renderMarkdown(
      ':::details{summary="展开查看"}\n## 这是折叠内\n\n这里是折叠内容。\n:::',
    );

    expect(markup).toContain("markdown-details");
    expect(markup).toContain('data-toc-exclude="true"');
    expect(markup).toMatch(/<h2[^>]*>.*这是折叠内.*<\/h2>/);
  });

  it("marks blockquotes as excluded from the document table of contents", () => {
    const markup = renderMarkdown(
      "> ## 这是引用内\n>\n> 这里是引用内容。",
    );

    expect(markup).toMatch(/<blockquote[^>]*data-toc-exclude="true"/);
    expect(markup).toMatch(/<h2[^>]*>.*这是引用内.*<\/h2>/);
  });

  it("uses the exclusion marker for heading collection without rendering hash markers", () => {
    const tocSource = readFileSync(
      new URL("../src/components/TableOfContents.tsx", import.meta.url),
      "utf8",
    );
    const markdownCss = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );

    expect(tocSource).toMatch(
      /const isTableOfContentsHeading[\s\S]*closest\(TOC_EXCLUDE_SELECTOR\)/,
    );
    expect(tocSource).toMatch(/\.filter\(isTableOfContentsHeading\)/);
    expect(markdownCss).not.toMatch(/h1:hover a::before/);
    expect(markdownCss).not.toMatch(
      /\[data-toc-exclude="true"\][^{}]*a::after\s*\{/,
    );
    expect(markdownCss).not.toMatch(/content:\s*"#";/);
  });
});
