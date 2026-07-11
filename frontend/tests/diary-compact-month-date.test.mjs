import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = readFileSync(resolve(frontendRoot, "src/pages/Diary.tsx"), "utf8");

test("diary list renders a compact English month and date with a centered separator", () => {
  assert.match(source, /const formatCompactDiaryDate =/);
  assert.match(source, /"Jan", "Feb", "Mar", "Apr", "May", "Jun"/);
  assert.match(source, /MONTH_LABELS\[parts\.month - 1\]/);
  assert.match(source, /MONTH_LABELS\[parts\.month - 1\] \+ " · " \+ String\(parts\.day\)/);
  assert.match(source, /String\(parts\.day\)\.padStart\(2, "0"\)/);
  assert.match(source, /compactDate: formatCompactDiaryDate\(entry\.published_at\)/);
  assert.match(source, /formatDateInBeijing\(value, "zh-CN", \{ weekday: "short" \}\)/);
  assert.match(source, /weekday: formatWeekday\(entry\.published_at\)/);
  assert.match(source, /\{entry\.compactDate \|\| "--"\}/);
  assert.match(source, /\{entry\.weekday\}/);
  assert.match(source, /whitespace-nowrap text-base font-body font-medium/);
  assert.match(source, /mt-1 text-\[10px\] font-body text-foreground\/25/);
});
