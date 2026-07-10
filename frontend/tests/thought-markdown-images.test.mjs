import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";

const thoughtsPagePath = fileURLToPath(new URL("../src/pages/Thoughts.tsx", import.meta.url));
const imageRendererStylesPath = fileURLToPath(
  new URL("../src/components/CommentMarkdownRenderer.css", import.meta.url),
);

test("thoughts render Markdown bodies with the comment image renderer", async () => {
  const source = await readFile(thoughtsPagePath, "utf8");

  assert.match(source, /import CommentMarkdownRenderer from "@\/components\/CommentMarkdownRenderer";/);
  assert.match(source, /<CommentMarkdownRenderer\s+content=\{thought\.content\}/);
});

test("centers the three-column image grid within a thought", async () => {
  const styles = await readFile(imageRendererStylesPath, "utf8");

  assert.match(
    styles,
    /\.aerisun-comment-attachment-grid\s*\{[\s\S]*margin:\s*0 auto 0\.9rem;/,
  );
});
