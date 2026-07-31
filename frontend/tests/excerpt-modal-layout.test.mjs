import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";

const excerptsPagePath = fileURLToPath(new URL("../src/pages/Excerpts.tsx", import.meta.url));
const surfacePath = fileURLToPath(new URL("../src/components/WalineSurface.tsx", import.meta.url));
const indexCssPath = fileURLToPath(new URL("../src/index.css", import.meta.url));

const readExcerptsPage = () => readFile(excerptsPagePath, "utf8");

test("excerpt detail dialog expands comments naturally below the comment control", async () => {
  const source = await readExcerptsPage();

  assert.match(source, /aerisun-excerpt-dialog/);
  assert.match(source, /aerisun-excerpt-dialog[^"\n]*overflow-x-hidden overflow-y-auto/);
  assert.match(source, /aerisun-excerpt-reader/);
  assert.match(source, /aerisun-excerpt-comment-drawer/);
  assert.match(source, /layout="modal"/);
  assert.match(source, /const excerptDialogHeightClass = "max-h-full sm:max-h-\[min\(88vh,calc\(100dvh-6\.5rem\),54rem\)\]"/);
  assert.match(source, /\$\{excerptDialogHeightClass\}/);
  assert.match(source, /flex items-start justify-center px-3 pb-\[max\(0\.75rem,env\(safe-area-inset-bottom\)\)\] pt-\[max\(5rem,calc\(env\(safe-area-inset-top\)\+4rem\)\)\] sm:px-6 sm:pb-6 sm:pt-20/);
  assert.match(source, /showModalComments \? "max-h-\[min\(8vh,5\.5rem\)\] sm:max-h-\[min\(18vh,10\.5rem\)\]" : ""/);
  assert.match(source, /relative flex min-h-0 flex-1 flex-col/);
  assert.match(source, /aerisun-excerpt-reader[^"\n]*min-h-0 flex-1/);
  assert.match(source, /aerisun-excerpt-comment-drawer mt-1 flex min-h-0 flex-col sm:mt-3/);
  assert.doesNotMatch(source, /aerisun-excerpt-comment-drawer[^"\n]*rounded-\[1\.7rem\]/);
  assert.doesNotMatch(source, /aerisun-excerpt-comment-drawer absolute/);
  assert.ok(
    source.indexOf("aria-expanded={showModalComments}") < source.indexOf("aerisun-excerpt-comment-drawer"),
  );
  assert.match(source, /className=\{`flex items-center gap-2 text-\[13px\] font-body transition-colors sm:py-1 sm:text-sm/);
  assert.doesNotMatch(source, /aerisun-excerpt-markdown[^"\n]*whitespace-pre-wrap/);
});

test("excerpt reader keeps its indicator while the comment list stays visually clean", async () => {
  const [excerpts, surface, indexCss] = await Promise.all([
    readFile(excerptsPagePath, "utf8"),
    readFile(surfacePath, "utf8"),
    readFile(indexCssPath, "utf8"),
  ]);

  assert.match(excerpts, /aerisun-excerpt-reader aerisun-detail-scrollbar[^"\n]*overflow-y-auto/);
  assert.match(surface, /aerisun-community-surface__list scrollbar-hide/);
  assert.doesNotMatch(surface, /ScrollPositionIndicator/);
  assert.match(excerpts, /aerisun-excerpt-dialog scrollbar-hide/);
  assert.match(surface, /aerisun-community-surface__composer scrollbar-hide/);
  const desktopScrollbarCss = indexCss.split("@media (hover: hover) and (pointer: fine)")[0];

  assert.doesNotMatch(desktopScrollbarCss, /\.aerisun-detail-scrollbar\s*\{[\s\S]*scrollbar-(?:width|color):/);
  assert.match(indexCss, /\.aerisun-detail-scrollbar::-webkit-scrollbar\s*\{[\s\S]*width:\s*0\.32rem/);
  assert.match(indexCss, /\.aerisun-detail-scrollbar::-webkit-scrollbar-track\s*\{[\s\S]*margin-block:\s*0\.75rem/);
  assert.match(indexCss, /@media \(hover: none\), \(pointer: coarse\)\s*\{[\s\S]*\.aerisun-detail-scrollbar\s*\{[\s\S]*scrollbar-width:\s*none/);
});

test("excerpt comment drawer uses local transform-based layout motion", async () => {
  const source = await readExcerptsPage();

  assert.match(source, /import \{ staggerItem, transition \} from "@\/config";/);
  assert.match(source, /import \{ useReducedMotionPreference \} from "@\/lib\/useReducedMotion";/);
  assert.match(source, /const prefersReducedMotion = useReducedMotionPreference\(\);/);
  assert.match(source, /<motion\.div\s+layoutRoot/);
  assert.match(source, /layoutScroll/);
  assert.match(source, /<motion\.div\s+layout="position"/);
  assert.match(source, /<motion\.button[\s\S]*?whileTap=\{prefersReducedMotion \? undefined : \{ scale: 0\.98 \}\}/);
  assert.match(source, /className="aerisun-excerpt-comment-drawer__content"/);
});
