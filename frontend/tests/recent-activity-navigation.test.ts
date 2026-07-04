import { describe, expect, it } from "vitest";
import { normalizeActivity, resolveRecentActivityNavigation } from "../src/components/RecentActivity";

const t = (key: string, _values?: Record<string, string | number>, fallback?: string) => fallback ?? key;

describe("recent activity navigation", () => {
  it("keeps diary publish titles and summaries visible in the timeline", () => {
    const item = normalizeActivity(
      {
        kind: "publish_diary",
        actor_name: "Aerisun",
        actor_avatar: "",
        target_title: "春分，天气转暖",
        excerpt: "阳光从窗帘缝隙里漏进来，整个房间都有一点松动感。",
        created_at: "2026-03-21T12:00:00+08:00",
        href: "/diary/spring-equinox-and-warm-light",
      },
      t,
      "zh",
    );

    expect(item.type).toBe("publish_diary");
    expect(item.target).toBe("春分，天气转暖");
    expect(item.detail).toBe("阳光从窗帘缝隙里漏进来，整个房间都有一点松动感。");
  });

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
