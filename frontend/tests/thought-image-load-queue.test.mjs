import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");
const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

test("thought attachments use a controlled foreground and background image queue", () => {
  const queueImage = readSource("frontend/src/components/QueuedAttachmentImage.tsx");
  const thoughts = readSource("frontend/src/pages/Thoughts.tsx");
  const excerpts = readSource("frontend/src/pages/Excerpts.tsx");

  assert.match(queueImage, /createImageLoadQueue/);
  assert.match(queueImage, /import \{ shouldBackgroundPrefetch \} from "@\/lib\/idle"/);
  assert.match(queueImage, /if \(!shouldBackgroundPrefetch\(\)\) \{\s*return;\s*\}/);
  assert.match(queueImage, /queue\.resumeBackground\(\)/);
  assert.match(queueImage, /new IntersectionObserver/);
  assert.match(queueImage, /loading: queue \? "eager" : "lazy"/);
  assert.match(queueImage, /loadPriority === "foreground"\s*\? "high"\s*:\s*"low"/);
  assert.match(thoughts, /import \{ ImageLoadQueueProvider \} from "@\/components\/QueuedAttachmentImage"/);
  assert.match(thoughts, /<ImageLoadQueueProvider>[\s\S]*?<CommentMarkdownRenderer/);
  assert.doesNotMatch(excerpts, /ImageLoadQueueProvider/);
});
