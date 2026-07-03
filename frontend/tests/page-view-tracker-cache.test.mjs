import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");

const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

test("post detail page-view reports update cached post view counts without refetching lists", () => {
  const trackerSource = readSource("frontend/src/components/PageViewTracker.tsx");
  const cacheSource = readSource("frontend/src/lib/content-view-cache.ts");

  assert.match(trackerSource, /useQueryClient/);
  assert.match(trackerSource, /resolvePostDetailSlug/);
  assert.match(trackerSource, /incrementPostViewCountInCache\(queryClient,\s*postSlug\)/);
  assert.doesNotMatch(trackerSource, /invalidateQueries\(\{\s*queryKey:\s*\["site",\s*"posts"\]/);

  assert.match(cacheSource, /setQueriesData<InfiniteContentList>/);
  assert.match(cacheSource, /setQueryData<ContentDetailResponse>/);
  assert.doesNotMatch(cacheSource, /invalidateQueries/);
});
