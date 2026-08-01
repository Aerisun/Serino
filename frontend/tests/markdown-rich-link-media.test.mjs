import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");
const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");
const readCssRules = (source, selector) => {
  const needle = `${selector} {`;
  const rules = [];
  let cursor = 0;

  while (cursor < source.length) {
    const start = source.indexOf(needle, cursor);
    if (start === -1) break;
    const end = source.indexOf("}", start + needle.length);
    if (end === -1) break;
    rules.push(source.slice(start, end + 1));
    cursor = end + 1;
  }

  return rules.join("\n");
};

test("rich links keep server-selected roles inside a unified square media layout", () => {
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
  assert.match(richLinkCard, /naturalWidth/);
  assert.match(richLinkCard, /naturalHeight/);
  assert.match(
    readCssRules(css, ".prose .markdown-link-card.has-cover-media"),
    /grid-template-columns:\s*5rem\s+minmax\(0, 1fr\);/,
  );
  assert.match(
    readCssRules(css, ".prose .markdown-link-card.has-cover-media .markdown-link-card-media"),
    /width:\s*5rem;[\s\S]*?height:\s*5rem;[\s\S]*?aspect-ratio:\s*1;/,
  );
  assert.match(
    readCssRules(css, ".prose .markdown-link-card.has-thumbnail-media"),
    /grid-template-columns:\s*5rem\s+minmax\(0, 1fr\);/,
  );
  assert.match(
    readCssRules(css, ".prose .markdown-link-card-image"),
    /max-width:\s*none;[\s\S]*?margin:\s*0;[\s\S]*?object-fit:\s*contain;/,
  );
  assert.match(
    readCssRules(css, ".prose .markdown-link-card-image.is-thumbnail-crop"),
    /object-fit:\s*cover;/,
  );
});

test("all rich-link images use a complete left-side media slot", () => {
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
  assert.doesNotMatch(adminPreview, /imageRatio/);
  assert.match(adminRichLinkCard, /const hasMediaImage = Boolean\(imageUrl\)/);
  assert.match(adminRichLinkCard, /naturalWidth/);
  assert.match(adminRichLinkCard, /naturalHeight/);
  assert.match(adminRichLinkCard, /const isNonSquareImage = thumbnailCropImageUrl === imageUrl/);
  assert.match(adminRichLinkCard, /isNonSquareImage \? "object-cover" : "object-contain"/);
  assert.doesNotMatch(adminRichLinkCard, /scale-\[1\.22\]/);
  assert.match(
    readCssRules(css, ".prose .markdown-link-card.has-thumbnail-media .markdown-link-card-media"),
    /grid-column:\s*1;[\s\S]*?width:\s*5rem;[\s\S]*?height:\s*5rem;[\s\S]*?border-radius:\s*0\.5rem;/,
  );
  assert.doesNotMatch(css, /transform:\s*scale\(1\.22\);/);
  assert.match(
    readCssRules(css, ".prose .markdown-link-card-arrow"),
    /position:\s*absolute;[\s\S]*?right:\s*0\.85rem;[\s\S]*?bottom:\s*0\.8rem;/,
  );
  assert.doesNotMatch(
    readCssRules(css, ".prose .markdown-link-card.has-thumbnail-media .markdown-link-card-arrow"),
    /position:\s*static;/,
  );
  assert.match(publicRichLinkCard, /const isGithubProfile = preview\?\.card_type === "github_profile"/);
  assert.match(publicRichLinkCard, /const showExternalLink = !isGithubProfile/);
  assert.match(publicRichLinkCard, /is-github-profile/);
  assert.match(publicRichLinkCard, /showExternalLink \? \(/);
  assert.match(adminRichLinkCard, /const isGithubProfile = preview\?\.card_type === "github_profile"/);
  assert.match(adminRichLinkCard, /const showExternalLink = !isGithubProfile/);
  assert.match(adminRichLinkCard, /showExternalLink \? \(/);
  assert.match(adminRichLinkCard, /sm:h-20 sm:w-20/);
  assert.match(adminRichLinkCard, /grid-cols-\[4rem_minmax\(0,1fr\)\][^\"]*sm:grid-cols-\[5rem_minmax\(0,1fr\)\]/);
  assert.match(adminRichLinkCard, /grid-cols-\[4rem_minmax\(0,1fr\)\][^\"]*sm:grid-cols-\[5rem_minmax\(0,1fr\)\]/);
  assert.match(adminRichLinkCard, /col-start-1 row-start-1 h-16 w-16/);
  assert.match(adminRichLinkCard, /hasMediaImage \? "col-start-2 row-start-1/);
  assert.match(adminRichLinkCard, /absolute bottom-3\.5 right-3\.5/);
  assert.doesNotMatch(adminRichLinkCard, /col-start-3 row-start-1/);
  assert.match(
    readCssRules(css, ".prose .markdown-link-card.is-github-profile"),
    /grid-template-columns:\s*5rem minmax\(0, 1fr\);/,
  );
  assert.match(
    css,
    /@media \(max-width: 640px\) \{[\s\S]*?\.markdown-link-card\.is-github-profile\s*\{[\s\S]*?grid-template-columns:\s*4rem minmax\(0, 1fr\);/,
  );
  assert.match(
    css,
    /@media \(max-width: 640px\) \{[\s\S]*?\.markdown-link-card\.has-cover-media\s+\.markdown-link-card-media\s*\{[\s\S]*?width:\s*4rem;[\s\S]*?height:\s*4rem;/,
  );
  assert.match(
    readCssRules(css, ".prose .markdown-link-card.is-github-profile .markdown-link-card-media"),
    /grid-column:\s*1;[\s\S]*?width:\s*5rem;[\s\S]*?height:\s*5rem;/,
  );
});

test("rich-link thumbnail cropping stays associated with the image that was measured", () => {
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const adminPreview = readSource("admin/src/components/MarkdownPreview.tsx");
  const publicRichLinkCard = renderer.slice(
    renderer.indexOf("function MarkdownRichLinkCard"),
    renderer.indexOf("function MarkdownImage"),
  );
  const adminRichLinkCard = adminPreview.slice(
    adminPreview.indexOf("function MarkdownRichLinkCard"),
    adminPreview.indexOf("function MarkdownAnchor"),
  );

  for (const richLinkCard of [publicRichLinkCard, adminRichLinkCard]) {
    assert.match(richLinkCard, /const \[thumbnailCropImageUrl, setThumbnailCropImageUrl\] = useState<string \| null>\(null\)/);
    assert.match(richLinkCard, /const isNonSquareImage = thumbnailCropImageUrl === imageUrl/);
    assert.match(richLinkCard, /setThumbnailCropImageUrl\(isSquareImage\([^)]*\) \? null : imageUrl\)/);
    assert.doesNotMatch(richLinkCard, /setIsNonSquareImage\(false\)/);
  }
});

test("rich-link favicons do not inherit prose image spacing", () => {
  const css = readSource("frontend/src/components/markdown.css");

  assert.match(
    readCssRules(css, ".prose .markdown-link-card-favicon"),
    /display:\s*block;[\s\S]*?max-width:\s*none;[\s\S]*?margin:\s*0;/,
  );
});

test("mobile rich-link descriptions allow three lines", () => {
  const adminPreview = readSource("admin/src/components/MarkdownPreview.tsx");
  const css = readSource("frontend/src/components/markdown.css");

  assert.match(
    css,
    /@media \(max-width: 640px\) \{[\s\S]*?\.markdown-link-card\.has-cover-media\s+\.markdown-link-card-meta,[\s\S]*?\.markdown-link-card\.has-thumbnail-media\s+\.markdown-link-card-meta\s*\{[\s\S]*?-webkit-line-clamp:\s*3;/,
  );
  assert.match(adminPreview, /line-clamp-3[^\"]*sm:line-clamp-2/);
});

test("rich-link text rows stay grouped instead of stretching down the card", () => {
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const css = readSource("frontend/src/components/markdown.css");
  const publicRichLinkCard = renderer.slice(
    renderer.indexOf("function MarkdownRichLinkCard"),
    renderer.indexOf("function MarkdownImage"),
  );

  assert.match(
    publicRichLinkCard,
    /markdown-link-card-content[\s\S]*markdown-link-card-badge[\s\S]*markdown-link-card-title[\s\S]*markdown-link-card-meta/,
  );
  assert.match(
    readCssRules(css, ".prose .markdown-link-card.has-media .markdown-link-card-content"),
    /grid-column:\s*2;[\s\S]*?grid-row:\s*1;/,
  );
  assert.doesNotMatch(css, /grid-row:\s*1\s*\/\s*span\s*3;/);
});

test("compact rich links keep a readable site-name-to-title gap", () => {
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

  assert.match(
    readCssRules(css, ".prose .markdown-link-card.has-cover-media"),
    /grid-template-columns:\s*5rem\s+minmax\(0, 1fr\);/,
  );
  assert.match(
    readCssRules(css, ".prose .markdown-link-card.has-cover-media .markdown-link-card-content"),
    /row-gap:\s*0\.16rem;/,
  );
  assert.match(
    readCssRules(css, ".prose .markdown-link-card.has-thumbnail-media .markdown-link-card-content"),
    /row-gap:\s*0\.18rem;/,
  );
  assert.match(
    readCssRules(css, ".prose .markdown-link-card.has-compact-meta .markdown-link-card-content"),
    /row-gap:\s*0;/,
  );
  assert.match(
    readCssRules(css, ".prose .markdown-link-card.has-compact-meta .markdown-link-card-badge"),
    /margin-bottom:\s*0\.5rem;/,
  );
  assert.match(publicRichLinkCard, /const hasCompactMeta = cardMeta === fallbackMeta/);
  assert.match(publicRichLinkCard, /has-compact-meta/);
  assert.match(adminRichLinkCard, /const hasCompactMeta = cardMeta === fallbackMeta/);
  assert.match(adminRichLinkCard, /hasCompactMeta \? "mb-2 leading-tight" : "mb-1\.5"/);
});

test("rich-link image failures retain the existing fallback behavior", () => {
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");

  assert.match(renderer, /if \(imageState === "primary" && fallbackImageUrl\)/);
  assert.match(renderer, /setImageState\("fallback"\)/);
  assert.match(renderer, /setImageState\("hidden"\)/);
});
