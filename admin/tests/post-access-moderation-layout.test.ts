import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const pageSource = readFileSync(
  new URL("../src/pages/moderation/ModerationPage.tsx", import.meta.url),
  "utf-8",
);
const panelSource = readFileSync(
  new URL("../src/pages/moderation/PostAccessRequestsPanel.tsx", import.meta.url),
  "utf-8",
);

describe("post access moderation layout", () => {
  it("shows the independent article-application queue only when its feature is enabled", () => {
    expect(pageSource).toContain('"post-access"');
    expect(pageSource).toContain('t("moderation.postAccessRequests")');
    expect(pageSource).toContain("post_access_approval_enabled");
    expect(pageSource).toContain("<PostAccessRequestsPanel />");
  });

  it("gives article titles room, truncates them, and links them to the public article", () => {
    expect(panelSource).toContain("useSystemInfoApiV1AdminSystemInfoGet");
    expect(panelSource).toContain("resolveFrontendUrl");
    expect(panelSource).toContain("buildPostHref");
    expect(panelSource).toContain('w-[38%] min-w-[20rem]');
    expect(panelSource).toContain("max-w-[38rem]");
    expect(panelSource).toContain("truncate");
    expect(panelSource).toContain('target="_blank"');
    expect(panelSource).not.toContain('<div className="truncate text-xs text-muted-foreground">/{row.postSlug}</div>');
  });
});
