# Markdown Image Attachments Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Give thought and excerpt editors a comment-style image attachment area while preserving Markdown storage and leaving other editors inline.

**Architecture:** `MarkdownEditor` gains an opt-in attachment mode. In that mode it parses Markdown image tokens into ordered attachments, shows them above the textarea, and serializes the text plus attachments back to the existing Markdown body. Thought and excerpt editors opt in; all other users retain inline Markdown images. The public excerpt modal reuses the existing image-aware Markdown renderer, while cards use stripped plain text.

**Tech Stack:** React, TypeScript, Vitest, react-markdown.

---

### Task 1: Add attachment-mode parsing and editing behavior

**Files:**
- Modify: `admin/src/components/MarkdownEditor.tsx`
- Modify: `admin/tests/markdown-editor.test.tsx`

**Step 1: Write failing tests**

Cover an attachment-mode editor that renders existing Markdown images as removable thumbnails, hides their Markdown tokens from the textarea, preserves text edits, and emits Markdown with the remaining attachments on removal.

**Step 2: Verify red**

Run: `pnpm --filter aerisun-admin test -- markdown-editor.test.tsx`

Expected: FAIL because the editor always writes image Markdown directly into the textarea.

**Step 3: Implement minimally**

Add `imageLayout="attachments" | "inline"` (default `inline`). Parse image tokens only in attachment mode, compose the controlled Markdown body from textarea text and ordered attachments, append uploads as attachments, and provide a comment-style thumbnail grid with remove buttons.

**Step 4: Verify green**

Run the focused test again. Expected: PASS.

### Task 2: Opt in thoughts and excerpts; render excerpts safely

**Files:**
- Modify: `admin/src/pages/thoughts/ThoughtEditPage.tsx`
- Modify: `admin/src/pages/excerpts/ExcerptEditPage.tsx`
- Modify: `frontend/src/pages/Excerpts.tsx`
- Modify: `frontend/tests/thought-markdown-images.test.mjs`

**Step 1: Write failing tests**

Assert only thought and excerpt editors opt in. Assert the public excerpt modal uses the shared image-aware renderer while its compact card excludes image Markdown from its text snippet.

**Step 2: Verify red**

Run focused admin and frontend tests. Expected: FAIL.

**Step 3: Implement minimally**

Pass `imageLayout="attachments"` only at the thought and excerpt call sites. Reuse `CommentMarkdownRenderer` in the excerpt modal, and derive a plain-text card snippet by removing Markdown image tokens.

**Step 4: Verify green**

Run focused tests. Expected: PASS.

### Task 3: Verify integration

**Files:** Verify only.

**Step 1:** Run `pnpm --filter aerisun-admin test`, `pnpm --filter aerisun-admin typecheck`, `pnpm --filter aerisun-admin lint`, `pnpm -C frontend typecheck`, and `pnpm -C frontend build`.

**Step 2:** Run `git diff --check` and inspect the scoped diff.
