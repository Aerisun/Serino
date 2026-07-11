import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(frontendRoot, "src/pages/Posts.tsx"), "utf8");

test("article list excerpts are limited to two lines", () => {
  assert.match(
    source,
    /<p className="mt-2 line-clamp-2 text-sm leading-relaxed text-foreground\/35/,
  );
  assert.doesNotMatch(
    source,
    /<p className="mt-2 line-clamp-1 text-sm leading-relaxed text-foreground\/35/,
  );
});

test("article list counters stay grouped at the right edge when they wrap", () => {
  assert.match(
    source,
    /<div className="ml-auto flex shrink-0 items-center gap-4 whitespace-nowrap">[\s\S]*<Eye[\s\S]*<MessageCircle/,
  );
});
