import fs from "node:fs";
import { describe, expect, it } from "vitest";

const resumePage = fs.readFileSync(
  new URL("../src/pages/resume/ResumePage.tsx", import.meta.url),
  "utf-8",
);

describe("ResumePage dark surface", () => {
  it("uses admin surface tokens instead of a hard-coded white desktop background", () => {
    expect(resumePage).not.toContain("sm:bg-[rgba(255,255,255,0.72)]");
    expect(resumePage).toContain(
      "sm:bg-[rgb(var(--admin-surface-strong)/var(--admin-surface-alpha-strong))]",
    );
    expect(resumePage).toContain(
      "sm:border-[rgba(var(--admin-border-subtle)/var(--admin-border-subtle-alpha))]",
    );
  });
});
