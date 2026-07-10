import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const thoughtEditor = readFileSync(
  new URL("../src/pages/thoughts/ThoughtEditPage.tsx", import.meta.url),
  "utf-8",
);
const excerptEditor = readFileSync(
  new URL("../src/pages/excerpts/ExcerptEditPage.tsx", import.meta.url),
  "utf-8",
);
const postEditor = readFileSync(
  new URL("../src/pages/posts/PostEditPage.tsx", import.meta.url),
  "utf-8",
);
const diaryEditor = readFileSync(
  new URL("../src/pages/diary/DiaryEditPage.tsx", import.meta.url),
  "utf-8",
);

describe("Markdown image layout scope", () => {
  it("enables attachment images only for thoughts and excerpts", () => {
    expect(thoughtEditor).toContain('imageLayout="attachments"');
    expect(excerptEditor).toContain('imageLayout="attachments"');
    expect(postEditor).not.toContain('imageLayout="attachments"');
    expect(diaryEditor).not.toContain('imageLayout="attachments"');
  });
});
