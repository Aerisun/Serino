export interface CategoryStat {
  name: string;
  count: number;
}

export interface CategoryFilterEntry {
  key: string | null;
  label: string;
  count: number;
}

export interface CategoryFilterLayout {
  firstRowCount: number;
  secondRowCount: number;
  secondRowOffset: number;
  showMore: boolean;
}

export const CATEGORY_COLOR_COUNT = 24;

export function buildCategoryFilterEntries(
  allLabel: string,
  total: number,
  categories: CategoryStat[],
  promotedCategory: string | null,
): CategoryFilterEntry[] {
  const sorted = [...categories]
    .filter((category) => category.name.trim() && category.count >= 0)
    .sort((left, right) => right.count - left.count || left.name.localeCompare(right.name, "zh-CN"));
  const promoted = promotedCategory
    ? sorted.find((category) => category.name === promotedCategory)
    : undefined;
  const remaining = promoted
    ? sorted.filter((category) => category.name !== promoted.name)
    : sorted;

  return [
    { key: null, label: allLabel, count: total },
    ...(promoted ? [promoted] : []),
    ...remaining,
  ].map((category) => ({
    key: "name" in category ? category.name : category.key,
    label: "name" in category ? category.name : category.label,
    count: category.count,
  }));
}

export function getCategoryPromotion(
  category: string | null,
  visibleCategoryKeys: Array<string | null>,
): string | null {
  if (!category || visibleCategoryKeys.includes(category)) {
    return null;
  }
  return category;
}

export function getCategoryFilterLayout(
  entries: Array<{ width: number }>,
  containerWidth: number,
  moreWidth: number,
  gap: number,
): CategoryFilterLayout {
  if (entries.length === 0 || containerWidth <= 0) {
    return { firstRowCount: 0, secondRowCount: 0, secondRowOffset: 0, showMore: false };
  }

  const rowWidth = (items: Array<{ width: number }>) =>
    items.reduce((total, item, index) => total + item.width + (index === 0 ? 0 : gap), 0);
  let firstRowCount = 0;
  for (let candidateCount = 1; candidateCount <= entries.length; candidateCount += 1) {
    const candidate = entries.slice(0, firstRowCount + 1);
    if (rowWidth(candidate) > containerWidth) {
      break;
    }
    firstRowCount += 1;
  }
  firstRowCount = Math.max(1, firstRowCount);

  const remaining = entries.slice(firstRowCount);
  if (remaining.length === 0) {
    return { firstRowCount, secondRowCount: 0, secondRowOffset: 0, showMore: false };
  }
  const firstRowWidth = rowWidth(entries.slice(0, firstRowCount));
  const secondRowOffset = Math.max(0, containerWidth - firstRowWidth);
  let secondRowCount = 0;
  for (let candidateCount = 1; candidateCount <= remaining.length; candidateCount += 1) {
    const candidate = remaining.slice(0, secondRowCount + 1);
    const widthWithMore = rowWidth([...candidate, { width: moreWidth }]);
    if (widthWithMore > firstRowWidth) {
      break;
    }
    secondRowCount += 1;
  }

  return { firstRowCount, secondRowCount, secondRowOffset, showMore: true };
}

export function getCategoryColorIndex(category: string): number {
  let hash = 0;
  for (let index = 0; index < category.length; index += 1) {
    hash = (hash * 31 + category.charCodeAt(index)) >>> 0;
  }
  return hash % CATEGORY_COLOR_COUNT;
}
