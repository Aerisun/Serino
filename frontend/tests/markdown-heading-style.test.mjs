import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { test } from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const repoRoot = resolve(frontendRoot, "..");

const readSource = (path) => readFileSync(resolve(repoRoot, path), "utf8");

const extractHeadingTypographyBlock = (source) => {
  const marker = '"h1, h2, h3, h4": {';
  const start = source.indexOf(marker);
  assert.notEqual(start, -1, "heading typography block should exist");
  const end = source.indexOf("},", start);
  assert.notEqual(end, -1, "heading typography block should close");
  return source.slice(start, end + 2);
};

const extractTitleClassName = (source) => {
  const match = source.match(/<h1 className="([^"]+)">/);
  assert.notEqual(match, null, "detail title should render as h1 with a static className");
  return match[1];
};

const extractMarkdownHeadingFunction = (source) => {
  const start = source.indexOf("function MarkdownHeading");
  assert.notEqual(start, -1, "MarkdownHeading component should exist");
  const end = source.indexOf("function MarkdownPre", start);
  assert.notEqual(end, -1, "MarkdownHeading component should close before MarkdownPre");
  return source.slice(start, end);
};

const extractCssBlock = (source, selector) => {
  const marker = `${selector} {`;
  const start = source.indexOf(marker);
  assert.notEqual(start, -1, `${selector} block should exist`);
  const end = source.indexOf("}", start);
  assert.notEqual(end, -1, `${selector} block should close`);
  return source.slice(start, end + 1);
};

const extractHeadingNumberPattern = (source) => {
  const match = source.match(/const headingNumberPattern = \/(.+)\/u;/);
  assert.notEqual(match, null, "heading number regex should be declared as a unicode literal");
  return new RegExp(match[1], "u");
};

test("article markdown heading typography is upright and refined", () => {
  const tailwindConfig = readSource("frontend/tailwind.config.ts");
  const headingBlock = extractHeadingTypographyBlock(tailwindConfig);

  assert.doesNotMatch(headingBlock, /fontStyle:\s*"italic"/);
  assert.match(headingBlock, /fontStyle:\s*"normal"/);
  assert.match(headingBlock, /fontWeight:\s*"700"/);
  assert.match(headingBlock, /letterSpacing:\s*"0"/);
});

test("light mode markdown body copy is readable enough", () => {
  const tailwindConfig = readSource("frontend/tailwind.config.ts");

  assert.match(tailwindConfig, /"--tw-prose-body":\s*"hsl\(var\(--foreground\) \/ 0\.68\)"/);
});

test("markdown css protects headings from page-level italic styles", () => {
  const css = readSource("frontend/src/components/markdown.css");

  assert.match(css, /\.prose\s+:where\(h1,\s*h2,\s*h3,\s*h4,\s*h5,\s*h6\)\s*\{[\s\S]*font-style:\s*normal;/);
  assert.match(css, /\.prose\s+:where\(h1,\s*h2,\s*h3,\s*h4,\s*h5,\s*h6\)\s*\{[\s\S]*font-weight:\s*700;/);
});

test("numbered markdown headings separate section numbers from titles", () => {
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const css = readSource("frontend/src/components/markdown.css");
  const headingNumberPattern = extractHeadingNumberPattern(renderer);
  const numberedSamples = [
    ["2.", "2."],
    ["2. XXX", "2."],
    ["2.2", "2.2"],
    ["2.2 XXX", "2.2"],
    ["2.2.2", "2.2.2"],
    ["2.2.2 XXX", "2.2.2"],
    ["3.2邮箱配置", "3.2"],
  ];

  assert.match(renderer, /formatHeadingNumberSpacing/);
  assert.match(renderer, /value\.slice\(sectionNumber\.length\)\.replace\(\/\^\\s\+\/,\s*""\)/);
  assert.match(renderer, /markdown-heading-number/);
  assert.match(renderer, /MarkdownHeading/);
  assert.match(css, /\.prose\s+\.markdown-heading-number\s*\{[\s\S]*margin-inline-end:\s*0\.34em;/);

  for (const [sample, expectedNumber] of numberedSamples) {
    assert.equal(sample.match(headingNumberPattern)?.[1], expectedNumber);
  }
});

test("second-level markdown headings avoid blockquote-like left rails", () => {
  const renderer = readSource("frontend/src/components/MarkdownRenderer.tsx");
  const headingFunction = extractMarkdownHeadingFunction(renderer);
  const css = readSource("frontend/src/components/markdown.css");
  const h2Block = extractCssBlock(css, ".prose .markdown-heading--h2");

  assert.match(headingFunction, /markdown-heading--\$\{level\}/);
  assert.doesNotMatch(headingFunction, /border-l-2/);
  assert.doesNotMatch(headingFunction, /pl-3/);
  assert.match(h2Block, /border-bottom:/);
  assert.doesNotMatch(h2Block, /border-left/);
});

test("article detail titles match markdown h1 prominence", () => {
  const postTitleClassName = extractTitleClassName(readSource("frontend/src/pages/PostDetail.tsx"));
  const previewTitleClassName = extractTitleClassName(readSource("frontend/src/pages/Preview.tsx"));

  for (const className of [postTitleClassName, previewTitleClassName]) {
    const classes = new Set(className.split(/\s+/));

    assert.ok(classes.has("text-3xl"));
    assert.ok(classes.has("sm:text-4xl"));
    assert.ok(classes.has("font-bold"));
    assert.ok(classes.has("not-italic"));
    assert.ok(classes.has("tracking-normal"));
    assert.equal(classes.has("text-2xl"), false);
    assert.equal(classes.has("italic"), false);
    assert.equal(classes.has("tracking-tight"), false);
  }
});

test("markdown blockquotes do not add decorative quote marks", () => {
  const css = readSource("frontend/src/components/markdown.css");

  assert.match(css, /\.prose\s+blockquote\s*\{[\s\S]*quotes:\s*none;/);
  assert.match(css, /\.prose\s+blockquote\s+p:first-of-type::before,\s*[\s\S]*\.prose\s+blockquote\s+p:last-of-type::after\s*\{[\s\S]*content:\s*none;/);
});

test("markdown text links look clickable without affecting rich link cards", () => {
  const css = readSource("frontend/src/components/markdown.css");
  const linkSelector = ".prose :where(p, li, blockquote, td, th) a:not(.markdown-link-card):not(.markdown-footnote-ref-link):not(.markdown-footnote-backref)";

  assert.ok(css.includes(`${linkSelector} {`));
  assert.match(css, /text-decoration-line:\s*underline;/);
  assert.match(css, /text-underline-offset:\s*0\.18em;/);
  assert.match(css, /background-image:\s*linear-gradient/);
  assert.match(css, /transition:[\s\S]*text-decoration-color[\s\S]*background-size/);
  assert.ok(css.includes(`${linkSelector}:hover,`));
  assert.ok(css.includes(`${linkSelector}:focus-visible {`));
  assert.match(css, /background-size:\s*100%\s+0\.62em;/);
});

test("friends application markdown does not force italic headings", () => {
  const friendsPage = readSource("frontend/src/pages/Friends.tsx");

  assert.doesNotMatch(friendsPage, /prose-headings:italic/);
  assert.doesNotMatch(friendsPage, /prose-headings:font-semibold/);
  assert.match(friendsPage, /prose-headings:font-bold/);
});
