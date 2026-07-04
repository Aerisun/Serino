import fs from "node:fs";
import { describe, expect, it } from "vitest";

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
    expect(profileTab).toContain("请先填写真实姓名");
    expect(profileTab).toContain("required");
  });

  it("keeps the admin shell out of search indexes", () => {
    expect(adminIndex).toContain('name="robots"');
    expect(adminIndex).toContain("noindex");
    expect(adminIndex).toContain("nofollow");
  });
});
