import fs from "node:fs";
import { describe, expect, it } from "vitest";

const source = fs.readFileSync(
  new URL("../src/components/PageViewTracker.tsx", import.meta.url),
  "utf-8",
);

describe("page view cache isolation", () => {
  it("reports visits without mutating shared content query caches", () => {
    expect(source).toContain("reportPageView");
    expect(source).not.toContain("useQueryClient");
    expect(source).not.toContain("setQueryData");
    expect(source).not.toContain("invalidateQueries");
  });
});
