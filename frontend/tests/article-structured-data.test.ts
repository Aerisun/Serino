import fs from "node:fs";
import { describe, expect, it } from "vitest";
import {
  buildArticleStructuredData,
  buildContentSearchDescription,
} from "../src/lib/article-structured-data";

describe("article structured data", () => {
  it("reuses the canonical bilingual person identity without changing visible article UI", () => {
    const data = buildArticleStructuredData({
      title: "从零搭建设计系统",
      description: "文章摘要",
      slug: "design-system",
      type: "posts",
      publishedAt: "2026-08-01",
      modifiedAt: "2026-08-02T12:00:00+08:00",
      tags: ["设计系统"],
      image: "/media/share.webp",
      origin: "https://preview.example.com",
      canonicalBaseUrl: "https://canonical.example",
      siteName: "Aerisun",
      realName: "杨汶帛",
    });

    expect(data).toMatchObject({
      "@type": "BlogPosting",
      author: {
        "@type": "Person",
        "@id": "https://canonical.example/#person",
        name: "杨汶帛",
        url: "https://canonical.example/resume",
      },
      publisher: {
        "@id": "https://canonical.example/#person",
      },
      "@id": "https://canonical.example/posts/design-system#article",
      url: "https://canonical.example/posts/design-system",
      datePublished: "2026-08-01",
      dateModified: "2026-08-02T12:00:00+08:00",
      image: "https://canonical.example/media/share.webp",
      mainEntityOfPage: {
        "@id": "https://canonical.example/posts/design-system",
      },
    });
  });

  it("does not ship hard-coded or misleading global alternate-page links", () => {
    const indexHtml = fs.readFileSync(new URL("../index.html", import.meta.url), "utf-8");

    expect(indexHtml).not.toContain("https://aerisun.top");
    expect(indexHtml).not.toContain("AI-readable resume page");
    expect(indexHtml).not.toContain('rel="alternate"');
  });

  it("falls back to the current deployment origin when no canonical URL is configured", () => {
    const data = buildArticleStructuredData({
      title: "文章标题",
      description: "文章摘要",
      slug: "article",
      type: "posts",
      origin: "https://preview.example.com",
      siteName: "Aerisun",
      realName: "杨汶帛",
    });

    expect(data).toMatchObject({
      author: {
        "@id": "https://preview.example.com/#person",
        url: "https://preview.example.com/resume",
      },
      mainEntityOfPage: {
        "@id": "https://preview.example.com/posts/article",
      },
    });
  });

  it("ignores unsafe configured canonical URLs", () => {
    const data = buildArticleStructuredData({
      title: "文章标题",
      description: "文章摘要",
      slug: "article",
      type: "posts",
      origin: "https://current.example",
      canonicalBaseUrl: "javascript:alert(1)",
      siteName: "Aerisun",
      realName: "杨汶帛",
    });

    expect(data).toMatchObject({
      "@id": "https://current.example/posts/article#article",
      author: {
        "@id": "https://current.example/#person",
      },
    });
  });

  it("keeps article metadata summaries consistent and strips Markdown only for body fallbacks", () => {
    expect(
      buildContentSearchDescription({
        summary: "  用户填写的摘要  ",
        body: "# 不应使用的正文",
      }),
    ).toBe("用户填写的摘要");
    expect(
      buildContentSearchDescription({
        body: "# 标题\n正文包含 [站点](https://example.com) 与 **重点**。",
      }),
    ).toBe("标题 正文包含 站点 与 重点 。");

    const longDescription = "长".repeat(240);
    const data = buildArticleStructuredData({
      title: "文章标题",
      description: longDescription,
      slug: "long-description",
      type: "posts",
      origin: "https://example.com",
      siteName: "Aerisun",
      realName: "杨汶帛",
    });
    expect(data.description).toBe(longDescription);
  });
});
