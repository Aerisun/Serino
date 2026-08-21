import { describe, expect, it } from "vitest";
import {
  getVerticalWheelDelta,
  shouldCaptureWheelScroll,
} from "../src/hooks/use-contained-wheel-scroll";

describe("contained wheel scrolling", () => {
  it("captures vertical wheel movement while the list can continue", () => {
    expect(
      shouldCaptureWheelScroll({
        scrollTop: 40,
        clientHeight: 100,
        scrollHeight: 300,
        deltaY: 24,
      }),
    ).toBe(true);
  });

  it("releases vertical wheel movement at the bottom boundary", () => {
    expect(
      shouldCaptureWheelScroll({
        scrollTop: 200,
        clientHeight: 100,
        scrollHeight: 300,
        deltaY: 24,
      }),
    ).toBe(false);
  });

  it("releases vertical wheel movement when the list has no overflow", () => {
    expect(
      shouldCaptureWheelScroll({
        scrollTop: 0,
        clientHeight: 300,
        scrollHeight: 300,
        deltaY: 24,
      }),
    ).toBe(false);
  });

  it("ignores horizontal-first wheel gestures", () => {
    expect(
      getVerticalWheelDelta({
        deltaX: 24,
        deltaY: 8,
        deltaMode: 0,
        pageSize: 600,
      }),
    ).toBe(0);
  });

  it("converts line-mode wheel deltas to pixels", () => {
    expect(
      getVerticalWheelDelta({
        deltaX: 0,
        deltaY: 2,
        deltaMode: 1,
        pageSize: 600,
      }),
    ).toBe(32);
  });
});
