import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";
import { fileURLToPath } from "node:url";

const commentSectionPath = fileURLToPath(new URL("../src/components/CommentSection.tsx", import.meta.url));
const surfacePath = fileURLToPath(new URL("../src/components/WalineSurface.tsx", import.meta.url));
const surfaceCssPath = fileURLToPath(new URL("../src/components/WalineSurface.css", import.meta.url));
const commentFormPath = fileURLToPath(new URL("../src/components/WalineCommentForm.tsx", import.meta.url));
const walineTypesPath = fileURLToPath(new URL("../src/components/waline-types.tsx", import.meta.url));
const indexCssPath = fileURLToPath(new URL("../src/index.css", import.meta.url));

test("excerpt comment drawer expands its composer naturally before the comment list", async () => {
  const [commentSection, surface, css] = await Promise.all([
    readFile(commentSectionPath, "utf8"),
    readFile(surfacePath, "utf8"),
    readFile(surfaceCssPath, "utf8"),
  ]);

  assert.match(commentSection, /layout\?: "default" \| "modal"/);
  assert.match(commentSection, /layout=\{layout\}/);
  assert.match(surface, /layout = "default"/);
  assert.match(surface, /aerisun-community-surface--modal/);
  assert.match(surface, /aerisun-community-surface__list/);
  assert.match(surface, /aerisun-community-surface__composer/);
  assert.match(surface, /const isComposerPinned = composerOpen;/);
  assert.match(surface, /const shouldShowCommentList = !isModalLayout \|\| !composerOpen;/);
  assert.match(surface, /\{shouldShowCommentList \? commentList : null\}/);
  assert.doesNotMatch(surface, /shouldRenderComposerBeforeList/);
  assert.doesNotMatch(surface, /!isModalLayout \? \(/);
  assert.match(surface, /onReply=\{handleReply\}/);
  assert.match(css, /\.aerisun-community-surface--modal\s*\{[\s\S]*min-height:\s*0/);
  assert.match(css, /\.aerisun-community-surface__composer\s*\{/);
  assert.doesNotMatch(css, /\.aerisun-community-surface--modal \.aerisun-community-surface__composer\s*\{[^}]*background:\s*transparent/);
  assert.match(
    css,
    /@media \(max-width: 639px\) \{[\s\S]*\.aerisun-community-surface--modal \.aerisun-community-surface__composer--open\s*\{[\s\S]*max-height:\s*min\(58dvh, 26rem\);[\s\S]*overflow-y:\s*auto;/,
  );
  assert.match(
    css,
    /\.aerisun-community-surface--modal \.aerisun-community-surface__composer--open \.aerisun-community-textarea\s*\{[\s\S]*min-height:\s*8\.5rem;/,
  );
  assert.match(
    css,
    /\.aerisun-community-surface--modal \.aerisun-community-surface__list:has\(\.aerisun-waline-empty\)\s*\{[\s\S]*overflow-y:\s*visible;/,
  );
  assert.match(
    css,
    /\.aerisun-community-surface--modal \.aerisun-waline-empty\s*\{[\s\S]*min-height:\s*8rem;/,
  );
  assert.match(
    css,
    /@media \(max-width: 639px\) \{[\s\S]*\.aerisun-community-surface--modal \.aerisun-community-surface__composer\s*\{[\s\S]*margin-top:\s*0\.5rem;/,
  );
  assert.match(
    css,
    /@media \(max-width: 639px\) \{[\s\S]*\.aerisun-community-surface--modal \.aerisun-community-surface__list\s*\{[\s\S]*padding-right:\s*1\.25rem;/,
  );
  assert.match(
    css,
    /\.aerisun-community-surface--modal \.aerisun-community-surface__list\s*\{[\s\S]*padding-bottom:\s*calc\(4rem \+ env\(safe-area-inset-bottom\)\);[\s\S]*scroll-padding-bottom:\s*calc\(4rem \+ env\(safe-area-inset-bottom\)\);/,
  );
});


test("comment textarea uses the same understated scrollbar as the detail panels", async () => {
  const [form, types, surfaceCss] = await Promise.all([
    readFile(commentFormPath, "utf8"),
    readFile(walineTypesPath, "utf8"),
    readFile(surfaceCssPath, "utf8"),
  ]);

  assert.match(form, /<textarea[\s\S]*?wrap="soft"/);
  assert.doesNotMatch(types, /communityTextareaClass\s*=\s*[\s\S]*scrollbar-hide/);
  assert.match(types, /communityTextareaClass\s*=\s*[\s\S]*aerisun-detail-scrollbar/);
  assert.match(form, /className=\{emojiPickerOpen \|\| avatarPickerOpen \? "aerisun-comment-form-motion overflow-visible" : "aerisun-comment-form-motion overflow-hidden"\}/);
  assert.match(surfaceCss, /\.aerisun-comment-form-motion:focus-within\s*\{[\s\S]*overflow:\s*visible\s*!important;/);
});

test("comment list stays scrollable without a visible position indicator", async () => {
  const [surface, css] = await Promise.all([
    readFile(surfacePath, "utf8"),
    readFile(surfaceCssPath, "utf8"),
  ]);

  assert.doesNotMatch(surface, /ScrollPositionIndicator/);
  assert.doesNotMatch(surface, /commentListRef/);
  assert.match(surface, /aerisun-community-surface__list scrollbar-hide/);
  assert.match(
    css,
    /\.aerisun-community-surface--modal \.aerisun-community-surface__list\s*\{[\s\S]*max-height:\s*min\(52vh, 28rem\);[\s\S]*overflow-y:\s*auto;/,
  );
  assert.doesNotMatch(css, /aerisun-scroll-position-indicator/);
});

test("last modal comment keeps a desktop clearance above the dialog edge", async () => {
  const css = await readFile(surfaceCssPath, "utf8");

  assert.match(
    css,
    /\.aerisun-community-surface--modal \.aerisun-comment-thread:last-child\s*\{[\s\S]*padding-bottom:\s*1\.5rem;/,
  );
});

test("composer content enters with a short reduced-motion-aware transform", async () => {
  const [form, surface] = await Promise.all([
    readFile(commentFormPath, "utf8"),
    readFile(surfacePath, "utf8"),
  ]);

  assert.match(form, /initial=\{\{ height: 0, opacity: 0, y: prefersReducedMotion \? 0 : 6 \}\}/);
  assert.match(form, /animate=\{\{ height: "auto", opacity: 1, y: 0 \}\}/);
  assert.match(form, /exit=\{\{ height: 0, opacity: 0, y: prefersReducedMotion \? 0 : 6 \}\}/);
  assert.match(form, /duration: 0\.26, reducedMotion: prefersReducedMotion/);
  assert.match(surface, /import \{ motion \} from "motion\/react";/);
  assert.match(surface, /<motion\.button[\s\S]*?whileTap=\{prefersReducedMotion \? undefined : \{ scale: 0\.98 \}\}/);
});
