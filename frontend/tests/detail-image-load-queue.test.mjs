import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");
const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

test("article, diary, and comment images reuse the controlled page image queue", () => {
  const queueImage = readSource("frontend/src/components/QueuedAttachmentImage.tsx");
  const markdown = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const comments = readSource("frontend/src/components/CommentSection.tsx");
  const postDetail = readSource("frontend/src/pages/PostDetail.tsx");
  const diaryDetail = readSource("frontend/src/pages/DiaryDetail.tsx");

  assert.match(queueImage, /export function useQueuedImageLoad/);
  assert.match(queueImage, /export function ImageLoadQueueBoundary/);
  assert.match(queueImage, /const isVisibleThroughAncestors/);
  assert.match(queueImage, /if \(!isVisibleThroughAncestors\(element\)\)/);
  assert.match(queueImage, /new ResizeObserver/);
  assert.match(queueImage, /const promoteIfNearViewport/);
  assert.match(markdown, /useQueuedImageLoad/);
  assert.match(markdown, /fetchPriority=\{imageLoad\.fetchPriority\}/);
  assert.match(comments, /import \{ ImageLoadQueueBoundary \} from "@\/components\/QueuedAttachmentImage"/);
  assert.match(comments, /<ImageLoadQueueBoundary>[\s\S]*?<WalineSurface/);
  assert.match(postDetail, /import \{ ImageLoadQueueProvider \} from "@\/components\/QueuedAttachmentImage"/);
  assert.match(postDetail, /<ImageLoadQueueProvider>[\s\S]*?<ArticleMarkdownRenderer/);
  assert.match(diaryDetail, /import \{ ImageLoadQueueProvider \} from "@\/components\/QueuedAttachmentImage"/);
  assert.match(diaryDetail, /<ImageLoadQueueProvider>[\s\S]*?<ArticleMarkdownRenderer/);
});
