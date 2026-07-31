import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";

const navbarSource = readFileSync(new URL("../src/components/Navbar.tsx", import.meta.url), "utf8");
const translationsSource = readFileSync(new URL("../src/i18n/translations.ts", import.meta.url), "utf8");

test("post access card only exposes granted articles in a scrollable new-tab dialog", () => {
  assert.match(navbarSource, /listMyPostAccessApiV1SitePostAccessMeGet/);
  assert.match(navbarSource, /postAccessItems\.length > 0/);
  assert.match(navbarSource, /postAccessDialogOpen/);
  assert.match(navbarSource, /target="_blank"/);
  assert.match(navbarSource, /max-h-\[60vh\] overflow-y-auto/);
  assert.match(translationsSource, /"navbar\.postAccessPermission": "拥有文章查看权限"/);
});
