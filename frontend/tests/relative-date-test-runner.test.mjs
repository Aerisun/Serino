import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const frontendRoot = resolve(import.meta.dirname, "..");
const packageJson = JSON.parse(readFileSync(resolve(frontendRoot, "package.json"), "utf8"));

test("frontend test command runs the relative-date Vitest suite", () => {
  assert.match(packageJson.scripts.test, /^vitest run tests\/\*\.test\.ts && node --test/);
});
