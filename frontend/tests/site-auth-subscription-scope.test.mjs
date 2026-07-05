import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import test from "node:test";

const repoRoot = resolve(import.meta.dirname, "../..");

test("profile subscription management uses current visitor scoped subscriptions", () => {
  const providerSource = readFileSync(
    resolve(repoRoot, "frontend/src/contexts/site-auth.tsx"),
    "utf8",
  );
  const apiSource = readFileSync(
    resolve(repoRoot, "frontend/src/lib/site-auth.ts"),
    "utf8",
  );

  assert.match(providerSource, /readMyManagedContentSubscriptions/);
  assert.match(providerSource, /unsubscribeMyManagedContentSubscription/);
  assert.doesNotMatch(providerSource, /getTrackedSubscriptionEmails/);
  assert.doesNotMatch(providerSource, /replaceTrackedSubscriptionEmails/);
  assert.doesNotMatch(providerSource, /readContentSubscriptionByEmail/);
  assert.doesNotMatch(providerSource, /unsubscribeContentSubscriptionByEmail/);
  assert.match(apiSource, /\/api\/v1\/site\/subscriptions\/mine/);
  assert.match(apiSource, /\/api\/v1\/site\/subscriptions\/mine\/unsubscribe/);
});
