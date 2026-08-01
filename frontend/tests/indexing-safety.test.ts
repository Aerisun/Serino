import fs from "node:fs";
import { describe, expect, it } from "vitest";

const source = (relativePath: string) =>
  fs.readFileSync(new URL(`../src/${relativePath}`, import.meta.url), "utf-8");

describe("private and preview indexing safety", () => {
  it("keeps every preview surface out of search indexes", () => {
    const pageShell = source("components/PageShell.tsx");
    const preview = source("pages/Preview.tsx");
    const thoughts = source("pages/Thoughts.tsx");
    const excerpts = source("pages/Excerpts.tsx");
    const caddy = fs.readFileSync(new URL("../../Caddyfile", import.meta.url), "utf-8");

    expect(pageShell).toContain("noIndex?: boolean");
    expect(pageShell).toContain("noIndex={noIndex}");
    expect(preview).toContain("<PageMeta");
    expect(preview).toContain("noIndex");
    expect(thoughts).toContain("noIndex={Boolean(previewThought)}");
    expect(excerpts).toContain("noIndex={Boolean(previewExcerpt)}");
    expect(caddy).toContain('X-Robots-Tag "noindex, nofollow"');
    expect(caddy).toContain("path /preview");
  });

  it("keeps archived and access-protected details out of search indexes", () => {
    const posts = source("pages/PostDetail.tsx");
    const diary = source("pages/DiaryDetail.tsx");

    expect(posts).toContain("post?.isArchived");
    expect(posts).toContain("post?.requiresApproval");
    expect(diary).toContain("diaryPrivateEnabled");
    expect(diary).toContain("entry?.isArchived");
  });
});
