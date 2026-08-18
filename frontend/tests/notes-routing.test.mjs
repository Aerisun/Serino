import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import test from "node:test";
import { fileURLToPath } from "node:url";

const frontendRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const source = (path) => readFileSync(resolve(frontendRoot, "src", path), "utf8");

test("notes use an independent page instance while reusing article views and APIs", () => {
  assert.match(source("AppRuntime.tsx"), /<Route path="\/posts" element={<Posts key="manuscript" \/>} \/>/);
  assert.match(source("AppRuntime.tsx"), /<Route path="\/notes" element={<Posts key="note" kind="note" \/>} \/>/);
  assert.match(source("AppRuntime.tsx"), /<Route path="\/notes\/:id" element={<PostDetail kind="note" \/>} \/>/);
  assert.match(source("pages/Posts.tsx"), /readNotesApiV1SiteNotesGet/);
  assert.match(source("pages/PostDetail.tsx"), /useReadNoteApiV1SiteNotesSlugGet/);
  assert.match(source("lib\/route-preload.ts"), /prefetchNotesData/);
  assert.match(source("components\/CommentSection.tsx"), /contentType === "notes"/);
});

test("notes render as a compact poetic yearbook without cards", () => {
  const postsPage = source("pages/Posts.tsx");

  assert.match(postsPage, /const isNoteView = kind === "note";/);
  assert.match(postsPage, /data-note-yearbook/);
  assert.match(postsPage, /data-note-year/);
  assert.match(postsPage, /<CategoryFilter/);
  assert.match(postsPage, /data-note-date/);
  assert.match(postsPage, /formatDateInBeijing\(value, "en-US", \{ month: "short", day: "2-digit" \}\)/);
  assert.match(postsPage, /showSearch=\{!isNoteView\}/);
  assert.match(source("components/CategoryFilter.tsx"), /showSearch = true/);
  assert.match(postsPage, /font-heading text-\[1\.9rem\] italic leading-none tracking-\[0\.015em\][\s\S]*sm:text-\[2\.25rem\]/);
  assert.match(postsPage, /<div className="mt-5 sm:mt-6 space-y-1\.5 sm:space-y-2">/);
  assert.match(postsPage, /pl-1\.5 text-\[1\.4rem\][\s\S]*sm:pl-4 sm:text-\[1\.55rem\]/);
  assert.match(postsPage, /sm:text-\[1\.75rem\]/);
  assert.match(postsPage, /fontFamily: "'Pinyon Script', cursive"/);
  assert.match(postsPage, /label\.replace\(" ", "\\u00A0"\)/);
  assert.match(postsPage, /grid-cols-\[6rem_minmax\(0,1fr\)\] items-center gap-x-3/);
  assert.match(postsPage, /<h3 className="truncate min-w-0/);
  assert.doesNotMatch(postsPage, /grid-cols-1 gap-y-1\.5/);
  assert.doesNotMatch(postsPage, /data-note-card/);
  assert.doesNotMatch(postsPage, /divide-y/);
  assert.doesNotMatch(postsPage, /year:\s*"numeric"/);
  assert.doesNotMatch(postsPage, /lang === "zh" \? "手记" : "notes"/);
  assert.doesNotMatch(postsPage, /<header className="[^"]*border-b[^"]*">/);
});

test("notes hide their header count on mobile without leaving a spacer", () => {
  assert.match(
    source("pages/Posts.tsx"),
    /headerAsideClassName=\{isNoteView \? "hidden sm:flex" : ""\}/,
  );
  assert.match(source("components/PageShell.tsx"), /headerAsideClassName = "",/);
  assert.match(source("components/PageShell.tsx"), /\$\{headerAsideClassName\}/);
});

test("notes leave more space between filters and the year on mobile", () => {
  assert.match(
    source("pages/Posts.tsx"),
    /isNoteView \? "mt-10 sm:mt-9" : "mt-6 sm:mt-8"/,
  );
});
