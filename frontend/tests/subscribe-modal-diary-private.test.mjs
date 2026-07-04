import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");

const subscribeModal = readFileSync(
  resolve(repoRoot, "frontend/src/components/SubscribeModal.tsx"),
  "utf8",
);

test("private diary subscription follows access state while RSS hides diary", () => {
  assert.doesNotMatch(subscribeModal, /CONTENT_OPTIONS\.filter\(\(item\) => item\.key !== "diary"/);
  assert.match(subscribeModal, /useReadMyDiaryAccessApiV1SiteDiaryAccessMeGet/);
  assert.match(subscribeModal, /enabled: open && diaryPrivateEnabled/);
  assert.match(subscribeModal, /diaryAccessAllowed = !diaryPrivateEnabled \|\| Boolean\(diaryAccessResponse\?\.data\?\.has_access\)/);
  assert.match(subscribeModal, /const contentOptions = useMemo\(\s*\(\) => CONTENT_OPTIONS/);
  assert.match(subscribeModal, /const isDiaryDisabled = useCallback\([\s\S]*\(key: ContentType\) => diaryPrivateEnabled && !diaryAccessAllowed && key === "diary"/);
  assert.match(subscribeModal, /availableContentOptions = useMemo\([\s\S]*contentOptions\.filter\(\(item\) => !isDiaryDisabled\(item\.key\)\)/);
  assert.match(subscribeModal, /\.filter\(\(item\) => item\.key !== "diary" \|\| !diaryPrivateEnabled\)/);
  assert.match(subscribeModal, /disabled=\{!enabled \|\| submitting \|\| disabled\}/);
  assert.match(subscribeModal, /aria-disabled=\{disabled\}/);
});
