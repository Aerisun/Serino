import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const readSource = (path: string) =>
  readFileSync(new URL(path, import.meta.url), "utf-8");

describe("extended configuration layout", () => {
  it("omits decorative English eyebrows from network, mail, and storage settings", () => {
    const sources = [
      "../src/pages/more/ProxyConfigSection.tsx",
      "../src/pages/more/ExternalConfigSection.tsx",
      "../src/pages/more/ObjectStorageSection.tsx",
    ].map(readSource);

    for (const source of sources) {
      expect(source).not.toContain("eyebrow=");
      expect(source).not.toContain("eyebrow:");
    }
  });

  it("centers the active configuration section without changing its content", () => {
    const source = readSource("../src/pages/more/MorePage.tsx");

    expect(source).toContain('className="flex justify-center"');
  });

  it("keeps the feature toggle card within the shared centered width", () => {
    const source = readSource("../src/pages/more/FeatureTogglesSection.tsx");

    expect(source).toContain('className="mt-4 w-full max-w-2xl space-y-5"');
  });
});
