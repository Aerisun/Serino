import { describe, expect, it } from "vitest";
import {
  buildCategoryFilterEntries,
  CATEGORY_COLOR_COUNT,
  getCategoryFilterLayout,
  getCategoryColorIndex,
  getCategoryPromotion,
} from "@/lib/category-filter";

describe("category filter ordering", () => {
  const stats = [
    { name: "技术", count: 3 },
    { name: "设计", count: 4 },
    { name: "随想", count: 3 },
  ];

  it("sorts categories by complete count after the all entry", () => {
    expect(buildCategoryFilterEntries("全部", 10, stats, null)).toEqual([
      { key: null, label: "全部", count: 10 },
      { key: "设计", label: "设计", count: 4 },
      { key: "技术", label: "技术", count: 3 },
      { key: "随想", label: "随想", count: 3 },
    ]);
  });

  it("temporarily puts only a promoted category immediately after all", () => {
    expect(buildCategoryFilterEntries("全部", 10, stats, "随想").map((entry) => entry.key)).toEqual([
      null,
      "随想",
      "设计",
      "技术",
    ]);
  });

  it("keeps the count order when selecting a category that is already visible", () => {
    expect(buildCategoryFilterEntries("全部", 10, stats, null).map((entry) => entry.key)).toEqual([
      null,
      "设计",
      "技术",
      "随想",
    ]);
  });

  it("only promotes a category that was hidden behind more", () => {
    expect(getCategoryPromotion("技术", [null, "设计", "技术"])).toBeNull();
    expect(getCategoryPromotion("随想", [null, "设计", "技术"])).toBe("随想");
  });

  it("keeps each category tint stable when the selected order changes", () => {
    expect(getCategoryColorIndex("技术")).toBe(getCategoryColorIndex("技术"));
    expect(getCategoryColorIndex("技术")).not.toBe(getCategoryColorIndex("设计"));
  });

  it("gives the current category set distinct tint indexes", () => {
    const names = ["全部", "技术", "11111111111111", "1241241", "125125125", "23123123", "33333333333333", "41241254125", "设计", "随想"];
    expect(CATEGORY_COLOR_COUNT).toBe(24);
    expect(new Set(names.map(getCategoryColorIndex))).toHaveLength(names.length);
  });

});

describe("category filter two-row overflow", () => {
  it("keeps a single category row right-aligned until it needs a second row", () => {
    expect(
      getCategoryFilterLayout(
        [{ width: 54 }, { width: 70 }, { width: 68 }],
        260,
        58,
        6,
      ),
    ).toEqual({ firstRowCount: 3, secondRowCount: 0, secondRowOffset: 0, showMore: false });
  });

  it("reserves the final second-row position for more once categories need two rows", () => {
    expect(
      getCategoryFilterLayout(
        [{ width: 70 }, { width: 70 }, { width: 70 }, { width: 70 }],
        180,
        58,
        6,
      ),
    ).toEqual({
      firstRowCount: 2,
      secondRowCount: 1,
      secondRowOffset: 34,
      showMore: true,
    });
  });

  it("reserves the final second-row position for more only after two rows overflow", () => {
    expect(
      getCategoryFilterLayout(
        [{ width: 70 }, { width: 70 }, { width: 70 }, { width: 70 }, { width: 70 }],
        180,
        58,
        6,
      ),
    ).toEqual({
      firstRowCount: 2,
      secondRowCount: 1,
      secondRowOffset: 34,
      showMore: true,
    });
  });

  it("uses the all-aligned second-row width when deciding whether more is needed", () => {
    expect(
      getCategoryFilterLayout(
        [{ width: 60 }, { width: 60 }, { width: 120 }, { width: 60 }],
        200,
        40,
        6,
      ),
    ).toEqual({
      firstRowCount: 2,
      secondRowCount: 0,
      secondRowOffset: 74,
      showMore: true,
    });
  });
});
