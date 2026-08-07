import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";

const rendererPath = fileURLToPath(new URL("../src/components/CommentMarkdownRenderer.tsx", import.meta.url));
const stylesPath = fileURLToPath(new URL("../src/components/CommentMarkdownRenderer.css", import.meta.url));

test("lightweight Markdown renders fenced code and KaTeX math without restoring inline images", async () => {
  const [renderer, styles] = await Promise.all([
    readFile(rendererPath, "utf8"),
    readFile(stylesPath, "utf8"),
  ]);

  assert.match(renderer, /import remarkMath from "remark-math";/);
  assert.match(renderer, /import rehypeKatex from "rehype-katex";/);
  assert.match(renderer, /import "katex\/dist\/katex\.min\.css";/);
  assert.match(
    renderer,
    /remarkPlugins=\{\[[\s\S]*remarkGfm,[\s\S]*remarkMath,[\s\S]*remarkDirective,[\s\S]*remarkAerisunIndentDirectives,[\s\S]*\]\}/,
  );
  assert.match(renderer, /rehypePlugins=\{\[rehypeKatex\]\}/);
  assert.match(renderer, /code: \(\{ className, children/);
  assert.match(renderer, /pre: \(\{ children/);
  assert.match(renderer, /resolveMarkdownDocumentIndent\(content\)/);
  assert.match(
    renderer,
    /extractMarkdownImageAttachments\(\s*documentIndent\.content,\s*imageSourceMap,?\s*\)/,
  );
  assert.match(styles, /\.aerisun-comment-markdown pre:has\(> code\.math-display\)/);
  assert.match(styles, /\.aerisun-comment-markdown \.katex-display/);
});
