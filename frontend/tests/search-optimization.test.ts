import { describe, expect, it } from "vitest";
import {
  DEFAULT_ROBOTS_DIRECTIVE,
  buildSearchMetadata,
  normalizeSearchOptimization,
} from "../src/lib/search-optimization";

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
        same_as: ["https://github.com/example"],
        canonical_url: "https://example.com",
      }),
      pathname: "/",
    });

    expect(metadata.title).toBe("Serino Notes");
    expect(metadata.shareTitle).toBe("Rowan - Frontend and AI Automation");
    expect(metadata.description).toBe("Rowan Zhu (Serino Notes). Notes, projects, and public writing by Rowan.");
    expect(metadata.author).toBe("Rowan Zhu");
    expect(metadata.keywords).toBe("frontend, AI automation");
    expect(metadata.robots).toBe(DEFAULT_ROBOTS_DIRECTIVE);
    expect(metadata.canonicalUrl).toBe("https://example.com/");
    expect(metadata.siteJsonLd["@context"]).toBe("https://schema.org");
    const [person, webSite, profilePage] = jsonLdGraph(metadata);
    expect(person).toMatchObject({
      "@type": "Person",
      name: "Rowan Zhu",
      alternateName: ["Serino Notes"],
      description: "Rowan Zhu (Serino Notes). A concise source of truth for Rowan's work and expertise.",
      sameAs: ["https://github.com/example"],
      knowsAbout: ["Frontend architecture", "Search optimization"],
      mainEntityOfPage: {
        "@id": "https://example.com/resume#profile",
      },
    });
    expect(webSite).toMatchObject({
      "@type": "WebSite",
      name: "Serino Notes",
      alternateName: "Rowan - Frontend and AI Automation",
      about: {
        "@id": "https://example.com#person",
      },
      mainEntity: {
        "@id": "https://example.com#person",
      },
    });
    expect(profilePage).toMatchObject({
      "@type": "ProfilePage",
      "@id": "https://example.com/resume#profile",
      url: "https://example.com/resume",
      mainEntity: {
        "@id": "https://example.com#person",
      },
    });
  });

  it("keeps the browser title branded while strengthening the configured real-name identity", () => {
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
    expect(metadata.description).toContain("Configured Person (Aerisun)");
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
        "@id": "https://example.com#person",
      },
      mainEntity: {
        "@id": "https://example.com#person",
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
    expect(metadata.shareTitle).toBe("Rowan Zhu Resume · Serino Notes");
    expect(metadata.canonicalUrl).toBe("https://example.com/resume");
    const [person, , profilePage] = jsonLdGraph(metadata);
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
  });
});
