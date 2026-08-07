import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";

const excerptsPagePath = fileURLToPath(new URL("../src/pages/Excerpts.tsx", import.meta.url));
const thoughtsPagePath = fileURLToPath(new URL("../src/pages/Thoughts.tsx", import.meta.url));
const commentRendererPath = fileURLToPath(new URL("../src/components/CommentMarkdownRenderer.tsx", import.meta.url));

const getRendererClass = (source, valueName) => {
  const match = source.match(
    new RegExp(`<CommentMarkdownRenderer\\s+content=\\{${valueName}\\.content\\}\\s+className="([^"]+)"`, "s"),
  );
  assert.notEqual(match, null, `${valueName} should use the lightweight Markdown renderer`);
  return match[1];
};

test("excerpts and thoughts keep the lightweight renderer and use blank lines for paragraph breaks", async () => {
  const [excerpts, thoughts, renderer] = await Promise.all([
    readFile(excerptsPagePath, "utf8"),
    readFile(thoughtsPagePath, "utf8"),
    readFile(commentRendererPath, "utf8"),
  ]);

  assert.match(excerpts, /import CommentMarkdownRenderer from "@\/components\/CommentMarkdownRenderer";/);
  assert.match(thoughts, /import CommentMarkdownRenderer from "@\/components\/CommentMarkdownRenderer";/);
  assert.doesNotMatch(getRendererClass(excerpts, "selected"), /whitespace-pre-wrap/);
  assert.doesNotMatch(getRendererClass(thoughts, "thought"), /whitespace-pre-wrap/);
  assert.match(renderer, /resolveMarkdownDocumentIndent\(content\)/);
  assert.match(
    renderer,
    /extractMarkdownImageAttachments\(\s*documentIndent\.content,\s*imageSourceMap,?\s*\)/,
  );
  assert.match(
    renderer,
    /remarkPlugins=\{\[[\s\S]*remarkGfm,[\s\S]*remarkMath,[\s\S]*remarkDirective,[\s\S]*remarkAerisunIndentDirectives,[\s\S]*\]\}/,
  );
});
