import { describe, expect, it } from "vitest";
import { formatContentRelativeDate, formatRelativeUpdatedAt } from "../src/lib/api/utils";

const zh = (key: string, values?: Record<string, string | number>, fallback?: string) => {
  const count = values?.count;
  const translations: Record<string, string> = {
    "recentActivity.justNow": "刚刚",
    "recentActivity.minutesAgo": `${count} 分钟前`,
    "recentActivity.hoursAgo": `${count} 小时前`,
    "recentActivity.yesterday": "昨天",
    "recentActivity.dayBeforeYesterday": "前天",
    "recentActivity.daysAgo": `${count} 天前`,
  };
  return translations[key] ?? fallback ?? key;
};

describe("content relative date", () => {
  const now = new Date("2026-07-05T20:00:00+08:00").getTime();

  it("formats from published_at instead of trusting a stale relative_date", () => {
    expect(
      formatContentRelativeDate(
        {
          published_at: "2026-07-05T01:00:00+08:00",
          relative_date: "1 分钟前",
        },
        zh,
        "zh",
        now,
      ),
    ).toBe("19 小时前");
  });

  it("formats from published_at instead of the last updated time", () => {
    expect(
      formatContentRelativeDate(
        {
          published_at: "2026-07-05T01:00:00+08:00",
          updated_at: "2026-07-05T19:59:00+08:00",
          relative_date: "1 分钟前",
        },
        zh,
        "zh",
        now,
      ),
    ).toBe("19 小时前");
  });

  it("keeps minute-level labels for fresh thoughts", () => {
    expect(
      formatContentRelativeDate(
        { published_at: "2026-07-05T19:58:00+08:00" },
        zh,
        "zh",
        now,
      ),
    ).toBe("2 分钟前");
  });

  it("falls back to created_at when published_at is missing", () => {
    expect(
      formatContentRelativeDate(
        { created_at: "2026-07-04T20:00:00+08:00" },
        zh,
        "zh",
        now,
      ),
    ).toBe("昨天");
  });

  it("uses Beijing calendar days for yesterday even when less than 24 hours passed", () => {
    const afterMidnight = new Date("2026-07-05T00:30:00+08:00").getTime();

    expect(
      formatContentRelativeDate(
        { published_at: "2026-07-04T23:30:00+08:00" },
        zh,
        "zh",
        afterMidnight,
      ),
    ).toBe("昨天");
  });

  it("uses Beijing calendar days for the day before yesterday", () => {
    const afterMidnight = new Date("2026-07-05T00:30:00+08:00").getTime();

    expect(
      formatContentRelativeDate(
        { published_at: "2026-07-03T23:30:00+08:00" },
        zh,
        "zh",
        afterMidnight,
      ),
    ).toBe("前天");
  });
});

describe("content updated relative date", () => {
  const now = new Date("2026-07-12T12:00:00+08:00").getTime();

  it("uses seconds and minutes before switching to hours", () => {
    expect(formatRelativeUpdatedAt(now - 20 * 1000, now)).toBe("20 秒");
    expect(formatRelativeUpdatedAt(now - 20 * 60 * 1000, now)).toBe("20 分钟");
  });

  it("uses Chinese hour labels within 24 hours", () => {
    expect(formatRelativeUpdatedAt(now - 2 * 60 * 60 * 1000, now)).toBe("2 小时");
  });

  it("uses yesterday, the day before yesterday, and elapsed days through three months", () => {
    expect(formatRelativeUpdatedAt(now - 24 * 60 * 60 * 1000, now)).toBe("昨天");
    expect(formatRelativeUpdatedAt(now - 2 * 24 * 60 * 60 * 1000, now)).toBe("前天");
    expect(formatRelativeUpdatedAt(now - 12 * 24 * 60 * 60 * 1000, now)).toBe("12 天");
  });

  it("uses months after three months and years after one year", () => {
    expect(formatRelativeUpdatedAt(now - 90 * 24 * 60 * 60 * 1000, now)).toBe("3 个月");
    expect(formatRelativeUpdatedAt(now - 365 * 24 * 60 * 60 * 1000, now)).toBe("1 年");
  });

  it("hides future and non-finite timestamps instead of misreporting them as past updates", () => {
    expect(formatRelativeUpdatedAt(now + 60 * 60 * 1000, now)).toBe("");
    expect(formatRelativeUpdatedAt(Number.POSITIVE_INFINITY, now)).toBe("");
  });

  it("keeps the Unix epoch as a valid timestamp", () => {
    expect(formatRelativeUpdatedAt(0, now)).not.toBe("--");
  });
});
