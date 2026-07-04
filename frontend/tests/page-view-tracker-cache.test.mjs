import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");

const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

test("post detail page-view reports do not optimistically mutate cached post view counts", () => {
  const trackerSource = readSource("frontend/src/components/PageViewTracker.tsx");

  assert.match(trackerSource, /reportPageView/);
  assert.doesNotMatch(trackerSource, /useQueryClient/);
  assert.doesNotMatch(trackerSource, /content-view-cache/);
  assert.doesNotMatch(trackerSource, /resolvePostDetailSlug/);
  assert.doesNotMatch(trackerSource, /invalidateQueries\(\{\s*queryKey:\s*\["site",\s*"posts"\]/);
});
