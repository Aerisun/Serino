import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const source = readFileSync(
  new URL("../src/components/MarkdownEditor.tsx", import.meta.url),
  "utf-8",
);

describe("MarkdownEditor mobile attachments", () => {
  it("gives fullscreen attachment thumbnails and the textarea separate flex space", () => {
    expect(source).toContain("flex h-full min-h-0 flex-col");
    expect(source).toContain("min-h-0 flex-1 resize-none");
  });
});
