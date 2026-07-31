import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const promptSource = readFileSync(
  new URL("../src/components/DiaryAccessPrompt.tsx", import.meta.url),
  "utf8",
);
const detailSource = readFileSync(new URL("../src/pages/PostDetail.tsx", import.meta.url), "utf8");
const translationsSource = readFileSync(new URL("../src/i18n/translations.ts", import.meta.url), "utf8");

test("post access prompt uses independent APIs and a blue article application dialog", () => {
  assert.match(promptSource, /createPostAccessRequestApiV1SitePostAccessSlugRequestsPost/);
  assert.match(promptSource, /getReadMyPostAccessApiV1SitePostAccessSlugMeGetQueryKey/);
  assert.match(promptSource, /border-sky-400\/42/);
  assert.match(detailSource, /post_access_approval_enabled/);
  assert.match(detailSource, /t\("postAccess\.privateTitle"\)/);
  assert.match(detailSource, /t\("postAccess\.loginTitle"\)/);
  assert.match(detailSource, /accessErrorStatus !== 401/);
  assert.match(translationsSource, /"postAccess\.loginTitle": "请先登录来查看这篇文章"/);
  assert.match(translationsSource, /"postAccess\.privateTitle": "您可以申请查看这篇文章"/);
  assert.match(translationsSource, /"postAccess\.privateDescription": "站长一般都会同意的~"/);
});
