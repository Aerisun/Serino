import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(frontendRoot, "src/pages/Friends.tsx"), "utf8");

test("friends page removes the Friend Circle header controls while keeping its content", () => {
  assert.doesNotMatch(source, /const circleTitle/);
  assert.doesNotMatch(source, /const updatedLabel/);
  assert.doesNotMatch(source, /const refreshLabel/);
  assert.doesNotMatch(source, /const summaryTemplate/);
  assert.doesNotMatch(source, /<h2 className="text-2xl font-heading italic/);
  assert.match(source, /randomPickerLabel/);
  assert.match(source, /visiblePosts\.map/);
  assert.match(source, /onClick=\{\(\) => refetchAll\(\)\}/);
});
