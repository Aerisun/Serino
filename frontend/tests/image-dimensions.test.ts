import { describe, expect, it } from "vitest";

import { isSquareImage } from "@serino/utils/image-dimensions";

describe("isSquareImage", () => {
  it("keeps square images intact", () => {
    expect(isSquareImage(512, 512)).toBe(true);
  });

  it("marks landscape and portrait images for thumbnail cropping", () => {
    expect(isSquareImage(1200, 630)).toBe(false);
    expect(isSquareImage(630, 1200)).toBe(false);
  });
});
