import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(frontendRoot, "src/components/CategoryFilter.tsx"), "utf8");

test("shared category filter owns the measured two-line category bar", () => {
  assert.match(source, /export function CategoryFilter/);
  assert.match(source, /from "@\/lib\/category-filter"/);
  assert.match(source, /ResizeObserver/);
  assert.match(source, /getCategoryFilterLayout/);
  assert.match(source, /Math\.max\(0, measureContainer\.clientWidth - 24\)/);
  assert.match(
    source,
    /secondRowOffset:\s*measuredLayout\.secondRowCount > 0 \|\| measuredLayout\.showMore\s*\?\s*measuredLayout\.secondRowOffset \+ 24/,
  );
  assert.match(source, /sm:w-\[10\.5rem\] sm:shrink-0/);
  assert.match(source, /sm:gap-8/);
  assert.match(source, /min-w-0/);
  assert.match(source, /data-category-filter-measure/);
  assert.match(source, /justify-start gap-1\.5 sm:flex-nowrap sm:justify-end/);
  assert.match(source, /sm:flex-nowrap sm:ms-\[var\(--category-second-row-offset\)\]/);
  assert.match(source, /entry\.key === activeCategory \? "px-4" : "px-2"/);
  assert.match(source, /\[activeCategory, entries, moreLabel\]/);
  assert.match(source, /"--category-second-row-offset": `\$\{layout\.secondRowOffset\}px`/);
  assert.match(source, /rounded-full/);
  assert.match(source, /sm:max-w-\[10rem\]/);
  assert.match(source, /rounded-2xl/);
  assert.match(source, /underline underline-offset-4/);
  assert.match(source, /ml-2 inline-flex h-9.*underline underline-offset-4/);
  assert.doesNotMatch(source, /ChevronDown/);
  assert.match(source, /sm:items-center/);
  assert.match(source, /sm:absolute sm:inset-x-0 sm:top-1\/2 sm:-translate-y-1\/2/);
});

test("shared category filter provides an accessible complete-category dialog", () => {
  assert.match(source, /role="dialog"/);
  assert.match(source, /aria-modal="true"/);
  assert.match(source, /categories\.more/);
  assert.match(source, /categories\.dialogTitle/);
  assert.match(source, /const baseEntries = useMemo/);
  assert.match(source, /baseEntries\.map\(\(entry\) =>/);
  assert.match(source, /onKeyDown/);
  assert.match(source, /moreButtonRef\.current\?\.focus\(\)/);
  assert.match(source, /text-right tabular-nums/);
  assert.doesNotMatch(source, /CARD_COLOR_CLASSES/);
  assert.match(source, /liquid-glass/);
  assert.match(source, /CATEGORY_TINT_HUES/);
  assert.match(source, /getCategoryColorIndex/);
  assert.match(source, /max-h-\[min\(78dvh,34rem\)\].*sm:max-h-\[min\(80dvh,42rem\)\]/);
  assert.match(source, /w-\[88vw\] max-w-\[26rem\] sm:w-full sm:max-w-xl/);
  assert.match(source, /flex-col overflow-hidden/);
  assert.match(source, /min-h-0 flex-1 overflow-y-auto overscroll-contain/);
  assert.match(source, /overflow-y-auto overscroll-contain scrollbar-hide/);
  assert.match(source, /grid grid-cols-1 gap-2 sm:grid-cols-2 sm:gap-2\.5/);
  assert.match(source, /min-h-12.*sm:min-h-14/);
  assert.doesNotMatch(source, /bg-white\/\[0\.88\]/);
  assert.match(source, /#007AFF/);
  assert.match(source, /bg-\[#007AFF\] text-white/);
  assert.match(source, /focus-visible:ring-\[#0A84FF\]\/25/);
});
