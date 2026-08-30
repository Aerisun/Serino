import { createElement } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import MarkdownRenderer from "../src/components/MarkdownRenderer";

const renderMarkdown = (content: string) =>
  renderToStaticMarkup(createElement(MarkdownRenderer, { content }));

describe("Markdown visual language", () => {
  it("keeps semantic icons on ordinary links and same-article references", () => {
    const markup = renderMarkdown(
      "[外部文档](https://example.com)、[站内页面](/posts/1)、[本文章节](#目标标题)。\n\n### 目标标题",
    );

    expect(markup).toMatch(
      /<a href="https:\/\/example\.com" class="[^"]*markdown-inline-link[^"]*markdown-inline-link--external[^"]*"[^>]*>外部文档<svg[^>]*class="[^"]*markdown-inline-link-icon[^"]*markdown-inline-link-icon--external[^"]*"/,
    );
    expect(markup).toMatch(
      /<a href="\/posts\/1" class="[^"]*markdown-inline-link[^"]*"[^>]*>站内页面<svg[^>]*class="[^"]*markdown-inline-link-icon[^"]*"/,
    );
    expect(markup).toMatch(
      /<a href="#%E7%9B%AE%E6%A0%87%E6%A0%87%E9%A2%98" class="[^"]*markdown-inline-reference[^"]*"[^>]*><svg[^>]*class="[^"]*markdown-inline-reference-icon[^"]*"[^>]*>[\s\S]*?本文章节<\/a>/,
    );

    const headingMarkup = markup.match(/<h3[^>]*>[\s\S]*?<\/h3>/)?.[0] ?? "";
    expect(headingMarkup).not.toContain("markdown-inline-link");
    expect(headingMarkup).not.toContain("markdown-inline-link-icon");
  });

  it("uses a single directional underline for inline links and one-shot target arrival feedback", () => {
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );
    const rendererSource = readFileSync(
      new URL("../src/components/MarkdownRenderer.tsx", import.meta.url),
      "utf8",
    );

    expect(css).toMatch(
      /\.markdown-inline-link\s*\{[\s\S]*?background-size:\s*0% 0\.1em;[\s\S]*?text-decoration:\s*none;/,
    );
    expect(css).toMatch(
      /\.markdown-inline-link:hover,[\s\S]*?\.markdown-inline-link:focus-visible\s*\{[\s\S]*?background-size:\s*100% 0\.1em;/,
    );
    expect(css).toMatch(
      /\.markdown-inline-link-icon\s*\{[\s\S]*?transition:[\s\S]*?transform 200ms cubic-bezier\(0\.22, 1, 0\.36, 1\)/,
    );
    expect(css).toMatch(
      /\.markdown-inline-link--external:hover \.markdown-inline-link-icon--external\s*\{[\s\S]*?transform:\s*translateX\(0\.08em\);/,
    );
    expect(css).not.toMatch(
      /\.markdown-inline-link--external:hover \.markdown-inline-link-icon--external[^}]*translateY/,
    );
    expect(css).not.toMatch(
      /\.markdown-inline-link:active \.markdown-inline-link-icon[^}]*scale/,
    );
    expect(css).toMatch(
      /\.markdown-inline-link:focus-visible[\s\S]*?outline:/,
    );
    expect(css).toMatch(
      /\.markdown-inline-link:focus-visible\s*\{[^}]*transition:\s*none;/,
    );
    expect(css).toMatch(
      /\.markdown-inline-reference:hover \.markdown-inline-reference-icon[\s\S]*?translateY\(-0\.08em\)/,
    );
    expect(css).not.toMatch(
      /\.markdown-inline-reference:hover \.markdown-inline-reference-icon[^}]*rotate\(180deg\)/,
    );
    expect(css).toMatch(
      /@keyframes markdown-target-arrival[\s\S]*?box-shadow:/,
    );
    expect(css).toMatch(
      /\.markdown-target-arrival > \.markdown-heading-anchor[\s\S]*?animation:\s*markdown-target-arrival 800ms/,
    );
    expect(css).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.markdown-inline-link,[\s\S]*?\.markdown-inline-link-icon[\s\S]*?\.markdown-target-arrival > \.markdown-heading-anchor[\s\S]*?animation:\s*none;/,
    );
    expect(rendererSource).toMatch(
      /target\.classList\.add\("markdown-target-arrival"\)/,
    );
  });

  it("renders same-article references as link chips without changing heading anchors", () => {
    const markup = renderMarkdown("### 目标标题\n\n参阅[目标标题](#目标标题)。");
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );

    expect(markup).toMatch(
      /<h3[^>]*>\s*<a[^>]*class="[^"]*markdown-heading-anchor[^"]*"[^>]*>目标标题<\/a>\s*<\/h3>/,
    );
    expect(markup.match(/<h3[^>]*>[\s\S]*?<\/h3>/)?.[0]).not.toContain("hover:text-");
    expect(markup).toMatch(
      /<p[^>]*>参阅<a[^>]*href="#%E7%9B%AE%E6%A0%87%E6%A0%87%E9%A2%98"[^>]*class="[^"]*markdown-inline-reference[^"]*"[^>]*>[\s\S]*markdown-inline-reference-icon[\s\S]*目标标题[\s\S]*<\/a>。<\/p>/,
    );
    expect(css).toMatch(/\.prose \.markdown-inline-link\s*\{/);
    expect(css).toMatch(/\.prose \.markdown-heading-anchor:hover[\s\S]*color:\s*inherit;/);
  });

  it("uses an editorial hierarchy instead of button-like heading decoration", () => {
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );

    expect(css).toMatch(/\.markdown-heading--h1[\s\S]*text-align:\s*center;/);
    expect(css).toMatch(
      /\.markdown-heading--h1::after[\s\S]*width:\s*100%;[\s\S]*clip-path:\s*inset\(0 calc\(\(100% - 2\.4rem\) \/ 2\)\);/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h1:hover::after[\s\S]*clip-path:\s*inset\(0\);/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h2\s*\{[^}]*isolation:\s*isolate;[^}]*background:\s*none;[^}]*box-shadow:\s*none;[^}]*color:\s*rgb\(var\(--shiro-foreground-rgb\) \/ 0\.92\);[^}]*text-shadow:\s*none;/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h2::after\s*\{[^}]*pointer-events:\s*none;[^}]*bottom:\s*0\.08em;[^}]*height:\s*0\.48em;[^}]*background:\s*linear-gradient\([^}]*box-shadow:\s*0 0\.16em 0\.7em rgb\(var\(--shiro-accent-rgb\) \/ 0\.08\);[^}]*scaleX\(0\.66\);[^}]*transform 260ms cubic-bezier\(0\.22, 1, 0\.36, 1\);/,
    );
    expect(css).toMatch(
      /\.dark \.prose \.markdown-heading--h2\s*\{[^}]*color:\s*rgb\(var\(--shiro-foreground-rgb\) \/ 0\.98\);[^}]*text-shadow:\s*none;/,
    );
    expect(css).toMatch(
      /\.dark \.prose \.markdown-heading--h2::after\s*\{[^}]*rgb\(var\(--shiro-accent-rgb\) \/ 0\.42\)[^}]*rgb\(var\(--shiro-accent-rgb\) \/ 0\.3\)[^}]*rgb\(var\(--shiro-accent-rgb\) \/ 0\.1\)[^}]*box-shadow:\s*0 0\.18em 0\.85em rgb\(var\(--shiro-accent-rgb\) \/ 0\.14\);/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h2:hover::after[^}]*\{[^}]*scaleX\(1\);/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h2:hover\s*\{[^}]*color:\s*rgb\(var\(--shiro-accent-rgb\) \/ 0\.98\);/,
    );
    expect(css).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.markdown-heading--h2::after[^}]*\{[^}]*transition:\s*none;/,
    );
    expect(css).toMatch(/\.markdown-heading--h3::before[\s\S]*width:\s*0\.25rem;/);
    expect(css).toMatch(/\.markdown-heading--h4::before[\s\S]*border-radius:\s*50%;/);
  });

  it("gives article headings a descending editorial rhythm", () => {
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );

    expect(css).toMatch(
      /\.markdown-heading--h1\s*\{[^}]*margin-block:\s*3\.75rem 1\.5rem;/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h2\s*\{[^}]*margin-block:\s*3\.125rem 1\.125rem;/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h3\s*\{[^}]*margin-block:\s*2\.5rem 0\.875rem;/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h4\s*\{[^}]*margin-block:\s*2rem 0\.75rem;/,
    );
    expect(css).toMatch(
      /\.prose > \.markdown-heading:first-child\s*\{[^}]*margin-top:\s*0;/,
    );
    expect(css).toMatch(
      /@media \(max-width: 640px\)[\s\S]*\.markdown-heading--h2\s*\{[^}]*margin-block:\s*2\.625rem 1rem;/,
    );
  });

  it("keeps heading hover motion brisk and keyboard focus immediate", () => {
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );
    const headingCss = css.slice(
      css.indexOf("/* Markdown headings"),
      css.indexOf(".prose blockquote"),
    );

    expect(css).toMatch(
      /\.markdown-heading--h1\s*\{[^}]*transform 240ms cubic-bezier\(0\.22, 1, 0\.36, 1\);/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h1::after\s*\{[^}]*clip-path 260ms cubic-bezier\(0\.22, 1, 0\.36, 1\);/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h2\s*\{[^}]*transform 240ms cubic-bezier\(0\.22, 1, 0\.36, 1\);/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h2:focus-within\s*\{[^}]*transition:\s*none;/,
    );
    expect(css).not.toMatch(/\.markdown-heading--h2:focus-within::after/);
    expect(headingCss).not.toMatch(
      /(?:transition|animation):[^;]*(?:3\d\d|[4-9]\d\d)ms[^;]*;/,
    );
  });

  it("keeps emphasized heading text readable without a second underline", () => {
    const markup = renderMarkdown("# **部署**与`命令`\n\n## **准备服务器**");
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );

    expect(markup).toMatch(/<h1[^>]*>[\s\S]*<strong>部署<\/strong>[\s\S]*<\/h1>/);
    expect(markup).toMatch(/<h1[^>]*>[\s\S]*<code>命令<\/code>[\s\S]*<\/h1>/);
    expect(markup).toMatch(/<h2[^>]*>[\s\S]*<strong>准备服务器<\/strong>[\s\S]*<\/h2>/);
    expect(css).toMatch(
      /\.markdown-heading-anchor\s+:where\(strong, em, del, code\)[\s\S]*?border:\s*0;[\s\S]*?color:\s*inherit;[\s\S]*?text-shadow:\s*inherit;/,
    );
    expect(css).toMatch(
      /\.prose \.markdown-heading-anchor\s*\{[\s\S]*?font-weight:\s*inherit;/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h2\s*\{[^}]*color:\s*rgb\(var\(--shiro-foreground-rgb\) \/ 0\.92\);[^}]*text-shadow:\s*none;/,
    );
  });

  it("matches the reference hover rhythm for h3 and h4", () => {
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );
    const headingCss = css.slice(
      css.indexOf("/* Markdown headings"),
      css.indexOf(".prose blockquote"),
    );

    expect(css).toMatch(
      /\.markdown-heading--h3\s*\{[\s\S]*?padding-inline-start:\s*0\.875rem;/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h3 \.markdown-heading-anchor\s*\{[\s\S]*?translateX\(-0\.2rem\)[\s\S]*?220ms cubic-bezier\(0\.22, 1, 0\.36, 1\)/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h3:hover \.markdown-heading-anchor\s*\{[\s\S]*?translateX\(0\)/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h3::before\s*\{[\s\S]*?width:\s*0\.25rem;[\s\S]*?height:\s*62%;[\s\S]*?scaleY\(0\.72\)/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h3:hover::before\s*\{[\s\S]*?scaleY\(1\)/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h4:hover\s*\{[\s\S]*?translateX\(0\.16rem\)/,
    );
    expect(css).toMatch(
      /\.markdown-heading--h4:hover::before\s*\{[\s\S]*?scale\(1\.16\)/,
    );
    expect(headingCss).not.toContain("cubic-bezier(0.34, 1.56, 0.64, 1)");
  });

  it("adapts the Phycat Forest inline interactions with softened emphasis", () => {
    const markup = renderMarkdown("**加粗**、*斜体*、~~删除线~~、`行内代码`");
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );
    const globalCss = readFileSync(new URL("../src/index.css", import.meta.url), "utf8");
    const strongRule = css.match(/\.prose strong\s*\{([^}]*)\}/)?.[1] ?? "";
    const strongHoverRule = css.match(/\.prose strong:hover\s*\{([^}]*)\}/)?.[1] ?? "";
    const emphasisRule = css.match(/\.prose em\s*\{([^}]*)\}/)?.[1] ?? "";
    const emphasisHoverRule = css.match(/\.prose em:hover\s*\{([^}]*)\}/)?.[1] ?? "";
    const deletionRule = css.match(/\.prose del\s*\{([^}]*)\}/)?.[1] ?? "";
    const deletionHoverRule = css.match(/\.prose del:hover\s*\{([^}]*)\}/)?.[1] ?? "";
    const codeRule = css.match(/\.prose :not\(pre\) > code\s*\{([^}]*)\}/)?.[1] ?? "";
    const codeHoverRule = css.match(/\.prose :not\(pre\) > code:hover\s*\{([^}]*)\}/)?.[1] ?? "";

    expect(markup).toMatch(
      /<strong>加粗<\/strong>、<em>斜体<\/em>、<del>删除线<\/del>、<code>行内代码<\/code>/,
    );
    expect(strongRule).toContain("display: inline-block;");
    expect(strongRule).toContain(
      "transform 220ms cubic-bezier(0.22, 1, 0.36, 1)",
    );
    expect(strongHoverRule).toContain("transform: translateY(-1px) scale(1.05);");
    expect(strongHoverRule).toContain("text-shadow: 1px 1px 0");
    expect(emphasisRule).toContain("padding: 0 2px 2px;");
    expect(emphasisRule).toContain("-webkit-text-stroke 200ms ease");
    expect(emphasisHoverRule).toContain("-webkit-text-stroke: 0.6px");
    expect(css).toMatch(
      /\.prose em::after\s*\{[^}]*height:\s*4px;[^}]*mask-size:\s*12px 4px;/,
    );
    expect(css).toMatch(
      /@keyframes markdown-emphasis-wave-flow[\s\S]*?mask-position-x:\s*12px;/,
    );
    expect(css).toMatch(
      /\.prose em:hover::after\s*\{[^}]*animation:\s*markdown-emphasis-wave-flow 1s linear infinite;/,
    );
    expect(deletionRule).toContain("color: hsl(var(--foreground) / 0.42);");
    expect(deletionRule).toContain(
      "text-decoration-color: rgb(var(--shiro-accent-rgb));",
    );
    expect(deletionHoverRule).toContain("opacity: 0.6;");
    expect(deletionHoverRule).toContain("cursor: not-allowed;");
    expect(codeRule).toContain("padding: 5px;");
    expect(codeRule).toContain("margin: 0;");
    expect(codeRule).not.toContain("margin: 0 2px;");
    expect(codeRule).toContain("border-radius: 6px;");
    expect(codeRule).toContain("vertical-align: middle;");
    expect(codeRule).toContain("color 240ms ease");
    expect(codeRule).toContain("background-color 240ms ease");
    expect(codeRule).toContain(
      "transform 260ms cubic-bezier(0.22, 1, 0.36, 1)",
    );
    expect(codeHoverRule).toContain(
      "background: rgb(var(--shiro-accent-rgb) / 0.9);",
    );
    expect(codeHoverRule).toContain("color: white;");
    expect(codeHoverRule).toContain(
      "box-shadow: 0 4px 12px rgb(var(--shiro-accent-rgb) / 0.28);",
    );
    expect(codeHoverRule).toContain("transform: scale(1.035);");
    expect(css).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.prose em:hover::after[^}]*\{[^}]*animation:\s*none;/,
    );
    expect(css).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*?\.prose strong:hover,[\s\S]*?\.prose :not\(pre\) > code:hover\s*\{[^}]*transform:\s*none;/,
    );
    expect(globalCss).not.toMatch(
      /\.content-detail-markdown\.prose :where\(strong, b\)\s*\{/,
    );
  });

  it("lets deletion and code semantics win inside nested inline formatting", () => {
    const markup = renderMarkdown(
      "~~**已删除重点**、`removed()`~~\n\n**~~外层重点删除~~**、**`const x`**",
    );
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );

    expect(markup).toMatch(
      /<del><strong>已删除重点<\/strong>、<code>removed\(\)<\/code><\/del>/,
    );
    expect(markup).toMatch(/<strong><del>外层重点删除<\/del><\/strong>/);
    expect(markup).toMatch(/<strong><code>const x<\/code><\/strong>/);
    expect(css).toMatch(
      /\.prose del :where\(strong, em, code\)\s*\{[^}]*color:\s*inherit;[^}]*text-shadow:\s*none;/,
    );
    expect(css).toMatch(/\.prose del code\s*\{[^}]*color:\s*inherit;/);
    expect(css).toMatch(
      /\.prose del em::after\s*\{[^}]*content:\s*none;/,
    );
    expect(css).toMatch(
      /\.prose strong:has\(> :where\(del, code\):only-child\)[\s\S]*?transform:\s*none;/,
    );
  });

  it("does not let paragraph indentation leak into inline formatting boxes", () => {
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );
    const strongRule = css.match(/\.prose strong\s*\{([^}]*)\}/)?.[1] ?? "";
    const codeRule = css.match(/\.prose :not\(pre\) > code\s*\{([^}]*)\}/)?.[1] ?? "";

    expect(css).toMatch(
      /\.markdown-indent-enabled \.markdown-paragraph\s*\{[^}]*text-indent:\s*2em;/,
    );
    expect(strongRule).toContain("display: inline-block;");
    expect(strongRule).toContain("text-indent: 0;");
    expect(codeRule).toContain("display: inline-block;");
    expect(codeRule).toContain("text-indent: 0;");
  });

  it("renders task states with an animated custom checkbox language", () => {
    const markup = renderMarkdown("- [ ] 待办\n- [x] 完成");
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );

    expect(markup).toContain("contains-task-list");
    expect(markup).toMatch(/<input type="checkbox" disabled=""\/> 待办/);
    expect(markup).toMatch(/<input type="checkbox" disabled="" checked=""\/> 完成/);
    expect(css).toMatch(/\.prose \.task-list-item > input\[type="checkbox"\][\s\S]*appearance:\s*none;/);
    expect(css).toMatch(/@keyframes markdown-task-pulse/);
    expect(css).toMatch(/input\[type="checkbox"\]:checked::after[\s\S]*opacity:\s*1;/);
    expect(css).toMatch(/\.task-list-item:has\(> input\[type="checkbox"\]:checked\)[\s\S]*text-decoration:/);
    expect(css).toMatch(/\.task-list-item > input\[type="checkbox"\][\s\S]*border-radius:\s*50%;/);
    expect(css).toMatch(/ul:not\(\.contains-task-list\)[\s\S]*::marker[\s\S]*color:/);
    expect(css).toMatch(/\.prose ol[\s\S]*::marker[\s\S]*color:/);
  });

  it("triggers image lift only on visible image pixels and respects reduced motion", () => {
    const css = readFileSync(
      new URL("../src/components/markdown.css", import.meta.url),
      "utf8",
    );

    expect(css).toMatch(
      /@media \(hover: hover\) and \(pointer: fine\)[\s\S]*\.markdown-figure-image:hover[\s\S]*transform:\s*translateY\(-0\.2rem\) scale\(1\.015\);/,
    );
    expect(css).not.toMatch(
      /\.markdown-figure-button:hover \.markdown-figure-image/,
    );
    expect(css).toMatch(
      /\.markdown-figure-image\s*\{[^}]*--markdown-image-shadow-contact:\s*rgb\(var\(--shiro-accent-rgb\) \/ 0\.1\);[^}]*--markdown-image-shadow-ambient:\s*rgb\(var\(--shiro-accent-rgb\) \/ 0\.08\);[^}]*--markdown-image-shadow-glow:\s*rgb\(var\(--shiro-accent-rgb\) \/ 0\.05\);/,
    );
    expect(css).toMatch(
      /\.markdown-figure-image\s*\{[^}]*box-shadow:\s*0 2px 8px var\(--markdown-image-shadow-contact\),\s*0 14px 34px var\(--markdown-image-shadow-ambient\),\s*0 26px 62px var\(--markdown-image-shadow-glow\),\s*inset 0 1px 0 var\(--markdown-image-shadow-edge\);/,
    );
    expect(css).toMatch(
      /\.dark \.prose \.markdown-figure-image\s*\{[^}]*--markdown-image-shadow-contact:\s*rgb\(var\(--shiro-accent-rgb\) \/ 0\.12\);[^}]*--markdown-image-shadow-hover-ambient:\s*rgb\(var\(--shiro-accent-rgb\) \/ 0\.15\);[^}]*--markdown-image-shadow-hover-glow:\s*rgb\(var\(--shiro-accent-rgb\) \/ 0\.09\);/,
    );
    expect(css).toMatch(
      /\.markdown-figure-image:hover,[\s\S]*?\.markdown-figure-button:focus-visible \.markdown-figure-image\s*\{[^}]*box-shadow:\s*0 4px 12px var\(--markdown-image-shadow-hover-contact\),\s*0 22px 46px var\(--markdown-image-shadow-hover-ambient\),\s*0 34px 76px var\(--markdown-image-shadow-hover-glow\),\s*0 0 0 1px var\(--markdown-image-shadow-hover-ring\),\s*inset 0 1px 0 var\(--markdown-image-shadow-hover-edge\);/,
    );
    expect(css).toMatch(
      /@media \(prefers-reduced-motion: reduce\)[\s\S]*\.markdown-figure-image[\s\S]*transition:\s*none;/,
    );
  });
});
