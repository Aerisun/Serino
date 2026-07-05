import { describe, expect, it } from "vitest";
import type { SystemUpdateStatusRead } from "@serino/api-client/models";
import {
  AUTO_CHECK_STALE_MS,
  shouldQueueSilentUpdateCheck,
} from "../src/pages/dashboard/systemUpdateNoticeLogic";

function status(overrides: Partial<SystemUpdateStatusRead> = {}): SystemUpdateStatusRead {
  return {
    schema_version: 1,
    state: "idle",
    current_version: "0.1.62",
    latest_version: "v0.1.62",
    channel: "dev",
    update_available: false,
    auto_update_supported: false,
    signature_verified: false,
    release: null,
    checked_at: "2026-07-05T10:00:00Z",
    recent_log: [],
    ...overrides,
  };
}

describe("system update notice logic", () => {
  it("queues a silent check when the cached status is stale", () => {
    const now = Date.parse("2026-07-05T10:03:00Z");

    expect(
      shouldQueueSilentUpdateCheck({
        autoCheckPending: false,
        isError: false,
        isStateActive: false,
        lastAutoCheckRequestedAt: now - AUTO_CHECK_STALE_MS,
        now,
        state: "idle",
        status: status(),
      }),
    ).toBe(true);
  });

  it("does not queue another silent check while the cached status is fresh", () => {
    const now = Date.parse("2026-07-05T10:01:00Z");

    expect(
      shouldQueueSilentUpdateCheck({
        autoCheckPending: false,
        isError: false,
        isStateActive: false,
        lastAutoCheckRequestedAt: 0,
        now,
        state: "idle",
        status: status(),
      }),
    ).toBe(false);
  });
});
