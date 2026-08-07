import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import MarkdownPreview from "../src/components/MarkdownPreview";

describe("admin Markdown paragraph indentation", () => {
  it("previews ordinary paragraphs with the authored-content default", () => {
    const markup = renderToStaticMarkup(<MarkdownPreview content="后台预览段落" />);

    expect(markup).toContain("markdown-indent-enabled");
    expect(markup).toMatch(/<p class="markdown-paragraph"[^>]*>后台预览段落<\/p>/);
  });

  it("previews explicit indentation overrides without showing their syntax", () => {
    const markup = renderToStaticMarkup(
      <MarkdownPreview content={":indent 强制缩进\n\n:noindent 强制不缩进"} />,
    );

    expect(markup).toMatch(
      /<p class="markdown-paragraph markdown-paragraph--force-indent"[^>]*>强制缩进<\/p>/,
    );
    expect(markup).toMatch(
      /<p class="markdown-paragraph markdown-paragraph--force-no-indent"[^>]*>强制不缩进<\/p>/,
    );
    expect(markup).not.toContain(":indent ");
    expect(markup).not.toContain(":noindent ");
  });

  it("previews a document default override while keeping paragraph overrides stronger", () => {
    const markup = renderToStaticMarkup(
      <MarkdownPreview
        content={"@noindent\n\n后台普通段落\n\n:indent 后台单段缩进"}
      />,
    );

    expect(markup).not.toContain("markdown-indent-enabled");
    expect(markup).not.toContain("@noindent");
    expect(markup).toMatch(
      /<p class="markdown-paragraph markdown-paragraph--force-indent"[^>]*>后台单段缩进<\/p>/,
    );
  });

  it("keeps non-leading markers literal without supporting bracketed markers", () => {
    const markup = renderToStaticMarkup(
      <MarkdownPreview
        content={"正文里的 :indent 保持原样\n\n:noindent[旧写法]\n\n:noindentation 相似单词保持原样"}
      />,
    );

    expect(markup).toContain("正文里的 :indent 保持原样");
    expect(markup).toMatch(/<p class="markdown-paragraph">旧写法<\/p>/);
    expect(markup).not.toContain(":noindent[旧写法]");
    expect(markup).toContain(":noindentation 相似单词保持原样");
    expect(markup).not.toContain("markdown-paragraph--force-indent");
    expect(markup).not.toContain("markdown-paragraph--force-no-indent");
  });
});
