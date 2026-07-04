import { describe, expect, it } from "vitest";
import { resolveRecentActivityNavigation } from "../src/components/RecentActivity";

describe("recent activity navigation", () => {
  it("blocks diary detail clicks while diary details are private", () => {
    expect(
      resolveRecentActivityNavigation({
        type: "publish_diary",
        href: "/diary/spring-equinox-and-warm-light",
        diaryPrivateEnabled: true,
      }),
    ).toEqual({ kind: "blocked-diary", href: "/diary/spring-equinox-and-warm-light" });
  });

  it("blocks diary comment and like activity clicks while diary details are private", () => {
    expect(
      resolveRecentActivityNavigation({
        type: "comment",
        href: "/diary/spring-equinox-and-warm-light#comments",
        diaryPrivateEnabled: true,
      }),
    ).toEqual({ kind: "blocked-diary", href: "/diary/spring-equinox-and-warm-light#comments" });

    expect(
      resolveRecentActivityNavigation({
        type: "like",
        href: "/diary/spring-equinox-and-warm-light",
        diaryPrivateEnabled: true,
      }),
    ).toEqual({ kind: "blocked-diary", href: "/diary/spring-equinox-and-warm-light" });
  });

  it("keeps non-diary and public-diary clicks navigable", () => {
    expect(
      resolveRecentActivityNavigation({
        type: "publish_post",
        href: "/posts/dark-mode-design-details",
        diaryPrivateEnabled: true,
      }),
    ).toEqual({ kind: "navigate", href: "/posts/dark-mode-design-details" });

    expect(
      resolveRecentActivityNavigation({
        type: "publish_diary",
        href: "/diary/spring-equinox-and-warm-light",
        diaryPrivateEnabled: false,
      }),
    ).toEqual({ kind: "navigate", href: "/diary/spring-equinox-and-warm-light" });
  });
});
