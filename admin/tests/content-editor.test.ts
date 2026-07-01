import { describe, expect, it } from "vitest";
import {
  applySynchronizedStateUpdate,
  normalizeServerTextField,
} from "../src/lib/content-editor";

describe("applySynchronizedStateUpdate", () => {
  it("updates the mutable ref immediately so save handlers read the latest select values", () => {
    const formRef = {
      current: {
        mood: "",
        weather: "",
      },
    };

    const withMood = applySynchronizedStateUpdate(formRef, (previous) => ({
      ...previous,
      mood: "calm",
    }));
    const withWeather = applySynchronizedStateUpdate(formRef, (previous) => ({
      ...previous,
      weather: "overcast",
    }));

    expect(withMood.mood).toBe("calm");
    expect(withWeather).toEqual({
      mood: "calm",
      weather: "overcast",
    });
    expect(formRef.current).toBe(withWeather);
  });
});

describe("normalizeServerTextField", () => {
  it("preserves saved diary mood and overcast weather values from admin read responses", () => {
    expect(normalizeServerTextField("calm")).toBe("calm");
    expect(normalizeServerTextField("overcast")).toBe("overcast");
  });

  it("normalizes missing or non-string response values to an empty form value", () => {
    expect(normalizeServerTextField(null)).toBe("");
    expect(normalizeServerTextField(undefined)).toBe("");
    expect(normalizeServerTextField({ value: "overcast" })).toBe("");
  });
});
