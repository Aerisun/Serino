import fs from "node:fs";
import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import CommentMarkdownRenderer from "../src/components/CommentMarkdownRenderer";
import MarkdownRenderer from "../src/components/MarkdownRenderer";

const renderMarkdown = (content: string) =>
  renderToStaticMarkup(createElement(MarkdownRenderer, { content }));

const renderLightweightMarkdown = (content: string, indentParagraphs = false) =>
  renderToStaticMarkup(
    createElement(CommentMarkdownRenderer, { content, indentParagraphs }),
  );

describe("Markdown paragraph indentation", () => {
  it("indents authored Markdown by default but keeps the lightweight renderer opt-in", () => {
    const authored = renderMarkdown("普通正文段落");
    const comment = renderLightweightMarkdown("评论段落");
    const thought = renderLightweightMarkdown("说说段落", true);

    expect(authored).toContain("markdown-indent-enabled");
    expect(authored).toMatch(/<p class="markdown-paragraph"[^>]*>普通正文段落<\/p>/);
    expect(comment).not.toContain("markdown-indent-enabled");
    expect(comment).toMatch(/<p class="markdown-paragraph"[^>]*>评论段落<\/p>/);
    expect(thought).toContain("markdown-indent-enabled");
  });

  it("renders concise directives as force-indent paragraph overrides", () => {
    const authored = renderMarkdown(
      ":indent 强制缩进而且不需要结束标记\n第二行仍属于同一段落\n\n:noindent **加粗开头也能强制不缩进**",
    );
    const comment = renderLightweightMarkdown(":indent 评论中强制缩进");

    expect(authored).toMatch(
      /<p class="markdown-paragraph markdown-paragraph--force-indent"[^>]*>强制缩进而且不需要结束标记\n第二行仍属于同一段落<\/p>/,
    );
    expect(authored).toMatch(
      /<p class="markdown-paragraph markdown-paragraph--force-no-indent"[^>]*><strong>加粗开头也能强制不缩进<\/strong><\/p>/,
    );
    expect(comment).toMatch(
      /<p class="markdown-paragraph markdown-paragraph--force-indent"[^>]*>评论中强制缩进<\/p>/,
    );
    expect(authored).not.toContain(":indent ");
    expect(authored).not.toContain(":noindent ");
  });

  it("lets a document header override authored and lightweight renderer defaults", () => {
    const authored = renderMarkdown(
      "\r\n  \r\n  @noindent  \r\n\r\n普通正文\r\n\r\n:indent 单段仍然缩进",
    );
    const comment = renderLightweightMarkdown(
      "@indent\n\n评论整体缩进\n\n:noindent 单段仍然不缩进",
    );

    expect(authored).not.toContain("markdown-indent-enabled");
    expect(authored).not.toContain("@noindent");
    expect(authored).toMatch(/<p class="markdown-paragraph"[^>]*>普通正文<\/p>/);
    expect(authored).toMatch(
      /<p class="markdown-paragraph markdown-paragraph--force-indent"[^>]*>单段仍然缩进<\/p>/,
    );

    expect(comment).toContain("markdown-indent-enabled");
    expect(comment).not.toContain("@indent");
    expect(comment).toMatch(
      /<p class="markdown-paragraph markdown-paragraph--force-no-indent"[^>]*>单段仍然不缩进<\/p>/,
    );
  });

  it("only recognizes a document directive on the first non-empty line", () => {
    const misplaced = renderMarkdown(
      "正文先出现\n\n@noindent\n\n@indentation 相似单词",
    );
    const escaped = renderMarkdown("\\@noindent\n\n转义后的正文");

    expect(misplaced).toContain("markdown-indent-enabled");
    expect(misplaced).toContain("@noindent");
    expect(misplaced).toContain("@indentation 相似单词");
    expect(escaped).toContain("markdown-indent-enabled");
    expect(escaped).toContain("@noindent");
  });

  it("only treats an exact line-leading marker as an indentation override", () => {
    const authored = renderMarkdown(
      "段落中间的 :indent 保持原样\n\n:indent[旧方括号写法]\n\n:indentation 相似单词保持原样\n\n:indent\n\n\\:noindent 转义后保持原样",
    );

    expect(authored).toContain("段落中间的 :indent 保持原样");
    expect(authored).toMatch(/<p class="markdown-paragraph">旧方括号写法<\/p>/);
    expect(authored).not.toContain(":indent[旧方括号写法]");
    expect(authored).toContain(":indentation 相似单词保持原样");
    expect(authored).toMatch(/<p class="markdown-paragraph">:indent<\/p>/);
    expect(authored).toContain(":noindent 转义后保持原样");
    expect(authored).not.toContain("markdown-paragraph--force-indent");
    expect(authored).not.toContain("markdown-paragraph--force-no-indent");
  });

  it("keeps unrelated directive syntax literal in the lightweight renderer", () => {
    const comment = renderLightweightMarkdown(":underline[评论原文]");

    expect(comment).toContain(":underline[评论原文]");
    expect(comment).not.toContain("data-md-kind");
  });

  it("opts thoughts and excerpts into indentation without changing comment surfaces", () => {
    const thoughts = fs.readFileSync(
      new URL("../src/pages/Thoughts.tsx", import.meta.url),
      "utf8",
    );
    const excerpts = fs.readFileSync(
      new URL("../src/pages/Excerpts.tsx", import.meta.url),
      "utf8",
    );
    const commentForm = fs.readFileSync(
      new URL("../src/components/WalineCommentForm.tsx", import.meta.url),
      "utf8",
    );
    const commentList = fs.readFileSync(
      new URL("../src/components/WalineCommentList.tsx", import.meta.url),
      "utf8",
    );

    expect(thoughts).toMatch(
      /<CommentMarkdownRenderer\s+content=\{thought\.content\}[\s\S]*?indentParagraphs/,
    );
    expect(excerpts).toMatch(
      /<CommentMarkdownRenderer\s+content=\{selected\.content\}[\s\S]*?indentParagraphs/,
    );
    const excerptRendererClass = excerpts.match(
      /<CommentMarkdownRenderer\s+content=\{selected\.content\}\s+className="([^"]+)"/s,
    )?.[1];
    expect(excerptRendererClass).toBeDefined();
    expect(excerptRendererClass).not.toContain("indent-[2em]");
    expect(commentForm).not.toContain("indentParagraphs");
    expect(commentList).not.toContain("indentParagraphs");
  });

  it("keeps structural Markdown flush unless an explicit directive overrides it", () => {
    const styles = fs.readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );
    const lightweightStyles = fs.readFileSync(
      new URL("../src/components/CommentMarkdownRenderer.css", import.meta.url),
      "utf8",
    );

    expect(styles).toMatch(
      /\.markdown-indent-enabled[\s\S]*\.markdown-paragraph[\s\S]*text-indent:\s*2em/,
    );
    expect(styles).toMatch(
      /:where\(li, blockquote\)[\s\S]*\.markdown-paragraph[\s\S]*text-indent:\s*0/,
    );
    expect(styles).toMatch(
      /\.markdown-paragraph--force-indent[\s\S]*text-indent:\s*2em/,
    );
    expect(styles).toMatch(
      /\.markdown-paragraph--force-no-indent[\s\S]*text-indent:\s*0/,
    );
    expect(lightweightStyles).toMatch(
      /\.markdown-indent-enabled[\s\S]*\.markdown-paragraph[\s\S]*text-indent:\s*2em/,
    );
  });
});
