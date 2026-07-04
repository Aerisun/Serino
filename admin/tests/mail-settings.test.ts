import fs from "node:fs";
import { describe, expect, it } from "vitest";

const externalConfigSection = fs.readFileSync(
  new URL("../src/pages/more/ExternalConfigSection.tsx", import.meta.url),
  "utf-8",
);

describe("mail settings", () => {
  it("persists successful SMTP tests from the test button", () => {
    expect(externalConfigSection).toContain(
      'onClick={() => void runMailCheck({ persistSuccess: true })}',
    );
  });
});
