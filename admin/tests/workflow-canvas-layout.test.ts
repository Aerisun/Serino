import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(
  new URL("../src/pages/automation/WorkflowCanvas.tsx", import.meta.url),
  "utf-8",
);

describe("workflow canvas layout", () => {
  it("keeps content-heavy workflow nodes at a stable width", () => {
    expect(source).toContain(
      '"w-[240px] min-w-[240px] max-w-[240px] overflow-hidden',
    );
    expect(source).toContain('className="min-w-0 flex-1 space-y-1"');
    expect(source).toContain("break-words");
  });
});
