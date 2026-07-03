import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");

const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

test("article markdown images mark portrait uploads and cap their rendered width", () => {
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const css = readSource("frontend/src/components/markdown.css");

  assert.match(renderer, /naturalHeight\s*>\s*(?:\w+\.)?naturalWidth/);
  assert.match(renderer, /markdown-figure-image--portrait/);
  assert.match(css, /\.prose\s+\.markdown-figure-image--portrait\s*\{/);
  assert.match(css, /max-width:\s*min\(100%,\s*24rem\);/);
  assert.match(css, /@media\s*\(max-width:\s*640px\)[\s\S]*\.prose\s+\.markdown-figure-image--portrait/);
  assert.match(css, /max-width:\s*min\(78%,\s*16rem\);/);
});

test("admin markdown preview uses the same portrait upload treatment", () => {
  const preview = readSource("admin/src/components/MarkdownPreview.tsx");
  const css = readSource("admin/src/index.css");

  assert.match(preview, /naturalHeight\s*>\s*(?:\w+\.)?naturalWidth/);
  assert.match(preview, /markdown-preview-image--portrait/);
  assert.match(css, /\.markdown-preview-image--portrait\s*\{/);
  assert.match(css, /max-width:\s*min\(100%,\s*24rem\);/);
  assert.match(css, /@media\s*\(max-width:\s*640px\)[\s\S]*\.markdown-preview-image--portrait/);
  assert.match(css, /max-width:\s*min\(78%,\s*16rem\);/);
});
