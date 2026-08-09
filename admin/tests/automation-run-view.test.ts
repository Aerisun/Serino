import { describe, expect, it } from "vitest";
import {
  formatAutomationDuration,
  getAutomationRunItems,
  summarizeAutomationOverview,
} from "../src/pages/automation/automation-run-view";

describe("automation run view helpers", () => {
  it("reads the generated cursor collection without treating it as an array", () => {
    const run = { id: "run-1" } as never;

    expect(getAutomationRunItems({ items: [run], total: 1 })).toEqual([run]);
    expect(getAutomationRunItems(undefined)).toEqual([]);
  });

  it("summarizes live and attention counts from the overview", () => {
    expect(
      summarizeAutomationOverview({
        queued_run_count: 2,
        running_run_count: 3,
        awaiting_approval_count: 4,
        pending_approval_count: 5,
        total_run_count: 12,
        recent_failed_run_count: 1,
        generated_at: "2026-08-09T00:00:00+08:00",
      }),
    ).toEqual({ active: 9, approvals: 5, runs: 12, failed: 1 });
  });

  it("formats durations compactly for operators", () => {
    expect(formatAutomationDuration(null, "zh")).toBe("-");
    expect(formatAutomationDuration(820, "zh")).toBe("820 毫秒");
    expect(formatAutomationDuration(1_540, "en")).toBe("1.5 s");
    expect(formatAutomationDuration(65_000, "zh")).toBe("1 分 5 秒");
  });
});
