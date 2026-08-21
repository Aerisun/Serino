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

const adminIndex = fs.readFileSync(new URL("../index.html", import.meta.url), "utf-8");

describe("profile search optimization controls", () => {
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
