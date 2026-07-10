import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";

const excerptsPagePath = fileURLToPath(new URL("../src/pages/Excerpts.tsx", import.meta.url));

test("excerpt details render extracted image attachments while cards keep text-only snippets", async () => {
  const source = await readFile(excerptsPagePath, "utf8");

  assert.match(source, /import CommentMarkdownRenderer from "@\/components\/CommentMarkdownRenderer";/);
  assert.match(source, /<CommentMarkdownRenderer\s+content=\{selected\.content\}/);
  assert.match(source, /stripMarkdownImages\(excerpt\.content\)/);
});
