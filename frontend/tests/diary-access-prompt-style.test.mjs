import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");

const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

test("diary login-required prompt is a red warning with a centered login action", () => {
  const prompt = readSource("frontend/src/components/DiaryAccessPrompt.tsx");
  const translations = readSource("frontend/src/i18n/translations.ts");

  assert.match(translations, /"diaryAccess\.loginRequired":\s*"请先登录，检查权限以查看日记"/);
  assert.match(prompt, /ACTION_TOAST_DURATION_MS = 2000/);
  assert.match(prompt, /actionLabel \? ACTION_TOAST_DURATION_MS : PASSIVE_TOAST_DURATION_MS/);
  assert.match(prompt, /isPostAccess \? "postAccess" : "diaryAccess"/);
  assert.match(prompt, /pushToast\(\s*"error",\s*t\(accessKey\("loginRequired"\)\),\s*t\("navbar\.login"\),\s*"login"\s*\)/);
  assert.match(prompt, /toast\.actionType === "login"/);
  assert.match(prompt, /className=\{`mx-auto mt-2 flex items-center/);
});

test("diary access warning toast keeps extra breathing room on the right", () => {
  const prompt = readSource("frontend/src/components/DiaryAccessPrompt.tsx");

  assert.match(prompt, /pl-4 pr-7/);
  assert.match(prompt, /max-w-\[min\(72vw,24rem\)\]/);
});

test("blocked diary detail page uses neutral treatment and a centered single action", () => {
  const detail = readSource("frontend/src/pages/DiaryDetail.tsx");

  assert.match(detail, /accessErrorStatus === 401\s*\?\s*t\("diaryAccess\.loginRequired"\)/);
  assert.match(detail, /liquid-glass/);
  assert.doesNotMatch(detail, /border-\[rgba\(225,29,72,0\.42\)\]/);
  assert.doesNotMatch(detail, /bg-rose-100/);
  assert.doesNotMatch(detail, /t\("diaryAccess\.backToList"\)/);
  assert.doesNotMatch(detail, /showBlockedFromError/);
  assert.match(detail, /accessErrorStatus === 401 \? openLoginDialog : openRequestDialog/);
  assert.match(detail, /accessErrorStatus === 401 \? t\("navbar\.login"\) : t\("diaryAccess\.apply"\)/);
});

test("diary list detail action is not nested inside the expandable row button", () => {
  const diary = readSource("frontend/src/pages/Diary.tsx");

  assert.doesNotMatch(diary, /<button(?=[^>]*className="w-full text-left")[^>]*>/);
  assert.match(diary, /role="button"/);
  assert.match(diary, /onKeyDown=\{\(event\) => handleEntryKeyDown\(event, isExpanded, entry\.id\)\}/);
});

test("account menu shows granted diary access remaining time above edit profile", () => {
  const navbar = readSource("frontend/src/components/Navbar.tsx");
  const translations = readSource("frontend/src/i18n/translations.ts");

  assert.match(navbar, /readMyDiaryAccessApiV1SiteDiaryAccessMeGet/);
  assert.match(navbar, /enabled:\s*Boolean\(user && authMenuOpen\)/);
  assert.match(navbar, /diaryAccessState\?\.has_access/);
  assert.match(navbar, /t\("navbar\.diaryAccessPermission"\)/);
  assert.match(navbar, /t\("navbar\.diaryAccessRemaining"/);
  assert.match(navbar, /border-\[rgb\(var\(--shiro-accent-rgb\)\/0\.32\)\]/);
  assert.match(navbar, /bg-\[linear-gradient\(135deg,rgb\(var\(--shiro-accent-rgb\)\/0\.18\),rgb\(255_255_255\/0\.08\)\)\]/);
  assert.match(navbar, /shadow-\[inset_0_1px_0_rgb\(255_255_255\/0\.18\),0_12px_30px_rgb\(var\(--shiro-accent-rgb\)\/0\.12\)\]/);
  assert.doesNotMatch(navbar, /Clock3/);
  assert.ok(
    navbar.indexOf('t("navbar.diaryAccessPermission")') < navbar.indexOf('t("navbar.editProfile")'),
    "diary access status should render above edit profile",
  );
  assert.match(translations, /"navbar\.diaryAccessPermission":\s*"拥有查看日记权限"/);
  assert.match(translations, /"navbar\.diaryAccessRemaining":\s*"剩余时间：\{time\}"/);
});
