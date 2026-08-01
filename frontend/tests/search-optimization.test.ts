import { describe, expect, it } from "vitest";
import {
  DEFAULT_ROBOTS_DIRECTIVE,
  buildSearchMetadata,
  normalizeSearchOptimization,
} from "../src/lib/search-optimization";
import { normalizePublicBaseUrl } from "../src/lib/public-url";

const baseSite = {
  name: "Rowan",
  title: "Serino Notes",
  bio: "Personal site about frontend, automation, and long-form notes.",
  role: "Independent developer",
  ogImage: "https://example.com/og.png",
};

const jsonLdGraph = (metadata: ReturnType<typeof buildSearchMetadata>) =>
  metadata.siteJsonLd["@graph"] as Array<Record<string, unknown>>;

describe("search optimization metadata", () => {
  it("normalizes stored feature flag values for SEO and GEO", () => {
    const config = normalizeSearchOptimization({
      meta_title: "  Rowan - Frontend and AI Automation  ",
      meta_description: "  Notes, projects, and public writing by Rowan.  ",
      keywords: "frontend, AI automation\npersonal website",
      llm_summary: "  Rowan builds thoughtful frontend systems and automation tools.  ",
      real_name: "  Rowan Zhu  ",
      english_name: "  Rowan Zhu  ",
      expertise: ["Frontend systems", " AI agents ", ""],
      same_as: "https://github.com/example\nhttps://www.linkedin.com/in/example",
      canonical_url: "https://example.com/",
    });

    expect(config).toEqual({
      metaTitle: "Rowan - Frontend and AI Automation",
      metaDescription: "Notes, projects, and public writing by Rowan.",
      keywords: ["frontend", "AI automation", "personal website"],
      llmSummary: "Rowan builds thoughtful frontend systems and automation tools.",
      realName: "Rowan Zhu",
      englishName: "Rowan Zhu",
      expertise: ["Frontend systems", "AI agents"],
      sameAs: ["https://github.com/example", "https://www.linkedin.com/in/example"],
      canonicalUrl: "https://example.com/",
    });
  });

  it("builds crawler-facing metadata and structured identity data", () => {
    const metadata = buildSearchMetadata({
      site: baseSite,
      searchOptimization: normalizeSearchOptimization({
        meta_title: "Rowan - Frontend and AI Automation",
        meta_description: "Notes, projects, and public writing by Rowan.",
        keywords: ["frontend", "AI automation"],
        llm_summary: "A concise source of truth for Rowan's work and expertise.",
        real_name: "Rowan Zhu",
        expertise: ["Frontend architecture", "Search optimization"],
        same_as: ["https://github.com/example", "mailto:rowan@example.com"],
        canonical_url: "https://example.com",
      }),
      pathname: "/",
    });

    expect(metadata.title).toBe("Rowan");
    expect(metadata.shareTitle).toBe("Rowan - Frontend and AI Automation");
    expect(metadata.description).toBe("Notes, projects, and public writing by Rowan.");
    expect(metadata.author).toBe("Rowan Zhu");
    expect(metadata.keywords).toBe("Rowan Zhu, Rowan, frontend, AI automation");
    expect(metadata.robots).toBe(DEFAULT_ROBOTS_DIRECTIVE);
    expect(metadata.canonicalUrl).toBe("https://example.com/");
    expect(metadata.siteJsonLd["@context"]).toBe("https://schema.org");
    const [person, webSite] = jsonLdGraph(metadata);
    expect(person).toMatchObject({
      "@type": "Person",
      "@id": "https://example.com/#person",
      name: "Rowan Zhu",
      alternateName: ["Rowan"],
      description: "A concise source of truth for Rowan's work and expertise.",
      sameAs: ["https://github.com/example"],
      knowsAbout: ["Frontend architecture", "Search optimization"],
      mainEntityOfPage: {
        "@id": "https://example.com/resume#profile",
      },
    });
    expect(webSite).toMatchObject({
      "@type": "WebSite",
      "@id": "https://example.com/#website",
      name: "Rowan",
      about: {
        "@id": "https://example.com/#person",
      },
      mainEntity: {
        "@id": "https://example.com/#person",
      },
    });
    expect(webSite).not.toHaveProperty("alternateName");
    expect(jsonLdGraph(metadata)).toHaveLength(2);
  });

  it("keeps the browser title branded without rewriting the configured description", () => {
    const metadata = buildSearchMetadata({
      site: {
        ...baseSite,
        name: "Aerisun",
        title: "Aerisun",
        bio: "I write frontend notes and personal essays.",
      },
      searchOptimization: normalizeSearchOptimization({
        real_name: "Configured Person",
        canonical_url: "https://example.com",
      }),
      pathname: "/",
    });

    expect(metadata.title).toBe("Aerisun");
    expect(metadata.description).toBe("I write frontend notes and personal essays.");
    expect(metadata.author).toBe("Configured Person");
    const [person, webSite] = jsonLdGraph(metadata);
    expect(person).toMatchObject({
      "@type": "Person",
      name: "Configured Person",
      alternateName: ["Aerisun"],
    });
    expect(webSite).toMatchObject({
      "@type": "WebSite",
      name: "Aerisun",
      about: {
        "@id": "https://example.com/#person",
      },
      mainEntity: {
        "@id": "https://example.com/#person",
      },
    });
  });

  it("uses the resume page as the structured profile target without treating it as the homepage", () => {
    const metadata = buildSearchMetadata({
      site: baseSite,
      searchOptimization: normalizeSearchOptimization({
        meta_title: "Rowan - Frontend and AI Automation",
        real_name: "Rowan Zhu",
        canonical_url: "https://example.com",
      }),
      pageTitle: "",
      pathname: "/resume",
    });

    expect(metadata.title).toBe("Rowan Zhu");
    expect(metadata.shareTitle).toBe("Rowan Zhu Resume · Rowan");
    expect(metadata.canonicalUrl).toBe("https://example.com/resume");
    const [person, profilePage] = jsonLdGraph(metadata);
    expect(person).toMatchObject({
      "@type": "Person",
      name: "Rowan Zhu",
      mainEntityOfPage: {
        "@id": "https://example.com/resume#profile",
      },
    });
    expect(profilePage).toMatchObject({
      "@type": "ProfilePage",
      "@id": "https://example.com/resume#profile",
      url: "https://example.com/resume",
    });
    expect(jsonLdGraph(metadata)).toHaveLength(2);
  });

  it("derives the homepage title while making the resume and identity bilingual", () => {
    const searchOptimization = normalizeSearchOptimization({
      real_name: "杨汶帛",
      english_name: "Wenbo Yang",
      canonical_url: "https://aerisun.top",
    });
    const site = {
      ...baseSite,
      name: "Aerisun",
      title: "Aerisun",
      bio: "北京大学本科生，关注全栈开发与 AI 基础设施。",
    };

    const home = buildSearchMetadata({
      site,
      searchOptimization,
      pathname: "/",
    });
    const resume = buildSearchMetadata({
      site,
      searchOptimization,
      pageTitle: "遗留的简历页标题",
      pathname: "/resume",
    });
    const posts = buildSearchMetadata({
      site,
      searchOptimization,
      pageTitle: "Posts",
      pathname: "/posts",
      ogType: "article",
    });

    expect(home.title).toBe("Aerisun - 杨汶帛(Wenbo Yang)");
    expect(home.siteTitle).toBe("Aerisun");
    expect(home.description).toBe("北京大学本科生，关注全栈开发与 AI 基础设施。");
    const [person] = jsonLdGraph(home);
    expect(person).toMatchObject({
      "@type": "Person",
      name: "杨汶帛",
      alternateName: ["Wenbo Yang", "Aerisun"],
    });
    expect(resume.title).toBe("杨汶帛 - Wenbo Yang");
    expect(resume.shareTitle).toBe("杨汶帛 - Wenbo Yang Resume · Aerisun");
    expect(posts.title).toBe("Posts · Aerisun");
    expect(posts.ogType).toBe("article");
    expect(posts.title).not.toContain("杨汶帛");
    const [, profilePage] = jsonLdGraph(resume);
    expect(profilePage).toMatchObject({
      "@type": "ProfilePage",
      name: "杨汶帛 - Wenbo Yang Resume",
    });
  });

  it("falls back to the homepage display name unless both SEO names are configured", () => {
    const site = {
      ...baseSite,
      name: "Aerisun",
      title: "A manually configured legacy title",
    };

    const withoutNames = buildSearchMetadata({
      site,
      searchOptimization: normalizeSearchOptimization({}),
      pathname: "/",
    });
    const incompleteNames = buildSearchMetadata({
      site,
      searchOptimization: normalizeSearchOptimization({ real_name: "杨汶帛" }),
      pathname: "/",
    });

    expect(withoutNames.title).toBe("Aerisun");
    expect(incompleteNames.title).toBe("Aerisun");
  });

  it("uses the configured meta description exactly without adding identity prefixes", () => {
    const configuredDescription =
      "杨汶帛，北京大学集成电路设计与集成系统专业24级本科生，辅修智能科学与技术";
    const metadata = buildSearchMetadata({
      site: {
        ...baseSite,
        name: "Aerisun",
      },
      searchOptimization: normalizeSearchOptimization({
        real_name: "杨汶帛",
        english_name: "Wenbo Yang",
        meta_description: configuredDescription,
      }),
      pathname: "/",
    });

    expect(metadata.description).toBe(configuredDescription);
  });

  it("falls back from an unsafe canonical URL and supports noindex pages", () => {
    const metadata = buildSearchMetadata({
      site: baseSite,
      searchOptimization: normalizeSearchOptimization({
        canonical_url: "javascript:alert(1)",
      }),
      pageTitle: "Missing",
      pathname: "/missing",
      origin: "https://current.example",
      noIndex: true,
    });

    expect(metadata.canonicalUrl).toBe("https://current.example/missing");
    expect(metadata.robots).toBe("noindex,follow");
  });

  it("rejects configured canonical values that are not a site origin", () => {
    const metadata = buildSearchMetadata({
      site: { ...baseSite, ogImage: "/media/share.webp" },
      searchOptimization: normalizeSearchOptimization({
        canonical_url: "https://canonical.example/blog/?source=legacy#section",
      }),
      pathname: "/posts/example",
      origin: "https://current.example",
    });

    expect(metadata.canonicalUrl).toBe("https://current.example/posts/example");
    expect(metadata.image).toBe("https://current.example/media/share.webp");
  });

  it("normalizes canonical origins consistently", () => {
    expect(normalizePublicBaseUrl("HTTPS://EXAMPLE.COM:443/")).toBe("https://example.com");
    expect(normalizePublicBaseUrl("http://EXAMPLE.COM:80/")).toBe("http://example.com");
    expect(normalizePublicBaseUrl("https://example.com/blog")).toBe("");
  });

  it("normalizes trailing slashes and transient URL data in page canonicals", () => {
    const metadata = buildSearchMetadata({
      site: baseSite,
      searchOptimization: normalizeSearchOptimization({
        canonical_url: "https://canonical.example",
      }),
      pathname: "/posts/example/?utm_source=test#section",
    });

    expect(metadata.canonicalUrl).toBe("https://canonical.example/posts/example");
  });
});
