import fs from "node:fs";
import { describe, expect, it } from "vitest";

const source = (relativePath: string) =>
  fs.readFileSync(new URL(`../src/${relativePath}`, import.meta.url), "utf-8");

describe("visitor-scoped subscription management", () => {
  it("keeps profile management on current-visitor endpoints", () => {
    const provider = source("contexts/site-auth.tsx");
    const api = source("lib/site-auth.ts");

    expect(provider).toContain("readMyManagedContentSubscriptions");
    expect(provider).toContain("unsubscribeMyManagedContentSubscription");
    expect(provider).not.toContain("getTrackedSubscriptionEmails");
    expect(provider).not.toContain("replaceTrackedSubscriptionEmails");
    expect(provider).not.toContain("readContentSubscriptionByEmail");
    expect(provider).not.toContain("unsubscribeContentSubscriptionByEmail");
    expect(api).toContain('"/api/v1/site/subscriptions/mine"');
    expect(api).toContain('"/api/v1/site/subscriptions/mine/unsubscribe"');
  });
});
