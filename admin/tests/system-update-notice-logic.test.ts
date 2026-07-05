import { describe, expect, it } from "vitest";
import type { SystemUpdateStatusRead } from "@serino/api-client/models";
import {
  AUTO_CHECK_STALE_MS,
  shouldShowUpdateReleaseNotes,
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

  it("hides GitHub release 404 JSON from dev channel update notes", () => {
    expect(
      shouldShowUpdateReleaseNotes(
        status({
          auto_update_supported: true,
          channel: "dev",
          release: {
            version: "v0.1.64",
            notes:
              '{"message":"Not Found","documentation_url":"https://docs.github.com/rest/releases/releases#get-a-release-by-tag-name","status":"404"}',
            notes_format: "markdown",
          },
        }),
      ),
    ).toBe(false);
  });

  it("hides generated empty release notes for dev channel tag-only builds", () => {
    expect(
      shouldShowUpdateReleaseNotes(
        status({
          auto_update_supported: true,
          channel: "dev",
          release: {
            version: "v0.1.64",
            notes: "# Serino v0.1.64\n\n- 发布版本：v0.1.64\n- 镜像版本：0.1.64\n\n本版本未提供额外更新说明。\n",
            notes_format: "markdown",
          },
        }),
      ),
    ).toBe(false);
  });
});
