import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");

const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

test("home hero starts image and video requests together while keeping the poster visible", () => {
  const pageSource = readSource("frontend/src/pages/Index.tsx");
  const resetEffect = pageSource.match(
    /useEffect\(\(\) => \{([\s\S]*?)\},\s*\[videoUrl\]\);/,
  );
  const conditionalPosterBlock = pageSource.match(
    /\{showImageFallback\s*&&\s*\(\s*(<img\b[\s\S]*?\/>\s*)\)\}/,
  );
  const conditionalVideoBlock = pageSource.match(
    /\{showVideo\s*&&\s*\(\s*(<video\b[\s\S]*?<\/video>)\s*\)\}/,
  );

  assert.doesNotMatch(pageSource, /useDeferredActivation|videoActivated/);
  assert.match(
    pageSource,
    /const \[videoPlaying, setVideoPlaying\] = useState\(false\);/,
  );
  assert.ok(resetEffect, "hero video URL changes should reset playback state");
  assert.match(resetEffect[1], /setVideoPlaying\(false\);/);
  assert.match(resetEffect[1], /setVideoFailed\(false\);/);
  assert.match(
    pageSource,
    /const showVideo\s*=\s*Boolean\(videoUrl\)\s*&&\s*!videoFailed;/,
  );
  assert.match(
    pageSource,
    /const showImageFallback\s*=\s*Boolean\(posterUrl\);/,
  );
  assert.ok(conditionalPosterBlock, "hero poster should be gated by showImageFallback");
  assert.ok(conditionalVideoBlock, "hero video should be gated by showVideo");

  const posterBlock = conditionalPosterBlock[1];
  const videoBlock = conditionalVideoBlock[1];

  assert.match(posterBlock, /src=\{posterUrl\}/);
  assert.match(posterBlock, /loading="eager"/);
  assert.match(posterBlock, /fetchPriority="high"/);
  assert.doesNotMatch(posterBlock, /\bvideoPlaying\b|\bvideoFailed\b/);
  assert.ok(
    pageSource.indexOf(conditionalPosterBlock[0]) <
      pageSource.indexOf(conditionalVideoBlock[0]),
    "hero poster should be rendered before the conditional video",
  );

  assert.match(videoBlock, /preload="auto"/);
  assert.match(videoBlock, /transition-opacity duration-100/);
  assert.match(videoBlock, /onPlaying=\{\(\) => setVideoPlaying\(true\)\}/);
  assert.equal((pageSource.match(/setVideoPlaying\(true\)/g) ?? []).length, 1);
  assert.match(
    videoBlock,
    /onError=\{\(\) => \{[\s\S]*?setVideoPlaying\(false\);[\s\S]*?setVideoFailed\(true\);[\s\S]*?\}\}/,
  );
  assert.match(videoBlock, /videoPlaying \? "opacity-100" : "opacity-0"/);
  assert.doesNotMatch(videoBlock, /\bcrossOrigin\s*=/);
});

test("home hero treats each configured video URL as a distinct media identity", () => {
  const pageSource = readSource("frontend/src/pages/Index.tsx");
  const activationSource = readSource("frontend/src/hooks/useDeferredActivation.ts");
  const activate = activationSource.match(
    /const\s+activate\s*=\s*\(\s*\)\s*=>\s*\{([\s\S]*?)\n\s*\};/,
  );
  const conditionalVideoBlock = pageSource.match(
    /\{showVideo\s*&&\s*\(\s*(<video\b[\s\S]*?<\/video>)\s*\)\}/,
  );

  assert.ok(activate, "deferred activation should activate from a dedicated callback");
  assert.ok(conditionalVideoBlock, "hero video should be gated by showVideo");

  assert.match(
    activate[1],
    /depsKey[\s\S]*?setActive\(\s*true\s*\)/,
  );
  assert.match(
    activationSource,
    /return\s+active\s*&&\s*[^;]*depsKey[^;]*;/,
  );
  assert.match(conditionalVideoBlock[1], /<video\b[^>]*\bkey=\{videoUrl\}/);
  assert.match(conditionalVideoBlock[1], /<source\s+src=\{videoUrl\}/);
});
