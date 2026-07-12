import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const frontendRoot = resolve(import.meta.dirname, "..");
const source = readFileSync(resolve(frontendRoot, "src/pages/PostDetail.tsx"), "utf8");

test("post detail keeps published_at as the displayed date and uses updated_at only for its update label", () => {
  assert.match(source, /date: formatPublishedDate\(entry\.published_at\)/);
  assert.match(source, /updatedAt: parseUpdateTimestamp\(entry\.updated_at\)/);
  assert.match(source, /date: formatPublishedDate\(preview\.published_at\)/);
  assert.match(source, /updatedAt: parseUpdateTimestamp\(preview\.updated_at\)/);
  assert.match(source, /const updatedRelativeLabel = post\?\.updatedAt != null/);
  assert.match(source, /updatedRelativeLabel \?/);
  assert.match(source, /post-updated-at/);
  assert.match(source, /最后更新于/);
  assert.match(source, /post-updated-at-value/);
  assert.match(source, /inline-flex items-baseline gap-1 mr-4/);
  assert.match(source, /\{" \("\}/);
  assert.match(source, /最后更新于 <span className="post-updated-at-value">\{updatedRelativeLabel\}<\/span>\{updatedRelativeSuffix \? ` \$\{updatedRelativeSuffix\}` : ""\}\)/);
});

test("post detail places the word count before its category", () => {
  const categoryIndex = source.indexOf("{post.category}");
  const titleIndex = source.indexOf("<h1 className=");
  const tagRowIndex = source.indexOf("<div className=\"mt-4 flex flex-wrap gap-2\">", titleIndex);

  assert.ok(titleIndex > -1);
  assert.ok(tagRowIndex > titleIndex);
  assert.ok(categoryIndex > tagRowIndex);
});

test("post detail splits comma-separated tag values into separate pills", () => {
  assert.match(source, /tags: normalizeContentTags\(entry\.tags\)/);
  assert.match(source, /tags: normalizeContentTags\(preview\.tags\)/);
});
