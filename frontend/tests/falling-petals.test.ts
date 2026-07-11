import { describe, expect, it } from "vitest";
import { getPetalCount } from "../src/components/FallingPetals";

describe("falling petal density", () => {
  it("keeps the desktop density while using fewer petals on mobile", () => {
    expect(getPetalCount("light", false)).toBe(10);
    expect(getPetalCount("dark", false)).toBe(6);
    expect(getPetalCount("light", true)).toBe(6);
    expect(getPetalCount("dark", true)).toBe(4);
  });
});
