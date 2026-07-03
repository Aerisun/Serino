import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");

const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

test("table of contents includes top-level markdown headings", () => {
  const toc = readSource("frontend/src/components/TableOfContents.tsx");

  assert.match(toc, /querySelectorAll<HTMLHeadingElement>\("h1,\s*h2,\s*h3,\s*h4"\)/);
  assert.match(toc, /document\.querySelectorAll<HTMLHeadingElement>\(\s*"article h1,\s*article h2,\s*article h3,\s*article h4"/);
});

test("table of contents keeps final item clear of the scroll fade", () => {
  const css = readSource("frontend/src/index.css");
  const toc = readSource("frontend/src/components/TableOfContents.tsx");

  assert.match(css, /\.toc-scroll-mask\s*\{[\s\S]*padding-bottom:\s*calc\(var\(--toc-mask-size\)\s*\+\s*0\.75rem\);/);
  assert.match(css, /\.toc-scroll-mask\s*\{[\s\S]*scroll-padding-block:\s*var\(--toc-mask-size\);/);
  assert.doesNotMatch(toc, /toc-scroll-mask[^"]*pb-0/);
});

test("table of contents click does not flash the destination heading", () => {
  const toc = readSource("frontend/src/components/TableOfContents.tsx");

  assert.doesNotMatch(toc, /TARGET_FLASH_DURATION_MS/);
  assert.doesNotMatch(toc, /targetFlash/);
  assert.doesNotMatch(toc, /markdown-target-flash/);
  assert.doesNotMatch(toc, /void element\.offsetWidth/);
  assert.match(
    toc,
    /if \(element\.classList\.contains\("markdown-target-hover"\)\) \{\s*element\.classList\.remove\("markdown-target-hover"\);\s*\}/,
  );
  assert.match(toc, /autoScrollingRef\.current = true;[\s\S]*element\.scrollIntoView/);
  assert.match(toc, /stopAutoScrollFlagLater\(900\)/);
  assert.match(toc, /if \(clickActiveLockRef\.current\) return;\s*ensureActiveVisible\("smooth"\);/);
});

test("markdown heading target navigation does not animate the destination", () => {
  const css = readSource("frontend/src/components/markdown.css");
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");

  assert.doesNotMatch(renderer, /flashMarkdownTarget/);
  assert.doesNotMatch(renderer, /markdown-target-flash/);
  assert.doesNotMatch(css, /markdown-target-flash/);
  assert.doesNotMatch(css, /@keyframes markdown-target-flash/);
});
