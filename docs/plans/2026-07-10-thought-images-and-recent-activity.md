# Thought Images and Recent Activity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Render Markdown images in public thoughts with the existing comment image gallery, and protect public thought entries in the chronologically ordered recent-activity feed with regression tests.

**Architecture:** The thoughts page will reuse `CommentMarkdownRenderer`, which already extracts Markdown images into a three-column gallery and supplies the lightbox. Its image styles will move beside that renderer so they load wherever it is used. The recent-activity backend keeps its global timestamp ordering; a focused API test will verify that a newly published public thought is emitted with the expected type, excerpt, and anchor URL.

**Tech Stack:** React 19, TypeScript, Tailwind CSS, react-markdown, FastAPI, SQLAlchemy, pytest.

---

### Task 1: Cover public-thought activity ordering

**Files:**
- Modify: `backend/tests/public/test_activity.py`
- Modify: `backend/src/aerisun/domain/activity/repository.py` only if the test reveals a missing candidate or incorrect URL.

**Step 1: Write the failing test**

Create a public `ThoughtEntry` with a publication time newer than all seeded data. Request one recent activity item and assert it is `publish_thought`, contains a plain-text excerpt with Markdown images removed, and links to `/thoughts#<slug>`.

**Step 2: Run test to verify it fails**

Run: `uv run --directory backend pytest tests/public/test_activity.py -k thought -v`

Expected: a focused failure if public thought publication is omitted or not ordered by `published_at`.

**Step 3: Write minimal implementation**

Ensure `find_recent_published_content` returns public `ThoughtEntry` rows as `thought` candidates with a `/thoughts#{slug}` href; preserve the final timestamp sort and limit.

**Step 4: Run test to verify it passes**

Run: `uv run --directory backend pytest tests/public/test_activity.py -k thought -v`

Expected: PASS.

### Task 2: Reuse the comment Markdown image renderer on thoughts

**Files:**
- Modify: `frontend/src/pages/Thoughts.tsx`
- Modify: `frontend/src/components/CommentMarkdownRenderer.tsx`
- Create: `frontend/src/components/CommentMarkdownRenderer.css`
- Modify: `frontend/src/components/WalineSurface.css`

**Step 1: Write the failing test**

Add a frontend source-level regression test that asserts the thoughts page imports and renders `CommentMarkdownRenderer` for each thought body.

**Step 2: Run test to verify it fails**

Run the focused frontend test with the repository's test runner.

Expected: FAIL because thought bodies are currently rendered in a plain paragraph.

**Step 3: Write minimal implementation**

Replace the plain thought-body paragraph with `CommentMarkdownRenderer`, retaining the current typography classes. Move the shared gallery, thumbnail-button, and lightbox styles from `WalineSurface.css` into a stylesheet imported by `CommentMarkdownRenderer`, so gallery styling is available before comments are opened.

**Step 4: Run test to verify it passes**

Run the focused frontend test, then `pnpm -C frontend typecheck` and `pnpm -C frontend build`.

Expected: all commands pass.

### Task 3: Verify both surfaces together

**Files:**
- Verify only.

**Step 1: Run backend regression coverage**

Run: `uv run --directory backend pytest tests/public/test_activity.py -v`

Expected: PASS.

**Step 2: Run frontend static checks**

Run: `pnpm -C frontend typecheck && pnpm -C frontend build`

Expected: PASS.

**Step 3: Inspect the final diff**

Run: `git diff --check` and `git status --short`.

Expected: no whitespace errors and only the planned files changed.
