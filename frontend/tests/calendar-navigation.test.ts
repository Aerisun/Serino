import { describe, expect, it } from "vitest";
import { resolveCalendarEventNavigation } from "../src/pages/CalendarPage";

describe("calendar navigation", () => {
  it("blocks diary detail clicks while diary details are private", () => {
    expect(
      resolveCalendarEventNavigation({
        type: "diary",
        href: "/diary/spring-equinox-and-warm-light",
        diaryPrivateEnabled: true,
      }),
    ).toEqual({ kind: "blocked-diary", href: "/diary/spring-equinox-and-warm-light" });
  });

  it("keeps non-diary and public-diary clicks navigable", () => {
    expect(
      resolveCalendarEventNavigation({
        type: "post",
        href: "/posts/dark-mode-design-details",
        diaryPrivateEnabled: true,
      }),
    ).toEqual({ kind: "navigate", href: "/posts/dark-mode-design-details" });

    expect(
      resolveCalendarEventNavigation({
        type: "diary",
        href: "/diary/spring-equinox-and-warm-light",
        diaryPrivateEnabled: false,
      }),
    ).toEqual({ kind: "navigate", href: "/diary/spring-equinox-and-warm-light" });
  });
});
