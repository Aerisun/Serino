import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");
const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

test("rich links render the server-selected media role instead of guessing image ratios", () => {
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const css = readSource("frontend/src/components/markdown.css");
  const richLinkCard = renderer.slice(
    renderer.indexOf("function MarkdownRichLinkCard"),
    renderer.indexOf("function MarkdownImage"),
  );

  assert.match(richLinkCard, /preview\?\.image_mode === "thumbnail"/);
  assert.match(richLinkCard, /has-cover-media/);
  assert.match(richLinkCard, /has-thumbnail-media/);
  assert.doesNotMatch(richLinkCard, /resolveRichLinkMediaVariant/);
  assert.doesNotMatch(richLinkCard, /naturalWidth/);
  assert.match(css, /\.markdown-link-card\.has-cover-media[\s\S]*?grid-template-columns:\s*7\.2rem/);
  assert.match(css, /\.markdown-link-card\.has-thumbnail-media[\s\S]*?grid-template-columns:\s*minmax\(0, 1fr\)\s+4rem\s+auto;/);
  assert.match(css, /\.markdown-link-card-image\s*\{[\s\S]*?max-width:\s*none;[\s\S]*?margin:\s*0;/);
});

test("identity thumbnails use the Shiro-style right-side square slot", () => {
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const adminPreview = readSource("admin/src/components/MarkdownPreview.tsx");
  const css = readSource("frontend/src/components/markdown.css");
  const publicRichLinkCard = renderer.slice(
    renderer.indexOf("function MarkdownRichLinkCard"),
    renderer.indexOf("function MarkdownImage"),
  );
  const adminRichLinkCard = adminPreview.slice(
    adminPreview.indexOf("function MarkdownRichLinkCard"),
    adminPreview.indexOf("function MarkdownAnchor"),
  );

  assert.match(renderer, /preview\?\.card_type/);
  assert.match(adminPreview, /preview\?\.image_mode === "thumbnail"/);
  assert.doesNotMatch(adminPreview, /imageRatio/);
  assert.match(adminPreview, /m-0 h-full w-full max-w-none/);
  assert.match(
    css,
    /\.markdown-link-card\.has-thumbnail-media\s+\.markdown-link-card-media\s*\{[\s\S]*?width:\s*4rem;[\s\S]*?height:\s*4rem;[\s\S]*?border-radius:\s*0\.5rem;/,
  );
  assert.match(css, /\.markdown-link-card\.has-thumbnail-media\s+\.markdown-link-card-image\s*\{[\s\S]*?transform:\s*scale\(1\.22\);/);
  assert.match(
    css,
    /\.markdown-link-card\.has-thumbnail-media\s+\.markdown-link-card-arrow\s*\{[\s\S]*?position:\s*static;/,
  );
  assert.match(publicRichLinkCard, /const isGithubProfile = preview\?\.card_type === "github_profile"/);
  assert.match(publicRichLinkCard, /const showExternalLink = !isGithubProfile/);
  assert.match(publicRichLinkCard, /is-github-profile/);
  assert.match(publicRichLinkCard, /showExternalLink \? \(/);
  assert.match(adminRichLinkCard, /const isGithubProfile = preview\?\.card_type === "github_profile"/);
  assert.match(adminRichLinkCard, /const showExternalLink = !isGithubProfile/);
  assert.match(adminRichLinkCard, /showExternalLink \? \(/);
  assert.match(adminRichLinkCard, /sm:h-20 sm:w-20/);
  assert.match(css, /\.markdown-link-card\.is-github-profile\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0, 1fr\) 5rem;/);
  assert.match(
    css,
    /@media \(max-width: 640px\) \{[\s\S]*?\.markdown-link-card\.is-github-profile\s*\{[\s\S]*?grid-template-columns:\s*minmax\(0, 1fr\) 4rem;/,
  );
  assert.match(
    css,
    /\.markdown-link-card\.is-github-profile\s+\.markdown-link-card-media\s*\{[\s\S]*?width:\s*5rem;[\s\S]*?height:\s*5rem;/,
  );
});

test("rich-link image failures retain the existing fallback behavior", () => {
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");

  assert.match(renderer, /if \(imageState === "primary" && fallbackImageUrl\)/);
  assert.match(renderer, /setImageState\("fallback"\)/);
  assert.match(renderer, /setImageState\("hidden"\)/);
});
