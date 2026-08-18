import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = (path) => readFileSync(resolve(frontendRoot, "src", path), "utf8");

test("posts and excerpts share the category filter, while thoughts remain unclassified", () => {
  const posts = source("pages/Posts.tsx");
  const excerpts = source("pages/Excerpts.tsx");
  const thoughts = source("pages/Thoughts.tsx");

  for (const page of [posts, excerpts]) {
    assert.match(page, /import \{ CategoryFilter \} from "@\/components\/CategoryFilter"/);
    assert.match(page, /<CategoryFilter/);
    assert.match(page, /activeCategory/);
    assert.match(page, /category: activeCategory \?\? undefined/);
    assert.doesNotMatch(page, /const allCategories = useMemo/);
  }

  assert.match(posts, /const pageKey = kind === "note" \? "notes" : "posts";/);
  assert.match(posts, /queryKey: \["site", pageKey, pageSize, activeCategory\]/);
  assert.match(posts, /showSearch=\{!isNoteView\}/);
  assert.match(excerpts, /queryKey: \["site", "excerpts", pageSize, activeCategory\]/);
  assert.doesNotMatch(thoughts, /CategoryFilter/);
  assert.doesNotMatch(thoughts, /activeCategory/);
  assert.doesNotMatch(thoughts, /allCategories/);
});

test("category filtering no longer relies on the already loaded list", () => {
  for (const path of ["pages/Posts.tsx", "pages/Excerpts.tsx"]) {
    const page = source(path);
    assert.doesNotMatch(page, /const matchCategory =/);
  }
});
