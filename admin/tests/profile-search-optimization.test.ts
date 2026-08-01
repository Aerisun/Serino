import fs from "node:fs";
import { describe, expect, it } from "vitest";
import type { SiteProfileAdminRead } from "@serino/api-client/models";
import {
  buildProfilePayload,
  buildSiteBrandTitle,
  createProfileForm,
  isSearchOptimizationValid,
  isCanonicalUrlValid,
  serializeSearchOptimization,
  shouldBlockSearchOptimizationSave,
} from "../src/pages/site-config/tabs/ProfileTab";

const profileTab = fs.readFileSync(
  new URL("../src/pages/site-config/tabs/ProfileTab.tsx", import.meta.url),
  "utf-8",
);
const adminIndex = fs.readFileSync(new URL("../index.html", import.meta.url), "utf-8");

describe("profile search optimization controls", () => {
  it("adds a collapsible search optimization block in the profile tab", () => {
    expect(profileTab).toContain("CollapsibleSection");
    expect(profileTab).toContain("搜索优化");
    expect(profileTab).toContain("search_optimization");
    expect(profileTab).toContain("search_real_name");
    expect(profileTab).toContain("real_name");
    expect(profileTab).toContain("LabelWithHelp");
  });

  it("requires a real name before saving search optimization data", () => {
    expect(profileTab).toContain("isSearchOptimizationValid");
    expect(profileTab).toContain("search_english_name");
    expect(profileTab).toContain("english_name");
    expect(profileTab).toContain("请同时填写中文名和英文名");
    expect(profileTab).toContain("hasSearchOptimizationChanges");
    expect(profileTab).toContain("required");
    expect(profileTab).toContain("!border-destructive");
  });

  it("renders Chinese and English names as one divided input group", () => {
    expect(profileTab).toContain('aria-label={lang === "zh" ? "中文名" : "Chinese name"}');
    expect(profileTab).toContain('aria-label={lang === "zh" ? "英文名" : "English name"}');
    expect(profileTab).toContain("grid-cols-2");
    expect(profileTab).toContain("divide-x");
  });

  it("removes the manual site title and derives it from the homepage name and SEO identity", () => {
    expect(profileTab).not.toContain('(["name", "title", "role"] as const)');
    expect(profileTab).toContain('(["name", "role"] as const)');
    expect(profileTab).toContain("buildSiteBrandTitle");
    expect(profileTab).toContain('`${displayName} - ${realName}(${englishName})`');
    expect(profileTab).toContain("payload.title = buildSiteBrandTitle(form)");
  });

  it("restores keyword-like lists with visible comma separators", () => {
    expect(profileTab).toContain("readDelimitedTextList");
    expect(profileTab).toContain('readList(value, ", ")');
    expect(profileTab).toContain("search_keywords: readDelimitedTextList(config.keywords)");
    expect(profileTab).toContain("search_expertise: readDelimitedTextList(config.expertise)");
    expect(profileTab).toContain("search_same_as: readLineTextList(config.same_as)");
  });

  it("round-trips delimited lists and preserves unrelated feature flags", () => {
    const profile = {
      name: "Aerisun",
      feature_flags: {
        toc: true,
        search_optimization: {
          real_name: "杨汶帛",
          english_name: "Wenbo Yang",
          keywords: ["杨汶帛", "Wenbo Yang", "Aerisun"],
          expertise: ["AI Infra", "AI Agent", "全栈开发"],
          same_as: ["https://github.com/Aerisun", "https://example.com/profile"],
        },
      },
    } as SiteProfileAdminRead;

    const form = createProfileForm(profile);
    expect(form.search_keywords).toBe("杨汶帛, Wenbo Yang, Aerisun");
    expect(form.search_expertise).toBe("AI Infra, AI Agent, 全栈开发");
    expect(form.search_same_as).toBe("https://github.com/Aerisun\nhttps://example.com/profile");
    expect(buildSiteBrandTitle(form)).toBe("Aerisun - 杨汶帛(Wenbo Yang)");

    const payload = buildProfilePayload(form, profile);
    expect(payload.title).toBe("Aerisun - 杨汶帛(Wenbo Yang)");
    expect(payload.feature_flags).toMatchObject({
      toc: true,
      search_optimization: {
        keywords: ["杨汶帛", "Wenbo Yang", "Aerisun"],
        expertise: ["AI Infra", "AI Agent", "全栈开发"],
        same_as: ["https://github.com/Aerisun", "https://example.com/profile"],
      },
    });
  });

  it("rejects an incomplete bilingual identity after search settings change", () => {
    const form = createProfileForm();
    form.search_real_name = "杨汶帛";
    expect(isSearchOptimizationValid(serializeSearchOptimization(form))).toBe(false);
  });

  it("allows unrelated edits when a legacy profile already has an incomplete identity", () => {
    const savedForm = createProfileForm({
      name: "Aerisun",
      bio: "原简介",
      feature_flags: {
        search_optimization: {
          real_name: "杨汶帛",
        },
      },
    } as SiteProfileAdminRead);
    const unrelatedEdit = { ...savedForm, bio: "新简介" };
    const searchEdit = { ...savedForm, search_meta_description: "新搜索摘要" };

    expect(shouldBlockSearchOptimizationSave(unrelatedEdit, savedForm)).toBe(false);
    expect(shouldBlockSearchOptimizationSave(searchEdit, savedForm)).toBe(true);
  });

  it("accepts only HTTP(S) canonical site roots without query or fragment data", () => {
    expect(isCanonicalUrlValid("")).toBe(true);
    expect(isCanonicalUrlValid("https://aerisun.top")).toBe(true);
    expect(isCanonicalUrlValid("HTTPS://EXAMPLE.COM:443/")).toBe(true);
    expect(isCanonicalUrlValid("https://example.com/blog/")).toBe(false);
    expect(isCanonicalUrlValid("javascript:alert(1)")).toBe(false);
    expect(isCanonicalUrlValid("https://example.com/?source=legacy")).toBe(false);
    expect(isCanonicalUrlValid("https://example.com/#section")).toBe(false);
  });

  it("keeps the admin shell out of search indexes", () => {
    expect(adminIndex).toContain('name="robots"');
    expect(adminIndex).toContain("noindex");
    expect(adminIndex).toContain("nofollow");
  });
});
